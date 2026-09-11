---
title: "Offline RL & Imitation Learning"
description: "Learn how to train decision policies when live exploration is unsafe, unethical, or too expensive. This module teaches the production boundary between behavior cloning, conservative offline RL, interactive imitation, adversarial imitation, and honest offline evaluation."
slug: ai-ml-engineering/reinforcement-learning/module-2.1-offline-rl-and-imitation-learning
sidebar:
  order: 21
---

> Track: AI/ML Engineering | Complexity: `[ADVANCED]` | Time: 100-120 minutes
> Prerequisites: [Module 1.1: RL Practitioner Foundations](../module-1.1-rl-practitioner-foundations/), [Module 2.7: Causal Inference for ML Practitioners](../../machine-learning/module-2.7-causal-inference-for-ml-practitioners/), and comfort with supervised validation, sequential data, and Python experiment logs.

The most tempting reinforcement-learning demo is also the least available production workflow. Let an agent explore.
Watch rewards improve. Deploy the best checkpoint.

Real systems are less permissive. You cannot let an unproven treatment policy explore on patients. You cannot let a
recommender system freely show bad content to millions of users while it learns. You often have logs, not a
playground. The policy that created those logs is already gone, undocumented, biased by product rules, or mixed with
human overrides.

Offline reinforcement learning and imitation learning live in that uncomfortable space. They ask whether a better
policy can be learned from fixed experience. They also ask when the honest answer is no.

## Learning Outcomes

- **Diagnose** whether a logged decision dataset has enough coverage for offline RL, behavior cloning, or no policy-learning attempt at all.
- **Explain** how distribution shift and extrapolation error make offline RL harder than ordinary supervised learning on logged examples.
- **Implement** a small d3rlpy workflow on a Minari (D4RL-derived) dataset using the current v2 configuration API and offline evaluators.
- **Compare** behavior cloning, CQL, BCQ, IQL, TD3+BC, DAgger, and GAIL by the kind of pessimism, supervision, or interaction each method adds.
- **Decide** how to evaluate an offline policy when online A/B testing is unavailable, risky, or only allowed after a strict offline gate.

## Why This Module Matters

A model can fail in production before it ever takes a bad action. It can fail at the moment the team decides the
training data is enough.

Imagine a hospital has five years of treatment logs. For every patient state, the records show what a clinician chose,
what medications were given, what vitals changed, and whether the patient improved. The product question sounds like
RL: "Can we learn a treatment policy that improves outcomes over time?" The safety answer is harsher: you cannot
deploy an exploratory policy that tries unfamiliar treatment sequences just to learn their returns.

Now imagine a large recommender system. The team has billions of logged impressions, clicks, dwell times, skips,
hides, and purchases. Online RL sounds attractive because recommendations shape future user behavior. But a random
exploratory policy across a large user base can damage trust, revenue, creator ecosystems, and legal exposure before
the learning curve has time to recover.

In both systems, online exploration is the thing you want mathematically and cannot have operationally. The dataset is
not a neutral sample from all possible actions. It is the fossil record of previous policies, human choices,
guardrails, ranking heuristics, product launches, and missing counterfactuals.

Offline RL is therefore not "RL without a simulator" in the casual sense. It is decision learning under a hard
evidence constraint. If the logged data never tried an action in a state, the learner does not get to discover its
outcome by trying it now.

Imitation learning enters from another angle. Sometimes the best policy signal is not a scalar reward at all. It is a
demonstration: a clinician's historical choice, a driver taking over an autonomous system, a human operator steering a
robot, or a support agent resolving a customer workflow. If the demonstrations are good enough and the deployment
distribution stays close, supervised behavior cloning may be the right answer.

The central skill in this module is restraint. You will learn the algorithms, but the practitioner test is whether you
can say: "This dataset cannot support that policy claim."

## Section 1: What offline RL is, and why it's different from online RL

Online RL learns by interacting. The agent chooses actions, observes rewards, updates its policy, and uses the
improved policy to collect more data. That loop is the engine behind the algorithms in [Module 1.1: RL Practitioner Foundations](../module-1.1-rl-practitioner-foundations/).

Offline RL breaks the loop. The agent receives a fixed dataset of transitions: state, action, reward, next state, and
terminal flag. Training may run for many gradient steps, but the evidence does not expand. No new action is tried. No
uncertain region is probed. No evaluator rescues a bad assumption by collecting a fresh rollout.

That no-exploration constraint changes the meaning of generalization. In supervised learning, you normally ask whether
the model predicts well on held-out examples drawn from a similar data-generating process. In offline RL, you ask
whether a new policy will choose actions that may not look like the logged policy's actions. The target policy can
move the state distribution away from the dataset that trained it.

The ordinary vocabulary can hide the danger. "Off-policy" in online RL often means the algorithm can reuse
replay-buffer data collected by older policies. But the learner may still collect more data later. "Offline" means the
dataset is fixed before training starts. There is no recovery path through exploration.

| Setting | Data source | Can the learner explore | Main evaluation problem |
|---|---|---|---|
| Online RL | Current policy rollouts | Yes | Seed variance and environment validity |
| Off-policy online RL | Replay plus new rollouts | Usually yes | Replay bias plus online stability |
| Offline RL | Fixed logged dataset | No | Counterfactual policy value |
| Imitation learning | Demonstrations or expert labels | Sometimes | Expert coverage and compounding errors |

Why does this matter? Because a high-value action in an offline value function may be a hallucination. If a Q-network
sees a state-action pair that never appeared in the data, it may assign a high value because of function
approximation, not because reality supports that choice. An online agent can sometimes try the action and learn. An
offline agent cannot.

The conservative instinct starts here. An offline policy should usually stay near the support of the behavior policy
unless the evidence is strong enough to justify leaving it. That one sentence explains much of the algorithmic
landscape in this module.

