---
title: "Data Pipelines"
slug: ai-ml-engineering/mlops/module-1.7-data-pipelines
sidebar:
  order: 608
---
> **AI/ML Engineering Track** | Complexity: `[COMPLEX]` | Time: 5-6

## Hypothetical Scenario: When Unversioned Training Data Derails a Launch

**Hypothetical scenario:** A model team is in the final hours before launch after months of work on a personalized pricing model, with very little margin for last-minute uncertainty about the training data. Offline evaluation looked strong and leadership has already communicated the launch externally. Then someone asks a basic question nobody can answer with confidence: which exact dataset version produced the candidate model about to ship? The engineer who opens the shared folder finds a graveyard of ambiguous filenames rather than a catalog of record:

```
data/
├── train.csv
├── train_v2.csv
├── train_v2_clean.csv
├── train_v3.csv
├── train_v3_FINAL.csv
├── train_v3_FINAL_REAL.csv
├── train_FINAL_USE_THIS.csv
└── train_march_update.csv
```

When the team traces filenames against experiment notes, they discover the launch candidate was trained on a different file than the one used in validation — `train_v3_FINAL_REAL.csv` versus `train_FINAL_USE_THIS.csv` are not the same dataset. The launch slips, engineering time is spent re-running training and audits, and the team implements the data versioning and pipeline controls that should have existed from the beginning.

This pattern is common in teams that version code in Git but treat datasets as disposable files on shared drives. In ML, your model is only as good as your data — and your data is only as trustworthy as your ability to track, version, validate, and orchestrate it through reproducible pipelines. A model trained on corrupted or mismatched data rarely throws errors; it quietly makes bad predictions that erode trust and revenue until someone traces the failure back to the data layer.

---

## What You'll Be Able To Do

After working through the theory, tool walkthroughs, and hands-on checkpoints below, you should be able to explain how each layer of the stack fits together and implement the core workflows yourself:
- Master DVC for dataset and model versioning—a widely adopted approach for tracking datasets like code
- Understand feature stores and implement Feast—the solution to feature engineering chaos
- Implement data validation with Great Expectations—unit tests for your data
- Build reproducible ML data pipelines with versioned data, scheduling, and orchestrated dependencies
- Understand data lineage and governance—tracing data from source to model for debugging and compliance

---

## Why This Module Matters

Machine learning systems fail in production far more often at the data layer than at the model layer. Teams invest months tuning architectures while their training tables live in folders named `final_v2_REAL.csv`, their feature definitions diverge across three services, and their nightly ingestion jobs fail silently because nobody wired dependencies or validation gates. Data pipelines — the scheduled, dependency-aware workflows that ingest, transform, validate, and publish ML-ready datasets — are how you turn ad-hoc scripts into infrastructure you can trust.

Without orchestrated data pipelines, every retrain becomes forensic archaeology: which upstream export ran, which transformation version produced this partition, and whether validation ran before training started. With them, you declare dependencies explicitly, backfill historical partitions safely, and block training when expectations fail. The durable concepts — DAGs, idempotency, ETL versus ELT, lineage — outlast any single orchestrator; the tools (Airflow, Dagster, Prefect, and others) are interchangeable implementations of the same operational spine.

This module teaches that spine alongside the data-management tools that sit inside it: DVC for versioning, Feast for consistent features, Great Expectations for validation, and lineage systems for auditability. Module 1.8 goes deeper on ML workflow orchestration for training and deployment; here you focus on the data moving through those workflows.

---

## Data Pipelines for ML: Orchestration, ETL, and Dependencies

### What Counts as a Data Pipeline?

