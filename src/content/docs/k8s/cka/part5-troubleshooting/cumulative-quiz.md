---
citations_verified: true
title: "Part 5: Troubleshooting - Cumulative Quiz"
sidebar:
  order: 9
---

> **Complexity**: `[COMPLEX]`
>
> **Time to Complete**: 75-90 minutes
>
> **Prerequisites**: Part 5 modules on troubleshooting methodology, application failures, control plane failures, worker node failures, networking, services, logging, and monitoring.
>
> **Exam Weight**: [Troubleshooting is 30% of the CKA exam domain coverage.](https://www.cncf.io/training/certification/cka/)
>
> **Cluster Target**: Kubernetes 1.35+

---

## Learning Outcomes

By the end of this cumulative troubleshooting module, you will be able to carry the Part 5 diagnostic habits across workloads, nodes, and networks:

1. **Debug** failing Kubernetes workloads by moving from symptoms to evidence, using Events, status fields, logs, rollout state, and resource data instead of guessing.
2. **Analyze** control plane and worker node failures by separating API reachability, static pod health, kubelet behavior, container runtime state, certificates, and node pressure conditions.
3. **Evaluate** service and network incidents by tracing traffic from client to Service, EndpointSlice, Pod readiness, container port, kube-proxy, DNS, and CNI behavior.
4. **Design** a time-boxed troubleshooting plan for CKA-style scenarios that prioritizes reversible fixes, preserves evidence, and avoids unnecessary disruption.
5. **Compare** similar failure signatures, such as `Pending`, `ContainerCreating`, `CrashLoopBackOff`, `ImagePullBackOff`, empty endpoints, and `NotReady`, to choose the next command with confidence.

---

## Why This Module Matters

Hypothetical scenario: At 02:13, an on-call engineer is paged because checkout requests have started failing across two regions. The application team says their Deployment "looks fine" because the desired replica count still says six, the platform team says the cluster "looks fine" because most nodes are `Ready`, and the incident commander wants to know whether to roll back, drain nodes, or fail traffic away from the cluster. In that moment, a troubleshooter who only remembers commands becomes slow. A troubleshooter who understands failure paths can turn vague symptoms into a narrow, testable hypothesis.

The CKA exam compresses that pressure into short scenarios. You do not get time to read every object in the namespace, and you do not get credit for running commands that merely look sophisticated. You get credit for identifying the failing layer, applying the smallest correct fix, and proving the cluster now behaves as expected. That skill is not command memorization. It is diagnostic reasoning under time pressure.

This cumulative module is written as a capstone for Part 5. It reviews the major troubleshooting domains, but it does so by teaching how the domains connect. A `CrashLoopBackOff` can be an application bug, a bad ConfigMap, an OOM kill, or a probe that kills a healthy process too aggressively. A Service outage can be DNS, labels, readiness, ports, kube-proxy, node firewalling, or CNI. A control plane outage can look like "kubectl is broken" even when the real failure is a static pod manifest typo or an expired certificate.

A senior Kubernetes troubleshooter does not start with a favorite command. They start with a mental model of the request path, choose the quickest observation that can eliminate whole classes of causes, and make changes only after they can explain why the change should work. That is the standard this module trains toward.

---

## Core Content

### 1. Troubleshooting Is Evidence-Driven, Not Command-Driven

A Kubernetes incident is easier to debug when you treat every command as a question you are asking the system. `kubectl get pods` asks whether the desired workload exists and what high-level state Kubernetes reports. `kubectl describe pod` asks what the control plane and kubelet have recently tried to do. `kubectl logs` asks what the process inside the container said before or during failure. These commands overlap, but they do not answer the same question.

The basic workflow is simple enough to remember under pressure: define the symptom, locate the failing layer, collect the most relevant evidence, apply the smallest safe fix, and verify from the user's perspective. The order matters because Kubernetes exposes many tempting details. If you inspect logs before confirming the Pod was ever scheduled, you might waste time on an application that has not started. If you patch a Service before checking endpoints, you might change a working abstraction while the real issue is Pod readiness.

```ascii
+----------------------+     +----------------------+     +----------------------+
|  1. Define Symptom   | --> |  2. Locate Layer     | --> |  3. Collect Evidence |
|  Who is affected?    |     |  App, node, network, |     |  Events, logs,       |
|  What changed?       |     |  control plane, DNS  |     |  status, metrics     |
+----------------------+     +----------------------+     +----------------------+
              |                                                     |
              v                                                     v
+----------------------+     +----------------------+     +----------------------+
|  6. Document Result  | <-- |  5. Verify Behavior  | <-- |  4. Apply Safe Fix   |
|  What proved fixed?  |     |  User-visible check  |     |  Small, reversible,  |
|  What evidence stays?|     |  plus object status  |     |  scoped to cause     |
+----------------------+     +----------------------+     +----------------------+
```

The first useful question is not "what command do I run?" but "what layer could produce this symptom?" A user saying "the app is down" could mean the Pod never started, the Service selector is wrong, DNS cannot resolve the name, the application is returning HTTP 500, or traffic cannot cross nodes. Each layer has a faster test than inspecting every resource in the namespace. You narrow the field by checking the most central object first, then following the dependency chain outward.

For workload incidents, start with the controller and Pod because they connect desired state to actual execution. A Deployment may show three desired replicas, but only the Pods reveal whether scheduling, image pulls, volume mounts, probes, or process exits are failing. For service incidents, start with Service and endpoint state because a Service with no endpoints cannot route traffic no matter how healthy DNS looks. For node incidents, start with node conditions and kubelet because the kubelet is the bridge between the API server and local container execution.

> **Active Learning Prompt: Predict Before You Inspect**
>
> Your teammate says a Deployment has `READY 0/3`, and `kubectl get pods` shows all three Pods are `Pending`. Before running another command, predict which evidence source is most likely to explain the cause: container logs, Pod Events, Service endpoints, or CoreDNS logs. Then explain why the other three are weaker first checks for a `Pending` Pod.

The best first pair of commands for many workload failures is still a wide Pod listing followed by a describe of one representative Pod, because the listing shows where each Pod landed and the describe output shows what Kubernetes last tried to do with it:

```bash
kubectl get pods -o wide
kubectl describe pod <pod-name>
```

`-o wide` gives you node placement, Pod IPs, and readiness at a glance. `describe` gives you Events, which are often the fastest path to causes such as failed scheduling, image pull errors, missing ConfigMaps, missing Secrets, volume mount failures, failed probes, and node pressure. Logs are powerful, but they are application evidence; Events are Kubernetes orchestration evidence. A Pod that never started will usually have no useful application logs.

A practical CKA troubleshooting loop moves from controller state to one Pod's Events, then to previous logs, recent namespace Events, and finally the full object YAML:

```bash
kubectl get deploy,rs,pods -o wide
kubectl describe pod <pod-name>
kubectl logs <pod-name> --previous
kubectl get events --sort-by=.lastTimestamp
kubectl get pod <pod-name> -o yaml
```

Do not run all of those every time. Use them as a sequence only when the earlier command does not answer the question. If Events say `FailedScheduling` because the Pod requests more CPU than any node can provide, logs will not help. If Events show the container starts and then exits, logs become the better source. If logs show the app cannot read a file mounted from a ConfigMap, the Pod spec and mounted volume configuration become relevant.

A senior habit is to preserve evidence before changing state. In the exam, "preserve evidence" may simply mean reading Events and logs before deleting a Pod. In production, it can mean copying failure output into an incident note, checking previous container logs, and avoiding a rollback until you know whether the new version is bad or the environment changed. Kubernetes is highly reconciled, which means evidence can disappear quickly as controllers recreate objects and kubelet rotates logs.

---

### 2. Workload Failures: From Pod State To Root Cause

Pod state is not a root cause. `Pending`, `ContainerCreating`, `ImagePullBackOff`, and `CrashLoopBackOff` are labels on where the lifecycle is stuck. They are useful because each state points to a different part of the lifecycle. A good troubleshooter uses the state to choose the next evidence source, then validates the cause with a specific field or message.

```ascii
+----------------+     +-------------------+     +----------------------+     +------------------+
| Pod Accepted   | --> | Scheduled To Node | --> | Image And Volumes    | --> | Container Runs   |
| API object     |     | scheduler         |     | kubelet + runtime    |     | process + probes |
+----------------+     +-------------------+     +----------------------+     +------------------+
        |                       |                          |                            |
        v                       v                          v                            v
  YAML invalid?          Pending forever?          ContainerCreating?            CrashLoopBackOff?
  admission denied?      taints/resources?         ConfigMap/Secret/CNI?         logs/probes/OOM?
```

`Pending` usually means scheduling has not completed. The fastest evidence is the Events section of `kubectl describe pod`. Common causes include insufficient CPU or memory, untolerated taints, node selectors that match no nodes, required node affinity that is too strict, PVCs that cannot bind, or a scheduler that is unavailable. Logs are not useful because the container has not run.

`ContainerCreating` means the Pod was scheduled, but kubelet has not completed local setup. This often points to image preparation, volume mounting, missing ConfigMaps or Secrets, CNI setup, or container runtime problems. Again, Events usually beat logs. If Events say `MountVolume.SetUp failed` for a missing Secret, the fix is not to restart the Deployment. The fix is to create or correct the referenced Secret or update the Pod template to use the right name.

`ImagePullBackOff` means kubelet cannot obtain the image, and the backoff is merely Kubernetes slowing repeated attempts. The cause might be a wrong repository, wrong tag, missing registry credentials, unauthorized access to a private registry, DNS failure to the registry, registry rate limiting, or a network egress block. The image string and Event messages are the key evidence, not application logs.

[`CrashLoopBackOff` means the container process starts, exits, and is restarted according to Pod restart policy.](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) The application did run, so `kubectl logs --previous` is often the most useful command. Causes include invalid command arguments, missing runtime configuration, app-level dependency failures, failed startup probes, failed liveness probes, permission errors, and memory limits causing `OOMKilled`.

Comparing similar failure signatures side by side is what turns these labels into decisions. `Pending` and `ContainerCreating` both mean the application has not produced useful logs yet, but `Pending` points at scheduling while `ContainerCreating` points at kubelet setup on a node that was already chosen, so the node placement column in `kubectl get pods -o wide` is a quick tiebreaker. `ImagePullBackOff` and `CrashLoopBackOff` both describe a backoff, but only the second one means a process actually ran, which is why previous logs help with a crash and not with a pull failure. The same comparison works beyond Pods: an empty EndpointSlice and a `NotReady` node can both make a Service look down, yet the first sends you to selectors and readiness while the second sends you to kubelet, the runtime, and host resources.

#### Worked Example: Debugging A CrashLoopBackOff Without Guessing

Suppose a team deploys a simple API, and the Deployment never becomes available. The first view shows that Kubernetes created the desired Pods, but they are restarting.

```bash
kubectl get deploy,pods -l app=orders-api
```

In this example output, the Deployment has created all three Pods, yet none of them is ready and each one has already restarted several times:

```text
NAME                         READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/orders-api   0/3     3            0           6m

NAME                              READY   STATUS             RESTARTS   AGE
pod/orders-api-6b6f8f7b8d-2bq9m   0/1     CrashLoopBackOff   5          6m
pod/orders-api-6b6f8f7b8d-hw6kn   0/1     CrashLoopBackOff   5          6m
pod/orders-api-6b6f8f7b8d-tm8xs   0/1     CrashLoopBackOff   5          6m
```

At this point, the status tells you the process has started and failed repeatedly. That makes previous logs and termination state more useful than scheduling checks. You inspect one Pod rather than all three because all three share the same Deployment template.

```bash
kubectl describe pod orders-api-6b6f8f7b8d-2bq9m
```

The describe output for that Pod includes an example termination record like the one below, which shows why the last container instance stopped and how many times it has been restarted:

```text
Last State:     Terminated
  Reason:       OOMKilled
  Exit Code:    137
Restart Count:  5
```

Exit code 137 is commonly associated with a `SIGKILL`, and Kubernetes reporting `OOMKilled` confirms memory pressure at the container limit. The next question is whether the configured limit is unrealistically low for this app. You inspect the Pod template through the Deployment, because editing an individual Pod would be temporary and the controller would recreate it.

```bash
kubectl get deployment orders-api -o jsonpath='{.spec.template.spec.containers[0].resources}{"\n"}'
```

In this example output, the container both requests and is limited to only 64Mi of memory, which is the value to weigh against what the application actually needs to run:

```json
{"limits":{"memory":"64Mi"},"requests":{"cpu":"100m","memory":"64Mi"}}
```

A safe exam fix is to patch the Deployment template to a more realistic memory value, then watch the rollout. In production, you would compare against metrics and application history, but in a CKA scenario the evidence often makes the intended correction clear.

```bash
kubectl set resources deployment/orders-api \
  --containers=orders-api \
  --requests=cpu=100m,memory=128Mi \
  --limits=memory=256Mi
```

Now verify that Kubernetes creates new Pods from the updated template and that they remain running, instead of trusting the successful exit of the `set resources` command.

```bash
kubectl rollout status deployment/orders-api
kubectl get pods -l app=orders-api
```

The important teaching point is not that every `CrashLoopBackOff` is memory-related. It is that the status selected the evidence source, the evidence identified the cause, the fix targeted the controller template, and verification checked the rollout rather than merely checking that the command returned without error.

> **Active Learning Prompt: Choose The Next Command**
>
> You see `CrashLoopBackOff`, but `kubectl describe pod` shows `Last State: Terminated, Reason: Error, Exit Code: 1` rather than `OOMKilled`. Which command should you run next, and what kind of evidence would make you patch the Deployment versus roll back the image?

A different `CrashLoopBackOff` may point to application configuration rather than memory. When the termination reason is a plain error, the next command would be previous logs, because the last container instance is the one that actually hit the failure and exited:

```bash
kubectl logs <pod-name> --previous
```

If the log says `missing environment variable DATABASE_URL`, inspect the Deployment environment and the ConfigMaps or Secrets it references, since the fix belongs in whichever object is supposed to supply that value:

```bash
kubectl get deployment <deployment-name> -o yaml
kubectl get configmap
kubectl get secret
```

If the missing value is supposed to come from a ConfigMap, correct the ConfigMap name or key in the Deployment template, or create the missing ConfigMap when the scenario clearly expects it. Avoid changing the container image, resource limits, and probes at the same time. Multiple simultaneous fixes make it harder to prove what mattered, and in an exam they increase the chance of breaking a previously correct field.

#### Decision Matrix For Common Workload States

| Symptom | Most Useful First Evidence | Likely Layer | Good Next Action |
|---|---|---|---|
| Pod is `Pending` | `kubectl describe pod` Events | Scheduler, PVC binding, taints, resources | Fix requests, tolerations, selectors, affinity, or storage binding |
| Pod is `ContainerCreating` | `kubectl describe pod` Events | Kubelet setup, volume mount, CNI, runtime | Fix missing ConfigMap or Secret, volume, CNI, or runtime issue |
| Pod is `ImagePullBackOff` | `kubectl describe pod` Events and image field | Registry, image name, credentials, network | Correct image, tag, `imagePullSecrets`, or registry access |
| Pod is `CrashLoopBackOff` | `kubectl logs --previous` and last termination state | Process, configuration, probes, memory | Fix config, command, resources, probes, or roll back bad image |
| Deployment stuck rolling out | `kubectl rollout status` and new ReplicaSet Pods | New template revision | Fix new Pod cause or `kubectl rollout undo` when rollback is safest |
| Service has no endpoints | `kubectl get endpointslice` and Pod readiness | Labels or readiness | Fix selector, labels, readiness probe, or container health |

This table is useful because it prevents a common troubleshooting mistake: treating every workload failure as if it requires deleting Pods. Deleting a Pod may temporarily retry the same broken configuration, but it rarely fixes a bad template. For controller-managed workloads, fix the controller template unless the evidence proves the Pod is stuck due to transient node state.

Rollbacks are appropriate when the newest revision introduced the failure and the previous revision was known good. They are not a substitute for diagnosis when the issue is missing infrastructure or a cluster-level dependency. If a new image crashes because it expects a new ConfigMap key that was not created, rollback may restore service quickly, but the lasting fix still includes aligning configuration with the application version.

Use this rollback sequence when availability matters more than preserving the new revision, and read the history first so you know which revisions exist before the undo moves the Deployment back:

```bash
kubectl rollout history deployment/<deployment-name>
kubectl rollout undo deployment/<deployment-name>
kubectl rollout status deployment/<deployment-name>
```

Use this correction sequence when the intended state is clear and the current template is wrong, because editing the Deployment changes the source of truth and the rollout status then shows whether the new Pods became available:

```bash
kubectl edit deployment/<deployment-name>
kubectl rollout status deployment/<deployment-name>
kubectl get pods -l app=<label-value>
```

In CKA scenarios, prefer direct, narrow changes that can be verified. If a Pod references `configmap app-config` and Events say that ConfigMap is missing, creating that ConfigMap or correcting the reference is a narrow fix. Recreating the Deployment from scratch is broad, risky, and usually unnecessary.

---

### 3. Control Plane And Node Failures: Separate API, Kubelet, Runtime, And Host

Cluster troubleshooting gets harder when `kubectl` itself becomes unreliable. If the API server is unreachable, normal Kubernetes commands cannot tell you whether the API server, etcd, certificates, networking, or kubelet is responsible. At that point, you move from the Kubernetes API to the host and container runtime on the control plane node.

In kubeadm-style clusters, [key control plane components commonly run as static Pods](https://kubernetes.io/docs/concepts/workloads/pods/). [Static Pod manifests live on disk, and the kubelet watches those files.](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/) When a manifest changes, kubelet recreates the corresponding static Pod. That means a bad flag, wrong certificate path, invalid YAML field, or moved manifest can break a control plane component even when the rest of the node is healthy.

```ascii
+--------------------------- Control Plane Node ---------------------------+
|                                                                         |
|  +-------------------+        watches         +-----------------------+  |
|  |      kubelet      | ---------------------> | /etc/kubernetes/      |  |
|  | systemd service   |                        | manifests/*.yaml      |  |
|  +-------------------+                        +-----------------------+  |
|          |                                                        |      |
|          | creates static Pods                                    |      |
|          v                                                        v      |
|  +-------------------+   +-------------------+   +-------------------+  |
|  | kube-apiserver    |   | scheduler         |   | controller-manager |  |
|  | listens on 6443   |   | assigns Pods      |   | reconciles objects |  |
|  +-------------------+   +-------------------+   +-------------------+  |
|          |                                                               |
|          v                                                               |
|  +-------------------+                                                   |
|  | etcd              |                                                   |
|  | cluster state     |                                                   |
|  +-------------------+                                                   |
+-------------------------------------------------------------------------+
```

When `kubectl` times out, SSH to the control plane node and ask whether the kubelet is running. If kubelet is down, it cannot manage static Pods. If kubelet is running, inspect the container runtime and static pod containers. If the API server container exists but restarts, inspect kubelet logs and container logs. If the API server runs but returns certificate errors, inspect certificate expiration and file references.

A useful host-level sequence follows the same dependency order, moving from the kubelet service and its journal to the runtime's view of the API server container and then to the manifests:

```bash
sudo systemctl status kubelet
sudo journalctl -u kubelet -n 80 --no-pager
sudo crictl ps -a | grep kube-apiserver
sudo crictl logs <api-server-container-id>
sudo ls -l /etc/kubernetes/manifests/
```

Those commands are not interchangeable with `kubectl`. [`crictl` talks to the container runtime through the Container Runtime Interface, so it remains useful when the API server is down.](https://kubernetes.io/docs/tasks/debug/debug-cluster/crictl/) `journalctl` reads systemd logs, so it can show kubelet errors before static Pods exist. The manifest directory shows the desired static pod definitions kubelet is trying to run.

For etcd health in a kubeadm cluster, use `etcdctl` with the correct certificates. The exact certificate file names can vary by setup, but kubeadm clusters commonly use the etcd PKI directory shown below.

```bash
sudo ETCDCTL_API=3 etcdctl endpoint health \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key
```

The reason to check etcd carefully is that the API server depends on it for cluster state. If etcd is unavailable, the API server may start but fail readiness checks or be unable to serve normal requests. If etcd is healthy and the API server is not, focus on API server flags, certificates, admission configuration, and network binding. If both are unhealthy, restore etcd first because a healthy API server cannot function without its backing store.

Certificate failures often look like authentication or connection errors rather than obvious expiration messages. `kubeadm certs check-expiration` is the fast check on kubeadm-managed clusters:

```bash
sudo kubeadm certs check-expiration
```

If the expiration check confirms that certificates are expired in a practice cluster, the renewal commands are shown below, and the proof afterward is that the API answers requests again:

```bash
sudo kubeadm certs renew all
sudo systemctl restart kubelet
```

In production, certificate renewal has operational risk and should follow the organization's rotation procedure. In a CKA scenario, the expected answer may be more direct because the cluster is disposable and the exam goal is to restore function.

Worker node failures have a similar layered model. [A node becomes `NotReady` when the control plane stops receiving healthy kubelet status.](https://kubernetes.io/docs/reference/node/node-status/) The cause may be kubelet down, container runtime down, network path to the API server broken, disk pressure, memory pressure, PID pressure, certificate problems, or CNI problems. `NotReady` tells you the control plane sees a node problem; it does not tell you which host component failed.

```ascii
+------------------------------- Worker Node ------------------------------+
|                                                                          |
|  +-------------------+       CRI calls       +------------------------+  |
|  |      kubelet      | --------------------> | containerd or runtime  |  |
|  | reports Node      |                       | starts containers      |  |
|  +-------------------+                       +------------------------+  |
|          |                                                               |
|          | CNI calls                                                     |
|          v                                                               |
|  +-------------------+        traffic        +------------------------+  |
|  | CNI plugin        | --------------------> | Pod network namespace  |  |
|  | routes Pods       |                       | app container ports    |  |
|  +-------------------+                       +------------------------+  |
|          |                                                               |
|          v                                                               |
|  +-------------------+                                                   |
|  | host resources    |  disk, memory, PIDs, kernel, certificates          |
|  +-------------------+                                                   |
+--------------------------------------------------------------------------+
```

Start from the API view if the API is reachable, because node conditions and recent node Events show what the control plane believes about the node before you log in to it:

```bash
kubectl get nodes -o wide
kubectl describe node <node-name>
```

Then move to the node when node-local evidence is needed, checking kubelet, containerd, running containers, disk space, and memory in roughly the order the worker node diagram shows:

```bash
ssh <node-name>
sudo systemctl status kubelet
sudo journalctl -u kubelet -n 80 --no-pager
sudo systemctl status containerd
sudo crictl ps
df -h
free -m
```

Node pressure conditions affect scheduling and eviction. `MemoryPressure=True` can block new Pods from scheduling to the node and can trigger eviction of lower-quality-of-service Pods. `DiskPressure=True` can prevent kubelet from creating more containers or writing logs. A node can be reachable and still unsuitable for new workloads because resource pressure makes it unsafe.

A safe maintenance response is to cordon before drain when you need to stop new workloads arriving and evict existing workloads deliberately:

```bash
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
```

After maintenance, return the node to scheduling, because a cordoned node stays unschedulable until someone explicitly reverses the cordon, even after it is healthy again:

```bash
kubectl uncordon <node-name>
```

Do not drain a node as a first response to every `NotReady` condition. Draining requires the API server and eviction path to work, and it may disrupt workloads with strict PodDisruptionBudgets. First determine whether the node can be recovered by restarting kubelet or containerd, freeing disk, correcting network access, or fixing certificates. Drain is a maintenance action, not a diagnostic shortcut.

> **Active Learning Prompt: Diagnose The Layer**
>
> A node is `NotReady`, and new Pods cannot be scheduled there. `ssh` works, `containerd` is active, but `journalctl -u kubelet` repeatedly shows failures connecting to `https://control-plane:6443`. Decide whether you would inspect CNI pods, container logs, API server reachability, or Service selectors next. Explain your choice in terms of the dependency path.

---

### 4. Service, DNS, And Network Troubleshooting: Follow The Packet

Service incidents are confusing because Kubernetes hides several moving parts behind one stable name. A client may call `http://checkout.default.svc.cluster.local`, but the request path includes DNS resolution, Service virtual IP handling, kube-proxy rules or equivalent dataplane behavior, EndpointSlice membership, Pod readiness, container ports, and network policy. A failure at any layer can look like "the Service is down."

The packet path is the best organizing model. Start with name resolution only if the client cannot resolve the Service name. Start with endpoints if the name resolves but connections fail. Start with Pod readiness and labels if endpoints are empty. Start with ports if endpoints exist but traffic reaches the wrong port. Start with kube-proxy or dataplane health if Services fail on one node or all Services fail from a particular node.

```ascii
+-------------+       DNS        +-------------+       VIP        +----------------+
| client Pod  | ---------------> | CoreDNS     | ---------------> | Service        |
| curl name   |                  | kube-dns    |                  | ClusterIP:port |
+-------------+                  +-------------+                  +----------------+
       |                                                                    |
       | connection after name resolves                                     |
       v                                                                    v
+-------------+       dataplane    +----------------+       ready Pods +-------------+
| node rules  | -----------------> | EndpointSlice  | ---------------> | Pod IP      |
| kube-proxy  |                    | addresses      |                  | targetPort  |
+-------------+                    +----------------+                  +-------------+
```

A compact service-debug sequence checks the Service definition, the EndpointSlices that back it, the labels on candidate Pods, and the Service description with its selector and endpoints:

```bash
kubectl get svc <service-name> -o wide
kubectl get endpointslice -l kubernetes.io/service-name=<service-name>
kubectl get pods --show-labels
kubectl describe svc <service-name>
```

If the EndpointSlice has no addresses, check the selector and Pod labels. A Service selector must match Pod labels exactly. It is common for a Deployment to use `app: checkout-api` while the Service selects `app: checkout`. Kubernetes will create the Service happily, but the Service will have no endpoints because no ready Pods match.

```bash
kubectl get svc checkout -o jsonpath='{.spec.selector}{"\n"}'
kubectl get pods -l app=checkout --show-labels
kubectl get pods -l app=checkout-api --show-labels
```

Readiness also matters. [A Pod can match the selector but be excluded from endpoints when it is not ready.](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) That behavior protects clients from traffic to unhealthy Pods, but it can surprise learners who only look at labels. If endpoints are missing and labels look correct, inspect Pod readiness, probe Events, and container logs.

```bash
kubectl get pods -l app=checkout -o wide
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

Port mismatches are another common service failure. [In a Service, `port` is the port clients use on the Service, while `targetPort` is the port on the Pod.](https://kubernetes.io/docs/concepts/services-networking/service/index.html) If the Service has `port: 80` and `targetPort: 8080`, but the container listens on 80, traffic will be forwarded to a port where nothing is listening. The Service object can look normal, endpoints can exist, and DNS can resolve, yet the application remains unreachable.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: checkout
spec:
  selector:
    app: checkout
  ports:
    - port: 80
      targetPort: 8080
```

The fix is to align the Service `targetPort` with the container's actual listening port, or change the container to listen on the expected target port. In exam scenarios, inspect the Pod spec and application documentation in the question. Do not assume that `port` and `targetPort` must always match; they can differ intentionally when the Service exposes a conventional port and the application listens elsewhere.

DNS troubleshooting begins inside a Pod because cluster DNS behavior depends on the Pod's resolver configuration and network path to CoreDNS. Use a temporary Pod or an existing app Pod when allowed:

```bash
kubectl run dns-test --image=busybox:1.36 --restart=Never -- sleep 3600
kubectl exec dns-test -- nslookup kubernetes.default.svc.cluster.local
kubectl exec dns-test -- cat /etc/resolv.conf
```

If every Service name fails, inspect CoreDNS and the kube-dns Service, because a cluster-wide resolution failure points at the shared DNS path rather than at any one application:

```bash
kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide
kubectl -n kube-system logs -l k8s-app=kube-dns
kubectl -n kube-system get svc kube-dns
kubectl -n kube-system get endpointslice -l kubernetes.io/service-name=kube-dns
```

If only one Service name fails, DNS is less likely to be the root cause. The Service might not exist, the namespace might be wrong, or the client might be using the wrong short name. [A Pod in namespace `frontend` resolving `checkout` will search `checkout.frontend.svc.cluster.local` before other names. If the Service lives in namespace `payments`, the client should use `checkout.payments` or the fully qualified name.](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)

NetworkPolicy failures require a different habit: check whether a policy selects the affected Pods and whether it allows the direction you are testing. [A policy that selects Pods and has ingress rules makes ingress restricted for those Pods. Egress remains unrestricted unless egress isolation is also created by policy type and rules. If both ingress and egress are restricted, you must allow DNS as well as application traffic when Pods need name resolution.](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

```bash
kubectl get networkpolicy
kubectl describe networkpolicy <policy-name>
kubectl get pod <pod-name> --show-labels
```

Cross-node communication failures often point below Service objects. If Pods on the same node communicate but Pods on different nodes do not, suspect CNI routing, overlay encapsulation, MTU, node firewalling, or blocked node-to-node traffic. Check CNI Pods across nodes, then inspect node-level CNI configuration only when needed.

```bash
kubectl -n kube-system get pods -o wide
kubectl -n kube-system logs <cni-pod-name>
```

The key is to follow the packet rather than chase components randomly. If the name does not resolve, work on DNS. If the name resolves and the Service has no endpoints, work on labels and readiness. If endpoints exist but connections fail, work on ports, NetworkPolicy, dataplane, and CNI. Each step eliminates several possible causes.

---

### 5. Logging, Events, Metrics, And Time: Use The Right Signal For The Time Window

Kubernetes gives you several observability signals, but each signal has a different time horizon and failure layer. Events are excellent for recent orchestration decisions. Container logs are excellent for process-level failures. Previous logs are essential for restarted containers. Metrics are useful for resource trends, but `kubectl top` depends on Metrics Server and does not replace status and Events during first response.

[Events are not a durable incident archive. They can expire, be compacted, or be absent by the time you investigate.](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/) That is why recent CKA-style problems often expect you to look at Events immediately, while real production systems need centralized logging, metrics, and alerting. In the exam, if Events are still present, they are often the fastest clue.

```bash
kubectl get events --sort-by=.lastTimestamp
kubectl describe pod <pod-name>
```

For a crashing container, current logs may show only the newest instance, which might not yet have reached the failure point. [Previous logs show the prior terminated container instance:](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)

```bash
kubectl logs <pod-name> --previous
```

For multi-container Pods, always specify the container when needed, because without `-c` you may read a different container from the one that actually restarted:

```bash
kubectl logs <pod-name> -c <container-name> --previous
```

[Metrics Server powers `kubectl top`, but metrics absence does not automatically mean workloads are healthy or unhealthy.](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/) It means the metrics pipeline is not available to that command. Check whether Metrics Server exists and is ready before assuming a resource view is meaningful:

```bash
kubectl top pods
kubectl -n kube-system get pods | grep metrics-server
```

When Metrics Server is unavailable in a cluster where you are allowed to install it, the standard manifest is often used. In a locked-down exam or production environment, do not install components unless the task explicitly allows it. Verify the expected cluster policy first.

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Node-local logs matter when Kubernetes API evidence is incomplete. Container logs are commonly exposed through paths under `/var/log/containers/`, while kubelet logs are available through systemd on many Linux nodes. Use these when `kubectl logs` is insufficient or when the API server is unavailable.

```bash
sudo journalctl -u kubelet -n 100 --no-pager
sudo ls -l /var/log/containers/
```

A disciplined troubleshooter also understands time. A failure that started immediately after a rollout suggests template, image, configuration, or probe changes. A failure that started after a node reboot suggests kubelet, runtime, CNI, certificates, disk, or node network state. A failure that affects only one namespace suggests policy, quota, configuration, or namespace-specific resources. A failure that affects every namespace suggests shared services, DNS, CNI, kube-proxy, nodes, or the control plane.

That timeline thinking turns raw commands into analysis. If DNS fails for every Pod in every namespace, do not begin by editing one application's Deployment. If only one Service has empty endpoints, do not restart CoreDNS. If only new Pods are stuck `Pending` but existing Pods keep running, focus on scheduling, quota, node resources, taints, or PVC binding rather than application logs.

---

### 6. Exam-Grade Strategy: Fast, Safe, And Verifiable

CKA troubleshooting scenarios reward targeted action. You need to solve the issue, but you also need to avoid creating a second issue. The safest approach is to make one change at a time, choose reversible changes when possible, and verify through the affected object path. A successful patch that is not verified is incomplete work.

A useful time budget is to spend the first minute identifying the layer, the next few minutes collecting evidence, and the remaining time applying and verifying the fix. If you are still collecting unrelated evidence after several minutes, stop and restate the symptom. Ask what single observation would eliminate the largest number of possible causes.

For workload fixes, edit the controller rather than the Pod when a controller owns the Pod. For service fixes, edit the Service or labels according to the evidence, then verify endpoints and traffic. For node fixes, verify kubelet, runtime, disk, memory, and API reachability before draining. For control plane fixes, use host-level tools because the API may not be available.

Use rollbacks when they match the evidence. A Deployment that broke immediately after a rollout and whose new Pods crash with application errors is a good rollback candidate. A Deployment whose Pods are `Pending` because the cluster has no schedulable nodes is not fixed by rollback. A Service with an incorrect selector is not fixed by restarting Pods.

A good final verification follows the dependency path in reverse. If you fixed a Deployment, check rollout status and Pods. If you fixed a Service selector, check EndpointSlices and run a request from a client Pod. If you restarted kubelet, check node readiness and that Pods can be scheduled. If you renewed certificates, check API health and component status through supported commands.

```bash
kubectl rollout status deployment/<deployment-name>
kubectl get pods -o wide
kubectl get endpointslice -l kubernetes.io/service-name=<service-name>
kubectl run curl-test --image=curlimages/curl:8.11.1 --restart=Never --rm -it -- \
  curl -sS http://<service-name>.<namespace>.svc.cluster.local
```

The exam does not require perfect production incident management, but it does reward production-shaped thinking. Avoid broad restarts, avoid deleting resources unless the scenario clearly supports it, and avoid editing generated Pods when their controller will overwrite the change. Think in layers, prove the cause, fix the source of truth, and verify from the same path the user depends on.

---

## Did You Know?

1. [**Events are recent orchestration evidence, not a long-term log store.**](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/) They are excellent for fresh scheduling, image pull, mount, and probe failures, but production clusters need durable logging and alerting for historical incident analysis.

2. [**`CrashLoopBackOff` names the restart behavior, not the root cause.**](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) The actual cause usually appears in previous logs, termination state, probe Events, configuration references, or resource limit evidence.

3. [**A Service can be perfectly valid and still route to nothing.**](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) Kubernetes accepts a selector that matches no ready Pods, so endpoint inspection is mandatory during service debugging.

4. [**`crictl` is valuable because it bypasses the Kubernetes API.**](https://kubernetes.io/docs/tasks/debug/debug-cluster/crictl/) When the API server is down, container runtime evidence on the node may be the only practical way to inspect static pod containers.

---

## Common Mistakes

| Mistake | Why It Hurts | Better Practice |
|---|---|---|
| Checking application logs before Events for a `Pending` Pod | A `Pending` Pod has not run, so logs usually cannot explain the scheduling failure | Use `kubectl describe pod` and read Events before moving to logs |
| Deleting Pods owned by a broken Deployment template | The ReplicaSet recreates Pods with the same bad configuration | Fix the Deployment template, then verify the rollout |
| Treating `CrashLoopBackOff` as one specific failure | Crashes can come from app bugs, missing config, probes, permissions, or memory limits | Inspect previous logs and last termination state before patching |
| Restarting CoreDNS for one Service with empty endpoints | DNS may be healthy while the Service selector or Pod readiness is wrong | Check Service selector, EndpointSlices, labels, and readiness first |
| Draining a `NotReady` node before checking kubelet and runtime | Drain can disrupt workloads and may fail if node or API paths are unhealthy | Inspect kubelet, containerd, disk, memory, and API reachability first |
| Editing a static pod manifest without validating syntax and paths | A typo can keep a control plane component down because kubelet continuously retries the bad manifest | Check kubelet logs and manifest content carefully before and after changes |
| Installing Metrics Server whenever `kubectl top` fails | The command failure may reflect missing metrics, permissions, or cluster policy rather than workload failure | Verify whether Metrics Server is expected and allowed before installing components |

---

## Quiz

### Q1: Pending Pods After A Deployment

Your team deploys `reports-api` with three replicas. The Deployment exists, but every Pod is `Pending`, and the application team asks you for container logs. You need to choose the fastest useful first check and explain what you would do with the result.

A) Run `kubectl logs` on each Pod, because the application team needs container output to explain why startup is blocked.
B) Run `kubectl describe pod` on one Pod and read its Events, because a `Pending` Pod has not been scheduled or started yet.
C) Restart the CoreDNS Pods, because new Pods often stay `Pending` when the cluster cannot resolve Service names during startup.
D) Delete the three Pods so the ReplicaSet recreates them, because a fresh scheduling attempt usually clears a `Pending` state.
<details>
<summary>Answer</summary>

B is correct because `Pending` means scheduling has not completed, so the Events from `kubectl describe pod` are where Kubernetes explains what blocked placement. A is wrong because the container has not started, so there are usually no application logs to read. C is wrong because the usual `Pending` causes are resources, taints, selectors, affinity, PVC binding, or the scheduler itself, and cluster DNS is not part of that placement decision. D is wrong because the ReplicaSet recreates Pods from the same template, so the replacements hit the same scheduling constraint.

Start with `kubectl describe pod <pod-name>` and read the Events section because `Pending` means the Pod has not been scheduled or cannot complete scheduling-related prerequisites. Container logs are unlikely to exist because the container has not started.

If Events show insufficient CPU or memory, reduce the request if appropriate or add capacity in a real cluster. If Events show an untolerated taint, add the correct toleration only if the workload should run there. If Events show node selector or affinity mismatch, correct the Deployment template. If Events show PVC binding problems, inspect the PVC and StorageClass. The verification is `kubectl get pods -o wide` showing assigned nodes and then readiness progressing.

</details>

### Q2: CrashLoopBackOff After A New Image

A Deployment was updated ten minutes ago, and the new Pods are in `CrashLoopBackOff`. `kubectl describe pod` shows `Last State: Terminated, Reason: Error, Exit Code: 1`, but no `OOMKilled`. The previous revision worked. You need to decide whether to roll back immediately or patch configuration.

A) Roll back with `kubectl rollout undo` right away, because any crash after an image change proves the new image is the cause.
B) Raise the Deployment memory limit, because a `CrashLoopBackOff` that starts right after an update is usually an out-of-memory kill.
C) Read `kubectl logs --previous` first, then roll back if the new image is bad or patch if expected configuration is missing.
D) Delete the new Pods so the ReplicaSet retries them, because exit code 1 usually signals a transient startup problem that clears itself.
<details>
<summary>Answer</summary>

