---
citations_verified: true
title: "Module 3.8: AI/ML on Cloud Native Infrastructure"
slug: k8s/kcna/part3-cloud-native-architecture/module-3.8-ai-ml-cloud-native
sidebar:
  order: 9
revision_pending: false
---

> **Complexity**: `[MEDIUM]` - Cloud native architecture and workload design
>
> **Time to Complete**: 35-45 minutes
>
> **Prerequisites**: Module 3.1 (Cloud Native Principles), Module 3.3 (Cloud Native Patterns), basic familiarity with Pods, Deployments, Jobs, and scheduling

## What You'll Be Able to Do

After completing this module, you will be able to make architecture and operations decisions for AI/ML workloads that run on Kubernetes 1.35 or newer, including selecting the right workload controller, validating accelerator scheduling, and explaining the trade-offs behind self-hosted model serving.

1. **Apply** Kubernetes resource and scheduling concepts to choose appropriate runtime patterns for AI/ML training, fine-tuning, batch inference, and real-time inference workloads.
2. **Compare** GPU-enabled Kubernetes components such as device plugins, node labels, taints, autoscaling, and specialized schedulers in realistic platform design scenarios.
3. **Design** a basic cloud native serving architecture for a model endpoint that balances privacy, latency, scaling behavior, and operational responsibility.
4. **Debug** common AI/ML scheduling failures by reading Pod status, scheduler events, node capacity, and accelerator resource requests.
5. **Evaluate** ecosystem tools such as Kubeflow, KServe, Ray, vLLM, GPU Operator, and Volcano by matching each tool to a concrete lifecycle problem, assessment item, or hands-on troubleshooting task instead of treating every model workload as an ordinary web service.

## Why This Module Matters

Hypothetical scenario: a retail company launched a recommendation feature that worked perfectly during a small pilot, then failed during the holiday traffic surge. The application Pods scaled, the frontend remained healthy, and the database had spare capacity, yet the recommendation endpoint became slow and then unavailable. The platform team eventually found the real problem: the model server needed GPUs, the cluster autoscaler was only adding CPU nodes, and half the inference replicas were stuck Pending while users waited for product suggestions that never arrived.

That failure is common because AI/ML workloads look familiar from a distance but behave differently under pressure. They still run in containers, they still need networking, and they still benefit from Kubernetes controllers, but their most expensive resources are accelerators and memory rather than ordinary CPU. A learner who treats model serving like a normal stateless API will miss the scheduling constraints, startup time, GPU capacity, model size, and latency behavior that determine whether the system works.

KCNA does not expect you to become a machine learning engineer or install every tool in the ecosystem. It does expect you to reason about why Kubernetes is used for AI/ML, how accelerators become schedulable resources, why training and inference need different workload patterns, and how cloud native practices apply to systems that may cost more per hour than the rest of the cluster combined. This module builds that reasoning step by step, starting with the platform problem and ending with a hands-on scheduler investigation.

The practical lesson is that AI/ML infrastructure fails at the boundary between application thinking and platform thinking. A model developer may correctly say that the code needs a GPU, while the scheduler only sees a Pod that requests an extended resource, a set of node labels, a possible taint, and a queue of other workloads competing for capacity. The useful platform engineer translates between those views without pretending the model is magic. That translation is why this module spends as much time on workload shape, rollout safety, and evidence-driven debugging as it spends on the accelerator name itself.

## 1. Kubernetes Is Useful for AI/ML Because It Coordinates Scarce Infrastructure

Kubernetes did not become popular for AI/ML because it understands neural networks. It became useful because AI/ML platforms need repeatable scheduling, isolation, rollout control, observability, secret management, storage integration, and APIs that many teams can share. Those are cloud native platform concerns, and Kubernetes already provides a control plane for them.

The important shift is that AI/ML workloads often care about resources Kubernetes did not originally manage. A web API may need a small amount of CPU and memory on any general-purpose node. A model training job may need multiple GPUs, large local scratch space, high-throughput storage, and workers that start together. A model server may need one GPU, enough VRAM to load the model, and autoscaling policies tied to request latency or queue depth rather than CPU alone.

```text
┌─────────────────────────────────────────────────────────────┐
│              WHY K8S FOR AI/ML?                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Kubernetes provides what AI/ML workloads need:             │
│                                                             │
│  1. GPU SCHEDULING                                          │
│     ─────────────────────────────────────────────────────   │
│     K8s schedules GPUs like CPU/memory after a device       │
│     plugin advertises accelerator capacity to each kubelet  │
│                                                             │
│  2. DEVICE PLUGINS                                          │
│     ─────────────────────────────────────────────────────   │
│     Extend K8s to manage specialized hardware:              │
│     • NVIDIA GPUs exposed as nvidia.com/gpu                 │
│     • AMD GPUs, Intel accelerators, Google TPUs             │
│     • Any accelerator integrated through the plugin model   │
│                                                             │
│  3. BATCH PROCESSING                                        │
│     ─────────────────────────────────────────────────────   │
│     Jobs and training operators handle runs that finish,    │
│     unlike services that are expected to run continuously   │
│                                                             │
│  4. AUTOSCALING                                             │
│     ─────────────────────────────────────────────────────   │
│     Scale inference endpoints with traffic, queue length,   │
│     latency, or custom metrics when capacity exists         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

A useful mental model is to separate Kubernetes into two layers. The core platform knows how to run Pods, place them on nodes, observe their status, and reconcile desired state. The AI/ML extensions teach the platform about specialized hardware, distributed training, model serving, and experiment workflows. When a Pod requests a GPU, Kubernetes is not running a machine learning algorithm; it is matching a resource request against node capacity published by a device plugin.

> **Pause and predict:** A cluster has three CPU-only nodes and one GPU node. A Pod requests `nvidia.com/gpu: 1` but does not include any node selector or affinity. If the NVIDIA device plugin is installed only on the GPU node, where can the scheduler place the Pod, and what status will you expect if that GPU is already allocated?

The answer is that the Pod can only run where the requested extended resource is available. If the GPU is already allocated, the Pod remains Pending because GPU resources are non-compressible. CPU can sometimes be oversubscribed and throttled, but [a Pod that requests an integer GPU either receives the device or it does not start](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/).

That non-compressible property changes how you evaluate capacity. A CPU-heavy Deployment might limp along while throttled, which gives an operator time to add nodes or tune requests. A GPU-bound inference replica that cannot receive a device does not become a slower replica; it never starts, and the Service has no additional endpoint to receive traffic. This distinction is especially important during autoscaling because an HPA can create more Pods faster than the cluster can create accelerator nodes, download drivers, start the device plugin, pull a large model image, and warm the model server.

Cloud native AI/ML platforms therefore need a capacity story before they need a tool story. The team should know which namespaces are allowed to consume accelerators, which node groups contain which GPU models, whether production inference can preempt experimental training, and which metrics prove that a model endpoint is healthy. Kubernetes gives you the vocabulary for those decisions, but it does not decide the business priority. If an expensive node pool is shared by researchers, notebooks, batch scoring jobs, and customer-facing inference, policy is part of the architecture rather than a governance document someone reads after an outage.

## 2. How GPUs Become Schedulable Kubernetes Resources

Kubernetes does not automatically discover every accelerator in the data center. The kubelet receives accelerator capacity from a device plugin, and the plugin usually runs as a DaemonSet on nodes that have the hardware. [The device plugin reports resources such as `nvidia.com/gpu`, and the node status then includes that resource as allocatable capacity](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/).

A Pod requests GPUs in the `resources.limits` field. Extended resources are requested as whole units in limits, and for many common GPU configurations the request and limit are effectively the same scheduling signal. The scheduler then checks node allocatable capacity and existing allocations before binding the Pod to a node.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-smoke-test
spec:
  restartPolicy: Never
  containers:
    - name: cuda-container
      image: nvidia/cuda:12.4.1-base-ubuntu22.04
      command: ["nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
```

