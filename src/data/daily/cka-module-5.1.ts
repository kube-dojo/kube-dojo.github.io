/**
 * Daily Dojo — Slice 1 pilot units derived from CKA Module 5.1 (Troubleshooting Methodology).
 * Single source of truth for the feature name constant and the ten version-neutral units.
 */

export const DAILY_FEATURE_NAME = 'Daily Dojo';
export const DAILY_ROUTE = '/daily/';
export const DAILY_MAX_UNIT_WORDS = 450;

export const PARENT_MODULE_PATH = '/k8s/cka/part5-troubleshooting/module-5.1-methodology/';
export const PARENT_MODULE_TITLE = 'Module 5.1: Troubleshooting Methodology';
export const PARENT_LAB_ID = 'cka-5.1-methodology';
export const PARENT_LAB_URL = 'https://killercoda.com/kubedojo/scenario/cka-5.1-methodology';

export interface DailySource {
  title: string;
  url: string;
}

export interface DailyCheckOption {
  id: string;
  label: string;
  correct: boolean;
  explanation: string;
}

export interface DailyCheck {
  id: string;
  prompt: string;
  options: readonly DailyCheckOption[];
}

export interface DailyWorkedExample {
  title: string;
  language: 'bash' | 'yaml' | 'text';
  code: string;
  takeaway: string;
}

export interface DailyUnit {
  id: string;
  number: number;
  title: string;
  estimatedMinutes: number;
  reviewMinutes: number;
  idea: string;
  workedExample: DailyWorkedExample;
  checks: readonly DailyCheck[];
  parentAnchor: string;
  parentSectionTitle: string;
  labId: string;
  labUrl: string;
  sources: readonly DailySource[];
}

export interface DailyPack {
  id: string;
  title: string;
  subtitle: string;
  parentModulePath: string;
  parentModuleTitle: string;
  labId: string;
  labUrl: string;
  units: readonly DailyUnit[];
}