C is correct because the container started and exited, so the previous instance's logs hold the evidence that decides between a rollback and a narrow patch. A is wrong because it skips the evidence step, and a crash after an update does not by itself prove the image is bad; the new image may simply expect configuration that was never created. B is wrong because the termination reason is `Error` with exit code 1, not `OOMKilled`, so nothing points at memory. D is wrong because the replacement Pods come from the same template, and nothing in the evidence suggests the failure is transient.

Run `kubectl logs <pod-name> --previous` first because the container started and exited. If the previous logs show an application error caused by the new image, such as a failed migration or missing binary, and availability is the immediate goal, `kubectl rollout undo deployment/<name>` is the fastest safe recovery. Verify with `kubectl rollout status deployment/<name>` and `kubectl get pods`.

If the logs clearly show a missing environment variable or missing ConfigMap key that the scenario expects you to provide, patch the Deployment or create the missing configuration instead of rolling back. The decision depends on evidence. Roll back when the new revision itself is bad or unknown; patch when the intended configuration is clearly absent and the fix is narrow.

</details>

### Q3: Service Name Resolves But Requests Fail

A client Pod can resolve `checkout.default.svc.cluster.local`, but HTTP requests time out. The Service exists, and CoreDNS Pods are healthy. You need to trace the next layers without randomly restarting components.

