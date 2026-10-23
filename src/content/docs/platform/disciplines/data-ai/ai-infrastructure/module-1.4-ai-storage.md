---
title: "Module 1.4: High-Performance Storage for AI"
slug: platform/disciplines/data-ai/ai-infrastructure/module-1.4-ai-storage
sidebar:
  order: 5
revision_pending: false
---
> **Complexity**: `[MEDIUM]`
>
> **Time to Complete**: 3 hours
>
> **Prerequisites**: Kubernetes storage fundamentals, including PersistentVolumes, PersistentVolumeClaims, StorageClasses, and CSI drivers; basic understanding of ML training data pipelines, including datasets, batches, and data loaders; recommended completion of [Module 1.1: GPU Provisioning](../module-1.1-gpu-provisioning/); and practical familiarity with object storage such as S3, GCS, or MinIO.

---

## What You'll Be Able to Do

After completing this module, you will be able to:

- **Design** high-throughput storage architectures for AI workloads that separate training data, checkpoints, and model artifacts by access pattern.
- **Implement** Kubernetes storage solutions using CSI drivers, local NVMe, distributed filesystems, and object-backed filesystems without breaking scheduler placement.
- **Configure** caching layers that reduce data loading bottlenecks during repeated and distributed training runs.
- **Evaluate** local NVMe, network-attached filesystems, cloud object stores, and dataset caches against measurable AI workload I/O profiles.
- **Diagnose** whether a slow training job is compute-bound, CPU-bound, or storage-bound using GPU utilization, data-loader timing, and storage benchmarks.

## Why This Module Matters

Hypothetical scenario: your platform team has just delivered a clean GPU pool for the machine learning group. The nodes have modern accelerators, the scheduler can place GPU jobs, and the team has confidence in quota enforcement because earlier modules covered provisioning and sharing. Then the first serious image-training job lands, eight GPUs light up for a few seconds, and the utilization graph flattens around forty percent because the workers spend most of each step waiting for the next batch to arrive from storage.

Meta's Llama 3 training run is the same lesson at industrial scale. In the Llama 3 paper, Meta describes a Tectonic-based storage fabric with **240 PB of capacity** across **7,500 SSD-equipped servers**, supporting **2 TB/s sustainable** and **7 TB/s peak** throughput for pre-training I/O and highly bursty checkpoint writes. The **54-day** figure in that paper is a fault-analysis snapshot window for training interruptions, not a total data-served duration, and Meta does not report a single derived average read rate across the full run. The takeaway is structural: industrial LLM training needs storage that can sustain terabyte-scale throughput and absorb checkpoint bursts without starving accelerators for weeks.

That situation is frustrating because it looks like a GPU problem from a distance, but it is usually a data path problem. A training loop cannot compute on examples it has not loaded, decoded, shuffled, transferred, and staged, so storage design directly determines how much expensive accelerator time turns into useful gradient updates. If the platform exposes only a generic network filesystem or a direct object-store mount, the job may be correct yet still waste more money than a scheduling bug would.

This module teaches storage as an operational design problem rather than a shopping list of tools. You will start by recognizing the I/O shape of different AI workloads, then build up the storage tiers that Kubernetes can expose: local NVMe for hot data, distributed filesystems for shared warm data, object storage for durable cold data, and caching systems that move bytes closer to the GPUs. The goal is not to memorize one preferred product; the goal is to choose a path that matches the dataset, checkpoint cadence, fault-tolerance needs, and Kubernetes scheduling constraints in front of you.

The performance gap explains why the storage layer deserves its own module. GPU memory and GPU compute move at speeds that storage systems cannot approach, so the platform has to hide latency through locality, batching, prefetching, and parallelism. The relative order is stable enough to use as a design compass: GPU memory and compute sit closest to the accelerator, local NVMe is the fastest node-local tier, shared filesystems trade latency for sharing semantics, and object storage trades per-request latency for durability and cost at scale.

> **Landscape snapshot — as of 2026-06. This changes fast; verify against vendor docs before relying on specifics.**
>
> | Layer | Indicative throughput / latency |
> |-------|----------------------------------|
> | GPU compute (A100 BF16) | ~312 TFLOPS |
> | GPU memory (HBM3) | ~2 TB/s |
> | Local NVMe SSD | ~7 GB/s read; 10–100 µs latency |
> | Network filesystem (e.g., CephFS) | ~1–5 GB/s; 0.5–5 ms latency |
> | Object storage (e.g., S3) | ~100–500 MB/s per prefix; 10–100 ms per request |
>
> **Workload I/O profiles (indicative):**
>
> | Workload | Data size | Access pattern | Typical read size | Throughput need |
> |----------|-----------|----------------|-------------------|-----------------|
> | Image classification (ImageNet) | ~150 GB | Random small files | 100–500 KB | ~2–5 GB/s |
> | Object detection (COCO) | ~20 GB | Random medium files | 200 KB–5 MB | ~1–3 GB/s |
> | NLP pre-training (C4) | ~800 GB | Sequential shards | 1–100 MB | ~5–20 GB/s |
> | Video training | 5–50 TB | Sequential large files | 50–500 MB | ~10–50 GB/s |
> | LLM fine-tuning (tokenized) | 10–100 GB | Sequential | 1–10 MB | ~1–5 GB/s |
> | Checkpoint save | 1–50 GB per save | Sequential write burst | Full model state | ~5–20 GB/s burst |
>
> **Dataset-cache tooling (peer capabilities):** Fluid (CNCF Incubating since 2026-01-08) coordinates cache engines such as Alluxio, JuiceFS, and JindoFS with dataset-aware scheduling; JuiceFS exposes POSIX over object storage with local cache; Alluxio tiers memory and disk cache in front of under-storage.

These figures are not promises that every disk, cluster, or bucket will match them on your hardware. They are a reminder that storage sits far away from the compute unit in both latency and throughput, especially when the training workload issues millions of small reads. A platform that ignores this gap can buy more GPUs and still deliver slower training, while a platform that respects the gap can improve utilization with a cache, a packaging change, or a different checkpoint strategy.

## The I/O Bottleneck in ML Workloads

Every training step contains a small pipeline, and the slowest stage controls the useful pace of the whole job. The framework asks a data loader for a batch, the data loader reads files or records, CPU workers decode and transform the examples, the host transfers tensors to GPU memory, and only then does the forward and backward pass run. When storage is slow, GPU utilization appears low even if the model, CUDA libraries, and GPU scheduling are healthy.

```mermaid
flowchart LR
    subgraph Training_Loop ["Training Loop (This dominates when storage is slow)"]
        direction LR
        A["1. Load batch\nRead from storage\n(IO bound)\n100ms - 5s"] --> B["2. Transfer to GPU\nCPU RAM -> GPU VRAM\n(PCIe bound)\n1-10ms"]
        B --> C["3. Compute\nForward + Backward\n(compute)\n10-100ms"]
    end
```

The diagram deliberately separates storage reads from GPU transfer because they fail in different ways. A PCIe transfer bottleneck often shows up after the batch is already resident in host memory, while a storage bottleneck shows up before the CPU workers can produce the batch. That distinction matters when you decide whether to tune `DataLoader` workers, pre-stage data onto local disks, package small files into larger records, or change the filesystem entirely.

Different ML workloads have radically different I/O profiles, and platform teams get into trouble when they treat all training jobs as if they were the same. Image training often reads a huge count of tiny objects in random order, which punishes object storage and metadata-heavy network filesystems. Tokenized language-model training is usually friendlier because it can read larger sequential shards, but the required aggregate throughput may be much higher because the GPUs consume tokens quickly. Video workloads favor large sequential reads; checkpointing flips the problem from reads to write bursts. See the **Landscape snapshot** above for indicative size and throughput ranges by workload type.

