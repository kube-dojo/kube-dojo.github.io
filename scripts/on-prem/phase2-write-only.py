#!/usr/bin/env python3
"""On-Prem Phase 2 — bulk module drafting WITH per-module fact-checking, NO review loop.

Bypasses the v1 pipeline's review/check/score retry loop. Per module:

  1. WRITE — call the chosen writer model (default: scripts/dispatch.py writer pin)
  2. SAVE — write the module markdown to disk
  3. FACT-CHECK — call the calibrated fact-grounder (gpt-5.3-codex-spark) on
     the just-written module, produce a structured ledger (SUPPORTED /
     CONFLICTING / UNVERIFIED / HALLUCINATED counts) saved alongside the
     module as a sibling .factcheck.json file

The user reviews drafts AND fact-check ledgers when they wake up. The ledger
makes 21 untrusted drafts into 21 drafts WITH explicit hallucination data —
the human reviewer can prioritize modules with high hallucination counts
and trust the rest.

This is the "fast progress" mode for content writing while the architecture
PR (`feat/fact-ledger-architecture`) is being built. Once the architecture
PR ships, this becomes a standard pipeline step instead of a one-off script.

Sequential by design — never parallelizes Gemini calls (per
feedback_sequential_gemini.md memory rule).

Resumable: skips modules whose target file already has >2000 chars AND a
fresh fact-check ledger. Re-runs the fact-check if the markdown is fresh
but the ledger is missing.

Usage:
    .venv/bin/python scripts/on-prem/phase2-write-only.py            # all 21
    .venv/bin/python scripts/on-prem/phase2-write-only.py 1 2 3      # only the first 3 (1-indexed)
    .venv/bin/python scripts/on-prem/phase2-write-only.py --dry-run  # show what would run
    .venv/bin/python scripts/on-prem/phase2-write-only.py --writer gpt-5.4   # override writer
    .venv/bin/python scripts/on-prem/phase2-write-only.py --skip-factcheck   # write only

Environment override (set this if the rigorous writer calibration picked a
non-default model):
    KUBEDOJO_WRITER_MODEL=<model-name>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
VENV_PYTHON = str((REPO_ROOT / ".venv" / "bin" / "python").resolve())

from dispatch import GEMINI_WRITER_MODEL, dispatch_agy  # type: ignore  # noqa: E402

CONTENT_ROOT = REPO_ROOT / "src" / "content" / "docs" / "on-premises"
LOG_FILE = REPO_ROOT / ".pipeline" / "on-prem-logs" / "phase2-write-only.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_WRITER = os.environ.get("KUBEDOJO_WRITER_MODEL") or GEMINI_WRITER_MODEL
FACT_CHECKER = "gpt-5.3-codex-spark"  # calibrated winner from fact-grounding test
MIN_CONTENT_CHARS = 2000  # below this is treated as a stub
FACT_CHECK_TIMEOUT = 900

# 21 modules — index aligned across the four arrays. Mirrors phase2-new-modules.sh.
MODULES: list[dict] = [
    {"sec": "planning", "num": "1.5", "stem": "onprem-finops-chargeback",
     "title": "On-Prem FinOps & Chargeback",
     "topic": "On-Prem FinOps and chargeback models. Kubecost and OpenCost on bare metal, showback/chargeback for internal platform teams, capacity rightsizing lifecycle, depreciation modeling, budget alerting, comparing on-prem TCO to cloud FinOps disciplines."},
    {"sec": "networking", "num": "3.5", "stem": "cross-cluster-networking",
     "title": "Cross-Cluster Networking",
     "topic": "Cross-cluster networking for bare metal K8s. Submariner, Cilium Cluster Mesh, Liqo. East-west traffic across geographically distributed clusters without cloud load balancers. Service discovery, encrypted tunnels, MTU/MSS considerations, dual-stack support."},
    {"sec": "networking", "num": "3.6", "stem": "service-mesh-bare-metal",
     "title": "Service Mesh on Bare Metal",
     "topic": "Service mesh on bare metal without cloud load balancers. Istio, Cilium service mesh, Linkerd, Consul. mTLS, traffic shaping, observability integration. Performance considerations vs cloud mesh deployments. Data plane choices: envoy vs eBPF. Kernel tuning for high-throughput mesh traffic."},
    {"sec": "storage", "num": "4.4", "stem": "object-storage-bare-metal",
     "title": "Object Storage on Bare Metal",
     "topic": "Object storage on bare metal with MinIO. S3-compatible API, distributed deployment modes, tiering policies, erasure coding, encryption at rest, Prometheus metrics. Replication topologies, bucket quotas, multi-tenancy via STS. Lifecycle policies, versioning, legal hold."},
    {"sec": "storage", "num": "4.5", "stem": "database-operators",
     "title": "Database Operators",
     "topic": "Database operators on Kubernetes for bare metal. CloudNativePG for PostgreSQL with streaming replication, PITR, pgBouncer. Vitess for MySQL sharding. Self-hosted Redis, Memcached, and Valkey operators. Backup strategies, failover, connection pooling, monitoring."},
    {"sec": "multi-cluster", "num": "5.4", "stem": "fleet-management",
     "title": "Fleet Management",
     "topic": "Fleet management for multi-cluster bare metal. Rancher Fleet, Open Cluster Management, ArgoCD ApplicationSets at scale. Cluster registration, placement rules, GitOps rollout strategies, policy distribution, centralized audit logs. Comparing with Karmada and ClusterAPI-based approaches."},
    {"sec": "multi-cluster", "num": "5.5", "stem": "active-active-multi-site",
     "title": "Active-Active Multi-Site",
     "topic": "Active-active multi-site architectures on bare metal. Global load balancing without cloud services, cross-DC data replication, conflict resolution patterns. Eventual consistency vs strong consistency tradeoffs. Split-brain prevention. Database replication (Galera, CockroachDB, YugabyteDB on bare metal)."},
    {"sec": "security", "num": "6.5", "stem": "workload-identity-spiffe",
     "title": "Workload Identity with SPIFFE/SPIRE",
     "topic": "Workload identity via SPIFFE/SPIRE. Zero-trust workload identity without cloud IAM. X.509 SVIDs, JWT SVIDs, federation across trust domains, workload attestation (k8s, selectors, plugins). Integration with service mesh and secrets managers. Rotation, key management, audit."},
    {"sec": "security", "num": "6.6", "stem": "secrets-management-vault",
     "title": "Secrets Management on Bare Metal",
     "topic": "Secrets management on bare metal K8s. HashiCorp Vault on bare metal (Raft storage, HA), External Secrets Operator, sealed-secrets, Kubernetes Secrets encryption at rest. KMS integration without cloud services. Secret rotation, dynamic secrets for databases, PKI engine usage."},
    {"sec": "security", "num": "6.7", "stem": "policy-as-code",
     "title": "Policy as Code & Governance",
     "topic": "Policy as Code and governance on K8s. OPA Gatekeeper and Kyverno for admission control. Runtime policy enforcement with Falco and Tetragon. Policy libraries, violation dashboards, exemption workflows. Comparing OPA vs Kyverno: Rego vs native YAML. Policy CI/CD and testing."},
    {"sec": "security", "num": "6.8", "stem": "zero-trust-architecture",
     "title": "Zero Trust Architecture",
     "topic": "Zero Trust Architecture on bare metal K8s. mTLS everywhere via service mesh, network segmentation with NetworkPolicies and Cilium Network Policies, microsegmentation strategies. Identity-based access with SPIFFE, BeyondCorp-style patterns, continuous verification, assume breach posture."},
    {"sec": "operations", "num": "7.6", "stem": "self-hosted-cicd",
     "title": "Self-Hosted CI/CD",
     "topic": "Self-hosted CI/CD on K8s. Tekton Pipelines, Gitea with Actions runners, Jenkins on K8s (JCasC, Kubernetes plugin), Woodpecker CI, Drone. Build caching, artifact storage, secret injection, multi-arch builds. Comparing self-hosted options on capability, resource footprint, and operational burden."},
    {"sec": "operations", "num": "7.7", "stem": "self-hosted-registry",
     "title": "Self-Hosted Container Registry",
     "topic": "Self-hosted container registries on bare metal. Harbor (replication, scanning, signing), Quay, Zot, GitLab registry. Distribution architecture, pull-through caches, proxy cache for upstream, vulnerability scanning pipelines (Trivy, Clair). Signing with cosign, policy enforcement, storage backends."},
    {"sec": "operations", "num": "7.8", "stem": "observability-at-scale",
     "title": "Observability at Scale",
     "topic": "Observability at scale on bare metal. Prometheus federation and sharding, Thanos, Cortex, Mimir for long-term storage. OpenTelemetry Collector pipelines. Grafana LGTM stack (Loki, Grafana, Tempo, Mimir). Cardinality management, exemplars, profiling with Pyroscope, alerting fatigue mitigation."},
    {"sec": "operations", "num": "7.9", "stem": "serverless-bare-metal",
     "title": "Serverless on Bare Metal",
     "topic": "Serverless on bare metal K8s. Knative Serving and Eventing for FaaS patterns, KEDA event-driven autoscaling (scale-to-zero), OpenFaaS, Fission. Cold start optimization, autoscaling triggers, comparing serverless runtimes. When to use serverless vs long-running workloads on bare metal."},
    {"sec": "ai-ml-infrastructure", "num": "9.1", "stem": "gpu-nodes-accelerated",
     "title": "GPU Nodes & Accelerated Computing",
     "topic": "GPU nodes and accelerated computing on K8s. NVIDIA GPU Operator, device plugins, MIG (Multi-Instance GPU), GPU time slicing, node labeling, scheduling strategies. Monitoring GPU utilization (DCGM), driver management, CUDA version compatibility. AMD ROCm and Intel Gaudi alternatives."},
    {"sec": "ai-ml-infrastructure", "num": "9.2", "stem": "private-ai-training",
     "title": "Private AI Training Infrastructure",
     "topic": "Private AI training infrastructure. Distributed training on bare metal with PyTorch DDP, FSDP, JAX on K8s. NCCL over InfiniBand/RoCE, RDMA tuning. Job schedulers (Volcano, Kueue, Slurm bridges). Checkpoint storage, fault-tolerant training, topology-aware scheduling for multi-GPU nodes."},
    {"sec": "ai-ml-infrastructure", "num": "9.3", "stem": "private-llm-serving",
     "title": "Private LLM Serving",
     "topic": "Private LLM serving on bare metal. vLLM, Text Generation Inference (TGI), Ollama at scale. Model caching, quantization (GPTQ, AWQ), autoscaling inference with KServe/Kubeflow. Token throughput tuning, batch scheduling, continuous batching, multi-model serving, GPU memory optimization."},
    {"sec": "ai-ml-infrastructure", "num": "9.4", "stem": "private-mlops-platform",
     "title": "Private MLOps Platform",
     "topic": "Private MLOps platform on bare metal. Kubeflow, MLflow, model registry, experiment tracking, feature stores (Feast on bare metal). Data versioning (DVC, LakeFS), model deployment pipelines, A/B testing harness, lineage tracking. Self-hosted alternatives to SageMaker and Vertex AI."},
    {"sec": "ai-ml-infrastructure", "num": "9.5", "stem": "private-aiops",
     "title": "Private AIOps",
     "topic": "Private AIOps on bare metal. Anomaly detection for cluster metrics, predictive scaling with ML, self-healing workflows with AI-augmented incident response. Robusta for Prometheus alerts, Kubecost integration, log anomaly detection. Safely letting AI make operational decisions with guardrails."},
    {"sec": "ai-ml-infrastructure", "num": "9.6", "stem": "high-performance-storage-ai",
     "title": "High-Performance Storage for AI",
     "topic": "High-performance storage for AI workloads on bare metal. NFS-over-RDMA, parallel file systems (Lustre, BeeGFS, WekaFS), data pipeline optimization. Managing training dataset storage at scale, checkpoint I/O, avoiding GPU idle on data bottlenecks. Storage tiering for hot/warm/cold model data."},
]


PROMPT_TEMPLATE = """You are writing a complete KubeDojo curriculum module. KubeDojo is a free,
open-source cloud-native curriculum for practitioners — engineers who already know
the basics of Kubernetes and need production-grade depth.

