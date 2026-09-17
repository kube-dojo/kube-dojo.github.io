---
revision_pending: false
title: "Module 2.4: Jobs & CronJobs"
slug: k8s/cka/part2-workloads-scheduling/module-2.4-jobs-cronjobs
sidebar:
  order: 5
lab:
  id: cka-2.4-jobs-cronjobs
  url: https://killercoda.com/kubedojo/scenario/cka-2.4-jobs-cronjobs
  duration: "30 min"
  difficulty: intermediate
  environment: kubernetes
---
> **Complexity**: `[MEDIUM]` - Long-form batch workload module with hands-on Job and CronJob practice
>
> **Time to Complete**: 30-40 minutes
>
> **Prerequisites**: Module 2.1 (Pods)

---

## What You'll Be Able to Do

After this module, you will be able to:
- **Implement** Jobs and CronJobs with appropriate completions, parallelism, restart policy, and retry settings.
- **Diagnose** failed Jobs by connecting Job status, pod events, container exit behavior, and logs.
- **Configure** CronJob scheduling, concurrency policy, history retention, suspension, and manual triggering for operational use.
- **Compare** Jobs, CronJobs, and Deployments so you can choose the right controller for batch or long-running work.

---

## Why This Module Matters

Hypothetical scenario: you deploy an application update that needs a database migration before the new pods can serve traffic safely. If that migration is packaged as a Deployment, Kubernetes will keep trying to run it forever, and a successful migration may be followed by repeated duplicate attempts. If it is launched by hand from a terminal, the work depends on a human session staying alive and on someone remembering how to inspect failure. A Job gives Kubernetes the right contract: run this task until the requested number of successful completions happens, retry within a controlled budget, and keep enough status behind for debugging.

CronJobs solve the recurring version of the same problem. Backups, report generation, cache refreshes, cleanup routines, certificate checks, and batch imports usually do not need a stable Service address or continuous replicas. They need a schedule, a template for the task, and policy choices for late or overlapping runs. A CronJob wraps those choices around a Job template, so each scheduled execution becomes an ordinary Job with ordinary pods, logs, events, retries, and cleanup behavior.

The CKA exam tends to test this topic through practical work rather than trivia. You may be asked to create a Job imperatively, produce YAML with dry-run output, adjust parallelism, troubleshoot a failed batch task, or trigger a CronJob manually. The deeper skill is recognizing the controller contract: Deployments maintain desired long-running replicas, Jobs pursue successful completion, and CronJobs create Jobs from a calendar-like schedule. Once that contract is clear, the commands and fields become much easier to reason about under time pressure.

---

## Jobs: Completion Is the Desired State

A Job is the Kubernetes controller for finite work. A Pod managed by a Deployment is expected to keep serving until something replaces it, so a clean exit is treated as a problem to heal. A Pod managed by a Job is expected to exit, and the important question is whether enough pods exited successfully. That difference is why Job pods require `restartPolicy: Never` or `restartPolicy: OnFailure`; `Always` would fight the whole idea of completion by restarting containers even after the task has finished.

Think of a Job as a ticket in a maintenance queue rather than a worker assigned to a permanent desk. The Job controller creates one or more pods, observes their phases and exit results, and marks the Job complete when the requested work has succeeded. If a pod fails, the controller decides whether another attempt is still allowed. If the retry budget or deadline is exhausted first, the Job becomes failed and preserves enough state for you to investigate what happened.

That controller relationship also explains why you usually do not create the pod directly for batch work. A standalone pod can run a command and exit, but it has no higher-level object deciding whether another attempt is needed, whether enough attempts have succeeded, or whether the whole operation should now be considered failed. The Job adds that missing intent. It owns the pods through labels and owner references, records status at the controller level, and gives you one stable object to wait on even though the actual pods may come and go.

```text
┌────────────────────────────────────────────────────────────────┐
│                         Job Lifecycle                           │
│                                                                 │
│   Job Created                                                   │
│       │                                                         │
│       ▼                                                         │
│   Pod Created ─────────────────────────────────────────┐       │
│       │                                                │       │
│       ▼                                                │       │
│   Pod Running                                          │       │
│       │                                                │       │
│       ├───► Exit 0 (Success) ──► Job Complete         │       │
│       │                                                │       │
│       └───► Exit ≠ 0 (Fail) ──► Retry? ──────────────►┘       │
│                                  (based on backoffLimit)       │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

The smallest useful Job has a pod template and a restart policy. The example below calculates digits of pi using a container that exits after the command completes. The `backoffLimit` is not a performance setting; it is an error-budget setting for failed attempts. A low value surfaces systematic problems quickly, while a higher value gives transient image pulls, node interruptions, or flaky external dependencies more chances before the Job is considered failed.

The pod template inside a Job should be treated with the same care as any other workload template. Images should be pinned according to your team's release practice, commands should fail clearly when inputs are missing, and environment or volume dependencies should be explicit. A Job makes a task repeatable only if the template is repeatable. If a human has to remember an extra shell variable or manually upload a file before each run, the manifest is not yet a reliable operational tool.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: pi-calculation
spec:
  template:
    spec:
      containers:
      - name: pi
        image: perl
        command: ["perl", "-Mbignum=bpi", "-wle", "print bpi(2000)"]
      restartPolicy: Never    # Required for Jobs
  backoffLimit: 4             # Retry up to 4 times on failure
```

Imperative creation is useful on the exam and during quick operational checks, but you should still understand the YAML it produces. `kubectl create job` creates a one-off Job template from the image and command that follow the `--` delimiter. The dry-run form is especially valuable because it lets you generate a valid starting manifest, add fields such as `completions` or `ttlSecondsAfterFinished`, and then apply the edited version.

```bash
# Create job imperatively
kubectl create job pi --image=perl -- perl -Mbignum=bpi -wle "print bpi(100)"

# Generate YAML
kubectl create job pi --image=perl --dry-run=client -o yaml -- perl -Mbignum=bpi -wle "print bpi(100)"
```

The everyday inspection commands follow the same pattern you already know from pods and Deployments: list the controller, describe it for conditions and events, then read logs from the pod or through the Job shortcut. `kubectl logs job/pi-calculation` is convenient when there is a clear pod to select, but during failures you often want the actual pod names as well. Failed pods can remain after the Job stops retrying, and those old pods are often the most useful evidence.

