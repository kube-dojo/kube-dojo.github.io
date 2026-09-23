---
citations_verified: true
title: "Module 2.7: ConfigMaps & Secrets"
slug: k8s/cka/part2-workloads-scheduling/module-2.7-configmaps-secrets
revision_pending: false
sidebar:
  order: 8
lab:
  id: cka-2.7-configmaps-secrets
  url: https://killercoda.com/kubedojo/scenario/cka-2.7-configmaps-secrets
  duration: "45 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 55 minutes
>
> **Prerequisites**: Complete [Module 2.1: Pods Deep-Dive](../module-2.1-pods/) and [Module 2.2: Deployments](../module-2.2-deployments/) before starting, because this module assumes you can read Pod specs and understand why restarting a Pod changes runtime state. You should also have a running Kubernetes 1.35+ cluster, such as kind or minikube, and a working shell where `kubectl` is available.
>
> **CKA Weight**: Workloads & Scheduling

---

## Learning Outcomes

After this module, you will be able to:

- **Design** a configuration injection strategy that separates container images from environment-specific settings while choosing correctly between ConfigMaps and Secrets.
- **Implement** ConfigMaps and Secrets from literals, files, env files, and manifests, then mount selected keys as environment variables or files.
- **Compare** environment-variable injection, full volume mounts, projected volumes, and `subPath` mounts using update behavior, security exposure, and application expectations.
- **Debug** Pods that fail or behave incorrectly because of missing keys, wrong mount paths, stale values, invalid Secret encoding, or restrictive file permissions.
- **Evaluate** when immutable configuration objects, versioned names, RBAC restrictions, and external secret stores are appropriate in production systems.

## Why This Module Matters

Hypothetical scenario: a release engineer ships a new web service on Friday afternoon. The image works in staging, the readiness probe passes, and the Deployment rolls out cleanly. Ten minutes later, production traffic starts failing because the container image still points to the staging database host. The image was rebuilt correctly, but the wrong setting was baked into it, so the team must rebuild, retag, rescan, and redeploy just to change one string.

Another team avoids that mistake by [moving the database host into a ConfigMap and the password into a Secret](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/). Their rollout is faster, but a later incident reveals a different failure mode: the password was injected as an environment variable, a debug endpoint dumped the process environment, and a credential that should have stayed private appeared in logs. The primitive was correct, but the injection method was not matched to the risk.

ConfigMaps and Secrets are simple API objects, but they sit on a critical boundary between application design, cluster administration, and security practice. On the CKA exam, you must create them quickly and wire them into Pods without breaking the workload. In production, you must also understand the update mechanics, file paths, encoding rules, RBAC exposure, and restart behavior well enough to choose a design that remains safe after the first successful `kubectl apply`.

The deeper lesson is that configuration has a lifecycle of its own. A value is authored by a person or automation, stored in the Kubernetes API, delivered by kubelet to a specific Pod, read by a process, and eventually rotated or removed. Each step can fail in a different way. A typo in the object name fails before the container starts, a wrong key may surface as `CreateContainerConfigError`, a stale environment variable can survive a correct ConfigMap patch, and an extra newline in a Secret may not become obvious until the application authenticates.

This module therefore treats ConfigMaps and Secrets as runtime contracts, not just YAML snippets. You will create the objects, inspect their stored representation, attach them to containers through several injection methods, and reason about what happens after the object changes. That reasoning matters because the same manifest can look correct in code review and still be wrong for the application. A senior operator traces the path from key to runtime view and asks whether the process can actually observe the value at the time it needs it.

Keep one mental model in mind throughout the module: Kubernetes can deliver configuration, but it cannot make an application reread configuration that the application has already cached. [Environment variables are copied into the process at startup, mounted files can change on disk, and `subPath` mounts intentionally behave like fixed file replacements.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/) Those mechanics turn simple-looking choices into operational trade-offs. The fastest exam answer is often the shortest command, but the most reliable production answer is the one with an explicit reload, restart, rollback, and verification story that another engineer can follow during an incident without guessing at hidden state.

## Core Content

### 1. Configuration Is Runtime Input, Not Image Content

A container image should describe what the application is, while configuration should describe how that application behaves in a specific environment. If the same image can run in development, staging, and production by changing only Kubernetes objects, deployments become faster and less risky. When an image contains database hosts, feature flags, or certificates, every configuration change becomes a supply-chain change, which increases operational cost and makes rollback harder than it needs to be.

Kubernetes gives you two first-class objects for this separation. [A ConfigMap stores non-sensitive configuration, such as log levels, endpoint names, feature flags, and application config files. A Secret stores sensitive configuration, such as passwords, bearer tokens, SSH keys, TLS private keys, and registry credentials.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/) The objects look similar because both are key-value maps, but they carry different security expectations and should be handled differently by people, automation, and applications.

The first design question is not "what command creates this object?" The first question is "how does the application need to consume this data?" Some applications read environment variables at process startup and never look again. Others watch files for changes or reload configuration when a file changes. Some expect a whole directory of files, while others expect one exact file path. Your Kubernetes design should fit that application behavior instead of forcing the application into a convenient manifest shape.

```ascii
+----------------------+        +----------------------+        +----------------------+
| Container Image      |        | Kubernetes Object    |        | Runtime View in Pod  |
|----------------------|        |----------------------|        |----------------------|
| app binary           |        | ConfigMap            |        | env vars or files    |
| libraries            |        | Secret               |        | env vars or files    |
| default config       |        | projected volume     |        | merged file tree     |
+----------------------+        +----------------------+        +----------------------+
          |                              |                              |
          | same image across envs       | environment-specific data     | values injected at start
          +------------------------------+------------------------------+
```

A useful rule is to classify each value by both sensitivity and reload behavior. A log level may be non-sensitive and safe as an environment variable if the application only reads it during startup. A TLS key is sensitive and usually safer as a read-only mounted file with restrictive permissions. A routing table that changes during an incident may need a full volume mount because environment variables will not update inside an already-running process.

> **Active learning prompt:** Your team wants to store `PAYMENTS_API_URL`, `FEATURE_CHECKOUT_V2`, and `PAYMENTS_API_TOKEN`. Which of these belong in a ConfigMap, which belong in a Secret, and which injection method would you choose if the application reads only environment variables during startup?

The CKA exam rewards speed, so you will often create objects imperatively and patch YAML generated with `--dry-run=client -o yaml`. Real clusters reward clarity, so production teams usually manage these objects through GitOps, Helm, Kustomize, External Secrets, or another controlled workflow. The underlying Kubernetes mechanics are the same in both contexts, which is why learning the primitive deeply pays off beyond exam muscle memory.

### 2. Creating ConfigMaps From Literals, Files, Directories, And Env Files

A ConfigMap stores string data under keys. A key can represent a simple value like `LOG_LEVEL`, or it can represent an entire file like `nginx.conf`. This distinction matters because Kubernetes does not inspect file contents and automatically split them into application settings unless you ask it to do so with the right creation mode.

The simplest exam-friendly creation method is `--from-literal`. Use it when each value is already known and short enough to type safely. Because every `--from-literal` flag becomes one key, this method maps naturally to environment variables and small configuration maps.

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=CACHE_TTL_SECONDS=300 \
  --from-literal=FEATURE_CHECKOUT_V2=true
