---
title: "Convolutional Neural Networks & Computer Vision"
slug: ai-ml-engineering/deep-learning/module-1.5-cnns-computer-vision
sidebar:
  order: 1006
---

> **AI/ML Engineering Track** | Complexity: `[COMPLEX]` | Time: 5–6 hours
>
> **Prerequisites**: Block A (forward pass, backprop by hand, scalar autograd). Block B (PyTorch bridge, initialization 1.3.1, normalization 1.3.4, training diagnostics 1.3.5, numerical stability 1.3.6). Block C (residual connections 1.4.2 — you will reuse the same skip-connection intuition in ResNet blocks here).
>
> **Primary tools**: PyTorch 2.12, `torchvision` pretrained models.

---

In September 2012, a team from the University of Toronto entered the ImageNet Large Scale Visual Recognition Challenge with a deep convolutional network called AlexNet. The competition had been running since 2010, and the winning top-5 error rate had hovered around 26% the year before. AlexNet cut that figure to roughly 15.3% — a margin so large that computer-vision researchers initially suspected a data-handling bug rather than a genuine breakthrough. The network was not radically new in its ingredients: convolutions, pooling, ReLU activations, and fully connected layers had all appeared in Yann LeCun's LeNet-5 architecture, which AT&T Bell Labs had deployed commercially in the late 1990s to read handwritten digits on bank cheques. What changed in 2012 was scale — millions of labelled images, GPUs that could train on them in days rather than weeks, and an engineering culture that treated depth and data augmentation as first-class design levers. AlexNet did not invent convolution; it proved that, given enough data and compute, a convolutional stack could outperform hand-crafted feature pipelines on a problem the field had considered nearly solved.

That result redirected an entire industry toward deep learning, but the underlying idea is older and simpler than the hype suggests. A convolutional layer is not a new kind of mathematics. It is a `nn.Linear` layer with two structural priors bolted on: **weight sharing** (the same small filter slides across every spatial position) and **local connectivity** (each output neuron sees only a patch of the input, not the full image). You already derived backpropagation by hand in Block A and traced how gradients accumulate when the same weight is reused — that is exactly what happens when a conv filter's gradient is summed over every position it touched during the forward pass. You already built residual blocks in module 1.4.2; ResNet's skip connections are the same gradient highway applied to spatial feature maps. You already studied BatchNorm in module 1.3.4; every modern CNN block wraps convolutions in normalization for the same loss-smoothing reason. This module shows that computer vision is not a separate subject — it is the dense network you already own, specialised for images by structure rather than by magic.

---

## Learning Outcomes

By the end of this module, you will be able to:

- **Explain** why flattening a high-resolution image into a dense layer causes catastrophic parameter blow-up, and **articulate** how weight sharing and local connectivity encode translation-aware inductive biases that dense layers lack.
- **Derive** convolution output dimensions using `out = floor((H − K + 2P)/S) + 1`, **verify** the result with a numeric worked example, and **implement** the same operation both as an explicit loop and via `nn.Conv2d` with shape comments at every step.
- **Compare** max pooling, average pooling, and strided convolutions as downsampling strategies, and **trace** how receptive fields grow with depth so that deep units integrate context from large regions of the original image.
- **Implement** a complete small CNN classifier for CIFAR-10-shaped inputs in PyTorch 2.12, **summarize** the design principles behind LeNet-5, AlexNet, VGG, and ResNet, and **connect** ResNet skip connections to the residual-stream model from module 1.4.2.
- **Design** a transfer-learning pipeline with a `torchvision` ImageNet backbone, **evaluate** where CNNs sit relative to Vision Transformers today, and **debug** common train/eval and normalization mistakes using the diagnostics mindset from module 1.3.5.

---

## Why This Module Matters

Images are not vectors. A 224×224 RGB photograph contains 150,528 pixel values arranged in a two-dimensional grid with strong local correlations — neighbouring pixels tend to share colour and texture, edges form continuous curves, and objects occupy contiguous regions. If you flatten that grid and feed it into a single `nn.Linear` layer with 1,000 hidden units, you need roughly 150 million weight parameters for the first layer alone, and you destroy every spatial relationship the grid encoded. The network must relearn from scratch that a cat's ear two pixels to the left is still a cat's ear. Convolutional neural networks (CNNs) solve this by baking spatial structure into the architecture: each filter looks at a small local window, the same filter is applied everywhere, and stacking layers builds a hierarchy from edges to textures to object parts.

For an engineering practitioner who has already built backpropagation and trained MLPs, the payoff of this module is conceptual unification. You do not need a new autograd engine, a new optimizer, or a new loss function to train a CNN. You need to understand how convolutions reshape tensors, how parameter counts shrink relative to dense equivalents, and how the training diagnostics you learned in module 1.3.5 — watching train/val loss divergence, checking gradient norms, verifying input normalization — apply unchanged to vision models. When a production vision model underperforms, the failure modes are almost always engineering failures: wrong channel order, missing ImageNet normalization, BatchNorm left in training mode during inference, or padding math that silently crops the input. This module teaches you to see those bugs before they reach a deployment runbook.

Computer vision also sits at the historical centre of deep learning's industrial adoption. The techniques you learn here — transfer learning from ImageNet, data augmentation, mixed-precision training from module 1.3.6 — are the same production patterns used in medical imaging, manufacturing defect detection, satellite analysis, and on-device inference. Vision Transformers and hybrid ConvNeXt-style architectures have shifted the research frontier, but CNNs remain the default choice when data is limited, latency budgets are tight, or you need a well-understood baseline before experimenting with heavier models. Finishing this module means you can justify architecture choices from data structure, not from blog-post trends.

Engineers sometimes ask whether they should learn CNNs at all in the transformer era. The honest answer is yes, because the structural priors taught here — locality, weight sharing, hierarchical feature maps — explain not only classical vision backbones but also the inductive biases that patch-based transformers lack until they have seen enormous pretraining corpora. When you read a ViT paper's ablation that adds convolutional stem layers to stabilize early training, you are watching the field reuse the lessons of this module inside a nominally attention-first architecture.