The key design move is to translate the workload into read size, randomness, concurrency, and write burst requirements before choosing storage. Image classification against millions of JPEG files may need local caching or dataset repackaging even when the total dataset is modest. Video training may tolerate higher latency per file because each read is large, but it can saturate network links if several jobs stream at once. Checkpointing flips the problem from reads to writes, and a fast read cache does not automatically make checkpoint saves safe or durable.

> **Pause and predict:** If a large language model and an image classifier both report low GPU utilization, which one would you expect to benefit more from packing data into larger sequential shards, and which one would you inspect first for metadata or small-file overhead?
>
> **Answer:** The image classifier usually benefits most from packing because millions of small random reads create metadata and request overhead; the LLM workload is more likely to need aggregate sequential throughput across already-sharded data.

Before optimizing, measure the job that is actually slow. GPU utilization tells you whether accelerators are waiting, but it does not prove storage is the cause by itself. Correlate that signal with data-loader timing, CPU saturation, network throughput, filesystem latency, and pod placement, because a CPU-heavy augmentation pipeline can look similar to an I/O bottleneck from the GPU side.

```bash
# Monitor GPU utilization during training
# If GPU util is < 80% and you're not memory-bound, you're IO-bound

# Quick check: poll nvidia-smi during training (minimal GPU images often lack watch)
kubectl exec -it training-pod -- bash -c 'while true; do nvidia-smi --query-gpu=utilization.gpu,utilization.memory --format=csv,noheader; sleep 1; done'

# Better: check PyTorch DataLoader timing
# Add this to your training script:
# import time
# for batch in dataloader:
#     load_end = time.time()
#     print(f"Data load: {load_end - load_start:.3f}s")
#     # ... training step ...
#     load_start = time.time()
```

The command is intentionally simple because the first measurement should be easy enough to run during an incident. If the GPU is below target utilization and the data loader repeatedly spends longer than the compute step, storage and preprocessing deserve immediate attention. If the data loader is fast but GPU memory utilization is high, you may be facing a model-memory or batch-size issue instead; the important skill is to avoid tuning storage when the evidence points somewhere else.

> **Stop and think:** If GPU utilization is around forty percent, what three metrics would you check before blaming the storage backend?
>
> **Answer:** Check GPU utilization and memory pressure, data-loader wait time per batch, and an infrastructure signal such as filesystem latency, node network throughput, or cache hit rate.

## Storage Tiers for AI

AI platforms usually need multiple storage tiers because no single tier gives perfect cost, latency, throughput, durability, and sharing semantics. Local disks are fast and close to the training process, but they disappear with the node and cannot be mounted by every pod at once. Distributed filesystems can provide shared POSIX access, but their metadata services and network paths create latency that small-file workloads feel immediately. Object storage is durable and cheap at scale, but it exposes a request-oriented API rather than the low-latency filesystem behavior most training scripts expect.

```mermaid
flowchart TD
    A["GPU VRAM (training)\nClosest to compute\nManaged by framework"]
    B["Local NVMe (hot cache)\nNode-local; lowest remote latency\nTopoLVM, OpenEBS LVM"]
    C["Distributed FS (warm)\nShared POSIX; network path\nCephFS, GlusterFS, JuiceFS"]
    D["Object Storage (cold)\nDurable; request-oriented API\nS3, GCS, MinIO"]
    E["Tape/Archive\nArchival\nGlacier, Coldline"]

    A -->|"Cost #36;, Speed #36;#36;#36;#36;"| B
    B -->|"Cost #36;#36;, Speed #36;#36;#36;"| C
    C -->|"Cost #36;#36;#36;, Speed #36;#36;"| D
    D -->|"Cost #36;#36;#36;#36;, Speed #36;"| E
```

Think of the pyramid as a map of distance from the GPU. The farther data sits from the accelerator, the more the platform must compensate with prefetching, caching, batching, or careful scheduling. The closer data sits to the accelerator, the more the platform must compensate for durability, capacity, and scheduling restrictions. A good architecture does not try to put every byte on the fastest tier; it puts the active working set on the fastest tier while keeping the canonical dataset in a durable tier that can survive node loss.

The platform team's job is to make movement between tiers predictable. For example, a training pod can read a canonical dataset from object storage, stage the current shard set onto local NVMe, and write durable checkpoints to a shared filesystem or object-backed layer. That flow gives the job a fast hot path during the epoch while still allowing the team to rebuild state after rescheduling. Kubernetes storage objects are the contract that lets you expose those choices without hard-coding node paths into every training script.

Local NVMe matters because a modern SSD can serve sequential reads at several gigabytes per second and can handle random I/O far better than a remote object store. The practical strategy is to keep the active dataset, or a cache of it, on local NVMe while the canonical copy lives in object storage. This is especially effective for repeated experiments over the same data, where the first run warms the cache and later runs avoid most remote reads.

TopoLVM is a CSI driver that provisions PersistentVolumes from local LVM volume groups with topology awareness. The topology part is essential: a local volume only exists on the node where its backing device exists, so Kubernetes must delay binding until it knows where the pod will run. Without that scheduler coordination, a PVC can bind to storage on one node while the GPU pod lands on another node, which leaves the job pending or forces manual repair.

```bash
# Install TopoLVM
helm repo add topolvm https://topolvm.github.io/topolvm
helm repo update

helm install topolvm topolvm/topolvm \
  --namespace topolvm-system \
  --create-namespace \
  --set controller.replicaCount=2 \
  --set node.volumeGroup.name=nvme-vg    # LVM VG name on each node
```

The StorageClass is where the scheduling intent becomes visible. `volumeBindingMode: WaitForFirstConsumer` tells Kubernetes not to bind the PVC until a pod actually needs it, which gives the scheduler a chance to consider both GPU availability and local storage availability. `allowVolumeExpansion` is useful for training caches because dataset working sets often grow after the first successful experiment.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: nvme-local
provisioner: topolvm.io
parameters:
  topolvm.io/device-class: nvme       # Maps to a device class in TopoLVM config
volumeBindingMode: WaitForFirstConsumer # Delay binding until Pod is scheduled
allowVolumeExpansion: true
reclaimPolicy: Delete
```

The training pod mounts a cache PVC exactly like it would mount any other Kubernetes volume, which is the point of using CSI rather than hand-managed host paths. The application sees a normal directory at `/data/cache`, while the platform keeps the placement and allocation logic inside Kubernetes. In a production environment, you would also constrain the pod to nodes with the right GPU type and local disk pool, but the storage pattern remains the same.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: training-cache
  namespace: ml-training
spec:
  storageClassName: nvme-local
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: image-trainer
  namespace: ml-training
spec:
  containers:
    - name: trainer
      image: nvcr.io/nvidia/pytorch:24.09-py3
      volumeMounts:
        - name: cache
          mountPath: /data/cache
        - name: dataset
          mountPath: /data/s3     # S3 FUSE mount or pre-downloaded
      resources:
        limits:
          nvidia.com/gpu: 4
  volumes:
    - name: cache
      persistentVolumeClaim:
        claimName: training-cache
    - name: dataset
      persistentVolumeClaim:
        claimName: imagenet-s3
```

OpenEBS LVM LocalPV offers a similar local-volume pattern with a different operational footprint. It is attractive when you want a simpler local-provisioning story and already manage node volume groups outside the storage driver. As with TopoLVM, the key is not the product name but the combination of local disk performance, CSI lifecycle management, and delayed binding so the scheduler does not make impossible placement decisions.

