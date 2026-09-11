---
citations_verified: true
title: "Notebooks to Production for ML/LLMs"
slug: ai-ml-engineering/mlops/module-1.11-notebooks-to-production-for-ml-llms
sidebar:
  order: 612
---

> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 2-3 hours

**Reading Time**: 2-3 hours

**Prerequisites**: Notebooks, Scripts, and Project Layouts; Experiment Tracking; ML Pipelines; Model Serving; basic Python packaging; basic YAML configuration.

## Learning Outcomes

By the end of this module, you will be able to:

- **Refactor** notebook-only ML or LLM work into reviewable Python modules with explicit inputs, stable functions, and repeatable entry points.
- **Diagnose** whether a notebook is still a useful exploration artifact or has become a production risk through hidden state, manual ordering, duplicated logic, or unclear lineage.
- **Design** a minimal production handoff that separates training, evaluation, artifact governance, and serving contracts without overbuilding an enterprise platform.
- **Evaluate** whether a model or LLM workflow is ready for promotion by checking reproducibility, baseline comparison, dataset or prompt lineage, and rollback expectations.
- **Compare** notebook, script, pipeline, and service responsibilities so that each layer owns the right part of the ML lifecycle.

## Why This Module Matters

A data scientist has a promising notebook open at midnight, a product leader is asking for a demo in the morning, and the notebook finally produces the metric everyone wanted. Two weeks later, that same notebook is running behind a scheduled job, a copied cell has become a production dependency, and nobody can reproduce the model that is now influencing customer-facing decisions.

The failure does not look dramatic at first. The team still has code, metrics, charts, and model artifacts, so the project appears alive and technical. The real problem is that the workflow has no clean boundary between discovery and delivery, which means a lucky result can become an operational system before anyone has defined what should be reviewed, reproduced, monitored, or rolled back.

This module teaches the practical bridge from notebooks to production for both classic ML systems and LLM applications. The goal is not to shame notebooks or replace exploration with bureaucracy; the goal is to protect useful discovery by moving durable logic into software shapes that other engineers can run, test, compare, deploy, and repair under pressure.

A beginner should leave with a clear rule of thumb: notebooks are excellent for learning and investigation, but production needs explicit inputs and repeatable execution. A senior practitioner should leave with a sharper design lens: promotion is not a file copy or an API wrapper, but a controlled handoff across code ownership, evaluation evidence, artifact governance, and serving behavior.

## Core Content

## 1. The Boundary Problem: Lab Bench Versus Factory Floor

A notebook is a lab bench because it lets the learner touch the data, change one variable, plot a result, and ask the next question quickly. That is exactly why notebooks are so valuable during early ML and LLM work, where the team often does not yet know which features, prompts, labels, retrieval settings, or evaluation slices matter.

A production workflow is closer to a factory floor because it must produce a trustworthy result under repeatable conditions. The production concern is not whether one person can make the code work on Tuesday afternoon; the concern is whether another engineer can run the workflow from a clean checkout, understand the inputs, inspect the outputs, and explain why a specific artifact is allowed to serve users.

The central transition in this module is therefore not "notebook bad, script good." The transition is from hidden state to explicit state, from personal memory to reviewable code, from manual cell order to reproducible execution, and from interesting output to governed promotion.

A notebook may discover the workflow, but the notebook should not remain the workflow once other people depend on the result. That distinction matters because discovery rewards speed and looseness, while production rewards clarity and constraint.

```text
+---------------------------+        +----------------------------+
| Notebook Exploration      |        | Production Workflow        |
|---------------------------|        |----------------------------|
| Manual cell execution     | -----> | Command or pipeline entry  |
| Local variables in memory | -----> | Explicit config and inputs |
| Informal plots and notes  | -----> | Versioned metrics reports  |
| Hardcoded paths           | -----> | Parameterized data sources |
| One-person understanding  | -----> | Reviewable team ownership  |
+---------------------------+        +----------------------------+
```

The first production risk is hidden execution order. A notebook can contain correct-looking code while still depending on cells that were run earlier, variables that no longer appear near the final result, or local files that only exist on one machine.

The second production risk is copied business logic. When feature engineering, prompt construction, or label cleanup is copied from a notebook into several scripts, a later fix can land in one path and miss the others, creating different behavior between training, evaluation, and serving.

The third production risk is weak evidence. A notebook that prints good-looking examples or a single metric does not automatically prove that a model is better than the baseline, safer for edge cases, cheaper to serve, or acceptable under realistic latency.

The fourth production risk is a missing contract. A notebook can call a model function and display responses, but a service must define request shape, validation rules, error behavior, timeout limits, concurrency expectations, and rollout boundaries.

> **Stop and think:** If your current notebook vanished but its exported model file remained, could another engineer explain which data, config, prompt, code version, and evaluation result produced that artifact? If the answer is no, the team has an artifact without lineage.

The right response is not to rewrite everything at once. The right response is to identify the parts of the notebook that have become durable, move those parts into modules, and leave the notebook focused on analysis, explanation, visualization, and error inspection.

This is where many teams overcorrect. They build a full platform before they have a stable workflow, or they keep everything in notebooks because platform work sounds heavy. The practical middle path is a small, disciplined project layout with functions, scripts, configs, outputs, reports, and clear promotion rules.

The four boundaries below are the minimum boundaries that keep notebook-born work from turning into operational confusion. They apply to tabular models, computer vision models, embedding systems, RAG prototypes, fine-tuning jobs, and LLM orchestration workflows.

The first boundary separates exploration from reproducible execution. Exploration asks what might work; reproducible execution asks whether the same inputs and code can create the same artifact again without personal memory.

The second boundary separates training from evaluation. Training creates a candidate; evaluation decides whether that candidate is acceptable compared with a baseline, a threshold, or a previous release.

The third boundary separates offline inference from online serving. Offline inference can be slow, manual, and investigative; online serving must validate requests, meet latency expectations, handle failures, and expose behavior that operations teams can observe.

The fourth boundary separates artifact creation from artifact governance. Artifact creation answers "what file did the run produce," while governance answers "which artifact is approved, why was it approved, and what happens if it disappoints in production."

