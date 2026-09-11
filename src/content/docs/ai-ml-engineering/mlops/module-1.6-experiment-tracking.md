---
title: "Experiment Tracking"
slug: ai-ml-engineering/mlops/module-1.6-experiment-tracking
sidebar:
  order: 607
---
> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 5-6 hours

> **Landscape snapshot -- as of 2026-06. Verify against vendor docs before relying on specifics.** MLflow's current stable release stream is 3.x, with 3.13.0 published on 2026-05-29; the project joined the Linux Foundation on 2020-06-25. Weights & Biases operates as a SaaS platform with team/enterprise tiers; its free tier covers personal and academic use. DVC remains the de facto open-source data versioning tool in the ML ecosystem. Framework versions referenced in code examples (PyTorch, scikit-learn, CUDA) reflect common stable releases at time of writing; adjust to your environment.

## What You'll Be Able to Do

By the end of this module, you will:
- Master MLflow for experiment tracking, model versioning, and registry
- Learn Weights & Biases (W&B) for real-time experiment visualization and team collaboration
- Implement systematic experiment organization and tagging strategies
- Understand the MLOps maturity model and where your organization stands
- Deploy production-grade tracking infrastructure with authentication, backups, and multi-tenancy

## Why This Module Matters

**Hypothetical scenario:** A production sentiment classifier has started returning unreliable predictions, even though the team believed they had deployed a well-performing model. The investigation exposes a familiar failure mode: the team has no reliable record of which artifact was deployed, who produced it, or how it relates to earlier runs. The training script exists in four different versions across three team members' laptops. The dataset could be any of twelve different versions -- the file was just called `training_data.csv` with no version information. The hyperparameters? Lost in a Jupyter notebook that had been overwritten countless times. After failing to reconstruct the original setup, the team has to retrain from scratch and accept a model they can at least trace and explain.

This scenario plays out in ML teams every day, and it points to the same underlying problem: teams can train strong models yet still struggle to reproduce them later or explain exactly how a production model was created. Traditional software engineering solved this decades ago with version control (Git), continuous integration, and artifact registries. But machine learning introduces a fundamentally different kind of artifact -- the trained model -- whose provenance depends not just on code, but on data versions, hyperparameters, random seeds, hardware configurations, and the specific sequence of preprocessing steps applied. None of these fit naturally into a Git commit.

Experiment tracking solves this by treating every training run as a structured, queryable record: what went in (parameters, data, code), what came out (metrics, artifacts, the model itself), and how it relates to every other run. When done systematically, it turns model development from archaeology into engineering. This module teaches you how to build that discipline using the tools that leading ML teams rely on -- and how to avoid the failure mode where a model vanishes because nobody recorded how it was built.

## The Experiment Tracking Problem

### Why Experiment Tracking Matters

Machine learning development is fundamentally different from traditional software development. In traditional software, you write code, test it, and deploy it. The code IS the product. In ML, you train models -- and the model is the product. The code is just a recipe.

This creates a unique problem. Traditional version control (Git) tracks code changes beautifully, but it is structurally incapable of tracking the environmental factors that determine model behavior: which dataset version was used for training, what hyperparameters produced the best result, which preprocessing steps were applied, the random seed that made results reproducible, and the actual model weights themselves, which can run to gigabytes and have no meaningful line-by-line diff.

Think of it like a kitchen. Git can track your recipe (the code), but it cannot track which specific tomatoes you used, what temperature your oven actually was -- not what you set it to -- or the skill of the chef on that particular day. In ML, all of these environmental factors matter, sometimes more than the recipe itself. A model trained with the same code but a different random seed can converge to a different local minimum and exhibit meaningfully different behavior in production.

Without proper tracking, ML development degrades into chaos. Teams create folder structures that look like archaeological sites: `model_final.pt`, `model_final_v2.pt`, `model_final_ACTUALLY_FINAL.pt`, `model_best_USE_THIS.pt`. When the inevitable question comes -- "Can we reproduce the model we shipped six months ago?" -- the answer is usually a panicked silence.

The reproducibility challenge in ML has been documented extensively in the research community. Systematic surveys of ML papers have found that key experimental details -- preprocessing, hyperparameter ranges, random seeds, evaluation protocols -- are frequently omitted, making independent reproduction of published results difficult even for the original authors after a few months. The ICLR Reproducibility Challenge, launched in 2019, formalized this concern by inviting researchers to reproduce accepted papers and report their findings. What began as an academic concern has become an engineering one: as more organizations deploy ML in production, the cost of non-reproducibility shifts from "we cannot verify this paper" to "we cannot explain why this model denied a loan application."

### The Hidden Cost of Poor Tracking

Poor experiment tracking creates a persistent maintenance burden: teams lose time reconstructing old runs, environments, and decisions instead of building new models. This is not a hypothetical cost -- it compounds with every team member who leaves, every model that needs updating, and every stakeholder who asks why a model made a particular decision.

The problem is self-reinforcing. When tracking is poor, institutional knowledge becomes tribal knowledge. Only Alice knows which preprocessing script was used for the Q2 fraud model. Only Bob knows why the learning rate was set to 0.0003 instead of 0.001. When Alice and Bob leave or move to other projects, that knowledge leaves with them, and the next engineer has to reverse-engineer the original training environment from whatever fragments remain.

This cost is not evenly distributed across the ML lifecycle. It is lowest during initial experimentation, when everything is fresh and the team is small. It rises sharply during handoff from research to production, when the data scientist cannot tell the ML engineer exactly which preprocessing steps were needed and the ML engineer cannot tell operations which model version is actually serving traffic. And it peaks during incident response, when a production model degrades and nobody can determine what changed.

The solution is experiment tracking: systematically recording everything about every experiment, so any model can be reproduced, explained, and improved upon. It is not glamorous work -- logging parameters and metrics does not ship features or win Kaggle competitions -- but it is the difference between an ML team that can operate at scale and one that collapses under the weight of its own history.

### The Params-Metrics-Artifacts Data Model

Every experiment tracking tool, regardless of its interface or pricing model, is built on the same conceptual foundation: a run is a structured record of an experiment, and every run contains three categories of information.

**Parameters** are the inputs you control: learning rate, batch size, number of layers, dropout rate, dataset version, random seed, optimizer choice. They are the knobs you turn before training begins, and they are typically logged once at the start of a run. Parameters are the "why" of an experiment -- they encode the hypothesis you are testing: "I believe that lowering the learning rate and adding dropout will reduce overfitting."

**Metrics** are the outputs you measure: training loss, validation accuracy, F1 score, inference latency, model size. Unlike parameters, metrics evolve during training -- a loss curve is not a single number but a time series. Most tracking tools support step-level logging (every N batches) and epoch-level logging (once per pass through the dataset). Metrics are the "what" of an experiment -- they tell you whether your hypothesis was correct.

**Artifacts** are the durable outputs: the trained model file, a confusion matrix plot, a feature importance report, a serialized tokenizer, a requirements.txt capturing the Python environment. Artifacts are what you would need to recreate the model's behavior in production. They are the "how" of an experiment -- the concrete deliverables that survive after the training script finishes.

