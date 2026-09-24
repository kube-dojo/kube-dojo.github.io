---
revision_pending: false
title: "Module 3.4: Ingress"
slug: k8s/cka/part3-services-networking/module-3.4-ingress
sidebar:
  order: 5
lab:
  id: cka-3.4-ingress
  url: https://killercoda.com/kubedojo/scenario/cka-3.4-ingress
  duration: "40 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - HTTP/HTTPS routing
>
> **Time to Complete**: 45-55 minutes
>
> **Prerequisites**: Module 3.1 (Services), Module 3.3 (DNS)

---

## What You'll Be Able to Do

After this module, you will be able to:

- **Design** path-based and host-based Ingress routing that sends HTTP traffic to the correct Kubernetes Service.
- **Configure** TLS termination with Kubernetes TLS Secrets and explain namespace constraints.
- **Evaluate** Ingress controllers, IngressClass selection, and Gateway API migration tradeoffs for Kubernetes 1.35+ clusters.
- **Diagnose** routing failures by inspecting Ingress status, controller logs, Services, Endpoints, and path rules.

## Why This Module Matters

Hypothetical scenario: a platform team has moved fifteen internal web applications into Kubernetes, and every application team asks for public HTTPS access before a launch window. If the cluster exposes each workload with its own `LoadBalancer` Service, the team gets fifteen external load balancers, fifteen public endpoints, duplicated TLS work, and no shared place to express host or path policy. The applications might work, but the operating model becomes expensive and difficult to reason about under pressure.

Ingress exists to solve that Layer 7 routing problem. A Service gives stable access to Pods inside the cluster, while an Ingress describes HTTP and HTTPS rules that a controller turns into real proxy configuration. The common mental model is a hotel reception desk: guests arrive at one front door, the receptionist reads the name or room request, and the guest is sent to the correct room without every room needing its own street entrance.

For the CKA, you need to create an Ingress quickly, explain why an Ingress resource alone does nothing, and debug why a request falls through to the wrong backend. For production design, you also need the wider context: the Ingress API remains supported in Kubernetes 1.35+, but the community `ingress-nginx` controller was retired in March 2026, so new deployments should evaluate maintained controllers and Gateway API instead of treating older examples as an endorsement for new platform architecture.

## Ingress Architecture and Responsibility Boundaries

The first trap with Ingress is assuming that the YAML resource is the network component. It is not. An Ingress resource is a desired-state document stored in the Kubernetes API, and an Ingress controller is the running software that watches those documents, programs a proxy, and exposes that proxy through its own Service. Without a controller, the API server will happily store your Ingress, but no data-plane component will accept external traffic or populate the `ADDRESS` field.

```
┌────────────────────────────────────────────────────────────────┐
│                   Ingress Architecture                          │
│                                                                 │
│   External Traffic                                              │
│        │                                                        │
│        ▼                                                        │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │            Load Balancer / NodePort                      │  │
│   │            (Ingress Controller's Service)                │  │
│   └────────────────────────┬────────────────────────────────┘  │
│                            │                                    │
│                            ▼                                    │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              Ingress Controller                          │  │
│   │              (nginx, traefik, etc.)                     │  │
│   │                                                          │  │
│   │   Reads Ingress resources and configures routing        │  │
│   └─────────────────────────┬────────────────────────────────┘  │
│                             │                                   │
│               ┌─────────────┼─────────────┐                    │
│               │             │             │                    │
│               ▼             ▼             ▼                    │
│         ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│         │ Service  │  │ Service  │  │ Service  │             │
│         │   /api   │  │   /web   │  │   /docs  │             │
│         └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│              │             │             │                    │
│              ▼             ▼             ▼                    │
│         ┌──────┐      ┌──────┐      ┌──────┐                 │
│         │ Pods │      │ Pods │      │ Pods │                 │
│         └──────┘      └──────┘      └──────┘                 │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The architecture is easier to debug when you separate control plane from data plane. The Kubernetes API stores Ingress, Service, EndpointSlice, Secret, and IngressClass objects. The controller reads those objects and rewrites its proxy configuration. The proxy then accepts packets from the controller Service, applies HTTP routing rules, and forwards traffic to backend Services that in turn select Pods.

| Feature | NodePort | LoadBalancer | Ingress |
|---------|----------|--------------|---------|
| Layer | L4 (TCP/UDP) | L4 (TCP/UDP) | L7 (HTTP/HTTPS) |
| Path routing | No | No | Yes |
| Virtual hosts | No | No | Yes |
| TLS termination | No | Limited | Yes |
| Cost | Free | $ per LB | One controller for many services |
| External IP | Node IP:Port | Cloud LB IP | Controller's IP |

NodePort and LoadBalancer are still useful, but they solve a lower-level exposure problem. A `LoadBalancer` Service can put one application behind a cloud load balancer, and that is often the right answer for a TCP service, a database endpoint inside a private network, or a dedicated appliance-style workload. Ingress is the better fit when the decision depends on HTTP hostnames, paths, TLS certificates, and shared routing policy.

| Component | Purpose | Who Creates |
|-----------|---------|-------------|
| Ingress Controller | Actually routes traffic | Cluster admin |
| Ingress Resource | Defines routing rules | Developer |
| Backend Services | Target services | Developer |
| TLS Secret | HTTPS certificates | Developer/cert-manager |

**Pause and predict:** if you apply a valid Ingress manifest to a cluster with no Ingress controller installed, which Kubernetes object accepts the manifest, and which visible field will usually remain empty? Decide before opening the explanation.

<details>
<summary>Check your prediction</summary>

The API server accepts the object because the schema is valid, but the controller-owned status is not updated because no controller is reconciling the resource.

</details>

The next section is an operational guide to class definitions and routing engines; review how implementation choices fulfill these declarative manifests.

## Controllers, IngressClass, and the Post-Retirement Landscape

The controller is an implementation choice, not a property of the Ingress API itself. In older tutorials, `nginx` often appears as the default controller because `ingress-nginx` became the community example that many clusters used for years. In 2026, the safer teaching stance is more precise: Ingress remains a stable API, the community `ingress-nginx` controller reached retirement, and production clusters should use a maintained controller or move new HTTP routing work to Gateway API when the platform supports it.

| Controller | Description | Best For |
|------------|-------------|----------|
| **nginx** | Most common, feature-rich | General use |
| **traefik** | Auto-discovery, modern | Dynamic environments |
| **haproxy** | High performance | High-traffic sites |
| **contour** | Envoy-based | Service mesh users |
| **AWS ALB** | Native AWS integration | AWS environments |

For exam practice and local labs, you will still see NGINX-shaped examples because they make the relationship between resource, class, controller, and backend easy to observe. Treat those examples as a learning target, not a blanket production recommendation. When a real organization is choosing a controller for Kubernetes 1.35+, the decision should include maintenance status, Gateway API support, cloud integration, security policy support, observability, and how controller-specific annotations will be migrated later.

```bash
# For kind
# retired controller — lab/learning use only; see Sources for maintained alternatives
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# For minikube
minikube addons enable ingress

