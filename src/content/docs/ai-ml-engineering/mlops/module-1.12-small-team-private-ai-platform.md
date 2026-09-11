---
citations_verified: true
title: "Small-Team Private AI Platform"
slug: ai-ml-engineering/mlops/module-1.12-small-team-private-ai-platform
sidebar:
  order: 613
---

> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 2-3 hours

**Reading Time**: 2-3 hours  
**Prerequisites**: Experiment Tracking, ML Pipelines, Model Serving, Notebooks to Production for ML/LLMs, and the AI Infrastructure section

---

## Learning Outcomes

By the end of this module, you will be able to:

- design a small-team private AI platform that connects source control, experiment tracking, artifact storage, repeatable jobs, serving, and ownership rules into one coherent operating model
- evaluate which platform capabilities should be standardized now and which should be deliberately deferred until scale, compliance, or workload pressure justifies them
- debug common failure modes in small ML platforms, including laptop-only training, disconnected artifact stores, inconsistent serving patterns, and unclear ownership
- compare lightweight private platform choices against enterprise MLOps patterns without copying complexity that the team cannot operate
- create a phased evolution plan that lets a small team grow from shared discipline to shared services, operational hardening, and later platform expansion

---

## Why This Module Matters

A four-person ML team at a healthcare startup had a model that looked excellent in a notebook, passed a local evaluation script, and was quietly copied into an internal API by the only engineer who knew how the artifact was produced. Three months later, a customer-reported regression forced the team to ask basic questions under pressure: which run produced the model, which dataset snapshot was used, which prompt template changed, who approved the deployment, and whether the previous artifact could be restored. Everyone remembered part of the story, but no one could reconstruct the system.

The team did not fail because it lacked advanced tooling. It failed because its working process never became a platform. There was Git, there were notebooks, there was object storage, and there was a model endpoint, but those pieces did not form a reliable chain from experiment to artifact to deployment to ownership. When work remained personal and informal, every production question became an archaeological dig through laptop folders, chat messages, and half-remembered commands.

A small-team private AI platform exists to prevent that middle-ground failure. It is not a miniature version of a hyperscale platform, and it should not begin with a portal, multi-cluster architecture, or complex tenancy model. It is a deliberately small shared system that gives the team enough repeatability, traceability, serving discipline, and access control to move faster without becoming reckless.

The private part matters because many AI teams cannot send datasets, prompts, model outputs, or customer context to arbitrary external systems. The small-team part matters because the people building the platform are often the same people training models, writing evaluations, serving endpoints, responding to incidents, and explaining decisions to leadership. A sustainable design must improve their leverage rather than becoming a second product they have to maintain.

---

## The Platform Boundary: What Counts and What Does Not

A small-team private AI platform is a shared operating environment for model development and internal AI services. It gives the team one accepted way to track experiments, store artifacts, run training or evaluation jobs, expose inference endpoints, and decide who owns what. The platform may use managed services, open-source tools, or simple scripts, but it must create a shared path that another teammate can follow without reverse engineering someone else's laptop.

The boundary is important because small teams are vulnerable to two opposite mistakes. One mistake is under-building: every engineer keeps a private workflow, and the team pretends coordination will happen through memory and chat. The other mistake is over-building: the team copies an enterprise reference architecture and spends its limited energy operating infrastructure instead of delivering useful AI systems. A good small-team platform avoids both by standardizing the few capabilities that remove repeated confusion.

The easiest way to recognize a platform is to ask whether it can answer operational questions without heroics. If a model endpoint is misbehaving, can the team identify the artifact, run, config, data source, owner, deployment path, logs, and rollback option? If the answer depends on one person's memory, the platform is not yet doing its job. If the answer comes from shared records and repeatable commands, the team has crossed from informal tooling into a real operating model.

A private AI platform also needs an explicit "not yet" list. If the team has not agreed that multi-cluster scheduling, fine-grained chargeback, self-service project provisioning, or advanced governance workflows are out of scope for now, those expectations will drift into planning conversations anyway. Saying "not solved yet" is not a weakness; it protects focus and makes later upgrades intentional.

> **Pause and predict:** Imagine a six-person team that has Git, a shared bucket, and a model endpoint, but no experiment tracking. Before reading further, write down the first three questions the team will struggle to answer when a production model regresses. Then compare your list with the traceability chain in the next section.

A useful mental model is that the platform is the path, not the pile of tools. Tools become a platform only when they are connected by conventions, ownership, and verification. Without those connections, the team has a cabinet of parts, and every new model becomes a custom assembly project.

```text
+----------------------+      +------------------------+      +----------------------+
| Source + Configs     | ---> | Tracked Run            | ---> | Artifact + Metadata  |
| repo, docs, reviews  |      | params, metrics, code  |      | model, data, lineage |
+----------------------+      +------------------------+      +----------------------+
              |                            |                              |
              |                            v                              v
              |                 +------------------------+      +----------------------+
              |                 | Repeatable Job         | ---> | Internal Serving     |
              |                 | train, eval, batch     |      | API, logs, rollback  |
              |                 +------------------------+      +----------------------+
              |                                                            |
              v                                                            v
+----------------------+                                      +----------------------+
| Ownership Rules      |                                      | Consumers            |
| deploy, restore, ACL |                                      | apps, notebooks, ops |
+----------------------+                                      +----------------------+
```

This diagram deliberately shows a small number of boxes. The first design review for a small-team platform should not be about how many tools can be added. It should be about whether every model can move through this path in a way that is understandable, repeatable, and recoverable.

---

## Capability One: Shared Source of Truth

The first capability is not glamorous, but it is foundational: the team needs one source of truth for code, configuration, infrastructure definitions, and operating documentation. In a small team, the source of truth is usually a Git repository or a small set of repositories with clear ownership. The important point is not whether the team chooses a monorepo or several repos; the important point is that model behavior is not defined by uncommitted notebook cells and private shell history.

A source of truth must include more than Python files. It should include the training entry point, environment definition, evaluation configuration, serving contract, deployment notes, and a short explanation of how artifacts are named. When those pieces live together, a reviewer can connect a code change to the run it will produce and the service it may affect. When they are scattered, even a simple update becomes difficult to reason about.

Small teams often avoid structure because it feels premature. The better framing is that structure should be minimal but real. A reasonable first repository layout can be understood in minutes, but it still tells the team where code, jobs, serving, and docs belong. The layout below is intentionally plain because the first platform rule should be easy to follow.