```bash
# Install OpenEBS (default chart enables Local PV LVM; disable Mayastor if not needed)
helm repo add openebs https://openebs.github.io/openebs
helm repo update

helm install openebs openebs/openebs \
  --namespace openebs \
  --create-namespace \
  --set engines.replicated.mayastor.enabled=false
```

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: openebs-nvme
provisioner: local.csi.openebs.io
parameters:
  storage: "lvm"
  vgpattern: "nvme-vg"          # LVM volume group pattern (regex)
  fsType: "xfs"                  # XFS recommended for large files
volumeBindingMode: WaitForFirstConsumer
```

An init container is the simplest cache warmer because it makes the data movement explicit and keeps the training container focused on training. The job starts, the init container copies the selected dataset from object storage to the cache volume, and the main container runs only after staging completes. This pattern is not perfect for multi-terabyte datasets or highly shared caches, but it is reliable, easy to debug, and often sufficient for medium-sized datasets.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: training-with-staging
  namespace: ml-training
spec:
  template:
    spec:
      initContainers:
        - name: stage-data
          image: amazon/aws-cli:2.17
          command: ["sh", "-c"]
          args:
            - |
              echo "Staging dataset from S3..."
              start=$(date +%s)
              aws s3 sync s3://my-datasets/imagenet/ /data/cache/imagenet/ \
                --no-sign-request --quiet
              end=$(date +%s)
              size=$(du -sh /data/cache/imagenet/ | cut -f1)
              echo "Staged $size in $((end-start)) seconds"
          volumeMounts:
            - name: cache
              mountPath: /data/cache
          resources:
            requests:
              cpu: "4"
              memory: 8Gi
      containers:
        - name: trainer
          image: nvcr.io/nvidia/pytorch:24.09-py3
          command: ["torchrun", "--nproc_per_node=4", "train.py", "--data_dir=/data/cache/imagenet"]
          volumeMounts:
            - name: cache
              mountPath: /data/cache
          resources:
            limits:
              nvidia.com/gpu: 4
      volumes:
        - name: cache
          persistentVolumeClaim:
            claimName: training-cache
      restartPolicy: OnFailure
```

Before running a staged-training pattern in production, decide how cache freshness will be enforced. A copied dataset is fast, but it can become stale if the canonical object-store prefix changes after the cache was populated. Some teams solve that with immutable dataset versions, such as `imagenet-v3` rather than `latest`; others include a manifest checksum in the job and refuse to train if the local cache does not match it. Either approach is better than silently training against a mixture of old and new files.

## Distributed Filesystems and Object-Backed POSIX

Distributed filesystems solve a different problem than local NVMe. They provide shared access, larger aggregate capacity, and sometimes stronger durability, which makes them useful for multi-node training, shared datasets, and checkpoint directories. The tradeoff is that each metadata lookup and data read crosses a network path, so the system has to be sized, tuned, and measured under the same access pattern the AI job will use.

CephFS is widely deployed in Kubernetes through Rook because it gives applications POSIX-compatible filesystem semantics backed by a Ceph cluster. That POSIX behavior matters because many training scripts expect files, directories, renames, and ordinary path traversal rather than object-store APIs. CephFS can be a good shared warm tier, but it is still not a magic replacement for local caching when a workload performs millions of tiny random reads.

The strengths and weaknesses for AI workloads are practical rather than ideological. CephFS supports ReadWriteMany access, can scale with more OSDs and metadata servers, and integrates cleanly with Kubernetes. At the same time, metadata latency, network saturation, and small-file overhead can dominate image workloads unless the dataset is packed, cached, or prewarmed. The correct response is not to reject CephFS; it is to place it where shared semantics matter and avoid asking it to behave like GPU-local memory.

```yaml
# Rook-Ceph CephFS StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: cephfs-ai
provisioner: rook-ceph.cephfs.csi.ceph.com
parameters:
  clusterID: rook-ceph
  fsName: ai-filesystem
  pool: ai-data-pool
  csi.storage.k8s.io/provisioner-secret-name: rook-csi-cephfs-provisioner
  csi.storage.k8s.io/provisioner-secret-namespace: rook-ceph
  csi.storage.k8s.io/node-stage-secret-name: rook-csi-cephfs-node
  csi.storage.k8s.io/node-stage-secret-namespace: rook-ceph
mountOptions:
  - noatime                    # Disable access time updates (major perf win)
  - nodiratime
```

The `noatime` and `nodiratime` options are small settings with large consequences for read-heavy training. Traditional access-time updates create metadata writes when files are read, which means an apparently read-only workload can still pressure the metadata path. Disabling those updates is usually safe for datasets and checkpoint inputs because training jobs rarely depend on access times for correctness.

RDMA-capable storage networks such as InfiniBand or RoCE can also help by reducing network latency and CPU overhead, but they cannot rescue a workload that turns every example into a serialized metadata operation. The storage path still has to match the workload shape.

> **Stop and think:** Why can `noatime` or RDMA matter even when a storage benchmark shows acceptable sequential throughput?
>
> **Answer:** `noatime` removes metadata writes from read-heavy paths, while RDMA reduces network overhead; both matter because training bottlenecks often come from latency and metadata pressure rather than headline sequential bandwidth.

JuiceFS targets the awkward space between object storage and filesystem expectations. It presents a POSIX client through FUSE and CSI, stores metadata in a separate engine such as Redis or PostgreSQL, stores data in object storage, and caches reads locally. That architecture lets a team keep the durable copy in S3-compatible storage while giving training code a familiar path-based interface.

```mermaid
flowchart LR
    Client["POSIX Client\n(FUSE/CSI)"]
    Meta["Metadata Engine\n(Redis/PG)"]
    Obj["Object Storage\n(S3)"]
    Cache["Local Cache\n(NVMe or RAM)"]

    Client -->|"Metadata"| Meta
    Client -->|"Data path"| Obj
    Client <-->|"Local caching"| Cache
```

The separation of metadata, object data, and local cache creates both power and responsibility. A warm JuiceFS cache can make repeated reads approach local-disk behavior, but the metadata engine is now part of the critical path and must be monitored like any other stateful service. Object storage remains the durable backend, so network reliability, bucket policies, and request rates still matter even when most hot reads are served locally.

```bash
# Install JuiceFS CSI Driver
helm repo add juicefs https://juicedata.github.io/charts/
helm repo update

helm install juicefs-csi juicefs/juicefs-csi-driver \
  --namespace kube-system \
  --set storageClasses[0].name=juicefs-sc \
  --set storageClasses[0].enabled=true \
  --set storageClasses[0].backend.name=ai-data \
  --set storageClasses[0].backend.metaurl=redis://:password@redis-master:6379/1 \
  --set storageClasses[0].backend.storage=s3 \
  --set storageClasses[0].backend.bucket=s3://my-ai-datasets \
  --set storageClasses[0].backend.accessKey=AKIAIOSFODNN7EXAMPLE \
  --set storageClasses[0].backend.secretKey=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY \
  --set storageClasses[0].cachePVC=juicefs-cache
```

