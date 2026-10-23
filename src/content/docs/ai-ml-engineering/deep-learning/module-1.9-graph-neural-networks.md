---
title: "Graph Neural Networks"
description: "Decide when graph-structured inductive bias actually helps, choose between GCN, GraphSAGE, and GAT for the regime you have, recognize over-smoothing, over-squashing, and heterophily as the three GNN-specific failure modes, and use PyTorch Geometric correctly for node, link, and graph-level tasks."
slug: ai-ml-engineering/deep-learning/module-1.9-graph-neural-networks
sidebar:
  order: 1010
---

> Track: AI/ML Engineering | Complexity: `[MEDIUM]` | Time: 90-120 minutes
> Prerequisites: [Module 1.3.1: Initialization & Signal Propagation](module-1.3.1-initialization-signal-propagation/), [Module 1.4.4: The Transformer Block from Scratch](module-1.4.4-transformer-block-from-scratch/), and [Module 1.3: Model Evaluation, Validation, Leakage & Calibration](../../machine-learning/module-1.3-model-evaluation-validation-leakage-and-calibration/).

Graph neural networks, usually shortened to GNNs, are the part of deep learning
that handles inputs whose natural structure is a set of entities connected by
relationships rather than a regular grid or a sequence.
The reason practitioners care is not that graphs are fashionable.
It is that for some problems — molecule property prediction, social-network
classification, recommendation, knowledge-graph completion, fraud rings — the
relationships between examples carry signal that a row-and-column model can
only approximate by hand-engineering aggregate features.
The dominant pitfall is the opposite of underuse.
A team frames a problem as a graph because it can,
not because the graph structure actually informs the target,
and ends up paying the GNN tax — extra infrastructure, harder evaluation,
training-time bottlenecks — without earning the inductive bias premium.
This module is built around that decision discipline:
when GNNs are the right tool,
which family fits the regime,
how to evaluate without leaking,
and the three failure modes that are specific to graph models and have no
direct analog in CNNs or transformers.

## Learning Outcomes
- **Decide** whether a problem benefits from graph-structured inductive bias before reaching for a GNN, by comparing against a strong tabular baseline and inspecting whether the graph carries information the features do not.
- **Choose** between GCN, GraphSAGE, and GAT for a given regime by matching their assumptions about homophily, scale, and inductive versus transductive deployment to the data you actually have.
- **Diagnose** the three GNN-specific failure modes — over-smoothing as you stack layers, over-squashing on long-range tasks, heterophily that violates the connected-nodes-are-similar assumption — and explain which mitigations apply to each.
- **Design** train, validation, and test splits for transductive and inductive graph tasks that match the deployment shape, avoid leaking held-out labels (transductive) or held-out structural fragments (inductive), and prevent the link-prediction-specific traps of overlapping positive/negative edges and reverse-edge leakage.
- **Build** a working PyTorch Geometric pipeline using `Data`, the `MessagePassing` family, `GCNConv` / `SAGEConv` / `GATConv`, and `NeighborLoader` for graphs that do not fit in memory.

