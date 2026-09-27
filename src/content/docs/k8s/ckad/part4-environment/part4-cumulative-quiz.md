---
revision_pending: false
title: "Part 4 Cumulative Quiz: Application Environment, Configuration and Security"
sidebar:
  order: 7
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 80–95 minutes, including a 25-minute quiz and a hands-on drill
>
> **Prerequisites**: [Module 4.1: ConfigMaps](../module-4.1-configmaps/), [Module 4.2: Secrets](../module-4.2-secrets/), [Module 4.3: Resource Requirements and Limits](../module-4.3-resources/), [Module 4.4: SecurityContexts](../module-4.4-securitycontext/), [Module 4.5: ServiceAccounts](../module-4.5-serviceaccounts/), and [Module 4.6: Custom Resource Definitions](../module-4.6-crds/)

## Learning Outcomes

After completing this cumulative review of Modules 4.1 through 4.6, you should be able to perform each of these tasks under exam-style time pressure:

- **Diagnose** ConfigMap and Secret delivery failures from the namespace, key names, volume `items`, and Pod status, separating `ContainerCreating` from `CreateContainerConfigError`.
- **Predict** which configuration edits reach a running container through environment variables, ordinary directory mounts, and `subPath` mounts.
- **Distinguish** how CPU and memory requests affect scheduling while limits affect runtime throttling and OOM kills, including equivalent quantities such as `cpu: 0.1` and `cpu: 100m`.
- **Evaluate** Pod identity settings, including `runAsNonRoot`, `runAsUser`, the assigned ServiceAccount, and token automount behavior.
- **Separate** what a CustomResourceDefinition registers from what a controller reconciles, and predict what deleting a CRD does to its custom resources.

## Why This Module Matters

Hypothetical scenario: a developer moves a small report API from a laptop into a shared namespace. The same image must read a log level, a database password, and a properties file. It must fit the namespace's resource policy, run as a non-root user, and avoid holding an API token it never uses. A platform team has also installed a custom `Backup` resource, and the developer expects that creating one will schedule backups. Each expectation belongs to a different Part 4 mechanism, and each one fails with a different visible symptom.

The six Part 4 modules teach those mechanisms separately. [Module 4.1](../module-4.1-configmaps/) covers how configuration enters a container and when edits reach it. [Module 4.2](../module-4.2-secrets/) applies the same delivery paths to sensitive values and explains what base64 does not protect. [Module 4.3](../module-4.3-resources/) separates scheduling reservations from runtime ceilings. [Module 4.4](../module-4.4-securitycontext/) turns identity and filesystem assumptions into fields. [Module 4.5](../module-4.5-serviceaccounts/) follows a workload identity from admission to authorization. [Module 4.6](../module-4.6-crds/) separates a registered API type from the controller that acts on it.

Use the core content as a decision guide before you attempt the quiz. Then hide the answers and give yourself 25 minutes for its eight scenarios. Every question has one best option under its stated assumptions, and every wrong option is a mistake that a Part 4 learner could plausibly make. The answer blocks explain each option, because a correct-looking edit can still target the wrong stage. After scoring, complete the hands-on drill and use its observations to test any reasoning you were unsure about.

## Core Content

### Name the stage before you edit

Part 4 features share one pattern: an object or field is accepted at one stage and consumed at another. The API server validates and admits objects, the scheduler places Pods by their requests, the kubelet builds each container's volumes and environment, and the running process finally reads files, variables, and tokens. A symptom tells you which stage stopped. Reading that stage first is faster than editing every field that sounds related, because a fix aimed at the wrong stage leaves the original failure untouched.

Admission failures appear when you create or update an object, before a Pod exists or before a custom resource is stored. A LimitRange minimum or maximum, an exhausted ResourceQuota, a ServiceAccount name that does not exist in the namespace, and a custom resource that violates its CRD schema all fail here. Scheduling failures leave an existing Pod `Pending` with events such as `Insufficient memory`. Container setup failures leave a scheduled Pod in `ContainerCreating` or `CreateContainerConfigError`. Runtime failures show a container that is slow, restarting, or denied by an application or by the API server.

| Evidence you see | Stage that stopped | First check |
|---|---|---|
| `kubectl apply` returns an error | Admission or schema validation | The error's field path, LimitRange, ResourceQuota, ServiceAccount name, or CRD schema |
| `Pending` with `Insufficient cpu` or `Insufficient memory` | Scheduling | Container requests and node allocated resources |
| `ContainerCreating` with a mount event | Volume setup | ConfigMap or Secret name, namespace, and `items` keys |
| `CreateContainerConfigError` | Environment setup | `configMapKeyRef` or `secretKeyRef` object and key names |
| Start refused because the container would run as root | Security check | `runAsNonRoot`, `runAsUser`, and the image default user |
| Last state `OOMKilled`, or Running but slow | Runtime limits | Memory limit and usage, or CPU limit throttling |
| The application receives `403 Forbidden` from the API server | Authorization | RoleBinding subjects and Role rules for the ServiceAccount |

```bash
kubectl get pod report-api -n reports
kubectl describe pod report-api -n reports
kubectl get events -n reports --sort-by=.lastTimestamp
kubectl get pod report-api -n reports -o jsonpath='{.status.containerStatuses[0].lastState}'
```

These commands are diagnostic examples, not recorded output, and the namespace and Pod names are illustrative. `kubectl describe pod` is the most useful single command in this Part because it shows the assigned ServiceAccount, the mounted volumes, the container state, the last termination reason, and the events that name a missing key, object, or resource. Logs help only after a process has started. A container stuck before startup has no application logs that could explain its missing volume.

### ConfigMaps: namespace, key, and delivery shape

A ConfigMap is a namespaced object that holds non-sensitive key-value data, and a Pod can reference a ConfigMap only in its own namespace. That rule explains a common exam trap. You create `app-config` without `-n`, so it lands in your current namespace, and then you apply the Pod to `production`. Running `kubectl get configmap app-config` from the same shell appears to prove the object exists, yet the Pod's reference still fails. Include the namespace in every inspection command once more than one namespace is involved, and compare the Pod's namespace with the object's namespace before editing keys.