> **Pause and decide:** A fraud-response team has logs where analysts almost always chose "manual review" for borderline cases and almost never chose "auto approve." The offline RL learner assigns high value to auto approval in those borderline states. Do you treat that as discovery, or as an extrapolation warning? What evidence would change your mind?

The answer is not "never improve." Offline RL exists because logged data can contain better-than-current behavior:
good rare decisions, suboptimal old policies, mixed strategies, and reward information that supervised imitation
ignores. The answer is that improvement claims require support. Without support, offline RL becomes value-function fan
fiction.

## Section 2: Distribution shift and extrapolation error

The fundamental problem is distribution shift with consequences. The training data comes from one behavior policy. The
learned policy may choose different actions. Those different actions can lead to different future states. Now both the
action distribution and the state distribution have shifted.

This is sharper than a normal covariate shift warning. In a sequential decision system, one unsupported action can
place the policy into an unsupported future state, where the next action is even less grounded. Errors compound.

Extrapolation error is the value-function version of this failure. A critic estimates Q-values for actions. For
actions inside the data distribution, the estimate is at least anchored by observed transitions. For
out-of-distribution actions, the estimate can be arbitrarily optimistic. The policy then selects those optimistic
actions because the critic told it to. The critic is wrong because the policy selected unsupported actions. The loop
reinforces itself.

This is why offline RL papers often sound pessimistic. They are not trying to make policies timid for aesthetic
reasons. They are trying to prevent the learned policy from exploiting estimation error.

Consider a recommender log. The old system rarely showed long technical videos to new users. The offline critic
notices that the few new users who did see those videos had excellent long-term retention. That may be a real
opportunity. It may also be selection bias: the old system only showed those videos when onboarding signals already
indicated a technical user. If the new policy shows those videos to everyone, the data did not answer that
counterfactual.

This is the bridge to [Module 2.7: Causal Inference for ML Practitioners](../../machine-learning/module-2.7-causal-inference-for-ml-practitioners/). Both offline RL and causal
inference deal with observational data where interventions are missing or constrained. Both force you to separate "we
observed this association" from "we know what would happen if we intervened." Offline RL adds sequential feedback and
policy optimization, which makes the counterfactual burden heavier.

| Failure mode | What it looks like | Why it happens |
|---|---|---|
| Unsupported action | Policy chooses actions absent from similar logged states | The critic extrapolated beyond evidence |
| Narrow behavior policy | Dataset covers only one operating style | Improvement options are not observable |
| Hidden confounding | Logged action depends on variables missing from state | Rewards reflect unobserved selection |
| Compounding error | Small action mismatch creates future state mismatch | The policy controls its own next data distribution |
| Reward proxy drift | Logged reward no longer matches deployment objective | Product or clinical context changed |

The hard part is that offline train-test splits do not solve this by themselves. A held-out transition from the same
behavior policy tests prediction on logged behavior. It does not prove that a new policy's chosen actions have
support.

Practical diagnostics therefore look at coverage. How often does the candidate policy choose actions similar to logged
actions in similar states? How much of the dataset comes from high-return episodes? Are rare high-return actions
spread across states, or concentrated in a narrow segment? Can a simple behavior-cloning model reproduce the logs? If
it cannot, the state representation may be missing key variables.

The sober default is simple: the narrower the data, the more conservative the policy must be.

Distribution shift in offline RL is not a single jump but a chain reaction. The behavior policy `π_b` generated the logs. Your candidate policy `π` may assign high probability to actions that `π_b` rarely took in similar states. Those actions lead to next states that are themselves underrepresented, so both action marginals and state marginals drift away from the training distribution with every sequential decision. Supervised learning on logged `(state, action)` pairs mostly tests whether you can imitate labels on states that appeared in the data. Offline RL asks whether a new policy's sequential choices will stay in regions where returns were actually observed, which is a harder counterfactual claim.

Extrapolation error is the mechanism critics exploit. Function approximators are smooth: a Q-network or value model can assign an optimistic score to an unseen action because neighboring seen actions looked good. Without online correction, the policy gradient or improvement step chases that optimism. Conservative methods exist to push down values outside the data support, constrain the policy toward logged actions, or avoid explicit maximization over unseen actions during critic training. None of these remove the need for coverage; they reduce how aggressively the learner can hallucinate improvement.

## Section 3: Behavior cloning — when supervised learning is enough

Behavior cloning is imitation learning in its simplest deployed form. Treat the logged expert action as a label. Train
a supervised model from state to action. Deploy the model only where the state distribution resembles the
demonstration distribution.

That sounds too simple for an RL module. It is often the right starting point.

Behavior cloning ignores rewards. That is a limitation when demonstrations are mixed-quality or when the learner could
improve by preferring high-return trajectories. But ignoring rewards is also a stabilizer. The model does not invent
value for unsupported actions. It learns to stay close to observed behavior.

Behavior cloning is enough when three conditions hold. The demonstrator is competent. The deployment states will
remain close to the training states. The cost of merely matching the demonstrator is acceptable.

Autonomous driving provides the classic caution. A model trained to imitate human steering from dashboard camera
frames may perform well on ordinary roads. But if it drifts slightly from the lane center, it starts seeing states
that the human data rarely contains, because humans corrected earlier. The cloned policy then receives unfamiliar
observations and can drift more. This is compounding error, not ordinary classification error.

In recommender systems, behavior cloning may mean copying a mature ranking policy before adding small guarded
improvements. In medical decision support, it may mean learning a clinician-assistive suggestion model that stays
within historical practice rather than claiming treatment-policy optimization.