Audience: a senior DevOps / platform engineer who needs to operate this technology
on bare metal (no cloud managed services). They are not learning Kubernetes from
scratch — they are learning the practitioner-grade operational reality of THIS
specific topic.

## Module to write

**Title**: {title}
**Slug**: on-premises/{sec}/module-{num}-{stem}
**Section**: {sec}
**Number**: {num}

**Topic and scope**:
{topic}

## Required output structure

Return ONLY the module markdown. No preamble, no commentary, no "here is the module".
Start with the YAML frontmatter delimiter `---`.

Required sections in this order:

1. **Frontmatter** (YAML between `---` delimiters):
   - `title`: "{title}"
   - `description`: a one-sentence summary of what the module covers
   - `sidebar`: with `order: <derived from {num}>` (e.g. for 3.5 use 35, for 9.1 use 91)

2. **Title heading** (`# {title}`)

3. **Learning Outcomes** (`## Learning Outcomes`): a bulleted list of 4-6 specific
   skills the reader will gain. Each bullet starts with a verb (Configure, Diagnose,
   Compare, Implement, etc.). Outcomes must be measurable, not "understand X".

4. **Theory** (multiple `## Section` headings as needed): the conceptual depth needed
   to operate this technology. Include:
   - Architecture diagrams in Mermaid format where they help
   - Comparison tables when there are multiple options (Helm chart values, tool
     trade-offs, version differences)
   - Specific version numbers, API versions, deprecated paths, and current best practices
   - At least one production gotcha or war-story per major sub-section