This three-category model is not unique to MLflow or W&B. It appears in DVC's run tracking, in Kubeflow Pipelines' artifact passing, and in every serious experiment tracking system. Understanding it conceptually matters because it tells you what to log and why. When you add a new data source to your training pipeline, you log it as a parameter. When you compute a new evaluation metric, you log it as a metric. When you save a model checkpoint, you log it as an artifact. The tool handles storage and querying; your job is to feed it the right structured information at the right time.

## 1. MLflow: The Open-Source Standard

### The Vision Behind MLflow

MLflow was created at Databricks in 2018 to address a recurring pattern the company observed across its customers: brilliant data scientists would build impressive models in notebooks, but those models would die in the handoff to production. The problem was not deployment technology -- it was that nobody could reliably describe what they were deploying. The data scientist could not specify the preprocessing pipeline unambiguously. The ML engineer could not identify the exact model version in production. Operations had no audit trail for model provenance.

MLflow was designed to solve this by treating experiment metadata with the same rigor that databases treat data: structured, queryable, and persistent. Rather than building yet another walled-garden platform, the team released it as open source under the Apache 2.0 license, allowing any organization to self-host and integrate it into existing infrastructure. On 2020-06-25, MLflow joined the Linux Foundation, cementing its role as a neutral, community-governed project rather than a single-vendor tool.

The name "MLflow" comes from the concept of "workflow" -- but specifically, the flow of machine learning experiments from conception to production. It is not just about tracking; it is about enabling the entire ML lifecycle.

### MLflow's Four Components

MLflow is actually four tools in one, each solving a different part of the ML lifecycle.

**MLflow Tracking** records experiments: parameters, metrics, artifacts, and source code. Every time you train a model, Tracking creates a "run" that captures everything about that training session. You can think of it as a flight recorder for your ML experiments -- it captures enough information to reconstruct what happened later, even if the original environment is gone.

**MLflow Projects** packages code in a reproducible format. Instead of sending a colleague a Python script and hoping it works on their machine, you package the code with its dependencies and entry points. Anyone can run the same experiment by pointing MLflow at the project, regardless of their local environment differences.

**MLflow Models** provides a standard format for saving models across frameworks. Different libraries -- PyTorch, TensorFlow, scikit-learn, XGBoost -- save models in different formats with different loading APIs. MLflow Models provides a unified `pyfunc` interface, so any deployment tool can load any model without knowing which framework trained it. It is analogous to PDF for documents: a broadly compatible format that works in many environments regardless of the original authoring tool.

**MLflow Model Registry** provides versioning and lifecycle management for production models. It is the bridge between experimentation and deployment, letting you label candidate models, assign aliases such as `champion` to the version intended for live traffic, and roll back when things go wrong. The Registry tracks model versions, tags, aliases, descriptions, and lineage -- providing the audit trail that the hypothetical scenario at the start of this module was missing.

### Basic Experiment Tracking

Every experiment tracking library follows the same pattern: start a run, log structured data, and let the tool handle storage and querying. In MLflow, this pattern looks like the following example, which trains a simple classifier and records everything:

```python
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

# Set the experiment name -- all runs are grouped under this
mlflow.set_experiment("sentiment-classifier")

# Start a run -- creates a new experiment record with a unique ID
with mlflow.start_run(run_name="random-forest-baseline"):
    # Log parameters -- the knobs you control
    mlflow.log_param("n_estimators", 100)
    mlflow.log_param("max_depth", 10)
    mlflow.log_param("dataset_version", "v3.2")
    mlflow.log_param("random_seed", 42)

    # Train the model
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42
    )
    model.fit(X_train, y_train)

    # Evaluate and log metrics -- the outcomes you measure
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    f1 = f1_score(y_test, predictions, average='weighted')

    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("f1_score", f1)
    mlflow.log_metric("train_samples", len(X_train))
    mlflow.log_metric("test_samples", len(X_test))

    # Log the model itself as an artifact so it can be reloaded later
    mlflow.sklearn.log_model(model, "model")

    # Log supporting artifacts -- plots, reports, data samples
    mlflow.log_artifact("confusion_matrix.png")
    mlflow.log_artifact("feature_importance.json")

    # The run ID is your reference for later retrieval
    run_id = mlflow.active_run().info.run_id
    print(f"Run ID: {run_id}")
    print(f"Accuracy: {accuracy:.4f}")
```

Every `log_param`, `log_metric`, and `log_artifact` call writes to MLflow's storage backend. After the experiment finishes, you can browse the MLflow UI, search for runs matching specific criteria, compare metrics across runs in parallel coordinate plots or scatter plots, and download the exact model that achieved the best results.

The real power becomes apparent when you have run hundreds or thousands of experiments. Instead of sifting through folders and notebooks, you query: "Show me all runs where `learning_rate` is less than 0.01 and `accuracy` is above 0.9, sorted by F1 score." MLflow returns the exact runs, with every parameter, metric, and artifact needed to reproduce them. The equivalent in Weights & Biases uses the dashboard's filter bar with a similar query syntax. In DVC, you would use `dvc experiments show` with metric filters.

### Autologging: Tracking Without Code Changes

Manually logging every parameter is tedious and error-prone -- it is easy to forget a hyperparameter or typo a metric name. MLflow's autologging feature addresses this by automatically capturing parameters, metrics, and artifacts for supported frameworks:

```python
import mlflow

# Enable autologging for PyTorch with a single call
mlflow.pytorch.autolog()

# Your training code remains completely unchanged, but MLflow now
# automatically captures:
# - Model architecture (layer types, sizes, parameter counts)
# - Optimizer settings (learning rate, momentum, weight decay)
# - Loss curves (training loss at each step)
# - Validation metrics (accuracy, F1 at each epoch)
# - Model checkpoints (best and last)
# - Training time and hardware metadata

trainer = Trainer(model, train_loader, val_loader)
trainer.train(epochs=10)
```

Autologging supports PyTorch, TensorFlow, scikit-learn, XGBoost, LightGBM, and several other major ML libraries. It captures roughly 80% of what you would want to log in a typical training run without any manual instrumentation. You still add manual `log_param` calls for custom parameters that the framework does not know about -- your dataset version, your business use case, your experiment group -- but autologging eliminates the repetitive boilerplate.

Think of autologging like a security camera that records automatically. You do not have to remember to press "record" for the standard channels. You only add manual logging for domain-specific metadata that the framework cannot infer. Weights & Biases provides a similar feature through `wandb.watch()`, which hooks into PyTorch and TensorFlow models to log gradients and parameter histograms automatically.

### The Model Registry: From Experiment to Production

Training a good model is only half the battle. Getting that model safely into production -- and managing it once it is there -- requires a different set of tools. The Model Registry provides that bridge.

