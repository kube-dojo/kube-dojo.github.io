---
revision_pending: false
title: "Part 5 Cumulative Quiz: Services and Networking"
sidebar:
  order: 4
---

> **Complexity**: `[MEDIUM]` — connect three application networking mechanisms under time pressure.
>
> **Time to Complete**: 65–80 minutes, including the exercise and review.
>
> **Prerequisites**: [Module 5.1: Services](../module-5.1-services/), [Module 5.2: Ingress](../module-5.2-ingress/), and [Module 5.3: NetworkPolicies](../module-5.3-networkpolicies/).

## Learning Outcomes

After completing this cumulative module, you will be able to investigate each networking handoff and explain what evidence supports your decision:

- Diagnose Service discovery and forwarding failures by separating DNS, selectors, ready endpoints, and port mappings.
- Choose a Service exposure type and explain where NodePort, LoadBalancer, headless discovery, and ExternalName change the client contract.
- Trace an HTTP request through an Ingress controller, its routing rule, a Service, and the selected application pods.
- Evaluate NetworkPolicy ingress and egress isolation, additive allow rules, and selector scope against a concrete traffic path.
- Verify a networking change with positive and negative tests, then explain what the evidence does and does not prove.

## Why This Module Matters

Hypothetical scenario: a checkout client resolves `api.orders.svc.cluster.local`, but its request times out after a rollout. The application pods appear Ready, an Ingress object exists, and a NetworkPolicy was recently applied. Those observations describe different layers. A DNS answer establishes a name mapping, while an EndpointSlice describes eligible destinations, an Ingress controller handles external HTTP routing, and a policy-capable network plugin decides whether a packet may pass. None of those observations alone proves that the complete request path works.

In Modules 5.1–5.3, each mechanism could be studied separately. This quiz asks you to combine them without treating every timeout as the same problem. A Service may select no pods, or it may select ready pods but forward to the wrong numeric port. An Ingress may define a valid rule while no controller publishes an address. A NetworkPolicy may allow destination ingress yet leave source egress isolated. The quickest reliable response is to locate the first failed boundary and test one hypothesis at a time.

The eight questions are deliberately scenario based. Try each without opening the answer, write down the observation that makes your choice stronger than the other options, and then inspect the explanations. Set a suggested twenty minute limit for the question set, but use the remaining time for the hands-on exercise and corrections. The time limit is practice guidance, not a claim about the live exam format or passing score. Correct reasoning matters more than racing through YAML that you have not verified.

## Core Content

### Start with the caller and the destination

Begin every networking investigation by naming the caller, destination, protocol, and intended port. A request from an in-cluster Pod to a Service name is different from a request from an external browser to an Ingress host. The first path can work while the second fails because the controller has no published address. Equally, the browser can reach a controller that returns an HTTP error while an internal caller cannot resolve a cross-namespace Service name. Writing the actual path prevents one layer from standing in for another.

For an internal call, separate the name from the backend. Cluster DNS can resolve a normal ClusterIP Service even when its selector matches zero pods. Inspect the Service and its EndpointSlices before changing DNS. The selector must match Pod labels exactly, and the selected pods must be eligible for ordinary Service traffic. A pod that exists but has not become Ready does not prove that the Service has a usable destination. The question is which addresses the Service currently offers to its data plane.

The Service name also has a namespace context. A Pod in `web` asking for `api` normally looks in its own namespace first. If the Service lives in `orders`, use `api.orders` or its fully qualified form. That change is about name resolution, not Service type or application port. Verify the caller namespace and the Service namespace before changing a deployment. A valid short name in one Pod can refer to a different object, or no object, in another namespace.

Once the name and endpoint set are correct, inspect the three ports without collapsing them into one number. Clients call the Service `port`. The Service sends traffic to the pod's `targetPort`. A NodePort Service also opens its `nodePort` on nodes, with the default allocation range of `30000–32767`. A wrong numeric `targetPort` can leave endpoints populated while requests fail at the workload listener. In that case, changing a selector would destroy useful evidence because selection already worked.

A named `targetPort` has a different failure mode. The name must resolve against a port named in the selected Pod's container specification. If the Service refers to `http` but the container declares `web`, inspect endpoint port resolution instead of treating it like a numeric port that forwards to a closed listener. Record the exact Service port declaration and the container port names. A failed mapping and a wrong reachable number are related, but they do not leave the same evidence behind.

ClusterIP, NodePort, and LoadBalancer Services use selected backends for the normal examples in Module 5.1. ClusterIP provides an internal virtual address; NodePort adds a node-level entry point; LoadBalancer asks surrounding infrastructure to supply an external one. An external address that remains pending says something about provisioning, not necessarily about in-cluster reachability. Test the ClusterIP path and endpoint set separately. A pending external address does not justify changing a healthy Deployment.