Treat the command as a shape, not a production secret-management pattern. In a real cluster, backend credentials should come from Kubernetes Secrets or an external secret operator, the metadata engine should have backups and access controls, and the cache should be sized from observed working sets. The important storage lesson is that the CSI driver turns the object-backed filesystem into a normal PVC interface that training teams can consume without rewriting every data loader.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: juicefs-ai
provisioner: csi.juicefs.com
parameters:
  csi.storage.k8s.io/provisioner-secret-name: juicefs-secret
  csi.storage.k8s.io/provisioner-secret-namespace: kube-system
  juicefs/mount-options: |
    cache-dir=/var/jfsCache
    cache-size=512000          # 500GB local cache
    buffer-size=1024           # 1GB read-ahead buffer
    prefetch=3                 # Prefetch 3 blocks ahead
    max-uploads=40             # Parallel upload threads
    metacache-expire=300       # Metadata cache TTL (seconds)
    open-cache=300             # Open file handle cache
reclaimPolicy: Retain
volumeBindingMode: Immediate
```

The mount options show where performance choices become explicit. A larger cache can reduce repeat reads but competes with other workloads for local disk. A larger read-ahead buffer can improve sequential scans but may waste bandwidth when the access pattern is random. `Retain` protects the filesystem from accidental PVC deletion, which is often appropriate when the volume represents a durable dataset namespace rather than a disposable scratch cache.

> **Pause and predict:** Which approach would you choose here and why: a ReadWriteMany CephFS volume for a multi-node training job whose dataset changes daily, or a JuiceFS object-backed mount with local cache for many repeated experiments over immutable dataset versions?
>
> **Answer:** CephFS is the better default for frequently updated shared POSIX data, while JuiceFS is stronger for immutable versions with repeated reads because the cache can turn object-backed storage into a fast warm path.

## Dataset Caching and Data-Aware Scheduling

Caching becomes most valuable when the same data is read repeatedly by many jobs. Without a cache, each run pays the object-store request latency and network transfer cost again, even if another pod on the same node just read the same files. With a cache, the first read is still cold, but later reads can be served from local disk or memory, and the platform can stop treating every training run as a brand-new download.

```text
Hypothetical scenario: fifty engineers each run a training job that downloads 500 GB from S3.

Engineer 1 training job: Downloads 500GB from S3 -> 30 min
Engineer 2 training job: Downloads 500GB from S3 -> 30 min
...
Engineer 50 training job: Downloads 500GB from S3 -> 30 min

Total: 25 TB downloaded, 25 hours of wait time, $50+ in S3 egress
```

```text
Hypothetical scenario: the same fifty engineers reuse a warm node-local cache.

Engineer 1 training job: Downloads 500GB from S3 -> 30 min (cold)
Engineer 2 training job: Reads from cache -> 2 min (warm)
...
Engineer 50 training job: Reads from cache -> 2 min (warm)

Total: 500GB downloaded, 2 hours total wait, $1 in S3 egress
```

Those numbers are illustrative, but the direction is real: repeated reads turn network traffic into local traffic when the cache is warm. The hard part is keeping the cache close to the jobs that need it. If Kubernetes schedules a pod on a node with no cached data, the pod experiences a cold read even though another node in the cluster has the dataset ready. That is why storage design and scheduling design cannot be separated for AI workloads.

> **Stop and think:** If fifty engineers repeatedly train against the same five-hundred-gigabyte dataset every day, what costs would you include in the cache business case besides object-store egress?
>
> **Answer:** Include GPU idle time, experiment turnaround, network contention, cache disk cost, operational overhead, and the risk of stale data.

Fluid brings dataset-aware scheduling to Kubernetes as a CNCF Incubating project (see the **Landscape snapshot** for current maturity). Instead of treating a dataset as just another PVC, Fluid models the dataset as a resource and coordinates cache engines such as Alluxio, JuiceFS, or JindoFS under the hood. That resource model lets the platform track cache placement and influence pod scheduling so jobs prefer nodes where the needed data is already warm.

```bash
# Install Fluid
helm repo add fluid https://fluid-cloudnative.github.io/charts
helm repo update

helm install fluid fluid/fluid \
  --namespace fluid-system \
  --create-namespace
```

The Dataset resource describes the canonical location, while the runtime describes how the cache should be built and maintained. In the following example, the dataset points at an S3 path, and the Alluxio runtime gives each cache worker both memory and SSD tiers. That combination is useful because metadata and small hot objects can live in memory while larger cached blocks can live on SSD.

```yaml
apiVersion: data.fluid.io/v1alpha1
kind: Dataset
metadata:
  name: imagenet
  namespace: ml-training
spec:
  mounts:
    - mountPoint: s3://my-datasets/imagenet/
      name: imagenet
      options:
        aws.accessKeyId: AKIAIOSFODNN7EXAMPLE
        aws.region: us-east-1
      encryptOptions:
        - name: aws.secretAccessKey
          valueFrom:
            secretKeyRef:
              name: s3-credentials
              key: secretAccessKey
---
apiVersion: data.fluid.io/v1alpha1
kind: AlluxioRuntime
metadata:
  name: imagenet
  namespace: ml-training
spec:
  replicas: 3                    # 3 cache workers
  tieredstore:
    levels:
      - mediumtype: MEM
        path: /dev/shm
        quota: 100Gi              # RAM cache per worker
        high: "0.95"
        low: "0.7"
      - mediumtype: SSD
        path: /var/cache/alluxio
        quota: 400Gi              # SSD cache per worker
        high: "0.95"
        low: "0.7"
  fuse:
    args:
      - fuse
      - --attr-timeout=7200s
      - --entry-timeout=7200s
    cleanPolicy: OnDemand
  properties:
    alluxio.user.metadata.cache.enabled: "true"
    alluxio.user.metadata.cache.expireTime: "2day"
    alluxio.user.streaming.data.timeout: "300sec"
```

The training pod consumes the dataset through the PVC Fluid creates. From the application perspective, this is still a mounted path, which is exactly what you want for adoption. From the scheduler perspective, the dataset now carries locality information that ordinary PVCs do not express. That is the difference between "mount this shared volume somewhere" and "place this job where the data is already warm if the cluster has a reasonable option."

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: imagenet-training
  namespace: ml-training
spec:
  template:
    spec:
      containers:
        - name: trainer
          image: nvcr.io/nvidia/pytorch:24.09-py3
          command: ["python", "train.py", "--data_dir=/data/imagenet"]
          volumeMounts:
            - name: imagenet
              mountPath: /data/imagenet
              readOnly: true
          resources:
            limits:
              nvidia.com/gpu: 4
      volumes:
        - name: imagenet
          persistentVolumeClaim:
            claimName: imagenet    # Automatically created by Fluid
      restartPolicy: OnFailure
```

Fluid also supports explicit warmup through a DataLoad resource. Prewarming is useful when benchmark correctness matters, because a cold first epoch can make one storage design look worse than it will be during steady-state training. It is also useful before scheduled training windows, where the platform can move data during a quieter period and reserve GPU time for compute rather than downloads.

```yaml
# Fluid automatically injects scheduling hints
# Pods using the 'imagenet' dataset prefer nodes where Alluxio workers
# have already cached ImageNet data

# You can also trigger pre-warming:
apiVersion: data.fluid.io/v1alpha1
kind: DataLoad
metadata:
  name: imagenet-warmup
  namespace: ml-training
spec:
  dataset:
    name: imagenet
    namespace: ml-training
  loadMetadata: true
  target:
    - path: /
      replicas: 2    # Cache 2 copies for fault tolerance
```

Alluxio can also be deployed independently when a team wants more control over the cache layer. That may be appropriate in an environment with multiple compute platforms or a mature storage team that already operates Alluxio outside Kubernetes. The cost is that you now own more of the integration and scheduling behavior yourself, so the operational model should be chosen deliberately rather than by habit.

