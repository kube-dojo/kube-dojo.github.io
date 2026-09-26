---
revision_pending: false
title: "Part 1 Cumulative Quiz: Application Design and Build"
sidebar:
  order: 5
---

> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 75–90 minutes, including a 25-minute quiz and a hands-on drill
>
> **Prerequisites**: [Module 1.1: Container Images](../module-1.1-container-images/), [Module 1.2: Jobs and CronJobs](../module-1.2-jobs-cronjobs/), [Module 1.3: Multi-Container Pods](../module-1.3-multi-container-pods/), and [Module 1.4: Volumes for Developers](../module-1.4-volumes/)

## Learning Outcomes

After completing this cumulative module, you will be able to:

- **Diagnose** image pull failures using Pod events and image fields, then distinguish an image reference error from a command override error.
- **Choose** a Job, CronJob, or Deployment from the work's lifetime, and place retry, schedule, and cleanup controls at the correct level.
- **Design** init and sidecar collaboration through a shared Pod volume, and distinguish ambassador and adapter roles by the direction of communication.
- **Select** `emptyDir`, ConfigMap, Secret, or PersistentVolumeClaim storage from the required lifetime and file visibility, then explain common mount failures.
- **Verify** a combined workload with focused `kubectl` observations, tracing a symptom through the image, controller, container, and volume layers.

## Why This Module Matters

Hypothetical scenario: a developer needs a small report generated once and then served from a Pod. The report generator must finish before the server starts. The server also needs configuration files, and an operator wants the generated report to remain available after a container restart. A single vague instruction to “make the Pod work” hides several decisions: which image runs each process, whether the work is finite or continuous, how the containers exchange a file, and how long that file must survive.

The four Part 1 modules solve those decisions separately. [Module 1.1](../module-1.1-container-images/) connects image references and process overrides to startup behavior. [Module 1.2](../module-1.2-jobs-cronjobs/) separates finite and scheduled work from continuously available applications. [Module 1.3](../module-1.3-multi-container-pods/) explains why helpers may share a Pod but still have different lifecycles. [Module 1.4](../module-1.4-volumes/) connects file sources, mount paths, and persistence. This review asks you to make all four decisions together without inventing a new Kubernetes mechanism.

Use the core content as a decision guide before you attempt the quiz. Then hide the answers and give yourself 25 minutes for its eight scenarios. Every question has one best option under its stated assumptions. The answer blocks explain the other options because a plausible command can still address the wrong failure layer. After scoring, complete the hands-on drill and use its observations to test any reasoning you were uncertain about.

## Core Content

### Start with the observable boundary

A Kubernetes symptom is evidence about a stage, not a diagnosis by itself. A Pod can be accepted by the API yet wait for a claim, fail to pull an image, run an init container repeatedly, or start an app that immediately exits. These states invite different first checks. Read the resource kind and its intended lifetime, inspect the Pod status and events, identify the affected container, then inspect the fields that can explain that stage. This order reduces the temptation to rebuild an image for a missing volume or change storage for a bad process argument.

The smallest useful observation set is often `kubectl get pod`, `kubectl describe pod`, and the relevant controller or claim status. `kubectl describe pod` shows events and container states; a focused JSONPath query exposes the actual image string stored in the Pod. When a container has started and failed, its logs become useful. When a container has never started because it cannot pull an image or mount a volume, application logs cannot explain the earlier failure. Ask which transition failed before choosing the next command.

```bash
kubectl get pod report-web
kubectl describe pod report-web
kubectl get pod report-web -o jsonpath='{.spec.containers[*].image}'
kubectl get pvc
```

These commands are diagnostic examples, not recorded output from a cluster. The Pod and claim names are illustrative. In a real namespace, substitute the names shown by `kubectl get` and read the event text before making a change. A Pending Pod with an unbound claim needs storage investigation; a Pod with `ErrImagePull` needs image and registry investigation. A container that starts and exits needs command, arguments, and logs checked instead.

### Image references and process overrides answer different questions

An image field tells the node runtime what artifact to fetch. A container process definition tells that runtime what executable and arguments to start from the fetched artifact. Module 1.1 teaches the compact image reference shape: optional registry and namespace, image name, optional tag, and optional digest. If the tag is omitted, the default tag is `latest`. That word names a tag; it does not prove that the registry serves the newest release, a compatible architecture, or the version a question requests.

When a Pod reports `ErrImagePull` or `ImagePullBackOff`, inspect the image string and the Pod events together. A typo in a repository, an unavailable tag, or missing private registry credentials may all prevent a pull, but the event text distinguishes them. Do not change a correctly spelled image to `latest` as a generic fix. Doing so discards the requested version and may introduce a mutable reference. Correct the specific reference or credential problem, then observe the replacement workload rather than assuming the edit worked.