5. **Hands-on Lab** (`## Hands-on Lab`): a runnable end-to-end exercise. Must include:
   - Prerequisites (`kind`, `kubectl`, `helm`, etc.)
   - Numbered steps with copy-pasteable commands and YAML manifests
   - Verification commands at each checkpoint
   - Expected output (`kubectl get ... -> READY`)
   - A brief "what to do if this fails" troubleshooting note for the most common failures

6. **Practitioner Gotchas** (`## Practitioner Gotchas`): 3-5 production failure modes
   that catch teams off-guard, each with 1-2 sentences of context and the fix.

7. **Quiz** (`## Quiz`): 5 scenario-based multiple-choice questions. Each question must:
   - Set up a scenario in 1-2 sentences (not just "what is X?")
   - Have 4 options (A/B/C/D)
   - Have exactly ONE correct answer marked
   - Test reasoning, not recall

8. **Further Reading** (`## Further Reading`): a bulleted list of 3-6 authoritative
   external links (official docs, CNCF announcements, project README files). NO
   blog posts unless from the project's official blog.

## Voice and quality constraints

- Practitioner-grade. Assume the reader knows what a Pod, Deployment, and Service are.
- No marketing language. Banned: "delve into", "leverage", "robust", "powerful",
  "seamless", "comprehensive", "in this section we will explore".
