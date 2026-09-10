---
citations_verified: true
title: "Reproducible Python, CUDA, and ROCm Environments"
slug: ai-ml-engineering/prerequisites/module-1.3-reproducible-python-cuda-rocm-environments
sidebar:
  order: 103
---
> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 2-3 hours
>
> **Prerequisites**: [Module 1.1: Prerequisites & Environment Setup](./module-1.1-prerequisites-environment-setup/), [Module 1.2: Home AI Workstation Fundamentals](./module-1.2-home-ai-workstation-fundamentals/), basic command-line navigation, and comfort editing small text files.

## Learning Outcomes

- **Design** a project-local Python environment that another learner can recreate without relying on your shell history or global package state.
- **Debug** environment failures by separating Python interpreter problems, package-resolution problems, GPU driver problems, and framework-runtime compatibility problems.
- **Compare** plain virtual environments, higher-level environment managers, and containers, then justify which one fits a learning project, team workstation, or deployment-bound prototype.
- **Evaluate** whether a CUDA or ROCm setup is internally compatible before installing a deep learning framework, instead of discovering incompatibility through runtime errors.
- **Build** and run a smoke test that proves the environment imports the expected packages, uses the expected interpreter, and sees the intended CPU, CUDA, or ROCm backend.

## Why This Module Matters

*(Mira is a hypothetical illustrative learner, not a documented incident.)* Mira joins a small applied AI team on Monday and receives a model repository, a short README, and a message that says, "It should run after installing the requirements." By Tuesday afternoon, one teammate can train on an NVIDIA GPU, another silently falls back to CPU, and Mira's notebook imports a different package version than the command-line script. Nobody has changed the model code, but every person is seeing a different system.

That failure is not a Python trivia problem. It is a systems problem disguised as setup friction. AI projects combine interpreted code, compiled native extensions, hardware drivers, compute runtimes, and framework wheels that were built against specific assumptions. When those assumptions drift, the learner often blames the line of model code they can see, even though the failure was created several layers below it.

Reproducibility is the skill that turns that chaos into an inspectable system. A reproducible environment does not mean every laptop is identical, and it does not mean you never have to debug setup again. It means the project has a declared path, an isolated interpreter, a dependency record, a hardware assumption, and a small verification sequence that shows where the stack is healthy or broken.

Senior practitioners care about this because unreproducible environments waste expensive hardware time and make incidents harder to explain. Beginners should care because every future module in the AI/ML Engineering track assumes that a Python command, a notebook kernel, and a framework import all mean what they appear to mean. If you cannot trust the environment, you cannot trust the experiment.

## The Mental Model: Reproducibility Is a Boundary Problem

A local AI environment is not one thing. It is a stack of boundaries, and each boundary answers a different question. The operating system answers whether the machine can load drivers and libraries. The GPU driver answers whether the hardware is visible. CUDA or ROCm answers whether software can ask the GPU to do compute work. Python and the framework answer whether your code can call the right compiled binaries.

Most painful setup sessions start when a learner treats those boundaries as interchangeable. They reinstall Python when the driver is missing, upgrade a GPU driver when the notebook kernel is pointing at the wrong virtual environment, or install a CPU-only framework wheel and then wonder why the GPU is invisible. The fix is not memorizing every possible version combination; the fix is learning to ask which layer owns the failure.

```text
AI project stack, read from bottom to top

+--------------------------------------------------------------+
| Project code and notebooks                                  |
| model.py, train.py, notebooks, tests, configuration files     |
+--------------------------------------------------------------+
| Python packages and framework wheels                         |
| numpy, torch, tensorflow, tokenizers, compiled extensions     |
+--------------------------------------------------------------+
| Python interpreter and isolated environment                   |
| .venv/bin/python, pip metadata, notebook kernel binding       |
+--------------------------------------------------------------+
| Compute runtime family                                       |
| CUDA libraries for NVIDIA, ROCm/HIP libraries for AMD         |
+--------------------------------------------------------------+
| GPU driver and device visibility                             |
| nvidia-smi, rocminfo, kernel modules, device permissions      |
+--------------------------------------------------------------+
| Operating system, kernel, filesystem, shell                   |
| Linux distribution, package manager, PATH, working directory  |
+--------------------------------------------------------------+
```

The important move is to debug downward or upward deliberately, not randomly. If a package cannot import, start at the Python environment and package layer. If the package imports but the GPU is unavailable, move down to framework build, runtime family, and driver visibility. If the driver tool cannot see the device, Python is not the first suspect.

> **Pause and predict:** A teammate says `import torch` works, but `torch.cuda.is_available()` returns `False` on a workstation with an NVIDIA GPU. Before reading further, decide which two layers you would inspect first and which layer you would avoid changing until you have evidence.

A strong first answer is to inspect the framework wheel and the driver/runtime layer. The import only proves that Python found a package named `torch`; it does not prove that the package was built with CUDA support, that the driver can expose the GPU, or that the runtime libraries expected by the wheel are usable. Recreating the virtual environment may eventually be useful, but reinstalling Python itself is usually an expensive guess.

## The Baseline Rule: One Project, One Environment, One Verification Path

The baseline rule for this track is simple: one project, one isolated environment, one documented setup path, and one smoke test. This rule sounds small, but it prevents the most common failure pattern in early AI work: many projects slowly sharing one global interpreter until package versions and notebook kernels become impossible to reason about.

An isolated environment gives each project a private package directory and a predictable interpreter path. The interpreter path matters because `pip install` and `python train.py` must refer to the same environment. If they do not, you get the classic failure where installation succeeds in one terminal and the application fails in another.

A documented setup path matters because memory is not reproducibility. If the only record of the environment is "I installed a few things last month," the project cannot be handed to another learner, recreated on a second workstation, or diagnosed after a failed upgrade. The goal is not a perfect enterprise build system on day one; the goal is enough evidence that a future person can rebuild the same starting point.