```python
from d3rlpy.algos import BCConfig
from d3rlpy.datasets import get_minari
from d3rlpy.metrics import EnvironmentEvaluator

dataset, env = get_minari("mujoco/halfcheetah/medium-v0")

bc = BCConfig(
    batch_size=256,
    learning_rate=1e-3,
).create(device=False)

bc.fit(
    dataset,
    n_steps=10000,
    n_steps_per_epoch=2500,
    evaluators={
        "environment": EnvironmentEvaluator(env, n_trials=3),
    },
)
```

This code is not presented as a performance recipe. It is a baseline discipline. If a sophisticated offline RL method
cannot beat a behavior-cloning baseline under the same evaluation protocol, the extra machinery has not earned its
keep.

Behavior cloning is also a dataset audit. If BC performs poorly even on logged validation data, the state may not
contain the information the demonstrator used. In a hospital, that missing information might be a clinician note,
bedside observation, or contraindication not captured in structured features. In a product system, it might be a
hidden rule, ranking override, or delayed moderation signal.

Do not skip BC. It is the cheapest way to learn whether "imitate the data" is already hard.

Imitation learning is broader than behavior cloning alone, and the taxonomy matters for scoping projects. Behavior cloning treats expert actions as supervised labels and is the right first move when demonstrations are competent and deployment states stay near the training distribution. DAgger adds interactive expert corrections on states the learner actually visits, which attacks compounding error but requires ongoing expert availability. Inverse RL tries to recover a reward function that explains expert behavior when no trustworthy scalar reward exists, which is powerful but identification-heavy. GAIL and related adversarial methods learn imitation rewards from discriminator feedback and usually need rollouts, so they sit between pure offline logs and full online RL. Choosing among them is less about prestige than about what evidence you have: fixed logs, live expert time, a simulator, or only trajectories without rewards.

## Section 4: Conservative offline RL — CQL, BCQ, IQL

Conservative offline RL methods ask a practical question: how can a learner improve on logged behavior without
trusting unsupported actions too much?

The answer is not one trick. Different algorithms place the guardrail in different parts of the learning problem. CQL
penalizes optimistic Q-values. BCQ restricts candidate actions toward the behavior distribution. IQL avoids querying
values for unseen actions during policy improvement.

### CQL: make unsupported actions look worse

Conservative Q-Learning trains a critic to be pessimistic about actions outside the dataset. The core idea is to push
down Q-values for actions the policy might choose unless the data supports them. That directly targets extrapolation
error.

CQL is attractive because it matches the practitioner's fear: "The critic is too optimistic where we have no
evidence." Its knob is conservatism. Too little, and the policy chases hallucinated value. Too much, and the policy
becomes behavior cloning with extra compute.

In d3rlpy v2, continuous-control CQL uses `CQLConfig`. Discrete-action CQL uses `DiscreteCQLConfig`. That distinction
matters because old examples on the internet often use older constructor patterns.

```python
from d3rlpy.algos import CQLConfig, DiscreteCQLConfig

continuous_cql = CQLConfig(conservative_weight=5.0).create(device=False)
discrete_cql = DiscreteCQLConfig(alpha=1.0).create(device=False)
```

### BCQ: generate only plausible actions

Batch-Constrained Q-Learning attacks the problem from the action side. Instead of allowing the actor to propose
arbitrary actions, BCQ learns a generative model of actions that resemble the batch. The policy then chooses among
plausible actions rather than searching the full action space.

That is a strong fit when the logged behavior policy is broad enough to contain useful alternatives, but not broad
enough to justify unconstrained maximization. The policy can improve by selecting better-supported actions, not by
inventing new behavior.

The limitation is also clear. If the dataset does not contain good behavior, BCQ cannot manufacture it. A narrow
dataset creates a narrow candidate set.

### IQL: avoid out-of-distribution action queries

Implicit Q-Learning takes another route. It learns value functions from dataset actions and uses expectile regression
to identify high-value behavior without explicitly maximizing over unseen actions during critic learning. The policy
extraction step then imitates high-advantage actions.

That makes IQL feel less like "learn a value function and exploit it everywhere" and more like "find the good parts of
the data and imitate them harder." This is often a useful production mental model. IQL can be strong when the dataset
contains a mixture of weak and strong behavior.

| Method | Pessimism mechanism | Useful when | Main caution |
|---|---|---|---|
| CQL | Penalize high Q-values for unsupported actions | Critic optimism is the main risk | Conservatism can flatten real improvement |
| BCQ | Restrict candidate actions near the batch | Logged actions are broad but not safe to leave | Cannot escape bad coverage |
| IQL | Learn from dataset actions and extract high-advantage behavior | Dataset mixes mediocre and strong behavior | Hyperparameters shape how selective imitation becomes |

> **Pause and decide:** You have a customer-support routing dataset where experienced agents sometimes chose excellent escalations, but the old routing policy also made many routine choices. Would you prefer BC, IQL, or CQL first? What does your answer assume about the quality spread inside the logs?

Conservative offline RL is not a guarantee. It is a set of bias choices. You deliberately bias the learner away from
unsupported improvement because unsupported improvement is the dangerous kind.

> **Landscape snapshot — as of 2026-06**
>
> d3rlpy v2 exposes algorithms through `*Config` classes (for example `CQLConfig`, `BCConfig`) followed by `.create()`. Discrete-action variants use separate configs such as `DiscreteCQLConfig`. Parameter names like `conservative_weight` and `alpha` differ by algorithm and release; verify against the pinned docs in **Sources** before copying snippets into production pipelines.
>
> **Datasets:** the original D4RL package is unmaintained and pins Python `<3.11`, so it will not install on a modern interpreter. The Farama Foundation is superseding it with **Minari**, which re-hosts the D4RL datasets under a `D4RL/`-prefixed and `mujoco/<env>/<quality>` namespace (e.g. `mujoco/halfcheetah/medium-v0`). d3rlpy v2 loads these through `get_minari(<id>)`. Exact dataset ids and version suffixes drift — confirm the current id with `minari list remote` before relying on one.

