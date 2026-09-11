---
title: "Recurrent Networks & Sequence Models"
slug: ai-ml-engineering/deep-learning/module-1.6-rnns-sequence-models
sidebar:
  order: 1007
---

> **AI/ML Engineering Track** | Complexity: `[COMPLEX]` | Time: 4-5 hours
>
> **Prerequisites**: Forward propagation in MLPs (1.1.3), backprop by hand for dense nets (1.1.6), scalar autograd (1.1.8), the PyTorch bridge (1.2), initialization and signal propagation (1.3.1), training diagnostics (1.3.5), numerical stability and precision (1.3.6), residual architectures (1.4.2), attention from scratch (1.4.3), and the transformer block from scratch (1.4.4).
>
> **Primary tools**: PyTorch 2.12, `nn.RNN`, `nn.LSTM`, `nn.GRU`, `nn.utils.rnn.pack_padded_sequence`, `nn.utils.clip_grad_norm_`, `DataLoader`, and `torch.optim.AdamW`.

On September 10, 2014, Ilya Sutskever, Oriol Vinyals, and Quoc V. Le submitted "Sequence to Sequence Learning with Neural Networks" to arXiv. Their model used an encoder LSTM to read an input sentence into a state and a decoder LSTM to write the output sentence one token at a time. That paper belongs to a short but important era when recurrent networks were the default serious answer to variable-length sequence problems: translation, speech, handwriting, clickstreams, sensor readings, and character-level language models all used the same basic idea of a learned state moving through time.

That history matters because RNNs are easy to misfile in your head as "the thing before transformers." The better framing is sharper and more useful: an RNN is the same MLP cell you already built in Block A, applied repeatedly across timesteps with shared weights. The hidden state is a running summary, and backpropagation through time is the same chain rule from module 1.1.6 applied to the unrolled graph. Once you see that, LSTM gates, GRU gates, teacher forcing, and packed variable-length batches stop looking like separate tricks and start looking like engineering answers to one problem: how do we train a weight-shared network whose effective depth is the sequence length?

## Learning Outcomes

- **Implement** a vanilla recurrent cell from explicit tensor operations, including shape checks for `(B, T, input_size)`, `(B, hidden_size)`, and `(B, T, hidden_size)`.
- **Derive** the backprop-through-time dependency that repeatedly multiplies by recurrent Jacobians, then **diagnose** why this produces vanishing or exploding gradients.
- **Debug** practical RNN training failures using gradient clipping, truncated BPTT, hidden-state detachment, padding masks, packed sequences, and batch/sequence dimension discipline.
- **Compare** vanilla RNNs, LSTMs, and GRUs in terms of gates, parameter count, gradient flow, memory behavior, and common use cases.
- **Design** an encoder-decoder sequence model with teacher forcing, then **evaluate** recurrent models against attention-based transformer blocks under realistic latency, memory, and sequence-length constraints.

## Why This Module Matters

Sequences are not just tables with an extra dimension. In a tabular MLP, swapping two rows in a batch should not change the prediction for either row. In a sequence model, swapping two timesteps can completely change the meaning. The log line "database restarted after timeout" does not mean the same thing as "timeout after database restarted." A heart-rate trace, shell command history, weather record, or token stream carries information in order, and a model that ignores order throws away one of the strongest priors the data gives you.

You already have almost all the machinery needed for recurrence. From Block A, you know how an MLP cell computes affine transforms, nonlinearities, cached activations, and gradients. From Block B, you know why signal scale changes with depth and why exploding gradients become a training incident rather than a philosophical problem. From Block C, you know residual additions as gradient highways and attention as a way to let positions communicate directly. This module connects those pieces: recurrence is weight sharing across time, BPTT is backprop on the unrolled graph, and gates are architectural paths that make long time-depth trainable.

The useful analogy is a shift handoff. Imagine a site reliability team where every engineer writes one short summary before handing the pager to the next engineer. Each new engineer reads the current incident event and the previous summary, then writes an updated summary for the next person. The team does not create a new policy manual every hour; it reuses the same handoff template. A vanilla RNN cell is that template. The event is `x_t`, the old summary is `h_{t-1}`, the new summary is `h_t`, and the same weights are reused at every timestep.

The analogy also exposes the failure mode. If every handoff compresses too aggressively, the first signal disappears long before the tenth shift. If every handoff exaggerates uncertainty, the summary becomes unstable and useless. Vanishing and exploding gradients are the mathematical version of those bad handoffs. In a vanilla RNN, information and gradients both travel through repeated applications of the recurrent transform. LSTMs and GRUs do not make long memory automatic, but they give the model controlled gates and additive paths that are easier to train than repeatedly squeezing everything through one tanh state update.

This is also the right moment to place RNNs in the modern architecture map. Transformers displaced RNNs for many long-range text tasks because attention computes interactions across positions in parallel and gives any two positions a short path through the graph. That does not mean recurrence is obsolete. A recurrent state is still a strong fit when data arrives one step at a time, memory must stay bounded, latency matters, or the sequence is small enough that a transformer would be more machinery than the problem needs.

## Part 1: Why Sequences Need a Different Prior

A dense network treats each example as a fixed-width vector. If the input is an image flattened to 784 numbers or a feature vector with 40 columns, the first weight in the first `nn.Linear` layer always connects to the first input feature. That assumption works when feature positions are fixed and every example has the same shape. It becomes awkward for sequences because the length can vary, positions are ordered, and the same pattern can appear at many positions. A phrase can occur near the beginning or end of a sentence; a CPU spike can appear early or late in a trace; a melody motif can repeat with a different offset.

The recurrent prior says that the same update rule should be applied at each position. Instead of learning separate weights for timestep 1, timestep 2, and timestep 3, the model learns one cell and reuses it across time. That is the same weight-sharing idea as convolution, except the sharing axis is temporal rather than spatial. In D1, a convolution filter accumulates gradient from every image patch where it was applied. In an RNN, the recurrent cell's weights accumulate gradient from every timestep where the same cell was applied.

The vanilla recurrence is compact:

```text
h_t = f(W_xh x_t + W_hh h_{t-1} + b_h)
y_t = g(W_hy h_t + b_y)
```

Read this with the Block A lens. `W_xh x_t` is an affine transform of the current input. `W_hh h_{t-1}` is an affine transform of the previous hidden summary. The bias shifts the preactivation, and `f` is usually `tanh` or ReLU in a vanilla RNN. The output head `g(W_hy h_t + b_y)` can be a linear projection for regression, logits for classification, or token logits for language modeling. Nothing in that formula requires new calculus; the only novelty is that one cell instance is reused over a chain of timesteps.