Headless and ExternalName Services require a different mental model. A headless Service declares `clusterIP: None` and can publish selected Pod addresses directly for clients that need member discovery. It does not resolve to a ClusterIP. An ExternalName Service returns a DNS alias for an external name; it does not select Pods or create a ClusterIP forwarding path. If a question asks for direct peer discovery, choose headless deliberately. If it asks for a stable internal alias to an existing external DNS name, choose ExternalName and avoid claiming it supplies Kubernetes endpoints.

The Service abstraction also has a node data plane. In the common kube-proxy modes described in Module 5.1, kube-proxy programs kernel forwarding rules rather than carrying every packet through a long-running proxy process. A kube-proxy problem on one node can leave previously programmed rules working for a time. Consequently, an old successful request from that node does not prove the component is currently healthy, and one failed request does not prove every node is affected. Compare the same request from two nodes when node-local forwarding is a plausible branch.

Read command output as evidence with a narrow meaning. `kubectl get service` proves the API object and displayed address exist. `kubectl get endpointslices` shows the destination data published for the Service. `kubectl get pods --show-labels` lets you compare the selector with actual labels. A request from a known caller proves an end-to-end path for that caller at that moment. Keep those claims separate; the difference between object state and packet behavior is the center of this cumulative exercise.

### Follow the external HTTP path

An Ingress is a routing configuration object, not a Service and not the controller implementation. The standard API is `networking.k8s.io/v1`, and `spec.ingressClassName` ties a rule to an intended IngressClass. The controller must watch that class, reconcile the rule, and publish a reachable entry point according to its environment. A valid manifest by itself does not open an external socket. The Service referenced in a backend must still have a matching port and usable endpoints.

For a browser request, write the expected path in order: external client, controller address, host and path rule, Service port, selected endpoint, and application listener. The standard Ingress resource models HTTP and HTTPS routing. A host can match while a path fails, and a path can match while the backend Service is absent. Inspect the Ingress rule and controller status before adjusting Pod labels. Then inspect the referenced Service and its endpoints before assuming the controller is the only problem.

An empty `ADDRESS` field means the controller has not published an address for that Ingress. It does not, by itself, prove that the Service selector is wrong. Check whether an appropriate controller and IngressClass exist, whether the rule names that class, and whether the environment has a way to expose the controller. Conversely, a populated address is only one part of success. A controller may publish an address while the rule points to the wrong Service port or while NetworkPolicy blocks traffic to the pods.

Path types matter because they define matching behavior. `Exact` matches the stated path, while `Prefix` matches a path prefix by segments as taught in Module 5.2. A route for `/api` should not be guessed from a request for `/web`; inspect the host and path together. Host testing should send the intended Host header when the request goes to a controller address. A plain request to an IP may exercise the controller's default behavior rather than the named rule you intended to test.

TLS adds another boundary without changing the underlying Service selector. An Ingress can refer to a TLS Secret for a host, and the controller can terminate HTTPS before forwarding traffic to the backend. If a certificate mismatch appears, inspect hostnames, Secret contents, and controller reconciliation. A healthy ClusterIP Service does not establish that the external certificate is valid. Likewise, a valid certificate does not establish that the Service has ready endpoints. Each observation speaks to one segment of the path.

Use Ingress when the task is HTTP or HTTPS routing by host or path through an installed controller. Use a Service exposure type when the task is to expose a workload at the network transport level without those Ingress rules. This is a design distinction as well as a debugging distinction. A NodePort might help an external packet reach the cluster, but it does not automatically implement the host-based routing or TLS behavior described by a separate Ingress object.

### Apply policy after understanding the path

NetworkPolicy decides allowed connections for Pods selected by its top-level `podSelector`. The policy lives in a namespace, and that top-level selector chooses protected Pods in that namespace. An empty top-level selector selects all Pods there. A policy affects only the directions in `policyTypes`; selected ingress can be isolated while egress remains open, or vice versa. The network plugin must support enforcement for a declared policy to affect packets. The API accepting a policy is not an enforcement test.

Policy rules are additive. If two policies select the same destination Pod, the allowed ingress is the union of their ingress rules. A new policy cannot revoke a path already allowed by another matching policy. To decide whether a connection can start, examine source egress if it is isolated and destination ingress if it is isolated. A packet needs permission on both isolated sides. This explains why editing only the destination policy may leave an outbound timeout unchanged.

`ingress: []` is a rule list with no ingress allowances. For selected Pods isolated for ingress, that denies new ingress connections unless another policy selects them and allows a matching path. An ingress rule containing `from: []` has an empty peer list, which matches all sources for that rule; the rule's port restriction still matters. These two YAML shapes are easy to confuse because both contain empty brackets. They belong to different structural levels and have opposite effects on source selection.

Similarly, `ingress: - {}` supplies one unrestricted ingress allow rule. That is broader than an empty rule list, and it is broad for a reason: the rule has neither peer nor port limits. Translate the YAML into a sentence before applying it. If you intend a default deny, use a selected pod set, an explicit `Ingress` policy type, and no ingress rules. If you intend a narrow allowance, state both the peer identity and the destination port whenever the task requires them.