## Section 5: TD3+BC and the regularized-policy family

TD3+BC became influential partly because it is conceptually plain. Start with a strong off-policy continuous-control
algorithm. Add a behavior-cloning regularizer to the actor update. The policy is rewarded for high estimated value,
but penalized for straying too far from dataset actions.

That regularization view is useful beyond the specific method. Many production offline RL systems end up needing the
same shape: optimize an objective, but keep the new policy close to a known behavior policy.

Why does that help? Because the actor is the part of the system that can exploit critic error. If the actor is free to
search the action space, it will find places where the critic is accidentally optimistic. The BC term makes that
search expensive.

```python
from d3rlpy.algos import TD3PlusBCConfig

td3_bc = TD3PlusBCConfig(
    alpha=2.5,
    actor_learning_rate=3e-4,
    critic_learning_rate=3e-4,
).create(device=False)
```

The `alpha` parameter controls the value-versus-imitation balance. The exact interpretation belongs to the
implementation, but the production question is general: how far are you willing to let the policy move from observed
behavior?

This family is common in practice because it communicates well. Stakeholders can understand a policy that is allowed
to improve only while staying close to logs. Risk reviewers can ask for support diagnostics on the proposed actions.
Engineers can compare against BC and CQL without changing the whole workflow.

The weakness is that closeness is not the same as safety. If the logged behavior is unsafe, biased, or legally
problematic, regularizing toward it preserves those problems. If the logged action is only safe because of hidden
human context, the model may imitate the surface action without the hidden judgment.

Regularization is a seatbelt, not a proof.

## Section 6: Model-based offline RL — MOReL/MOPO

Model-based offline RL asks: can we learn a dynamics model from the offline dataset, then use that model to generate
imagined rollouts for policy improvement?

The appeal is obvious. If real exploration is forbidden, maybe simulated exploration from a learned model can fill the
gap. The danger is equally obvious. The model is trained on the same narrow data. When the policy drives the model out
of distribution, the model can become confidently wrong.

MOReL and MOPO are two influential research-frontier responses. They both recognize that model uncertainty is the core
problem. They differ in how they make uncertainty costly.

MOReL learns a pessimistic MDP. When the learned model detects that the policy has entered an uncertain region, it
transitions to an absorbing low-reward state. The policy learns that unsupported areas are dangerous.

MOPO penalizes rewards in model-generated rollouts according to uncertainty. If the model is uncertain about a
transition, the imagined reward is reduced. The policy is nudged toward model-supported rollouts.

| Method | Model-based idea | Pessimism trick |
|---|---|---|
| MOReL | Learn a model and plan in a pessimistic MDP | Send uncertain regions to a bad absorbing state |
| MOPO | Learn a model and optimize imagined rollouts | Penalize rewards by model uncertainty |

This is powerful research territory, but it is not the first production move for most teams. Dynamics models add
another source of error. You now have policy error, critic error, and model error. The evaluation burden rises.

Model-based offline RL is most plausible when the state-action space has learnable structure, the dataset has
meaningful coverage, and uncertainty estimates are taken seriously. It is least plausible when the data is narrow,
high-dimensional, nonstationary, and missing the variables that drove behavior.

## Section 7: DAgger and interactive imitation

Behavior cloning learns from a fixed demonstration dataset. DAgger changes the data collection loop.

The DAgger idea is simple: let the learner act, ask the expert what should have been done in the states the learner
actually visits, add those labeled states to the dataset, and retrain. This directly attacks compounding error.

Why does that matter? Because the learner's mistakes create states the expert demonstrations may not contain. A cloned
driving policy drifts left. Now the relevant question is not, "What did humans do in normal centered-lane states?" It
is, "What should the policy do from this slightly wrong state?"

DAgger is interactive imitation, not pure offline learning. It requires expert labeling during or after learner
rollouts. That makes it impossible in some safety-critical settings, but extremely useful when safe supervised
intervention is available.

Robotics, operations tooling, and internal workflow automation often fit this pattern. You can let the learner propose
actions in a sandbox, or under human supervision, then ask experts to correct the states it reaches.

The production tradeoff is expert time. DAgger can reduce distribution shift, but it spends human attention on the
learner's actual failure states. That is often a good bargain when failures are structured and expensive.

```python
# Sketch of the DAgger loop. The expert_label function is domain-specific.

dataset = []
policy = train_behavior_clone(dataset)

for round_id in range(5):
    visited_states = roll_out_policy(policy, safety_monitor=True)
    corrections = [(state, expert_label(state)) for state in visited_states]
    dataset.extend(corrections)
    policy = train_behavior_clone(dataset)
    print(f"round={round_id}, labeled_states={len(dataset)}")
```

The code is intentionally small because the infrastructure is the point. DAgger is not a single import that solves
imitation. It is a workflow: safe learner rollouts, expert correction, dataset aggregation, retraining, and regression
tests for earlier states.

Use DAgger when the expert can label learner-induced states. Do not pretend it is offline RL when the expert is
unavailable.

## Section 8: GAIL and adversarial imitation

GAIL starts from a different frustration: what if expert demonstrations are available, but the reward function is
missing, unreliable, or impossible to write cleanly?

Generative Adversarial Imitation Learning borrows the adversarial idea from GANs. A discriminator learns to
distinguish expert behavior from policy behavior. The policy learns to produce behavior that the discriminator cannot
distinguish from the expert.

Why is this useful? Because many real tasks have demonstrations but no trustworthy scalar reward. A human can show how
to drive smoothly, manipulate an object, or handle a workflow. Writing a reward that captures all of that behavior
without loopholes is much harder.