```bash
helm repo add alluxio-charts https://alluxio-charts.storage.googleapis.com/openSource/2.9.5
helm repo update

helm install alluxio alluxio-charts/alluxio \
  --namespace alluxio \
  --create-namespace \
  --set master.count=1 \
  --set worker.count=3 \
  --set worker.resources.limits.memory=32Gi \
  --set tieredStore.levels[0].level=0 \
  --set tieredStore.levels[0].mediumtype=MEM \
  --set tieredStore.levels[0].path=/dev/shm \
  --set tieredStore.levels[0].quota=16Gi \
  --set tieredStore.levels[1].level=1 \
  --set tieredStore.levels[1].mediumtype=SSD \
  --set tieredStore.levels[1].path=/mnt/nvme/alluxio \
  --set tieredStore.levels[1].quota=500Gi \
  --set properties."alluxio.underfs.s3.region"=us-east-1
```

The most common caching failure is celebrating a fast second read without asking whether the third job will land on the same node. Cache hit rate is partly a storage metric and partly a scheduling metric. If you scale the GPU pool, add autoscaling, or mix many datasets, you need to watch whether hot data is distributed across the nodes where future jobs will actually run.

## Checkpoint Storage and Benchmarking

Training data is mostly a read problem, but checkpointing is a write problem with correctness consequences. A checkpoint may include model parameters, optimizer state, random seeds, scheduler state, and training metadata. If it is slow, GPUs wait; if it is corrupt, the team may lose days of progress; if it is stored only on a failed node, recovery may be impossible.

```text
Model parameters:   70B x 2 bytes (BF16)  = 140 GB
Optimizer state:    70B x 8 bytes (Adam)   = 560 GB
Total:              ~700 GB per checkpoint
```

If a storage target writes at two gigabytes per second, saving a checkpoint of that size takes about three hundred and fifty seconds before accounting for metadata, serialization, network contention, and filesystem behavior. That delay is not just annoying; it creates an expensive idle window on every checkpoint interval when checkpointing is synchronous. As model size grows, checkpoint design becomes part of the training architecture rather than an afterthought.

The simplest checkpoint is synchronous and monolithic, which is easy to reason about but expensive. The training process stops, writes one state file, and resumes when the write completes. This is acceptable for small models, infrequent checkpoints, or early experiments, but it can waste a meaningful share of accelerator time in large distributed jobs.

```python
# Training pauses during save
torch.save(model.state_dict(), "/checkpoints/latest.pt")
# 6 minutes of idle GPUs
```

Asynchronous checkpointing reduces the visible pause by copying state to CPU memory and writing in the background. The tradeoff is that the system must protect the in-flight checkpoint from process failure, node failure, and mutation of tensors that training continues to update. In practice, teams use temporary paths, atomic renames, completion markers, and checkpoint validation so a partially written checkpoint is never mistaken for a recoverable one.

```python
import threading

def save_async(state_dict, path):
    torch.save(state_dict, path)

# Clone state dict to CPU, then save in background
state_dict_cpu = {k: v.cpu().clone() for k, v in model.state_dict().items()}
thread = threading.Thread(target=save_async, args=(state_dict_cpu, path))
thread.start()
# Training continues immediately
```

Sharded checkpoints match the distributed shape of modern training. Instead of one worker writing the entire model state, each rank writes its own shard in parallel, which reduces wall-clock save time and avoids funneling every byte through one process. The storage target must still handle the aggregate write burst, so sharding helps most when the filesystem or object-backed layer can accept parallel writes without turning metadata into the next bottleneck. Hypothetical scenario: eight GPUs each writing an 87.5 GB shard at 2 GB/s completes in about 44 seconds wall-clock versus roughly 350 seconds for one serial 700 GB write.

```python
# Requires torch.distributed init and FSDP or model-parallel setup.
from torch.distributed.checkpoint import save

state_dict = {"model": model.state_dict()}
save(state_dict, checkpoint_id=f"/checkpoints/step_{step}")
```

> **Pause and predict:** What is the risk of using asynchronous checkpointing if the node crashes exactly while the background thread is writing the checkpoint?
>
> **Answer:** The write may leave a partial or corrupt checkpoint that looks usable unless the design uses temporary paths, completion markers, atomic promotion, validation, and a durable source of truth.

| Storage Type | Write profile | Best For |
|-------------|---------------|----------|
| Local NVMe (TopoLVM) | Highest node-local sequential bandwidth | Fastest saves; risk of data loss on node failure |
| CephFS / GlusterFS (RWX) | Shared parallel writes across nodes | Shared access, multi-node distributed saves |
| JuiceFS (NVMe cache + S3) | Fast local landing with async object flush | Fast writes with durable object-store backend |
| NFS | Moderate shared throughput; metadata-sensitive | Simple, widely available; benchmark before large checkpoints |

The table is a decision aid, not a universal ranking. Local NVMe may be the right first landing zone for very frequent checkpoints if a separate process quickly copies completed checkpoints to durable storage. A shared filesystem may be better when many ranks need a common path and the platform can provision enough throughput. NFS remains useful for small teams and modest jobs, but it should be benchmarked under checkpoint-like writes before it becomes the default for large models.

Benchmark storage from inside a pod because the pod path includes the same CSI driver, mount options, node network, security context, and filesystem behavior the workload will experience. A benchmark from the node shell can hide container-level constraints, while a cloud-provider dashboard can miss application-visible latency. The goal is not to produce a perfect storage benchmark; it is to collect a baseline that is close enough to the training job to guide decisions.

```bash
# Create a test pod with your storage class
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: storage-bench
  namespace: default
spec:
  containers:
    - name: bench
      image: ubuntu:22.04
      command: ["sleep", "infinity"]
      volumeMounts:
        - name: test-vol
          mountPath: /data
      resources:
        requests:
          cpu: "4"
          memory: 8Gi
  volumes:
    - name: test-vol
      persistentVolumeClaim:
        claimName: bench-pvc
EOF

# Inside the pod:
kubectl exec -it storage-bench -- bash

apt-get update && apt-get install -y fio

# Sequential read (simulates loading a large dataset)
fio --name=seq-read --rw=read --bs=1M --size=10G \
  --numjobs=4 --direct=1 --directory=/data \
  --runtime=60 --time_based --group_reporting

# Random read (simulates image dataset loading)
fio --name=rand-read --rw=randread --bs=256K --size=10G \
  --numjobs=8 --direct=1 --directory=/data \
  --runtime=60 --time_based --group_reporting \
  --iodepth=32

# Sequential write (simulates checkpoint saves)
fio --name=seq-write --rw=write --bs=1M --size=10G \
  --numjobs=4 --direct=1 --directory=/data \
  --runtime=60 --time_based --group_reporting
```

Read the benchmark as three separate stories. Sequential read approximates shard streaming, random read approximates image or small-record training, and sequential write approximates checkpoint bursts. If random read collapses while sequential read looks fine, the storage system may still be acceptable for tokenized LLM data and unacceptable for small-file image training. If sequential write is weak, a read cache will not fix checkpoint stalls.

## Patterns & Anti-Patterns

Pattern: keep the canonical dataset durable and cache only the active working set near the GPU. This works because object storage or a distributed filesystem can remain the source of truth while local NVMe absorbs repeated hot reads. The scaling constraint is cache capacity and placement; when dataset versions multiply, you need eviction rules, quotas, and monitoring so one team does not fill every node cache with stale experiments.

Pattern: use delayed binding for local storage classes. `WaitForFirstConsumer` aligns the PVC with the pod that will consume it, which allows the scheduler to consider node-local disk and GPU availability in the same placement decision. The scaling constraint is fragmentation: if each node has different free disk capacity, the scheduler may need labels, quotas, or separate storage classes to avoid stranding GPUs behind full local volumes.