The hidden state is the model's running memory. At time `t`, `h_t` is not a storage container with human-readable fields. It is a learned vector whose coordinates are useful only because the training objective made them useful. In a sentiment model, some dimensions may become sensitive to negation or intensity. In a sensor model, some dimensions may track recent trend. In a character model, a dimension may activate inside quoted strings or after opening braces. The learner-visible rule is simpler than the learned semantics: each update sees the current input and the previous state, then produces the next state.

Unrolling makes the graph visible. A recurrent definition looks cyclic because `h_t` depends on `h_{t-1}`, but a finite sequence has a finite directed computation graph:

```text
x_1 ---> [cell] ---> h_1 ---> [head] ---> y_1
          ^
          |
h_0 ------+

x_2 ---> [same cell weights] ---> h_2 ---> [head] ---> y_2
          ^                         ^
          |                         |
          +-------------------------+

x_3 ---> [same cell weights] ---> h_3 ---> [head] ---> y_3
          ^                         ^
          |                         |
          +-------------------------+
```

The diagram is deliberately repetitive. The cell box at each timestep is not a different module with different parameters. It is the same parameter set reused over and over. During the forward pass, you cache the activations for each timestep because the backward pass needs them. During the backward pass, each timestep contributes a partial gradient to `W_xh`, `W_hh`, and `b_h`, and those partials are summed. That is exactly how shared parameters behave in autograd: one parameter tensor can be used multiple times in the forward graph, and its `.grad` accumulates every path's contribution.

Variable length is the other reason sequences need a different prior. You can batch fixed-length windows by padding shorter examples, but the model should not learn from the pad tokens as though they were real observations. That is why later sections use masks and packed sequences. Padding is a storage trick for the batch; it is not part of the underlying sequence. The architecture should preserve the distinction between "there was an event at time 4" and "the batch needed a placeholder at column 4."

The prior is not limited to text. A login session, network flow, build log, stock tick, and patient monitor all have a current observation whose meaning depends on previous observations. A feed-forward baseline can still work if you hand it engineered lag features or summarize the window yourself, and that is often a useful baseline. The recurrent model moves that summary-learning burden into the network. It learns a state update that can decide whether the new event is routine noise, a boundary marker, or evidence that should change the running summary.

That design choice also defines the model's information bottleneck. At each timestep, the RNN compresses everything it wants to remember into `hidden_size` numbers. If `hidden_size` is too small, the state cannot carry all task-relevant information. If it is too large, the model may overfit or become slower than necessary. This is why sequence-model design still follows the engineering playbook from Block B: build a simple baseline, overfit a small batch, inspect train and validation behavior, and change capacity because a diagnostic points there, not because a larger hidden state sounds more impressive.

## Part 2: A Vanilla RNN From Scratch in PyTorch

The fastest way to demystify `nn.RNN` is to write the cell yourself. The implementation below uses explicit parameters, a Python loop over timesteps, and shape checks that mirror the recurrence formula. It is not the production implementation you would use for speed, but it is the right implementation for understanding. Every line maps back to `h_t = tanh(W_xh x_t + W_hh h_{t-1} + b_h)`.

```python
import torch
import torch.nn as nn


class TinyVanillaRNN(nn.Module):
    """A teaching RNN with explicit tensor math and batch-first input."""

    def __init__(self, input_size: int, hidden_size: int, output_size: int):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size

        # W_xh: (input_size, hidden_size), W_hh: (hidden_size, hidden_size)
        self.W_xh = nn.Parameter(torch.randn(input_size, hidden_size) * 0.1)
        self.W_hh = nn.Parameter(torch.randn(hidden_size, hidden_size) * 0.1)
        self.b_h = nn.Parameter(torch.zeros(hidden_size))

        # Output head maps each hidden state to logits or regression outputs.
        self.W_hy = nn.Parameter(torch.randn(hidden_size, output_size) * 0.1)
        self.b_y = nn.Parameter(torch.zeros(output_size))

    def forward(self, x: torch.Tensor, h0: torch.Tensor | None = None):
        # x: (B, T, input_size)
        B, T, input_size = x.shape
        if input_size != self.input_size:
            raise ValueError(f"expected input_size={self.input_size}, got {input_size}")

        if h0 is None:
            # h: (B, hidden_size), one hidden summary per batch element.
            h = x.new_zeros(B, self.hidden_size)
        else:
            # h0: (B, hidden_size)
            h = h0

        states = []
        for t in range(T):
            # x_t: (B, input_size)
            x_t = x[:, t, :]

            # x_t @ W_xh: (B, input_size) @ (input_size, hidden_size) -> (B, hidden_size)
            # h @ W_hh:   (B, hidden_size) @ (hidden_size, hidden_size) -> (B, hidden_size)
            h = torch.tanh(x_t @ self.W_xh + h @ self.W_hh + self.b_h)

            # Save h_t so the caller can use all timesteps, not only the final one.
            states.append(h)

        # hidden_seq: (B, T, hidden_size)
        hidden_seq = torch.stack(states, dim=1)

        # logits: (B, T, output_size)
        logits = hidden_seq @ self.W_hy + self.b_y
        return logits, h, hidden_seq


torch.manual_seed(7)
B, T, input_size, hidden_size, output_size = 2, 4, 3, 5, 2
x = torch.randn(B, T, input_size)

model = TinyVanillaRNN(input_size, hidden_size, output_size)
logits, final_h, hidden_seq = model(x)

print(logits.shape)      # torch.Size([2, 4, 2])
print(final_h.shape)     # torch.Size([2, 5])
print(hidden_seq.shape)  # torch.Size([2, 4, 5])
```

The important detail is not that this code uses `@` instead of `nn.Linear`. The important detail is that `self.W_hh` is read once per timestep and receives gradient contributions from every use. If you call `loss.backward()` on a loss built from all logits, PyTorch follows the unrolled computation graph and adds all the partial gradients into `self.W_hh.grad`. You do not manually sum those contributions in PyTorch, but the math is the same sum you would write by hand.

A tiny numeric forward pass makes the recurrence concrete. Suppose the hidden size is one, the activation is tanh, `W_xh = 0.5`, `W_hh = 0.8`, `b_h = 0`, and the input sequence is `[1.0, 0.0, 1.0]` with `h_0 = 0`. Then `h_1 = tanh(0.5)`, which is about `0.462`. The second step has no input signal, but the old hidden state still matters: `h_2 = tanh(0.8 * 0.462)`, about `0.354`. The third step combines the new input and the remembered state: `h_3 = tanh(0.5 + 0.8 * 0.354)`, about `0.654`. The input at time 1 affects time 3 only because the hidden state carried it forward.