There is a final reason this module belongs at the end of the architecture arc before sequence models and the capstone. In Block C you built attention and transformer blocks that operate on sequences of tokens. Images are not token sequences until you patchify them — which is exactly what Vision Transformers do. CNNs treat the grid structure as primary: locality and weight sharing are hard-coded, not learned from data. Understanding conv nets first makes the ViT design choice legible later. When someone proposes "just use a ViT," you can ask the engineering questions that matter: how much labelled data do we have, what is our latency budget, do we need translation equivariance, and can we afford the pretraining recipe? The answer is often a ResNet baseline with transfer learning, not because transformers are wrong, but because the inductive bias matches the problem.

---

## Part 1: Why Convolution, Not a Dense Layer, for Images

Consider a colour image of size 224×224×3. Flattening produces a vector of length 150,528. Connecting that vector to a hidden layer of 1,000 neurons requires a weight matrix of shape `(150528, 1000)` — about **150.5 million** parameters in a single layer, before counting biases or any deeper layers. A dataset of 50,000 training images cannot reliably estimate that many degrees of freedom; the model memorizes noise. Worse, the weight matrix has no built-in notion of locality. The weight connecting pixel (10, 10) to hidden neuron 42 is unrelated to the weight connecting pixel (11, 10) to neuron 42, even though those pixels are neighbours in the image.

Convolution replaces this free-for-all with two structural priors that you can state in the language of Block A:

**Local connectivity.** Each output value depends only on a small patch of the input — for a 3×3 kernel, nine input pixels (per channel) rather than the full 150,528. That is the spatial analogue of an MLP hidden unit that sees a low-dimensional slice of the input instead of the entire vector.

**Weight sharing.** The same kernel weights are applied at every spatial position. If the network learns a vertical-edge detector, that detector slides across the entire image. In backprop terms, the kernel's gradient at each position is computed independently, then **summed** into a single shared weight tensor — exactly the gradient-accumulation pattern you saw when the same scalar weight appeared on multiple paths in your hand-derived computation graphs.

Viewed this way, a conv layer is a structured, weight-tied dense layer. Unroll every local patch into a row, stack the rows, and the convolution becomes a sparse matrix multiply with repeated blocks — but materializing that matrix would defeat the purpose. PyTorch's `nn.Conv2d` implements the operation directly with fused CUDA kernels, which is why production vision code never expands convolutions into literal dense matrices.

The inductive bias has a practical consequence practitioners feel daily: **translation equivariance** (roughly, if a feature shifts in the input, the corresponding activation shifts in the feature map) combined with pooling yields **translation invariance** (the network cares less about exact pixel coordinates). A pedestrian detector that fires only when a person stands in the centre of the frame is useless on a roadside camera; convolution plus pooling builds the spatial robustness that dense layers would need to learn from data alone.

```text
Dense layer on flattened 224×224×3 image:
  Input: 150,528 values — each connects to every hidden unit
  Parameters (1000 hidden): ~150.5M weights

Conv2d(3 → 64, kernel 3×3, padding 1):
  Each output sees 3×3×3 = 27 inputs (local)
  Same 27 weights reused at every spatial position
  Parameters: 64 × 3 × 3 × 3 + 64 biases = 1,792 weights
```

The parameter ratio is not a rounding error — it is six orders of magnitude. That is why CNNs were feasible on 1990s cheque-reading hardware long before ImageNet-scale GPUs existed, and why they remain the efficient default on edge devices today.

To make the weight-sharing view concrete, imagine unrolling a single row of a grayscale image into patches of length nine (a 3×3 window). A dense layer would assign independent weights to every patch location. A convolutional layer uses one nine-weight filter at position zero, the **same** nine weights at position one, and so on across the row. In the backward pass, the gradient for the third weight in the filter equals the sum of ∂L/∂(output at position 0)×(input at position 2) plus the same contribution from position 1, position 2, and every other position where that weight participated. You derived this accumulation pattern manually in module 1.1.6 when a shared scalar appeared on multiple paths. Convolution is that idea in two spatial dimensions with thousands of filters running in parallel.

Translation equivariance is not the same as translation invariance, and the distinction matters when you debug detectors. Pure convolution is equivariant: shift the input, and the feature map shifts correspondingly. Classifiers usually want invariance: a cat in the top-left should score like a cat in the bottom-right. Pooling (and data augmentation during training) pushes the network toward invariance by discarding exact coordinates while preserving strong local responses. If your model is equivariant when you wanted invariance, add pooling or global average pooling before the softmax; if it is too invariant and misses fine localization, reduce pooling depth or add skip connections that preserve higher-resolution feature maps for a segmentation head.

---

## Part 2: The Convolution Operation in Detail

### 2.1 Kernels, stride, padding, and channels

A **kernel** (or **filter**) is a small learnable tensor. For RGB input, a single filter has shape `(C_in, K, K)` — three colour channels times a `K×K` spatial stencil. A `nn.Conv2d` layer holds `C_out` such filters, producing `C_out` feature maps.

The forward pass slides each filter across the height and width of the input. At each position, it computes the sum of element-wise products between the filter and the input patch — the discrete cross-correlation that deep-learning frameworks call "convolution." (Purists note the sign flip relative to the mathematical convolution definition; PyTorch follows the cross-correlation convention used throughout the vision literature.)

**Stride** `S` controls how far the window advances. Stride 1 evaluates every position; stride 2 skips every other position, halving spatial resolution in one step. **Padding** `P` adds border pixels (usually zeros) so that edge positions have enough context; `padding=1` with `kernel_size=3` preserves height and width when stride is 1. **Dilation** inserts gaps between kernel elements, expanding the receptive field without downsampling — useful in segmentation, where you need context without destroying pixel alignment.

Channel order is a recurring source of silent bugs. OpenCV, PIL, and NumPy often store colour images as `(H, W, C)` while PyTorch conv layers expect `(N, C, H, W)`. The `torchvision.transforms.ToTensor()` helper converts PIL images to `(C, H, W)` in `[0, 1]` range and is the safest default in data pipelines. If you hand-build tensors from NumPy, insert an explicit `permute(2, 0, 1)` and document the transformation in comments so the next engineer does not flip channels accidentally. Grayscale inputs use `C=1`; medical and industrial greyscale pipelines frequently forget to unsqueeze the channel dimension, producing shape `(B, H, W)` instead of `(B, 1, H, W)` and failing on the first `Conv2d` call.

