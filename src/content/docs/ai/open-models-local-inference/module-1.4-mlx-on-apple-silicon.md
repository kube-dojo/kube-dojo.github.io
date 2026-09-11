---
citations_verified: true
title: "MLX on Apple Silicon"
slug: ai/open-models-local-inference/module-1.4-mlx-on-apple-silicon
sidebar:
  order: 4
---

> **Open Models & Local Inference** | Complexity: `[MEDIUM]` | Time: 55-75 min | Prerequisites: Python virtual environments, basic terminal use, and the previous modules on local model runtimes

## Learning Outcomes

By the end of this module, you will be able to:

1. **Compare** MLX with Ollama, Transformers, and Linux GPU inference paths, then choose a runtime that matches an Apple Silicon learner's hardware, model size, and learning goal.
2. **Design** a small MLX-based local inference workflow that separates environment setup, model selection, prompt execution, measurement, and cleanup.
3. **Debug** common MLX setup and inference failures by checking processor architecture, macOS version, Python version, model format, memory pressure, and command syntax.
4. **Evaluate** when MLX is a good Mac-native learning path and when a team should move toward GGUF tools, Hugging Face engineering workflows, CUDA infrastructure, or production serving.
5. **Justify** a model and runtime decision for a realistic local AI experiment using constraints such as unified memory, latency, privacy, reproducibility, and future portability.

## Why This Module Matters

A learner opens a new MacBook, installs a popular local model tool, and quickly hits a confusing question: is the Mac a serious machine for open-model learning, or is it only a convenient terminal for cloud GPUs? The wrong answer pushes that learner toward unnecessary infrastructure before they understand the shape of local inference. The right answer is more useful: Apple Silicon has its own runtime lane, and MLX is the most direct way to study that lane without pretending the machine is a smaller CUDA workstation.

This matters because hardware shapes learning. A learner with an M-series Mac has unified memory, an integrated GPU, a neural engine, good battery life, and a mature desktop operating system. Those constraints are not the same constraints as a Linux server with an NVIDIA card. If the learner copies every command from a CUDA tutorial, they may learn a lot about installation pain and very little about model behavior, prompt latency, context windows, quantization trade-offs, or inference measurement.

MLX changes the beginner conversation because it gives Apple Silicon learners a native framework to explore arrays, model loading, token generation, quantization, and local experimentation. It also changes the senior conversation because a native laptop workflow can become a fast prototyping lane for privacy-sensitive demos, evaluation scripts, model comparisons, and pre-production design discussions. The point is not that every production system should run on a laptop. The point is that a laptop can teach the core mechanics before infrastructure complexity becomes the main subject.

The senior skill is knowing where the boundary sits. MLX is excellent when the machine, runtime, and learning goal line up. It is weaker when you need a shared service, multi-user scheduling, GPU fleet utilization, Kubernetes deployment, or compatibility with a production serving stack. A strong practitioner can use MLX without turning it into a religion. They can explain why it works, what it hides, where it breaks, and when another runtime is the better engineering choice.

## 1. Start With The Problem MLX Solves