```python
import mlflow
from mlflow.tracking import MlflowClient

client = MlflowClient()

# After a successful training run, register the model
model_uri = f"runs:/{run_id}/model"
registered_model = mlflow.register_model(
    model_uri,
    "SentimentClassifier"  # The model's name in the registry
)

# Add documentation -- your future self (and your colleagues) will thank you
client.update_model_version(
    name="SentimentClassifier",
    version=registered_model.version,
    description="""
    BERT-based sentiment classifier trained on v3.2 dataset.
    Achieves 94.2% accuracy on test set.
    Uses 6-layer DistilBERT for inference efficiency.
    Trained by ML Team, reviewed by Alice.
    """
)

# Mark the version as a candidate while integration tests run
client.set_model_version_tag(
    name="SentimentClassifier",
    version=registered_model.version,
    key="validation_status",
    value="pending"
)

# After testing passes, record the result and move the serving alias
client.set_model_version_tag(
    name="SentimentClassifier",
    version=registered_model.version,
    key="validation_status",
    value="passed"
)
client.set_registered_model_alias(
    name="SentimentClassifier",
    alias="champion",
    version=registered_model.version
)
```

The Registry now centers on model versions, tags, and aliases. Tags record structured status such as `validation_status=pending` or `validation_status=passed`, while aliases provide named pointers such as `champion`, `challenger`, or `rollback-candidate`. MLflow's older fixed stages (`None`, `Staging`, `Production`, `Archived`) were deprecated in MLflow 2.9, so a current workflow should use aliases for serving references and tags or environment-specific registered models for process state.

This might seem like bureaucracy, but it prevents disasters. When the hypothetical team at the start of this module had the model in a "USE_THIS_ONE" folder, there was no process, no audit trail, no way to know what was actually in production. With the Registry, there is exactly one `champion` alias for the model intended to serve live traffic, and every alias movement can be paired with validation tags, review comments, and a versioned model record.

### Loading Models from the Registry

Once models are registered, loading them for inference is straightforward and framework-agnostic:

```python
import mlflow.pyfunc

# Load the current production model by alias -- always the intended live version
model = mlflow.pyfunc.load_model(
    model_uri="models:/SentimentClassifier@champion"
)

# Or load a specific version for A/B comparison or debugging
model_v2 = mlflow.pyfunc.load_model(
    model_uri="models:/SentimentClassifier/2"
)

# Inference works the same regardless of which framework trained the model
predictions = model.predict(input_data)
```

The `models:/` URI scheme is the key abstraction. Your serving infrastructure can point at `models:/ModelName@champion`, and the Registry handles which specific version that means. Promoting a new model is an alias update, optionally paired with tags such as `validation_status=passed` and `reviewed_by=alice` -- no configuration changes, no restart required, no risk of pointing at a stale path.

## 2. Weights & Biases: Visualization and Collaboration

### A Different Philosophy

Weights & Biases (W&B) takes a different approach than MLflow. While MLflow emphasizes self-hosting, lifecycle management, and the full pipeline from experiment to deployment, W&B emphasizes real-time visualization and team collaboration. The two tools represent complementary philosophies rather than direct competitors, and many teams use both.

W&B was founded in 2017 by Lukas Biewald, who had previously founded CrowdFlower (later Figure Eight), a data labeling platform. That background shaped W&B's focus: Biewald had seen firsthand how data quality affects model quality, and how teams struggle to understand model behavior without good visualization. W&B was built to make experiment results immediately visible -- so teams could inspect metrics as training happens rather than discovering problems days later in static reports.

The name "Weights & Biases" references the fundamental parameters in neural networks (the `w` and `b` in `y = Wx + b`), but it also nods to the scientific process: every researcher has biases, and systematic tracking helps account for them by making results transparent and comparable.

Where MLflow treats experiment tracking as an infrastructure problem (structured storage, lifecycle management, deployment integration), W&B treats it as a collaboration problem (shared dashboards, real-time updates, easy comparison). Neither is wrong; they serve different stages of the ML lifecycle and different team structures.

### Basic W&B Logging

W&B's API is deliberately simple. You initialize a run, log what you want, and W&B handles the rest -- storage, visualization, sharing, and comparison:

```python
import wandb
import torch
import torch.nn as nn

# Initialize a run with all configuration in one place
wandb.init(
    project="sentiment-classifier",
    config={
        "learning_rate": 0.001,
        "epochs": 10,
        "batch_size": 32,
        "architecture": "BERT-base",
        "dataset": "sentiment-v3.2",
        "optimizer": "AdamW"
    },
    notes="Testing BERT-base with lower learning rate",
    tags=["bert", "experiment", "v3.2-dataset"]
)

# Training loop with real-time logging -- metrics appear in the
# dashboard as soon as wandb.log() is called
for epoch in range(wandb.config.epochs):
    for batch_idx, (data, target) in enumerate(train_loader):
        output = model(data)
        loss = criterion(output, target)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # Log step-level metrics -- visible in real time
        wandb.log({
            "train_loss": loss.item(),
            "epoch": epoch,
            "batch": batch_idx,
            "learning_rate": get_lr(optimizer)
        })

    # Validation at end of each epoch
    val_loss, val_acc = evaluate(model, val_loader)
    wandb.log({
        "val_loss": val_loss,
        "val_accuracy": val_acc,
        "epoch": epoch
    })

# Save the trained model as a versioned artifact
artifact = wandb.Artifact("sentiment-model", type="model")
artifact.add_file("model.pt")
wandb.log_artifact(artifact)

wandb.finish()
```

The moment you call `wandb.log()`, the metric appears in the W&B dashboard. If you are training on a remote GPU server, you can watch the training curves update in real time from your laptop. Multiple team members can compare runs side by side, overlay metrics from different experiments, and share report URLs with a single click. The equivalent in MLflow requires either the MLflow UI (self-hosted) or programmatic querying through the tracking API. DVC takes yet another approach: it stores metrics in version-controlled YAML or JSON files and uses `dvc metrics diff` and `dvc metrics show` for comparison, integrating tightly with Git workflows.

### W&B Sweeps: Hyperparameter Optimization

One of W&B's most popular features is Sweeps -- built-in hyperparameter optimization that automates the search over configuration space:

```python
import wandb

# Define the search space -- which parameters to tune and how
sweep_config = {
    "method": "bayes",  # Bayesian optimization; alternatives: random, grid
    "metric": {
        "name": "val_accuracy",
        "goal": "maximize"
    },
    "parameters": {
        "learning_rate": {
            "min": 0.0001,
            "max": 0.1,
            "distribution": "log_uniform_values"
        },
        "batch_size": {
            "values": [16, 32, 64, 128]
        },
        "hidden_size": {
            "min": 64,
            "max": 512,
            "distribution": "int_uniform"
        },
        "dropout": {
            "min": 0.1,
            "max": 0.5
        }
    },
    "early_terminate": {
        "type": "hyperband",
        "min_iter": 3
    }
}

# Create the sweep -- returns an ID that agents use to pull work
sweep_id = wandb.sweep(sweep_config, project="sentiment-classifier")

# Define the training function that each agent will execute
def train():
    wandb.init()

    # Config values come from the sweep, not from hard-coded constants
    model = build_model(
        hidden_size=wandb.config.hidden_size,
        dropout=wandb.config.dropout
    )

    for epoch in range(10):
        train_epoch(model, wandb.config.learning_rate, wandb.config.batch_size)
        val_acc = evaluate(model)
        wandb.log({"val_accuracy": val_acc, "epoch": epoch})

# Launch sweep agents -- count=50 means 50 different configurations
wandb.agent(sweep_id, train, count=50)
```