### 2.2 Output-size formula and numeric check

The spatial output size for one dimension is:

```text
out = floor((H − K + 2P) / S) + 1
```

Worked example matching a common ImageNet stem pattern:

```text
Input height H = 224, kernel K = 3, padding P = 1, stride S = 2

out = floor((224 − 3 + 2×1) / 2) + 1
    = floor(223 / 2) + 1
    = floor(111.5) + 1
    = 111 + 1
    = 112
```

So `Conv2d(3, 96, kernel_size=3, stride=2, padding=1)` maps `(B, 3, 224, 224)` → `(B, 96, 112, 112)`. Always run this arithmetic before debugging a shape mismatch in a training loop — the formula is faster than reading a stack trace.

### 2.3 From-scratch loop, then `nn.Conv2d`

Seeing the loop once connects the API to the math:

```python
import torch

def conv2d_single_channel(
    image: torch.Tensor,   # (H, W)
    kernel: torch.Tensor,  # (K, K)
    stride: int = 1,
    padding: int = 0,
) -> torch.Tensor:
    """Explicit correlation — pedagogical only; use F.conv2d in production."""
    if padding > 0:
        image = torch.nn.functional.pad(image, (padding, padding, padding, padding))
    H, W = image.shape
    K = kernel.shape[0]
    out_h = (H - K) // stride + 1
    out_w = (W - K) // stride + 1
    out = torch.zeros(out_h, out_w)
    for i in range(out_h):
        for j in range(out_w):
            patch = image[i * stride : i * stride + K, j * stride : j * stride + K]
            out[i, j] = (patch * kernel).sum()
    return out

# Tiny numeric sanity check
img = torch.tensor([
    [1., 2., 3., 4., 5.],
    [6., 7., 8., 9., 10.],
    [11., 12., 13., 14., 15.],
    [16., 17., 18., 19., 20.],
    [21., 22., 23., 24., 25.],
])
edge_kernel = torch.tensor([
    [1., 0., -1.],
    [1., 0., -1.],
    [1., 0., -1.],
])
manual = conv2d_single_channel(img, edge_kernel)  # (3, 3)

conv = torch.nn.Conv2d(1, 1, kernel_size=3, padding=0, bias=False)
with torch.no_grad():
    conv.weight.copy_(edge_kernel.view(1, 1, 3, 3))
api = conv(img.unsqueeze(0).unsqueeze(0))[0, 0]  # (3, 3)
assert torch.allclose(manual, api, atol=1e-5)
```

Production code uses `nn.Conv2d`, which fuses the loop and runs on GPU:

```python
import torch.nn as nn

# (B, C_in, H, W) -> (B, C_out, H', W')
rgb = torch.randn(4, 3, 224, 224)          # batch of 4 ImageNet-sized images
layer = nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, padding=1)
features = layer(rgb)
print(features.shape)  # torch.Size([4, 32, 224, 224]) — spatial size preserved
```

### 2.4 Backprop through shared weights

During the backward pass, each position where a kernel weight `w` participated in the forward sum contributes `∂L/∂w` through the chain rule. Because the **same** `w` appears at every position, PyTorch **accumulates** those contributions into one gradient tensor. If you unrolled the convolution into independent dense operations per patch, you would sum their weight gradients manually; `nn.Conv2d` does that summation inside the CUDA kernel. This is the spatial twin of backprop through a recurrent weight shared across timesteps — you will see the temporal version in the next module on RNNs.

### 2.5 Parameter count: conv versus hypothetical dense

For `Conv2d(C_in, C_out, kernel_size=K)`, weights number `C_out × C_in × K × K` (plus `C_out` biases if enabled). Compare to a dense layer connecting every pixel in a 7×7 patch to one neuron: `C_in × 7 × 7` inputs per neuron, `C_out` neurons → `C_out × C_in × 49` — identical when `K=7`, but the dense layer would **not** share those weights across positions. For a 224×224 image, a single dense layer from flattened pixels to 1,000 units needs ~150M parameters; a `Conv2d(3, 64, 3)` first layer needs 1,792. The engineering choice is not subtle.

### 2.6 Multi-channel convolution and grouped conv

RGB images carry three input channels. Each of the `C_out` filters has shape `(C_in, K, K)` and produces one feature map; stacking `C_out` filters yields output shape `(B, C_out, H', W')`. When `C_in` and `C_out` are large, parameter count grows linearly in both — another reason depth is stacked gradually (3→32→64→128) rather than jumping to thousands of channels on the first layer. **Grouped convolution** splits channels into independent groups, each convolved separately; depthwise-separable conv (used in MobileNet) pushes grouping to the extreme where each input channel has its own filter before a 1×1 pointwise mix. The lesson for practitioners is unchanged: control parameter count by kernel size, channel width, and grouping — not by hoping a dense layer will generalize.

---

## Part 3: Pooling, Receptive Fields, and Depth

### 3.1 Max and average pooling

**Max pooling** partitions a feature map into non-overlapping windows (typically 2×2) and keeps the maximum activation in each window. It acts like a logical OR over local presence: if any position in the window detected an edge, the pooled output stays high. **Average pooling** keeps the mean, smoothing noise at the cost of weaker peak responses. Global average pooling — reducing each channel to a single value with `nn.AdaptiveAvgPool2d(1)` — replaces large flatten layers in modern classifiers and is the default head in many ResNet variants.

```text
Input (4×4):              MaxPool 2×2, stride 2:
[1  3  2  4]
[5  6  7  8]     →        [6   8]
[9  1  3  4]              [9   7]
[2  3  7  1]
```

```python
import torch.nn as nn

features = torch.randn(8, 64, 56, 56)   # (B, C, H, W) mid-network tensor
pooled = nn.MaxPool2d(kernel_size=2, stride=2)(features)
print(pooled.shape)  # torch.Size([8, 64, 28, 28]) — spatial halved, channels unchanged
```