```text
private-ai-platform/
├── README.md
├── docs/
│   ├── platform-scope.md
│   ├── serving-standard.md
│   ├── ownership.md
│   └── roadmap.md
├── ml/
│   ├── train.py
│   ├── evaluate.py
│   └── configs/
├── serving/
│   ├── app.py
│   └── model_contract.md
├── ops/
│   ├── run-train.sh
│   ├── run-eval.sh
│   └── deploy-serving.sh
└── artifacts/
    └── README.md
```

This layout solves a teaching problem as much as an operational one. New teammates can learn the platform by walking the directory tree, because the design exposes the workflow. The repository says: training code is here, serving code is here, operational scripts are here, and platform decisions are documented here.

The team should also decide how much infrastructure-as-code belongs in the same place. For a very small platform, a `docker-compose.yml`, Helm values file, or Terraform module can live near the docs if that keeps the system understandable. As the platform grows, infrastructure may move into a dedicated repository. The key is that there must always be a discoverable link between platform behavior and the files that define it.

A source of truth is only useful if changes are reviewed with the right questions. For a small-team AI platform, review should ask whether the change preserves reproducibility, traceability, serving compatibility, and rollback. Reviewing only style or syntax misses the platform risk. Reviewing only model quality misses the operational risk.

> **Stop and think:** A teammate proposes storing prompt templates in the serving container image but outside Git because "they change often." What breaks when prompt templates are not versioned with the service contract, and how would your rollback story change?

The answer is that unversioned prompt templates create hidden behavior. A model endpoint can change without a code review, a run can become impossible to reproduce, and rollback may restore the old container while keeping the new prompt. The small-team rule is simple: if a file changes model behavior, evaluation behavior, or serving behavior, it belongs in the source of truth or in a versioned system linked from it.

---

## Capability Two: Experiment and Artifact Tracking

Experiment tracking is where a private AI platform starts to become inspectable. It records the relationship between code, parameters, metrics, datasets, artifacts, and human decisions. Without it, the team may have trained many models, but it cannot explain which result is trustworthy or why a particular artifact was promoted.

Artifact tracking is the companion capability. A tracked run without durable artifacts is only a note about work that may no longer exist. An artifact store without run metadata is just a bucket full of files. The platform needs both: metadata that explains how something was produced, and storage that preserves the output under predictable names and access rules.

For a small team, MLflow or an equivalent tracking tool is often enough to begin. The goal is not to adopt every feature immediately. The goal is to create one default experiment, one artifact location, one naming convention, and one habit: every training or evaluation run that may influence a shared decision must be logged. That habit is more valuable than a complex registry that no one uses consistently.

The minimum metadata should answer a short but powerful set of questions. What code version ran? What config was used? Which input data source or dataset snapshot was referenced? What metrics were produced? Which artifact path contains the model or evaluation output? Who ran it, and what decision was made afterward? If the team cannot answer those questions, later serving and incident response will be fragile.

| Platform Question | Tracking Record Needed | Artifact Record Needed | Why It Matters |
|---|---|---|---|
| Which run produced the current model? | run ID, commit, config | model path and checksum | Enables rollback and comparison |
| Which data shaped the result? | dataset version or source URI | evaluation outputs | Prevents silent data drift confusion |
| Why was the model promoted? | metrics, notes, reviewer | promoted artifact reference | Makes decisions auditable |
| Can we reproduce the result? | environment and parameters | saved model and dependencies | Reduces laptop-only knowledge |
| Who owns follow-up? | run owner and endpoint owner | storage owner | Avoids orphaned production assets |

Notice that the table includes ownership because traceability is not only technical. A run can be perfectly logged and still become operationally risky if no one owns the artifact or knows whether it can be deleted. Small teams should keep ownership lightweight, but they should not leave it implicit.

A practical convention is to treat run IDs and artifact URIs as first-class references in pull requests, deployment notes, and incident records. Instead of saying "deployed the latest classifier," the team says "deployed model artifact from run `churn-baseline-2026-04-20-a`, evaluated with config `eval-v3`, rollback artifact `churn-baseline-previous`." The exact naming scheme can vary, but the discipline must be consistent.

```bash
export MLFLOW_TRACKING_URI="http://127.0.0.1:5000"
export ARTIFACT_BUCKET="ml-platform-artifacts"
export RUN_NAME="support-triage-baseline"

.venv/bin/python ml/train.py \
  --config ml/configs/support-triage.yaml \
  --run-name "$RUN_NAME" \
  --artifact-root "s3://$ARTIFACT_BUCKET/models/support-triage"
```

This command is intentionally boring. It names the tracking server, points to a config, chooses a run name, and declares an artifact root. Boring commands are good platform design when they are shared, documented, and repeatable.

---

## Capability Three: Repeatable Training and Evaluation Jobs

Repeatable job execution is the difference between "Alice can train it" and "the team can operate it." A job does not need to run on a large Kubernetes cluster to be repeatable. It needs a documented entry point, a reproducible environment, explicit inputs, explicit outputs, and a record of what happened. A small team can begin with scripts, CI jobs, a simple queue, or Kubernetes Jobs, as long as the job is not trapped inside one person's notebook session.

Notebooks can still be useful for exploration. The mistake is letting notebooks become the only executable definition of training. Once a model is a candidate for shared use, the path should move from exploratory notebook to script or package entry point. That shift reduces ambiguity because the team can run the same command in local development, CI, a job runner, or a cluster.

A repeatable job should make assumptions visible. If it reads data from a path, that path should be configured rather than hidden in code. If it writes artifacts, the location should follow a convention. If it depends on secrets, the environment variables should be documented and excluded from source control. If it logs metrics, the tracking URI should be supplied consistently.

The small-team version of orchestration is sequencing with discipline. A training run may need to prepare data, train, evaluate, log artifacts, and write a summary. The team can express that sequence in a shell script or Make target before adopting a full workflow engine. The important question is whether the sequence is understandable, rerunnable, and observable.

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://127.0.0.1:5000}"
export ARTIFACT_DIR="${ARTIFACT_DIR:-artifacts/support-triage}"

mkdir -p "$ARTIFACT_DIR"

.venv/bin/python ml/train.py \
  --config ml/configs/support-triage.yaml \
  --artifact-dir "$ARTIFACT_DIR" \
  --summary-file artifacts/last-run.json

.venv/bin/python ml/evaluate.py \
  --summary-file artifacts/last-run.json \
  --output-file artifacts/last-eval.json