[MLX is a machine learning framework from Apple's machine learning research group, designed around Apple Silicon hardware.](https://github.com/ml-explore/mlx) The practical learner version is simpler: MLX gives M-series Mac users a native path for running and studying machine learning workloads without first translating everything through a CUDA mental model. For open-model learners, the most visible package is usually `mlx-lm`, which [provides command-line and Python workflows for loading, generating with, quantizing, and fine-tuning language models](https://github.com/ml-explore/mlx-lm).

The problem MLX solves is not merely "run a model on a Mac." Other tools can do that too, and some are easier for casual chat. The deeper problem is that learners need a path where the runtime matches the hardware well enough that experiments feel real. If every test is dominated by compatibility layers, missing acceleration, or unclear memory behavior, the learner's mental model becomes distorted. They may conclude that local models are fragile when the actual problem was a mismatched runtime.

Apple Silicon is different from the classic desktop GPU setup because [CPU and GPU share unified memory](https://github.com/ml-explore/mlx). That does not make memory infinite, and it does not magically turn every model into a laptop-sized workload. It does mean that the boundary between "CPU memory" and "GPU memory" feels different from a discrete GPU system where model weights must fit into a separate VRAM budget. MLX was built with that environment in mind, so it is a strong first runtime when the goal is to learn locally on a Mac.

```ascii
+--------------------------------------------------------------------------------+
|                         Apple Silicon Local Inference Path                      |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Learner Goal                                                                  |
|  "Run and study an open model on the Mac I already own."                        |
|                                                                                |
|        |                                                                       |
|        v                                                                       |
|  +------------------+      +------------------+      +----------------------+   |
|  | Native Python    | ---> | mlx / mlx-lm     | ---> | Apple Silicon        |   |
|  | virtual env      |      | model workflow   |      | unified memory + GPU |   |
|  +------------------+      +------------------+      +----------------------+   |
|        |                         |                          |                  |
|        v                         v                          v                  |
|  install cleanly          load MLX model              measure output, latency   |
|  reproduce commands       generate tokens             and memory pressure       |
|                                                                                |
+--------------------------------------------------------------------------------+
```

The diagram shows the main teaching idea: the learner should see one coherent path from environment setup to model execution to measurement. MLX is useful because it reduces the number of unrelated problems in that path. Instead of debugging Docker images, CUDA drivers, or remote GPU billing before any model runs, the learner can focus on model selection, prompt shape, token generation, and resource use.

**Active Learning Prompt:** Before reading further, decide which failure would teach you more about local inference: a model that cannot start because the Python environment is wrong, or a model that starts but becomes slow when the prompt grows. The second failure teaches more about inference behavior because it happens after the runtime is working; the first failure mostly teaches setup hygiene.

## 2. What MLX Is, And What It Is Not

MLX is an array framework and machine learning stack that can be used directly, but most local LLM learners meet it through `mlx-lm`. That distinction matters because "MLX" can mean the lower-level framework, while "MLX LM" is the package that turns that framework into a practical language-model workflow. When you install `mlx-lm`, you are choosing a path where the model loading and generation commands are already shaped for LLM work.

A useful mental model is to separate the runtime layer from the model workflow layer. The runtime layer handles computation on the machine. The workflow layer handles questions like which model to load, how to apply a chat template, how many tokens to generate, and how to stream output. Senior engineers keep those layers separate because failures can occur in either place. A model-format mismatch is not the same thing as a broken accelerator, and a bad prompt template is not the same thing as insufficient memory.

```ascii
+--------------------------------------------------------------------------------+
|                              MLX Layer Model                                    |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Application Goal                                                              |
|  "Ask a local model to classify support tickets."                              |
|                                                                                |
|        |                                                                       |
|        v                                                                       |
|  +----------------------+                                                       |
|  | Your script or CLI   |  prompt, sampling options, output handling            |
|  +----------------------+                                                       |
|        |                                                                       |
|        v                                                                       |
|  +----------------------+                                                       |
|  | mlx-lm workflow      |  load model, apply tokenizer, generate tokens         |
|  +----------------------+                                                       |
|        |                                                                       |
|        v                                                                       |
|  +----------------------+                                                       |
|  | MLX framework        |  arrays, operations, device execution                 |
|  +----------------------+                                                       |
|        |                                                                       |
|        v                                                                       |
|  +----------------------+                                                       |
|  | Apple Silicon Mac    |  unified memory, integrated GPU, macOS runtime        |
|  +----------------------+                                                       |
|                                                                                |
+--------------------------------------------------------------------------------+
```

MLX is not a drop-in replacement for every local inference tool. [Ollama is often easier for a quick chat server](https://github.com/ollama/ollama/blob/main/README.md), [GGUF-based tools are widely used across different machines](https://github.com/ggml-org/llama.cpp/blob/master/README.md), [Hugging Face Transformers is a broad engineering ecosystem](https://huggingface.co/docs/transformers/v4.48.0/en/index), and [vLLM is built for high-throughput serving rather than laptop learning](https://github.com/vllm-project/vllm/blob/main/README.md). MLX is best understood as a Mac-native technical lane that can be excellent for learning and prototyping, especially when the learner wants to see how a model is loaded and called from Python.

That framing prevents two opposite mistakes. The first mistake is dismissing MLX because it is not the dominant production serving stack. The second mistake is overselling MLX as if every learner should use it for every local model task. Both mistakes flatten the decision. A strong practitioner asks: what is the machine, what is the goal, what model format is available, what operational behavior matters, and what will the learner need to transfer later?

| Runtime path | Best first use | Strength on Apple Silicon | Trade-off to evaluate |
|---|---|---|---|
| MLX / MLX LM | Studying native Mac inference and Python model workflows | Built around Apple Silicon assumptions and convenient for MLX-compatible models | Not every tutorial, model, or production stack is MLX-first |
| Ollama | Fast local chat and simple local model serving | Very approachable and good for quick experiments | Hides more runtime detail from learners who need to study mechanics |
| Hugging Face Transformers | Portable model engineering and broad ecosystem work | Strong for code-level workflows when dependencies support the machine | Setup and performance can vary by backend and model |
| GGUF tools | Cross-platform quantized local inference | Mature local-model ecosystem and broad model availability | Model conversion and runtime behavior differ from MLX workflows |
| Linux CUDA stack | GPU-heavy training, serving, and production patterns | Not native to the Mac, but essential for many production teams | Requires different hardware assumptions and more infrastructure knowledge |

The table is not a ranking. It is a decision matrix. If the learner wants the shortest path to chatting with a model, Ollama may be the right first step. If the learner wants to understand Apple Silicon-native inference from Python, MLX is a stronger teaching path. If the team is planning a multi-user inference platform, the laptop experiment should be treated as a prototype, not as the deployment architecture.

## 3. Prepare A Clean MLX Environment

A clean environment is not busywork; it is part of the experiment. Local inference combines Python packages, native libraries, model files, tokenizer behavior, and hardware assumptions. If the environment is messy, failures become ambiguous. The learner cannot tell whether a crash came from a missing package, the wrong Python interpreter, an unsupported machine, a model that is too large, or a runtime incompatibility.

For a KubeDojo learner, the first engineering habit is to make the experiment reproducible. Use a dedicated directory, create a virtual environment, record the Python version, and run a minimal command before attempting a larger model. This mirrors the way senior engineers reduce blast radius in production: isolate the change, verify the smallest useful path, then add complexity.

```bash
mkdir -p mlx-local-lab
cd mlx-local-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install mlx-lm
python -c "import platform; print(platform.machine())"
```

The final command should report an Apple Silicon architecture such as `arm64` on a native Python install. If it reports an unexpected architecture, stop before downloading models. A non-native interpreter can make a good Mac behave like the wrong machine. That kind of failure is frustrating because the hardware is capable, but the software path prevents MLX from using it correctly.

You can then run a small generation command. The default model used by `mlx-lm` may change over time, so a serious lab should name the model explicitly when reproducibility matters. For a first smoke test, keep the prompt short and the token count modest. The goal is not to judge model intelligence yet; the goal is to prove that the local runtime can load a model, tokenize a prompt, generate text, and return control to the shell.

```bash
mlx_lm.generate \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --prompt "Explain local inference in two practical sentences." \
  --max-tokens 80
```

If the command succeeds, you have proven the basic path. You have not proven that the model is the best choice, that performance is acceptable, that long prompts fit comfortably, or that the workflow is production-ready. That distinction is important because beginners often treat the first successful generation as the end of the lesson. In reality, it is only the baseline that makes useful experiments possible.

If the command fails, read the error as a diagnostic clue instead of as a verdict on MLX. Package import errors point toward environment setup. Architecture errors point toward the Python interpreter or machine. Model download errors point toward network or repository access. Out-of-memory behavior points toward model size, quantization, prompt length, or other applications consuming memory. A senior engineer narrows the failure domain before changing many things at once.

```bash
python - <<'PY'
import platform
import sys

print("python:", sys.version.split()[0])
print("machine:", platform.machine())
print("processor:", platform.processor())
print("platform:", platform.platform())
PY
```

This diagnostic script is intentionally small and runnable. It does not prove MLX performance, but it gives you a baseline to paste into notes or a support request. When debugging local inference, always capture the environment before changing it. Otherwise, you may fix the problem accidentally and lose the evidence that would help another learner.

**Active Learning Prompt:** Suppose `mlx_lm.generate` fails on a Mac that definitely has an M-series chip. What would you check first: model quality, Python architecture, or prompt wording? Check Python architecture first, because a model cannot demonstrate quality and a prompt cannot matter until the runtime is executing in the expected environment.

## 4. Choose A Model Like An Engineer

Model choice is where MLX becomes more than an installation exercise. A learner often asks, "What is the biggest model I can run?" A practitioner asks a better question: "What is the smallest model that can answer the question I am testing with acceptable behavior?" That shift matters because local inference is a constraints exercise. Model size, quantization, context length, memory pressure, latency, and task quality all move together.

For a first Apple Silicon MLX experiment, a quantized instruction model in the small-to-medium range is usually a better teaching model than a large model that barely fits. A smaller model starts faster, fails less dramatically, and gives the learner more repetitions. Repetition matters because the learner needs to vary prompts, measure latency, observe output drift, and compare settings. A model that consumes all available memory turns every experiment into a waiting game.

A useful model-selection process has four steps. First, define the task in one sentence, such as "summarize short support tickets" or "classify command output into likely causes." Second, choose a model family with an MLX-compatible repository. Third, choose a quantized variant that leaves memory headroom for the operating system and other applications. Fourth, run a fixed set of prompts so you can compare results instead of relying on impressions.

```ascii
+--------------------------------------------------------------------------------+
|                            Model Selection Funnel                               |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Task: What behavior do you need to test?                                       |
|    |                                                                           |
|    v                                                                           |
|  Model family: Is there an MLX-compatible version available?                    |
|    |                                                                           |
|    v                                                                           |
|  Size and quantization: Does it fit with memory headroom?                       |
|    |                                                                           |
|    v                                                                           |
|  Prompt set: Can you compare multiple runs against the same scenarios?          |
|    |                                                                           |
|    v                                                                           |
|  Decision: Keep, downsize, change runtime, or move to another machine.          |
|                                                                                |
+--------------------------------------------------------------------------------+
```

The funnel is deliberately conservative. It keeps the learner from turning model selection into a popularity contest. A model that is impressive in a benchmark may be a poor fit for a laptop lab if it leaves no room for context or repeated tests. A smaller model that runs reliably can teach more because the learner can observe cause and effect.

Here is a worked example. A team wants to prototype a local assistant that rewrites rough incident notes into a concise handoff. The notes are short, privacy matters, and the team wants to experiment on Mac laptops before deciding whether to build a shared service. MLX is a reasonable first runtime because the task is local, the prompts are small, and Python scripting is useful for repeatable comparisons. A small quantized instruction model is a reasonable first model because the team needs iteration speed more than maximum reasoning depth.

```bash
cat > incident_prompt.txt <<'EOF'
Rewrite the following incident notes into a concise handoff for the next engineer.

Notes:
- checkout errors started after the 09:15 deployment
- logs show database timeout spikes
- rollback reduced errors but did not clear queue backlog
- next shift should check worker saturation and slow queries
EOF

mlx_lm.generate \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --prompt "$(cat incident_prompt.txt)" \
  --max-tokens 160
```

After the first run, the team should not immediately declare success. They should ask whether the output preserves the important details, whether it invents facts, whether the latency is acceptable, and whether a repeated run is stable enough for the intended workflow. If the model drops the rollback detail or invents a root cause, the team can adjust the prompt, try another model, or conclude that this class of task needs stronger evaluation before adoption.

Now compare that with a different scenario. A platform team wants to serve many users through an internal API with access controls, monitoring, queues, and throughput targets. MLX on a laptop can still be useful for early prompt experiments, but it is not the obvious final serving path. The team should evaluate server-oriented runtimes and deployment patterns once the problem moves from "can this model help?" to "can we operate this reliably for many users?"

| Decision question | MLX-friendly answer | Move beyond MLX when |
|---|---|---|
| Who is the user? | One learner, one developer, or a small local prototype | Many users need a shared service with predictable capacity |
| Where is the data? | Local files or privacy-sensitive samples on the Mac | Data already lives in a governed server-side workflow |
| What is the goal? | Learn, prototype, compare prompts, or script experiments | Provide production latency, quotas, audit logs, and uptime |
| How portable must it be? | Mac-first workflow is acceptable for the team | Linux deployment parity is required from the start |
| How much control is needed? | Python-level model loading and generation are useful | A standardized API gateway or inference platform is required |

The senior-level decision is not "MLX or not MLX." It is "MLX for which phase of the lifecycle?" A local MLX script can be the right tool for discovery, while a different runtime becomes the right tool for serving. Good engineering preserves what was learned in the prototype without confusing the prototype with the final architecture.

## 5. Run And Inspect A Python Workflow

The command-line interface is the quickest proof that the runtime works, but Python is where MLX becomes a learning tool. Python lets you wrap model calls in repeatable scripts, store prompts in files, compare outputs, time runs, and build small evaluation harnesses. That is the bridge from casual local inference to engineering practice.

The following script loads a model, applies a chat template when available, generates an answer, and prints timing information. It is intentionally small enough to read in one sitting. The goal is not to build a complete evaluation framework yet. The goal is to show the moving parts that a learner must understand before they can debug or extend the workflow.

```bash
cat > run_mlx_prompt.py <<'PY'
import time
from mlx_lm import generate, load

MODEL = "mlx-community/Llama-3.2-3B-Instruct-4bit"

messages = [
    {
        "role": "user",
        "content": (
            "You are helping a developer choose a local inference runtime. "
            "Compare MLX and a Linux CUDA stack for a privacy-sensitive Mac prototype."
        ),
    }
]

started = time.perf_counter()
model, tokenizer = load(MODEL)
loaded = time.perf_counter()

if hasattr(tokenizer, "apply_chat_template"):
    prompt = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
    )
else:
    prompt = messages[0]["content"]

text = generate(
    model,
    tokenizer,
    prompt=prompt,
    max_tokens=180,
    verbose=False,
)

finished = time.perf_counter()

print("model:", MODEL)
print("load_seconds:", round(loaded - started, 2))
print("generate_seconds:", round(finished - loaded, 2))
print("response:")
print(text)
PY

python run_mlx_prompt.py
```

This script teaches several important mechanisms. The `load` call brings the model and tokenizer into the process. The tokenizer prepares text in the format the model expects. [The chat template matters because instruction-tuned models are often trained with special message formatting.](https://huggingface.co/docs/transformers/main/chat_templating_writing) The generation call turns the prompt into output tokens. The timing measurements separate model load time from generation time, which helps the learner avoid vague complaints like "it is slow" when the slow part may only be the first load.

The script also demonstrates a serious local-inference habit: keep the model identifier visible. When learners copy snippets from different examples, they often forget which model they actually tested. That makes comparison impossible. Every meaningful local inference note should include the model, runtime, machine, prompt shape, token limit, and observed behavior.

You can extend the script to test multiple prompts. The important design choice is to keep the prompts stable across runs. If both the prompt and the model change at the same time, you cannot tell which change caused the output difference. This is the same experimental discipline used in performance testing, debugging, and production incident analysis.

```bash
cat > compare_prompts.py <<'PY'
import time
from mlx_lm import generate, load

MODEL = "mlx-community/Llama-3.2-3B-Instruct-4bit"

prompts = {
    "short_decision": "Recommend a local inference runtime for a Mac-only prototype.",
    "debug_setup": "A learner installed mlx-lm but generation fails before downloading a model. What should they check?",
    "runtime_boundary": "Explain when a team should move from MLX prototyping to a server-oriented inference stack.",
}

model, tokenizer = load(MODEL)

for name, prompt in prompts.items():
    started = time.perf_counter()
    output = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=140,
        verbose=False,
    )
    elapsed = time.perf_counter() - started
    print(f"\n=== {name} ===")
    print(f"seconds={elapsed:.2f}")
    print(output)
PY

python compare_prompts.py
```

This is the first step toward evaluation. It does not score the model, but it makes comparison possible. A senior engineer would later add expected properties, failure labels, regression prompts, and perhaps human review. The beginner should first learn the simple discipline of changing one variable at a time.

**Active Learning Prompt:** If the second script gives one excellent answer and two weak answers, should you immediately replace MLX with another runtime? Probably not. The first question is whether the weakness comes from the prompt, the model, the token limit, or the task itself; the runtime is only one part of the chain.

## 6. Debug MLX By Following The Failure Domain

Debugging local inference is easier when you classify the failure before you try fixes. Beginners often reinstall packages, change models, restart terminals, and switch tools all in the same session. That sometimes makes the error disappear, but it does not produce understanding. A better approach is to locate the failure domain and run the smallest check that can confirm or reject it.

There are five common domains: machine compatibility, Python environment, package installation, model access, and runtime resource pressure. Machine compatibility asks whether this is actually the right hardware and operating system path. Python environment asks whether the interpreter is native and isolated. Package installation asks whether `mlx-lm` and its dependencies import correctly. Model access asks whether the requested model exists and can be downloaded. Runtime resource pressure asks whether the model and prompt fit comfortably on the machine.

```ascii
+--------------------------------------------------------------------------------+
|                              MLX Debugging Map                                  |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Error appears before Python starts                                            |
|      -> check shell, virtual environment activation, command spelling           |
|                                                                                |
|  Error appears during import                                                    |
|      -> check package install, Python version, native architecture              |
|                                                                                |
|  Error appears during model download                                            |
|      -> check model name, network, repository access, local disk space          |
|                                                                                |
|  Error appears while loading weights                                            |
|      -> check model size, quantization, available memory, other applications    |
|                                                                                |
|  Error appears during generation                                                |
|      -> check prompt length, token limit, chat template, sampling options       |
|                                                                                |
+--------------------------------------------------------------------------------+
```

The map is a practical alternative to panic. If Python cannot import the package, changing the prompt cannot help. If the model identifier is wrong, closing browser tabs will not help. If memory pressure appears during weight loading, reinstalling `pip` is noise. Each symptom points to a narrower set of checks.

A worked debugging example makes the process concrete. Imagine a learner says, "MLX is broken; the command fails." The first useful question is where it fails. If the shell says `command not found: mlx_lm.generate`, the package may not be installed in the active environment, or the learner may need to use the module form if the console script is unavailable. If Python says the module cannot be imported, the environment is wrong. If the model download starts and then fails, the runtime is probably installed and the problem has moved to model access.

```bash
source .venv/bin/activate

python - <<'PY'
import mlx
import mlx_lm

print("mlx import: ok")
print("mlx_lm import: ok")
PY

python -m mlx_lm.generate \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --prompt "Say one sentence about MLX." \
  --max-tokens 40
```

The module form, `python -m mlx_lm.generate`, is useful because it proves which Python interpreter is running the command. That matters in environments where shell entry points can become confusing. If the module form works but the direct command does not, the issue is likely the shell path rather than MLX itself. That is a valuable diagnostic result, not a failure.

Memory debugging requires a different mindset. If a model loads slowly, swaps heavily, or causes the machine to become unresponsive, choose a smaller or more aggressively quantized model before blaming the framework. Unified memory makes some workflows convenient, but it still has limits. Local inference should leave headroom for macOS, the terminal, the editor, browser tabs, and the prompt context itself.

| Symptom | Likely domain | Better first check | Risky reaction |
|---|---|---|---|
| `command not found` | Shell or environment path | Activate the virtual environment and try `python -m mlx_lm.generate` | Reinstalling unrelated packages repeatedly |
| `ModuleNotFoundError` | Python environment | Confirm `python -m pip show mlx-lm` inside the active environment | Switching models before imports work |
| Architecture looks wrong | Native interpreter | Print `platform.machine()` and confirm a native Apple Silicon Python | Assuming the hardware is too weak |
| Model repository not found | Model access or identifier | Copy the model name carefully and test a known MLX model | Changing runtime settings blindly |
| Machine becomes sluggish | Memory pressure | Try a smaller quantized model and reduce prompt size | Opening more tools to watch the slowdown |
| Output ignores instructions | Prompt or chat formatting | Apply the model's chat template and test a simpler prompt | Treating all poor output as runtime failure |
| First token is slow | Load or warm-up behavior | Separate model load time from generation time | Judging all future runs by the first run |
| Repeated runs differ too much | Sampling or prompt ambiguity | Control prompt wording and generation options | Declaring the model useless after one run |

The debugging lesson is transferable beyond MLX. Every local runtime has layers, and every layer can fail in a different way. MLX gives Mac learners a clean place to practice that layered reasoning because the environment can be small enough to understand.

## 7. Compare Runtimes With A Controlled Test

Runtime comparison becomes useful only after you control the variables that are not the runtime. If one test uses a different prompt, a different model family, and a different token budget, the result does not tell you whether MLX, Ollama, Transformers, or a GGUF tool behaved better. It tells you that several things changed at once. A controlled test fixes the task first, then records the remaining differences honestly.

For this module, use a small task that can be judged without a benchmark harness: rewrite rough operational notes into a concise handoff. The task is short enough for laptop testing, but it still reveals important behavior. A good answer preserves the deployment time, the database timeout signal, the queue backlog, and the next checks. A bad answer may sound fluent while inventing a root cause or dropping the queue detail.

The comparison artifact should name the task, prompt file, model identifier, runtime, token limit, sampling settings, and observed result. That may feel formal for a laptop experiment, but it prevents the most common comparison error: remembering the strongest answer from one tool and the weakest answer from another. The record does not need to be elaborate. It needs to be complete enough that another learner can repeat the run.

```bash
cat > runtime-comparison.md <<'EOF'
# Runtime Comparison: Incident Handoff

Task:
Rewrite synthetic incident notes into a concise handoff.

Prompt file:
handoff_prompt.txt

Success criteria:
- Preserve deployment timing without claiming proven causality.
- Preserve database timeout and queue backlog signals.
- Avoid invented root cause statements.
- Return a concise handoff within the chosen token budget.

Runs:
| Runtime | Model | Token limit | Settings | Result notes |
|---|---|---:|---|---|
| MLX LM | mlx-community/Llama-3.2-3B-Instruct-4bit | 180 | default sampling | fill in after run |
| Other runtime | comparable model if available | 180 | record defaults | fill in after run |
EOF
```

This file separates model evidence from runtime evidence in a concrete way. Model evidence is about whether the chosen weights and prompt produce useful text. Runtime evidence is about installation path, load time, generation time, resource pressure, and how much control the tool gives you over the experiment. If the MLX run preserves the facts and another runtime drops them, check whether the models were comparable before claiming a runtime victory.

A fair test also records what the tool hides. Ollama may make a local chat workflow fast to start, but the learner should still identify the model artifact and quantization used for the run. Transformers may expose tokenization and generation settings more directly, but setup can add dependency work that is unrelated to the handoff task. GGUF-based tools may make cross-platform quantized inference easier to compare across machines, while MLX gives the Mac learner a native Python path for the same kind of prompt experiment.

```ascii
+--------------------------------------------------------------------------------+
|                         Controlled Runtime Comparison                           |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Fixed across runs                                                             |
|    task -> prompt file -> token limit -> success criteria                       |
|                                                                                |
|  Recorded per run                                                              |
|    runtime -> model artifact -> settings -> load time -> generation time        |
|                                                                                |
|  Judged after runs                                                             |
|    fact preservation -> invented claims -> latency -> setup friction            |
|                                                                                |
+--------------------------------------------------------------------------------+
```

The diagram is a checklist, not a ranking. A Mac-native MLX run can win the setup and scripting category while another runtime wins cross-platform availability. A GGUF run can be easier to share with non-Mac users while the MLX run remains easier for an Apple Silicon learner to inspect from Python. The useful result is not a trophy; it is a written explanation of which constraint mattered most for this task.

**Active Learning Prompt:** Before you compare two runtime outputs, write down one reason the model could be responsible for a difference and one reason the runtime could be responsible. That short separation protects you from treating every output-quality problem as a tool problem.

## 8. Record Artifact, Version, And Timing Evidence

An MLX experiment becomes reusable when the run record is specific enough to reconstruct. The model identifier is the first piece, but it is not the whole record. A useful note also captures the Python version, package versions, machine architecture, prompt file, token limit, and timing split between loading and generation. Those fields turn "it worked on my Mac" into evidence another person can inspect.

The timing split matters because first-run behavior can be misleading. A slow first command may include model download, cache population, tokenizer load, weight loading, and generation. A later command may skip several of those costs. If you report only wall-clock time for the whole command, you may blame generation for work that happened before the first token could be produced.

```bash
cat > run_record.py <<'PY'
import json
import platform
import subprocess
import time
from pathlib import Path

from mlx_lm import generate, load

MODEL = "mlx-community/Llama-3.2-3B-Instruct-4bit"
PROMPT_PATH = Path("handoff_prompt.txt")
MAX_TOKENS = 180

def package_version(name: str) -> str:
    result = subprocess.run(
        ["python", "-m", "pip", "show", name],
        check=False,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return "not-found"

prompt = PROMPT_PATH.read_text()

load_started = time.perf_counter()
model, tokenizer = load(MODEL)
load_finished = time.perf_counter()

generate_started = time.perf_counter()
output = generate(
    model,
    tokenizer,
    prompt=prompt,
    max_tokens=MAX_TOKENS,
    verbose=False,
)
generate_finished = time.perf_counter()

record = {
    "model": MODEL,
    "prompt_file": str(PROMPT_PATH),
    "max_tokens": MAX_TOKENS,
    "machine": platform.machine(),
    "platform": platform.platform(),
    "mlx_lm_version": package_version("mlx-lm"),
    "mlx_version": package_version("mlx"),
    "load_seconds": round(load_finished - load_started, 2),
    "generate_seconds": round(generate_finished - generate_started, 2),
    "output_preview": output[:300],
}

Path("run-record.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
PY

python run_record.py
```

This script uses `pip show` because package metadata is easy to paste into a lab note. It is not a full observability system, and it does not measure tokens per second directly. It does, however, capture enough context to answer practical questions. Did the experiment use the intended model? Was the interpreter native to the machine? Did most time disappear into loading or generation? Were the package versions known when the result was discussed?

For a richer local study, add a small prompt suite instead of a single prompt. Keep each prompt in a file, run the same model against each file, and record whether the output preserved required facts. That gives you a miniature regression set. If a prompt edit improves one case and breaks another, the run record shows the trade-off immediately.

```bash
mkdir -p prompts
cp handoff_prompt.txt prompts/handoff-basic.txt

cat > prompts/handoff-causal-risk.txt <<'EOF'
Rewrite the notes into a handoff. Do not claim a root cause unless the notes prove it.

Notes:
- errors increased after a deployment
- database timeouts and queue backlog are both visible
- rollback helped new errors but backlog remains
- next engineer should inspect worker saturation and slow queries
EOF
```

The second prompt tests a specific behavior: whether the model can avoid overstating causality. That is different from testing whether generation works. A healthy runtime can still run a model that makes a poor judgment, and a careful prompt can sometimes reduce that risk. When the test names the behavior, the learner can improve the workflow without changing unrelated parts of the stack.

Finally, record license and data-handling notes before using real internal examples. MLX execution can keep inference local, but the model artifact still has a license and the generated output can still be stored, synced, or pasted somewhere inappropriate. A good lab uses synthetic notes until the team has approved the model, the data category, and the storage location for outputs.

## 9. Manage Caches, Disk, And Repeat Runs

Local model experiments leave traces on disk, and those traces affect later tests. Package wheels live in one cache, model artifacts usually live under a hub cache, and your project directory may contain prompt files, generated notes, and run records. If you do not know which files are part of the experiment, you may accidentally compare a cold model download against a warm cached run or share output files that were only meant for a private lab.

Start by measuring disk use before you remove anything. Model caches can be large, and a learner who downloads several quantized variants may run out of space before they run out of ideas. The goal is not to memorize one cache path forever. The goal is to recognize that model artifacts are persistent local state, and persistent state belongs in the experiment record when it changes timing or reproducibility.

```bash
du -sh . 2>/dev/null || true
du -sh ~/.cache/huggingface 2>/dev/null || true
python -m pip cache info
```

Those commands answer different questions. The project directory size tells you how much local lab material you created. [The Hugging Face cache size shows whether model downloads are accumulating outside the project.](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache) The pip cache output tells you about package downloads, not model weights. Keeping those categories separate prevents a common cleanup mistake: deleting the virtual environment and wondering why the model cache still consumes disk space.

For repeatable runs, create a short manifest after the environment is working. `pip freeze` is not a perfect software bill of materials, but it is useful for a learner-scale lab because it records the installed Python packages at the moment of the test. Pair it with the run record from the previous section and the prompt files used in the comparison. That small bundle is enough for a reviewer to see whether the result came from a stable setup or from a drifting shell session.

```bash
python -m pip freeze > requirements-run.txt
ls -lh handoff_prompt.txt run-record.json requirements-run.txt
```

A clean rerun should be deliberate. If you want to measure warm-generation behavior, keep the downloaded model cache and report that the model was already present. If you want to measure the full first-use experience, say that explicitly and expect download time to dominate. Do not mix those measurements in the same conclusion. A learner who reports "generation took several minutes" after including a first download is describing onboarding time, not token generation behavior.

Environment cleanup should also be scoped. Removing the lab virtual environment resets Python packages for that directory, but it does not remove model artifacts stored in a user cache. Removing prompt and output files resets the task material, but it does not change package versions. Removing model cache entries forces future downloads, but it does not prove the model will behave differently. Name the state you are resetting before you reset it.

```bash
cat > cleanup-note.md <<'EOF'
# Cleanup Note

Kept:
- prompt files
- run-record.json
- requirements-run.txt

Reset for next test:
- virtual environment packages will be recreated

Not reset:
- downloaded model cache
- previous runtime-comparison.md notes
EOF
```

This note may seem more careful than a beginner lab needs, but it teaches the habit that makes local inference experiments trustworthy. A future rerun can explain why it became faster, why it used less network, or why a package version changed. Without the note, the learner may attribute every difference to MLX or the model when the real cause was cached state.

One more practical detail belongs in the run record: whether the model was already present before the command began. You can capture that as a plain sentence rather than trying to inspect every internal cache file. Write "model already cached" when the download had happened before the measurement, and write "first local download included" when network transfer was part of the timing. That distinction makes a timing note honest without turning a beginner lab into cache forensics.

If a learner needs to hand the experiment to another Mac user, share the prompt files, the run record, and the package manifest before sharing generated output. The receiving learner can recreate the environment, run the same prompt, and compare behavior without depending on another person's prose summary. Generated answers are still useful, but they are evidence after the reproducible inputs, not a substitute for them.

**Active Learning Prompt:** If a second run is much faster than the first, which three cached or already-loaded states could explain the difference? Name them before you change the model, because the answer may be model download cache, weight loading behavior, or a Python environment that no longer needs package installation.

## Did You Know?

1. MLX is designed around Apple Silicon assumptions, which makes it a useful way to study local inference on the same class of machine many learners already use every day.
2. `mlx-lm` is not just a chat command; it also exposes Python workflows that help learners inspect loading, prompting, generation, and repeatable evaluation scripts.
3. Unified memory can make local model experimentation feel smoother than discrete VRAM workflows, but it still requires headroom for the operating system, prompts, and other applications.
4. A successful MLX laptop prototype can produce valuable evaluation prompts and task insight even when the final serving platform later moves to Linux GPUs or managed infrastructure.

## Common Mistakes

| Mistake | Why It Hurts | Better Move |
|---|---|---|
| Running a non-native Python interpreter | MLX may install or run through the wrong architecture path, which makes hardware diagnosis misleading | Print `platform.machine()` inside the active environment and use a native Apple Silicon Python |
| Trusting a shell command before checking imports | A broken entry point can look like a framework failure even when the package is installed elsewhere | Test `import mlx_lm` and try `python -m mlx_lm.generate` from the same virtual environment |
| Choosing the largest model first | A model that barely fits can create memory pressure, slow iteration, and confusing failures | Start with a smaller quantized model that leaves headroom for macOS, the prompt, and repeated tests |
| Skipping the chat template | Instruction models may receive text in a format that does not match their training convention | Use the tokenizer's chat template when available and record whether the script applied it |
| Comparing runtimes with different tasks | The team cannot tell whether the model, prompt, token limit, or runtime caused the difference | Fix the prompt, task, token budget, and success criteria before comparing runtime behavior |
| Reporting only whole-command time | Download, cache, and weight loading costs get mixed with generation latency | Separate model load time from generation time in the Python runner |
| Recording output without artifact details | Another learner cannot reproduce or challenge the result without knowing what actually ran | Save the model identifier, package versions, machine architecture, prompt file, and token limit |
| Testing with real sensitive notes too early | Local execution does not remove license, retention, sharing, or policy obligations | Use synthetic notes until the model license, data category, and output storage are approved |

## Quiz

1. **Your teammate has an M-series Mac and wants to learn local open-model inference, but they plan to begin with a CUDA container tutorial because most production examples use NVIDIA GPUs. How would you redirect the learning path, and what would you preserve for later?**

   <details>
   <summary>Answer</summary>
   Start them with a Mac-native MLX workflow so they can learn model loading, prompting, generation, memory pressure, and evaluation without first debugging a mismatched CUDA environment. Preserve the CUDA material for the later production-infrastructure stage, when the learner already understands inference mechanics and needs to study server hardware, drivers, scheduling, and deployment patterns.
   </details>

2. **A learner installs `mlx-lm`, runs a generation command, and gets `ModuleNotFoundError` from the terminal. They immediately try a different model name. What is wrong with that response, and what should they check first?**

   <details>
   <summary>Answer</summary>
   Changing the model cannot fix a Python import failure because the runtime has not reached model loading yet. They should activate the virtual environment, confirm which Python interpreter is running, check `python -m pip show mlx-lm`, and try `python -m mlx_lm.generate` so the command uses the same interpreter as the installed package.
   </details>

3. **Your team wants to prototype a local assistant that rewrites short incident notes containing sensitive operational details. The prototype will be used by two engineers on Apple Silicon laptops. Evaluate whether MLX is a reasonable first runtime.**

   <details>
   <summary>Answer</summary>
   MLX is a reasonable first runtime because the task is local, privacy-sensitive, small enough for laptop experimentation, and useful to script from Python. The team should still record model identifiers, prompts, package versions, and observed behavior, and it should not assume the laptop workflow is the final architecture if the assistant later becomes a shared service.
   </details>

4. **A model runs successfully in MLX, but the first request takes much longer than later requests. A learner concludes that MLX is too slow. How would you analyze that conclusion?**

   <details>
   <summary>Answer</summary>
   The conclusion is premature because first-run timing may include model download, weight loading, cache setup, and warm-up effects. Separate load time from generation time in a Python script, rerun with the model already available, and compare task-level latency before judging whether the runtime is too slow for the workflow.
   </details>

5. **A Mac with limited memory becomes sluggish when loading a large quantized model. The learner wants to keep the same model because larger sounds better. What recommendation would you make and why?**

   <details>
   <summary>Answer</summary>
   Recommend starting with a smaller or more aggressively quantized model that leaves memory headroom. A model that barely fits reduces iteration speed and can make every experiment unstable, while a smaller model lets the learner run repeated prompts, compare behavior, and understand the task before increasing model size.
   </details>

6. **A team compares MLX and another local runtime, but they use different prompts, different model families, and different token limits. They ask which runtime won. How should you redesign the comparison?**

   <details>
   <summary>Answer</summary>
   Redesign the comparison around a fixed task, shared prompt set, similar model family where possible, explicit token limits, and predefined success criteria such as factual preservation, latency, concision, and hallucination risk. Without controlling those variables, the team is comparing anecdotes rather than runtime behavior.
   </details>

7. **An MLX prototype produces strong output for a local support-ticket classification task. A manager asks whether the team can now deploy the laptop script as an internal multi-user service. What should you explain?**

   <details>
   <summary>Answer</summary>
   Explain that the prototype is useful evidence about prompts, model behavior, and task feasibility, but it is not automatically an operating model for a shared service. A multi-user deployment needs capacity planning, access control, observability, update strategy, failure handling, and possibly a server-oriented runtime or managed platform.
   </details>

8. **A learner gets poor answers from an MLX model and says the runtime is bad. The setup works, imports pass, and the model generates quickly. What would you investigate before changing runtimes?**

   <details>
   <summary>Answer</summary>
   Investigate the prompt, chat template, model choice, token limit, sampling settings, and whether the task is appropriate for the chosen model size. Poor output after a healthy setup is often a model or prompt problem, not a runtime problem, so the next step is controlled evaluation rather than an immediate runtime switch.
   </details>

## Hands-On Exercise

In this exercise, you will design and test a small MLX local inference workflow. If you have Apple Silicon available, run the commands directly. If you do not have Apple Silicon, complete the design and debugging analysis as a paper lab, then compare the MLX path with the Linux or local runtime path you would use on your own machine.

### Scenario

Your team wants to evaluate whether a local model can turn rough operational notes into concise engineering handoffs. The notes may contain internal details, so the first prototype should avoid cloud APIs. One engineer owns an Apple Silicon Mac and wants to use MLX. Your job is to design the first experiment, run or simulate it, and decide whether MLX is the right first runtime.

### Step 1: Define The Experiment

Write a short experiment plan before running commands. The plan should name the task, the expected input size, the model you plan to test, the reason MLX is a candidate, and one condition that would make you choose a different runtime later. This forces you to make the decision explicit instead of treating the tool as the goal.

Use this structure:

```bash
cat > experiment-plan.md <<'EOF'
# MLX Local Inference Experiment

Task:
Rewrite rough incident notes into a concise handoff for the next engineer.

Why local:
The notes may include internal operational details, so the first prototype should avoid cloud APIs.

Why MLX:
The first tester has an Apple Silicon Mac, and MLX gives a native Python workflow for local inference.

Candidate model:
mlx-community/Llama-3.2-3B-Instruct-4bit

Success signal:
The output preserves important facts, avoids invented causes, and returns quickly enough for repeated testing.

Reason to move beyond MLX later:
The workflow becomes a shared service with multiple users, access controls, observability, and capacity targets.
EOF
```

### Step 2: Prepare Or Describe The Environment

If you have Apple Silicon, create a clean environment and install `mlx-lm`. If you do not have Apple Silicon, write the checks you would ask the Mac user to run and explain what each result would prove. The important learning goal is not merely typing commands; it is knowing what each command rules in or rules out.

```bash
mkdir -p mlx-incident-handoff
cd mlx-incident-handoff
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install mlx-lm

python - <<'PY'
import platform
import sys

print("python:", sys.version.split()[0])
print("machine:", platform.machine())
print("platform:", platform.platform())
PY
```

### Step 3: Run A Small Smoke Test

Run a short prompt before testing the real scenario. This separates runtime health from task quality. If this step fails, debug the environment or model access before judging whether MLX can solve the operational handoff task.

```bash
python -m mlx_lm.generate \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --prompt "Explain in one sentence why local inference can help with privacy-sensitive prototypes." \
  --max-tokens 60
```

### Step 4: Run The Scenario Prompt

Create a prompt file that looks like the real workflow. Keep it short enough for a first test, but realistic enough to evaluate whether the output preserves the important facts. Do not include actual confidential data in a curriculum exercise; use synthetic notes with the same structure.

```bash
cat > handoff_prompt.txt <<'EOF'
Rewrite the following incident notes into a concise handoff for the next engineer.

Notes:
- checkout errors increased after the 09:15 deployment
- application logs show database timeout spikes
- rollback reduced new errors but did not clear existing queue backlog
- queue workers are processing slowly
- next shift should check worker saturation and slow database queries
EOF

python -m mlx_lm.generate \
  --model mlx-community/Llama-3.2-3B-Instruct-4bit \
  --prompt "$(cat handoff_prompt.txt)" \
  --max-tokens 180
```

### Step 5: Add A Repeatable Python Runner

Now turn the one-off command into a repeatable script. This is the step that moves the exercise from casual local inference to engineering practice. The script records model identity, separates loading from generation, and makes it easier to compare prompts later.

```bash
cat > run_handoff.py <<'PY'
import time
from pathlib import Path

from mlx_lm import generate, load

MODEL = "mlx-community/Llama-3.2-3B-Instruct-4bit"
PROMPT_PATH = Path("handoff_prompt.txt")

prompt = PROMPT_PATH.read_text()

load_started = time.perf_counter()
model, tokenizer = load(MODEL)
load_finished = time.perf_counter()

generate_started = time.perf_counter()
output = generate(
    model,
    tokenizer,
    prompt=prompt,
    max_tokens=180,
    verbose=False,
)
generate_finished = time.perf_counter()

print("model:", MODEL)
print("prompt_file:", PROMPT_PATH)
print("load_seconds:", round(load_finished - load_started, 2))
print("generate_seconds:", round(generate_finished - generate_started, 2))
print()
print(output)
PY

python run_handoff.py
```

### Step 6: Evaluate The Output

Review the model output against task-level criteria. Do not score only whether the answer "sounds good." Local inference prototypes fail when they sound plausible while dropping important facts or inventing causes. Your evaluation should check preservation, concision, safety, and operational usefulness.

Use these review questions:

- Does the handoff mention the deployment timing without overstating causality?
- Does the handoff preserve both the database timeout signal and the queue backlog signal?
- Does the handoff avoid inventing a root cause that was not in the notes?
- Does the handoff identify useful next checks for the next engineer?
- Is the response concise enough to be used during an incident handoff?
- Is generation fast enough that you would run several prompt variations?

### Step 7: Debug One Likely Failure

Choose one failure and write the first three checks you would perform. Pick from environment failure, model download failure, memory pressure, poor output quality, or unstable repeated responses. Your answer should name the failure domain before naming the fix.

Example response:

```text
Failure:
The command fails with ModuleNotFoundError before any model downloads.

Failure domain:
Python environment or package installation.

First checks:
1. Confirm the virtual environment is active.
2. Run python -m pip show mlx-lm inside the environment.
3. Run python -m mlx_lm.generate instead of relying on a shell entry point.
```

### Step 8: Make The Runtime Decision

Write a short decision note. The note should not be "MLX is good" or "MLX is bad." It should explain whether MLX is the right first runtime for this specific prototype, what evidence supports that decision, and what would trigger a move to another runtime.

Use this structure:

```bash
cat > decision-note.md <<'EOF'
# Runtime Decision

Decision:
MLX is the right first runtime for this prototype.

Evidence:
The task is local, the first tester has Apple Silicon, the workflow benefits from Python scripting,
and the model can be evaluated with synthetic incident notes before using sensitive real data.

Limits:
The result does not prove that a laptop script is a production service.

Move beyond MLX when:
Multiple users need shared access, access controls, monitoring, request queues, or deployment parity
with Linux GPU infrastructure.
EOF
```

### Success Criteria

- [ ] You can explain why MLX is a Mac-native learning path rather than a universal replacement for every inference runtime.
- [ ] You created or described a clean environment and identified what machine, Python, and package checks prove.
- [ ] You ran or analyzed a smoke test before evaluating the real task so runtime health and model quality stayed separate.
- [ ] You selected a model with an explicit reason instead of choosing the largest model by default.
- [ ] You used a realistic scenario prompt and evaluated whether the output preserved key facts without inventing causes.
- [ ] You wrote or inspected a repeatable Python runner that records model identity and separates load time from generation time.
- [ ] You diagnosed at least one likely failure by naming the failure domain before proposing fixes.
- [ ] You wrote a runtime decision note that explains when MLX is appropriate and when another runtime would be better.

## Sources

- [MLX](https://github.com/ml-explore/mlx) — Primary upstream source for Apple's MLX array framework.
- [MLX LM](https://github.com/ml-explore/mlx-lm) — Canonical MLX-LM repository and README for language-model workflows.
- [MLX Examples](https://github.com/ml-explore/mlx-examples) — Upstream examples for MLX tasks beyond a single language-model command.
- [MLX documentation](https://ml-explore.github.io/mlx/build/html/index.html) — Hosted documentation for MLX concepts and API reference.
- [MLX installation guide](https://ml-explore.github.io/mlx/build/html/install.html) — Official MLX installation instructions.
- [MLX unified memory documentation](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html) — Official explanation of MLX unified-memory behavior.
- [Hugging Face Hub MLX guide](https://huggingface.co/docs/hub/en/mlx) — Hugging Face documentation for MLX-compatible model repositories.
- [Hugging Face mlx-community](https://huggingface.co/mlx-community) — Community namespace for MLX-converted model artifacts.
- [mlx-lm on PyPI](https://pypi.org/project/mlx-lm/) — Package metadata for installing MLX-LM through pip.
- [Ollama](https://github.com/ollama/ollama) — Upstream local-model runtime used for comparison with MLX.
- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Upstream GGUF-focused local inference runtime used for cross-platform comparison.
- [Transformers documentation](https://huggingface.co/docs/transformers/index) — Hugging Face documentation for the broader Python model-engineering workflow.
- [vLLM documentation](https://docs.vllm.ai/en/latest/) — Server-oriented inference runtime documentation for later comparison with laptop workflows.
- [github.com: README.md](https://github.com/ollama/ollama/blob/main/README.md) — The Ollama README shows local chat usage and documents the REST API for running and managing models.
- [huggingface.co: index](https://huggingface.co/docs/transformers/v4.48.0/en/index) — The Transformers docs describe the library as state-of-the-art ML for inference and training and highlight portable inference workflows such as pipelines and AutoClass loading.
- [github.com: README.md](https://github.com/ggml-org/llama.cpp/blob/master/README.md) — The llama.cpp README presents GGUF-based local inference with broad backend support and direct local model execution.
- [github.com: README.md](https://github.com/vllm-project/vllm/blob/main/README.md) — The vLLM README describes vLLM as an inference and serving library with state-of-the-art throughput and high-throughput serving features.
- [huggingface.co: chat templating writing](https://huggingface.co/docs/transformers/main/chat_templating_writing) — The Transformers chat-template docs explain that templates are stored on the tokenizer and are used whenever `apply_chat_template()` is called to match the model's expected format.
- [huggingface.co: manage cache](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache) — The Hugging Face Hub cache guide directly documents the local cache layout and default cache directory.

## Next Module

Continue to [Running Open Models on Linux Boxes](../module-1.5-running-open-models-on-linux-boxes/).
