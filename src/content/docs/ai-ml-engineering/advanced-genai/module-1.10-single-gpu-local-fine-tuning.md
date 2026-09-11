---
citations_verified: true
title: "Single-GPU Local Fine-Tuning"
slug: ai-ml-engineering/advanced-genai/module-1.10-single-gpu-local-fine-tuning
sidebar:
  order: 811
---

> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 2-3 hours

**Reading Time**: 2-3 hours  
**Prerequisites**: Fine-tuning LLMs, LoRA and Parameter-Efficient Fine-Tuning, Home AI Workstation Fundamentals, and Reproducible Python, CUDA, and ROCm Environments

---

## Learning Outcomes

By the end of this module, you will be able to:

- **Evaluate** whether a local single-GPU fine-tuning project is the right solution compared with prompting, retrieval, or data cleanup.
- **Design** a constrained LoRA or QLoRA experiment that fits real VRAM, storage, dataset, and evaluation limits instead of relying on guesswork.
- **Debug** common failure modes in local fine-tuning runs, including out-of-memory errors, unstable loss, inconsistent outputs, and untraceable checkpoints.
- **Compare** baseline and tuned model behavior using a small held-out evaluation set and a decision rule for keeping or discarding the adapter.
- **Package** the final training artifacts so another engineer can reproduce the model choice, data split, configuration, and measured outcome.

These outcomes deliberately focus on judgment and engineering practice, not on memorizing fine-tuning terminology. A learner who can run a command but cannot explain why the run should exist is not ready to own a fine-tuning workflow. A learner who can choose the right adaptation method, reserve an evaluation set, interpret failure, and preserve evidence is much closer to practitioner readiness.

---

## Why This Module Matters

A machine learning engineer inherits a local workstation with one consumer GPU and a request that sounds simple: "Make the model follow our support format better." The team has already tried prompt templates, but responses still drift under pressure. Someone proposes fine-tuning because it sounds more permanent than prompting, while someone else warns that local training is a distraction from building a better retrieval system.

The engineer cannot solve this by enthusiasm. A single GPU can support useful adaptation, but it also exposes every weak assumption in the workflow. If the base model is too large, the run fails before learning anything. If the dataset mixes unrelated tasks, the adapter learns noise. If evaluation is just a few remembered prompts, the team may ship a model that only feels better during a demo.

This module teaches single-GPU fine-tuning as a disciplined engineering loop. The point is not to turn a home workstation into a research cluster. The point is to build a narrow, evidence-driven experiment where every choice has a reason: model size, PEFT method, data format, validation split, checkpoint policy, and runtime evaluation.

The senior-level skill is knowing when to stop. Many failed tuning projects do not fail because LoRA is weak or the GPU is small. They fail because the team tried to use fine-tuning for changing facts, used data that did not demonstrate the desired behavior, or kept training after evaluation had already shown no useful gain.

---

## 1. Frame the Decision: Fine-Tune, Retrieve, or Prompt?

Single-GPU fine-tuning is best understood as behavior adaptation under resource limits. The model already has broad language ability, and your job is to adjust how it behaves on a narrow pattern. You are not teaching it a large new body of facts, and you are not replacing a production knowledge system with frozen weights.

The first decision is whether the problem belongs in model weights at all. Fine-tuning can improve response format, task consistency, tone, classification discipline, or the ability to imitate a repeated workflow. Retrieval is better when the model needs fresh or source-grounded information. Prompting is better when the behavior can be controlled reliably through instructions without changing model parameters.

A useful test is to ask what should happen when the source material changes. If the answer is "the model should immediately use the new document," fine-tuning is probably the wrong first tool. If the answer is "the model should keep using the same response structure, judgment rubric, or style across many examples," a local adapter may be worth testing.

````ascii
+---------------------------+-------------------------------+-------------------------------+
| Problem Signal            | Better First Tool             | Why It Fits                   |
+---------------------------+-------------------------------+-------------------------------+
| Fresh facts change often  | Retrieval                     | Knowledge stays external      |
| Prompt works most times   | Prompt engineering            | Lowest cost and fastest loop  |
| Format drifts repeatedly  | LoRA or QLoRA fine-tuning     | Behavior pattern can be shown |
| Task is broad and vague   | Task redesign                 | Training signal is unclear    |
| Base model lacks ability  | Smaller scope or new model    | Adapter cannot add everything |
+---------------------------+-------------------------------+-------------------------------+
````

For example, a support team may want strict JSON priority labels. If the input is a ticket description and the output always follows one schema, fine-tuning can reinforce that behavior. If the team instead wants the model to answer every support policy question from a changing handbook, retrieval should carry the knowledge and the model should synthesize from retrieved context.

> **Stop and think:** Your team asks for fine-tuning because "the model does not know our procedures." Are the procedures stable behavior patterns, such as how to classify tickets, or changing facts, such as the current escalation roster? Write down which part belongs in weights and which part belongs outside the model.

The distinction matters because a fine-tuned model can become confidently stale. When you train on last quarter's policy text, you create a model that may speak as if old policy is current. A retrieval system can swap documents without retraining, while a fine-tuned adapter requires another training and evaluation cycle before the change is trustworthy.

Prompting still deserves respect in this decision. A strong prompt with examples may solve the problem without any training run, especially when the task is simple and latency is acceptable. Local fine-tuning becomes more attractive when prompt examples are too long, behavior must stay consistent across many calls, or the model repeatedly ignores a compact instruction that appears clearly in the prompt.

Single-GPU constraints sharpen this decision. You have less room for waste, so the task must be narrow enough for a small model, small adapter, and small dataset to reveal signal. A project that cannot be stated in one sentence is usually not ready for local fine-tuning. The best first project sounds like "return incident severity as strict JSON from short ticket descriptions," not "make a general company assistant."

A senior engineer also considers ownership and lifecycle. A fine-tuned adapter becomes an artifact that someone must store, name, test, document, and eventually retire. If the organization cannot keep track of the dataset, base model, license, evaluation prompts, and deployment runtime, then the training run creates operational debt even if the demo looks impressive.

Use this module's workflow as a gate. If you cannot define a stable target behavior, choose a fitting base model, inspect the data manually, and compare baseline versus tuned outputs on held-out prompts, do not start training yet. The disciplined pause is part of the engineering work, not a delay from it.

### Fine-Tuning Fit Matrix

| Scenario | Fine-Tune Locally? | Better Move | Decision Rationale |
|---|---|---|---|
| Strict JSON output from short support tickets | Usually yes | LoRA on a small instruct model | The behavior is narrow, repeated, and easy to evaluate |
| Monthly employee handbook questions | Usually no | Retrieval over current documents | The knowledge changes and needs source grounding |
| Legal summaries across many document types | Not as a first pass | Scope one format or build retrieval plus review | The task is broad and risk is high |
| Tone adaptation for internal release notes | Possibly yes | Compare prompting against LoRA | The style may be learnable if examples are consistent |
| Teaching a model an entire product catalog | Usually no | Retrieval or database-backed tools | Large factual inventory should not be frozen into weights |
| Classifying short alerts into fixed labels | Usually yes | LoRA or QLoRA with held-out checks | Labels, inputs, and evaluation can be tightly controlled |