The delivery shape decides what a later edit can reach. Environment values taken from a ConfigMap, whether through `configMapKeyRef` or `envFrom`, are fixed when the container starts; the kubelet never rewrites a running process environment. An ordinary directory mount of the ConfigMap can pick up later changes after the kubelet's sync delay, which Module 4.1 describes as commonly about a minute. A `subPath` mount does not receive those updates, because its file is bound when the container starts. Even a refreshed file matters only if the application rereads it.

Mount failures depend on whether the Pod asks for particular keys. A volume `items` list is a whitelist plus an optional filename remap. If `items` names a key that the ConfigMap lacks, and the reference is not marked `optional: true`, the mount fails: the container stays `ContainerCreating`, and an event names the missing key. When the whole ConfigMap is mounted as a directory instead, the kubelet projects the keys that exist. A key the application expects but the object does not contain can let the container start without that file, so the failure moves into application behavior.

Those two outcomes need different evidence. A `ContainerCreating` Pod needs `kubectl describe pod` and its events, because no process has started yet. A started container with a missing file needs a look inside the container, such as a listing of the mounted directory, followed by a comparison with the keys shown by `kubectl get configmap -o yaml`. The `optional: true` flag changes which of these symptoms you see, not whether the data is correct. It is useful when an application has a real fallback and harmful when a required setting silently disappears.

Directory mounts have one more side effect. Mounting a volume at a path hides whatever the image already had at that path, because Kubernetes places the volume there instead of merging two directories. Mounting a ConfigMap over `/etc/nginx/conf.d` therefore removes the image's default files from view. Mounting one key as a file with `subPath` preserves neighboring files but gives up live updates. Mapping a key through `items` can rename the projected file, which is often cleaner than rebuilding an image just because the application expects a different filename.

**Pause and predict:** A ConfigMap named `web-config` contains only the key `default.conf`, and neither Pod below marks its reference optional. Pod A mounts it through an `items` entry that names `site.conf`. Pod B mounts the whole ConfigMap at `/etc/web`, and its application expects `/etc/web/site.conf`. Which Pod's container starts, and where would you find each problem?

<details>
<summary>Prediction answer</summary>

Pod A stays in `ContainerCreating`, and its events name the missing key `site.conf`, because a required `items` key cannot be projected. Pod B's container starts, because a whole-directory mount projects only `default.conf`. Its problem appears inside the container or in application logs, where `site.conf` is absent.

</details>

Carry that split into every mount question you meet. A healthy container status proves only that the kubelet completed the volume setup it was asked to perform, so check the files that the process actually opens before you call the configuration finished.

### Secrets: the same mechanics with stricter handling

Secrets reuse the ConfigMap delivery mechanics: a Pod can read one key through `secretKeyRef`, import every key with `envFrom`, mount the object as files, or project selected keys through `items`. Secret references are also namespaced, and the kubelet delivers decoded values into the container. The difference is intent and handling. A Secret is meant for sensitive values, it has types such as `kubernetes.io/tls` and `kubernetes.io/dockerconfigjson` that fix the expected key names, and access to it should be treated as access to the credential itself.

The `data` field holds base64-encoded values, and base64 obscures data without encrypting it. Anyone who can `get` the Secret can decode a key with one pipeline. The `stringData` field is a write-only authoring convenience: you submit plain text, the API server converts it into `data`, and later reads return `data`, not `stringData`. Protection comes from controls around the object. RBAC limits readers, encryption at rest can protect values inside etcd when administrators configure it, and careful Pod design keeps decoded values out of logs. Both Secrets and ConfigMaps are limited to 1 MiB per object.

Missing Secrets fail in two recognizable ways. A required environment reference that cannot be resolved, because the Secret or the key is absent, leaves the container in `CreateContainerConfigError`, since the kubelet cannot construct its environment. A Secret volume whose Secret is missing leaves the container in `ContainerCreating`, because the mount cannot be prepared. Neither failure involves the password bytes. Check the Pod's namespace, the Secret name, and the key spelling before you decode anything, because an absent key cannot be fixed by changing a value.

```bash
kubectl get secret db-creds -n billing
kubectl get secret db-creds -n billing -o jsonpath='{.type}'
kubectl describe pod api -n billing
kubectl get secret db-creds -n billing -o jsonpath='{.data.password}' | base64 -d
echo
```

Run those commands in order, and stop as soon as one explains the symptom. The last command decodes one key only after the structure is confirmed, and the separate `echo` keeps your prompt from running into the value. A wrong value behaves differently from a missing reference. If a value was encoded with plain `echo`, its decoded bytes include a trailing newline; the container starts normally, and the application reports an authentication failure. Encoding with `echo -n`, writing `stringData`, or using `kubectl create secret generic` avoids that mistake.

Private image pulls follow a separate path. The kubelet expects a Secret of type `kubernetes.io/dockerconfigjson`, usually created with `kubectl create secret docker-registry`, referenced under the Pod's `imagePullSecrets`, and stored in the Pod's namespace. A generic Secret containing a username and password is the wrong shape for that flow. Because this failure happens before the container starts, the Pod shows `ImagePullBackOff`, and application environment variables are irrelevant to the fix. Rotation adds timing: environment values need new Pods, while mounted Secret files can refresh for applications that reread them.

### Requests reserve capacity; limits enforce runtime

Requests affect scheduling, and limits affect runtime. The scheduler treats each container's requests as a reservation and places a Pod only where the summed requests fit into a node's allocatable capacity that is not already reserved. It does not measure live usage. A Pod can therefore stay `Pending` with `Insufficient memory` while node dashboards show idle memory, because earlier Pods have reserved it. Lowering a limit does not help that Pod schedule; only a smaller honest request, freed reservations, or more capacity changes the placement test.

Limits act after the container is running, and CPU and memory respond differently. CPU is compressible, so a container that tries to use more CPU than its limit is throttled: it keeps running, often with slow responses and no restarts. Memory is not compressible, so a container that exceeds its memory limit can be OOM-killed and restarted, with `OOMKilled` recorded in its last state. That split gives a quick diagnostic rule. A slow Running container points toward CPU, while restarts with `OOMKilled` point toward memory limits or application memory behavior.