```bash
kubectl describe pod report-web
kubectl get pod report-web -o jsonpath='{.spec.containers[0].image}'
```

The process can fail after the pull succeeds. Dockerfile `ENTRYPOINT` provides the executable, and `CMD` provides its default arguments in the model taught by Module 1.1. Kubernetes `command` overrides the image `ENTRYPOINT`, while Kubernetes `args` overrides the image `CMD`. Setting `command` without `args` also discards the image `CMD`. Suppose an image declares `ENTRYPOINT ["python"]` and `CMD ["worker.py"]`. To run a different script with the same Python executable, set `args: ["check.py"]`; setting `command: ["check.py"]` asks the runtime to execute that file directly.

This distinction matters during time-boxed work because both image and command mistakes may leave a Pod unready, yet their evidence differs. If events show the image never arrived, editing `args` cannot help. If the image pulled and the container exited with an executable error, changing registry credentials cannot help. Read the stage, then change the field that controls that stage. A correct diagnosis is a narrower, faster edit than a broad manifest rewrite.

**Pause and predict:** A Pod names a valid image with `ENTRYPOINT ["python"]` and `CMD ["worker.py"]` in its Dockerfile. Its Kubernetes spec changes only `command` to `["check.py"]`, and the container exits with an executable error. Which field would you edit to keep Python as the executable while running `check.py`?

<details>
<summary>Prediction answer</summary>

Set `args: ["check.py"]` and remove the mistaken `command` override. Kubernetes `args` replaces the image's default `CMD` while the original `ENTRYPOINT` remains the executable.

</details>

The same evidence sequence applies to batch Pods and helper containers. First locate the failing container by name, because changing a healthy neighbor can obscure the actual fault and consume valuable practice time. A precise container name also makes later log and execution commands unambiguous.

### Choose a controller from work duration

A Job represents work that should finish. A CronJob creates Jobs on a schedule. A Deployment keeps application replicas available. These are not interchangeable wrappers around the same Pod: each controller has a different success condition. A report export that exits successfully belongs in a Job; a nightly report export belongs in a CronJob; an HTTP server that should remain available belongs in a Deployment. The Pod template still describes the container, but the controller decides what to do after it exits.

Start by writing the success sentence without Kubernetes terms. “The process must complete once” points to a Job. “The process must complete on a schedule” points to a CronJob. “The process should continue serving requests” points to a Deployment. This prevents a common Part 1 mistake: wrapping a finite script in a Deployment and then treating its expected exit as a crash, or wrapping a long-running server in a Job that never completes.

The `kubectl create job` and `kubectl create cronjob` commands can generate a useful first manifest. The container command comes after `--`, which separates tool options from the command passed into the container. For a shell expression, pass `sh -c` after that separator. Generate YAML for inspection when you need fields the short command does not express, then put each setting at its proper level. The command separator is about command parsing; it does not set retry or scheduling policy.

```bash
kubectl create job report-once --image=busybox:1.36 --dry-run=client -o yaml -- sh -c 'echo report-ready'
kubectl create cronjob report-nightly --image=busybox:1.36 --schedule='0 2 * * *' --dry-run=client -o yaml -- sh -c 'echo report-ready'
```

A Job's `backoffLimit` limits retries after failure. It does not schedule another successful run, and it does not keep a web server available. A failing script can therefore consume the configured retry budget before the Job is marked failed. Inspect the Job and its Pods rather than assuming one failed Pod means the controller has finished. In a lab, an explicit small limit makes a broken command visible sooner, although the right value for real work depends on whether retries are safe and useful.

CronJob settings add another level of nesting. `schedule`, `concurrencyPolicy`, `successfulJobsHistoryLimit`, and `failedJobsHistoryLimit` belong to the CronJob. A `backoffLimit` for each run belongs under `jobTemplate.spec`; its Pod template lives one level deeper. `concurrencyPolicy: Forbid` prevents a new overlapping run while an earlier run remains active. It does not fix a script that fails or turn a recurring schedule into one finite run. Read the nesting before applying a generated manifest, because valid fields at the wrong scope will not express the intended behavior.

CronJob history limits and `ttlSecondsAfterFinished` address different cleanup questions. History limits bound the count of completed Jobs retained by a CronJob. A Job TTL asks the TTL controller to remove a finished Job after a duration. If you need a few recent runs for inspection and eventual time-based removal, both may be appropriate. Neither should be presented as a fix for an image pull, a broken command, or a still-active run. Cleanup begins only after the workload reaches the relevant finished state.

**Pause and predict:** A nightly export sometimes runs into the next scheduled time, and the operator wants to avoid overlapping runs while retaining two successful Jobs for inspection. Which controller fields address those two wishes, and where would a per-run retry limit go?

<details>
<summary>Prediction answer</summary>