A) Check the Service and its EndpointSlices, then compare the selector, Pod readiness, and `targetPort` with the Pods behind it.
B) Restart the CoreDNS Pods, because a timeout after a successful lookup usually means the DNS answer was stale or cached.
C) Recreate the client Pod with a new `/etc/resolv.conf`, because its resolver search path is probably pointing at the wrong namespace.
D) Delete and recreate the Service, because a new ClusterIP forces the dataplane on every node to rebuild its forwarding rules.
<details>
<summary>Answer</summary>

A is correct because name resolution already works, so the next layers on the packet path are Service routing, endpoints, readiness, and ports. B is wrong because the name resolved, which means CoreDNS has already done its part of the request. C is wrong because the client used the fully qualified name, so the resolver search path is not involved in this lookup. D is wrong because recreating the Service from the same definition brings back the same selector and `targetPort`, so it is a broad change that does not test any specific cause.

Because DNS resolution works, move to Service routing evidence. Check the Service and EndpointSlices:

```bash
kubectl get svc checkout -o wide
kubectl get endpointslice -l kubernetes.io/service-name=checkout
kubectl describe svc checkout
```

If EndpointSlices are empty, compare the Service selector with Pod labels and readiness. If endpoints exist, compare Service `targetPort` with the container's actual listening port, then consider NetworkPolicy, kube-proxy or dataplane behavior, and CNI. Restarting CoreDNS is not justified because name resolution already works.