```

This script is runnable in shape, but its deeper purpose is social. It gives the team one command to discuss, review, and improve. If a teammate wants to add a data validation step, they can add it to the shared entry point instead of writing a private instruction in a chat message.

For teams already using Kubernetes, a `Job` can be a good next step because it moves execution off laptops while keeping the abstraction simple. The team should not jump straight to a large workflow platform unless there is a real need for dependency graphs, retries across many steps, scheduled pipelines, or cross-team self-service. A single Kubernetes Job can be enough to standardize runtime, resources, and logs.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: support-triage-train
  labels:
    app.kubernetes.io/name: support-triage
    platform.kubedojo.io/workload: training
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: train
          image: registry.internal.example/ml/support-triage-train:2026-04-20
          env:
            - name: MLFLOW_TRACKING_URI
              value: "http://mlflow.ml-platform.svc.cluster.local:5000"
            - name: ARTIFACT_ROOT
              value: "s3://ml-platform-artifacts/models/support-triage"
          command:
            - /bin/sh
            - -c
            - ".venv/bin/python ml/train.py --config ml/configs/support-triage.yaml"
```

This manifest also shows what should be standardized early: labels, image naming, tracking URI, artifact root, and restart behavior. It does not require the team to build a complex scheduler. It gives the platform a repeatable unit of execution that operators can inspect.

> **Pause and predict:** If this job succeeds but the tracking server is unreachable, what should the team consider the state of the run: successful, failed, or quarantined? Write your answer before reading the next paragraph.

A strong small-team platform treats the run as incomplete or quarantined because the artifact cannot be trusted without metadata. The model file may exist, but the team cannot connect it to parameters, metrics, and decision records. This is why job scripts should fail when required tracking or artifact writes fail, unless the team has an explicit offline recovery process.

---

## Capability Four: Stable Internal Model Serving

Serving should be standardized earlier than many teams expect because serving is where private experiments become shared dependencies. If every model exposes a different API shape, packaging format, logging style, and rollback method, incidents become difficult even when traffic is modest. The goal is not to force every model into one architecture forever. The goal is to prevent avoidable fragmentation while the team is small enough to agree on simple rules.

A good first serving standard defines the request shape, response shape, health endpoint, versioning rule, logging fields, authentication expectation, and rollback approach. The standard should be concrete enough that a teammate can implement a new service without inventing a deployment pattern. It should also be modest enough that exceptions are possible when a workload genuinely needs something different.

For internal AI services, the first endpoint pattern is often a simple HTTP API with `/health` and `/predict`. The health endpoint proves that the service is alive and has loaded required dependencies. The prediction endpoint accepts a typed request and returns a typed response with model version information. Even if the model itself changes, the contract should remain stable or be versioned deliberately.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="support-triage-service", version="1.0.0")

MODEL_VERSION = "support-triage-2026-04-20"


class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    label: str
    score: float
    model_version: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    label = "needs-human-review" if len(request.text.split()) > 8 else "auto-reply-candidate"
    score = min(0.95, 0.55 + len(request.text.split()) / 100)
    return PredictResponse(label=label, score=score, model_version=MODEL_VERSION)
```

This example is intentionally simple, but it captures several platform habits. The service has a declared version, a health check, a typed request, a typed response, and predictable behavior. In a real model service, the prediction function would load a model artifact, but the surrounding contract should look just as plain.

Serving logs need a standard too. At minimum, the team should log request ID, endpoint version, model version, latency, status, and error class. For privacy-sensitive AI systems, the team must decide whether prompts, inputs, or outputs can be logged at all. The safest small-team default is to log metadata first and require explicit approval before storing sensitive content.

Rollback should be practiced before the first incident. A simple rollback plan might say that each service keeps the previous model artifact available, deploys model version changes independently from API contract changes when possible, and records the run ID for both current and previous artifacts. The plan should identify who can trigger rollback and what verification command proves the endpoint is healthy afterward.

```bash
curl -sf http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"text":"customer cannot access the billing dashboard after password reset"}'
```

These commands are not just smoke tests. They are part of the serving standard because they define what "the service is usable" means. A small platform becomes easier to operate when every service can be checked in the same way.

---

## Capability Five: Access, Ownership, and Recovery

Small teams often delay access control because everyone trusts everyone. Trust is valuable, but it does not replace ownership. A team can trust each other and still accidentally overwrite a model, delete a dataset snapshot, leak a token, or deploy an endpoint no one else understands. Access rules protect the team from confusion as much as they protect against malicious behavior.

Ownership should be assigned to platform surfaces rather than only to people. Someone owns experiment tracking availability. Someone owns artifact bucket policy. Someone owns serving standards. Someone owns a model endpoint. Someone owns restoring from backup. A small team can rotate these duties, but it should never be unclear who makes a decision during an incident.

The access model can begin with a simple matrix. The matrix should say who can read artifacts, write artifacts, register or promote models, deploy services, rotate secrets, and delete shared resources. The first version can be maintained in documentation if the team is not ready for automated policy management. The important part is that the documented rule matches reality.

| Capability | Developer | Model Owner | Platform Owner | Team Lead |
|---|---:|---:|---:|---:|
| Read experiment runs | yes | yes | yes | yes |
| Write experiment runs | yes | yes | yes | limited |
| Promote model artifact | no | yes | yes | approve |
| Deploy serving endpoint | no | yes | yes | approve |
| Rotate platform secrets | no | no | yes | approve |
| Delete shared artifacts | no | no | restricted | approve |
| Restore deleted artifact | request | request | yes | informed |

The table is small enough to maintain, but it forces decisions that otherwise remain hidden. For example, developers can write experiment runs but cannot promote production artifacts alone. A model owner can request deployment, while a platform owner ensures the serving standard and rollback process are followed. The team lead approves high-risk changes without becoming the day-to-day operator.

Recovery deserves special attention because many small teams discover their backup story only after losing something. Artifact buckets should have versioning or retention. Tracking databases should have backups. Serving deployments should keep a previous known-good artifact. Documentation should say how to restore and who is allowed to do it. If a restore procedure is too complicated to write down, it is too complicated to rely on.

> **Stop and think:** Your team has bucket versioning enabled, but only one person knows the restore command and that person is on vacation. Is the platform recoverable in practice? Explain what documentation or access change would make the answer different.

The answer is that recoverability is a team property, not a storage feature. Versioning creates the possibility of recovery, but documented procedure, tested permissions, and assigned ownership make recovery real. A small platform should practice one restore before it is needed, even if the practice uses a harmless test artifact.

Secrets should also follow a small but explicit rule. No secret belongs in Git, notebook output, experiment parameters, or model artifacts. Local development can use `.env` files excluded from source control, while shared environments should use the team's normal secret manager or platform-native secret mechanism. The platform documentation should name the secret owner and rotation process because vague secret handling eventually becomes incident handling.

---

## Worked Example: Rescuing a Laptop-Only Model

This worked example demonstrates the design process before you attempt the hands-on exercise. The scenario is intentionally common: a small team has a useful classifier trained from a notebook, but it cannot be reproduced, promoted, or served safely. The goal is not to build an enterprise platform in one move. The goal is to convert one fragile workflow into the first slice of a private AI platform.

The team begins with a notebook called `ticket_triage_final.ipynb` on a developer's workstation. The notebook reads a CSV from a local downloads folder, trains a classifier, prints accuracy, and saves `model.pkl` beside the notebook. The model was copied into a small FastAPI service, but the endpoint does not report a model version, and no one knows which dataset produced the current artifact.

### Step 1: Identify the platform questions that cannot be answered

The first step is diagnostic, not technical. The team lists the questions they would need to answer during a regression, audit, or handoff. They discover that they cannot identify the dataset snapshot, code version, parameters, metric threshold, artifact checksum, model owner, or rollback artifact. This confirms that the problem is not merely "the notebook is messy"; the problem is that the team lacks traceability across the model lifecycle.

### Step 2: Move behavior into the source of truth

The team creates `ml/train.py`, `ml/configs/ticket-triage.yaml`, and `serving/app.py` in Git. The notebook can remain as exploration history, but it is no longer the production definition of training. The training script accepts a config path and artifact directory, so another teammate can run it without editing code. The config records the dataset URI, feature settings, and evaluation threshold.

```yaml
dataset_uri: "s3://private-ai-data/ticket-triage/snapshot-2026-04-20.csv"
target_column: "label"
text_column: "ticket_text"
metric_threshold:
  accuracy: 0.84