A smoke test matters because successful installation logs are not proof. Package installers can succeed while installing CPU-only wheels, while leaving a notebook kernel bound to an old interpreter, or while accepting versions that import but fail during a real tensor operation. The smoke test gives the project a known checkpoint before model code enters the story.

```text
Reproducible project shape

my-ai-project/
+-- .venv/                     # project-local interpreter and installed packages
+-- src/                       # importable project code
+-- notebooks/                 # exploration, bound to the project environment
+-- data/                      # local data samples, usually not committed if large
+-- outputs/                   # generated artifacts, usually ignored by Git
+-- requirements.in            # direct human-chosen dependencies
+-- requirements.txt           # resolved or pinned install input for this project
+-- verify_env.py              # smoke test for interpreter, packages, and backend
+-- README.md                  # setup and verification steps
+-- .gitignore                 # excludes .venv, outputs, caches, large local files
```

This structure is deliberately ordinary. Ordinary environments are easier to inspect, easier to document, and easier to replace when they break. The less mystery your setup contains, the more attention you can spend on data, training behavior, and model quality.

## Building the First Environment Deliberately

The first environment should be boring enough that you can explain every line of the setup. Start by creating the project directory, then create the virtual environment inside that directory. Once the virtual environment exists, run package-management commands through `.venv/bin/python -m pip` so the interpreter and installer are tied together by path rather than by shell assumptions.

```bash
mkdir -p reproducible-ai-env/src reproducible-ai-env/notebooks reproducible-ai-env/data reproducible-ai-env/outputs
cd reproducible-ai-env
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip --version
.venv/bin/python -c "import sys; print(sys.version); print(sys.prefix)"
```

The command `python3.12 -m venv .venv` is the one unavoidable bootstrap step in this example because the environment does not exist yet. After that, the module uses `.venv/bin/python` explicitly so package installation, verification, and scripts all run under the project interpreter. In a team README, state which bootstrap command your operating system uses, then keep the rest of the workflow path-explicit.

A beginner often asks why activation is not enough. Activation is convenient for interactive work, but it modifies shell state, and shell state is easy to lose across terminals, notebooks, task runners, and editor integrations. Path-explicit commands are noisier, yet they make documentation and automation more reliable because the command itself names the interpreter.

```bash
cat > requirements.in <<'EOF'
numpy
packaging
EOF

.venv/bin/python -m pip install -r requirements.in
.venv/bin/python -m pip freeze > requirements.txt
.venv/bin/python -m pip check
```

The split between `requirements.in` and `requirements.txt` is a useful beginner-to-practitioner bridge. The `.in` file records the dependencies the project intentionally asked for, while the `.txt` file records the concrete installed result, including transitive dependencies. Small solo projects sometimes use only `requirements.txt`, but larger projects benefit from knowing which dependencies were direct choices and which arrived because another package required them.

```bash
cat > .gitignore <<'EOF'
.venv/
__pycache__/
.ipynb_checkpoints/
outputs/
*.pyc
EOF

cat > README.md <<'EOF'
# Reproducible AI Environment

## Setup
Create the environment with Python 3.12, then run package commands through `.venv/bin/python`.

## Install
`.venv/bin/python -m pip install -r requirements.txt`

## Verify
`.venv/bin/python verify_env.py`
EOF
```

This README is intentionally short, but it already captures the reproducibility contract. It tells the next person which Python line matters, how packages are installed, and how health is checked. A better README can add GPU expectations later, but even this small version is much stronger than an undocumented global environment.

> **Stop and think:** If a teammate says "I activated the environment yesterday, so the editor should still be using it today," what hidden assumption are they making? Write down how you would prove which interpreter the editor or notebook actually uses.

The hidden assumption is that every tool shares the same shell activation state. Editors, notebook servers, task runners, and terminals often start as separate processes, so they may not inherit the activation you think they inherited. The proof is to print the interpreter path from inside the exact tool that is running the code, not from a different terminal that happens to look similar.

## Worked Example: Debugging a Notebook and CLI Mismatch

Consider a project where the command-line smoke test works, but a notebook fails with `ModuleNotFoundError: No module named 'numpy'`. A weak diagnosis is "Jupyter is broken." A better diagnosis is "the notebook kernel is probably bound to a different interpreter than the project CLI."

First, prove what the command line is using. This command prints the interpreter path and imports `numpy` from the project environment. Because it calls `.venv/bin/python` directly, there is no ambiguity about which interpreter is being tested.

```bash
.venv/bin/python - <<'PY'
import numpy
import sys

print("cli_executable:", sys.executable)
print("numpy_version:", numpy.__version__)
PY
```

Next, run the same two checks inside the notebook. Put the code in a notebook cell and compare the output with the command-line output. The exact path does not need to be memorized, but it should point into the same project `.venv` directory.

```python
import numpy
import sys

print("notebook_executable:", sys.executable)
print("numpy_version:", numpy.__version__)
```

If those paths differ, installing more packages from the notebook is usually the wrong first fix. You should register or select a notebook kernel that points at the project environment, then rerun the proof. The key lesson is that environment debugging is evidence collection, not package whack-a-mole.

```bash
.venv/bin/python -m pip install ipykernel
.venv/bin/python -m ipykernel install --user --name reproducible-ai-env --display-name "Python (.venv reproducible-ai-env)"
```

After selecting that kernel in the notebook UI, rerun the notebook cell. If the paths now agree, the failure was not a missing package in the project environment; it was a tool boundary problem. This is the same reasoning pattern you will use later for CUDA and ROCm: identify the boundary, prove what each side sees, then change the smallest responsible layer.

## Choosing Between venv, Environment Managers, and Containers

Plain `venv` is the baseline because it teaches the core mechanism without hiding too much. You can see the interpreter path, inspect installed packages, remove the environment directory, and recreate it from the dependency file. For learning modules and small projects, that transparency is more valuable than clever automation.

