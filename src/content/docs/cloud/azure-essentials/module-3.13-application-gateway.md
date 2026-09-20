---
title: "Module 3.13: Azure Application Gateway — Operator Path"
slug: cloud/azure-essentials/module-3.13-application-gateway
sidebar:
  order: 14
---
**Complexity**: `[COMPLEX]` | **Time to Complete**: 60-90 min | **Prerequisites**: [3.2-vnet](../module-3.2-vnet/), [3.5-dns](../module-3.5-dns/), [3.10-monitor](../module-3.10-monitor/). Start this module by naming who controls each control boundary, because governance is the operational shortcut that prevents ownership disputes during incidents.

## What You'll Be Able to Do

After completing this module, you will be able to reason through the full request path, evaluate control boundaries, and make deliberate runbook and rollback choices when multiple teams share one ingress.

- **Debug** Application Gateway failures by following a request through listener, WAF policy, routing rule, backend HTTP settings, probe, and backend pool.
- **Design** a regional ingress pattern that uses the right boundary: Application Gateway, Front Door, AGIC, Application Gateway for Containers, or an in-cluster ingress controller.
- **Evaluate** WAF, TLS, autoscaling, cost, logging, and migration choices before they become production incidents.
- **Configure** WAF policies with managed and custom rules, narrow exclusions after log review, and a deliberate Detection-to-Prevention workflow.
- **Implement** TLS termination with Key Vault-backed listener certificates and backend HTTP settings that stay aligned with health probe contracts.

The emphasis is operational. You are not only learning which Azure resource to create; you are learning how to keep the resource understandable when many teams depend on it.

## Why This Module Matters

Application Gateway is often described as Azure's Layer 7 load balancer, and that phrase is true, but incomplete. In production, it is a regional traffic appliance that combines HTTP routing, TLS termination, health probing, optional Web Application Firewall protection, autoscaling, and diagnostic logging into one operational control plane. That combination lets platform teams enforce policy and routing before traffic reaches services, which is why it is often the first place teams look when traffic behavior is inconsistent.