artifact_name: "ticket-triage-model"
```

This config is small, but it changes the review conversation. Instead of asking what a notebook cell happened to read, reviewers can inspect the dataset URI and threshold directly. The platform now has a visible control surface for training behavior.

### Step 3: Add a repeatable training command

The team creates a single script called `ops/run-train.sh`. It sets the tracking URI, creates the artifact directory, runs the training script, and writes a summary file. This does not require a workflow platform yet. It creates one repeatable command that can later move into CI or a Kubernetes Job.

```bash
#!/usr/bin/env bash
set -euo pipefail

export MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://127.0.0.1:5000}"
mkdir -p artifacts/ticket-triage

.venv/bin/python ml/train.py \
  --config ml/configs/ticket-triage.yaml \
  --artifact-dir artifacts/ticket-triage \
  --summary-file artifacts/last-run.json
```

The team now has a shared entry point. If the model changes, the change should flow through this script or an intentional successor. This is how a platform starts: one repeated manual process becomes a shared, reviewable command.

### Step 4: Connect tracking and artifact storage

The training script logs parameters, metrics, and the produced artifact. The team decides that every candidate model must have a run ID and artifact URI before it can be considered for serving. If tracking is unavailable, the script fails rather than producing an untraceable artifact. This rule may feel strict, but it prevents the team from creating another mystery model.

```json
{
  "run_name": "ticket-triage-baseline",
  "run_id": "ticket-triage-2026-04-20-a",
  "artifact_uri": "s3://ml-platform-artifacts/models/ticket-triage/ticket-triage-2026-04-20-a",
  "accuracy": 0.86,
  "model_owner": "ml-platform-team"
}
```

The summary file gives humans and automation a stable handoff. A deployment script can read it, a pull request can reference it, and an incident note can compare it with the previous run. The exact format is less important than the fact that the team has a consistent record.

### Step 5: Standardize the serving contract

The team updates the FastAPI service to expose `/health` and `/predict`, include `model_version` in responses, and log request metadata. The endpoint contract is documented in `docs/serving-standard.md`. The model artifact is loaded from a configured path rather than copied by hand into an unknown location.

```json
{
  "text": "customer cannot sign in after password reset"
}
```

```json
{
  "label": "account-access",
  "score": 0.91,
  "model_version": "ticket-triage-2026-04-20-a"
}
```

The service now tells consumers what version they are using. That makes debugging easier because application logs and model logs can be connected. It also gives the team a simple compatibility promise: clients depend on the request and response contract, while the model artifact can be updated behind that contract when behavior changes are approved.

### Step 6: Define ownership and recovery

The team writes `docs/ownership.md` and records that the model owner approves promotions, the platform owner deploys serving changes, and the team lead approves deletion of shared artifacts. They enable retention on the artifact store and document how to restore the previous model. They also name a backup owner so recovery does not depend on one person's memory.

This final step is where many small teams stop too early. They believe the platform is complete once the code runs. In practice, the platform becomes reliable only when someone owns the lifecycle and the recovery path. A model that can be trained and served but not restored is still a fragile system.

### Step 7: Decide what is deliberately deferred

The team writes a short roadmap. They standardize tracking, artifacts, repeatable training, serving contracts, and ownership now. They defer a platform portal, multi-cluster scheduling, complex tenancy, and chargeback because one team does not yet need them. This protects the team from architecture theater and makes future expansion conditional on real pressure.

The worked example teaches the pattern you will use in the exercise: diagnose the missing traceability, move behavior into source control, create one repeatable job, connect tracking and artifacts, standardize serving, assign ownership, and defer advanced features explicitly. The sequence matters because each step removes a concrete failure mode before the team adds more machinery.

---

## Choosing What to Standardize First

Small teams need a decision framework because every platform conversation can become a tool debate. The useful question is not "Which tool is best?" but "Which repeated confusion should we eliminate next?" A capability deserves standardization when it affects reproducibility, production safety, collaboration, or recovery often enough that individual preference creates team risk.

The first standard is usually project structure and source control. Without it, the team cannot review or reproduce behavior. The second standard is tracking and artifact storage because those create the lineage needed for model decisions. The third standard is job execution because it moves important work off personal machines. The fourth standard is serving because internal consumers need stable contracts. Ownership sits across all of these because every shared surface needs a responsible party.

Some capabilities should remain lightweight. A small team may not need a model registry UI if a tracked run plus artifact URI plus promotion document is enough. It may not need a workflow engine if a script and CI job cover current training. It may not need multi-tenant isolation if one trusted team is using the environment and access boundaries are documented. Deferring these choices is responsible when the team has named the trigger that would change the decision.

| Capability | Standardize Early When | Keep Lightweight When | Upgrade Trigger |
|---|---|---|---|
| Repository layout | multiple people touch training or serving | one prototype is still private | repeated handoff confusion |
| Experiment tracking | metrics influence shared decisions | exploration is throwaway | promotion needs audit trail |
| Artifact storage | models are reused or served | outputs are temporary | rollback or comparison matters |
| Job execution | laptops create inconsistent runs | one engineer is exploring | scheduled or shared runs appear |
| Serving contract | consumers call the model | service is local-only | clients need compatibility |
| Access rules | shared resources can be changed | one sandbox is isolated | deletion or secret risk appears |
| Workflow engine | many dependent steps exist | one or two commands suffice | retries and scheduling dominate |

This table should be used during planning, not after the architecture is already chosen. If a proposed tool does not map to a current standardization need or a named upgrade trigger, the team should treat it as optional. Optional tools are not forbidden, but they should not become platform dependencies by accident.

---

## A Practical Reference Architecture

A realistic private AI platform for a small team can be built from modest parts. It may use Git for source, MLflow for tracking, object storage for artifacts, a script or CI job for training, FastAPI for internal serving, and Kubernetes or a small VM environment for running services. The important design property is coherence: each part knows how it connects to the next.

```text
+--------------------------------------------------------------------------------+
|                         Small-Team Private AI Platform                          |
+--------------------------------------------------------------------------------+
|                                                                                |
|  +------------------+       +--------------------+       +-------------------+  |
|  | Git Repository   | ----> | Training/Eval Job  | ----> | Experiment Run    |  |
|  | code, config,    |       | script, CI, or     |       | params, metrics,  |  |
|  | docs, contracts  |       | Kubernetes Job     |       | notes, owner      |  |
|  +------------------+       +--------------------+       +-------------------+  |
|            |                          |                              |          |
|            |                          v                              v          |
|            |                +--------------------+       +-------------------+  |
|            |                | Artifact Store     | <---- | Promotion Record  |  |
|            |                | models, evals,     |       | approved run,     |  |
|            |                | reports, datasets  |       | rollback target   |  |
|            |                +--------------------+       +-------------------+  |
|            |                          |                              |          |
|            v                          v                              v          |
|  +------------------+       +--------------------+       +-------------------+  |
|  | Platform Docs    | ----> | Serving Service    | ----> | Internal Clients  |  |
|  | scope, access,   |       | health, predict,   |       | apps, tools,      |  |
|  | ownership, ops   |       | logs, rollback     |       | notebooks, APIs   |  |
|  +------------------+       +--------------------+       +-------------------+  |
|                                                                                |
+--------------------------------------------------------------------------------+
```

The diagram does not require every box to be a separate product. The promotion record could be a pull request, a small YAML file, an MLflow registry transition, or an internal deployment note. The platform docs could be Markdown files at first. The training job could run locally during early development and later move into CI or Kubernetes. What matters is that the team can trace a model from source to run to artifact to service to owner.

Private deployment choices depend on the team's constraints. A team with strict data rules may self-host tracking and object storage. A team with acceptable managed-service boundaries may use a private cloud bucket and managed CI while keeping sensitive datasets inside approved networks. The design should document what is self-hosted, what is external, and why the boundary is acceptable.

For a small team, one environment may be enough at first, but naming environments early prevents confusion. Development can be local or sandboxed, staging can validate the serving contract with realistic artifacts, and production can serve internal consumers. Even if all three environments are lightweight, separating their purpose reduces accidental promotion of experiments.

Monitoring should start simple as well. The platform should collect service health, latency, errors, model version, and basic request counts. For model quality, the team should log evaluation results at promotion time and define how drift or poor feedback will be investigated. Full observability maturity can come later, but the first platform should not be blind.

---

## Avoiding Enterprise Imitation

Enterprise MLOps platforms solve real problems, but not every team has those problems yet. Large organizations need self-service onboarding, multi-team tenancy, policy enforcement, chargeback, centralized governance, complex scheduling, and deep audit workflows. A small team may eventually need some of those capabilities, but copying them too early creates operational drag before it creates value.

The danger is that enterprise diagrams look authoritative. They show many layers, many services, and many control points, so they can make a simple design feel immature. Senior engineering judgment is the ability to distinguish missing maturity from appropriate simplicity. A small team should be able to explain why it does not yet need a layer, not merely apologize for lacking it.

A useful test is operator burden. If the proposed platform requires more operational attention than the workloads it supports, the design is likely too heavy. If it requires skills the team does not have and cannot maintain, the design is risky. If it slows down model iteration without improving reproducibility, safety, or recovery, the design is misaligned.

Another test is adoption. Small-team platforms fail when the official path is so complex that engineers quietly return to private notebooks and manual copies. The platform should make the right path easier than the wrong path. A shared training script, default experiment, documented artifact path, and predictable serving template can outperform a grand architecture that no one uses.

This does not mean the team should reject serious tools. Kubernetes Jobs, MLflow, object storage, CI, and identity integration can be excellent choices when they solve current problems. The discipline is to adopt them in the smallest coherent shape first, then expand when the next bottleneck is real.

---

## Maturity Path for a Small Team

A small-team private AI platform should grow in layers. Each layer adds capabilities that depend on the previous layer. Skipping layers creates hidden gaps because advanced automation cannot compensate for missing source control, missing tracking, or missing ownership. The path below is a practical maturity model rather than a procurement plan.

```text
Layer 4: Platform Expansion
         self-service, stronger isolation, larger serving, governance workflows
                     ▲