There is a useful discipline here: inspect from the outside inward. The Job tells you whether the controller thinks the desired state was reached. The pods tell you how many attempts happened and which phases they reached. The containers tell you the application-level reason for success or failure. If you start directly with container logs, you may miss a scheduling failure, a deadline, or a retry limit that explains why the logs are incomplete.

```bash
# List jobs
kubectl get jobs

# Watch job progress
kubectl get jobs -w

# Describe job
kubectl describe job pi-calculation

# Get job logs
kubectl logs job/pi-calculation

# Delete job (also deletes pods)
kubectl delete job pi-calculation
```

Pause and predict: A Job has `restartPolicy: Never` and `backoffLimit: 4`. The container fails on every attempt. Before reading further, what do you expect to see in `kubectl get pods` after the Job gives up, and how would that differ from `restartPolicy: OnFailure`?

The answer depends on where the retry happens. With `Never`, Kubernetes normally creates a fresh pod for each failed attempt, so the original failed pod remains visible and additional failed pods appear until the Job reaches its limit. With `OnFailure`, the kubelet restarts the container inside the same pod, so the evidence is concentrated in the pod's restart count and previous logs. Both policies can be correct, but `Never` is often easier to teach and inspect because each attempt is a separate object.

```yaml
spec:
  template:
    spec:
      restartPolicy: Never      # New pod per failure
      # restartPolicy: OnFailure  # Restart same pod
```

| Policy | Behavior |
|--------|----------|
| `Never` | Usually create a new pod after failure |
| `OnFailure` | Restart container in same pod on failure |

The most common beginner mistake is treating `backoffLimit` as a guarantee about exactly how many pods will exist. It is safer to treat it as controller policy, then inspect status and events to see what actually happened. Pod replacement, container restart behavior, deadlines, and controller timing can all affect what you observe at a specific moment. For the exam, the practical lesson is simpler: set an intentional retry budget, know which restart policy you chose, and use pod logs plus Job conditions to confirm the result.

Another practical detail is naming. Job names become part of generated pod names and labels, so short descriptive names help during troubleshooting. A name like `backup` or `report-daily` is easier to filter than a long sentence encoded with punctuation. For manual reruns, choose unique names because Kubernetes object names are namespace-scoped. If you reuse a name while an old Job still exists, the API will reject the create request and the delay can cost precious exam minutes.

## Completions, Parallelism, and Work Shape

Many Jobs are not just "run one pod once." A batch import may have one hundred independent files, a report generator may need five shards, and a data repair may need several workers to pull from a queue. Kubernetes gives you two important knobs for this shape: `completions`, which says how many successful pod completions are required, and `parallelism`, which says how many pods may run at the same time. The controller keeps creating replacement pods until the success target is reached or failure policy stops the Job.

These knobs are separate because they answer separate questions. `completions` answers "how many successful units of work make this Job done?" while `parallelism` answers "how much work may happen at once?" A restaurant analogy is useful: one hundred meal tickets might need to be cooked, but only six burners are available. Printing more tickets does not add burners, and lighting more burners does not reduce the number of meals owed. Jobs use the same distinction for batch pods.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: batch-job
spec:
  completions: 5          # Job succeeds when 5 pods complete successfully
  parallelism: 2          # Run 2 pods at a time
  template:
    spec:
      containers:
      - name: worker
        image: busybox
        command: ["sh", "-c", "echo Processing item; sleep 5"]
      restartPolicy: Never
```

The relationship between completions and parallelism is easy to visualize as a set of lanes. If `completions` is five and `parallelism` is two, Kubernetes can keep two pods active, but it still needs five successful exits before the Job is complete. A failed pod does not count toward the successful completions, so the controller creates another attempt if failure policy still allows it. This model helps you avoid the mistake of setting parallelism high and assuming that means the task is done faster no matter what the work actually does.

```text
┌────────────────────────────────────────────────────────────────┐
│              Completions=5, Parallelism=2                       │
│                                                                 │
│   Time ─────────────────────────────────────────────────►      │
│                                                                 │
│   Slot 1: [Pod 1 ✓] [Pod 3 ✓] [Pod 5 ✓]                        │
│   Slot 2: [Pod 2 ✓] [Pod 4 ✓]                                  │
│                                                                 │
│   2 pods run concurrently, until 5 completions achieved        │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

| Pattern | completions | parallelism | Behavior |
|---------|-------------|-------------|----------|
| Single pod | 1 (default) | 1 (default) | One pod runs to completion |
| Fixed completions | N | M | M pods run in parallel until N succeed |
| Work queue | unset | N | N pods run until one succeeds |

Parallelism only helps when the task can be safely split. If every pod writes the same output file, migrates the same schema row, or consumes an API that cannot handle bursts, increasing `parallelism` can turn a batch job into a race condition. If each pod processes an independent shard or pulls distinct work from a queue, parallelism is the right scaling lever. The Job controller does not understand your business idempotency rules, so the pod command and backing system must make duplicate or replacement attempts safe.

In cluster operations, parallelism also competes with quota and scheduling capacity. A namespace may have enough CPU for two workers but not ten, and a cluster may delay pods if every worker requests a large amount of memory. When a Job appears slower than expected, do not assume the controller ignored `parallelism`. Check pod events for pending scheduling, resource quota errors, image pull delay, and node pressure. The Job can request concurrency, but the scheduler still decides where each pod can actually run.

```bash
# Scale parallelism of an existing job (completions is immutable)
kubectl create job batch --image=busybox -- sh -c "echo done; sleep 30"
kubectl patch job batch -p '{"spec":{"parallelism":3}}'

# Or create with YAML
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: parallel-job
spec:
  completions: 10
  parallelism: 3
  template:
    spec:
      containers:
      - name: worker
        image: busybox
        command: ["sh", "-c", "echo Task complete; sleep 2"]
      restartPolicy: Never
EOF

# Wait for completion
kubectl wait --for=condition=complete job/parallel-job --timeout=90s
kubectl get jobs parallel-job
```

Notice the comment in that command block: `completions` is effectively part of the Job's work contract, so you normally choose it before creation. `parallelism` is a safer runtime adjustment because it controls how many workers are allowed at once. During an incident, reducing parallelism can slow a noisy batch task without deleting the Job, while increasing it can help drain a safe backlog. The skill is not memorizing mutability; it is recognizing whether you are changing the amount of work or only the rate of work.