**Pause and predict:** A container sets `requests.cpu: 0.1`, `limits.cpu: 200m`, and a memory request and limit of `256Mi` each. Under load it stays Running with zero restarts, yet its responses slow down sharply. A teammate proposes raising the memory limit and rewriting `0.1` as `100m`. Which setting is the more likely constraint, and does either proposed edit address it?

<details>
<summary>Prediction answer</summary>

The CPU limit is the likely constraint, because CPU above a limit is throttled rather than killed, which matches a slow container with no restarts. Neither edit addresses it: the absence of `OOMKilled` restarts suggests the memory limit is not being crossed, and `cpu: 0.1` already equals `cpu: 100m`.

</details>

Before raising any CPU limit, confirm throttling with usage or application metrics, because a slow Running container can also reflect a database, a lock, or a code path that no resource field will repair.

Quantities have exact meanings. CPU is measured in cores, and the `m` suffix means millicores, so `1` equals `1000m` and `cpu: 0.1` equals `cpu: 100m`. Memory accepts binary suffixes such as `Mi` and `Gi`, which count in powers of 1024, and decimal suffixes such as `M` and `G`, which count in powers of 1000. The values are close but not identical, so consistent `Mi` and `Gi` units make reviews easier. Resources belong under each container, and a Pod's scheduling request sums its regular containers. For each resource, the scheduler uses the larger of that sum and the biggest init-container request.

Resource settings also determine a Pod's Quality of Service class. When every container sets CPU and memory requests equal to their limits, the Pod is Guaranteed and receives the strongest eviction protection. When some requests or limits are set but the Guaranteed condition is not met, the Pod is Burstable. When no container sets any requests or limits, the Pod is BestEffort and is first in line for eviction under node pressure. Admission policy can change what you wrote, because a LimitRange can inject default requests and limits, so inspect the stored Pod when its class matters.

Namespace policy fails at admission, not at scheduling. A LimitRange can reject a container whose values fall below its minimum or above its maximum. A ResourceQuota can reject a new Pod whose requests or limits would exceed the namespace budget, even when nodes have plenty of free capacity. Those errors return from `kubectl apply` before any Pod exists. Matching the command to the stage keeps you from reading node allocation when the real blocker is a namespace quota, and it keeps you from editing quotas when the scheduler is the stage that failed.

```bash
kubectl get pod report-api -n reports -o jsonpath='{.spec.containers[*].resources}'
kubectl get pod report-api -n reports -o jsonpath='{.status.qosClass}'
kubectl describe node NODE_NAME | grep -A10 "Allocated resources"
kubectl describe limitrange -n reports
kubectl describe resourcequota -n reports
```

### SecurityContext: assertions, identities, and writable paths

SecurityContext appears at two levels. The Pod-level `spec.securityContext` supplies defaults such as `runAsUser`, `runAsGroup`, and `runAsNonRoot`, plus pod-scoped settings such as `fsGroup`. The container-level `securityContext` holds process settings such as `allowPrivilegeEscalation`, `readOnlyRootFilesystem`, and capabilities, and it can override supported identity fields for one container. When the same field appears at both levels, the container value wins for that container, while every field the container does not set is still inherited from the Pod.

The `runAsNonRoot: true` setting is an assertion, not an instruction. It does not change the UID. It tells the kubelet to reject a container that would run as UID 0, whether that UID comes from the image's default user or from an explicit `runAsUser: 0`. A container-level `runAsUser: 0` therefore conflicts with a Pod-level `runAsNonRoot: true` instead of overriding it, and the start fails with an event explaining that the container would run as root. Pair the guard with a numeric non-zero `runAsUser`, such as `1000`, then prove the result with `kubectl exec POD -- id`.

Permission errors after a successful start belong to a different layer. The `runAsUser` field sets the process UID and `runAsGroup` sets its primary group, while `fsGroup` adds a supplementary group and can adjust group ownership on supported mounted volumes; it does not change files baked into the image. Setting `readOnlyRootFilesystem: true` blocks writes to the image layer, so an application that needs scratch, cache, or socket paths needs explicit writable mounts, usually `emptyDir` volumes at paths such as `/tmp` or `/var/run`. Mounting only the paths that need writes keeps the broader protection in place.

Privilege settings should stay narrow and visible. Setting `allowPrivilegeEscalation: false` stops a process from gaining more privilege than its parent. Dropping `ALL` capabilities and adding back one named capability, such as `NET_BIND_SERVICE` for a port below 1024, grants a specific kernel permission without broad access. Setting `privileged: true` grants broad host access and is rarely right for an application Pod. In a namespace that enforces the restricted Pod Security Standard, privileged mode, privilege escalation, and missing non-root controls become admission rejections that usually name the offending field.

### ServiceAccounts: identity, token, then authorization

Every Pod has a Kubernetes identity, even when its manifest does not name one. If `spec.serviceAccountName` is empty, the ServiceAccount admission controller writes the namespace's `default` ServiceAccount into the Pod. Unless token automounting is disabled, the kubelet also projects a token, a CA certificate, and a namespace file under `/var/run/secrets/kubernetes.io/serviceaccount/`. A Pod that never calls the API still carries that credential, so a static web server or a database-only worker should set `automountServiceAccountToken: false` on the Pod, or on the ServiceAccount it uses.

Assign a purpose-built ServiceAccount through `serviceAccountName` in the Pod spec, which for a Deployment means `spec.template.spec`. The ServiceAccount must exist in the Pod's namespace; otherwise admission rejects the new Pods. Changing the template triggers a rollout, so verify the replacement Pods rather than the old ones. The identity is shared by every container in the Pod, which is one reason to keep unrelated processes out of a Pod that holds API permissions. The subject name the API server sees is `system:serviceaccount:<namespace>:<name>`, and that exact string appears in authorization errors.