The Bayesian optimization in Sweeps is particularly valuable. It builds a probabilistic model of the objective function based on completed runs and uses it to select the next hyperparameters to try. Instead of randomly sampling from the search space -- which wastes compute on configurations that are obviously bad -- it focuses on promising regions and balances exploration of unknown areas against exploitation of known good ones.

The early termination feature, using the Hyperband algorithm, makes sweeps even more efficient. If a configuration is performing terribly after three epochs, there is little chance it will become the best after a hundred. Hyperband automatically kills unpromising runs and redirects compute resources to more promising candidates, dramatically reducing the total GPU-hours needed to find a good configuration.

The equivalent in the MLflow ecosystem is typically implemented through Optuna or Hyperopt integration: you run a hyperparameter search script that creates MLflow runs for each trial and logs parameters and metrics, then use the MLflow UI to compare results. DVC handles this through its experiments queue (`dvc exp run --queue`) combined with `dvc exp run --run-all`, which executes queued experiments in parallel and tracks their parameters and metrics in Git.

### W&B Tables: Data and Prediction Visualization

Beyond metrics, W&B Tables let you log and visualize structured data -- predictions, datasets, evaluation results, and anything else that fits in a table:

```python
import wandb

# Create a table for model predictions with interactive columns
table = wandb.Table(columns=["text", "true_label", "predicted", "confidence"])

for text, true, pred, conf in predictions:
    table.add_data(text, true, pred, conf)

# Log the table -- it becomes interactive in the dashboard, with
# sorting, filtering, and custom queries
wandb.log({"predictions": table})

# Built-in plot types for common evaluation tasks
wandb.log({
    "confusion_matrix": wandb.plot.confusion_matrix(
        y_true=y_true,
        preds=y_pred,
        class_names=["negative", "positive"]
    )
})

wandb.log({
    "pr_curve": wandb.plot.pr_curve(
        y_true=y_true,
        y_probas=y_probas,
        labels=["negative", "positive"]
    )
})
```

Tables in the W&B dashboard are fully interactive. You can sort by confidence to find high-confidence errors, filter by label to analyze specific classes, and build custom queries to answer questions like "show me all examples where the true label is positive but the model predicted negative with confidence above 0.8." For debugging model behavior, this is invaluable -- you can see exactly which examples the model gets wrong and form hypotheses about why, rather than staring at aggregate metrics and guessing.

## 3. MLflow vs W&B: Choosing Your Platform

### The Trade-offs

Both MLflow and W&B are mature, widely adopted tools, but they emphasize different things. Understanding their design philosophies helps you choose the right tool for the right job rather than treating them as interchangeable.

**MLflow** is open-source, self-hostable, and built around the full ML lifecycle from experiment to deployment. Choose MLflow when you need to self-host for security or compliance reasons, when model serving and deployment integration are central concerns, when you want full control over your infrastructure and data residency, or when your organization's procurement process makes SaaS tools difficult to adopt. MLflow's strength is that it gives you a complete platform with no external dependencies -- tracking, projects, models, and registry all run on your own infrastructure.

**W&B** is SaaS-first with superior visualization and collaboration. Choose W&B when you want best-in-class experiment visualization without building custom dashboards, when team collaboration and real-time monitoring are priorities, when you need built-in hyperparameter sweeps with Bayesian optimization, or when you prefer a managed service that eliminates infrastructure overhead. W&B's strength is that it makes experiment results immediately visible and shareable with near-zero setup.

Many teams use both tools simultaneously: W&B for experiment visualization and collaboration during the research phase, MLflow for model registry and deployment management in production. The tools are not mutually exclusive -- they solve overlapping but different problems, and the integration path is straightforward: log metrics to W&B during training, then register the final model artifact in MLflow for production serving.

Think of the difference as analogous to GitHub versus your CI/CD system. GitHub excels at code review, collaboration, and visibility into the development process. Your CI/CD system excels at automated testing, deployment, and operations. Similarly, W&B excels at experiment collaboration and real-time visibility, while MLflow excels at model lifecycle management and production deployment. Using both is not duplication -- it is specialization.

### When to Use Both

A common pattern in teams that use both tools works as follows. During the research and experimentation phase, data scientists log everything to W&B: every training run, every hyperparameter combination, every evaluation result. W&B dashboards become the team's shared view of experimental progress, and Sweeps automate the hyperparameter search.

When a model shows sufficient promise to be considered for production, the team registers it in MLflow's Model Registry. The MLflow run captures the final parameters, metrics, and model artifact. The Registry tracks the candidate through version tags such as `validation_status=passed`, aliases such as `champion`, and, in stricter environments, separate registered models for development, staging, and production. The serving infrastructure loads from `models:/ModelName@champion` and never needs to know about W&B.

This division of labor plays to each tool's strengths. W&B handles the high-volume, iterative, collaborative research workflow. MLflow handles the lower-volume, high-stakes, auditable production workflow. The handoff point -- registering a model from a successful experiment into the Registry -- is the seam between the two systems.

## 4. Experiment Organization Best Practices

### Naming Conventions That Scale

As your experiments grow from tens to hundreds to thousands, organization becomes the difference between a searchable knowledge base and an unreadable dump. The key is consistency: every team member should use the same naming conventions, the same experiment groupings, and the same tagging strategy. Here is a structure that scales from a single researcher to a multi-team organization:

```
Project: sentiment-classifier
├── Experiment: baseline-models
│   ├── Run: logistic-regression-v1
│   ├── Run: random-forest-v1
│   └── Run: naive-bayes-v1
│
├── Experiment: transformer-experiments
│   ├── Run: bert-base-lr001
│   ├── Run: bert-base-lr0001
│   ├── Run: bert-large-frozen
│   └── Run: distilbert-finetuned
│
├── Experiment: hyperparameter-sweep-2026-Q1
│   ├── Run: sweep-001 through sweep-100
│   └── (100 runs with different configurations)
│
└── Experiment: production-candidates
    ├── Run: candidate-v1.0-validated
    ├── Run: candidate-v1.1-validated
    └── Run: candidate-v1.2-A/B-testing
```

The hierarchy of Project > Experiment > Run is common to both MLflow and W&B. Projects represent broad business problems (sentiment classification, fraud detection, recommendation). Experiments represent coherent investigations within a project (baseline comparison, transformer architecture exploration, hyperparameter optimization). Runs represent individual training executions with a specific configuration.

Naming runs descriptively pays compounding returns. A name like `bert-base-lr001` tells you the architecture and learning rate at a glance. A name like `run_152` tells you nothing. When you are comparing runs six months later, descriptive names reduce the cognitive load of understanding what each run represents.