GAIL learns an imitation reward implicitly. The policy is optimized through RL so that its occupancy measure, the
distribution of visited state-action pairs, matches the expert's.

That also explains the cost. GAIL usually requires interaction with an environment or simulator. It is not a drop-in
replacement for offline RL on fixed logs. If the policy cannot roll out, the adversarial loop loses its main training
signal.

AIRL extends this line by trying to learn rewards that transfer better across dynamics. That is valuable when the
reward, not just the behavior, is the object you want to recover.

| Method | Learns from | Needs rollouts | Practitioner use |
|---|---|---|---|
| Behavior cloning | Expert actions | No | First imitation baseline |
| DAgger | Expert corrections on learner states | Yes, with supervision | Fix compounding errors |
| GAIL | Expert trajectories plus discriminator feedback | Usually yes | Imitate behavior when reward is hard to write |
| AIRL | Expert trajectories with reward recovery goal | Usually yes | Learn a more transferable reward model |

The mistake is to treat adversarial imitation as magic reward discovery. The learned reward is only as meaningful as
the demonstrations, the discriminator setup, and the environment coverage. It can still imitate bias, unsafe
shortcuts, or expert habits that do not match the deployment objective.

## Section 9: d3rlpy in practice — implement a small offline workflow

d3rlpy is the most direct practitioner library for this module's workflow. It focuses on offline RL, online RL,
datasets, off-policy evaluation, and a consistent algorithm API. The important v2 pattern is configuration first, then
`.create()`. That matters because many older examples instantiate algorithm classes directly. Current v2 examples use classes such
as `CQLConfig`, `BCQConfig`, `IQLConfig`, `TD3PlusBCConfig`, `BCConfig`, `DiscreteCQLConfig`, and `DiscreteBCQConfig`.

The following script is intentionally modest. It loads a Minari MuJoCo dataset (the D4RL-derived `mujoco/halfcheetah/medium-v0`), trains behavior cloning as a baseline,
trains CQL as a conservative offline RL method, then trains FQE to estimate the learned CQL policy from the offline
data. The environment evaluator is included because Minari can recover a benchmark environment, but in a real medical or
recommender deployment, that online evaluator would be replaced by a stricter offline gate and later a guarded
experiment. Treat this as an **implement** exercise: you are wiring configuration objects, a fixed dataset, training loops, and evaluators—not chasing a leaderboard number.

```python
import os

import d3rlpy
from d3rlpy.algos import BCConfig, CQLConfig
from d3rlpy.datasets import get_minari
from d3rlpy.metrics import (
    EnvironmentEvaluator,
    InitialStateValueEstimationEvaluator,
    TDErrorEvaluator,
)
from d3rlpy.ope import FQE, FQEConfig


def main() -> None:
    dataset, env = get_minari("mujoco/halfcheetah/medium-v0")
    device = "cuda:0" if os.environ.get("USE_CUDA") == "1" else False

    evaluators = {
        "environment": EnvironmentEvaluator(env, n_trials=3),
        "td_error": TDErrorEvaluator(episodes=dataset.episodes),
    }

    bc = BCConfig(
        batch_size=256,
        learning_rate=1e-3,
    ).create(device=device)

    bc.fit(
        dataset,
        n_steps=10000,
        n_steps_per_epoch=2500,
        evaluators=evaluators,
    )

    cql = CQLConfig(
        batch_size=256,
        conservative_weight=5.0,
        actor_learning_rate=1e-4,
        critic_learning_rate=3e-4,
    ).create(device=device)

    cql.fit(
        dataset,
        n_steps=20000,
        n_steps_per_epoch=5000,
        evaluators=evaluators,
    )

    fqe = FQE(algo=cql, config=FQEConfig())
    fqe.fit(
        dataset,
        n_steps=10000,
        n_steps_per_epoch=2500,
        evaluators={
            "init_value": InitialStateValueEstimationEvaluator(),
        },
    )

    cql.save("cql_halfcheetah_medium_v2.d3")


if __name__ == "__main__":
    main()
```

Install commands vary by workstation, especially around MuJoCo and the Minari dataset backend. For a local experiment environment, start
with an isolated virtual environment and pin the RL library version you are testing.

```bash
.venv/bin/python -m pip install "d3rlpy==2.8.1"
.venv/bin/python -m pip install "minari[all]"
.venv/bin/python offline_halfcheetah.py
```

If dataset installation fails, do not rewrite the learning code first. Resolve the Minari/benchmark dependency, MuJoCo runtime,
and Python-version compatibility. Offline RL results are already noisy enough without silently changing datasets.

For discrete-action datasets, switch to the discrete algorithm configs.

```python
from d3rlpy.algos import DiscreteBCQConfig, DiscreteCQLConfig

discrete_cql = DiscreteCQLConfig(alpha=1.0).create(device=False)
discrete_bcq = DiscreteBCQConfig().create(device=False)
```

The library does not remove the need for judgment. Use d3rlpy to run disciplined experiments, not to outsource the
decision of whether the dataset supports policy improvement.

## Section 10: D4RL benchmarks — what the community measures on

D4RL is the benchmark suite most associated with offline RL practice and papers. It provides fixed datasets for
environments such as MuJoCo locomotion, AntMaze, Adroit manipulation, and other domains where data quality and
coverage vary deliberately.

The key contribution is not just "more datasets." It is the ability to test algorithms under different dataset
regimes: medium behavior, expert behavior, mixed behavior, random behavior, and narrow trajectory coverage.

That matters because offline RL methods can look strong in one data regime and weak in another. A method that excels
on expert demonstrations may not handle mixed-quality logs. A method that improves on medium data may fail when
coverage is too narrow. A method that handles locomotion may not handle sparse-reward navigation.