## Why This Module Matters
Picture a data-science team at a payments company spinning up a new fraud
project on a Monday morning.
They already have a strong tabular gradient-boosted classifier on engineered
transaction features — velocity, device fingerprint, prior-incident counts —
and a senior reviewer asks the obvious question.
"There is a graph here.
Customers connect to merchants, devices connect to multiple customers,
fraud rings cluster.
Should we be using a graph neural network?"
The good answer is to take the question seriously and the bad answer is to
treat it as rhetorical.
A team that says "yes, let's add a GCN" without first checking whether the
graph carries signal beyond what the engineered aggregates already encode
will spend a sprint plumbing graph data, fight node ID hygiene, hit
training-time issues with full-batch updates over a multi-million-node graph,
and produce a result that is hard to compare honestly against the tabular
baseline.
A team that says "no, graphs are overkill" too early misses the entire point
of the inductive bias when fraud rings really do look like rings.
The decision needs evidence.
The first move is to define the prediction unit (nodes, edges, or whole
subgraphs) and pick a small benchmark you can iterate on quickly.
The second is to run two baselines: the existing tabular model on whatever
features already exist, and a graph-blind multilayer perceptron on the same
node features ignoring the graph entirely.
If a 2-layer GCN cannot beat both, the graph is not adding information at the
scale of complexity you have introduced and the right answer is to keep the
tabular model.
PyTorch Geometric is the standard library that makes this experiment cheap
([PyTorch Geometric documentation](https://pytorch-geometric.readthedocs.io/en/latest/)).
Its `Data` object holds node features and edge indices in a few lines.
Its `MessagePassing` base class implements the canonical aggregate-then-update
abstraction ([PyG MessagePassing tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/create_gnn.html)).
Its layer cheatsheet enumerates the dozens of published GNN architectures
behind a single API ([PyG GNN cheatsheet](https://pytorch-geometric.readthedocs.io/en/latest/cheatsheet/gnn_cheatsheet.html)).
The reason this module matters is not that GNNs are exotic.
It is that the cost of using them poorly is high and the cost of skipping
them when they would have helped is also high.
Practitioners need a steady framework for choosing,
a vocabulary for the failure modes,
and a small set of working patterns that survive contact with real graphs.

## Section 1: What GNNs are, and what they aren't
A graph neural network is a model whose forward pass is structured by an
explicit graph: it computes node representations by repeatedly aggregating
information from each node's neighbors and updating the node's own state.
The simplest way to think about it is as a generalization of the convolution
operation in CNNs.
A 2D convolution computes a new feature for a pixel by mixing features in a
fixed-shape neighborhood — three by three, five by five — using shared
weights.
The neighborhood is regular because images are sampled on a grid.
A graph convolution computes a new feature for a node by mixing features
across the node's actual graph neighbors — which can be one or one thousand,
in any pattern — using shared weights.
The neighborhood is irregular because graphs are arbitrary.
That generalization is the whole point.
GNNs let the model exploit relational structure that a CNN can only see if
you re-shape the data into a grid first.
GNNs are not the same thing as graph algorithms.
Dijkstra, PageRank, community detection, and shortest-path queries are
deterministic procedures that read a graph and compute something specific.
They are not learning anything from labels.
A GNN is a parameterized model trained to fit a target signal — node labels,
edge presence, graph-level outcomes — using gradient descent.
A GNN is also not the only way to feed graph structure into a learner.
You can compute graph features (node degree, clustering coefficient,
neighborhood-aggregated statistics) and feed them to an XGBoost model, and
this hand-crafted approach often wins on small or feature-rich problems
([Module 1.6: XGBoost & Gradient Boosting](../../machine-learning/module-1.6-xgboost-gradient-boosting/)).
The interesting question for practitioners is when the learned aggregation
inside a GNN beats the hand-engineered aggregation outside one.
The honest answer is "sometimes," not "always," and most of this module is
about telling those situations apart.
Two regimes where GNNs tend to earn their cost are large graphs whose local
structure is rich enough that hand-engineering features is prohibitive,
and tasks where the same feature value carries different meaning depending
on its neighbors (a transaction at \$50 is normal for one merchant,
suspicious for another).
Two regimes where they tend to lose are small graphs with strong engineered
features and graphs whose connectivity does not actually carry signal toward
the target, where the graph is decorative rather than informative.

## Section 2: Graph data, briefly
A graph is a set of nodes and a set of edges.
Nodes can carry features (a vector per node), and edges can carry features
too (a vector per edge), although a lot of GNN work uses unweighted, untyped
edges to start.
Edges can be directed or undirected; in PyTorch Geometric, undirected graphs
are usually represented by storing each edge twice, once in each direction
([PyG introduction](https://pytorch-geometric.readthedocs.io/en/latest/get_started/introduction.html)).
Heterogeneous graphs have multiple node types and multiple edge types — for
instance a knowledge graph with `Person`, `Movie`, and `Director` node types
and `acted_in`, `directed`, and `friend_of` edge types.
PyG handles heterogeneous graphs through a separate API
([PyG heterogeneous tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/heterogeneous.html)),
because the message-passing rules are different per edge type and stacking
plain `GCNConv` layers does not respect that.
Three benchmark families recur across the literature, so it is worth
recognizing them.
Citation networks like Cora, CiteSeer, and Pubmed are small,
homophilic, and ship with standard transductive splits — they are the GNN
equivalent of MNIST, useful for quick iteration but not predictive of how a
model will behave on a million-node industrial graph.
Molecule datasets such as those in the Open Graph Benchmark family treat
each molecule as a separate small graph and the task as graph classification
or graph regression — predicting properties of the whole molecule.
Social and recommendation graphs are typically much larger, often
heterogeneous, and require sampled training because they do not fit in GPU
memory.
PyG ships datasets and `Data` builders for all three families
([PyG dataset tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/dataset.html)).
The data structure that ties everything together in PyG is the `Data`
object, which stores `x` (node features, shape `[num_nodes, num_features]`),
`edge_index` (shape `[2, num_edges]`, where row 0 is source nodes and row 1
is target nodes), and optional fields such as `y` for labels and
`edge_attr` for edge features.
Carrying that mental model makes the rest of the API much easier to read.

## Section 3: Message passing — the core abstraction
The unifying abstraction behind almost every modern GNN is the
message-passing neural network, or MPNN, framework.
At each layer, every node performs three steps.
First, for each neighbor, compute a message as a function of the source
node's features, the target node's features, and the edge features.
Second, aggregate the incoming messages with a permutation-invariant
function — typically sum, mean, or max — so that the result does not depend
on the arbitrary order of neighbors.
Third, update the target node's representation by combining its previous
state with the aggregated message, usually through a small neural network.
PyTorch Geometric exposes this directly through its `MessagePassing` base
class, which has three corresponding hook methods: `message`, `aggregate`,
and `update`
([PyG MessagePassing tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/create_gnn.html)).
GCN, GraphSAGE, GAT, and most other layers are implemented as
`MessagePassing` subclasses that override one or two of those hooks.
The abstraction matters for a reason that beginners often miss.
Stacking $k$ message-passing layers gives every node access to information
from nodes up to $k$ hops away.
That is the GNN equivalent of receptive field in CNNs, and it has direct
practical consequences.
A 2-layer model can only see 2-hop neighborhoods, so any task that requires
information from 5 or 6 hops away will need either a deeper model or a
different architectural choice.
The naive instinct — "if 5 hops is needed, stack 5 layers" — runs straight
into the over-smoothing and over-squashing failure modes covered in
Sections 7 and 8, which is exactly why GNNs do not get arbitrarily deep
the way transformers and CNNs do.

## Section 4: GCN — the simplest baseline
The graph convolutional network of Kipf and Welling is the cleanest starting
point ([Kipf & Welling, 2017](https://arxiv.org/abs/1609.02907)).
A GCN layer can be written as

$$
H^{(l+1)} = \sigma\big(\hat{D}^{-1/2}\, \hat{A}\, \hat{D}^{-1/2}\, H^{(l)} W^{(l)}\big)
$$

where $\hat{A} = A + I$ adds a self-loop to each node, $\hat{D}$ is the
diagonal degree matrix of $\hat{A}$, $H^{(l)}$ is the matrix of node
features at layer $l$, $W^{(l)}$ is a learned weight matrix, and $\sigma$
is a nonlinearity.
In plain English, each node's new feature vector is a normalized average of
its neighbors' features (including itself), passed through a linear
transform and then a nonlinearity.
The symmetric $\hat{D}^{-1/2}$ scaling is borrowed from spectral graph
theory and reflects the first-order approximation to a Chebyshev
polynomial of the graph Laplacian.
GCN is transductive in its original formulation: training and inference both
operate on a single fixed graph, with train and test nodes distinguished by
boolean masks rather than by being separate graphs.
You feed the entire graph in, the model sees all node features and the full
adjacency, and the loss is computed only on the train-mask nodes.
The implicit assumption that makes vanilla GCN work is homophily —
neighbors in the graph are likely to share a label.
Citation networks are highly homophilic, which is why GCN performs well on
Cora and friends.
Section 9 returns to what happens when that assumption breaks.
For a sense of where this lives in PyG, the `torch_geometric.nn.GCNConv`
class implements exactly this layer, with one practical caveat: by default
it adds self-loops and computes the symmetric normalization on every
forward pass
([PyG nn module reference](https://pytorch-geometric.readthedocs.io/en/latest/modules/nn.html)).

## Section 5: GraphSAGE — inductive and sampled
GraphSAGE generalizes GCN in two important ways
([Hamilton et al., 2017](https://arxiv.org/abs/1706.02216)).
First, it is inductive by design: the same trained model can be applied to
graphs it never saw at training time, because each layer is just an
aggregation function plus a learned transform that operates on
neighborhoods, not on a fixed adjacency matrix.
Second, instead of using every neighbor at every layer, GraphSAGE samples a
fixed-size subset of neighbors per node per layer.
The original paper used something like 25 neighbors at the first layer and
10 at the second.
That sampling decision is the load-bearing trick for scaling.
On a million-node graph, materializing the full adjacency matrix in GPU
memory is impossible.
Sampling fixes the memory cost per node and per layer, which makes
mini-batch training feasible.
PyG implements this end-to-end through `SAGEConv` for the layer and
`NeighborLoader` for the sampling
([PyG NeighborLoader tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/neighbor_loader.html)).
GraphSAGE supports several aggregator choices: mean (the default and most
common), max-pool (a small MLP applied to each neighbor's features followed
by an elementwise max), and LSTM (an order-dependent aggregator that the
authors note technically violates permutation invariance and use only with
random ordering).
The mean aggregator is the right starting point for most teams.
The pool aggregator can help when the per-neighbor features need a learned
projection before aggregation.
The LSTM aggregator is rarely the answer in modern practice and you should
treat it as historical context unless you have a specific reason.
For inductive problems — predicting on a graph the model has not seen, such
as new molecules, new users, or new fraud subgraphs — GraphSAGE is the
default choice.
For transductive problems on a single fixed graph, you can use either
GraphSAGE without sampling or a vanilla GCN; the difference is small and
the choice usually comes down to library familiarity.

## Section 6: GAT — attention on graphs
The graph attention network replaces fixed-coefficient aggregation with a
learned attention mechanism ([Veličković et al., 2018](https://arxiv.org/abs/1710.10903)).
Where GCN gives each neighbor of a node a weight that depends only on the
node degrees, GAT computes a weight per edge as a function of the source
and target node features.
The attention coefficient between source $j$ and target $i$ at a given
layer is

$$
\alpha_{ij} = \frac{\exp\big(\text{LeakyReLU}\big(a^{\top}\,[W h_i \,\|\, W h_j]\big)\big)}{\sum_{k \in \mathcal{N}(i)} \exp\big(\text{LeakyReLU}\big(a^{\top}\,[W h_i \,\|\, W h_k]\big)\big)}
$$

where $a$ is a learned attention vector, $W$ is a learned linear
projection, $\|$ denotes concatenation, and $\mathcal{N}(i)$ is the set of
neighbors of $i$.
Multi-head attention runs $K$ independent attention heads in parallel and
either concatenates their outputs (intermediate layers) or averages them
(final layer), in direct analogy to multi-head self-attention in
transformers.
The conceptual link is worth carrying: GAT applies the same
attention-as-learned-weighting idea that drives transformers, but
restricted to actual graph neighbors instead of every position in a
sequence.
A transformer step attends across all token positions; a GAT layer
attends only across the explicit edges in the graph.
That restriction is what keeps GAT computationally tractable on large
graphs while still giving the model the flexibility to weight neighbors
non-uniformly.
GAT helps most when neighbor importance varies sharply across edges — for
instance when a node has many neighbors but only a few are actually
informative for the target — and when the graph leans somewhat away from
strict homophily, so that uniform averaging is a worse default than learned
weighting.
GAT does not help much on highly homophilic graphs with low-variance
neighborhoods, where GCN's degree-normalized averaging is already a
reasonable inductive bias.
A GAT layer in PyG is `torch_geometric.nn.GATConv` with arguments for the
hidden dimension and the number of heads
([PyG nn module reference](https://pytorch-geometric.readthedocs.io/en/latest/modules/nn.html)).

## Section 7: Over-smoothing — the depth ceiling
Stacking more GNN layers does not give you progressively richer
representations the way stacking more CNN or transformer layers does.
Past two or three layers, vanilla GCN representations begin to converge
toward a fixed point that depends on graph topology but is independent of
the original node features.
Every node ends up looking like every other node in its connected
component.
This phenomenon is called over-smoothing, and it is the single most
important practical fact about GNN depth.
The intuition is that each GCN layer is approximately a step of Laplacian
smoothing on the node features.
Iterating Laplacian smoothing on a connected graph drives all node
representations toward a stationary distribution determined by the graph
structure, not the inputs.
[Oono and Suzuki (2020)](https://arxiv.org/abs/1905.10947) made this
formal and showed that, under standard conditions, deep GCNs lose
expressive power exponentially with depth.
That is why Kipf and Welling's original GCN paper used two layers, why
most GraphSAGE pipelines use two or three, and why a beginner's instinct to
"just stack more" backfires.

> **Pause and predict:** You stack a 2-layer GCN, a 4-layer GCN, an 8-layer
> GCN, and a 16-layer GCN on Cora using the same hidden width and the same
> training budget. What does the validation accuracy curve look like as a
> function of depth, and at what depth do you expect the model to start
> behaving like an MLP that ignores its inputs entirely? (Answer: validation
> accuracy peaks around 2 to 3 layers, decays steadily beyond that, and
> approaches a value determined by class imbalance plus graph structure as
> depth grows large — node embeddings have collapsed and the linear head is
> classifying near-identical vectors.)

The mitigations are real and worth knowing, but none of them is a free lunch.
Skip connections borrowed from ResNet — adding the layer's input back to
its output — let gradient and feature signal bypass the smoothing operator,
which delays the collapse but does not avoid it indefinitely.
Jumping Knowledge networks
([Xu et al., 2018](https://arxiv.org/abs/1806.03536)) concatenate or
maximize across representations from every layer, letting the model pick
the right effective depth per node.
GCNII ([Chen et al., 2020](https://arxiv.org/abs/2007.02133)) combines an
initial residual to the layer-zero features with an identity mapping in the
weight, making GCNs that are 32 or 64 layers deep tractable.
Layer normalization or batch normalization between message-passing layers
helps a little.
For practitioner work, the right default is two or three vanilla layers
plus a strong feature head, and you only reach for deep-GCN tricks when you
have evidence that long-range information is genuinely needed and your
shallow model is bottlenecked by it.

## Section 8: Over-squashing — long-range bottlenecks
Over-squashing is a different and more fundamental failure mode.
Even before over-smoothing kills you, long-range information has to flow
through narrow cuts in the graph topology, and a fixed-width
representation per node simply cannot carry enough bits.
[Alon and Yahav (2021)](https://arxiv.org/abs/2006.05205) framed this
formally and showed that on tasks requiring information from many hops
away, GNNs degrade sharply because the per-node representation acts as a
bottleneck on every long path.
The intuition is geometric.
Imagine a tree with a deep root and many leaves.
A signal at one leaf needs to travel up to the root, mix with signals from
every other branch at the root, and then travel back down to a different
leaf.
Each intermediate node squashes its entire growing receptive field into the
same fixed-width vector.
By the time the signal reaches a far-away node, it has been averaged with
exponentially many other signals, and the relevant bit is lost.
Over-squashing is fundamental rather than implementational because the
bottleneck lives in the topology and the fixed representation width, not
in any particular layer or optimizer.
The most striking empirical finding from the same paper is that adding a
single fully-adjacent layer — one round in which every node directly sees
every other node, like a transformer step — recovered most of the lost
performance on long-range tasks.
That observation seeded the current line of work on graph transformers,
which trade locality for global mixing in select layers.
For practitioner work today, the practical implication is that if your
problem genuinely needs information from six or more hops away, you should
consider graph rewiring, virtual global nodes, or hybrid GNN-plus-attention
architectures rather than simply stacking more local GNN layers.
Local-only GNNs are not the right tool for fundamentally long-range tasks.

## Section 9: Heterophily — the connected-nodes-are-similar trap
The implicit assumption baked into vanilla GCN, GraphSAGE, and GAT is
homophily: nodes connected by an edge tend to share label or be similar in
the target sense.
Citation networks have this property — papers cite papers in their own
subfield.
So do many social networks — friends share interests.
But not all graphs are homophilic.
Some online discussion graphs are heterophilic, where connections form
between disagreeing parties.
Some chemistry problems involve structures where adjacent atoms tend to be
of different elements.
And many real-world graphs land somewhere in between, with mixed local
patterns.
On a strongly heterophilic graph, averaging neighbor features mixes in
signal that is actively misleading.
Each GCN layer makes node representations look more like their dissimilar
neighbors, which is exactly the opposite of what the downstream classifier
needs.
[Zhu et al. (2020)](https://arxiv.org/abs/2006.11468) showed empirically
that on several heterophilic benchmark graphs — Texas, Wisconsin, and
Cornell webpage networks among them — a plain 2-layer multilayer
perceptron that ignores the graph entirely outperformed GCN, GraphSAGE, and
GAT.
That is a striking result and worth carrying in your head: a 2-layer MLP
beating a 2-layer GCN means the graph structure was either not informative
or actively harmful for the standard architectures.

> **Pause and decide:** A teammate proposes training a vanilla GCN on a
> graph where edges connect users who flagged each other for problematic
> behavior, and the prediction target is whether a given user is themselves
> problematic. Why might that be exactly the wrong default architecture,
> and what is the one-line baseline you should run first to ground the
> decision? (Answer: flagging is a heterophilic signal — users tend to
> flag people unlike themselves, not similar to themselves — so vanilla
> GCN's homophily-implicit averaging will smooth in misleading neighbor
> features. Run a graph-blind MLP on the same node features as the
> baseline; if GCN cannot beat it, the graph structure is not adding
> usable signal for this architecture.)

The principled answer when you suspect heterophily is to compute a
homophily ratio — the fraction of edges where the two endpoints share the
target label — on the training portion of the graph.
A high ratio (above roughly 0.7) is a strong indicator that vanilla GCN is
a reasonable default.
A low ratio (below roughly 0.5) is a strong indicator that you should
compare against a graph-blind MLP and consider heterophily-aware
architectures such as H2GCN or GPR-GNN, which separate self representations
from neighbor representations or learn signed propagation coefficients.
Cross-link [Module 1.7: Naive Bayes, k-NN & SVMs](../../machine-learning/module-1.7-naive-bayes-knn-and-svms/)
for the broader principle that the right learner depends on the structure
of the data.

## Section 10: Practical tasks — node, edge, graph
Three task categories cover most GNN work in industry, each with a
different evaluation discipline.
Node classification predicts a label for each node — for instance, whether
a user is fraudulent, whether a paper belongs to a topic, whether a protein
has a particular function.
The training signal lives on a subset of nodes, the evaluation signal lives
on a held-out subset of nodes from the same graph (transductive) or from
separate graphs (inductive), and the loss is computed per node.
Link prediction predicts whether a candidate edge exists or scores a
likelihood — recommendation systems, drug-target interaction, knowledge
graph completion.
Training requires both positive examples (real edges) and negative
examples (sampled non-edges), and evaluation needs careful negative
sampling to avoid trivial negatives.
Graph classification predicts a label for an entire graph — molecule
property prediction is the canonical example.
Each example is a separate small graph with its own nodes and edges, and
the model produces a single output per graph by pooling node
representations after several message-passing layers.
PyG ships graph-level pooling layers (`global_mean_pool`, `global_max_pool`,
`global_add_pool`) for exactly this case
([PyG nn module reference](https://pytorch-geometric.readthedocs.io/en/latest/modules/nn.html)).
Each task has its own evaluation failure modes.
Node classification on a single graph is the slipperiest because the
transductive setting deliberately exposes the whole graph at training time;
the practitioner trap is reporting transductive numbers and silently
implying inductive generalization (covered in Section 11).
Link prediction *does* leak if your negative samples include edges that
exist in your validation or test set, or if your train edges include the
reverse of test edges in an undirected graph.
Graph classification is closest to standard supervised learning because the
graphs are independent, but random splits can still understate brittleness
when scaffold-aware splits would have surfaced it
([Module 1.3: Model Evaluation, Validation, Leakage &
Calibration](../../machine-learning/module-1.3-model-evaluation-validation-leakage-and-calibration/)).

## Section 11: Evaluation discipline for graphs
The leakage taxonomy from Module 1.3 applies directly to graphs, but with
two extra wrinkles worth naming.

The first wrinkle is the transductive-versus-inductive distinction.
In a transductive node-classification setup, the model sees the entire
graph at training time — full structure, full node features, edges in both
directions across the train-test boundary. Only the **labels** of test
nodes are masked. Aggregating across train-test edges during message
passing is not leakage in this setup; it is the defining feature of
transductive evaluation. This is the standard regime for Cora, CiteSeer,
and Pubmed, and it is appropriate when deployment is the same shape: a
fixed graph that grows with new labels rather than with new nodes.

In an inductive setup, the test nodes (or test graphs) are completely held
out, including their edges and structural positions. The model has to
generalize to unseen graph fragments at inference time. Most production
fraud, recommendation, and molecular-property problems are inductive in
practice. The real and common evaluation failure in published GNN work is
not "messages crossed train-test edges" — it is **reporting transductive
accuracy and silently claiming inductive generalization from it**. Match
your evaluation to your deployment shape, or both numbers are uninterpretable.

The second wrinkle is that random splits often understate failure modes
that a structural split would expose. Adjacent nodes share community,
time, or scaffold context, and a random shuffle distributes that context
evenly across train, validation, and test, which makes the held-out
performance look more robust than it is. On custom graphs, the discipline
is to split by a structural unit that matches deployment — connected
component, time window, molecular scaffold, user cluster — so that the
test set actually exercises the kind of generalization the model will be
asked to do in production. The standard Cora/CiteSeer/Pubmed splits are
publicly fixed for benchmark comparability rather than for realism, which
is why production-leaning papers usually report results on splits that
respect graph structure as well.

Cross-link [Module 1.3: Model Evaluation, Validation, Leakage &
Calibration](../../machine-learning/module-1.3-model-evaluation-validation-leakage-and-calibration/)
for the full leakage discipline; it transfers to graphs with the
modifications above.

## Section 12: PyTorch Geometric in practice
PyTorch Geometric is the dominant Python library for GNN work today, and
its API is small enough that a working pipeline fits on one page
([PyG documentation](https://pytorch-geometric.readthedocs.io/en/latest/);
[PyG installation notes](https://pytorch-geometric.readthedocs.io/en/latest/notes/installation.html)).
DGL is the other actively maintained option and remains a reasonable
choice in some research environments, but for new practitioner pipelines
PyG is the default and that is what this section covers.
The core data object holds node features and edges:

```python
import torch
from torch_geometric.data import Data

# A graph with 4 nodes and 4 directed edges, 1 feature per node.
edge_index = torch.tensor(
    [[0, 1, 1, 2],
     [1, 0, 2, 3]],
    dtype=torch.long,
)
x = torch.tensor([[-1.0], [0.0], [1.0], [2.0]])
data = Data(x=x, edge_index=edge_index)
```

A two-layer GCN model is a few more lines, using the same `forward` shape
as any other PyTorch module:

```python
import torch
import torch.nn.functional as F
from torch_geometric.nn import GCNConv


class GCN(torch.nn.Module):
    def __init__(self, in_dim, hidden, out_dim):
        super().__init__()
        self.conv1 = GCNConv(in_dim, hidden)
        self.conv2 = GCNConv(hidden, out_dim)

    def forward(self, x, edge_index):
        h = F.relu(self.conv1(x, edge_index))
        h = F.dropout(h, p=0.5, training=self.training)
        return self.conv2(h, edge_index)
```

The training loop on a transductive node-classification graph uses train
and validation masks to restrict the loss and metric computation:

```python
import torch
import torch.nn.functional as F

model = GCN(in_dim=data.num_node_features, hidden=16, out_dim=7)
optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)

for epoch in range(200):
    model.train()
    optimizer.zero_grad()
    out = model(data.x, data.edge_index)
    loss = F.cross_entropy(out[data.train_mask], data.y[data.train_mask])
    loss.backward()
    optimizer.step()
```

For graphs that do not fit in GPU memory, the same model architecture
trains on sampled mini-batches via `NeighborLoader`
([PyG NeighborLoader tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/neighbor_loader.html)):

```python
from torch_geometric.loader import NeighborLoader

loader = NeighborLoader(
    data,
    num_neighbors=[25, 10],
    batch_size=128,
    input_nodes=data.train_mask,
)

for batch in loader:
    optimizer.zero_grad()
    out = model(batch.x, batch.edge_index)
    loss = F.cross_entropy(
        out[: batch.batch_size],
        batch.y[: batch.batch_size],
    )
    loss.backward()
    optimizer.step()
```

Swapping in `SAGEConv` or `GATConv` is a one-line change in the model
definition, because PyG keeps the layer-call signature consistent across
the `MessagePassing` family.
That uniformity is a deliberate design choice and is worth more than any
single layer in the library — it is what makes architecture experiments
cheap.

## Section 13: When GNNs are the wrong tool
The most important section in this module is also the shortest, because
the principle is simple and the rest of the work is in following it.
Try a strong non-GNN baseline first.
For a node-level task with rich engineered features, an XGBoost model on
those features ([Module 1.6: XGBoost & Gradient Boosting](../../machine-learning/module-1.6-xgboost-gradient-boosting/))
is often within a small margin of the best GNN and is dramatically simpler
to operate.
For a node-level task with weaker features but informative graph
structure, a graph-blind MLP on the node features alone is the right
sanity check; if that baseline beats your GCN, you have learned something
important about the data and you should investigate before adding GNN
infrastructure.
Concrete situations where GNNs tend to lose include the following.
A small graph with a few thousand nodes and well-engineered features —
the inductive bias premium does not pay for itself.
A heterophilic graph without specialized architecture — Section 9
documented the empirical pattern.
A latency-sensitive inference path where you need millisecond predictions
and the neighborhood lookup itself becomes the bottleneck — sampling-based
inference can mitigate but adds complexity that simpler models avoid.
A graph where the relationships are decorative rather than informative —
the structure exists but does not carry signal toward the target.
The discipline is the same as in every other module of this curriculum.
Beat a strong simple baseline before adding complexity.
GNNs do real work when the graph structure carries information that
hand-engineered features do not, the regime is large enough that the
inductive bias amortizes the engineering cost, and you have the patience
to evaluate honestly through inductive splits.
They are the wrong tool when those conditions do not hold.

> **Pause and reflect:** Your team has a fraud-detection problem with one
> million users, dense engineered features (transaction velocity, device
> fingerprint, prior-incident counts), and a strong XGBoost baseline at
> some target precision. A junior teammate proposes a GraphSAGE model on
> the user-merchant bipartite graph. What is the smallest, fairest
> experiment that decides whether to invest, and what is the failure
> condition under which you go back to XGBoost? (Answer: train a
> graph-blind MLP on the same engineered features and a GraphSAGE on the
> same node features plus the graph, evaluating both with the same
> inductive split that simulates the deployment scenario. If GraphSAGE
> cannot beat both XGBoost and the graph-blind MLP by a margin that
> exceeds the operational cost of the new pipeline — feature engineering
> is shifted, neighborhood serving is added, monitoring is expanded — go
> back to XGBoost.)

Across these regimes the discipline is the same as everywhere else in deep learning: reach for the heavier tool only after a cheaper baseline has been given a fair chance and lost. A graph-structured model earns its operational cost — feature pipelines, neighborhood serving, extra monitoring, and the debugging surface of message passing — only when the graph carries signal that a graph-blind baseline on the same features genuinely cannot recover. When a tabular model or a plain MLP matches the GNN within the margin that the new infrastructure would cost, the senior decision is to ship the simpler system and revisit the graph approach only if the data situation changes. Treat a GNN as one option in a portfolio of models, not as the default, and let the fair-experiment result rather than architectural novelty decide what reaches production.

## Decision-keyed regime table

| Regime | Algorithm | Why |
|---|---|---|
| Small homophilic graph, fixed at deployment, transductive | 2-layer GCN | Strong default; minimal infrastructure; matches the assumption that connected nodes share labels. |
| Large graph that does not fit in GPU memory, inductive deployment | GraphSAGE with `NeighborLoader` | Sampling-based training scales; same model runs on unseen graph fragments. |
| Neighbors carry highly variable importance for the target | GAT | Learned attention earns its cost when uniform averaging is a worse default. |
| Need for many hops of receptive field beyond what 2-3 layers gives | JKNet, GCNII, or graph rewiring with virtual nodes | Vanilla deep GCNs collapse from over-smoothing; deep-GNN tricks address that, global mixing addresses over-squashing. |
| Heterophilic graph (low neighbor-label agreement) | Graph-blind MLP first; H2GCN- or GPR-GNN-style if MLP plus structure helps | Vanilla GCN often loses to MLP here; the right baseline is MLP, not a deeper GCN. |
| Small graph with rich engineered features, latency-sensitive deployment | XGBoost on engineered features (no GNN) | The inductive-bias premium does not amortize; tabular wins on cost and latency. |
| Graph-level prediction (molecules, small subgraphs) | GCN or GAT body plus `global_mean_pool` head | Pooling collapses node embeddings into a graph embedding for the final head. |

## Did You Know?

- The symmetric normalization in GCN — $\hat{D}^{-1/2} \hat{A} \hat{D}^{-1/2}$
  — is borrowed from spectral graph theory and corresponds to the
  first-order Chebyshev polynomial approximation of a localized graph
  filter. Kipf and Welling derived their layer as a simplification of
  earlier spectral approaches, and the surprising empirical result was
  that this drastic simplification still works well on standard citation
  benchmarks ([Kipf & Welling, 2017](https://arxiv.org/abs/1609.02907)).

- GraphSAGE stands for "Sample and AggregatE." Sampling is in the name
  because it is the load-bearing trick that makes the method scale to
  large graphs — fixed-size neighborhood sampling at each layer keeps
  memory bounded regardless of graph size or node degree
  ([Hamilton et al., 2017](https://arxiv.org/abs/1706.02216)).

- Adding a single round of fully-connected mixing — letting every node
  directly see every other node for one layer — recovered most of the lost
  performance on long-range tasks in the over-squashing study by Alon and
  Yahav, suggesting the bottleneck is fundamentally about graph topology
  rather than depth or capacity
  ([Alon & Yahav, 2021](https://arxiv.org/abs/2006.05205)). This finding
  motivates much of the current work on graph transformers.

- Oono and Suzuki showed formally that under standard conditions deep
  GCNs lose expressive power exponentially in depth — node embeddings
  collapse toward a low-dimensional subspace whose structure depends on
  the graph rather than the input features. The two-layer convention in
  most GCN papers is empirically calibrated to stay safely above this
  collapse ([Oono & Suzuki, 2020](https://arxiv.org/abs/1905.10947)).

## Common Mistakes

| Mistake | Failure mode | Correct approach |
|---|---|---|
| Stacking 8 or more GCN layers expecting CNN-like depth gains | Over-smoothing collapses node embeddings; validation accuracy decays | Use 2-3 layers as the default; reach for JKNet or GCNII only with evidence that long-range information is the bottleneck |
| Splitting nodes uniformly at random on a custom graph and reporting transductive accuracy as if it were inductive | Random splits hide structural correlation; transductive numbers do not measure inductive generalization | Match the split shape to deployment — split by structural unit (component, time, scaffold, user cluster) when the model must generalize to unseen graph fragments |
| Reaching for a GNN before running a tabular or graph-blind baseline | Wasted infrastructure if XGBoost or MLP already wins on cost | Beat XGBoost on engineered features and an MLP on node features alone before claiming a GNN result |
| Forgetting to scale continuous node features | Distance- and attention-based layers see lopsided per-feature magnitudes | Standardize node features unless you are sure the scales are already comparable, mirroring the discipline in [Module 1.4: Feature Engineering & Preprocessing](../../machine-learning/module-1.4-feature-engineering-and-preprocessing/) |
| Training a vanilla GCN on a heterophilic graph and reporting only its accuracy | A 2-layer MLP on the same features may beat the GCN; the comparison hides the diagnosis | Check the homophily ratio, run an MLP baseline, and use heterophily-aware architectures if the regime requires it |
| Full-batch training on a multi-million-node graph | GPU OOM and unstable runs | Switch to `NeighborLoader` and sampling-based mini-batches |
| Treating GAT attention weights as global feature importance | Attention weights are conditional on path and message-passing dynamics | Use proper interpretability tools such as gradient-based attribution or GNNExplainer if the goal is feature attribution |
| Reporting transductive accuracy and claiming inductive generalization | The model never had to generalize structurally; deployment will reveal the gap | Match evaluation to deployment — if the production scenario is inductive, evaluate inductively |

## Quiz

1. A team trains a 2-layer GCN on Cora and gets a strong validation
   accuracy. They double the depth to 4 layers expecting an improvement,
   then 6, then 8. Validation accuracy drops monotonically. What is the
   diagnosis and what is the cheapest mitigation that does not abandon the
   architecture?
   <details>
   <summary>Answer</summary>
   The diagnosis is over-smoothing: repeated symmetric aggregation
   collapses node embeddings toward a fixed point dominated by graph
   structure rather than input features. The cheapest mitigation is to
   add residual connections so the layer's input is added back to its
   output, which lets feature signal bypass the smoothing operator. If
   that is not enough, JKNet-style concatenation across layers or GCNII's
   initial-residual plus identity-mapping construction allow much deeper
   stacks. The wrong answer is to keep stacking layers in the hope that a
   deeper model will find a better optimum.
   </details>

2. A fraud team has a strong XGBoost baseline on engineered transaction
   features at the desired precision. A teammate proposes adding a GNN
   over the user-merchant bipartite graph. What is the smallest fair
   experiment that decides whether to invest, and what failure condition
   sends the team back to XGBoost?
   <details>
   <summary>Answer</summary>
   Train a graph-blind MLP on the same engineered features and a
   GraphSAGE on the same node features plus the graph, evaluating both
   under the same inductive split that simulates deployment. If GraphSAGE
   cannot beat both the XGBoost baseline and the MLP baseline by a margin
   that exceeds the operational cost of the new pipeline — feature
   engineering shifts, neighborhood serving, expanded monitoring — go
   back to XGBoost.
   </details>

3. A team trains on graph G1 and evaluates on graph G2, where G2 is a
   completely separate graph the model has never seen. Which family of
   architecture is the natural fit and why?
   <details>
   <summary>Answer</summary>
   GraphSAGE is the natural fit because it is inductive by design. Each
   layer is an aggregation function plus a learned transform that
   operates on local neighborhoods rather than on a fixed adjacency
   matrix, so the same trained model applies to graphs it never saw at
   training time. Vanilla GCN as originally formulated is transductive
   and does not generalize to a new graph in the same way without
   modification.
   </details>

4. A graph has a low homophily ratio — neighbors typically have different
   target labels. A team plans to train a 4-layer GCN on it. What is the
   first baseline they should run instead, and why?
   <details>
   <summary>Answer</summary>
   A graph-blind MLP on the node features alone. On heterophilic graphs,
   averaging neighbor features actively mixes in misleading signal, and
   empirical studies have shown that a plain 2-layer MLP outperforms
   GCN, GraphSAGE, and GAT on several heterophilic benchmarks. If the
   MLP wins or matches the GCN, the conclusion is that the graph
   structure is not adding usable signal under the standard architecture
   and the team should consider heterophily-aware models or stick with
   the MLP.
   </details>

5. A team needs to train a node classifier on a graph with several
   million nodes. Full-batch training runs out of GPU memory. What is the
   right tool from PyTorch Geometric and what does it do conceptually?
   <details>
   <summary>Answer</summary>
   `NeighborLoader` performs GraphSAGE-style sampling: at each layer, for
   every node in the batch, it samples a fixed number of neighbors —
   typically 25 at the first layer and 10 at the second. The sampled
   subgraph fits in GPU memory regardless of the global graph size, and
   the same trained model can be applied to the full graph at inference
   time. This is the standard scaling answer for industrial GNN
   pipelines.
   </details>

6. A team finds that GCN and GAT give nearly the same validation
   accuracy on a homophilic citation benchmark. Should they ship GAT
   because it is more expressive, or GCN because it is simpler?
   <details>
   <summary>Answer</summary>
   On a homophilic graph with low-variance neighborhoods, GCN's
   degree-normalized averaging is already a good inductive bias and
   GAT's learned attention does not earn its extra cost. Ship GCN. GAT
   helps when neighbor importance varies sharply — a node has many
   neighbors and only a few are informative — or when the graph is not
   strictly homophilic. Picking the more expressive model when the data
   does not require it costs training time and serving complexity for
   no measurable gain.
   </details>

7. Alon and Yahav reported that adding a single fully-adjacent layer
   recovered much of the lost performance on long-range tasks. What
   broader lesson does this carry for GNN architecture design?
   <details>
   <summary>Answer</summary>
   The lesson is that over-squashing is a topological bottleneck rather
   than a depth or capacity problem. A fixed-width per-node
   representation cannot carry enough bits along long paths, no matter
   how many local message-passing layers you stack. Recovering long-range
   performance requires breaking locality somewhere — through global
   mixing layers, virtual fully-connected nodes, graph rewiring, or
   transformer-style attention over the whole graph at select layers —
   not through stacking more local layers.
   </details>

8. A team plans to predict molecule properties: each example is a small
   graph and the prediction is a single number per molecule. Sketch the
   architecture and identify the one structural component that
   distinguishes graph-level work from node-level work.
   <details>
   <summary>Answer</summary>
   Stack two or three message-passing layers (GCN or GAT) to compute node
   embeddings, then apply a graph-level pooling operation —
   `global_mean_pool`, `global_max_pool`, or `global_add_pool` — to
   collapse the per-node embeddings into a single per-graph vector,
   followed by a small MLP head for the final prediction. The
   distinguishing component is the pooling step: node-level work returns
   one prediction per node, while graph-level work pools first and
   returns one prediction per graph.
   </details>

## Hands-On Exercise

The goal of this exercise is to internalize three things at once: the
graph-blind baseline, the homophily check, and the over-smoothing
diagnostic. You will compare an MLP, a 2-layer GCN, and a deeper GCN on
the standard Cora citation dataset shipped with PyTorch Geometric and
write a short decision memo at the end.

- [ ] Install `torch` and `torch_geometric` per the official installation
  notes ([PyG installation](https://pytorch-geometric.readthedocs.io/en/latest/notes/installation.html)).
  Verify by importing both libraries in a Python shell.

- [ ] Load the Cora dataset and inspect the `Data` object.

```python
from torch_geometric.datasets import Planetoid

dataset = Planetoid(root="/tmp/Cora", name="Cora")
data = dataset[0]
print(data)
print("num_nodes:", data.num_nodes)
print("num_edges:", data.num_edges)
print("num_features:", data.num_features)
print("num_classes:", dataset.num_classes)
```

- [ ] Compute the homophily ratio: the fraction of edges where the two
  endpoints share a label, restricted to the training subgraph. Note the
  result. Cora is highly homophilic, which sets your expectations for the
  baselines below.

- [ ] Train a graph-blind MLP on the node features alone, ignoring
  `edge_index` entirely. Use the train mask, validate on the val mask,
  and report final test accuracy. This is your floor.

- [ ] Train a 2-layer GCN with `GCNConv` on the same data, same loss,
  same training budget. Report the test accuracy. On Cora this should
  noticeably outperform the MLP, confirming the graph carries signal
  beyond the features alone.

- [ ] Replace the GCN body with `GATConv` (one head is fine to start) and
  rerun. On Cora the gap to GCN should be small. Note the result and
  reflect on whether attention earned its extra training cost.

- [ ] Stretch goal: train two more GCN configurations with depth 4 and
  depth 8, holding hidden width and training budget constant. Plot or
  tabulate test accuracy as a function of depth. You should see
  validation and test accuracy peak around depth 2 to 3 and degrade as
  depth increases — this is over-smoothing in practice.

- [ ] Assemble the full PyTorch Geometric pipeline end to end: build the
  `Data` object, wire `MessagePassing` layers (`GCNConv` / `SAGEConv` /
  `GATConv`) into a model, and use `NeighborLoader` so the same pipeline
  scales to graph data that does not fit in GPU memory.

- [ ] Write a short decision memo. State the homophily ratio. State each
  baseline's accuracy. Identify which architecture you would ship for
  Cora-style problems and why. Note explicitly whether the depth
  experiment confirmed over-smoothing on this dataset, and what you
  would do differently on a heterophilic graph with the same node
  features.

## Sources

- [PyTorch Geometric documentation](https://pytorch-geometric.readthedocs.io/en/latest/): the canonical entry point and library reference for the `Data`, `MessagePassing`, and layer APIs used throughout this module.
- [PyTorch Geometric introduction](https://pytorch-geometric.readthedocs.io/en/latest/get_started/introduction.html): hands-on getting-started guide that documents the `Data` object and the standard transductive Cora workflow.
- [PyTorch Geometric installation notes](https://pytorch-geometric.readthedocs.io/en/latest/notes/installation.html): authoritative installation procedure including the wheel-index step that is easy to miss on first install.
- [PyTorch Geometric MessagePassing tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/create_gnn.html): explains the `message`, `aggregate`, `update` hook structure that underlies most published GNN layers.
- [PyTorch Geometric nn module reference](https://pytorch-geometric.readthedocs.io/en/latest/modules/nn.html): full API for `GCNConv`, `SAGEConv`, `GATConv`, and the graph-level pooling layers used in graph classification.
- [PyTorch Geometric heterogeneous graph tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/heterogeneous.html): documents the separate API and message-passing rules for graphs with multiple node and edge types.
- [PyTorch Geometric NeighborLoader tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/neighbor_loader.html): the standard mini-batch sampling pattern for graphs that do not fit in GPU memory.
- [PyTorch Geometric dataset tutorial](https://pytorch-geometric.readthedocs.io/en/latest/tutorial/dataset.html): documents how PyG ships standard benchmark datasets and how to wrap a custom dataset.
- [PyTorch Geometric GNN cheatsheet](https://pytorch-geometric.readthedocs.io/en/latest/cheatsheet/gnn_cheatsheet.html): reference table of published GNN layers and the `MessagePassing` features each one uses.
- [PyTorch documentation](https://pytorch.org/docs/stable/index.html): canonical reference for the underlying tensor, module, autograd, and optimizer APIs that PyG builds on.
- [Kipf & Welling, 2017](https://arxiv.org/abs/1609.02907): introduced the GCN layer with symmetric normalized adjacency aggregation as a first-order spectral approximation, plus the standard transductive Cora and CiteSeer benchmarks.
- [Hamilton et al., 2017](https://arxiv.org/abs/1706.02216): introduced GraphSAGE with the inductive sampling-based aggregator design that scales to large graphs.
- [Veličković et al., 2018](https://arxiv.org/abs/1710.10903): introduced GAT with multi-head attention over graph neighbors, mirroring transformer-style attention restricted to local structure.
- [Xu et al., 2018](https://arxiv.org/abs/1806.03536): introduced Jumping Knowledge networks as a structural mitigation for over-smoothing by combining representations across layers.
- [Oono & Suzuki, 2020](https://arxiv.org/abs/1905.10947): proved formally that deep GCNs lose expressive power exponentially with depth, the rigorous version of over-smoothing.
- [Alon & Yahav, 2021](https://arxiv.org/abs/2006.05205): identified over-squashing as a topological bottleneck for long-range tasks and showed that a single fully-adjacent layer recovered much of the lost performance.
- [Zhu et al., 2020](https://arxiv.org/abs/2006.11468): introduced H2GCN and documented the heterophilic-graph regime where a plain MLP outperforms GCN, GraphSAGE, and GAT on standard benchmarks.
- [Chen et al., 2020](https://arxiv.org/abs/2007.02133): introduced GCNII with initial residual and identity mapping to enable practically-deep GCN stacks without collapse.

## Next Module

This module closes the Tier-2 extension of the Deep Learning Foundations
track. The KubeDojo curriculum continues in two adjacent tracks under
the same AI/ML Engineering umbrella.

The [Reinforcement Learning](../../reinforcement-learning/module-1.1-rl-practitioner-foundations/)
track introduces RL as a practitioner decision discipline, and a Tier-2
Offline RL & Imitation Learning module is forthcoming. The
[Machine Learning](../../machine-learning/module-1.11-hyperparameter-optimization/)
track's Tier-1 sequence (modules 1.1 through 1.12) is complete; the
Tier-2 sequence covering class imbalance, interpretability, Bayesian ML,
recommenders, conformal prediction, fairness, and causal inference is
forthcoming.

The unifying theme across all three tracks is the same discipline you
have applied throughout this module: pick the right tool for the data
structure and the deployment regime, beat a strong simple baseline
before adding complexity, and evaluate honestly under a split that
matches deployment.