Pattern: package small files into larger records when the training framework supports it. This works because fewer larger reads reduce metadata pressure, object-store request overhead, and per-file latency. The scaling constraint is data-preparation discipline; once teams adopt shard formats, they need versioned manifests and validation so a corrupt shard does not silently poison a training run.

Pattern: write checkpoints in shards and promote completed checkpoints atomically. This works because distributed training already partitions state across ranks, and the storage layer can often process parallel writes more efficiently than one large serial write. The scaling constraint is restore complexity; the platform should document how to find a complete checkpoint, validate every shard, and clean up failed partial saves.

Anti-pattern: mounting object storage directly through a generic FUSE layer for every training job. Teams fall into this because the path looks like a filesystem and the setup is quick, but random reads can pay remote request latency for every small file. A better alternative is to use a cache-aware filesystem, pre-stage the working set, or convert the dataset into larger sequential shards.

Anti-pattern: using one shared network filesystem for data, checkpoints, logs, and scratch space without classifying access patterns. It feels simple because every job gets one path, but a checkpoint burst can interfere with data loading and logging can create metadata noise. A better alternative is to separate hot cache, shared read-only datasets, durable checkpoint destinations, and disposable scratch volumes.

Anti-pattern: benchmarking only a warm cache and presenting the result as storage performance. Teams do this because the second run looks good, but production jobs experience cold starts, evictions, and rescheduling. A better alternative is to report cold-cache, warm-cache, and post-eviction results, then tie those results to scheduler behavior and expected reuse.

Anti-pattern: treating asynchronous checkpointing as safe just because training resumes quickly. The background write may still fail, produce a partial checkpoint, or fall behind future checkpoints under load. A better alternative is to use temporary directories, completion markers, atomic promotion, restore tests, and metrics that show checkpoint lag.

## Decision Framework

Start the decision with the workload, not the storage brand. If the workload is dominated by random small-file reads and repeated experiments, prioritize locality, cache hit rate, and dataset packaging. If the workload streams large token or video shards, prioritize aggregate sequential throughput and network capacity. If the workload is checkpoint-heavy, prioritize write bandwidth, atomic completion, and restore reliability.

Choose local NVMe when the active working set fits on node-local disks, the data can be reconstructed from a durable source, and pod placement can be controlled with topology-aware provisioning. Choose a distributed filesystem when multiple nodes need shared POSIX access, the dataset or checkpoint directory must outlive any one node, and the storage team can provision enough metadata and network capacity. Choose object-backed POSIX systems when you want object storage durability with filesystem compatibility and a cache layer that makes repeated reads practical.

Use dataset-aware caching when repeated jobs access the same dataset and scheduler placement is a major factor in performance. Fluid with Alluxio is compelling when the platform wants Kubernetes-native dataset resources and cache-aware placement. JuiceFS is compelling when a team wants a POSIX namespace backed by object storage with transparent local caching. An init-container staging pattern is compelling when the dataset slice is small enough to copy, freshness can be validated, and operational simplicity matters more than dynamic cache orchestration.

For checkpoints, decide where a completed checkpoint becomes durable before deciding where it is first written. A common design is to land the checkpoint quickly on local or cache-backed storage, verify completion, then copy or flush it to a durable shared tier. Another design writes shards directly to a shared filesystem when the filesystem can handle the burst. The wrong design is to write quickly to ephemeral storage and call the job protected without a tested promotion path.

Finally, require evidence before standardizing the storage class. A storage architecture should come with expected I/O profiles, a benchmark command, cache hit-rate metrics, and a restore test for checkpoints. Without those artifacts, the team has a storage preference rather than an operational decision. Kubernetes 1.35+ gives you the storage API surface, but it does not choose the right tier or prove the path is fast enough for your models.

Make the decision review repeatable so storage choices survive staff changes and workload growth. Record the dataset size, file-count shape, expected reuse rate, checkpoint interval, restore objective, and acceptable cold-start time next to the StorageClass or platform template that teams will consume. That record gives future reviewers a way to see whether a new workload still matches the original assumptions or whether it needs a different tier, cache size, or checkpoint destination.

## Did You Know?

1. **ImageNet contains more than fourteen million images and is often described as roughly one hundred fifty gigabytes in common training setups.** The total size is manageable, but the file count creates a small-read problem that punishes object stores, metadata services, and uncached network filesystems. This is why a dataset can be "small" by capacity planning standards and still be difficult for training throughput.

2. **A single large checkpoint can be bigger than the full dataset used for many classic image tasks.** A seventy-billion-parameter model with Adam optimizer state can produce a checkpoint on the order of hundreds of gigabytes, which turns checkpoint storage into a first-class design concern. The write path must be tested, not assumed, because a slow checkpoint cadence can erase the benefit of faster GPUs.

3. **The fastest path is not always the safest path.** Local NVMe can make training reads and checkpoint landing zones extremely fast, but data on a node-local disk is not durable when the node fails. Production designs often pair a fast first hop with a durable promotion step so speed and recovery are both addressed.

4. **Kubernetes `WaitForFirstConsumer` is a storage performance feature as much as a scheduling feature.** It prevents local volumes from binding before the consuming pod is scheduled, which helps the scheduler align GPU availability and local-disk availability. Without that alignment, a technically valid PVC can still create an impossible training placement.

## Common Mistakes

| Mistake | Why It Happens | How to Fix It |
|---------|----------------|---------------|
| Using S3 FUSE mounts for training | FUSE adds 2-10x latency overhead per I/O operation, and object storage is request-oriented rather than small-read oriented | Use JuiceFS or Alluxio with local NVMe cache, or download the working set to local disk first |
| Network storage for ImageNet-style training | Millions of small random reads overload metadata paths and expose network latency | Cache the dataset on local NVMe, or use WebDataset, TFRecord, or another sequential shard format |
| Synchronous checkpoints on slow storage | GPUs idle for minutes during each checkpoint save while the training loop blocks | Use asynchronous checkpointing, sharded distributed checkpoints, or a faster first-hop checkpoint target |
| No `noatime` mount option | Every file read can trigger unnecessary metadata updates on the filesystem | Mount read-heavy training volumes with `noatime,nodiratime` when application semantics allow it |
| RWO volumes for multi-node training | ReadWriteOnce volumes cannot be mounted by pods on multiple nodes for shared training data | Use RWX storage such as CephFS, NFS, or JuiceFS, or provide a local cache per node |
| Ignoring storage class `volumeBindingMode` | PVCs can bind to local storage on the wrong node before the scheduler sees the pod | Use `WaitForFirstConsumer` for local storage and test pod placement with real GPU constraints |
| Not pre-warming cache before training | The first epoch runs at cold-cache speed, which skews benchmarks and wastes GPU time | Use Fluid's `DataLoad` CRD, an init container, or a scheduled warmup job before critical runs |
| Using ext4 for large-file checkpoint workloads by default | The default filesystem choice may not match large sequential writes or the team's operational tuning | Benchmark XFS and ext4 under checkpoint-like writes, then standardize the filesystem and mount options |

## Quiz

<details>
<summary>Question 1: Your ML team trains a ResNet model directly against an S3 bucket containing millions of individual JPEG files through a generic FUSE mount. GPUs stay under target utilization even though the dataset is not large. What should you change first, and why?</summary>