- Direct, terse, technically precise. Get to the point.
- All commands and YAML must be syntactically valid for current Kubernetes (1.32+).
- All version numbers, API names, helm chart values, and CRD field paths must be
  current. If you are unsure, prefer "current" framing rather than naming a specific
  version that might be wrong.
- Cover the learning outcomes fully. Cut padding and repetition, and explain every term,
  step and reason the learner needs, with worked examples; give both equal weight. Do
  not write to a word count.
- Use Starlight callout syntax for important notes: `:::note`, `:::caution`, `:::tip`.

Output ONLY the module markdown. Start with `---`. No preamble.
"""


FACT_CHECK_PROMPT_TEMPLATE = """You are doing a fact-grounding pass on a freshly-written KubeDojo curriculum
module. Your job is to identify every externally-versioned factual claim in the
module and verify it against current authoritative upstream sources.

As-of date: {as_of_date}
Module topic: {topic_label}

For each factual claim — version numbers, API names, helm chart values, command
flags, deprecation status, project status (CNCF sandbox/incubating/graduated),
metric names, doc URLs — return one of these verdicts:

- VERIFIED: the claim is supported by current authoritative sources.
- CONFLICTING: authoritative sources disagree.
- UNVERIFIED: cannot establish a reliable answer from authoritative sources.
- HALLUCINATED: you can verify the claim is factually wrong.