</details>

### Q4: API Server Timeout On A Kubeadm Cluster

Every `kubectl` command times out. You can SSH to the control plane node. The incident started after someone edited a control plane manifest. You need to restore API access while collecting useful evidence.

A) Run `kubectl describe pod` for the API server in `kube-system`, because its Events will show the flag rejected after the manifest edit.
B) Run `kubeadm certs renew all` first, because API timeouts right after a manifest edit are most often caused by expired certificates.
C) Drain the control plane node and reboot it, because a restart makes kubelet rebuild every static Pod from a clean state.
D) Use host-level tools: check kubelet status and its journal, find the API server container with `crictl`, and review the edited manifest.
<details>
<summary>Answer</summary>

D is correct because the API is unavailable, so evidence has to come from kubelet, the container runtime, and the static Pod manifest directory on the node. A is wrong because every `kubectl` command already times out, so it cannot fetch Pod Events from the API server. B is wrong because the evidence points at the recent manifest edit, and renewing certificates changes a second thing without any sign that they expired. C is wrong because draining needs a working API server and eviction path, and a reboot does not correct a bad manifest that kubelet will simply read again.

Use host-level checks because the API is unavailable. Start with kubelet and static pod evidence:

```bash
sudo systemctl status kubelet
sudo journalctl -u kubelet -n 80 --no-pager
sudo crictl ps -a | grep kube-apiserver
sudo ls -l /etc/kubernetes/manifests/
```