# Verify installation
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx
```

That installation block is useful for controlled learning environments because it gives you a concrete controller to inspect. The important operational detail is not the command itself; it is the fact that the controller runs as Pods, exposes a Service, and registers or uses an `IngressClass`. If a learner can find those objects, they can reason about whether the cluster has the control loop and data plane required for an Ingress to work.

```bash
# Check pods
kubectl get pods -n ingress-nginx

# Check service
kubectl get svc -n ingress-nginx

# Check IngressClass
kubectl get ingressclass
```

`ingressClassName` is the handshake between an Ingress resource and the controller that should process it. In clusters with one default class, an omitted class may still work, but that habit becomes fragile when a platform has multiple controllers. A cluster might have one controller for public internet traffic, another for private internal traffic, and another for a cloud-native application load balancer; an unclassified Ingress can be ignored, claimed by the wrong default, or rejected by admission policy.

## Designing Path and Host Routing

A simple Ingress routes one or more HTTP paths to backend Services. The backend is a Service name and Service port, not a Pod IP, because Kubernetes wants the routing rule to survive Pod replacement and scaling events. That design keeps the Ingress focused on Layer 7 decisions while Services keep doing the stable load-balancing work you learned earlier in the networking track.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: simple-ingress
spec:
  ingressClassName: nginx            # Which controller to use
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service        # Target service
            port:
              number: 80             # Service port
```

The simplest route above is deliberately plain: every HTTP request handled by this Ingress goes to `web-service` on Service port `80`. This is not a replacement for the Service selector or the Pod container port. It is the last hop in a chain: client to controller, controller to Service, Service to endpoints, and endpoints to Pods.

Path-based routing becomes useful when a single hostname or external address fronts several applications. A common pattern is to put `/api` in front of an API Service, `/web` in front of a web Service, and `/` in front of a default frontend or landing page. The catch is that path rules are not evaluated as a top-to-bottom firewall list; Kubernetes defines precedence rules so the most specific match wins.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-ingress
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
      - path: /web
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: default-service
            port:
              number: 80