The first change should address the small-random-read pattern rather than the total dataset size. Object storage has meaningful per-request latency, and a FUSE layer adds more overhead before each tiny file reaches the data loader. A local cache, a cache-aware filesystem such as JuiceFS or Alluxio, or a shard format such as WebDataset reduces the number of remote requests and makes reads more sequential. Increasing GPU count would likely make the problem worse because more workers would issue more small reads against the same slow path.
</details>

<details>
<summary>Question 2: A platform engineer creates a local NVMe StorageClass but leaves `volumeBindingMode` at the default. Some GPU jobs remain pending even though nodes have free GPUs and free local disk. What is the likely storage scheduling mistake?</summary>

The likely mistake is binding the PVC before Kubernetes knows which pod will consume it. For local storage, early binding can attach the claim to a volume on a node that does not match the eventual GPU placement, leaving the scheduler with incompatible requirements. `WaitForFirstConsumer` delays binding until pod scheduling, which lets Kubernetes consider local disk topology and GPU availability together. The fix is to update the StorageClass and recreate affected PVCs because existing claims may already be bound.
</details>

<details>
<summary>Question 3: A team reports that a JuiceFS-backed dataset is fast on the second run but slow whenever jobs move to newly added GPU nodes. What metric and operational behavior should you investigate?</summary>

Investigate cache hit rate by node and pod placement relative to cached data. A fast second run proves that the cache can help on a warm node, but it does not prove that the scheduler consistently places future jobs near the warm cache. You should check whether autoscaling or random placement is sending jobs to nodes with cold caches, then consider Fluid-style data-aware scheduling, prewarming, or node-affinity rules. Also verify that cache size and eviction policy are not discarding the dataset between runs.
</details>

<details>
<summary>Question 4: A seventy-billion-parameter training job pauses for several minutes every checkpoint because one rank writes a monolithic file to NFS. What design changes reduce idle GPU time without sacrificing recoverability?</summary>

Use sharded distributed checkpoints so multiple ranks write their own state in parallel, and consider asynchronous checkpointing so training does not block on the full storage write. To preserve recoverability, write to temporary paths, validate all shards, and promote the checkpoint only after completion markers confirm that every shard is present. The storage target should be benchmarked for aggregate sequential writes because parallel checkpointing can expose metadata and network limits. A fast local landing zone is acceptable only if completed checkpoints are copied or flushed to durable storage before older restore points are deleted.
</details>

<details>
<summary>Question 5: Two teams ask for a shared dataset platform. Team A repeatedly trains on immutable dataset versions, while Team B updates a shared dataset daily and requires POSIX semantics across many pods. How would you compare JuiceFS caching and CephFS for these teams?</summary>

Team A is a strong fit for object-backed caching because immutable versions make cache freshness easier to reason about and repeated reads can hit local NVMe after the first run. JuiceFS can expose a POSIX-like path while keeping object storage as the durable backend. Team B may be a better fit for a shared distributed filesystem such as CephFS if daily updates and multi-pod POSIX semantics are central requirements. The final decision should still be benchmarked under each team's read sizes, concurrency, and update pattern.
</details>

<details>
<summary>Question 6: A benchmark shows excellent sequential read throughput but poor random-read throughput on the same storage class. Which AI workloads can still use this storage safely, and which need another design?</summary>

Large-shard workloads such as tokenized LLM pretraining, video reads, or packed record formats may still perform well because they mostly issue sequential reads. Image datasets with millions of small files are risky because random reads and metadata operations dominate their data path. The better design for small-file workloads is to introduce local caching, use a dataset-aware cache, or repackage files into larger shards. The benchmark result should be documented with workload guidance so teams do not treat one throughput number as universal.
</details>

## Hands-On Exercise: JuiceFS Cache Over S3 with Latency Measurement

In this exercise you will deploy a small S3-compatible object store, place a test dataset in it, expose that dataset through JuiceFS, and measure the difference between cold-cache and warm-cache reads. The exercise uses MinIO and Redis so it can run in a test cluster without cloud credentials. The goal is not to build a production JuiceFS deployment; the goal is to see the shape of the performance difference and connect it to the cache architecture discussed in the module.

Use a Kubernetes 1.35+ test cluster with permission to create namespaces, Deployments, Services, Secrets, StorageClasses, PVCs, and Pods. EmptyDir-backed MinIO storage is acceptable for the exercise because the dataset is disposable. If your cluster already has a locked-down default namespace or restricted Pod Security settings, create a dedicated lab cluster or adjust the manifests to match your local policy before running the commands.

### Step 1: Deploy MinIO

Create a local S3-compatible endpoint that will act as the slow durable tier for the lab. In production, this layer would usually be cloud object storage, an enterprise object store, or a managed MinIO deployment with real credentials and durable disks. For the exercise, the object store is intentionally small and disposable.

<details>
<summary>Solution</summary>

```bash
# Install MinIO for local S3-compatible storage
kubectl create namespace storage

cat <<'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: storage
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: minio/minio:RELEASE.2024-10-13T13-34-11Z
          args: ["server", "/data", "--console-address", ":9001"]
          env:
            - name: MINIO_ROOT_USER
              value: minioadmin
            - name: MINIO_ROOT_PASSWORD
              value: minioadmin123
          ports:
            - containerPort: 9000
            - containerPort: 9001
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          emptyDir:
            sizeLimit: 20Gi
---
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: storage
spec:
  ports:
    - port: 9000
      targetPort: 9000
      name: api
    - port: 9001
      targetPort: 9001
      name: console
  selector:
    app: minio
EOF

kubectl -n storage wait --for=condition=Ready pod -l app=minio --timeout=120s
```

</details>

### Step 2: Create a Test Dataset

Now create a bucket and upload a small dataset made of many equal-sized files. This shape is useful because it gives the cache enough objects to show a visible warm-read effect without requiring a large cluster. In a real AI platform, the equivalent step would be publishing a versioned training dataset and recording its manifest.

<details>
<summary>Solution</summary>

```bash
# Create a bucket and upload test data
kubectl -n storage run mc --rm -it --restart=Never \
  --image=minio/mc:RELEASE.2024-10-08T09-37-26Z -- bash -c '
  mc alias set local http://minio:9000 minioadmin minioadmin123
  mc mb local/ai-datasets

  # Create a 1GB test dataset (256 files of 4MB each)
  for i in $(seq 1 256); do
    dd if=/dev/urandom of=/tmp/data_${i}.bin bs=4M count=1 2>/dev/null
    mc cp /tmp/data_${i}.bin local/ai-datasets/training/
    rm /tmp/data_${i}.bin
  done

  echo "Dataset created:"
  mc ls local/ai-datasets/training/ | wc -l
  mc du local/ai-datasets/
'
```

</details>

### Step 3: Deploy Redis for Metadata

JuiceFS separates metadata from object data, so the lab needs a metadata engine. Redis is convenient for a short exercise because it starts quickly and has a simple service endpoint. A production deployment should make a deliberate metadata-engine choice, then back it up and monitor it as a critical dependency.

<details>
<summary>Solution</summary>

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: storage
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: storage
spec:
  ports:
    - port: 6379
  selector:
    app: redis
EOF
```

</details>

### Step 4: Install the JuiceFS CSI Driver

The CSI driver is what makes the object-backed filesystem consumable through Kubernetes PVCs. Notice that the lab Secret contains example credentials for the disposable MinIO deployment, not production secrets. In a real environment, use your organization's secret-management pattern and restrict access to the bucket that contains the relevant dataset.

<details>
<summary>Solution</summary>

```bash
helm repo add juicefs https://juicedata.github.io/charts/
helm repo update

# Create the JuiceFS secret
cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: juicefs-secret
  namespace: storage
