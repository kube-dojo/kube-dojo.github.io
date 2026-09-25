---
citations_verified: true
title: "Part 3 Cumulative Quiz: Services & Networking"
sidebar:
  order: 10
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 45-60 minutes
>
> **Prerequisites**: Module 3.1 Services Deep-Dive, Module 3.2 Endpoints & EndpointSlices, Module 3.3 DNS & CoreDNS, Module 3.4 Ingress, Module 3.5 Gateway API, Module 3.6 Network Policies, Module 3.7 CNI & Cluster Networking, Module 3.8 Cluster Networking Data Path
>
> **Kubernetes Version**: 1.35+

---

## Learning Outcomes

- **Evaluate** Service routing abstractions, EndpointSlice scalability mechanisms, and kube-proxy data-plane implementations across ClusterIP, NodePort, and LoadBalancer configurations.
- **Diagnose** CoreDNS resolution pipelines, ndots search path traversal, stub domains, and upstream forwarders for pod and Service fully qualified domain names.
- **Implement** declarative L7 traffic management using Ingress controllers and Gateway API resources including GatewayClass, Gateway, and HTTPRoute for path routing and TLS termination.
- **Enforce** pod network isolation and microsegmentation using NetworkPolicy specifications with podSelector, namespaceSelector, ipBlock, and explicit policyTypes for ingress and egress.
- **Troubleshoot** cluster networking data paths, container network interface (CNI) plugin IPAM and routing models, overlay encapsulations, and host iptables, nftables, or deprecated IPVS packet flows.

---

## Why This Module Matters

Kubernetes networking establishes the foundational communication plane that connects decoupled containerized microservices across dynamic distributed infrastructure. In the Certified Kubernetes Administrator examination, services and networking represent one of the most heavily weighted operational competencies, accounting for twenty percent of practical scoring. Candidates frequently memorize basic imperative commands, yet struggle when traffic drops silently due to misconfigured selectors, missing controller daemons, or unpermissive network policies. Mastering Part 3 requires synthesizing virtual IP translation, endpoint chunking, cluster DNS search traversal, layer-seven routing abstractions, microsegmentation boundaries, and kernel packet flows into an integrated mental model.

Hypothetical scenario: a platform engineering team deployed a multi-tenant payment gateway into a production Kubernetes cluster, exposing the application through an Ingress resource and securing it with NetworkPolicies. However, the engineers omitted a governing Ingress controller deployment and configured a NetworkPolicy with policyTypes set to Ingress without specifying any ingress rules, inadvertently isolating the pods from all ingress traffic. At the same time, client microservices attempting to communicate with external payment APIs generated overwhelming DNS traffic because an unoptimized ndots setting forced CoreDNS to traverse multiple internal cluster search domains before attempting external lookups. The resulting cascading timeout caused widespread transaction failures and customer checkout aborts across all regional nodes. Had the engineers validated controller reconciliation semantics, understood ndots query amplification, and implemented methodical network policy testing, the operational outage would have been completely prevented.

Operating resilient clusters requires diagnosing subtle behavioral boundaries across multiple network abstractions rather than relying on superficial command syntax. A failing network request may indicate an unready pod endpoint, an unassigned node port, an unsatisfied DNS search domain, or an iptables rule dropping packets at the host kernel level. When you understand how kube-proxy programs packet filtering chains and how CoreDNS processes plugins sequentially, troubleshooting shifts from anxious trial-and-error into methodical root-cause isolation. This diagnostic discipline ensures that you select safe, targeted remediation steps during high-severity production incidents.

The Certified Kubernetes Administrator examination evaluates your ability to resolve multi-component networking failure scenarios under strict time constraints. You will encounter practical tasks requiring rapid manifest generation using client dry runs, surgical patching of Service and Ingress specifications, precise implementation of NetworkPolicy ingress and egress rules, and CoreDNS ConfigMap troubleshooting. Developing automatic recall for declarative networking primitives allows you to focus mental energy on architectural constraints rather than basic tool navigation.

Senior infrastructure practitioners treat Kubernetes networking as an asynchronous, declarative state machine that translates high-level intent into low-level kernel rules. Controllers continuously reconcile API objects with host-level routing tables, packet filters, and reverse proxy configurations across every worker node. Cultivating a deep appreciation for endpoint chunking, search path mechanics, role-oriented routing models, and container network interfaces empowers you to build secure, scalable cloud-native platforms capable of sustaining heavy production traffic without degradation.

---

## Core Content: Service Architecture, EndpointSlices, and kube-proxy Modes

Kubernetes Services provide stable, persistent IP addresses and DNS hostnames that decouple transient container life cycles from dependent consumers. Because Pods are ephemeral artifacts assigned dynamic IP addresses upon creation, connecting clients directly to pod IPs creates severe operational fragility when pods restart or reschedule. A Service establishes an abstraction layer, allocating a virtual IP known as a ClusterIP from a dedicated service CIDR range configured on the API server. Traffic directed to a ClusterIP is intercepted and load-balanced transparently across matching backend pods without requiring external service registries.

Service routing behavior depends upon the declared Service type, which defines the scope of accessibility for exposed workloads. ClusterIP is the default type, exposing the Service exclusively on an internal cluster-scoped IP address accessible only from within worker nodes and running pods. NodePort extends ClusterIP by allocating a dedicated high port from the cluster-wide range between 30000 and 32767 on every worker node interface, allowing external clients to reach the service by contacting any node IP at that assigned port. LoadBalancer builds upon NodePort by interfacing with cloud provider control planes or bare-metal load balancer controllers to provision an external physical or virtual load balancer that routes public traffic directly to the allocated node ports. ExternalName differs fundamentally from other types by bypassing proxying entirely, creating a CoreDNS CNAME record that redirects in-cluster queries directly to an external fully qualified domain name.

The port configuration within a Service specification bridges external listener definitions with internal container network ports. The port field designates the network port exposed on the Service ClusterIP itself, representing the destination port that in-cluster clients connect to when issuing requests. The targetPort field designates the actual port on which the container process listens inside the pod network namespace; if omitted, targetPort defaults to the identical value declared in port. Kubernetes also supports named targetPorts, allowing application developers to change container listening ports across deployment revisions without requiring modifications to the governing Service specification.

Service traffic routing and source IP preservation are governed by traffic policy settings declared on the Service specification. By default, externalTrafficPolicy is set to Cluster, which instructs kube-proxy to balance incoming NodePort or LoadBalancer traffic evenly across all pods in the cluster, regardless of which node hosts the pods. While this ensures uniform workload distribution, it introduces an extra network hop when traffic lands on a node lacking local pods, and it performs Source Network Address Translation (SNAT), replacing the client's real IP with the node's IP. Setting externalTrafficPolicy to Local forces kube-proxy to forward external traffic exclusively to pods residing on the specific node that received the request, completely preserving the original client source IP and avoiding cross-node network hops, though nodes lacking local pods drop arriving traffic.

```text
+-------------------------------------------------------------------------+
|                  Service and EndpointSlice Packet Routing               |
|                                                                         |
|  Client Request --> [ ClusterIP: 10.96.10.50:80 ]                       |
|                             |                                           |
|                             v                                           |
|              [ EndpointSlice: web-svc-abcde ]                           |
|              +--------------------------------+                         |
|              | Pod A: 10.244.1.15:8080 (Ready)|                         |
|              | Pod B: 10.244.2.22:8080 (Ready)|                         |
|              +--------------------------------+                         |
|                             |                                           |
|           +-----------------+-----------------+                         |
|           v                                   v                         |
|  [ Pod A (Node 1) ]                  [ Pod B (Node 2) ]                 |
+-------------------------------------------------------------------------+
```

Historically, the Kubernetes control plane tracked backend pod addresses using a monolithic API object named Endpoints. For every Service with a label selector, an Endpoints object stored an unbounded list of IP addresses corresponding to all healthy pods matching that selector. In large-scale clusters running hundreds or thousands of replicas behind a single Service, this monolithic architecture created severe performance degradation. Whenever a single pod was created, terminated, or changed readiness status, the entire Endpoints object had to be serialized, written to etcd, and transmitted over the network to every kube-proxy instance across all worker nodes, generating massive etcd write amplification and saturating control plane bandwidth.