Token handling changed in Kubernetes 1.24. Since that release, long-lived ServiceAccount token Secrets are not created automatically, and `kubectl describe sa default` can show `Tokens: <none>` while admitted Pods still receive projected tokens. Those projected tokens are bound to the Pod and expire, and the kubelet refreshes them before they become invalid. For workstation debugging, `kubectl create token NAME` asks the TokenRequest API for a short-lived token. Recreating the legacy token Secret type for a new workload revives the long-lived credential that the newer model removed.

Authentication and authorization fail differently. An authentication error points at the token, which may be missing because automount is off, expired in a client that never rereads it, or aimed at the wrong audience. A `403 Forbidden` response that names `system:serviceaccount:reports:report-reader` proves the token worked, because the API server identified the caller before RBAC denied the verb. The fix is a Role and RoleBinding that grant that exact verb and resource. Recreating Pods or tokens cannot fix a missing binding, and broader RBAC cannot fix a missing token.

```bash
kubectl get pod report-api -n reports -o jsonpath='{.spec.serviceAccountName}'
kubectl exec -n reports report-api -- ls /var/run/secrets/kubernetes.io/serviceaccount/
kubectl auth can-i list pods --as=system:serviceaccount:reports:report-reader -n reports
```

The first command shows the identity that admission assigned, the second shows whether a token was projected into the container, and the third asks the authorization layer about one verb and resource for that subject. Run them in that order, because each answer points to the next layer and keeps you from widening permissions when the credential itself is the missing piece.

### CRDs: registration is not reconciliation

A CustomResourceDefinition registers a new resource type with the API server. The CRD is a cluster-scoped object named `plural.group`, such as `backups.example.com`, and it declares the kind, scope, names, versions, and an `openAPIV3Schema`. Once the CRD is established, the API server serves the new endpoint, stores custom resources, applies RBAC and admission, and validates each object against the schema. A version with `served: true` can be requested, and exactly one version is marked `storage: true`. A manifest whose `apiVersion` names an unserved version is rejected before any controller sees it.

Registration is not action. A controller, if one exists, watches the custom resources, creates or updates lower-level objects, and records progress in `status`. Creating a custom resource does not by itself provision the thing its name suggests. A `Backup` object without a running controller is stored intent: `kubectl get backups` lists it, and nothing else happens. When an accepted object produces no child resources, inspect its status and events, then the controller's Pods, logs, and permissions, rather than the CRD schema that already accepted it.

Validation errors come from the API server. If `kubectl apply` reports an unsupported value, a missing required field, or a type mismatch for a custom resource, the CRD schema rejected it, and the controller never received the object. Read `spec.versions[*].schema.openAPIV3Schema`, or run `kubectl explain` on the resource, to find accepted field paths. Discovery commands confirm the vocabulary. `kubectl get crd` lists definitions, while `kubectl api-resources` shows the plural name, group, scope, and short names you actually type. In scripts, wait for the `Established` condition before creating the first custom resource.

Deletion needs care at both levels. Deleting a custom resource lets its controller run cleanup, and a finalizer can hold the object in a terminating state until that controller removes it. Deleting the CRD is much broader: it removes the resource type, and it can delete every custom resource that the CRD served. Treat CRD deletion as an administrative decommissioning step, not as a reset button. Delete instances first, confirm what remains, and only then remove the definition when you intend to retire the whole type.

```bash
kubectl get crd backups.example.com
kubectl api-resources | grep example.com
kubectl wait --for condition=established --timeout=60s crd/backups.example.com
kubectl explain backup.spec
kubectl describe backup nightly -n reports
```

### Read one combined manifest

The manifest below combines the Pod-level Part 4 mechanisms in one Pod that you will run in the hands-on exercise, so save it as `part4-app.yaml`. It reads one ConfigMap key into the environment, mounts the whole ConfigMap as a directory, projects one Secret key under a new filename, reserves and limits resources, runs as a non-root UID with a read-only root filesystem, and uses a named ServiceAccount without a mounted token. The CRD part of the exercise stays separate, because a custom resource type is cluster-wide API vocabulary rather than a Pod field.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: part4-app
  namespace: part4-drill
spec:
  serviceAccountName: app-runner
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    env:
    - name: LOG_LEVEL
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: LOG_LEVEL
    resources:
      requests:
        cpu: "100m"
        memory: "64Mi"
      limits:
        cpu: "200m"
        memory: "128Mi"
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: ["ALL"]
    volumeMounts:
    - name: config
      mountPath: /etc/app
    - name: secret
      mountPath: /etc/app-secret
      readOnly: true
    - name: scratch
      mountPath: /tmp
  volumes:
  - name: config
    configMap:
      name: app-config
  - name: secret
    secret:
      secretName: app-secret
      items:
      - key: password
        path: db-password
  - name: scratch
    emptyDir: {}