### Strategic Tagging

Tags are the secret weapon of experiment organization. A good tagging strategy turns your experiment history into a queryable database, making it easy to find any experiment months later regardless of its position in the project hierarchy:

```python
mlflow.set_tags({
    # Experiment classification
    "experiment_type": "hyperparameter_search",
    "team": "nlp",
    "owner": "alice@company.com",

    # Data provenance -- which data was used and how
    "dataset_version": "v3.2",
    "dataset_source": "production_logs",
    "data_split": "stratified_5_fold",
    "train_samples": "50000",
    "test_samples": "10000",

    # Model architecture
    "model_family": "transformer",
    "model_base": "bert-base-uncased",
    "model_size_mb": "400",
    "trainable_params": "110M",

    # Training environment
    "gpu": "A100-40GB",
    "framework": "pytorch-2.0",
    "cuda_version": "11.8",

    # Business context
    "project": "customer-sentiment",
    "use_case": "support-automation",
    "priority": "high",

    # Status flags
    "validated": "true",
    "production_candidate": "true"
})
```

With this tagging, you can answer questions like "Show me all production candidates from the NLP team that were trained on dataset v3.2 using A100 GPUs" with a single query rather than hours of manual searching. The tags create a faceted search interface over your experiment history, similar to how an e-commerce site lets you filter products by brand, price, and category simultaneously.

The equivalent in W&B uses the same concept: the `config` dictionary passed to `wandb.init()` and the `tags` list serve as the searchable metadata layer. In DVC, parameters are tracked in `params.yaml` and metrics in `metrics.yaml`, with Git providing the versioning and searchability through commit messages and branch names.

### Metric Logging Strategy

Not all metrics are equal. Some should be logged at every training step to diagnose learning dynamics. Others should be logged once per epoch to enable run comparison. And a small set of final metrics should be logged once at the end for quick filtering and model selection:

```python
# Step-level metrics: logged frequently during training to diagnose
# learning dynamics -- convergence speed, gradient health, loss spikes
for step, batch in enumerate(train_loader):
    loss = train_step(batch)

    # Log every N steps to avoid overwhelming storage with per-step data
    if step % 10 == 0:
        mlflow.log_metric("train_loss", loss, step=step)
        mlflow.log_metric("learning_rate", get_lr(optimizer), step=step)

# Epoch-level metrics: logged once per epoch for run comparison
for epoch in range(num_epochs):
    train_metrics = train_epoch()
    val_metrics = evaluate()

    mlflow.log_metrics({
        "epoch_train_loss": train_metrics["loss"],
        "epoch_train_accuracy": train_metrics["accuracy"],
        "epoch_val_loss": val_metrics["loss"],
        "epoch_val_accuracy": val_metrics["accuracy"],
    }, step=epoch)

# Final metrics: logged once at the end for quick filtering and model selection
mlflow.log_metrics({
    "best_val_accuracy": best_accuracy,
    "final_test_accuracy": test_accuracy,
    "total_training_time_hours": training_time / 3600,
    "final_model_size_mb": get_model_size(model),
    "total_epochs_trained": actual_epochs,
    "early_stopped": was_early_stopped
})
```

Step-level metrics let you diagnose training dynamics: Is the loss decreasing smoothly or oscillating? Is the learning rate schedule working as intended? Epoch-level metrics are for comparing runs: Which architecture achieved the best validation accuracy? Final metrics are for quick filtering: Show me all runs with test accuracy above 0.9, sorted by training time. Each logging frequency serves a different analytical purpose, and a good logging strategy uses all three.

## 5. The MLOps Maturity Model

### Understanding Where You Are

Industry maturity models for MLOps frame the journey as a progression from manual, ad-hoc practices toward increasing automation of training, deployment, and monitoring. Understanding where your team sits on this spectrum helps you prioritize the next investment rather than trying to build everything at once.

**Level 0: No MLOps.** This is the state described in the hypothetical scenario at the start of this module. Models live in notebooks. Deployment is manual -- someone copies a `.pkl` file to a server. There is no version control for models, no experiment tracking, no reproducibility. Everything depends on individual memory and good intentions. A 2021 Comet survey of 508 U.S. machine learning practitioners found that 58% of ML teams tracked all or at least some experiments manually; that narrower finding does not prove those organizations were at Level 0, but it does show how common manual experiment tracking still was in real teams.

**Level 1: DevOps but not MLOps.** Teams at this level have adopted standard software engineering practices: Git for code, CI/CD for application deployment, automated testing for application logic. But ML-specific concerns -- experiment tracking, data versioning, model versioning, feature engineering pipelines -- remain manual. Training is repeatable only through individual tribal knowledge. The code is under control, but the models are not.

**Level 2: Automated Training.** This is the first milestone where MLflow and W&B deliver their core value. Experiments are tracked systematically. Models are versioned. Automated training pipelines can be triggered and re-run. Parameters, metrics, and artifacts are captured for every run. But deployment is still manual -- someone has to look at the metrics and decide to promote a model to production. This level is achievable with a small team and provides massive benefits: reproducibility, audit trails, and the ability to compare experiments across team members and time.

**Level 3 and beyond: Automated Deployment and Monitoring.** At higher maturity levels, teams automate model validation (performance checks, fairness tests, drift detection), implement staged rollout patterns (canary, A/B, shadow), and build monitoring systems that trigger alerts and retraining when model performance degrades. The most advanced organizations close the loop entirely with continuous training: new data triggers automated retraining, the new model is validated against the current production model, and if it performs better, it is promoted automatically.

Most organizations should target Level 2 as the first concrete milestone. It is achievable with a small team, provides immediate and visible benefits, and creates the foundation -- structured experiment data, a model registry, reproducible training pipelines -- that higher levels depend on. You cannot automate deployment if you cannot reliably reproduce a model. You cannot monitor model drift if you do not know which model version is in production. Level 2 is not the destination, but it is the prerequisite for everything beyond it.

## 6. Production Experiment Tracking Setup

### MLflow Production Architecture

Running `mlflow server` on a laptop with a local SQLite file is fine for individual experimentation. For a team, and especially for a team that depends on experiment tracking for production reproducibility, you need proper infrastructure: a database for metadata, object storage for artifacts, and authentication for security. The following compose file is an illustrative topology sketch, not a copy-paste production runbook; a runnable deployment still needs real secrets, an actual object-storage bucket or MinIO service, TLS, backups, and image dependency validation for your environment:

```yaml
# docker-compose.yml sketch for MLflow with PostgreSQL and object storage
version: '3.8'

services:
  mlflow:
    image: ghcr.io/mlflow/mlflow:v3.13.0
    ports:
      - "5000:5000"
    environment:
      - MLFLOW_BACKEND_STORE_URI=postgresql://mlflow:${POSTGRES_PASSWORD}@postgres:5432/mlflow
      - MLFLOW_ARTIFACT_ROOT=s3://mlflow-artifacts/
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    command: >
      mlflow server
      --host 0.0.0.0
      --port 5000
      --backend-store-uri postgresql://mlflow:${POSTGRES_PASSWORD}@postgres:5432/mlflow
      --default-artifact-root s3://mlflow-artifacts/

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_USER=mlflow
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=mlflow
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

In production, teams typically back MLflow with a dedicated database (PostgreSQL or MySQL) for structured metadata and an object store (S3, GCS, or MinIO) for artifacts. The database holds parameters, metrics, tags, and run metadata -- everything that is small and queryable. The object store holds model files, plots, and other large artifacts that do not need to be queryable but do need to be durable and versioned. Separating these concerns keeps the database small and fast while allowing artifact storage to scale independently.

### Configuring Clients

Once the server is running, every client -- team members' laptops, training servers, CI/CD runners, notebooks -- points to the same tracking server:

```python
import mlflow
import os

# Point all MLflow API calls to the shared tracking server
mlflow.set_tracking_uri("http://mlflow-server.internal:5000")

# Or configure via environment variables so every script picks it up
os.environ["MLFLOW_TRACKING_URI"] = "http://mlflow-server.internal:5000"
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "http://minio:9000"  # If using MinIO

# Now all logging goes to the server, not local files
with mlflow.start_run():
    mlflow.log_param("model", "bert-base")
    mlflow.log_metric("accuracy", 0.95)
    mlflow.sklearn.log_model(model, "model")