Kubernetes resolved this critical scaling bottleneck by introducing EndpointSlices, which partition backend endpoints into scalable chunks. By default, each EndpointSlice holds up to one hundred endpoints, ensuring that cluster scaling operations modify only a single slice rather than a monolithic object. When a Service exceeds one hundred endpoints, the EndpointSlice controller automatically provisions additional slice objects, keeping update payloads small and predictable. EndpointSlices also store rich metadata alongside endpoint addresses, including conditions indicating whether a pod is ready, serving, or terminating, as well as topology and zone hints used by modern traffic routing mechanisms.

The EndpointSlice mirroring controller copies user-created Endpoints into EndpointSlices for selectorless Services. That copy keeps those backends visible to kube-proxy when an older client still writes the Endpoints API. The controller does not copy EndpointSlices back into Endpoints objects. It skips an Endpoints object that sets the skip-mirror label, carries the control-plane leader annotation, has no Service, or belongs to a Service with a selector. Kubernetes has deprecated this mirror since version 1.33, so a new selectorless Service should create EndpointSlices directly. Selector-based Services still receive both objects, because the Endpoints controller and the EndpointSlice controller each write from Pod state. A normal Service therefore still appears when you run kubectl get endpoints. kube-proxy programs node forwarding rules from EndpointSlices.

On every worker node, the kube-proxy daemon translates Service virtual IPs and ports into actual pod backend addresses by programming host kernel networking rules. The operational performance and scalability of cluster networking depend heavily upon the active kube-proxy proxy mode. In earlier Kubernetes versions, kube-proxy operated in userspace mode, proxying connections through a user-space daemon process; this introduced severe context-switching overhead between user space and kernel space, leading to low throughput and high latency.

The standard iptables proxy mode replaces userspace proxying by programming Linux Netfilter chains directly inside the host kernel. When a client sends a packet to a Service ClusterIP, the kernel traverses custom iptables chains in the PREROUTING and OUTPUT tables, using probabilistic random matching rules to balance traffic across matching pod endpoints. While iptables mode operates entirely in kernel space with high packet processing speed, its sequential rule evaluation architecture scales poorly in clusters containing thousands of Services, because adding or removing a Service requires sequential rule rebuilding and table-wide mutex locks.

The IPVS (IP Virtual Server) proxy mode was built to address iptables scale limits by load balancing inside the Linux kernel with hash tables. A hash lookup stays close to constant time as the number of services grows, and IPVS offers algorithms beyond random selection, including round-robin, least connections, destination hashing, source hashing, and weighted shortest expected delay. On Kubernetes 1.35 this mode is deprecated. kube-proxy logs a warning when it starts in ipvs mode, and the project directs operators to nftables.

The nftables proxy mode is stable on Kubernetes 1.35. It graduated to general availability in 1.33 and programs the kernel nftables API, which requires Linux 5.13 or newer. When proxy mode is left unset, Linux kube-proxy still selects iptables, so an upgrade does not change the data plane unexpectedly. nftables updates Service rules without rebuilding one large iptables table, which is why the 1.35 IPVS deprecation notice names nftables as the mode to use instead. In every mode, kube-proxy watches Service and EndpointSlice objects and refreshes node forwarding rules from that watch.

Service session affinity allows cluster operators to direct repeated connections from a specific client to the identical backend pod. When sessionAffinity is configured as ClientIP within the Service specification, kube-proxy tracks client source IP addresses and establishes persistent affinity mapping for a configurable duration. This mechanism provides sticky session routing for stateful legacy protocols that require session persistence, though cloud-native architectures generally prefer stateless backend tiers or application-layer session management.

Headless Services are created by setting clusterIP to None, instructing the control plane to bypass virtual IP allocation entirely. Instead of providing load balancing through a single virtual address, a headless Service returns direct A-records for all matching pod IP addresses through CoreDNS. This configuration is indispensable for stateful workloads and distributed storage clusters that require direct pod-to-pod communication, custom client-side load balancing, or ordered peer discovery under StatefulSet supervision.

Topology-aware routing in modern Kubernetes optimizes network traffic efficiency by keeping traffic within the same availability zone where it originated. When service routing hints are enabled through the service.kubernetes.io/topology-mode annotation, the EndpointSlice controller annotates endpoints with zone hints, guiding kube-proxy to route requests to endpoints residing within the identical failure domain. This local routing reduces cross-zone data transfer costs and minimizes network latency across distributed multi-zone cloud infrastructure.

Internal traffic policy configuration allows cluster operators to restrict Service traffic originating from inside the cluster to local node endpoints. Setting internalTrafficPolicy to Local ensures that when a pod contacts an internal Service, kube-proxy routes traffic exclusively to pods running on the same node, eliminating cross-node network transit. If no local pods exist on that node, the connection fails immediately, making this setting ideal for node-local daemons such as logging agents or monitoring scrapers.

Service health check node ports provide external load balancers with reliable endpoint health detection when using local traffic policies. When externalTrafficPolicy is set to Local on a LoadBalancer Service, Kubernetes automatically allocates a healthCheckNodePort on every worker node. The cloud load balancer probes this port using HTTP; nodes running healthy local pods respond with HTTP status 200, while nodes without local pods return HTTP status 503, ensuring that external traffic is directed exclusively to nodes hosting active workloads.

---

## Core Content: Cluster DNS Architecture and CoreDNS Query Resolution

Cluster DNS provides automatic, declarative service discovery across Kubernetes workloads, enabling microservices to communicate using human-readable domain names rather than volatile IP addresses. The internal DNS infrastructure is powered by CoreDNS, a modular, plugin-based DNS server deployed as a high-availability Deployment inside the kube-system namespace. CoreDNS is exposed to the entire cluster through a dedicated ClusterIP Service named kube-dns, which is typically assigned a static IP address such as 10.96.0.10 from the service CIDR block during cluster initialization.

CoreDNS executes a flexible request processing pipeline configured through a centralized ConfigMap named coredns containing the Corefile. When a DNS query arrives, CoreDNS passes the request sequentially through configured plugins, each responsible for a distinct resolution responsibility. The errors plugin logs query errors, health exposes an HTTP health check endpoint, kubernetes resolves in-cluster Service and Pod domain names, forward routes non-cluster queries to upstream recursive nameservers, cache caches resolved responses in memory to reduce lookup latency, and loop detects recursive forwarding loops. Modifying the Corefile allows administrators to define custom stub domains, rewrite queries dynamically, or configure split-horizon DNS routing.

When a pod is scheduled onto a worker node, the local kubelet automatically injects DNS resolution settings into the container filesystem at /etc/resolv.conf. The generated file contains three critical configuration directives: nameserver, which points to the ClusterIP of the kube-dns Service; search, which declares an ordered list of search domains used to resolve unqualified hostnames; and options ndots:5, which establishes the threshold determining how the resolver handles domain names containing dots. Understanding how these directives interact is critical for preventing latency anomalies in production environments.

The search directive typically includes <namespace>.svc.cluster.local, svc.cluster.local, cluster.local, and any search domains inherited from the host worker node. When an application queries a short hostname such as database, the Linux resolver appends the first search domain, querying database.<namespace>.svc.cluster.local against CoreDNS. If that query returns an A-record, resolution completes immediately. If the query returns NXDOMAIN, the resolver proceeds down the search path list, querying database.svc.cluster.local and database.cluster.local sequentially before finally querying the bare hostname.

The ndots:5 option dictates how the client resolver handles domain names that already contain dots, such as external fully qualified domain names. The resolver counts the number of dots in the queried name; if the dot count is strictly less than the configured ndots value of five, the resolver prioritizes the search domains over an immediate absolute query. Because most public internet domain names contain fewer than five dots (for example, api.example.com has two dots, while github.com has one dot), the client resolver appends all internal cluster search paths first before attempting an absolute lookup against upstream servers.

**Pause and predict:** A pod configured with default DNS options in namespace production issues a DNS query for api.example.com under the standard ndots:5 configuration. Because the domain name contains only two dots, which search path is appended to form the first DNS query sent to CoreDNS?