A peer `podSelector` by itself searches the policy namespace. A `namespaceSelector` selects namespaces using labels on Namespace objects. If both selectors appear in the same `from` item, both conditions must match. If they appear as separate list items, either item can match. One extra dash can therefore change a narrow cross-namespace allowance into a broad union. Verify namespace labels as carefully as Pod labels, because a namespace name does not automatically equal a team-owned label such as `env: production`.

NetworkPolicy ports describe the packet reaching the destination Pod, not merely the number the client typed in a Service URL. A Service might listen on port `80` and forward to application port `8080`; a policy protecting that Pod should be checked against the destination traffic it actually sees. If a client is egress-isolated, DNS queries may also need an explicit egress allowance. A name lookup failure after an egress policy is therefore a useful separate observation from an HTTP connection timeout after successful resolution.

Do not infer policy enforcement from a successful request alone. A positive test shows that one intended caller can pass; it does not show that unintended callers are blocked. A negative test from a Pod with known labels is necessary to test the boundary. If a denied caller still reaches the workload, first verify that the policy selects the destination and that the installed network plugin enforces NetworkPolicy. Then inspect other additive allow rules before concluding that one manifest is ineffective.

**Pause and predict:** A Service has a DNS name, a ClusterIP, and no ready endpoints. Would replacing it with a NodePort make its selected application reachable from outside? Write down what the NodePort adds and what it leaves unchanged before revealing the answer.

<details>
<summary>Prediction answer</summary>

No. NodePort adds a node-level port while the Service still needs eligible backends. Inspect selector labels, readiness, and EndpointSlices before changing the exposure type. An external entry point cannot forward successfully to an empty selected set.

</details>

The bridge from that prediction to the quiz is an evidence rule: identify the earliest empty or incorrect handoff in the path, then fix that handoff without changing layers that already behave as declared.

**Pause and predict:** A NetworkPolicy selects the API Pods, declares `Ingress`, and contains `ingress: []`. A second policy selects the same Pods and allows traffic from labeled frontend Pods on TCP `8080`. Predict which frontend and unrelated clients can connect, assuming the network plugin enforces both policies.

<details>
<summary>Prediction answer</summary>

The selected frontend path can pass because policies combine their allowed paths. An unrelated source has no matching ingress allowance and remains blocked. If the frontend Pod is also egress-isolated, its egress policy must allow the connection too.

</details>

This second prediction connects policy syntax to a live request. The empty list isolates the destination, while the other policy contributes an exception; neither rule can be judged without the selected Pods, port, and source direction.

### Worked decision path

Simulation: an API Deployment has Ready Pods labeled `app: catalog`, while a ClusterIP Service named `catalog` selects `app: catalogue`. A web Pod reports that `catalog.store.svc.cluster.local` resolves, but its HTTP request fails. The simulation supplies those observations only; it does not claim a real incident or measured production outcome. Start by writing the caller namespace, the resolved Service name, and the Service selector. The two label values differ, so the Service cannot derive the intended Pod endpoints from those Pods.

The first check would inspect the Service selector and the backing EndpointSlices, then compare them with labels on Ready Pods. Do not begin by changing the NetworkPolicy or Ingress: this request is internal, the name resolves, and the chosen Service has no selected destinations. If an EndpointSlice nevertheless showed eligible addresses, revisit the hypothesis because some other matching Pods or manually supplied endpoints could change the picture. Evidence should be read from the actual objects, not from the story alone.

Suppose you correct the selector and endpoints appear, but the client still times out. The next check compares the Service `port` and `targetPort` with the container listener. If the numeric target points to `9090` while the application listens on `8080`, populated endpoints are expected and the failure shifts to port translation. If the target is a name missing from the Pod's declared container ports, investigate named-port resolution. Neither case is explained by the original label mismatch after endpoints are repaired.

Finally, suppose the port mapping is correct and a direct test from one labeled web Pod succeeds, while an otherwise similar debug Pod fails. That difference points toward policy selection or caller-specific routing. Inspect destination ingress and source egress policies, including additive policies in both namespaces, before editing the application. A second caller is a controlled comparison, not proof on its own: the two Pods may differ in labels, namespace, node, DNS settings, or policy exposure. Record those differences to choose the next test.

This sequence is more useful than memorizing a single troubleshooting command. It moves from name resolution to selected backends, then port translation, then packet permissions. Each step has a concrete observation that could falsify the current hypothesis. In a timed exercise, that habit prevents repeated manifest edits that only move the symptom. In a real application, it gives another engineer enough evidence to reproduce your reasoning and check any remaining uncertainty.

### Choose exposure by the caller's need

Consider a stateless API called only by other Pods. A ClusterIP Service gives those clients a stable internal name and selected ready backends. Turning it into a LoadBalancer adds an external provisioning dependency without solving an internal discovery problem. If the requirement is a fixed node port for a lab, NodePort adds one while retaining the internal Service behavior. Its default port range is a configuration default, so check the cluster before assuming every explicitly requested value is permitted.

