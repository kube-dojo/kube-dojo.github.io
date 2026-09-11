---
title: "Capstone: Train a Real Net End-to-End"
slug: ai-ml-engineering/deep-learning/module-1.7-capstone-train-a-real-net
sidebar:
  order: 1008
---

> **AI/ML Engineering Track** | Complexity: `[COMPLEX]` | Time: 6-8 hours
>
> **Prerequisites**: Modules 1.1.1–1.1.8 (Block A — forward pass, backprop, NumPy NN lab, scalar autograd), Modules 1.2, 1.3, 1.3.1–1.3.6 (Block B — PyTorch bridge, training loop, initialization, optimizers, regularization, normalization, diagnostics playbook, numerical stability), Modules 1.4.1–1.4.4 (Block C — embeddings, residual, attention, transformer from scratch), Modules 1.5 (CNNs) and 1.6 (RNNs/LSTMs) from Block D.
>
> **Primary tools**: PyTorch 2.12, torchvision, `torch.amp.autocast`, `torch.optim.AdamW`, `DataLoader`, `torch.save` / `torch.load`.

---

In 2018, the Conference on Neural Information Processing Systems (NeurIPS) introduced a mandatory reproducibility checklist for all submitted papers. The checklist was not a theoretical exercise — it was a response to a quiet crisis. A 2016 survey by Nature found that over 70% of researchers had tried and failed to reproduce another scientist's experiments, and more than half had failed to reproduce their own. In machine learning, where a single training run can consume thousands of GPU-hours, irreproducible results do not just waste time; they erode the foundation of peer review. Joelle Pineau, the NeurIPS reproducibility chair who championed the checklist, described the workflow that actually produces reliable results: fixed seeds, tracked hyperparameters, held-out test sets you touch exactly once, baselines you run before architectures, and an honest record of what failed, not just what worked.

That workflow is what this module teaches. You have built forward pass and backprop by hand (Block A). You have bridged to PyTorch and learned training as an engineering discipline: initialization, optimizers, regularizers, normalization, the diagnostics playbook, and numerical stability (Block B). You have assembled the transformer from scratch (Block C) and specialized architectures for vision and sequences (Block D). You now hold every piece. This module asks you to put them together — not to win a Kaggle competition or publish a paper, but to execute one honest, reproducible, end-to-end project the way a practitioner does it: dataset first, baseline second, architecture third, diagnostics throughout, ablation to verify understanding, and a runbook to close the loop.

We will work with CIFAR-10 — 60,000 32×32 color images across ten classes — because it is small enough for a laptop GPU or a Colab instance, real enough to reveal the problems you will encounter on larger datasets, and has served as a teaching benchmark since 2009. Every code block is designed to run on PyTorch 2.12. Every metric we report is labeled illustrative unless it is a published result you can verify. The goal is not a single number on a leaderboard. The goal is the process.

---

## Learning Outcomes

By the end of this module, you will be able to:

1. **Implement** a full end-to-end training pipeline — data loading, baseline, architecture selection (MLP versus CNN versus deeper CNN, justified by the data's structural properties from Blocks C and D), training loop, diagnostics, ablation, and checkpointing — on a real dataset using PyTorch 2.12.
2. **Design** a baseline-first strategy and **interpret** what a simple model's performance reveals about data quality, label consistency, and the difficulty ceiling before investing in architecture.
3. **Apply** the training-diagnostics playbook (Module 1.3.5) to diagnose convergence failures, overfitting, and optimization stalls in a multi-layer architecture, instrumenting every diagnostic signal from init loss to per-layer gradient norms.
4. **Run** a controlled ablation study isolating one variable at a time — normalization, depth, learning rate, augmentation — and **tabulate** the effect on a held-out validation metric with honest reporting of variance and seed sensitivity.
5. **Write** a reproducible engineer's runbook documenting hyperparameters, environment, known failure modes, and the next experiment to try, using `torch.save` and `state_dict` checkpointing as the foundation.

---

## Why This Module Matters

Building a neural network from scratch in NumPy (Block A) proved you understand the math. Bridging to PyTorch (Block B) proved you can use the tools. Architectures (Blocks C and D) proved you know the landscape. None of those prove you can take an unfamiliar dataset, pick a reasonable architecture, train it without leaking information, diagnose why it is not converging on epoch 17, isolate which design choice actually improved validation accuracy, and write down what you did so that someone — including yourself six months later — can reproduce it.

That is the gap between a student who has taken courses and an engineer who ships models. The gap is not mathematical depth. It is discipline: seed everything, never tune on the test set, run a baseline before you design an architecture, ablate one variable at a time, report variance across seeds, and document the failures. The modules that precede this one each gave you a tool — the diagnostics playbook in 1.3.5, the architectural reasoning in 1.5 and 1.6, the stability toolkit in 1.3.6. This module is the integration exercise that teaches you to hold all of them at once, in the right order, on a real problem.

The CIFAR-10 dataset we will use is intentionally modest. A ResNet-56 can reach 93% test accuracy on CIFAR-10 in under an hour on a single consumer GPU. But the point is not the final accuracy — the point is that you can trace every design decision from data inspection to final runbook, explain why it worked or did not work, and reproduce the result from scratch. That capability transfers directly to ImageNet-scale problems, to production vision systems, and to any supervised learning task where the data will not tell you what is wrong; only your process will.

---

## Part 1: Frame the Problem and the Data

Before you write a single `nn.Module`, you must understand what you are classifying and whether the data can be trusted. This section establishes the problem, the splits, the inspection routine, and the reproducibility foundation.

### 1.1 The task: CIFAR-10 image classification

CIFAR-10 contains 50,000 training images and 10,000 test images, each 32×32 pixels with three color channels (RGB), evenly distributed across ten classes: airplane, automobile, bird, cat, deer, dog, frog, horse, ship, truck. The images are tiny by modern standards — 32×32 is one-tenth the spatial dimension of a typical ImageNet crop — but that compression makes the problem interesting. A convolutional network must extract class-discriminative features (wheels versus wings, fur texture versus metallic sheen) from very limited spatial information.

The dataset is bundled with `torchvision` and can be loaded in two lines. But loading is the easy part. Understanding what you loaded — class balance, pixel statistics, label correctness — is where the engineering begins.

```python
import torch
import torchvision
import torchvision.transforms as T
from torch.utils.data import DataLoader, random_split

# Reproducibility foundation — seed everything before any random operation
torch.manual_seed(42)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

# Load the raw training set (no transforms yet — inspect first)
raw_train = torchvision.datasets.CIFAR10(
    root='./data', train=True, download=True, transform=T.ToTensor()
)
raw_test = torchvision.datasets.CIFAR10(
    root='./data', train=False, download=True, transform=T.ToTensor()
)
print(f"Train: {len(raw_train)}, Test: {len(raw_test)}")
# Train: 50000, Test: 10000
```

### 1.2 Data inspection: class balance, pixel statistics, and the first visual check

A balanced dataset is not guaranteed even when the documentation says "evenly distributed." You verify by counting. A dataset with an off-by-one label encoding — where class indices start at 0 but your loss function expects indices starting at 1 — will not error; it will silently degrade accuracy by 10% and you will spend three hours tuning the learning rate before you check.

```python
import numpy as np
from collections import Counter

# Count class frequencies
labels = [label for _, label in raw_train]
counts = Counter(labels)
for cls_idx, count in sorted(counts.items()):
    print(f"Class {cls_idx} ({raw_train.classes[cls_idx]}): {count}")
# Each should be 5000

# Per-channel mean and standard deviation (over the training set)
# Compute on the raw pixel values after ToTensor() (which scales to [0, 1])
all_pixels = torch.cat([img.reshape(3, -1) for img, _ in raw_train], dim=1)
mean = all_pixels.mean(dim=1)  # shape: (3,)
std = all_pixels.std(dim=1)    # shape: (3,)
print(f"Per-channel mean: {mean}")   # ~(0.4914, 0.4822, 0.4465)
print(f"Per-channel std:  {std}")    # ~(0.2470, 0.2435, 0.2616)
```

These statistics are canonical for CIFAR-10 — you will see them hard-coded in many repositories. But you should *verify* them on your own split because if your preprocessing pipeline accidentally applies the normalization twice, your model will train on data with unit variance instead of the original distribution, and the initialization scheme (Module 1.3.1) will produce activations at the wrong scale. Every number in your pipeline should be traceable to a measurement or a deliberate choice, never copied blindly.

### 1.3 The train/val/test split discipline

The test set of 10,000 images is sacred. You touch it exactly once — at the end, after every hyperparameter decision, every architecture choice, every ablation has been finalized on the training and validation sets. This is not a suggestion. It is the central contract of supervised learning: if you tune on the test set, your reported accuracy is no longer an estimate of generalization; it is a training metric with a misleading name.

From the 50,000 training images, we carve out a validation set:

```python
# Hold out 10% of the training set for validation
val_size = 5000
train_size = len(raw_train) - val_size
train_set, val_set = random_split(
    raw_train, [train_size, val_size],
    generator=torch.Generator().manual_seed(42)  # reproducible split
)
print(f"Train: {len(train_set)}, Val: {len(val_set)}, Test: {len(raw_test)}")
# Train: 45000, Val: 5000, Test: 10000
```

The `generator` argument to `random_split` ensures that the split is deterministic given the seed. Without it, two colleagues running the same script get different train/val assignments — and your reported validation accuracy will not be comparable to theirs. This is the kind of detail that separates a reproducible experiment from an anecdote.

### 1.4 Data leakage: the silent accuracy killer

Data leakage occurs when information from the validation or test set contaminates the training process. The most common vector on image datasets is computing normalization statistics (mean and standard deviation) on the combined train+val+test set, then applying those statistics during training. This is leakage because the normalization constants encode information about the test distribution — information the model should not have during training. The correct procedure is to compute mean and standard deviation on the *training set only*, apply those same constants to the validation and test sets, and never look at the test set's pixel distribution until the final evaluation.

A subtler form of leakage on CIFAR-10 is near-duplicate images. The dataset was collected by downsampling larger photographs, and some classes (automobile and truck, for example) share visual characteristics. If you perform data augmentation that generates validation-like crops during training, you should verify that your validation set is not bleeding into training through the augmentation pipeline. For CIFAR-10, the standard practice of computing normalization on the training split and applying it identically to val and test is sufficient; the dataset has been curated to avoid train/test overlap. But on your own datasets, always run a nearest-neighbor scan between splits before trusting the numbers.

### 1.5 Reproducibility: seeding, deterministic flags, and environment

Reproducibility in PyTorch requires three things: a fixed seed for Python's random module, a fixed seed for PyTorch's CPU RNG, and deterministic CUDA operations. The stanza you saw at the top of Section 1.1 is the minimum:

```python
torch.manual_seed(42)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
```

`cudnn.deterministic = True` forces cuDNN to use deterministic algorithms, which can be slower because it disables some optimized kernels that are non-deterministic by design. `cudnn.benchmark = False` prevents cuDNN from auto-tuning convolution algorithms based on input shape, which would introduce run-to-run variability even with fixed seeds. In production training where speed matters more than bit-for-bit reproducibility, you would set `benchmark = True` after validating correctness, but during development and especially during ablation studies, deterministic mode is non-negotiable.

Beyond the code, pin your environment. A `requirements.txt` or a `conda env export` file that records exact package versions — PyTorch 2.12, torchvision 0.25 (or whatever `torchvision.__version__` reports alongside PyTorch 2.12), CUDA toolkit version — is the difference between "it ran six months ago" and "it runs today." The NeurIPS reproducibility checklist asks for this explicitly because environment drift is one of the top-three causes of irreproducible results.

---

## Part 2: A Baseline First

The most expensive mistake in applied deep learning is building a sophisticated architecture before establishing that a simple model can learn anything at all from the data. A baseline serves as a sanity floor: if your logistic regression gets 40% test accuracy on a balanced ten-class problem (chance is 10%), the data, labels, and training loop are fundamentally functional. If it gets 12%, something is broken — and no ResNet will fix it.

### 2.1 The dumbest reasonable model

For CIFAR-10, a "dumbest reasonable" baseline is a single fully-connected layer with no hidden units — effectively multinomial logistic regression. The input is 3×32×32 = 3,072 pixels flattened into a vector. The output is ten logits.

```python
import torch.nn as nn

class LogisticBaseline(nn.Module):
    def __init__(self, input_dim=3072, num_classes=10):
        super().__init__()
        self.fc = nn.Linear(input_dim, num_classes)  # 3072 -> 10

    def forward(self, x):
        # x: (B, 3, 32, 32)
        x = x.reshape(x.size(0), -1)  # (B, 3072)
        return self.fc(x)              # (B, 10)

baseline = LogisticBaseline()
print(f"Baseline parameters: {sum(p.numel() for p in baseline.parameters()):,}")
# Baseline parameters: 30,730  (3072*10 weights + 10 biases)
```

Thirty thousand parameters on fifty thousand images — roughly 1.6 images per parameter. This is a heavily over-parameterized logistic regression, but it is also the simplest thing that could possibly work. If this model cannot exceed 30% validation accuracy after a reasonable number of epochs, something in the data pipeline or the loss function is wrong.

### 2.2 What the baseline buys you

The baseline answers four questions before you write a single convolutional layer:

**(1) Are the labels aligned with the inputs?** If `CrossEntropyLoss` receives logits with shape `(B, 10)` and targets with shape `(B,)` where each target is in `[0, 9]`, the loss should start near `ln(10) ≈ 2.30` — the expected entropy of a uniform distribution over ten classes. This is the init-loss sanity check from Module 1.3.5. If your init loss is 0.05 or 15.2, the shapes or label encoding are wrong.

```python
criterion = nn.CrossEntropyLoss()
# Random logits, shape (B, 10), with correct label indices in [0, 9]
dummy_logits = torch.randn(16, 10)
dummy_labels = torch.randint(0, 10, (16,))
init_loss = criterion(dummy_logits, dummy_labels).item()
print(f"Init loss: {init_loss:.3f}  (expected ~{np.log(10):.3f})")
# Init loss: ~2.30
```

**(2) Can the model overfit a single batch?** Take a batch of 64 training examples, disable all regularization, and train for 200 steps. The loss should drop below 0.1. If it does not, the model's capacity is insufficient, the loss function does not match the output head, or the optimizer is not actually updating the parameters (check `param.grad` after `loss.backward()`).

```python
def overfit_one_batch(model, loader, steps=200, lr=0.01):
    model.train()
    opt = torch.optim.SGD(model.parameters(), lr=lr)
    batch = next(iter(loader))
    xb, yb = batch
    for step in range(steps):
        opt.zero_grad()
        loss = nn.CrossEntropyLoss()(model(xb), yb)
        loss.backward()
        opt.step()
        if step % 50 == 0:
            print(f"  Step {step:3d}: loss = {loss.item():.4f}")
    return loss.item()

# Run on a small loader with one batch
tiny_loader = DataLoader(train_set, batch_size=64, shuffle=True)
final = overfit_one_batch(baseline, tiny_loader)
assert final < 0.1, f"Overfit test failed: final loss {final:.4f}"
```

**(3) Is there signal in the data?** A logistic regression baseline that achieves 38–42% validation accuracy on CIFAR-10 confirms that linear separability exists in the pixel space — not much, but enough to know the labels are not random. This number is your floor. Every architectural improvement must exceed it, or you are adding complexity that does not pay for itself. Interpreting the baseline is a skill, not a checkbox. If validation accuracy lands near 10%, you are at random chance — check label encoding and the train/val split before touching the CNN. If it lands in the 25–35% range, the pipeline works but the linear model is weak; a CNN should add meaningful lift. If it exceeds 45%, CIFAR-10's pixel space is surprisingly linearly separable for your split, and you should expect diminishing returns from depth alone. Record the baseline number in your runbook with the exact epoch count and optimizer settings so you can compare fairly when you swap architectures later.

**(4) What is the difficulty ceiling?** Human accuracy on CIFAR-10 is approximately 94% (Karpathy, 2011). A strong CNN with data augmentation reaches 95–97%. Knowing these numbers gives you a realistic target: anything above 90% is in the "respectable" range; anything above 95% is excellent. If you spend a week chasing 98% on CIFAR-10, you are overfitting to the test set, and the process in Section 2.1 should have warned you.

### 2.3 Baseline training loop

Train the baseline for a modest number of epochs (10–15) with a reasonable optimizer and learning rate. The goal is not peak performance but a validated floor.

```python
def train_one_epoch(model, loader, opt, device='cpu'):
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for xb, yb in loader:
        xb, yb = xb.to(device), yb.to(device)
        opt.zero_grad()
        logits = model(xb)
        loss = nn.CrossEntropyLoss()(logits, yb)
        loss.backward()
        opt.step()
        total_loss += loss.item() * xb.size(0)
        correct += (logits.argmax(dim=1) == yb).sum().item()
        total += xb.size(0)
    return total_loss / total, correct / total

def validate(model, loader, device='cpu'):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    with torch.no_grad():
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            logits = model(xb)
            loss = nn.CrossEntropyLoss()(logits, yb)
            total_loss += loss.item() * xb.size(0)
            correct += (logits.argmax(dim=1) == yb).sum().item()
            total += xb.size(0)
    return total_loss / total, correct / total
```

Running this on the logistic baseline with `AdamW(lr=1e-3)` for 15 epochs should yield a validation accuracy around 38–42%. If it does, the foundation is solid. If it does not, fix the pipeline before moving on — Part 5 of Module 1.3.5 is your reference.

---

## Part 3: Choose an Architecture Justified by the Data

CIFAR-10 is an image dataset. Images have spatial structure: adjacent pixels are highly correlated, and the features that distinguish an airplane from a bird (wings, cockpit, tail shape) are local patterns that can appear anywhere in the frame. A fully-connected network treats every pixel as an independent input with no spatial priors — it must *learn* that pixel (5,7) and pixel (5,8) are neighbors, burning parameters on spatial bookkeeping that a convolutional filter gets for free.

### 3.1 Why a CNN?

Module 1.5 established that a convolutional layer is a `nn.Linear` with two structural priors: weight sharing (the same filter slides across all spatial positions) and local connectivity (each output neuron sees only a small input patch). On a 32×32×3 image:

- A dense layer with 512 hidden units would have 32×32×3×512 ≈ 1.57 million parameters.
- A 3×3 convolutional layer with 64 output channels has 3×3×3×64 + 64 = 1,792 parameters.

The conv layer uses 0.1% of the parameters to capture local features everywhere in the image, and it does so translation-equivariantly: a wing shifted three pixels to the right activates the same filter at a different output location. The dense layer would need to see the wing at every possible position in the training set and memorize each one separately. That parameter efficiency is not a convenience — it is the difference between a model that learns generalizable features with 50,000 images and one that memorizes the training set.

### 3.2 Architecture design

Our architecture follows the LeNet-5 → VGG pattern: stacked convolutional blocks with increasing channel depth, interleaved pooling for spatial downsampling, and a small classifier head. We keep it modest — trainable on a single GPU with consumer VRAM — because the capstone is about process, not about squeezing out the last half-percent of accuracy.

```python
class CIFAR10CNN(nn.Module):
    def __init__(self, num_classes=10, dropout=0.3):
        super().__init__()
        # Block 1: 32x32 -> 16x16
        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)   # (B, 32, 32, 32)
        self.bn1   = nn.BatchNorm2d(32)
        self.conv2 = nn.Conv2d(32, 32, kernel_size=3, padding=1)  # (B, 32, 32, 32)
        self.bn2   = nn.BatchNorm2d(32)
        self.pool1 = nn.MaxPool2d(2)                               # (B, 32, 16, 16)

        # Block 2: 16x16 -> 8x8
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, padding=1)  # (B, 64, 16, 16)
        self.bn3   = nn.BatchNorm2d(64)
        self.conv4 = nn.Conv2d(64, 64, kernel_size=3, padding=1)  # (B, 64, 16, 16)
        self.bn4   = nn.BatchNorm2d(64)
        self.pool2 = nn.MaxPool2d(2)                               # (B, 64, 8, 8)

        # Block 3: 8x8 -> 4x4
        self.conv5 = nn.Conv2d(64, 128, kernel_size=3, padding=1) # (B, 128, 8, 8)
        self.bn5   = nn.BatchNorm2d(128)
        self.pool3 = nn.MaxPool2d(2)                               # (B, 128, 4, 4)

        # Classifier head
        self.flatten = nn.Flatten()
        self.fc1     = nn.Linear(128 * 4 * 4, 256)               # (B, 256)
        self.dropout = nn.Dropout(dropout)
        self.fc2     = nn.Linear(256, num_classes)                 # (B, 10)

    def forward(self, x):
        # x: (B, 3, 32, 32)
        x = torch.relu(self.bn1(self.conv1(x)))  # (B, 32, 32, 32)
        x = torch.relu(self.bn2(self.conv2(x)))  # (B, 32, 32, 32)
        x = self.pool1(x)                         # (B, 32, 16, 16)

        x = torch.relu(self.bn3(self.conv3(x)))  # (B, 64, 16, 16)
        x = torch.relu(self.bn4(self.conv4(x)))  # (B, 64, 16, 16)
        x = self.pool2(x)                         # (B, 64, 8, 8)

        x = torch.relu(self.bn5(self.conv5(x)))  # (B, 128, 8, 8)
        x = self.pool3(x)                         # (B, 128, 4, 4)

        x = self.flatten(x)                       # (B, 128*4*4) = (B, 2048)
        x = torch.relu(self.fc1(x))              # (B, 256)
        x = self.dropout(x)                       # (B, 256)
        x = self.fc2(x)                           # (B, 10)
        return x

model = CIFAR10CNN()
print(f"CNN parameters: {sum(p.numel() for p in model.parameters()):,}")
# CNN parameters: ~670,000
```

The architecture follows the principle of increasing channel depth as spatial resolution decreases — the computational budget shifts from spatial dimensions to feature dimensions, trading location precision for semantic richness. This is the same design pattern that scales from LeNet-5 (1998) to EfficientNet (2019): early layers learn edges and textures; deeper layers compose those into parts and objects.

Every shape annotation in the `forward` comments is a contract. If you change the kernel size or padding, the spatial dimensions shift, and the `fc1` input size `128 * 4 * 4` becomes wrong. The error will manifest as a cryptic `RuntimeError: mat1 and mat2 shapes cannot be multiplied` at the first forward pass — late enough to be annoying, early enough that you can fix it before any training has run. The fix is always to compute the spatial size after the final pooling layer and update the `Linear` input dimension, or to use `nn.AdaptiveAvgPool2d` to decouple the spatial output from the fully-connected input. We are keeping the explicit computation here because it forces you to understand the geometry — Module 1.5 walked through the output-size formula `(H - K + 2P)/S + 1` step by step.

### 3.3 Connecting architecture to diagnostics

This CNN is trainable with the same `train_one_epoch` and `validate` functions we wrote for the baseline. The training loop does not care whether the model is a single `nn.Linear` or a six-layer CNN — it calls `model(xb)`, computes the loss, calls `loss.backward()`, and steps the optimizer. This uniformity is the practical payoff of the `nn.Module` abstraction you learned in Module 1.2. Every architectural improvement you make from here — adding residual connections, increasing depth, swapping `MaxPool2d` for strided convolution — plugs into the same training loop. The diagnostics playbook from Module 1.3.5 applies identically.

---

## Part 4: The Training Loop, Done Properly

A training loop that works for a baseline on 50,000 images can break when you add BatchNorm, increase depth, or try mixed precision. This section builds the production training loop with the full toolkit from Block B, applied to the CNN from Part 3.

### 4.1 Normalized data pipeline

The raw pixel values from `T.ToTensor()` are in `[0, 1]`. Feeding unnormalized pixels into a network with random initialization produces input-to-first-layer activations whose variance depends on the image brightness distribution. We normalize using the per-channel statistics we computed in Part 1 so that each channel has zero mean and unit variance — a prerequisite for the initialization analysis in Module 1.3.1 to hold.

```python
# CIFAR-10 canonical normalization constants (computed on training set)
CIFAR10_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR10_STD  = (0.2470, 0.2435, 0.2616)

train_transform = T.Compose([
    T.RandomCrop(32, padding=4),       # padding then crop = cheap augmentation
    T.RandomHorizontalFlip(p=0.5),     # 50% horizontal flip
    T.ToTensor(),
    T.Normalize(CIFAR10_MEAN, CIFAR10_STD),
])

val_test_transform = T.Compose([
    T.ToTensor(),
    T.Normalize(CIFAR10_MEAN, CIFAR10_STD),
])

# Validation must use DETERMINISTIC transforms, never the random augmentation
# used for training. A Subset from random_split inherits its parent dataset's
# transform, so we load two views of the training data (one augmented, one not),
# split the indices once, and take the matching subset from each view.
train_full = torchvision.datasets.CIFAR10(
    root='./data', train=True, download=True, transform=train_transform
)
val_full = torchvision.datasets.CIFAR10(
    root='./data', train=True, download=True, transform=val_test_transform
)
test_set_final = torchvision.datasets.CIFAR10(
    root='./data', train=False, download=True, transform=val_test_transform
)

# Split the index set once (same seed -> consistent partition across both views).
train_idx, val_idx = random_split(
    range(len(train_full)), [45000, 5000],
    generator=torch.Generator().manual_seed(42)
)
train_set_final = torch.utils.data.Subset(train_full, list(train_idx))   # augmented
val_set_final   = torch.utils.data.Subset(val_full, list(val_idx))       # deterministic

# DataLoaders with sensible defaults
train_loader = DataLoader(train_set_final, batch_size=128, shuffle=True,
                          num_workers=2, pin_memory=True)
val_loader   = DataLoader(val_set_final, batch_size=128, shuffle=False,
                          num_workers=2, pin_memory=True)
test_loader  = DataLoader(test_set_final, batch_size=128, shuffle=False,
                          num_workers=2, pin_memory=True)
```

The augmentation strategy is minimal: random horizontal flips exploit the left-right symmetry of most CIFAR-10 classes (airplanes, cars, animals), and random crops with 4-pixel padding add translational invariance. This is not the most aggressive augmentation pipeline — no Cutout, no MixUp, no AutoAugment — because the capstone is about a clean baseline-to-ablation workflow, not about squeezing out the last percent of accuracy. You can add those later as an ablation.

### 4.2 Optimizer, learning rate schedule, and AMP

We use `AdamW` — the decoupled weight-decay variant of Adam that Module 1.3.2 analyzed. A cosine annealing schedule reduces the learning rate smoothly from its initial value to near zero over the course of training, which consistently outperforms step-wise decay in practice (Loshchilov & Hutter, 2017). Automatic Mixed Precision (AMP) trains most operations in `float16` for speed, automatically upcasting to `float32` where precision matters — the machinery Module 1.3.6 explained in detail.

```python
from torch.amp import autocast, GradScaler

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = CIFAR10CNN().to(device)

# AdamW with decoupled weight decay
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=1e-3,
    weight_decay=5e-4,
    betas=(0.9, 0.999),
)

# Cosine annealing from 1e-3 to 1e-6 over 80 epochs
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
    optimizer, T_max=80, eta_min=1e-6
)

# AMP scaler for mixed-precision training
scaler = GradScaler('cuda')  # 'cuda' or 'cpu'
criterion = nn.CrossEntropyLoss()
```

The `GradScaler` handles loss scaling: in `float16`, gradients smaller than ~2⁻²⁴ underflow to zero, so the scaler multiplies the loss by a large factor before `backward()`, then divides the gradients back down before the optimizer step. PyTorch's AMP does this automatically, adjusting the scale dynamically to avoid overflow. You do not need to understand the internals — Modules 1.3.2 and 1.3.6 covered them — but you do need to use the pattern correctly.

### 4.3 The full training loop with checkpointing and early stopping

This loop integrates every best practice from Block B: AMP, gradient clipping (in case the scaler encounters an overflow), checkpointing the best validation loss, and early stopping. It logs train loss, val loss, val accuracy, and the learning rate at every epoch — the minimum observability you need to apply the diagnostics playbook.

```python
import copy
import time

def train_model(model, train_loader, val_loader, optimizer, scheduler,
                scaler, criterion, device, epochs=80, patience=12,
                checkpoint_path='best_model.pt'):
    """Train with AMP, checkpointing, and early stopping."""
    best_val_loss = float('inf')
    best_model_state = None
    patience_counter = 0
    history = {'train_loss': [], 'val_loss': [], 'val_acc': [], 'lr': []}

    for epoch in range(epochs):
        t0 = time.time()

        # --- Training ---
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()

            with autocast('cuda' if device.type == 'cuda' else 'cpu'):
                logits = model(xb)                    # (B, 10)
                loss = criterion(logits, yb)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()

            train_loss += loss.item() * xb.size(0)
            train_correct += (logits.argmax(dim=1) == yb).sum().item()
            train_total += xb.size(0)

        train_loss /= train_total
        train_acc = train_correct / train_total

        # --- Validation ---
        model.eval()
        val_loss, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                logits = model(xb)
                loss = criterion(logits, yb)
                val_loss += loss.item() * xb.size(0)
                val_correct += (logits.argmax(dim=1) == yb).sum().item()
                val_total += xb.size(0)

        val_loss /= val_total
        val_acc = val_correct / val_total
        current_lr = optimizer.param_groups[0]['lr']

        # --- Logging ---
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['lr'].append(current_lr)

        elapsed = time.time() - t0
        print(f"Epoch {epoch+1:3d}/{epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f} | "
              f"LR: {current_lr:.2e} | {elapsed:.1f}s")

        # --- Checkpointing (best val loss) ---
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = copy.deepcopy(model.state_dict())
            patience_counter = 0
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'scheduler_state_dict': scheduler.state_dict(),
                'scaler_state_dict': scaler.state_dict(),
                'val_loss': val_loss,
                'val_acc': val_acc,
                'history': history,
            }, checkpoint_path)
            print(f"  -> Checkpoint saved (val_loss={val_loss:.4f})")
        else:
            patience_counter += 1

        # --- Early stopping ---
        if patience_counter >= patience:
            print(f"Early stopping at epoch {epoch+1} (no improvement for {patience} epochs)")
            break

        scheduler.step()

    # Restore best model
    if best_model_state is not None:
        model.load_state_dict(best_model_state)

    return history
```

A few design notes on this loop:

- **AMP context**: `autocast('cuda')` wraps only the forward pass. The loss computation, `backward()`, and optimizer step are outside `autocast` — the scaler handles precision management from there. Wrapping `backward()` in `autocast` is harmless but unnecessary.
- **Gradient clipping after `unscale_`**: The scaler inflates gradients during `scale(loss).backward()`. Calling `unscale_(optimizer)` restores them to their true magnitudes before clipping, so `max_norm=1.0` is applied to real gradient norms, not inflated ones.
- **Checkpoint format**: Saving the full training state — model weights, optimizer momentum buffers, scheduler state, AMP scaler internal state, and training history — makes the checkpoint a complete restore point. If training crashes at epoch 30, you resume from epoch 30, not from scratch. This is standard engineering practice and the foundation of the runbook in Part 7.
- **Early stopping**: Twelve epochs without validation loss improvement triggers a stop. This patience value is intentionally conservative for CIFAR-10; on larger datasets or with noisier validation metrics, you might use 20–30. The `best_model_state` is restored after training finishes so that any subsequent evaluation uses the checkpoint that achieved the lowest validation loss, not the final (possibly overfit) weights.

### 4.4 Expected results

With the architecture in Part 3 and this training loop, a single run on a consumer GPU (NVIDIA RTX 3060 or equivalent) should reach approximately 88–91% validation accuracy in 60–80 epochs. The training loss should decrease monotonically with small oscillations. The validation loss should decrease, flatten, and eventually begin to rise — the overfitting signature — at which point early stopping should trigger. The gap between training and validation accuracy should grow slowly; a gap exceeding 15% indicates overfitting and calls for stronger regularization (dropout increase, weight decay increase, or more aggressive augmentation).

These numbers are illustrative, not guaranteed. CIFAR-10 training is sensitive to initialization seed, GPU nondeterminism, and the exact data augmentation pipeline. If your numbers differ by 2–3 percentage points, that is normal variance across runs. If your validation accuracy is below 80% after 80 epochs, something systematic is wrong — return to the diagnostics playbook in Part 5.

---

## Part 5: Diagnostics — Read the Curves

The training loop in Part 4 produces four signals per epoch: training loss, validation loss, validation accuracy, and learning rate. This section applies the diagnostics playbook from Module 1.3.5 to those signals, showing you how to interpret what you see and act on it.

### 5.1 The four canonical curve shapes

Plot training and validation loss on the same axes. The relationship between them tells you more about your model than any single metric.

**Healthy convergence**: Both curves decrease, with validation loss slightly above training loss and a stable gap of 0.1–0.3. Validation accuracy rises and plateaus. This is what you want. No action needed — let training finish.

**Overfitting**: Training loss continues to decrease while validation loss rises after an initial decline. The gap between curves widens. Validation accuracy peaks and then degrades. The model is memorizing training-set noise that does not generalize. Fix: increase dropout, increase weight decay, add data augmentation, reduce model capacity, or trigger early stopping sooner. Module 1.3.3 covered each of these.

**Underfitting**: Both curves remain high and flat. Validation accuracy is only modestly above the baseline. The model does not have enough capacity or is not being trained aggressively enough. Fix: increase model depth or width, increase learning rate, reduce weight decay if it is too strong, or verify that the learning rate is not already at its minimum due to a misconfigured schedule.

**Optimization failure**: Training loss oscillates wildly, contains NaN values, or diverges. The learning rate is too high, or gradient norms are exploding. Fix: reduce learning rate by 3–10×, verify gradient clipping is active, check the per-layer gradient norms from Module 1.3.5 Section 3, and inspect for dead ReLUs in early layers. Module 1.3.6 covers the numerical-stability angle; Module 1.3.1 covers initialization as a root cause.

### 5.1.1 From curve shape to concrete next action

Reading curves is not pattern-matching for its own sake — each shape implies a specific intervention, and applying the wrong fix wastes epochs. When you see **healthy convergence**, log the epoch where validation loss first plateaus and compare it to your cosine schedule: if the plateau arrives while learning rate is still above 1e-4, you may have room to train longer or increase capacity modestly. When you see **overfitting**, do not reach for depth first. Increase regularization in order of cost: tighten early stopping (reduce patience from 12 to 8), raise weight decay from 5e-4 to 1e-3, increase dropout from 0.3 to 0.5, then add augmentation. Only after those levers are exhausted should you shrink the model. When you see **underfitting**, verify the learning rate has not collapsed prematurely — plot the LR curve alongside loss. A cosine schedule that reaches eta_min by epoch 40 on an 80-epoch budget can starve a model that was still improving at epoch 35. If LR is healthy but both curves stay high, add one conv block or widen channels by 50%, not both at once (that violates the ablation discipline in Part 6). When you see **optimization failure**, stop training immediately — continuing past the first NaN corrupts BatchNorm running statistics and wastes checkpoint slots. Reload the last good checkpoint, halve the learning rate, and confirm gradient norms stay below 10.0 for the first five epochs before resuming the full schedule.

The validation-accuracy curve deserves separate attention because it can diverge from loss in informative ways. A rising validation accuracy with flat validation loss usually means the model is sharpening predictions on examples it already classifies correctly — calibration is improving even though the argmax decision boundary is stable. A falling validation accuracy with falling validation loss means the model is becoming overconfident on wrong predictions — a classic sign that you should switch early-stopping criterion to accuracy if your deployment metric is accuracy, not cross-entropy. Plot per-class validation accuracy when aggregate accuracy stalls: CIFAR-10's cat/dog and automobile/truck pairs often dominate the error budget, and fixing class confusion requires targeted augmentation or class-weighted loss, not a global learning-rate change.

### 5.1.2 Using the learning-rate curve as a diagnostic overlay

Your training loop logs learning rate every epoch. Overlay it on the loss plot as a secondary y-axis or a separate panel beneath the loss curves. Three LR-related failure signatures appear repeatedly on CIFAR-10. **Premature annealing**: validation loss decreases until epoch 25, then flatlines while LR is still above 5e-4 — the schedule is too aggressive for your architecture. Extend `T_max` or add a linear warmup of 5 epochs before cosine decay. **LR too high at start**: training loss spikes in epoch 1–3 and never recovers — halve the initial LR and re-run the init-loss check; the spike often correlates with init loss above 3.0. **LR too low throughout**: both curves decrease monotonically but validation accuracy stalls below 85% after 60 epochs — the model is under-exploring the loss landscape. Double the initial LR and verify the overfit-one-batch test still passes; if it does, the higher LR is safe. These LR diagnostics are part of the training-diagnostics playbook from Module 1.3.5 — they turn a vague "it is not converging" complaint into a numbered experiment.

### 5.2 The overfit-one-batch sanity check, revisited

Before diagnosing any curve, run the overfit-one-batch test from Section 2.2 on your CNN. If it fails — loss does not go below 0.1 after 200 steps — the problem is not underfitting or overfitting; it is a bug in the model, the loss function, or the optimizer. Common causes:

- The `forward` method returns logits with the wrong shape (e.g., `(B, 10, 1, 1)` instead of `(B, 10)` because a `Flatten` was omitted).
- The optimizer's parameter list is empty (check `len(list(model.parameters()))` and `optimizer.param_groups[0]['params']`).
- A normalization layer is in `eval` mode during training (BatchNorm uses running statistics instead of batch statistics, adding noise and breaking gradient flow).
- The loss function expects log-probabilities but receives raw logits (use `CrossEntropyLoss`, not `NLLLoss`, unless you apply `log_softmax` explicitly).

This gauntlet catches 90% of training failures in under two minutes. Run it every time you change the architecture.

### 5.3 Gradient norms and dead units

After a few epochs, instrument the gradient norms. If the global gradient norm (via `clip_grad_norm_`'s return value in the training loop) grows exponentially across epochs, you have an exploding gradient problem — reduce the learning rate or add stronger clipping. If the norm collapses to near zero in early layers while later layers show healthy gradients, the early layers are receiving vanishing gradients — check initialization (Module 1.3.1), verify that activation functions are not saturating (ReLU is safe unless inputs are negative everywhere), and consider residual connections (Module 1.4.2).

Dead ReLU units — neurons that output zero for every input in the batch — are a specific failure mode. A ReLU unit dies when its weights shift such that its pre-activation is always negative. In a CNN, a dead filter contributes nothing and wastes computation. You can detect dead units by registering a forward hook that counts the fraction of zero activations:

```python
def dead_unit_fraction(module, input, output):
    """Hook to measure fraction of dead ReLU units in a layer."""
    # output shape: (B, C, H, W) — fraction of channels that are all-zero
    dead = (output.sum(dim=(0, 2, 3)) == 0).float().mean().item()
    if dead > 0.1:
        print(f"  WARNING: {dead*100:.1f}% dead units in {module.__class__.__name__}")
```

Attach this hook to every `nn.ReLU` or `nn.Conv2d` layer (after activation) and check once per epoch. If more than 10–20% of channels are dead, lower the learning rate, add BatchNorm if the layer lacks it, or reinitialize the affected layer.

### 5.4 The init-loss sanity check

Before the first training step, compute the loss on a random batch using the initialized model. For a balanced ten-class problem with random-weight logits, the expected cross-entropy is `ln(10) ≈ 2.30`. If your observed init loss is:

- **Near 0.0**: The model is outputting highly confident (wrong) predictions — likely the final layer bias is initialized to large values. This is harmless if the optimizer can correct it, but it obscures the sanity check. Zero-initialize the final bias explicitly: `nn.init.zeros_(model.fc2.bias)`.
- **Near 0.05–0.15**: Suspiciously low for random weights. Check whether the logits are being passed through `softmax` before the loss (double-softmax bug). The loss should receive raw logits; `CrossEntropyLoss` applies `log_softmax` internally.
- **Above 4.0**: The logits are peaked on the wrong classes. Verify label encoding — if labels are one-hot encoded instead of class indices, `CrossEntropyLoss` will produce garbage.
- **Exactly 2.30**: Your model, loss, and label encoding are consistent. Proceed.

This check takes fifteen seconds and catches label-encoding bugs before they burn a GPU-hour.

---

## Part 6: A Real Ablation

An ablation study is a controlled experiment: change exactly one component of your system, measure the effect, and report it honestly. The discipline of ablation is what separates a practitioner who understands *why* a model works from one who is guessing.

### 6.1 The protocol

Choose a fixed set of components to ablate. For each ablation, train the model from scratch with the same seed, the same number of epochs, and the same early stopping patience. Report validation accuracy, the number of epochs trained, and the standard deviation across three different seeds. The last point is critical: a 0.5% accuracy difference between two ablations is noise if the per-seed standard deviation is 1.2%.

```python
def ablation(model_fn, train_loader, val_loader, device, seeds=[42, 123, 456], epochs=80):
    """Run an ablation across multiple seeds and return mean ± std of best val acc."""
    results = []
    for seed in seeds:
        torch.manual_seed(seed)
        model = model_fn().to(device)
        opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=5e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-6)
        scaler = GradScaler('cuda')
        hist = train_model(model, train_loader, val_loader, opt, sched, scaler,
                          nn.CrossEntropyLoss(), device, epochs=epochs, patience=12)
        best_acc = max(hist['val_acc'])
        results.append(best_acc)
    return np.mean(results), np.std(results)
```

### 6.2 Ablation table

Run the following ablations and tabulate the results:

| Ablation | Description | Val Acc (mean ± std) | Δ vs Baseline |
|---|---|---|---|
| Baseline CNN | Architecture from Part 3 with BN, dropout=0.3, AdamW, cosine LR | Illustrative | — |
| No BatchNorm | Remove all BatchNorm layers; keep everything else identical | Lower by 2–5% | − |
| No augmentation | Remove RandomCrop and RandomHorizontalFlip; use only Normalize | Lower by 1–3% | − |
| LR × 10 | Increase initial learning rate from 1e-3 to 1e-2 | Training diverges or NaN | — |
| LR × 0.1 | Decrease initial learning rate from 1e-3 to 1e-4 | Slower convergence, possibly lower final accuracy | — |
| Half depth | Remove Block 3 (conv5, bn5, pool3); adjust fc1 input dim | Lower capacity | − |
| No dropout | Set dropout=0.0 | Possibly higher train acc, lower val acc (overfit) | − |

The numbers in this table are marked illustrative because they depend on your exact hardware, PyTorch build, and CUDA version. The *direction* of each effect is what matters: BatchNorm helps, augmentation helps, extreme LRs hurt, depth helps within reason. Your job is to fill this table with your own numbers and verify that the directions hold.

### 6.3 Honest reporting: what the ablation table is *not*

An ablation table is not a leaderboard. Its purpose is not to show that every design choice was brilliant. If removing BatchNorm *improves* validation accuracy on your setup (unlikely but possible with very small batch sizes where BN statistics are noisy), report it. If doubling the depth degrades performance because the model overfits with only 50,000 images, report it. The table is a diagnostic tool: each row tells you whether a component is pulling its weight. A component that does not improve validation accuracy across three seeds should be removed — it is dead complexity.

The standard deviation column is the honesty column. If your three seeds produce validation accuracies of 88.1%, 90.3%, and 88.9%, the mean is 89.1% and the standard deviation is 0.9%. An ablation that reports 89.5% (a 0.4% improvement) is statistically indistinguishable from the baseline. You should report it as "no significant effect" rather than claiming an improvement. The ML literature is littered with claimed improvements that disappear when you add error bars. Do not contribute to that problem.

### 6.3.1 How to read the ablation table row by row

Treat each row as a hypothesis test, not a scoreboard entry. Start with the **baseline CNN row** — this is your reference distribution. Before comparing any ablation, confirm that the baseline mean and standard deviation are stable across reruns on your hardware. If baseline seed 42 gives 90.2% but seed 123 gives 86.8% on the same code, your environment has nondeterminism you have not controlled; fix seeding and cuDNN flags before interpreting ablations. For the **No BatchNorm row**, expect a 2–5% drop on CIFAR-10 with batch size 128 — if the drop is zero or BatchNorm *helps* training loss but hurts validation, your batch size may be too small for reliable BN statistics (see the runbook failure mode in Section 7.1). For **No augmentation**, a 1–3% drop confirms that your CNN is relying on synthetic diversity; if the drop exceeds 5%, your base model may be overfitting and augmentation is doing heavy lifting — note that in the runbook as a capacity warning. For **LR × 10**, divergence or NaN is the expected outcome; if training completes but validation is worse than baseline by more than 10%, your gradient clipping saved the run but the LR is still too high for stable convergence. For **LR × 0.1**, slower convergence is expected; compare the epoch count at best validation loss, not just the peak accuracy — a model that reaches 89% at epoch 70 with LR × 0.1 may be cheaper to train to the same peak with the default LR in 45 epochs. For **Half depth** and **No dropout**, read the train/val gap: if removing dropout raises train accuracy by 8% but val accuracy falls by 2%, you have isolated overfitting as the binding constraint.

### 6.3.2 Seed variance and when to stop ablating

Running three seeds is a minimum, not a luxury. CIFAR-10's small training set (45,000 images after the val split) amplifies seed sensitivity: different shuffles expose different hard examples early in training, and AdamW's adaptive moments diverge subtly across runs. When seed standard deviation exceeds 1.0% for the baseline CNN, treat any ablation delta smaller than 1.5% as inconclusive and run two additional seeds before drawing conclusions. When standard deviation is below 0.5%, you can trust a 1.0% improvement as real — but still report mean ± std in the runbook, not the best seed alone. The stopping rule for ablation is practical: once you have identified which components matter (typically BatchNorm, augmentation, and depth on CIFAR-10), stop ablating and invest compute in the test-set evaluation and runbook. Ablating every hyperparameter is infinite; the capstone asks you to demonstrate the *discipline* of isolating one variable, not to exhaust the search space.

---

## Part 7: The Runbook and Shipping Mindset

An engineer's runbook is a document that answers one question: "If I need to reproduce this result six months from now, what do I do?" It is not a paper. It is not a blog post. It is a checklist.

### 7.1 What a runbook contains

A minimal runbook includes:

1. **Environment**: Python version, PyTorch version (2.12), CUDA version, key package versions (`torchvision.__version__`), and the GPU model. A `pip freeze > requirements.txt` or `conda env export > environment.yml` covers this.
2. **Reproduction command**: The single command that trains from scratch — typically `python train.py` with any required arguments. If training requires a specific seed, specify it.
3. **Dataset**: Where to download CIFAR-10, which splits were used, and the exact transforms (including normalization constants with four decimal places).
4. **Hyperparameters**: A table with every hyperparameter and its chosen value: initial LR, LR schedule, weight decay, batch size, optimizer, dropout, early stopping patience, number of epochs, AMP status.
5. **Results**: Validation accuracy (with standard deviation across seeds), test accuracy (exactly one evaluation, after all decisions are final), and the epoch at which the best validation checkpoint was saved.
6. **Known failure modes**: What commonly goes wrong — e.g., "without `cudnn.deterministic=True`, validation accuracy varies by ±0.8% across runs"; "BatchNorm with batch_size < 16 causes instability on this architecture."
7. **Next steps**: What you would try if you had more time or compute — e.g., "increase depth with residual connections (Module 1.4.2)"; "add Cutout augmentation"; "try a cosine LR schedule with warmup."

Here is a concrete runbook for our CIFAR-10 CNN:

```
# CIFAR-10 CNN Runbook
# Last updated: 2026-06-06

**Environment**
- Python 3.12, PyTorch 2.12, torchvision 0.25, CUDA 12.4
- GPU: NVIDIA RTX 3060 (12 GB VRAM)
- Full environment: requirements.txt at repo root

**Reproduction**
python train_cifar10.py --seed 42

**Dataset**
- CIFAR-10 from torchvision (auto-downloaded to ./data/)
- Train: 45,000 / Val: 5,000 / Test: 10,000
- Normalization: mean=(0.4914, 0.4822, 0.4465), std=(0.2470, 0.2435, 0.2616)
- Augmentation: RandomCrop(32, padding=4) + RandomHorizontalFlip(p=0.5)

**Hyperparameters**
| Parameter        | Value       |
|------------------|-------------|
| Optimizer        | AdamW       |
| Initial LR       | 1e-3        |
| LR schedule      | CosineAnnealingLR to 1e-6 over 80 epochs |
| Weight decay     | 5e-4        |
| Batch size       | 128         |
| Dropout          | 0.3         |
| Early stop patience | 12 epochs |
| AMP              | Yes (GradScaler) |
| Gradient clip    | max_norm=1.0 |
| Epochs (max)     | 80          |

**Results (3 seeds: 42, 123, 456)**
- Best validation accuracy: 90.2% ± 0.9% (mean ± std)
- Test accuracy (seed 42 best checkpoint): 89.8%
- Best val epoch: 52 (seed 42)

**Known failure modes**
- Without cudnn.deterministic=True, val accuracy varies ±0.8% across runs
- BatchNorm with batch_size=16 produces noisy statistics; use batch_size ≥ 64
- LR=1e-2 causes training divergence (NaN loss by epoch 5)
- Forgetting model.eval() during validation inflates val loss by ~0.3

**Next steps**
- Add Cutout augmentation (expected +0.5-1.0% val accuracy)
- Try ResNet-20 architecture for deeper residual learning
- Experiment with label smoothing (0.1) for better calibration
```

### 7.2 Saving and loading for serving

The `torch.save` call in Part 4 saves a full checkpoint dictionary. For serving — where you do not need the optimizer or scheduler state — save only the model's `state_dict`:

```python
# Save for inference/serving
torch.save(model.state_dict(), 'cifar10_cnn_weights.pt')

# Load for inference
model = CIFAR10CNN()
model.load_state_dict(torch.load('cifar10_cnn_weights.pt', map_location='cpu'))
model.eval()
```

If you are deploying to production behind an API, wrap this in a lightweight inference class that handles preprocessing (the exact same `T.Compose` pipeline used during validation), batching, and postprocessing (softmax → top-K class indices). Production serving, containerization, and Kubernetes deployment are outside the scope of this arc, but the trained `state_dict` and the normalization constants are the portable artifacts you would package in a `pytorch/pytorch:2.12.0-cuda12.4-cudnn9-runtime` image. Module 1.9 (Self-Supervised Learning) and the Advanced Electives track extend this foundation to production systems.

### 7.3 The test set: one evaluation, one number

After you have finalized every hyperparameter, every architecture choice, and every ablation based on the validation set — and only then — run a single evaluation on the test set:

```python
model.eval()
test_loss, test_correct, test_total = 0.0, 0, 0
with torch.no_grad():
    for xb, yb in test_loader:
        xb, yb = xb.to(device), yb.to(device)
        logits = model(xb)
        loss = criterion(logits, yb)
        test_loss += loss.item() * xb.size(0)
        test_correct += (logits.argmax(dim=1) == yb).sum().item()
        test_total += xb.size(0)

test_acc = test_correct / test_total
print(f"Test Accuracy: {test_acc:.4f}  ({test_correct}/{test_total})")
```

That is the only number you should ever report as your model's test accuracy. If you evaluate on the test set, adjust a hyperparameter, and evaluate again, you have contaminated the test set — it is now a second validation set, and your reported accuracy no longer estimates generalization. This is the discipline that the NeurIPS reproducibility checklist was designed to enforce. It feels conservative the first time you follow it. After your first project where a contaminated test set led you to ship a model that underperformed in production, it feels like the only sane choice.

---

## Did You Know?

- > **Did You Know?** Karpathy's "A Recipe for Training Neural Networks" was published as a single blog post in April 2019 and has been cited in thousands of papers, yet it contains no new algorithms — it is purely a process document. The overfit-one-batch test in Section 2.2, the init-loss sanity check in Section 5.4, and the curve-diagnosis framework in Section 5.1 all derive from that post.

- > **Did You Know?** The CIFAR-10 dataset was created by Alex Krizhevsky, Vinod Nair, and Geoffrey Hinton in 2009 at the University of Toronto as a manageable subset of the 80 Million Tiny Images dataset. It was explicitly designed to be "tractable for teaching and rapid experimentation" — and fifteen years later, it still is.

- > **Did You Know?** The Cosine Annealing learning rate schedule was proposed by Loshchilov and Hutter in their 2017 paper "SGDR: Stochastic Gradient Descent with Warm Restarts." The key insight — that smoothly decaying the learning rate to near zero produces better final performance than step-wise decay — is now a default in most training pipelines and is built into `torch.optim.lr_scheduler.CosineAnnealingLR`.

- > **Did You Know?** A 2021 study by Bouthillier et al. ("Accounting for Variance in Machine Learning Benchmarks") at NeurIPS demonstrated that the standard deviation of test accuracy across identical training runs with different random seeds often exceeds the claimed improvement of published architectural innovations. In other words, many papers reporting a 0.5% improvement were measuring noise. The multi-seed ablation protocol in Section 6.1 directly addresses this finding.

---

## Common Mistakes

| Mistake | Why it happens | Fix |
|---|---|---|
| Tuning hyperparameters on the test set | The temptation to "just check one more time" is strong, especially when a paper reports a higher number | Touch the test set exactly once, after all decisions are final. Use a dedicated validation split for all tuning |
| Skipping the baseline | Believing a simple model cannot possibly work on a complex dataset | Train logistic regression or a tiny MLP first. If it fails, the pipeline is broken |
| No fixed random seed | PyTorch defaults to random initialization and nondeterministic CUDA operations | Set `torch.manual_seed()`, `cudnn.deterministic=True`, and seed the DataLoader worker_init_fn |
| Comparing models trained for different numbers of epochs | Early stopping triggers at different epochs for different architectures | Report the best validation accuracy achieved, not the final epoch accuracy. Control for total optimizer steps |
| Reporting a single run with no variance | A lucky seed can inflate accuracy by 1–2% | Run at least three seeds, report mean ± standard deviation |
| Forgetting `model.eval()` during validation | BatchNorm and Dropout behave differently in train vs eval mode | Call `model.eval()` before validation and `model.train()` after. Use a context manager or a validation helper that enforces this |
| Not checkpointing the best validation model | Training continues past the best epoch, and the final model is overfit | Save `state_dict` whenever validation loss reaches a new minimum; restore after training |
| Using `torch.cuda.amp` instead of `torch.amp.autocast` | The `torch.cuda.amp` namespace is deprecated in favor of the device-generic `torch.amp` API; it still works as an alias but should not be used in new code | Use `torch.amp.autocast('cuda')` and `torch.amp.GradScaler('cuda')` |

---

## Quiz

1. **In an end-to-end training pipeline with data loading and checkpointing, why must you compute normalization statistics (mean and standard deviation) on the training set only, not on the combined train+val+test set?**

   <details>
   <summary>Answer</summary>

   Computing statistics on the combined set leaks information from the validation and test distributions into the training pipeline. The normalization constants encode pixel-level statistics of the test set — information the model should not have during training. The correct procedure is to compute statistics on the training set and apply those same constants to validation and test. This is a specific instance of the data-leakage principle from Section 1.4.

   </details>

2. **In a baseline-first strategy, what should you interpret from a logistic regression baseline's validation accuracy before investing in a CNN architecture, and what does the overfit-one-batch test prove about the pipeline?**

   <details>
   <summary>Answer</summary>

   The baseline-first strategy uses a simple model's validation accuracy as a sanity floor: 38–42% on CIFAR-10 confirms labels and data loading work; near 10% signals random chance and a broken pipeline; the number sets the minimum lift any CNN must deliver. The overfit-one-batch test proves that the model has sufficient capacity to memorize a small batch, that the loss function matches the output shape, that gradients flow through all parameters, and that the optimizer updates are applied correctly. It is the same contract test you ran in Module 1.3.5 Section 1 and in the Block A Tiny NumPy NN lab. It does **not** prove generalization, correct hyperparameter values, or that the architecture is suitable for the full dataset.

   </details>

3. **When applying the training-diagnostics playbook to diagnose convergence failures, your validation loss decreases but validation accuracy stays flat — what pattern is this, and what diagnostic action should you take next?**

   <details>
   <summary>Answer</summary>

   The model is becoming more confident in its correct predictions (reducing the loss contribution from correctly classified examples) while continuing to misclassify the same hard examples. The loss measures confidence-calibrated probability mass; accuracy measures only the argmax. This pattern often indicates that the model has saturated on easy examples and needs harder augmentation, a larger model, or a different architecture to separate the difficult classes. Apply the diagnostics playbook: check per-class accuracy — one or two classes are likely dragging down the aggregate number — then inspect curve shape (Section 5.1) before changing learning rate.

   </details>

4. **You run a controlled ablation study isolating BatchNorm as the only variable. The BatchNorm model's validation accuracy is 1.5% higher than the no-BatchNorm model, but the standard deviation across three seeds is 2.1%. Should you tabulate this as a significant result?**

   <details>
   <summary>Answer</summary>

   No. In a controlled ablation study that isolates one variable at a time, the effect size (1.5%) is smaller than the noise floor (2.1% standard deviation across seeds). Tabulate the result honestly as "no significant effect detected — more seeds or a larger dataset needed to resolve." A meaningful ablation row requires the delta to exceed seed variance; the multi-seed protocol in Section 6.1 exists precisely to prevent overinterpreting noise as signal when you run ablations on normalization, depth, learning rate, or augmentation.

   </details>

5. **Why does `torch.amp.autocast('cuda')` wrap only the forward pass and loss computation, not `backward()`?**

   <details>
   <summary>Answer</summary>

   `autocast` controls the precision of operations in the forward pass — convolutions, matrix multiplications, activations — casting them to `float16` where safe. The backward pass uses the same precision choices automatically because PyTorch records the autocast context in the autograd graph. Calling `GradScaler.scale(loss).backward()` then handles gradient scaling to prevent `float16` underflow. Wrapping `backward()` in `autocast` is redundant. Module 1.3.6 covered this mechanism in detail.

   </details>

6. **After training your CNN for 80 epochs, the test accuracy is 89.8%. A colleague reports 91.2% on the same architecture. List three non-architecture reasons the numbers could differ.**

   <details>
   <summary>Answer</summary>

   (1) **Different random seeds**: Initialization and data shuffling vary, producing different local minima. (2) **Different normalization constants**: If your colleague computed statistics on a different split or used different precision (three decimals vs four), the input distribution shifts. (3) **Different augmentation pipelines**: A subtle difference in `RandomCrop` padding, `RandomHorizontalFlip` probability, or ToTensor order changes the effective training set. (4) Hardware nondeterminism: Different GPU architectures or CUDA versions can produce slightly different convolution outputs even with `cudnn.deterministic=True` for some operations.

   </details>

7. **You are writing a reproducible engineer's runbook for a model you trained six weeks ago. You have the `best_model.pt` checkpoint but cannot remember the hyperparameters that produced it. What should you have documented, and what should you save differently next time?**

   <details>
   <summary>Answer</summary>

   The checkpoint saved in Section 4.3 includes `optimizer_state_dict`, `scheduler_state_dict`, `scaler_state_dict`, and `history` — but the hyperparameter values themselves (initial LR, weight decay, batch size) are not stored unless you explicitly add them to the checkpoint dictionary. You should either: save a `config` dict alongside the state dicts, use a configuration file (YAML/JSON) tracked in version control, or log all hyperparameters to a tool like Weights & Biases or TensorBoard at the start of training. The runbook in Section 7.1 should be written *during* the project, not reconstructed from memory afterward.

   </details>

8. **Why is early stopping on validation loss preferred over validation accuracy, even when accuracy is your primary metric?**

   <details>
   <summary>Answer</summary>

   Validation loss is a smoother, more informative signal than accuracy. Accuracy is a step function of the logits — a prediction that moves from 49.9% confidence to 50.1% confidence flips the argmax and changes accuracy, but the loss changes continuously. Validation loss captures improvements in calibration and confidence that accuracy ignores, and it generally peaks (reaches a minimum) before accuracy peaks (reaches a maximum), providing an earlier stopping signal. It is also directly comparable to the training loss, which accuracy is not — train/val accuracy gaps are harder to interpret because accuracy has a ceiling at 100%.

   </details>

---

## Hands-On Exercise

Train the CIFAR-10 CNN from scratch, produce an ablation table, and write a runbook. This exercise integrates every part of the module into a single deliverable you can reference for future projects.

**Task**: Starting from the code in Parts 1–4, train the `CIFAR10CNN` on CIFAR-10, run at least four of the ablations from Section 6.2, evaluate once on the test set, and produce a `RUNBOOK.md` in the format of Section 7.1.

**Steps**:

1. **Set up the environment.** Create a fresh Python script or Jupyter notebook. Install PyTorch 2.12 and torchvision. Copy the seeding stanza, the data loading code (Parts 1 and 4.1), the model definition (Part 3), and the training loop (Part 4.3) into your script. Verify that the code runs without errors on a single epoch.

2. **Train the baseline.** Before training the CNN, train the `LogisticBaseline` from Section 2.1 for 15 epochs with `AdamW(lr=1e-3)`. Record the validation accuracy. Confirm it exceeds 35%. If it does not, debug the pipeline using the init-loss and overfit-one-batch checks before proceeding.

3. **Train the CNN baseline.** Train `CIFAR10CNN` for 80 epochs with the hyperparameters from the runbook in Section 7.1. Log train loss, val loss, val accuracy, and learning rate for every epoch. Identify the epoch where validation loss reached its minimum — this is your best checkpoint.

4. **Run the ablations.** Using the `ablation` function from Section 6.1 (or a manual equivalent), run these four ablations across three seeds each:
   - No BatchNorm (remove all `nn.BatchNorm2d` layers from the model)
   - No augmentation (use only `T.ToTensor()` and `T.Normalize()` without `RandomCrop` or `RandomHorizontalFlip`)
   - LR × 10 (initial learning rate `1e-2` instead of `1e-3`)
   - No dropout (set `dropout=0.0` in `CIFAR10CNN`)

   For each ablation, record the mean and standard deviation of the best validation accuracy across three seeds. Fill in the ablation table from Section 6.2.

5. **Evaluate on the test set — once.** Load the best checkpoint from the CNN baseline (seed 42), run `model.eval()`, and compute the test accuracy. This is your final reported number. Do not re-evaluate after adjusting anything.

6. **Write the runbook.** Create a `RUNBOOK.md` file containing all seven sections from Section 7.1: environment, reproduction command, dataset, hyperparameters table, results, known failure modes, and next steps. Include the ablation table results in the "Results" section.

**Success Criteria**:

- [ ] `LogisticBaseline` achieves ≥35% validation accuracy on CIFAR-10
- [ ] `CIFAR10CNN` achieves ≥85% validation accuracy (best checkpoint, seed 42)
- [ ] Ablation table filled with four rows, each with mean ± std across three seeds
- [ ] Test accuracy evaluated exactly once and recorded
- [ ] `RUNBOOK.md` contains all seven sections from Section 7.1
- [ ] The overfit-one-batch test passed for both the baseline and the CNN
- [ ] Init loss verified within 0.3 of `ln(10)` before training the CNN

**Verification**:

```python
# After training completes, verify the key assertions
import math

assert baseline_val_acc >= 0.35, f"Baseline accuracy too low: {baseline_val_acc}"
assert cnn_val_acc >= 0.85, f"CNN accuracy too low: {cnn_val_acc}"
assert abs(init_loss - math.log(10)) < 0.3, f"Init loss check failed: {init_loss}"
assert overfit_final_loss < 0.1, f"Overfit test failed: {overfit_final_loss}"
print("All capstone exercise checks passed.")
```

---

## Key Takeaways

- **Process over architecture**: A disciplined workflow — baseline first, dataset inspection, fixed seeds, held-out test set, one-variable-at-a-time ablation — produces reliable results faster than adding architectural complexity to a broken pipeline.
- **The baseline is non-negotiable**: A logistic regression or tiny MLP catches label bugs, data leakage, and loss-function mismatches before they waste GPU-hours in a deep network. If the baseline cannot exceed random chance, the CNN will not either.
- **The training-diagnostics playbook (Module 1.3.5) is the universal debugger**: Init-loss sanity, overfit-one-batch, curve reading, gradient norms, and dead-unit detection — applied in order — localize the root cause of training failures without guessing.
- **AMP is standard, not optional**: `torch.amp.autocast` reduces memory usage and increases throughput with no accuracy penalty when used correctly. The `GradScaler` pattern in Section 4.3 is the canonical PyTorch 2.12 recipe.
- **Checkpoint the best validation model, not the last model**: Early stopping and checkpoint restoration ensure you evaluate the model that generalized best, not the one that trained longest and potentially overfit.
- **Ablation with variance reporting is how you know what matters**: Changing one variable at a time across multiple seeds and reporting mean ± standard deviation distinguishes real improvements from noise. Most published "improvements" below 1% fail this test.
- **The runbook is the deliverable, not the accuracy number**: A model with 90% accuracy and no documentation is a curiosity. A model with 88% accuracy and a complete runbook is an engineering asset — reproducible, debuggable, and extendable by anyone.

---

## Sources

- Karpathy, A. (2019). *A Recipe for Training Neural Networks*. https://karpathy.github.io/2019/04/25/recipe/
- Krizhevsky, A., Nair, V., & Hinton, G. (2009). *CIFAR-10 Dataset*. https://www.cs.toronto.edu/~kriz/cifar.html
- Pineau, J. et al. (2019). *NeurIPS Reproducibility Program*. https://neurips.cc/Conferences/2019/CallForReproducibility
- Loshchilov, I. & Hutter, F. (2017). *SGDR: Stochastic Gradient Descent with Warm Restarts*. https://arxiv.org/abs/1608.03983
- Bouthillier, X. et al. (2021). *Accounting for Variance in Machine Learning Benchmarks*. https://arxiv.org/abs/2103.03098
- Zhang, A., Lipton, Z.C., Li, M., & Smola, A.J. (2023). *Dive into Deep Learning (d2l.ai)* — Chapter 7: Modern Convolutional Neural Networks, Chapter 13: Computer Vision. https://d2l.ai/
- Stanford CS231n: *Convolutional Neural Networks for Visual Recognition*. https://cs231n.github.io/
- PyTorch 2.12 Documentation: `torch.amp.autocast`. https://pytorch.org/docs/stable/amp.html
- PyTorch 2.12 Documentation: `torch.optim.AdamW`. https://pytorch.org/docs/stable/generated/torch.optim.AdamW.html
- PyTorch 2.12 Documentation: `torch.utils.data.DataLoader`. https://pytorch.org/docs/stable/data.html
- PyTorch 2.12 Documentation: `torch.save` and `torch.load`. https://pytorch.org/docs/stable/generated/torch.save.html
- LeCun, Y., Bottou, L., Bengio, Y., & Haffner, P. (1998). *Gradient-Based Learning Applied to Document Recognition* (LeNet-5). http://yann.lecun.com/exdb/publis/pdf/lecun-98.pdf
- He, K., Zhang, X., Ren, S., & Sun, J. (2016). *Deep Residual Learning for Image Recognition* (ResNet). https://arxiv.org/abs/1512.03385
- Baker, M. (2016). *1,500 scientists lift the lid on reproducibility*. Nature, 533, 452–454. https://www.nature.com/articles/533452a
- Loshchilov, I. & Hutter, F. (2019). *Decoupled Weight Decay Regularization* (AdamW). https://arxiv.org/abs/1711.05101

---

## Next Module

Continue to **[Module 1.8: Self-Supervised Learning](../module-1.8-self-supervised-learning/)** — where you will learn to train without labels, pretraining representations on unlabeled data before fine-tuning on scarce annotations. The end-to-end supervised workflow you mastered here is the foundation; self-supervised learning extends it to data regimes where labels are the bottleneck.

---

## Learner check

> | 1.7 | [Capstone: Train a Real Net End-to-End](/ai-ml-engineering/deep-learning/module-1.7-capstone-train-a-real-net/) |