```

Every team member, every training server, and every notebook can point to the same tracking server. Experiments from all sources appear in the same UI, making collaboration seamless and eliminating the "it works on my machine but the results are invisible to everyone else" problem.

### Authentication, Multi-Tenancy, and Backup

A production tracking server needs more than just a database and object store. Three additional concerns become critical as the system moves from individual use to team infrastructure.

**Authentication** ensures that only authorized users can read experiment data and modify the model registry. Current MLflow supports basic HTTP authentication for tracking-server access control, and MLflow 3.13 adds role-based access control with reusable roles and an Admin UI for self-hosted deployments. Many production deployments still place MLflow behind an SSO-aware reverse proxy or identity-aware gateway, but that should be framed as an integration pattern rather than a sign that MLflow has no built-in auth.

**Multi-tenancy** separates experiments and models across teams, preventing accidental cross-team access or modification. The simplest approach is to use naming conventions (`team-nlp/sentiment-classifier` vs `team-vision/object-detector`) combined with separate tracking servers for teams with strict data isolation requirements. More sophisticated setups use MLflow workspaces and RBAC, SSO integrations, or a gateway layer to enforce per-team access controls.

**Backup and disaster recovery** protect against the loss of experiment history and model artifacts. The PostgreSQL database should be backed up regularly following standard database backup practices (point-in-time recovery with WAL archiving). The object store should have versioning enabled and cross-region replication configured if the organization's recovery objectives require it. Losing experiment history is losing institutional knowledge -- treat it with the same backup discipline you would apply to source code repositories and production databases.

The equivalent concerns apply to W&B's SaaS platform: teams configure access controls through W&B's project-level permissions, and data durability is handled by W&B's infrastructure. The trade-off is operational simplicity (no servers to manage) against data residency control (your data lives on W&B's infrastructure). DVC addresses these concerns differently: because DVC stores metadata in Git and artifacts in configurable remotes (S3, GCS, SSH, local), authentication and backup are handled by your existing Git and storage infrastructure rather than by DVC itself.

## Did You Know?

- **MLflow joined the Linux Foundation on 2020-06-25**, transitioning from a Databricks-led project to a neutral, community-governed foundation. This move parallels similar transitions by other ML infrastructure projects (Kubeflow to CNCF, Jupyter to NumFOCUS) and signals the project's maturity as a shared industry standard rather than a single-vendor tool.
- **The ICLR Reproducibility Challenge**, launched in 2019, formalized a concern that had been growing in the ML community for years: that published results were often difficult or impossible to reproduce. Participating teams attempted to replicate accepted ICLR papers and published their findings, revealing that even well-regarded papers frequently omitted critical experimental details. The challenge helped drive adoption of systematic experiment tracking as a standard practice.
- **DVC (Data Version Control)** approaches experiment tracking from a different angle than MLflow or W&B: it treats ML experiments as a Git problem. Parameters go in `params.yaml`, metrics in `metrics.yaml`, and large artifacts (datasets, models) are stored in remote storage with Git-tracked pointers. The `dvc experiments` command provides a Git-branch-like workflow for experiments, making it a natural fit for teams that already think in terms of branches, commits, and diffs.
- **Google's "Rules of ML"** (43 rules distilled from years of production ML experience at Google) treats ML infrastructure as a first-class engineering problem. Rule 4 -- "Keep the first model simple and get the infrastructure right" -- emphasizes that robust pipelines matter more than model sophistication early on, while Rule 22 -- "Clean up features you are no longer using" -- warns that unused features create technical debt.

## Common Mistakes

| Mistake | Problem | Solution |
|---------|---------|----------|
| Logging only final metrics | You lose the training dynamics -- loss curves, learning rate schedules, validation progress -- that explain why a model converged well or poorly. When a run performs unexpectedly, you have no data to diagnose it. | Log step-level metrics (every N batches) for training dynamics and epoch-level metrics for run comparison, in addition to final metrics for filtering. |
| Using vague run names | Names like `run_152` or `test_3` become meaningless after a week. When you need to find a specific experiment among hundreds of runs, vague names force you to open each run individually to understand what it represents. | Use descriptive names that encode the key configuration: `bert-base-lr001-bs32`, `resnet50-augmented-v2`. The name should tell you at a glance what makes this run different. |
| Skipping a random seed log | Without the seed, a model is not truly reproducible. Two runs with identical code, data, and hyperparameters but different seeds can produce meaningfully different models, especially with small datasets or unstable architectures. | Always log the random seed as a parameter, and set it explicitly rather than relying on framework defaults. |
| Treating the model registry as optional | Without a registry, "which model is in production?" becomes a forensic investigation. Teams resort to file naming conventions (`model_production_FINAL_v2.pkl`) that are error-prone and un-auditable. | Register every model that reaches validation. Use tags for review state, assign aliases such as `champion` for serving, and point serving infrastructure at `models:/ModelName@champion`. |
| Mixing tracking backends across team members | When Alice logs to a local SQLite file, Bob logs to a shared PostgreSQL server, and Charlie logs to a different server entirely, there is no single source of truth. Comparing experiments requires manual data collection. | Point every client at the same tracking server. Use environment variables or a shared configuration file so that consistency is the default, not something each team member must remember. |
| Not logging data provenance | Knowing that a model achieved 94% accuracy is useful. Knowing that it was trained on dataset v3.2, with a specific train/test split and preprocessing pipeline, is essential. Without data provenance, you cannot explain performance changes or reproduce results. | Log dataset version, source, split method, and sample counts as parameters. Tag runs with data provenance metadata so you can filter by which data was used. |
| Ignoring artifact storage costs | Model files can be gigabytes. Logging every checkpoint from every run to S3 without a lifecycle policy creates unbounded storage costs that only become visible when the cloud bill arrives. | Configure lifecycle policies on your artifact bucket to transition old artifacts to cheaper storage tiers or expire them after a defined retention period. Not every intermediate checkpoint needs to be kept forever. |
| Over-relying on autologging | Autologging captures what the framework knows about, but it cannot capture your domain-specific context: business use case, experiment hypothesis, data source rationale, stakeholder decisions. These are often the most important metadata when reviewing experiments months later. | Use autologging for the mechanical logging of framework parameters and metrics. Supplement it with manual `log_param` calls for business context, experiment rationale, and any metadata that the framework cannot infer. |

## Quiz

**Q1.** Your team retrained a customer support classifier three months after launch, but the new results are worse and nobody can explain why. The old run was trained by a teammate who left, and all you have is a notebook plus a file named `model_final_v3.pkl`. What specific pieces of information should have been tracked to make the original model reproducible, and which MLflow logging calls would have captured them?

<details>
<summary>Answer</summary>
They should have tracked the dataset version, hyperparameters, preprocessing context, random seed, evaluation metrics, and the model artifact itself. In MLflow, that means logging items such as `dataset_version` and `random_seed` with `mlflow.log_param()`, logging outcomes like accuracy and F1 with `mlflow.log_metric()`, and storing the trained model with `mlflow.sklearn.log_model()`. Artifacts such as a confusion matrix or feature importance report should also have been saved with `mlflow.log_artifact()`. The module's core point is that Git alone tracks code, not the full experimental state needed to reproduce a model later.
</details>

**Q2.** An NLP researcher on your team is iterating quickly in PyTorch and keeps forgetting to manually log optimizer settings, loss curves, and checkpoints. She wants the fewest possible code changes while still capturing most training metadata. What is the best feature to use, and what kinds of information will it record automatically?

<details>
<summary>Answer</summary>
She should use MLflow autologging, such as `mlflow.pytorch.autolog()`. According to the module, autologging automatically captures items like model architecture, optimizer settings, loss curves, validation metrics, model checkpoints, and training time. This is the right choice because it reduces manual logging overhead while still recording the majority of useful experiment metadata.
</details>

**Q3.** Your company has a fraud-detection model that passed offline evaluation, but compliance requires a documented promotion path before anything serves live traffic. You want one clear source of truth for which version is still under validation and which version is actually live. How should you use the current MLflow Model Registry workflow to manage this safely?

<details>
<summary>Answer</summary>
You should register the model after training, tag the version with validation metadata such as `validation_status=pending`, update the tag to `validation_status=passed` after testing succeeds, and then assign or move the `champion` alias to that version. The module explains that MLflow's current Registry workflow uses aliases and tags rather than the deprecated fixed stages API. This avoids the "which file is live?" problem because serving systems can load `models:/ModelName@champion` instead of depending on ambiguous folder names.
</details>

**Q4.** A distributed training job is running overnight on a remote GPU server, and product managers want to watch validation accuracy evolve in real time from their laptops. The team also wants built-in dashboards without writing custom visualization scripts. Which platform is the better fit for this workflow, and why?

<details>
<summary>Answer</summary>
Weights & Biases is the better fit because the module highlights its real-time visualization and collaboration strengths. With `wandb.log()`, metrics appear immediately in the dashboard, so teammates can monitor training live and compare runs without building custom plotting tools. This matches W&B's SaaS-first philosophy of instant charts, shared dashboards, and collaborative experiment analysis.
</details>

**Q5.** You need to search over learning rate, batch size, hidden size, and dropout for a text classifier, but you do not want to waste compute finishing clearly bad runs. Which W&B capability should you use, and how does it avoid wasting resources?

<details>
<summary>Answer</summary>
You should use W&B Sweeps. The module explains that Sweeps can define a search space and use methods like Bayesian optimization to choose promising hyperparameter configurations instead of sampling blindly. It also supports early termination with Hyperband, which stops poorly performing runs early and shifts compute toward better candidates.
</details>

**Q6.** Six months from now, your platform team wants to answer a query like: "Show all production-candidate transformer runs from the NLP team trained on dataset v3.2 using A100 GPUs." What experiment organization practice from the module makes this possible?

<details>
<summary>Answer</summary>
A disciplined tagging strategy makes that possible. The module recommends tagging runs with structured metadata such as team, owner, dataset version, model family, model base, GPU type, business use case, and status flags like `production_candidate`. With consistent tags, runs become searchable and comparable instead of disappearing into vague experiment names and folder structures.
</details>

**Q7.** Your organization already uses Git and CI/CD for application code, but model experiments, dataset provenance, and model versions are still managed manually in notebooks and shared folders. Training is repeatable only through individual tribal knowledge. According to the module's maturity model, what level are you at now, and what is the next practical milestone?

<details>
<summary>Answer</summary>
You are at Level 1: DevOps but not MLOps. The module describes this level as having version control and basic CI/CD for code, while ML-specific concerns like experiment tracking and model versioning remain manual. The next practical milestone is Level 2, where experiments are tracked, models are versioned, and automated training pipelines provide reproducibility.
</details>

**Q8.** Your team's MLflow tracking server is currently a single Docker container with a local SQLite database. If that container is deleted, all experiment history and model artifacts are lost. What three infrastructure components does the module identify as essential for a production-grade tracking deployment, and why does each one matter?

<details>
<summary>Answer</summary>
The three essential components are: (1) a dedicated database (PostgreSQL or MySQL) for structured metadata, which provides durability and concurrent access beyond what SQLite offers on a single host; (2) an external object store (S3, GCS, or MinIO) for artifacts, which separates large binary storage from the queryable metadata and allows independent scaling; and (3) an authentication and authorization layer, such as MLflow basic auth/RBAC plus SSO integration where needed, which prevents unauthorized access to experiment data and the model registry. The module also emphasizes backup and disaster recovery for both the database and the object store, since losing experiment history means losing institutional knowledge.
</details>

## Hands-On Exercises

The following three exercises give you hands-on experience with the experiment tracking tools covered in this module. Complete them in order: first set up a local MLflow tracking server and log a simple experiment, then use W&B to visualize a simulated training run in real time, and finally implement the full model registry workflow from training through production deployment.

### Exercise 1: Set Up Local MLflow Tracking
**Task**: Install MLflow on your machine, start a local tracking server, and log your first experiment with parameters and metrics.
**Steps**:

```bash
# Install MLflow
pip install mlflow

# Start the local tracking server
mlflow server --host 0.0.0.0 --port 5000

# In another terminal, run an experiment
python -c "
import mlflow
mlflow.set_tracking_uri('http://localhost:5000')
mlflow.set_experiment('my-first-experiment')
with mlflow.start_run():
    mlflow.log_param('learning_rate', 0.001)
    mlflow.log_metric('accuracy', 0.95)
    print('Run logged successfully!')