```

You can inspect the resulting object with `kubectl get` or `kubectl describe`. The YAML representation is worth reading because it shows exactly what a Pod can reference later. A Pod cannot reference "the third literal" or "the cache setting" as an idea; it references a specific object name and a specific key.

```bash
kubectl get configmap app-config -o yaml
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  CACHE_TTL_SECONDS: "300"
  FEATURE_CHECKOUT_V2: "true"
  LOG_LEVEL: info
```

Use `--from-file` when the application expects a file, such as an NGINX server block, a Java properties file, or an application YAML file. With plain `--from-file=config.properties`, the key becomes the filename and the value becomes the complete file content. Kubernetes does not split the file into multiple keys just because the file happens to contain `key=value` lines.

```bash
cat > config.properties <<'EOF'
database.host=orders-db.default.svc.cluster.local
database.port=5432
cache.enabled=true
EOF

kubectl create configmap app-file-config --from-file=config.properties
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-file-config
data:
  config.properties: |
    database.host=orders-db.default.svc.cluster.local
    database.port=5432
    cache.enabled=true
```

If the filename in the container must differ from the local filename, provide a custom key. This is common when a generated file has a temporary name on your workstation but the application expects a stable path inside the container. The key you choose becomes the filename when the ConfigMap is mounted as a volume unless you remap it again with `items`.

```bash
kubectl create configmap app-file-config-v2 \
  --from-file=application.properties=config.properties
```

[Use `--from-env-file` when each line should become a separate key-value pair.](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_configmap/) This is a frequent exam trap because env files and config files can look similar to a human. [To Kubernetes, `--from-file` means "store this entire file under one key," while `--from-env-file` means "parse each valid line into its own key."](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_configmap/)

```bash
cat > app.env <<'EOF'
LOG_LEVEL=debug
CACHE_TTL_SECONDS=120
FEATURE_CHECKOUT_V2=false
EOF

kubectl create configmap app-env-config --from-env-file=app.env
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-env-config
data:
  CACHE_TTL_SECONDS: "120"
  FEATURE_CHECKOUT_V2: "false"
  LOG_LEVEL: debug
```

| Creation Method | Best Use | Resulting Keys | Common Exam Risk |
|---|---|---|---|
| `--from-literal` | A few known values | One key per flag | Typing the wrong key name |
| `--from-file=file` | Application needs the whole file | Filename becomes one key | Expecting lines to split automatically |
| `--from-file=key=file` | Application needs a specific filename | Custom key becomes filename | Forgetting the custom key later |
| `--from-file=directory/` | Several files become one ConfigMap | One key per file | Hidden files and invalid names are skipped |
| `--from-env-file=file` | Each line should become an env-style key | One key per parsed line | Using it for multi-line config files |

A directory import is useful when an application expects several configuration files in the same mounted directory. Kubernetes creates one key for each regular file in the directory. This is convenient, but it also means the directory contents become part of the API object, so avoid using it casually from a directory that includes local editor files, backups, or secrets that should not be in a ConfigMap.

```bash
mkdir -p config-dir

cat > config-dir/app.yaml <<'EOF'
server:
  port: 8080
logging:
  level: info
EOF

cat > config-dir/routes.yaml <<'EOF'
routes:
  - path: /health
    upstream: local
EOF

kubectl create configmap app-directory-config --from-file=config-dir/
```

A ConfigMap can also be written as a manifest, which is often clearer for reviewed changes. In a manifest, the `data` field contains text values and the optional `binaryData` field contains base64-encoded binary values. For CKA tasks, imperative creation is usually faster, but knowing the manifest shape helps you debug generated YAML and work with real repositories.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orders-config
data:
  LOG_LEVEL: "info"
  application.yaml: |
    database:
      host: orders-db.default.svc.cluster.local
      port: 5432
    features:
      checkoutV2: true
```

> **Active learning prompt:** You created a ConfigMap from `app.properties` with `--from-file`, then used `envFrom` in a Pod and expected `database.host` to appear as an environment variable. Predict what variable, if any, appears in the container, then decide which creation method you should have used.

### 3. Injecting ConfigMaps: Environment Variables, Files, And Key Path Mapping

Once the ConfigMap exists, the Pod spec decides how the container sees it. The two most common choices are environment variables and volume-mounted files. Environment variables are simple and familiar, but they are fixed when the container process starts. [Volume mounts are better for file-oriented applications and can receive updates automatically, as long as you avoid `subPath`.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/)

Use `env.valueFrom.configMapKeyRef` when you want one key mapped to one environment variable with a container-specific name. This pattern is precise and readable. It also lets you mark an individual key optional, which can be useful during staged rollouts but should be used carefully because optional missing config can hide a deployment mistake.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-env-single
spec:
  containers:
  - name: app
    image: nginx:1.27
    env:
    - name: APP_LOG_LEVEL
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: LOG_LEVEL
    - name: APP_CACHE_TTL_SECONDS
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: CACHE_TTL_SECONDS
```

[Use `envFrom` when every valid key in the ConfigMap should become an environment variable.](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/) This is fast for exam tasks and clean for simple applications, but it can be too broad in production because every key becomes part of the process environment. A prefix reduces naming collisions and makes it clearer that the value came from Kubernetes configuration.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-env-all
spec:
  containers:
  - name: app
    image: nginx:1.27
    envFrom:
    - configMapRef:
        name: app-config
      prefix: APP_
```

[When a ConfigMap is mounted as a volume, each key becomes a file.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/) This is the core mental model that prevents most mount-path mistakes. If the ConfigMap has keys `application.yaml` and `routes.yaml`, and the volume is mounted at `/etc/app`, the container sees `/etc/app/application.yaml` and `/etc/app/routes.yaml`.

```ascii
+-----------------------------+          +--------------------------------+
| ConfigMap: orders-config    |          | Container filesystem           |
|-----------------------------|          |--------------------------------|
| data.LOG_LEVEL              |   env    | APP_LOG_LEVEL=info             |
| data.application.yaml       |  file    | /etc/app/application.yaml      |
| data.routes.yaml            |  file    | /etc/app/routes.yaml           |
+-----------------------------+          +--------------------------------+
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-config-volume
spec:
  containers:
  - name: app
    image: nginx:1.27
    volumeMounts:
    - name: app-config-volume
      mountPath: /etc/app
  volumes:
  - name: app-config-volume
    configMap:
      name: orders-config
```

The following diagram is the most important path-mapping model in this module. [The key name is not just metadata; for volume mounts it becomes a filename unless the Pod remaps it.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/) The `mountPath` is the directory where the volume appears, and the file path inside the container is the directory plus the mapped key path.

```ascii
+-----------------------------------+      +--------------------------------------+
| ConfigMap key map                 |      | Mounted volume at /etc/app           |
|-----------------------------------|      |--------------------------------------|
| application.yaml                  | ---> | /etc/app/application.yaml             |
| routes.yaml                       | ---> | /etc/app/routes.yaml                  |
| feature-flags.json                | ---> | /etc/app/feature-flags.json           |
+-----------------------------------+      +--------------------------------------+
```

Sometimes you only want selected keys, or you want the file path inside the mounted directory to be different from the key name. Use `items` for that mapping. This is safer than changing the ConfigMap key just to match one application's preferred filename, because several Pods can reuse the same ConfigMap with different path mappings.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-config-items
spec:
  containers:
  - name: app
    image: nginx:1.27
    volumeMounts:
    - name: app-config-volume
      mountPath: /etc/app
  volumes:
  - name: app-config-volume
    configMap:
      name: orders-config
      items:
      - key: application.yaml
        path: config/application.yaml
      - key: routes.yaml
        path: routes.yaml