An ML data pipeline is a repeatable workflow that moves raw inputs through transformation and validation stages until they are safe to consume for training or serving. Unlike a one-off notebook export, a pipeline declares what runs, in what order, on what schedule, and what must succeed before downstream steps proceed. Orchestrators such as [Apache Airflow](https://airflow.apache.org/docs/apache-airflow/stable/), [Dagster](https://docs.dagster.io/), and [Prefect](https://docs.prefect.io/) exist to express that graph — historically as task-based DAGs (Airflow, Prefect) or asset-based graphs where data products are first-class (Dagster).

Think of the pipeline as a factory line for datasets. Ingestion stations pull from APIs, databases, or object storage. Transformation stations clean, join, and engineer features. Quality stations run expectations before anything reaches the training floor. Storage stations write versioned artifacts and register metadata. If any station skips a step or uses a different recipe than yesterday, the finished product — your training table — is not the same product even when the filename unchanged.

### ETL Versus ELT: Where Transformation Runs

**ETL (Extract, Transform, Load)** transforms data before it lands in the warehouse or lake. Extraction pulls from sources into a staging area; transformation applies business rules, aggregations, and feature logic; load writes curated tables downstream jobs consume. ETL keeps heavy computation close to the pipeline engine and produces narrow, ML-ready tables early. It suits teams with strict schema contracts and centralized data engineering ownership.

**ELT (Extract, Load, Transform)** loads raw data first, then transforms inside the warehouse or lakehouse using SQL or Spark. Extraction and load prioritize speed and completeness; transformation happens where storage and compute colocate. ELT suits exploratory feature work and teams that want raw history preserved for reprocessing when definitions change. ML teams often hybridize: ELT for raw retention, ETL-style Python or Spark steps for complex feature engineering that SQL cannot express cleanly.

The choice affects pipeline design. ETL pipelines fail fast when upstream schemas drift because transforms run before load commits. ELT pipelines defer failure to transform time but preserve raw inputs for backfills when you fix a bug in feature logic. Neither is universally correct; the tradeoff is where you pay transformation cost and how easily you can recompute history.

### Scheduling, Sensors, and Data Dependencies

Production data rarely arrives at a fixed clock. A nightly sales export might land at 02:10 some days and 03:40 others. Hard-coding `sleep(3600)` between jobs creates flaky pipelines. Orchestrators express **dependencies** explicitly: task B runs only after task A succeeds, or after a **sensor** detects that today's partition exists in object storage.

Scheduling defines the cadence (`@daily`, cron expressions, or event triggers). **Backfills** replay historical intervals — essential when you fix a transformation bug and must rebuild three months of feature tables without manual one-off scripts. Safe backfills require **idempotent** tasks: re-running the same date partition overwrites or upserts deterministically instead of duplicating rows.

Data dependencies also cross team boundaries. Your training pipeline may depend on a finance team's ledger export and a product team's event stream. Document those edges in lineage metadata and alert upstream owners when your SLA misses — otherwise ML becomes the last team to discover a silent upstream failure.

### Backfills: Replaying History Safely

**Hypothetical scenario:** A data engineer discovers that a window function in the daily feature job used the wrong partition column for three weeks. Training and serving both consumed the bad feature, but offline metrics looked stable because the bug was consistent — not random noise. Fixing the SQL is easy; rebuilding trust requires reprocessing every affected date partition and proving downstream models retrained on the corrected tables. Stakeholders will ask whether predictions issued during the bad window must be re-scored; lineage and partition metadata are how you scope that answer without reprocessing the entire history of the business.

Backfills are how you replay orchestrated pipelines across historical intervals. The orchestrator schedules the same DAG once per date (or hour) in a range, writing into deterministic partition paths such as `s3://features/ds=2026-05-01/`. Idempotency is non-negotiable: each replay must replace that partition entirely or upsert on a primary key so retries and overlaps do not duplicate rows. Coordinate with consumers — freeze training jobs, bump feature-store materialization versions, or mark partitions as `staging` until validation passes — so models do not blend old and new statistics in the same batch.

Operational teams often maintain a backfill playbook: identify blast radius with lineage, run Great Expectations on a canary partition, replay in ascending date order to simplify dependency checks, and attach the rebuilt dataset hash to experiment metadata before promoting models. That playbook turns a scary "recompute three weeks" request into a routine pipeline operation rather than a weekend of manual CSV juggling. Document the playbook beside the DAG so on-call engineers inherit the sequence instead of reinventing it during an incident. Treat backfill drills as routine capacity tests, not emergency-only procedures, so the team practices partition replays before production pressure hits.

### Feature Pipelines Inside the Data Layer

Feature pipelines are specialized data pipelines that compute, validate, and publish features for both offline training and online serving. They sit between raw ingestion and model training, often feeding a feature store. The failure mode you are preventing is training-serving skew: training reads batch-computed features while serving recomputes with slightly different code or timestamps.

A mature feature pipeline version-controls transformation code (Git), version-controls outputs (DVC or warehouse time travel), validates with Great Expectations checkpoints, and registers definitions in a feature store so serving pulls the same logic. Orchestration ties the stages together so materialization runs after upstream facts land and before training DAGs start.

> **Landscape snapshot — as of 2026-06. Verify against vendor docs before relying on specifics.**
>
> | Capability | Apache Airflow | Dagster | Prefect |
> |------------|----------------|---------|---------|
> | Primary abstraction | Task-based DAG | Software-defined assets | Python `@flow` / `@task` |
> | Typical metadata store | Airflow metastore (often PostgreSQL) | Dagster instance storage | Prefect server / cloud API |
> | Common ML use | Batch ingestion, sensors, cron retraining triggers | Data-aware pipelines with typed assets | Dynamic Python-native flows with hybrid execution |
> | Docs entry point | [airflow.apache.org](https://airflow.apache.org/docs/apache-airflow/stable/) | [docs.dagster.io](https://docs.dagster.io/) | [docs.prefect.io](https://docs.prefect.io/) |

---

## Theory

### The Data Management Problem

Data is the foundation of ML, but it's often treated as an afterthought. We obsess over model architectures while our data sits in chaotic folder structures with names like "final_v2_REAL.csv". This is like building a house on sand—no matter how beautiful the structure, it will collapse.

The data management problem has three layers, each more insidious than the last:

**Layer 1: Version Chaos.** Without versioning, you can't answer basic questions: "What data trained model v2.3?" "Has the training data changed since last week?" "Can we reproduce last month's results?" In software engineering, these questions are trivially answered with Git. In ML, they often produce shrugs and guesses.

**Layer 2: Feature Inconsistency.** Different teams compute the same features differently. Your data science team calculates "user_age" one way in Python. Your backend team calculates it another way in SQL. Your mobile team calculates it a third way in Swift. Same concept, three implementations, three bugs waiting to happen.

**Layer 3: Silent Quality Degradation.** **Hypothetical scenario:** Data drifts silently. Suppose your training snapshot had roughly 2% missing values, but new production batches arrive with roughly 15% missing — your model doesn't fail; it just makes increasingly worse predictions. By the time someone notices, the damage is done.

Think of data versioning like a time machine for your datasets. Git lets you travel back in time through your code history. DVC lets you do the same with your data. You can answer questions like "What dataset did model v2.3 use?" and "What changed between training runs?" Instead of guessing, you can know.

```
THE DATA CHAOS PROBLEM
======================

Without Versioning:
───────────────────
"Which version of the dataset was model v2.3 trained on?"
"Did someone update the preprocessing script?"
"Why do we get different results on the same code?"

    data/
    ├── train.csv
    ├── train_v2.csv
    ├── train_final.csv
    ├── train_FINAL_real.csv
    └── train_USE_THIS_ONE.csv

With DVC:
─────────
    data/
    └── train.csv.dvc  ← Tracked in Git, points to versioned data

    git log:
    - commit abc123: "Add train data v3.2 (50K samples)"
    - commit def456: "Update train data v3.1 (45K samples)"
    - commit ghi789: "Initial train data v3.0 (40K samples)"
```

### Did You Know? Why Data Quality Decides Production Success

Data quality and data management problems are a common reason ML systems fail to deliver in production, which is one reason data-centric approaches gained traction.

The Data-Centric AI movement represents a philosophical shift in how we think about ML. For years, the ML community focused on model architecture—new layers, new attention mechanisms, new training techniques. Kaggle competitions rewarded clever model ensembles. Research papers emphasized architectural innovations.


---

## 1. DVC: Data Version Control

### What is DVC?

[DVC (Data Version Control) is Git for data and ML models](https://dvc.org/doc). Think of it like a librarian for your datasets—it keeps track of every version, knows where everything is stored, and can retrieve any historical version on demand.

To understand why DVC matters, imagine trying to manage a library without a catalog system. Every book is somewhere on the shelves, but nobody knows where. Readers wander the stacks hoping to stumble across what they need. When someone asks "do we have the 1985 edition of this textbook?" the librarian can only shrug.

That's what data management looks like without DVC. Datasets exist somewhere on S3 or Google Cloud Storage. Someone downloaded a version last month. Someone else modified it. The original might still exist. Or maybe it was overwritten. Nobody knows for certain.

DVC creates that missing catalog. Every dataset gets a unique identifier. Every version is tracked. Every change is logged. When someone asks "what data trained model v2.3?" the answer is one command away.

The core insight is elegant: Git is terrible at tracking large files, but great at tracking small text files. So [DVC creates small "pointer" files (`.dvc` files) that Git tracks, while the actual data lives in external storage (S3, GCS, Azure, or local disk)](https://dvc.org/doc/user-guide/data-management/remote-storage). It's like keeping a library card catalog in Git while the actual books sit on warehouse shelves.

```
DVC ARCHITECTURE
================

┌─────────────────────────────────────────────────────────────────────┐
│                           DVC                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │   Data Files    │  │    Pipelines    │  │    Metrics      │    │
│  │                 │  │                 │  │                 │    │
│  │ • .dvc files    │  │ • dvc.yaml      │  │ • dvc metrics   │    │
│  │ • Remote storage│  │ • Reproducible  │  │ • Experiments   │    │
│  │ • Cache         │  │ • Dependencies  │  │ • Comparisons   │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Remote Storage                            │   │
│  │  S3 | GCS | Azure Blob | SSH | Local | HTTP | HDFS          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Basic DVC Workflow

The DVC workflow mirrors Git closely enough that much of it will feel familiar if you already know Git. This wasn't accidental—Dmitry Petrov deliberately designed DVC to feel familiar. When you've been using Git for a decade, the last thing you want is to learn a completely new paradigm for data.

The mental model is simple: DVC handles big files the same way Git handles small files. `git add` becomes `dvc add`. `git push` becomes `dvc push`. `git pull` becomes `dvc pull`. The commands feel natural because they extend a workflow you already know — just applied to datasets and model artifacts that Git was never designed to store inline.

The key commands map directly to that mental model:

```bash
# Initialize DVC in a Git repo
cd my-ml-project
git init
dvc init

# Add data to DVC tracking (like git add, but for big files)
dvc add data/train.csv
# Creates: data/train.csv.dvc (small text file, tracked by Git)
# Actual data stored in .dvc/cache/

# Commit the .dvc file (the pointer, not the data)
git add data/train.csv.dvc data/.gitignore
git commit -m "Add training data v1.0"

# Push data to remote storage (like git push, but for data)
dvc remote add -d myremote s3://my-bucket/dvc-cache
dvc push

# Later: pull data on another machine (like git pull)
git clone <repo>
dvc pull
```

The magic happens in that `.dvc` file—a small YAML file that Git happily tracks:

```yaml
# data/train.csv.dvc
outs:
  - md5: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
    size: 1048576
    path: train.csv
```

This file is like a receipt. It says "the file `train.csv` has this specific hash and this size." When you `dvc pull`, DVC uses this receipt to fetch the exact right version from storage, which is why reproducing a teammate's environment reduces to matching Git commits and running one pull command.

### DVC Pipelines: Reproducibility Built In

DVC doesn't just version data—it versions entire ML pipelines. You define your pipeline in `dvc.yaml`, and DVC tracks dependencies, parameters, and outputs. It's like a Makefile for ML that actually understands data dependencies.

This is where DVC becomes truly powerful. Data versioning alone is useful, but pipeline versioning is transformative. Consider the typical ML workflow: you preprocess data, train a model, evaluate it, and maybe do some post-processing. Each step depends on the outputs of previous steps. Change your preprocessing, and everything downstream needs to re-run. Change a hyperparameter, and only training and evaluation need to re-run.

Without DVC, you track these dependencies manually—or more likely, you don't track them at all. You run the entire pipeline every time, wasting hours on unchanged steps. Or you run only part of the pipeline and wonder why your results don't match last week's.

DVC pipelines make dependencies explicit. You declare what each step needs and what it produces. DVC builds a dependency graph and intelligently re-runs only what changed. It's like having a smart assistant who knows exactly which steps need to run based on what you modified.

```yaml
# dvc.yaml - Your ML pipeline as code
stages:
  preprocess:
    cmd: python src/preprocess.py
    deps:
      - src/preprocess.py
      - data/raw/
    params:
      - preprocess.split_ratio
    outs:
      - data/processed/

  train:
    cmd: python src/train.py
    deps:
      - src/train.py
      - data/processed/
    params:
      - train.learning_rate
      - train.epochs
    outs:
      - models/model.pkl
    metrics:
      - metrics.json:
          cache: false

  evaluate:
    cmd: python src/evaluate.py
    deps:
      - src/evaluate.py
      - models/model.pkl
      - data/processed/test.csv
    metrics:
      - evaluation.json:
          cache: false
```

[DVC automatically builds a dependency graph and only re-runs stages when their inputs change](https://dvc.org/doc/user-guide/pipelines). Changed the preprocessing script? Only preprocessing and downstream stages re-run. Changed a hyperparameter? Only training and evaluation re-run. It's incremental builds for ML.

```
DVC PIPELINE DAG
================

     ┌────────────────┐
     │   data/raw/    │
     └───────┬────────┘
             │
             ▼
     ┌────────────────┐
     │  preprocess    │
     │                │
     │  deps:         │
     │  - raw data    │
     │  - script      │
     └───────┬────────┘
             │
             ▼
     ┌────────────────┐
     │    train       │
     │                │
     │  deps:         │
     │  - processed   │
     │  - params      │
     └───────┬────────┘
             │
             ▼
     ┌────────────────┐
     │   evaluate     │
     │                │
     │  outputs:      │
     │  - metrics     │
     └────────────────┘
```

### Did You Know? The Origin of DVC

DVC was created by Dmitry Petrov in 2017 and is maintained by Iterative.ai with a large open-source community. The name plays on CSV even though DVC handles any file type — a reminder that the project began with everyday tabular datasets before expanding to pipelines, metrics, and model artifacts.

The success of DVC highlights an important lesson: ML tools succeed when they meet practitioners where they are. DVC did not ask data scientists to learn a completely new paradigm. It built on Git, which most developers already know. The learning curve is gentle because the concepts are familiar — just applied to a new domain.

This tradeoff explains why many teams adopt DVC before heavier platforms such as Pachyderm, which targets Kubernetes-native data versioning and typically demands more infrastructure upfront. DVC is a scalpel where others offered chainsaws. You can add it to an existing project in five minutes and see immediate benefits. That low-friction onboarding drove community adoption, which in turn expanded the feature set.

### DVC Experiments

Experiment tracking is where DVC overlaps with dedicated tools like MLflow, but stays tightly coupled to your data and pipeline hashes. You can run multiple training configurations, compare metrics side by side, and promote the winning run to a branch without maintaining a separate spreadsheet of hyperparameters:

```bash
# Run experiment with parameter changes
dvc exp run -S train.learning_rate=0.001 -S train.epochs=20

# List experiments
dvc exp show

# Compare experiments
dvc exp diff exp-abc123 exp-def456

# Apply best experiment to your branch
dvc exp apply exp-abc123
git commit -m "Apply best experiment"
```

This is like git branches for hyperparameters. You can try dozens of configurations, compare their metrics, and promote the best one—all without manually tracking spreadsheets.

---

## 2. Feature Stores: Solving the Feature Engineering Problem

### The Feature Engineering Chaos

Feature engineering is where data science meets software engineering—and usually crashes. The problem isn't computing features; it's managing them across teams, environments, and time.

**Hypothetical scenario:** Your recommendation team builds a user embeddings feature. It works well in offline tests. Your fraud team hears about it and wants the same signal, but they cannot import the code directly — different language, database, and deployment stack — so they reimplement it. Three months later, a third team reimplements it again. You now have three implementations of the same conceptual feature: Team A computes on-demand in Python from birthdate; Team B computes nightly in SQL from signup year minus birth year; Team C serves cached age buckets from Redis in Java.

Same concept. Three implementations. Three sources of bugs. When Team A discovers an edge case and fixes it, Teams B and C continue using buggy versions. When the underlying data schema changes, each team scrambles independently to fix their code.


Think of it like a restaurant kitchen without recipes. Every chef makes their own version of "garlic sauce"—some add cream, some don't, some roast the garlic first. Customers get inconsistent dishes, and when a chef leaves, their recipes leave with them.

```
FEATURE ENGINEERING CHAOS
=========================

Without Feature Store:
──────────────────────
Team A: "We compute user_age from birthdate"
Team B: "We compute age from signup_year - birth_year"
Team C: "We use age_bucket categorical feature"

Result: Same feature, 3 different implementations!

Training vs Serving Skew:
────────────────────────
Training: Features computed in batch (Spark, 1 hour lag)
Serving:  Features computed in real-time (different code)
Result:   Model works in training, fails in production!

With Feature Store:
──────────────────
┌─────────────────────────────────────────────────────────────────┐
│                     FEATURE STORE                               │
├─────────────────────────────────────────────────────────────────┤
│  Single source of truth for all features                        │
│  Same features for training AND serving                         │
│  Versioning, lineage, discovery                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Training-Serving Skew: The Silent Killer

The most insidious problem in production ML is **training-serving skew**. Your model trains on features computed one way (say, a Spark job running overnight) but serves predictions using features computed another way (say, real-time Python code). Even tiny differences can cause dramatic accuracy drops.

It's like training a translator on formal English, then deploying them in a room full of teenagers using slang. The "language" is different enough that the skills don't transfer.

Here's a concrete example of how training-serving skew appears in practice. Your training pipeline computes `days_since_last_purchase` in a Spark job using a fixed snapshot date baked into the historical extract, while your serving pipeline computes the same feature name in Python with `datetime.now()` at request time. If training data was materialized two weeks ago, every live prediction carries a systematic offset the model never saw during training — the feature name matches, but the semantics drift.

This bug doesn't crash your system. It doesn't throw exceptions. It just makes your model subtly wrong—and wrong in a way that's almost impossible to debug without understanding the training-serving gap.

Feature stores solve this by ensuring the exact same code computes features for training and serving. One definition, one implementation, consistent results.

### Feast: Open-Source Feature Store

Feast is a popular open-source feature store. Think of it as a database specifically designed for ML features—with time-travel capabilities, online/offline stores, and first-class support for ML workflows.

The name "Feast" is a playful acronym for "Feature Store." It was created at Gojek (the Indonesian super-app) by Willem Pienaar, who previously worked on Uber's Michelangelo platform—arguably the first production feature store at scale. When Pienaar joined Gojek, he brought those hard-won lessons and built Feast from scratch as an open-source project.

What makes Feast powerful is its dual-store architecture. Most databases optimize for one thing: either fast writes and complex queries (OLAP) or fast reads with simple lookups (OLTP). ML needs both. You need complex queries for training (joining features with historical labels) and fast lookups for serving (get user X's features quickly). [Feast provides both through its offline and online stores](https://github.com/feast-dev/feast).

```
FEAST ARCHITECTURE
==================

┌─────────────────────────────────────────────────────────────────────┐
│                           FEAST                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ Feature Repo    │  │  Offline Store  │  │  Online Store   │    │
│  │                 │  │                 │  │                 │    │
│  │ • Definitions   │  │ • Historical    │  │ • Low latency   │    │
│  │ • Transformations│ │ • Batch queries │  │ • Real-time     │    │
│  │ • Metadata      │  │ • Training data │  │ • Serving       │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                              │                     │               │
│                              ▼                     ▼               │
│                       ┌───────────┐         ┌───────────┐         │
│                       │ BigQuery  │         │   Redis   │         │
│                       │ Snowflake │         │ DynamoDB  │         │
│                       │ Redshift  │         │ Postgres  │         │
│                       └───────────┘         └───────────┘         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The architecture deliberately separates concerns so each store can optimize for its access pattern without forcing one database to do everything poorly:

- **Offline Store**: For historical data and training — a warehouse or lakehouse optimized for scans and joins.
- **Online Store**: For low-latency serving — often Redis, DynamoDB, or Postgres tuned for key lookups.

Let's walk through a complete feature definition example that shows how entities, sources, and TTL interact. Feast uses Python for definitions — the lingua franca of most data science teams — so feature views live in version-controlled code beside training scripts rather than in a proprietary UI-only format:

### Feast Feature Definitions

```python
# feature_repo/features.py
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64, String

# Define entity (the thing we're making predictions about)
# Like a primary key in a database
user = Entity(name="user", join_keys=["user_id"])

# Define data source (where features come from)
user_features_source = FileSource(
    path="data/user_features.parquet",
    event_timestamp_column="event_timestamp",
    created_timestamp_column="created_timestamp"
)

# Define feature view (collection of related features)
# Like a table in a database
user_features = FeatureView(
    name="user_features",
    entities=[user],
    ttl=timedelta(days=365),  # How long features are valid
    schema=[
        Field(name="age", dtype=Int64),
        Field(name="total_purchases", dtype=Int64),
        Field(name="avg_order_value", dtype=Float32),
        Field(name="days_since_last_purchase", dtype=Int64),
        Field(name="favorite_category", dtype=String),
    ],
    online=True,  # Available for real-time serving
    source=user_features_source,
)
```

### Using Feast in Practice

With features defined, you can retrieve them for training and serving. This is where Feast really shines: the same API works for both historical data (training) and real-time data (serving), ensuring consistency.

The key concept is "point-in-time correct" feature retrieval. When training a model, you don't want to use features from the future—that would be data leakage. If you're predicting whether a user churned on January 15th, you should only use features available before January 15th. Feast handles this automatically through its `get_historical_features` API.

```python
from feast import FeatureStore
import pandas as pd

# Initialize feature store
store = FeatureStore(repo_path="feature_repo/")

# Get training data (historical features)
# "Point-in-time correct" - features as they existed at each timestamp
entity_df = pd.DataFrame({
    "user_id": [1, 2, 3, 4, 5],
    "event_timestamp": pd.to_datetime(["2024-01-01"] * 5)
})

training_df = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "user_features:age",
        "user_features:total_purchases",
        "user_features:avg_order_value",
    ]
).to_df()

# Get online features (real-time serving)
# Low-latency lookup for production inference
online_features = store.get_online_features(
    features=[
        "user_features:age",
        "user_features:total_purchases",
        "user_features:avg_order_value",
    ],
    entity_rows=[{"user_id": 123}]
).to_dict()
```

### Did You Know? The Origin of Feature Stores

Feature stores emerged from Uber's Michelangelo platform in 2017, where feature inconsistency and training-serving skew showed up repeatedly at scale. Willem Pienaar, who worked on Michelangelo, later created Feast at Gojek and contributed it to the Linux Foundation AI & Data. Hyperscale vendors also offer managed feature-store products (for example [Amazon SageMaker Feature Store](https://docs.aws.amazon.com/sagemaker/latest/dg/feature-store.html), [Vertex AI Feature Store](https://cloud.google.com/vertex-ai/docs/featurestore), and [Azure Machine Learning managed features](https://learn.microsoft.com/en-us/azure/machine-learning/concept-asset-management)) alongside open-source options such as Feast, which supports multiple offline and online backends when you need hybrid deployment patterns.

---

## 3. Data Validation with Great Expectations

### Why Data Validation Belongs in the Pipeline

Data validation is like quality control in manufacturing. You wouldn't ship products without inspection, so why train models on uninspected data?

The problem is that data fails silently. Your pipeline runs successfully, your model trains successfully, your deployment succeeds—and then your model makes terrible predictions because the input data was garbage.

**Hypothetical scenario:** Your e-commerce model predicts customer churn. It's trained on customer data: age, purchase history, days since last login, and so on. One day, your upstream data team changes the age calculation. Instead of computing age from birthdate, they now use a self-reported age field. That field might have:
- Missing values for a sizable share of users who skipped the optional field
- Outliers like "999" (from users trying to skip the field)
- String values like "twenty-five" (from users who didn't follow instructions)

Your pipeline doesn't break. It happily converts "999" to an integer and treats "twenty-five" as missing. Your model trains on this garbage and starts making garbage predictions. Customer support tickets spike. Revenue drops. And you spend a week debugging before discovering the upstream change.

Data validation prevents this. You define what "good data" looks like upfront. Before training, you check that the data meets those expectations. If it doesn't, you fail fast—before corruption spreads downstream.

```
DATA QUALITY ISSUES
===================

Common Problems (illustrative examples):
──────────────────────────────────────
• Missing values increased sharply (for example, from a low single-digit rate to a much higher one)
• Categorical column has new unexpected values
• Numerical column has outliers (negative ages)
• Data distribution shifted (concept drift)
• Schema changed (new columns, renamed fields)

Without Validation:
───────────────────
Data pipeline runs successfully...
Model trains successfully...
Model deployed successfully...
 Model makes terrible predictions!
"Why is the model predicting -$500 orders?"

With Great Expectations:
───────────────────────
 Data validated before training
 Expectations documented
 Failed validations alert immediately
 Data quality is part of CI/CD
```

[Think of Great Expectations like unit tests for your data](https://github.com/great-expectations/great_expectations). You define what "good data" looks like (your expectations), and the system validates every dataset against those expectations.

### Great Expectations Architecture

```
GREAT EXPECTATIONS ARCHITECTURE
===============================

┌─────────────────────────────────────────────────────────────────────┐
│                    GREAT EXPECTATIONS                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │  Expectations   │  │   Datasources   │  │   Checkpoints   │    │
│  │                 │  │                 │  │                 │    │
│  │ • Rules         │  │ • Pandas        │  │ • Validation    │    │
│  │ • Tests         │  │ • Spark         │  │   runs          │    │
│  │ • Documentation │  │ • SQL           │  │ • Actions       │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Data Docs                                 │   │
│  │  Auto-generated HTML documentation of expectations          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Common Expectations

Great Expectations provides many built-in expectations — pre-built validation rules you can apply without writing custom assertion code for every column. Instead of hand-rolling Python checks for "does this column exist?" you call `expect_column_to_exist("user_id")`; instead of bespoke range logic you call `expect_column_values_to_be_between("age", 0, 120)`. The API reads like documentation of your data contract, which makes suites reviewable by stakeholders who do not read pipeline code.

Here are the essential expectations every data scientist should know when bootstrapping a training-table suite:

```python
import great_expectations as gx
import great_expectations.expectations as gxe

context = gx.get_context()

# GX 1.x: register a batch definition, then attach expectations to a suite
batch_definition = (
    context.data_sources.add_pandas(name="my_datasource")
    .add_dataframe_asset(name="user_data")
    .add_batch_definition_whole_dataframe(name="user_data_batch")
)

suite = context.suites.add(gx.ExpectationSuite(name="user_data_suite"))

# Column existence — does the data have the columns we expect?
suite.add_expectation(gxe.ExpectColumnToExist(column="user_id"))
suite.add_expectation(gxe.ExpectColumnToExist(column="age"))
suite.add_expectation(gxe.ExpectColumnToExist(column="email"))

# Data types — are values the right type?
suite.add_expectation(gxe.ExpectColumnValuesToBeOfType(column="user_id", type_="int64"))
suite.add_expectation(gxe.ExpectColumnValuesToBeOfType(column="age", type_="int64"))
suite.add_expectation(gxe.ExpectColumnValuesToBeOfType(column="email", type_="str"))

# Null checks — are required fields populated?
suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="user_id"))
suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="email"))

# Value ranges — are values within reasonable bounds?
suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(column="age", min_value=0, max_value=120))
suite.add_expectation(gxe.ExpectColumnValuesToBeBetween(column="purchase_amount", min_value=0))

# Uniqueness — are IDs actually unique?
suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="user_id"))
suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="email"))

# Patterns — do strings match expected formats?
suite.add_expectation(
    gxe.ExpectColumnValuesToMatchRegex(
        column="email",
        regex=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )
)

# Categorical values — are categories from expected set?
suite.add_expectation(
    gxe.ExpectColumnValuesToBeInSet(column="country", value_set=["US", "UK", "CA", "DE", "FR"])
)

# Distribution checks — has the data distribution shifted?
suite.add_expectation(gxe.ExpectColumnMeanToBeBetween(column="age", min_value=25, max_value=45))
suite.add_expectation(
    gxe.ExpectColumnStdevToBeBetween(column="purchase_amount", min_value=10, max_value=100)
)

# Row count — do we have expected data volume?
suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=1000, max_value=1000000))

# Column count — has the schema changed?
suite.add_expectation(gxe.ExpectTableColumnCountToEqual(value=15))
```

### Automated Validation in Pipelines

The real power of Great Expectations emerges when you embed checkpoints in orchestrated pipelines rather than running validation manually before each train. Configure a named checkpoint once, then invoke it after ingestion, after transformation, and immediately before model training so bad batches fail fast:

Here is a minimal pattern for wiring that gate:

```python
from great_expectations import Checkpoint, ValidationDefinition

# GX 1.x: link batch definition + suite, then group in a checkpoint
validation_definition = context.validation_definitions.add(
    ValidationDefinition(
        name="user_data_validation",
        data=batch_definition,
        suite=suite,
    )
)

checkpoint = context.checkpoints.add(
    Checkpoint(
        name="user_data_checkpoint",
        validation_definitions=[validation_definition],
    )
)

# Run checkpoint against the ingestion DataFrame (in-memory batches pass data at run time)
result = checkpoint.run(batch_parameters={"dataframe": df})

# Check if validation passed
if not result.success:
    print("Data validation failed!")
    for validation_result in result.results:
        # validation_result is an ExpectationSuiteValidationResult
        for exp_result in validation_result.results:
            if not exp_result.success:
                print(f"  - {exp_result.expectation_config.type}")
    raise ValueError("Cannot proceed with invalid data")
else:
    print("Data validation passed!")
```

### Did You Know? The Great Expectations Origin


The project has a large open-source community and is widely used for data validation in ML pipelines — see the [Great Expectations documentation](https://docs.greatexpectations.io/docs/) for current integration patterns.

---

## 4. Data Lineage & Governance

### What is Data Lineage?

Data lineage tracks where data comes from and where it goes—like a family tree for your datasets. When something goes wrong, lineage lets you trace the problem back to its source.

Think of it like supply chain tracking. When a product is recalled, manufacturers can trace every component back to its source. Data lineage provides the same capability for ML: when a model fails, you can trace exactly which data, transformations, and code were involved.

**Hypothetical scenario:** Your fraud detection model suddenly starts flagging noticeably more legitimate transactions as fraudulent. Users are angry. Revenue is dropping. You need to figure out what changed.

Without lineage, you're blind. Did the model change? Did the features change? Did the training data change? Did some upstream ETL job modify the data schema? You have no way to know without manually checking dozens of systems.

With lineage, you can trace the problem systematically. You look at the model's lineage and see it was retrained yesterday. The lineage shows it used features from the `fraud_features_v3` table. You trace `fraud_features_v3` and find it depends on a transformation that was updated two days ago. You examine that transformation and find a bug—someone changed a timezone calculation that shifted all timestamps by 8 hours. Bug found in minutes, not days.

Lineage isn't just about debugging — it's about confidence. When a regulator asks "what data was used to make this decision about this customer?" you can answer precisely. When GDPR requires you to trace a user's data through your system, you have a map. When an audit asks about model decisions, you have receipts.

In practice, lineage collectors hook into orchestrators and transformation frameworks to emit OpenLineage events: which job ran, which input datasets it read, which output datasets it wrote, and which Git commit or container image defined the logic. Catalogs such as DataHub ingest those events into a searchable graph. The ML-specific win is connecting that graph to experiment tracking — so model `v2.3.1` links not only to metrics but to exact feature table snapshots and validation results.

```
DATA LINEAGE
============

Lineage tracks where data comes from and where it goes:

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Raw Data   │────►│ Transformed │────►│   Model     │
│  (S3)       │     │   (Spark)   │     │  Features   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Training   │────►│   Model     │
                    │   Data      │     │  v2.3.1     │
                    └─────────────┘     └─────────────┘

Questions Lineage Answers:
─────────────────────────
• What data was used to train model v2.3.1?
• Which models will be affected if table X changes?
• Who created this feature and when?
• What transformations were applied to this data?
```

### Data Governance Best Practices

Governance is the set of policies and practices that ensure data is managed responsibly — who may read it, how changes are audited, and how incidents escalate. In traditional software, governance is often treated as bureaucracy; in ML it is how you prevent invisible degradation. Effective data governance answers six recurring questions that auditors, regulators, and on-call engineers all ask eventually:

**1. Where did this data come from?** (Provenance)
Every dataset should have a birth certificate. Where was it collected? Who processed it? What transformations were applied? This matters when you discover a bug—you need to trace it back to the source.

**2. Who is allowed to access this data?** (Access Control)
Not all data should be available to all teams. PII requires special handling. Financial data has compliance requirements. Healthcare data has HIPAA restrictions. Governance defines who can see what.

**3. How is this data being used?** (Usage Tracking)
When many downstream models and dashboards depend on a particular table, even a small schema change can break consumers you did not know existed. Usage tracking and lineage metadata reveal those dependencies before you modify or deprecate a dataset.

**4. How long should we keep this data?** (Retention)
Data storage isn't free. More importantly, old data creates liability. GDPR's "right to be forgotten" means you must be able to delete user data on request. Retention policies define when data should be archived or deleted.

**5. How do we handle data quality issues?** (Incident Response)
When someone discovers bad data, what happens? Who gets notified? How quickly must it be fixed? Governance defines the playbook for data incidents.

**6. How do we prove compliance?** (Audit Trail)
Regulators and auditors ask hard questions. "Show me the data that trained this model that denied this customer a loan." Without governance, you can't answer. With governance, it's a query.

```
DATA GOVERNANCE CHECKLIST
=========================

 Version Control
   • All data versioned (DVC)
   • All code versioned (Git)
   • All configs versioned

 Data Quality
   • Expectations defined (Great Expectations)
   • Automated validation in pipelines
   • Alerting on failures

 Documentation
   • Data dictionaries
   • Feature definitions
   • Schema documentation

 Access Control
   • Role-based access
   • Audit logging
   • PII handling

 Lineage
   • End-to-end tracking
   • Impact analysis
   • Reproducibility
```

---

## 5. Tool Comparison: Building Your Data Management Stack

### The MLOps Tool Explosion

If you've spent any time researching data management tools, you've likely been overwhelmed by choices. DVC, Feast, Great Expectations, MLflow, Weights & Biases, Kubeflow, Pachyderm, Delta Lake, LakeFS, dbt, Airflow, Prefect, Dagster... the list goes on.

This explosion of tools reflects the maturity of ML as a discipline. When ML was new, everyone built custom solutions. Now that patterns have emerged, tools have crystallized around common needs. But the sheer number of tools creates its own problem: analysis paralysis.

Here's the key insight: **you don't need all these tools, and you definitely don't need them all at once.** Start with the basics, add complexity when pain emerges, and always prioritize solving real problems over having a "complete" stack.

### When to Use What

Different tools solve different problems along the data lifecycle, and the decision matrix below is a durable map — not a shopping list. Use it to match pain points to capabilities before adopting another component you must operate:

```
TOOL SELECTION MATRIX
=====================

┌────────────────────┬─────────────────────────────────────────────────┐
│     Problem        │              Solution                           │
├────────────────────┼─────────────────────────────────────────────────┤
│ Version large      │ DVC                                             │
│ datasets           │ • Git-like workflow for data                    │
│                    │ • Remote storage integration                    │
├────────────────────┼─────────────────────────────────────────────────┤
│ Share features     │ Feast / Feature Store                           │
│ across teams       │ • Centralized definitions                       │
│                    │ • Same features train & serve                   │
├────────────────────┼─────────────────────────────────────────────────┤
│ Validate data      │ Great Expectations                              │
│ quality            │ • Schema validation                             │
│                    │ • Distribution checks                           │
├────────────────────┼─────────────────────────────────────────────────┤
│ Track data         │ OpenLineage / DataHub                           │
│ lineage            │ • End-to-end tracking                           │
│                    │ • Impact analysis                               │
├────────────────────┼─────────────────────────────────────────────────┤
│ All-in-one         │ DVC + Great Expectations + Feast                │
│ data platform      │ • Full data lifecycle                           │
│                    │ • Can be overwhelming for small teams           │
└────────────────────┴─────────────────────────────────────────────────┘
```

### Complexity vs Value

Start simple and add complexity when a specific failure mode appears — the complexity/value curve is not linear, and most incidents trace to missing basics rather than missing exotic tooling:

```
TOOL COMPLEXITY VS VALUE
========================

High │                              ┌─────────────┐
     │                     ┌────────│ Full Data   │
     │              ┌──────│        │ Platform    │
     │       ┌──────│Feast │        └─────────────┘
V    │       │      │      │
A    │       │      └──────┘
L    │       │ Great
U    │       │ Expectations
E    │       └──────┘
     │ ┌──────┐
     │ │ DVC  │
     │ └──────┘
     │
Low  └─────────────────────────────────────────────────►
                     COMPLEXITY
```

**Recommendation**: Start with DVC for data versioning. Add Great Expectations when data quality issues hurt. Add Feast when multiple teams share features or training-serving skew becomes a problem.

### The 80/20 Rule of Data Management

Most teams early in their ML journey get disproportionate value from a small set of practices before they need a full enterprise platform. **Start with DVC and Git** so every dataset and model artifact has a content hash you can tie to training runs — that alone eliminates a large class of "which CSV was it?" incidents, lets you share data through remotes instead of USB drives, and makes rollbacks a checkout rather than a panic. **Add Great Expectations** once data quality issues have cost you real time: unexpected nulls after an upstream schema change, silent drift in categorical distributions, or days lost debugging a model that trained successfully on garbage rows. **Add Feast** when feature consistency becomes organizational: two teams compute the same feature differently, training-serving skew shows up in production metrics, or inference requires sub-second feature lookups you cannot recompute on the fly. **Invest in a full data platform** when self-service feature access, compliance-driven lineage, and cross-team SLAs justify the operational overhead of cataloging, access control, and dedicated data engineering.

Do not let tool FOMO drive the roadmap. Every component you adopt is a component you must upgrade, monitor, and teach. Add complexity when a concrete incident or SLA gap proves you need it — not because a vendor slide says your stack is incomplete.

---

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Treating shared-drive CSV folders as "version control" | Nobody can reproduce which file trained which model; validation and production diverge silently | Track datasets with DVC (or equivalent) and reference `.dvc` hashes in training configs and pipeline parameters |
| Running transforms differently in batch training versus online serving | Training-serving skew degrades accuracy without obvious errors | Centralize feature definitions in a feature store and orchestrate one materialization path for offline and online stores |
| Skipping validation before expensive training jobs | Bad upstream data wastes GPU hours and can promote corrupt models | Embed Great Expectations checkpoints as hard gates in orchestrated pipelines; fail fast when expectations break |
| Non-idempotent pipeline tasks combined with automatic retries | Retries duplicate rows, double-charge aggregations, or corrupt partitions | Design tasks to upsert or replace partitions by run date; make backfills safe to re-run |
| Hard-coded absolute paths and schedules in scripts | Pipelines break when environments change or upstream data arrives late | Parameterize paths and dates; use orchestrator sensors or asset checks for upstream readiness |
| Passing large DataFrames through orchestrator metadata (e.g., Airflow XCom) | Workers and metadata databases exhaust memory serializing multi-gigabyte objects | Write artifacts to object storage; pass URIs and schema hashes between tasks |
| Ignoring lineage until production incidents | Debugging takes days because teams cannot trace which transform or dataset version changed | Adopt OpenLineage or catalog tools; record dataset versions in experiment and model metadata |
| Backfilling without isolating downstream consumers | Rebuilt tables change statistics mid-flight while models still read old snapshots | Coordinate backfills with partition markers, feature store TTLs, and training schedule blackouts |

---

## Knowledge Check

<details>
<summary>1. What problem does DVC solve that Git alone cannot handle well for ML datasets?</summary>

**Answer:** Git stores full file blobs in history, which becomes impractical for large binary datasets and model artifacts. [DVC](https://dvc.org/doc) tracks lightweight `.dvc` pointer files in Git while storing actual bytes in remote object storage and a local cache keyed by content hash. That gives you Git-like versioning, sharing, and reproducibility without bloating the repository or re-uploading unchanged data on every commit.
</details>

<details>
<summary>2. What is training-serving skew, and how does a feature store like Feast reduce it?</summary>

**Answer:** Training-serving skew happens when features are computed differently offline (batch Spark jobs, historical snapshots) versus online (real-time API code), so the model sees a different feature distribution in production. [Feast](https://docs.feast.dev/) stores feature definitions once and serves the same transformations through offline historical retrieval and low-latency online lookups, aligning training and inference on one implementation.
</details>

<details>
<summary>3. Name five categories of checks you should encode as Great Expectations on an ML training table.</summary>

**Answer:** Typical suites cover column existence and schema stability; null constraints on required fields; numeric ranges (for example age between 0 and 120); uniqueness on identifiers; categorical value sets; regex patterns for emails; row-count bands; and distribution statistics (mean or standard deviation windows) to catch drift. The point is to treat these as automated pipeline gates, not ad-hoc notebook checks.
</details>

<details>
<summary>4. When would you choose Feast in addition to DVC rather than DVC alone?</summary>

**Answer:** DVC excels at versioning datasets, models, and reproducible pipeline stages for experiments. Feast addresses a different problem: shared, discoverable feature definitions with online serving and point-in-time correct joins for training. Add Feast when multiple teams reuse features, when you need sub-second inference lookups, or when training-serving consistency becomes a recurring incident category.
</details>

<details>
<summary>5. What is data lineage, and why does it matter for governance and debugging?</summary>

**Answer:** Data lineage records how datasets flow from sources through transformations to models and predictions. When accuracy drops or regulators ask what data influenced a decision, lineage lets you identify the exact upstream export, transformation version, and feature snapshot involved. Tools such as [OpenLineage](https://openlineage.io/) and [DataHub](https://datahubproject.io/docs/) standardize capturing that graph from orchestrated jobs.
</details>

<details>
<summary>6. How do ETL and ELT differ, and why does the choice affect ML pipeline backfills?</summary>

**Answer:** ETL transforms before load, producing curated tables early and failing when transforms break on schema drift. ELT loads raw data first and transforms inside the warehouse or lakehouse, preserving raw history for recomputation. ELT simplifies backfills when you fix feature logic—you re-run transforms on stored raw partitions—while ETL may require re-extracting from sources if staging data was not retained.
</details>

<details>
<summary>7. Why must orchestrated data pipeline tasks be idempotent before you enable automatic retries or historical backfills?</summary>

**Answer:** Orchestrators retry failed tasks and replay date partitions during backfills. If a task blindly appends rows or increments counters, a retry duplicates data and corrupts aggregates. Idempotent tasks replace or upsert a deterministic partition for each run key, so the same logical date can be processed multiple times without changing the final table state.
</details>

<details>
<summary>8. How do DVC pipelines help you build reproducible ML data workflows with versioned dependencies?</summary>

**Answer:** A `dvc.yaml` pipeline declares stages, commands, dependencies, parameters, and outputs. DVC builds a DAG and reruns only stages whose inputs changed, caching intermediate artifacts by hash. Combined with Git for code and `.dvc` files for data, you can reproduce exactly which preprocessing, training, and evaluation steps produced a given model metric.
</details>

---

## Hands-On Exercises

Work through these in order. Each exercise reinforces one layer of the data pipeline stack: versioning, orchestrated stages, features, and validation.

### Exercise 1: Set Up DVC

- [ ] Initialize a Git repository and run `dvc init` in a clean project directory
- [ ] Track a sample CSV with `dvc add` and commit the generated `.dvc` pointer file
- [ ] Configure a remote (local path or cloud bucket) and verify `dvc push` / `dvc pull` round-trip the artifact

```bash
# Initialize (S3 remotes: install the s3 extra — see DVC docs for remote setup)
pip install "dvc[s3]"
git init
dvc init

# Add data
dvc add data/train.csv
git add data/train.csv.dvc
git commit -m "Add training data"

# Set up remote
dvc remote add -d myremote s3://bucket/path
dvc push
```

### Exercise 2: Create a DVC Pipeline

- [ ] Author a `dvc.yaml` with at least preprocess and train stages and explicit `deps` / `outs`
- [ ] Change only a hyperparameter in `params.yaml` and confirm DVC reruns downstream stages only
- [ ] Inspect `dvc dag` to verify the dependency graph matches your mental model

```yaml
# dvc.yaml
stages:
  preprocess:
    cmd: python src/preprocess.py
    deps:
      - src/preprocess.py
      - data/raw/
    outs:
      - data/processed/
```

### Exercise 3: Define Feast Features

- [ ] Define an `Entity` and a `FeatureView` with at least three features and a TTL
- [ ] Materialize features and retrieve historical rows with `get_historical_features` for a fixed timestamp
- [ ] Fetch the same feature names with `get_online_features` and compare values for one entity

```python
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64, String

# Define entity and data source, then build a FeatureView — see Feast Feature Definitions above
user = Entity(name="user", join_keys=["user_id"])
# ... complete FileSource, schema=[Field(...)], and run `feast apply`
```

### Exercise 4: Create a Great Expectations Suite

- [ ] Create an expectation suite with at least ten expectations spanning schema, nulls, ranges, and row counts
- [ ] Run a checkpoint against a sample batch and confirm failures surface clearly
- [ ] Document the suite in Data Docs and wire the checkpoint as a pre-training gate in your pipeline sketch

```python
import great_expectations as gx
import great_expectations.expectations as gxe

context = gx.get_context()
suite = context.suites.add(gx.ExpectationSuite(name="my_suite"))

# Add at least 10 expectations — see Common Expectations above, then wire ValidationDefinition + Checkpoint
```

---

## Key Takeaways

If you remember nothing else from this module, remember these eight principles that separate professional ML from hobbyist ML:

1. **Data versioning is non-negotiable.** DVC gives you Git-like control over datasets. Every model should be traceable to the exact data it was trained on.

2. **Feature stores prevent training-serving skew.** When the same code computes features for training and serving, a whole class of bugs disappears.

3. **Data validation catches problems early.** Great Expectations acts like unit tests for data—catching quality issues before they corrupt your models.

4. **Lineage enables debugging.** When a model fails in production, lineage lets you trace back to the root cause—whether it's bad data, broken code, or shifted distributions.

5. **Start simple, add complexity as needed.** DVC alone addresses most early reproducibility pain before you need a full platform. Add Feast and Great Expectations when their specific problems become acute.

6. **Data quality > model complexity.** Andrew Ng's Data-Centric AI movement has it right: a simple model on good data beats a complex model on messy data.

7. **Reproducibility requires versioning everything.** Data, code, configs, parameters—if it affects your results, it needs to be versioned.

8. **Automation is key.** Manual data validation doesn't scale. Embed Great Expectations checkpoints into your CI/CD pipelines.

The journey from ad-hoc CSV folders to orchestrated, validated, versioned data pipelines is incremental. Teams usually feel the pain in a predictable order: first they cannot reproduce experiments, then they get burned by schema drift, then feature inconsistencies appear across services, and finally compliance asks for lineage they cannot produce. The tooling in this module maps cleanly onto that maturity curve — DVC when reproducibility breaks, Great Expectations when silent data bugs slip through, Feast when features become a shared product, orchestrators when cron scripts sprawl, and lineage when audits or incidents demand traceability.

Start with DVC plus explicit pipeline stages in `dvc.yaml`. Wire Great Expectations checkpoints into those stages before GPU-heavy training. Introduce Feast when the same features feed multiple models or online inference. Layer Airflow, Dagster, or Prefect when schedules, sensors, and cross-team dependencies outgrow manual runs. Each addition should close a failure mode you have already experienced — that discipline keeps operational load proportional to real risk.

---

## Next Module

Continue to [Module 1.8: ML Pipelines](../module-1.8-ml-pipelines/) for workflow orchestration patterns that wire validated, versioned data into training, evaluation, and deployment DAGs.

---

## Sources

- [DVC Documentation](https://dvc.org/doc) — Data and model versioning, pipelines, remotes, and experiment tracking.
- [DVC GitHub Repository](https://github.com/treeverse/dvc) — Source reference for pipeline DAG behavior and cache semantics.
- [Feast Documentation](https://docs.feast.dev/) — Offline/online stores, feature views, and point-in-time retrieval.
- [Feast GitHub Repository](https://github.com/feast-dev/feast) — Reference implementation for feature-store architecture.
- [Great Expectations Documentation](https://docs.greatexpectations.io/docs/) — Expectations, checkpoints, and Data Docs.
- [Great Expectations GitHub Repository](https://github.com/great-expectations/great_expectations) — Core validation APIs and integration patterns.
- [Apache Airflow Documentation](https://airflow.apache.org/docs/apache-airflow/stable/) — Task-based DAG orchestration, scheduling, and sensors.
- [Dagster Documentation](https://docs.dagster.io/) — Asset-based orchestration and data-aware pipelines.
- [Prefect Documentation](https://docs.prefect.io/) — Python-native flow orchestration and deployment models.
- [OpenLineage](https://openlineage.io/) — Open standard for capturing job and dataset lineage events.
- [DataHub Documentation](https://datahubproject.io/docs/) — Metadata catalog and lineage graph for data platforms.
- [Data Mesh Principles (Martin Fowler)](https://martinfowler.com/articles/data-mesh-principles.html) — Durable framing for decentralized data ownership and pipeline contracts.