<details>
<summary>Check your prediction</summary>

Because api.example.com contains only two dots, which is strictly less than the ndots:5 threshold, the resolver evaluates local search paths before attempting an absolute lookup, sending `api.example.com.production.svc.cluster.local` as its first query to CoreDNS.

</details>

Tuning client search paths and recognizing query amplification helps platform architects minimize CoreDNS query latency and prevent upstream recursive nameserver saturation during bursty microservice communication workloads. Resolving names efficiently stabilizes high-throughput distributed applications by eliminating redundant recursive lookups across infrastructure layers.

This default resolver behavior can trigger severe query amplification and latency degradation in clusters executing high volumes of external API calls. When a container attempts to resolve api.example.com, the resolver sends four consecutive queries to CoreDNS: api.example.com.production.svc.cluster.local, api.example.com.svc.cluster.local, api.example.com.cluster.local, and finally the bare name api.example.com. Each of the first three queries forces CoreDNS to evaluate its kubernetes plugin and return an NXDOMAIN response, consuming cluster network bandwidth and saturating CoreDNS CPU capacity.

Platform engineers employ multiple remediation strategies to mitigate ndots query amplification across production environments. The most immediate application-level solution is appending a trailing dot to external domain names in application configuration files, such as writing `api.example.com.`. The trailing dot explicitly signals to the Linux resolver that the name is fully qualified and absolute, instructing it to bypass search path evaluation completely and query CoreDNS for the bare name immediately.

At the pod specification level, engineers can customize resolver settings using the dnsConfig field under spec. By defining options with a lower ndots value, such as name: ndots and value: '2', any hostname containing two or more dots is queried as an absolute name first. However, lowering ndots requires caution: if an application queries an in-cluster service using a partial name like redis.backend (which contains one dot), setting ndots to 1 causes the resolver to query redis.backend externally first, failing resolution unless the full five-part name is used.

To solve DNS scalability cluster-wide, Kubernetes provides NodeLocal DNSCache, which runs a CoreDNS caching agent as a DaemonSet on every worker node. NodeLocal DNSCache binds a link-local IP address such as 169.254.20.10 on each node, and the kubelet is configured to inject this local IP as the primary nameserver in pod /etc/resolv.conf. Pods send DNS queries directly to the local node cache over loopback, avoiding network hops, bypassing Linux Netfilter conntrack race conditions associated with UDP port translation, and caching responses locally to protect central CoreDNS pods from query spikes.

CoreDNS generates predictable DNS record structures for all Kubernetes resources within the cluster domain. Standard Services receive an A-record or AAAA-record formatted as <service-name>.<namespace>.svc.<cluster-domain>, pointing to the virtual ClusterIP. CoreDNS also creates SRV records for named service ports, formatted as _<port-name>._<protocol>.<service-name>.<namespace>.svc.<cluster-domain>, enabling dynamic port discovery for distributed protocols without hardcoding numerical port values.

Headless Services, declared with clusterIP: None, alter CoreDNS resolution behavior fundamentally. Because no virtual ClusterIP is allocated, CoreDNS returns a set of A-records containing the direct IP addresses of all healthy backend pods matching the selector. When client applications query a headless Service name, CoreDNS returns all matching pod IPs in round-robin order, allowing clients to handle connection pooling or peer-to-peer clustering directly.

When headless Services are paired with StatefulSets, CoreDNS constructs individual, predictable A-records for every replica instance. Each ordinal pod receives a dedicated DNS record formatted as <pod-name>.<service-name>.<namespace>.svc.<cluster-domain>. For example, a pod named datastore-0 governed by a headless Service named db-headless in namespace prod resolves reliably at datastore-0.db-headless.prod.svc.cluster.local, guaranteeing immutable network identities across container restarts and rescheduling events.

Customizing upstream forwarding rules in the Corefile enables fine-grained integration with enterprise nameservers. Platform administrators configure custom server blocks inside the Corefile to direct corporate domains such as corp.internal to internal Active Directory DNS servers, while continuing to route public domain queries to cloud-provider recursive resolvers. These server blocks support connection retries, health checking, and TLS-encrypted DNS transport to safeguard sensitive corporate naming data.

Pod DNS policy configurations grant fine-grained control over how individual container sandboxes resolve domain names. Setting dnsPolicy to ClusterFirst instructs pods to query CoreDNS for all queries, forwarding external queries upstream through Corefile rules. In contrast, setting dnsPolicy to Default instructs pods to inherit the node host resolver configuration directly, bypassing CoreDNS entirely. For pods requiring custom resolution parameters without inheriting cluster defaults, setting dnsPolicy to None allows administrators to specify completely custom nameservers and search paths via dnsConfig.

Troubleshooting CoreDNS performance issues requires inspecting query logs, monitoring Prometheus metrics, and evaluating upstream network latency. CoreDNS exposes standard Prometheus metrics on port 9153, including coredns_dns_request_duration_seconds and coredns_dns_responses_total broken down by response code. When applications experience DNS timeouts, administrators analyze whether elevated latencies originate from CoreDNS internal plugin processing or slow upstream recursive resolvers.

---

## Core Content: Ingress Controllers and Gateway API Evolution

While Services operate primarily at the transport layer (Layer 4), modern web applications require application-layer (Layer 7) traffic routing capabilities, including HTTP path-based routing, virtual host multiplexing, SSL/TLS termination, and header manipulation. Exposing dozens of microservices individually using cloud LoadBalancer services is economically inefficient and operationally cumbersome, as each LoadBalancer provisions a dedicated cloud load balancer with associated cloud provider costs and public IP allocations. The Kubernetes Ingress API addresses these challenges by consolidating external HTTP and HTTPS routing behind a single entry point.

An Ingress resource is a declarative API object that defines routing rules mapping incoming HTTP request hostnames and URL paths to backend Kubernetes Services. However, an Ingress resource possesses no active networking capability on its own. The core Kubernetes control plane merely validates and stores Ingress manifests inside the etcd datastore; it does not configure reverse proxies, allocate external IP addresses, or route network traffic. To make an Ingress functional, a cluster must run an Ingress controller, an autonomous daemon that continuously watches the API server for Ingress events and configures data-plane reverse proxies accordingly.

Common Ingress controllers include ingress-nginx, Traefik, HAProxy, and Envoy-based implementations such as Contour and Emissary-ingress. When an Ingress controller detects a newly created or modified Ingress object, it parses the declared rules, validates the referenced backend Services and TLS Secrets, and updates its internal routing table dynamically. If the controller runs behind a cloud load balancer, it writes the provisioned public IP address or hostname into the .status.loadBalancer.ingress field of the Ingress resource, signalling to operators that external connectivity is established.

**Pause and predict:** An administrator creates an Ingress resource defining routing rules for an application in a cluster where no Ingress controller has been deployed. What object is created in the API datastore, and which field in the Ingress resource status remains empty?

<details>
<summary>Check your prediction</summary>

The Ingress API object itself is successfully accepted and stored in etcd by the kube-apiserver, but the `.status.loadBalancer.ingress` address field remains empty because no active Ingress controller exists to provision data-plane ingress gateways or populate external endpoints.

</details>

Understanding the division of responsibility between declarative control plane resource storage and autonomous controller daemons prevents administrators from assuming manifest syntax errors when missing gateway infrastructure is the true cause. System engineers verify both control plane object states and controller logs when troubleshooting unresponsive ingress endpoints.

To support multiple distinct Ingress implementations within a single cluster, Kubernetes provides the IngressClass resource. An IngressClass defines the specific controller implementation responsible for managing associated Ingress objects through its spec.controller field. Ingress manifests declare their intended controller by setting spec.ingressClassName. Alternatively, a cluster administrator can mark an IngressClass as the cluster default using the ingressclass.kubernetes.io/is-default-class: 'true' annotation, allowing Ingress objects that omit the class name to be claimed automatically by the default controller.