If the API server container is restarting, inspect its container logs with `crictl logs <container-id>` and check the manifest for the recent edit. A wrong flag, bad certificate path, or YAML error can prevent the static Pod from running. After correcting the manifest, kubelet should recreate the static Pod. Verify with `crictl ps` and then `kubectl get nodes` once API access returns.

</details>

### Q5: Node Is NotReady But Workloads Still Exist Elsewhere

A worker node becomes `NotReady`. Existing workloads on other nodes are fine, but new Pods avoid the affected node. You can SSH to the node, and the container runtime is running. Kubelet logs show repeated failures reaching the API server. You need to choose the next diagnostic layer.

A) Inspect the Service selectors for workloads on that node, because `NotReady` usually means those Pods have dropped out of every endpoint list.
B) Test API server reachability from the node and read kubelet journal errors, because kubelet must reach the API to report node status.
C) Restart containerd on the node, because a `NotReady` node almost always means the container runtime has stopped answering kubelet.
D) Drain the node right away, because eviction is the fastest way to find out which host component has failed on it.
<details>
<summary>Answer</summary>

B is correct because the kubelet journal already shows that it cannot reach the API server, and the node reports its status only through that connection. A is wrong because Service selectors decide which Pods receive traffic, not whether a node reports itself `Ready`. C is wrong because the scenario states that the runtime is running, and the kubelet errors point at the API connection instead. D is wrong because drain is a maintenance action, not a diagnostic shortcut, and it depends on the same API path that is failing.