For a clustered workload whose clients need to address particular members, headless discovery exposes Pod addresses rather than one virtual ClusterIP. That shifts connection choice and retry responsibility toward the client. For an external managed dependency that already has a DNS name, ExternalName provides an internal alias to that name. It cannot confer readiness tracking or kube-proxy forwarding on the external system. The Service type is a contract with callers, and the chosen contract should match how those callers resolve and connect.

An HTTP application with multiple public hosts or paths needs an Ingress controller and routing rules if that is the chosen cluster entry mechanism. The backend of each rule is a Service, so the Service still handles Pod selection and port mapping. Ingress can consolidate host and path decisions, but it does not replace the backend Service. Ask whether the controller is installed and publishing before promising public reachability. Then check the rule, Service, endpoints, and application in that order as the symptom allows.

Cost and ownership are part of that choice. A LoadBalancer Service can request external infrastructure, while an Ingress controller is another running component with its own exposure and operations. NodePort relies on reachable nodes and the surrounding network configuration. The lesson does not assign a universal price to any option because provider behavior differs. Choose the smallest required entry point, verify the actual cluster implementation, and avoid adding public exposure merely to work around an internal selector or policy mistake.

### Interpret failures without overclaiming

A DNS failure is not the same as a connection refusal or a timeout. A failed name lookup directs you to the caller's namespace, DNS configuration, Service record, and any egress policy affecting DNS. A connection to a resolved address that refuses immediately may indicate missing endpoints or a listener or port problem, though exact behavior depends on the data plane. A timeout can arise from policy enforcement, routing, or an unreachable external entry point. Use these symptoms as branching clues, then inspect objects and test the next boundary.

An empty endpoint set is unusually decisive when the Service is meant to select Pods. Compare the selector, Pod labels, readiness, and EndpointSlices. For ExternalName, an empty Kubernetes endpoint set is expected because the target is a DNS alias outside that selection path. For headless Services, do not search for a ClusterIP that cannot exist. State the Service type before interpreting the absence of a virtual address. The same output column can mean different things under different declared contracts.

An Ingress that has no published address still might have valid routing syntax. Check `spec.ingressClassName`, available IngressClasses, controller presence, and controller exposure. The next question is whether the controller has reconciled the object, not whether a backend Pod should be restarted. If an address appears later, verify the actual host and path through that address. A successful request to the controller's default backend cannot validate a named host rule that was never matched.

A policy object that is visible in the API still might have no effect. It could select no Pods, affect the wrong direction, use a nonmatching peer selector, or run on a cluster whose network plugin does not enforce it. The converse is also possible: traffic blocked after a policy change may be blocked by source egress, destination ingress, or both. A negative and a positive request from controlled Pods make the policy claim testable. If policy enforcement is unavailable, report it as unknown rather than claiming the manifest proved isolation.

### Rehearse a disciplined answer

Before selecting an answer, restate the observation without adding an explanation. “The Service resolves but has no ready endpoints” is an observation; “the DNS system is broken” is an unsupported explanation. Next, identify the object that owns the failed handoff. DNS owns the lookup, the Service and EndpointSlices own backend discovery, the controller owns Ingress reconciliation, and the enforcing network plugin owns policy decisions. This order keeps each proposed fix attached to evidence you can actually inspect.

Look for the narrowest discriminating test. When two possibilities remain, ask which command or controlled request gives a different result under each. Empty endpoints distinguish selector or readiness trouble from a simple numeric listener mismatch. A populated endpoint port can help separate numeric forwarding from an unresolved named target. A working internal request alongside a missing Ingress address narrows the external problem to the controller entry path. A request that succeeds from one labeled source and fails from another gives you a policy hypothesis worth testing.

Avoid translating “all external requests fail” into “the application is down” without checking internal reachability. The backend can be healthy while the controller has no address or its host rule does not match. Similarly, avoid translating “the Service exists” into “the backend is healthy.” An API object can outlive all eligible Pods. The quiz options deliberately include plausible actions at adjacent layers, because in practice many wasted repairs are technically valid changes to the wrong part of the path.

When a node-specific result appears, compare like with like. The same Service name, namespace, port, and caller conditions should be tested from two nodes before attributing the difference to kube-proxy. Existing kernel forwarding rules can remain useful after kube-proxy stops updating them, so an immediate success is not a clean health verdict. Compare current rule behavior and component state, and do not make control-plane repair your first move in this application-focused exercise.

For an Ingress question, sketch the rule before choosing a command. Identify the expected host, path type, backend Service name, backend Service port, and IngressClass. A request sent to a bare controller IP without a matching Host header may hit a default route, which tells you little about the named application route. If the controller has no published address, host and path tests cannot establish public reachability. The right sequence is to confirm an entry point, then test the intended rule through it.

For a policy question, translate each YAML list into plain language. “These destination Pods are ingress-isolated” describes selection and direction. “Frontend Pods in namespaces labeled production may use TCP port 8080” describes a narrow peer and port allowance. That translation exposes accidental broadening from separate `from` entries. It also shows why an empty top-level selector differs from an empty peer list: one chooses all protected Pods in the namespace, while the other removes a peer restriction from an allow rule.