```

Read the fields as a chain of predictions. The `configMapKeyRef` value is fixed at startup, so editing `LOG_LEVEL` later changes the file under `/etc/app` but not the variable. The Secret `items` entry names `password`, and a typo there would hold the container in `ContainerCreating`. The requests are smaller than the limits, so the QoS class should be Burstable. The `runAsNonRoot` guard passes because `runAsUser` is `1000`, while `fsGroup` applies to the mounted volumes. The `emptyDir` gives `/tmp` a writable path, and automount is off, so no token directory should exist.

Each prediction names the command that would disprove it. Running `id` through `kubectl exec` checks the UID and groups, a `touch` under `/` should fail while one under `/tmp` succeeds, and a listing of the token path should report that it does not exist. The QoS class and ServiceAccount name come from the stored Pod through JSONPath. This habit matters more than the specific manifest, because a Part 4 answer is complete only when an observation confirms that the setting did what you expected.

### Rehearse the triage order

The first rehearsal starts with a Pod in `ContainerCreating` that mounts both a ConfigMap and a Secret. Its events name a missing key in the ConfigMap volume. Nothing about the image, the Secret value, or the resource settings can explain that event. Compare the `items` key with the object's keys in the Pod's namespace, fix the key or the object, and watch the event history before touching other fields. If the event instead names a missing object, check the namespace first, because the object may exist somewhere else.

The second rehearsal is `CreateContainerConfigError` after a new `secretKeyRef` was added. The kubelet could not build the container's environment, so a required Secret or key is missing from the Pod's namespace. Decoding the password is premature, because the structure is wrong rather than the bytes. Once the reference resolves and the container starts, an authentication error in the application becomes the next clue. Only then is decoding one key to look for a trailing newline the right move.

The third rehearsal separates three resource symptoms. A Pod that is `Pending` with `Insufficient cpu` needs its requests compared with allocatable capacity and existing reservations. A container whose last state is `OOMKilled` needs its memory limit compared with real peaks, runtime overhead, and cache behavior. A container that stays Running but slow under load needs its CPU limit and throttling signals checked. An `apply` error that names a LimitRange or ResourceQuota is an admission failure, and no node command explains it.

The fourth rehearsal covers identity. If a container never starts and its events say it would run as root, compare the Pod's `runAsNonRoot` with the effective UID from the image or `runAsUser`, and add a numeric non-zero UID rather than removing the guard. If the container starts but logs `permission denied` on a write, run `id` and list the target path. A mounted volume may need `fsGroup`, while a path on a read-only root filesystem needs its own writable mount.

The fifth rehearsal is an application that reports API errors. First confirm which ServiceAccount the running Pod received, because a template edit may not have rolled out yet. Next confirm whether a token exists at the projected path. Then read the error itself: an authentication failure points back to the token, while a forbidden response naming the ServiceAccount subject points to RBAC. Running `kubectl auth can-i` with `--as` answers the RBAC question without redeploying anything or printing a token.

The final rehearsal is a custom resource that exists and does nothing. Because `kubectl get` lists it, the CRD accepted and stored it. The next evidence is the object's status and events, then whether a controller is installed and allowed to create the child objects it manages. Deleting and recreating the CRD is the wrong experiment, because it can delete every custom resource of that type while teaching you nothing about the controller.

## Did You Know?

- **Did You Know?** ConfigMaps and Secrets share a 1 MiB size limit per object, so large payloads belong in images, artifact stores, or volumes designed for them. See [Module 4.1](../module-4.1-configmaps/) and [Module 4.2](../module-4.2-secrets/).
- **Did You Know?** `cpu: 0.1` and `cpu: 100m` are the same quantity, because Kubernetes measures CPU in cores and `1000m` equals one core. See [Module 4.3](../module-4.3-resources/) and the [resource management guide](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).
- **Did You Know?** `fsGroup` affects supported mounted volumes, not files already baked into the container image, so it cannot repair image-layer ownership. See [Module 4.4](../module-4.4-securitycontext/) and the [security context task](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/).
- **Did You Know?** Since Kubernetes 1.24, long-lived ServiceAccount token Secrets are not created automatically, so `Tokens: <none>` does not mean a Pod lacks a projected token. See [Module 4.5](../module-4.5-serviceaccounts/) and the [ServiceAccount concept page](https://kubernetes.io/docs/concepts/security/service-accounts/).

## Common Mistakes

| Mistake | Why it misleads | Better check or design |
|---|---|---|
| Creating the ConfigMap or Secret in one namespace and the Pod in another | Pod references resolve only in the Pod's own namespace, so the object seems to exist but the reference fails. | Create the object in the Pod's namespace and verify both with `-n`. |
| Expecting environment values or a `subPath` file to change after a ConfigMap edit | Environment values are fixed at container start, and `subPath` mounts do not receive projection updates. | Roll out new Pods, or use an ordinary directory mount with an application that rereads files. |
| Treating a started container as proof that every expected key arrived | A whole-directory mount projects only the keys the object has. | List the mounted directory inside the container; use `items` when a missing key should block startup. |
| Treating base64 in `data` as encryption | Any reader with `get` on the Secret can decode it. | Restrict RBAC, rely on encryption at rest where configured, and avoid printing decoded values. |
| Raising a limit to fix a `Pending` Pod | The scheduler fits requests, not limits, against allocatable capacity. | Right-size the request, free reservations, or add capacity; confirm with Pod events. |
| Reading `runAsNonRoot: true` as "switch to a non-root user" | It asserts that UID 0 is forbidden and never assigns a UID. | Set a numeric non-zero `runAsUser` and verify it with `id`. |
| Assuming an empty `serviceAccountName` means no API credential | Admission assigns the namespace `default` ServiceAccount, and a token is projected unless automount is off. | Set `automountServiceAccountToken: false` for Pods that never call the API. |
| Deleting a CRD to reset a stuck custom resource | Deleting the CRD can delete every custom resource of that type. | Inspect status, events, finalizers, and the controller; delete instances deliberately. |

## Quiz

Attempt these eight scenarios without opening the answers. Allow about 25 minutes, and choose the action that best matches the stated evidence. A score of at least six correct is a useful signal to continue to the lab; revisit the source module for any explanation that still surprises you. Each wrong option is a plausible Part 4 mistake, so eliminate options by naming the stage each one would actually change.

### Question 1: A mount that never finishes

A ConfigMap named `web-config` in namespace `shop` was created from a file named `default.conf`, so its only key is `default.conf`. A Pod in `shop` mounts that ConfigMap through a volume whose `items` list names the key `nginx.conf` and maps it to the path `default.conf`. The Pod has stayed in `ContainerCreating` for several minutes, and its events name the missing key. Which action best fixes the cause?

A) Add `optional: true` to the ConfigMap volume so the container starts now and receives the file on the next kubelet sync.
B) Change the `items` key to `default.conf`, or add an `nginx.conf` key to the ConfigMap, then confirm the event clears and the file appears.
C) Run `kubectl rollout restart` on the owning Deployment, because ConfigMap volumes are projected only when a new ReplicaSet starts.
D) Replace the volume with `envFrom` so the ConfigMap keys arrive as environment variables instead of as mounted files.

<details>
<summary>Answer and reasoning</summary>

**Correct: B.** The `items` list names a key the object does not contain, and the reference is required, so the container waits in `ContainerCreating` because the kubelet cannot build that volume. Fixing either the key name or the object removes the mismatch. A) is wrong because `optional: true` starts the container without the file, and a later sync cannot invent a key that was never added. C) replaces Pods but keeps the same broken reference. D) changes the delivery shape, and an application that reads a configuration file still would not find one.

</details>

### Question 2: Which consumer sees the edit?

A container reads `LOG_LEVEL` through `configMapKeyRef`, reads `/etc/app/app.properties` from an ordinary directory mount of the same ConfigMap, and reads `/etc/nginx/conf.d/default.conf` through a `subPath` mount of a third key. You edit all three keys in the ConfigMap and do not replace the Pod. After the kubelet sync delay, which configuration change reaches the running container?

A) All three values, because the kubelet refreshes every consumer of a ConfigMap on its sync period.
B) The environment variable and the `subPath` file, because both consumers name one specific ConfigMap key.
C) Only the `subPath` file, because a precise file mount is refreshed faster than a whole directory mount.
D) Only the directory-mounted file; the environment variable and the `subPath` file both need a new Pod.

<details>
<summary>Answer and reasoning</summary>

**Correct: D.** Environment values are fixed when the container starts, and a `subPath` mount does not receive later projection updates, so only the ordinary directory mount changes on disk. The application must still reread `app.properties` to use the new content. A) is wrong because the kubelet does not rewrite a running process environment. B) is wrong because naming a key does not make either consumer live-updating. C) reverses the `subPath` tradeoff: it preserves neighboring image files but gives up updates.

</details>

### Question 3: Two missing Secrets, two statuses

In namespace `billing`, Pod `api` reads `DB_PASSWORD` through a required `secretKeyRef` to Secret `db-creds`. Pod `tls-proxy` mounts Secret `proxy-tls` as a volume. Neither Secret exists in `billing`, although a teammate created both in `default`. Which status pairing and fix match this evidence?

A) `api` shows `CreateContainerConfigError` and `tls-proxy` stays in `ContainerCreating`; create both Secrets in `billing` with the referenced keys.
B) Both Pods show `ImagePullBackOff`; add each Secret name under `imagePullSecrets` so the kubelet can fetch the values.
C) Both containers start with an empty variable and an empty directory, because Secret references are optional by default.
D) Both Pods stay `Pending`, because the scheduler waits for Secrets, and the copies in `default` are found after a retry.

<details>
<summary>Answer and reasoning</summary>

**Correct: A.** A required environment reference that cannot be resolved stops the kubelet from building the container configuration, which shows as `CreateContainerConfigError`, while a missing Secret volume keeps the container in `ContainerCreating`. Secret references resolve only in the Pod's namespace, so copies in `default` do not help. B) is wrong because `imagePullSecrets` carries registry credentials of type `kubernetes.io/dockerconfigjson`, not application data. C) is wrong because references are required unless marked `optional: true`. D) confuses scheduling with container setup, and a Pod-to-Secret lookup never crosses namespaces.

</details>

### Question 4: What base64 and stringData really do

A teammate writes a Secret manifest with `stringData.password`, applies it, and says the password is now protected: "The API stores it as base64 in `data`, and `stringData` is never returned, so nobody can read the value back." Which response is accurate?

A) Correct, because the API server encrypts `stringData` into `data`, and reads return ciphertext that only the kubelet can decrypt.
B) Correct only if the Secret is marked `immutable: true`, because immutability prevents anyone from reading its stored data.
C) Partly wrong: `stringData` is write-only, but `data` is only base64-encoded, so anyone who can get the Secret can decode it.
D) Partly wrong: the value should move to a ConfigMap, because ConfigMaps are namespaced and hidden from other Pods.

<details>
<summary>Answer and reasoning</summary>

**Correct: C.** `stringData` is a write-only convenience, so later reads return the encoded `data` field, and base64 is not encryption; read access to the Secret is effectively access to the value. Real protection comes from RBAC, encryption at rest configured by cluster administrators, and careful delivery into Pods. A) is wrong because the API server encodes rather than encrypts, and encryption at rest does not stop an authorized reader from retrieving the Secret. B) is wrong because immutability blocks edits, not reads. D) is wrong because ConfigMaps are meant for non-sensitive data and offer no stronger read protection.

</details>

### Question 5: Pending while memory sits idle

Pod `report-api` stays `Pending`, and `kubectl describe pod` shows that no node has enough memory, reporting `Insufficient memory` for each one. Its only container requests `memory: 3Gi` with a `4Gi` limit, and it declares `cpu: 0.5` for both its request and its limit. Monitoring from a similar environment shows the process uses about `1Gi`. Which change is the safest effective way to clear the `Pending` status?

A) Raise the memory limit to `6Gi`, so the scheduler sees more headroom for this container on every node.
B) Rewrite `cpu: 0.5` as `cpu: 500m`, because decimal CPU quantities make the scheduler reject the resource request.
C) Remove every request and limit, so the Pod becomes BestEffort and no longer needs reserved capacity from the scheduler.
D) Lower the memory request toward the measured baseline, keep a limit with headroom, and confirm placement from Pod events.

<details>
<summary>Answer and reasoning</summary>

**Correct: D.** The scheduler places Pods by comparing requests against unreserved allocatable capacity, so an overstated `3Gi` request can block placement even when node memory sits idle. A request closer to real use, with a limit above expected peaks, addresses the stage that failed. A) is wrong because limits are runtime ceilings, and raising one does not shrink the reservation. B) is wrong because `cpu: 0.5` and `cpu: 500m` are the same quantity. C) can drop the scheduling request when no LimitRange injects defaults, so the Pod might schedule. It is still the wrong choice here, because a BestEffort Pod is evicted first when the node comes under memory pressure.

</details>

### Question 6: A guard, not a switch

A Pod-level `securityContext` sets `runAsNonRoot: true`, and the image's default user is root. The container fails to start, and its events say it would run as root. A teammate adds `runAsUser: 0` to the container `securityContext`, reasoning that the container level overrides the Pod level. Which outcome and fix are correct?

A) The container is still refused, because the guard rejects UID 0; set a non-zero numeric `runAsUser` such as `1000`, then verify with `id`.
B) The container starts as an unprivileged user, because `runAsNonRoot` remaps UID 0 to a safe account when the process launches.
C) The container starts as root, because a container-level `runAsUser` replaces every field of the Pod-level `securityContext`.
D) The container starts once `privileged: true` is added, because privileged mode satisfies the non-root requirement for root images.

<details>
<summary>Answer and reasoning</summary>

**Correct: A.** `runAsNonRoot` asserts that the container must not run as UID 0 and never chooses a UID. The container inherits that guard from the Pod, and an explicit `runAsUser: 0` directly conflicts with it, so the start still fails. A non-zero numeric `runAsUser` satisfies the guard, and running `id` through `kubectl exec` proves the effective UID. B) is wrong because no remapping happens. C) is wrong because a container field overrides only the same field, so the inherited guard remains. D) is wrong because privileged mode broadens host access and does not change the UID.

</details>

### Question 7: The Pod that never calls the API

Deployment `status-page` serves static pages and never calls the Kubernetes API. Its Pod template has no `serviceAccountName`, and `kubectl describe sa default` shows `Tokens: <none>`. Neither the Pod template nor the `default` ServiceAccount sets `automountServiceAccountToken: false`. A security review asks whether the running Pods hold an API credential. Which answer is accurate?

A) No. An empty `serviceAccountName` means admission creates the Pod without any identity, so the kubelet has nothing to mount.
B) Yes. Admission assigns the namespace `default` ServiceAccount and a token is projected; set `automountServiceAccountToken: false` in the template.
C) No. Since Kubernetes 1.24, ServiceAccounts have no tokens at all, which is exactly what `Tokens: <none>` confirms here.
D) Yes. The fix is a RoleBinding that grants the `default` ServiceAccount zero verbs, which removes the token from the filesystem.

<details>
<summary>Answer and reasoning</summary>

**Correct: B.** When the field is empty, admission writes `default`, and because neither the Pod nor the ServiceAccount disables automounting, the kubelet projects a token under `/var/run/secrets/kubernetes.io/serviceaccount/`. Setting `automountServiceAccountToken: false` in the Pod template removes the credential from new Pods. A) is wrong because an empty field still yields an identity. C) is wrong because Kubernetes 1.24 stopped auto-creating long-lived token Secrets, not projected tokens. D) is wrong because RBAC controls what a token may do and does not remove the token file.

</details>

### Question 8: A custom resource that does nothing

A platform team installed CRD `backups.example.com` with kind `Backup`. A developer applies a `Backup` named `nightly`, and `kubectl get backups -n reports` lists it, yet no Job or PersistentVolumeClaim appears. A teammate proposes deleting the CRD and reapplying it to reset the resource type. Which response is best?

A) Reapply the CRD, because a CRD creates the Jobs for each custom resource when its API endpoint first becomes established.
B) Read the controller logs for a schema error first, because CRD schema validation runs inside the controller after storage.
C) Check the resource's status, events, and whether a controller is running; do not delete the CRD, which can delete every `Backup`.
D) Add a second version with `served: true`, because a controller notices only custom resources written through a newly served version.

<details>
<summary>Answer and reasoning</summary>

**Correct: C.** A CRD registers the API, and a controller, if one exists, reconciles `Backup` objects into Jobs, claims, and status. Creating the custom resource only stored intent, so the evidence to gather is its status, its events, and the controller's Pods and permissions. A) is wrong because a CRD provisions nothing by itself. B) is wrong because the API server applies schema validation before storing the object, and this object was accepted. D) is wrong because served versions control which `apiVersion` values the API accepts, not whether a controller exists. Deleting the CRD can remove every custom resource it served.

</details>

## Hands-On Exercise

Simulation: in a disposable practice cluster where you may create namespaces and a CRD, build the combined Pod from Core Content, verify each Part 4 setting from inside and outside the container, break one ConfigMap mount on purpose, watch a live ConfigMap update reach only one consumer, and register a custom resource type with no controller. The expected results below describe what the commands should show; they are not recorded output, and exact event wording, ages, and timing depend on your cluster.

First create the namespace and the objects the Pod references. The Secret value is a disposable lab string, and the ServiceAccount exists only to give the Pod a named identity. Because `serviceAccountName` must resolve in the Pod's namespace at admission, create these objects before you apply the Pod, or the API server will reject it.

```bash
kubectl create namespace part4-drill
kubectl create configmap app-config -n part4-drill \
  --from-literal=LOG_LEVEL=info \
  --from-literal=app.properties='mode=review'