```

```
┌────────────────────────────────────────────────────────────────┐
│                   Path-Based Routing                            │
│                                                                 │
│   Request: http://mysite.com/api/users                         │
│                        │                                        │
│                        ▼                                        │
│   ┌────────────────────────────────────────────────────────┐   │
│   │                    Ingress                              │   │
│   │                                                         │   │
│   │   /api/*  ──────────► api-service                      │   │
│   │   /web/*  ──────────► web-service                      │   │
│   │   /*      ──────────► default-service                  │   │
│   │                                                         │   │
│   └────────────────────────────────────────────────────────┘   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

| PathType | Behavior | Example |
|----------|----------|---------|
| `Exact` | Exact match only | `/api` matches `/api`, not `/api/` |
| `Prefix` | Prefix match | `/api` matches `/api`, `/api/users` |
| `ImplementationSpecific` | Controller decides | Varies by controller |

`Prefix` is usually the CKA-friendly choice because it covers both the base path and child paths. `Exact` is valuable when one endpoint must be isolated from nearby paths, such as `/healthz` or a callback route that should not match `/healthz/debug`. `ImplementationSpecific` can unlock controller-specific behavior, including regex-like matches in some controllers, but it trades portability for power and should be used only when you know which controller will process the resource.

**Pause and predict:** you have two Ingress path rules, `/api` with `pathType: Prefix` and `/api/v1` with `pathType: Exact`. A request arrives for `/api/v1/users`, and a second request arrives for `/api/v1`; which rule handles each request? Predict the matching behavior before opening the explanation.

<details>
<summary>Check your prediction</summary>

The longer exact path handles only `/api/v1`, while `/api/v1/users` falls back to the `/api` prefix, which is the only prefix that matches `/api/v1/users` in this example.

</details>

The next section is an introduction to domain routing and virtual host dispatching across distinct backend services sharing one public IP.

Host-based routing, also called virtual hosting, uses the HTTP `Host` header to choose a backend. This is the same idea that lets one web server host several websites on one IP address. In Kubernetes, it lets one controller Service accept traffic for `api.example.com` and `web.example.com` while sending each hostname to a different internal Service.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: virtual-host-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
  - host: web.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

```
┌────────────────────────────────────────────────────────────────┐
│                   Host-Based Routing                            │
│                                                                 │
│   api.example.com  ──────────► api-service                     │
│   web.example.com  ──────────► web-service                     │
│   *.example.com    ──────────► default-service (if configured) │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Host and path rules compose cleanly when you need a real application shape. One hostname can route `/api` to a backend API and `/` to a frontend, while another hostname routes everything to an admin application. This is where Ingress starts to feel like a small HTTP router rather than a simple exposure knob.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: combined-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
  - host: admin.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: admin-service
            port:
              number: 80
```

Before running this in a lab, what output do you expect from `kubectl describe ingress` if the backend Service names exist but no Pods match the Service selectors? The Ingress rule can still appear valid because it points at Services, while the actual request path fails later because the Services have no endpoints.

## TLS Termination and Controller-Specific Behavior

TLS termination is the point where encrypted HTTPS traffic becomes decrypted HTTP traffic. With a typical Ingress setup, the client speaks HTTPS to the controller, the controller presents a certificate from a Kubernetes TLS Secret, and the controller forwards plain HTTP to the backend Service inside the cluster. Some environments also encrypt the backend hop, but that is not part of the basic Ingress contract and depends on controller features or service mesh policy.

```bash
# Generate self-signed certificate (for testing)
# self-signed, no SAN — modern curl needs --insecure (lab/testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=example.com"

# Create secret
kubectl create secret tls example-tls --cert=tls.crt --key=tls.key
```

That Secret must live in the same namespace as the Ingress. This namespace rule is not a controller quirk; it is part of how the Ingress API references Secrets. If you create `example-tls` in `default` and the Ingress in `production`, the controller cannot use that Secret through the Ingress reference, and you may see a default certificate or a TLS error depending on the controller.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tls-ingress
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - example.com
    - www.example.com
    secretName: example-tls      # TLS secret name
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

```
┌────────────────────────────────────────────────────────────────┐
│                   TLS Termination                               │
│                                                                 │
│   Client (HTTPS)                                               │
│        │                                                        │
│        │ TLS/SSL encrypted                                     │
│        ▼                                                        │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              Ingress Controller                          │  │
│   │              (TLS terminates here)                       │  │
│   │                                                          │  │
│   │   Uses certificate from Secret: example-tls             │  │
│   └─────────────────────────────────────────────────────────┘  │
│        │                                                        │
│        │ Plain HTTP (inside cluster)                           │
│        ▼                                                        │
│   ┌──────────────────┐                                         │
│   │     Service      │                                         │
│   │     (port 80)    │                                         │
│   └──────────────────┘                                         │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Annotations are where Ingress becomes powerful and messy. The Kubernetes Ingress API defines hosts, paths, TLS, default backends, and backend references, but it does not standardize every proxy behavior that teams expect. Controllers therefore expose features such as redirects, rewrites, timeouts, rate limiting, and CORS through annotations, which means the YAML can become tied to one controller implementation.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: annotated-ingress
  annotations:
    # Rewrite URL path
    nginx.ingress.kubernetes.io/rewrite-target: /

    # SSL redirect
    nginx.ingress.kubernetes.io/ssl-redirect: "true"

    # Timeouts
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"

    # Rate limiting
    nginx.ingress.kubernetes.io/limit-rps: "10"

    # CORS
    nginx.ingress.kubernetes.io/enable-cors: "true"
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

URL rewriting is the classic example of that portability tradeoff. A backend might serve `/dashboard`, while the public URL should be `/app/dashboard`; without a rewrite, the backend receives the public prefix and may return a valid application-level 404. The annotation below shows the controller-specific style many learners encounter, while Gateway API later gives you a more portable way to express similar behavior through filters.

```yaml
# Route /app/(.*)  to backend /($1)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rewrite-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$1
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /app/(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: web-service
            port:
              number: 80
```

Stop and think: your Ingress serves both `api.example.com` and `web.example.com`, and you want HTTPS for both with different certificates. You need two TLS Secrets if the certificates are distinct, both Secrets must be in the same namespace as the Ingress that references them, and termination happens at the controller unless you deliberately configure a different backend encryption model.

## Diagnosing Ingress Routing Failures

Ingress debugging works best when you walk the request path in order instead of staring at the Ingress manifest alone. Start with whether a controller has processed the resource, then check whether the controller can reach a Service, then check whether the Service has endpoints, and only then investigate application-level behavior. Most exam failures fit into one of those steps, and most production incidents benefit from the same discipline.

```
Ingress Not Working?
    │
    ├── kubectl get ingress (check ADDRESS)
    │       │
    │       ├── No ADDRESS → Controller not processing
    │       │                Check IngressClass
    │       │
    │       └── Has ADDRESS → Continue debugging
    │
    ├── kubectl describe ingress (check events)
    │       │
    │       └── Errors? → Fix configuration
    │
    ├── Check backend service
    │   kubectl get svc,endpoints
    │       │
    │       └── No endpoints? → Service has no pods
    │
    ├── Check Ingress controller logs
    │   kubectl logs -n ingress-nginx <controller-pod>
    │
    └── Test from inside cluster
        kubectl run test --rm -i --image=curlimages/curl -- \
          curl -s <service>
```

```bash
# List ingresses
kubectl get ingress
kubectl get ing              # Short form

# Describe ingress
kubectl describe ingress my-ingress

# Get ingress YAML
kubectl get ingress my-ingress -o yaml

# Check IngressClass
kubectl get ingressclass

# Check Ingress controller pods
kubectl get pods -n ingress-nginx

# View controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx
```

| Symptom | Cause | Solution |
|---------|-------|----------|
| No ADDRESS assigned | No Ingress controller | Install ingress controller |
| ADDRESS assigned but 404 | Path doesn't match | Check path and pathType |
| 503 Service Unavailable | No endpoints | Check service selector/pods |
| SSL error | Wrong/missing TLS secret | Verify secret exists and matches host |
| Wrong IngressClass | Multiple controllers | Specify correct ingressClassName |

An empty `ADDRESS` usually means the controller did not claim or reconcile the Ingress. The cause could be a missing controller, a wrong `ingressClassName`, a class that points to a different controller, or a controller that lacks permission to update status. A `404` usually means the controller is alive but the request did not match the host and path combination you expected. A `503` usually means the route matched but the backend Service has no usable endpoints.

Default backends are useful when you want unmatched requests to land somewhere deliberate. Without a default backend, an unmatched host or path typically receives the controller's own default response. With a default backend, you can return a branded error page, a catch-all service, or a controlled response that helps operations distinguish between "the controller is working" and "the route is not configured."

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: default-backend-ingress
spec:
  ingressClassName: nginx
  defaultBackend:                    # Catch-all
    service:
      name: default-service
      port:
        number: 80
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

Exercise scenario: you apply an Ingress with `ingressClassName: nginx`, `kubectl get ingress` shows an address, and `/api/users` returns a frontend page. The best first check is not the controller Pod restart count; it is whether the `/api` path uses `Prefix`, whether a more specific rule exists for that hostname, and whether the request includes the host header that matches the rule you think you are testing.

### Worked Request Walkthrough

Imagine a request for `https://app.example.com/api/users` entering the cluster through an external load balancer in front of the controller. DNS has already resolved the hostname to the controller's public address, and the client now opens a TLS connection to that controller. At this moment, Kubernetes Services for `api` and `web` are not visible to the client; the client only sees the endpoint exposed by the controller Service.

The controller receives the TLS handshake and selects a certificate by using the requested server name and the `tls.hosts` entries from matching Ingress resources. If the certificate Secret exists in the correct namespace and contains usable certificate material, the controller can complete the handshake. If the Secret is wrong, the failure still happens before any Service or Pod receives traffic, which is why TLS errors should not send you straight to Deployment debugging.

After TLS termination, the controller reads the HTTP request line and headers. The `Host` header decides which host rule is eligible, and the path decides which backend under that host should receive the request. This ordering matters because `/api` under `app.example.com` is different from `/api` under `admin.example.com`; a path that looks correct in one host block does nothing for a request carrying another host value.

For `pathType: Prefix`, Kubernetes defines path elements rather than a naive string prefix in the common case. A route for `/api` is intended to match `/api` and `/api/users`, but you should still be precise when trailing slashes or similarly named paths appear. A route for `/api` should not be treated as a casual match for every application path that merely begins with the same letters, and controller documentation is worth reading when behavior gets subtle.

Once a rule matches, the controller forwards the request toward the named Service and port. This is where many wrong mental models break down. The Ingress backend does not point to a Deployment, a ReplicaSet, or a Pod label selector; it points to a Service, and the Service then points to endpoints derived from selected Pods that are ready enough to receive traffic.

That separation gives you a clean troubleshooting sequence. If the Ingress rule names `api` on port `80`, start by confirming that a Service named `api` exists in the same namespace and exposes port `80`. Then confirm that the Service selector matches the intended Pods. Finally, confirm that the Pods are running and ready, because a Service without endpoints is a common cause of route-matched but backend-unavailable responses.

The response path follows the reverse direction, but the important ownership boundaries remain the same. Application code owns the response status and body after the request reaches the Pod. The Service owns endpoint selection. The controller owns HTTP matching, TLS termination, and proxy behavior. The external load balancer or NodePort owns the first network entry point into the controller.

This boundary model helps you interpret status codes. A TLS alert usually points toward certificate selection, Secret shape, or client trust. A controller-generated 404 usually points toward unmatched host or path rules. A 503 usually points toward an unavailable backend after a route matched. A backend-generated 404 usually means the request arrived at the application but the application did not recognize the path it received.

When rewriting or stripping prefixes, be especially careful to identify which component produced the 404. If the controller never matched the route, rewrite annotations cannot help because the request did not reach that rule. If the backend received `/app/dashboard` and expected `/dashboard`, a rewrite can help, but now your portability depends on the chosen controller and its exact annotation semantics.

This is also why curl tests should include the host header when DNS is not configured. Testing `curl http://controller-ip/api` without `-H "Host: app.example.com"` does not exercise the same rule as a real browser request for `app.example.com`. In exam labs, local clusters often make this easy to forget because everything seems reachable through localhost, but HTTP routing decisions still depend on the host value.

The same discipline applies when several Ingress resources share a hostname. Controllers typically merge routes for the same host according to their implementation, and conflicts may be rejected, warned about, or resolved by precedence rules. For learning and exam work, keep related rules in one manifest when possible so you can see the complete host and path shape in one `kubectl describe ingress` output.

Namespaces add one more boundary that is easy to overlook. An Ingress backend Service reference is namespaced, so the route points to Services in the same namespace as the Ingress. A TLS Secret reference is also namespaced. If platform teams want cross-namespace attachment models, they should evaluate Gateway API because it has explicit concepts for delegation and reference permission rather than relying on accidental cross-namespace assumptions.

### Production Readiness and Migration Notes

Ingress is still worth learning deeply because many clusters will run Ingress manifests for years, even as new designs move toward Gateway API. A production operator needs to distinguish "the API is deprecated" from "a particular controller is retired" because those statements lead to different actions. The former would require replacing the resource model immediately, while the latter requires reviewing controller maintenance, migration timing, and annotation dependence.

The community `ingress-nginx` retirement raises that distinction directly. Existing clusters may still contain many Ingress resources that are valid Kubernetes API objects, but the data-plane controller behind them may no longer receive maintenance. That means a migration plan should inventory controller Deployments, IngressClasses, annotations, admission webhooks, custom snippets, TLS automation, and operational dashboards rather than merely counting Ingress objects.

Gateway API improves several areas that Ingress stretched through annotations. It separates infrastructure-owned listeners from application-owned routes, models more routing behavior as first-class fields, and provides clearer cross-namespace attachment patterns. That does not make every Ingress urgent to replace, but it does mean new platform work should justify why it is choosing Ingress rather than defaulting to the newer routing model.

For CKA purposes, focus on the stable Ingress behaviors that transfer across controllers: class selection, host rules, path rules, Service backends, TLS Secret references, and basic troubleshooting. Do not try to memorize every annotation from one controller. The exam expects you to apply core Kubernetes networking concepts, and controller-specific features are more likely to appear as contextual clues than as the main learning target.

For platform design, annotations deserve a migration label. A route that only sets `ssl-redirect` may be easy to recreate elsewhere, while a route that uses regex paths, complex rewrites, custom snippets, and rate limits may require careful translation. The route with the most annotations is often the route that looks simple to application owners but carries the most hidden platform coupling.

Certificate management also changes with scale. A self-signed certificate created by `openssl` is fine for a lab, but production certificates should be requested, renewed, and distributed by automation. If the platform uses cert-manager, external DNS automation, or cloud certificate managers, the Ingress manifest becomes one part of a larger chain, and debugging must include issuer status, DNS records, and controller event logs.

Access control is another production difference. In a shared cluster, not every namespace should be allowed to create internet-facing routes, choose every IngressClass, or attach arbitrary annotations. Admission policies can require approved class names, block dangerous annotation patterns, enforce host naming conventions, and require TLS for public hosts. These controls turn routing rules from individual YAML choices into platform policy.

Observability should be planned before the first outage. The controller should expose metrics for request rates, response codes, latency, configuration reloads, and rejected resources. Logs should let operators distinguish an unmatched route from an upstream failure. Application teams should know whether they can see controller access logs or whether the platform team owns that evidence during an incident.

Capacity planning belongs in the controller layer too. A single shared controller can simplify external exposure, but it can also become a shared bottleneck if resource requests, autoscaling, and load balancer settings are neglected. High availability usually means multiple controller replicas, disruption budgets, careful node placement, and enough load balancer health checking to avoid sending traffic to a broken proxy.

The backend Services still matter when the controller is healthy. If readiness probes are too strict, a Deployment can have running Pods but no endpoints, causing route-matched traffic to fail. If readiness probes are too weak, the Service can send traffic to Pods that are not actually ready. Ingress debugging often reveals application readiness problems because HTTP traffic concentrates through a visible entry point.

Path ownership should be written down for shared hostnames. If one team owns `/api` and another owns `/api/admin`, the teams need agreement about precedence, rewrites, authentication, and rollout order. Otherwise a harmless-looking route can shadow a more specific route or change the path a backend receives. Hostname-per-product boundaries are often easier to operate because ownership is visible in DNS and certificates.

Default backends are useful, but they should be intentional. A default backend that returns a generic success page can hide missing route configuration by making every unmatched request look healthy. A better default response explains that no route matched, sets a clear status code, and gives operators enough information to determine whether the controller received the request. In production, observability matters more than a pretty fallback page.

When comparing Ingress and Gateway API, do not frame the choice as "old versus new" only. The practical question is who owns the listener, who owns the route, how much behavior needs to be portable, and how many controller-specific features are already in use. A small existing Ingress with one host and one Service may not deserve urgent migration, while a new shared platform should strongly prefer the clearer Gateway API ownership model.

For the exam, practice writing the boring correct manifest before reaching for advanced behavior. Set the class, set the host when required, choose `Prefix` or `Exact` deliberately, reference the Service port correctly, and verify endpoints before blaming the controller. That routine solves more failures than memorizing rare annotations, and it gives you a reliable fallback when time pressure makes complex debugging tempting.

The final operational habit is to keep route tests realistic. Include the host header, use the right scheme, test the exact path, and know whether you are testing from outside the cluster, from a node, or from a temporary Pod. Each location bypasses or includes different parts of the request path. A passing in-cluster Service curl proves the backend works, but it does not prove TLS, host matching, or external load balancer behavior.

### Reading Ingress Manifests Under Exam Pressure

When you read an Ingress manifest during the CKA, scan it in the same order a request uses it. Start with `ingressClassName`, because a beautifully written route is inert if no matching controller processes it. Then scan `tls` for host coverage and Secret names. Finally, read each host rule and path rule, checking that every backend Service name and port can exist in the same namespace as the Ingress.

The backend port is worth a deliberate pause. Kubernetes lets a Service expose one port while forwarding to a different target port on Pods, and the Ingress backend references the Service port. If a Deployment listens on container port `8080`, the Service exposes port `80`, and the Ingress points at port `8080`, the route may fail because the Service does not expose that port number.

Read the manifest for hidden controller assumptions as well. An annotation key beginning with `nginx.ingress.kubernetes.io` tells you the manifest expects NGINX-compatible behavior, not generic Ingress behavior. A future controller might ignore that annotation or interpret a similar feature differently. In an exam setting, that clue helps you understand the intended behavior; in production, it becomes migration inventory.

Hostnames should make you ask how the test request is formed. If the Ingress rule says `host: api.example.com`, then a curl to an IP address without a host header is not a faithful test. The controller sees the HTTP host value, not the comment you had in mind. This is why many local tests use `curl -H "Host: api.example.com"` while DNS is still absent.

For path rules, check whether the route family needs child paths. A frontend route for `/` with `Prefix` is broad by design, so any more specific route must be correct enough to beat it. If `/api/users` falls through to `/`, the issue is commonly an `Exact` path, a host mismatch, or a test request that never reached the intended host block.

Descriptions and events are faster than guessing. `kubectl describe ingress` usually shows the rules in a compact form, the class, the address, and recent controller events. If the controller rejected a rule, could not find a Service, or had trouble loading a TLS Secret, the event stream may give you the direct clue. Treat describe output as the bridge between YAML intent and controller reconciliation.

Controller logs add detail when events are not enough, but they should not be the first stop for every failure. Logs can be noisy, especially on shared controllers handling many namespaces. Narrow the problem first with the Ingress object, Service, endpoints, and a realistic curl test. Then use logs to confirm whether the controller matched the route, selected an upstream, or generated the response itself.

Endpoint inspection is the shortest path through many 503 failures. A Service can exist, have the right port, and still have no ready endpoints because Pod labels do not match, readiness probes are failing, or the Deployment has not rolled out. In that case, editing Ingress only adds churn. Fix the backend availability problem, then retest the same route without changing the routing rule.

TLS failures deserve their own branch in your mental checklist. Confirm that the Secret type is `kubernetes.io/tls`, that the Secret contains certificate and key data, and that the Secret is in the same namespace as the Ingress. Then confirm that the host in the TLS section matches the hostname clients actually use. A certificate for the wrong name can look like an Ingress failure even when routing is otherwise correct.

Finally, remember that Ingress is one layer in a longer chain. DNS, cloud load balancers, node networking, controller Pods, Ingress rules, Services, EndpointSlices, Pod readiness, and application routing all participate in the final user experience. The practical skill is not blaming the right layer by instinct; it is walking the chain quickly enough that each observation eliminates several wrong theories at once.

The safest exam strategy is to keep your first manifest conservative. Avoid optional annotations until the required route works, use `Prefix` only where a route family needs child paths, and keep host rules obvious. Once the core route is healthy, add TLS or rewrites one change at a time so the next failure has a small search space.

In production, that same habit becomes change management. A route change, certificate change, and rewrite change in one pull request can make rollback unclear because any one of those edits can alter user-visible behavior. Smaller route changes are easier to review, easier to test with realistic curl commands, and easier to reverse if the controller accepts the manifest but traffic behaves unexpectedly.

If you remember only one debugging sentence, make it this: no address points toward controller or class reconciliation, 404 points toward host and path matching, and 503 points toward matched routes with unavailable backends. That shorthand is not a substitute for evidence, but it gives you a fast starting hypothesis that maps cleanly onto the Kubernetes objects you can inspect.

## Patterns & Anti-Patterns

Ingress patterns are less about memorizing YAML and more about making routing ownership explicit. A good pattern lets an application team ship a route without accidentally taking over another team's hostname, while a good platform pattern lets cluster administrators change controllers without rewriting every application from scratch. The table below focuses on decisions you can defend in an exam explanation and in a design review.

| Pattern | Use When | Why It Works | Scaling Consideration |
|---------|----------|--------------|-----------------------|
| One shared controller with explicit `ingressClassName` | Several teams need HTTP routing through one platform entry point | Each Ingress says which controller owns it, avoiding accidental default behavior | Add admission policy or templates so teams do not omit the class |
| Host-based routing per application boundary | Different apps need independent DNS names | Hostnames create clean ownership and avoid path prefix coupling | Certificate automation becomes important as host count grows |
| Path-based routing inside one product surface | One public app has multiple internal backends | Users see one hostname while services remain separately deployable | Document prefix ownership so teams do not collide on `/api` or `/admin` |
| TLS Secrets managed by automation | Certificates rotate regularly or many hosts exist | Manual Secret replacement becomes operational risk | Use cert-manager or platform tooling with clear namespace rules |

The main anti-pattern is treating annotations as harmless decoration. An annotation such as a rewrite rule, redirect, or timeout can change request semantics just as much as a route rule can. If those annotations are tied to one controller, they should be documented as implementation-specific behavior and considered migration work when the organization evaluates Gateway API or a different controller.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Omit `ingressClassName` in multi-controller clusters | No controller claims the route, or the wrong default controller does | Require explicit class names in manifests and policy |
| Put one unrelated fleet behind path prefixes | Backends become coupled to public path structure and rewrites multiply | Prefer host-based routing when products have separate ownership |
| Store TLS Secret in a different namespace | The Ingress cannot reference the certificate | Keep the Secret beside the Ingress or use Gateway API cross-namespace mechanisms where appropriate |
| Use `ImplementationSpecific` for ordinary prefixes | Behavior changes when controllers change | Use `Prefix` or `Exact` unless a controller-specific feature is required |

## Decision Framework

Choose Ingress when the routing problem is HTTP or HTTPS, the cluster already has a maintained controller, and the needed features fit the stable Ingress API plus a small number of accepted annotations. Choose a `LoadBalancer` Service when the workload is not HTTP-aware or deserves its own dedicated L4 endpoint. Choose Gateway API for new platform designs that need richer, more portable routing features, separate infrastructure and application ownership, or cleaner cross-namespace delegation.

| Question | Prefer This | Reason |
|----------|-------------|--------|
| Do you need TCP or UDP without HTTP host/path decisions? | `LoadBalancer` Service | Ingress is HTTP-oriented and adds unnecessary Layer 7 machinery |
| Do you need many HTTP apps behind one external entry point? | Ingress or Gateway API | Both can route by host and path through shared infrastructure |
| Are you building a new Kubernetes 1.35+ platform? | Gateway API | It is the successor model with better role separation and richer routing concepts |
| Are you maintaining existing Ingress manifests? | Ingress with migration planning | The API remains supported, but controller and annotation choices need review |
| Do you rely heavily on controller-specific annotations? | Evaluate migration effort | Those annotations are the cost center when controllers change |

Use this sequence during design reviews. First, decide whether the traffic is HTTP-aware. Second, decide who owns the external listener and certificate. Third, decide whether routing rules must be portable across controllers. Finally, decide whether the cluster already has the controller and policy needed to make the chosen model reliable.

## Did You Know?

- The Ingress API moved to `networking.k8s.io/v1` and has been the stable API shape since Kubernetes 1.19, which is why modern examples must include `pathType` and the structured `service.name` backend format.
- The community `ingress-nginx` controller retirement was announced by Kubernetes project leadership for March 2026, but that retirement did not deprecate the Kubernetes Ingress API itself.
- A single Ingress can contain multiple host rules and multiple path rules, but TLS Secrets referenced by that Ingress still have to live in the same namespace as the Ingress object.
- Kubernetes path matching uses longest-path precedence, and when an `Exact` and `Prefix` match are tied for the longest path, the `Exact` match wins.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Creating an Ingress before any controller exists | The API accepts the object, so learners assume routing exists | Install or identify a controller, then verify Pods, Service, and `IngressClass` |
| Omitting `ingressClassName` in a shared cluster | Local labs often have one default class, hiding the dependency | Set `spec.ingressClassName` explicitly and confirm it matches `kubectl get ingressclass` |
| Sending the Ingress backend to the container port instead of the Service port | The backend block says `port`, so it is easy to think Pod-first | Match the Ingress backend to the Service port that fronts the Pods |
| Using `Exact` for paths that need children | `/api` works in a quick test but `/api/users` falls through | Use `Prefix` for route families and reserve `Exact` for single endpoints |
| Expecting TLS Secrets to work across namespaces | Secret names look global when read quickly | Create the TLS Secret in the same namespace as the Ingress |
| Treating a 404 and a 503 as the same failure | Both are visible to users as broken pages | Use 404 as a match/routing clue and 503 as a backend endpoint clue |
| Copying controller-specific annotations without reading controller docs | Examples often hide portability assumptions | Document the controller dependency or use Gateway API features where available |

## Quiz

<details>
<summary>Question 1: Your team runs several HTTPS web services and proposes one `LoadBalancer` Service per workload. What design would you recommend, and what tradeoff should you mention?</summary>

Use an Ingress or Gateway API route through a shared controller when the traffic is HTTP or HTTPS and the platform needs host-based or path-based routing. A separate `LoadBalancer` per workload can be valid for dedicated endpoints, but it increases external IPs, cloud load balancer cost, certificate duplication, and operational surface area. For a new Kubernetes 1.35+ platform, mention that Gateway API is the preferred direction, while Ingress remains common and supported for existing routing.

</details>

<details>
<summary>Question 2: You apply an Ingress and `kubectl get ingress` shows no address after several minutes. What should you inspect first?</summary>

Start by checking whether an Ingress controller is installed and healthy, because the API server does not route traffic by itself. Then inspect `kubectl get ingressclass` and compare the class name with `spec.ingressClassName` on the Ingress. If the controller and class look correct, describe the Ingress and inspect controller logs to see whether the controller rejected the resource or lacks permission to update status.

</details>

<details>
<summary>Question 3: Requests to `/api/users` are returning the frontend page, while `/` is meant for the frontend and `/api` is meant for the API. What is the likely routing mistake?</summary>

The most likely mistake is that the `/api` path uses `Exact`, is attached to a different host rule, or is not being matched because the test request lacks the expected host header. With `pathType: Prefix`, `/api/users` should match `/api` and beat the `/` prefix because Kubernetes uses longest-path precedence. After checking the path type and host, inspect the rendered Ingress with `kubectl describe ingress` and confirm the backend Service name and port.

</details>

<details>
<summary>Question 4: A TLS Ingress references `secretName: prod-tls`, but clients see a default certificate. What namespace rule should you verify?</summary>

Verify that `prod-tls` exists in the same namespace as the Ingress object. The Ingress API does not let a route in one namespace directly reference a TLS Secret in another namespace. If the Secret is missing, in the wrong namespace, malformed, or not a Kubernetes TLS Secret, the controller may serve a fallback certificate or report an error in events and logs.

</details>

<details>
<summary>Question 5: A backend serves `/dashboard`, but users visit `/app/dashboard` through Ingress and receive an application 404. How do you diagnose the difference between Ingress routing and application routing?</summary>

First confirm whether the request reaches the intended backend by checking controller access logs, Service endpoints, and a direct in-cluster request to the Service. If the backend receives `/app/dashboard` but only serves `/dashboard`, the Ingress matched correctly and the remaining problem is URL shape. A controller-specific rewrite annotation can strip the `/app` prefix, but that should be documented because rewrite behavior is not portable across all controllers.

</details>

<details>
<summary>Question 6: A platform has both public and private Ingress controllers. Why is an explicit `ingressClassName` part of the security posture?</summary>

An explicit class prevents a route from being claimed by whichever controller is default or by no controller at all. In a public/private split, the class can encode whether a route is internet-facing or internal, which is an infrastructure ownership decision rather than a small YAML detail. Admission policy can require allowed class names so application teams cannot accidentally publish an internal service through the public controller.

</details>

<details>
<summary>Question 7: An Ingress returns 503 for a path that appears to match correctly. What backend checks should you perform before editing the route?</summary>

A 503 usually means the controller matched the route but could not reach healthy backend endpoints. Check the Service name and port referenced by the Ingress, then run `kubectl get svc,endpoints` or inspect EndpointSlices for the Service. If there are no endpoints, fix the Service selector, Pod labels, Pod readiness, or Deployment health before changing path rules.

</details>

## Hands-On Exercise

Exercise scenario: build a small HTTP routing setup with two Services, one path-based Ingress, one host-based Ingress, and one TLS Ingress. The lab assumes a learning cluster with an Ingress controller and an `nginx` IngressClass available; if your cluster uses a different maintained controller, keep the same API structure but substitute the class name and controller-specific annotations according to that controller's documentation.

### Task 1: Create Backend Services

Create two simple Deployments and expose them as ClusterIP Services. The images are intentionally boring because the goal is routing behavior, not application logic. After creation, verify both Deployments and Services before writing any Ingress rule, because a correct route cannot save a missing backend.

```bash
# API service
kubectl create deployment api --image=nginx
kubectl expose deployment api --port=80

# Web service
kubectl create deployment web --image=nginx
kubectl expose deployment web --port=80
```

```bash
kubectl get deployment api web
kubectl get svc api web
```

<details>
<summary>Solution notes for Task 1</summary>

Both Deployments should show available replicas after the image starts, and both Services should show `TYPE` as `ClusterIP` with port `80`. If the Deployments are not available yet, wait for the Pods before debugging Ingress. If the Services are missing or have unexpected names, later Ingress backend references will produce confusing 503-style failures.

</details>

### Task 2: Create Path-Based Routing

Create one Ingress that sends `/api` to the API Service and `/` to the web Service. This is the smallest useful routing shape for the exam because it forces you to connect path precedence, Service names, Service ports, and the selected IngressClass in one manifest.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: multi-path-ingress
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 80
EOF
```

```bash
kubectl get ingress
kubectl describe ingress multi-path-ingress
```

```bash
# Get ingress address (fallback to localhost if no LB IP is assigned in local clusters)
INGRESS_IP=$(kubectl get ingress multi-path-ingress -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
[ -z "$INGRESS_IP" ] && INGRESS_IP="localhost"

# Test paths directly from the host node (since INGRESS_IP might be localhost)
curl -s http://$INGRESS_IP/api
curl -s http://$INGRESS_IP/
```

<details>
<summary>Solution notes for Task 2</summary>

The important success signal is that the Ingress has rules pointing at the `api` and `web` Services on port `80`. In local clusters, the `ADDRESS` value can vary, so do not overfit to a cloud-style external IP. If `/api` fails but `/` works, inspect the path type and the backend Service endpoints before editing unrelated TLS or annotation settings.

</details>

### Task 3: Create Host-Based Routing

Create an Ingress that routes two different hostnames to the two Services. Host routing is the cleanest way to separate ownership between applications because each team can reason about its own DNS name without sharing path prefixes under one public site.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: host-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
  - host: web.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 80
EOF
```

```bash
kubectl describe ingress host-ingress
```

<details>
<summary>Solution notes for Task 3</summary>

The describe output should show two host rules, each with a `/` prefix and a different backend Service. To test this shape, you need to send the correct `Host` header or configure local DNS. A request without the expected host header can hit a default backend even when the Ingress is perfectly valid.

</details>

### Task 4: Add TLS Termination

Create a self-signed certificate for practice and store it as a Kubernetes TLS Secret. Self-signed certificates are not production material, but they are good for learning because they let you practice the object shape without relying on an external certificate issuer.

```bash
# self-signed, no SAN — modern curl needs --insecure (lab/testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=example.com"

kubectl create secret tls example-tls --cert=tls.crt --key=tls.key
```

```bash
kubectl get secret example-tls
```

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tls-ingress
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - secure.example.com
    secretName: example-tls
  rules:
  - host: secure.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 80
EOF
```

```bash
kubectl describe ingress tls-ingress
```

<details>
<summary>Solution notes for Task 4</summary>

The TLS section should reference `example-tls`, and the Secret must be in the same namespace as `tls-ingress`. If your controller serves a fallback certificate, check the Secret type, namespace, certificate common name or subject alternative names, and controller events. In a production cluster, certificate automation usually owns this Secret rather than a human running `openssl` by hand.

</details>

### Task 5: Clean Up and Verify Success

Clean up the lab resources after you have inspected them. Deleting the Ingress resources first removes external routes before deleting backends, which is the same safe ordering you would normally use during controlled teardown.

```bash
kubectl delete ingress multi-path-ingress host-ingress tls-ingress
kubectl delete deployment api web
kubectl delete svc api web
kubectl delete secret example-tls
rm tls.key tls.crt
```

**Card A: A valid Ingress manifest publishes an address even when no Ingress controller is installed.** A learner creates an Ingress resource in a fresh cluster and expects external routing to function immediately without any controller running.

<details>
<summary>Check your prediction</summary>

Failure layer: control loop reconciliation versus declarative API schema. Next action: inspect the Ingress with `kubectl get ingress` and verify whether an Ingress controller is installed and running; the API server accepts the valid resource schema, but without an active controller reconciling the class, the address field remains unpopulated and external traffic cannot be routed.

</details>

**Card B: A request for /api/v1/users matches the Exact rule on /api/v1 when /api is Prefix.** An operator assumes an Exact match on a shorter path will automatically match all subpath requests before checking broader Prefix rules.

<details>
<summary>Check your prediction</summary>

Failure layer: path matching specification and precedence. Next action: review the path rules in the Ingress resource; an Exact rule on `/api/v1` matches only identical request paths, meaning a request for `/api/v1/users` will evaluate against other matching rules and fall back to the `/api` Prefix rule.

</details>

**Card C: An Ingress TLS Secret in another namespace is selected by name alone.** An administrator stores TLS certificates in a shared system namespace and references the Secret name inside an application Ingress deployed in a different namespace.

<details>
<summary>Check your prediction</summary>

Failure layer: namespace isolation and certificate reference boundaries. Next action: verify the Secret location with `kubectl get secrets -n <namespace>`; the Kubernetes Ingress specification requires TLS Secrets to reside in the exact same namespace as the Ingress resource itself to prevent cross-tenant credential access.

</details>

**Card D: The Ingress object itself proxies packets to the backend Pods.** A newcomer views an Ingress manifest as an active network proxy component rather than a declarative routing specification consumed by a controller.

<details>
<summary>Check your prediction</summary>

Failure layer: control plane resource specification versus data plane packet forwarding. Next action: inspect the controller Pods and backing Services; the Ingress resource is merely configuration metadata stored in etcd, while the separate Ingress controller data plane receives network traffic and forwards connections to backend endpoints.

</details>

**Success Criteria**:

- [ ] Design path-based and host-based Ingress routing for two backend Services.
- [ ] Configure TLS termination with a Kubernetes TLS Secret in the correct namespace.
- [ ] Evaluate whether the cluster has an appropriate IngressClass and controller for the route.
- [ ] Diagnose routing failures with `kubectl describe ingress`, Services, Endpoints, and controller logs.
- [ ] Explain when Gateway API would be a better next design than adding more annotations to Ingress.

### Timed Practice Drills

These drills preserve the exam-speed practice from the original module. Run them only in a disposable namespace or lab cluster. They deliberately repeat small routing shapes so that you can write correct manifests quickly while still explaining why the route should work.

#### Drill 1: Basic Ingress

```bash
# Create service
kubectl create deployment drill-app --image=nginx
kubectl expose deployment drill-app --port=80

# Create Ingress
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: drill-ingress
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: drill-app
            port:
              number: 80
EOF

# Check
kubectl get ingress drill-ingress
kubectl describe ingress drill-ingress

# Cleanup
kubectl delete ingress drill-ingress
kubectl delete deployment drill-app
kubectl delete svc drill-app
```

#### Drill 2: Multi-Path Ingress

```bash
# Create services
kubectl create deployment api --image=nginx
kubectl create deployment web --image=nginx
kubectl expose deployment api --port=80
kubectl expose deployment web --port=80

# Create Ingress
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: multi-path
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web
            port:
              number: 80
EOF

# Verify
kubectl describe ingress multi-path

# Cleanup
kubectl delete ingress multi-path
kubectl delete deployment api web
kubectl delete svc api web
```

#### Drill 3: Host-Based Ingress

```bash
# Create services
kubectl create deployment app1 --image=nginx
kubectl create deployment app2 --image=nginx
kubectl expose deployment app1 --port=80
kubectl expose deployment app2 --port=80

# Create Ingress
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: host-based
spec:
  ingressClassName: nginx
  rules:
  - host: app1.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: app1
            port:
              number: 80
  - host: app2.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: app2
            port:
              number: 80
EOF

# Verify
kubectl get ingress host-based
kubectl describe ingress host-based

# Cleanup
kubectl delete ingress host-based
kubectl delete deployment app1 app2
kubectl delete svc app1 app2
```

#### Drill 4: TLS Ingress

```bash
# Create service
kubectl create deployment secure-app --image=nginx
kubectl expose deployment secure-app --port=80

# Generate certificate
# self-signed, no SAN — modern curl needs --insecure (lab/testing only)
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt -subj "/CN=secure.local"

# Create secret
kubectl create secret tls tls-secret --cert=tls.crt --key=tls.key

# Create Ingress with TLS
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tls-ingress
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - secure.local
    secretName: tls-secret
  rules:
  - host: secure.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: secure-app
            port:
              number: 80
EOF

# Verify
kubectl describe ingress tls-ingress

# Cleanup
kubectl delete ingress tls-ingress
kubectl delete deployment secure-app
kubectl delete svc secure-app
kubectl delete secret tls-secret
rm tls.key tls.crt
```

#### Drill 5: Check IngressClass

```bash
# List IngressClasses
kubectl get ingressclass

# Describe
kubectl describe ingressclass nginx

# Check which is default
kubectl get ingressclass -o jsonpath="{range .items[*]}{.metadata.name}{\"\\t\"}{.metadata.annotations['ingressclass\\.kubernetes\\.io/is-default-class']}{\"\\n\"}{end}"
```

#### Drill 6: Ingress with Annotations

```bash
# Create service
kubectl create deployment annotated-app --image=nginx
kubectl expose deployment annotated-app --port=80

# Create Ingress with annotations
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: annotated-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: annotated-app
            port:
              number: 80
EOF

# Check annotations
kubectl get ingress annotated-ingress -o yaml | grep -A5 annotations

# Cleanup
kubectl delete ingress annotated-ingress
kubectl delete deployment annotated-app
kubectl delete svc annotated-app
```

#### Drill 7: Debug Ingress

```bash
# Create Ingress with wrong service name (intentionally broken)
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: broken-ingress
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nonexistent-service
            port:
              number: 80
EOF

# Debug
kubectl describe ingress broken-ingress
# Look for warnings about backend

# Check ingress controller logs (if installed)
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=10

# Fix: create the missing service
kubectl create deployment fix-app --image=nginx
kubectl expose deployment fix-app --port=80 --name=nonexistent-service

# Verify
kubectl describe ingress broken-ingress

# Cleanup
kubectl delete ingress broken-ingress
kubectl delete deployment fix-app
kubectl delete svc nonexistent-service
```

#### Drill 8: Challenge - Complete Ingress Setup

Without looking at the solution, create deployments named `api` and `frontend`, expose both as ClusterIP Services on port `80`, create an Ingress for host `myapp.local`, route `/api` to `api`, route `/` to `frontend`, add a TLS Secret, verify with `describe`, and clean up everything.

```bash
# YOUR TASK: Complete the challenge in under 7 minutes
```

<details>
<summary>Solution</summary>

```bash
# 1. Create deployments
kubectl create deployment api --image=nginx
kubectl create deployment frontend --image=nginx

# 2. Expose as ClusterIP
kubectl expose deployment api --port=80
kubectl expose deployment frontend --port=80

# 3. Create Ingress
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: challenge-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: myapp.local
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
EOF

# 4. Add TLS
# self-signed, no SAN — modern curl needs --insecure (lab/testing only)
openssl req -x509 -nodes -days 1 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt -subj "/CN=myapp.local"
kubectl create secret tls myapp-tls --cert=tls.crt --key=tls.key

# Update Ingress with TLS
cat << 'EOF' | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: challenge-ingress
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - myapp.local
    secretName: myapp-tls
  rules:
  - host: myapp.local
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api
            port:
              number: 80
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend
            port:
              number: 80
EOF

# 5. Verify
kubectl describe ingress challenge-ingress

# 6. Cleanup
kubectl delete ingress challenge-ingress
kubectl delete deployment api frontend
kubectl delete svc api frontend
kubectl delete secret myapp-tls
rm tls.key tls.crt
```

</details>

## Sources

- [Ingress | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [IngressClass | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/ingress/#ingress-class)
- [Ingress path types | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/ingress/#path-types)
- [Ingress TLS | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls)
- [Services, Load Balancing, and Networking | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/)
- [Service | Kubernetes](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/)
- [Migrating from Ingress | Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/guides/migrating-from-ingress/)
- [Ingress NGINX Retirement: What You Need to Know | Kubernetes Blog](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/)
- [Ingress NGINX Statement | Kubernetes Blog](https://kubernetes.io/blog/2026/01/29/ingress-nginx-statement/)
- [ingress2gateway | Kubernetes SIGs](https://github.com/kubernetes-sigs/ingress2gateway)
- [ingress-nginx kind deployment manifest](https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml) — retired controller; lab/learning use only; see maintained alternatives above

## Next Module

[Module 3.5: Gateway API](../module-3.5-gateway-api/) - The next generation of Kubernetes ingress, with richer route resources and cleaner platform ownership boundaries.

## Learner check

> If you remember only one debugging sentence, make it this: no address points toward controller or class reconciliation, 404 points toward host and path matching, and 503 points toward matched routes with unavailable backends.