| D4RL-style dataset regime | Production analogy | Expected difficulty |
|---|---|---|
| Expert | Strong human or policy demonstrations | BC can be hard to beat |
| Medium | Imperfect deployed policy logs | Offline RL may improve selectively |
| Random | Exploratory or low-quality behavior | Coverage may be broad but reward signal weak |
| Mixed | Multiple behavior policies | Strong fit for methods that identify good behavior |
| Sparse navigation | Rewards rarely observed | Evaluation and credit assignment become harder |

D4RL scores are useful for method comparison, but they are not production evidence by themselves. A benchmark
environment has known dynamics, repeatable resets, and cleaner logging than many real systems. Your product logs may
contain policy changes, delayed rewards, partial observability, feature backfills, and hidden action filters.

Use D4RL for fluency. Use your own coverage audits for deployment decisions.

## Section 11: Offline RL evaluation — decide how to gate deployment without online A/B tests

Offline evaluation is the uncomfortable center of offline RL. Training a policy from logs is hard. Knowing whether the
policy is better without deploying it is harder.

The gold standard is still an online experiment in the target environment. But this module exists because that
experiment may be unsafe, unethical, too expensive, or only allowed after strong offline evidence.

Fitted Q Evaluation trains a value function for a fixed candidate policy using the offline dataset. Instead of
learning a policy, FQE estimates the return of a policy you already trained. This is appealing because it uses dynamic
programming structure rather than only trajectory-level reweighting.

The risk is familiar. FQE is still a learned value estimator. If the candidate policy chooses unsupported actions, the
FQE estimate can be unreliable. FQE is a useful gate, not an oracle.

Weighted importance sampling takes a different route. If you know the probability that the behavior policy chose each
logged action, and the probability that the target policy would choose that same action, you can reweight observed
returns.

```python
import numpy as np


def weighted_importance_sampling(
    episode_returns: np.ndarray,
    target_action_probs: list[np.ndarray],
    behavior_action_probs: list[np.ndarray],
) -> float:
    weights = []
    for target_probs, behavior_probs in zip(target_action_probs, behavior_action_probs):
        ratio = np.prod(target_probs / np.clip(behavior_probs, 1e-8, None))
        weights.append(ratio)

    weights_array = np.asarray(weights, dtype=float)
    normalized = weights_array / np.clip(weights_array.sum(), 1e-8, None)
    return float(np.sum(normalized * episode_returns))
```

This function is runnable, but it hides the production difficulty in the inputs. You need behavior propensities. Many
logs do not contain them. If the old policy was deterministic, rule-based, or changed over time, the required
probabilities may be unavailable or untrustworthy.

Importance weights can also explode over long horizons. A small probability mismatch at each step multiplies across
the trajectory. Weighted variants reduce variance, but they do not create overlap where none exists.

A practical offline evaluation stack often combines: behavior-cloning baseline, dataset support diagnostics, FQE,
importance-sampling checks when propensities exist, stress tests by segment, and a guarded online rollout only after
the offline story is coherent.

Do not let a single offline number carry the decision. The correct question is not, "Which metric says this policy is
best?" It is, "What evidence would have to be false for this policy to be unsafe?"

Evaluating offline-trained policies safely usually means stacking imperfect gates rather than trusting one score. Start with dataset diagnostics: action coverage, segment-level return, and whether a behavior-cloning model can reproduce logged actions. Add off-policy evaluation when propensities exist, FQE or similar value estimators for a candidate policy, and stress tests on slices where hidden confounding is plausible. Reserve guarded online rollouts—shadow mode, small cohort A/B tests, or human-in-the-loop approval—for policies that already pass conservative offline checks. When online A/B testing is unavailable or ethically blocked, document explicitly which assumptions each offline metric requires and what failure would look like in production.

## Section 12: When offline RL is the wrong tool

Offline RL is wrong when the data cannot answer the intervention question. That sounds abstract, so make it
operational.

If the logged policy almost never tried alternative actions, the data is too narrow. If high rewards appear only in
states where hidden human judgment selected the action, the state is incomplete. If the reward is delayed beyond the
logging window, the return is truncated. If the product changed after the logs were collected, the environment is
nonstationary.

Offline RL is also wrong when supervised learning is enough. If the desired output is a one-step action label and
matching experts is acceptable, behavior cloning or ordinary supervised learning is cheaper and easier to validate.

It is wrong when stakeholders need a causal claim that the data cannot identify. Offline RL can optimize a policy
estimate, but it does not magically solve confounding. The causal framing in [Module 2.7: Causal Inference for ML Practitioners](../../machine-learning/module-2.7-causal-inference-for-ml-practitioners/) still applies.

It is wrong when the cost of a bad policy is high and there is no safe evaluation path. No algorithm name should
override that.

| Situation | Better move |
|---|---|
| Logs contain only one action per state type | Collect broader data or stay with the current policy |
| Demonstrations are strong and deployment stays close | Start with behavior cloning |
| Hidden confounders drove historical actions | Fix logging and state representation first |
| Reward is a weak proxy for the real objective | Redesign the reward or use human review |
| Online experiment is possible but expensive | Use offline RL as a filter, not as final proof |
| Dataset comes from an obsolete product surface | Treat old logs as research data, not deployment evidence |

The hardest production answer is often: "We should not train this yet." That answer can save months of work and prevent a false sense of safety. When stakeholders push for training anyway, translate the coverage audit into operational language: which actions would the new policy take that the logs never tried, which segments lack high-return examples, and what offline gate would need to pass before any guarded online test.

## Section 13: Connecting back — bridging to RLHF and causal inference