Work-queue style Jobs deserve special caution because the queue, not the Job, decides which item each pod processes. That can be a powerful design when workers claim items atomically and mark them complete in an external system. It can also be confusing during an exam because the manifest alone does not show the number of items waiting in the queue. For CKA-style tasks, fixed completions are usually easier to reason about unless the prompt explicitly describes a queue-based workload.

For more advanced batch designs, Kubernetes also supports indexed Jobs, where each pod receives a completion index. That pattern is useful when worker `0` should process shard `0`, worker `1` should process shard `1`, and so on. You do not need indexed Jobs for the basic CKA tasks in this module, but knowing they exist helps you explain why plain Jobs are intentionally simple. Start with ordinary completions and parallelism, then reach for indexes only when the work requires stable per-completion identity.

If you are designing a real batch platform, decide where progress is recorded before choosing the Job shape. Fixed completions record progress in Kubernetes by counting successful pods, while queue workers usually record progress in the queue or database. Indexed Jobs split the difference by giving Kubernetes a stable index for each completion, but the application still needs to map that index to meaningful work. The cleanest design is the one where a failed pod can be retried without an operator guessing what it already changed.

Before running this, what output do you expect from a Job with `completions: 10`, `parallelism: 3`, and a command that sleeps for two seconds? You should expect no more than three pods active at the same time, several completed pods over the lifetime of the Job, and a final Job status of `10/10` once all successful completions are counted. If your cluster creates fewer active pods, look for scheduling constraints, image pull delay, namespace quota, or a lower parallelism value than you intended.

## Failure Handling, Deadlines, and Debugging Evidence

Failure handling is where Jobs become operationally interesting. A batch task can fail because the image cannot be pulled, the command exits nonzero, a ConfigMap is missing, a node disappears, a deadline is exceeded, or an external dependency refuses traffic. The Job controller does not solve those application problems for you, but it does give you a structured place to look: Job conditions tell you whether the controller considers the work complete or failed, pods tell you what happened during each attempt, and events explain scheduling or image-level problems.

A good failure policy begins with the expected failure mode. If a command is wrong, more retries only repeat the same mistake and fill the namespace with failed pods. If a remote API sometimes returns a temporary error, a few retries may be exactly what you want. If a node interruption kills a pod, replacement is reasonable as long as the task can resume safely. The manifest should express those expectations rather than copying a retry value from another workload.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: failing-job
spec:
  backoffLimit: 3           # Retry 3 times, then fail
  template:
    spec:
      containers:
      - name: fail
        image: busybox
        command: ["sh", "-c", "exit 1"]  # Always fails
      restartPolicy: Never
```

`backoffLimit` is the first guardrail because it stops a broken task from creating attempts forever. Set it low when failure is likely to be deterministic, such as a bad command, missing file, or invalid argument. Set it higher when transient failures are expected and the task is idempotent. The value is not a substitute for alerting or log inspection; it is a controller-level decision about when Kubernetes should stop spending cluster capacity on attempts that are not succeeding.

The backoff behavior also affects how fast you see the final failed condition. Kubernetes does not necessarily retry in a tight loop; controllers use backoff patterns to avoid hammering the cluster with immediate replacements. That means a Job with several allowed failures can take longer to fail than the container runtime alone would suggest. During troubleshooting, watch both the Job and its pods so you can distinguish "still retrying" from "stuck because no pod can be scheduled."

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: timeout-job
spec:
  activeDeadlineSeconds: 60    # Kill job after 60 seconds
  template:
    spec:
      containers:
      - name: long-task
        image: busybox
        command: ["sleep", "120"]  # Tries to run 2 minutes
      restartPolicy: Never
```

`activeDeadlineSeconds` is a different kind of protection. It puts a wall-clock limit on the Job, so even a retry budget that has not been exhausted cannot keep the Job alive past the deadline. This is useful when a task is only valuable within a time window, such as a report that must finish before business hours or a cleanup routine that should never run into the next maintenance window. If both a backoff limit and a deadline exist, whichever stopping condition becomes true first determines the outcome.

Deadlines are especially important for CronJobs because scheduled work can pile up conceptually even when objects are not overlapping. A daily task that normally takes ten minutes but suddenly runs for hours may still be active when the next operational window begins. A deadline forces the task to declare failure instead of silently consuming time. Pair it with useful logs and alerts, because a deadline without evidence only tells you that time ran out, not why the task could not finish.

Pause and predict: A Job with `activeDeadlineSeconds: 60` and `backoffLimit: 10` runs a container that takes fifteen seconds per attempt and always fails. Which guardrail should you expect to matter first, and what extra delay might make the exact number of pods different from a simple arithmetic estimate?

The right prediction starts with the deadline, not the retry count. Four fifteen-second attempts already consume the whole minute before you account for scheduling time, image startup, backoff delay, and controller reconciliation. In a real cluster you should not promise an exact pod count from the manifest alone. You should inspect the Job condition, list pods by `job-name`, and read events to confirm whether the controller stopped because it hit the deadline, the backoff limit, or another failure mode.

```bash
# Job status
kubectl get job myjob
# NAME    COMPLETIONS   DURATION   AGE
# myjob   3/5           2m         5m

# Detailed status
kubectl describe job myjob | grep -A5 "Pods Statuses"

# Check failed pods
kubectl get pods -l job-name=myjob --field-selector=status.phase=Failed
```

| Issue | Symptom | Debug Command |
|-------|---------|---------------|
| Image pull failure | Pod in ImagePullBackOff | `kubectl describe pod <pod>` |
| Command failure | Job may not complete successfully | `kubectl logs job/<job-name>` |
| Timeout | Job killed | Check `activeDeadlineSeconds` |
| Too many retries | Multiple failed pods | Check `backoffLimit` |

The debugging workflow should move from controller to pod to container output. Start with `kubectl get job` because it tells you the completion count and high-level condition. Use `kubectl describe job` because it collects controller events, pod status counts, and failure messages. Then list pods with the `job-name` label, because a failed Job may have several pods and the most recent one is not always the one with the clearest evidence.