A production-minded team draws these boundaries early enough that promotion does not depend on heroic archaeology. The team should not need to open a notebook, scroll through old cells, and infer which local variable mattered most during the successful run.

The maturity path is usually gradual. Stage one is notebook-only exploration, stage two is notebooks importing reusable code, stage three is scripted experiments with tracked outputs, and stage four is a production candidate with explicit lineage and serving expectations.

Stage one is not a failure when the team is still learning. It becomes a failure when the notebook becomes the system of record, because system-of-record work needs review, reproducibility, and ownership beyond the original author.

Stage two is the healthiest early transition point. The notebook still helps the data scientist reason about the problem, but durable logic such as loading, cleaning, prompt building, training, evaluation, and inference begins to live under `src/`.

Stage three turns important runs into commands or pipeline steps. A run can start from a config file, write metrics to a known location, and produce artifacts that can be compared without opening the notebook.

Stage four is where a candidate becomes eligible for production review. The team can show the model lineage, baseline comparison, acceptance criteria, serving contract, and rollback path before traffic moves.

A useful senior-level question is not "have we eliminated notebooks." The better question is "does each notebook now depend on the production code path instead of secretly defining it."

## 2. A Practical Project Shape for the Transition

A good transition layout gives the team a place for exploration without letting exploration own the system. The layout should be boring enough that a new engineer can guess where training, evaluation, inference, configs, outputs, reports, and tests live.

The layout below is intentionally small. It works for a learner project, a small startup, or a platform team proving a new ML workflow before choosing larger orchestration tools.

```text
ml-project/
├── README.md
├── pyproject.toml
├── configs/
│   ├── train.yaml
│   ├── eval.yaml
│   └── serve.yaml
├── notebooks/
│   ├── 01-exploration.ipynb
│   └── 02-error-analysis.ipynb
├── src/
│   └── project_name/
│       ├── __init__.py
│       ├── data.py
│       ├── features.py
│       ├── prompts.py
│       ├── training.py
│       ├── evaluation.py
│       └── inference.py
├── scripts/
│   ├── train.py
│   ├── evaluate.py
│   └── inspect_candidate.py
├── tests/
│   ├── test_features.py
│   └── test_prompts.py
├── outputs/
│   └── .gitkeep
└── reports/
    └── .gitkeep
```

The `notebooks/` directory keeps exploratory work visible and versioned, but the notebook should become a consumer of reusable modules rather than a container for all logic. A notebook can still contain markdown explanations, charts, manual inspection, and investigation notes.

The `src/` directory holds durable behavior. If a function is needed by training and serving, it belongs under `src/` so both paths import the same implementation instead of copying a cell.

The `scripts/` directory holds command-line entry points. A script should be thin: parse config, call library functions, write outputs, and exit with a clear status.

The `configs/` directory stores parameters that should not be hidden in cell edits. Dataset paths, feature flags, prompt templates, model names, thresholds, and artifact destinations should be visible before the run starts.

The `outputs/` directory stores generated model artifacts, embeddings, indexes, or serialized state. In a real platform, these may move to object storage or a model registry, but the local structure should still teach predictable artifact ownership.

The `reports/` directory stores metrics, evaluation summaries, slice analysis, qualitative review notes, and candidate promotion evidence. A report should help a reviewer understand whether the artifact deserves the next environment.

The `tests/` directory protects logic that is easy to break silently. Feature transforms, prompt formatting, request validation, and evaluation calculations are especially worth testing because a tiny change can invalidate comparisons.