### 3.2 Receptive field growth

A neuron's **receptive field** is the region of the input image that can influence its activation. Stacking 3×3 convolutions with stride 1 grows the field linearly in depth: with `L` layers of kernel size 3, the receptive field along one axis is approximately `1 + L × (3 − 1) = 1 + 2L`. Five such layers yield an 11×11 region; you need depth or downsampling to integrate whole-object context.

Pooling and strided convolutions jump the field faster by shrinking the feature map. That is the spatial analog of stacking depth in an MLP: early layers see pixels; late layers see object parts. When you debug a CNN that misses large-scale structure, trace the receptive field before blaming the optimizer.

A practical receptive-field exercise: for a VGG-style stack of three 3×3 conv layers followed by 2×2 max pool, repeated three times, the effective field on the input grows from 7×7 after the first block to roughly 44×44 pixels after three pool stages (exact values depend on padding and stride details). A pedestrian's head might span 30×30 pixels in a surveillance frame; if your field at the classifier is smaller, the network literally cannot integrate context from shoulders and torso. Receptive-field calculators exist online, but the habit of hand-estimating from kernel sizes and pool strides catches design errors in architecture reviews before anyone writes training code.

### 3.3 Stride versus pooling

Classic architectures alternate conv → ReLU → pool. Modern designs often **downsample with strided convolutions** instead, letting the network learn how to discard spatial resolution rather than enforcing a fixed max rule. Both approaches shrink `H` and `W`; the tradeoff is interpretability versus flexibility. If train and val losses look healthy but localization is poor, check whether you downsampling too aggressively before the classifier head.

```python
# Traditional: conv then pool
traditional = nn.Sequential(
    nn.Conv2d(64, 128, kernel_size=3, padding=1),  # (B,64,H,W)->(B,128,H,W)
    nn.ReLU(),
    nn.MaxPool2d(2),                               # (B,128,H,W)->(B,128,H/2,W/2)
)

# Modern: learnable downsampling in one conv
modern = nn.Sequential(
    nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),  # halves H and W
    nn.ReLU(),
)
```

---

## Part 4: Classic Architectures — Brief and Accurate

These architectures are historical landmarks, not a deployment checklist. Each introduced a design principle you still see in code reviews.

### 4.1 LeNet-5 (1998)

Yann LeCun's LeNet-5 processed 32×32 grayscale digits with alternating convolution and subsampling, then fully connected layers — the template for decades. AT&T deployed derivatives commercially in the 1990s for cheque digit recognition. The lesson is not the exact filter counts; it is the **pattern**: conv blocks extract local features, pooling adds robustness, dense layers classify.

```text
Input 32×32×1 → Conv 5×5 (6 filters) → Pool → Conv 5×5 (16) → Pool → FC → 10 classes
```

### 4.2 AlexNet (2012)

Alex Krizhevsky, Ilya Sutskever, and Geoffrey Hinton scaled LeNet's recipe to 224×224 RGB ImageNet with ReLU, dropout on fully connected layers, and GPU training. The ILSVRC 2012 top-5 error drop from roughly 26% to about 15% demonstrated that deep conv nets on large labelled datasets could beat hand-engineered pipelines. AlexNet's large 11×11 first convolution with stride 4 aggressively downsamples early — a design later architectures refined away, but the message endured: depth plus data wins. The paper also normalized inputs by subtracting the per-channel mean across the training set — an early instance of the preprocessing discipline you now encode with `transforms.Normalize`. Local response normalization appeared before BatchNorm became standard; reading AlexNet today is partly archaeology and partly a reminder that many "new" training tricks are old ideas scaled up.

### 4.3 VGG (2014)

Simonyan and Zisserman showed that stacking **3×3** convolutions — three ReLU nonlinearities between receptive-field expansions — matches the expressivity of larger kernels with fewer parameters and more nonlinearity. Two 3×3 layers have `2 × (3² × C²) = 18C²` weight multiplies per spatial position versus one 5×5 layer's `25C²`, while providing two ReLU gates instead of one. VGG-16's ~138 million parameters are dominated by its fully connected layers; that observation later motivated global average pooling and tighter heads.

### 4.4 ResNet (2015) — connecting to module 1.4.2

You already implemented residual blocks as `y = x + F(x)`. ResNet transplanted the same idea onto convolutional feature maps, solving the **degradation problem** He et al. documented: very deep plain CNNs on CIFAR-10 trained worse than shallower ones, not from overfitting but from optimization failure. Skip connections provide a gradient highway — the identity path carries gradients even when `F(x)` is hard to learn — enabling networks with 50, 100, or 152 layers. BatchNorm after each conv (module 1.3.4) keeps activations in a trainable range inside each residual branch. When you load `torchvision.models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V1)`, you are loading a stack of conv–BN–ReLU blocks wired with the same residual philosophy you coded by hand.

```python
import torchvision.models as models
from torchvision.models import ResNet50_Weights

# Current API — weights enum, not deprecated pretrained=True
backbone = models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V1)
```

### 4.5 BatchNorm in deep CNNs

Every block above assumes normalized activations. Without BatchNorm (or another normalizer), deep CNN training is brittle — the same internal covariate shift and loss-landscape conditioning issues you studied in module 1.3.4. In vision, `nn.BatchNorm2d` tracks running mean and variance per channel across the batch and spatial axes. Remember the train/eval split: training uses batch statistics; inference uses running buffers. Forgetting `model.eval()` is one of the most common silent bugs in vision deployment.