```bash
# 1. Check job status
kubectl get job myjob
kubectl describe job myjob

# 2. Find pods created by job
kubectl get pods -l job-name=myjob

# 3. Check pod logs
kubectl logs <pod-name>
kubectl logs job/myjob  # Auto-selects a pod

# 4. If still running, exec into pod
kubectl exec -it <pod-name> -- /bin/sh

# 5. Check events
kubectl get events --field-selector involvedObject.name=myjob
```

Logs are necessary but not sufficient. An image pull failure may have no application logs because the container never started, while a node scheduling problem may only appear in events. A command that exits quickly can leave a pod in `Error` with useful logs, but an `OnFailure` restart policy may require `kubectl logs --previous` on the pod to read the last failed container attempt. Good Job debugging is therefore a sequence: controller status, pods by label, pod description, logs, and events.

The label selector is your friend when generated pod names are hard to remember. Jobs automatically label their pods with the Job name, so `kubectl get pods -l job-name=myjob` gives you the attempt set without copying long pod names from memory. This is also why deleting or relabeling pods by hand can make debugging harder. Let the controller own the objects, and use labels to observe the relationship Kubernetes already maintains for you.

When cleanup matters, prefer `ttlSecondsAfterFinished` over manual habits. Finished Jobs and their pods remain by default so you can inspect them, but a busy namespace can accumulate many completed objects. The TTL controller can delete finished Jobs after a chosen number of seconds, which also removes their dependent pods. Use it after you are confident that logs are shipped somewhere durable or that the completed pod evidence is no longer needed for normal troubleshooting.

Cleanup policy is an observability tradeoff, not just housekeeping. Keeping every finished Job forever makes `kubectl get jobs` noisy and can slow down human diagnosis during an incident. Deleting immediately keeps the namespace tidy but removes convenient access to pod logs and status. A balanced approach keeps enough recent history for normal questions and sends important logs to a durable system. In an exam namespace, manual cleanup is fine; in a production namespace, make cleanup intentional.

## CronJobs: Scheduling Jobs Without Hiding the Job

A CronJob is a schedule plus a Job template. At each scheduled time, the CronJob controller creates a Job, and that Job creates pods exactly like the one-time Jobs you have already inspected. This layering is important because it prevents debugging confusion. If the schedule did not fire, inspect the CronJob. If a scheduled run fired but the work failed, inspect the Job and pods created for that run. The CronJob decides when to create work; the Job decides whether that work completed.

The generated Jobs are ordinary Kubernetes Jobs, which means your existing Job skills still apply. You can describe them, wait for completion, inspect their pods, and read their logs. The main difference is ownership and naming: the CronJob owns the schedule and creates Jobs with generated names. When you are debugging, keep the parent-child chain clear in your notes: CronJob schedule, generated Job, generated pod, container command.

```text
┌────────────────────────────────────────────────────────────────┐
│                        CronJob                                  │
│                                                                 │
│   Schedule: "0 * * * *" (hourly)                               │
│                                                                 │
│   1:00 ──► Creates Job ──► Creates Pod ──► Completes          │
│   2:00 ──► Creates Job ──► Creates Pod ──► Completes          │
│   3:00 ──► Creates Job ──► Creates Pod ──► Completes          │
│   ...                                                           │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

Kubernetes CronJob schedules use the familiar five-field cron format. The leftmost field is minute, then hour, day of month, month, and day of week. This ordering is a classic source of mistakes because humans often say "two in the morning" first, but cron writes the minute before the hour. When you read `0 2 * * *`, translate it out loud as "minute zero, hour two, every day." That habit catches many schedule errors before they reach the cluster.

Schedules also need to be realistic about task duration. A schedule of every minute is excellent for a lab because you can see a run quickly, but it is rarely appropriate for expensive work. If a task routinely takes eight minutes, a five-minute schedule forces you to make a concurrency decision every run. Sometimes the correct fix is not `Forbid` or `Replace`; it is changing the schedule interval so the task has enough time to complete under normal conditions.

```text
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday = 0)
│ │ │ │ │
* * * * *
```

| Schedule | Description |
|----------|-------------|
| `* * * * *` | Every minute |
| `0 * * * *` | Every hour |
| `0 0 * * *` | Every day at midnight |
| `0 0 * * 0` | Every Sunday at midnight |
| `*/5 * * * *` | Every 5 minutes |
| `0 9-17 * * 1-5` | Every hour 9-17, Mon-Fri |

In Kubernetes 1.35, you should also be aware of CronJob time zones. The `timeZone` field lets you specify a named time zone for schedule interpretation, while older clusters often depended on the controller-manager's local time. For portable exam work, UTC-style reasoning is safest unless the task explicitly asks for a time zone. For production work, specify the time zone when local business time matters, because daylight-saving changes and controller configuration should not be left to guesswork.

Another schedule-related field, `startingDeadlineSeconds`, controls how late a CronJob run may start before Kubernetes counts it as missed. This matters when the controller is down, the cluster is overloaded, or scheduling is delayed beyond the useful window for the task. A backup might still be valuable if it starts ten minutes late, while a market-open report may be useless after the meeting begins. The field turns that operational judgment into controller policy.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup
spec:
  schedule: "0 2 * * *"           # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: busybox
            command: ["sh", "-c", "echo Backup started; sleep 10; echo Backup done"]
          restartPolicy: OnFailure
  successfulJobsHistoryLimit: 3   # Keep 3 successful job records
  failedJobsHistoryLimit: 1       # Keep 1 failed job record
```

The `jobTemplate` section is the part many learners rush past. It is not a pod template directly under the CronJob; it is a Job template, which then contains the pod template. That nesting is why history limits, concurrency policy, and suspension belong to the CronJob, while restart policy and container command belong under the Job's pod template. If a manifest is rejected, check indentation and field placement before assuming the API object is unavailable.

When editing CronJob YAML under pressure, read the indentation like a path. `spec.schedule` belongs to the CronJob. `spec.jobTemplate.spec.template.spec.containers` belongs to the pod that the generated Job will create. A misplaced field may either be rejected or silently fail to do what you intended because it is sitting under the wrong object. This is one reason dry-run output is useful: it gives you the correct scaffold before you add policy fields.