This matrix is not a rulebook; it is a way to expose the real reason behind the request. If the reason is "we need current facts," avoid local fine-tuning as the primary mechanism. If the reason is "we need the model to behave consistently on a repeated input-output pattern," a small local experiment can be justified.

---

## 2. Size the Experiment Before Writing Code

The most common beginner mistake is choosing the base model before understanding the hardware. Single-GPU fine-tuning is not a moral contest about using the largest model. It is an optimization problem where VRAM, sequence length, batch size, quantization, optimizer state, and adapter settings interact.

VRAM pressure comes from more than the base model weights. Training also needs activations, gradients for trainable parameters, optimizer state, temporary buffers, and memory fragmentation headroom. PEFT reduces the trainable parameter count, but it does not make every model magically fit into every card.

A practical single-GPU plan starts with measurement. Check the GPU name, total memory, free memory, driver stack, and disk space before picking a model. Also confirm whether other desktop or notebook processes are using VRAM, because a local browser, display server, or previous Python process can be the difference between a stable run and an out-of-memory crash.

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv
df -h .
```

For AMD systems, the exact toolchain differs, and library support may vary by operating system and package versions. The engineering principle is the same: record the accelerator, memory budget, driver/runtime stack, and training framework before claiming the experiment is reproducible. The adapter is not the whole artifact; the environment is part of the result.

A conservative sizing rule is to start smaller than your ego wants. If the task can be tested on a sub-billion or low-billion parameter instruct model, start there and prove the workflow. Once the data, evaluation, and artifact policy are correct, you can consider a larger base model if the observed limitation is model capability rather than workflow quality.

````ascii
+-------------------+       +----------------------+       +------------------+
| Hardware Budget   | ----> | Model + PEFT Choice  | ----> | Training Config  |
| GPU VRAM          |       | base model size      |       | sequence length  |
| disk space        |       | LoRA or QLoRA        |       | batch strategy   |
| driver/runtime    |       | quantization support |       | checkpoint limit |
+-------------------+       +----------------------+       +------------------+
          |                              |                            |
          v                              v                            v
+-------------------+       +----------------------+       +------------------+
| Failure Signal    |       | Adjustment           |       | Evidence Kept    |
| OOM, slow run      | ----> | smaller model, QLoRA | ----> | config + logs    |
| unstable outputs   |       | cleaner data, eval   |       | baseline/tuned   |
+-------------------+       +----------------------+       +------------------+
````

LoRA and QLoRA are the default methods for this scale because they keep the base model mostly frozen and train small adapter matrices. LoRA stores low-rank updates in selected layers, commonly attention and projection modules. QLoRA combines LoRA-style adapter training with a quantized base model so the frozen weights require less memory during training.

The trade-off is not only memory. Quantization can change numerical behavior, kernel compatibility, training speed, and deployment assumptions. A model trained or evaluated through one quantized path may not behave identically when moved to a different runtime. That is why the evaluation runtime should match the intended use as closely as practical.

> **Stop and think:** Suppose two configurations both fit in VRAM. One uses a larger quantized model with fragile runtime support, while the other uses a smaller full-precision or half-precision model with stable tooling. Which one would you choose for a first reproducible experiment, and what evidence would change your mind?

Sequence length is another hidden budget. A short classification prompt and output can use a small maximum sequence length, while long summarization examples may require far more memory. Beginners often copy a high sequence length from a tutorial and then blame the GPU when the real issue is that the task does not need that much context.

Batch size should be treated as an effective batch, not only a per-device value. If VRAM allows only `per_device_train_batch_size: 1`, gradient accumulation can approximate a larger effective batch while keeping memory lower. This slows wall-clock training, but it may be the difference between a controlled experiment and a failed launch.

Checkpointing policy also affects resource use. Saving every few steps is useful for debugging but quickly creates storage clutter. For a first local adapter, keep a small `save_total_limit`, record the final adapter, and preserve the config. You need enough artifacts to reproduce and compare, not a folder full of unlabeled intermediate states.

### Constraint Planning Table

| Constraint | What It Controls | First Adjustment | Senior-Level Check |
|---|---|---|---|
| VRAM | Base model size, quantization, batch, sequence length | Choose a smaller model or use QLoRA | Confirm the run has headroom, not just a lucky start |
| Dataset size | Signal strength, overfitting risk, inspection burden | Start small and manually review examples | Keep a held-out split with realistic edge cases |
| Sequence length | Activation memory and speed | Match task length instead of copying defaults | Measure prompt and output lengths from real examples |
| Disk space | Checkpoints, merged models, logs, cache | Limit checkpoints and name artifacts clearly | Preserve only artifacts tied to a known config |
| Runtime support | Compatibility for quantization and kernels | Use a proven stack for your GPU | Evaluate in the runtime you expect to deploy |
| Time budget | Iteration speed and debugging feedback | Run short experiments first | Stop when evidence says the design is wrong |

The table should influence the plan before any training command is written. If you cannot explain which constraint is tightest, you are not sizing the experiment; you are hoping. Hope is expensive when a run takes hours and produces artifacts nobody can interpret.

---

## 3. Prepare Data That Teaches One Behavior

Fine-tuning quality is usually data quality wearing a training costume. A local adapter learns from the examples you provide, including contradictions, inconsistent tone, malformed outputs, and hidden shortcuts. If the dataset is unclear, the model may still reduce training loss while becoming less useful in the real task.

The first dataset should be narrow enough that a human can inspect every example. This is not a permanent ceiling; it is a learning strategy. Manual inspection teaches you what the model will see, reveals inconsistent labels, and prevents the common mistake of treating a large JSONL file as automatically valuable.

A good example has three properties. The instruction is stable, the input resembles real use, and the output demonstrates exactly the behavior you want repeated. If the output schema varies from example to example, the model receives a mixed signal. If the instruction changes wording unnecessarily, the model may learn superficial phrasing instead of the task.

```bash
mkdir -p data eval
cat > data/train.jsonl <<'EOF'
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"Checkout fails for every customer after the latest payment deployment.","output":"{\"priority\":\"critical\",\"reason\":\"customer checkout is unavailable\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"One analyst reports that an internal dashboard widget loads slowly.","output":"{\"priority\":\"low\",\"reason\":\"limited internal impact\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"Password reset emails are not being delivered to customers.","output":"{\"priority\":\"high\",\"reason\":\"account recovery is impaired\"}"}
EOF
```

This example is intentionally small, but it shows the structure. Each row teaches the same behavior: read a short ticket and return a strict JSON object with priority and reason. It does not mix summarization, apology writing, retrieval, and classification in the same file.

The evaluation set must be separate from training. If you train and evaluate on the same examples, you measure memorization and formatting familiarity rather than generalization to similar cases. A small held-out set is enough for a first local experiment, but it must contain prompts that represent the behavior you actually care about.

```bash
cat > eval/check.jsonl <<'EOF'
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"The public status page is unreachable during an active incident.","expected":"{\"priority\":\"high\",\"reason\":\"incident communication is impaired\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"A typo appears in one paragraph of an internal help article.","expected":"{\"priority\":\"low\",\"reason\":\"minor documentation issue\"}"}
EOF
```

The held-out examples should not be trick questions, but they should test the same judgment the production workflow needs. If the model only succeeds on obvious outage examples and fails on degraded communication, the evaluation should reveal that. Evaluation is not a celebration step after training; it is the mechanism that protects the team from believing a weak adapter.

> **Stop and think:** If you add an example where the output is a friendly paragraph instead of strict JSON, what behavior might the model learn? Before reading further, write one failure mode you would expect to see in the tuned model's responses.

A senior data preparation habit is to write a dataset contract. The contract states what every example must contain, what output shape is valid, which labels are allowed, and what examples are out of scope. This prevents silent drift when another teammate contributes new rows.

```yaml
task: support_ticket_priority_json
instruction: "Classify the support ticket priority and return strict JSON."
allowed_priorities:
  - critical
  - high
  - medium
  - low
required_output_fields:
  - priority
  - reason
out_of_scope:
  - policy questions requiring current documentation
  - long incident retrospectives
  - multi-turn conversations
  - examples without a clear business impact signal
```

Data cleaning should be concrete. Validate JSONL parsing, check duplicate inputs, verify label values, and sample outputs for schema consistency. You do not need a heavyweight data platform for the first run, but you do need enough checks to catch mistakes before they enter the training loop.

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

allowed = {"critical", "high", "medium", "low"}
seen_inputs = set()

for path in [Path("data/train.jsonl"), Path("eval/check.jsonl")]:
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        row = json.loads(line)
        for field in ["instruction", "input"]:
            if not row.get(field):
                raise ValueError(f"{path}:{line_number} missing {field}")
        output_field = "output" if path.name == "train.jsonl" else "expected"
        parsed_output = json.loads(row[output_field])
        if parsed_output["priority"] not in allowed:
            raise ValueError(f"{path}:{line_number} invalid priority")
        if row["input"] in seen_inputs:
            raise ValueError(f"{path}:{line_number} duplicate input")
        seen_inputs.add(row["input"])

print("dataset contract checks passed")
PY
```

The validation script is small, but the habit is important. It turns vague trust into a repeatable gate. When the model performs poorly, you can investigate data quality with evidence instead of wondering whether the JSONL file was malformed all along.

For local fine-tuning, small datasets can work when the target behavior is narrow and the base model is already capable. The adapter is nudging behavior, not teaching language from scratch. However, small does not mean careless. Ten excellent examples may be useful for a smoke test, but a production candidate needs broader coverage of normal cases, edge cases, and negative cases.

A negative case is an example that shows what not to overreact to. In the support priority task, not every customer-facing issue is critical, and not every internal complaint is low priority. Including realistic contrast helps the model learn the decision boundary instead of mapping dramatic words to the highest label.

The most valuable data review question is "Would two domain experts agree on this output?" If the answer is no, the model is being asked to learn ambiguous policy. Fix the rubric before training. Fine-tuning amplifies your examples; it does not adjudicate vague business rules.

---

## 4. Configure a Local LoRA or QLoRA Run

A training configuration is an engineering document, not just a set of knobs. It records the assumptions of the experiment in a form that can be reviewed, repeated, and compared. The same adapter without its configuration is like a binary without the source version that produced it.

The minimum useful configuration names the base model, PEFT method, LoRA rank, alpha, dropout, target modules, sequence length, batch settings, learning rate, epoch count, checkpoint policy, dataset paths, and output directory. You may not tune every value at first, but you should know which values exist and why the defaults are acceptable.

```bash
mkdir -p artifacts logs
cat > artifacts/config.yaml <<'EOF'
base_model: HuggingFaceTB/SmolLM2-135M-Instruct
peft_method: lora
quantization: none
lora:
  r: 8
  alpha: 16
  dropout: 0.05
  target_modules:
    - q_proj
    - v_proj
training:
  max_seq_length: 512
  per_device_train_batch_size: 1
  gradient_accumulation_steps: 8
  learning_rate: 0.0002
  num_train_epochs: 2
  save_total_limit: 2
paths:
  train_file: data/train.jsonl
  eval_file: eval/check.jsonl
  output_dir: artifacts/adapter
EOF
```

This configuration chooses a very small instruct model for workflow demonstration, not because it is the best production choice. That distinction matters. A tiny model lets you test data formatting, adapter saving, evaluation comparison, and artifact hygiene quickly. If the workflow is broken on a tiny model, a larger model will only make the failure slower and more expensive.

LoRA rank controls the capacity of the adapter. A higher rank can express more change but costs more memory and may overfit small data. Alpha scales the adapter updates, and dropout can reduce overfitting pressure. The right values depend on model, data, and task, but the first run should favor stability and interpretability over aggressive tuning.

Target modules decide where adapters are inserted. Many transformer architectures use projection module names such as `q_proj` and `v_proj`, but names vary across model families. A practical engineer verifies module names instead of assuming a tutorial's names match the selected base model.

```bash
.venv/bin/python - <<'PY'
from transformers import AutoModelForCausalLM

model_name = "HuggingFaceTB/SmolLM2-135M-Instruct"
model = AutoModelForCausalLM.from_pretrained(model_name)

matches = []
for name, module in model.named_modules():
    if name.endswith(("q_proj", "v_proj", "k_proj", "o_proj")):
        matches.append(name)

for name in matches[:40]:
    print(name)
print(f"matched projection modules: {len(matches)}")
PY
```

If this script shows no matching modules, do not blindly run training. Inspect the model architecture and adjust `target_modules` to real layer names. A configuration that names nonexistent modules may fail immediately, attach adapters somewhere unintended, or depend on library behavior you have not reviewed.

QLoRA enters when the base model would be too memory-heavy without quantization. The frozen base model is loaded in lower precision, while trainable LoRA adapters remain small. This can make a larger model practical on one GPU, but it adds compatibility questions around bitsandbytes, hardware support, kernels, and deployment runtime.

Use QLoRA when it solves a measured memory problem, not because it sounds more advanced. If a small model trains cleanly without quantization, a first workflow demonstration may be easier to debug without QLoRA. Once the process is sound, quantization becomes a controlled change rather than another variable mixed into an already uncertain run.

### QLoRA 4-bit loading, NF4, and the VRAM budget

QLoRA keeps the base model frozen in 4-bit NormalFloat (NF4) quantization while training low-rank adapter matrices in higher precision. bitsandbytes implements the storage format and double-quantization of quantization constants so the frozen weights occupy far less VRAM than fp16 baselines. The durable mental model is a **VRAM ledger** with four major buckets during training:

| Bucket | What it holds | PEFT impact |
|---|---|---|
| Model weights | Frozen base parameters | QLoRA shrinks this bucket via 4-bit storage |
| Optimizer state | Moments for trainable params | LoRA trains only adapter weights, so optimizer state stays small |
| Activations | Forward/backward tensors per layer | Scales with sequence length, batch, and checkpointing policy |
| Gradients | Updates for trainable params | LoRA limits gradients to adapter modules only |

Gradient checkpointing trades compute for memory by recomputing activations during the backward pass instead of storing every intermediate tensor. Gradient accumulation simulates a larger batch by summing gradients over several micro-batches before an optimizer step. On a single GPU, the effective batch size is approximately `per_device_train_batch_size × gradient_accumulation_steps`; VRAM is dominated by the micro-batch size, not the effective batch.

A conservative **fit-check** before a long run:

```bash
# Illustrative — replace model id and lengths with your experiment.
.venv/bin/python - <<'PY'
# Estimate whether a 7B-class model might fit with QLoRA on ~24 GB.
# These are order-of-magnitude checks, not guarantees.
params_b = 7
bytes_fp16 = params_b * 2          # GB if fully fp16 weights
bytes_4bit = params_b * 0.5        # rough NF4 storage
adapter_mb = 200                   # typical small LoRA adapter + optimizer
activation_gb = 8                    # highly sequence/batch dependent
headroom_gb = 2
needed = bytes_4bit + adapter_mb/1024 + activation_gb + headroom_gb
print(f"illustrative minimum VRAM (GB): {needed:.1f}")
print("verify with a short smoke run and nvidia-smi — do not trust this table alone")
PY
```

> **Landscape snapshot — as of 2026-06**
>
> Library stacks for single-GPU fine-tuning move quickly. **PEFT** exposes `LoraConfig` and QLoRA helpers; **Transformers** `Trainer` and **TRL** `SFTTrainer` wrap training loops; **Accelerate** handles device placement; **bitsandbytes** 4-bit loaders depend on CUDA capability and package version. Confirm argument names (`bnb_4bit_compute_dtype`, `load_in_4bit`) against [PEFT](https://huggingface.co/docs/peft/index), [Transformers Trainer](https://huggingface.co/docs/transformers/en/main_classes/trainer), [TRL](https://huggingface.co/docs/trl/index), and [Accelerate](https://huggingface.co/docs/accelerate/index) for the versions pinned in your environment. Any published "fits in 24 GB" claim is valid only for the cited model, sequence length, batch, and driver stack.

When OOM persists after QLoRA, reduce sequence length and micro-batch before increasing LoRA rank. Rank increases adapter capacity but also grows optimizer state and activation paths through adapted layers. The senior move is to change one pressure source, rerun a fifty-step smoke test, and record peak `memory.used` from `nvidia-smi` rather than chasing ten hyperparameters at once.

Gradient checkpointing deserves an explicit experiment note because it changes the compute/memory trade-off in ways training loss alone will not reveal. Enable checkpointing when activation memory dominates the ledger; disable it when the run is already stable and you need shorter wall-clock time for iteration. Document the flag in `artifacts/config.yaml` so the next engineer knows whether slower steps were intentional frugality or accidental misconfiguration.

A training command should be captured exactly. The command, package versions, GPU state, dataset checksum, and config belong in the experiment notes. If you cannot reproduce the command later, you cannot responsibly compare adapters or explain why one run improved.

```bash
{
  date
  nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv
  .venv/bin/python -m pip freeze | sed -n '1,120p'
  sha256sum data/train.jsonl eval/check.jsonl artifacts/config.yaml
} > logs/environment.txt
```

This log is not glamorous, but it answers questions that matter during review. Did the dataset change? Did the package stack change? Was the GPU memory already crowded? These details often explain differences that otherwise look like model randomness.

Training loss should be interpreted carefully. A lower loss on a tiny dataset may mean the adapter memorized the examples. It does not automatically mean the model improved on held-out prompts. Treat loss as a debugging signal, then let baseline-versus-tuned evaluation answer the product question.

Out-of-memory errors should be handled by reducing the pressure source. Lower sequence length, reduce per-device batch size, use gradient accumulation, choose a smaller model, enable quantization if supported, or close other GPU processes. Do not respond by randomly changing many settings at once, because then you cannot tell which adjustment fixed the problem.

````ascii
+------------------------------+
| OOM During Local Fine-Tuning |
+------------------------------+
              |
              v
+------------------------------+
| Did the model ever load?     |
+------------------------------+
       | yes              | no
       v                  v
+------------------+   +--------------------------+
| Reduce sequence  |   | Use smaller base model   |
| length or batch  |   | or supported quantization|
+------------------+   +--------------------------+
       |
       v
+------------------------------+
| Still failing after changes? |
+------------------------------+
       | yes              | no
       v                  v
+------------------+   +--------------------------+
| Reduce model or  |   | Record final memory and  |
| change runtime   |   | keep the config fixed    |
+------------------+   +--------------------------+
````

The troubleshooting flow intentionally changes one class of constraint at a time. If you lower sequence length, change model size, alter LoRA rank, switch precision, and modify the dataset in one edit, the next result cannot teach you much. Engineering progress comes from controlled changes.

A local notebook can be useful for exploration, but the final experiment should be scriptable. Scripts make it easier to rerun, review, and automate. They also reduce hidden state from notebook cells executed out of order, which is a common source of misleading fine-tuning results.

For team settings, write the training config so a reviewer can read it without running anything. The config should answer "what is being adapted, with which data, under which resource assumptions, and where will the adapter land?" If those answers are scattered across shell history, notebook cells, and memory, the experiment is not reviewable.

---

## 5. Worked Example: Turning Messy Support Notes into a Single-GPU Plan

This worked example demonstrates the reasoning process before the hands-on exercise asks you to run a similar workflow. The input is deliberately messy because real requests rarely arrive as clean training specifications. The goal is to transform an ambiguous request into a narrow, testable local fine-tuning plan.

### Input Scenario

A support operations lead says: "We want a local model that reads support tickets and writes the right response. The model should know our support priorities, sound friendly, summarize the issue, decide urgency, and include escalation instructions. We have one workstation GPU and a folder of old tickets."

A beginner might turn the whole folder into training data and hope the model learns everything at once. A stronger engineer slows down and separates the request into tasks. Some parts are stable behavior, some parts may depend on current policy, and some parts are too broad for a first adapter.

### Step 1: Split the Request by Learning Target

The request contains at least four different behaviors. It asks for prioritization, tone, summarization, and escalation guidance. Those behaviors can interfere with each other if they appear in one small dataset without a clear output contract.

| Requested Behavior | Local Fine-Tuning Fit | Reason |
|---|---|---|
| Decide priority from a short ticket | Good first candidate | Fixed labels and clear evaluation are possible |
| Sound friendly in response text | Possible later | Tone can be learned, but it complicates output scoring |
| Summarize long issue history | Risky first candidate | Longer context and subjective evaluation add complexity |
| Include escalation instructions | Usually retrieval or rules | Current procedures may change and need grounding |

The first local experiment should focus on ticket priority classification with strict JSON output. That task is narrow, has measurable outputs, and can use short examples. Escalation instructions should stay outside the adapter unless the policy is stable and deliberately included in the task contract.

### Step 2: Define the Output Contract

The output contract reduces ambiguity. Instead of "write the right response," the model must return a JSON object with a priority and reason. This makes baseline comparison easier because the evaluation can check parseability, allowed labels, and judgment quality.

```json
{
  "priority": "critical | high | medium | low",
  "reason": "short business-impact reason"
}
```

The reason field should be short because the target behavior is classification discipline, not long-form support writing. If the team later wants a friendly customer response, that should be a second experiment or a downstream templating step. Mixing it into the first run would make the evaluation less clear.

### Step 3: Choose the Base Model by Hardware Reality

Assume the workstation has one consumer GPU with limited VRAM and no production training cluster. The worked example chooses a small instruct model for the first run to validate the loop. If the adapter improves format adherence but judgment remains weak because the base model lacks capability, the next experiment can test a larger quantized model.

The decision rule is simple: the first run should be small enough to finish, inspect, and discard without drama. A failed tiny run is cheap evidence. A failed oversized run often produces only frustration and unclear logs.

### Step 4: Create Training and Evaluation Splits

The training split shows the target behavior. The evaluation split uses similar but unseen tickets. The key is not the number of rows in this example; the key is separation and consistency.

```bash
mkdir -p worked-example/data worked-example/eval
cat > worked-example/data/train.jsonl <<'EOF'
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"All customers receive an error when submitting payment.","output":"{\"priority\":\"critical\",\"reason\":\"payment flow is unavailable\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"A single internal report has a stale chart title.","output":"{\"priority\":\"low\",\"reason\":\"minor internal reporting issue\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"New users cannot complete account verification.","output":"{\"priority\":\"high\",\"reason\":\"new customer onboarding is blocked\"}"}
EOF

cat > worked-example/eval/check.jsonl <<'EOF'
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"Some invoices are generated two hours late, but checkout still works.","expected":"{\"priority\":\"medium\",\"reason\":\"billing communication is delayed\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"The incident banner is missing from the public status page.","expected":"{\"priority\":\"high\",\"reason\":\"incident visibility is impaired\"}"}
EOF
```

Notice what the example does not include. It does not include a customer apology, a policy citation, a multi-turn conversation, or a long retrospective summary. Those may be useful tasks later, but adding them now would blur the training signal.

### Step 5: Predict Baseline Weakness Before Training

Before tuning, the team runs the base model on the held-out prompts and records outputs. Suppose the base model often returns friendly paragraphs like "This seems important, so you should investigate soon." That may be semantically reasonable, but it violates strict JSON and does not provide a stable label.

The prediction is that LoRA may improve schema adherence and label consistency if the base model already understands the ticket language. If the base model cannot reason about business impact at all, LoRA on a tiny dataset may not be enough. This prediction gives the team a fair way to interpret the result later.

### Step 6: Apply the Training Plan

The training plan uses LoRA because the task is narrow and the GPU is constrained. It keeps sequence length modest because tickets are short. It limits checkpoints because the team needs a final adapter and enough logs to reproduce, not dozens of intermediate files.

```yaml
base_model: HuggingFaceTB/SmolLM2-135M-Instruct
task: support_ticket_priority_json
peft_method: lora
lora:
  r: 8
  alpha: 16
  dropout: 0.05
training:
  max_seq_length: 512
  per_device_train_batch_size: 1
  gradient_accumulation_steps: 8
  learning_rate: 0.0002
  num_train_epochs: 2
  save_total_limit: 2
evaluation:
  compare:
    - json_parse_success
    - allowed_priority_label
    - business_impact_reason
```

This is a plan, not proof. The adapter still has to be evaluated against the baseline. A disciplined engineer avoids declaring success until the same held-out prompts show better behavior under the same inference conditions.

### Step 7: Decide Keep, Iterate, or Discard

After training, the team compares baseline and tuned outputs. If the tuned adapter returns valid JSON with reasonable labels on held-out examples and the baseline did not, keeping the adapter for further testing is justified. If both models behave similarly, the adapter does not earn a place in the workflow.

If the tuned model overfits and labels nearly everything as critical, the next change should probably be data contrast, not more epochs. If the model follows JSON but chooses weak labels, the task rubric or base model may be the limiting factor. If the output improves only in a notebook but fails in the intended runtime, the runtime mismatch must be fixed before any deployment claim.

The lesson from the worked example is that fine-tuning is not one command. It is a chain of decisions that starts with scope, moves through data and constraints, and ends with evidence. The hands-on exercise later asks you to perform the same chain on a small local project.

---

## 6. Evaluate, Package, and Decide Whether to Keep It

Evaluation is where local fine-tuning becomes engineering instead of folklore. The central question is not "did training finish?" The central question is "does the tuned adapter improve the target behavior on examples it did not train on, in the runtime where we expect to use it?"

Baseline comparison is mandatory. You need outputs from the original model and outputs from the tuned adapter on the same held-out prompts. Without that comparison, you cannot separate true improvement from the base model already being good, prompt variation, or selective memory of a few nice generations.

```bash
mkdir -p eval/results
cat > eval/prompts.txt <<'EOF'
Classify the support ticket priority and return strict JSON.

Ticket: The public status page is unreachable during an active incident.
EOF
```

The exact inference command depends on your chosen stack, but the output capture pattern should be stable. Save raw outputs, not just your interpretation. Later reviewers need to see what the model actually produced, including malformed JSON, extra commentary, or missing fields.

A small scoring rubric helps avoid vague impressions. For the support ticket example, score whether the output parses as JSON, whether the priority is one of the allowed labels, whether the reason references business impact, and whether the label is defensible. This still involves judgment, but it makes the judgment explicit.

| Evaluation Check | Passing Example | Failing Example | Why It Matters |
|---|---|---|---|
| JSON parseability | `{"priority":"high","reason":"incident visibility is impaired"}` | `This is probably high priority.` | Downstream systems need structured output |
| Allowed label | `medium` | `urgent-ish` | The task contract defines valid labels |
| Business-impact reason | `checkout is unavailable` | `it sounds bad` | The model must explain the classification basis |
| Held-out behavior | Works on unseen tickets | Only repeats training examples | Fine-tuning should generalize within scope |
| Runtime match | Evaluated in deployment runtime | Evaluated only in a different notebook path | Quantization and loading path can affect behavior |

Evaluation should include at least one borderline case. Borderline cases are where weak rubrics fail. For example, a delayed invoice email is not as severe as broken checkout, but it may still matter. If the model treats every customer-facing issue as critical, it is not learning the priority rubric; it is learning alarm words.

> **Stop and think:** Your tuned adapter returns valid JSON on every held-out prompt, but the labels are worse than the base model's labels. Do you keep the adapter because formatting improved, or discard it because the decision quality regressed? State the decision rule before you look at more examples.

Packaging comes after evaluation, not before it. A good final artifact directory contains the adapter, config, dataset snapshot or reference, evaluation outputs, environment log, and a short decision note. A bad artifact directory contains unlabeled checkpoints, merged models with unknown settings, and no baseline comparison.

```bash
find artifacts eval logs -maxdepth 3 -type f | sort
du -sh artifacts eval logs
```

A decision note should be brief and specific. It should say whether the adapter is kept, why, what evidence supports the decision, and what limitation remains. If the adapter is discarded, the note should still be kept because it prevents the same failed path from being repeated later.

```bash
cat > logs/decision.md <<'EOF'
# Decision

Adapter: artifacts/adapter
Base model: HuggingFaceTB/SmolLM2-135M-Instruct
Task: support ticket priority as strict JSON
Decision: keep for further testing or discard

Evidence:
- Baseline JSON parse success:
- Tuned JSON parse success:
- Label quality notes:
- Runtime used for comparison:

Remaining risks:
- Dataset is small and needs broader edge-case coverage.
- Priority rubric should be reviewed by support operations before production use.
EOF
```

Storage hygiene is not optional at home scale. Model caches, checkpoints, and merged outputs can fill disks quickly. Keep what is needed to reproduce and compare. Delete throwaway checkpoints only after you have confirmed that the final adapter, config, logs, and evaluation outputs are preserved.

A senior workflow also records licensing and data governance constraints. Before training on internal tickets, confirm that the data is allowed for the selected model license, storage location, and intended use. Remove secrets and personal data unless there is a documented reason and approved handling path. Local does not mean exempt from governance.

The final keep-or-discard decision should be boring. If evidence shows improvement on the target behavior without unacceptable regression, keep the adapter for the next review stage. If evidence is weak, discard or redesign. The point of a controlled local run is not to guarantee success; it is to make the next decision honest.

---

## Did You Know?

- **LoRA adapters are usually small compared with full model weights.** That is why they are practical to store, move, compare, and discard during local experiments, but they still depend on the exact compatible base model.
- **QLoRA reduces memory pressure by quantizing the frozen base model while training adapter weights.** This can make larger local experiments possible, but it also makes runtime compatibility and evaluation path more important.
- **A held-out evaluation set can be tiny and still valuable.** Even a handful of unseen prompts can catch schema drift, label collapse, and overfitting that training loss alone will not reveal.
- **A successful fine-tuning run may still be the wrong product decision.** If retrieval, rules, or a better prompt solves the problem with less operational risk, the adapter should not become the default just because training completed.

---

## Common Mistakes

| Mistake | What Goes Wrong | Better Move |
|---|---|---|
| Using fine-tuning to store changing facts | The model becomes stale and may answer old policy as if it were current | Use retrieval for changing documents and reserve fine-tuning for stable behavior |
| Choosing the largest model before measuring VRAM | The run fails, becomes painfully slow, or requires extreme settings that hide other problems | Measure hardware first and choose a model that leaves memory headroom |
| Mixing unrelated tasks in one small dataset | The adapter receives contradictory signals and produces inconsistent outputs | Start with one narrow input-output contract and expand only after evaluation works |
| Evaluating only by intuition | The team keeps an adapter because a few outputs feel better during a demo | Compare baseline and tuned outputs on held-out prompts with explicit checks |
| Training on the same examples used for evaluation | The model appears better because it saw the answers during training | Reserve a separate check set before the first training command |
| Keeping chaotic checkpoint folders | Nobody can map artifacts back to a base model, dataset, or configuration | Limit checkpoints and preserve named configs, logs, and decision notes |
| Changing many settings after a failure | The team cannot identify which adjustment fixed or worsened the run | Change one major constraint at a time and record the reason |
| Evaluating in a different runtime than deployment | Quantization, loading, or inference differences hide practical failures | Compare baseline and tuned behavior in the runtime you intend to use |

---

## Quiz

**Q1.** Your team wants a local model to answer employee questions about a handbook that changes every month. A teammate suggests fine-tuning on the latest handbook because the model "needs to know company policy." What should you recommend, and what evidence from the scenario drives your decision?

<details>
<summary>Answer</summary>

Recommend retrieval as the first design, not local fine-tuning. The key signal is that the handbook changes every month, so the knowledge needs to stay current and source-grounded. Fine-tuning would freeze policy into weights and require repeated retraining whenever the handbook changes. A fine-tuned adapter might still be useful later for response style or formatting, but the changing factual content should live outside the model.

</details>

**Q2.** A learner has one GPU with limited VRAM and starts with a model that barely loads. Training fails with out-of-memory errors after the first few steps. They propose increasing LoRA rank because "the adapter needs more capacity." What should they debug first?

<details>
<summary>Answer</summary>

They should debug the resource fit before increasing adapter capacity. The first checks are GPU memory, model size, sequence length, per-device batch size, other GPU processes, and whether quantization or a smaller base model is needed. Increasing LoRA rank adds capacity and memory pressure, so it is unlikely to fix an out-of-memory problem. A controlled response would reduce sequence length or batch size, use gradient accumulation, choose a smaller model, or move to a supported QLoRA setup.

</details>

**Q3.** A support team creates a small dataset that mixes ticket priority labels, customer apology paragraphs, long summaries, and escalation instructions. After tuning, the model sometimes returns JSON, sometimes writes a friendly paragraph, and sometimes invents policy. How would you redesign the next experiment?

<details>
<summary>Answer</summary>

Redesign the experiment around one behavior with one output contract. For a first pass, ticket priority classification as strict JSON is a good candidate because labels and parseability can be evaluated. Customer tone, summarization, and escalation policy should be separated into later experiments or handled by templates, retrieval, or rules. The next dataset should use consistent instructions, realistic inputs, valid output labels, and a held-out evaluation split.

</details>

**Q4.** Your tuned adapter returns valid JSON on all held-out prompts, while the base model often adds prose around the JSON. However, the tuned adapter labels several medium incidents as critical. Should the team keep the adapter as a success?

<details>
<summary>Answer</summary>

Not automatically. The adapter improved schema adherence but regressed decision quality, so the team should apply the decision rule defined before evaluation. If correct prioritization is the primary business behavior, the adapter should be discarded or iterated with better contrast examples and a clearer rubric. If formatting is the only target, it may be a partial success, but the scenario says priority labels matter, so the regression is significant.

</details>

**Q5.** A training run completes successfully, and the final folder contains many checkpoints named `test`, `new`, `final`, and `final-fixed`. There is no saved config, no dataset checksum, and no baseline output. A month later, another engineer asks whether the adapter can be deployed. What is the correct engineering response?

<details>
<summary>Answer</summary>

The adapter should not be treated as deployable evidence. Without the base model reference, training config, dataset version, environment details, and baseline-versus-tuned evaluation outputs, the team cannot reproduce or review the result. The correct response is to rerun or reconstruct the experiment with artifact hygiene: named config, dataset snapshot or checksum, environment log, final adapter, raw evaluation outputs, and a decision note.

</details>

**Q6.** A colleague evaluates a QLoRA-trained adapter in a notebook using one loading path, then plans to deploy it through a different local runtime with different quantization behavior. The notebook outputs look better than baseline. What risk should you raise before approving the result?

<details>
<summary>Answer</summary>

Raise the risk that the evaluation runtime does not match the intended deployment runtime. Quantization and loading paths can affect compatibility, performance, and outputs. The team should compare baseline and tuned behavior in the runtime they plan to use, or at least document why the notebook path is equivalent. A successful notebook result is useful, but it is not enough to approve deployment when the runtime will change.

</details>

**Q7.** During evaluation, the tuned model performs well on obvious outage tickets but fails on borderline cases such as delayed invoices, degraded status-page communication, and limited internal impact. The training set mostly contains severe incidents. What should the next iteration change?

<details>
<summary>Answer</summary>

The next iteration should improve dataset coverage and contrast, not simply train longer. The model is likely learning a shallow association between incident language and high urgency because the training set lacks borderline and negative examples. Add well-reviewed examples for medium, low, and high-but-not-critical cases, clarify the priority rubric, and keep those categories represented in the held-out evaluation set. Training longer on the same skewed data may reinforce the failure.

</details>

---

## Hands-On Exercise

Goal: complete a reproducible single-GPU LoRA fine-tuning workflow on a narrow structured-output task, then decide whether the adapter deserves to be kept. This exercise uses a small model and small dataset so you can practice the engineering loop before attempting larger local runs.

The task is support ticket priority classification as strict JSON. That task is intentionally narrow because it lets you test the full workflow: scope, hardware measurement, data contract, baseline capture, adapter training, tuned evaluation, artifact packaging, and keep-or-discard decision.

- [ ] Create a clean workspace for one experiment and keep all artifacts under that workspace.

```bash
mkdir -p single-gpu-ft/{data,eval,artifacts,logs,scripts}
cd single-gpu-ft
pwd
```

- [ ] Confirm that your virtual environment exists and install the packages for a small local LoRA run.

```bash
test -x .venv/bin/python || { echo "Create .venv before continuing"; exit 1; }
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install "transformers>=4.40" "datasets>=2.18" "peft>=0.10" "trl>=0.8" "accelerate>=0.28" torch pyyaml
```

- [ ] Record hardware and environment details before choosing settings.

```bash
{
  date
  nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv || true
  df -h .
  .venv/bin/python -m pip freeze | sed -n '1,160p'
} > logs/environment.txt
sed -n '1,80p' logs/environment.txt
```

- [ ] Write the task contract so the dataset has one clear behavior.

```bash
cat > data/contract.yaml <<'EOF'
task: support_ticket_priority_json
instruction: "Classify the support ticket priority and return strict JSON."
allowed_priorities:
  - critical
  - high
  - medium
  - low
required_output_fields:
  - priority
  - reason
scope:
  include: short support tickets with business-impact clues
  exclude: current policy lookup, long-form summaries, customer apology drafting
EOF
sed -n '1,120p' data/contract.yaml
```

- [ ] Create a narrow training dataset with consistent instructions and output shape.

```bash
cat > data/train.jsonl <<'EOF'
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"Checkout fails for every customer after the latest payment deployment.","output":"{\"priority\":\"critical\",\"reason\":\"customer checkout is unavailable\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"One analyst reports that an internal dashboard widget loads slowly.","output":"{\"priority\":\"low\",\"reason\":\"limited internal impact\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"Password reset emails are not being delivered to customers.","output":"{\"priority\":\"high\",\"reason\":\"account recovery is impaired\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"Invoice emails are delayed, but customers can still complete purchases.","output":"{\"priority\":\"medium\",\"reason\":\"billing communication is delayed\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"The public API returns errors for all authentication requests.","output":"{\"priority\":\"critical\",\"reason\":\"authentication service is unavailable\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"A typo appears in one paragraph of an internal onboarding document.","output":"{\"priority\":\"low\",\"reason\":\"minor internal documentation issue\"}"}
EOF
wc -l data/train.jsonl
```

- [ ] Create a held-out evaluation set and do not train on it.

```bash
cat > eval/check.jsonl <<'EOF'
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"The public status page is unreachable during an active incident.","expected":"{\"priority\":\"high\",\"reason\":\"incident communication is impaired\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"Some invoice PDFs are generated two hours late, but payment still works.","expected":"{\"priority\":\"medium\",\"reason\":\"billing artifact delivery is delayed\"}"}
{"instruction":"Classify the support ticket priority and return strict JSON.","input":"A color is wrong on one internal dashboard chart.","expected":"{\"priority\":\"low\",\"reason\":\"minor internal presentation issue\"}"}
EOF
wc -l eval/check.jsonl
```

- [ ] Validate the dataset contract before any training run.

```bash
cat > scripts/check_data.py <<'PY'
import json
from pathlib import Path

allowed = {"critical", "high", "medium", "low"}
seen_inputs = set()

for path in [Path("data/train.jsonl"), Path("eval/check.jsonl")]:
    output_field = "output" if path.name == "train.jsonl" else "expected"
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        row = json.loads(line)
        for field in ["instruction", "input", output_field]:
            if not row.get(field):
                raise ValueError(f"{path}:{line_number} missing {field}")
        parsed = json.loads(row[output_field])
        if set(parsed) != {"priority", "reason"}:
            raise ValueError(f"{path}:{line_number} output fields are wrong")
        if parsed["priority"] not in allowed:
            raise ValueError(f"{path}:{line_number} invalid priority")
        if row["input"] in seen_inputs:
            raise ValueError(f"{path}:{line_number} duplicate input")
        seen_inputs.add(row["input"])

print("dataset checks passed")
PY

.venv/bin/python scripts/check_data.py
```

- [ ] Create a training configuration with an intentionally small model for workflow validation.

```bash
cat > artifacts/config.yaml <<'EOF'
base_model: HuggingFaceTB/SmolLM2-135M-Instruct
peft_method: lora
lora:
  r: 8
  alpha: 16
  dropout: 0.05
  target_modules:
    - q_proj
    - v_proj
training:
  max_seq_length: 512
  per_device_train_batch_size: 1
  gradient_accumulation_steps: 8
  learning_rate: 0.0002
  num_train_epochs: 2
  save_total_limit: 2
paths:
  train_file: data/train.jsonl
  eval_file: eval/check.jsonl
  output_dir: artifacts/adapter
EOF
sed -n '1,120p' artifacts/config.yaml
```

- [ ] Save checksums so later changes to data or config are visible.

```bash
sha256sum data/train.jsonl eval/check.jsonl data/contract.yaml artifacts/config.yaml > logs/checksums.txt
cat logs/checksums.txt
```

- [ ] Create a minimal training script that formats each example as an instruction, input, and expected assistant output.

```bash
cat > scripts/train_lora.py <<'PY'
import json
from pathlib import Path

import torch
import yaml
from datasets import Dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

config = yaml.safe_load(Path("artifacts/config.yaml").read_text())
base_model = config["base_model"]

def load_rows(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        item = json.loads(line)
        text = (
            f"Instruction: {item['instruction']}\n"
            f"Input: {item['input']}\n"
            f"Answer: {item['output']}"
        )
        rows.append({"text": text})
    return rows

tokenizer = AutoTokenizer.from_pretrained(base_model)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    base_model,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" if torch.cuda.is_available() else None,
)

lora = config["lora"]
peft_config = LoraConfig(
    r=lora["r"],
    lora_alpha=lora["alpha"],
    lora_dropout=lora["dropout"],
    target_modules=lora["target_modules"],
    task_type="CAUSAL_LM",
)

train_dataset = Dataset.from_list(load_rows(config["paths"]["train_file"]))

training = config["training"]
args = SFTConfig(
    output_dir=config["paths"]["output_dir"],
    max_seq_length=training["max_seq_length"],
    per_device_train_batch_size=training["per_device_train_batch_size"],
    gradient_accumulation_steps=training["gradient_accumulation_steps"],
    learning_rate=training["learning_rate"],
    num_train_epochs=training["num_train_epochs"],
    save_total_limit=training["save_total_limit"],
    logging_steps=1,
    save_strategy="epoch",
    report_to=[],
    dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_dataset,
    peft_config=peft_config,
    args=args,
)

trainer.train()
trainer.model.save_pretrained(config["paths"]["output_dir"])
tokenizer.save_pretrained(config["paths"]["output_dir"])
print(f"saved adapter to {config['paths']['output_dir']}")
PY
```

- [ ] Create an evaluation script that can run the base model and the adapter on the same held-out prompts.

```bash
cat > scripts/evaluate.py <<'PY'
import argparse
import json
from pathlib import Path

import torch
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

parser = argparse.ArgumentParser()
parser.add_argument("--adapter", action="store_true")
parser.add_argument("--output", required=True)
args = parser.parse_args()

config = yaml.safe_load(Path("artifacts/config.yaml").read_text())
base_model = config["base_model"]

tokenizer = AutoTokenizer.from_pretrained(base_model)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    base_model,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" if torch.cuda.is_available() else None,
)

if args.adapter:
    model = PeftModel.from_pretrained(model, config["paths"]["output_dir"])

model.eval()
outputs = []

for line in Path(config["paths"]["eval_file"]).read_text().splitlines():
    item = json.loads(line)
    prompt = (
        f"Instruction: {item['instruction']}\n"
        f"Input: {item['input']}\n"
        "Answer:"
    )
    encoded = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        generated = model.generate(
            **encoded,
            max_new_tokens=80,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    decoded = tokenizer.decode(generated[0], skip_special_tokens=True)
    outputs.append({
        "input": item["input"],
        "expected": item["expected"],
        "response": decoded,
    })

Path(args.output).write_text(json.dumps(outputs, indent=2) + "\n")
print(f"wrote {args.output}")
PY
```

- [ ] Run the baseline evaluation before training and keep the raw outputs.

```bash
.venv/bin/python scripts/evaluate.py --output eval/baseline.json
sed -n '1,200p' eval/baseline.json
```

- [ ] Start the LoRA training run and record the exact command.

```bash
printf '%s\n' ".venv/bin/python scripts/train_lora.py" >> logs/run-command.txt
.venv/bin/python scripts/train_lora.py 2>&1 | tee logs/train.log
```

- [ ] Confirm that the adapter exists and that checkpoints are limited.

```bash
find artifacts -maxdepth 4 -type f | sort
du -sh artifacts
```

- [ ] Run the tuned evaluation using the same held-out prompts.

```bash
.venv/bin/python scripts/evaluate.py --adapter --output eval/tuned.json
sed -n '1,240p' eval/tuned.json
```

- [ ] Compare baseline and tuned outputs without relying on memory.

```bash
diff -u eval/baseline.json eval/tuned.json || true
```

- [ ] Write a decision note that explicitly keeps, iterates, or discards the adapter.

```bash
cat > logs/decision.md <<'EOF'
# Decision

Task: support ticket priority as strict JSON
Base model: HuggingFaceTB/SmolLM2-135M-Instruct
Adapter path: artifacts/adapter
Decision: keep for more testing, iterate, or discard

Evidence:
- Baseline JSON adherence:
- Tuned JSON adherence:
- Label quality on held-out prompts:
- Runtime used for comparison:
- Remaining failure modes:

Next action:
EOF
sed -n '1,120p' logs/decision.md
```

- [ ] Keep only traceable artifacts and remove any throwaway outputs that are not tied to the saved config or evaluation.

```bash
find data eval artifacts logs scripts -maxdepth 3 -type f | sort
```

Success criteria:

- [ ] You can explain why this task is a fine-tuning candidate instead of a retrieval problem.
- [ ] `data/train.jsonl` and `eval/check.jsonl` are separate files with one consistent output contract.
- [ ] The experiment records hardware, package versions, checksums, config, baseline outputs, tuned outputs, and a decision note.
- [ ] The adapter path is traceable to a base model, dataset, LoRA configuration, and evaluation set.
- [ ] The keep-or-discard decision is based on baseline-versus-tuned behavior, not on whether training merely completed.
- [ ] Any failure leads to a specific next change, such as cleaner labels, smaller model, lower sequence length, supported quantization, or a retrieval-based redesign.

---

## Next Module

- [Multi-GPU and Home-Lab Fine-Tuning](../module-1.11-multi-gpu-home-lab-fine-tuning/)

## Sources

- [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685) — Original LoRA paper for freezing base weights, training low-rank adapters, and PEFT trade-offs versus full fine-tuning.
- [QLoRA: Efficient Finetuning of Quantized LLMs](https://arxiv.org/abs/2305.14314) — 4-bit NF4 quantization, double quantization, paged optimizers, and single-GPU memory claims.
- [PEFT documentation](https://huggingface.co/docs/peft/index) — Library reference for LoRA/QLoRA configuration and adapter saving.
- [bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes) — 4-bit and 8-bit CUDA kernels used by QLoRA loading paths.
- [Transformers Trainer](https://huggingface.co/docs/transformers/en/main_classes/trainer) — Training loop, checkpointing, and gradient accumulation integration.
- [Accelerate](https://huggingface.co/docs/accelerate/index) — Device placement and mixed-precision helpers for local training scripts.
- [TRL](https://huggingface.co/docs/trl/index) — Supervised fine-tuning trainers commonly paired with PEFT adapters.
- [PyTorch AMP examples](https://pytorch.org/docs/stable/notes/amp_examples.html) — Autocast and gradient scaling patterns relevant to fp16/bf16 fine-tuning.
- [Hugging Face Transformers documentation](https://huggingface.co/docs/transformers/index) — Model loading, tokenizers, and generation APIs used throughout the hands-on exercise.
- [bitsandbytes installation guide](https://huggingface.co/docs/bitsandbytes/installation) — Hardware and CUDA prerequisites for 4-bit loaders used by QLoRA paths.