Focus on API server reachability from the node and kubelet authentication or network path, not application logs or Service selectors. The kubelet must communicate with the API server to report node status. Check network connectivity to the API endpoint, DNS or host resolution if a name is used, firewall rules, and kubelet certificate-related errors in the journal.

Useful checks include:

```bash
curl -k https://<api-server-address>:6443/healthz
sudo journalctl -u kubelet -n 120 --no-pager
```

If the API endpoint is reachable but kubelet authentication fails, inspect kubelet certificate state and configuration. If the endpoint is unreachable only from that node, inspect node network routing or firewalling. Verify by returning the node to `Ready`.

</details>

### Q6: Empty Endpoints After A Label Change

A developer changed Pod labels during a cleanup. The Deployment has healthy Pods, but traffic through the Service fails, and `kubectl get endpointslice -l kubernetes.io/service-name=web` shows no ready addresses. You need to restore traffic without recreating the application.

A) Restart kube-proxy on every node, because empty EndpointSlices mean the dataplane has lost its forwarding rules for the Service.
B) Delete and recreate the Deployment, because fresh Pods register themselves with the Service automatically when they start.
C) Compare the Service selector with the current Pod labels, then realign either the selector or the Deployment template labels.
D) Restart CoreDNS, because a label cleanup changes the Service name that DNS returns to clients inside the cluster.
<details>
<summary>Answer</summary>