Layer 3: Operational Hardening
         monitoring, backups, access control, rollback practice, runbooks
                     ▲
Layer 2: Shared Services
         tracking, artifact storage, internal endpoints, shared job runners
                     ▲
Layer 1: Shared Discipline
         Git, configs, project layout, repeatable commands, review habits
```

Layer 1 is about discipline. The team agrees where code lives, how configs are reviewed, how training is invoked, and how decisions are documented. This layer is not glamorous, but it prevents most early chaos. Without it, shared services will become inconsistent because every user brings a private workflow.

Layer 2 introduces shared services. Experiment tracking, artifact storage, and internal serving give the team a common environment. The platform begins to provide leverage because work can be compared, reused, and consumed by others. The team should still keep the number of patterns small.

Layer 3 hardens operations. Backups, access control, monitoring, rollback practice, and runbooks become more important as the platform supports decisions or internal products. The team should rehearse failure handling at this stage because the cost of confusion is rising. Hardening is not bureaucracy; it is how a useful platform becomes trustworthy.

Layer 4 expands the platform. Self-service onboarding, stronger workload isolation, heavier governance, more advanced scheduling, and larger serving infrastructure may become necessary when multiple teams depend on the system. By this point, the team has real usage data and can justify complexity with evidence. Expansion becomes a response to pressure, not a guess.

---

## Did You Know?

- **MLflow began as an open-source project for the full ML lifecycle**: Small teams often adopt only its tracking and artifact features first, which is a reasonable starting point when the immediate problem is traceability rather than complete platform automation.
- **Kubernetes Jobs are often enough for early shared training**: A team does not need a full workflow engine to stop relying on personal laptops; one well-defined Job can standardize image, command, resources, logs, and failure behavior.
- **Object storage conventions can matter as much as the storage product**: A bucket full of unnamed model files is not a platform, while a simple naming scheme tied to run IDs can make rollback and audit practical.
- **The first access-control failure in a small team is often accidental**: The common early incident is not an attacker bypassing policy, but a trusted teammate overwriting, deleting, or exposing something because ownership and permissions were never written down.

---

## Common Mistakes

| Mistake | What Goes Wrong | Better Practice |
|---|---|---|
| Starting with a large platform portal | The team spends months building UI and abstractions before standardizing training, artifacts, or serving | Begin with shared commands, docs, tracking, artifact paths, and one serving pattern |
| Treating notebooks as production definitions | Runs depend on hidden state, local files, and cell execution order, so teammates cannot reproduce results | Move candidate training and evaluation into scripts or package entry points |
| Logging metrics without saving artifacts | The team can see that a run happened but cannot restore or deploy the produced model reliably | Store artifacts durably and link artifact URIs to run metadata |
| Saving artifacts without run metadata | The bucket contains model files, but no one knows which config, data, or code produced them | Require run IDs, commit references, parameters, metrics, and owner notes for shared artifacts |
| Standardizing serving too late | Every model gets a different API, auth pattern, logging format, and rollback process | Define a minimal `/health` and `/predict` contract, versioning rule, and logging standard early |
| Avoiding ownership because the team is small | Shared systems become fragile when deletion, deployment, restore, and secret rotation are everyone's job | Assign lightweight owners for tracking, storage, serving, model promotion, and recovery |
| Copying enterprise MLOps patterns too early | The platform becomes harder to operate than the workloads it supports, so adoption drops | Defer multi-cluster, complex tenancy, portals, and heavy governance until concrete triggers appear |

---

## Quiz

**Q1.** Your team has five ML engineers. Each engineer trains from a local notebook, copies promising model files into a shared bucket, and announces results in chat. A production regression appears, and the team cannot identify the dataset or parameters used by the deployed model. What should you standardize first, and why?

<details>
<summary>Answer</summary>

Standardize experiment tracking and artifact conventions around a repeatable training entry point. The immediate failure is traceability: the team cannot connect model behavior to code, config, data, metrics, and artifact URI. A full enterprise platform would be premature, but a shared script plus tracking server plus artifact naming rule would let the team reproduce, compare, and roll back candidate models.

</details>

**Q2.** A teammate proposes adopting a workflow engine, model registry, feature store, policy engine, and platform portal in the first quarter. The team currently has one internal model, no shared training command, and no documented serving contract. How would you evaluate this proposal?

<details>
<summary>Answer</summary>

The proposal is over-scoped for the current maturity level. The team should first build shared discipline and shared services: source-controlled configs, repeatable training, experiment tracking, artifact storage, a simple serving contract, and ownership rules. The proposed tools may become useful later, but adopting them before the basic path exists creates operator burden without solving the immediate reproducibility and serving problems.

</details>

**Q3.** A small team has MLflow tracking enabled, but training scripts continue even when they cannot write to MLflow. The scripts still save model files locally and mark the run as successful in CI. During review, what risk should you call out, and what change would you require?

<details>
<summary>Answer</summary>

The risk is that the team is producing untraceable artifacts that look successful but cannot be connected to metadata. For shared candidate models, tracking failure should fail the job or place the artifact in an explicit quarantine path that cannot be promoted. The required change is to make tracking and artifact logging part of the success criteria for any run that may influence deployment or shared decisions.

</details>

**Q4.** Your team exposes three internal AI services. One uses `/predict`, another uses `/classify`, and another accepts raw text over a custom endpoint. Only one service reports its model version. Incidents are taking longer because clients and operators cannot compare behavior. What platform standard would you introduce?

<details>
<summary>Answer</summary>

Introduce a minimal serving standard that defines health checks, prediction endpoint shape, request and response schemas, model version reporting, logging fields, and rollback expectations. The goal is not to make every model identical internally. The goal is to give consumers and operators a predictable contract so incidents can be debugged without relearning each service from scratch.

</details>

**Q5.** A team lead says access control can wait because the platform is used only by trusted employees. Two weeks later, a developer deletes an old artifact that turns out to be the rollback target for a production service. How should the platform design change?

<details>
<summary>Answer</summary>

The team should add lightweight ownership, permissions, and recovery rules for shared artifacts. Trusted employees can still make accidental destructive changes, so delete permissions should be restricted, artifact retention or versioning should be enabled, and the rollback target should be documented in promotion records. The platform should also name who can restore artifacts and how restoration is verified.

</details>

**Q6.** Your organization is adding a second ML team that wants to use the same tracking server and artifact store. GPU demand is beginning to conflict, and compliance now requires clearer promotion records. Which maturity changes are justified, and which should still be questioned?

<details>
<summary>Answer</summary>

Stronger access control, clearer promotion workflow, backup practice, monitoring, and possibly workload scheduling are justified because multiple teams and compliance pressure increase operational risk. More advanced isolation may also be justified if shared GPU use causes real contention. A full portal or complex chargeback system should still be questioned unless onboarding friction or cost allocation has become a concrete problem.

</details>

**Q7.** A model owner wants to deploy a new artifact because its evaluation metric is higher than the current model. The artifact has a run ID and metrics, but no documented rollback target and no serving contract compatibility check. What should happen before deployment?

<details>
<summary>Answer</summary>

The team should block or delay deployment until rollback and compatibility are verified. A higher metric alone is not enough for platform promotion. The deployment record should identify the current and previous artifact, confirm that the serving request and response contract remains compatible, and provide health and prediction checks that prove the service can be operated after release.

</details>

---

## Hands-On Exercise

**Goal**: Build a minimal private AI platform design for a small team. You will create the structure, documentation, runnable training entry point, simple serving API, and ownership rules that turn informal ML work into a shared operating model.

You can complete this exercise in a local directory. The example uses Python, FastAPI, and shell scripts. If your environment already has a preferred package manager, keep it, but preserve the platform behaviors: one source of truth, one training command, one artifact convention, one serving contract, and explicit ownership.

### Step 1: Create the platform workspace

Create a workspace that makes the lifecycle visible. The directory names should tell a new teammate where to find platform scope, training code, serving code, operational scripts, and artifacts. Do not hide the platform process inside one notebook folder.

```bash
mkdir -p private-ai-platform/{docs,ml/configs,serving,ops,artifacts}
touch private-ai-platform/README.md
touch private-ai-platform/docs/{platform-scope.md,serving-standard.md,ownership.md,access-matrix.md,roadmap.md}
touch private-ai-platform/artifacts/README.md
```

Add a short scope document that separates what the team owns now from what it deliberately defers. This scope document is part of the platform because it prevents accidental expansion.

```bash
cat > private-ai-platform/docs/platform-scope.md <<'EOF'
# Platform Scope