```bash
# Create CronJob imperatively
kubectl create cronjob backup --image=busybox --schedule="0 2 * * *" -- sh -c "echo Backup done"

# Generate YAML
kubectl create cronjob backup --image=busybox --schedule="*/5 * * * *" --dry-run=client -o yaml -- echo "hello"
```

The basic commands mirror other controllers. `kubectl get cronjobs` shows schedule, suspension, active runs, and last schedule time. `kubectl describe cronjob` gives events and the generated Job template. A manual trigger with `kubectl create job --from=cronjob/name` is one of the most useful operational commands because it lets you run the exact scheduled template immediately without waiting for the next cron tick.

Manual triggering is also safer than copying the container command into an ad hoc pod. If the CronJob template includes environment variables, service account settings, volumes, security context, or image pull secrets, `--from=cronjob/name` preserves those details. The manual Job still needs its own name, and it will not change the CronJob's next scheduled run. Treat it as a one-time execution of the same template, not as a schedule modification.

```bash
# List CronJobs
kubectl get cronjobs
kubectl get cj           # Short form

# Describe
kubectl describe cronjob backup

# Manually trigger a job from CronJob
kubectl create job --from=cronjob/backup backup-manual

# Suspend CronJob
kubectl patch cronjob backup -p '{"spec":{"suspend":true}}'

# Resume CronJob
kubectl patch cronjob backup -p '{"spec":{"suspend":false}}'

# Delete CronJob (also deletes Jobs it created)
kubectl delete cronjob backup
```

Stop and think: You have a CronJob that runs a database backup every hour, but sometimes the backup takes ninety minutes. With the default `concurrencyPolicy: Allow`, two backup jobs may overlap. What could go wrong with concurrent backups, and which concurrency policy would you choose instead?

Overlap is not automatically wrong, but it is dangerous when the task touches shared state. Two backups may compete for disk bandwidth, hold locks longer than expected, upload the same object name, or capture inconsistent snapshots. `Forbid` is usually the conservative choice for backups because it skips a new run while the previous one is still active. `Replace` is better for tasks where the newest run is more valuable than finishing stale work, such as a cache refresh that can be safely restarted.

```yaml
spec:
  concurrencyPolicy: Allow    # Default - allow concurrent jobs
  # concurrencyPolicy: Forbid   # Skip if previous still running
  # concurrencyPolicy: Replace  # Kill previous, start new
```

| Policy | Behavior |
|--------|----------|
| `Allow` | Multiple Jobs can run simultaneously |
| `Forbid` | Skip new Job if previous still running |
| `Replace` | Kill running Job, start new one |

History limits are the cleanup companion to concurrency policy. `successfulJobsHistoryLimit` and `failedJobsHistoryLimit` decide how many completed Job objects the CronJob keeps around. Keeping a few successful records helps you confirm normal operation, and keeping failed records gives you evidence when an alert fires. Keeping too many records creates clutter, while keeping none can make root cause analysis harder unless logs and events are captured somewhere else.

The history values should match how often the CronJob runs and how quickly someone would notice a problem. Keeping three successful runs for a daily backup gives you several days of visible confirmation. Keeping three successful runs for a minute-level task only shows a few minutes of history. For failed runs, keeping at least one is often worth the small object cost because it preserves the exact Job that failed, including pod labels and events.

Suspension is another operational control that belongs in your mental model. Setting `spec.suspend: true` pauses future schedule executions, but it does not necessarily delete Jobs that already exist. This makes it useful during maintenance windows when you want to stop new batch work without changing the Job template. When you resume the CronJob, check the next scheduled time and watch the generated Jobs rather than assuming the missed work will behave exactly like a queue.

Suspension is not a rollback mechanism. If a bad template has already produced a bad Job, suspending the CronJob prevents new scheduled Jobs but does not repair the failed one. You still need to inspect or delete the generated Job, fix the template, and decide whether a manual run is needed. This distinction is useful in incident response because it separates stopping future damage from cleaning up current evidence.

## Patterns & Anti-Patterns

The strongest pattern for Jobs is to make the task idempotent before you make it parallel. Idempotency means a retry or duplicate attempt does not corrupt the system: an import can skip rows already processed, a backup can write to a unique object path, and a migration can record which version has already applied. Kubernetes can retry containers and replace pods, but it cannot know whether your command is safe to run twice. That safety has to be designed into the workload.

Another durable pattern is to keep the batch command boring. Complex orchestration hidden inside a shell one-liner is hard to quote correctly, hard to test, and hard to read in a manifest. Put substantial logic in an image, script, or application that has its own tests, then let the Job manifest describe how Kubernetes should run it. The manifest should clarify controller behavior, resource needs, and policy choices rather than becoming a fragile programming language.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| One-shot Job | Migrations, reports, one-time checks | Completion is explicit and inspectable | Keep `backoffLimit` low when failure is deterministic |
| Fixed-completion Job | Known number of shards or files | `completions` states the success target | Tune `parallelism` to capacity and external limits |
| CronJob with `Forbid` | Backups or cleanup that must not overlap | Skips unsafe concurrent runs | Monitor skipped schedules and adjust duration or interval |
| CronJob with manual trigger | Emergency rerun or validation | Reuses the exact scheduled template | Use unique Job names for each manual run |

The most harmful anti-pattern is using a Deployment for finite work because it "already runs containers." A Deployment will keep reconciling replicas, so a command that exits successfully can be restarted as if it failed. Another common anti-pattern is putting complex scheduling logic inside a long-running pod while ignoring CronJob policy. That hides schedule state from Kubernetes and makes failures look like application behavior rather than controller behavior.

Teams also get into trouble when they treat CronJobs as invisible background chores. A scheduled task can be just as critical as a user-facing service, especially when it handles backups, billing exports, or cleanup that protects cluster capacity. Give important CronJobs clear names, intentional history, alerts on failure or excessive duration, and documented manual trigger steps. The fact that a task is scheduled does not make it self-operating.

| Anti-pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| Deployment for a migration | Successful exit gets restarted or treated as unhealthy | Use a Job with a clear retry budget |
| High parallelism without idempotency | Duplicate writes, lock contention, or inconsistent output | Prove safe retries, then scale concurrency |
| CronJob `Allow` for shared state | Scheduled runs overlap and compete | Use `Forbid` or lengthen the schedule interval |
| Zero retained history without log shipping | Debug evidence disappears too quickly | Keep limited history or centralize logs first |