The [Application Gateway overview](https://learn.microsoft.com/en-us/azure/application-gateway/overview) is the right entry point, but operations teams need one deeper layer. You must know which component owns hostnames, where TLS terminates, which probe defines readiness, what WAF rule blocks a request, and which log lines prove the answer during an incident. Without that mental map, each team can still correctly explain their own layer and still fail to explain the overall behavior.

Consider a common incident. A checkout API returns `403` for some customers and `502` for others while pods remain ready at the application layer. In this case, the gateway may be following its configuration exactly, so your first question is not "is the app healthy?" but "which regional policy boundary handled this request?" A likely root cause is that WAF blocked a suspicious payload, the backend probe points at the wrong path, or backend TLS expects a different host name. Without a request-path model, teams still chase their own dashboards and miss shared ownership.

Use this flow as your mental map:

```text
client
  -> DNS name
  -> frontend listener
  -> WAF policy
  -> routing rule
  -> backend HTTP settings
  -> health probe
  -> backend pool
  -> application
```

The operator goal is not to memorize every property value. The goal is to know which property answers which question during a design review or an incident, and in practice that means mapping request lifecycle, ownership, and observability together before failure appears.

**Pause and predict:** If a backend service is healthy at `https://api.internal.example.com/ready` but the gateway probe checks `/` with the wrong host header, what will the application team see, and what will the gateway see?

<details>
<summary>Check your prediction</summary>

The application team sees pods reporting Ready in Kubernetes because kubelet probes succeed against `/ready`, while Application Gateway marks the backend pool Unhealthy because probes evaluate root path `/` with an unmatched host header configured in backend HTTP settings. Gateway health requires explicit alignment with backend HTTP settings contracts; a health probe mismatch isolates the target backend from client traffic even when container runtimes report successful container health.
</details>

Production incident triage requires operators to isolate edge routing stages systematically from ingress listener acceptance down to internal transport contracts. Tracing request execution across discrete networking boundaries ensures platform engineers diagnose routing and transport anomalies rapidly without relying on trial-and-error configuration updates during critical service disruptions.

## When App Gateway, Front Door, or AKS Ingress

Start with the traffic boundary. If one boundary cannot hold shared blast radius, then architecture decisions become reactive and expensive.

Application Gateway is regional and VNet-integrated, so it is a strong fit when a workload needs regional HTTP routing, private backend access, WAF, TLS termination, and Azure Monitor diagnostics inside an Azure network boundary. The [components documentation](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-components) is useful for this reason: each component is a separate operational lever you can discuss during design reviews.

Azure Front Door is global, so it becomes the right choice when users are distributed across regions, edge latency matters, global failover is required, or an anycast-style public entry point is needed before traffic reaches regional origins. AKS ingress is cluster-centered, and that model is effective when Kubernetes teams own routes as Kubernetes objects and already have an accepted ingress or Gateway API operating model.

Application Gateway for Containers sits between those two ideas by being Kubernetes-native while preserving an Azure boundary model. It uses the ALB controller and Gateway API-style workflows, and for many teams it is the forward-looking path for container ingress designs where platform and application ownership must be split more clearly.

Use this decision sequence:

1. If users need a global edge, evaluate Front Door first.
2. If traffic must enter a regional VNet and reach private backends, evaluate Application Gateway.
3. If the route lifecycle is owned by Kubernetes teams, evaluate AGIC or Application Gateway for Containers.
4. If the service is internal to the cluster and does not need Azure-managed WAF, use an in-cluster ingress or Gateway API controller.

Use the comparison table as a boundary check, not as a product ranking:

| Requirement | Better first candidate | Why |
|---|---|---|
| Global public web app with multi-region failover | Front Door | The boundary is global before traffic reaches a region. |
| Regional private API in a hub-and-spoke VNet | Application Gateway | The boundary is regional and close to private backends. |
| Existing App Gateway fronts both VMs and AKS | AGIC plus Application Gateway | Reuses the regional gateway while AKS expresses ingress intent. |
| New AKS ingress platform with Gateway API ownership | Application Gateway for Containers | Separates platform-owned gateways from app-owned routes. |
| Cluster-only internal service | AKS ingress or Gateway API controller | A managed regional edge may add cost without adding value. |

Worked example: a public retail site has users in North America and Europe, but each regional API is private inside its VNet. In practice, a strong design is Front Door at the global edge with Application Gateway in each region, because each layer handles a distinct responsibility: global entry/failover at Front Door and regional WAF, private backend routing, and VNet integration at Application Gateway. The same pattern would be overkill for an internal admin tool used by one team in one region, where a private Application Gateway can be enough, or internal AKS ingress can be enough if that tool never needs a managed regional edge.

In review sessions, this example is often a useful anti-pattern detector. Teams that propose both services without defining ownership often report higher incident cost later, because "which team owns the global policy?" becomes a recurring meeting topic. A crisp ownership matrix reduces that cost before production: one team owns the Global Edge, one team owns regional policy, and one team is accountable for route lifecycle and rollback sequence.

> **Stop and think:** Which team owns each boundary in your organization: public DNS, global edge, regional listener, WAF policy, Kubernetes route, certificate, and incident dashboard? If the answer is "everyone," the design needs clearer ownership.

## Provisioning Patterns

Application Gateway has many nested child resources. Provision it as code so listener, rule, probe, WAF, and certificate changes are reviewable together.

A production-shaped deployment normally includes:

- a dedicated Application Gateway subnet;
- a Standard public IP for public gateways;
- a private frontend when internal ingress is required;
- a v2 SKU for new deployments;
- autoscale bounds;
- a separate WAF policy;
- listener certificates from Key Vault;
- explicit backend probes;
- diagnostic settings to Log Analytics.

Do not share the Application Gateway subnet with other resources, size the subnet for scale-out, and keep room for migration work. Many teams reserve at least `/24` for production v2 gateways, because capacity growth and subnet redesign are easier to plan than to execute during an outage.

When planning these resources, treat each line in the list as a capacity surface. The subnet controls possible future autoscale, the WAF policy controls control-plane blast radius, and the diagnostics setting controls time-to-diagnosis. If any of these are undersized or ambiguous, the environment usually fails first under stress, not during a planned maintenance window.

### Terraform Example

This snippet is intentionally compact, because it shows the relationships an operator must review together, not a full reusable module that fits every estate.

```hcl
resource "azurerm_user_assigned_identity" "appgw" {
  name                = "id-appgw-prod-eus"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

resource "azurerm_public_ip" "appgw" {
  name                = "pip-appgw-prod-eus"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = ["1", "2", "3"]
}

resource "azurerm_web_application_firewall_policy" "appgw" {
  name                = "waf-appgw-prod-eus"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  policy_settings {
    enabled                     = true
    mode                        = "Prevention"
    request_body_check          = true
    max_request_body_size_in_kb = 128
  }

  managed_rules {
    managed_rule_set {
      type    = "OWASP"
      version = "3.2"
    }
  }
}

resource "azurerm_application_gateway" "appgw" {
  name                = "agw-prod-eus"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  zones               = ["1", "2", "3"]
  firewall_policy_id  = azurerm_web_application_firewall_policy.appgw.id

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.appgw.id]
  }

  sku {
    name = "WAF_v2"
    tier = "WAF_v2"
  }

  autoscale_configuration {
    min_capacity = 2
    max_capacity = 10
  }

  gateway_ip_configuration {
    name      = "gw-ipcfg"
    subnet_id = azurerm_subnet.appgw.id
  }

  frontend_ip_configuration {
    name                 = "public-fe"
    public_ip_address_id = azurerm_public_ip.appgw.id
  }

  frontend_port {
    name = "https-443"
    port = 443
  }

  ssl_certificate {
    name                = "cert-api"
    key_vault_secret_id = azurerm_key_vault_certificate.api.secret_id
  }

  backend_address_pool {
    name  = "pool-api"
    fqdns = ["api.internal.contoso.example"]
  }

  probe {
    name                                      = "probe-api"
    protocol                                  = "Https"
    path                                      = "/ready"
    interval                                  = 30
    timeout                                   = 10
    unhealthy_threshold                       = 3
    pick_host_name_from_backend_http_settings = true
  }

  backend_http_settings {
    name                                = "https-api"
    protocol                            = "Https"
    port                                = 443
    probe_name                          = "probe-api"
    request_timeout                     = 30
    pick_host_name_from_backend_address = true
    cookie_based_affinity               = "Disabled"
  }

  http_listener {
    name                           = "lst-api"
    frontend_ip_configuration_name = "public-fe"
    frontend_port_name             = "https-443"
    protocol                       = "Https"
    host_name                      = "api.contoso.example"
    ssl_certificate_name           = "cert-api"
  }

  request_routing_rule {
    name                       = "rule-api"
    rule_type                  = "Basic"
    priority                   = 100
    http_listener_name         = "lst-api"
    backend_address_pool_name  = "pool-api"
    backend_http_settings_name = "https-api"
  }
}
```

The design choice is to keep the WAF policy separate from the gateway so security reviewers can focus on WAF behavior while platform reviewers focus on listeners, routes, and backends. This separation also makes rollbacks cleaner because policy and topology have different owners and risk profiles. The probe uses `/ready`, not `/`, because a root path may redirect, render a marketing page, or depend on optional systems, whereas the readiness endpoint should consistently answer whether this backend should receive traffic now.

A useful preflight for this configuration is to validate each relationship before applying resources: listener-hostname, routing-priority order, probe path, and backend TLS assumptions. If any one relationship is not explicitly documented, the change should not be merged because it adds non-determinism to operational ownership.

### Bicep Example

The Bicep model is also nested, and that structure is intentional because each nested resource carries lifecycle and ownership concerns. In production, split this into modules only when ownership boundaries are clear enough to avoid drift from dual ownership.

The same idea applies when the team uses module composition in Terraform. Grouping too early can make review difficult because reviewers cannot quickly isolate what changed in one boundary, especially if WAF or certificate values are updated alongside routing priorities. When you keep the nested relationships coherent, ownership and audit traceability become easier than by trying to micro-separate every block.

```bicep
param location string = resourceGroup().location
param appGatewayName string = 'agw-prod-eus'
param appGwSubnetId string
param keyVaultSecretId string
param backendFqdn string = 'api.internal.contoso.example'

resource publicIp 'Microsoft.Network/publicIPAddresses@2023-11-01' = {
  name: 'pip-appgw-prod-eus'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
  zones: [
    '1'
    '2'
    '3'
  ]
}

resource wafPolicy 'Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies@2023-11-01' = {
  name: 'waf-appgw-prod-eus'
  location: location
  properties: {
    policySettings: {
      enabledState: 'Enabled'
      mode: 'Prevention'
      requestBodyCheck: true
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'OWASP'
          ruleSetVersion: '3.2'
        }
      ]
    }
  }
}

resource appGateway 'Microsoft.Network/applicationGateways@2023-11-01' = {
  name: appGatewayName
  location: location
  properties: {
    firewallPolicy: {
      id: wafPolicy.id
    }
    sku: {
      name: 'WAF_v2'
      tier: 'WAF_v2'
    }
    autoscaleConfiguration: {
      minCapacity: 2
      maxCapacity: 10
    }
    gatewayIPConfigurations: [
      {
        name: 'gw-ipcfg'
        properties: {
          subnet: {
            id: appGwSubnetId
          }
        }
      }
    ]
    frontendIPConfigurations: [
      {
        name: 'public-fe'
        properties: {
          publicIPAddress: {
            id: publicIp.id
          }
        }
      }
    ]
    frontendPorts: [
      {
        name: 'https-443'
        properties: {
          port: 443
        }
      }
    ]
    sslCertificates: [
      {
        name: 'cert-api'
        properties: {
          keyVaultSecretId: keyVaultSecretId
        }
      }
    ]
    backendAddressPools: [
      {
        name: 'pool-api'
        properties: {
          backendAddresses: [
            {
              fqdn: backendFqdn
            }
          ]
        }
      }
    ]
    probes: [
      {
        name: 'probe-api'
        properties: {
          protocol: 'Https'
          path: '/ready'
          interval: 30
          timeout: 10
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: true
        }
      }
    ]
    backendHttpSettingsCollection: [
      {
        name: 'https-api'
        properties: {
          protocol: 'Https'
          port: 443
          requestTimeout: 30
          pickHostNameFromBackendAddress: true
          probe: {
            id: resourceId('Microsoft.Network/applicationGateways/probes', appGatewayName, 'probe-api')
          }
        }
      }
    ]
    httpListeners: [
      {
        name: 'lst-api'
        properties: {
          protocol: 'Https'
          hostName: 'api.contoso.example'
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', appGatewayName, 'public-fe')
          }
          frontendPort: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGatewayName, 'https-443')
          }
          sslCertificate: {
            id: resourceId('Microsoft.Network/applicationGateways/sslCertificates', appGatewayName, 'cert-api')
          }
        }
      }
    ]
    requestRoutingRules: [
      {
        name: 'rule-api'
        properties: {
          ruleType: 'Basic'
          priority: 100
          httpListener: {
            id: resourceId('Microsoft.Network/applicationGateways/httpListeners', appGatewayName, 'lst-api')
          }
          backendAddressPool: {
            id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGatewayName, 'pool-api')
          }
          backendHttpSettings: {
            id: resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appGatewayName, 'https-api')
          }
        }
      }
    ]
  }
}
```

Before merging a provisioning change, review subnet size, SKU, WAF policy attachment, certificate source, probe paths, rule priorities, diagnostics, and rollback plan.

## WAF Policy Design

Application Gateway WAF is a policy system, not a checkbox. The [WAF overview](https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/ag-overview) explains the managed-rule model, but operators need to understand how policy changes are tested, scoped, and rolled back because each change alters what traffic is allowed or denied at scale. Start with managed OWASP rules, use Detection mode while learning a new application's request profile, and move to Prevention once the false-positive behavior is understood. Do not leave production in Detection mode indefinitely unless the risk is explicitly accepted.

A mature WAF workflow has four principles:

- custom rules are used for business-specific controls;
- managed rules are tuned narrowly;
- false positives are investigated with logs, not guesses;
- every exclusion has an owner and review date.

### Custom Rule Example

This custom rule blocks `/admin` unless the source IP is in the operations CIDR. It reduces exposure but does not replace application authentication.

```hcl
resource "azurerm_web_application_firewall_policy" "appgw" {
  name                = "waf-appgw-prod-eus"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location

  policy_settings {
    enabled = true
    mode    = "Prevention"
  }

  custom_rules {
    name      = "BlockAdminOutsideOps"
    priority  = 10
    rule_type = "MatchRule"
    action    = "Block"

    match_conditions {
      match_variables {
        variable_name = "RequestUri"
      }
      operator     = "BeginsWith"
      match_values = ["/admin"]
    }

    match_conditions {
      match_variables {
        variable_name = "RemoteAddr"
      }
      operator           = "IPMatch"
      negation_condition = true
      match_values       = ["10.20.0.0/16"]
    }
  }

  managed_rules {
    managed_rule_set {
      type    = "OWASP"
      version = "3.2"
    }
  }
}
```

Why this shape? The URI condition identifies the sensitive surface. The source-IP condition limits exposure to operations networks. The application still owns identity and authorization.

This structure is a defensive layer, not an access model, so it narrows only specific risk before requests reach the backend without replacing service-level authentication.

### Tuned Rule and Rate-Limit Example

False positives should be narrowed, not bulldozed. Suppose a legacy search client sends a header named `X-Legacy-Search` that trips one SQL injection rule. In that case, a per-rule exclusion keeps the rest of the SQLi group active and avoids weakening broader protection.

```bash
az network application-gateway waf-policy managed-rule exclusion rule-set add \
  --resource-group rg-edge-prod \
  --policy-name waf-appgw-prod-eus \
  --type OWASP \
  --version 3.2 \
  --group-name "REQUEST-942-APPLICATION-ATTACK-SQLI" \
  --rule-ids 942430 \
  --match-variable "RequestHeaderValues" \
  --match-operator "Equals" \
  --selector "X-Legacy-Search"
```

Rate limiting is a custom-rule problem. This example blocks a login path after 100 matching requests in the configured window, grouping all matching traffic together:

```bash
az network application-gateway waf-policy custom-rule create \
  --resource-group rg-edge-prod \
  --policy-name waf-appgw-prod-eus \
  --name LoginRateLimit \
  --priority 99 \
  --rule-type RateLimitRule \
  --action Block \
  --rate-limit-threshold 100 \
  --group-by-user-session '[{"groupByVariables":[{"variableName":"None"}]}]'

az network application-gateway waf-policy custom-rule match-condition add \
  --resource-group rg-edge-prod \
  --policy-name waf-appgw-prod-eus \
  --name LoginRateLimit \
  --match-variables RequestUri \
  --operator Contains \
  --value "/login"
```

For geo-blocking, use `RemoteAddr` with `GeoMatch` and document the business owner. Country rules are easy to add and easy to forget, so include review cadence in the same change.

### False-Positive Triage Steps

Use this sequence when valid traffic is blocked:

1. Capture timestamp, URL, method, client IP, user action, and correlation ID.
2. Confirm the gateway returned the response; not every `403` is WAF.
3. Query WAF logs for rule ID, action, message, match variable, and selector.
4. Reproduce safely in staging or Detection mode when possible.
5. Decide whether the request is unsafe, malformed, or legitimately blocked by a broad rule.
6. Apply the narrowest exclusion: rule, variable, selector, path, listener, or policy scope.
7. Return to Prevention mode and document why the exception exists.

The [WAF customization guidance](https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/application-gateway-customize-waf-rules-portal) is useful when translating a portal investigation back into code.

### WAF Policy Change Loop

**Pause and predict:** If a checkout payload trips a SQL injection rule because a product name contains suspicious punctuation, which is safer: disabling the SQLi rule group globally or excluding one selector for one path after log review?

<details>
<summary>Check your prediction</summary>

Applying the narrowest per-rule exclusion—identifying the exact rule ID, match variable, and selector after thorough log review—is strictly safer than disabling the entire SQL injection rule group. In Detection mode, the WAF policy logs transaction telemetry without blocking requests, whereas Prevention mode immediately terminates matching requests with HTTP 403 Forbidden. Disabling the entire rule group removes protection across the application, introducing critical security vulnerabilities.
</details>

Production WAF policy management requires strict exception governance and automated audit trails to ensure edge security controls remain intact. Platform teams coordinate policy updates through version-controlled pull requests that document operational justification, ticket references, and scheduled re-evaluation dates for every rule exception. This rigorous lifecycle prevents emergency operational adjustments from degrading the organization's defensive posture over time.

The result you want from a policy change is threefold: reduced noise, unchanged protection level for unrelated flows, and clear evidence for the next review. If one of those is missing, revert and rework the approach before the next deployment window.

## Backend Pools: AKS Integration — AGIC vs AGfC

AKS integration is a control-plane decision, because you are choosing who expresses routing intent and who is allowed to mutate the edge. In this model, the key is not just "what is supported today," but "who owns drift and who can safely change it at 2 a.m."

That perspective matters most during migration windows. If the team cannot answer who can change listener and route ownership during a release freeze, the best architecture decision is not the one with the most features; it is the one with the clearest ownership path.

AGIC, the Application Gateway Ingress Controller, watches Kubernetes Ingress resources and programs an existing Application Gateway. The [AGIC overview](https://learn.microsoft.com/en-us/azure/application-gateway/ingress-controller-overview) remains important because many production clusters use it today, and it documents the operational assumptions around controller-driven updates. Application Gateway for Containers is the successor path for Kubernetes-first Application Gateway designs; the [Application Gateway for Containers overview](https://learn.microsoft.com/en-us/azure/application-gateway/for-containers/overview) describes the newer model built around the ALB controller and Gateway API-style resources.

Backend pools are not only for AKS. Operators commonly mix backend types during migrations, and that mix is usually where ownership assumptions get tested first because each backend class drives different readiness behavior and certificate expectations.

| Backend pattern | Pool entry | Health probe concern | HTTPS-to-backend concern |
|---|---|---|---|
| AKS with AGIC | Pod IPs from Kubernetes endpoints | Align AGIC annotations with pod readiness. | Backend cert and protocol must match AGIC support. |
| App Service | FQDN or private endpoint path | Pick host name from backend settings for multi-tenant hostnames. | SNI and host header usually need the app hostname. |
| VMs or VMSS | NIC, VMSS, private IP, or FQDN | Probe the real app readiness path, not just `/`. | Upload trusted root certs for private CA chains. |
| Mixed migration | Separate pool per backend class | Do not reuse one probe across unlike apps. | Keep backend settings explicit per pool. |

Pick AGIC when:

- an existing Application Gateway already fronts the environment;
- the platform team accepts ARM-level gateway updates from the controller;
- Ingress resources and AGIC annotations are already standardized;
- the gateway also fronts non-Kubernetes backends.

Pick Application Gateway for Containers when:

- you are designing a new AKS ingress platform;
- Gateway API ownership matters;
- app teams need route objects while platform teams own gateways;
- faster Kubernetes route and backend updates are important;
- you can invest in new runbooks and migration testing.

Teams often use both models during migration, but only with explicit ownership boundaries and one migration runbook that names which object type each team owns in each phase.

### AGIC Ingress Example

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: orders
  namespace: apps
  annotations:
    kubernetes.io/ingress.class: azure/application-gateway
    appgw.ingress.kubernetes.io/backend-protocol: "https"
    appgw.ingress.kubernetes.io/health-probe-path: "/ready"
    appgw.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  tls:
    - hosts:
        - orders.contoso.example
      secretName: orders-tls
  rules:
    - host: orders.contoso.example
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: orders
                port:
                  number: 443
```

The important parts are not the annotations themselves. The important contract is that Kubernetes now declares host, path, backend protocol, and probe behavior that will affect an Azure gateway, so route ownership and gateway behavior are encoded in manifests rather than only portal operations.

Because those declarations are in manifest form, ownership questions become deterministic. Reviewers can diff exactly what changed in one rollout and link an unexpected result to either one host routing rule, one probe target, or one TLS contract, instead of searching through portal history.

### AGfC Gateway API Example

Your installed GatewayClass name may differ. Confirm it from your cluster before applying.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: shared-edge
  namespace: platform
spec:
  gatewayClassName: azure-alb-external
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      hostname: "*.apps.contoso.example"
      allowedRoutes:
        namespaces:
          from: Selector
          selector:
            matchLabels:
              traffic.kubedojo.io/allowed: "true"
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: orders
  namespace: apps
spec:
  parentRefs:
    - name: shared-edge
      namespace: platform
  hostnames:
    - orders.apps.contoso.example
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: orders
          port: 8080
```

This example separates ownership. The platform namespace owns the Gateway, and the app namespace owns the HTTPRoute only if route policy allows it. That is easier to review than a shared Ingress object with many annotations because role boundaries are explicit.

**Pause and predict:** In a shared cluster, what outage can happen if any namespace can claim any hostname on the shared gateway?

<details>
<summary>Check your prediction</summary>

On a shared AGIC or Kubernetes Ingress gateway lacking admission control, a workload in another namespace can define an Ingress with the same production hostname and hijack incoming production traffic. Application Gateway for Containers mitigates this risk by providing `allowedRoutes` policies on the parent Gateway listener, allowing platform administrators to strictly restrict which namespaces can attach routes to specific hostnames.
</details>

Multi-tenant cluster architecture requires explicit administrative boundaries between shared networking infrastructure and tenant workload definitions. Enforcing tenant isolation at the ingress layer ensures that team namespaces operate independently without interfering with shared edge routing policies. Establishing verifiable admission boundaries provides predictable and secure traffic segregation across complex enterprise environments.

## TLS Termination + Key Vault Cert Sync

Application Gateway can terminate TLS at the listener and then connect to backends over HTTP or HTTPS; for production, prefer HTTPS to the backend unless there is a documented reason not to, because protocol symmetry is often a security assumption in audits. The [TLS overview](https://learn.microsoft.com/en-us/azure/application-gateway/ssl-overview) explains listener-side TLS, and the [backend HTTP settings documentation](https://learn.microsoft.com/en-us/azure/application-gateway/configuration-http-settings) explains backend protocol, host name, timeout, and probe behavior so you do not mix semantics across hops. Key Vault-backed certificates are the usual production pattern, and the [Key Vault certificate integration documentation](https://learn.microsoft.com/en-us/azure/application-gateway/key-vault-certs) covers the managed identity and secret-reference model.

In practice, production TLS design is where many teams discover that staging success is not enough. A shared edge that serves one tenant correctly can still fail another tenant when trust chains or protocol expectations differ, which is why every route model should include explicit TLS and trust chain checks in the same runbook.

### TLS Ownership and Failure Interpretation

Failure interpretation is often split into separate tickets when teams do not agree on which certificate value was expected by which hop. Keep one ownership matrix that maps listener certificate, backend certificate, and probe expected identity per route. If one of those three changes and the others do not, you can identify the likely blast radius before opening an incident in production.

For teams using automation, this matrix can be validated with simple scripted checks: read the listener configuration, read the backend TLS settings, then compare the cert subject expectations against recent rollout notes. This avoids waiting for user symptoms to reveal a drift that should have been caught by design review.

### Rotation Gotchas

**Pause and predict:** When an administrator updates a TLS certificate in Azure Key Vault with a newly issued certificate version, will the Application Gateway HTTPS listener update immediately because the gateway automatically binds to the newest secret?

<details>
<summary>Check your prediction</summary>

No. Microsoft Learn strongly recommends configuring a versionless secret identifier for automated rotation; specifying a versioned secret ID pins the gateway to that specific revision indefinitely. Application Gateway instances do not update instantly; they poll Azure Key Vault periodically every four hours and also synchronize whenever an explicit gateway configuration change occurs. Furthermore, if Key Vault access fails due to expired managed identity credentials or network firewall restrictions, the associated HTTPS listener is automatically disabled to prevent unencrypted or broken TLS handshakes.
</details>

Production certificate operations require active monitoring of the actual TLS handshake presented at the frontend listener rather than relying solely on Key Vault audit events. Synthetic monitoring agents should establish TLS connections from external endpoints and alert when listener expiry counters drop below thirty days. This operational pattern verifies that rotation pipelines, identity assignments, and networking routes remain fully functional before certificate expiration impacts end users.

### Chain Order

Certificate chain problems are painful because some clients cache intermediates and others do not. Test with a clean client and verify the leaf certificate, intermediates, hostname, expiry, and trust chain because partial trust is a common source of intermittent failures.

### Backend mTLS

Backend TLS validates the backend to the gateway. Backend mTLS also validates the gateway to the backend, which creates mutual trust but also adds certificate lifecycle burden. Use mTLS when the backend requires client-certificate authentication or compliance demands it, but only if automation is mature enough to handle that extra complexity.

TLS troubleshooting sequence:

1. DNS resolves to the expected frontend.
2. Listener serves the expected certificate.
3. Certificate includes the hostname and is not expired.
4. Chain is complete.
5. Gateway identity can read the Key Vault secret.
6. Backend setting uses the expected protocol, port, host name, and SNI behavior.
7. Probe status matches application readiness.

## Autoscaling + Cost

Application Gateway v2 supports autoscaling, and the [autoscaling documentation](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-autoscaling-zone-redundant) is the starting point for how minimum and maximum capacity behave. Autoscaling does not remove capacity planning; you still choose minimum capacity for baseline reliability and maximum capacity for cost and blast-radius control.

Capacity units represent consumption across compute, persistent connections, and throughput. The [pricing documentation](https://learn.microsoft.com/en-us/azure/application-gateway/understanding-pricing) defines one capacity unit as the highest pressure among one compute unit, 2,500 persistent connections, or 2.22 Mbps throughput, which is why one metric can look healthy while another saturates behavior. A traffic pattern with many long-lived connections can stress the gateway differently than a burst of small requests.

```text
capacity_units = max(
  current_compute_units,
  current_connections / 2500,
  throughput_mbps / 2.22
)
```

Worked example: if the gateway reports 18 compute units, 50,000 current connections, and 16 Mbps throughput, the estimate is `max(18, 20, 7.2)`, so current capacity pressure is about 20 capacity units. If autoscale minimum is two instances, you are already reserving roughly that baseline because each instance maps to 10 reserved capacity units, and scale-up thresholds should reflect workload volatility around that baseline.

Autoscaling rules of thumb:

- keep production minimum capacity high enough for normal traffic;
- set maximum capacity deliberately and alert before it is reached;
- load test WAF-enabled traffic, not just pass-through traffic;
- isolate noisy or regulated applications when shared capacity is risky;
- treat scale events as signals worth reviewing after incidents.

Cost-lens checklist:

- Does the design need both Front Door and Application Gateway, or only one boundary?
- Are dev and test gateways scaled down with explicit maximums?
- Are zones required for the workload and region?
- Are Log Analytics retention and WAF log volume estimated?
- Are Key Vault, public IP, DNS, data transfer, and monitoring included?
- Is a dedicated gateway justified by isolation, compliance, or ownership?
- Is the WAF policy scoped so inspection work matches real exposure?

Cost decisions should be tied to reliability decisions. A shared gateway may be cheaper, but one noisy tenant can affect many services. Dedicated gateways cost more, but they can make ownership and blast radius clearer.

That does not mean cost is ignored for architecture reasons, and it does not mean reliability always wins automatically. It means cost and reliability should be compared in the same table, with explicit owners for when each choice is expected to break and who will absorb that break.

### Capacity Incident Ladder

Think about autoscaling in three tiers: normal, warning, and emergency. In normal, keep minimum capacity high enough for healthy baseline traffic and document why that floor was chosen. In warning, watch sustained pressure against max capacity and route ownership at the same time, because pressure often points to one or two teams owning incompatible release assumptions. In emergency, isolate problematic workloads or temporarily adjust routing before scaling becomes a masking action for broader contract mismatch.

This ladder makes two things explicit: first, that scaling decisions are always coupled to ownership, and second, that cost limits should be changed only after proving whether the issue is capacity, route policy, or backend readiness. If issue classification is absent, autoscaling becomes a temporary patch and the same alert will return with a bigger threshold.

## Monitoring + Diagnostics

Application Gateway without logs is a black box, so enable diagnostics before sending production traffic; otherwise incident response begins with guesswork. Send access logs and WAF logs to Log Analytics, and route metrics to Azure Monitor alerts. For operational clarity, keep one set of dashboards that maps each metric to an expected on-call owner.

Use the [monitoring documentation](https://learn.microsoft.com/en-us/azure/application-gateway/monitor-application-gateway) and [diagnostics documentation](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-diagnostics) to confirm the right categories for your SKU and collection mode, because different SKUs and WAF settings emit different log shapes.

A useful dashboard answers these questions:

- Are requests reaching the gateway?
- Which listeners and backend pools are active?
- Which backends are unhealthy?
- Which status codes changed?
- Which WAF rules are firing?
- Are capacity units, connections, or latency rising?

### KQL: 5xx by Backend Pool

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.NETWORK"
| where Category == "ApplicationGatewayAccessLog"
| where httpStatus_d between (500 .. 599)
| summarize Requests=count(), ExampleUri=any(requestUri_s)
  by bin(TimeGenerated, 5m), Resource, backendPoolName_s, httpStatus_d
| order by TimeGenerated desc
```

This query starts from user-visible failure and groups by backend pool. If one pool dominates, the incident is probably not gateway-wide. Use that signal with 5xx totals to distinguish localized backend contract issues from shared gateway failures before changing autoscaling or WAF defaults.

### KQL: WAF Blocks by Rule

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.NETWORK"
| where Category == "ApplicationGatewayFirewallLog"
| where action_s in ("Blocked", "Block")
| summarize Blocks=count(), ExampleMessage=any(message_s)
  by bin(TimeGenerated, 15m), Resource, ruleId_s, requestUri_s, clientIp_s
| order by Blocks desc
```

This query turns "the WAF broke checkout" into evidence: rule ID, URI, client IP, count, and time window. If one rule ID clusters across one URI and one source range, you are often dealing with one application behavior shift. If one source generates many URIs, you may have automation, attack traffic, or policy scope tuning needs.

### KQL: Latency and Error Trend

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.NETWORK"
| where Category == "ApplicationGatewayAccessLog"
| summarize
    Requests=count(),
    P95LatencyMs=percentile(timeTaken_d * 1000, 95),
    Errors=countif(httpStatus_d >= 500)
  by bin(TimeGenerated, 10m), backendPoolName_s
| extend ErrorRate = todouble(Errors) / todouble(Requests)
| order by TimeGenerated desc
```

Use this query with the WAF and 5xx output so your team can answer whether incidents are transport, application, or policy in origin. A spike in 5xx with flat WAF blocks often points toward probe or backend capacity. A spike in WAF blocks with steady 5xx may be policy tuning before deployment.

Metric alerts should cover unhealthy host count, 5xx spikes, WAF blocked request spikes, capacity approaching maximum, current connections, response latency, and certificate expiration inventory.

When those metrics are aligned with ownership, you get a practical incident response loop: detect, classify, execute, and verify with one owner per step. That avoids duplicate actions by multiple teams that otherwise respond to the same dashboard.

Build a post-incident memo template around those same metrics, because templates reduce memory dependence during late-night incidents. The template should include: observed behavior, likely control ownership, first mitigation attempt, final root cause hypothesis, and one preventive action. Teams that adopt this pattern often reduce mean time to clarity and improve audit readiness because each incident leaves behind reusable operating knowledge.

Teams that keep that evidence package current typically add one line per change request: what ownership boundary changed, what was validated, what failed the first time, and who will close the loop on rollback. This practice avoids discovering ownership questions after an alert fires, and it also reduces the number of ambiguous change approvals because every reviewer has the same expected signal before pressing merge. It turns the runbook into a control-plane artifact rather than a historical postmortem folder, which is why operators can keep speed while still improving reliability.

## Reliability Operating Routine for Shared Ingress

The same artifact that protects architecture clarity during planning also protects it during incidents: a boundary-aware runbook that is updated whenever the gateway topology changes. In practice, that runbook starts with three claims that should already be accepted in the design review. First, each request has a single traceable path from DNS to backend. Second, each control boundary has one accountable owner for change, validation, and rollback. Third, any operational exception should include a bounded time window and an owner responsible for removal.

Treat the runbook as a living contract that sits beside your infrastructure code. A common anti-pattern is to treat YAML and Terraform as the source of truth but leave operational ownership in meeting notes that are never revisited. When the runbook is explicit, routing-policy changes, TLS certificate lifecycle actions, and WAF exception handling become predictable, because every change includes "who changes this", "how they validate it", and "what happens if it misbehaves." This does not replace architecture checks; it removes ambiguity from them.

A practical pre-change review for this module should include this sequence:

1. Confirm the request boundary for the change (global edge, regional gateway, or cluster routing).
2. Verify readiness probes and readiness semantics against the target workload, including host and path contract.
3. Confirm WAF mode, exclusion scope, and the expected owner for any temporary Detection or exception.
4. Validate certificate chain assumptions and whether the source-of-truth for certificate updates is shared.
5. Validate rollback order: what can be reverted first, what requires downstream coordination, and which alert must clear before final sign-off.

For each step, keep documentation concrete by writing a one-line "expected evidence" statement in the change description. That evidence can be a log ID, a query output assertion, a dashboard condition, or a manual command output, but it should be testable without guessing. If a reviewer cannot identify that evidence before approval, the change is not ready. This simple rule often catches the difference between a theoretical design and an operation-ready one.

Ownership should be explicit before any production rollout for shared boundaries. For an AGIC workflow, that means someone owns the gateway-controller reconciliation behavior, someone owns Kubernetes route intent, and someone owns the WAF policy governance process. For an Application Gateway for Containers rollout, that means someone owns the Gateway object lifecycle and someone owns the route object policy envelope. For a single-namespace team, that can be one person in some environments, but it is still the same accountability model: one name for each control plane action and one name for rollback.

Do not skip staged observability validation because logging is what keeps the incident loop fast. The first release can test only log shape and alert state without business traffic if needed. The second release can validate policy response under controlled synthetic traffic. The third release can complete full synthetic path replay end-to-end. This staging sequence is slower than a direct full rollout, but it reduces the number of unknown unknowns that appear at 2 a.m., because the team already knows whether request mapping, probe health, and WAF policy behavior stay stable under controlled pressure.

When you hit a migration, keep capacity and ownership logic in one sequence instead of spreading it across tools and meetings. In a v1 to v2 migration, for example, the first checkpoint is topology equivalence, the second is WAF posture equivalence, and the third is observability equivalence. In all three checkpoints, ask a single team owner to sign that the equivalent behavior is proven; otherwise your team may have technically completed migration tasks while still changing semantics by accident. This model also works for certificate rotation or policy changes because the same three checkpoints still apply: topology, policy, and observability.

If a design exercise shows pressure to add shared boundaries quickly, use the runbook to prevent accidental broadening. Ask whether each new requirement should change boundary, ownership, or both. If both change, require an explicit migration plan with rollback conditions and at least one rehearsal. If only one changes, keep the other stable. That rule sounds procedural, but it is the same guardrail teams use to stop healthy technical debt from becoming a recurring incident source.

## Production Gotchas

### Gotcha 1: v1 to v2 Is a Migration

Moving from a legacy v1 gateway to v2 is not a casual SKU toggle. Treat it as a migration with new capacity, copied configuration, certificate validation, WAF review, DNS cutover, rollback, and parallel observability. The [v1/v2 migration guidance](https://learn.microsoft.com/en-us/azure/application-gateway/migrate-v1-v2) exists because the change affects more than a billing label.

### Gotcha 2: WAF Blocks Valid Traffic

During a launch, a form field can trigger a managed WAF rule. The fastest action is to disable a rule group globally, but that often creates a hidden blast radius. The safer operator action is slower and more deliberate: find the rule ID, confirm the match variable and selector, reproduce safely, scope the exclusion to the affected path or policy, and document the reason before returning the control posture to a bounded state.

### Gotcha 3: Certificate Sync Timing

A certificate is renewed in Key Vault, but the gateway still serves the old certificate. The likely causes are identity access, versioned secret IDs, sync timing, or an incomplete certificate object. Always monitor the served listener certificate and rehearse renewal before expiration week.

### Gotcha 4: Probe Contract Drift

An application can change readiness from `/ready` to `/healthz`, or make readiness depend on a database that is not required for degraded service. When that happens, Application Gateway marks backends unhealthy because the probe contract changed, even if the app appears usable for partial scenarios. Treat probes as release contracts, not incidental URLs, because teams that skip this contract review repeatedly generate false incidents after releases.

A practical way to prevent contract drift is to include probe path and readiness expectations in every rollout checklist. The checklist should include expected response body behavior, expected host name, and whether the app can return ready during partial degradation. If this contract is missing, release teams should pause and complete it before enabling any route promotion.

## Decision Framework

### App Gateway vs Front Door

| Decision factor | Application Gateway | Front Door |
|---|---|---|
| Primary boundary | Regional VNet edge | Global public edge |
| Best fit | Private regional apps, regional APIs, AKS ingress | Global web apps, multi-region failover |
| Backend reachability | Strong for private VNet backends | Strong for origin groups and edge routing |
| WAF placement | Regional | Global edge |
| Latency model | Users reach a regional gateway | Users reach a nearby edge |
| Operational risk | Regional blast radius | Broad edge-config blast radius |
| Use both when | Regional private ingress still matters | Global routing needs protected regional origins |

### SKU v1 vs v2

| Decision factor | v1 | v2 |
|---|---|---|
| New deployments | Avoid for modern production | Preferred default |
| Autoscaling | Legacy behavior | Built-in v2 autoscaling |
| Zone redundancy | Limited compared with v2 | Supported in eligible regions |
| Public IP model | Legacy | Standard public IP model |
| Feature investment | Legacy | Current strategic path |
| Operator action | Stabilize and migrate | Standardize and automate |

## Did You Know?

- Application Gateway is regional even when it has a public frontend.
- Detection mode logs WAF matches without blocking, which is useful during onboarding.
- A backend can be healthy in Kubernetes but unhealthy to Application Gateway because of host header, path, TLS, or probe status mismatch.
- Versionless Key Vault secret IDs are usually preferred when automatic certificate rotation is intended.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Using `/` as a health probe because it is easy to remember | The default path responds during early testing | Probe the app's real readiness endpoint and expected host header. |
| Creating an undersized Application Gateway subnet | Teams size for today's instance count | Reserve subnet space for max autoscale, private frontend IPs, and v2 migration. |
| Leaving WAF in Detection mode forever | Teams fear false positives | Review logs, tune narrow exclusions, then move to Prevention with rollback. |
| Disabling broad WAF rule groups for one false positive | Incident pressure rewards fast unblocks | Use per-rule exclusions tied to a selector, path, and owner. |
| Pinning a Key Vault certificate version accidentally | Scripts copy the full secret ID | Use versionless secret IDs for normal rotation. |
| Letting AGIC and Terraform fight over gateway child resources | Both tools seem authoritative | Give controller-generated listeners, pools, and rules one owner. |
| Choosing Front Door or Application Gateway without naming the traffic boundary first | Feature lists look similar | Decide global edge, regional VNet edge, or cluster ingress before selecting product. |

## Quiz

### Question 1

A private regional API runs in AKS. Users connect through corporate networks. The platform team wants WAF, Key Vault-backed TLS, private backend access, and Azure Monitor diagnostics. Which entry point is the best first candidate?

A. Azure Front Door only
B. Application Gateway with AKS integration
C. Public Kubernetes LoadBalancer service
D. Azure Traffic Manager only

<details>
<summary>Answer</summary>

**Correct: B.** The workload is regional and private-backend oriented. Application Gateway can sit in the VNet, terminate TLS, apply WAF policy, and integrate with AKS.

</details>

### Question 2

Checkout POST requests are blocked after WAF moves to Prevention mode. Logs show one managed rule firing on one request field. What should the operator do first?

A. Disable the whole managed rule group globally
B. Move the policy to Detection forever
C. Apply the narrowest justified exclusion after confirming rule ID, field, selector, and path
D. Remove WAF from the listener

<details>
<summary>Answer</summary>

**Correct: C.** The evidence points to a scoped false positive. Broad disables reduce protection for unrelated traffic.

</details>

### Question 3

A new multi-team AKS platform wants platform engineers to own listeners and application teams to own routes only for allowed namespaces. Which model best expresses that ownership?

A. One public LoadBalancer service per namespace
B. AGIC annotations on arbitrary Ingress objects without admission policy
C. Gateway and HTTPRoute resources through Application Gateway for Containers
D. Manual listener edits in the portal after every release

<details>
<summary>Answer</summary>

**Correct: C.** Gateway API separates infrastructure-owned Gateway configuration from application-owned HTTPRoute configuration, which matches the ownership requirement.

</details>

### Question 4

A listener still serves an old certificate after a renewed certificate appears in Key Vault. What should you check first?

A. Backend replica count
B. Gateway identity access and whether the listener uses a versioned or versionless secret ID
C. DNS MX records
D. WAF CRS version

<details>
<summary>Answer</summary>

**Correct: B.** Certificate sync depends on secret access and the referenced secret ID. Backend replicas, MX records, and WAF rules do not explain the listener certificate.

</details>

### Question 5

An architecture review must **design** a **regional** **ingress** pattern with an explicit traffic **boundary**. A global retail brand needs multi-region failover at the edge, WAF on private regional APIs inside hub-spoke VNets, and no managed Azure Layer-7 hop for an internal-only batch job in a single AKS cluster. Which pairing best matches those boundaries?

A. Azure Front Door at the global edge, Application Gateway per region for private APIs, and in-cluster ingress only for the internal batch job
B. Application Gateway only for global users and every backend, including the internal batch job
C. Azure Load Balancer Standard as the sole public HTTPS entry with hostname-based routing to all workloads
D. Azure API Management as the only edge for browser traffic, regional APIs, and Kubernetes workloads

<details>
<summary>Answer</summary>

**Correct: A.** [Azure Front Door](https://learn.microsoft.com/en-us/azure/frontdoor/front-door-overview) fits the global edge and failover boundary; [Application Gateway](https://learn.microsoft.com/en-us/azure/application-gateway/overview) fits regional VNet-integrated WAF and private backends. An internal-only cluster service does not need a regional managed gateway when cluster ingress is enough. Load Balancer operates at Layer 4 and does not provide Application Gateway-style HTTP host routing. API Management is an API lifecycle and policy plane, not a substitute for a global CDN-style web edge plus regional private ingress.

</details>

### Question 6

During application onboarding, `/checkout` POST bodies trip OWASP rule `942430` after the team moves a WAF policy to Prevention. Security asks you to **configure** the **WAF** **policy** with the narrowest defensible change. Firewall logs show one `RequestHeaderValues` selector on a legacy header. What should you do first?

A. Disable the entire SQL injection managed rule group for all listeners
B. Add a per-rule exclusion for rule `942430` scoped to that header selector after confirming the log evidence, then keep other SQLi rules active
C. Detach the WAF policy from the Application Gateway
D. Leave Prevention mode but stop collecting WAF logs to reduce noise

<details>
<summary>Answer</summary>

**Correct: B.** The [WAF customization guidance](https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/application-gateway-customize-waf-rules-portal) expects operators to tune with evidence: identify rule ID, match variable, and selector, then apply the smallest exclusion. Disabling a whole rule group weakens unrelated traffic. Removing WAF or ignoring logs removes the feedback loop you need before returning to a bounded Prevention posture.

</details>

### Question 7

Pods show Ready in Kubernetes, but Application Gateway reports unhealthy backends. The application now exposes `/healthz`, while the gateway probe still calls `/ready` with a host header that does not match backend HTTP settings. As the operator responsible for how you **implement** **TLS** and probe contracts, what is the best next step?

A. Increase autoscale `max_capacity` without touching probes or backend settings
B. Update the probe path and host-header behavior to match the readiness contract, then revalidate listener TLS and backend HTTPS settings on the same route
C. Disable health probes so traffic flows while the app team investigates
D. Switch backends to HTTP-only on port 80 without updating documentation or certificates

<details>
<summary>Answer</summary>

**Correct: B.** Probe contract drift is a common cause of false unhealthy backends when applications change readiness paths or host expectations. [Backend HTTP settings](https://learn.microsoft.com/en-us/azure/application-gateway/configuration-http-settings) and [TLS overview](https://learn.microsoft.com/en-us/azure/application-gateway/ssl-overview) should be validated together because hostname, SNI, protocol, and certificate behavior cross both hops. Scaling or disabling probes masks the mismatch and can send traffic to backends that the gateway correctly refuses.

</details>

## Hands-On Exercise

This exercise is local-first, and that means you can complete the Kubernetes reasoning with `kind` or `minikube` before deciding whether to run Azure commands. The Azure CLI section is optional and requires an Azure subscription plus approval to create billable resources, so you can still finish the design practice in a developer workstation without touching cloud resources.

### Setup

Create a local cluster with `kind` so you can validate ownership, route semantics, and manifest-level rollout behavior before adding any Azure-managed edge behavior:

```bash
kind create cluster --name appgw-operator
```

Fallback with `minikube`:

```bash
minikube start -p appgw-operator
```

Create a sample workload:

```bash
kubectl create namespace apps
kubectl -n apps create deployment orders --image=nginx:1.27
kubectl -n apps expose deployment orders --port=8080 --target-port=80
kubectl -n apps get deploy,svc
```

This does not create Azure resources; it gives you local Kubernetes objects for route-design practice and lowers the cost of validating request flow and ownership boundaries.

### Tasks

1. Draw the request path for `orders.contoso.example`: DNS, listener, WAF policy, routing rule, backend setting, probe, service, pod.
2. Write an AGIC-style Ingress for the local `orders` service with host `orders.contoso.example` and probe path `/ready`.
3. Write a Gateway API HTTPRoute for `orders.apps.contoso.example` that attaches to a platform-owned Gateway named `shared-edge`.
4. Draft a WAF false-positive runbook using the KQL queries from this module.
5. Decide whether AGIC or Application Gateway for Containers is a better starting point for a new multi-team AKS ingress platform, and explain why.

Expected artifacts from this exercise:

1. A request map with explicit ownership labels for each hop.
2. One Ingress manifest that proves host and probe intent.
3. One HTTPRoute manifest that proves namespace ownership and route policy boundaries.
4. A WAF runbook with one log query per decision step.
5. A migration recommendation that names who updates policy, who updates routing, and who approves rollback.

### Why this exercise is staged this way

The sequence is deliberate, not accidental. By starting with local path mapping, you force route semantics to come first, then add gateway boundary mechanics, and only at the end test managed platform details. This prevents teams from learning the surface area of Azure commands before they agree on what the request path should actually mean.

The second stage is WAF reasoning, because operators need to connect false-positive decisions to evidence before they rely on policy knobs. The third stage is governance modeling, where you connect manifest intent to migration order, approval owner, and rollback owner. That sequence avoids the common failure mode where teams can deploy a manifest but still disagree on who owns an incident.

If you keep this order, local verification produces stronger value: route changes are testable in minutes, WAF policy behavior is explicit by design, and only then does Azure execution become a controlled deployment of an agreed ownership contract. This is the same operational pattern teams use for reliability-heavy architectures, because ownership clarity is only cheap while you still have a clear blast radius.

If you are using this exercise in a team brown-bag, reviewers should evaluate it by tracing one synthetic request from DNS to backend and confirming that every hop has a defined owner and a defined rollback condition.

### Azure Subscription Note

Only run these commands if you have an Azure subscription and permission to create billable networking resources:

```bash
az group create \
  --name rg-appgw-operator-lab \
  --location eastus

az network vnet create \
  --resource-group rg-appgw-operator-lab \
  --name vnet-appgw-operator-lab \
  --address-prefixes 10.42.0.0/16 \
  --subnet-name snet-appgw \
  --subnet-prefixes 10.42.0.0/24

az network public-ip create \
  --resource-group rg-appgw-operator-lab \
  --name pip-appgw-operator-lab \
  --sku Standard \
  --allocation-method Static
```

Clean up optional Azure resources when finished:

```bash
az group delete \
  --name rg-appgw-operator-lab \
  --yes
```

Confirm that the resource group deletion has initiated successfully by querying group state or reviewing the Azure activity log. Removing the lab resource group ensures that provisioned virtual networks, public IP addresses, and gateway instances do not accumulate unexpected infrastructure costs in training subscriptions.

**Card A: If Kubernetes reports Ready, Application Gateway must also mark the backend healthy.** An operations engineer observes that application pods report Ready status in Kubernetes and assumes Application Gateway will automatically route client traffic to those backend instances without health probe errors. The engineer assumes pod readiness probes inside the cluster directly govern gateway health states.

<details>
<summary>Check your prediction</summary>

Failure layer: Kubernetes container readiness evaluation versus external Application Gateway health probe configuration. Next action: inspect backend health using `az network application-gateway show-backend-health` and verify that backend HTTP settings match the application's actual health endpoint path and host header contract.
</details>

**Card B: Disabling the whole SQLi managed rule group is the safe first fix for one checkout false positive.** During an e-commerce deployment, valid checkout transactions are blocked by a SQL injection managed rule because product descriptions contain specific punctuation symbols. An on-call engineer proposes disabling the entire SQL injection rule group across the WAF policy to restore checkout functionality immediately.

<details>
<summary>Check your prediction</summary>

Failure layer: global threat protection suppression versus targeted rule exclusion. Next action: review WAF logs in Log Analytics to identify the specific rule ID, match variable, and selector, then configure a scoped exclusion for that precise selector while retaining Prevention mode for all other traffic.
</details>

**Card C: On a shared AGIC gateway, any namespace can safely claim any hostname.** A development team deploys a new service into a non-production Kubernetes namespace and creates an Ingress resource targeting a shared corporate hostname. The team assumes the shared AGIC controller isolates hostnames across namespaces and prevents unauthorized routing conflicts automatically.

<details>
<summary>Check your prediction</summary>

Failure layer: shared Ingress controller route collision and lack of namespace admission control. Next action: implement Kubernetes admission policies to validate hostname ownership across namespaces, or migrate to Application Gateway for Containers using Gateway API `allowedRoutes` policies to restrict route attachments.
</details>

**Card D: A renewed Key Vault certificate updates the Application Gateway listener immediately because the gateway always uses the latest version.** A platform administrator uploads a renewed TLS certificate to Azure Key Vault and expects the Application Gateway HTTPS listener to begin serving the new certificate immediately without configuration intervention. The administrator assumes the gateway synchronizes renewed secret versions continuously in real time without operational delay.

<details>
<summary>Check your prediction</summary>

Failure layer: Key Vault secret versioning reference and polling synchronization interval. Next action: ensure the gateway configuration references a versionless secret ID, account for the standard four-hour Key Vault polling interval, and trigger an explicit gateway update or review managed identity access policies if immediate rotation is required.
</details>

**Success Criteria**:

Your success is complete when the design artifacts clearly show ownership and control decisions, not just command output:

- [ ] Your diagram separates global, regional, and Kubernetes boundaries.
- [ ] Your Ingress manifest makes host, service, and probe intent clear.
- [ ] Your HTTPRoute answer explains who owns the parent Gateway.
- [ ] Your WAF runbook requires logs before exclusions.
- [ ] Your AGIC vs AGfC answer explains ownership and rollout behavior, not just product names.
- [ ] You can explain what changed in one request path end-to-end without opening ticket systems.

If you finish without Azure credentials, submit the path diagram and manifest diffs, then validate that each checklist line has a reviewer owner assigned before your next merge cycle.

## Sources

- [Azure Application Gateway overview](https://learn.microsoft.com/en-us/azure/application-gateway/overview)
- [Application Gateway autoscaling and zone redundancy](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-autoscaling-zone-redundant)
- [Understanding pricing for Azure Application Gateway and Web Application Firewall](https://learn.microsoft.com/en-us/azure/application-gateway/understanding-pricing)
- [Application Gateway TLS overview](https://learn.microsoft.com/en-us/azure/application-gateway/ssl-overview)
- [Use Key Vault certificates with Application Gateway](https://learn.microsoft.com/en-us/azure/application-gateway/key-vault-certs)
- [Application Gateway backend HTTP settings](https://learn.microsoft.com/en-us/azure/application-gateway/configuration-http-settings)
- [Monitor Application Gateway](https://learn.microsoft.com/en-us/azure/application-gateway/monitor-application-gateway)
- [Application Gateway WAF overview](https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/ag-overview)
- [Customize WAF rules for Application Gateway](https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/application-gateway-customize-waf-rules-portal)
- [Application Gateway Ingress Controller overview](https://learn.microsoft.com/en-us/azure/application-gateway/ingress-controller-overview)
- [Application Gateway for Containers overview](https://learn.microsoft.com/en-us/azure/application-gateway/for-containers/overview)
- [Migrate Azure Application Gateway and WAF from v1 to v2](https://learn.microsoft.com/en-us/azure/application-gateway/migrate-v1-v2)

## Next Module

Continue with [Module 3.14 — App Service](../module-3.14-app-service/) for the next track checkpoint, or move to the [Enterprise Hybrid Cloud track](../../enterprise-hybrid/) if your context requires a broader hybrid architecture view.