## Self-hosted

- Experiment tracking for shared model runs
- Local artifact directory for the exercise
- Internal FastAPI inference service
- Platform documentation and operating scripts

## External

- Source control provider
- Developer identity provider
- Future object storage service

## Not solved yet

- Multi-cluster scheduling
- Complex tenancy model
- Platform portal
- Automated chargeback
EOF
```

- [ ] `private-ai-platform/` contains `docs/`, `ml/`, `serving/`, `ops/`, and `artifacts/`.
- [ ] `docs/platform-scope.md` states what is self-hosted, external, and intentionally not solved yet.
- [ ] At least three deferred features are named explicitly.

Verification:

```bash
find private-ai-platform -maxdepth 2 -type d | sort
grep -E "Self-hosted|External|Not solved yet" private-ai-platform/docs/platform-scope.md
grep -E "Multi-cluster|tenancy|portal|chargeback" private-ai-platform/docs/platform-scope.md
```

### Step 2: Add a training config

Create a small config file that records the model's input assumptions and metric threshold. Even in a toy exercise, the habit matters: training behavior should come from a reviewed file rather than a hidden notebook cell.

```bash
cat > private-ai-platform/ml/configs/support-triage.yaml <<'EOF'
run_name: support-triage-baseline
dataset_uri: local-demo-data
text_column: text
target_column: label
metric_threshold:
  accuracy: 0.80