A small layout like this teaches the most important MLOps habit: [code, config, data reference, output, and decision evidence should be separable](https://learn.microsoft.com/en-us/azure/machine-learning/concept-model-management-and-deployment?view=azureml-api-2). When those are separable, automation becomes possible later.

The same shape works for LLM applications, but the module names may shift. For an LLM system, `features.py` may become `retrieval.py`, `prompts.py` becomes central, and `evaluation.py` may combine exact-match metrics, rubric scoring, cost tracking, and human review sampling.

The point is not the exact directory names. The point is that the notebook should no longer be the only place where the system can be understood.

| Responsibility | Notebook Stage | Production-Oriented Stage | Review Question |
|---|---|---|---|
| Data access | Path edited in a cell before running | Dataset source and version named in config | Can another run use the same data reference without guessing? |
| Feature or prompt logic | Built interactively across several cells | Shared function imported by training, evaluation, and serving | Does one implementation define behavior across all paths? |
| Training | Executed by running cells in order | Started by a command or pipeline step | Can the run start from a clean process with explicit parameters? |
| Evaluation | Manual spot checks and ad hoc plots | Repeatable report with baseline comparison | Would a reviewer know whether the candidate is better enough? |
| Serving | Function call from a notebook cell | Request contract with validation and failure behavior | Can the service handle bad input, latency pressure, and rollback? |
| Promotion | Someone copies the newest artifact | Candidate approved only with lineage and evidence | Can the team explain why this artifact is allowed to serve traffic? |

This table is useful because it shows that the migration is not primarily about moving files. The real migration is moving responsibility from memory and habit into interfaces that can be reviewed.

A learner often asks which cells should move first. The answer is the cells with the most operational consequence, not necessarily the longest cells or the cells that look most polished.

Move data loading early because a model trained on the wrong dataset version can produce convincing metrics with no trustworthy meaning. Data paths, filters, joins, and label rules should not remain hidden in exploratory state.

Move feature generation or prompt construction early because these functions must match between training, evaluation, and serving. If the model learned from one transformation but serving uses another, the production system is already inconsistent.

Move evaluation early because promotion should depend on repeatable evidence. A model that cannot be evaluated from a clean command is not ready for production discussion, even when its notebook charts look impressive.

Move inference wrappers early because they define the contract between the model and the rest of the application. The wrapper should make input validation, preprocessing, prediction, postprocessing, and error behavior visible.

Keep exploratory plots in notebooks longer because plots are often used to think, not to operate. The notebook remains an excellent place for residual analysis, prompt failure review, class imbalance exploration, and explanation for stakeholders.

Keep manual error analysis in notebooks longer because human judgment is often needed before the system design stabilizes. The important guardrail is that manual analysis should inspect outputs from reproducible runs, not create the only outputs that matter.

> **Stop and think:** Which cell in your most important notebook would create the most damage if it were copied incorrectly into a script? That cell is a strong candidate for extraction into a tested module before the next promotion conversation.

A useful extraction rule is simple: if logic must be rerun exactly and trusted by other people, it belongs in code rather than only in a cell. If logic is there to explain, inspect, or explore, it can stay in a notebook while it remains exploratory.

This rule also prevents premature engineering. You do not need to turn every plot into a package function, and you do not need a pipeline scheduler for a workflow that is still changing daily.

The standard is not ceremony. The standard is that another engineer can reproduce the important run and understand the decision trail without asking the original notebook author to remember the magic sequence.

## 3. Worked Example: Extracting a Notebook Cell Into a Module

This worked example shows a concrete extraction from input to transformation to solution. The example is intentionally small so the mechanics are visible, but the same pattern scales to larger ML feature code and LLM prompt orchestration code.

The scenario is a support-ticket classifier. A notebook cell cleans ticket text, builds a simple feature dictionary, trains a small classifier, prints accuracy, and saves a model file.

The team wants to schedule training, compare candidates, and eventually serve predictions from an API. Before doing any scheduling, the team extracts text normalization and feature building because those transformations must match across training, evaluation, and serving.

### Input: the notebook cell that works only in context

The notebook cell below appears harmless because it is short and produces a useful result. The production risk is that it mixes data assumptions, feature logic, training, evaluation, and artifact writing in one execution context.

```python
# notebooks/01-exploration.ipynb cell
import json
import re
from pathlib import Path

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.pipeline import make_pipeline

rows = [json.loads(line) for line in Path("../data/tickets.jsonl").read_text().splitlines()]

def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())

examples = []
labels = []

for row in rows:
    text = clean_text(row["title"] + " " + row["body"])
    examples.append({
        "contains_refund": "refund" in text,
        "contains_login": "login" in text,
        "word_count": len(text.split()),
    })
    labels.append(row["label"])

model = make_pipeline(DictVectorizer(), LogisticRegression(max_iter=200))
model.fit(examples, labels)

predictions = model.predict(examples)
print("accuracy", accuracy_score(labels, predictions))

Path("../outputs").mkdir(exist_ok=True)
Path("../outputs/ticket_model.json").write_text("placeholder artifact")
```

This cell is not production-ready even if it reports a strong metric. It trains and evaluates on the same examples, uses a hardcoded relative path, writes a placeholder artifact, and defines feature logic in a location the serving path cannot safely import.

The goal of the extraction is not to make the system fancy. The goal is to separate stable transformations from exploratory execution so training, evaluation, and serving can reuse the same behavior.

### Transformation: decide what each responsibility becomes

The first transformation step is to name the responsibilities hidden inside the cell. Naming responsibilities prevents the common mistake where the same messy cell is moved wholesale into a script with a different file extension.

| Notebook Responsibility | Production Location | Reason for the Move |
|---|---|---|
| Text cleanup with regular expressions | `src/ticket_model/features.py` | Training and serving must normalize text identically, or model behavior will drift. |
| Feature dictionary construction | `src/ticket_model/features.py` | Feature names and meanings are part of the model contract and deserve tests. |
| Dataset loading from JSONL | `src/ticket_model/data.py` | Data paths and parsing rules should be explicit, reusable, and easy to validate. |
| Model training | `src/ticket_model/training.py` | Training should be callable from scripts or pipelines without notebook state. |
| Metric calculation | `src/ticket_model/evaluation.py` | Promotion evidence should be generated by repeatable evaluation code. |
| Manual inspection and charts | `notebooks/02-error-analysis.ipynb` | Analysis remains valuable, but it should inspect outputs from reproducible runs. |

The second transformation step is to define function boundaries. A good extracted function should receive explicit inputs, return explicit outputs, and avoid reading global notebook state.

For this example, `clean_text(text)` and `build_features(title, body)` are the first functions to extract. They are small enough to test and important enough that duplication would create real production risk.

The third transformation step is to replace hidden path choices with config. The training command can still be simple, but it should know where the dataset lives, where reports go, and where artifacts should be written.

The fourth transformation step is to leave the notebook as a consumer. After extraction, the notebook imports `build_features` and uses it for analysis, which means exploratory work now exercises the same transform used by training and serving.

### Solution: extracted module with a runnable command

The extracted feature module is small, but it changes the ownership model. Feature behavior is now versioned code that can be imported, tested, and reviewed.

```python
# src/ticket_model/features.py
import re


def clean_text(text: str) -> str:
    lowered = text.lower()
    letters_and_numbers = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    return " ".join(letters_and_numbers.split())


def build_features(title: str, body: str) -> dict[str, int | bool]:
    text = clean_text(f"{title} {body}")
    words = text.split()
    return {
        "contains_refund": "refund" in words,
        "contains_login": "login" in words,
        "word_count": len(words),
    }
```

The dataset loader makes data parsing explicit. In a larger system, this is where you would add schema validation, dataset version metadata, or checks that required fields are present.

```python
# src/ticket_model/data.py
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: str) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    return [json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip()]
```

The training module receives a dataset path and returns a trained model plus metrics. Notice that the code imports `build_features`; this is the design move that prevents training and serving from drifting apart.

```python
# src/ticket_model/training.py
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline, make_pipeline

from ticket_model.data import load_jsonl
from ticket_model.features import build_features


def train_ticket_classifier(dataset_path: str) -> tuple[Pipeline, dict[str, float]]:
    rows = load_jsonl(dataset_path)
    examples = [build_features(row["title"], row["body"]) for row in rows]
    labels = [row["label"] for row in rows]

    model = make_pipeline(DictVectorizer(), LogisticRegression(max_iter=200))
    model.fit(examples, labels)

    predictions = model.predict(examples)
    metrics = {"training_accuracy": float(accuracy_score(labels, predictions))}
    return model, metrics
```

The script becomes a thin entry point. It is intentionally uninteresting because the reusable behavior lives in `src/`, where tests and services can import it.

```python
# scripts/train.py
import argparse
import json
from pathlib import Path

import joblib
import yaml

from ticket_model.training import train_ticket_classifier


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text())
    model, metrics = train_ticket_classifier(config["dataset_path"])

    artifact_dir = Path(config["artifact_dir"])
    report_dir = Path(config["report_dir"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, artifact_dir / "ticket_classifier.joblib")
    (report_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

The config makes the run visible before execution. A reviewer can now see which dataset and output locations the training run will use without opening a notebook.

```yaml
# configs/train.yaml
dataset_path: data/tickets.jsonl
artifact_dir: outputs/ticket-classifier-candidate
report_dir: reports/ticket-classifier-candidate
```

A minimal test protects the extracted transformation. This test is not a replacement for model evaluation, but it catches a class of bugs where feature behavior changes silently.

```python
# tests/test_features.py
from ticket_model.features import build_features, clean_text


def test_clean_text_removes_punctuation_and_normalizes_spaces() -> None:
    assert clean_text("Refund!!!   LOGIN?") == "refund login"


def test_build_features_marks_known_terms_and_counts_words() -> None:
    features = build_features("Refund request", "Cannot login after reset.")
    assert features["contains_refund"] is True
    assert features["contains_login"] is True
    assert features["word_count"] == 6
```

The notebook can now shrink. Instead of defining production logic, it imports the function and uses it for inspection, which keeps exploration connected to the real code path.

```python
# notebooks/02-error-analysis.ipynb cell
from ticket_model.features import build_features

sample = {"title": "Refund request", "body": "Cannot login after reset."}
build_features(sample["title"], sample["body"])
```

The command is now reproducible from a clean process. It does not depend on a notebook kernel, manually run cells, or a variable that happens to be left in memory.

```bash
.venv/bin/python scripts/train.py --config configs/train.yaml
```

This example is deliberately modest, but it demonstrates the core pattern: extract one risky cell into one module, add one script that calls it, add one config that controls it, and add one test that protects it. That is how notebook work starts becoming software without demanding a large platform rewrite.

The same pattern works for LLM prompt construction. If a notebook cell builds a prompt template, inserts retrieved passages, calls a model, and manually grades answers, extract prompt assembly and retrieval formatting first because those functions must match across evaluation and serving.

For example, `build_support_prompt(question, passages)` should live in `src/project_name/prompts.py`, while evaluation code can call it against a labeled set and serving code can call it for live requests. The notebook may still compare outputs, but it should not be the only definition of the prompt contract.

The senior-level lesson is that extraction is not just code movement. Extraction is a design decision about which behavior must become stable, which behavior must remain exploratory, and which boundary lets the team compare candidates honestly.

> **Stop and think:** In the worked example, what would happen if serving used a slightly different `clean_text` function from training? The model might receive features during serving that do not match the training distribution, and debugging would be harder because both paths could look individually reasonable.

A learner can practice this pattern with any notebook by drawing three columns: current cell, durable responsibility, and destination module. The moment the same responsibility appears in multiple destinations, the design should pause and extract a shared function.

## 4. Separating Training, Evaluation, and Serving

Training, evaluation, and serving often appear together in a notebook because that is the fastest way to learn. Production systems separate them because each path answers a different question and has a different failure mode.

Training asks whether code and data can produce a candidate artifact. Evaluation asks whether the candidate artifact is good enough under defined criteria. Serving asks whether the approved artifact can handle real requests with acceptable behavior.

When those paths are mixed, the team can accidentally tune against the evaluation set, overwrite the artifact being reviewed, or deploy a model whose apparent success came from informal inspection rather than repeatable evidence.

A clean training path should produce a candidate and record enough context to reproduce it. At minimum, record code version, config, dataset reference, feature or prompt version, artifact location, and training metrics.

A clean evaluation path should compare the candidate to a baseline. The baseline may be the previous production model, a simple heuristic, a zero-shot prompt, a smaller model, or a business threshold, but it must be named.

A clean serving path should consume only approved artifacts. Serving should not retrain, mutate evaluation thresholds, or contain hidden feature edits that differ from training.

```text
+--------------------+     +--------------------+     +----------------------+
| Training Path      |     | Evaluation Path    |     | Serving Path         |
|--------------------|     |--------------------|     |----------------------|
| Reads train config |     | Reads eval config  |     | Reads serve config   |
| Loads train data   |     | Loads eval data    |     | Accepts requests     |
| Builds candidate   | --> | Compares baseline  | --> | Uses approved model  |
| Writes artifact    |     | Writes report      |     | Returns responses    |
| Records lineage    |     | Gates promotion    |     | Emits telemetry      |
+--------------------+     +--------------------+     +----------------------+
```

The arrows in this diagram represent governance, not automatic deployment. A training artifact should become an evaluation candidate, and an evaluation candidate should become a serving candidate only when the evidence supports promotion.

For classic ML, evaluation often includes metrics such as precision, recall, ROC AUC, calibration, slice performance, data drift checks, and error analysis. The correct metrics depend on the business problem, but the evaluation should be repeatable.

For LLM systems, evaluation may include exact matching, semantic similarity, rubric-based grading, retrieval relevance, groundedness checks, refusal behavior, latency, token cost, and human review sampling. LLM evaluation is rarely a single score, so the report should make trade-offs visible.

For RAG systems, the team must separate retrieval changes from generation changes. If the prompt, retrieval index, chunking method, embedding model, and LLM all change in the same notebook, the team cannot explain which change improved or harmed the result.

For fine-tuning systems, the team must separate training data changes from model configuration changes. A better score may come from cleaner labels, more examples, a changed prompt format, different hyperparameters, or leakage into the evaluation set.

The training script should not decide promotion alone. It can write metrics, but [a promotion decision should compare those metrics against thresholds and baselines that were agreed before the candidate was produced](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning).

The evaluation script should not quietly train a new model. If evaluation mutates the artifact it is judging, the report no longer describes the candidate that would be served.

The serving code should not import from notebooks. If serving imports notebook-derived behavior, operations cannot rely on normal review, testing, dependency management, or reproducible builds.

A minimal promotion report can be a JSON file and a markdown summary. The format matters less than the presence of evidence that another engineer can inspect.

```json
{
  "candidate_id": "ticket-classifier-2026-04-26-a",
  "dataset_reference": "tickets-jsonl-2026-04-snapshot",
  "code_reference": "git-sha-recorded-by-ci",
  "baseline_id": "ticket-classifier-previous",
  "metrics": {
    "candidate_accuracy": 0.91,
    "baseline_accuracy": 0.86
  },
  "promotion_decision": "hold-for-slice-review"
}
```

The example decision says `hold-for-slice-review` instead of `promote` because a single aggregate metric is often insufficient. A model can improve average accuracy while hurting a critical customer segment, language, region, or request type.

This is where senior judgment matters. Production readiness is not just a high score; it is a defensible explanation of what changed, which risks remain, and what the team will observe after deployment.

The serving contract is the next boundary. Before building an API, the team should [define the request, response, validation rules, failure behavior, timeout target, model versioning behavior, and rollback mechanism](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2).

A serving contract for the ticket classifier might say that the request contains `title` and `body`, both must be non-empty strings, the response contains `label`, `confidence`, and `model_version`, and invalid requests return a structured client error.

A serving contract for an LLM assistant might say that the request contains a user question and optional conversation context, retrieval must return citations for grounded answers, responses must include refusal reasons when policy blocks an answer, and timeouts return a fallback message.

The contract forces the team to face production behavior before traffic arrives. It prevents the common mistake where someone wraps the notebook's final function in a web framework and discovers validation, cost, latency, and failure handling only after users depend on it.

| Serving Concern | Notebook Behavior | Production Requirement |
|---|---|---|
| Input validation | Assumes the author passes reasonable examples | Rejects or normalizes malformed requests predictably before model execution. |
| Latency | Waits as long as the experiment needs | Sets timeout targets and measures slow paths before rollout. |
| Concurrency | Runs one manual call at a time | Handles multiple requests without shared mutable state leaking between calls. |
| Versioning | Uses whichever model file the author loaded | Identifies the exact approved model or prompt version used for every response. |
| Failure handling | Displays an exception in the cell output | Returns structured errors or fallbacks that callers can handle safely. |
| Observability | Relies on visible notebook output | Emits logs, metrics, traces, and evaluation hooks suitable for operations. |

A team does not need Kubernetes, a service mesh, or a large model registry to start practicing these boundaries. Those tools may become useful later, but the first boundary is architectural discipline inside the project.

The learner should notice the progression: first make the behavior importable, then make the run repeatable, then make evaluation comparable, then make serving contractual, and only then consider promotion automation.

That sequence matters because automating a bad handoff only makes the bad handoff faster. A scheduled notebook that writes ungoverned artifacts is not an MLOps system; it is a faster way to accumulate unclear production risk.

## 5. Artifact Governance and Promotion Readiness

An artifact is not production-ready just because it exists. A production candidate needs lineage, evaluation, ownership, and rollback expectations because real systems fail in ways that are not visible during a successful notebook run.

Lineage means the team can answer how the artifact was produced. The answer should include [code reference, config, data reference, feature or prompt version, training command, evaluation command, and output location](https://learn.microsoft.com/en-us/azure/machine-learning/concept-model-management-and-deployment?view=azureml-api-2).

Evaluation means the team can explain why the artifact is better, safer, cheaper, faster, or otherwise preferable to the baseline. The answer should include metrics, slices, known weaknesses, and acceptance criteria.

Ownership means the team knows who can modify the workflow, approve promotion, investigate incidents, and decide whether a rollback is needed. Without ownership, a model can become critical infrastructure while still being treated like a personal experiment.

Rollback means the team knows how to stop serving the candidate if it behaves badly. Rollback may be as simple as switching a config back to the previous artifact, but the path must exist before deployment pressure rises.

A minimal production handoff is enough for many small teams. The notebook proves the idea, reusable logic moves into `src/`, configs replace hidden values, scripts produce tracked runs, evaluation compares against a baseline, and only approved artifacts move toward serving.

The minimum does not require a large platform. It requires a habit: every candidate should be explainable without reopening the notebook kernel that created it.

For an ML classifier, candidate evidence may include [dataset snapshot, training config, aggregate metrics, per-class metrics, confusion matrix, baseline comparison, and a short note about observed failure modes](https://huggingface.co/docs/hub/main/model-cards).

For an LLM RAG system, candidate evidence may include prompt version, retrieval index version, embedding model, evaluation set, groundedness checks, answer quality rubric, latency, token cost, and examples of failures that remain unacceptable.

For a fine-tuned LLM, candidate evidence may include training corpus reference, data cleaning rules, base model, fine-tuning config, validation results, safety evaluation, cost estimate, and fallback plan if the model regresses.

The promotion decision should be a gate, not a feeling. A gate can be lightweight, but it should say what must be true before the artifact moves closer to users.

```yaml
candidate_gate:
  required:
    - training_config_recorded
    - dataset_reference_recorded
    - baseline_comparison_recorded
    - evaluation_report_written
    - serving_contract_reviewed
    - rollback_path_documented
  decision_options:
    - reject
    - hold_for_more_evidence
    - approve_for_shadow_test
    - approve_for_limited_rollout
```

This gate teaches a crucial habit: production readiness has stages. A candidate might be rejected, held for more evidence, [approved for shadow testing, or approved for limited rollout, and those are different decisions](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2).

Shadow testing means the system runs the candidate without affecting user-visible results. It is useful when offline evaluation is promising but the team needs live traffic characteristics, latency data, or distribution checks.

Limited rollout means a small percentage of traffic or a narrow user segment receives the candidate. It is useful only when rollback is ready and the team knows which signals would trigger intervention.

Full rollout should come after the team has evidence that the candidate behaves acceptably under realistic conditions. A full rollout is not the first time the team learns whether the model can survive production traffic.

Governance should also protect against baseline drift. If the team keeps changing the baseline casually, every new candidate can look impressive against a weak or forgotten comparison.

A stable baseline gives improvement a reference point. The baseline might be the current production model, a simple rules system, a previous prompt, or a documented manual workflow, but it should be named and preserved.

Governance also protects against prompt drift in LLM systems. A prompt may look like text, but in production it behaves like code because small wording changes can alter output quality, safety behavior, latency, and cost.

The same is true for retrieval settings. Chunk size, overlap, embedding model, filtering rules, reranking, and citation formatting are not incidental details; they are part of the system that must be versioned and evaluated.

Senior teams treat these details as controlled inputs rather than notebook comments. That does not remove experimentation; it makes experimentation comparable.

A practical promotion review can ask eight questions before approving a candidate. Can the run start from a clean environment, are inputs explicit, is the dataset or prompt set versioned, is the baseline named, are metrics and artifacts tracked, can another engineer reproduce the result, is the serving contract defined, and is rollback possible.

If several answers are unclear, deployment is not the next step. The next step is usually one round of extraction, config cleanup, evaluation hardening, or report writing.

This is not bureaucracy for its own sake. It is the difference between "the notebook worked once" and "the team can operate this system when it matters."

## 6. What Changes for LLM Workflows

LLM systems make the notebook-to-production gap sharper because behavior is spread across prompts, retrieval, model selection, tool calls, safety rules, cost controls, and human expectations. A notebook can hide those interactions behind a few convenient cells.

Prompt changes are especially deceptive because they look cheap. A single phrase can improve one demo example while harming another category, increasing token cost, changing refusal behavior, or making citations less reliable.

Retrieval changes are also easy to mix up with generation changes. If the team changes chunking, embedding, reranking, prompt wording, and model version at once, the notebook may show better answers without explaining which change mattered.

LLM evaluation is often weaker than classic ML evaluation because teams rely on a few handpicked examples. Manual inspection is useful, but it should be organized into scenarios, rubrics, regression sets, and failure categories.

Cost and latency often matter earlier for LLM systems than for small classic models. A prompt that produces better answers but doubles token use or adds a slow reranking step may still be unacceptable for production.

The production handoff for an LLM system usually needs at least three separate code paths. Prompt or orchestration logic defines how inputs become model calls, evaluation logic judges outputs against scenarios, and serving logic handles real requests with validation and fallbacks.

A RAG system may need a fourth path for index building. Index construction should not be hidden inside the same notebook that evaluates answers, because retrieval corpus changes must be versioned and reproducible.

```text
+---------------------+       +---------------------+
| Index Build Path    |       | Prompt Path         |
|---------------------|       |---------------------|
| Reads source docs   |       | Builds instructions |
| Chunks content      |       | Inserts context     |
| Creates embeddings  |       | Formats user input  |
| Writes index version|       | Calls model client  |
+---------------------+       +---------------------+
          |                               |
          v                               v
+---------------------+       +---------------------+
| Evaluation Path     |       | Serving Path        |
|---------------------|       |---------------------|
| Runs scenario set   |       | Validates requests  |
| Scores groundedness |       | Enforces timeouts   |
| Measures cost       |       | Returns response    |
| Compares baseline   |       | Emits telemetry     |
+---------------------+       +---------------------+
```

The diagram separates paths because each path changes at a different rate. Prompt edits may happen daily during exploration, index builds may happen on corpus updates, evaluation may run on every candidate, and serving should change cautiously.

An LLM notebook can remain useful for inspecting bad answers. The notebook should load a candidate report, sample failures, display retrieved passages, and help the team decide what to investigate next.

The notebook should not be the only place where prompt assembly, retrieval formatting, tool schemas, evaluation rubrics, or serving fallbacks are defined. Those pieces need versioned code and review because they shape production behavior.

A useful senior-level test is to ask whether the team can attribute an LLM quality change. If the team cannot say whether improvement came from the prompt, the retriever, the model, the evaluation data, or the serving wrapper, the system is not yet production-ready.

For LLMs, the serving contract should also address cost limits and failure modes. The contract may define maximum context length, timeout behavior, fallback when retrieval returns no useful passages, and how the system handles model provider errors.

The contract should define output obligations. If answers require citations, the response schema should include citations; if refusals are possible, the response should distinguish refusal from system failure; if tools are used, tool results should be traceable.

LLM systems also benefit from regression examples. A prompt change should be tested against examples that previously failed, examples that previously succeeded, and examples that represent risky user behavior.

This is how the notebook remains part of a mature workflow. It becomes an analysis surface over reproducible runs rather than a private control panel for production behavior.

## Did You Know?

- **Notebook execution order can invalidate evidence:** A notebook may display a successful result even when a clean restart would fail, so restart-and-run-all is a useful early reproducibility check before extracting code.

- **Prompts behave like production code in LLM systems:** A prompt change can alter accuracy, safety behavior, cost, latency, and citation quality, which means important prompts deserve versioning and review.

- **Baselines protect teams from self-deception:** A candidate that feels better during manual inspection may still underperform a simple previous version on edge cases, slices, or operational constraints.

- **Small handoffs can be enough:** A team can reach a credible MLOps baseline with reusable modules, explicit configs, repeatable scripts, tracked reports, and promotion rules before adopting larger platform tools.

## Common Mistakes

| Mistake | What Goes Wrong | Better Practice |
|---|---|---|
| Scheduling a notebook as production | The job depends on hidden state, manual cell order, local paths, and weak observability when failures occur outside the author’s environment. | Extract durable logic into modules, create thin scripts or pipeline steps, and keep notebooks for exploration and analysis. |
| Copying cells into several scripts | Training, evaluation, and serving drift apart because bug fixes and feature changes land in one copy but not the others. | Put shared feature, prompt, and inference logic under `src/` and have every entry point import the same implementation. |
| Promoting without a named baseline | The team cannot defend whether the candidate is actually better, because improvement is judged against memory or selective examples. | Preserve a baseline artifact or prompt, run a repeatable comparison, and record the decision evidence before promotion. |
| Mixing training and evaluation data | Metrics look strong because the model is judged on examples it already learned from, which hides real generalization risk. | Define separate data references for training and evaluation, and make evaluation read-only with respect to the candidate. |
| Wrapping notebook inference as an API | The service lacks validation, timeouts, versioning, fallback behavior, and operational telemetry needed for real user traffic. | Define a serving contract before deployment and implement a service path that consumes approved artifacts only. |
| Treating LLM spot checks as evaluation | A few pleasing answers hide regressions in groundedness, refusal behavior, cost, latency, or important user scenarios. | Build scenario-based evaluation sets with rubrics, baseline comparisons, and representative failure categories. |
| Overbuilding the platform too early | The team spends weeks on infrastructure while the task, data path, prompt, or evaluation criteria are still unstable. | Start with modules, configs, scripts, tests, and reports, then add orchestration or registries once the workflow is stable. |

## Quiz

**Q1.** Your team has a notebook that trains a fraud model, evaluates it, and exports a file. It only works when the author runs cells in a remembered order after editing three paths near the top. A manager wants to schedule that notebook nightly. What should you change before scheduling anything?

<details>
<summary>Answer</summary>

The workflow is still exploratory because it depends on hidden notebook state, manual path edits, and remembered execution order. Before scheduling it, extract durable logic into modules, move paths and thresholds into config, create command-line training and evaluation entry points, and make the run reproducible from a clean process. Scheduling the notebook first would automate the weak boundary instead of fixing it.

</details>

**Q2.** A notebook contains prompt construction, retrieval calls, model invocation, manual answer grading, and a few charts. The team changes the prompt and chunking strategy at the same time, then sees better answers on several examples. How should you redesign the workflow so the team can explain what improved?

<details>
<summary>Answer</summary>

Separate prompt assembly, retrieval/index configuration, evaluation, and serving into distinct code paths with explicit versions. Run one controlled change at a time when possible, compare against a named baseline, and record metrics or rubric results for a fixed scenario set. Without that separation, the team cannot attribute improvement to the prompt, retrieval, model behavior, or evaluation sample.

</details>

**Q3.** A data scientist extracts `build_features()` from a notebook into `src/project/features.py`, but the serving prototype still has an older copied version of the same logic. Production predictions look different from evaluation results even on similar tickets. What is the likely design flaw, and how would you repair it?

<details>
<summary>Answer</summary>

The design flaw is duplicated transformation logic across evaluation and serving. The repair is to make serving import the same `build_features()` implementation used by training and evaluation, then add tests for important feature cases so future changes are visible. This aligns the model’s training-time inputs with its serving-time inputs and reduces silent drift.

</details>

**Q4.** Your team trains a recommendation model that beats the previous aggregate metric, but the evaluation report contains no per-segment results. The model is likely to affect several customer groups differently. What promotion decision should you recommend, and why?

<details>
<summary>Answer</summary>

Recommend holding the candidate for more evidence rather than approving broad rollout. A better aggregate metric can hide regressions in critical slices, so the team should add segment-level evaluation and compare the candidate against the baseline for those groups. Promotion should depend on evidence that the model improves or remains acceptable where production risk is highest.

</details>

**Q5.** A notebook-based LLM assistant returns impressive answers during a demo, so an engineer proposes wrapping the final notebook function in a web framework. The notebook has no request validation, no timeout rule, and no fallback when retrieval returns weak context. What production boundary is missing?

<details>
<summary>Answer</summary>

The missing boundary is the separation between offline inference and online serving. A serving contract should define request schema, response schema, validation rules, timeout behavior, fallback behavior, model or prompt versioning, and telemetry. Wrapping the notebook function would expose exploratory assumptions directly to users without operational safeguards.

</details>

**Q6.** A candidate model has a saved artifact and strong metrics, but nobody can identify the dataset snapshot, config values, or code version used for the run. The team says the artifact itself is enough because it can be loaded by the service. How should you evaluate that claim?

<details>
<summary>Answer</summary>

The claim is weak because a loadable artifact is not the same as a governed production candidate. Without lineage, the team cannot reproduce the model, investigate regressions, compare it fairly, or explain why it was approved. The candidate should be held until the run records dataset reference, config, code reference, evaluation report, and rollback expectations.

</details>

**Q7.** A small team wants to avoid heavy platform work, but they also want to stop relying on notebooks as the system of record. Design the smallest credible handoff that still improves production readiness.

<details>
<summary>Answer</summary>

Use notebooks for exploration, move reusable logic into `src/`, store parameters in explicit config files, create thin scripts for training and evaluation, write artifacts and reports to predictable locations, compare every candidate against a named baseline, and define a serving contract before deployment. This handoff is small but meaningful because it creates reproducibility, reviewability, and promotion evidence without requiring a large platform.

</details>

## Hands-On Exercise

**Goal:** Convert a notebook-born ML or LLM prototype into a reproducible, reviewable workflow with separated extraction, evaluation, and serving responsibilities.

Start with any notebook that currently owns important workflow behavior. If you do not have one, create a small notebook or script that loads a JSONL dataset, builds features or prompts, runs a simple model or mock LLM call, prints evaluation output, and writes an artifact.

The exercise is intentionally staged. Do not begin by building a scheduler, API, registry, or dashboard; begin by making the workflow understandable from code, config, commands, and reports.

**Step 1: Classify the notebook cells by responsibility.** Before moving any code, read the notebook from top to bottom and label what each cell is actually for, because that classification decides which logic becomes a durable module and which stays exploratory.

- [ ] Identify cells that load data, parse files, query a warehouse, create labels, build prompts, create features, train models, call models, evaluate results, plot outputs, or inspect errors.

- [ ] Mark each cell as `exploration`, `durable logic`, `run entry point`, `evaluation evidence`, or `serving behavior` so you can see which cells should move first.

- [ ] Write a short mapping table that names the destination for each durable cell, such as `src/project/data.py`, `src/project/features.py`, `src/project/prompts.py`, `src/project/evaluation.py`, or `src/project/inference.py`.

**Step 2: Create the project structure for the handoff.** A predictable directory layout is what lets scripts, tests, and teammates find code without asking the original author, so create the skeleton before moving any logic into it.

- [ ] Create `notebooks/`, `src/project/`, `scripts/`, `configs/`, `outputs/`, `reports/`, and `tests/` so the workflow has a clear home for each responsibility.

- [ ] Move the original notebook into `notebooks/01-exploration.ipynb` and keep it as the analysis surface rather than the production control surface.

- [ ] Add `src/project/__init__.py` so the extracted modules can be imported consistently by scripts, tests, and notebooks.

**Step 3: Extract one risky transformation first.** Start with the single transformation whose silent failure would do the most production damage, because extracting the riskiest logic first delivers the largest reduction in hidden-state risk.

- [ ] Choose one feature builder, prompt builder, data cleaning function, retrieval formatter, or inference wrapper that would cause production damage if copied incorrectly.

- [ ] Move that logic into a module under `src/project/` with explicit function arguments and explicit return values.

- [ ] Update the notebook so it imports the extracted function instead of redefining the logic in a cell.

- [ ] Add at least two focused tests that prove the extracted function handles a normal case and an edge case.

**Step 4: Create explicit configuration.** Configuration that lives inside code is invisible until a run fails, so lift every production-relevant value into a config file where it can be reviewed before execution begins.

- [ ] Move dataset paths, model names, prompt template names, threshold values, artifact directories, and report directories into `configs/train.yaml`, `configs/eval.yaml`, or `configs/serve.yaml`.

- [ ] Remove hardcoded production-relevant values from notebook cells and scripts whenever those values should be visible before a run starts.

- [ ] Document any remaining notebook-only values as exploratory choices rather than production inputs.

**Step 5: Create repeatable training and evaluation commands.** A workflow is only reproducible when another engineer can run it without your kernel, so wrap training and evaluation in scripts that depend only on config files and importable modules.

- [ ] Write `scripts/train.py` so it reads a config file, calls reusable code from `src/project/`, writes an artifact under `outputs/`, and records run metadata.

- [ ] Write `scripts/evaluate.py` so it reads a candidate artifact, compares it against a named baseline or threshold, and writes a report under `reports/`.

- [ ] Ensure neither script imports from `notebooks/` or depends on variables that exist only in an interactive kernel.

**Step 6: Define the production candidate gate.** Promotion is a decision, not a file copy, so record the evidence and the explicit verdict in a short review file that anyone on the team can audit later.

- [ ] Write a short `reports/candidate-review.md` file that records the candidate ID, dataset or prompt reference, config path, baseline, metrics, known risks, and recommended decision.

- [ ] Choose one of these decisions: `reject`, `hold_for_more_evidence`, `approve_for_shadow_test`, or `approve_for_limited_rollout`.

- [ ] Explain the decision using evidence from the evaluation report rather than demo impressions.

**Step 7: Define the serving contract before building service code.** Writing the serving contract before any service code forces the interface to be designed deliberately, rather than emerging by accident from whatever the notebook happened to return.

- [ ] Write the expected request format, response format, validation rules, timeout target, fallback behavior, versioning rule, and rollback mechanism.

- [ ] For an LLM system, include cost-related constraints, retrieval failure behavior, citation requirements, and refusal behavior when applicable.

- [ ] Confirm that serving would import reusable logic from `src/project/` instead of copying notebook cells.

**Step 8: Run verification commands from a clean shell.** Run the verification commands from a brand-new shell so that nothing depends on hidden interactive state, which is exactly the failure mode this whole exercise is meant to eliminate.

```bash
find notebooks src scripts configs outputs reports tests -maxdepth 3 -type f | sort
```

```bash
.venv/bin/python scripts/train.py --config configs/train.yaml
```

```bash
.venv/bin/python scripts/evaluate.py --config configs/eval.yaml
```

```bash
.venv/bin/python -m pytest tests
```

```bash
grep -R "notebooks" src scripts configs tests
```

The final `grep` command should not show production code importing from notebooks. If it does, the workflow still depends on the exploration surface.

**Success criteria:**

- [ ] The notebook is no longer the only place where durable training, evaluation, feature, prompt, or inference logic exists.

- [ ] At least one high-risk notebook cell has been extracted into a reusable module with explicit inputs and outputs.

- [ ] Training and evaluation can run from command-line scripts with explicit config files.

- [ ] Evaluation produces a report that compares the candidate against a named baseline, threshold, or previous release.

- [ ] The serving contract is written separately from the notebook and includes validation, failure behavior, versioning, and rollback.

- [ ] Another engineer can understand the candidate’s lineage from files and commands without asking the notebook author to remember the execution order.

- [ ] The notebook still has a useful role for analysis, visualization, explanation, or error inspection, but it no longer owns the production workflow.

## Next Module

- [Small-Team Private AI Platform](../module-1.12-small-team-private-ai-platform/)
- [ML Monitoring](../module-1.10-ml-monitoring/)
- [Local Inference Stack for Learners](../ai-infrastructure/module-1.4-local-inference-stack-for-learners/)

## Sources

- [MLOps: Continuous delivery and automation pipelines in machine learning](https://cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning) — Google's MLOps architecture guide explains the transition from notebook experimentation to modular, automated pipelines, and states that evaluation produces quality metrics and validation confirms performance against a baseline before deployment.
- [Rules of Machine Learning](https://developers.google.com/machine-learning/guides/rules-of-ml) — Google's engineering best practices for moving ML from prototype to a maintainable production system.
- [Hidden Technical Debt in Machine Learning Systems](https://papers.nips.cc/paper_files/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html) — Sculley et al. (NeurIPS 2015), the seminal account of how ad-hoc ML code accrues production risk — the failure mode this module prevents.
- [Continuous Delivery for Machine Learning](https://martinfowler.com/articles/cd4ml.html) — Thoughtworks' end-to-end pattern for automating the path from experiment to production.
- [MLOps machine learning model management](https://learn.microsoft.com/en-us/azure/machine-learning/concept-model-management-and-deployment?view=azureml-api-2) — Covers model registration, versioning, metadata, and deployment concerns that map directly to artifact governance and production handoff.
- [Online endpoints for real-time inference](https://learn.microsoft.com/en-us/azure/machine-learning/concept-endpoints-online?view=azureml-api-2) — The Azure online-endpoints doc specifies model files, scoring script, environment, instance/scaling settings, and monitoring as deployment requirements.
- [MLflow Models](https://mlflow.org/docs/latest/models/) — Standard packaging format for promotion-ready model artifacts with reproducible dependencies.
- [Papermill](https://papermill.readthedocs.io/en/latest/) — Tool for parameterizing and executing notebooks as repeatable, non-interactive jobs during the transition off the lab bench.
- [DVC Documentation](https://dvc.org/doc) — Data and model versioning that gives candidates reproducible dataset and artifact lineage.
- [Model Cards](https://huggingface.co/docs/hub/en/model-cards) — Hugging Face's documentation on making model candidates reviewable by documenting intended uses, limitations, training data, and evaluation results.