PyTorch's production `nn.RNN` wraps this idea in optimized kernels and a stable API. The default tensor convention for recurrent modules is sequence-first, but this curriculum consistently uses batch-first examples because they align with `DataLoader` batches and the transformer modules you just built. Set `batch_first=True` unless you have a specific reason to use `(T, B, input_size)`.

```python
import torch
import torch.nn as nn

torch.manual_seed(11)

B, T, input_size, hidden_size = 3, 6, 4, 8
x = torch.randn(B, T, input_size)  # (B, T, input_size)

rnn = nn.RNN(
    input_size=input_size,
    hidden_size=hidden_size,
    num_layers=1,
    nonlinearity="tanh",
    batch_first=True,
)

# output: (B, T, hidden_size), h_n: (num_layers, B, hidden_size)
output, h_n = rnn(x)

print(output.shape)  # torch.Size([3, 6, 8])
print(h_n.shape)     # torch.Size([1, 3, 8])
print(torch.allclose(output[:, -1, :], h_n[-1]))  # True for one-layer, unidirectional RNN
```

That final equality is a useful shape check, not a universal rule to cargo-cult. For a one-layer, unidirectional RNN with no packing complications, the last output along the time axis equals the final hidden state for the last layer. If you add multiple layers, bidirectionality, or packed variable-length inputs, the indexing story changes. In real code, prefer to reason from documented shapes and from the task you are solving: sequence labeling usually needs all `output` states, while sequence classification often uses the final valid state.

Parameter counts also expose the "cell reused over time" idea. A vanilla RNN layer has `input_size * hidden_size` input-to-hidden weights, `hidden_size * hidden_size` hidden-to-hidden weights, and two bias vectors (`bias_ih` and `bias_hh`) in PyTorch's built-in `nn.RNN` module — the from-scratch cell above folds these into one combined `b_h`, which is mathematically equivalent. The count does not multiply by `T`. A sequence with 10 timesteps and a sequence with 100 timesteps use the same learned parameters; the longer sequence simply applies them more times and creates a deeper unrolled computation graph.

This is why recurrent models can generalize across lengths better than a dense model that expects a fixed flattened window. The same cell can process a four-step sequence and a forty-step sequence because the parameters describe a transition rule, not a fixed input slot. That does not guarantee good extrapolation to lengths far beyond training, because the hidden dynamics may drift or saturate. It does mean the architecture expresses the right invariance: "the same kind of update should be useful wherever this event appears in time."

The output choice should match the task, and many bugs come from choosing it by habit. For sequence classification, you often use the final valid hidden state because the whole sequence maps to one label. For sequence labeling, you use every hidden state because each timestep receives a label. For next-token modeling, you project every hidden state to vocabulary logits and shift targets by one position. Those are different heads on the same recurrent backbone, and the loss shape should make the distinction obvious before training starts.

## Part 3: BPTT and the Gradient Problem

Backpropagation through time sounds like a special algorithm, but the name mostly reminds you which graph is being differentiated. During the forward pass, the recurrent computation is unrolled for the actual sequence length. During the backward pass, ordinary reverse-mode autodiff walks backward through that unrolled graph. The recurrent weights are shared, so every timestep that used `W_hh` adds to the same gradient tensor. The temporal sum is the RNN version of the convolutional filter's spatial gradient accumulation.

For a vanilla RNN, each hidden state depends on the previous hidden state:

```text
a_t = W_xh x_t + W_hh h_{t-1} + b_h
h_t = tanh(a_t)
```

The local Jacobian from `h_t` back to `h_{t-1}` contains the recurrent matrix and the derivative of tanh. Ignoring batch notation, one useful way to read it is:

```text
d h_t / d h_{t-1} = diag(1 - tanh(a_t)^2) W_hh
```

If a loss at time `T` needs to send gradient back to time `k`, the backward path multiplies a chain of those Jacobians:

```text
d L_T / d h_k = d L_T / d h_T
                * (d h_T / d h_{T-1})
                * (d h_{T-1} / d h_{T-2})
                * ...
                * (d h_{k+1} / d h_k)
```

This is the same signal-propagation issue from module 1.3.1, but sequence length turns it into depth-in-time. If the repeated products tend to shrink vectors, early timesteps receive tiny gradients and the model struggles to learn long dependencies. If the repeated products tend to expand vectors, gradients can explode, the loss can spike, and parameters can jump into a bad numerical region. Tanh saturation makes the shrinking case even more common because `1 - tanh(a_t)^2` is near zero when `a_t` is large in magnitude.

The spectral-radius intuition is a compact mental model. If a recurrent transform behaves roughly like multiplying by a matrix whose dominant eigenvalue magnitude is less than 1, repeated multiplication tends to shrink components aligned with that direction. If it is greater than 1, repeated multiplication tends to expand them. Real RNNs include nonlinear derivatives, input-dependent gates, and changing activations, so the exact behavior is more complicated than one eigenvalue. The intuition is still useful because it tells you why long sequences are not merely "more data"; they are deeper computational graphs with repeated transforms.

Exploding gradients are the easier failure to patch mechanically. Gradient clipping rescales a too-large gradient norm before the optimizer step. It does not fix the underlying architecture's memory problem, but it prevents one bad batch from creating a parameter update so large that training becomes unrecoverable. The PyTorch utility modifies gradients in place after `loss.backward()` and before `optimizer.step()`.

```python
import torch
import torch.nn as nn

torch.manual_seed(13)

B, T, input_size, hidden_size, num_classes = 4, 12, 6, 16, 5
x = torch.randn(B, T, input_size)              # (B, T, input_size)
target = torch.randint(0, num_classes, (B, T)) # (B, T), class per timestep

model = nn.RNN(input_size, hidden_size, batch_first=True)
head = nn.Linear(hidden_size, num_classes)
optimizer = torch.optim.AdamW(list(model.parameters()) + list(head.parameters()), lr=1e-3)
loss_fn = nn.CrossEntropyLoss()

optimizer.zero_grad(set_to_none=True)

# output: (B, T, hidden_size)
output, _ = model(x)

# logits: (B, T, num_classes)
logits = head(output)

# CrossEntropyLoss expects (N, num_classes) logits, so flatten batch and time into N.
loss = loss_fn(logits.reshape(B * T, num_classes), target.reshape(B * T))
loss.backward()

# Clip all trainable gradients to a global norm of at most 1.0.
total_norm = nn.utils.clip_grad_norm_(
    list(model.parameters()) + list(head.parameters()),
    max_norm=1.0,
)

optimizer.step()
print(float(loss), float(total_norm))
```

Vanishing gradients are harder because clipping cannot amplify useful signal that disappeared before it reached early timesteps. Initialization can help, especially orthogonal recurrent initialization for tanh RNNs, and normalization can help in some architectures, but the classic fix is architectural: use gates and additive state paths so the model can decide what to preserve. That is where LSTMs and GRUs enter.