artifact_name: support-triage-model
EOF
```

- [ ] The config names the run, dataset, input column, target column, metric threshold, and artifact name.
- [ ] The config can be reviewed without opening the training code.

Verification:

```bash
grep -E "run_name|dataset_uri|metric_threshold|artifact_name" private-ai-platform/ml/configs/support-triage.yaml
```

### Step 3: Implement a repeatable training script

Create a runnable training script. This demo uses only the Python standard library so the exercise does not depend on external packages. The script reads the config, writes a model artifact, records a simple metric, and produces `artifacts/last-run.json`.

```bash
cat > private-ai-platform/ml/train.py <<'EOF'
import argparse
import json
from pathlib import Path


def parse_simple_yaml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--summary-file", required=True)
    args = parser.parse_args()

    config_path = Path(args.config)
    artifact_dir = Path(args.artifact_dir)
    summary_file = Path(args.summary_file)

    config = parse_simple_yaml(config_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_file.parent.mkdir(parents=True, exist_ok=True)

    model_file = artifact_dir / "model.json"
    model = {
        "artifact_name": config["artifact_name"],
        "rule": "classify longer support requests as needs-human-review",
        "model_version": "support-triage-local-1",
    }
    model_file.write_text(json.dumps(model, indent=2) + "\n")

    summary = {
        "run_name": config["run_name"],
        "dataset_uri": config["dataset_uri"],
        "metric": {"accuracy": 0.86},
        "artifact_uri": str(model_file),
        "model_version": model["model_version"],
        "promotion_ready": True,
    }
    summary_file.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
EOF
```

Now create the shared entry point. The point of the wrapper is that teammates should not need to remember every flag or path.

```bash
cat > private-ai-platform/ops/run-train.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 ml/train.py \
  --config ml/configs/support-triage.yaml \
  --artifact-dir artifacts/support-triage \
  --summary-file artifacts/last-run.json
EOF

chmod +x private-ai-platform/ops/run-train.sh
```

- [ ] `ops/run-train.sh` runs training without opening a notebook.
- [ ] The run writes a model artifact under `artifacts/`.
- [ ] The run writes `artifacts/last-run.json` with metric and artifact information.

Verification:

```bash
bash private-ai-platform/ops/run-train.sh
test -f private-ai-platform/artifacts/support-triage/model.json
test -f private-ai-platform/artifacts/last-run.json
cat private-ai-platform/artifacts/last-run.json
```

### Step 4: Implement one internal inference service

Create a minimal FastAPI service with `/health` and `/predict`. This service uses the artifact written by the training step and returns the model version in every prediction response. If FastAPI is not installed in your environment, the code still documents the standard; install dependencies only if your local policy allows it.

```bash
cat > private-ai-platform/serving/app.py <<'EOF'
import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

ROOT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT_DIR / "artifacts" / "support-triage" / "model.json"

app = FastAPI(title="support-triage-service", version="1.0.0")


class PredictRequest(BaseModel):
    text: str


class PredictResponse(BaseModel):
    label: str
    score: float
    model_version: str


def load_model() -> dict[str, str]:
    return json.loads(MODEL_PATH.read_text())


@app.get("/health")
def health() -> dict[str, str]:
    model = load_model()
    return {"status": "ok", "model_version": model["model_version"]}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    model = load_model()
    word_count = len(request.text.split())
    label = "needs-human-review" if word_count >= 8 else "auto-reply-candidate"
    score = min(0.95, 0.55 + word_count / 100)
    return PredictResponse(label=label, score=score, model_version=model["model_version"])
EOF
```

Document the serving standard in a short reference file that every service is expected to follow. This shared contract is what prevents the next model from inventing a different API shape, a different health check, or a different rollback path.

```bash
cat > private-ai-platform/docs/serving-standard.md <<'EOF'
# Serving Standard

## Endpoints

- `GET /health` returns service status and model version.
- `POST /predict` accepts JSON with a `text` field and returns label, score, and model version.

## Versioning Rule

Model artifact changes must update `model_version`. API contract changes require a service version change and client review.

## Logging Rule

Services should log request ID, endpoint, model version, latency, status, and error class. Sensitive input text is not logged by default.

## Rollback Rule

Every deployment record must name the current artifact and previous artifact. Rollback restores the previous artifact and verifies `/health` and `/predict`.
EOF
```

- [ ] The service has a health endpoint and a prediction endpoint.
- [ ] The prediction response includes a model version.
- [ ] `docs/serving-standard.md` documents request shape, response shape, versioning, logging, and rollback.

Verification, if FastAPI and Uvicorn are available:

```bash
cd private-ai-platform
python3 -m uvicorn serving.app:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl -sf http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"text":"customer cannot access the billing dashboard after password reset"}'
```

### Step 5: Define ownership and access rules

Write ownership down while the platform is still small. The goal is not to create bureaucracy. The goal is to make deployment, deletion, secret rotation, and restore decisions clear before an incident.

```bash
cat > private-ai-platform/docs/ownership.md <<'EOF'
# Ownership