Set `concurrencyPolicy: Forbid` and `successfulJobsHistoryLimit: 2` on the CronJob. Put the per-run `backoffLimit` under `jobTemplate.spec`, because each scheduled Job owns its own retry behavior.

</details>

Now distinguish a scheduling decision from a data decision. Preventing overlap can protect one operation from competing with itself, but it does not make files durable. If the export must survive replacement of the Pod that wrote it, select storage with that lifecycle separately from the CronJob settings.

### Give each helper a lifecycle and a communication path

Module 1.3 names four multi-container patterns: init, sidecar, ambassador, and adapter. They describe a helper's purpose, not four new Kubernetes API kinds. A regular init container performs setup and must finish successfully before application containers start. A sidecar continues helping while the app runs. An ambassador provides a local route from the app to an outside dependency. An adapter converts local output into another format for a consumer. Decide whether the helper must finish or keep running, then decide what crosses the container boundary.

A report generator that writes one file before the web process starts is a regular init container when both belong to one Pod. The init container and web container can mount the same `emptyDir` at different paths. The generator writes the file and exits successfully; Kubernetes then starts the web container, which reads the file through its own mount. If the generator instead sleeps forever, the app never starts because normal init completion never occurs. Making the generator a Deployment would also lose the deliberate start ordering inside this Pod.

A sidecar is different because its work continues. A log reader or local proxy must keep a foreground process alive beside the app. Kubernetes 1.35 also supports a native sidecar as an entry under `initContainers` with `restartPolicy: Always`. That specific setting gives the container a continuing lifecycle even though it appears in the init list. A regular init container without it still runs to completion. A classic sidecar under `containers` remains a valid pattern when the extra lifecycle ordering is unnecessary.

Containers in the same Pod share a network namespace, so they can communicate over localhost. They can also share a volume when both mount the same named source, and process visibility can be shared when the Pod is configured for a shared process namespace. These are distinct channels. Sharing a Pod IP does not automatically make one container's private filesystem visible to another. Defining a volume at Pod level also does not mount it into every container; each consumer needs its own `volumeMounts` entry with the matching volume name.

An ambassador and adapter can look similar in YAML because each can be a second running container. The direction of work distinguishes them. If the app calls `localhost` and a helper forwards that call to an outside service, the helper is an ambassador. If the app writes a local format and a helper translates that output for monitoring, the helper is an adapter. Both are ongoing helpers rather than blocking setup. State their direction explicitly in a design answer, then choose localhost or a shared file according to the actual interface.

Consider a Pod with a web app and a log formatter. The app writes a plain log file to `/work/app.log`, and the formatter reads that file and exposes transformed output. Both containers must mount the same volume, because the formatter cannot read the app's image layer by virtue of sharing a Pod. The formatter is an adapter if the transformation serves an external consumer. If it only ships unchanged logs while the app serves requests, “sidecar” describes the general helper role. The pattern names help you communicate intent; the mount makes the intent work.

### Match files to a lifecycle before choosing a source

Module 1.4's central distinction is between a container filesystem, a Pod volume, and a claim. A container restart starts from a clean writable container state. An `emptyDir` belongs to the Pod and survives a container restart within that same Pod, but its data is gone when the Pod is replaced. A PersistentVolumeClaim is a separate storage request and can outlive the Pod. A ConfigMap or Secret volume presents API object data as files; it is a source of configuration or credentials, not a place for the application to write durable output.

For generated report content that can be rebuilt whenever a Pod is replaced, `emptyDir` gives the init container and server a simple handoff. The file remains available if only the server container restarts within the Pod. It is rebuilt when a new Pod starts and its init container runs again. If the report must remain the same after Pod replacement, `emptyDir` is the wrong contract even though it worked during a container restart. A bound PVC is the Part 1 option for storage that should survive that replacement.

The volume source and mount are separate declarations. `spec.volumes` names the source for the Pod; each container's `volumeMounts` maps that source to a path in that container. The mount path can differ between containers, but the volume name must match. If the writer saves `/work/report.txt` while the reader mounts the same volume at `/usr/share/nginx/html`, the reader sees `/usr/share/nginx/html/report.txt`. It does not need the writer's path, and it does not see the file until both mounts point to the same source.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: report-web
spec:
  initContainers:
    - name: prepare-report
      image: busybox:1.36
      command: ["sh", "-c", "echo report-ready > /work/report.txt"]
      volumeMounts:
        - name: report-files
          mountPath: /work
  containers:
    - name: web
      image: nginx:1.27-alpine
      volumeMounts:
        - name: report-files
          mountPath: /usr/share/nginx/html
  volumes:
    - name: report-files
      emptyDir: {}