Rules:
- Do NOT answer from memory. Use current upstream documentation.
- Prefer official vendor/project docs over blog posts.
- Be honest about uncertainty. UNVERIFIED costs nothing. VERIFIED on something
  you cannot actually check is the worst possible answer.
- Only flag claims a reader would actually act on. Skip narrative framing.
- HALLUCINATED is the most important verdict — it means the module asserts
  something demonstrably false.

Return strict JSON only, no prose preamble.

Required JSON shape:
{{
  "module": "{module_key}",
  "as_of_date": "{as_of_date}",
  "claims": [
    {{
      "id": "C1",
      "claim": "exact claim from the module",
      "verdict": "VERIFIED | CONFLICTING | UNVERIFIED | HALLUCINATED",
      "current_truth": "what is actually true (or null if VERIFIED matches the claim)",
      "sources": [
        {{"url": "...", "source_date": "YYYY-MM-DD or null"}}
      ],
      "note": "one sentence explaining the verdict, especially if HALLUCINATED or CONFLICTING"
    }}
  ],
  "summary": {{
    "total_claims": N,
    "verified": N,
    "conflicting": N,
    "unverified": N,
    "hallucinated": N
  }}
}}

The module to fact-check is below the marker.

---MODULE---
{module_text}
---END MODULE---
"""


def log(msg: str) -> None:
    """Append to log file and print to stdout."""
    line = f"[{datetime.now(UTC).strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def module_path(m: dict) -> Path:
    return CONTENT_ROOT / m["sec"] / f"module-{m['num']}-{m['stem']}.md"


def factcheck_path(m: dict) -> Path:
    p = module_path(m)
    return p.with_suffix(".factcheck.json")


def is_stub(path: Path) -> bool:
    """A module is a stub if it doesn't exist or has < MIN_CONTENT_CHARS chars."""
    if not path.exists():
        return True
    return len(path.read_text(encoding="utf-8")) < MIN_CONTENT_CHARS


def extract_section_from_codex_output(raw: str) -> str:
    """Strip Codex CLI noise (banner, prompt echo, tokens, duplicated output)."""
    if "codex\n" in raw:
        after = raw.split("codex\n", 1)[1]
        if "\ntokens used\n" in after:
            after = after.split("\ntokens used\n", 1)[0]
        return after.strip()
    return raw.strip()