Check both the positive and negative policy cases. An allowed frontend should connect if its own egress direction and the backend ingress direction both permit the path. An unlabeled debug Pod should fail if the intended boundary is narrow and enforcement works. If both connect, inspect every policy selecting the destination because allowances are additive; also confirm the CNI enforces policy. If neither connects, inspect source egress, destination ingress, port mapping, and application health in that order suggested by the available evidence.

Be precise about success criteria. A `kubectl apply` success proves the API accepted a manifest, not that a controller published an address or a CNI enforced a drop. A Ready Pod proves readiness evaluation passed, not that a Service selects it. A populated EndpointSlice proves a candidate destination exists, not that a caller may reach it. Define the observable outcome for each layer before running the command. That discipline turns a list of checks into a reproducible diagnosis.

There is no single command that replaces reasoning across all three modules. `kubectl describe service` can expose selectors and port mappings, but it cannot prove a browser's Host header matched an Ingress rule. `kubectl describe ingress` can show a backend reference, but it cannot prove a policy allows packets. `kubectl describe networkpolicy` can show declared peers, but it cannot establish that the cluster's CNI enforces them. Use the tools together and state the limit of every result.

The best answer in a timed question is the one that explains the observed difference with the fewest extra assumptions. If a Service has zero endpoints and a mismatched selector, correcting the selector directly addresses the evidence. If endpoints are populated and a numeric target is wrong, changing labels does not. If a named target is unresolved, do not call it the same as forwarding to a closed numeric port. If an Ingress has no address, do not promise external access simply because its backend Service works internally.

After each question, classify any wrong choice by the boundary it confused. A discovery mistake confuses DNS with backend selection. A forwarding mistake confuses Service port with container port or node port. A routing mistake confuses the Ingress object with the controller. A policy mistake confuses isolation with allowance or changes AND logic into OR logic. This review is more useful than memorizing the answer letter, because the next scenario will change names and numbers while preserving the same mechanism.

Treat the practical exercise as another falsifiable investigation. Establish a working baseline before applying isolation, then apply one change and run the same requests again. Preserve command output or notes for the allowed and excluded callers. If the cluster does not have a policy-capable network implementation, the policy portion cannot be claimed as verified; explain that limit and still inspect the manifest's selector logic. The exercise is designed to produce evidence, not merely accepted YAML.

## Did You Know?

- **A headless Service has no ClusterIP:** With `clusterIP: None`, selected Pod addresses can be published for direct discovery instead of resolving the Service name to a virtual ClusterIP.
- **An ExternalName Service is a DNS alias:** It does not create a ClusterIP, select Pods, or use kube-proxy to forward to the external target.
- **NodePort has a default allocation range:** The Service node port range defaults to `30000–32767`, while clients still use the Service `port` for the internal path.
- **NetworkPolicy allowances combine:** Separate policies selecting the same Pod contribute a union of allowed paths, so a later policy cannot cancel an existing allowance.

## Common Mistakes

| Mistake | Why it causes trouble | Better check or correction |
|---|---|---|
| Treating a DNS answer as proof of a healthy backend | A Service record can exist while its selector yields no ready endpoints. | Compare the Service selector, Pod labels, readiness, and EndpointSlices. |
| Changing the selector after endpoints appear | A wrong numeric `targetPort` can still leave endpoints populated. | Compare `port`, `targetPort`, and the application listener before touching labels. |
| Treating a named target like a wrong numeric listener | A missing container port name changes endpoint port resolution. | Inspect container port names and the Service's named `targetPort`. |
| Expecting headless or ExternalName to resolve to a ClusterIP | Neither type supplies the ordinary virtual address. | Choose direct Pod discovery or an external DNS alias intentionally. |
| Calling an Ingress a Service | Ingress requires a controller and routes HTTP or HTTPS to backend Services. | Check the IngressClass, controller, rule, then Service and endpoints. |
| Assuming `ingress: []` and `from: []` deny the same traffic | One is an empty allowance list; the other is an empty peer list within an allow rule. | Read the YAML level and test a disallowed source. |
| Reading a peer `podSelector` as cluster wide | Alone, it selects peer Pods in the policy namespace. | Combine it with a `namespaceSelector` in one peer item for a narrow cross-namespace rule. |
| Testing only one allowed Pod | A successful request cannot show that unwanted callers are blocked. | Test one intended caller and one known excluded caller with the same destination and port. |

## Quiz

Choose one answer for each scenario before opening its explanation. Each set uses the same four-option format so that the reason for rejecting a plausible neighboring fix matters as much as the selected letter. The questions cover discovery, exposure, routing, and policy decisions from Modules 5.1–5.3. Record any uncertain answer, then reproduce its evidence path in the exercise rather than memorizing a phrase from the answer key.

### Question 1: Service discovery after a rollout