Exercise scenario: you own a nightly cleanup that deletes expired records and sometimes runs longer than usual. A good design starts with the data operation, not the manifest. If deleting the same expired record twice is harmless, retries are safe. If two workers may scan the same range and fight over locks, reduce parallelism or partition the work. If the cleanup must not overlap with tomorrow's run, set `concurrencyPolicy: Forbid` and alert when a run takes longer than its schedule interval.

For exam readiness, practice translating a sentence into the controller and fields before touching the keyboard. "Run this once and retry twice" points to a Job with `backoffLimit`. "Run ten units with three workers" points to `completions` and `parallelism`. "Run every day but never overlap" points to a CronJob schedule plus `concurrencyPolicy: Forbid`. That translation step reduces syntax mistakes because the manifest is now an expression of a decision you already made.

## Decision Framework

Choose the controller by asking what "healthy" means. If healthy means "the process keeps serving," use a Deployment or another long-running workload controller. If healthy means "the task reached a successful exit a certain number of times," use a Job. If healthy means "that Job template should be created on a schedule," use a CronJob. This framing is more reliable than choosing based on image, command length, or whether the task is important.

The next question is how much evidence you need after the work finishes. A one-time diagnostic Job in a lab can be deleted immediately after you read its logs. A production payroll export might need retained Job status, centralized logs, and a manual rerun procedure. A frequent cleanup CronJob might need aggressive history limits to keep the namespace readable. The controller choice starts the design, but evidence retention makes the design operable.

| Need | Use | Key Fields | Operational Question |
|------|-----|------------|----------------------|
| Run a command once | Job | `restartPolicy`, `backoffLimit` | How many failed attempts are acceptable? |
| Run several independent units | Job | `completions`, `parallelism` | Can the work be safely retried or duplicated? |
| Run on a calendar | CronJob | `schedule`, `jobTemplate` | What time zone and history policy should apply? |
| Avoid overlapping scheduled work | CronJob | `concurrencyPolicy: Forbid` | Is skipping safer than overlap? |
| Prefer newest scheduled work | CronJob | `concurrencyPolicy: Replace` | Is terminating old work acceptable? |
| Keep a service running | Deployment | `replicas`, probes, rollout fields | Should a clean process exit be restarted? |

Which approach would you choose here and why? A report must run every weekday morning, but analysts also need to rerun it manually after correcting input data. The scheduled part belongs in a CronJob, and the rerun should be a manual Job created from that CronJob template. That choice keeps the report definition in one place, makes manual execution auditable as a Job, and avoids copying a long command into a shell session during a stressful morning.

When the decision is close, look at cleanup and observability. Jobs and CronJobs leave Kubernetes objects that explain whether batch work completed, failed, overlapped, or was suspended. Deployments leave rollout and replica state, which is excellent for services but awkward for completed tasks. A shell command launched from your laptop leaves almost nothing in cluster state. On the exam and in production, prefer the controller that makes the desired state visible to Kubernetes.

Finally, check whether the workload needs a stable network identity. Jobs and CronJobs usually do not sit behind Services because clients are not supposed to call them continuously. If other systems need to submit work, you may need a long-running service that writes to a queue and a Job-style worker that drains it. Kubernetes controllers are building blocks, not labels for importance. The right architecture often combines a Deployment for request handling with Jobs or CronJobs for finite background execution.

## Did You Know?

- Kubernetes CronJobs graduated to the stable `batch/v1` API in Kubernetes 1.21, replacing the older beta API path.
- CronJob time zone support is stable in modern Kubernetes, and Kubernetes 1.35 continues to support `.spec.timeZone` for named time zones.
- Finished Jobs are not automatically deleted by default; `ttlSecondsAfterFinished` delegates cleanup to the TTL-after-finished controller.
- Indexed Jobs can assign each completion a stable index, which is useful for shard-oriented batch work where pod identity matters.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Using `restartPolicy: Always` | The learner copies a Deployment-style pod template into a Job | Use `Never` or `OnFailure`, then decide where failed attempts should be visible |
| Forgetting `backoffLimit` | The task looks simple, so retry behavior is left implicit | Set a retry budget that matches whether failure is transient or deterministic |
| Treating `parallelism` as a success target | The name sounds like "number of tasks" | Use `completions` for required successes and `parallelism` for concurrent workers |
| Using CronJob `Allow` for backups | The default is accepted without considering runtime length | Use `Forbid` when overlap can corrupt output or overload shared systems |
| Checking only `kubectl logs job/name` | The shortcut hides which pod supplied the logs | List pods by `job-name`, then inspect the specific failed pod and its events |
| Putting CronJob fields inside `jobTemplate.spec.template` | The nested Job and pod templates are easy to confuse | Keep schedule, suspension, concurrency, and history on the CronJob spec |
| Deleting failed Jobs before reading evidence | Cleanup feels like progress during an incident | Describe the Job, list pods, capture logs, and review events before deletion |

## Quiz

<details>
<summary>Question 1: A developer creates a Job with `restartPolicy: Always`, and the API rejects it. They say retrying should mean restarting forever. How do you explain the rejection, and which restart policy would you choose for easy failure inspection?</summary>

`restartPolicy: Always` is invalid for a Job because a Job needs pod termination to represent progress toward completion or failure. A container that always restarts can never clearly say "this task finished successfully." For easy failure inspection, choose `Never` because each failed attempt normally leaves a separate failed pod with its own status and logs. `OnFailure` can still be valid, but it restarts the container in the same pod, so you may need restart counts and previous logs to understand repeated failures.

</details>

<details>
<summary>Question 2: Your data pipeline needs to process one hundred independent objects, and each object takes about thirty seconds. You want to finish in under ten minutes without overwhelming the backing API. What `completions` and `parallelism` would you start with, and what happens if one pod fails?</summary>

Use `completions: 100` because the success target is one hundred completed units of work. A starting `parallelism` of six or eight is reasonable if the backing API can handle that many concurrent workers; it should finish under ten minutes while leaving room for scheduling overhead. If a pod fails, that failed attempt does not count toward the one hundred completions, and the Job controller creates another attempt if the retry budget allows it. The application still must make retries safe, because Kubernetes cannot prevent duplicate side effects inside your business logic.

</details>