export const CKA_MODULE_5_1_UNITS: readonly DailyUnit[] = [
  {
    id: 'observe-before-mutating',
    number: 1,
    title: 'Observe Before You Mutate',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Your first minute on a broken cluster should be strictly read-only. Deleting or restarting a failing Pod erases previous container logs, resets restart counters, and obscures timing clues while the controller simply recreates the same broken Pod spec. Capture blast radius and object state first, then decide what to change.',
    workedExample: {
      title: 'Read-only triage pass',
      language: 'bash',
      code: [
        'kubectl get nodes -o wide',
        'kubectl get pods -A -o wide',
        "kubectl get events -n prod --sort-by='.lastTimestamp' | tail -20",
      ].join('\n'),
      takeaway:
        'Wide output shows whether failures cluster on one node or span one Deployment before any object is altered.',
    },
    checks: [
      {
        id: 'observe-q1',
        prompt:
          'A Deployment pod enters CrashLoopBackOff during a release. Why should you avoid running kubectl delete pod immediately?',
        options: [
          {
            id: 'a',
            label: 'It deletes the Deployment along with the Pod.',
            correct: false,
            explanation:
              'Deleting a Pod does not remove its owning Deployment; the ReplicaSet immediately creates a replacement Pod.',
          },
          {
            id: 'b',
            label: 'It destroys previous container logs and restart history without fixing the underlying spec.',
            correct: true,
            explanation:
              'Correct. A controller recreates the same broken template while wiping the old Pod instance and its --previous log evidence.',
          },
          {
            id: 'c',
            label: 'Kubernetes forbids deleting Pods that are in a backoff state.',
            correct: false,
            explanation:
              'The API server accepts Pod deletion in any phase; the problem is losing diagnostic evidence, not API rejection.',
          },
        ],
      },
    ],
    parentAnchor: '11-observe-the-symptom-without-mutating-the-cluster',
    parentSectionTitle: '1.1 Observe the Symptom Without Mutating the Cluster',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Debug Running Pods',
        url: 'https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/',
      },
    ],
  },
  {
    id: 'isolate-by-layer',
    number: 2,
    title: 'Isolate the Failing Layer',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Kubernetes stacks control plane, node, Pod, container, Service, and application layers. A symptom at one layer rarely means that layer owns the fault. Narrow the boundary first: check whether the failure affects every namespace, only one node, or only one workload so you do not inspect application logs for a scheduling problem.',
    workedExample: {
      title: 'Separating node failure from workload failure',
      language: 'bash',
      code: [
        'kubectl get pods -A -o wide --field-selector spec.nodeName=worker-2',
        'kubectl describe node worker-2',
      ].join('\n'),
      takeaway:
        'When unrelated workloads fail only on worker-2, investigate node conditions and kubelet instead of rewriting app manifests.',
    },
    checks: [
      {
        id: 'isolate-q1',
        prompt:
          'Pods from three different teams stay stuck in Pending across every namespace. Which layer should you inspect first?',
        options: [
          {
            id: 'a',
            label: 'Application container logs inside each Pending Pod.',
            correct: false,
            explanation:
              'A Pending Pod has not started its application container yet, so container logs do not exist.',
          },
          {
            id: 'b',
            label: 'CoreDNS pods in kube-system.',
            correct: false,
            explanation:
              'DNS resolution happens after a container starts; it does not prevent the scheduler from placing Pods.',
          },
          {
            id: 'c',
            label: 'Pod scheduling Events, node capacity, and kube-scheduler health.',
            correct: true,
            explanation:
              'Correct. Cluster-wide Pending pods point to scheduling, node readiness, taints, quotas, or kube-scheduler.',
          },
        ],
      },
    ],
    parentAnchor: '13-isolate-by-layer-not-by-guess',
    parentSectionTitle: '1.3 Isolate by Layer, Not by Guess',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Kubernetes Components',
        url: 'https://kubernetes.io/docs/concepts/overview/components/',
      },
    ],
  },
  {
    id: 'follow-pod-lifecycle',
    number: 3,
    title: 'Follow the Pod Lifecycle Order',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'A Pod progresses through distinct stages: API admission, scheduling to a node, preparing volumes and pulling images, starting container processes, and passing readiness probes. Reading evidence in that same order prevents wasted guesses—never debug a process crash before confirming the Pod scheduled and mounted its volumes.',
    workedExample: {
      title: 'Checking Pod conditions in lifecycle order',
      language: 'bash',
      code: [
        "kubectl get pod billing-7d -n prod -o jsonpath='{.status.conditions[*].type}{\"\\n\"}{.status.conditions[*].status}{\"\\n\"}'",
        '# PodScheduled  Initialized  ContainersReady  Ready',
        '# True          True         False            False',
      ].join('\n'),
      takeaway:
        'PodScheduled=True rules out the scheduler and narrows the investigation to kubelet setup, container startup, or probes.',
    },
    checks: [
      {
        id: 'lifecycle-q1',
        prompt:
          'A Pod shows PodScheduled=True and status ContainerCreating for three minutes. Which stage is failing?',
        options: [
          {
            id: 'a',
            label: 'kube-scheduler cannot find a node with enough CPU.',
            correct: false,
            explanation:
              'PodScheduled=True proves the scheduler already assigned the Pod to a node.',
          },
          {
            id: 'b',
            label: 'kubelet setup on the assigned node (volume mount, Secret/ConfigMap, image pull, or CNI).',
            correct: true,
            explanation:
              'Correct. ContainerCreating happens after scheduling while kubelet prepares volumes, networking, and container images.',
          },
          {
            id: 'c',
            label: 'The Service selector does not match the Pod labels.',
            correct: false,
            explanation:
              'Service selectors affect traffic routing after readiness, never whether kubelet can create a container.',
          },
        ],
      },
    ],
    parentAnchor: '14-inspect-evidence-in-an-order-that-matches-the-lifecycle',
    parentSectionTitle: '1.4 Inspect Evidence in an Order That Matches the Lifecycle',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Pod Lifecycle',
        url: 'https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/',
      },
    ],
  },
  {
    id: 'describe-before-logs',
    number: 4,
    title: 'Read describe Before logs',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'kubectl describe pod gathers Kubernetes-level facts in one view: assigned node, conditions, image name, container state, last termination reason, probe settings, and recent Events. Container logs only show stdout and stderr after a process starts, so describe is almost always the stronger first deep inspection.',
    workedExample: {
      title: 'Spotting a missing ConfigMap in Events',
      language: 'bash',
      code: [
        'kubectl describe pod api-6c9f -n prod',
        '# State:   Waiting',
        '# Reason:  CreateContainerConfigError',
        '# Events:  Warning  Failed  kubelet  configmap "app-env" not found',
      ].join('\n'),
      takeaway:
        'CreateContainerConfigError happens before the process launches; describe names the missing ConfigMap immediately.',
    },
    checks: [
      {
        id: 'describe-q1',
        prompt:
          'A newly deployed Pod reports CreateContainerConfigError. Which command gives the fastest root cause?',
        options: [
          {
            id: 'a',
            label: 'kubectl logs <pod> --previous',
            correct: false,
            explanation:
              'No container instance started yet, so there is no previous process log to read.',
          },
          {
            id: 'b',
            label: 'kubectl describe pod <pod> -n <namespace>',
            correct: true,
            explanation:
              'Correct. Events and container state in describe identify the missing ConfigMap, Secret, or key blocking startup.',
          },
          {
            id: 'c',
            label: 'kubectl top pod <pod> -n <namespace>',
            correct: false,
            explanation:
              'Metrics show live CPU and memory usage for running containers, not configuration lookup errors.',
          },
        ],
      },
    ],
    parentAnchor: '32-describe-before-logs',
    parentSectionTitle: '3.2 Describe Before Logs',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Debug Running Pods',
        url: 'https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/',
      },
    ],
  },
  {
    id: 'previous-and-multicontainer-logs',
    number: 5,
    title: 'Use --previous and -c for Logs',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Once describe confirms a container started and exited, inspect its logs carefully. When restartCount is greater than zero, the live container may have just booted, hiding the crash line—add --previous to read the terminated instance. In multi-container Pods, bare kubectl logs fails unless a default-container annotation is set, so list container names first and pass -c to target the failing container.',
    workedExample: {
      title: 'Targeting the crashed container in a multi-container Pod',
      language: 'bash',
      code: [
        "kubectl get pod web-abc -n prod -o jsonpath='{.spec.containers[*].name}{\"\\n\"}'",
        '# app log-agent',
        'kubectl logs web-abc -n prod -c app --previous',
      ].join('\n'),
      takeaway:
        'Explicitly naming -c app and --previous fetches the exact error written just before the application container exited.',
    },
    checks: [
      {
        id: 'logs-q1',
        prompt:
          'A Pod has containers app and metrics-sidecar. Running kubectl logs <pod> fails asking for a container name, and describe shows app restarted four times. What should you run next?',
        options: [
          {
            id: 'a',
            label: 'kubectl logs <pod> -c app --previous',
            correct: true,
            explanation:
              'Correct. Selecting -c app targets the failing container and --previous retrieves output from its last terminated run.',
          },
          {
            id: 'b',
            label: 'kubectl rollout restart deployment',
            correct: false,
            explanation:
              'Restarting replaces the Pod and wipes the prior container log buffer before you read the crash cause.',
          },
          {
            id: 'c',
            label: 'kubectl get events --all-namespaces',
            correct: false,
            explanation:
              'Events confirm restarts occurred, but application stack traces live in the terminated container logs.',
          },
        ],
      },
    ],
    parentAnchor: '33-logs-and-previous-logs',
    parentSectionTitle: '3.3 Logs and Previous Logs',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: kubectl logs Reference',
        url: 'https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/',
      },
      {
        title: 'Kubernetes Docs: Logging Architecture',
        url: 'https://kubernetes.io/docs/concepts/cluster-administration/logging/',
      },
    ],
  },
  {
    id: 'exit-codes-and-oom',
    number: 6,
    title: 'Interpret Exit Codes and OOMKilled',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Last State termination details separate application errors from OS signals. Exit code 1 usually indicates an app error; 127 means command not found; 143 means graceful SIGTERM; 137 means SIGKILL, commonly with reason OOMKilled. Do not blindly double memory limits—first check whether a recent release introduced a leak or whether limits were unrealistically low.',
    workedExample: {
      title: 'Extracting termination reason and exit code',
      language: 'bash',
      code: [
        "kubectl get pod worker-9x -n batch -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason} {.status.containerStatuses[0].lastState.terminated.exitCode}{\"\\n\"}'",
        '# OOMKilled 137',
        'kubectl get pod worker-9x -n batch -o jsonpath=\'{.spec.containers[0].resources}{"\\n"}\'',
      ].join('\n'),
      takeaway:
        'Confirm OOMKilled in Last State first, then compare configured requests and limits against recent release changes.',
    },
    checks: [
      {
        id: 'exit-q1',
        prompt:
          'A batch Pod restarts with Last State reason OOMKilled and exit code 137. Which statement is most accurate?',
        options: [
          {
            id: 'a',
            label: 'Run kubectl top pod first because it records the exact peak memory at the instant of termination.',
            correct: false,
            explanation:
              'kubectl top reports current sampled usage for running containers; describe and Last State establish the historical OOM kill.',
          },
          {
            id: 'b',
            label: 'The container was killed with SIGKILL due to memory constraints; inspect requests, limits, and recent workload changes before resizing.',
            correct: true,
            explanation:
              'Correct. Exit 137 with OOMKilled confirms a memory kill, and inspecting limits plus recent changes avoids masking a memory leak.',
          },
          {
            id: 'c',
            label: 'Exit code 137 means the container binary was missing from the image.',
            correct: false,
            explanation:
              'Exit code 127 indicates command not found; 137 is 128 + 9 (SIGKILL).',
          },
        ],
      },
    ],
    parentAnchor: '43-exit-codes-and-termination-reasons',
    parentSectionTitle: '4.3 Exit Codes and Termination Reasons',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Pod Lifecycle',
        url: 'https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/',
      },
    ],
  },
  {
    id: 'running-is-not-ready',
    number: 7,
    title: 'Running Does Not Mean Ready',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Pod phase Running only means the Pod is bound to a node, all containers are created, and at least one container is running, starting, or restarting. It does not guarantee the Pod receives Service traffic. If the readiness probe fails, Kubernetes keeps the container running while marking Ready=False and excluding the Pod IP from ready EndpointSlices.',
    workedExample: {
      title: 'Checking readiness probe failures on a Running Pod',
      language: 'bash',
      code: [
        'kubectl get pods -n prod -l app=web',
        '# NAME      READY   STATUS    RESTARTS   AGE',
        '# web-5f2   0/1     Running   0          4m',
        'kubectl describe pod web-5f2 -n prod | grep -A3 "Readiness\\|Unhealthy"',
      ].join('\n'),
      takeaway:
        '0/1 Running signals a readiness failure—inspect the probe path, port, and app health endpoint rather than assuming the process crashed.',
    },
    checks: [
      {
        id: 'ready-q1',
        prompt:
          'All Pods behind a Service show 0/1 Running with zero restarts, and clients get connection errors. What is Kubernetes doing?',
        options: [
          {
            id: 'a',
            label: 'Routing traffic anyway because the Pod phase is Running.',
            correct: false,
            explanation:
              'Standard Services exclude unready Pods from active routing until readiness probes succeed.',
          },
          {
            id: 'b',
            label: 'Keeping the containers alive while withholding them from ready Service endpoints because readiness fails.',
            correct: true,
            explanation:
              'Correct. A failing readiness probe protects callers by keeping Running Pods out of ready endpoints without restarting them.',
          },
          {
            id: 'c',
            label: 'Terminating the Pods with SIGTERM every periodSeconds.',
            correct: false,
            explanation:
              'Liveness probes trigger container restarts; readiness probes only control endpoint eligibility.',
          },
        ],
      },
    ],
    parentAnchor: '44-running-does-not-mean-ready',
    parentSectionTitle: '4.4 Running Does Not Mean Ready',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Pod Lifecycle',
        url: 'https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/',
      },
      {
        title: 'Kubernetes Docs: Configure Liveness, Readiness and Startup Probes',
        url: 'https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/',
      },
    ],
  },
  {
    id: 'service-endpoints-before-dns',
    number: 8,
    title: 'Check EndpointSlices Before DNS',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Cluster DNS resolves a ClusterIP Service name to its virtual IP even when zero backend Pods match it. When in-cluster requests fail or time out, inspect EndpointSlices first. Empty endpoints point to a selector mismatch, wrong namespace, or unready Pods; populated endpoints shift focus to targetPort, container listening port, or NetworkPolicy.',
    workedExample: {
      title: 'Tracing an empty Service back to a label typo',
      language: 'bash',
      code: [
        'kubectl get endpointslices -n prod -l kubernetes.io/service-name=checkout',
        '# PORTS   ENDPOINTS   AGE -> <unset>',
        'kubectl get svc checkout -n prod -o jsonpath=\'{.spec.selector}{"\\n"}\'',
        'kubectl get pods -n prod --show-labels',
      ].join('\n'),
      takeaway:
        'Comparing spec.selector against --show-labels catches selector typos in seconds without touching CoreDNS.',
    },
    checks: [
      {
        id: 'svc-q1',
        prompt:
          'nslookup checkout.prod.svc.cluster.local returns a ClusterIP, but HTTP requests to checkout:8080 fail and EndpointSlices show no addresses. What should you inspect next?',
        options: [
          {
            id: 'a',
            label: 'CoreDNS ConfigMap and kube-dns logs.',
            correct: false,
            explanation:
              'DNS already resolved the Service ClusterIP; EndpointSlice population is handled by the EndpointSlice controller, not CoreDNS.',
          },
          {
            id: 'b',
            label: 'Service selector labels, Pod labels in the same namespace, and Pod readiness.',
            correct: true,
            explanation:
              'Correct. Empty EndpointSlices mean no ready Pods match the Service selector in that namespace.',
          },
          {
            id: 'c',
            label: 'Node kernel routing tables over SSH.',
            correct: false,
            explanation:
              'Without ready backend endpoints, dataplane routing has no backend Pod IP to forward traffic to.',
          },
        ],
      },
      {
        id: 'svc-q2',
        prompt:
          'If EndpointSlices DO list ready backend Pod IPs, what is the next most useful check?',
        options: [
          {
            id: 'a',
            label: 'Verify Service targetPort matches the port the container actually listens on, and check NetworkPolicy.',
            correct: true,
            explanation:
              'Correct. With ready endpoints present, failures typically stem from port mapping mismatches, app listeners, or NetworkPolicy rules.',
          },
          {
            id: 'b',
            label: 'Recreate the Service with a new name.',
            correct: false,
            explanation:
              'Renaming the Service breaks callers and does not diagnose port or policy mismatches.',
          },
        ],
      },
    ],
    parentAnchor: 'service-path-debugging',
    parentSectionTitle: 'Service Path Debugging',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Debug Services',
        url: 'https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/',
      },
      {
        title: 'Kubernetes Docs: DNS for Services and Pods',
        url: 'https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/',
      },
    ],
  },
  {
    id: 'storage-bind-vs-mount',
    number: 9,
    title: 'Separate PVC Binding from Node Mounting',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Storage failures split into two distinct stages: binding and mounting. A PersistentVolumeClaim stuck in Pending cannot bind to a PersistentVolume because of StorageClass, access mode, capacity, or dynamic provisioning errors. A Bound PVC paired with Pod event FailedMount means the volume exists, but the node cannot attach or mount it.',
    workedExample: {
      title: 'Distinguishing bind failures from mount failures',
      language: 'bash',
      code: [
        'kubectl get pvc -n db',
        '# NAME      STATUS    VOLUME   STORAGECLASS',
        '# pg-data   Pending            fast-ssd',
        'kubectl describe pvc pg-data -n db',
      ].join('\n'),
      takeaway:
        'Check PVC status first: Pending directs you to PVC events and StorageClass; Bound with FailedMount directs you to Pod events and CSI node setup.',
    },
    checks: [
      {
        id: 'storage-q1',
        prompt:
          'A database Pod stays in ContainerCreating with event FailedMount, while kubectl get pvc shows STATUS Bound. Which layer is implicated?',
        options: [
          {
            id: 'a',
            label: 'Dynamic provisioning failed to match a StorageClass.',
            correct: false,
            explanation:
              'STATUS Bound confirms the PVC already bound to a PersistentVolume.',
          },
          {
            id: 'b',
            label: 'Node-level attachment, filesystem mounting, permissions, or the CSI node plugin.',
            correct: true,
            explanation:
              'Correct. Once a PVC is Bound, FailedMount indicates kubelet or the storage plugin on the node failed to attach or mount the volume.',
          },
          {
            id: 'c',
            label: 'kube-scheduler rejected the Pod due to CPU limits.',
            correct: false,
            explanation:
              'FailedMount only occurs after scheduling, when kubelet attempts to set up volumes on the node.',
          },
        ],
      },
    ],
    parentAnchor: 'storage-triage',
    parentSectionTitle: 'Storage Triage',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Persistent Volumes',
        url: 'https://kubernetes.io/docs/concepts/storage/persistent-volumes/',
      },
    ],
  },
  {
    id: 'repair-small-validate-path',
    number: 10,
    title: 'Repair Small, Validate the Real Path',
    estimatedMinutes: 4,
    reviewMinutes: 2,
    idea:
      'Apply the smallest fix that matches your confirmed evidence—one change at a time so cause and effect stay clear. Then validate the user-facing symptom, not just Pod phase. If the incident was "frontend cannot reach backend," confirm rollout convergence, ready EndpointSlices, and an actual in-cluster request through the Service.',
    workedExample: {
      title: 'Targeted patch followed by end-to-end validation',
      language: 'bash',
      code: [
        'kubectl patch svc backend -n prod --type=merge -p \'{"spec":{"selector":{"app":"backend"}}}\'',
        'kubectl rollout status deployment/backend -n prod --timeout=90s',
        'kubectl get endpointslices -n prod -l kubernetes.io/service-name=backend',
        'kubectl exec -n prod deploy/frontend -- wget -qO- http://backend:8080/healthz',
      ].join('\n'),
      takeaway:
        'A green Pod does not prove traffic works; test from a caller through the Service name and port.',
    },
    checks: [
      {
        id: 'validate-q1',
        prompt:
          'After fixing an image typo in a Deployment, the new Pods show 1/1 Running. The ticket asks to restore reachability via the web Service on port 8080. Are you done?',
        options: [
          {
            id: 'a',
            label: 'Yes—1/1 Running proves the Service routes traffic properly.',
            correct: false,
            explanation:
              'A ready Pod can still be missed by a mismatched Service selector, wrong targetPort, or blocking NetworkPolicy.',
          },
          {
            id: 'b',
            label: 'No—verify rollout status, confirm Service EndpointSlices, and send a test request through http://web:8080 from inside the cluster.',
            correct: true,
            explanation:
              'Correct. Validation must prove the actual requested caller path, not only Pod status.',
          },
          {
            id: 'c',
            label: 'Only after deleting the old ReplicaSet manually.',
            correct: false,
            explanation:
              'Deployments retain old ReplicaSets for rollback history; manual deletion does not validate Service reachability.',
          },
        ],
      },
    ],
    parentAnchor: '16-validate-the-workload-path-not-just-the-object-status',
    parentSectionTitle: '1.6 Validate the Workload Path, Not Just the Object Status',
    labId: PARENT_LAB_ID,
    labUrl: PARENT_LAB_URL,
    sources: [
      {
        title: 'Kubernetes Docs: Debug Services',
        url: 'https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/',
      },
      {
        title: 'Kubernetes Docs: Debug Running Pods',
        url: 'https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/',
      },
    ],
  },
];

export const CKA_MODULE_5_1_PACK: DailyPack = {
  id: 'cka-module-5.1',
  title: 'CKA Troubleshooting Methodology',
  subtitle: 'Ten 3–5 minute units from CKA Module 5.1 — observe, isolate, inspect, repair, and validate.',
  parentModulePath: PARENT_MODULE_PATH,
  parentModuleTitle: PARENT_MODULE_TITLE,
  labId: PARENT_LAB_ID,
  labUrl: PARENT_LAB_URL,
  units: CKA_MODULE_5_1_UNITS,
};

/**
 * Count all learner-visible prose/example/check words in a unit.
 * Used by tests to enforce the 450-word cap (AC-03).
 */
export function countUnitWords(unit: DailyUnit): number {
  const parts: string[] = [
    unit.title,
    unit.idea,
    unit.workedExample.title,
    unit.workedExample.code,
    unit.workedExample.takeaway,
  ];
  for (const check of unit.checks) {
    parts.push(check.prompt);
    for (const option of check.options) {
      parts.push(option.label, option.explanation);
    }
  }
  const tokens = parts
    .join(' ')
    .trim()
    .split(/\s+/)
    .filter((token) => token.length > 0);
  return tokens.length;
}