Long sequences also create memory and compute pressure because the backward pass needs the unrolled graph. Truncated BPTT cuts a long stream into chunks, backpropagates through each chunk, and detaches the hidden state between chunks. The forward hidden value still carries information into the next chunk, but the gradient graph does not grow without bound. This is a deliberate tradeoff: you keep streaming state while limiting the maximum temporal depth through which gradients flow.

```python
import torch
import torch.nn as nn

torch.manual_seed(17)

B, total_T, chunk_T, input_size, hidden_size = 2, 30, 10, 3, 7
stream = torch.randn(B, total_T, input_size)  # (B, total_T, input_size)
target = torch.randn(B, total_T, hidden_size) # (B, total_T, hidden_size)

rnn = nn.RNN(input_size, hidden_size, batch_first=True)
optimizer = torch.optim.AdamW(rnn.parameters(), lr=1e-3)
loss_fn = nn.MSELoss()

h = None
for start in range(0, total_T, chunk_T):
    x_chunk = stream[:, start : start + chunk_T, :]   # (B, chunk_T, input_size)
    y_chunk = target[:, start : start + chunk_T, :]   # (B, chunk_T, hidden_size)

    optimizer.zero_grad(set_to_none=True)
    output, h = rnn(x_chunk, h)                       # output: (B, chunk_T, hidden_size)
    loss = loss_fn(output, y_chunk)
    loss.backward()
    nn.utils.clip_grad_norm_(rnn.parameters(), max_norm=1.0)
    optimizer.step()

    # Keep the numeric hidden state, but cut the old computation graph.
    h = h.detach()

print(h.shape)  # torch.Size([1, 2, 7])
```

The `detach()` line is not optional bookkeeping. Without it, the second chunk's graph points back into the first chunk, the third points back into the first two, and so on. Memory grows with the stream, and a later backward pass may try to traverse old graph segments that were already freed. Detachment says, "use this hidden value as the initial state for the next chunk, but treat it as a constant boundary for gradient purposes."

Truncation is a modeling choice as well as a memory choice. If you train with chunks of length 32, the optimizer receives direct gradient credit assignment across at most 32 recurrent transitions. The hidden state can still carry information farther forward numerically, but the loss in a later chunk will not directly adjust the earlier chunk's computations through the graph. That can be exactly right for streaming systems where very old context should influence state but not create unbounded training graphs. It can be wrong when the task truly requires precise credit assignment over hundreds of steps, in which case you need a different truncation window, a gated architecture, attention, or a task reformulation.

The diagnostic habit is to separate exploding, vanishing, and data-interface failures. Exploding often looks like a sudden loss spike, non-finite gradients, or parameters that become `nan`; clipping and learning-rate reduction are immediate checks. Vanishing often looks like a model that learns local cues but ignores early sequence information; a synthetic memory task, gradient-norm logging by layer, and an LSTM or GRU ablation are useful probes. Data-interface bugs look more mundane: shifted labels, pad tokens in the loss, sorted lengths mismatched from examples, or final-state indexing that reads the last padded position instead of the last real timestep.

## Part 4: LSTM

The Long Short-Term Memory architecture was introduced by Sepp Hochreiter and Jürgen Schmidhuber in 1997 to address the difficulty of learning long-term dependencies with gradient descent. The key change is that an LSTM separates the hidden state `h_t`, which is exposed to the output and next computations, from the cell state `c_t`, which acts as a longer-lived memory highway. Instead of replacing memory with a single tanh update, the LSTM uses gates to decide what to forget, what to write, and what to expose.

One common LSTM formulation is:

```text
f_t = sigmoid(W_xf x_t + W_hf h_{t-1} + b_f)      # forget gate
i_t = sigmoid(W_xi x_t + W_hi h_{t-1} + b_i)      # input gate
g_t = tanh(   W_xg x_t + W_hg h_{t-1} + b_g)      # candidate content
o_t = sigmoid(W_xo x_t + W_ho h_{t-1} + b_o)      # output gate

c_t = f_t * c_{t-1} + i_t * g_t
h_t = o_t * tanh(c_t)
```

The cell-state update is the part to stare at: `c_t = f_t * c_{t-1} + i_t * g_t`. The previous memory travels through a multiplication by the forget gate and then an addition. That additive path is why LSTMs are often explained as giving gradients a better highway through time. The intuition is related to the residual `+` from module 1.4.2. A pure replacement path forces all information through a fresh nonlinear transform; an additive path allows useful state to be carried forward with controlled modification.

The gates are not human-written if statements. They are sigmoid outputs in `(0, 1)` learned by backpropagation. A forget gate value near 1 preserves a cell coordinate; a value near 0 erases it. An input gate value near 1 allows candidate content to write into the cell; a value near 0 blocks that write. The output gate controls how much of the cell is exposed as the hidden state. Because every gate is differentiable, the same BPTT machinery trains the whole cell.

PyTorch's `nn.LSTM` returns two state tensors because LSTMs carry both `h_n` and `c_n`. With `batch_first=True`, the input and output sequence use `(B, T, input_size)` and `(B, T, hidden_size)`, but the final states still use `(num_layers * num_directions, B, hidden_size)`. That exception is a common source of bugs: `batch_first` changes input and output layout, not the hidden-state layout.

```python
import torch
import torch.nn as nn

torch.manual_seed(19)

B, T, input_size, hidden_size = 3, 5, 4, 9
x = torch.randn(B, T, input_size)  # (B, T, input_size)

lstm = nn.LSTM(
    input_size=input_size,
    hidden_size=hidden_size,
    num_layers=2,
    batch_first=True,
    dropout=0.1,
)

# output: (B, T, hidden_size)
# h_n: (num_layers, B, hidden_size)
# c_n: (num_layers, B, hidden_size)
output, (h_n, c_n) = lstm(x)

print(output.shape)  # torch.Size([3, 5, 9])
print(h_n.shape)     # torch.Size([2, 3, 9])
print(c_n.shape)     # torch.Size([2, 3, 9])
print(torch.allclose(output[:, -1, :], h_n[-1]))  # True for last layer, unidirectional, un-packed
```

The `dropout` argument in `nn.LSTM` applies between recurrent layers when `num_layers > 1`; it is not applied on the outputs of a single-layer LSTM by that argument. This detail is worth remembering because a model can appear to have dropout configured while actually using `num_layers=1`, which means the recurrent module's own dropout setting has no effect. You can still apply explicit `nn.Dropout` before or after the LSTM if the task needs it.