A client resolves `catalog.store.svc.cluster.local`, and the Service has a ClusterIP. The `catalog` Service selects `app: catalog-api`, while the only Ready Pods show `app: catalog`. Its EndpointSlices contain no ready backend addresses. Which first change is supported by the evidence?

A) Change the Service selector to match the intended Ready Pods, then recheck endpoints.
B) Replace the ClusterIP Service with a NodePort Service, retaining the current selector.
C) Change the client to call the Service's ClusterIP; the successful DNS lookup already rules out a name-resolution fault.
D) Add an Ingress rule for the current Service and port, then test whether its external route reaches a backend.

<details>
<summary>Answer to Question 1</summary>

**A is correct** because the selector does not match the Ready Pod labels, so the Service has no selected destination. **B is wrong** because NodePort adds an entry point but leaves the empty backend set unchanged. **C is wrong** because DNS already resolves to the Service, and bypassing the name does not create endpoints. **D is wrong** because Ingress would route toward the same empty Service. Recheck EndpointSlices after correcting the selector before diagnosing a later port or policy failure.

</details>

### Question 2: Forwarding with populated endpoints

A Service listens on `port: 80`, selects two Ready Pods, and shows populated endpoints. The application listens on container port `8080`, but the Service declares numeric `targetPort: 9090`. A colleague proposes changing the Pod labels. What should you do first?

A) Change `nodePort` to `8080` and test through that port, even though this client currently uses the ClusterIP.
B) Set `targetPort` to `8080` and verify a request through Service port `80`.
C) Change the selector because populated endpoints indicate a selection failure.
D) Replace the Service with ExternalName to bypass Kubernetes port translation.

<details>
<summary>Answer to Question 2</summary>

**B is correct** because the numeric target points to a port where the stated application is not listening. **A is wrong** because a ClusterIP request does not require a node port. **C is wrong** because populated endpoints show that selection has already produced destinations. **D is wrong** because ExternalName is a DNS alias, not a fix for a selected workload's numeric forwarding port. Verify from a known in-cluster caller after changing the target.

</details>

### Question 3: Choosing a discovery contract

A clustered application needs clients to discover individual member Pods for peer identity. Another client needs a stable internal name for a managed database at `database.example.com`. Which pair of Service contracts fits those distinct requirements?

A) LoadBalancer for members so clients can reach them individually; NodePort for the managed database alias.
B) ClusterIP for both because every Service returns one virtual address and can alias the external database name.
C) Headless for member discovery; ExternalName for the external DNS alias.
D) ExternalName for members; headless for the managed database alias.

<details>
<summary>Answer to Question 3</summary>

**C is correct** because a headless Service can publish selected member addresses and ExternalName aliases an existing external DNS name. **A is wrong** because wider exposure does not supply the requested discovery semantics. **B is wrong** because neither headless nor ExternalName resolves to a ClusterIP. **D is wrong** because ExternalName does not select member Pods and a headless Service is not an external DNS alias. State which component handles retries and member choice after selecting headless discovery.

</details>

### Question 4: Ingress without an address

An Ingress uses `networking.k8s.io/v1` and names a valid backend Service. An internal Pod can reach that Service, but `kubectl get ingress` shows an empty `ADDRESS`, and the external host is unreachable. Which investigation best matches the observed boundary?

A) Rewrite the Service selector because any blank Ingress address means no endpoints.
B) Change the Ingress into a NodePort Service so the same object routes hosts.
C) Assume the route works because the manifest passed API validation.
D) Check `spec.ingressClassName`, the controller, and its published entry point.

<details>
<summary>Answer to Question 4</summary>

**D is correct** because an empty address means the controller has not published that Ingress route, even though internal Service access works. **A is wrong** because the observation does not show a selector defect. **B is wrong** because an Ingress is configuration rather than a Service, and NodePort does not implement host rules. **C is wrong** because API acceptance does not prove controller reconciliation or public reachability. Test the intended Host header after a controller entry point exists.

</details>

### Question 5: Policy list shape

A policy selects backend Pods for ingress and declares `ingress: []`. A second policy selects the same Pods and has one TCP `8080` ingress rule with `from: []`. Assuming enforcement and no restrictive source egress, what does the second rule allow?

A) No sources, because the empty top-level ingress list and the empty peer list both mean nobody matches.
B) All sources on the listed port, because the rule's empty peer list has no source restriction.
C) Only Pods in the policy namespace, because an empty list acts like a pod selector.
D) Only the backend Pods themselves, because top-level selection also selects peers.

<details>
<summary>Answer to Question 5</summary>

**B is correct** because `from: []` in an allow rule matches all sources, while its TCP port still constrains that rule. **A is wrong** because it confuses the empty top-level `ingress` rule list with an empty peer list inside a rule. **C is wrong** because no peer `podSelector` appears in that rule. **D is wrong** because the top-level selector chooses protected destinations, not permitted sources. The second policy's allowance joins the first policy's empty allowance set.

</details>

### Question 6: Cross-namespace selector logic