kubectl create secret generic app-secret -n part4-drill \
  --from-literal=password='example-password'
kubectl create serviceaccount app-runner -n part4-drill
```

Next save the Core Content manifest as `part4-app.yaml`, apply it, and wait for readiness. Then check identity, configuration, the Secret filename, the writable paths, the absent token, the QoS class, and the assigned ServiceAccount. Two commands are expected to fail: the `touch` on `/` should report a read-only file system, and the listing of the token directory should report that the path does not exist. Those failures are the evidence that the security settings work.

```bash
kubectl apply -f part4-app.yaml
kubectl wait --for=condition=Ready pod/part4-app -n part4-drill --timeout=120s
kubectl exec -n part4-drill part4-app -- id
kubectl exec -n part4-drill part4-app -- sh -c 'echo "LOG_LEVEL=$LOG_LEVEL"'
kubectl exec -n part4-drill part4-app -- ls /etc/app /etc/app-secret
kubectl exec -n part4-drill part4-app -- touch /probe
kubectl exec -n part4-drill part4-app -- touch /tmp/probe
kubectl exec -n part4-drill part4-app -- ls /var/run/secrets/kubernetes.io/serviceaccount
kubectl get pod part4-app -n part4-drill -o jsonpath='{.status.qosClass}{"\n"}'
kubectl get pod part4-app -n part4-drill -o jsonpath='{.spec.serviceAccountName}{"\n"}'
```

Expected results: `id` reports UID `1000`, primary group `3000`, and a group list that includes `2000`. The variable prints `LOG_LEVEL=info`. The ConfigMap directory lists `LOG_LEVEL` and `app.properties`, and the Secret directory lists `db-password` rather than `password`, because `items` remapped the key. The QoS class should be `Burstable`, and the ServiceAccount should be `app-runner`. If the Pod never becomes Ready, run `kubectl describe pod part4-app -n part4-drill` and match its events to the stage table in Core Content.

Now break one mount on purpose. The Pod below asks for a ConfigMap key that `app-config` does not contain, and its reference is not optional. Apply it, then inspect its status and events. Compare what you see with the first pause-and-predict prompt, because this Pod is the `items` case from that prediction.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: part4-broken
  namespace: part4-drill
spec:
  containers:
  - name: app
    image: busybox:1.36
    command: ["sh", "-c", "sleep 3600"]
    volumeMounts:
    - name: config
      mountPath: /etc/app
  volumes:
  - name: config
    configMap:
      name: app-config
      items:
      - key: missing.conf
        path: app.conf
EOF
kubectl get pod part4-broken -n part4-drill
kubectl describe pod part4-broken -n part4-drill
kubectl delete pod part4-broken -n part4-drill
```