C is correct because EndpointSlices get their ready addresses from Pods that match the Service selector, and the label change is the most recent difference between the two. A is wrong because kube-proxy programs traffic toward endpoints that already exist; it cannot fill an EndpointSlice whose selector matches no Pods. B is wrong because recreated Pods get the same labels from the same template, so the selector still matches nothing. D is wrong because Pod labels do not change the Service name, and DNS resolution is not the failing step here.

Compare the Service selector to the actual Pod labels:

```bash
kubectl get svc web -o jsonpath='{.spec.selector}{"\n"}'
kubectl get pods --show-labels
```

If the Service selects `app=web` but Pods now have `app=frontend`, either restore the expected Pod label through the Deployment template or update the Service selector to the correct stable label. Choose the option that matches the intended naming convention in the scenario. Verify with EndpointSlices showing addresses and a request from a client Pod. Recreating Pods is unnecessary unless you changed the Deployment template and need the controller to roll out new labels.

</details>

### Q7: Metrics Are Missing During An OOM Investigation

A Pod is repeatedly restarting, and the application owner asks for `kubectl top pod` output. The command returns `metrics not available`. You still need to determine whether memory limits are involved and decide the next action.

A) Install Metrics Server first, because the memory question cannot be answered until `kubectl top pod` returns current usage data.
B) Delete the Pod so its replacement starts with fresh memory, then watch whether the restart count keeps climbing afterward.
C) Rule memory out, because a missing `kubectl top` result means the container never used enough memory to be measured.
D) Read the Pod's last termination state and Events, then adjust the controller's memory limit if the reason is `OOMKilled`.
<details>
<summary>Answer</summary>

D is correct because the last termination state records whether the container was `OOMKilled`, and that evidence exists without any metrics pipeline. A is wrong because the root-cause question does not depend on current metrics, and installing a component may not be allowed in the cluster. B is wrong because the replacement Pod uses the same template and limit, and deleting the Pod removes the termination record you need. C is wrong because missing metrics only mean the metrics pipeline is unavailable to that command, not that memory usage was low.

Do not block on metrics if status evidence is available. Inspect the Pod termination state and Events:

```bash
kubectl describe pod <pod-name>
kubectl get pod <pod-name> -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}'
```

If the reason is `OOMKilled`, inspect the container resource limits in the controller template and adjust them if the scenario supports that fix. Metrics Server absence only means `kubectl top` cannot provide current metrics; it does not erase termination evidence. You can separately check whether Metrics Server is installed, but the immediate root-cause path uses Pod status and Events.

</details>

### Q8: Cross-Node Traffic Fails But Same-Node Traffic Works

Two Pods on the same node can communicate, but the same application fails when client and server Pods land on different nodes. Services and EndpointSlices look correct. You need to identify the likely failing subsystem and choose evidence to confirm it.

A) Inspect CNI Pods and logs across nodes, then check node-to-node reachability, because only traffic that crosses nodes is failing.
B) Fix the Service selector, because traffic between nodes is matched by labels, and a mismatch only affects Pods on remote nodes.
C) Restart CoreDNS, because Pods on different nodes resolve Service names through separate DNS caches that can drift apart.
D) Roll back the application Deployment, because a new image that fails only across nodes must contain a networking bug.
<details>
<summary>Answer</summary>

A is correct because the failure follows node placement, which points below Service objects to the CNI, overlay routing, MTU, or node firewalling. B is wrong because the Services and EndpointSlices already look correct, and a selector mismatch would break same-node traffic as well. C is wrong because same-node traffic already works with the same DNS setup, so name resolution is not what separates the working case from the failing one. D is wrong because the same application works when both Pods share a node, so the code is not the variable that changes.

Suspect CNI cross-node networking, node-to-node firewalling, overlay routing, or MTU issues because same-node traffic works while cross-node traffic fails. Service selectors and endpoints are less likely because they are already correct and same-node communication succeeds.

Check CNI Pods and logs across nodes:

```bash
kubectl -n kube-system get pods -o wide
kubectl -n kube-system logs <cni-pod-name>
```

Then inspect node network reachability if the scenario allows host access. The fix depends on the CNI implementation and evidence, but the diagnostic decision is to move below Service objects into the dataplane and node network layer.

</details>

---

## Hands-On Exercise

**Scenario**: You are given a practice cluster with a namespace named `trouble-lab`. The application team reports that `web` is unavailable through its Service, and a recent rollout may also have introduced a workload failure. Your task is to diagnose the failure path, apply the smallest correct fixes, and prove the application is reachable from inside the cluster.