Only Pods labeled `role: frontend` in namespaces labeled `env: production` should reach a backend. A reviewer sees one `from` item containing both `namespaceSelector` and `podSelector`. What would moving the pod selector into a separate `from` item do?

A) Preserve the same AND condition while making the YAML easier to read, because both selectors still appear in the rule.
B) Deny every source because two selector types cannot appear in one rule.
C) Create OR logic that allows all Pods in selected namespaces or matching local Pods.
D) Turn the rule into egress because namespace selectors are outbound only.

<details>
<summary>Answer to Question 6</summary>

**C is correct** because separate peer items are alternatives, while selectors in one peer item must both match. **A is wrong** because the dash changes the logic. **B is wrong** because combining the selectors in one peer item is valid. **D is wrong** because a namespace selector can identify ingress sources. Check Namespace object labels before concluding that a named namespace matches `env: production`.

</details>

### Question 7: A request fails after egress isolation

A frontend Pod can call `api.store.svc.cluster.local` before an egress policy selects it. After the policy is applied, its name lookup fails. The destination has ready endpoints and an ingress rule allowing frontend traffic. What is the most useful next check?

A) Inspect the frontend egress policy for an allowance to cluster DNS, then test name resolution from that Pod.
B) Add another destination ingress policy with the same frontend allowance, then confirm it selects the backend Pods.
C) Replace the API Service with LoadBalancer to avoid DNS inside the cluster.
D) Change the API Service's numeric `targetPort` before checking DNS.

<details>
<summary>Answer to Question 7</summary>

**A is correct** because the changed source egress policy may now block DNS queries before the client can address the API. **B is wrong** because destination ingress does not repair a failed name lookup. **C is wrong** because public exposure does not solve source DNS egress. **D is wrong** because the client has not resolved an address, so backend port translation has not been tested. Verify actual DNS Pod labels and the chosen policy peer before adding an allowance.

</details>

### Question 8: Evidence across two nodes

The same ClusterIP request succeeds from a Pod on node one and fails from an equivalent Pod on node two. Both callers use the same Service port, and EndpointSlices contain ready addresses. One engineer says kube-proxy must be healthy on node one because its request succeeds. What is the best response?

A) Accept that conclusion because every successful packet must pass through a live kube-proxy process.
B) Delete the Service and recreate it before comparing the nodes.
C) Assume NetworkPolicy cannot matter because endpoints are populated.
D) Compare node-local forwarding and kube-proxy state; installed rules can outlast updates.

<details>
<summary>Answer to Question 8</summary>

**D is correct** because kube-proxy programs kernel forwarding rules, and previously installed rules can continue forwarding temporarily. **A is wrong** because kube-proxy is not a mandatory user-space hop for each packet in the common modes taught here. **B is wrong** because deleting the Service discards evidence without isolating the node difference. **C is wrong** because endpoint presence does not prove caller permission. Compare the same request conditions on both nodes before assigning a cause.

</details>

## Hands-On Exercise

Simulation: use an isolated practice namespace to demonstrate Service selection, a corrected numeric target port, and a narrow ingress policy. This exercise assumes a working Kubernetes cluster, permission to create namespaced resources, and a network plugin that enforces NetworkPolicy for the final isolation check. The example uses the `nginx` image as a simple HTTP listener on port `80`. If the cluster cannot pull the image or lacks policy enforcement, report those environmental limits rather than claiming the missing behavior was observed.

Start by creating a namespace and three Pods with distinct labels. The backend listens on port `80`; the two client Pods provide one permitted caller and one excluded caller. Wait for readiness before interpreting Service or policy output. The initial Service manifest deliberately selects a label that no Pod has, which gives you an observable discovery defect to diagnose before making any policy change. Apply these commands in a disposable practice cluster and keep the namespace name unique to this exercise.

```bash
kubectl create namespace ckad-part5-practice
kubectl run catalog --image=nginx:1.27 --port=80 --labels=app=catalog -n ckad-part5-practice
kubectl run frontend --image=busybox:1.36 -n ckad-part5-practice --labels=role=frontend --command -- sleep 3600
kubectl run outsider --image=busybox:1.36 -n ckad-part5-practice --labels=role=other --command -- sleep 3600
kubectl wait --for=condition=Ready pod/catalog pod/frontend pod/outsider -n ckad-part5-practice --timeout=120s
kubectl apply -n ckad-part5-practice -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: catalog
spec:
  type: ClusterIP
  selector:
    app: wrong-label
  ports:
  - name: http
    protocol: TCP
    port: 80
    targetPort: 80
EOF
kubectl get service catalog -n ckad-part5-practice -o yaml
kubectl get endpointslices -n ckad-part5-practice -l kubernetes.io/service-name=catalog
```

The Service exists, but its selected backend set should be empty because `app: wrong-label` does not match the backend's `app: catalog`. Predict the endpoint result before reading it, then patch only the selector. Inspect the EndpointSlice again and request the Service from the frontend Pod. The expected HTTP response is an nginx welcome page, but label it as expected until you run the command in your own cluster. This step tests selection and an application request separately rather than interpreting the Service object alone.