type: Opaque
stringData:
  name: ai-data
  metaurl: redis://redis.storage.svc:6379/1
  storage: s3
  bucket: http://minio.storage.svc:9000/ai-datasets
  access-key: minioadmin
  secret-key: minioadmin123
EOF

# Install the CSI driver
helm install juicefs-csi juicefs/juicefs-csi-driver \
  --namespace kube-system \
  --version v0.24.8
```

</details>

### Step 5: Create the StorageClass and PVC

This StorageClass exposes JuiceFS to pods and sets a modest cache size so the lab can run on small clusters. The PVC uses ReadWriteMany because the filesystem can be mounted by more than one pod, which is a common requirement for shared training data. The cache settings are intentionally small; production settings should come from observed working-set size and node disk capacity.

<details>
<summary>Solution</summary>

```bash
cat <<'EOF' | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: juicefs-cache
provisioner: csi.juicefs.com
parameters:
  csi.storage.k8s.io/provisioner-secret-name: juicefs-secret
  csi.storage.k8s.io/provisioner-secret-namespace: storage
  csi.storage.k8s.io/node-publish-secret-name: juicefs-secret
  csi.storage.k8s.io/node-publish-secret-namespace: storage
  juicefs/mount-options: "cache-size=10240,buffer-size=512"
reclaimPolicy: Delete
volumeBindingMode: Immediate
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: juicefs-data
  namespace: storage
spec:
  storageClassName: juicefs-cache
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
EOF
```

</details>

### Step 6: Measure Cold and Warm Reads

The benchmark pod reads every test file once, then reads the same files again. The first pass should fetch data from the object backend through JuiceFS, while the second pass should benefit from the local cache. Do not treat the exact seconds as portable across clusters; focus on the relative behavior and the reason the second read changes.

<details>
<summary>Solution</summary>

```bash
cat <<'BENCHEOF' | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cache-benchmark
  namespace: storage
spec:
  containers:
    - name: bench
      image: ubuntu:22.04
      command: ["bash", "-c"]
      args:
        - |
          apt-get update -qq && apt-get install -y -qq time bc 2>/dev/null

          echo "=== COLD CACHE READ (first access, data fetched from S3) ==="
          sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

          cold_start=$(date +%s%N)
          total_bytes=0
          for f in /data/training/data_*.bin; do
            cat "$f" > /dev/null 2>&1
            total_bytes=$((total_bytes + $(stat -c%s "$f" 2>/dev/null || echo 0)))
          done
          cold_end=$(date +%s%N)

          cold_ms=$(( (cold_end - cold_start) / 1000000 ))
          cold_mbps=$(echo "scale=2; $total_bytes / 1048576 / ($cold_ms / 1000)" | bc 2>/dev/null || echo "N/A")
          echo "Cold read: ${cold_ms}ms for $(echo "$total_bytes / 1048576" | bc)MB = ${cold_mbps} MB/s"
          echo ""

          echo "=== WARM CACHE READ (second access, data from local cache) ==="
          warm_start=$(date +%s%N)
          for f in /data/training/data_*.bin; do
            cat "$f" > /dev/null 2>&1
          done
          warm_end=$(date +%s%N)

          warm_ms=$(( (warm_end - warm_start) / 1000000 ))
          warm_mbps=$(echo "scale=2; $total_bytes / 1048576 / ($warm_ms / 1000)" | bc 2>/dev/null || echo "N/A")
          echo "Warm read: ${warm_ms}ms for $(echo "$total_bytes / 1048576" | bc)MB = ${warm_mbps} MB/s"
          echo ""

          speedup=$(echo "scale=1; $cold_ms / $warm_ms" | bc 2>/dev/null || echo "N/A")
          echo "=== RESULT: Warm cache is ${speedup}x faster than cold ==="

          sleep 3600
      volumeMounts:
        - name: data
          mountPath: /data
      resources:
        requests:
          cpu: "2"
          memory: 4Gi
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: juicefs-data
  restartPolicy: Never
BENCHEOF

# Wait and check results
kubectl -n storage wait --for=condition=Ready pod/cache-benchmark --timeout=300s
sleep 60
kubectl -n storage logs cache-benchmark
```

</details>

### Step 7: Cleanup

Cleanup removes the disposable object store, Redis metadata engine, benchmark pod, and lab PVCs. If you want to inspect the namespace after the benchmark, run the cleanup only after you have captured logs and compared cold and warm read results. Leaving the namespace around is fine for a short investigation, but it should not become hidden state in a shared cluster.

<details>
<summary>Solution</summary>

```bash
kubectl delete namespace storage
```

</details>

### Success Criteria

You have completed this exercise when:

- [ ] MinIO is running and contains a 1GB test dataset with 256 files.
- [ ] Redis metadata engine is running.
- [ ] JuiceFS CSI driver is installed and the StorageClass is created.
- [ ] PVC is bound and mountable.
- [ ] Cold cache read time is measured.
- [ ] Warm cache read time is measured.
- [ ] Warm cache read is at least three times faster than cold cache read.
- [ ] You can explain why the speedup occurs: local cache reads avoid repeated object-store network round trips.

## Sources

- [Kubernetes StorageClasses](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [Kubernetes Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [Kubernetes Volumes](https://kubernetes.io/docs/concepts/storage/volumes/)
- [Container Storage Interface documentation](https://kubernetes-csi.github.io/docs/)
- [TopoLVM documentation](https://topolvm.github.io/topolvm)
- [TopoLVM GitHub repository](https://github.com/topolvm/topolvm)
- [OpenEBS LVM LocalPV (project repo + install)](https://github.com/openebs/lvm-localpv)
- [Rook CephFS filesystem storage](https://rook.io/docs/rook/latest/Storage-Configuration/Shared-Filesystem-CephFS/filesystem-storage/)
- [JuiceFS CSI Driver introduction](https://juicefs.com/docs/csi/introduction/)
- [JuiceFS Helm charts](https://juicedata.github.io/charts/)
- [Fluid — CNCF dataset orchestration & caching for AI](https://fluid-cloudnative.github.io/)
- [Fluid CNCF project page](https://www.cncf.io/projects/fluid/)
- [Fluid GitHub repository](https://github.com/fluid-cloudnative/fluid)
- [The Llama 3 Herd of Models (arXiv:2407.21783)](https://arxiv.org/abs/2407.21783)
- [Alluxio on Kubernetes (Helm deployment)](https://documentation.alluxio.io/os-en/kubernetes/running-alluxio-on-kubernetes)
- [Alluxio Kubernetes integration (Helm chart in repo)](https://github.com/Alluxio/alluxio)
- [PyTorch distributed checkpoint API](https://pytorch.org/docs/stable/distributed.checkpoint.html)
- [MinIO Kubernetes documentation](https://min.io/docs/minio/kubernetes/upstream/index.html)

## Key Takeaways

- AI workloads are often bottlenecked by data-pipeline throughput before they are bottlenecked by GPU compute.
- Storage choices must follow the workload shape: random small-file reads, sequential shard reads, and checkpoint writes need different paths.
- Topology-aware storage placement matters as much as topology-aware GPU placement when local NVMe or warm caches are involved.
- Cache designs need freshness rules, hit-rate metrics, and scheduler behavior, not just fast second-run benchmarks.
- Checkpoint storage is a recoverability system, so speed only counts when incomplete writes are detectable and completed checkpoints are durable.

## Next Module

Continue to [Module 1.5: Serving LLMs at Scale](../module-1.5-llm-serving/) to learn how inference platforms use vLLM, continuous batching, autoscaling, and model-serving storage patterns after training artifacts are ready to serve.