Expected result: `part4-broken` stays in `ContainerCreating`, and a mount event names `missing.conf` as the absent key. Do not fix it by adding `optional: true`, because that would start a container without the file it asked for. The last command deletes the Pod after you have read the event, since it will not recover until its reference or the ConfigMap changes.

Next change the ConfigMap in place and compare the two consumers inside `part4-app`. The generated manifest is piped back through `kubectl apply`, which may print a warning about a missing last-applied annotation because the object was created imperatively; the update still applies. Wait about a minute for the kubelet sync, then check both the environment and the mounted file in one command.

```bash
kubectl create configmap app-config -n part4-drill \
  --from-literal=LOG_LEVEL=debug \
  --from-literal=app.properties='mode=review' \
  --dry-run=client -o yaml | kubectl apply -n part4-drill -f -
kubectl exec -n part4-drill part4-app -- sh -c 'echo "env=$LOG_LEVEL file=$(cat /etc/app/LOG_LEVEL)"'
```

Expected result after the sync: the file shows `debug` while the environment still shows `info`. Repeat the last command if the file has not changed yet, because projection timing depends on the kubelet. The variable changes only when a new container starts, which is why a Deployment would need a rollout after the same edit.

Finally, register a custom resource type that has no controller. Creating a CRD requires cluster-wide permission, so do this only in your own practice cluster. The wait command prevents the first custom resource from racing the new endpoint before the API server is ready to serve it.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: drills.example.com
spec:
  group: example.com
  scope: Namespaced
  names:
    plural: drills
    singular: drill
    kind: Drill
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              target:
                type: string