```bash
kubectl patch service catalog -n ckad-part5-practice --type=merge -p '{"spec":{"selector":{"app":"catalog"}}}'
kubectl get endpointslices -n ckad-part5-practice -l kubernetes.io/service-name=catalog -o yaml
kubectl exec -n ckad-part5-practice frontend -- wget -qO- -T 5 http://catalog:80/
```

Next, set the numeric target to `8080` while leaving the backend listening on `80`. The Service selector still matches, so endpoint discovery should remain populated. The request should fail or return no application page because traffic is directed to the wrong listener. Restore `targetPort: 80` and repeat the same request. The changed outcome separates selected backend discovery from port forwarding. If your environment produces a different failure signal, record the actual output and verify the container listener before explaining it.

```bash
kubectl patch service catalog -n ckad-part5-practice --type=merge -p '{"spec":{"ports":[{"port":80,"targetPort":8080}]}}'
kubectl get endpointslices -n ckad-part5-practice -l kubernetes.io/service-name=catalog -o yaml
kubectl exec -n ckad-part5-practice frontend -- wget -qO- -T 5 http://catalog:80/
kubectl patch service catalog -n ckad-part5-practice --type=merge -p '{"spec":{"ports":[{"port":80,"targetPort":80}]}}'
kubectl exec -n ckad-part5-practice frontend -- wget -qO- -T 5 http://catalog:80/
```

Finally, isolate ingress to the backend and allow only Pods labeled `role: frontend` on TCP port `80`. The two rules below can be submitted as one manifest document containing two policy objects. The first selects the backend and provides no ingress allowances; the second selects the same backend and adds a narrow allowance. Test both callers after application. The expected result, only on a policy-capable network plugin, is success from `frontend` and failure from `outsider`; the latter must be measured rather than assumed from accepted YAML.

```bash
cat <<'EOF' | kubectl apply -n ckad-part5-practice -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: catalog-default-deny
spec:
  podSelector:
    matchLabels:
      app: catalog
  policyTypes:
  - Ingress
  ingress: []
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: catalog-from-frontend
spec:
  podSelector:
    matchLabels:
      app: catalog
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
kubectl get networkpolicy -n ckad-part5-practice
kubectl exec -n ckad-part5-practice frontend -- wget -qO- -T 5 http://catalog:80/
kubectl exec -n ckad-part5-practice outsider -- wget -qO- -T 5 http://catalog:80/
```

**Success Criteria**: You can show the empty and populated endpoint states, explain why the incorrect numeric target leaves selection intact, and demonstrate both the allowed and excluded caller results on a cluster that enforces NetworkPolicy. If the network plugin's enforcement is unavailable, mark the isolation result unverified while retaining the manifest and selector reasoning. The point is to connect each observed output to the one boundary it actually tests, including the limit of an API acceptance message.

- [ ] The Service selector correction produces ready backend addresses in an EndpointSlice, and you can name the exact label comparison that changed.
- [ ] The frontend request works with `targetPort: 80`, and you recorded the result of the deliberate numeric `targetPort: 8080` mismatch.
- [ ] The two policies select the backend Pods, with one empty ingress list and one narrow frontend allowance on TCP port `80`.
- [ ] Positive and negative caller requests were run, with network plugin enforcement confirmed or explicitly recorded as unverified.

When your evidence is recorded, remove only the namespace created for this exercise. Namespace deletion removes its Pods, Service, and policies together, so check the namespace name before running the command. If you reused a namespace with other work, remove the individual objects instead. The exercise does not require a public Ingress controller; its quiz questions test that boundary conceptually because local clusters vary in controller installation and exposure.

```bash
kubectl delete namespace ckad-part5-practice
```

## Sources

- [Kubernetes Service concepts](https://kubernetes.io/docs/concepts/services-networking/service/)
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/)
- [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/)
- [Service API reference](https://kubernetes.io/docs/reference/kubernetes-api/service-resources/service-v1/)
- [Source IP for Services](https://kubernetes.io/docs/tutorials/services/source-ip/)
- [Kubernetes Ingress concepts](https://kubernetes.io/docs/concepts/services-networking/ingress/)
- [Ingress API reference](https://kubernetes.io/docs/reference/kubernetes-api/service-resources/ingress-v1/)
- [IngressClass API reference](https://kubernetes.io/docs/reference/kubernetes-api/service-resources/ingress-class-v1/)
- [Kubernetes Network Policies](https://v1-35.docs.kubernetes.io/docs/concepts/services-networking/network-policies/)
- [NetworkPolicy API reference](https://v1-35.docs.kubernetes.io/docs/reference/kubernetes-api/policy-resources/network-policy-v1/)
- [Declare Network Policy task](https://v1-35.docs.kubernetes.io/docs/tasks/administer-cluster/declare-network-policy/)

## Next Module

Part 5 completes the networking sequence. Return to the [CKAD curriculum](../../) to revisit earlier application tasks and repeat any question whose evidence boundary was still uncertain.