```

```ascii
+-----------------------------+          +--------------------------------+
| ConfigMap: orders-config    |          | mountPath: /etc/app            |
|-----------------------------|          |--------------------------------|
| application.yaml            |  items   | /etc/app/config/application.yaml|
| routes.yaml                 |  items   | /etc/app/routes.yaml            |
| LOG_LEVEL                   | skipped  | no file created                 |
+-----------------------------+          +--------------------------------+
```

A `subPath` mount is different. It mounts one file from the volume onto one exact path in the container. This is useful when an image already contains a directory such as `/etc/nginx/conf.d`, and you only want to replace `/etc/nginx/conf.d/default.conf` without hiding the rest of the directory. The trade-off is major: ConfigMap and Secret updates do not propagate through `subPath` mounts.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-subpath-config
spec:
  containers:
  - name: nginx
    image: nginx:1.27
    volumeMounts:
    - name: nginx-config
      mountPath: /etc/nginx/conf.d/default.conf
      subPath: nginx.conf
  volumes:
  - name: nginx-config
    configMap:
      name: nginx-config
      items:
      - key: nginx.conf
        path: nginx.conf
```

```ascii
+---------------------------+          +-----------------------------------------+
| ConfigMap key             |          | subPath mount result                    |
|---------------------------|          |-----------------------------------------|
| nginx.conf                | -------> | /etc/nginx/conf.d/default.conf          |
|                           |          | single file mount, not auto-refreshed   |
+---------------------------+          +-----------------------------------------+
```

| Injection Pattern | Container View | Updates In Running Pod | Best Fit | Main Risk |
|---|---|---|---|---|
| `env` with one key | One named environment variable | No | Precise startup settings | Missing key blocks container unless optional |
| `envFrom` | Many environment variables | No | Small apps with env-based config | Too broad and collision-prone |
| Full volume mount | Directory of files | Yes, after kubelet sync delay | File-based config and reloadable apps | Mount hides existing directory contents |
| Volume with `items` | Selected files and paths | Yes, unless mounted by `subPath` | Curated file tree | Wrong key or path causes missing file |
| `subPath` file mount | One exact file path | No | Replacing one file inside existing directory | Stale config after object update |

> **Active learning prompt:** An NGINX image already contains several files in `/etc/nginx/conf.d/`, and you want to replace only `default.conf`. Which mount style avoids hiding the existing directory, and what operational cost do you accept when you choose it?

ConfigMap update behavior deserves special attention because it surprises both beginners and experienced engineers moving quickly. [A running process receives environment variables only when the process starts, so changing the ConfigMap will not rewrite the process environment. A full ConfigMap volume mount can update the files inside the container after kubelet syncs the new object, but the application must either reread the file or be reloaded. A `subPath` file mount stays stale until the Pod is restarted.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/)

### 4. Creating And Using Secrets Without Confusing Encoding With Security

A Secret is a Kubernetes object for sensitive data, but the default representation is not magic encryption. [Values in the `data` field are base64 encoded because Kubernetes API objects are JSON-compatible and need a safe text representation for arbitrary bytes.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/) Base64 protects formatting, not confidentiality. Anyone who can read the Secret through the API can decode it.