When you read a ResNet block diagram in papers or `torchvision` source, the pattern is Conv → BatchNorm → ReLU, optionally wrapped in `y = x + F(x)`. That is the same pre-activation versus post-activation debate you saw in module 1.4.2, transplanted to spatial tensors. The skip tensor and the residual branch must match in `(B, C, H, W)` before the add; when a stage doubles channels and halves resolution, the shortcut uses a 1×1 strided convolution to project `x` — the same projection shortcut pattern you coded as `ResidualBlockWithProjection` in the residual module, only implemented with `nn.Conv2d` instead of `nn.Linear`. Post-norm ResNet (Conv-BN-ReLU inside the residual branch, add, then maybe another ReLU) dominated the original ImageNet models. Pre-activation variants (BN-ReLU-Conv inside the branch) train somewhat more smoothly at extreme depth. Either way, BatchNorm is doing the loss-smoothing work Santurkar et al. measured — not merely keeping means at zero. When batch size drops below eight on a multi-GPU job, consider `nn.GroupNorm` as a drop-in replacement per module 1.3.4; the channel grouping preserves spatial structure without relying on batch composition.

### 4.6 Reading a classic architecture table

When you encounter a new backbone in a model zoo, read it as a repeated macro-pattern rather than memorizing layer lists. LeNet: conv → pool → conv → pool → FC. AlexNet: wide early conv, aggressive stride, dropout on FC. VGG: blocks of 3×3 convs separated by pool. ResNet: residual blocks with channel doubling at stage boundaries. The head is almost always global average pool → linear classifier in modern designs, replacing the enormous FC layers that made VGG parameter-heavy. If you can parse the macro-pattern, you can swap backbones in a training script by changing one `models.*` constructor and adjusting the classifier `in_features`.

---

## Part 5: Building a Small CNN from Scratch in PyTorch

The following `nn.Module` targets CIFAR-10-shaped inputs `(B, 3, 32, 32)`. It combines a stem conv, strided downsampling blocks, optional residual shortcuts (reusing the additive pattern from 1.4.2), global average pooling, and a linear classifier head. Weight initialization follows He normal for ReLU conv layers — the same scaling logic as module 1.3.1.

```python
import torch
import torch.nn as nn


class ConvBlock(nn.Module):
    """Conv → BatchNorm → ReLU; optional residual add when shapes match."""

    def __init__(
        self,
        in_ch: int,
        out_ch: int,
        kernel_size: int = 3,
        stride: int = 1,
        residual: bool = False,
    ):
        super().__init__()
        padding = kernel_size // 2
        self.conv = nn.Conv2d(in_ch, out_ch, kernel_size, stride=stride,
                              padding=padding, bias=False)
        self.bn = nn.BatchNorm2d(out_ch)
        self.relu = nn.ReLU(inplace=True)
        self.residual = residual
        self.shortcut = nn.Identity()
        if residual and (in_ch != out_ch or stride != 1):
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 1, stride=stride, bias=False),
                nn.BatchNorm2d(out_ch),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, in_ch, H, W)
        out = self.bn(self.conv(x))              # (B, out_ch, H', W') — no activation yet
        if self.residual:
            out = out + self.shortcut(x)         # additive merge BEFORE the activation
        out = self.relu(out)                     # post-activation (ResNet convention): relu(bn(conv(x)) + shortcut)
        return out


class CifarCNN(nn.Module):
    def __init__(self, num_classes: int = 10):
        super().__init__()
        self.stem = ConvBlock(3, 32)                    # (B,3,32,32)->(B,32,32,32)
        self.block1 = nn.Sequential(
            ConvBlock(32, 64, stride=2),                # -> (B,64,16,16)
            ConvBlock(64, 64, residual=True),
        )
        self.block2 = nn.Sequential(
            ConvBlock(64, 128, stride=2),               # -> (B,128,8,8)
            ConvBlock(128, 128, residual=True),
            ConvBlock(128, 128, residual=True),
        )
        self.block3 = nn.Sequential(
            ConvBlock(128, 256, stride=2),              # -> (B,256,4,4)
            ConvBlock(256, 256, residual=True),
        )
        self.pool = nn.AdaptiveAvgPool2d(1)             # -> (B,256,1,1)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(256, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.pool(x).flatten(1)                     # (B, 256)
        x = self.dropout(x)
        return self.fc(x)                               # (B, num_classes)


model = CifarCNN()
dummy = torch.randn(8, 3, 32, 32)
logits = model(dummy)
print(logits.shape)  # torch.Size([8, 10])
print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")
```

Training reuses the Block B machinery — `AdamW`, cross-entropy, train/val loops, and the diagnostics mindset from module 1.3.5 (plot losses, watch for overfitting when train accuracy diverges from val). Mixed precision via `torch.amp` reduces memory on CUDA:

```python
import torch
import torch.nn as nn
from torch.amp import autocast, GradScaler

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = CifarCNN().to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
criterion = nn.CrossEntropyLoss()
scaler = GradScaler("cuda") if device.type == "cuda" else None

def train_step(x, y):
    model.train()  # BatchNorm + Dropout use training behaviour
    x, y = x.to(device), y.to(device)
    optimizer.zero_grad(set_to_none=True)
    if scaler is not None:
        with autocast("cuda"):
            loss = criterion(model(x), y)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
    else:
        loss = criterion(model(x), y)
        loss.backward()
        optimizer.step()
    return loss.item()
```

Before trusting a loss curve, verify shapes once with a single batch, confirm normalization constants match your dataset (CIFAR-10 statistics differ from ImageNet), and log both train and validation accuracy per epoch. If val loss rises while train loss falls, reach for the regularization toolkit from module 1.3.3 before widening the network.

Apply the training-diagnostics playbook from module 1.3.5 deliberately. Plot train and validation loss on the same axes for the first twenty epochs. If training loss stalls near random-guess level for CIFAR-10 (log ≈ 2.3 for ten classes), suspect a bug — wrong label mapping, broken normalization, or a learning rate of zero because the optimizer has no trainable parameters. If training loss drops but validation loss flatlines, you are overfitting: increase augmentation, add dropout, or reduce model width. Log the norm of gradients at the first conv layer once per epoch; vanishing norms in early layers while the head trains suggest a frozen backbone you forgot to unfreeze, or a learning rate that is too small for early layers during fine-tuning.

Data augmentation for CIFAR-10 is lighter than ImageNet: random crops with padding, horizontal flips, and mild colour jitter are standard. For ImageNet transfer, `RandomResizedCrop(224)` and `RandomHorizontalFlip()` match the pretraining recipe. Augmentation is not cosmetic — it encodes the invariances you want the CNN to learn without seeing every translation at training time.