Ingress rules evaluate incoming request paths using three standardized path matching types defined in pathType. The Exact matching type matches the URL path strictly with case sensitivity, requiring an identical character-by-character match. The Prefix matching type matches URL paths based on URL path prefixes split by / delimiters, ensuring that a prefix of /app matches /app and /app/catalog, but does not match /application. The ImplementationSpecific matching type delegates path evaluation logic to the underlying Ingress controller, which may support regular expressions or custom wildcard matching.

TLS termination is declared under the spec.tls section of an Ingress manifest. The configuration references a Secret of type kubernetes.io/tls located within the same namespace, which must contain tls.crt and tls.key data entries. When configured, the Ingress controller terminates incoming TLS handshakes using the provided certificate, decrypts incoming traffic, and forwards cleartext HTTP requests to backend Services over the internal cluster network.

```text
+-------------------------------------------------------------------------+
|                  Gateway API Role-Oriented Architecture                 |
|                                                                         |
|  [ Infra Provider ]  --> GatewayClass (Defines controller, e.g. Envoy)  |
|                                |                                        |
|  [ Cluster Operator ] --> Gateway (Listeners, IP, TLS Certs, Ports)     |
|                                |                                        |
|  [ App Developer ]   --> HTTPRoute (Path rules, header filters, rewrites)|
|                                |                                        |
|                                v                                        |
|                      [ Backend Service / Pods ]                         |
+-------------------------------------------------------------------------+
```

Despite its widespread adoption, the Ingress API has significant architectural limitations that hinder advanced platform operations. The Ingress specification is monolithic, forcing cluster infrastructure settings, domain names, TLS certificates, and fine-grained application routing rules into a single configuration file. This tightly coupled design creates severe role friction: platform operators managing ingress infrastructure must either grant application developers write access to shared Ingress files or manually approve every path change. Furthermore, advanced routing features such as canary weighting, header-based routing, traffic mirroring, and URL rewrites were never standardized in the Ingress specification, forcing vendors to rely on brittle, non-portable annotations.

The Gateway API represents the next-generation evolution of service networking in Kubernetes, completely redesigning layer-four through layer-seven routing around a role-oriented, expressive, and extensible resource model. Rather than forcing all routing concerns into a single object, Gateway API divides configuration responsibilities across three distinct personas: the Infrastructure Provider, the Cluster Operator, and the Application Developer. This separation allows multi-tenant organizations to establish clear operational boundaries and enforce least-privilege administrative access.

The Infrastructure Provider manages the GatewayClass resource, which defines the underlying routing controller implementation, such as an Envoy-based proxy fleet, a hardware load balancer, or a cloud provider managed gateway service. The Cluster Operator creates and manages Gateway resources, which define physical or virtual points of data-plane ingress. A Gateway specifies listening ports, supported network protocols (HTTP, HTTPS, TCP, TLS, UDP), TLS certificates, and address allocations, while establishing policies governing which routes are permitted to attach to its listeners.

The Application Developer defines routing rules using route resources such as HTTPRoute, GRPCRoute, TCPRoute, and TLSRoute. An HTTPRoute declares path matching rules, header filtering, request redirects, URL rewrites, and traffic weighting across backend Services, attaching to parent Gateways through parentRefs. Because HTTPRoutes exist independently of Gateways, development teams can safely manage application routing in their own namespaces without possessing permissions to modify core Gateway infrastructure or view shared TLS certificates.

An HTTPRoute attaches to a Gateway in another namespace only when that Gateway listener allows the attachment through allowedRoutes. If allowedRoutes is omitted, the listener accepts routes from the same namespace as the Gateway. The cluster operator sets allowedRoutes.namespaces.from to All, or to Selector with a namespace label, when teams in other namespaces should attach. ReferenceGrant does not make that attachment decision. A ReferenceGrant lives in the namespace that owns the target object, and it permits a route in another namespace to reference a backend Service there. A Gateway that reads a TLS Secret from another namespace also needs a ReferenceGrant in the Secret namespace. Explaining a rejected parentRef as a missing ReferenceGrant hides the listener policy that accepts or rejects the route.

Gateway API also introduces native support for sophisticated traffic splitting and canary deployments directly within the core specification. Using the weight field under backendRefs in an HTTPRoute, developers specify integer percentages to distribute traffic between stable and canary application deployments without requiring custom annotations or service mesh sidecars. The underlying gateway implementation programs its data plane to enforce the configured traffic distribution deterministically.

Header-based routing and request modification capabilities are built directly into Gateway API route rules without relying on vendor annotations. Developers configure HTTPRoute filters to add custom tracking headers, strip sensitive incoming cookies, rewrite URL request prefixes, or redirect HTTP requests to secure HTTPS endpoints. These declarative filtering capabilities ensure portability across disparate gateway implementations without locking platform teams into proprietary controller syntaxes.

Status reporting in Gateway API provides unprecedented visibility into route attachment health and configuration validation. Gateways and HTTPRoutes expose detailed Condition arrays in their status subresources, indicating whether listeners are programmed, certificates are valid, and routes are accepted by parent gateways. This structured status reporting enables continuous delivery pipelines and GitOps engines to verify routing convergence automatically without inspecting proxy pod logs.

---

## Core Content: NetworkPolicy Microsegmentation and CNI Data Path Architecture

The fundamental Kubernetes networking model enforces a flat, non-isolated communication plane where every pod can communicate with every other pod across all cluster nodes without network address translation. While this open model simplifies application deployment and eliminates complex port-forwarding requirements, it presents severe security risks in enterprise multi-tenant environments. Without explicit boundaries, a compromised web frontend container can communicate directly with private backend databases, internal cache clusters, or node management daemons across namespace boundaries.

Kubernetes enforces network microsegmentation through declarative NetworkPolicy resources, which function as layer-three and layer-four stateful firewalls for container workloads. NetworkPolicies allow cluster administrators to specify exactly which network sources can communicate with selected pods, and which external destinations selected pods can contact. By default, pods in Kubernetes are non-isolated, meaning all incoming and outgoing connections are permitted. The moment a NetworkPolicy's podSelector matches a pod, that pod transitions into an isolated state for the directions specified in policyTypes.

A critical architectural prerequisite for network security is that NetworkPolicies require an active Container Network Interface (CNI) plugin with policy enforcement capabilities. The Kubernetes API server merely validates and stores NetworkPolicy manifests; the core control plane contains no built-in firewall enforcement mechanism. If a cluster utilizes a basic CNI plugin such as standard Flannel that provides only IP encapsulation without a policy engine, applied NetworkPolicy manifests are silently accepted by etcd but completely ignored in the data plane. Advanced CNI plugins such as Calico, Cilium, and Kube-router include integrated policy agents that program Linux Netfilter (iptables/ipset) or eBPF programs on every worker node to enforce declared rules.

NetworkPolicy manifests define traffic boundaries using three primary specification blocks: podSelector, policyTypes, and directional rule blocks named ingress and egress. The podSelector identifies the group of pods within the policy's namespace to which the firewall constraints apply; setting podSelector: {} selects every pod residing in that namespace. The policyTypes array declares whether the policy governs inbound traffic (Ingress), outbound traffic (Egress), or both. If policyTypes is omitted, Kubernetes infers Ingress by default, and automatically adds Egress if any egress rules are present.

**Pause and predict:** A security engineer creates a NetworkPolicy selecting database pods with policyTypes set to Ingress, but leaves the ingress rule array completely empty. What is the resulting network traffic posture for incoming connections to the selected pods?

<details>
<summary>Check your prediction</summary>

Incoming network traffic is completely blocked. When policyTypes includes Ingress without defining any ingress rules, the policy enforces a default-deny ingress posture for all selected pods, isolating them from all inbound connections including peer pods within the same namespace.

</details>

Establishing a strict baseline zero-trust posture guarantees that sensitive microservices remain protected against unintended lateral movement until explicit, audited ingress and egress allow rules are systematically introduced into cluster environments. Security teams use this default isolation mechanism to comply with rigorous multi-tenant data protection standards.