<details>
<summary>Question 3: It is early morning and a backup CronJob with schedule `0 2 * * *` shows `LAST SCHEDULE: <none>`. How do you investigate the schedule problem, and how do you run the backup immediately while you continue debugging?</summary>

First inspect the CronJob rather than the pod layer, because no scheduled Job appears to have been created. Check whether `spec.suspend` is true, verify the cron expression, confirm the expected time zone, and read `kubectl describe cronjob backup` for controller events. To run the backup immediately, create a Job from the CronJob template with `kubectl create job --from=cronjob/backup backup-manual`. That manual Job gives you normal Job status and logs while preserving the scheduled template for the root-cause fix.

</details>

<details>
<summary>Question 4: A metrics aggregation CronJob runs every five minutes, but some runs take seven minutes. With `Allow`, you see duplicate data. You switch to `Forbid`, and now some schedules are skipped. How do you evaluate `Forbid` versus `Replace`?</summary>

`Forbid` prevents overlap by skipping a new scheduled run when the prior Job is still active, so it protects shared state but can miss schedule ticks. `Replace` terminates the active Job and starts a new one, so it favors the newest run but discards work already in progress. For metrics aggregation, `Forbid` is usually safer if each long run eventually covers its intended interval. The better long-term fix is to shorten the task, increase the interval, or make aggregation idempotent enough that overlap no longer creates duplicates.

</details>

<details>
<summary>Question 5: A Job is marked failed, and `kubectl logs job/import` shows only a short error from one pod. The team wants to delete and recreate it. What should you inspect before deletion, and why?</summary>

List the pods with `kubectl get pods -l job-name=import` so you can see every attempt, not just the pod selected by the logs shortcut. Describe the Job to read conditions, retry counts, and controller events, then describe failed pods for image, scheduling, volume, and command details. If containers restarted in place, check previous logs on the pod as well. Deleting the Job removes dependent pods, so capturing evidence first prevents you from erasing the information needed to fix the manifest or command.

</details>

<details>
<summary>Question 6: A cleanup task currently runs as a Deployment with one replica. The container deletes old records and exits zero, then Kubernetes starts it again. Compare the controller choices and propose a safer design.</summary>

A Deployment is wrong because its desired state is a continuously running replica, so a clean exit causes reconciliation rather than completion. A Job is the right controller if the cleanup should run once on demand, because success is represented by completed pod exits. A CronJob is the right controller if the cleanup should run on a schedule, because it creates Jobs from a template and lets you configure overlap and history. The safer design is a CronJob with an idempotent cleanup command, an intentional retry budget, and `Forbid` if overlapping deletes could compete for locks.

</details>

## Hands-On Exercise

Exercise scenario: you are preparing a namespace for batch workload practice. You will create a simple Job, scale completions and parallelism, observe a controlled failure, create a scheduled CronJob, and manually trigger a scheduled template. Keep the objects small so the exercise works on a local or training cluster, and delete each object after inspection so later steps are easy to read.

```bash
kubectl create namespace jobs-lab
kubectl config set-context --current --namespace=jobs-lab
```

### Task 1: Create and inspect a simple Job

This first task proves the basic lifecycle. Create a Job that prints a message, wait for it to complete, read its logs, and delete it. The important observation is that completion is the desired state, so a pod that exits zero is success rather than a crash loop.

```bash
kubectl create job hello --image=busybox -- echo "Hello from job"
kubectl wait --for=condition=complete job/hello --timeout=60s
kubectl get jobs
kubectl logs job/hello
kubectl delete job hello
```

<details>
<summary>Solution notes</summary>

The Job should reach `complete` quickly, and `kubectl logs job/hello` should print the message from the container. If the wait command times out, describe the Job and pod before deleting anything. The most likely training-cluster causes are image pull delay, namespace quota, or a command typo.

</details>

### Task 2: Create a Job with completions and parallelism

Now create a Job that requires five successful completions while running two pods at a time. Watch the pods briefly and confirm that successful completions accumulate until the Job reaches the target. This is the smallest practical example of separating "how much work" from "how many workers at once."

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: batch-processor
spec:
  completions: 5
  parallelism: 2
  template:
    spec:
      containers:
      - name: processor
        image: busybox
        command: ["sh", "-c", "echo Processing $(hostname); sleep 3"]
      restartPolicy: Never
EOF

kubectl wait --for=condition=complete job/batch-processor --timeout=90s
kubectl get jobs batch-processor
kubectl get pods -l job-name=batch-processor
kubectl delete job batch-processor
```

<details>
<summary>Solution notes</summary>

You should see five successful completions over the lifetime of the Job, but no more than two active pods at the same time. If you only see one pod at a time, recheck `parallelism` and then inspect scheduling events. If the Job completes but pods remain, that is normal; Jobs preserve pods for inspection until the Job is deleted or a TTL cleanup policy removes them.

</details>

### Task 3: Create and diagnose a failing Job

This task intentionally creates a command that exits with status one. Let the Job fail, then inspect the Job, pods, and logs before cleanup. The goal is not to make it pass; the goal is to practice collecting evidence in the right order.

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: failing-job
spec:
  backoffLimit: 2
  template:
    spec:
      containers:
      - name: fail
        image: busybox
        command: ["sh", "-c", "echo 'About to fail'; exit 1"]
      restartPolicy: Never
EOF

kubectl wait --for=condition=failed job/failing-job --timeout=60s
kubectl get jobs failing-job
kubectl get pods -l job-name=failing-job  # Multiple failed pods
kubectl logs job/failing-job
kubectl delete job failing-job
```

<details>
<summary>Solution notes</summary>

The Job should fail after the retry budget is exhausted. Because the restart policy is `Never`, you should expect multiple failed pods rather than one pod with many restarts. If `kubectl logs job/failing-job` selects only one pod, list pods by label and inspect individual pod logs to compare attempts.

</details>

### Task 4: Create a CronJob and observe a scheduled run

Create a CronJob that runs every minute, wait long enough for at least one Job to appear, and read the generated Job's logs. The schedule is intentionally frequent for practice; do not use an every-minute schedule for expensive production work unless the task is designed for it.