def extract_first_json_object(text: str) -> dict | None:
    """Find the first balanced {...} JSON object in text and parse it."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            cand = parts[1]
            if cand.startswith("json"):
                cand = cand[4:]
            try:
                return json.loads(cand.strip())
            except json.JSONDecodeError:
                pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    depth = 0
    end = -1
    for i in range(len(text) - 1, -1, -1):
        ch = text[i]
        if ch == "}":
            if depth == 0:
                end = i
            depth += 1
        elif ch == "{":
            if depth > 0:
                depth -= 1
                if depth == 0 and end != -1:
                    cand = text[i:end + 1]
                    try:
                        return json.loads(cand)
                    except json.JSONDecodeError:
                        end = -1
                        continue
    return None


def dispatch_writer(prompt: str, writer_model: str) -> tuple[bool, str]:
    """Dispatch to whichever writer model is configured. Routes by model name."""
    if writer_model.startswith("gemini"):
        # gemini-* slugs route to the agy Google lane; gemini-cli retired (#2125).
        return dispatch_agy(prompt, model=writer_model, timeout=900)
    if writer_model.startswith("gpt-") or writer_model == "codex":
        cmd = [
            "codex", "--search", "exec", "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "-m", writer_model, prompt,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=900, cwd=str(REPO_ROOT),
            )
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"
        if result.returncode != 0:
            return False, result.stderr[:500]
        return True, extract_section_from_codex_output(result.stdout)
    if writer_model.startswith("claude"):
        cmd = [
            VENV_PYTHON, str(REPO_ROOT / "scripts" / "dispatch.py"),
            "claude", "-", "--model", writer_model,
        ]
        try:
            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                timeout=900, cwd=str(REPO_ROOT),
            )
        except subprocess.TimeoutExpired:
            return False, "TIMEOUT"
        if result.returncode != 0:
            return False, result.stderr[:500]
        return True, result.stdout
    return False, f"unknown writer model: {writer_model}"


def dispatch_factcheck(module_text: str, module_key: str, topic_label: str) -> tuple[bool, dict | None]:
    """Run gpt-5.3-codex-spark on a module to produce a structured fact ledger."""
    prompt = FACT_CHECK_PROMPT_TEMPLATE.format(
        as_of_date=datetime.now(UTC).strftime("%Y-%m-%d"),
        topic_label=topic_label,
        module_key=module_key,
        module_text=module_text,
    )
    cmd = [
        "codex", "--search", "exec", "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
        "-m", FACT_CHECKER, prompt,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=FACT_CHECK_TIMEOUT, cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return False, None
    if result.returncode != 0:
        return False, None

    cleaned = extract_section_from_codex_output(result.stdout)
    parsed = extract_first_json_object(cleaned)
    if parsed is None:
        return False, None
    return True, parsed


def write_module(m: dict, idx: int, total: int, writer: str,
                 dry_run: bool = False, skip_factcheck: bool = False) -> bool:
    md_path = module_path(m)
    fc_path = factcheck_path(m)
    module_key = f"on-premises/{m['sec']}/module-{m['num']}-{m['stem']}"
    log(f"==== Module {idx + 1}/{total}: {module_key} ====")

    needs_write = is_stub(md_path)
    needs_factcheck = (not skip_factcheck) and (not fc_path.exists())

    if not needs_write and not needs_factcheck:
        log(f"  SKIP: module ({len(md_path.read_text(encoding='utf-8'))} chars) and fact-check both fresh")
        return True

    if dry_run:
        log(f"  [DRY RUN] writer={writer} write={needs_write} factcheck={needs_factcheck}")
        return True

    # Step 1: writer (skip if existing fresh content)
    if needs_write:
        prompt = PROMPT_TEMPLATE.format(**m)
        log(f"  WRITER: dispatching to {writer}")
        t0 = time.time()
        ok, output = dispatch_writer(prompt, writer)
        elapsed = time.time() - t0

        if not ok:
            log(f"  ❌ writer FAILED after {elapsed:.0f}s: {output[:300] if output else '(empty)'}")
            return False

        output = output.strip()
        if not output.startswith("---"):
            log("  ❌ INVALID: response does not start with frontmatter delimiter")
            log(f"     First 200 chars: {output[:200]}")
            return False

        if len(output) < MIN_CONTENT_CHARS:
            log(f"  ❌ TOO SHORT: {len(output)} chars (< {MIN_CONTENT_CHARS}); leaving stub")
            return False

        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(output, encoding="utf-8")
        log(f"  ✓ writer wrote {len(output)} chars in {elapsed:.0f}s")
    else:
        log("  SKIP writer: existing content fresh")

    # Step 2: fact-check (always runs unless --skip-factcheck)
    if needs_factcheck:
        module_text = md_path.read_text(encoding="utf-8")
        log(f"  FACT-CHECK: dispatching to {FACT_CHECKER}")
        t0 = time.time()
        ok, ledger = dispatch_factcheck(module_text, module_key, m["title"])
        elapsed = time.time() - t0

        if not ok or ledger is None:
            log(f"  ⚠ fact-check FAILED after {elapsed:.0f}s — module written but no ledger")
            return True  # don't fail the whole module — the markdown is still useful
        fc_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        summary = ledger.get("summary") or {}
        total_claims = summary.get("total_claims", "?")
        hallucinated = summary.get("hallucinated", "?")
        verified = summary.get("verified", "?")
        log(f"  ✓ fact-check: total={total_claims} verified={verified} hallucinated={hallucinated} (in {elapsed:.0f}s)")
        if isinstance(hallucinated, int) and hallucinated > 0:
            log(f"  ⚠ {hallucinated} HALLUCINATED claims — review priority HIGH")
    else:
        log("  SKIP fact-check: existing ledger fresh")

    return True


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    skip_factcheck = "--skip-factcheck" in args
    args = [a for a in args if a != "--skip-factcheck"]
    writer = DEFAULT_WRITER
    if "--writer" in args:
        i = args.index("--writer")
        if i + 1 < len(args):
            writer = args[i + 1]
            args = args[:i] + args[i+2:]
        else:
            log("usage: --writer <model-name>")
            return 2

    if args:
        try:
            indices = [int(a) - 1 for a in args]
        except ValueError:
            log("usage: phase2-write-only.py [--dry-run] [--skip-factcheck] [--writer MODEL] [N1 N2 ...]")
            return 2
    else:
        indices = list(range(len(MODULES)))

    log("="*70)
    log("Phase 2 write-only batch starting")
    log(f"  Modules: {len(indices)}")
    log(f"  Writer: {writer}")
    log(f"  Fact-checker: {FACT_CHECKER}{' (SKIPPED)' if skip_factcheck else ''}")
    log(f"  Log file: {LOG_FILE}")
    log("="*70)

    failed: list[str] = []
    high_halluc: list[tuple[str, int]] = []
    for i, idx in enumerate(indices):
        if idx < 0 or idx >= len(MODULES):
            log(f"  SKIP: invalid index {idx + 1}")
            continue
        ok = write_module(MODULES[idx], i, len(indices),
                          writer=writer, dry_run=dry_run, skip_factcheck=skip_factcheck)
        if not ok:
            failed.append(f"module-{MODULES[idx]['num']}-{MODULES[idx]['stem']}")
        else:
            # Surface high-hallucination modules in the final report
            fc = factcheck_path(MODULES[idx])
            if fc.exists():
                try:
                    data = json.loads(fc.read_text())
                    h = (data.get("summary") or {}).get("hallucinated", 0)
                    if isinstance(h, int) and h > 0:
                        high_halluc.append((f"{MODULES[idx]['sec']}/module-{MODULES[idx]['num']}-{MODULES[idx]['stem']}", h))
                except (json.JSONDecodeError, OSError):
                    pass

    log("")
    log("="*70)
    log("BATCH COMPLETE")
    log(f"  Attempted: {len(indices)}")
    log(f"  Failed: {len(failed)}")
    if failed:
        for k in failed:
            log(f"    - {k}")
    log(f"  Modules with hallucinations (review priority HIGH): {len(high_halluc)}")
    if high_halluc:
        for k, h in sorted(high_halluc, key=lambda x: -x[1]):
            log(f"    - {k}: {h} hallucinated claim(s)")
    log("  Run 'npm run build' before reviewing.")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