RLHF is one reason offline RL matters to modern AI practitioners outside robotics and control. In [Module 1.4: RLHF & Alignment](../../advanced-genai/module-1.4-rlhf-alignment/), language-model behavior is shaped from human preferences,
rankings, and feedback data rather than from a simple hand-written reward. That workflow has a family resemblance to
offline and preference-based RL: learn from logged or collected judgments, avoid unsafe exploration in front of users,
and regularize the updated policy so it does not drift too far from a capable base model.

The details differ. Language models use token policies, preference models, KL penalties, and specialized optimization
methods. But the same production instinct appears: do not trust unconstrained optimization of a learned reward. Keep
the policy near a trusted reference unless evidence supports movement.

Causal inference is the other bridge. Offline RL asks, "What policy should we use if we cannot freely intervene during
learning?" Causal inference asks, "What would happen under an intervention we did not observe for everyone?" Both are
about learning from observational data without pretending it was randomized.

The difference is horizon and optimization. Causal inference often estimates an effect of a treatment or policy
contrast. Offline RL tries to learn a sequential decision rule. That adds future state distributions, credit
assignment, and policy-induced covariate shift.

If you remember one connection, make it this: offline RL is not an escape hatch from causal assumptions. It is a
harder setting where those assumptions can fail repeatedly over time.

Production teams sometimes treat offline RL as a way to skip the uncomfortable parts of online learning while still claiming policy improvement. The honest framing is narrower: you are estimating what would happen if you deployed a different policy, using evidence that was never collected for that purpose. Document the behavior policy, the logging window, missing variables, and the offline gates you require before any live test. That documentation is part of the model, not paperwork around it. A one-page deployment memo that names unsupported action regions is often worth more than another week of offline training on the same narrow logs.

## Did You Know?

- **D4RL was designed to make offline RL fail visibly**: its datasets include narrow, mixed, random, and sparse-reward regimes so methods cannot look good only on clean expert demonstrations.
- **Behavior cloning can beat offline RL on expert data**: when demonstrations are already strong and coverage is narrow, value optimization may add more risk than benefit.
- **Importance sampling needs behavior probabilities**: many production logs record the chosen action but not the probability that the old policy assigned to it, which blocks a whole evaluation family.
- **CQL, BCQ, IQL, and TD3+BC all encode distrust**: their differences are mostly about where to place that distrust: the Q-values, the action set, the policy extraction step, or the actor objective.

## Common Mistakes

| Mistake | What goes wrong | Better practice |
|---|---|---|
| Treating offline RL as online RL with saved data | The policy exploits unsupported actions | Audit action support before training claims |
| Skipping behavior cloning | You miss the simplest baseline and dataset audit | Train BC first and require offline RL to beat it honestly |
| Trusting held-out transition loss | Good one-step prediction does not prove policy value | Combine support checks, FQE, and policy-level evaluation |
| Ignoring behavior propensities | Importance-sampling estimates become impossible or fictional | Log action probabilities for future decision systems |
| Using D4RL score as production proof | Benchmarks do not represent your logging process | Treat D4RL as fluency, not deployment evidence |
| Regularizing toward unsafe logs | The policy preserves historical bias or bad practice | Audit the behavior policy before imitating it |
| Claiming causal improvement from observational logs | Confounding is rebranded as policy learning | State the identification assumptions explicitly |
| Letting a learned reward drive unconstrained optimization | The policy finds reward-model loopholes | Use conservative updates and human review gates |

## Quiz

1. **A recommender team has logs from a deterministic ranking policy. The new offline RL policy improves FQE estimates but chooses items that the old policy almost never showed to similar users. Should the team ship?**

   <details>
   <summary>Answer</summary>
   No. The FQE result is not enough because the candidate policy is leaving the support of the logged behavior. The team should inspect coverage, compare against behavior cloning, segment the unsupported actions, and collect guarded exploration data before making a broad rollout decision.
   </details>

2. **A robot has expert teleoperation demonstrations with high-quality actions, but no reward function. The deployment environment is close to the demonstration environment. Which baseline should come first?**

   <details>
   <summary>Answer</summary>
   Behavior cloning should come first. The data is expert-labeled action supervision, and matching the expert may already solve the task. More complex imitation or offline RL should be justified only if BC fails in states that matter or if improvement beyond the expert is required.
   </details>

3. **A clinical dataset records treatment choices and outcomes, but not several bedside observations clinicians used when choosing treatments. What is the main risk for offline RL?**

   <details>
   <summary>Answer</summary>
   Hidden confounding and incomplete state. The model may attribute outcomes to treatment actions while missing the clinical context that caused those actions. The correct move is to improve state representation and causal assumptions before treating the logs as sufficient policy evidence.
   </details>

4. **An offline policy has strong benchmark performance on `halfcheetah-medium-v2`. A stakeholder asks whether that proves the same algorithm will work on marketplace pricing logs. How should you respond?**

   <details>
   <summary>Answer</summary>
   It proves only that the implementation can run and perform in a known benchmark regime. Marketplace pricing has different state coverage, hidden confounding, delayed rewards, strategic users, and business constraints. The production dataset needs its own support and evaluation analysis.
   </details>

5. **A team wants to use DAgger, but experts are unavailable after the initial demonstration dataset is collected. What breaks?**

   <details>
   <summary>Answer</summary>
   DAgger's core loop breaks. It relies on expert labels for states the learner visits, especially learner-induced error states. Without ongoing expert correction, the team has behavior cloning or offline imitation, not DAgger.
   </details>

6. **A candidate TD3+BC policy stays close to logged actions and has lower estimated return than a less constrained actor. Which policy is safer to investigate first, and why?**

   <details>
   <summary>Answer</summary>
   The constrained policy is usually safer to investigate first because its actions are more supported by the data. The unconstrained actor may be exploiting critic optimism. The team can still study the higher-return policy, but it needs stronger support diagnostics before deployment consideration.
   </details>