```

Save this manifest as `report-web.yaml` in an ordinary Kubernetes 1.35 practice cluster with access to the named public images. It intentionally treats the web root as generated content and does not rely on image files under that path. After applying it, wait for readiness, check the init status, and read the file from the web container. The expected content is `report-ready`; the exact Pod age and IP depend on your cluster. If the file is missing, compare the two mount names before assuming nginx failed.

```bash
kubectl apply -f report-web.yaml
kubectl wait --for=condition=Ready pod/report-web --timeout=120s
kubectl get pod report-web
kubectl get pod report-web -o jsonpath='{.status.initContainerStatuses[*].state.terminated.exitCode}'
kubectl exec report-web -c web -- cat /usr/share/nginx/html/report.txt
```

A directory mount hides files the image already had at that path. That behavior matters when an image includes default configuration or web assets. Mounting a ConfigMap at `/etc/app` does not merge new keys with image files already under `/etc/app`; the mounted directory becomes the view the process sees. If one configuration file must appear alongside image defaults, choose a precise file mount and accept the update tradeoff. Module 1.4 explains that a ConfigMap or Secret mounted through `subPath` does not receive live updates the way an ordinary projected directory mount does.

ConfigMap and Secret volumes both expose key-value data as files, but their intended contents differ. A ConfigMap holds ordinary configuration, while a Secret holds sensitive values such as credentials. In either case, a missing referenced object can leave the container in `ContainerCreating`; inspect Pod events for the missing name before editing the image. If a volume's `items` lists a key absent from the object, and its reference is not `optional: true`, the mount also fails: the container stays `ContainerCreating`, and an event names the missing key. When the whole object is mounted as a directory instead, an app may expect a key that the object lacks; the container can start without that file. Check both Pod events and the container's filesystem view to distinguish these cases. Do not assume “Pod has a volume” means “the right container sees the right key.”

A PVC introduces another failure point before the container can start. If no matching volume or provisioner binds the claim, the PVC remains `Pending` and a Pod using it remains blocked. Check `kubectl get pvc` and `kubectl describe pvc` alongside Pod events. Changing the web container's command cannot bind the claim. Likewise, changing an `emptyDir` mount cannot make a PVC's data appear. Identify whether the problem is the requested source, the claim binding, or the container mount before modifying the manifest.

`ReadWriteOnce` describes node mounting, not an application file lock. It permits read-write mounting by one node at a time under the storage access-mode contract; it does not guarantee that only one process writes a file. If the design calls for exclusive application writes, reason about the workload and storage behavior separately. For this cumulative review, recognize the distinction and avoid promising exclusivity from an access-mode name. The claim's `Bound` state and the Pod's mount events provide more useful evidence during a blocked startup.

### Walk a combined failure without changing the wrong layer

Simulation: imagine a scheduled export Job that finishes successfully, followed by a web Pod that should serve its output. The Job's success proves its own container command ran and exited; it does not prove the web Pod has the same filesystem. A Job Pod and a web Pod do not share an `emptyDir`, even if both use a volume with the same name. `emptyDir` is scoped to one Pod. If the export must cross Pod lifetimes, the design needs a source both workloads can use, such as an appropriately bound PVC, with access mode and scheduling constraints checked.

Now suppose the web Pod stays `Pending`. The first useful distinction is whether its claim is unbound. Inspect PVC status before testing HTTP. If the claim is bound but the container stays `ContainerCreating`, inspect mount events and referenced ConfigMaps or Secrets. If the image cannot be fetched, inspect the image field and pull events. Only after the container runs should you inspect its command, logs, and served file. This sequence keeps each observation close to the subsystem that produced it.

If the app starts but returns an unexpected page, file visibility becomes the key question. A ConfigMap directory mount might have hidden the image's default page. An init container might have written to an `emptyDir` that the web container never mounted. A `subPath` file might still show old ConfigMap content. These possibilities differ even though the visible symptom is “wrong content.” Read `spec.volumes`, every relevant `volumeMounts` entry, and the file inside the named container before replacing the image or rewriting the Job.

Under a time limit, write a short evidence chain as you work: intended lifetime, observed state, responsible field, edit, and verification. For example, “one-time export; Job succeeded; web claim Pending; inspect PVC binding; fix the claim or provisioner mismatch; verify Bound and then the served file.” This is more reliable than collecting many unrelated commands. It also makes your answer explainable: a reviewer can see why the selected action follows from the specific event rather than from a memorized symptom label.

### Rehearse the decisions before the timed quiz

The first rehearsal is an image failure that resembles a storage failure from a distance. Imagine a Pod whose status reports `ImagePullBackOff` shortly after it is scheduled. Its manifest also contains an `emptyDir`, but that volume exists independently of registry resolution. Read the event and the image reference before touching the mount. If the event names an unavailable tag, replace that tag with the specifically required existing version. If it names an authentication problem, inspect the referenced image pull Secret and registry address. The correct fix follows the event, not the mere presence of a volume in the YAML.

The second rehearsal starts after a successful image pull. A Job Pod repeatedly exits because the configured executable is wrong. Raising `backoffLimit` may produce more failed attempts, but it cannot repair an invalid command. Inspect the Pod's container state and logs, then compare `command` and `args` with the image's intended `ENTRYPOINT` and `CMD`. Correct the process definition before tuning retries. Once a corrected Job succeeds, verify its completion status and decide whether its output must cross a Pod boundary. The Job's “Complete” condition alone does not establish durable storage.

The third rehearsal is a scheduling problem with a storage consequence. A CronJob runs every hour, and one run can take longer than an hour. `concurrencyPolicy: Forbid` addresses overlap, while history limits control retained Job objects. Neither setting keeps an `emptyDir` from disappearing when a Job Pod is removed. If the next run needs a previous run's file, the design must use a storage source that survives Pod replacement and can be mounted according to its access mode. Schedule, cleanup, and file lifetime are three separate questions, even when one manifest contains all three.

The fourth rehearsal asks you to separate helper roles. A regular init container prepares a configuration file and exits. A native sidecar continues to offer a local service and appears under `initContainers` with `restartPolicy: Always`. An ambassador forwards the app's local calls outward; an adapter transforms app output for another consumer. Choose the role from behavior, then make the communication channel explicit. If two containers exchange files, mount the same volume in both. If they use localhost, check which process listens and which one calls. If process inspection is needed, verify the Pod's shared process namespace setting instead of assuming it from co-location.

The fifth rehearsal concerns a web image with useful files under `/usr/share/nginx/html`. An ordinary ConfigMap volume mounted on that directory hides those image files. A precise `subPath` file mount can preserve neighboring image files but trades away live projected updates for that mounted file. Choose based on the file contract: replace the whole directory with managed content, or add one static file while preserving image defaults. Then inspect the mounted filesystem in the web container. A healthy Pod is insufficient evidence that the intended page is visible.

The final rehearsal is a blocked claim. A web Pod references a PVC that remains unbound. Its `Pending` status is a scheduling and storage clue, while the claim's own events explain why binding has not happened. Verify the claim name, requested capacity, access mode, and available provisioner or volume according to your lab. Do not infer from `ReadWriteOnce` that file writes are locked to one process. When the claim becomes `Bound`, verify the Pod can mount it and read a test file. That sequence proves more than changing the Pod image until the status happens to change.

## Did You Know?

- **Did You Know?** An omitted image tag resolves to the `latest` tag. The word is a registry tag name, so it does not certify that the referenced image is the newest release. [Module 1.1](../module-1.1-container-images/) and the [Kubernetes image guide](https://kubernetes.io/docs/concepts/containers/images/) explain the default and its tradeoff.

- **Did You Know?** CronJob history limits count retained Jobs, while a Job's `ttlSecondsAfterFinished` starts time-based cleanup after the Job finishes. They solve different retention problems, even when both appear in one scheduled workload. See [Module 1.2](../module-1.2-jobs-cronjobs/) and the [Job TTL guide](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/).

- **Did You Know?** In Kubernetes 1.35, a native sidecar is declared under `initContainers` with `restartPolicy: Always`. Unlike a regular init container, it continues running beside the application. See [Module 1.3](../module-1.3-multi-container-pods/) and the [sidecar guide](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/).

- **Did You Know?** An `emptyDir` keeps its files across a container restart within the same Pod, but loses them when that Pod is replaced. See [Module 1.4](../module-1.4-volumes/) and the [volume guide](https://kubernetes.io/docs/concepts/storage/volumes/).

## Common Mistakes

| Mistake | Why it misleads | Better check or design |
|---|---|---|
| Replacing a failed image reference with `latest` | The default tag does not identify the requested release or explain a registry error. | Read Pod events and the image field, then use the required valid reference or credential. |
| Changing `command` when only the default script should change | Kubernetes `command` overrides `ENTRYPOINT`, so the intended executable may disappear. | Keep the executable and change `args` when only `CMD` should change. |
| Running finite work in a Deployment | A successful exit conflicts with the controller's goal of keeping replicas available. | Use a Job once, or a CronJob when the same task needs a schedule. |
| Treating `backoffLimit` as a schedule or cleanup control | It limits retries for failed Job work, not new scheduled runs or retained objects. | Put schedule and history on the CronJob; use Job TTL when time-based cleanup is needed. |
| Making a regular init container run forever | Application containers wait for that init container to complete successfully. | End the setup process, or use a genuine ongoing sidecar pattern when the helper must continue. |
| Defining a Pod volume without mounting it in both collaborators | A volume declaration alone does not create a file path inside every container. | Match the volume name in each required container's `volumeMounts`. |
| Mounting a ConfigMap directory over image defaults | The mount hides existing files at that directory instead of merging with them. | Mount only the intended file when preserving neighbors matters, and account for `subPath` update behavior. |
| Assuming `emptyDir` or `ReadWriteOnce` guarantees durable exclusive data | Pod replacement removes `emptyDir`; node access mode does not lock application files. | Use a bound PVC for data that must survive replacement, and reason separately about writer coordination. |

## Quiz

Attempt these eight scenarios without opening the answers. Allow about 25 minutes, and choose the action that best matches the stated evidence. A score of at least six correct is a useful signal to proceed to the lab; revisit the related source module for every explanation that still feels surprising. The scenarios deliberately combine neighboring concepts so that a plausible Part 1 fix at the wrong layer is still a wrong answer.

### Question 1: Pull failure or process failure?

A Pod intended to use `registry.example.test/team/report:v2` is in `ImagePullBackOff`. Its event says the registry cannot find tag `v2`, and the container never starts. Which next step best addresses the observed failure?

A) Inspect the Pod image field and registry event, then correct the required tag to one confirmed available in that registry.
B) Set Kubernetes `args` to the script name so the image's entrypoint can run after the next restart.
C) Set `imagePullPolicy: Always` so each attempt pulls the same missing tag from the registry again.
D) Mount an `emptyDir` at the application's output directory so the image can start writing files.

<details>
<summary>Answer and reasoning</summary>

**Correct: A.** The image has not arrived, so its reference and the pull event are the relevant evidence because resolution failed before startup. B) changes process arguments only after a pull succeeds. C) requests another pull but cannot make a missing registry tag exist. D) changes file storage after startup and cannot repair image resolution. Confirm the available required version before editing; `latest` is not an evidence-based substitute.

</details>

### Question 2: Keep the image executable

An image declares `ENTRYPOINT ["python"]` and `CMD ["worker.py"]`. A Pod should run `check.py` with the same Python executable, and no image rebuild is allowed. Which Pod-level change preserves that intent?

A) Set `command: ["check.py"]` and leave `args` unset so Kubernetes keeps the image's Python entrypoint.
B) Set `args: ["check.py"]` and leave `command` unset so Kubernetes keeps the image's Python entrypoint.
C) Set `image: python:latest` and leave both process fields unset so the registry chooses the script.
D) Set `command: ["python"]` and leave `args` unset, relying on the image's default arguments.

<details>
<summary>Answer and reasoning</summary>

**Correct: B.** Kubernetes `args` overrides the image's `CMD` while preserving its `ENTRYPOINT`. A) is wrong because `command` overrides `ENTRYPOINT` and attempts to execute `check.py` directly. C) changes the image, not the script argument, and its `latest` tag carries no guarantee about this application. D) is wrong because setting `command: ["python"]` without `args` discards the image's `CMD` as well as its `ENTRYPOINT`, starting bare Python with neither `worker.py` nor `check.py`.

</details>

### Question 3: Choose the lifetime

A team has a script that exits after one successful report export. It must run once now, while a separate HTTP service must remain available. Which controller choice best matches those two lifetimes?

A) Put both the export script and HTTP server in a single Job, because the server can keep the Job active.
B) Put the export script in a Deployment and the HTTP server in a CronJob, because both will restart when needed.
C) Put the export script in a Job and the HTTP server in a Deployment, then verify each controller's own success condition.
D) Put both processes in one CronJob with a one-minute schedule, because repeated exports imply service availability.

<details>
<summary>Answer and reasoning</summary>

**Correct: C.** A Job is for finite work; a Deployment maintains serving replicas because each controller has a different success condition. A) would keep the Job from completing if its server never exits. B) assigns both controllers the opposite lifecycle. D) creates repeated scheduled work, which neither matches a single export nor makes an HTTP service continuously available. If the export later needs a schedule, convert that finite task to a CronJob.

</details>

### Question 4: Control scheduled runs

A CronJob starts an export every hour, but some exports take longer. The team wants no overlap, two recent successful Jobs, and at most two retries for each failing run. Which placement matches those controls?

A) Put `concurrencyPolicy: Forbid`, `successfulJobsHistoryLimit: 2`, and `backoffLimit: 2` all inside the Pod's container spec.
B) Put `backoffLimit: 2` on the CronJob metadata and use `ttlSecondsAfterFinished` to prevent overlap.
C) Put history limits under the container and set `restartPolicy: Always` to make successful runs recur.
D) Put `concurrencyPolicy: Forbid` and `successfulJobsHistoryLimit: 2` on the CronJob, with `backoffLimit: 2` under `jobTemplate.spec`.

<details>
<summary>Answer and reasoning</summary>

**Correct: D.** The CronJob owns schedule overlap and retained Job counts, while each Job template owns its retry limit because each scheduled run is a Job. A) and C) place controller fields in a container where they do not express the requested policy. B) confuses Job TTL, which removes finished Jobs after a delay, with overlap control. The required command for a generated CronJob still follows `--`; that separator does not set any of these fields.

</details>

### Question 5: A helper that must finish

A Pod must write a file before its web container starts. The file can be regenerated whenever a new Pod is created, and it should remain across a web container restart in that same Pod. Which design fits?

A) Use a regular init container to write into a shared `emptyDir`, and mount that volume in the web container.
B) Use a native sidecar with `restartPolicy: Always` to write once, but omit a web-container mount.
C) Use a CronJob to write into its own `emptyDir`, then mount a different `emptyDir` in the web Pod.
D) Use a regular init container that sleeps forever, because the web container can read its private filesystem.

<details>
<summary>Answer and reasoning</summary>

**Correct: A.** The init container completes before the web container starts, and both mounts expose one Pod-scoped volume. B) leaves the web container without the file and gives a continuing lifecycle to one-time work. C) uses two different Pod-scoped volumes, so the web Pod cannot see the Job Pod's data. D) blocks app startup because a regular init container must finish; its private filesystem is not automatically shared.

</details>

### Question 6: Name the helper's direction

An app sends requests to `localhost:5432`; a helper forwards them to an external database endpoint. A second helper reads the app's local metric file and converts it for monitoring. Which pairing describes their roles?

A) The forwarding helper is an adapter, and the metric translator is a regular init container.
B) The forwarding helper is an ambassador, and the metric translator is an adapter.
C) Both helpers are regular init containers because they share the same Pod address.
D) The forwarding helper is a Job, and the metric translator is a CronJob because each handles separate traffic.

<details>
<summary>Answer and reasoning</summary>

**Correct: B.** The ambassador carries the app's local request outward; the adapter transforms the app's output for another consumer. A) reverses the network-facing role and makes continuing translation a one-time init step. C) is wrong because both helpers must keep working while the app runs, regardless of shared localhost. D) substitutes finite and scheduled controllers for ongoing Pod-local helpers.

</details>

### Question 7: Keep image defaults visible

A web image includes several default files under `/usr/share/nginx/html`. A developer mounts a ConfigMap at that entire directory to add one file, and the defaults disappear. The added file rarely changes. Which correction best preserves the defaults?

A) Keep the directory mount but make it read-only so the image defaults stay visible beside the ConfigMap file.
B) Replace the ConfigMap with an `emptyDir` at the same directory, because it merges image files with volume files.
C) Use a precise `subPath` file mount for the added key, and accept that the mounted file will not receive ordinary live ConfigMap updates.
D) Use a `ReadWriteOnce` PVC at the same directory, because node-scoped mounting restores the hidden image files.

<details>
<summary>Answer and reasoning</summary>

**Correct: C.** A directory mount hides existing image files, while a precise file mount can preserve neighboring paths because it targets only the added file. A) makes the volume read-only but still hides the image defaults. B) and D) also mount over the directory and do not merge image defaults. The `subPath` tradeoff matters: choose it only when preserving the directory is worth losing ordinary live projected updates for that file.

</details>

### Question 8: Diagnose the blocked source

A Pod references a PVC and a Secret volume. The PVC is `Pending`, and the Pod has not started. A teammate claims `ReadWriteOnce` will lock the file after startup. Which response best follows the evidence?

A) Fix the Secret volume first, because a Secret mount is the likely reason this Pod has not started.
B) Delete and recreate the Pod so a fresh Pod can retry binding the same pending PVC.
C) Switch the claim to `ReadWriteMany` to settle the concern about concurrent writers and file locking.
D) Inspect PVC status and events for the binding failure; treat `ReadWriteOnce` as node mounting, not a file lock.

<details>
<summary>Answer and reasoning</summary>

**Correct: D.** The unbound PVC blocks the Pod, so claim status and events are the first evidence to inspect because storage binding precedes container startup. `ReadWriteOnce` describes node mounting rather than process-level file locking. A) investigates the Secret before the known pending claim. B) recreates the Pod without diagnosing why that claim cannot bind. C) changes the requested access mode without proving the storage supports it, and `ReadWriteMany` does not provide a file lock either.

</details>

## Hands-On Exercise

Simulation: in a disposable practice namespace, create a one-time Job and a web Pod whose init container prepares content in a shared `emptyDir`. The Job demonstrates finite completion; the web Pod demonstrates ordered preparation and Pod-scoped file sharing. You will inspect each controller or container rather than treating “Running” as proof of the whole design. The commands below require a reachable practice cluster and permission to create Pods and Jobs. Use the complete Pod manifest shown in Core Content as `report-web.yaml` in your working directory.

First, create the one-time report marker Job. The command after `--` is the process the container runs, while the Job controller observes whether it finishes. This Job intentionally does not exchange files with the web Pod; its own filesystem and any Pod-scoped volume would be separate. Confirm that the Job reaches `Complete` before concluding its finite work succeeded. The expected log line is `batch-complete`; actual names and timing depend on the cluster.

```bash
kubectl create job report-once --image=busybox:1.36 -- sh -c 'echo batch-complete'
kubectl wait --for=condition=complete job/report-once --timeout=120s
kubectl logs job/report-once
kubectl describe job report-once
```

Next, save the complete `report-web` Pod YAML from Core Content as `report-web.yaml` and apply it. The init container writes `report.txt` into the named `emptyDir` and exits. The nginx container mounts the same source as its web root. Inspect the init container exit state before reading the file from the web container. This distinguishes successful preparation from a server that simply became Running while showing unrelated image content. If the image is unavailable in your cluster, record the pull event rather than claiming the file handoff ran.

```bash
kubectl apply -f report-web.yaml
kubectl wait --for=condition=Ready pod/report-web --timeout=120s
kubectl get pod report-web
kubectl describe pod report-web
kubectl get pod report-web -o jsonpath='{.status.initContainerStatuses[*].state.terminated.exitCode}'
kubectl exec report-web -c web -- cat /usr/share/nginx/html/report.txt
```

Now make one controlled diagnosis without changing resources. In the Pod manifest, identify the image field that would explain an `ErrImagePull`, the init command whose failure would block the web container, and the two mount entries that must agree on the volume name. Predict what would happen if only the web container restarted: `emptyDir` retains `report.txt` in the same Pod. Predict what would happen if the Pod were deleted and recreated: the old `emptyDir` disappears, and the init container generates a new file. Do not use either event as proof of PVC durability.

If your practice cluster permits it, perform the replacement and verify the file is generated again. Record the old Pod UID before deletion and the new UID afterward, so you can tell a Pod replacement from a container restart. This is a destructive operation only for the disposable lab Pod created above. A new UID and a new init-container completion show that the lifecycle boundary moved; the same file content alone would not prove that the old volume survived.

```bash
kubectl get pod report-web -o jsonpath='{.metadata.uid}'
kubectl delete pod report-web
kubectl apply -f report-web.yaml
kubectl wait --for=condition=Ready pod/report-web --timeout=120s
kubectl get pod report-web -o jsonpath='{.metadata.uid}'
kubectl exec report-web -c web -- cat /usr/share/nginx/html/report.txt
```

Finally, explain the alternative storage decision aloud or in notes. If a future report must remain unchanged after web Pod replacement, which part of this manifest must change? The `emptyDir` source must be replaced by an appropriately bound PersistentVolumeClaim, and both the relevant writer and reader must have access under that storage contract. If the writer is a separate Job Pod, its own `emptyDir` cannot serve as that shared source. Check claim binding and mount events before claiming the new design works; this exercise does not assume a provisioner exists.

**Success Criteria**: Complete the checklist only after you have observed controller completion, init ordering, file visibility, and the Pod replacement boundary in your practice cluster.
- [ ] I can verify the combined workload with focused `kubectl` observations: the Job reaches `Complete`, and its logs show `batch-complete`.
- [ ] The `prepare-report` init container terminates successfully before the `web` container serves its generated file.
- [ ] `kubectl exec report-web -c web -- cat /usr/share/nginx/html/report.txt` shows `report-ready` from the shared volume.
- [ ] A recreated Pod has a new UID, reruns the init container, and shows regenerated content rather than retaining the old `emptyDir`.
- [ ] You can explain why a bound PVC is required when data must outlive Pod replacement, and why `ReadWriteOnce` does not lock files.

Remove only the disposable resources you created for this drill. Deleting the Pod and Job is safe for this isolated scenario, but check the current namespace and names before executing cleanup in a shared practice cluster. The manifest file remains local for another attempt. If any acceptance check fails, keep the resources long enough to inspect their events and container status, then clean up when the cause is understood.

```bash
kubectl delete pod report-web
kubectl delete job report-once
```

## Sources

- [Kubernetes: Images](https://kubernetes.io/docs/concepts/containers/images/)
- [Kubernetes: Define a command and arguments for a container](https://kubernetes.io/docs/tasks/inject-data-application/define-command-argument-container/)
- [Kubernetes: Pull an image from a private registry](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/)
- [Kubernetes: Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes: CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Kubernetes: TTL mechanism for finished Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/)
- [Kubernetes: Init containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
- [Kubernetes: Sidecar containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/)
- [Kubernetes: Volumes](https://kubernetes.io/docs/concepts/storage/volumes/)
- [Kubernetes: Configure a Pod to use a ConfigMap](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/)
- [Kubernetes: Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Kubernetes: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)

## Next Module

Continue to [Module 2.1: Deployments](../../part2-deployment/module-2.1-deployments/) to study how a controller maintains application replicas and manages their updates after the Part 1 design choices are clear.