## Platform Owner

Owns tracking availability, artifact storage conventions, secret rotation, backup checks, and restore procedure.

## Model Owner

Owns model quality, promotion recommendation, evaluation evidence, serving compatibility, and rollback target selection.

## Team Lead

Approves production promotion, artifact deletion, and changes that expand platform scope.

## Incident Rule

When a model or artifact is accidentally deleted, the platform owner leads restore, the model owner verifies behavior, and the team lead is informed before production traffic is changed.
EOF
```

```bash
cat > private-ai-platform/docs/access-matrix.md <<'EOF'
# Access Matrix

| Action | Developer | Model Owner | Platform Owner | Team Lead |
|---|---|---|---|---|
| read experiment runs | yes | yes | yes | yes |
| write experiment runs | yes | yes | yes | limited |
| promote artifact | no | yes | yes | approve |
| deploy service | no | request | yes | approve |
| rotate secrets | no | no | yes | approve |
| delete shared artifact | no | no | restricted | approve |
| restore artifact | request | verify | yes | informed |
EOF
```

- [ ] `ownership.md` names owners for tracking, storage, serving, promotion, secrets, backup, restore, and rollback.
- [ ] `access-matrix.md` distinguishes read, write, deploy, delete, and restore permissions.
- [ ] The restore path does not depend on one unnamed person.

Verification:

```bash
grep -E "Platform Owner|Model Owner|Team Lead|restore|rollback|secret" private-ai-platform/docs/ownership.md
grep -E "read|write|promote|deploy|delete|restore" private-ai-platform/docs/access-matrix.md
```

### Step 6: Create a phased roadmap

Create a roadmap that protects the team from premature complexity. The roadmap should show what is standardized now, what comes next, and what is deferred until a real trigger appears.

```bash
cat > private-ai-platform/docs/roadmap.md <<'EOF'
# Roadmap

## Now

- Source-controlled training, serving, and platform documentation
- One repeatable training entry point
- One artifact convention
- One serving contract
- Ownership and access documentation

## Next

- Shared experiment tracking service
- Durable object storage with retention
- CI job for training and evaluation
- Basic service monitoring and rollback rehearsal

## Later

- Multi-cluster deployment
- Complex tenancy model
- Platform portal
- Automated chargeback
- Advanced workflow orchestration
EOF
```

- [ ] The roadmap separates immediate standards from later expansion.
- [ ] Deferred items include multi-cluster deployment, tenancy, and a portal.
- [ ] The roadmap gives the team a way to say "not yet" without losing the future option.

Verification:

```bash
grep -E "Now|Next|Later" private-ai-platform/docs/roadmap.md
grep -E "Multi-cluster|tenancy|portal" private-ai-platform/docs/roadmap.md
```

### Exercise Success Criteria

- [ ] The platform workspace has a clear structure and documented scope boundary.
- [ ] The training behavior is controlled by a reviewed config file.
- [ ] A training run can be executed from `ops/run-train.sh` without relying on a notebook session.
- [ ] The run produces a model artifact and `artifacts/last-run.json`.
- [ ] The inference service exposes `/health` and `/predict`.
- [ ] The serving response includes a model version.
- [ ] Ownership, access, rollback, and recovery expectations are documented.
- [ ] The roadmap explicitly defers advanced platform features so the design stays small-team focused.

### Reflection Questions

After completing the exercise, review your design as if you were approving it for a real team. Which part would fail first if a second team started using it? Which part would fail first if a customer-facing application depended on the service? Which deferred feature has the clearest upgrade trigger? Your answers should guide the next iteration more than tool preference does.

---

## Next Module

- [Home AI Operations and Cost Model](../ai-infrastructure/module-1.5-home-ai-operations-cost-model/)
- [ML Monitoring](../module-1.10-ml-monitoring/)
- [Private MLOps Platform](../../on-premises/ai-ml-infrastructure/module-9.4-private-mlops-platform/)

## Sources

- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/) — Relevant to the module's recommendation to make training and evaluation execution repeatable outside individual laptops.
- [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) — Supports the module's emphasis on access control and ownership rules for shared platform components.
- [MLflow](https://github.com/mlflow/mlflow) — Open-source platform for experiment tracking and model registry, the reference implementation behind the module's shared tracking and artifact capabilities.
- [MLflow Tracking Documentation](https://mlflow.org/docs/latest/tracking/) — Concepts and APIs for recording runs, parameters, metrics, and artifacts in a shared team store.
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework used to build the stable internal inference service in the reference architecture.
- [Kubernetes Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/) — Declarative rollouts and rollbacks for the stable internal model-serving pattern.
- [DVC Documentation](https://dvc.org/doc) — Data and model versioning that gives the shared artifact store reproducible lineage.
- [MinIO](https://github.com/minio/minio) — Self-hosted, S3-compatible object storage suitable for a small team's private artifact store.
- [Continuous Delivery for Machine Learning](https://martinfowler.com/articles/cd4ml.html) — Thoughtworks' end-to-end operating model for evolving an ML platform from manual discipline to shared services.
- [The Twelve-Factor App](https://12factor.net/) — Configuration and operations discipline that underpins the module's serving, ownership, and recovery rules.