**Setup Assumption**: The lab author has already created the broken objects. If you are practicing on your own cluster, you can adapt the commands to any Deployment and Service that intentionally have a selector, port, image, ConfigMap, probe, or resource mistake.

### Step 1: Establish The Namespace And Baseline

Run the broadest safe read commands first so you can identify the visible symptom without changing state or triggering controller activity that could replace the evidence you need.

```bash
kubectl get all -n trouble-lab -o wide
kubectl get events -n trouble-lab --sort-by=.lastTimestamp
```

Record whether the primary symptom appears to be workload startup, Service routing, DNS, node placement, or a combination. Do not edit anything yet. The goal is to select a layer before selecting a fix.

### Step 2: Inspect Pods By Lifecycle State

If any Pod is `Pending`, `ContainerCreating`, `ImagePullBackOff`, or `CrashLoopBackOff`, inspect one representative Pod, because Pods created from the same template usually fail for the same reason and one describe output is enough to start.

```bash
kubectl describe pod -n trouble-lab <pod-name>
```

If the container has restarted, collect previous logs, because the current instance may not have reached the failure point yet when you read its output.

```bash
kubectl logs -n trouble-lab <pod-name> --previous
```

Decide whether the fix belongs in the Deployment template, a referenced ConfigMap or Secret, a resource request or limit, an image reference, or a probe. Apply only the change supported by the evidence.

### Step 3: Verify The Controller Source Of Truth

If you change workload configuration, change the owning controller rather than an individual Pod, because the controller recreates Pods from its template and would overwrite an edit made to one Pod.

```bash
kubectl get deploy -n trouble-lab
kubectl edit deployment -n trouble-lab <deployment-name>
kubectl rollout status deployment -n trouble-lab <deployment-name>
```

After the rollout, confirm that new Pods are healthy, using the wide listing so that readiness, restarts, and node placement appear together in one view.

```bash
kubectl get pods -n trouble-lab -o wide
```

### Step 4: Trace Service Routing

Once Pods are healthy or while another teammate fixes the workload, inspect the Service path, starting with the Service object and ending with the labels on the Pods it should select.

```bash
kubectl get svc -n trouble-lab web -o wide
kubectl describe svc -n trouble-lab web
kubectl get endpointslice -n trouble-lab -l kubernetes.io/service-name=web
kubectl get pods -n trouble-lab --show-labels
```

If endpoints are empty, compare selectors and labels, then fix the Service selector or the Deployment template labels according to the intended naming. If endpoints exist, compare Service `targetPort` with the container port and application listener.

### Step 5: Test From A Client Pod

Use a temporary client Pod to test the same path a real in-cluster client would use, so the check exercises DNS, the Service, its endpoints, and the network path together.

```bash
kubectl run curl-test -n trouble-lab \
  --image=curlimages/curl:8.11.1 \
  --restart=Never \
  --rm -it -- \
  curl -sS http://web.trouble-lab.svc.cluster.local
```

If DNS fails, test CoreDNS and resolver configuration. If DNS succeeds but the HTTP request fails, continue along the Service, endpoint, port, policy, and CNI path.

### Step 6: Capture Your Reasoning

Write a short incident note for yourself with the symptom, evidence, root cause, fix, and verification command. This is not busywork. It trains the same diagnostic discipline you need during CKA scenarios, where the difference between a fast fix and a lucky guess is whether you can explain the evidence chain.

**Success Criteria**: tick an item only when you can point to the command output that proved it, not when you merely remember running the command.

- [ ] You compared the failure signature with similar states, such as `Pending` versus `ContainerCreating`, and identified the first failing layer before making changes.
- [ ] You used `kubectl describe pod` Events for scheduling, image, mount, probe, or lifecycle evidence.
- [ ] You used `kubectl logs --previous` only when the container had actually started and restarted.
- [ ] You changed the owning controller or referenced object rather than patching an ephemeral Pod.
- [ ] You verified Deployment recovery with `kubectl rollout status` when a rollout was involved.
- [ ] You verified Service routing with EndpointSlices or endpoints before testing HTTP.
- [ ] You tested the final user path from a client Pod inside the cluster.
- [ ] You can explain why your fix was narrower than deleting and recreating the application.

**Reflection Questions**: answer these after the lab, while your incident note still holds the evidence chain from the first symptom to the verified fix.

1. Which command gave you the first decisive evidence, and why was it better than the command you almost ran?
2. What would have happened if you deleted the failing Pods without fixing the source object?
3. Which verification command proved the user-visible path was fixed rather than merely proving that Kubernetes accepted your edit?
4. If this incident happened in production, what evidence would you want retained after Kubernetes Events expire?

---

## Next Module

Continue to [Part 6: Mock Exams](/k8s/cka/part6-mock-exams/) for timed practice under exam conditions, where the same layered loop of symptom, evidence, narrow fix, and verification has to fit inside a fixed time budget.

## Sources

- [cncf.io: cka](https://www.cncf.io/training/certification/cka/) — CNCF publishes the current CKA domain weights and lists Troubleshooting at 30%.
- [kubernetes.io: pods](https://kubernetes.io/docs/concepts/workloads/pods/) — The Kubernetes Pods documentation states that a main use for static Pods is running a self-hosted control plane.
- [kubernetes.io: static pod](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/) — The static Pod task documents that kubelet periodically scans the configured manifest directory and adds or removes Pods as files appear or disappear.
- [kubernetes.io: pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/) — The Pod lifecycle documentation defines CrashLoopBackOff as the backoff state for a repeatedly crashing container.
- [kubernetes.io: crictl](https://kubernetes.io/docs/tasks/debug/debug-cluster/crictl/) — The crictl task explicitly describes crictl as a CLI for CRI-compatible runtimes used for node-level inspection and debugging.
- [kubernetes.io: node status](https://kubernetes.io/docs/reference/node/node-status/) — The node status reference defines Ready semantics and explains that missed heartbeats drive `Unknown` or `False` readiness states.
- [kubernetes.io: endpoint slices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) — EndpointSlice readiness is documented as mapping to Pod readiness for Service traffic selection.
- [kubernetes.io: index.html](https://kubernetes.io/docs/concepts/services-networking/service/index.html) — The Service documentation explicitly describes mapping a Service `port` to a backend `targetPort` on Pods.
- [kubernetes.io: dns pod service](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/) — The DNS for Services and Pods documentation explains namespace-scoped short-name lookup and the need to specify namespace for cross-namespace resolution.
- [kubernetes.io: network policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — The NetworkPolicy documentation covers independent ingress and egress isolation and explicitly notes that workloads needing DNS resolution require a separate egress policy.
- [kubernetes.io: event v1](https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/event-v1/) — The Event API reference says Events have limited retention time and are informative, best-effort supplemental data.
- [kubernetes.io: kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/) — The kubectl logs reference documents `--previous` as printing the previous container instance logs when available.
- [kubernetes.io: kubectl top](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_top/) — The kubectl top reference states that it fetches data from Metrics Server and requires that component to be installed and running.
- [Troubleshooting Applications](https://kubernetes.io/docs/tasks/debug/debug-application/) — Covers practical debugging paths for Pods, Services, StatefulSets, and common container failure modes.