Ingress rules specify allowed traffic sources within the from block, while egress rules specify allowed traffic destinations within the to block. NetworkPolicy rules operate as a pure allow-list: there are no explicit deny rules in standard Kubernetes NetworkPolicies. Any packet arriving at an isolated pod is evaluated against all active allow rules; if at least one rule permits the traffic, the packet is accepted, whereas packets failing to match any rule are dropped silently. An empty from list is a different form from an empty ingress array. On a rule, a missing or empty from field matches every source, including other namespaces and addresses outside the cluster. The default-deny form is an empty ingress array, written as ingress: [], which selects no allow rules.

Understanding the boolean logic of selector combinations within from and to blocks is essential for writing accurate policies. When multiple selectors are defined inside a single array element, they are evaluated as a logical AND condition. For example, declaring namespaceSelector and podSelector within the same list item restricts traffic strictly to pods that have the specified pod label AND reside within a namespace that has the specified namespace label. Conversely, defining selectors across separate array items creates a logical OR condition. A podSelector inside from, with no namespaceSelector beside it, selects pods in the policy's own namespace only. A separate namespaceSelector item permits pods in namespaces that carry the namespace label. The two items together allow either of those peer sets. They do not select the labeled pods in every namespace.

```text
+-------------------------------------------------------------------------+
|                  NetworkPolicy AND vs OR Evaluation Logic               |
|                                                                         |
|  [ Logical AND: Single List Element ]                                   |
|  - namespaceSelector: { matchLabels: { team: engineering } }            |
|    podSelector:       { matchLabels: { app: web } }                     |
|    --> Traffic allowed ONLY if BOTH namespace AND pod labels match.     |
|                                                                         |
|  [ Logical OR: Multiple List Elements ]                                 |
|  - namespaceSelector: { matchLabels: { team: engineering } }            |
|  - podSelector:       { matchLabels: { app: web } }                     |
|    --> OR: namespace match, or a pod in this policy namespace.          |
+-------------------------------------------------------------------------+
```

NetworkPolicies also support IP-based filtering through the ipBlock selector, which allows or restricts traffic based on CIDR network ranges. The ipBlock definition includes a cidr block defining the allowed network range, and an optional except array specifying sub-ranges to exclude from that block. Administrators commonly use ipBlock in egress policies to permit outbound connections to corporate subnets or public cloud services while excluding internal cluster ranges.

A frequent operational failure when implementing egress isolation involves cluster DNS disruption. When an administrator enables policyTypes: ['Egress'] on a pod, the pod immediately drops all outbound connections that are not explicitly permitted. Because CoreDNS runs inside the cluster and handles hostname resolution, isolating egress without creating an explicit allow rule for CoreDNS causes all DNS lookups to fail immediately, breaking database connections and external API calls. Hardened egress policies must always include a rule permitting UDP and TCP traffic on port 53 targeting the kube-dns Service or the kube-system namespace.

Underneath NetworkPolicies and Services lies the Container Network Interface (CNI) data path, which establishes the physical and virtual packet transport across worker nodes. When the kubelet creates a pod sandbox, it invokes CNI plugins to allocate IP addresses (via IPAM plugins such as host-local) and attach virtual ethernet (veth) interface pairs. One end of the veth pair resides inside the pod network namespace as eth0, while the peer end attaches to the host network namespace, connecting to a Linux bridge, an Open vSwitch datapath, or directly to host routing tables.

In overlay networking architectures, such as standard VXLAN or Geneve implementations, cross-node pod traffic is encapsulated inside outer host UDP packets. When Pod A on Node 1 communicates with Pod B on Node 2, the local CNI routing agent encapsulates the inner IP frame within a VXLAN packet (destination UDP port 4789 or 8472) and transmits it across the physical underlay network to Node 2. Node 2 decapsulates the packet and delivers the inner frame to Pod B's veth interface. While overlay networking allows clusters to operate seamlessly across heterogeneous physical networks without requiring route propagation, the outer encapsulation header adds 50 bytes of overhead, requiring administrators to reduce container MTU (typically to 1450 bytes) to prevent packet fragmentation.

In contrast, native routing architectures, such as Calico with BGP or cloud-native VPC plugins (AWS VPC CNI, Azure CNI, Google GKE CNI), assign pod IP addresses directly from underlying VPC subnets or distribute pod routes via BGP peering across physical routers. In native routing, pods communicate directly across nodes without encapsulation overhead, achieving line-rate network performance and native integration with cloud security groups, at the cost of consuming larger allocations of underlying subnet IP addresses. Modern eBPF-based CNIs like Cilium bypass iptables entirely, running eBPF bytecode programs attached directly to Linux kernel socket buffers, providing ultra-low-latency packet routing, transparent mutual TLS encryption, and granular observability.

Network troubleshooting in containerized environments requires inspecting packet flow across both host and container network namespaces. Platform administrators execute packet captures using tools like tcpdump inside container namespaces using ephemeral debugging containers or by entering container network namespaces via nsenter. Analyzing packet drops at iptables chains, observing conntrack table exhaustion, and monitoring CNI agent logs enables rapid isolation of performance bottlenecks across complex multi-cloud clusters.

Advanced CNI plugins provide application-layer network policies that extend filtering capabilities up to Layer 7. While standard Kubernetes NetworkPolicies evaluate only IP addresses and transport protocol ports, tools like Cilium and Calico can parse HTTP headers, methods, and paths directly at the kernel or proxy level. This capability enables operators to enforce granular authorization rules, such as permitting HTTP GET requests to public catalog endpoints while blocking POST or DELETE methods from untrusted client pods.

Securing pod-to-pod communications across untrusted intermediate physical networks frequently requires automated network encryption. Modern CNI implementations integrate transparent encryption using WireGuard or IPsec kernel modules, encrypting all cross-node overlay or native traffic automatically without requiring application code changes or service mesh sidecar proxies. This transparent encryption guarantees data privacy and prevents packet eavesdropping across heterogeneous bare-metal or multi-cloud network topologies.

---

## Did You Know?