Parameter count explains the cost. A vanilla RNN has one set of input and recurrent transforms. An LSTM has four gate/candidate sets: forget, input, candidate, and output. Ignoring PyTorch's separate bias vectors for a moment, that is roughly four times the recurrent cell parameters. The extra cost buys a richer state update and usually better long-dependency behavior, but it is not free. On tiny edge devices or very small datasets, the lighter model may be easier to fit and deploy.

LSTMs mitigate vanishing gradients; they do not repeal numerical reality. Forget gates can still learn values below 1 and gradually decay memory. Saturated sigmoids can still produce small derivatives. Long sequences can still demand clipping, careful initialization, and diagnostics. The correct engineering claim is modest and useful: LSTMs make it easier for the model to learn controlled memory paths than a vanilla tanh RNN, especially when dependencies span many timesteps.

## Part 5: GRU

The Gated Recurrent Unit was introduced by Kyunghyun Cho and collaborators in 2014 as part of an RNN encoder-decoder model for statistical machine translation. A GRU keeps the core idea of gates but merges the LSTM's separate cell and hidden state into one state vector. It usually has fewer parameters than an LSTM with the same input and hidden sizes, and in many practical sequence tasks it performs competitively enough that the choice is empirical rather than doctrinal.

A common GRU formulation is:

```text
z_t = sigmoid(W_xz x_t + W_hz h_{t-1} + b_z)      # update gate
r_t = sigmoid(W_xr x_t + W_hr h_{t-1} + b_r)      # reset gate
n_t = tanh(W_xn x_t + W_hn (r_t * h_{t-1}) + b_n) # candidate state

h_t = (1 - z_t) * n_t + z_t * h_{t-1}
```

The update gate decides how much previous state to keep versus how much candidate state to use. When `z_t` is near 1, the old hidden coordinate is copied forward. When `z_t` is near 0, the candidate replaces it. The reset gate decides how much previous state contributes to the candidate. If `r_t` is near 0, the candidate can ignore past state and respond mainly to the current input. This gives the model a learned way to reset memory around boundaries such as sentence starts, session breaks, or regime changes in a signal.

The additive interpolation in `h_t = (1 - z_t) * n_t + z_t * h_{t-1}` is the GRU's memory highway. It is not identical to the LSTM cell state, but it has the same training intuition: the model can preserve a coordinate by learning a gate value that copies it forward. The hidden state is both memory and exposed representation, so the interface is simpler than LSTM's `(h, c)` pair.

```python
import torch
import torch.nn as nn

torch.manual_seed(23)

B, T, input_size, hidden_size = 4, 7, 6, 10
x = torch.randn(B, T, input_size)  # (B, T, input_size)

gru = nn.GRU(
    input_size=input_size,
    hidden_size=hidden_size,
    num_layers=1,
    batch_first=True,
)

# output: (B, T, hidden_size), h_n: (num_layers, B, hidden_size)
output, h_n = gru(x)

print(output.shape)  # torch.Size([4, 7, 10])
print(h_n.shape)     # torch.Size([1, 4, 10])
print(torch.allclose(output[:, -1, :], h_n[-1]))  # True for one-layer, unidirectional, un-packed
```

A rough parameter comparison makes the tradeoff concrete. For one layer with input size `I` and hidden size `H`, a vanilla RNN has about `I*H + H*H` weights, a GRU has about `3*(I*H + H*H)` weights, and an LSTM has about `4*(I*H + H*H)` weights, before counting biases. PyTorch stores biases as two vectors per gate because of the underlying input-hidden and hidden-hidden terms, so exact counts differ slightly from the simplified expression. The simplification is still enough for architecture choice: GRU is gated but lighter than LSTM.

When should you prefer each? Use a vanilla RNN mainly as a teaching baseline or for very short, simple sequences where you want the smallest cell and can verify that long memory is irrelevant. Use a GRU when you want gated memory with a smaller parameter and state interface. Use an LSTM when long memory is central, the extra state is acceptable, and you want the historically robust default for recurrent sequence modeling. Then validate the choice with ablations rather than assuming the acronym wins.

## Part 6: Sequence-to-Sequence and Teacher Forcing

Many sequence tasks do not map a sequence to one label. Translation maps a source sentence of one length to a target sentence of another length. Speech recognition maps acoustic frames to tokens. A log summarizer maps an incident trace to a shorter report. The encoder-decoder pattern handles this by using one recurrent network to read the input and another recurrent network to generate the output. The encoder's final state initializes or conditions the decoder, and the decoder emits one output token at a time.

The simplest seq2seq architecture can be described in three steps. First, embed the source tokens and run the encoder RNN over them. Second, use the encoder's final state as the decoder's initial state. Third, run the decoder over target-side inputs and project each decoder hidden state to vocabulary logits. During training, the decoder usually receives the ground-truth previous token. During inference, it receives the token it generated at the previous step. That mismatch is the source of teacher forcing's power and its tradeoff.

Teacher forcing means feeding the correct previous target token during training. If the target sentence is `<bos> the service restarted <eos>`, the decoder sees `<bos>` when predicting `the`, sees `the` when predicting `service`, and so on. This makes optimization much easier because early mistakes do not corrupt every later input during training. The tradeoff is exposure bias: at generation time, the decoder must condition on its own imperfect outputs, and it may not have learned to recover from those mistakes.

The following minimal model shows the shape mechanics. It is intentionally small: no attention, no beam search, no masking of loss, and no production tokenizer. The goal is to see encoder state, decoder inputs, teacher forcing, and output logits line up.

```python
import torch
import torch.nn as nn


class TinySeq2Seq(nn.Module):
    """Minimal GRU encoder-decoder with teacher-forced decoder inputs."""

    def __init__(self, vocab_size: int, emb_size: int, hidden_size: int):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, emb_size, padding_idx=0)
        self.encoder = nn.GRU(emb_size, hidden_size, batch_first=True)
        self.decoder = nn.GRU(emb_size, hidden_size, batch_first=True)
        self.output_head = nn.Linear(hidden_size, vocab_size)

    def forward(self, src_tokens: torch.Tensor, tgt_input_tokens: torch.Tensor):
        # src_tokens: (B, S), tgt_input_tokens: (B, T)
        src_emb = self.embedding(src_tokens)        # (B, S, emb_size)
        tgt_emb = self.embedding(tgt_input_tokens)  # (B, T, emb_size)

        # encoder_final: (1, B, hidden_size)
        _, encoder_final = self.encoder(src_emb)

        # decoder_output: (B, T, hidden_size)
        decoder_output, decoder_final = self.decoder(tgt_emb, encoder_final)

        # logits: (B, T, vocab_size)
        logits = self.output_head(decoder_output)
        return logits, decoder_final


torch.manual_seed(29)
B, S, T, vocab_size = 2, 5, 6, 20
src = torch.randint(1, vocab_size, (B, S))          # (B, S)
tgt = torch.randint(1, vocab_size, (B, T + 1))      # (B, T+1), includes shifted target

# Teacher forcing split: input excludes final token, labels exclude first token.
tgt_input = tgt[:, :-1]   # (B, T)
tgt_labels = tgt[:, 1:]   # (B, T)

model = TinySeq2Seq(vocab_size=vocab_size, emb_size=8, hidden_size=16)
logits, decoder_final = model(src, tgt_input)

loss = nn.CrossEntropyLoss()(
    logits.reshape(B * T, vocab_size),
    tgt_labels.reshape(B * T),
)

print(logits.shape)        # torch.Size([2, 6, 20])
print(decoder_final.shape) # torch.Size([1, 2, 16])
print(float(loss))
```