This manifest is intentionally small because the important lesson is the resource request, not the application. If the cluster has a GPU node, the device plugin is healthy, and the GPU is free, the Pod can run and execute `nvidia-smi`. If any of those assumptions are false, Kubernetes will not invent a GPU; the Pod stays Pending and the scheduler event explains which resource is missing.

| Concept | What It Means | Why It Matters in Practice |
|---------|---------------|----------------------------|
| **Device Plugin** | A node-level component, commonly deployed as a DaemonSet, that advertises accelerator devices to the kubelet. | Without it, Kubernetes usually sees ordinary CPU and memory but no GPU resource to schedule. |
| **`nvidia.com/gpu`** | The common extended resource name used by NVIDIA GPU plugins. | Pods request this name, so a typo or missing plugin produces Pending Pods rather than slower execution. |
| **GPU time-slicing** | A configuration that allows multiple Pods to share one physical GPU over time. | It can improve utilization for light workloads, but it weakens isolation and may hurt latency predictability. |
| **MIG** | Multi-Instance GPU partitioning on supported NVIDIA hardware, exposing hardware-isolated GPU slices. | It gives stronger isolation than time-slicing for suitable workloads, but it requires compatible hardware and planning. |
| **Whole GPU allocation** | One Pod receives exclusive access to a full physical GPU. | It is the simplest model and often best for heavy training or latency-sensitive inference. |

Node labels and taints often appear alongside GPU resources. [Labels help target workloads to specific node groups, such as nodes with a particular GPU model. Taints help keep ordinary workloads away from expensive accelerator nodes unless those workloads explicitly tolerate the taint](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/). The GPU resource request itself is still essential because a label alone says "run on this kind of node" while `nvidia.com/gpu: 1` says "allocate one device to this container."

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: recommender-inference
spec:
  replicas: 2
  selector:
    matchLabels:
      app: recommender-inference
  template:
    metadata:
      labels:
        app: recommender-inference
    spec:
      nodeSelector:
        accelerator: nvidia
      tolerations:
        - key: "accelerator"
          operator: "Equal"
          value: "gpu"
          effect: "NoSchedule"
      containers:
        - name: model-server
          image: ghcr.io/example/recommender:1.0.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "2"
              memory: 8Gi
            limits:
              nvidia.com/gpu: 1
              memory: 16Gi