---

## Part 6: Transfer Learning, Done Right

Training a large CNN from scratch on ImageNet costs hundreds of GPU-hours. Transfer learning starts from weights pretrained on a public dataset and adapts them to your task. The pattern has two modes:

**Feature extraction (frozen backbone).** Set `requires_grad=False` on pretrained layers; train only a new classifier head. Use when labelled data is scarce (hundreds to a few thousand images) and your images are reasonably similar to natural photographs.

**Fine-tuning.** Unfreeze some or all backbone layers with a **smaller** learning rate than the head. Use when you have more labels, when domain shift is large (medical imaging, satellite, microscopy), or after the head has converged.

```python
import torch.nn as nn
import torchvision.models as models
from torchvision.models import ResNet18_Weights

def build_transfer_model(num_classes: int, freeze_backbone: bool = True) -> nn.Module:
    weights = ResNet18_Weights.IMAGENET1K_V1
    model = models.resnet18(weights=weights)

    if freeze_backbone:
        for param in model.parameters():
            param.requires_grad = False

    in_features = model.fc.in_features  # 512 for ResNet-18
    model.fc = nn.Sequential(
        nn.Dropout(0.5),
        nn.Linear(in_features, num_classes),
    )
    return model, weights


model, weights = build_transfer_model(num_classes=5, freeze_backbone=True)
preprocess = weights.transforms()  # official mean/std + resize for these weights

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
print(f"Trainable: {trainable:,} / {total:,}")
```

Preprocessing must match pretraining. ImageNet weights expect normalisation with mean `[0.485, 0.456, 0.406]` and std `[0.229, 0.224, 0.225]` after scaling pixels to `[0, 1]`. Using CIFAR statistics on an ImageNet backbone — or forgetting normalization entirely — produces confident-looking garbage. The `weights.transforms()` helper bundles the correct resize, crop, and normalize for the enum you loaded.

Discriminative learning rates are standard in fine-tuning: `lr=1e-3` for the new head, `lr=1e-4` or lower for unfrozen middle layers, `lr=1e-5` for early conv layers. A single high learning rate on the full network destroys pretrained filters in the first epoch.

A staged fine-tuning schedule works well in practice. **Stage 1:** freeze all backbone parameters, train the new head for five to ten epochs until validation accuracy plateaus. **Stage 2:** unfreeze the last residual stage (for ResNet, `layer4`), use a tenfold smaller learning rate on backbone weights than on the head, train another five epochs. **Stage 3:** optionally unfreeze the full network with an even smaller backbone rate if data volume supports it. Monitor validation loss after each unfreeze; if it spikes, reduce the backbone learning rate or return to stage 1 weights from a checkpoint. Feature extraction (stage 1 only) can reach strong accuracy on small natural-image datasets in minutes; full fine-tuning is for larger domain shifts — grayscale industrial X-rays, multispectral satellite bands, or microscopic cell imagery where ImageNet texture statistics mislead more than they help.

---

## Part 7: Memory, Performance, and Where CNNs Sit Today

### 7.1 Memory and throughput

Activation memory scales roughly with batch size × channels × height × width. Doubling spatial resolution quadruples feature-map memory at every layer that preserves resolution. When you hit CUDA OOM errors, reduce batch size first, then try mixed precision (module 1.3.6), then gradient accumulation to simulate larger batches without storing full activations for every sample simultaneously.

Throughput on GPU is usually highest when convolutions use channel counts aligned to tensor-core friendly multiples (often multiples of 8 or 16 on recent NVIDIA hardware) and when input tensors are contiguous in memory. Profiling with `torch.profiler` once per project reveals whether you are bound by compute, memory bandwidth, or data-loader stalls — the diagnostics playbook from module 1.3.5 applies to wall-clock time as well as loss curves. On CPU-only inference, depthwise-separable and quantized int8 models often beat full-precision ResNets; on GPU training, a slightly wider batch with AMP frequently beats a naive full-fp32 run that OOMs at batch size one.

### 7.2 CNNs versus Vision Transformers

Vision Transformers (ViTs) treat an image as a sequence of patch embeddings and apply self-attention (the mechanism you built in modules 1.4.3 and 1.4.4). ViTs excel when pretrained on very large datasets and often match or exceed CNNs at scale. CNNs retain advantages on **small data**, **tight latency budgets**, and **edge hardware** with mature int8 kernels. Hybrid models (ConvNeXt, CoAtNet) import ViT training recipes into convolutional stacks. Honest engineering: start with a ResNet or EfficientNet baseline, measure accuracy and latency, then justify a ViT if the problem rewards global context and you can afford pretraining. Neither architecture is universally dominant. Document the baseline in your experiment log before chasing state-of-the-art models — future reviewers will want evidence that extra complexity bought real accuracy or latency gains on your actual dataset, not just a heavier dependency tree and slower iteration cycles.

### 7.3 Forward pointer — deployment

Packaging a trained `torch.nn.Module` for inference — ONNX export, batching, GPU node pools — is a platform concern covered elsewhere in the curriculum. For Kubernetes-shaped deployment patterns (serving runtimes, autoscaling, health probes), see the platform-engineering material when you reach production ML ops. This teaching module stops at a correct PyTorch model and a runbook-quality training checklist.

### 7.4 When to reach for a ViT instead

Vision Transformers split an image into fixed-size patches (commonly 16×16), linearly embed each patch, add positional encodings, and stack transformer blocks — the same residual attention blocks you built in module 1.4.4, applied to a sequence of patch tokens. ViTs excel when pretrained on very large datasets (hundreds of millions of images) and often achieve superior accuracy on downstream tasks when you can afford the pretraining or use a public checkpoint. They are less parameter-efficient on tiny datasets unless heavily regularized, and they lack the built-in local inductive bias of convolutions, so they may need more data to learn edges and textures that CNNs get "for free." Hybrid models such as ConvNeXt modernize the CNN macro-design with transformer training recipes (larger batches, strong augmentation, LayerNorm instead of BatchNorm in some variants). The engineering workflow is: establish a ResNet-50 or EfficientNet baseline with transfer learning, measure accuracy/latency/memory, then experiment with a ViT only if the baseline is insufficient and you have the data or pretrained weights to support it.