Attention entered sequence-to-sequence modeling before transformers removed recurrence entirely. The 2014 Bahdanau, Cho, and Bengio neural machine translation work added a learned alignment mechanism so the decoder could look back at encoder states instead of relying on one fixed-length vector. In your Block C terms, this was an early use of attention as a content-addressed read over sequence states. The transformer later made attention the main sequence mixer and eliminated recurrent decoding in the encoder, but historically the bridge ran through recurrent encoder-decoder models.

Real batches also need variable-length handling. Padding lets you store examples in a rectangular tensor, but a recurrent module will still process the padded timesteps unless you tell it not to. `pack_padded_sequence` passes length information to the recurrent layer so it can skip pad computation and return final states aligned with the true sequence lengths. Use `enforce_sorted=False` for ordinary unsorted batches; sorting is mainly needed for ONNX export or older workflows.

```python
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

torch.manual_seed(31)

B, T, input_size, hidden_size = 3, 5, 4, 6
lengths = torch.tensor([5, 3, 2], dtype=torch.long)  # (B,), true lengths before padding
x = torch.randn(B, T, input_size)                   # (B, T, input_size), padded batch

# Zero out padded positions only to make the example easier to inspect.
x[1, 3:, :] = 0.0
x[2, 2:, :] = 0.0

lstm = nn.LSTM(input_size, hidden_size, batch_first=True)

packed = pack_padded_sequence(
    x,
    lengths.cpu(),
    batch_first=True,
    enforce_sorted=False,
)

packed_output, (h_n, c_n) = lstm(packed)

# output: (B, T, hidden_size), restored to padded rectangular form.
output, restored_lengths = pad_packed_sequence(
    packed_output,
    batch_first=True,
    total_length=T,
)

print(output.shape)           # torch.Size([3, 5, 6])
print(restored_lengths)       # tensor([5, 3, 2])
print(h_n.shape, c_n.shape)   # torch.Size([1, 3, 6]) torch.Size([1, 3, 6])
```

Packed sequences are not the only valid strategy. You can also process padded tensors directly and mask the loss so pad tokens do not contribute. For many small teaching experiments, loss masking is simpler and fast enough. Packing matters when sequence lengths vary a lot, when you rely on final hidden states for true sequence ends, or when wasted pad computation dominates the batch. The key is conceptual cleanliness: padding is a batching artifact, and your objective should not reward the model for predicting pad positions as though they were data.

Teacher forcing also interacts with metrics. Token-level cross entropy can improve while sequence-level generation remains brittle, because the training objective asks "given the correct prefix, predict the next token" and generation asks "given the model's own prefix, keep producing a good sequence." For translation-like tasks, you therefore evaluate generated sequences, not only teacher-forced loss. For control or forecasting tasks, you may roll the model forward for multiple steps and measure error accumulation. The evaluation should mimic how the model will actually be used.

Attention can be added to the recurrent encoder-decoder when the fixed encoder state is too narrow. Conceptually, the decoder hidden state becomes a query over all encoder outputs, and the resulting context vector is fed into the decoder's prediction step. That is the historical bridge from recurrent seq2seq to the attention machinery you built in Block C. The important continuity is that attention first solved a bottleneck inside recurrent encoder-decoder systems before later becoming the main sequence mixer in transformer architectures.

## Part 7: RNNs vs Transformers Today

You built attention in module 1.4.3 and a transformer block in module 1.4.4, so you already know the modern alternative. Self-attention lets every position compute a weighted read over every other position in a layer. That gives long-range dependencies a short path: token 2 and token 200 can interact through one attention operation, while a vanilla left-to-right RNN needs information to pass through every intervening recurrent step. Attention also parallelizes across positions during training because the token representations for a layer can be computed together once the previous layer is available.

Those advantages explain why transformers became dominant for long-context language modeling and many sequence transduction tasks. Parallelism matters at scale because hardware can process matrix multiplications over all positions efficiently. Constant path length matters because gradient and information do not need to survive hundreds of recurrent transitions before distant positions can interact. The original transformer paper emphasized both quality and parallel training time compared with recurrent and convolutional sequence models.

The honest comparison also includes attention's costs. Full self-attention over a sequence has quadratic memory and compute in sequence length for the attention matrix, unless you use sparse, linear, chunked, recurrent, or state-space variants. A transformer decoder used for streaming generation still caches previous keys and values, and a model with long context can carry a large memory footprint. A small recurrent model with a fixed hidden state has bounded memory by construction: it updates one state as new data arrives.

That makes RNNs and recurrent-style models still relevant in specific engineering regimes. Streaming sensor inference, embedded keyword spotting, low-latency anomaly detection, small tabular-time models, and online control loops often value bounded memory and strict causality. If the model must process one event, update a state, and discard raw history, recurrence is a natural prior. If the sequence is short or the dataset is small, a GRU baseline can be easier to train and explain than a transformer with many more moving parts.

State-space models and linear recurrent architectures also show that the design space did not end with "RNNs lost, transformers won." Modern sequence modeling keeps revisiting recurrence-like state updates because the hardware and memory tradeoffs matter. The practical lesson is not to declare one family obsolete. The lesson is to match the structural prior to the data and constraints, then run the diagnostics from module 1.3.5: overfit a batch, inspect gradient norms, compare a baseline, ablate the architecture choice, and measure the failure modes that matter for your task.

A useful architecture review question is: what path must information take? In a vanilla RNN, information from timestep 1 reaches timestep 100 by surviving 99 state updates. In an LSTM or GRU, gates can preserve some coordinates across that path, but the path is still sequential. In a transformer encoder, information can move between those positions through attention in one layer, but the cost includes attention memory over the context. In a convolutional sequence model, information spreads through receptive fields over depth. The best choice is rarely about fashion; it is about the path length, parameter sharing, memory budget, and latency profile your problem actually imposes.