7. **A product manager says the offline reward is "click within ten seconds," but the real objective is long-term user trust. What should happen before algorithm selection?**

   <details>
   <summary>Answer</summary>
   The reward definition must be revisited. Offline RL will optimize the logged reward signal, and a short-term click proxy can push harmful recommendations. The team should define a reward or evaluation gate closer to the real objective before choosing CQL, IQL, or any other method.
   </details>

8. **You must implement a small d3rlpy workflow on a Minari (D4RL-derived) dataset using the v2 configuration API. Online A/B testing is blocked until after an offline gate. What training order and evaluators would you use, and what would you decide before requesting any live rollout?**

   <details>
   <summary>Answer</summary>
   Train behavior cloning first as the imitation baseline, then a conservative method such as CQL with `CQLConfig(...).create()`, using `get_minari` for the fixed dataset and evaluators such as `EnvironmentEvaluator` plus FQE for off-policy value estimation. Before any online experiment, decide whether the candidate policy stays near logged action support, whether FQE and coverage diagnostics agree, and what guarded rollout evidence would be required if offline scores look promising.
   </details>

## Hands-On Exercise

**Task:** Train and evaluate a conservative offline RL policy on a Minari (D4RL-derived) continuous-control dataset using d3rlpy v2.

You will run behavior cloning first, then CQL, then FQE. The goal is not to chase leaderboard scores. The goal is to
practice the production workflow: baseline, conservative learner, offline evaluation, and a short deployment memo.

### Step 1: Prepare the environment

```bash
.venv/bin/python -m pip install "d3rlpy==2.8.1"
.venv/bin/python -m pip install "minari[all]"
```

If your workstation needs MuJoCo system packages, install them before changing the Python experiment. Dependency
errors are not policy-learning evidence.

### Step 2: Create `offline_halfcheetah.py`

```python
import os

from d3rlpy.algos import BCConfig, CQLConfig
from d3rlpy.datasets import get_minari
from d3rlpy.metrics import EnvironmentEvaluator, InitialStateValueEstimationEvaluator
from d3rlpy.ope import FQE, FQEConfig


def train() -> None:
    dataset, env = get_minari("mujoco/halfcheetah/medium-v0")
    device = "cuda:0" if os.environ.get("USE_CUDA") == "1" else False

    evaluator = EnvironmentEvaluator(env, n_trials=3)

    bc = BCConfig(batch_size=256, learning_rate=1e-3).create(device=device)
    bc.fit(
        dataset,
        n_steps=10000,
        n_steps_per_epoch=2500,
        evaluators={"environment": evaluator},
    )

    cql = CQLConfig(
        batch_size=256,
        conservative_weight=5.0,
        actor_learning_rate=1e-4,
        critic_learning_rate=3e-4,
    ).create(device=device)
    cql.fit(
        dataset,
        n_steps=20000,
        n_steps_per_epoch=5000,
        evaluators={"environment": evaluator},
    )

    fqe = FQE(algo=cql, config=FQEConfig())
    fqe.fit(
        dataset,
        n_steps=10000,
        n_steps_per_epoch=2500,
        evaluators={
            "init_value": InitialStateValueEstimationEvaluator(),
        },
    )

    cql.save("cql_halfcheetah_medium_v2.d3")


if __name__ == "__main__":
    train()
```

### Step 3: Run the experiment

```bash
.venv/bin/python offline_halfcheetah.py
```

### Step 4: Write the policy memo

In five to eight sentences, answer these questions:

- What did BC establish as the imitation baseline?
- Did CQL improve the evaluator signal enough to justify more investigation?
- Did the training logs show instability or collapse?
- What evidence would you require before using this method on a real logged decision system?
- Which actions or state regions would need support diagnostics?

### Success Criteria

- [ ] The script imports `BCConfig`, `CQLConfig`, `get_minari`, `EnvironmentEvaluator`, and `FQE` without using deprecated v1 constructors.
- [ ] The dataset name is `halfcheetah-medium-v2`.
- [ ] Behavior cloning trains before CQL.
- [ ] CQL uses a conservative weight rather than an unconstrained actor-only objective.
- [ ] FQE is trained after the candidate CQL policy exists.
- [ ] The run writes `cql_halfcheetah_medium_v2.d3`.
- [ ] Your memo explicitly says why benchmark evaluation is not production proof.
- [ ] Your memo names at least one coverage diagnostic you would require for real logs.

## Sources

- https://arxiv.org/abs/2005.01643
- https://arxiv.org/abs/1812.02900
- https://proceedings.neurips.cc/paper/2020/hash/0d2b2061826a5df3221116a5085a6052-Abstract.html
- https://arxiv.org/abs/2110.06169
- https://arxiv.org/abs/2106.06860
- https://arxiv.org/abs/2004.07219
- https://github.com/Farama-Foundation/D4RL
- https://arxiv.org/abs/1011.0686
- https://papers.nips.cc/paper/6391-generative-adversarial-imitation-learning
- https://arxiv.org/abs/1710.11248
- https://arxiv.org/abs/2005.05951
- https://arxiv.org/abs/2005.13239
- https://arxiv.org/abs/1511.03722
- https://arxiv.org/abs/2007.09055
- https://d3rlpy.readthedocs.io/en/v2.8.1/
- https://d3rlpy.readthedocs.io/en/v2.8.1/references/algos.html
- https://d3rlpy.readthedocs.io/en/v2.8.1/references/datasets.html
- https://d3rlpy.readthedocs.io/en/v2.8.1/references/off_policy_evaluation.html
- https://github.com/HumanCompatibleAI/imitation
- https://imitation.readthedocs.io/en/latest/

## Next Module

This completes the Reinforcement Learning track expansion planned for issue #677. There is no next RL module in this
issue; with Module 2.1 live, the ML/RL/DL curriculum expansion can close after orchestration and review.