---

## Did You Know?

- LeNet-5 and its descendants were deployed by NCR and other vendors in the late 1990s to read handwritten digits on bank cheques — one of the earliest large-scale commercial uses of convolutional neural networks, years before the ImageNet moment made deep learning fashionable in Silicon Valley.
- AlexNet's 2012 ImageNet top-5 error rate of about 15.3% was roughly ten percentage points better than the second-place entry that year — a gap so wide it convinced many researchers overnight that deep convolutional networks had become the default tool for large-scale visual recognition.
- The VGG team's 2014 systematic comparison showed that a stack of three 3×3 convolutional layers has the same receptive field as one 7×7 layer but with fewer parameters and three ReLU nonlinearities instead of one — a design rule still echoed in modern head architectures and depthwise-separable conv designs.
- Kaiming He's ResNet paper enabled training of networks with more than 100 layers on ImageNet by adding identity skip connections; the residual formulation underpins both modern vision backbones and the transformer blocks you assembled in Block C.

---

## Common Mistakes

| Mistake | Why it happens | Fix |
|---------|----------------|-----|
| Leaving `model.train()` on during inference | Default mode after construction; deployment scripts omit the toggle | Call `model.eval()` before inference; pair with `torch.no_grad()` |
| Wrong input layout `(H, W, C)` vs `(C, H, W)` | PIL and NumPy load channels last; PyTorch conv expects channels first | Use `permute(2, 0, 1)` or `ToTensor()` which converts to CHW |
| Missing ImageNet normalization | Assuming `[0,1]` pixels are sufficient for pretrained backbones | Apply `weights.transforms()` or manual `Normalize` with ImageNet mean/std |
| Off-by-one spatial sizes after conv | Padding/stride mis-specified without running the output formula | Compute `floor((H−K+2P)/S)+1` before building the classifier head |
| Flattening too early | Connecting a huge FC layer while spatial dimensions are still large | Use more pooling/striding or `AdaptiveAvgPool2d(1)` before the linear head |
| BatchNorm statistics mismatch | Small batch size at inference or BatchNorm in a recurrent deployment batch | Ensure `eval()` uses running stats; consider `GroupNorm` for tiny batches |
| Fine-tuning entire backbone with high LR on small data | Copying the head learning rate to all layers | Freeze backbone first; use discriminative LRs when unfreezing |
| Mismatched `weights` enum and transforms | Loading `IMAGENET1K_V2` but preprocessing for V1 | Always call `weights.transforms()` on the enum you actually loaded |

---

## Quiz

1. **A 224×224 RGB image is flattened and fed into `nn.Linear(150528, 1000)`. Roughly how many weight parameters does that linear layer require, and why is that problematic for a 50,000-image training set?**

<details>
<summary>Answer</summary>

About **150,528 × 1,000 ≈ 150.5 million** weights (plus 1,000 biases). With only 50,000 training examples, the model is severely underdetermined and will overfit unless heavily regularized — and it still wastes parameters relearning spatial relationships that convolution encodes by structure. A `Conv2d(3, 64, 3)` first layer needs on the order of **1,792** weights instead.

</details>

2. **Compute the output spatial size for `Conv2d(64, 128, kernel_size=3, stride=2, padding=1)` on input `(B, 64, 56, 56)`.**

<details>
<summary>Answer</summary>

`out = floor((56 − 3 + 2×1) / 2) + 1 = floor(55/2) + 1 = 27 + 1 = 28`. Full shape: **`(B, 128, 28, 28)`**.

</details>

3. **In backprop through a convolution layer, why is the kernel gradient a sum over spatial positions?**

<details>
<summary>Answer</summary>

The same kernel weights are reused at every spatial location (weight sharing). Each location contributes an independent partial derivative through the chain rule; PyTorch accumulates them into one gradient tensor for the shared kernel — the same accumulation pattern as reusing a weight on multiple paths in a hand-drawn computation graph from Block A.

</details>

4. **How does a ResNet skip connection `y = x + F(x)` relate to the residual blocks you built in module 1.4.2, and why does it help very deep CNNs train?**

<details>
<summary>Answer</summary>

It is the same additive residual pattern, applied on feature maps instead of flat vectors. The identity path `x` carries gradients directly to earlier layers even when `F(x)` is hard to optimize, mitigating degradation in very deep plain stacks and improving loss landscape conditioning — the same gradient-highway intuition you used for deep MLPs and will reuse in transformers.

</details>

5. **You have 800 labelled factory-defect images and want to use ResNet-18. Should you freeze the backbone on the first training phase?**

<details>
<summary>Answer</summary>

**Yes.** With under a few thousand images, freezing the ImageNet backbone and training only a new head prevents destroying pretrained filters and reduces overfitting. After the head converges, selectively unfreeze later blocks with a smaller learning rate if domain shift requires it.

</details>

6. **Train accuracy is 96% but validation accuracy is 62%. Name three engineering levers from Blocks B and C that address this gap before changing architecture family.**

<details>
<summary>Answer</summary>

(1) **Data augmentation** to increase effective training diversity; (2) **regularization** — higher dropout, weight decay (module 1.3.3); (3) **transfer learning** with a frozen backbone instead of training all parameters from scratch. Also verify **normalization** and run the **diagnostics playbook** (module 1.3.5) to confirm the gap is overfitting rather than a train/val preprocessing mismatch.

</details>

7. **Why might a segmentation model use dilated convolutions instead of max pooling between blocks?**

<details>
<summary>Answer</summary>

Max pooling shrinks spatial resolution, destroying fine detail needed for pixel labels. Dilated convolutions expand the receptive field without reducing `H` and `W`, preserving alignment between feature maps and the original image grid.

</details>

8. **Production inference returns different class probabilities for the same image depending on batch mates. What is the most likely PyTorch oversight?**

<details>
<summary>Answer</summary>