- **Fact 1**: [EndpointSlices split backend endpoints into chunks](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) of up to 100 endpoints by default, eliminating the severe etcd serialization and network broadcast bottlenecks caused by monolithic Endpoints objects in large-scale clusters.
- **Fact 2**: [Default Linux DNS client configuration specifies ndots:5](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/) inside container `/etc/resolv.conf`, which forces queries for external domain names with fewer than five dots to traverse local search paths first unless a trailing dot is appended to make the query absolute.
- **Fact 3**: [Flannel provides basic CNI overlay networking](https://kubernetes.io/docs/concepts/cluster-administration/networking/) but lacks a policy enforcement engine, meaning NetworkPolicy resources applied to clusters running standard Flannel are silently ignored without raising admission errors unless an auxiliary policy agent such as Calico is installed.
- **Fact 4**: [Gateway API decouples routing configurations](https://kubernetes.io/docs/concepts/services-networking/gateway/) into role-oriented resources, enabling infrastructure teams to manage Gateway listeners and IP allocations independently while granting application teams autonomous control over HTTPRoute rules without cross-tenant configuration conflicts.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Deploying Ingress resources without an Ingress controller installed | The Ingress API object is accepted by etcd, but the address status stays blank and no data-plane routing ever occurs | Always ensure an Ingress controller daemon is active and healthy before exposing services through Ingress |
| Assuming `from:` with separate `namespaceSelector` and `podSelector` acts as an AND filter | Separate array elements under `from` are evaluated as a logical OR, granting unintended access to unexpected workloads | Combine `namespaceSelector` and `podSelector` within a single `from` item when an AND condition is required |
| Omitting port 53 UDP and TCP egress rules when applying egress policies | Workload pods become unable to contact CoreDNS, breaking all in-cluster and external domain name resolution | Always include an explicit egress rule allowing traffic to port 53 on kube-dns when restricting egress traffic |
| Calling external FQDNs without trailing dots under default `ndots:5` configurations | The client traverses every internal search domain sequentially before querying upstream, causing CoreDNS query spikes | Append a trailing dot (`api.example.com.`) in application configurations or tune `ndots` in pod `dnsConfig` |
| Setting `externalTrafficPolicy: Local` on nodes that lack local workload pods | External traffic arriving at worker nodes without matching pods is dropped, causing intermittent client connection failures | Use `Cluster` policy unless client IP preservation is strictly required, or ensure workloads run across all ingress nodes |
| Creating a headless Service without configuring matching `subdomain` and `hostname` on pods | CoreDNS fails to generate individual A-records for ordinal pods, breaking peer discovery in distributed stateful applications | Ensure pod specs explicitly define `hostname` and `subdomain` matching the headless Service name |
| Expecting standard Flannel CNI to enforce NetworkPolicy resources | Flannel manages pod IP encapsulation but lacks a policy engine, silently leaving all network traffic unrestricted | Deploy a CNI with native policy enforcement like Calico or Cilium, or install Canal to enforce network security rules |
| Assuming `ingress: []` allows all traffic instead of acting as a default-deny rule | An empty rule list means no sources are permitted, isolating the selected pods from all incoming network connections | Use `ingress: [{}]` to allow all incoming traffic, or define explicit selector rules for permitted callers |

---

## Quiz

Answer these scenario-based questions without referring to earlier modules. After each answer, compare your reasoning with the explanation, not just the final command. The goal is to prove that you can choose safe actions under realistic exam constraints.

### 1. Service Types and Traffic Policy Configuration

An operations team deploys a web service exposed through a NodePort Service on port 30080. When inspecting backend access logs, the security team notices that incoming HTTP requests all appear to originate from node internal IP addresses rather than real client IP addresses. Additionally, traffic is evenly distributed across all nodes regardless of where pod replicas run. The team requires preserving the original client source IP address and eliminating extra network hops between cluster nodes. Which configuration change satisfies both requirements?

1. Set `externalTrafficPolicy: Local` in the Service specification.
2. Change the Service type from NodePort to ClusterIP and configure sessionAffinity as ClientIP.
3. Set `internalTrafficPolicy: Local` and configure an explicit nodePort value on the Service.
4. Set `publishNotReadyAddresses: true` in the Service specification.

<details>
<summary>Answer</summary>

Option 1 is correct because configuring `externalTrafficPolicy: Local` instructs kube-proxy to route external traffic only to local endpoints on the node receiving the request, preserving the original client IP without performing SNAT and preventing extra network hops to other nodes. Option 2 is wrong because ClusterIP services are not directly accessible from outside the cluster, and sessionAffinity only pins requests to backends without preserving source IP or preventing cross-node proxy hops. Option 3 is incorrect because internalTrafficPolicy governs traffic originating from within the cluster rather than external traffic arriving through node ports. Option 4 is not correct because publishNotReadyAddresses only affects whether unready pod IPs appear in EndpointSlices and has no effect on client source IP preservation or traffic policy routing.

</details>

### 2. EndpointSlice Scalability and Mirroring Architecture

A high-traffic microservice scales up to 1,500 active pod replicas during peak load events. The cluster administrator notices that updating pod configurations in earlier Kubernetes versions caused severe etcd write latency and network saturation across all worker nodes running kube-proxy. Which architectural mechanism in modern Kubernetes resolves this scaling bottleneck?

1. EndpointSlice objects group backend endpoints into chunks of up to 100 endpoints by default, limiting the payload size of individual updates sent across the cluster.
2. The kube-scheduler writes pod network routes directly into worker node routing tables, completely bypassing etcd and kube-proxy.
3. The Service controller converts all ClusterIP services into headless services when replica counts exceed 500 pods.
4. Kubernetes deploys dedicated CoreDNS pods for each microservice replica to handle client-side load balancing.

<details>
<summary>Answer</summary>

Option 1 is correct because EndpointSlices partition endpoints into manageable subsets (defaulting to 100 endpoints per slice), ensuring that adding or modifying an endpoint modifies only a small individual object rather than serializing and broadcasting an enormous monolithic Endpoints resource across all nodes. Option 2 is wrong because the kube-scheduler is responsible for node placement decisions and never modifies node routing tables or manages Service proxying. Option 3 is incorrect because the Service controller never mutates Service types dynamically based on replica counts. Option 4 is not correct because CoreDNS provides cluster name resolution rather than dedicated per-replica client proxying, and scaling pods does not spawn dedicated DNS servers.

</details>

### 3. CoreDNS Resolution Pipelines and ndots Search Traversal

A microservice running in the `payments` namespace issues high volumes of HTTPS requests to an external API at `api.stripe.com`. Monitoring dashboards reveal that CoreDNS pods are consuming excessive CPU and reporting elevated latencies due to millions of NXDOMAIN responses. Inspecting the application pod shows default DNS settings with `ndots:5`. What is the primary cause of the excessive CoreDNS queries, and how can the platform team eliminate the unnecessary lookup overhead?

1. The resolver queries `api.stripe.com` with internal search domains appended before attempting an external lookup; appending a trailing dot (`api.stripe.com.`) causes immediate absolute resolution.
2. The Corefile is missing a forward plugin pointing to public root DNS servers, causing recursive query loops.
3. The pod lacks an egress NetworkPolicy allowing port 53 UDP traffic, forcing CoreDNS to retry queries five times.
4. CoreDNS cannot resolve domain names with fewer than three dots unless NodeLocal DNSCache is deployed on every node.

<details>
<summary>Answer</summary>

Option 1 is correct because under `ndots:5`, any hostname containing fewer than five dots is first appended with local search paths (`payments.svc.cluster.local`, `svc.cluster.local`, `cluster.local`), producing multiple NXDOMAIN queries before querying the absolute name; appending a trailing dot marks the name as absolute, bypassing internal search paths completely. Option 2 is wrong because missing forward plugins would result in SERVFAIL errors rather than NXDOMAIN responses for search-suffixed internal domains. Option 3 is incorrect because a missing egress NetworkPolicy would drop packets entirely at the network layer rather than generating CoreDNS query metrics and NXDOMAIN logs. Option 4 is not correct because CoreDNS resolves names with any number of dots; the ndots setting is a client-side resolver behavior defined in glibc/musl, not a CoreDNS restriction.

</details>

### 4. Ingress Controller Reconciler and Resource Status

An engineer deploys an Ingress manifest defining host-based routing rules for `web.example.com` targeting a backend Service. Running `kubectl get ingress` reveals that the `ADDRESS` column remains empty for over fifteen minutes, and external clients cannot reach the application. Running `kubectl describe ingress` shows no warnings or events. What is the most likely root cause of this behavior?

1. No Ingress controller is running in the cluster to watch the Ingress resource, provision data-plane routing, and report the gateway address.
2. The target Service is configured as ClusterIP, but Ingress resources require the backend Service type to be NodePort or LoadBalancer.
3. The Ingress manifest omitted the `metadata.namespace` field, causing the API server to reject controller reconciliation.
4. Ingress resources require an explicit TLS secret reference before the control plane allocates an external IP address.

<details>
<summary>Answer</summary>

Option 1 is correct because an Ingress resource is merely a declarative configuration document in etcd; without an active Ingress controller watching the API and configuring reverse proxies, no traffic routing occurs and the `.status.loadBalancer.ingress` address field remains unpopulated. Option 2 is wrong because Ingress controllers route traffic directly to ClusterIP Service endpoints or pod IPs, so NodePort or LoadBalancer service types are not required. Option 3 is incorrect because omitting the namespace in a manifest simply defaults the object to the active or default namespace rather than suppressing reconciliation. Option 4 is not correct because Ingress resources support plain HTTP routing and do not require TLS configuration to receive an address.

</details>

### 5. Gateway API Resource Hierarchy and Cross-Namespace Routing

An organization migrates from traditional Ingress to the Gateway API. The platform infrastructure team creates a `Gateway` named `prod-gateway` in the `infra` namespace. An application team deploys an `HTTPRoute` in the `apps` namespace attempting to attach to `prod-gateway`. When applying the route, the HTTPRoute status reports that the parent reference is not accepted due to cross-namespace routing restrictions. Which configuration permits this attachment?

1. Set `allowedRoutes` on the `prod-gateway` listener so HTTPRoutes from the `apps` namespace may attach, for example `namespaces.from: All` or a namespace selector that matches `apps`.
2. Create a `ReferenceGrant` in the `infra` namespace that permits HTTPRoutes from `apps` to reference the Gateway.
3. An `IngressClass` resource configured with `is-default-class: "true"` in the `apps` namespace.
4. A `NetworkPolicy` in namespace `infra` allowing ingress traffic from pods in namespace `apps`.

<details>
<summary>Answer</summary>

Option 1 is correct because an HTTPRoute attaches to a Gateway in another namespace only when that Gateway listener's `allowedRoutes` permits the route namespace. Omitting `allowedRoutes` leaves the listener limited to the Gateway namespace, so the `apps` route stays unaccepted until the listener allows it. Option 2 is wrong because a `ReferenceGrant` authorizes a cross-namespace reference to a backend Service, and it belongs in the Service namespace. It does not accept a parent Gateway attachment. Option 3 is incorrect because IngressClass is part of the legacy Ingress API and has no role in Gateway API parent-route attachment validation. Option 4 is not correct because NetworkPolicies govern layer 3/4 packet forwarding between pods and do not control Gateway API route attachment acceptance.

</details>

### 6. NetworkPolicy Ingress Combinator Logic and Default Deny

A security engineer needs to secure a sensitive database pod with label `role: db` in namespace `production`. The pod must accept incoming TCP connections on port 5432 exclusively from frontend pods that possess the label `app: web` AND reside within namespaces labeled `team: engineering`. Which `NetworkPolicy` ingress configuration correctly implements this strict AND condition?

1. Under `ingress[0].from[0]`, declare both `namespaceSelector` matching `team: engineering` and `podSelector` matching `app: web` in the same list item.
2. Under `ingress[0].from`, define one list item with `namespaceSelector` matching `team: engineering` and a second list item with `podSelector` matching `app: web`.
3. Configure `policyTypes: ["Ingress"]` and leave the `ingress` block empty to let the CNI infer the labels automatically.
4. Declare `podSelector: {matchLabels: {role: db}}` and set `from: []` with port 5432.

<details>
<summary>Answer</summary>

Option 1 is correct because placing both `namespaceSelector` and `podSelector` inside the same element of the `from` array creates a logical AND condition, restricting traffic strictly to pods matching `app: web` inside namespaces labeled `team: engineering`. Option 2 is wrong because separate `from` items are a logical OR: every pod in a `team: engineering` namespace, or any pod labeled `app: web` in the policy's own namespace. That podSelector does not reach other namespaces. Option 3 is incorrect because an empty ingress block creates a default-deny rule that drops all incoming traffic without permitting the required frontend connections. Option 4 is not correct because an empty `from` list matches every source, so port 5432 would be open to all pods and to clients outside the cluster. An empty `ingress` list denies traffic. An empty `from` list does not.

</details>

### 7. NetworkPolicy Egress Lockdown and CoreDNS Disruption

An administrator applies a hardening `NetworkPolicy` to a namespace with `policyTypes: ["Egress"]`. The policy includes an egress rule allowing outbound HTTPS traffic (TCP port 443) to `0.0.0.0/0` via an `ipBlock`. Immediately after applying the policy, applications in the namespace experience total network failure, reporting that hostnames such as `payment-service` and `database.internal` cannot be resolved. What is the root cause of this failure?

1. Setting `policyTypes: ["Egress"]` isolated the pods for egress, blocking outbound UDP and TCP traffic to CoreDNS on port 53 because no egress rule permitted cluster DNS.
2. The `ipBlock` specification of `0.0.0.0/0` automatically disables internal cluster routing rules in the host iptables chains.
3. The CNI plugin crashed because egress policies cannot be evaluated concurrently with layer 4 port restrictions.
4. Kubernetes requires all egress policies to specify `ports: [{protocol: TCP, port: 80}]` before enabling HTTPS traffic.

<details>
<summary>Answer</summary>

Option 1 is correct because once a pod is selected by a policy that specifies `policyTypes: ["Egress"]`, all egress traffic not explicitly allowed is blocked; because DNS resolution requires outbound communication to CoreDNS on port 53 (UDP and TCP), omitting an egress rule for port 53 prevents pods from resolving any domain names. Option 2 is wrong because ipBlock defines CIDR ranges for packet filtering and does not corrupt or disable cluster iptables routing. Option 3 is incorrect because standard CNI plugins like Calico and Cilium fully support layer 4 port matching in egress policies without crashing. Option 4 is not correct because Kubernetes imposes no requirement to allow HTTP port 80 when allowing HTTPS port 443.

</details>

### 8. CNI Overlay Encapsulation and MTU Mismatch

A cluster running a VXLAN-based overlay CNI experiences intermittent network timeouts when pods transfer large bulk datasets over HTTP, while small requests succeed reliably. Packet captures on worker nodes reveal packet fragmentation and TCP connection stalls. Network engineers identify that worker nodes have a physical interface MTU of 1500 bytes, while container interfaces inside pods are also configured with an MTU of 1500 bytes. What is the fundamental networking problem, and what is the proper remediation?

1. The VXLAN encapsulation header adds 50 bytes of overhead, exceeding physical MTU; container MTU must be reduced to 1450 bytes to prevent packet drops and fragmentation.
2. The physical network switches do not support UDP port 8472, requiring all pods to switch from IPv4 to IPv6 addressing.
3. Pods require `hostNetwork: true` to bypass the Linux kernel netfilter stack when transferring payloads larger than 100 kilobytes.
4. CoreDNS buffer size limits must be expanded from 512 bytes to 4096 bytes to accommodate large TCP window sizes.

<details>
<summary>Answer</summary>

Option 1 is correct because VXLAN encapsulation wraps inner Ethernet and IP frames inside an outer UDP packet adding 50 bytes of header overhead; if the pod MTU matches the host physical MTU (1500), encapsulated packets exceed 1500 bytes and are either fragmented or dropped if DF (Don't Fragment) is set, requiring pod MTU to be reduced (typically to 1450 bytes). Option 2 is wrong because if UDP port 8472 were blocked, all cross-node pod traffic would fail completely rather than failing only on large bulk transfers. Option 3 is incorrect because enabling hostNetwork removes pod network isolation and is not a safe or appropriate remedy for overlay MTU misconfigurations. Option 4 is not correct because CoreDNS buffer size settings affect DNS query responses and have no connection to payload MTU or TCP data transfer sizing.

</details>

---

## Hands-On Exercise

**Task**: Execute a comprehensive services and networking verification drill across your local practice cluster. You will configure a ClusterIP Service and inspect its EndpointSlice objects, read the resolver file and look up one cluster name plus one external name with a single trailing dot, apply an Ingress manifest and inspect it, apply one ingress NetworkPolicy that allows TCP port 80 from same-namespace pods labeled role=frontend, and apply one egress NetworkPolicy whose only rule allows UDP and TCP port 53 to every destination.

Use an existing disposable local Kubernetes cluster such as kind, minikube, or a multi-node kubeadm sandbox. Do not run these destructive operations against a shared production environment. All commands use standard kubectl syntax without shell aliases. All workloads and network resources in this drill represent synthetic practice fixtures designed to demonstrate core networking primitives.

### Step 1: ClusterIP Service and EndpointSlice Inspection

Deploy a two-replica web deployment and expose it through a ClusterIP Service. Verify that the EndpointSlice controller allocates matching endpoints and inspect the generated slice metadata:

```bash
cat <<'EOF' > /tmp/svc-drill.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-backend
  labels:
    app: web-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web-backend
  template:
    metadata:
      labels:
        app: web-backend
    spec:
      containers:
      - name: nginx
        image: nginx:1.35
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web-service
spec:
  type: ClusterIP
  selector:
    app: web-backend
  ports:
  - port: 8080
    targetPort: 80
EOF

kubectl apply -f /tmp/svc-drill.yaml
kubectl rollout status deployment/web-backend --timeout=60s
kubectl get endpointslices -l kubernetes.io/service-name=web-service
kubectl describe service web-service | grep -E '(Type:|IP:|Port:|Endpoints:)'
kubectl delete -f /tmp/svc-drill.yaml
rm -f /tmp/svc-drill.yaml
```

### Step 2: CoreDNS Search Path and ndots Resolution Verification

Inspect the container resolver configuration in a diagnostic pod, then resolve one in-cluster fully qualified name and the external name `example.com.` written with a single trailing dot. The commands print resolv.conf and those two lookups. They do not time the queries or walk an unqualified search path.

```bash
kubectl run dns-tester --image=busybox:1.36 --restart=Never -- sleep 3600
kubectl wait --for=condition=Ready pod/dns-tester --timeout=30s
kubectl exec dns-tester -- cat /etc/resolv.conf
kubectl exec dns-tester -- nslookup kubernetes.default.svc.cluster.local
kubectl exec dns-tester -- nslookup example.com.
kubectl delete pod dns-tester
```

### Step 3: Ingress Manifest Creation and Controller Reconciliation Verification

Create an Ingress resource defining host-based routing for a service. Confirm that the API server accepts the object, then read the ADDRESS column and the describe output. Those fields stay empty when no Ingress controller is reconciling the resource. The commands do not install or remove a controller.

```bash
cat <<'EOF' > /tmp/ingress-drill.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: test-ingress
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mock-service
            port:
              number: 80
EOF

kubectl apply -f /tmp/ingress-drill.yaml
kubectl get ingress test-ingress
kubectl describe ingress test-ingress
kubectl delete -f /tmp/ingress-drill.yaml
rm -f /tmp/ingress-drill.yaml
```

### Step 4: NetworkPolicy Ingress Allow from Labeled Pods

Create a dedicated namespace with two pods. Apply one NetworkPolicy that selects the target pod and allows TCP port 80 only from pods labeled role=frontend in that same namespace, then describe the policy. The manifest does not use an empty ingress list, and the commands do not probe connectivity before or after the apply.

```bash
kubectl create namespace net-drill
kubectl run target-app -n net-drill --image=nginx:1.35 --labels=app=target --expose --port=80
kubectl run authorized-client -n net-drill --image=busybox:1.36 --labels=role=frontend -- sleep 3600
kubectl wait --for=condition=Ready pod/target-app -n net-drill --timeout=30s
kubectl wait --for=condition=Ready pod/authorized-client -n net-drill --timeout=30s

cat <<'EOF' > /tmp/netpol-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: isolate-target
  namespace: net-drill
spec:
  podSelector:
    matchLabels:
      app: target
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: frontend
    ports:
    - protocol: TCP
      port: 80
EOF

kubectl apply -f /tmp/netpol-ingress.yaml
kubectl describe networkpolicy isolate-target -n net-drill
kubectl delete namespace net-drill
rm -f /tmp/netpol-ingress.yaml
```

### Step 5: NetworkPolicy Egress Port Allow

Deploy an application pod and apply an egress policy whose only rule allows UDP and TCP port 53 to every destination. That rule is a port-only allow. It does not select the kube-dns pods or the kube-system namespace. The commands describe the policy. They do not show a DNS failure before the allow, and they do not prove that other ports are blocked.

```bash
kubectl create namespace egress-drill
kubectl run secure-worker -n egress-drill --image=busybox:1.36 --labels=app=worker -- sleep 3600
kubectl wait --for=condition=Ready pod/secure-worker -n egress-drill --timeout=30s

cat <<'EOF' > /tmp/netpol-egress.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: secure-egress
  namespace: egress-drill
spec:
  podSelector:
    matchLabels:
      app: worker
  policyTypes:
  - Egress
  egress:
  - ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
EOF

kubectl apply -f /tmp/netpol-egress.yaml
kubectl describe networkpolicy secure-egress -n egress-drill
kubectl delete namespace egress-drill
rm -f /tmp/netpol-egress.yaml
```

**Card A: A valid Ingress manifest publishes an address even when no controller is installed.** A platform engineer applies an Ingress manifest to expose a web application, expecting the status field to populate with an external IP address or hostname immediately. When the address column remains blank in kubectl get ingress output, the engineer suspects the YAML specification contains syntax errors or invalid host routing rules and reapplies the file repeatedly.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing declarative API resource registration with controller-driven data-plane reconciliation. Next action: deploy an active Ingress controller such as ingress-nginx or an Envoy-based gateway to watch the Ingress resource, configure routing infrastructure, and update the status address field.

</details>

**Card B: Under ndots:5, api.example.com is queried as an absolute name first.** A systems engineer troubleshooting high API latency observes microservices calling an external third-party service at api.example.com, assuming that because the domain name contains a subdomain and top-level domain, the Linux resolver queries it as an absolute domain name immediately. When CoreDNS query metrics show thousands of NXDOMAIN responses, the engineer suspects a cluster DNS outage rather than client resolver search path traversal.

<details>
<summary>Check your prediction</summary>

Failure layer: failing to recognize that the default resolver ndots threshold requires five dots before attempting an absolute lookup first. Next action: configure the client to append a trailing dot (`api.example.com.`) in configuration settings, or customize the pod dnsConfig with a lower ndots value to avoid generating redundant internal search domain queries.

</details>

**Card C: from: [] allows only pods in the same namespace.** A security administrator tries to limit a database to same-namespace callers by putting an empty from list on an ingress rule, expecting that omitted selectors mean local pods only. External clients continue to connect, and the administrator blames the CNI for ignoring pod metadata instead of reading the empty peer list.

<details>
<summary>Check your prediction</summary>

Failure layer: confusing an empty peer list with a same-namespace pod selector. An empty or missing `from` field matches all sources, which `kubectl describe` shows as `From: <any>`, including pods in other namespaces and clients outside the cluster. It does not block traffic. The form that denies every inbound peer is an empty `ingress` list. Next action: use an explicit `podSelector` when the peer set should be pods in the policy namespace only.

</details>

**Card D: EndpointSlices replaced Endpoints, so kubectl get endpoints is empty.** A cluster administrator notes that modern Kubernetes versions use EndpointSlices as the primary scalable data-plane representation for Service backends, assuming that the legacy Endpoints API has been completely removed and that running kubectl get endpoints will return no resources. Upon discovering that Endpoints objects still exist and display backend pod IPs, the administrator worries that rogue controllers are generating duplicate, conflicting network resources.

<details>
<summary>Check your prediction</summary>

Failure layer: reversing the EndpointSlice mirror and treating the still-served Endpoints API as removed. Selector-based Services still receive Endpoints objects from the Endpoints controller, so kubectl get endpoints is not empty. The mirroring controller copies user-created Endpoints for selectorless Services into EndpointSlices. It does not copy EndpointSlices back into Endpoints. Next action: read both objects, and create EndpointSlices directly when a selectorless Service needs custom backends, because that mirror has been deprecated since Kubernetes 1.33.

</details>

**Success Criteria**:

- [ ] You inspected the web-service EndpointSlice with kubectl get endpointslices and described the ClusterIP Service.
- [ ] You printed /etc/resolv.conf and resolved kubernetes.default.svc.cluster.local plus example.com. with one trailing dot.
- [ ] You applied test-ingress and inspected it with kubectl get ingress and kubectl describe ingress.
- [ ] You applied isolate-target, which allows TCP port 80 from pods labeled role=frontend, and described that policy.
- [ ] You applied secure-egress, whose only rule allows UDP and TCP port 53 to every destination, and described that policy.

---

## Sources

- https://kubernetes.io/docs/concepts/services-networking/service/
- https://kubernetes.io/docs/reference/networking/virtual-ips/
- https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/
- https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/
- https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/
- https://kubernetes.io/docs/tasks/administer-cluster/coredns/
- https://kubernetes.io/docs/concepts/services-networking/ingress/
- https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/
- https://kubernetes.io/docs/concepts/services-networking/gateway/
- https://gateway-api.sigs.k8s.io/guides/user-guides/multiple-ns/
- https://gateway-api.sigs.k8s.io/reference/api-types/referencegrant/
- https://kubernetes.io/docs/concepts/services-networking/network-policies/
- https://kubernetes.io/docs/tasks/administer-cluster/declare-network-policy/
- https://kubernetes.io/docs/concepts/cluster-administration/networking/
- https://kubernetes.io/docs/concepts/services-networking/service-traffic-policy/
- https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/
- https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/

## Next Module

Continue to [Part 4: Storage](/k8s/cka/part4-storage/)