Higher-level tools can add lock files, Python version management, dependency solving, and faster installs. They are useful when teams need stricter repeatability or when dependency trees become large. They do not remove the need to understand which interpreter is active, where packages are installed, or whether the framework build matches the hardware path.

Containers add a stronger boundary around the operating-system userland and package installation path. They help when onboarding must be repeatable, host machines are inconsistent, several incompatible stacks must coexist, or the project is already moving toward deployment. They also add new concepts: image layers, bind mounts, GPU runtime integration, container users, and host-driver interaction.

| Situation | Prefer `venv` | Prefer higher-level manager | Prefer container |
|---|---|---|---|
| Solo learning project with one Python stack | Best default because it is transparent and easy to delete | Optional if you already understand the basics | Usually unnecessary unless the host is already messy |
| Team prototype with many dependencies | Works if documentation is disciplined | Good fit when lock files and resolver behavior matter | Good fit when laptops keep drifting or onboarding is painful |
| Multiple incompatible CUDA or ROCm experiments | Risky because host libraries and package choices may collide | Helpful for Python packages but not a full OS boundary | Strong fit when each experiment needs a separate runtime image |
| Deployment-bound inference service | Useful for local development only | Useful for lock discipline before image build | Strong fit because runtime packaging becomes part of delivery |

The decision should be based on failure modes, not fashion. If the problem is "I do not know which Python I am using," a container will not automatically teach you that. If the problem is "four developers need the same userland and package stack on different hosts," staying with ad hoc host setup may keep wasting time.

## CUDA: Compatibility Is a Contract, Not a Guess

CUDA is NVIDIA's compute platform, and many deep learning frameworks publish builds that target specific CUDA runtime versions. The driver installed on the host must be new enough for the runtime expectations of the framework build. The framework wheel must also be the CUDA-enabled build, not a CPU-only build that happens to import successfully.

A practical CUDA workflow starts below Python. Confirm that the GPU is visible to the operating system and driver tooling before installing a framework build. If `nvidia-smi` cannot see the GPU, installing PyTorch again will not make the device appear. If `nvidia-smi` works but the framework cannot use CUDA, the next suspect is the framework build or runtime compatibility.

```bash
command -v nvidia-smi
nvidia-smi
```

The output of `nvidia-smi` is not a full proof that PyTorch or TensorFlow will work, but it proves something important: the NVIDIA driver layer can see the GPU. That narrows the problem. If a later tensor operation fails, you can focus on framework build, runtime expectation, permissions, or container GPU passthrough rather than wondering whether the hardware exists.

For PyTorch specifically, use the official installation selector for the target operating system, package manager, Python version, and compute platform. Do not mix a random wheel from one guide with a CUDA toolkit from another guide unless you understand exactly why that combination is supported. In most learner setups, the framework-provided wheel includes the runtime pieces it expects, while the host driver remains the critical host-level dependency.

```bash
.venv/bin/python - <<'PY'
try:
    import torch
except ImportError:
    print("torch: not installed")
else:
    print("torch_version:", torch.__version__)
    print("torch_cuda_build:", torch.version.cuda)
    print("cuda_available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        x = torch.tensor([1.0, 2.0], device="cuda")
        print("tensor_device:", x.device)
        print("tensor_sum:", float(x.sum().cpu()))
PY
```

This smoke test distinguishes several cases. If `torch` is not installed, you are still at the package layer. If `torch.version.cuda` is `None`, you likely installed a CPU build. If CUDA is built in but unavailable, the driver/runtime boundary deserves attention. If the tensor operation succeeds, you have stronger evidence than an import alone.