EOF
kubectl wait --for condition=established --timeout=60s crd/drills.example.com
cat << 'EOF' | kubectl apply -f -
apiVersion: example.com/v1
kind: Drill
metadata:
  name: nightly
  namespace: part4-drill
spec:
  target: part4-app
EOF
kubectl get drills -n part4-drill
kubectl api-resources | grep example.com
kubectl get pods -n part4-drill
```

Expected result: `kubectl get drills` lists `nightly`, and `kubectl api-resources` shows the `drills` resource in the `example.com` group as namespaced. The Pod list still shows only `part4-app`, because no controller watches `Drill` objects. The API server stored your intent and did nothing else, which is exactly the boundary between registration and reconciliation.

**Success Criteria**: Check each box only after you have observed the result in your own practice cluster, including the two commands that are expected to fail and the delayed ConfigMap update.
- [ ] `kubectl exec -n part4-drill part4-app -- id` reports UID `1000`, the stored Pod shows `Burstable` QoS, and its ServiceAccount is `app-runner`.
- [ ] The container shows `LOG_LEVEL=info` in its environment, lists both ConfigMap keys under `/etc/app`, and lists the Secret key as `db-password`.
- [ ] A write under `/` fails on the read-only root filesystem, a write under `/tmp` succeeds, and the ServiceAccount token directory does not exist.
- [ ] `part4-broken` stays in `ContainerCreating`, and its events name the missing ConfigMap key `missing.conf`.
- [ ] After the ConfigMap edit, the mounted file shows `debug` while the environment variable still shows `info`.
- [ ] The `Drill` custom resource is stored while no controller creates anything for it, and you delete it before deleting its CRD.

Clean up in the safe order. Delete the custom resource first, then the CRD, then the namespace, which removes the Pod, ConfigMap, Secret, and ServiceAccount together. Check your cluster context before running these commands anywhere shared, because the CRD is cluster-scoped and deleting it would remove every `Drill` object in every namespace.

```bash
kubectl delete drill nightly -n part4-drill
kubectl delete crd drills.example.com
kubectl delete namespace part4-drill
```

## Sources

- [Kubernetes: ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Kubernetes: Configure a Pod to use a ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/)
- [Kubernetes: Volumes, using subPath](https://kubernetes.io/docs/concepts/storage/volumes/#using-subpath)
- [Kubernetes: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes: Managing Secrets using kubectl](https://kubernetes.io/docs/tasks/configmap-secret/managing-secret-using-kubectl/)
- [Kubernetes: Encrypting Secret data at rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
- [Kubernetes: Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Kubernetes: Pod Quality of Service Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)
- [Kubernetes: Limit Ranges](https://kubernetes.io/docs/concepts/policy/limit-range/)
- [Kubernetes: Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [Kubernetes: Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Kubernetes: Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes: Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/)
- [Kubernetes: Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)
- [Kubernetes: Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Kubernetes: Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)
- [Kubernetes: Extend the Kubernetes API with CustomResourceDefinitions](https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/)
- [Kubernetes: Controllers](https://kubernetes.io/docs/concepts/architecture/controller/)

## Next Module

Continue to [Module 5.1: Services](../../part5-networking/module-5.1-services/) to move from configuring what runs inside a Pod to giving those Pods a stable network endpoint that other workloads in the cluster can reach.