The model is still in **training mode**. `BatchNorm2d` uses batch statistics and `Dropout` injects noise. Call **`model.eval()`** and use **`torch.no_grad()`** so running BatchNorm buffers and deterministic forward pass are used.

</details>

---

## Hands-On Exercise

Train and compare a from-scratch `CifarCNN` against a transfer-learning head on CIFAR-10, applying the diagnostics checklist from module 1.3.5. Download the dataset via `torchvision.datasets.CIFAR10` with train/test normalization constants (mean `(0.4914, 0.4822, 0.4465)`, std `(0.2023, 0.1994, 0.2010)`). Implement the complete small `CifarCNN` classifier from Part 5 on CIFAR-10-shaped `(B, 3, 32, 32)` inputs for at least ten epochs while logging train and validation accuracy. Build a second model from `resnet18` ImageNet weights: replace `conv1` with `Conv2d(3, 64, kernel_size=3, stride=1, padding=1, bias=False)`, set `maxpool` to `nn.Identity()` for 32×32 inputs, freeze the pretrained backbone, and train the new `conv1` and `fc` (the only randomly-initialized layers — a frozen random `conv1` would never learn useful features) for five epochs. Plot or print the train/validation gap for both runs; if train accuracy far exceeds validation accuracy, list which regularization or augmentation change you would try first.

- [ ] Explain flattening versus dense layers and weight sharing, then implement the complete small CifarCNN classifier on CIFAR-10-shaped inputs and summarize LeNet, AlexNet, VGG, and ResNet design principles.
- [ ] Both models accept `(B, 3, 32, 32)` without shape errors and you call `model.eval()` before evaluating validation accuracy.
- [ ] You record at least one epoch where validation accuracy improves over the initial random baseline and write three sentences comparing parameter counts and training time between scratch and transfer setups.

Run this quick verification snippet before the full training loop to confirm data shapes and normalization:

```python
import torch
from torchvision import datasets, transforms

transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010)),
])
train_set = datasets.CIFAR10(root="./data", train=True, download=True, transform=transform)
images, labels = train_set[0]
assert images.shape == (3, 32, 32), images.shape
print("Data OK:", images.shape, labels)
```

---

## Key Takeaways

A convolutional layer is a weight-tied, locally connected linear operator — the same `nn.Linear` plus nonlinearity pattern from Block A, structured for images rather than reinvented from scratch. Output sizes follow `floor((H − K + 2P)/S) + 1`; run that arithmetic on paper before you debug shape errors in a deep stack, because the formula catches padding and stride mistakes faster than a stack trace. Pooling and strided convolutions grow receptive fields and downsample feature maps; choose max or average pooling when you want a fixed, interpretable reduction rule, and strided convolutions when you want the network to learn how to downsample.

The classic architecture line — LeNet to AlexNet to VGG to ResNet — is a story of scaling data, depth, small 3×3 filters, and skip connections. ResNet's additive skips are the same residual highway you derived in module 1.4.2, now applied to spatial feature maps inside BatchNorm-wrapped conv blocks from module 1.3.4. BatchNorm and the correct `model.train()` versus `model.eval()` toggle are non-negotiable for stable training and deployment; silent BatchNorm bugs degrade accuracy without crashing. Transfer learning means matching `weights.transforms()`, freezing the backbone when labelled data is scarce, and using discriminative learning rates when you unfreeze deeper layers. CNNs remain strong baselines on small data and tight latency budgets; Vision Transformers and hybrids win many large-scale benchmarks but do not obsolete convolutional networks overnight — start with a ResNet baseline, measure, then justify heavier architectures from evidence.

---

## Sources

- [Gradient-Based Learning Applied to Document Recognition (LeNet)](http://yann.lecun.com/exdb/publis/pdf/lecun-98.pdf) — Original LeNet-5 paper describing the conv–pool–FC blueprint.
- [ImageNet Classification with Deep Convolutional Neural Networks (AlexNet)](https://papers.nips.cc/paper/4824-imagenet-classification-with-deep-convolutional-neural-networks) — 2012 ImageNet breakthrough and architectural details.
- [Very Deep Convolutional Networks for Large-Scale Image Recognition (VGG)](https://arxiv.org/abs/1409.1556) — Systematic 3×3 filter stacking and depth tradeoffs.
- [Deep Residual Learning for Image Recognition (ResNet)](https://arxiv.org/abs/1512.03385) — Skip connections and degradation-problem analysis.
- [Batch Normalization: Accelerating Deep Network Training](https://arxiv.org/abs/1502.03167) — Normalization layer referenced throughout modern CNN blocks.
- [PyTorch `nn.Conv2d` documentation](https://pytorch.org/docs/stable/generated/torch.nn.Conv2d.html) — Official API for convolution layers.
- [PyTorch Vision models](https://pytorch.org/vision/stable/models.html) — Pretrained backbones and `Weights` enums.
- [CS231n: Convolutional Neural Networks](https://cs231n.github.io/convolutional-networks/) — Stanford notes on conv, pooling, and receptive fields.
- [Dive into Deep Learning — Convolutional Neural Networks](https://d2l.ai/chapter_convolutional-modern/index.html) — Modern pedagogical reference with implementations.
- [PyTorch Automatic Mixed Precision](https://pytorch.org/docs/stable/amp.html) — `torch.amp.autocast` and `GradScaler` for memory-efficient training.
- [An Image is Worth 16x16 Words (ViT)](https://arxiv.org/abs/2010.11929) — Vision Transformer baseline for honest CNN comparisons.

---

## Learner check

> A convolutional layer is a structured, weight-tied dense layer; its backward pass accumulates the shared filter's gradient over every spatial position it visited during the forward pass.

---

## Next Module

Spatial structure — local patches, weight sharing across positions, pooling for translation robustness — is one axis of inductive bias. The next axis is **temporal and sequential structure**: applying the same cell at every timestep with shared recurrent weights, unrolling the graph through time, and fighting vanishing gradients with gated highways. Continue to **[Module 1.6: Recurrent Networks & Sequence Models](../module-1.6-rnns-sequence-models/)** to connect the convolution gradient-accumulation pattern you mastered here to backpropagation through time over sequences.