The capstone next will use this mindset. You will choose an architecture because the dataset has a structure, not because a module name came next in the syllabus. Images reward local spatial sharing. Sequences reward order-aware state or attention. Tabular baselines reward disciplined feature handling. The neural-network engineer's job is to make that prior explicit, test it against a simpler baseline, and write down the runbook so another engineer can reproduce both the training result and the reasoning.

## Did You Know?

- > **Did You Know?** Hochreiter and Schmidhuber's "Long Short-Term Memory" appeared in *Neural Computation* in 1997, before the 2010s deep-learning boom made LSTMs a default sequence-modeling tool.
- > **Did You Know?** Cho and collaborators introduced the GRU-style encoder-decoder model in 2014 for statistical machine translation, the same year Sutskever, Vinyals, and Le published the LSTM seq2seq paper.
- > **Did You Know?** Andrej Karpathy's 2015 "The Unreasonable Effectiveness of Recurrent Neural Networks" showed character-level RNNs generating text-like samples from datasets such as source code and Shakespeare.
- > **Did You Know?** The 2017 transformer paper proposed a sequence transduction architecture based solely on attention mechanisms, explicitly dispensing with recurrence and convolutions.

## Common Mistakes

| Mistake | Why it happens | Fix |
|---|---|---|
| Forgetting `batch_first=True` and silently swapping batch/time axes | PyTorch recurrent modules default to sequence-first tensors, while most `DataLoader` batches arrive batch-first. | Set `batch_first=True`, write shape comments, and assert that inputs are `(B, T, input_size)`. |
| Treating `h_n` as batch-first | `batch_first` changes input and output sequence tensors, but final hidden states stay `(layers * directions, B, H)`. | Index hidden states by layer/direction first, then batch, and document `h_n.shape` in model code. |
| Not detaching hidden state in truncated BPTT | The hidden value carries a computation graph from previous chunks, so memory grows and backward traverses too far. | Call `h = h.detach()` or detach each tensor in `(h, c)` after every optimizer step boundary. |
| Training on padded timesteps as if they were real data | Padding creates rectangular batches, but loss or recurrent computation may still include pad positions. | Use packed sequences, loss masks, `ignore_index` for pad tokens, or final-state gathering by true lengths. |
| Skipping gradient clipping on recurrent training | A long unrolled graph can produce rare but destructive gradient spikes. | Clip after `loss.backward()` and before `optimizer.step()`, then log total gradient norm during debugging. |
| Confusing LSTM cell state and hidden state | LSTMs return `(h_n, c_n)`, and both have the same shape but different roles. | Treat `c_n` as internal memory and `h_n` as exposed hidden representation; pass both between chunks. |
| Using teacher forcing at training time without testing free-running generation | The decoder learns under clean previous tokens but must condition on its own mistakes at inference. | Evaluate autoregressive generation, consider scheduled sampling carefully, and report sequence-level metrics. |
| Declaring transformers always better | Attention wins many long-range batch-training tasks, but it can be heavier than recurrence for streaming or bounded-memory workloads. | Compare a recurrent baseline under the actual latency, memory, sequence length, and accuracy constraints. |

## Quiz

1. **Why is a vanilla RNN cell best understood as a reused MLP rather than as a completely new kind of layer?**

   <details>
   <summary>Answer</summary>

   The cell performs the same affine-plus-nonlinearity pattern you used in Block A: it combines the current input with the previous hidden vector, adds a bias, and applies an activation. The new architectural prior is parameter sharing across timesteps. The same `W_xh`, `W_hh`, and bias are reused for every position, so the model can handle variable sequence lengths without learning separate parameters for every possible timestep.

   </details>

2. **What does BPTT add to ordinary backpropagation?**

   <details>
   <summary>Answer</summary>

   BPTT does not add a new derivative rule. It unrolls the recurrent computation across the observed timesteps and then applies ordinary reverse-mode backpropagation to that unrolled graph. Because recurrent parameters are reused, gradients from all timesteps accumulate into the same parameter tensors. The practical challenge is that gradients must pass through a long chain of recurrent Jacobians.

   </details>

3. **Why can repeated multiplication by recurrent Jacobians make gradients vanish or explode?**

   <details>
   <summary>Answer</summary>

   A gradient flowing from a late timestep to an early timestep is multiplied by a product of local Jacobians. If those transforms usually shrink vector norms, early gradients become tiny; if they usually expand norms, gradients can become huge. Tanh saturation worsens the shrinking case because its derivative approaches zero for large positive or negative preactivations.

   </details>

4. **What problem does gradient clipping solve, and what problem does it not solve?**

   <details>
   <summary>Answer</summary>

   Gradient clipping limits exploding gradients by rescaling gradients whose global norm exceeds a threshold before the optimizer step. It prevents destructive updates and NaNs, but it does not restore useful long-range signal after gradients have vanished. Vanishing gradients usually require better architecture, initialization, normalization, shorter truncation windows, or a different sequence model.

   </details>

5. **What is the main training intuition behind the LSTM cell state?**

   <details>
   <summary>Answer</summary>

   The LSTM cell state gives memory an additive update path: `c_t = f_t * c_{t-1} + i_t * g_t`. That lets the model preserve, erase, or write coordinates through differentiable gates instead of replacing the whole state with one tanh update. The additive path is a temporal gradient-highway idea similar in spirit to residual additions in deep feed-forward networks.

   </details>

6. **Why might you choose a GRU instead of an LSTM?**

   <details>
   <summary>Answer</summary>

   A GRU has gates and an additive hidden-state interpolation, but it merges cell and hidden state and usually has fewer parameters than an LSTM with the same hidden size. That can make it faster, simpler to manage, and easier to deploy. It is often a strong default when you want gated recurrence but do not need the LSTM's separate cell-state interface.

   </details>

7. **What is teacher forcing, and why can it create exposure bias?**

   <details>
   <summary>Answer</summary>

   Teacher forcing feeds the decoder the ground-truth previous token during training. This stabilizes optimization because one wrong prediction does not corrupt every later decoder input. Exposure bias appears because inference is different: the decoder must feed itself its own previous prediction, including mistakes, so it may enter states it rarely experienced during training.

   </details>

8. **Why did transformers displace RNNs for many long-range language tasks without making RNNs useless?**

   <details>
   <summary>Answer</summary>

   Transformers let positions communicate through attention with short path lengths and high parallelism during training, which is a major advantage for long-range text tasks at scale. RNNs still fit workloads where data streams one step at a time, memory must be bounded, strict causality matters, or a small gated baseline is easier to train and deploy than a heavier attention model.

   </details>

## Hands-On Exercise

You will train two tiny sequence classifiers on a synthetic memory task. Each sequence contains random noise, but the class is determined by the sign of the first feature at the first timestep. A model that only reads the final timestep cannot solve the task unless it learns to carry information forward. This is not a benchmark; it is a controlled debugging experiment that lets you compare a vanilla RNN and a GRU with the same training loop.

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