```

Notice the separation of concerns in this Deployment. The `nodeSelector` and toleration steer the Pod toward the GPU node group, while the GPU limit reserves the accelerator. CPU and memory requests tell the scheduler how much ordinary capacity the Pod needs, and the memory limit prevents one model server from exhausting the node. This is the kind of combined reasoning KCNA expects: not just naming a feature, but applying several platform mechanisms together.

The resource request also becomes an operational contract between the application team and the platform team. If the platform exposes full GPUs, the application asks for full GPUs and pays the scheduling cost of exclusive allocation. If the platform exposes [MIG slices or time-sliced resources](https://github.com/NVIDIA/k8s-device-plugin), the application may request smaller advertised resources, but the team must understand the isolation and performance trade-off. A manifest that says `nvidia.com/gpu: 1` is not just syntax; it is a claim about hardware, accounting, and failure behavior.

Hypothetical scenario: a team once moved a prototype image classifier from a single development node to a shared cluster and kept the same `nodeSelector` but accidentally dropped the GPU limit during a chart refactor. The Pod still landed on the GPU node because the selector matched, so the deployment looked correct during a quick review. Under load, the container failed when the model runtime could not find an assigned device, and ordinary CPU workloads also started landing on the expensive node because the taint policy was inconsistent. The fix was not one magic label; the fix was to make selectors, taints, tolerations, and extended resource requests tell the same story.

## 3. Training, Fine-Tuning, Batch Inference, and Real-Time Inference Are Different Workloads

The biggest beginner mistake is calling every model-related container "AI" and then deploying it the same way. Kubernetes architecture starts with workload shape. Does the process finish or run forever? Does it need all workers at once? Does it serve users synchronously? Does it need one GPU, many GPUs, or no GPU after preprocessing?

```text
┌─────────────────────────────────────────────────────────────┐
│              AI/ML WORKLOAD TYPES                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TRAINING                                                   │
│  ─────────────────────────────────────────────────────────  │
│  • Runs for hours, days, or sometimes longer                │
│  • May need many GPUs distributed across nodes              │
│  • Batch workload that should complete successfully         │
│  • Distributed runs may need gang scheduling                │
│                                                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ │
│  │ GPU worker │ │ GPU worker │ │ GPU worker │ │ GPU lead │ │
│  │   node A   │ │   node A   │ │   node B   │ │  node B  │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────┘ │
│                                                             │
│  INFERENCE SERVING                                          │
│  ─────────────────────────────────────────────────────────  │
│  • Runs continuously and serves predictions                 │
│  • Latency-sensitive because users or applications wait     │
│  • Often scales by adding replicas behind a Service         │
│  • May use one GPU per replica or partitioned GPU capacity  │
│                                                             │
│  Request ──▶ [Model Server] ──▶ Prediction                  │
│             [Model Server]      Autoscaled replicas         │
│             [Model Server]                                 │
│                                                             │
│  FINE-TUNING                                                │
│  ─────────────────────────────────────────────────────────  │
│  • Starts from a pretrained model and adapts it to data     │
│  • Usually shorter than full training                       │
│  • Still sensitive to checkpointing, storage, and GPUs      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Training is usually a batch problem. A data science team starts a run, waits for it to finish, and expects artifacts such as model weights, metrics, or checkpoints. [Kubernetes Jobs fit simple training because they track completion and do not restart successful Pods forever](https://kubernetes.io/docs/concepts/workloads/controllers/job/). Larger teams may use training operators such as PyTorchJob or TFJob because those operators understand worker roles, distributed launch behavior, and training-specific lifecycle events.

Real-time inference is usually a service problem. A model endpoint accepts requests, returns predictions, and must stay available while traffic changes. Deployments, Services, autoscalers, and rollout strategies fit this shape because replicas can be replaced gradually and traffic can be routed away from unhealthy Pods. Inference also has special constraints: model startup may take minutes, GPU memory may be the limiting factor, and CPU utilization may not reflect the actual bottleneck.

Batch inference sits between those two patterns. It uses a trained model to score a large offline dataset, such as millions of images or transactions, and then writes results to storage. It does not need a public endpoint because nobody is waiting on each individual request. A Job or workflow engine is usually a better fit than a Deployment, because completion and retry behavior matter more than steady request latency.

| Aspect | Training | Fine-Tuning | Batch Inference | Real-Time Inference |
|--------|----------|-------------|-----------------|---------------------|
| **Duration** | Long-running but finite, often hours or days. | Finite and usually shorter than full training. | Finite, tied to a dataset or queue. | Continuous, serving as long as the product needs predictions. |
| **Kubernetes pattern** | Job, training operator, or batch scheduler. | Job or specialized operator. | Job, workflow, or queue-driven workers. | Deployment, Service, autoscaler, and rollout controls. |
| **Scaling concern** | Throughput, parallel workers, and checkpoint restart. | GPU cost, storage access, and repeatability. | Dataset throughput and failure recovery. | Latency, concurrency, readiness, and traffic spikes. |
| **Failure handling** | Resume from checkpoints or restart a failed run. | Save intermediate adapters or checkpoints. | Retry failed chunks without duplicating output. | Route around unhealthy replicas and roll out safely. |
| **Scheduling risk** | Partial worker placement can waste GPUs. | A few GPUs may block other teams if priorities are unclear. | Large queues can starve interactive workloads. | Replicas may start too slowly for sudden traffic. |

> **Stop and decide:** Your team has a script that reads yesterday's support tickets, classifies each ticket with an existing model, writes labels to a database, and exits. Would you run it as a Deployment, a Job, or a DaemonSet? Write down the Kubernetes behavior you need before choosing the resource.

A good answer chooses a Job or workflow task because the process has a clear end condition. A Deployment would keep restarting the classifier after it finishes, and a DaemonSet would run one copy on every matching node whether or not the data pipeline needs that. The decision comes from workload shape, not from the fact that a model is involved.

When you design these workloads, start by writing the sentence "success means..." before you write the YAML. For training, success means the run completes and produces a model artifact, metrics, or checkpointed state. For batch inference, success means every input item is scored once, failures are retryable, and duplicate output is controlled. For real-time inference, success means the endpoint stays available, latency remains inside the service objective, and rollouts do not send traffic to cold or incompatible replicas. Those success definitions naturally point to different controllers, probes, autoscaling signals, and storage patterns.

Fine-tuning deserves its own judgment because it often feels small enough to improvise yet expensive enough to cause platform tension. A team adapting a pretrained model may need fewer GPUs than a full training run, but it still needs repeatability, dataset access, checkpointing, and clear ownership of output artifacts. If every fine-tune is launched by hand from a privileged notebook, the organization will struggle to answer which data was used, which image produced the weights, and whether the result can be reproduced. Kubernetes Jobs, workflow systems, or training operators are not bureaucracy in that situation; they are the audit trail that makes a useful experiment promotable.

## 4. Distributed Training Needs Scheduling Guarantees That Default Kubernetes May Not Provide

Default Kubernetes schedules Pods one at a time. That is enough for many independent services, but distributed training often needs a group of workers to start together. If a training job needs sixteen workers and only eight are scheduled, those eight may hold expensive GPUs while waiting for peers that cannot start. The result is poor utilization and sometimes a deadlock-like condition from the user's point of view.

Gang scheduling solves that problem by treating a set of Pods as a unit. The scheduler admits the group only when enough resources exist for the whole gang, or it waits without binding partial workers. Tools such as Volcano add batch scheduling capabilities including gang scheduling, queues, and fair sharing. KCNA does not require deep configuration knowledge, but it does expect you to recognize why the default scheduler's one-Pod-at-a-time behavior can be a poor fit for distributed AI/ML jobs.

```text
┌─────────────────────────────────────────────────────────────┐
│          DEFAULT SCHEDULING VS. GANG SCHEDULING             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Default scheduler:                                         │
│                                                             │
│  worker-1 ──▶ scheduled ──▶ holds GPU                       │
│  worker-2 ──▶ scheduled ──▶ holds GPU                       │
│  worker-3 ──▶ Pending   ──▶ no GPU left                     │
│  worker-4 ──▶ Pending   ──▶ no GPU left                     │
│                                                             │
│  Result: partial job may hold GPUs while doing no work       │
│                                                             │
│  Gang scheduler:                                            │
│                                                             │
│  workers 1-4 ──▶ enough GPUs? ──▶ yes: schedule all          │
│                         │                                   │
│                         └────▶ no: schedule none yet         │
│                                                             │
│  Result: fewer stranded GPUs and clearer queue behavior      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Distributed training also makes storage and networking more important. Workers may read large datasets, exchange gradients, and write checkpoints. A platform design that focuses only on GPU count can still fail if the storage path is slow or if workers cannot communicate reliably. Senior-level Kubernetes reasoning means asking which resource becomes the bottleneck next, not stopping after the first successful Pod start.

Priorities and quotas matter because GPU clusters are shared. A research notebook, a production inference endpoint, and a training run should not all compete without policy. ResourceQuota, PriorityClass, queueing systems, and separate node pools are ways to express business intent. The platform should answer questions such as "Can an experiment preempt production inference?" and "How many GPUs can one namespace consume?" before a traffic spike or training deadline forces the issue.

Default scheduling is still valuable, and the point is not that every AI/ML workload needs a custom scheduler. A single-replica model endpoint, a small batch scoring Job, or a CPU-only preprocessing stage may work perfectly with normal Kubernetes scheduling. The architectural skill is recognizing when independent Pod placement becomes the wrong abstraction. If the useful unit of work is "all workers in this training gang," then queue admission should happen at that unit. If the useful unit is "one independent scorer per data shard," ordinary Job parallelism may be enough.

Storage can be the hidden constraint after scheduling succeeds. A training job that starts all workers but reads a multi-terabyte dataset through an overloaded network path may waste GPU hours waiting on data. A batch inference job that writes results without idempotency may create duplicate rows after retries. A model server that downloads weights from object storage on every start may create slow rollouts and noisy dependency failures. The platform decision is therefore broader than "GPU or no GPU"; it includes data locality, checkpoint location, restart behavior, and whether the workload can resume from an interrupted state.

## 5. Model Serving Adds Latency, Rollout, and Privacy Trade-Offs

Serving a model is not just running a Python process in a container. The model has to be loaded, kept warm, monitored, scaled, and updated without breaking callers. A small model may behave like an ordinary web API, but a large language model can take significant time to start and may consume most of a GPU's memory before receiving a single request.

Organizations self-host inference for several reasons. Privacy is a common driver because prompts, documents, images, or customer records may be too sensitive to send to an external API. Latency can improve when the model server is close to the application and data. Cost can improve at sustained high volume if the team can keep GPUs highly utilized. Control improves because the organization chooses model versions, quantization settings, rollout timing, and observability.

```text
┌─────────────────────────────────────────────────────────────┐
│              WHY SELF-HOST LLMs?                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PRIVACY      Sensitive data stays in controlled systems    │
│  COST         Sustained high volume may beat per-token APIs │
│  LATENCY      Co-locate model servers with applications     │
│  COMPLIANCE   Meet data residency and audit requirements    │
│  CONTROL      Choose model, version, runtime, and rollout   │
│                                                             │
│  Trade-off: The platform team owns GPUs, drivers, scaling,  │
│  model rollout, capacity planning, and incident response.   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The trade-off is operational responsibility. A public model API hides GPU drivers, capacity planning, batching, runtime tuning, and model-server upgrades. A self-hosted platform exposes all of those concerns to the organization. Kubernetes helps coordinate the system, but it does not remove the need to understand accelerator scarcity, model memory, autoscaling metrics, or release safety.

For inference, readiness probes are especially important. A container can be running while the model is still loading, and sending traffic too early creates failed requests. [A readiness probe should report ready only after the server can actually answer predictions. For large models, startup probes may also be necessary so Kubernetes does not kill a slow-loading container before it has a fair chance to become healthy](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/).

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ticket-classifier
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ticket-classifier
  template:
    metadata:
      labels:
        app: ticket-classifier
    spec:
      containers:
        - name: classifier
          image: ghcr.io/example/ticket-classifier:2.1.0
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            periodSeconds: 5
            failureThreshold: 6
          startupProbe:
            httpGet:
              path: /ready
              port: 8080
            periodSeconds: 10
            failureThreshold: 30
          resources:
            requests:
              cpu: "1"
              memory: 4Gi
            limits:
              memory: 8Gi
              nvidia.com/gpu: 1
```

This Deployment teaches two subtle points. First, readiness is about serving capability, not container existence. Second, resource limits and probes must match the model's real behavior. If the model takes four minutes to load but the startup probe gives it only one minute, Kubernetes will create a crash loop even though the image and code are correct.

Rollouts are another place where ordinary web-service habits need adjustment. A small API can often start in seconds, accept traffic quickly, and roll back with little cost. A large model server may need to pull gigabytes of image layers or model weights, allocate GPU memory, compile kernels, and warm request caches before the first useful prediction. If the Deployment strategy allows too many old replicas to terminate before new replicas are truly ready, the system can lose serving capacity during an otherwise routine release. Readiness gates, conservative surge settings, and clear rollback criteria are part of the serving architecture, not optional polish.

Privacy and compliance also affect the architecture in ways that Kubernetes cannot solve alone. Self-hosting keeps data inside controlled infrastructure only if the surrounding system respects that boundary: logs must not leak prompts, traces must avoid sensitive payloads, access controls must protect model endpoints, and storage paths must follow retention rules. The Kubernetes pieces, such as Secrets, NetworkPolicy, service accounts, namespaces, and audit logs, are enabling mechanisms. They become a privacy design only when the team defines what data may cross which boundary and verifies that every component follows the rule.

Before running this in a real platform, what output would convince you that the model endpoint is ready for users rather than merely alive as a process? A strong answer names evidence from several layers: the Pod is Running, the readiness endpoint reports loaded model state, the Service has ready endpoints, latency metrics are within target, GPU memory is allocated as expected, and a synthetic prediction succeeds. That evidence chain prevents a common failure where an operator sees a green Pod and misses the fact that the model server is still warming or rejecting requests.

## 6. Ecosystem Tools Solve Different Parts of the AI/ML Lifecycle

The AI/ML on Kubernetes ecosystem is large because the lifecycle is larger than "run a container." Teams need notebooks for exploration, pipelines for repeatable training, registries for model versions, serving systems for inference, schedulers for batch jobs, and monitoring for performance drift. No single tool should be selected just because it appears in an AI/ML architecture diagram.

[Kubeflow is often discussed as an end-to-end ML platform on Kubernetes](https://github.com/kubeflow/kubeflow). It can include notebooks, pipelines, training operators, and serving integrations. It is useful when the organization wants a platform for data scientists and ML engineers rather than isolated YAML files. It also increases platform complexity, so a small team serving one model may not need the full stack.

[KServe focuses on model serving. It provides abstractions for inference services, canary rollout patterns, autoscaling integrations, and model-server conventions](https://github.com/kserve/kserve). vLLM is a high-throughput inference engine often used for large language models, where batching and memory management strongly affect cost and latency. Ray is a distributed computing framework used for training, data processing, and serving patterns that need flexible distributed execution.

| Tool | What It Does | Best-Fit Scenario |
|------|-------------|-------------------|
| **Kubeflow** | Provides a Kubernetes-native ML platform with notebooks, pipelines, training components, and serving integrations. | A platform team wants a shared ML workflow environment for multiple teams. |
| **KServe** | Standardizes model inference serving on Kubernetes with rollout and scaling patterns. | A team needs production model endpoints rather than only training jobs. |
| **Ray** | [Runs distributed Python workloads for training, data processing, and serving.](https://github.com/ray-project/ray) | A workload needs flexible distributed execution beyond a single Pod. |
| **vLLM** | [Serves large language models efficiently using optimized batching and memory handling.](https://github.com/vllm-project/vllm) | An organization self-hosts LLM inference and needs high throughput per GPU. |
| **NVIDIA GPU Operator** | [Automates GPU driver, container runtime, monitoring, and device plugin setup.](https://github.com/NVIDIA/gpu-operator) | A platform team manages NVIDIA GPU node pools and wants repeatable operations. |
| **Volcano** | Adds batch scheduling features such as gang scheduling, queues, and fair sharing. | Distributed training jobs need all workers scheduled together or predictable queue behavior. |

```text
┌─────────────────────────────────────────────────────────────┐
│              ML PIPELINE ON KUBERNETES                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Data Prep ──▶ Training ──▶ Evaluation ──▶ Serving ──▶ Monitor│
│     │             │              │             │          │ │
│  [Spark or     [Kubeflow      [tests,       [KServe,   [Prom │
│   Ray jobs]     Training]      metrics]      vLLM]      + logs│
│                                                             │
│  Kubernetes provides the API, Pods, Services, controllers,  │
│  scheduling hooks, secrets, storage integration, and events. │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

> **Architecture check:** Your organization has one fraud model that is retrained weekly and served behind an internal API. The data science team does not need notebooks in the cluster. Which is more likely to be the first useful platform investment: a full Kubeflow installation, a small Job plus Deployment pattern, or a serving-focused tool such as KServe? Justify the operational cost of your choice.

A practical answer might start with a Job for retraining and a Deployment or KServe-based inference endpoint, then add Kubeflow only when repeated workflows, notebooks, or multi-team standardization justify the overhead. Tool selection should follow workflow pain. Installing a large platform before the team has a lifecycle problem can create more work than it removes.

The same reasoning applies to GPU operations tools. The NVIDIA GPU Operator can simplify driver, runtime, monitoring, and device plugin management, especially across multiple node pools or managed environments with repeatable setup needs. It is not a substitute for understanding what the device plugin advertises, what the scheduler sees, or how the workload requests a resource. If a Pod is Pending with `Insufficient nvidia.com/gpu`, the operator may be part of the repair path, but the debugging question remains evidence-driven: do nodes exist, do they advertise allocatable GPU resources, are those resources already allocated, and are placement policies compatible with the Pod?

Large language model serving adds another dimension because runtime choice affects capacity as much as Kubernetes configuration. Engines such as vLLM improve throughput through batching and memory management strategies, but those optimizations still live inside a Pod that needs GPU capacity, readiness behavior, observability, and rollout control. A team that tunes the runtime but ignores Kubernetes scheduling may still fail to scale. A team that writes perfect Kubernetes YAML but chooses an unsuitable serving runtime may burn GPU hours on poor batching. The platform design has to connect both layers.

## 7. Worked Example: Debug a Pending GPU Inference Deployment

A worked example shows the reasoning process before you attempt a similar hands-on task. In this scenario, a team deploys a model server for real-time inference. The Deployment is correct enough to create Pods, but no replica becomes Running. Your goal is to move from symptom to cause using Kubernetes evidence rather than guessing.

The team applies this Deployment to a development cluster. They expect one replica to start because they believe the cluster has a GPU node. The platform uses the common `k` alias for `kubectl`; after defining the alias once with `alias k=kubectl`, the commands below use `k` for brevity.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: image-ranker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: image-ranker
  template:
    metadata:
      labels:
        app: image-ranker
    spec:
      containers:
        - name: ranker
          image: ghcr.io/example/image-ranker:1.0.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "1"
              memory: 4Gi
            limits:
              memory: 8Gi
              nvidia.com/gpu: 1
```

### Step 1: Start with the controller, then inspect the Pod

A beginner often starts by changing YAML immediately, but a stronger habit is to inspect what Kubernetes created. The Deployment owns a ReplicaSet, and the ReplicaSet owns Pods. If the Deployment has unavailable replicas, inspect the controller first and then move to the Pod status and scheduler events.

```bash
k get deployment image-ranker
k get pods -l app=image-ranker
```

The output below shows a healthy controller object with no available replica because the only created Pod is still Pending.

```text
NAME            READY   UP-TO-DATE   AVAILABLE   AGE
image-ranker    0/1     1            0           2m

NAME                             READY   STATUS    RESTARTS   AGE
image-ranker-6c9d7f8d9b-hp2lm    0/1     Pending   0          2m
```

Pending means the container has not started. That is different from CrashLoopBackOff, where the Pod was scheduled and a container started but failed. For scheduling problems, the `describe pod` output is the main source of truth because it includes scheduler events. In this scenario, the event names the missing extended resource directly.

```bash
k describe pod -l app=image-ranker
```

The scheduler event below is the critical clue because it describes node availability from the scheduler's perspective.

```text
Events:
  Type     Reason             Age   From               Message
  ----     ------             ----  ----               -------
  Warning  FailedScheduling   2m    default-scheduler  0/4 nodes are available: 4 Insufficient nvidia.com/gpu.
```

### Step 2: Interpret the event instead of memorizing the answer

The scheduler says it cannot find enough `nvidia.com/gpu` capacity. That does not prove the cluster has no physical GPU. It proves the Kubernetes scheduler does not currently see allocatable free capacity for that resource. The cause could be missing device plugin, no GPU nodes, a consumed GPU, a node taint without toleration, or node affinity that excludes the right node.

The next command checks whether any node advertises GPU capacity. If no node shows `nvidia.com/gpu` under allocatable resources, the problem is lower than the workload manifest. The platform team needs to confirm GPU nodes, drivers, and the device plugin. A healthy GPU node includes a line like the one shown below under `Allocatable`.

```bash
k describe nodes | grep -A5 -E "Name:|Allocatable:"
```

```text
nvidia.com/gpu:  1
```

If no such line appears, deploying more model replicas will not help. The scheduler cannot allocate a resource that the nodes do not advertise. The likely fix is to install or repair the GPU device plugin, or use a managed GPU node pool that includes the required integration.

### Step 3: Check whether the workload is missing placement rules

Suppose a node does advertise `nvidia.com/gpu`, but the Pod is still Pending. The next useful question is whether the node has taints that repel ordinary Pods. GPU nodes are commonly tainted because they are expensive, and the platform team wants only GPU-aware workloads to land there. Check the taint policy before changing the Deployment.

```bash
k describe node gpu-node-1 | grep -A4 Taints
```

The output below shows the classic taint that requires a matching toleration before scheduling can proceed.

```text
Taints: accelerator=gpu:NoSchedule
```

The Deployment above requests a GPU but does not tolerate the taint. The fix is to add a matching toleration, and many teams also add a node selector or affinity rule to express the intended node pool.

```yaml
spec:
  template:
    spec:
      nodeSelector:
        accelerator: nvidia
      tolerations:
        - key: "accelerator"
          operator: "Equal"
          value: "gpu"
          effect: "NoSchedule"
```

### Step 4: Verify the corrected scheduling path

After updating the Deployment, verify the Pod again instead of assuming the fix worked. A successful result should move from Pending to ContainerCreating and then Running, assuming image pulls and model startup succeed. If it moves to CrashLoopBackOff, that is progress in the debugging sequence because the problem changed from scheduling to runtime.

```bash
k rollout status deployment/image-ranker
k get pods -l app=image-ranker -o wide
k describe pod -l app=image-ranker
```

The key lesson is the order of investigation. Start with the observed status, read scheduler events, confirm node allocatable resources, then inspect placement constraints such as taints, tolerations, selectors, and affinity. That same pattern works for the hands-on exercise later in the module, even when your local cluster has no real GPU hardware.

This example also shows why "Pending" is not a vague status. It narrows the problem to scheduling and admission before the container runtime starts the workload. If the Pod later moves to `ContainerCreating`, you investigate image pulls, volume mounts, runtime classes, and node-level setup. If it moves to `CrashLoopBackOff`, you investigate command, environment, model files, permissions, and application logs. Good Kubernetes debugging is a sequence of narrowing questions, and GPU workloads reward that discipline because blindly changing manifests can hide the actual scarcity signal.

## Patterns & Anti-Patterns

Patterns are reusable decisions that make scarce accelerator capacity predictable. They are not rules to copy blindly, because the right answer depends on the workload shape, the cost of the hardware, and the operational maturity of the team. In AI/ML platforms, the most durable patterns make intent visible to both Kubernetes and humans: the manifest says what the workload needs, the node pool policy says who may use it, and the observability path shows whether the decision worked.

| Pattern | When to Use It | Why It Works | Scaling Consideration |
|---------|----------------|--------------|-----------------------|
| **Dedicated accelerator node pools** | Production inference or expensive training needs predictable access to known GPU models. | Labels, taints, quotas, and autoscaling policies can be tuned for accelerator workloads without disrupting CPU services. | Keep separate pools for incompatible GPU models or isolation levels so scheduling decisions stay explainable. |
| **Finite work as Jobs or workflows** | Training, fine-tuning, and batch inference have a clear completion condition. | Completion, retries, backoff, and artifact handoff match the workload better than continuously reconciled replicas. | Add checkpointing and idempotent output so retries do not waste large runs or duplicate results. |
| **Serving endpoints with model-aware readiness** | Real-time inference is part of a user or service request path. | Readiness reports prediction capability rather than process existence, which protects callers during startup and rollout. | Combine readiness with latency, queue depth, and GPU metrics because CPU alone may not show saturation. |
| **Batch schedulers for grouped workers** | Distributed training needs all or most workers to start together. | Gang scheduling and queues prevent partial placement from holding GPUs while the job cannot progress. | Define queue priority and fair sharing before several teams compete for the same accelerator pool. |

Anti-patterns usually appear when a team treats an AI/ML workload as either completely special or completely ordinary. If it is treated as completely special, the platform becomes a pile of bespoke scripts with no repeatability. If it is treated as ordinary, the team misses accelerator scheduling, model load behavior, and lifecycle differences. The healthier middle ground is to use Kubernetes primitives where they fit and add specialized controllers only where the model lifecycle demands them.

| Anti-Pattern | What Goes Wrong | Better Alternative |
|--------------|-----------------|--------------------|
| **One giant ML platform for one simple model** | The team operates notebooks, pipelines, identity integrations, and serving abstractions before those problems exist. | Start with a Job, a Deployment or KServe endpoint, and clear artifact storage, then expand when workflow repetition justifies it. |
| **GPU nodes without admission policy** | Experiments, notebooks, and production inference compete on cost rather than priority, causing surprise Pending Pods or noisy incidents. | Use taints, tolerations, ResourceQuota, PriorityClass, and separate node pools to encode the intended sharing model. |
| **Autoscaling on the wrong signal** | CPU-based scaling looks healthy while GPU memory, request queues, or latency are already saturated. | Scale inference with metrics that represent the bottleneck and validate that accelerator node groups can scale too. |
| **Ignoring the model artifact path** | Pods start slowly or fail during rollout because every replica downloads large weights from an overloaded or unavailable store. | Treat model storage, caching, image layering, and startup probes as part of the deployment design. |

## Decision Framework

Use the following framework when someone asks, "How should we run this model on Kubernetes?" The first decision is whether the process is finite or continuous, because that separates training and batch scoring from serving. The second decision is whether the workload needs accelerators, because that introduces device plugins, extended resources, node pools, and cost policy. The third decision is whether the workload is independent or grouped, because distributed training may need batch scheduling semantics that ordinary Deployments do not provide.

```text
┌─────────────────────────────────────────────────────────────┐
│              AI/ML WORKLOAD DECISION PATH                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Does the process finish?                                   │
│       │                                                     │
│       ├── yes ──▶ Training, fine-tuning, or batch inference │
│       │          Use Job, workflow, or training operator    │
│       │                                                     │
│       └── no ───▶ Real-time or internal inference service   │
│                  Use Deployment, Service, probes, scaling   │
│                                                             │
│  Does it need accelerators?                                 │
│       │                                                     │
│       ├── yes ──▶ Verify device plugin, GPU resources,      │
│       │          taints, tolerations, labels, autoscaling   │
│       │                                                     │
│       └── no ───▶ Treat as ordinary CPU/memory workload     │
│                  but keep artifact and data paths explicit  │
│                                                             │
│  Do workers need to start together?                         │
│       │                                                     │
│       ├── yes ──▶ Consider Volcano or training operators    │
│       └── no ───▶ Default scheduler may be sufficient       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| Decision Point | Choose This When | Trade-Off to Accept |
|----------------|------------------|---------------------|
| **Job or workflow** | The model task has a clear end condition and produces artifacts or batch output. | You must design retries, checkpointing, and output idempotency instead of relying on always-on replicas. |
| **Deployment plus Service** | The model answers requests continuously and callers need stable network access. | You must handle readiness, rollout timing, autoscaling metrics, and warm capacity. |
| **KServe or serving abstraction** | Many teams need consistent model serving, canaries, scaling conventions, or model server integration. | You add another control plane surface that platform engineers must operate and debug. |
| **Kubeflow or broader ML platform** | The organization needs shared notebooks, pipelines, training workflows, and multi-team lifecycle governance. | You accept installation, upgrades, identity integration, and user-support complexity. |
| **Ray or distributed framework** | The workload needs flexible distributed Python execution, data processing, or serving patterns beyond one Pod. | You must operate the framework runtime as well as the Kubernetes resources beneath it. |
| **Volcano or batch scheduler** | Grouped workers, queues, gang scheduling, or fair sharing are central to workload success. | You must define queue policy and teach users how batch scheduling differs from default Pod placement. |

Which approach would you choose for a nightly batch scoring job that runs on CPU today but may need one GPU next quarter, and why? A practical answer might start with a Job or workflow now, keep data input and output idempotent, and avoid installing a full ML platform until repeated workflow needs appear. The future GPU requirement should influence how you name resources, isolate namespaces, and document the scheduling path, but it should not force the team to operate every ecosystem component before the workload needs it.

There is one final check that experienced platform teams use before approving an AI/ML design: they ask what evidence would prove the design is wrong. If a training Job cannot resume from checkpoints, then a single node failure can waste the whole run. If an inference Deployment scales replicas but the cluster cannot add GPU nodes, then autoscaling creates Pending Pods without adding serving capacity. If a serving endpoint is private but prompt payloads appear in logs, then the privacy argument collapses even though the model never called an external API. Thinking this way turns architecture review into testable claims rather than preferences.

The same review should include the human workflow around the cluster. Data scientists need a repeatable way to request capacity, understand queue status, and find scheduler events without paging the platform team for every Pending Pod. Application teams need a contract for model versions, rollout windows, latency objectives, and rollback ownership. Platform teams need cost visibility, namespace quotas, and a support boundary for specialized runtimes such as Ray, vLLM, or KServe. Kubernetes supplies shared APIs for these conversations, but the organization still has to decide who owns each decision when the system is under pressure.

For KCNA-level reasoning, the important habit is to keep connecting symptoms back to Kubernetes objects. A slow model endpoint might be a runtime tuning issue, but Pending replicas point first to scheduling. A failed training run might be bad code, but partial worker placement points first to workload grouping and queue policy. A privacy concern might involve the model, but the enforceable boundary appears in namespaces, identities, network paths, logging choices, and storage destinations.

## Did You Know?

1. **GPU waste is a platform finance problem, not only a technical problem.** A single accelerator node can cost enough that low utilization becomes visible in cloud bills quickly, so scheduling policies, sharing strategies, and right-sized model serving directly affect business outcomes.

2. **Gang scheduling is not part of the default scheduler behavior most learners use first.** Kubernetes normally binds Pods independently, so distributed training teams often add schedulers such as Volcano when partial placement would strand GPUs and block useful work.

3. **A model server can be Running but still not ready to serve predictions.** Large models may need time to download weights, allocate GPU memory, compile kernels, or warm caches, which is why readiness and startup probes matter for inference reliability.

4. **Kubernetes won AI/ML infrastructure work through extensibility rather than original design.** Device plugins, custom controllers, operators, and specialized schedulers let the platform adapt to accelerators and ML workflows without requiring every feature in the core API.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Thinking Kubernetes automatically detects GPUs after installation. | Teams see a physical GPU on a node and assume the scheduler can allocate it without the device plugin path. | Install and verify the vendor device plugin or GPU Operator, then confirm nodes advertise `nvidia.com/gpu` as allocatable capacity. |
| Using a Deployment for a training script that should finish. | Deployments are familiar, so a finite script gets wrapped in a controller that expects continuous replicas. | Use a Job, workflow engine, or training operator for training, fine-tuning, and batch inference tasks with completion semantics. |
| Relying only on node labels for GPU workloads. | A label feels like placement control, but it does not allocate the accelerator or bypass a taint. | Combine resource limits, selectors or affinity, and tolerations so placement and device reservation match the node pool policy. |
| Scaling inference only on CPU utilization. | Generic web-service autoscaling examples are copied even when GPU memory, queue depth, or latency is the bottleneck. | Choose autoscaling signals that match the model server's real bottleneck and verify that GPU node groups can add capacity. |
| Ignoring model load time during rollouts. | The container process starts before weights are loaded, so operators mistake Running for ready. | Use startup and readiness probes that reflect actual model-serving readiness, and tune rollout settings for warm capacity. |
| Treating GPU time-slicing as equivalent to hardware isolation. | Utilization goals hide the fact that shared GPUs can create noisy-neighbor effects and unpredictable latency. | Use whole GPUs or MIG where isolation matters, and reserve time-slicing for suitable development or light workloads. |
| Installing a full ML platform before defining the workflow problem. | Tool diagrams make every component look mandatory before the team has repeated lifecycle pain. | Start with the smallest pattern that solves the workload, then adopt Kubeflow, KServe, Ray, or Volcano when their abstractions pay off. |
| Forgetting that cluster autoscaling must understand GPU node groups. | The HPA creates Pods, but the autoscaler can only add CPU nodes or cannot satisfy accelerator labels and taints. | Configure autoscaling for accelerator node pools and verify that Pending events trigger the expected scale-out path. |

## Quiz

<details>
<summary>1. Your team deploys a real-time recommendation model as a Deployment with three replicas. During a traffic spike, the HPA creates more replicas, but the new Pods stay Pending with `Insufficient nvidia.com/gpu`. What should you investigate first?</summary>

Investigate whether GPU node groups and the device plugin expose enough allocatable accelerator capacity. Pending means the Pod has not been scheduled, so image dependencies and runtime crashes are not the first issue. The event names the missing extended resource, which points to GPU capacity, device plugin health, existing allocations, or autoscaler configuration for GPU nodes. The web tier can scale normally because CPU nodes do not satisfy a GPU request.
</details>

<details>
<summary>2. A data science team has a script that trains a model for twelve hours, writes checkpoints every hour, uploads final weights, and then exits successfully. They ask you to run it as a Deployment so Kubernetes will keep it reliable. What should you recommend?</summary>

Recommend a Job, workflow engine, or training operator because the workload is finite. It starts, performs training, writes output, and exits, so success is completion rather than continuous availability. A Deployment tries to maintain continuously running replicas, which means it may restart the training after successful completion and duplicate expensive output. Checkpointing and artifact upload still matter, but they belong in a batch-oriented controller.
</details>

<details>
<summary>3. A distributed training run needs eight GPU workers to start together. Four workers are Running and holding GPUs, while four are Pending because the cluster has no remaining capacity. Which platform change best addresses the architecture problem?</summary>

Add gang scheduling through a batch scheduler such as Volcano, or use a training operator that integrates with suitable scheduling semantics. The failure is partial placement of a distributed workload, not HTTP readiness or service discovery. Gang scheduling prevents a subset of workers from consuming GPUs when the full set cannot run, which improves utilization and makes queue behavior clearer. The key is that the useful scheduling unit is the worker group, not each independent Pod.
</details>

<details>
<summary>4. A compliance team requires customer documents used in prompts to stay inside company-controlled infrastructure, and product leadership requires low latency for an interactive workflow. Which serving design best fits those constraints?</summary>

Self-host the inference service close to the application on Kubernetes, while accepting responsibility for accelerator capacity, model rollout, observability, and incident response. Keeping inference in controlled infrastructure helps address data handling constraints, and co-location can reduce network latency. Kubernetes can provide deployment, networking, access-control, and rollout mechanisms, but it does not remove the operational cost of running model servers. The design should also prevent sensitive prompts from leaking through logs, traces, or unmanaged storage paths.
</details>

<details>
<summary>5. A platform team has one weekly fraud-model retraining job and one internal fraud inference endpoint. They are considering installing a large end-to-end ML platform immediately. What is the most defensible first step?</summary>

Start with the smallest pattern that solves the workload: a Job or workflow for retraining and a Deployment or serving-focused abstraction for inference. A weekly finite retraining task maps naturally to batch execution, while the internal endpoint maps to serving infrastructure with readiness and rollout controls. Kubeflow can be valuable later, but adopting it before notebooks, pipelines, or multi-team governance are real needs may add avoidable operational complexity. The decision should evaluate ecosystem tools against workflow pain rather than tool popularity.
</details>

<details>
<summary>6. A model-serving Pod is Running, but users receive errors for the first few minutes after every rollout. Logs show the container is downloading weights and warming the model during that time. What should you change?</summary>

Add or adjust startup and readiness probes so traffic is withheld until the model server can actually answer requests. Running only means the container process exists; it does not prove the model is loaded, GPU memory is allocated, and prediction calls are safe. A startup probe can give a slow-loading model enough time before restarts interfere, while readiness keeps the Service from routing requests too early. The rollout strategy should also preserve enough warm replicas while new ones become ready.
</details>

<details>
<summary>7. A development cluster has one GPU shared by several lightweight notebook users. Whole-GPU allocation leaves most of the accelerator idle, and production workloads are not allowed on this cluster. Which approach could improve utilization while preserving the right trade-off?</summary>

Configure GPU time-slicing for suitable development workloads and document that isolation and latency predictability are weaker than whole-GPU allocation. Time-slicing can improve utilization when notebooks are light and strict isolation is not required. It should not be presented as the same thing as MIG or exclusive allocation because noisy-neighbor behavior is possible. The answer is acceptable precisely because the scenario keeps production latency-sensitive workloads out of that shared environment.
</details>

<details>
<summary>8. An inference Deployment requests `nvidia.com/gpu: 1` and the cluster has a GPU node with allocatable capacity. The Pod is still Pending, and node inspection shows the taint `accelerator=gpu:NoSchedule`. What is the most likely fix?</summary>

Add a matching toleration to the Pod, and optionally add node selection or affinity to make the intended GPU node pool explicit. A taint repels Pods unless they have a matching toleration, even if the node has the resource the Pod requests. The GPU limit reserves the device, while the toleration permits scheduling onto the tainted node. Selectors or affinity then make the placement intent easier to review and debug.
</details>

## Hands-On Exercise: Simulate and Debug a GPU Scheduling Request

In this exercise, you will create a Pod that requests a GPU and then inspect the scheduling result. You do not need a physical GPU for the exercise. In a typical local or CPU-only cluster, the expected result is a Pending Pod with a scheduler event showing that no node has enough `nvidia.com/gpu` capacity.

Before starting, define the common Kubernetes alias once if you want to use the shorter commands shown below. The full command `kubectl` works the same way, and the alias is only for convenience after the first explanation.

```bash
alias k=kubectl
```

1. Create a file named `gpu-pod.yaml` with a Pod that requests one NVIDIA GPU. The image and command are real, but the scheduler must find a node advertising `nvidia.com/gpu` before the container can run.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test-pod
spec:
  restartPolicy: Never
  containers:
    - name: cuda-container
      image: nvidia/cuda:12.4.1-base-ubuntu22.04
      command: ["nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
```

<details>
<summary>Solution for task 1</summary>

The important field is the extended resource limit under `resources.limits`. In a real GPU cluster, the NVIDIA device plugin or GPU Operator must advertise `nvidia.com/gpu` on at least one node before this Pod can run. The `restartPolicy: Never` setting fits the lab because the Pod is a one-time scheduling test rather than a long-running service.
</details>

2. Apply the manifest to your current Kubernetes context. Use a disposable namespace if your environment requires one, but keep the Pod name unchanged so the later commands match.

```bash
k apply -f gpu-pod.yaml
```

<details>
<summary>Solution for task 2</summary>

The expected command is `k apply -f gpu-pod.yaml` after defining `alias k=kubectl`, or the equivalent full `kubectl apply -f gpu-pod.yaml`. If your context points at a shared cluster, use the namespace policy your environment requires and keep the Pod name stable. The apply operation only asks the API server to create the object; it does not prove that scheduling has succeeded.
</details>

3. Check the Pod status and observe whether it starts. In a CPU-only cluster, it should remain Pending because no node advertises the extended GPU resource.

```bash
k get pod gpu-test-pod
```

<details>
<summary>Solution for task 3</summary>

In a CPU-only lab, the useful result is a Pending Pod, not a failure of the exercise. Pending tells you the container has not started because the scheduler has not found a suitable node. If the Pod runs in your environment, that means your cluster has a GPU scheduling path available, and you should still inspect the node and event evidence to prove why it worked.
</details>

4. Describe the Pod and read the scheduler events near the bottom of the output. Look for a `FailedScheduling` event that mentions `nvidia.com/gpu`, because that event connects the symptom to the missing schedulable resource.

```bash
k describe pod gpu-test-pod
```

<details>
<summary>Solution for task 4</summary>

The strongest evidence is an event from the scheduler that names insufficient `nvidia.com/gpu` capacity. That event means the scheduler could not find a node with free allocatable extended resources that also satisfied the Pod's other placement rules. Do not change the image or command first, because a Pending Pod has not reached the point where the container runtime could execute them.
</details>

5. Inspect node allocatable resources to connect the Pod event to cluster state. If no node lists `nvidia.com/gpu`, Kubernetes has no GPU capacity to allocate, even if a physical machine somewhere in the environment has accelerator hardware but no device plugin integration.

```bash
k describe nodes
```

<details>
<summary>Solution for task 5</summary>

Search the `Allocatable` sections for `nvidia.com/gpu`. If no node advertises that resource, the workload manifest cannot be the only fix because Kubernetes has no schedulable accelerator capacity. In a real platform, the next checks would include GPU node pool existence, driver installation, device plugin health, node taints, and whether another Pod already consumed the available GPU.
</details>

6. Clean up the Pod after you have captured the result. Leaving a Pending Pod behind is harmless in a lab, but cleanup is part of good cluster hygiene.

```bash
k delete pod gpu-test-pod
```

<details>
<summary>Solution for task 6</summary>

The cleanup command removes the test Pod and clears the Pending object from the namespace. Cleanup matters because repeated labs can leave misleading scheduler events or names that collide with later attempts. If deletion hangs, check whether your current context and namespace match the object you created.
</details>

Use this success criteria checklist to verify that you practiced the whole troubleshooting path rather than only creating the YAML:

- [ ] You created `gpu-pod.yaml` with a container resource limit requesting `nvidia.com/gpu: 1`.
- [ ] You applied the manifest with `kubectl` or the `k` alias after defining the alias.
- [ ] You observed the Pod status and correctly distinguished Pending scheduling failure from a container runtime failure.
- [ ] You found a `FailedScheduling` event or equivalent scheduler message explaining insufficient GPU resources in a CPU-only cluster.
- [ ] You inspected node descriptions and connected missing allocatable `nvidia.com/gpu` capacity to the scheduling result.
- [ ] You can explain what would need to change in a real GPU cluster: GPU nodes, drivers, device plugin or GPU Operator, available capacity, and any required tolerations or node selection.
- [ ] You deleted the lab Pod after completing the investigation.

For extra practice, modify the manifest by adding a fake node selector such as `accelerator: nvidia` and apply it again. Compare the scheduler event with the previous result. The exact wording may differ by Kubernetes version, but the reasoning should be the same: the scheduler can only bind a Pod when resource requests, node labels, taints, tolerations, and available capacity all line up.

## Sources

- [Kubernetes documentation: Device Plugins](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)
- [Kubernetes documentation: Extended resources for a container](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#extended-resources)
- [Kubernetes documentation: Assign Pods to Nodes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
- [Kubernetes documentation: Taints and Tolerations](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
- [Kubernetes documentation: Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes documentation: Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Kubernetes documentation: Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)
- [NVIDIA GPU Operator documentation](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html)
- [NVIDIA Kubernetes device plugin documentation](https://github.com/NVIDIA/k8s-device-plugin)
- [Kubeflow documentation](https://www.kubeflow.org/docs/)
- [KServe documentation](https://kserve.github.io/website/latest/)
- [Ray documentation: Ray on Kubernetes](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- [vLLM documentation](https://docs.vllm.ai/en/latest/)
- [Volcano documentation](https://volcano.sh/en/docs/)
- [kubernetes.io: scheduling gpus](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/) — The Kubernetes GPU scheduling documentation directly covers plugin installation, `nvidia.com/gpu`, and the `limits`-based request semantics.
- [kubernetes.io: liveness readiness startup probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) — The probes documentation directly explains startup-probe gating and failed-readiness behavior.
- [github.com: kubeflow](https://github.com/kubeflow/kubeflow) — The Kubeflow repository overview explicitly describes Kubeflow as a foundation of tools and an AI reference platform on Kubernetes.
- [github.com: kserve](https://github.com/kserve/kserve) — The KServe repository README explicitly describes the platform, its autoscaling, advanced deployment, and multi-framework inference features.
- [github.com: ray](https://github.com/ray-project/ray) — The Ray repository overview directly describes Ray's distributed runtime and its Train, Data, and Serve libraries, and notes Kubernetes support.
- [github.com: vllm](https://github.com/vllm-project/vllm) — The vLLM repository directly describes the project as a high-throughput, memory-efficient LLM serving engine.
- [github.com: gpu operator](https://github.com/NVIDIA/gpu-operator) — The GPU Operator README explicitly lists the automated GPU software components it manages on Kubernetes.

## Next Module

[Module 3.9: WebAssembly and Cloud Native](../module-3.9-webassembly/) - The emerging technology that can complement containers for fast-starting, portable, and strongly sandboxed workloads.