For exam speed, `kubectl create secret generic` is usually the safest way to avoid manual encoding mistakes. [The command accepts plain text literals or files and stores the encoded form in the API object. Quote shell-sensitive values, especially passwords containing `!`, `$`, `\`, spaces, or other characters the shell may interpret.](https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/)

```bash
kubectl create secret generic db-creds \
  --from-literal=username=orders_user \
  --from-literal=password='example-db-password'
```

Inspecting the Secret shows encoded values. [This is expected, and it does not prove the value is encrypted.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/) It only proves the API object stores the value in the `data` map. Use JSONPath and `base64 -d` when debugging a lab value, but avoid printing real production secrets into terminal scrollback, shell history, logs, or screen shares.

```bash
kubectl get secret db-creds -o jsonpath='{.data.password}' | base64 -d
```

When writing a Secret manifest by hand, use `stringData` unless you have a specific reason to provide already encoded data. [The `stringData` field accepts plain text and Kubernetes converts it into `data` when the object is stored.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/) This reduces the chance of accidentally encoding a trailing newline or double-encoding a value.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-creds
type: Opaque
stringData:
  username: orders_user
  password: example-db-password
```

If you use the `data` field, values must already be base64 encoded. Use `echo -n` rather than `echo`, because a trailing newline becomes part of the Secret value. This invisible character is a classic cause of authentication failures: humans see the same password, but the database receives an extra newline byte.

```bash
echo -n 'example-db-password' | base64
```

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-creds-encoded
type: Opaque
data:
  username: b3JkZXJzX3VzZXI=
  password: ZXhhbXBsZS1kYi1wYXNzd29yZA==
```

[Kubernetes defines several Secret types. The type does not make the value more secret, but it can add validation or signal intended use to controllers. For example, `kubernetes.io/tls` expects `tls.crt` and `tls.key`, while `kubernetes.io/dockerconfigjson` stores registry pull credentials in a specific JSON key.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/)

| Secret Type | Typical Keys | Primary Use | Validation Benefit |
|---|---|---|---|
| `Opaque` | Any keys | Generic app credentials | Minimal validation |
| [`kubernetes.io/tls`](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/) | `tls.crt`, `tls.key` | TLS certificate and private key | Checks required keys exist |
| `kubernetes.io/dockerconfigjson` | `.dockerconfigjson` | Private image registry auth | Checks expected key shape |
| `kubernetes.io/basic-auth` | `username`, `password` | Basic authentication | Documents intent clearly |
| `kubernetes.io/ssh-auth` | `ssh-privatekey` | SSH private key material | Documents intent clearly |
| `bootstrap.kubernetes.io/token` | Bootstrap token fields | Node bootstrap flows | Specialized cluster use |

Mounting Secrets follows the same environment-variable and volume patterns as ConfigMaps, but the security trade-offs are sharper. A Secret injected as an environment variable becomes part of the container process environment; if the application can read credentials from files, a read-only Secret volume is usually the safer default. A Secret mounted as a file still requires API access to create the Pod, but inside the container the application must intentionally read the file path.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-secret-env
spec:
  containers:
  - name: app
    image: nginx:1.27
    env:
    - name: DATABASE_USERNAME
      valueFrom:
        secretKeyRef:
          name: db-creds
          key: username
    - name: DATABASE_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-creds
          key: password
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-secret-volume
spec:
  containers:
  - name: app
    image: nginx:1.27
    volumeMounts:
    - name: db-creds-volume
      mountPath: /etc/db-creds
      readOnly: true
  volumes:
  - name: db-creds-volume
    secret:
      secretName: db-creds
      defaultMode: 0400
```

```ascii
+-----------------------------+          +--------------------------------+
| Secret: db-creds            |          | mountPath: /etc/db-creds       |
|-----------------------------|          |--------------------------------|
| username                    | -------> | /etc/db-creds/username         |
| password                    | -------> | /etc/db-creds/password         |
| defaultMode: 0400           | -------> | read permission only           |
+-----------------------------+          +--------------------------------+
```

For TLS, a Secret volume maps naturally to certificate files. The application or proxy still needs to reload the certificate after the file changes, so a successful volume update is only half of the rotation story. NGINX, Envoy, Java applications, and Go servers differ in how they reload certificates, which means the Kubernetes mount pattern and the application reload strategy must be designed together.

```bash
kubectl create secret tls web-tls \
  --cert=tls.crt \
  --key=tls.key
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: tls-nginx
spec:
  containers:
  - name: nginx
    image: nginx:1.27
    volumeMounts:
    - name: tls-certs
      mountPath: /etc/nginx/tls
      readOnly: true
  volumes:
  - name: tls-certs
    secret:
      secretName: web-tls
      defaultMode: 0400
```

| Secret Injection Choice | Exposure Inside Container | Update Behavior | When To Prefer It |
|---|---|---|---|
| Environment variable | Visible through process environment | Requires container restart | Legacy apps that only read env vars |
| Full volume mount | File read required | Files can update after sync | Credentials, certificates, tokens |
| `subPath` file mount | File read required | Does not update automatically | Exact file replacement only |
| Image pull Secret | Used by kubelet, not app process | Applied when pulling image | Private registry authentication |

> **Active learning prompt:** A security reviewer says your database password must not appear in `kubectl exec pod -- env`. Your application can read either an env var or a file. Which Secret injection method satisfies the reviewer, and what `volumeMount` and `secret` settings make the design stronger?

### 5. Update, Immutability, Projection, And Troubleshooting

ConfigMaps and Secrets are API objects, so you can change them after creation unless they are immutable. The harder question is whether a running workload notices the change. Kubernetes can update mounted volume files after kubelet observes the object change, but it cannot rewrite a process environment. Even when a file changes, the application may keep old values in memory until it reloads.

```bash
kubectl patch configmap app-config \
  --type merge \
  -p '{"data":{"LOG_LEVEL":"debug"}}'
```

After this patch, a Pod using `APP_LOG_LEVEL` from `envFrom` still has the old value until the container restarts. A Pod using a full ConfigMap volume may see the file contents update after a short kubelet sync delay. [A Pod using `subPath` remains stale until it is restarted, because `subPath` mounts do not receive ConfigMap or Secret updates.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/)

```ascii
+----------------------+        +----------------------+        +----------------------+
| ConfigMap update     |        | Injection method     |        | Running Pod outcome  |
|----------------------|        |----------------------|        |----------------------|
| LOG_LEVEL=debug      | -----> | env / envFrom        | -----> | old value until restart |
| app.yaml changed     | -----> | full volume mount    | -----> | file refresh after sync |
| nginx.conf changed   | -----> | subPath file mount   | -----> | stale until restart     |
+----------------------+        +----------------------+        +----------------------+
```

Immutability changes the operational model. [When you set `immutable: true`, Kubernetes rejects later updates to the object data. That sounds restrictive, but it can be desirable for production because it prevents accidental mutation and reduces watch load from kubelets.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/) The normal pattern is to create a new object name, such as `app-config-v2`, and update the Deployment template so Kubernetes performs a controlled rollout.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-v1
immutable: true
data:
  LOG_LEVEL: info
  CACHE_TTL_SECONDS: "300"
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orders-api
  template:
    metadata:
      labels:
        app: orders-api
    spec:
      containers:
      - name: orders-api
        image: nginx:1.27
        envFrom:
        - configMapRef:
            name: app-config-v2
```

Projected volumes let you merge multiple sources into one directory. This is useful when an application expects all configuration under one path, but your cluster design separates non-sensitive config, sensitive credentials, and Pod metadata into different Kubernetes sources. [A projected volume can include ConfigMaps, Secrets, the Downward API, and service account tokens.](https://kubernetes.io/docs/concepts/storage/projected-volumes/)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: projected-config-demo
spec:
  containers:
  - name: app
    image: nginx:1.27
    volumeMounts:
    - name: combined-config
      mountPath: /etc/runtime
      readOnly: true
  volumes:
  - name: combined-config
    projected:
      sources:
      - configMap:
          name: app-config
          items:
          - key: LOG_LEVEL
            path: config/log-level
      - secret:
          name: db-creds
          items:
          - key: password
            path: secrets/db-password
      - downwardAPI:
          items:
          - path: pod/name
            fieldRef:
              fieldPath: metadata.name
```

```ascii
+--------------------+       +----------------------------------+
| Projected sources  |       | /etc/runtime inside container    |
|--------------------|       |----------------------------------|
| ConfigMap LOG_LEVEL| ----> | /etc/runtime/config/log-level    |
| Secret password    | ----> | /etc/runtime/secrets/db-password |
| Downward API name  | ----> | /etc/runtime/pod/name            |
+--------------------+       +----------------------------------+
```

Troubleshooting configuration failures starts with the Pod status and events. [A missing ConfigMap, missing Secret, or missing required key can prevent the container from starting and usually surfaces in Pod events.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/) A wrong path may let the container start but cause the application to fail later. A bad Secret value may look like an application authentication bug until you decode the actual bytes.

```bash
kubectl get pod broken-app

kubectl describe pod broken-app

kubectl get events --sort-by=.lastTimestamp
```

For missing objects, the `Events` section usually names the exact reference Kubernetes could not resolve. For wrong keys, compare the Pod spec against the object data. For wrong file paths, `kubectl exec` into the container and inspect the directory structure. The goal is to trace the value from object key to injection rule to runtime location.

```bash
kubectl get configmap app-config -o yaml

kubectl get pod app-config-volume -o yaml

kubectl exec app-config-volume -- ls -la /etc/app

kubectl exec app-config-volume -- cat /etc/app/application.yaml
```

For Secret encoding issues, decode the value and reveal hidden characters. `cat -e` makes a trailing newline visible as `$`, and `xxd` shows the byte-level representation. Use these techniques in labs and controlled debugging, not casually against production credentials.

```bash
kubectl get secret db-creds -o jsonpath='{.data.password}' | base64 -d | cat -e

kubectl get secret db-creds -o jsonpath='{.data.password}' | base64 -d | xxd
```

| Symptom | Likely Cause | First Check | Usual Fix |
|---|---|---|---|
| `CreateContainerConfigError` | Missing ConfigMap, Secret, or key | `kubectl describe pod` events | Create object or correct reference |
| Env var has old value | ConfigMap or Secret changed after start | `kubectl exec pod -- env` | Restart Pod or roll Deployment |
| Mounted file has old value | Using `subPath` or app cached value | Pod YAML and file timestamp | Restart Pod or use full volume plus reload |
| File missing in mount directory | Wrong `items.key` or path mapping | Object keys and volume spec | Correct key name or `items` path |
| Auth fails with correct-looking password | Encoded newline or wrong field | Decode with `cat -e` or `xxd` | Recreate Secret with `stringData` or `echo -n` |
| App cannot read Secret file | Permissions or user mismatch | `ls -l` inside container | Adjust `defaultMode`, `fsGroup`, or app user |

A senior-level design often combines several ideas: non-sensitive config in a ConfigMap, sensitive values in a Secret, projected volume paths that match application expectations, immutable versioned objects for controlled rollouts, and [RBAC that limits who can read Secrets](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/). The exam may only ask you to wire a Pod, but the same commands support a production design when you understand the update and security semantics.

## Patterns & Anti-Patterns

The strongest pattern is to treat configuration as a small release artifact rather than as an informal cluster note. A ConfigMap named `app-config` is easy to type during the exam, but production systems benefit from names that express ownership, version, and rollout intent, such as `orders-api-config-v2` or `orders-nginx-routes-2026-05`. The reason is operational: when a rollout goes wrong, you want the Deployment template, events, and Git history to show exactly which configuration version was attached to the Pod. This pattern works especially well with immutable ConfigMaps and Secrets because a new object name forces a new Pod template reference and makes rollback an ordinary workload rollout instead of a hidden mutation.

Another reliable pattern is to match the injection method to the application reload contract before you write YAML. If the application reads only environment variables during startup, then an env-based ConfigMap is acceptable, but you should plan a restart whenever the value changes. If the application watches files or can reload after a signal, a full volume mount gives you a cleaner path for runtime updates. If the application needs one exact file path inside a populated image directory, `subPath` is useful, but you should document that rotation requires a Pod restart. This is the difference between a manifest that merely starts and a manifest that an on-call engineer can operate under pressure.

For sensitive values, the safer default is to mount Secrets as read-only files and keep RBAC narrow. File mounts do not make a Secret impossible to leak, because a compromised process can still read any file it is allowed to read, but they reduce accidental exposure through process environment dumps and broad diagnostic commands. Pair the volume mount with `readOnly: true`, a restrictive `defaultMode`, and a container security context that matches the application user. When applications support both env vars and files, choose files for credentials and reserve env vars for non-sensitive startup settings that the process cannot reload anyway.

Projected volumes are the pattern to reach for when the application expects a single configuration directory but the platform should keep sources separate. A clean design can place non-sensitive settings under `config/`, credentials under `secrets/`, and Pod metadata under `pod/` while still mounting one volume at `/etc/runtime`. This gives the application one tree to read without forcing operators to merge Secrets and ConfigMaps into the same API object. The trade-off is that path mapping becomes more important, so every `items.path` should be reviewed as carefully as a container port or readiness probe.

The common anti-pattern is to use `envFrom` as a shortcut for everything because it makes the Pod spec shorter. That shortcut can be reasonable for a tiny lab app, but it becomes messy when many keys arrive in the process environment with no explicit mapping in the container spec. Collisions become harder to see, stale values are easy to misdiagnose, and sensitive values are more likely to show up in debug output. A better production default is explicit `env.valueFrom` for the handful of startup variables the app truly needs, with prefixes only when the application convention already expects them.

Another anti-pattern is mounting a ConfigMap over an existing application directory without checking what the image already contains there. [Kubernetes volume mounts hide the original directory contents at the mount path, so a mount at `/etc/nginx/conf.d` can remove packaged defaults that the image author expected to remain present.](https://kubernetes.io/docs/concepts/storage/volumes/) Sometimes hiding the directory is exactly what you want, but it should be a deliberate replacement rather than a surprise. When you only need to replace one file, use `subPath` and accept restart-driven updates, or mount the ConfigMap into a separate directory and point the application at that location.

The most dangerous anti-pattern is treating Kubernetes Secrets as a complete secret-management system by themselves. A Secret object is an API object with special handling, not a guarantee that every surrounding system is safe. You still need encryption at rest when the cluster policy requires it, RBAC that prevents broad read access, audit logging for sensitive operations, safe GitOps handling that avoids committing plaintext, and a rotation procedure that restarts or reloads consumers. In real platforms, Kubernetes Secrets often become the delivery point for credentials managed elsewhere, while an external secret store, controller, or cloud provider service owns generation and rotation.

| Pattern Or Anti-Pattern | Use It When | Operational Consequence |
|---|---|---|
| Versioned immutable ConfigMaps | You want auditable changes and controlled rollouts | Every config change becomes a new object reference |
| Explicit `env.valueFrom` mappings | Only a few startup settings are needed | Pod specs are longer but easier to debug |
| Secret file mounts | The application can read credential files | Less accidental process-environment exposure |
| Projected runtime directory | Multiple sources must appear under one path | Path mapping needs careful review |
| Broad `envFrom` everywhere | You are rushing or copying a lab shortcut | Collisions, stale values, and accidental exposure increase |
| Blind directory mounts | You did not inspect the image path first | Existing image files may disappear behind the volume |

## Decision Framework

Start every design by classifying each value along two axes: sensitivity and refresh behavior. Sensitivity tells you whether the value belongs in a ConfigMap or a Secret. Refresh behavior tells you whether the value should be an environment variable, a full volume mount, a projected file, or a deliberately restart-driven `subPath` replacement. This classification sounds simple, but it prevents most bad designs because it forces you to ask how the application actually consumes the value rather than choosing the shortest YAML.

For a non-sensitive value that is read once at startup, use a ConfigMap with `env` or `envFrom` and plan for a Pod restart when it changes. A log level, feature flag, or cache TTL often fits this path if the application does not support reload. For a non-sensitive file that the application can reread, mount the ConfigMap as a full volume and put the file under a path the application already understands. If the path must replace one packaged file, use `subPath`, but make the rollout procedure explicit because file updates will not flow through that mount.

For sensitive values, first decide whether the application can read from files. If yes, mount a Secret volume with `readOnly: true`, set a restrictive `defaultMode`, and keep the path narrow. If the application only supports environment variables, use `secretKeyRef` instead of `envFrom` so the Pod spec shows exactly which keys are being exposed. In both cases, remember that changing the Secret object does not automatically mean the application is using the new credential. Environment variables require restart, full volume mounts require kubelet sync plus application reread, and external systems may require old and new credentials to overlap during rotation.

For values shared by many Pods, decide whether mutation or versioning is safer. Mutable ConfigMaps are convenient during development because one object name can stay constant while values change. Production rollouts often prefer immutable, versioned objects because the Deployment template records the exact configuration version and the old object remains available for rollback. The cost is extra naming discipline and cleanup, but that cost is usually smaller than debugging a fleet of Pods that all reference the same mutable object while different nodes refresh at different times.

Use the following matrix as a quick design check before you write the Pod spec. It is not a replacement for application knowledge, but it catches the most important Kubernetes mechanics. If a row suggests two possible choices, choose the one that makes failure easier to observe and rollback easier to execute.

| Value Type | App Reads | Recommended Object | Recommended Injection | Restart Needed For Changes |
|---|---|---|---|---|
| Log level read at startup | Environment variable | ConfigMap | `env.valueFrom` or prefixed `envFrom` | Yes |
| Reloadable application YAML | File | ConfigMap | Full volume mount with `items` | Maybe, depends on app reload |
| TLS certificate and key | Files | Secret | Read-only Secret volume | Maybe, depends on proxy reload |
| Database password | File preferred | Secret | Read-only Secret volume | Usually yes during rotation |
| Private registry credential | Kubelet pull config | Secret | `imagePullSecrets` | Used on image pull |
| One replacement NGINX file | Exact file path | ConfigMap | `subPath` mount | Yes |

**Pause and predict:** if a Deployment uses a mutable ConfigMap through `envFrom`, you patch the ConfigMap, and then you scale the Deployment from three replicas to five, which Pods see the old value and which Pods see the new value?

<details>
<summary>Check your prediction</summary>

The existing three Pods keep the environment copied at process start, and the two new Pods start with the patched value. That mixed state is one reason versioned names and rollouts are easier to reason about for production changes.

</details>

The next section is establishing practical verification routines to inspect container runtime state and confirm how configuration changes reach your workloads.

Before you choose an approach, also decide how you will prove it worked. For env vars, the proof is usually `kubectl exec <pod> -- env` plus a restart or rollout check. For mounted files, the proof is `kubectl exec <pod> -- ls -l <path>` and reading the file path the application uses. For Secret bytes, the proof may be a controlled decode with `cat -e` or `xxd`, but only in a lab or approved debugging session. A good design includes the verification command in the runbook, because the difference between a working object and a working runtime view is exactly where configuration incidents hide.

## Did You Know?

- [**Secrets are base64 encoded by default, not encrypted by default.** Encryption at rest must be configured for the cluster, and RBAC still controls who can read Secret objects through the API.](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/)
- **ConfigMap and Secret volume updates are eventually reflected through kubelet-managed projected files, but environment variables never update inside an already-running process.** The application must also reread or reload the file to use the new value.
- [**Objects marked `immutable: true` cannot be edited in place, which is useful when you want configuration changes to happen only through versioned object names and controlled Pod rollouts.**](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/)
- [**A projected volume can combine ConfigMaps, Secrets, Downward API data, and service account tokens into one directory tree, which helps applications that expect a single runtime configuration path.**](https://kubernetes.io/docs/concepts/storage/projected-volumes/)

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---|---|---|
| Using `--from-file` when each line should become a separate environment variable | The whole file becomes one key, so `envFrom` does not create the expected variables | Use `--from-env-file` for `KEY=value` files that should split into separate keys |
| Writing plain text under Secret `data` | The `data` field expects base64-encoded values, so the application may receive invalid bytes | Use `stringData` for hand-written YAML or let `kubectl create secret` encode values |
| Encoding Secrets with plain `echo` | The trailing newline becomes part of the credential and can break authentication | Use `echo -n`, `printf`, `stringData`, or `kubectl create secret --from-literal` |
| Expecting env vars to update after a ConfigMap or Secret changes | Environment variables are copied into the process at container start | Restart the Pod or use a volume mount with an application reload strategy |
| Using `subPath` for files that must rotate automatically | `subPath` mounts do not receive ConfigMap or Secret updates | Mount the full volume directory or restart Pods during rotation |
| Mounting a ConfigMap over a populated application directory | The volume hides files that were already present in the image at that path | Mount into an empty config directory or use `subPath` when exact replacement is acceptable |
| Injecting sensitive values with `envFrom` by default | Secrets become broad process environment data and are easier to leak in logs or diagnostics | Prefer read-only Secret volume mounts for credentials when the application supports files |
| Giving broad users or service accounts permission to read all Secrets | Anyone with read access can retrieve and decode Secret values | Scope RBAC narrowly and combine it with encryption at rest and audit logging |

## Quiz

### Question 1

Your team created `settings.env` with ten `KEY=value` lines and then ran `kubectl create configmap web-settings --from-file=settings.env`. The Pod uses `envFrom.configMapRef.name: web-settings`, but the application reports that `LOG_LEVEL` and `CACHE_TTL_SECONDS` are unset. What happened, and how would you fix the ConfigMap creation command?

<details>
<summary>Show Answer</summary>

`--from-file=settings.env` stored the entire file under one key named `settings.env`; Kubernetes did not split the lines into separate keys. When `envFrom` tried to create environment variables, the key name was not a useful application setting, and the expected keys such as `LOG_LEVEL` did not exist. Recreate the ConfigMap with `--from-env-file=settings.env` so each valid `KEY=value` line becomes its own key. If a Pod already exists, restart it after recreating the ConfigMap because environment variables are set only at container start.
</details>

### Question 2

A Pod mounts a ConfigMap at `/etc/app`, and the ConfigMap contains keys `application.yaml` and `routes.yaml`. A teammate expects the files to appear directly as `/application.yaml` and `/routes.yaml` because those are the key names. The app fails with "file not found" at `/etc/app/application.yaml`. How do you explain the path mapping and verify the real files?

<details>
<summary>Show Answer</summary>

For a full ConfigMap volume mount, each key becomes a file under the `mountPath`. The key `application.yaml` becomes `/etc/app/application.yaml`, and `routes.yaml` becomes `/etc/app/routes.yaml`. The files do not appear at the filesystem root unless the volume is mounted at `/`, which would be a bad design. Verify the mapping with `kubectl exec <pod> -- ls -la /etc/app` and then read the expected file with `kubectl exec <pod> -- cat /etc/app/application.yaml`. If the application is looking elsewhere, change the app config or adjust `mountPath` and `items.path`.
</details>

### Question 3

An NGINX Pod uses `subPath` to mount one ConfigMap key onto `/etc/nginx/conf.d/default.conf`. You patch the ConfigMap to add a new `/api` location, but traffic still follows the old configuration after several minutes. What are the two separate reasons this design may not update behavior immediately?

<details>
<summary>Show Answer</summary>

First, `subPath` mounts do not receive automatic ConfigMap updates, so the file mounted at `/etc/nginx/conf.d/default.conf` remains stale until the Pod is restarted. Second, even if the file were updated through a full volume mount, NGINX may keep its old configuration in memory until it is reloaded. The exam-friendly fix is to restart or recreate the Pod. A production design would usually mount the full config directory or use versioned ConfigMap names, then pair file changes with an explicit NGINX reload or rolling Deployment update.
</details>

### Question 4

A developer writes a Secret manifest with `data.password: example-db-password` and applies it. The Pod starts, but database authentication fails. They argue that `kubectl get secret -o yaml` clearly shows the password field exists. What should you check, and how should the manifest be rewritten?

<details>
<summary>Show Answer</summary>

The problem is likely that `data` contains plain text instead of base64-encoded data. The existence of the key only proves Kubernetes stored something; it does not prove the decoded bytes are the intended password. Check the decoded value with a controlled command such as `kubectl get secret <name> -o jsonpath='{.data.password}' | base64 -d | cat -e`. Rewrite the manifest using `stringData.password: example-db-password`, or encode the value correctly with `echo -n 'example-db-password' | base64` and place the result under `data.password`.
</details>

### Question 5

A security audit finds that database credentials are visible through `kubectl exec orders-api -- env`. The application can read credentials either from environment variables or from files. What Kubernetes change would reduce accidental exposure, and what hardening settings should you include?

<details>
<summary>Show Answer</summary>

The credentials are currently injected as environment variables through `env`, `envFrom`, or `secretKeyRef`. Switch to a Secret volume mount so the application reads files such as `/etc/db-creds/username` and `/etc/db-creds/password`. Set `readOnly: true` on the `volumeMount` and use a restrictive `defaultMode`, such as `0400`, in the Secret volume. This does not remove the need for RBAC and encryption at rest, but it avoids exposing the values through ordinary process environment inspection.
</details>

### Question 6

Your team marks `app-config` as immutable to prevent accidental edits. A week later, production needs `LOG_LEVEL=debug` for an incident. A teammate tries `kubectl patch configmap app-config`, but Kubernetes rejects the change. What rollout procedure should you use instead?

<details>
<summary>Show Answer</summary>

Immutable ConfigMaps cannot be changed in place. Create a new ConfigMap with a versioned name, such as `app-config-v2`, containing the updated value. Then update the Deployment Pod template to reference `app-config-v2`, which triggers a rollout and makes the change auditable. After the incident, create another version or roll back the Deployment to the previous ConfigMap name. This procedure treats configuration changes like release artifacts instead of mutable shared state.
</details>

### Question 7

A Pod fails with `CreateContainerConfigError` after you add a required Secret key reference. The Secret exists, and the Pod spec references the right Secret name. What Kubernetes-level checks would you perform before blaming the application image?

<details>
<summary>Show Answer</summary>

Start with `kubectl describe pod <pod>` and read the Events section, because Kubernetes often reports the missing key or invalid reference there. Then inspect the Secret keys with `kubectl get secret <secret> -o yaml` and compare them exactly against the Pod's `secretKeyRef.key`; key names are case-sensitive. Also confirm the Pod and Secret are in the same namespace, because Pod references do not cross namespaces. If the key is optional, the container may start without the value, but for required references Kubernetes blocks container creation until the reference is valid.
</details>

## Hands-On Exercise

### Scenario: Configure And Debug A Web Application

You are the platform engineer on call for a small web application. The application needs non-sensitive runtime settings, an NGINX config file, and database credentials. You will create the objects, mount them into a Pod, verify the runtime view, intentionally update configuration, and explain which values change without a restart.

### Step 1: Prepare The Namespace And Non-Sensitive Settings

Create a namespace for the lab so cleanup is safe and the object references are easy to inspect. The first ConfigMap uses literals because the values are short and map naturally to environment variables. The second ConfigMap uses a file because NGINX expects a complete server configuration file.

```bash
kubectl create namespace config-demo

kubectl create configmap app-settings -n config-demo \
  --from-literal=LOG_LEVEL=info \
  --from-literal=CACHE_TTL_SECONDS=300 \
  --from-literal=FEATURE_CHECKOUT_V2=true
```

```bash
cat > /tmp/kubedojo-nginx.conf <<'EOF'
server {
  listen 80;

  location / {
    return 200 'KubeDojo config demo\n';
    add_header Content-Type text/plain;
  }

  location /health {
    return 200 'OK\n';
    add_header Content-Type text/plain;
  }
}
EOF

kubectl create configmap nginx-config -n config-demo \
  --from-file=nginx.conf=/tmp/kubedojo-nginx.conf
```

### Step 2: Create Database Credentials As A Secret

Create the Secret imperatively so Kubernetes handles encoding. This is the safest exam path when the value contains punctuation. In production, avoid placing real secrets directly in shell history; this lab uses throwaway values in a local namespace.

```bash
kubectl create secret generic db-creds -n config-demo \
  --from-literal=username=orders_user \
  --from-literal=password='example-lab-password'
```

Inspect the object shape without printing decoded values unnecessarily. You should see base64 strings under `data`, which confirms storage format but not encryption.

```bash
kubectl get secret db-creds -n config-demo -o yaml
```

### Step 3: Deploy The Pod With Env Vars And Mounted Files

Apply a Pod that uses three different injection patterns. `app-settings` is loaded through `envFrom` with a prefix, `nginx-config` is mounted through `subPath` to replace one exact file, and `db-creds` is mounted as read-only files with restrictive permissions. This mixed design is realistic because different values have different consumers and risks.

```bash
cat > /tmp/kubedojo-webapp.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: webapp
  namespace: config-demo
  labels:
    app: webapp
spec:
  containers:
  - name: nginx
    image: nginx:1.27
    ports:
    - containerPort: 80
    envFrom:
    - configMapRef:
        name: app-settings
      prefix: APP_
    volumeMounts:
    - name: nginx-config
      mountPath: /etc/nginx/conf.d/default.conf
      subPath: nginx.conf
    - name: db-creds
      mountPath: /etc/db-creds
      readOnly: true
  volumes:
  - name: nginx-config
    configMap:
      name: nginx-config
      items:
      - key: nginx.conf
        path: nginx.conf
  - name: db-creds
    secret:
      secretName: db-creds
      defaultMode: 0400
EOF

kubectl apply -f /tmp/kubedojo-webapp.yaml

kubectl wait --for=condition=ready pod/webapp -n config-demo --timeout=90s
```

### Step 4: Verify The Runtime View

Verify each injection path separately. The goal is not just to prove the Pod is running; the goal is to trace each object key to what the container can actually see. This is the same troubleshooting habit you need when a Pod starts but the application behaves incorrectly.

```bash
kubectl exec webapp -n config-demo -- env | grep '^APP_'

kubectl exec webapp -n config-demo -- cat /etc/nginx/conf.d/default.conf

kubectl exec webapp -n config-demo -- ls -l /etc/db-creds

kubectl exec webapp -n config-demo -- sh -c 'curl -s localhost/health'
```

The environment output should include `APP_LOG_LEVEL=info`, `APP_CACHE_TTL_SECONDS=300`, and `APP_FEATURE_CHECKOUT_V2=true`. The NGINX config should match the file you created under `/tmp`, but remember that it is mounted with `subPath`. The Secret files should exist under `/etc/db-creds`, and the mode should reflect the restrictive Secret volume setting.

### Step 5: Update A ConfigMap And Observe Stale Values

Patch the `app-settings` ConfigMap and then check the running process environment. The value will not change inside the existing container because environment variables are copied at process start. This is not a bug; it is the expected runtime contract.

```bash
kubectl patch configmap app-settings -n config-demo \
  --type merge \
  -p '{"data":{"LOG_LEVEL":"debug"}}'

kubectl exec webapp -n config-demo -- env | grep '^APP_LOG_LEVEL='
```

Now restart the Pod by replacing it from the same manifest. This is a simple Pod lab, so `replace --force` is acceptable. In a Deployment, you would update the Pod template or restart the rollout instead.

```bash
kubectl replace --force -f /tmp/kubedojo-webapp.yaml

kubectl wait --for=condition=ready pod/webapp -n config-demo --timeout=90s

kubectl exec webapp -n config-demo -- env | grep '^APP_LOG_LEVEL='
```

### Step 6: Diagnose A Missing Key Failure

Create a deliberately broken Pod manifest that references a key that does not exist. Do not spend time guessing from memory; use the Kubernetes events to identify the exact failure. This step practices a fast CKA troubleshooting path for configuration references.

```bash
cat > /tmp/kubedojo-broken.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: broken-webapp
  namespace: config-demo
spec:
  containers:
  - name: nginx
    image: nginx:1.27
    env:
    - name: APP_REQUIRED_SETTING
      valueFrom:
        configMapKeyRef:
          name: app-settings
          key: DOES_NOT_EXIST
EOF

kubectl apply -f /tmp/kubedojo-broken.yaml

kubectl get pod broken-webapp -n config-demo

kubectl describe pod broken-webapp -n config-demo
```

Read the Events section and identify the missing key. Then repair the Pod by either changing the referenced key to an existing key or adding the missing key to the ConfigMap. For this lab, add the missing key and watch the Pod recover.

```bash
kubectl patch configmap app-settings -n config-demo \
  --type merge \
  -p '{"data":{"DOES_NOT_EXIST":"now-present"}}'

kubectl wait --for=condition=ready pod/broken-webapp -n config-demo --timeout=90s

kubectl exec broken-webapp -n config-demo -- env | grep APP_REQUIRED_SETTING
```

### Step 7: Validate Secret Bytes When Authentication Looks Wrong

Create a Secret with a trailing newline to see why invisible bytes matter. This is a controlled debugging exercise; the point is to learn the symptom without using real credentials. The command intentionally uses plain `echo`, which includes a newline.

```bash
echo 'bad-password' | base64

cat > /tmp/kubedojo-bad-secret.yaml <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: bad-db-creds
  namespace: config-demo
type: Opaque
data:
  password: YmFkLXBhc3N3b3JkCg==
EOF

kubectl apply -f /tmp/kubedojo-bad-secret.yaml

kubectl get secret bad-db-creds -n config-demo \
  -o jsonpath='{.data.password}' | base64 -d | cat -e
```

The `$` marker at the end shows that the decoded value includes a newline. Recreate the Secret using `stringData` or a no-newline encoding method. In real work, this small byte-level check often saves time when every visible character seems correct.

```bash
cat > /tmp/kubedojo-good-secret.yaml <<'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: good-db-creds
  namespace: config-demo
type: Opaque
stringData:
  password: bad-password
EOF

kubectl apply -f /tmp/kubedojo-good-secret.yaml

kubectl get secret good-db-creds -n config-demo \
  -o jsonpath='{.data.password}' | base64 -d | cat -e
```

**Card A: Patching a ConfigMap used through `envFrom` rewrites the environment of Pods that are already running.** An operator modifies a ConfigMap key and expects existing containers to see the updated environment variables immediately without a restart.

<details>
<summary>Check your prediction</summary>

Failure layer: environment variable immutability inside running container processes versus dynamic configuration delivery. Next action: recognize that environment variables are copied into the container process table at process start and never mutate dynamically; trigger a rolling restart of the owning Deployment with `kubectl rollout restart` or introduce versioned ConfigMap names so replacement Pods pick up the new configuration.

</details>

**Card B: A Secret's base64 `data` field means the value is encrypted at rest.** A developer stores sensitive database credentials in a Kubernetes Secret object and assumes the base64 encoding provides cryptographic confidentiality against unauthorized cluster storage access.

<details>
<summary>Check your prediction</summary>

Failure layer: base64 encoding representation versus cryptographic encryption at rest. Next action: understand that base64 is an encoding scheme designed for arbitrary byte transport, not encryption; configure an EncryptionConfiguration provider on the API server to achieve genuine encryption at rest in etcd, and restrict API access to Secret objects using granular RBAC policies.

</details>

**Card C: A `subPath` mount updates the file in the container when the ConfigMap is patched.** An administrator overrides an individual configuration file using a `subPath` volume mount and expects kubelet to propagate upstream ConfigMap edits into the mounted container path automatically.

<details>
<summary>Check your prediction</summary>

Failure layer: single-file `subPath` volume mounting versus atomic directory symlink updates. Next action: recognize that a `subPath` mount isolates an individual file without symlink projection, causing the mounted file to stay stale until the Pod is recreated; use a full ConfigMap volume mount if automatic file updates are required, or delete and recreate the Pod to consume updated file contents.

</details>

**Card D: `envFrom` and a full ConfigMap volume mount refresh a running process the same way.** A platform engineer assumes that injecting configuration through environment variables or through a full volume mount offers equivalent runtime update semantics for containerized applications.

<details>
<summary>Check your prediction</summary>

Failure layer: process environment immutability versus filesystem projection and application reload semantics. Next action: understand that environment variables never change in a running process, whereas a full volume mount can update files on disk via atomic symlink updates; even when files update on disk, the application process must actively reread or reload configuration files to use the updated values.

</details>

**Success Criteria**:

- [ ] You created a namespace, ConfigMap literals, a ConfigMap file, and a generic Secret without using hardcoded production credentials.
- [ ] The `webapp` Pod reached `Ready` and showed `APP_` environment variables from the ConfigMap.
- [ ] The NGINX config appeared at `/etc/nginx/conf.d/default.conf` through a `subPath` mount, and you can explain why that file will not auto-update.
- [ ] The database credential files appeared under `/etc/db-creds` with read-only mount behavior and restrictive Secret volume permissions.
- [ ] After patching `app-settings`, you observed that the running environment variable stayed stale until the Pod was restarted.
- [ ] You diagnosed a `CreateContainerConfigError` caused by a missing ConfigMap key using `kubectl describe pod`.
- [ ] You decoded a Secret value with `cat -e` and identified the difference between a password with and without a trailing newline.

### Cleanup

```bash
kubectl delete namespace config-demo

rm -f /tmp/kubedojo-nginx.conf \
  /tmp/kubedojo-webapp.yaml \
  /tmp/kubedojo-broken.yaml \
  /tmp/kubedojo-bad-secret.yaml \
  /tmp/kubedojo-good-secret.yaml
```

## Sources

- [ConfigMaps](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/configmap/) — Primary source for non-sensitive configuration, env-var and file-based injection, immutability, key/value structure, size limits, and update propagation behavior for mounted ConfigMaps.
- [Secrets](https://v1-35.docs.kubernetes.io/docs/concepts/configuration/secret/) — Primary source for Secret semantics, security caveats, env-var and volume consumption, optional and missing-key behavior, immutability, update propagation, and subPath update caveats.
- [kubernetes.io: kubectl create configmap](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_configmap/) — The kubectl command reference directly documents the semantics of `--from-file` and `--from-env-file`.
- [kubernetes.io: kubectl create secret generic](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_generic/) — Command reference for generic Secret creation from literals, files, and env files.
- [kubernetes.io: kubectl create secret tls](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_secret_tls/) — Command reference for TLS Secret creation from certificate and private-key files.
- [kubernetes.io: projected volumes](https://kubernetes.io/docs/concepts/storage/projected-volumes/) — The projected volumes concept page directly lists these source types for a single projected directory.
- [Kubernetes volumes: ConfigMap](https://kubernetes.io/docs/concepts/storage/volumes/#configmap) — Storage concept reference for ConfigMap volume behavior and optional keys.
- [Kubernetes volumes: Secret](https://kubernetes.io/docs/concepts/storage/volumes/#secret) — Storage concept reference for Secret volume behavior, file modes, and tmpfs-backed delivery.
- [Encrypting Secret Data at Rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/) — Kubernetes task documentation for configuring API-server encryption providers for Secret data.
- [RBAC Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/) — Kubernetes guidance for limiting powerful permissions, including access to Secret objects.
- [Downward API](https://kubernetes.io/docs/concepts/workloads/pods/downward-api/) — Primary documentation for exposing Pod and container metadata to workloads, including through projected volume paths.
- [Configure a Pod to Use a ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/) — Task documentation with examples for consuming ConfigMaps through environment variables and volumes.
- [kubernetes.io: distribute credentials secure](https://kubernetes.io/docs/tasks/inject-data-application/distribute-credentials-secure/) — The Secret task page directly shows imperative creation and the shell-escaping warning for special characters.
- [kubernetes.io: volumes](https://kubernetes.io/docs/concepts/storage/volumes/) — The volumes concept page explains that volumes are mounted into the container filesystem at specified paths, which is a reasonable anchor for this operational warning even though it does not state the hidden-files consequence verbatim.

## Next Module

You have completed Part 2: Workloads & Scheduling. Continue with [Part 2 Cumulative Quiz](../part2-cumulative-quiz/) to verify the workload patterns together before moving into Services & Networking.