"
```

**Success Criteria**: After completing the steps above, verify that your local MLflow setup works correctly by confirming each of the following conditions.
- [ ] MLflow server is running and accessible at http://localhost:5000
- [ ] The experiment "my-first-experiment" appears in the UI
- [ ] The run shows the logged parameter (`learning_rate = 0.001`) and metric (`accuracy = 0.95`)
- [ ] The UI's run detail page loads without errors

Now that you have seen MLflow's local tracking workflow, let us try W&B's real-time visualization approach, which gives you instant feedback during training.

### Exercise 2: Create a W&B Experiment with Real-Time Visualization
**Task**: Set up Weights & Biases, authenticate with your API key, and log a simulated training run that demonstrates real-time metric visualization.
**Steps**:

```bash
# Install and authenticate
pip install wandb
wandb login  # Follow the prompts to get your API key from wandb.ai/authorize

# Run a simulated experiment
python -c "
import wandb
import random

wandb.init(project='my-first-project', name='simulated-training')
for step in range(100):
    # Simulate a loss curve that trends downward with noise
    loss = 1.0 / (1 + step * 0.1) + random.uniform(-0.05, 0.05)
    accuracy = 1.0 - loss + random.uniform(-0.02, 0.02)
    wandb.log({'loss': loss, 'accuracy': accuracy, 'step': step})
wandb.finish()
"
```

**Success Criteria**: Confirm that W&B is configured correctly and the simulated run produced real-time visualizations by checking each of the following conditions.
- [ ] W&B login succeeds and the API key is configured
- [ ] The project "my-first-project" appears in your W&B dashboard
- [ ] The run "simulated-training" shows loss and accuracy curves in real time
- [ ] You can share a link to the run with a teammate

With MLflow tracking and W&B visualization under your belt, the final exercise ties everything together by walking through the complete model lifecycle from training through production deployment.

### Exercise 3: Implement a Full Model Registry Workflow
**Task**: Train a classification model on synthetic data, register it in the MLflow Model Registry, tag its validation status, and assign a serving alias.
**Steps**:

```python
import mlflow
import mlflow.pyfunc
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

# Create a synthetic dataset for the exercise
X, y = make_classification(n_samples=1000, n_features=20, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

mlflow.set_experiment("model-registry-demo")

with mlflow.start_run() as run:
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    accuracy = model.score(X_test, y_test)

    mlflow.log_param("n_estimators", 100)
    mlflow.log_param("random_state", 42)
    mlflow.log_metric("accuracy", accuracy)
    mlflow.sklearn.log_model(model, "model")

    run_id = run.info.run_id

# Register the model
model_uri = f"runs:/{run_id}/model"
registered_model = mlflow.register_model(model_uri, "DemoClassifier")

# Tag validation state, then move the serving alias after review
client = MlflowClient()
client.set_model_version_tag(
    "DemoClassifier",
    registered_model.version,
    "validation_status",
    "passed"
)
client.set_registered_model_alias(
    "DemoClassifier",
    "champion",
    registered_model.version
)

# Load the champion model and verify it works
production_model = mlflow.pyfunc.load_model("models:/DemoClassifier@champion")
test_prediction = production_model.predict(X_test[:5])
print(f"Production model predictions: {test_prediction}")
```

**Success Criteria**:
- [ ] The model is registered in the MLflow Model Registry under the name "DemoClassifier"
- [ ] The registered version has `validation_status=passed`
- [ ] The `champion` alias points to the registered version
- [ ] Loading `models:/DemoClassifier@champion` returns a working model that produces predictions

## Next Module

You now understand experiment tracking and model registry -- the foundation of reproducible ML. Every model you train from this point forward should be logged, tagged, and registered, so that six months from now, you (or your colleagues) can reproduce it, explain it, and improve upon it without archaeological excavation.

[Module 1.7: Data Versioning and Feature Stores](../module-1.7-data-versioning-feature-stores) -- where you will learn how to apply the same systematic tracking discipline to the data side of the ML pipeline: versioning datasets with DVC, managing features with Feast, and ensuring that the data your models were trained on is as reproducible as the models themselves.

## Sources

- [MLflow Documentation](https://mlflow.org/docs/latest/) -- Official documentation covering tracking, projects, models, and registry.
- [Weights & Biases Documentation](https://docs.wandb.ai/) -- Official guides and API reference for experiment tracking, sweeps, and collaboration.
- [MLflow 3.13.0 Release Notes](https://mlflow.org/releases/3.13.0/) -- Official release note for the 2026-05-29 MLflow 3.13.0 release and RBAC/Admin UI additions.
- [MLflow Model Registry Workflows](https://www.mlflow.org/docs/latest/ml/model-registry/workflow/) -- Current Registry guidance, including aliases, tags, environment-specific registered models, and the deprecation of fixed stages.
- [MLflow Authentication with Username and Password](https://mlflow.org/docs/latest/self-hosting/security/basic-http-auth/) -- Official documentation for built-in basic HTTP authentication and the 3.13 RBAC model.
- [MLflow Role-Based Access Control](https://mlflow.org/docs/latest/self-hosting/security/role-based-access-control/) -- Official documentation for workspace-scoped roles, grants, and permission management.
- [MLflow GitHub Repository](https://github.com/mlflow/mlflow) -- Canonical upstream entry point for the open-source project, releases, and community contributions.
- [DVC Documentation](https://dvc.org/doc) -- Official documentation for DVC, the open-source data versioning and experiment tracking tool.
- [W&B Sweeps Guide](https://docs.wandb.ai/guides/sweeps) -- Documentation on hyperparameter optimization with Bayesian search and Hyperband early termination.
- [MLOps: Continuous Delivery and Automation Pipelines in Machine Learning](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning) -- Google Cloud's vendor guidance on ML-specific CI/CD/CT patterns and maturity concepts.
- [The MLflow Project Joins Linux Foundation](https://www.linuxfoundation.org/press/press-release/the-mlflow-project-joins-linux-foundation) -- Press release on MLflow's transition to community governance under the Linux Foundation.
- [2021 Machine Learning Practitioner Survey](https://www.comet.com/site/wp-content/uploads/2022/07/Comet_Report-2021_ML_Practitioner_Survey.pdf) -- Comet/Censuswide survey methodology and results on manual experiment tracking and ML workflow friction.
- [ICLR Reproducibility Challenge 2019](https://github.com/reproducibility-challenge/iclr_2019) -- The formalized effort to replicate accepted ICLR papers, which helped drive adoption of systematic experiment tracking.
- [Hidden Technical Debt in Machine Learning Systems](https://proceedings.neurips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html) -- D. Sculley et al., NeurIPS 2015. Foundational paper on the engineering challenges unique to ML systems.
- [Rules of Machine Learning: Best Practices for ML Engineering](https://developers.google.com/machine-learning/guides/rules-of-ml/) -- Martin Zinkevich, Google. Practical guidance distilled from years of production ML, including Rule 4 on infrastructure and Rule 22 on unused features.
- [Improving Reproducibility in Machine Learning Research](https://arxiv.org/abs/2003.12206) -- Pineau et al., 2020. Overview of the reproducibility challenge in ML research and a checklist for reproducible experiments.