```bash
kubectl create cronjob minute-job --image=busybox --schedule="*/1 * * * *" -- date

# Wait for it to run
sleep 70
kubectl get cronjobs
kubectl get jobs
JOB_NAME=$(kubectl get jobs -o name | grep minute-job | head -n 1)
kubectl logs $JOB_NAME

kubectl delete cronjob minute-job
```

<details>
<summary>Solution notes</summary>

`kubectl get cronjobs` should show the schedule and last schedule time after the controller creates a Job. The generated Job name includes the CronJob name plus a suffix, which is why the command captures it dynamically. If no Job appears, describe the CronJob, verify the schedule, and check whether your cluster's controller manager is running normally.

</details>

### Task 5: Manually trigger a CronJob template

Create a daily CronJob that will not naturally run during the exercise, then trigger its Job template manually. This is the operational move you use when a scheduled task needs an immediate rerun after you fix input data or recover from a missed schedule.

```bash
kubectl create cronjob backup --image=busybox --schedule="0 0 * * *" -- echo "backup"

# Trigger manually
kubectl create job --from=cronjob/backup backup-now
kubectl get jobs
kubectl wait --for=condition=complete job/backup-now --timeout=60s
kubectl logs job/backup-now

kubectl delete job backup-now
kubectl delete cronjob backup
```

<details>
<summary>Solution notes</summary>

The manual Job should complete even though the CronJob's natural schedule is midnight. The important point is that `--from=cronjob/backup` copies the CronJob's Job template, so the manual run exercises the same command and image. Use a unique manual Job name each time, because Job names are namespace-scoped.

</details>

### Task 6: Challenge - complete Job workflow

Create a Job that runs four completions, runs two pods at a time, echoes its hostname, sleeps for three seconds, has a backoff limit of two, and automatically deletes after sixty seconds. Try to write the manifest from memory before opening the solution. The challenge combines completion count, concurrency, retry budget, and cleanup in one small object.

```bash
# Create the challenge Job manifest, apply it, and wait for completion.
```

<details>
<summary>Solution</summary>

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: challenge-job
spec:
  completions: 4
  parallelism: 2
  backoffLimit: 2
  ttlSecondsAfterFinished: 60
  template:
    spec:
      containers:
      - name: worker
        image: busybox
        command: ["sh", "-c", "echo $HOSTNAME; sleep 3"]
      restartPolicy: Never
EOF

kubectl wait --for=condition=complete job/challenge-job --timeout=60s
kubectl get job challenge-job
```

</details>

### Optional practice drills

These drills preserve the command shapes you are likely to use during exam practice. Run them only after the main tasks make sense, because speed without diagnosis can hide weak spots. Each drill should end with cleanup, and each failure-oriented drill should be inspected before deletion.

```bash
# Create job
kubectl create job quick --image=busybox -- echo "done"

# Wait for completion
kubectl wait --for=condition=complete job/quick --timeout=60s

# Check logs
kubectl logs job/quick

# Cleanup
kubectl delete job quick
```

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: parallel
spec:
  completions: 6
  parallelism: 3
  template:
    spec:
      containers:
      - name: worker
        image: busybox
        command: ["sh", "-c", "echo Pod: $HOSTNAME; sleep 5"]
      restartPolicy: Never
EOF

# Watch
kubectl get pods -l job-name=parallel -w &
kubectl get job parallel -w &
sleep 30
kill %1 %2 2>/dev/null

# Cleanup
kubectl delete job parallel
```

```bash
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: timeout-test
spec:
  activeDeadlineSeconds: 10
  template:
    spec:
      containers:
      - name: long-task
        image: busybox
        command: ["sleep", "60"]
      restartPolicy: Never
EOF

# Watch job timeout
kubectl get job timeout-test -w &
sleep 15
kill %1 2>/dev/null

# Check status
kubectl get job timeout-test -o jsonpath='{range .status.conditions[*]}{.type}{"="}{.status}{" reason="}{.reason}{"\n"}{end}'

# Cleanup
kubectl delete job timeout-test
```

```bash
# Create CronJob
kubectl create cronjob every-minute --image=busybox --schedule="*/1 * * * *" -- date

# Verify
kubectl get cronjob every-minute

# Wait for first run
sleep 70

# Check jobs created
kubectl get jobs

# Cleanup
kubectl delete cronjob every-minute
```

```bash
# Create CronJob (won't run for a while)
kubectl create cronjob daily --image=busybox --schedule="0 0 * * *" -- echo "daily task"

# Trigger manually
kubectl create job --from=cronjob/daily daily-manual-run

# Check
kubectl get jobs
kubectl wait --for=condition=complete job/daily-manual-run --timeout=60s
kubectl logs job/daily-manual-run

# Cleanup
kubectl delete job daily-manual-run
kubectl delete cronjob daily
```

```bash
# Create intentionally broken job
cat << 'EOF' | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: broken
spec:
  backoffLimit: 2
  template:
    spec:
      containers:
      - name: app
        image: busybox
        command: ["sh", "-c", "cat /nonexistent/file"]
      restartPolicy: Never
EOF

# Diagnose
kubectl get job broken
kubectl get pods -l job-name=broken
kubectl describe job broken
kubectl logs job/broken

# Answer: What's the error? How would you fix it?

# Cleanup
kubectl delete job broken
```

**Success Criteria**:
- [ ] Can create Jobs imperatively and declaratively
- [ ] Can explain and observe completions and parallelism
- [ ] Can diagnose failed Jobs using status, pods, events, and logs
- [ ] Can create CronJobs with schedule and history policy
- [ ] Can manually trigger CronJobs through a generated Job
- [ ] Can choose between Job, CronJob, and Deployment for a batch workload

## Sources

- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Automatic Cleanup for Finished Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/)
- [Kubernetes API Reference: Job v1](https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/job-v1/)
- [Kubernetes API Reference: CronJob v1](https://kubernetes.io/docs/reference/kubernetes-api/workload-resources/cron-job-v1/)
- [kubectl create job](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_job/)
- [kubectl create cronjob](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_cronjob/)
- [kubectl wait](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_wait/)
- [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/)
- [Kubernetes Workload Resources](https://kubernetes.io/docs/concepts/workloads/controllers/)

## Next Module

[Module 2.5: Resource Management](../module-2.5-resource-management/) teaches how requests, limits, and QoS classes shape scheduling and runtime behavior for the pods created by controllers like Jobs, CronJobs, and Deployments.