> **Pause and predict:** Suppose `nvidia-smi` works, `torch.__version__` prints normally, `torch.version.cuda` is `None`, and [`torch.cuda.is_available()`](https://docs.pytorch.org/docs/stable/notes/cuda.html) is `False`. Which layer is probably wrong, and why would reinstalling the NVIDIA driver be a low-value first move?

The likely problem is the framework package selection. A CPU-only PyTorch build can import perfectly while reporting no CUDA build support. The NVIDIA driver may still be healthy, so reinstalling it would change a lower layer that already passed its first proof.

## ROCm: Be Stricter About Supported Combinations

ROCm plays a similar role for AMD GPUs, but the support matrix can be more sensitive to GPU model, Linux distribution, kernel, ROCm release, and framework build. That does not make ROCm unsuitable for learning. It means you should treat official compatibility guidance as part of the setup, not as optional reading after a failed install.

A practical ROCm workflow starts by identifying the GPU and confirming ROCm tooling can see it. On systems with ROCm installed, `rocminfo` and related tools provide evidence from the runtime side. If those tools are unavailable or cannot see the hardware, installing a framework wheel is unlikely to fix the lower-layer issue.

```bash
lspci | grep -Ei 'vga|3d|display'
command -v rocminfo
rocminfo
```

ROCm also changes how you interpret framework output. [Many frameworks expose AMD GPU support through HIP-related fields, while still using some APIs named after CUDA for historical compatibility](https://github.com/pytorch/pytorch/blob/main/docs/source/notes/hip.rst). That naming can confuse beginners: a method name containing `cuda` does not always mean the backend is NVIDIA CUDA. You must inspect the framework's reported build information and official documentation for the package you installed.

```bash
.venv/bin/python - <<'PY'
try:
    import torch
except ImportError:
    print("torch: not installed")
else:
    print("torch_version:", torch.__version__)
    print("torch_cuda_build:", torch.version.cuda)
    print("torch_hip_build:", torch.version.hip)
    print("backend_available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        x = torch.tensor([3.0, 4.0], device="cuda")
        print("tensor_device:", x.device)
        print("tensor_sum:", float(x.sum().cpu()))
PY
```

The lesson is not that every learner must become a GPU driver expert before training a model. The lesson is that ROCm rewards a disciplined compatibility check before package installation. Identify the hardware, confirm the operating system and ROCm version are supported, choose a documented framework build, and then verify with a real tensor operation.

## Designing a Smoke Test That Teaches You Something

A smoke test is a small program that proves the environment can do the minimum meaningful work expected by the project. For AI environments, importing a package is too weak by itself. A useful smoke test reports interpreter identity, package versions, working directory, environment variables that matter, GPU visibility, and a tiny computation on the intended backend.

The smoke test should be committed to the project because it is part of the setup contract. When a future teammate says "the environment is broken," the first question becomes "which smoke-test line changed?" That is much better than comparing screenshots of terminal history or guessing which installation guide each person followed.

```bash
cat > verify_env.py <<'PY'
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


def run_optional(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return "not found"
    first_lines = completed.stdout.strip().splitlines()[:6]
    if not first_lines and completed.stderr.strip():
        first_lines = completed.stderr.strip().splitlines()[:6]
    return "\n".join(first_lines) if first_lines else f"exit code {completed.returncode}"


def main() -> None:
    project_root = Path(__file__).resolve().parent
    print("project_root:", project_root)
    print("python_version:", sys.version.split()[0])
    print("python_executable:", sys.executable)
    print("python_prefix:", sys.prefix)
    print("platform:", platform.platform())
    print("virtual_env:", os.environ.get("VIRTUAL_ENV", "not set"))

    import numpy

    print("numpy_version:", numpy.__version__)
    print("nvidia_smi:", run_optional(["nvidia-smi"]))
    print("rocminfo:", run_optional(["rocminfo"]))

    try:
        import torch
    except ImportError:
        print("torch_status: not installed")
        return

    print("torch_version:", torch.__version__)
    print("torch_cuda_build:", torch.version.cuda)
    print("torch_hip_build:", torch.version.hip)
    print("torch_backend_available:", torch.cuda.is_available())

    if torch.cuda.is_available():
        tensor = torch.tensor([1.0, 2.0, 3.0], device="cuda")
        print("torch_tensor_device:", tensor.device)
        print("torch_tensor_sum:", float(tensor.sum().cpu()))
    else:
        print("torch_tensor_device: cpu-only path")


if __name__ == "__main__":
    main()
PY

.venv/bin/python verify_env.py
```

This script is intentionally plain Python, not a testing framework. Early in a project, the goal is a readable diagnostic that any learner can run. Later, a team might turn parts of it into automated CI checks, but local hardware detection often remains a workstation-level verification step because CI runners may not have the same GPU backend.

A senior-level habit is to write the smoke test so success and failure both teach. If `nvidia-smi` is missing, the script says so without crashing. If PyTorch is not installed yet, the script reports that and exits cleanly. If a backend is available, the script performs a real tensor operation so you know more than "the package imported."

## Dependency Records: Minimum, Useful, and Stronger

Dependency records come in levels. The minimum useful record is a file that lets another person install the project dependencies into a clean environment. A stronger record distinguishes direct dependencies from resolved transitive dependencies. A still stronger record includes hashes, lock files, container images, or a tested build process.

For a beginner project, the most important mistake to avoid is editing the environment manually for days without updating any file. The moment the working environment exists only inside `.venv`, reproducibility is already decaying. Commit the dependency file, the smoke test, and the README; do not commit the `.venv` directory itself.

```bash
.venv/bin/python -m pip freeze > requirements.txt
.venv/bin/python -m pip check
.venv/bin/python verify_env.py
```

`pip freeze` is not perfect as a design document because it records everything installed, including transitive packages. That can be useful for recreation but noisy for human review. Many teams keep a human-authored input file and a generated lock file, or they use a tool that makes this separation explicit. The principle is the same: record intent and record the tested result.

When GPU frameworks are involved, write the hardware assumption in prose as well as dependencies. A requirements file can say which wheel was installed, but a README should also say whether the project was verified on CPU, CUDA, ROCm, or multiple paths. This prevents a teammate from treating a CPU-only environment as a failed GPU setup or treating a CUDA setup as a portable default.

## Version Strategy: Newest Is Not the Same as Compatible

A common beginner strategy is to install the newest driver, newest toolkit, newest framework, and newest Python version, then expect them to cooperate. That strategy fails because compatibility is about tested combinations, not individual freshness. A brand-new Python version may not have wheels for all packages yet, and a framework build may target a runtime that assumes a sufficiently new but not arbitrary driver.

The better strategy is to choose an anchor. In many AI projects, [the framework version is the anchor because it determines supported Python versions and available CPU, CUDA, or ROCm builds](https://github.com/pytorch/pytorch/blob/main/RELEASE.md). In other projects, hardware or organization policy is the anchor because the workstation driver or base image is fixed. Once you know the anchor, choose the rest of the environment around it.

```text
Compatibility decision order

1. Identify the project requirement.
   Example: "We need PyTorch with GPU acceleration for local fine-tuning."

2. Identify the hardware path.
   Example: "This workstation has an NVIDIA GPU, so the target runtime is CUDA."

3. Identify supported framework builds.
   Example: "The PyTorch install selector lists builds for specific CUDA targets."

4. Confirm host driver visibility.
   Example: "`nvidia-smi` sees the GPU before the framework is installed."

5. Install into a clean project environment.
   Example: "Use `.venv/bin/python -m pip` and avoid global packages."

6. Run the smoke test.
   Example: "A tensor operation succeeds on the intended backend."
```

This order reduces cognitive load because each step narrows the problem. If you install first and reason later, every failure could belong to every layer. If you reason first, a failure at step five or six has a smaller search space.

## Containers: Stronger Boundary, Different Debugging

Containers are valuable when the host environment has become part of the problem. A container image can capture a userland, system packages, Python packages, and application code in a repeatable build. For teams, that means onboarding can shift from "recreate my laptop" to "build or pull this image and run this command."

Containers do not package the physical GPU driver in the same way they package Python dependencies. [GPU container support still depends on host drivers and runtime integration](https://github.com/NVIDIA/nvidia-container-toolkit). That is why a CUDA container can fail on a host with a broken NVIDIA driver, and a ROCm container can fail on unsupported hardware or missing device access. The container boundary is strong, but it is not magic.

A beginner-friendly container decision is to start with `venv` until the project has a real reason to need a stronger boundary. A professional decision is to containerize when repeatability, deployment alignment, or incompatible stacks justify the extra layer. The wrong decision is to use containers as a way to avoid understanding the environment; that simply moves confusion into a Dockerfile.

```text
Host Python plus venv

Host OS
+-- GPU driver
+-- Project directory
    +-- .venv
    +-- project code
    +-- smoke test

Containerized project

Host OS
+-- GPU driver and container runtime integration
+-- Container image
    +-- OS userland
    +-- Python environment
    +-- project code
    +-- smoke test
```

If you containerize, keep the same teaching discipline. The image should have a documented build path, a minimal dependency strategy, and a smoke test that runs inside the container. A container that nobody can rebuild is only a larger version of an undocumented virtual environment.

## Common Failure Modes and How to Triage Them

The fastest environment debuggers do not try fixes first. They classify symptoms. A missing package, a wrong interpreter, a CPU-only wheel, a driver visibility problem, and a notebook kernel mismatch can all produce short error messages, but they require different changes.

When a package import fails, ask which interpreter ran the code and which interpreter installed the package. When a GPU is invisible, ask whether the driver tool sees it before blaming the framework. When a notebook disagrees with the CLI, ask whether the kernel is bound to the project `.venv`. When a rebuild fails after weeks of work, ask whether the dependency record actually matched the environment.

```text
Symptom triage map

+-------------------------------+-------------------------------+-------------------------------+
| Symptom                       | First proof to collect        | Likely boundary               |
+-------------------------------+-------------------------------+-------------------------------+
| ModuleNotFoundError           | print interpreter path         | Python environment/package     |
| CLI works, notebook fails     | compare notebook and CLI paths | notebook kernel binding        |
| Import works, GPU unavailable | inspect framework build fields | framework/runtime/driver       |
| nvidia-smi cannot see GPU     | run driver tool outside Python | driver or host visibility      |
| rocminfo missing or failing   | inspect ROCm install/support   | ROCm runtime or host support   |
| Rebuild gives new versions    | compare dependency records     | dependency pinning/resolution  |
+-------------------------------+-------------------------------+-------------------------------+
```

A senior practitioner also records the triage result. If the fix was "select the correct notebook kernel," put that in the README. If the fix was "install the CUDA-enabled framework wheel, not the CPU wheel," update the installation section. Every environment incident is an opportunity to remove one future mystery.

## Reproducibility as a Team Contract

A reproducible environment is not only a local convenience. It is a contract between the person who writes the model code, the person who reviews it, the person who runs it on another machine, and the person who eventually has to debug it when an experiment or demo fails. The contract says which interpreter is expected, which packages are intentionally installed, which hardware path was verified, which command proves basic health, and which files should be ignored because they are local artifacts. Without that contract, every teammate has to rediscover setup through trial and error.

The contract should be small enough to keep current. A long setup guide full of optional branches can decay faster than a short guide with a reliable smoke test. For this track, a useful environment contract normally contains a Python version expectation, a command that creates the local environment, a command that installs dependencies, a command that verifies the environment, and a short note about CPU, CUDA, or ROCm expectations. If the project later gains containers, the contract can add a container build and run path, but the same questions still apply.

Reviewers should treat environment changes as meaningful code changes. A requirements update can alter numerical behavior, available kernels, tokenizer output, serialization compatibility, or GPU runtime behavior. A Dockerfile base-image change can alter system libraries. A notebook kernel change can make a result impossible to reproduce. When reviewing an ML pull request, ask whether the dependency or environment change is intentional, documented, and covered by the smoke test. This is especially important when the code diff is small but the environment diff is large.

The same contract helps incident response. Suppose a scheduled training job starts failing after a package refresh. A useful environment record lets the team compare the last known-good dependency set, Python version, framework build, and backend visibility. Without that record, the team may spend hours debating whether the data changed, the model changed, the GPU driver changed, or the notebook used a different kernel. Reproducibility does not prevent every failure, but it narrows the search space when failures happen.

## Upgrade and Migration Discipline

Environment upgrades should be handled as migrations, not as casual cleanup. Upgrading Python, NumPy, PyTorch, TensorFlow, CUDA, ROCm, or a container base image can change build compatibility, binary extension behavior, numerical kernels, and hardware support. A safe migration starts with the current smoke test passing, changes one boundary at a time when possible, and records the new evidence after the change. If several layers change together, the team loses the ability to tell which layer caused a new failure.

The safest sequence is usually to preserve the working environment, create a fresh environment, install the proposed dependency set there, and run the smoke test before deleting anything. That approach costs disk space, but it protects the last known-good setup. For GPU workstations, it is also wise to record driver-tool output before and after the migration. If `nvidia-smi` or `rocminfo` changes at the same time as Python packages, the migration touched more than one boundary and should be reviewed with extra care.

Pinning does not mean freezing forever. It means choosing when change enters the project. A training project may deliberately upgrade a framework to use a new feature, improve performance, or match a deployment runtime. The difference between disciplined change and accidental drift is that disciplined change updates the dependency record, documents the reason, runs verification, and leaves a clear rollback path. Accidental drift happens when someone installs the newest version globally and the project slowly starts depending on it.

Containers need the same migration discipline. Rebuilding an image from a floating base tag can silently change the operating-system packages underneath a model service. If the image also installs Python packages without a lock or constraints file, two builds from the same Dockerfile may not be equivalent. Prefer explicit base tags, reviewed dependency records, and smoke tests that run inside the image. A container is only reproducible when its build inputs are reproducible enough for the risk level of the project.

## CI and Documentation Hooks

Even when GPU verification must happen locally, continuous integration can still catch many environment mistakes. A CPU-only CI job can create the virtual environment, install dependencies, run `pip check`, import core packages, execute unit tests, and run the CPU path of `verify_env.py`. This does not prove CUDA or ROCm health, but it catches broken dependency records, missing files, syntax errors, incompatible Python versions, and accidental reliance on global packages. CI should make the cheap checks automatic so humans can focus on hardware-specific evidence.

Documentation should show commands that can be copied exactly. Avoid instructions such as "activate your environment and install the usual packages" because they hide the interpreter and dependency source. Prefer path-explicit commands such as `.venv/bin/python -m pip install -r requirements.txt` and `.venv/bin/python verify_env.py`. If Windows support matters, provide the equivalent PowerShell path rather than relying on learners to translate. Good setup documentation is not verbose; it is precise about the boundaries that often fail.

The README should also say what success looks like. A smoke test that prints many lines is helpful only if the learner knows which lines matter. For a CPU-only path, success may mean the interpreter points into `.venv`, `numpy` imports, and the backend line clearly says CPU-only. For a CUDA path, success may mean `nvidia-smi` is found, the framework reports a CUDA build, and a tensor operation runs on a CUDA device. For a ROCm path, success may mean the framework reports a HIP build and the backend tensor operation succeeds.

When a project grows, move repeated setup knowledge into scripts. A `scripts/setup-env.sh` file, a `Makefile` target, or a task-runner command can reduce copy-paste errors, but the script should still call the project interpreter explicitly after bootstrap. Scripts should fail loudly when the wrong Python version is used or when dependency checks fail. The goal is not to hide the environment; the goal is to encode the environment contract so every learner and reviewer runs the same steps.

## When Reproducibility Meets Real Hardware

Hardware-backed AI environments are harder than ordinary Python projects because some important state lives outside the repository. The GPU driver, kernel module, device permissions, container runtime integration, and sometimes firmware are properties of the host. A dependency file can recreate Python packages, but it cannot recreate a missing driver or unsupported GPU model. That is why a good environment guide separates project-local setup from host prerequisites. The project can own `.venv`, requirements, smoke tests, and notebook kernels; the workstation owner or platform team usually owns driver installation and hardware support.

This distinction prevents blame loops. If a smoke test says the project interpreter is correct and the package is installed, but the driver tool cannot see the GPU, the project dependency file is not the first suspect. If the driver tool sees the GPU and the framework build reports CPU-only support, the package selection is the likely boundary. If the framework reports CUDA or HIP support and a tensor operation still fails, the next evidence may come from runtime libraries, permissions, or a mismatch documented in the framework's compatibility notes. Each result points to a smaller next question.

Teams should write hardware expectations as testable statements. "Works with GPU" is vague. "Verified on Ubuntu with NVIDIA driver visible through `nvidia-smi`, PyTorch installed from the CUDA build selector, and `verify_env.py` completing a CUDA tensor sum" is actionable. For AMD, the equivalent statement should name ROCm support expectations and the proof command used on that host. These statements help reviewers understand whether a change affects CPU-only learning, local GPU experimentation, or deployment-bound accelerator work.

The same practice helps when learners do not have matching hardware. A CPU-only learner should still be able to complete most environment lessons if the project clearly separates CPU verification from optional accelerator verification. The smoke test can report that no accelerator path is available without failing the entire setup. Later, when the learner gains access to a CUDA or ROCm machine, the same smoke test can prove the additional backend. Reproducibility should make differences explicit, not pretend every machine is identical.

Finally, remember that reproducibility is a habit, not a single file. Every time you add a package, change a Python version, switch a notebook kernel, rebuild a container, or move to different GPU hardware, rerun the verification path and update the project record if the expected output changed. This routine may feel slow during the first week of a project, but it becomes faster than rediscovering the environment from scratch after an unexplained failure. Reliable setup work compounds across every later experiment, review, and deployment.

## Did You Know?

- **Framework imports are weak evidence**: A deep learning framework can import successfully even when it was installed as a CPU-only build, so a real backend tensor operation is a stronger verification step than `import torch` alone.

- **Notebook kernels are separate execution choices**: Activating `.venv` in a terminal does not guarantee that an existing notebook server or editor has selected the same interpreter, so the path must be checked inside the notebook itself.

- **GPU containers still depend on host drivers**: Container images can package userland libraries and Python dependencies, but NVIDIA and AMD GPU access still requires compatible host driver and runtime integration.

- **A lock file is not a hardware proof**: Dependency records help recreate packages, but they do not prove that the workstation has the expected GPU, driver, permissions, or supported ROCm/CUDA path.

## Common Mistakes

| Mistake | What Goes Wrong | Better Move |
|---|---|---|
| Reusing one global Python environment for every AI project | Dependency collisions build slowly, and imports start depending on accidental install order rather than project intent | Create one project-local `.venv`, install only project dependencies, and document the setup path |
| Running `pip install` through one interpreter and scripts through another | Installation appears successful, but the application cannot find packages or sees different versions | Use `.venv/bin/python -m pip` and run verification through the same `.venv/bin/python` path |
| Treating a successful framework import as GPU verification | CPU-only builds and broken runtime paths can still import, so the first real tensor operation fails later | Run a smoke test that reports build fields and performs a tiny tensor operation on the intended backend |
| Installing frameworks before checking GPU driver visibility | Error messages span too many layers, making it unclear whether hardware, driver, runtime, or Python is responsible | Verify `nvidia-smi` or `rocminfo` first, then install the framework build that matches the chosen backend |
| Assuming notebook activation follows terminal activation | The notebook uses an old kernel while the CLI uses the project environment, creating contradictory results | Print the interpreter path inside the notebook and register a kernel from the project `.venv` when needed |
| Mixing package managers without a written strategy | Packages arrive from several sources, upgrades become hard to explain, and rebuilds differ across machines | Choose a primary environment strategy per project and record any exceptions in the README |
| Containerizing before understanding the failing layer | The team gains image, mount, user, and GPU runtime complexity while the original Python confusion remains | Use containers when repeatability or deployment needs justify them, and keep the same smoke-test discipline |
| Committing `.venv` or generated outputs to Git | The repository becomes large, platform-specific, and harder for others to clone or review | Commit dependency files, setup notes, and verification scripts; ignore local environments and generated artifacts |

## Quiz

**Q1.** Your team inherits a training repository where `README.md` says only "install requirements," and two developers report different `numpy` versions after following that instruction. What environment evidence would you add first, and why does that evidence reduce the debugging space?

<details>
<summary>Answer</summary>
Add a project-local environment path, a dependency record, and a smoke test that prints the interpreter path and package versions. This reduces the debugging space because the team can distinguish "different interpreter" from "different dependency resolution" instead of treating both as a generic install failure. The strongest immediate habit is running installs and verification through `.venv/bin/python` so the command itself names the environment being tested.
</details>

**Q2.** A learner reports that their notebook cannot import a package, but `.venv/bin/python -c "import package_name"` works in the project directory. What should you check before reinstalling dependencies, and what result would confirm your diagnosis?

<details>
<summary>Answer</summary>
Check the notebook's interpreter path from inside a notebook cell and compare it with the CLI interpreter path. If the notebook path does not point into the project `.venv`, the issue is a kernel binding mismatch rather than a missing package in the project environment. Registering or selecting a kernel backed by `.venv/bin/python` should make the notebook and CLI agree.
</details>

**Q3.** An NVIDIA workstation passes `nvidia-smi`, but PyTorch reports `torch.version.cuda` as `None` and `torch.cuda.is_available()` as `False`. Which layer should you change first, and which tempting change should you avoid?

<details>
<summary>Answer</summary>
Change the framework package selection first because the installed PyTorch build appears to be CPU-only. Avoid reinstalling the NVIDIA driver as a first move because `nvidia-smi` already gave evidence that the driver can see the GPU. The next action is to install a PyTorch build that matches the intended CUDA target, then rerun the smoke test with a real tensor operation.
</details>

**Q4.** A team with AMD GPUs installs random package versions from several blog posts, then sees different ROCm behavior across two Linux workstations. How should they redesign the setup process before trying more package commands?

<details>
<summary>Answer</summary>
They should start from a supported-combination check: identify the GPU models, confirm the Linux distribution and ROCm release are supported, choose a documented framework build, and install into a clean project environment. ROCm setups are less forgiving when hardware, distribution, runtime, and framework builds are mixed casually. A smoke test should report HIP/build information and perform a small backend tensor operation when available.
</details>

**Q5.** A prototype began as a solo `venv` project, but now six developers need the same setup, host machines keep drifting, and the service is moving toward deployment. Should the team stay with only host Python, and what trade-off justifies your recommendation?

<details>
<summary>Answer</summary>
This is a strong case for introducing containers because repeatable onboarding, deployment alignment, and host drift are now real problems. The trade-off is that containers add image builds, runtime configuration, mounts, users, and GPU passthrough concerns. The recommendation is justified because the stronger boundary solves a concrete team problem, not because containers are automatically simpler.
</details>

**Q6.** A smoke test imports `torch` and exits successfully, so a learner marks the CUDA environment as verified. Later, training silently runs on CPU. How would you improve the smoke test to catch this earlier?

<details>
<summary>Answer</summary>
The smoke test should report framework build fields such as CUDA or HIP version, report backend availability, and execute a tiny tensor operation on the intended device. Import success alone only proves that Python can load the package. A real tensor operation proves much more: the framework build, runtime path, and device access are aligned enough for minimal computation.
</details>

**Q7.** During a rebuild, `pip install -r requirements.txt` succeeds, but `pip check` reports dependency conflicts and the model behaves differently from last week. What does this suggest about the project's dependency record, and how should the team respond?

<details>
<summary>Answer</summary>
It suggests the dependency record is not strong enough to recreate the previously tested environment, or that incompatible versions were allowed into the environment. The team should separate direct dependencies from resolved versions, regenerate or repair the lock-style record from a known-good environment, run `pip check`, and rerun the smoke test. If the project needs stricter repeatability, a higher-level lock tool or container build may be justified.
</details>

## Hands-On Exercise

Goal: build a clean AI project environment, document it, and prove whether it is currently CPU-only, CUDA-capable, or ROCm-capable. You do not need a GPU to complete the exercise; if no GPU tooling exists, your smoke test should report that clearly instead of pretending the backend is available.

- [ ] Create a fresh project directory with a local virtual environment and confirm the interpreter path is project-owned.

```bash
mkdir -p reproducible-ai-env/src reproducible-ai-env/notebooks reproducible-ai-env/data reproducible-ai-env/outputs
cd reproducible-ai-env
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -c "import sys; print(sys.version); print(sys.executable); print(sys.prefix)"
```

- [ ] Add a minimal dependency input file, install through the project interpreter, and record the resolved environment.

```bash
cat > requirements.in <<'EOF'
numpy
packaging
EOF

.venv/bin/python -m pip install -r requirements.in
.venv/bin/python -m pip freeze > requirements.txt
.venv/bin/python -m pip check
```

- [ ] Create a README that documents the setup contract another learner should follow.

```bash
cat > README.md <<'EOF'
# Reproducible AI Environment

## Setup
Use Python 3.12 to create `.venv`, then run package commands through `.venv/bin/python`.

## Install
`.venv/bin/python -m pip install -r requirements.txt`

## Verify
`.venv/bin/python verify_env.py`

## Hardware expectation
This project may run CPU-only unless the smoke test reports a working CUDA or ROCm backend.
EOF
```

- [ ] Add a `.gitignore` so local environments and generated artifacts are not treated as project source.

```bash
cat > .gitignore <<'EOF'
.venv/
__pycache__/
.ipynb_checkpoints/
outputs/
*.pyc
EOF
```

- [ ] Inspect GPU tooling before installing any framework-specific CUDA or ROCm package.

```bash
lspci | grep -Ei 'vga|3d|display' || true
command -v nvidia-smi || true
command -v rocminfo || true
```

- [ ] Create a smoke test that reports interpreter identity, package health, optional GPU tools, and optional framework backend status.

```bash
cat > verify_env.py <<'PY'
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


def optional_output(command: list[str]) -> str:
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return "not found"
    combined = completed.stdout.strip() or completed.stderr.strip()
    if not combined:
        return f"exit code {completed.returncode}"
    return "\n".join(combined.splitlines()[:8])


def main() -> None:
    print("project_root:", Path(__file__).resolve().parent)
    print("python_version:", sys.version.split()[0])
    print("python_executable:", sys.executable)
    print("python_prefix:", sys.prefix)
    print("platform:", platform.platform())
    print("virtual_env:", os.environ.get("VIRTUAL_ENV", "not set"))

    import numpy

    print("numpy_version:", numpy.__version__)
    print("nvidia_smi_status:", optional_output(["nvidia-smi"]))
    print("rocminfo_status:", optional_output(["rocminfo"]))

    try:
        import torch
    except ImportError:
        print("torch_status: not installed")
        print("backend_status: CPU-only verification path completed")
        return

    print("torch_version:", torch.__version__)
    print("torch_cuda_build:", torch.version.cuda)
    print("torch_hip_build:", torch.version.hip)
    print("torch_backend_available:", torch.cuda.is_available())

    if torch.cuda.is_available():
        value = torch.tensor([5.0, 7.0], device="cuda").sum().cpu().item()
        print("torch_tensor_backend: cuda-compatible API")
        print("torch_tensor_sum:", value)
    else:
        print("torch_tensor_backend: cpu-only path")


if __name__ == "__main__":
    main()
PY

.venv/bin/python verify_env.py
```

- [ ] Recreate the environment from the recorded dependency file and confirm the same verification command still works.

```bash
rm -rf .venv
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python verify_env.py
```

Success criteria:

- [ ] The project contains `.venv`, `requirements.in`, `requirements.txt`, `README.md`, `.gitignore`, and `verify_env.py`.

- [ ] Verification commands use `.venv/bin/python` after the bootstrap environment is created.

- [ ] `requirements.txt` can recreate the installed packages in a fresh `.venv`.

- [ ] `verify_env.py` prints the interpreter path, Python version, project root, platform, and `numpy` version.

- [ ] GPU inspection reports whether `nvidia-smi` or `rocminfo` is available, without failing the whole smoke test when either tool is missing.

- [ ] If PyTorch is installed later, the smoke test distinguishes CPU-only, CUDA-build, and HIP-build evidence before claiming backend success.

- [ ] The README tells a future learner how to install and verify the environment without relying on your terminal history.

## Next Module

- [Notebooks, Scripts, and Project Layouts](./module-1.4-notebooks-scripts-project-layouts/)
- [PyTorch Fundamentals](../deep-learning/module-1.2-pytorch-fundamentals/)
- [Home AI Workstation Fundamentals](./module-1.2-home-ai-workstation-fundamentals/)

## Sources

- [Python documentation: venv](https://docs.python.org/3/library/venv.html) — Official reference for creating isolated Python virtual environments.
- [Python Packaging User Guide: Installing Packages](https://packaging.python.org/en/latest/tutorials/installing-packages/) — Explains package installation workflows and virtual environment usage.
- [pip documentation: pip check](https://pip.pypa.io/en/stable/cli/pip_check/) — Documents dependency consistency checks used in the module's verification workflow.
- [pip documentation: requirements file format](https://pip.pypa.io/en/stable/reference/requirements-file-format/) — Defines how `requirements.txt` files are interpreted by pip.
- [IPython documentation: Installing the IPython kernel](https://ipython.readthedocs.io/en/stable/install/kernel_install.html) — Covers registering a project interpreter as a notebook kernel.
- [Jupyter documentation: Kernels](https://docs.jupyter.org/en/latest/projects/kernels.html) — Explains how notebooks choose the execution kernel that runs code.
- [PyTorch: Get Started](https://pytorch.org/get-started/locally/) — Provides official install selectors for CPU, CUDA, and ROCm builds.
- [PyTorch documentation: CUDA semantics](https://pytorch.org/docs/stable/notes/cuda.html) — Documents PyTorch CUDA behavior and device checks.
- [NVIDIA documentation: CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/) — Explains driver and CUDA runtime compatibility expectations.
- [AMD ROCm documentation: Compatibility matrix](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/reference/system-requirements.html) — Lists supported ROCm operating system, hardware, and software combinations.
- [Docker documentation: Build with Dockerfile](https://docs.docker.com/build/concepts/dockerfile/) — Provides official background for container image build files.
- [NVIDIA Container Toolkit documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/) — Explains GPU runtime integration for containers on NVIDIA systems.
- [github.com: RELEASE.md](https://github.com/pytorch/pytorch/blob/main/RELEASE.md) — PyTorch's upstream RELEASE.md contains the release compatibility matrix with explicit Python, CUDA, and ROCm columns.
- [PyTorch CUDA semantics docs](https://docs.pytorch.org/docs/stable/notes/cuda.html) — PyTorch's CUDA semantics docs explicitly show `torch.cuda.is_available()` in device-selection examples and discuss what that check does.
- [github.com: hip.rst](https://github.com/pytorch/pytorch/blob/main/docs/source/notes/hip.rst) — PyTorch's HIP semantics docs explicitly state that HIP reuses `torch.cuda` interfaces and show `torch.version.hip` versus `torch.version.cuda` checks.
- [github.com: nvidia container toolkit](https://github.com/NVIDIA/nvidia-container-toolkit) — The NVIDIA Container Toolkit README says the toolkit configures containers to use NVIDIA GPUs and explicitly requires the NVIDIA driver on the host.