def make_memory_dataset(n: int = 512, T: int = 25, input_size: int = 3):
    torch.manual_seed(41)
    x = torch.randn(n, T, input_size)                  # (N, T, input_size)
    y = (x[:, 0, 0] > 0).long()                        # (N,), label depends on first timestep
    x[:, 1:, 0] += 0.25 * torch.randn(n, T - 1)        # distractor variation after timestep 0
    return x, y


class SequenceClassifier(nn.Module):
    def __init__(self, cell_type: str, input_size: int, hidden_size: int, num_classes: int):
        super().__init__()
        if cell_type == "rnn":
            self.encoder = nn.RNN(input_size, hidden_size, batch_first=True)
        elif cell_type == "gru":
            self.encoder = nn.GRU(input_size, hidden_size, batch_first=True)
        else:
            raise ValueError("cell_type must be 'rnn' or 'gru'")
        self.head = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor):
        # x: (B, T, input_size)
        output, h_n = self.encoder(x)
        # h_n: (1, B, hidden_size), final hidden state for the only layer.
        final = h_n[-1]                                # (B, hidden_size)
        logits = self.head(final)                      # (B, num_classes)
        return logits


def train_one(cell_type: str):
    x, y = make_memory_dataset()
    loader = DataLoader(TensorDataset(x, y), batch_size=64, shuffle=True)
    model = SequenceClassifier(cell_type, input_size=3, hidden_size=16, num_classes=2)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(8):
        correct = 0
        total = 0
        for xb, yb in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            pred = logits.argmax(dim=-1)
            correct += int((pred == yb).sum())
            total += yb.numel()
        print(f"{cell_type} epoch={epoch:02d} accuracy={correct / total:.3f}")


train_one("rnn")
train_one("gru")
```

**Success criteria**

- [ ] The script runs without shape errors and prints eight epochs for both `rnn` and `gru`.
- [ ] You can explain why the label depends on information from timestep 0 even though the classifier reads only the final hidden state.
- [ ] You can identify where gradient clipping occurs and why moving it after `optimizer.step()` would be wrong.
- [ ] You can modify `T` from 25 to 75 and describe how longer time-depth changes the vanilla RNN's difficulty.
- [ ] You can replace `nn.GRU` with `nn.LSTM`, handle `(h_n, c_n)`, and keep the classifier shape `(B, num_classes)`.

The expected outcome is not a fixed accuracy number, because random initialization and CPU math can vary. The useful observation is comparative and diagnostic. If the vanilla RNN struggles as `T` grows while the GRU remains more stable, you are seeing the gradient-path argument in miniature. If both fail, overfit a tiny batch of 16 examples, print gradient norms, lower the learning rate, and verify that the target really depends on `x[:, 0, 0]`.

## Key Takeaways

- A recurrent network is a weight-shared MLP cell applied across timesteps, not a separate magical primitive.
- The hidden state is a learned running summary; it is useful only because the training objective shapes it.
- BPTT is ordinary backprop on the unrolled graph, with shared recurrent weights accumulating gradients across time.
- Vanishing and exploding gradients are signal-propagation failures compounded by depth-in-time.
- Gradient clipping helps with exploding gradients, while LSTM and GRU gates provide trainable memory paths that mitigate vanishing gradients.
- Teacher forcing makes seq2seq training easier but creates a train/test mismatch that must be evaluated during generation.
- Transformers won many long-range batch-training workloads through parallelism and short attention paths, but recurrence remains useful for streaming, small, causal, and bounded-memory systems.

## Learner check

> A recurrent network is a weight-shared MLP cell applied across timesteps, not a separate magical primitive.

## Sources

- PyTorch Foundation, "PyTorch 2.12 Release Blog": https://pytorch.org/blog/pytorch-2-12-release-blog/
- PyTorch documentation, `torch.nn.RNN`: https://docs.pytorch.org/docs/stable/generated/torch.nn.RNN.html
- PyTorch documentation, `torch.nn.LSTM`: https://docs.pytorch.org/docs/stable/generated/torch.nn.LSTM.html
- PyTorch documentation, `torch.nn.GRU`: https://docs.pytorch.org/docs/stable/generated/torch.nn.GRU.html
- PyTorch documentation, `pack_padded_sequence`: https://docs.pytorch.org/docs/stable/generated/torch.nn.utils.rnn.pack_padded_sequence.html
- PyTorch documentation, `clip_grad_norm_`: https://docs.pytorch.org/docs/stable/generated/torch.nn.utils.clip_grad_norm_.html
- Hochreiter and Schmidhuber, "Long Short-Term Memory": https://direct.mit.edu/neco/article/9/8/1735/6109/Long-Short-Term-Memory
- Cho et al., "Learning Phrase Representations using RNN Encoder-Decoder for Statistical Machine Translation": https://arxiv.org/abs/1406.1078
- Sutskever, Vinyals, and Le, "Sequence to Sequence Learning with Neural Networks": https://arxiv.org/abs/1409.3215
- Bahdanau, Cho, and Bengio, "Neural Machine Translation by Jointly Learning to Align and Translate": https://arxiv.org/abs/1409.0473
- Pascanu, Mikolov, and Bengio, "On the difficulty of training recurrent neural networks": https://proceedings.mlr.press/v28/pascanu13.html
- Bengio, Simard, and Frasconi, "Learning long-term dependencies with gradient descent is difficult": https://pubmed.ncbi.nlm.nih.gov/18267787/
- Karpathy, "The Unreasonable Effectiveness of Recurrent Neural Networks": https://karpathy.github.io/2015/05/21/rnn-effectiveness/
- Vaswani et al., "Attention Is All You Need": https://arxiv.org/abs/1706.03762
- Dive into Deep Learning, "Recurrent Neural Networks": https://d2l.ai/chapter_recurrent-neural-networks/index.html
- Dive into Deep Learning, "Gated Recurrent Units (GRU)": https://d2l.ai/chapter_recurrent-modern/gru.html
- Dive into Deep Learning, "Long Short-Term Memory (LSTM)": https://d2l.ai/chapter_recurrent-modern/lstm.html
- Stanford CS231n, "Recurrent Neural Networks": https://cs231n.github.io/rnn/
- Stanford CS230, "Recurrent Neural Networks Cheatsheet": https://stanford.edu/~shervine/teaching/cs-230/cheatsheet-recurrent-neural-networks/
- Christopher Olah, "Understanding LSTM Networks": https://colah.github.io/posts/2015-08-Understanding-LSTMs/

## Next Module

**[Module 1.7: Capstone — Train a Real Net End-to-End](../module-1.7-capstone-train-a-real-net/)**
