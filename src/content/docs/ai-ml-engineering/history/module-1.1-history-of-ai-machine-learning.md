---
title: "History of AI & Machine Learning"
slug: ai-ml-engineering/history/module-1.1-history-of-ai-machine-learning
sidebar:
  order: 1202
---
> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 4-5

## Learning Outcomes

- **Explain** the major shifts in AI from 1943 neural abstractions through modern foundation models.
- **Connect** key personalities to the technical mechanisms they advanced, not just to famous dates.
- **Diagnose** why the two AI Winters happened and how similar failure patterns can reappear today.
- **Evaluate** the Bitter Lesson as a design lens for compute, data, search, learning, and hand-coded knowledge.
- **Use** history to make more careful claims about AI systems, benchmarks, products, and limits.

---

## Why This Module Matters

In 2012, Alex Krizhevsky, Ilya Sutskever, and Geoffrey Hinton entered the ImageNet Large Scale Visual Recognition Challenge with a deep convolutional network now remembered as AlexNet. Their paper reports a winning top-5 test error rate of 15.3%, compared with 26.2% for the second-best entry, a margin large enough to make many computer vision researchers reconsider what counted as practical machine learning. That moment is real and citable; the lesson is not that one competition magically created modern AI, but that decades of ideas suddenly had enough data, compute, and training technique behind them to become operational.

The history of AI is not a smooth march from weak systems to strong systems. It is a cycle of ambitious theories, painful bottlenecks, rediscovered ideas, infrastructure jumps, funding swings, and changed evaluation targets. A learner who only sees the latest chatbot or image model can easily assume that progress comes from one clever architecture, one charismatic founder, or one benchmark win. A learner who studies the history sees something more useful: methods succeed when the surrounding ecosystem is ready for them, and methods fail when promises outrun mechanisms.

This module is a condensed survey, not a replacement for the full history course. KubeDojo's [History of AI book](/ai-history/) covers these milestones across dozens of focused chapters with primary sources, timelines, and deeper context. Here we move quickly, but we still ask the engineering question that matters: what changed in the problem formulation, available data, available compute, training method, funding environment, or evaluation culture that made each era rise or stall?

The practical value is humility. When a team claims that a demo proves general intelligence, history gives you Deep Blue, ELIZA, expert systems, and previous hype cycles as counterweights. When someone dismisses a currently awkward method as a dead end, history gives you neural networks, backpropagation, and GPUs as reminders that an idea can be early rather than wrong. The goal is not nostalgia; the goal is better technical judgment.

---

## Did You Know?

- **McCulloch and Pitts did not build a learning machine in 1943**; they built a logical abstraction showing how simplified neural units could implement computation.
- **The Dartmouth proposal was written in 1955 for a 1956 workshop**, which is why careful histories distinguish the naming proposal from the summer meeting itself.
- **The 1986 backpropagation revival did not immediately end the neural-network drought**; it supplied a training mechanism that still needed later data, compute, and engineering scale.
- **The Transformer paper was originally a machine-translation paper**, but its self-attention design became a general sequence-modeling primitive across language, vision, audio, code, and multimodal systems.

---

## Common Mistakes

| Mistake | Why it happens | How to fix |
|---------|----------------|------------|
| Treating AI history as a list of famous people | Names are easier to remember than mechanisms, so learners miss why each transition happened | Pair every person with the problem they attacked, the method they used, and the limitation they exposed |
| Calling one benchmark win proof of general intelligence | Benchmarks compress messy capability into a single headline | Ask what distribution, task boundary, data source, and evaluation rule the benchmark actually measured |
| Blaming AI Winters on one critic or one book | Winter narratives are tempting because they create villains | Track the full system: funding expectations, compute limits, brittle demos, weak evaluation, and unmet promises |
| Saying symbolic AI simply failed | Modern systems still use search, planning, tools, constraints, retrieval, and structured representations | Separate failed claims of generality from useful ideas that survived in narrower or hybrid forms |
| Assuming scale alone explains modern AI | Scaling worked because data pipelines, accelerators, architectures, optimization, and deployment practices matured together | Analyze the whole stack before copying a scaling story into a new domain |
| Treating current vendor rosters as durable history | Model names and product capabilities change faster than curriculum modules | Keep volatile facts in dated snapshots and verify against official docs before relying on specifics |

---

## Introduction: How to Read This Survey

The journey you're about to take spans more than eight decades, from handwritten logical models in the 1940s to systems that generate text, code, images, audio, and action plans. Along the way, you will meet researchers who asked whether machines could think, engineers who made machines search, scientists who taught machines from examples, and builders who turned research prototypes into systems used by millions. The through-line is not a single theory of intelligence; it is the repeated discovery that intelligence-like behavior depends on representation, feedback, scale, and the environment in which a system is evaluated.

Use the dates as anchors, but do not memorize them as trivia. The important pattern is causal: McCulloch and Pitts made neurons computable as logic, Turing made machine intelligence discussable as behavior, Dartmouth gave the field a name, Rosenblatt showed weights could be learned, Minsky and Papert exposed limits in a popular architecture, expert systems converted domain rules into products, statistical learning handled uncertainty better than brittle rules, and deep learning finally exploited large datasets and accelerator hardware. Each step answered a real limitation from the previous era while creating new limitations of its own.

This module keeps the survey compact by pointing outward when depth matters. The *Go deeper* notes link to the [AI History book](/ai-history/) for chapter-length treatments, including the mathematics of gradient descent, the politics of Cold War funding, the construction of ImageNet, and the alignment story behind RLHF. Read this module first to build the map, then use the book chapters when you need the terrain.

---

## Part 1: The Pre-Dawn (1943-1955)

For deeper context, read [Ch02 the universal machine](/ai-history/ch-02-the-universal-machine/), [Ch03 the physical bridge](/ai-history/ch-03-the-physical-bridge/), [Ch05 the neural abstraction](/ai-history/ch-05-the-neural-abstraction/), and [Ch10 the imitation game](/ai-history/ch-10-the-imitation-game/), which unpack Turing, Shannon, McCulloch, Pitts, and the early bridge between logic, communication, and behavior.

### The First Artificial Neuron (1943)

The story begins not with computers, but with a paper-and-pencil model of how neurons might compute. In 1943, neurophysiologist **Warren McCulloch** and logician **Walter Pitts** published ["A Logical Calculus of the Ideas Immanent in Nervous Activity"](https://link.springer.com/article/10.1007/BF02478259), proposing a deliberately simplified neuron that treated firing as an all-or-nothing logical event:

```
McCulloch-Pitts Neuron (1943)
=============================

Inputs: x₁, x₂, x₃ (binary: 0 or 1)
Weights: w₁, w₂, w₃ (can be +1 or -1)
Threshold: θ

Output = 1 if (w₁x₁ + w₂x₂ + w₃x₃) ≥ θ
         0 otherwise

This is essentially: weighted sum → threshold → binary output
```

This looks trivially simple today, but it was revolutionary because it connected biology, logic, and computation in one formal model. McCulloch and Pitts did not solve learning, perception, or intelligence, but they showed that networks of threshold units could represent logical operations. That gave later researchers a way to discuss brains and machines with the same mathematical vocabulary, even when the biological details were far more complex than the model.

Imagine the McCulloch-Pitts neuron like a single voter in an election—it receives inputs (arguments for and against), weighs them, and then casts a binary vote (yes or no). Just as a single voter can't make complex decisions alone, but millions of voters together can elect governments, individual artificial neurons seem limited but networks of them can solve surprisingly complex problems.

The key limitation was just as important as the breakthrough. These units did not learn from examples; a designer had to decide the wiring and thresholds. That means the 1943 paper belongs to the history of representation before it belongs to the history of training. Modern neural networks inherit the threshold-and-network intuition, but they add differentiable weights, data-driven optimization, and enormous compute that the original model did not contain.

### Alan Turing's Foundation (1950)

In 1950, **Alan Turing** published ["Computing Machinery and Intelligence"](https://courses.cs.umbc.edu/471/papers/turing.pdf), one of the most influential papers in the history of AI. He opened by asking whether machines can think, then immediately shifted away from arguing over definitions and toward a behavioral test that could be operationalized.

Rather than defining "thinking," Turing proposed a practical test: if a machine can participate in text conversation well enough that a human judge cannot reliably distinguish it from a person, then the machine has earned a form of behavioral credit. The point was not that conversation is the whole of intelligence. The point was that scientific debate needed an observable task rather than an endless argument over private mental states.

```
The Turing Test (1950)
======================

    Human Judge
         |
    [Conversation]
       /    \
   Human    Machine

If the judge can't reliably distinguish
the machine from the human, the machine
"passes" the test.
```

Turing also made a cautious prediction about short conversations by the end of the twentieth century, which is often quoted because it combines technical imagination with measurable evaluation. Later chatbot contests sometimes produced superficially convincing conversations, but those results usually depended on constrained settings, evasive strategies, or human willingness to anthropomorphize. The durable contribution was the evaluation mindset: define the behavior, specify the judge, and inspect the conditions under which a claim holds.

The same paper addressed objections that still echo today, including the Lovelace objection that machines can only do what they are instructed to do, and the consciousness objection that external behavior cannot prove inner experience. Turing did not settle those debates, but he changed their engineering shape. Instead of asking whether a machine truly has a mind, builders could ask what class of tasks a system can perform, under what interface, with what evidence.

### The Shannon-Turing Chess Connection (1950s)

Both **Claude Shannon** and **Alan Turing** worked on chess-playing procedures before general-purpose computers were ready to make chess feel practical. Shannon's 1950 paper ["Programming a Computer for Playing Chess"](https://www.computerhistory.org/chess/doc-431614f453dde/) treated chess as a search problem: enumerate possible moves, evaluate resulting positions, and choose the move that looks best under assumptions about the opponent.

```
Minimax Algorithm
=================

        MAX (your move)
       /    |    \
     MIN   MIN   MIN (opponent's moves)
    / \   / \   / \
  MAX MAX MAX MAX   (your responses)

Assume opponent plays optimally.
Choose the move that maximizes your
minimum guaranteed outcome.
```

Turing went further with a hand-executable chess procedure later known as Turochamp, developed with David Champernowne. Accounts of the 1952 game against Alick Glennie describe Turing effectively acting as the processor, stepping through the rules manually because available machines could not run the program. The result was not strong chess, but it showed how search, evaluation functions, and procedural play could turn a symbolic game into an AI laboratory.

Chess mattered because it was bounded, formal, and difficult. It gave researchers a world where legal moves were unambiguous, goals were clear, and human expertise was visible. That made it a recurring proving ground for AI, from Shannon and Turing through Deep Blue and AlphaZero. The same lesson appears repeatedly: a clean task can accelerate research, but success inside that task does not automatically transfer to open-ended intelligence.

---

## Part 2: The Birth of AI (1956)

For deeper context, read [Ch11 the summer AI named itself](/ai-history/ch-11-the-summer-ai-named-itself/), [Ch12 Logic Theorist and GPS](/ai-history/ch-12-logic-theorist-gps/), and [Ch13 the list processor](/ai-history/ch-13-the-list-processor/), which explain why a short proposal, theorem-proving demos, and Lisp mattered more than the workshop's small headcount.

### The Dartmouth Conference

In the summer of 1956, a small group of researchers gathered at Dartmouth College for a workshop whose influence far exceeded its size. The proposal, written in 1955 by **John McCarthy**, **Marvin Minsky**, **Nathaniel Rochester**, and **Claude Shannon**, introduced the term "Artificial Intelligence" and framed the field around the conjecture that features of intelligence could be described precisely enough for machines to simulate them.

> "We propose that a 2-month, 10-man study of artificial intelligence be carried out... The study is to proceed on the basis of the conjecture that every aspect of learning or any other feature of intelligence can in principle be so precisely described that a machine can be made to simulate it."

The commonly cited attendees and associated participants included researchers who later shaped symbolic reasoning, programming languages, cognitive psychology, and machine learning:
- **John McCarthy** (coined "AI," invented Lisp)
- **Marvin Minsky** (neural nets, frames, co-founded MIT AI Lab)
- **Claude Shannon** (information theory)
- **Herbert Simon** (bounded rationality, Nobel laureate)
- **Allen Newell** (cognitive architecture, GPS)
- **Arthur Samuel** (machine learning pioneer, checkers)

```
Dartmouth Conference (1956)
===========================

Location: Dartmouth College, Hanover, NH
Duration: ~5-week workshop (proposal planned 2 months)
Attendees: ~10 researchers
Funding: $7,500 awarded by the Rockefeller Foundation
         (the proposal requested $13,500)

Output: The field of "Artificial Intelligence" was born
```

The funding detail is worth getting right because it keeps the origin story proportional. McCarthy requested \$13,500 for a two-month study, while Rockefeller's Robert Morison offered \$7,500 for a shorter five-week gathering. The important thing about Dartmouth is not that it solved AI; it clearly did not. Its importance is that it gathered scattered work on logic, search, neural nets, automata, language, and abstraction under one research identity. Naming a field changes funding, conferences, hiring, textbooks, and standards of proof. It also creates a temptation to promise more coherence than the underlying science can yet provide.

### The Name "Artificial Intelligence"

John McCarthy chose the name "Artificial Intelligence" deliberately, and the name mattered because it separated the new project from nearby labels such as cybernetics, automata theory, information processing, and machine intelligence. Different labels would have emphasized different goals: feedback loops, formal machines, cognition, decision-making, or engineering performance.

- **Automata Studies** (too narrow)
- **Complex Information Processing** (too vague)
- **Machine Intelligence** (used in Britain)
- **Computational Rationality** (McCarthy's later preference)

McCarthy's choice helped create a research community with a bold identity, but it also loaded the field with an expectation problem. "Artificial intelligence" sounds like the target is human-like mind, not just reliable task performance. That mismatch between public language and technical reality would recur in every boom: systems achieved impressive narrow results, while the name encouraged outsiders to hear a stronger claim.

---

## Part 3: The Golden Age (1956-1969)

For deeper context, read [Ch14 the Perceptron](/ai-history/ch-14-the-perceptron/), [Ch15 the gradient descent concept](/ai-history/ch-15-the-gradient-descent-concept/), and [Ch16 the Cold War blank check](/ai-history/ch-16-the-cold-war-blank-check/), which show how neural learning, optimization, and Cold War funding reinforced each other before the first major correction.

### The Perceptron (1957)

In the late 1950s, psychologist **Frank Rosenblatt** at Cornell developed the **perceptron**, a learning system that adjusted weights from examples instead of relying only on hand-coded rules. The historically careful claim is not that it was the first conceivable learning idea, but that it became the emblem of trainable pattern recognition in early AI and received unusually public attention.

```
Rosenblatt's Perceptron (1957)
==============================

Inputs: x₁, x₂, ..., xₙ (real numbers)
Weights: w₁, w₂, ..., wₙ (learned!)
Bias: b

Output = 1 if (w₁x₁ + w₂x₂ + ... + wₙxₙ + b) > 0
         0 otherwise

LEARNING RULE:
If output is wrong:
  - Should be 1 but was 0: add inputs to weights
  - Should be 0 but was 1: subtract inputs from weights
```

The key innovation was that weights were learned from examples, not hand-coded one by one. Picture the perceptron's learning process like a musician tuning an instrument: each wrong output nudges the weights, just as each sour note nudges a tuning peg. Over many examples, linearly separable problems can converge to a boundary that produces correct outputs, which made the perceptron feel like a route from raw data to behavior.

Rosenblatt's group built hardware demonstrations of the idea, including versions of the Mark I Perceptron that used a grid of photocells and adjustable connections:

```
Mark I Perceptron (1958)
========================

400 photocells (20x20 image input)
     ↓
512 "association units" (random connections)
     ↓
8 output units (learned weights)
     ↓
Classification decision

Size: Filled a room
Power: Considerable
Speed: Slow by modern standards
But: It LEARNED from data!
```

Press coverage of the perceptron was sensational because the demo connected three powerful ideas: machines, brains, and learning. That publicity helped attract interest, but it also encouraged a public story that moved faster than the mathematics. The perceptron could learn useful linear classifiers; it could not solve arbitrary perception, language, planning, or common-sense reasoning.

### Symbolic AI: Logic and Search

While Rosenblatt pursued neural approaches, most AI researchers focused on **symbolic AI**, using logic, rules, and search algorithms. Symbolic AI started from a reasonable engineering intuition: if intelligence often looks like manipulating symbols, proving theorems, planning steps, and applying rules, then a machine that manipulates explicit symbolic structures might reproduce important parts of reasoning.

**Logic Theorist (1956)**, created by Allen Newell, Herbert Simon, and J. C. Shaw, showed how search through symbolic proof states could solve a constrained reasoning task. Histories often emphasize its proofs from *Principia Mathematica* because theorem proving made the system's success legible: either the proof followed, or it did not.

**General Problem Solver (GPS, 1959)**: Newell and Simon's attempt to create a general-purpose reasoning program using means-ends analysis:

```
General Problem Solver (1959)
=============================

Goal: Transform current state into goal state

Method (Means-Ends Analysis):
1. Find difference between current and goal
2. Find operator that reduces this difference
3. If operator's preconditions aren't met,
   recursively solve subproblem
4. Apply operator
5. Repeat until goal reached

Example: Missionaries and Cannibals puzzle
- Current: 3M, 3C on left bank
- Goal: All on right bank
- Constraint: Cannibals can't outnumber missionaries
```

**ELIZA (1966)**, created by Joseph Weizenbaum, simulated conversation through pattern matching and scripted transformations. Its famous DOCTOR script did not understand therapy, emotion, or biography; it reflected phrases back in a way that let users supply most of the meaning themselves:

```
ELIZA Pattern Matching
======================

User: "I am sad"
Pattern: "I am <X>"
Response: "How long have you been <X>?"
Output: "How long have you been sad?"

User: "My mother hates me"
Pattern: "My <relation> <X>"
Response: "Tell me more about your <relation>"
Output: "Tell me more about your mother"
```

Weizenbaum later warned that users could attribute more understanding to such systems than the mechanism justified. That warning is not obsolete. Modern systems are far more capable than ELIZA, but the psychological pattern remains: fluent interaction can cause people to infer agency, expertise, or care that the system may not possess.

### The Optimism of the Era

The 1960s were a time of extraordinary optimism in AI, partly because early tasks were chosen where symbolic search and formal representation worked unusually well. When a system proves theorems or solves puzzles, it is easy to extrapolate from a clean laboratory domain to messy human intelligence. Several famous predictions from this era now read as warnings about how benchmarks can distort expectations:

| Researcher | Prediction | Year |
|------------|------------|------|
| Herbert Simon | "Within 20 years machines will be capable of doing any work a man can do" | 1965 |
| Marvin Minsky | "Within a generation the problem of creating 'artificial intelligence' will be substantially solved" | 1967 |
| Marvin Minsky | Life magazine attributed to him: "In from three to eight years we will have a machine with the general intelligence of an average human being" | 1970 |

The 1970 Life magazine line should be treated as an attributed popular-press quotation rather than an uncontested transcript; Minsky later disputed the wording as printed. Those predictions were wrong for structural reasons, not because the researchers were careless or unintelligent. They underestimated the complexity of ordinary perception, the ambiguity of natural language, the amount of tacit world knowledge behind common sense, and the compute required to search large spaces. They also lacked evaluation cultures that separated a staged demo from a robust system.
1. **The complexity of common sense** - "Easy" things like vision and language were actually hardest
2. **The limits of symbolic AI** - Logic couldn't capture fuzzy, uncertain real-world knowledge
3. **The computational requirements** - Moore's Law would need decades more progress

---

## Part 4: The First AI Winter (1969-1980)

For deeper context, read [Ch17 the Perceptron's fall](/ai-history/ch-17-the-perceptron-s-fall/), [Ch18 the Lighthill devastation](/ai-history/ch-18-the-lighthill-devastation/), and [Ch19 rules, experts, and the knowledge bottleneck](/ai-history/ch-19-rules-experts-and-the-knowledge-bottleneck/), which separate the mathematical critique from the funding and expectation collapse around it.

Think of AI Winters like ice ages for technology—long periods where progress slows to a crawl, funding evaporates, and researchers either abandon the field or rebrand their work to survive. Just as ice ages were caused by specific triggers (orbital changes, volcanic eruptions), AI Winters had specific causes: overpromising, underfunding, and crushing critiques that made the entire field seem hopeless. Understanding these winters is crucial because the conditions that caused them—hype cycles followed by disappointment—can happen again.

### The Perceptrons Bombshell (1969)

In 1969, Marvin Minsky and Seymour Papert published *Perceptrons*, a mathematical analysis of what perceptron-style systems could and could not do. The book is often simplified into a morality tale, but the more useful lesson is about scope: a popular architecture had real limits, and the community did not yet have a widely practical method for training multi-layer networks at scale.

The canonical classroom example is that a single-layer perceptron cannot learn XOR:

```
The XOR Problem
===============

Input A  Input B  Output
   0        0        0
   0        1        1
   1        0        1
   1        1        0

No single line can separate
the 1s from the 0s:

  B
  1 |  1    0
    |
  0 |  0    1
    +--------
       0    1   A

The 1s (at [0,1] and [1,0]) aren't
linearly separable from the 0s.
```

This seems trivial, but XOR represents any problem where the output depends on a **complex combination** of inputs rather than simple thresholds. Real-world patterns often have this structure.

The critique mattered because XOR stands for a broader class of problems where simple linear thresholds are not enough. Multi-layer networks can represent such functions, but representation is not the same as trainability. Without reliable training procedures, adequate data, and enough compute, the fact that a deeper network could in principle solve a problem did not make it an attractive research investment in the 1970s.

### The Lighthill Report (1973)

In 1973, mathematician **James Lighthill** prepared a skeptical survey of AI research for Britain's Science Research Council. His report became influential because it attacked not only particular techniques, but the gap between public claims and delivered impact:

> "In no part of the field have discoveries made so far produced the major impact that was then promised."

Lighthill criticized AI's failure to handle the **combinatorial explosion**: as problems grew, naive search spaces could become astronomically large. This was not a minor implementation detail. It meant that many symbolic systems looked intelligent on toy domains but became impractical when moved into richer worlds with more objects, relations, exceptions, and possible actions.

```
The Combinatorial Explosion
===========================

Chess positions:     ~10^120 possible games
Go positions:        ~10^170 possible games
English sentences:   Essentially infinite

Brute-force search fails!
1960s AI had no good answer.
```

The Lighthill Report contributed to a sharp reduction in British AI support and became one of the landmarks of the first AI Winter. In the United States, neural-network enthusiasm had already been weakened by the perceptron critique and by unmet promises. Together these pressures taught funders a painful lesson: ambitious names and impressive demos do not guarantee scalable methods.

### What Survived

Not all AI research stopped. **Expert systems** began emerging as a more constrained strategy: instead of promising general intelligence, encode expert knowledge for a narrow domain and provide explanations for the system's recommendations. This shift was pragmatic. If common sense was too broad, perhaps specialized professional knowledge could be captured one rule at a time.

```
DENDRAL (1965-1983)
===================

Domain: Chemical structure identification
Input: Mass spectrometry data
Output: Possible molecular structures

Method: Encoded rules from expert chemists
"If peak at mass X with intensity Y,
 then likely contains functional group Z"

Success: Performed as well as human experts
         in its narrow domain
```

MYCIN, developed at Stanford in the 1970s, advised on certain bacterial infections and antibiotic choices using rules plus uncertainty estimates. Its historical importance is not that hospitals deployed it widely; they did not. Its importance is that it demonstrated how narrow expertise, explicit rules, and explanation facilities could make AI useful inside a carefully bounded professional workflow.

---

## Part 5: The Expert Systems Boom (1980-1987)

For deeper context, read [Ch21 the rule-based fortune](/ai-history/ch-21-the-rule-based-fortune/), [Ch22 the Lisp machine bubble](/ai-history/ch-22-the-lisp-machine-bubble/), and [Ch23 the Japanese threat](/ai-history/ch-23-the-japanese-threat/), which explain why narrow rule systems became commercially attractive before their maintenance costs became obvious.

### Expert Systems Go Commercial

In the early 1980s, AI came roaring back in a more business-friendly form. **Expert systems** promised to capture human expertise and package it in software, which made the value proposition easier to explain to executives than general intelligence ever had been. A rule-based system could configure products, advise technicians, or support diagnosis without pretending to understand the whole world.

```
Expert System Architecture
==========================

KNOWLEDGE BASE          INFERENCE ENGINE
(domain facts &    +    (applies rules
 if-then rules)         to reach conclusions)
      ↓                        ↓
              USER INTERFACE
              (explains reasoning)

Example Rule (MYCIN):
IF: The infection is primary-bacteremia
AND: The site of culture is sterile
AND: The suspected portal is GI tract
THEN: There is evidence (0.7) that
      the organism is Bacteroides
```

Companies such as **Symbolics**, **Lisp Machines Inc.**, and **Teknowledge** sold specialized AI hardware and software into a market that believed knowledge engineering could become a repeatable industrial practice. **Japan's Fifth Generation Computer Project**, launched in the early 1980s, intensified that belief by presenting AI and logic programming as strategic national technologies. The international response showed how AI funding is often shaped by geopolitical fear as much as by measured technical readiness.

**R1/XCON** at Digital Equipment Corporation showed the commercial potential of rules when the domain was narrow, expensive, and repetitive:

```
R1/XCON (1980-1989)
===================

Task: Configure VAX computer systems
Rules: Started with 750, grew to 10,000+
Savings: DEC's broader expert-systems program
         was estimated at ~$40 million/year
Impact: Validated expert systems commercially
```

Investment followed the success stories, but the boom carried an assumption that did not generalize: if experts could explain their reasoning, knowledge engineers could extract it, encode it, and maintain it. In practice, much professional skill is tacit, exception-heavy, and context-dependent. The more rules a system accumulated, the more the rule base itself became a complex software artifact requiring debugging, governance, and change management.

### The Lisp Machine Era

For a brief period, specialized **Lisp machines** were the hardware of choice for AI because Lisp supported symbolic manipulation, interactive development, and dynamic programming styles that fit expert-system work:

```
Symbolics 3600 (1983)
=====================

Purpose: Run Lisp (the AI language) fast
CPU: Custom tagged architecture
Memory: 256KB - 8MB
Display: High-resolution graphics
Price: $100,000+
Buyers: AI labs, Wall Street, defense

Peak: ~7,000 installed worldwide
      (all vendors) by 1988
```

These machines had specialized hardware for running Lisp efficiently, with features such as tagged memory, garbage collection support, and integrated development environments. The bet was reasonable for a moment: if AI software needed Lisp and Lisp needed special machines, then the AI hardware market might grow with the expert-system market.
- **Tagged memory** (every word knew its type)
- **Hardware garbage collection** (automatic memory management)
- **Integrated development environments** (Symbolics Genera was legendary)

The fragility was that general-purpose computing was improving quickly. As Unix workstations and commodity machines gained performance, the special-purpose Lisp-machine advantage shrank. This is another recurring AI infrastructure lesson: accelerators and specialized stacks can be decisive when they match a workload, but they are vulnerable when general platforms become good enough at lower cost.

---

## Part 6: The Second AI Winter (1987-1993)

For deeper context, read [Ch28 the second AI winter](/ai-history/ch-28-the-second-ai-winter/), which follows the collapse of the expert-system market, the Lisp-machine business model, and the public appetite for the word "AI."

### The Collapse

The expert systems boom collapsed even faster than it had grown because the first deployments exposed costs that early success stories had hidden. Rule bases did not merely need to be created; they had to be updated as products changed, exceptions appeared, experts disagreed, and business processes evolved. That maintenance burden collided with a hardware market that no longer needed expensive specialized Lisp workstations.

```
Timeline of Collapse
====================

1987: Lisp machine market crashes
      - General-purpose workstations got fast enough
      - Apple, Sun, HP offered better price/performance

1988: Expert system limitations become clear
      - Couldn't learn from data
      - Knowledge acquisition "bottleneck"
      - Brittle: failed on edge cases

1989: Fifth Generation Project scaling back
      - Goals unmet
      - Parallel logic programming proved impractical

1990-1993: "AI Winter" in full effect
      - Funding cuts across government and industry
      - Researchers avoid using "AI" in proposals
```

The fundamental problems were linked rather than independent:

1. **Knowledge Acquisition Bottleneck**: Extracting expert knowledge was slow and expensive
2. **Brittleness**: Systems failed ungracefully on inputs outside their training
3. **No Learning**: Expert systems couldn't improve from experience
4. **Maintenance Nightmare**: Thousands of rules became extremely difficult to maintain

During the winter, many researchers avoided the grand label "AI" even when they continued working on learning, planning, speech, vision, or reasoning. This was not merely cosmetic. Labels influence grant review, hiring, customer trust, and press coverage. When a label becomes associated with inflated promises, serious work often survives by using narrower terms that make fewer public claims.

### What Kept Going

Despite the winter, important research continued in forms that would later become central. The lesson is that a field can be commercially cold while scientifically alive. Funding and fashion may punish a label, but useful mathematical tools can keep improving quietly until the surrounding infrastructure catches up.

**Backpropagation Revival (1986)**: Rumelhart, Hinton, and Williams published "Learning representations by back-propagating errors," showing how to train multi-layer neural networks:

```
Backpropagation (1986)
======================

Forward Pass:
Input → Hidden Layer → Output → Loss

Backward Pass:
Loss → ∂L/∂output → ∂L/∂hidden → ∂L/∂input

Key Insight: Chain rule lets us compute
gradients for hidden layers!

Update: weights -= learning_rate × gradient
```

Backpropagation addressed the training problem that made multi-layer networks unattractive after the perceptron critique, but it did not instantly make deep learning dominant. The algorithm needed differentiable architectures, useful datasets, better initialization, regularization, faster hardware, and enough patience to train networks that were still small by modern standards. A mechanism can be necessary without being sufficient.

**Statistical Methods Rise**: while symbolic AI struggled, statistical approaches gained ground because they handled uncertainty, noise, and data better than brittle hand-written rules. Speech recognition, information retrieval, classification, and probabilistic modeling all benefited from treating intelligence less like theorem proving and more like inference under uncertainty.
- **Hidden Markov Models** (HMMs) for speech recognition
- **Support Vector Machines** (SVMs) for classification
- **Probabilistic graphical models** for uncertainty

Geoffrey Hinton and other connectionist researchers kept developing neural methods while the approach was unfashionable in many circles. That persistence matters, but it should not be romanticized as one person defeating a field. The later breakthrough required a community, better hardware, benchmark datasets, open-source tooling, and a research culture ready to compare learned representations against engineered features.

---

## Part 7: The Machine Learning Renaissance (1990s-2000s)

For deeper context, read [Ch24 the math that waited](/ai-history/ch-24-the-math-that-waited-for-the-machine/), [Ch29 support vector machines](/ai-history/ch-29-support-vector-machines/), [Ch33 Deep Blue](/ai-history/ch-33-deep-blue/), [Ch34 the accidental corpus](/ai-history/ch-34-the-accidental-corpus/), [Ch37 distributing the compute](/ai-history/ch-37-distributing-the-compute/), and [Ch40 data becomes infrastructure](/ai-history/ch-40-data-becomes-infrastructure/), which connect statistical learning to web-scale data.

### The Quiet Revolution

While "AI" remained a risky label, machine learning researchers made steady progress by narrowing claims and improving evaluation. Instead of promising human-like intelligence, they asked whether a model improved classification, recognition, ranking, translation, or game play on a defined task. That shift made progress more measurable and less dependent on philosophical agreement.

**1997: Deep Blue Beats Kasparov.**

[IBM's Deep Blue defeated world chess champion Garry Kasparov in a six-game match](https://www.ibm.com/history/deep-blue), becoming a public symbol of machine competence:

```
Deep Blue (1997)
================

Hardware: 30 IBM RS/6000 processors
          480 custom chess chips
Speed: 200 million positions/second
Method: Alpha-beta search + evaluation function
Depth: 6-12 moves (up to 40 in some lines)

Game 6: Kasparov resigned after 19 moves
(in a difficult, rapidly collapsed position)
```

This was a **symbolic AI triumph** built from search, hand-crafted evaluation functions, opening knowledge, endgame knowledge, and specialized hardware. It did not learn chess from self-play in the modern reinforcement-learning sense. That makes Deep Blue historically important for two reasons: it showed that narrow superhuman performance was possible, and it showed that narrow superhuman performance was not the same thing as general intelligence.

**1997: LSTM Invented.**

While Deep Blue made headlines, **Sepp Hochreiter and Jürgen Schmidhuber** published "Long Short-Term Memory," addressing the vanishing-gradient problem for recurrent neural networks. LSTM mattered because sequence tasks often require information from much earlier timesteps, and ordinary recurrent networks struggled to preserve useful gradient signals across long spans.

```
LSTM Cell (1997)
================

The Problem:
Standard RNNs can't learn long-range dependencies
Gradients vanish or explode over many timesteps

The Solution: Gated memory cells

Cell State: ──────────────────────────→
                ↑          ↑
            Forget Gate   Input Gate
            (what to      (what to
             forget)       remember)

Output: controlled by Output Gate

Key: Gradients can flow unchanged through cell state!
```

LSTMs later became important in speech recognition, machine translation, and text generation, but the delay is the point. A good idea can wait years for data, hardware, tooling, and adjacent methods to make it widely useful. This is why history is dangerous when told only as a sequence of inventions; invention and adoption are different events.

### The Data Revolution

The late 1990s and 2000s brought something AI had often lacked: **massive amounts of data**. The web, digital cameras, search logs, speech corpora, and later smartphones changed machine learning from an algorithm-only discipline into a data-and-infrastructure discipline. Algorithms still mattered, but the advantage increasingly came from building pipelines that could collect, clean, label, store, and evaluate examples at scale.

```
The Data Explosion
==================

The practical change was not one magic number.
It was the arrival of many machine-readable traces:

- Web pages, links, and search logs
- Digital photos, video, and speech recordings
- Social-media and e-commerce interactions
- Smartphone sensors and location-aware apps
- Large benchmark datasets and web crawls
```

**ImageNet (2009)**: Fei-Fei Li's team and collaborators created ImageNet, a large labeled image database organized around WordNet categories that became a key benchmark for computer vision:

```
ImageNet
========

Images: 14+ million
Categories: 21,841 (WordNet synsets)
Labeled By: Amazon Mechanical Turk
Cost: Years of effort
Purpose: Enable visual recognition research

ImageNet Challenge (ILSVRC):
- Started 2010
- 1000 categories
- 1.2 million training images
- Became THE benchmark for computer vision
```

ImageNet's significance was not just size. It converted computer vision progress into an annual, shared comparison with enough data to reward representation learning. Once a benchmark becomes trusted, it changes what researchers optimize, what reviewers accept as evidence, and what engineering teams consider worth implementing.

### Support Vector Machines Dominate

Before deep learning's resurgence, **support vector machines** were a go-to algorithm for classification because they combined strong theory with good empirical performance on many small-to-medium datasets. They also fit the era's dominant pattern: engineer useful features, then train a mathematically well-understood classifier on top.

```
SVM Key Idea
============

Find the hyperplane that maximizes
the margin between classes:

Class A:  o  o     |     x  x  :Class B
          o  o     |     x  x
               o   |   x
          ←margin→ |

The "support vectors" are the points
closest to the decision boundary.

Kernel Trick: Map data to higher dimensions
where it becomes linearly separable!
```

SVMs are worth studying because they show what "best practice" looked like before representation learning took over. A strong pipeline often depended on a human choosing features that made the classes separable, then letting the classifier find a margin. Deep learning changed that balance by learning features and classifiers together, especially when data and compute were abundant.

---

## Part 8: The Deep Learning Revolution (2006-2012)

For deeper context, read [Ch41 the graphics hack](/ai-history/ch-41-the-graphics-hack/), [Ch42 CUDA](/ai-history/ch-42-cuda/), and [Ch43 the ImageNet smash](/ai-history/ch-43-the-imagenet-smash/), which explain why graphics processors and a benchmark dataset made old neural-network ideas newly effective.

Think of the deep learning revolution like the Wright Brothers' first flight—a moment when decades of failed attempts suddenly gave way to success, and everything that seemed impossible became merely difficult. The neural networks that had been written off as "dead ends" in the 1990s turned out to be just waiting for enough data and compute to reach their potential. Once those conditions were met, progress accelerated at a pace that shocked even the true believers.

### Hinton's Breakthrough (2006)

In 2006, **Geoffrey Hinton** and collaborators published "A Fast Learning Algorithm for Deep Belief Nets." The key engineering idea was to pre-train layers one at a time, then fine-tune the whole network. This mattered because deep networks were difficult to optimize directly with the hardware, initialization strategies, and datasets available at the time.

```
Deep Belief Net Training (2006)
===============================

Step 1: Train first layer unsupervised
Input → Layer 1 (RBM)

Step 2: Train second layer on Layer 1's output
Layer 1 output → Layer 2 (RBM)

Step 3: Continue stacking...

Step 4: Fine-tune entire network with backprop
```

Layer-wise pretraining helped by giving internal representations a useful starting point before supervised fine-tuning. It did not become the final recipe for all modern deep learning, but it reopened confidence that deep architectures could be trained. Historically, it is a bridge technique: important because it moved the field from shallow models and skepticism toward deeper learned representations.

### The AlexNet Earthquake (2012)

In 2012, **Alex Krizhevsky**, **Ilya Sutskever**, and **Geoffrey Hinton** entered the ImageNet competition with a deep convolutional neural network. The result is the right place to use a precise number because the paper itself reports the comparison:

```
AlexNet Results (2012)
======================

ILSVRC 2012 Top-5 Error Rate:

AlexNet:        15.3%  ← WINNER
Second place:   26.2%
                ↑
          11 percentage points!

This wasn't a small improvement.
This was a paradigm shift.

AlexNet Architecture:
- 8 layers (5 conv, 3 fully-connected)
- 60 million parameters
- ReLU activations (not sigmoid!)
- Dropout regularization
- Trained on 2 GPUs for 5–6 days
```

The AI community was stunned because the gain was too large to dismiss as a marginal tuning improvement. Within a few years, deep learning became the dominant approach in computer vision research, and the pattern spread into speech, translation, recommendation, robotics, and eventually language modeling.

The breakthrough worked because three factors converged at the same time:

1. **Data**: ImageNet provided millions of labeled images
2. **Compute**: GPUs (designed for gaming) happened to be perfect for neural networks
3. **Algorithms**: ReLU, dropout, and better initialization helped training

```
The Deep Learning Trinity
=========================

        DATA
       /    \
      /      \
COMPUTE ─── ALGORITHMS

All three had to reach critical mass together.
2012 was the year they did.
```

GPUs were not originally built for AI research, but the matrix-heavy computations needed for graphics mapped well onto the linear algebra inside neural networks. That hardware accident became an infrastructure shift. Once researchers could train larger models faster, algorithmic ideas that had seemed impractical became testable, and testable ideas could attract more data, funding, and engineering effort.

---

## Part 9: The Modern Era (2012-Present)

For deeper context, read [Ch44 the latent space](/ai-history/ch-44-the-latent-space/), [Ch50 Attention Is All You Need](/ai-history/ch-50-attention-is-all-you-need/), [Ch52 bidirectional context](/ai-history/ch-52-bidirectional-context/), [Ch53 the dawn of few-shot learning](/ai-history/ch-53-the-dawn-of-few-shot-learning/), [Ch55 the scaling laws](/ai-history/ch-55-the-scaling-laws/), [Ch57 the alignment problem](/ai-history/ch-57-the-alignment-problem/), and [Ch59 the product shock](/ai-history/ch-59-the-product-shock/), which turn this survey into a chapter-by-chapter modern AI path.

### The Deep Learning Tsunami (2012-2017)

After AlexNet, progress accelerated because computer vision researchers now had a strong recipe to iterate: deeper convolutional models, better regularization, larger training runs, improved normalization, and standardized ImageNet evaluation. "Exponential" is often used loosely here, so the safer claim is that measured benchmark progress was rapid and sustained for several years:

```
ImageNet Progress
=================

Year    Network      Top-5 Error    Layers
2012    AlexNet      15.3%          8
2014    VGGNet       7.3%           19
2014    GoogLeNet    6.7%           22
2015    ResNet       3.6%           152
2017    SENet        2.3%           Lots

Human Performance: ~5.1%

By 2015, machines surpassed humans
on ImageNet classification!
```

Several innovations made the gains practical rather than merely architectural:

- **VGGNet (2014)**: Showed that depth matters—just stack 3×3 convolutions
- **GoogLeNet (2014)**: Inception modules—parallel paths of different sizes
- **ResNet (2015)**: Skip connections—train networks with 1000+ layers
- **Batch Normalization (2015)**: Normalize activations, train faster

ResNet's skip connections were especially important because they changed the optimization problem. A very deep network no longer had to learn every transformation from scratch; residual blocks could learn changes relative to their inputs. That made it easier to train networks far deeper than earlier convolutional models and helped establish residual pathways as a general deep-learning design pattern.

### The Transformer Revolution (2017)

In June 2017, a team at Google published ["Attention Is All You Need"](https://arxiv.org/abs/1706.03762), introducing the **Transformer architecture**. The original context was sequence transduction for machine translation, but the architecture's deeper significance was that it made sequence modeling more parallelizable and gave models a direct way to relate every token to every other token.

```
Transformer Key Ideas
=====================

1. SELF-ATTENTION
   Every token attends to every other token
   Query, Key, Value projections
   Attention(Q,K,V) = softmax(QK^T/√d)V

2. NO RECURRENCE
   Process entire sequence in parallel
   Position encodings tell model about order

3. ENCODER-DECODER (for translation)
   Encoder: process source language
   Decoder: generate target language
   Cross-attention connects them

Result:
- Much faster training (parallelizable)
- Better long-range dependencies
- New SOTA on machine translation
```

The Transformer would become one of the most important architectural innovations in AI history because it fit the hardware and data regime of the scaling era. Recurrence processes sequences step by step, which limits parallel training. Self-attention is expensive in sequence length, but it lets training use accelerator hardware efficiently and gives the model flexible access to context.

### BERT and GPT: Language Transformers (2018)

[**BERT (2018)**](https://arxiv.org/abs/1810.04805) showed that pre-training on large text corpora could create powerful bidirectional language representations. Its masked-language-model objective let the model use both left and right context while learning, which made it useful for classification, question answering, named entity recognition, and other understanding-oriented tasks:

```
BERT Training
=============

Pre-training Tasks:
1. Masked Language Model (MLM)
   "The [MASK] sat on the mat" → "cat"

2. Next Sentence Prediction
   Do these sentences follow each other?

Pre-training Data: Wikipedia + Books
Parameters: 110M (base), 340M (large)

Fine-tuning: Add task-specific head
- Classification: [CLS] token → label
- QA: Predict start/end span
- NER: Token → entity type
```

[**GPT (2018)**](https://openai.com/index/language-unsupervised/) took a different approach: **autoregressive** language modeling. Compare it to how a novelist writes under a strict rule: rather than seeing the whole sentence bidirectionally like BERT during pre-training, GPT predicts the next token from the previous tokens, building continuation after continuation:

```
GPT Training
============

Task: Predict next token
"The cat sat on the" → "mat"

Just predict next word, over and over.
Train on internet text (WebText).

Generation: Sample from predictions
Input: "The cat"
P(next) = {sat: 0.3, ran: 0.2, meowed: 0.15, ...}
Sample → "sat"
Continue...
```

The GPT approach became central to powerful language generation because next-token prediction is simple, scalable, and compatible with enormous unlabeled text corpora. That simplicity is easy to underestimate. A task that looks almost too basic can force a model to learn syntax, facts, style, reasoning patterns, and code-like structures when the dataset and model are large enough.

### The Scaling Era (2019-2022)

**GPT-2 (2019)** showed that scaling an autoregressive Transformer produced qualitatively stronger text generation, while also triggering a public debate about staged release and misuse risk:

```
GPT Scaling
===========

Model      Parameters    Training Data
GPT-1      117M         ~5GB (BooksCorpus)
GPT-2      1.5B         40GB (WebText)
GPT-3      175B         570GB (Common Crawl+)

GPT-2 could:
- Write coherent paragraphs
- Answer questions (sometimes)
- Do simple math
- Generate code

OpenAI initially didn't release it,
citing concerns about misuse.
```

[**GPT-3 (2020)**](https://arxiv.org/abs/2005.14165) demonstrated that a 175-billion-parameter autoregressive language model could perform many tasks from prompts and examples without gradient updates. The careful claim is not that scale magically creates understanding, but that scaling changed the interface: users could describe a task in text and often get useful behavior without training a task-specific model.

```
GPT-3 Emergent Abilities
========================

Few-Shot Learning:
Give model a few examples, it generalizes!

Input:
"Translate English to French:
sea otter => loutre de mer
peppermint => menthe poivrée
cheese => "

Output: "fromage"

No fine-tuning needed!
Just demonstrate the task.
```

The term "emergent abilities" sparked debate because measurement thresholds can make gradual improvement look sudden. If a benchmark only counts an answer as correct after crossing a sharp accuracy line, a smooth underlying trend can appear discontinuous. That matters for forecasting: dramatic graphs may reflect real capability changes, evaluation artifacts, or both.

### ChatGPT: AI Goes Mainstream (November 2022)

On November 30, 2022, OpenAI released **ChatGPT**, presenting a conversational interface around an instruction-following language model. The technical family behind that moment included supervised instruction tuning and reinforcement learning from human feedback, both described in the InstructGPT line of work:

```
ChatGPT's Secret Sauce
======================

1. Large Language Model (GPT-3.5)
   Pre-trained on internet text

2. Instruction Fine-Tuning
   Train to follow instructions
   "Summarize this" → summary

3. RLHF (Reinforcement Learning from Human Feedback)
   Humans rank responses
   Train reward model on rankings
   Fine-tune LLM to maximize reward

Result: Helpful, harmless, honest
        (mostly)
```

ChatGPT's public impact came from packaging as much as from model capability. Earlier language models could produce impressive completions, but a chat interface made the system feel collaborative, interruptible, and broadly useful. That product lesson changed the industry: foundation models were no longer only research artifacts or API components; they became everyday interfaces for writing, coding, tutoring, search, analysis, and automation.

### The Current Moment (2023-Present)

We are now in an era where frontier systems change too quickly for undated prose to stay reliable. The durable pattern is not a particular product roster; it is the combination of foundation models, multimodal inputs, tool use, retrieval, agent loops, safety evaluations, and enormous infrastructure spending. Specific model names belong in a dated snapshot:

> **Landscape snapshot — as of 2026-06. This changes fast; verify against vendor docs before relying on specifics.**

| Family | Public documentation to verify | Why it appears in this survey |
|--------|--------------------------------|-------------------------------|
| OpenAI GPT models | OpenAI model and release pages | Illustrates closed frontier models, chat products, tool use, and instruction-following systems |
| Anthropic Claude models | Anthropic model documentation | Illustrates safety-focused frontier assistants, long-context workflows, and enterprise agent use cases |
| Google Gemini models | Google AI model documentation | Illustrates multimodal model families tied to search, developer APIs, and cloud workflows |
| Meta Llama models | Meta Llama documentation | Illustrates open-weight model releases and the ecosystem around local and self-hosted deployment |

This table is illustrative, not a leaderboard or endorsement. The point is that the modern era is not one model or one lab; it is an ecosystem of closed APIs, open-weight releases, cloud platforms, local inference stacks, retrieval systems, evaluation harnesses, and governance debates.

The limitations are equally durable. Modern systems can hallucinate, overfit to benchmark styles, fail under distribution shift, expose sensitive data through poor integrations, or act confidently without calibrated uncertainty. History should make you skeptical of both extremes: the claim that current systems are mere toys and the claim that current demos prove general intelligence.

---

## Part 10: The Key Personalities

People matter in AI history, but the safest way to teach personalities is to connect each person to a mechanism, institution, or research bet. Otherwise the story turns into founder mythology, and founder mythology hides the collaborative nature of the field. The names below are orientation points for further study, not a complete ranking of importance.

### The Founding Fathers

| Name | Contribution | Era |
|------|-------------|-----|
| **Alan Turing** | Turing Test, computation theory | 1936-1954 |
| **John McCarthy** | Coined "AI," invented Lisp, Stanford AI Lab | 1956-2011 |
| **Marvin Minsky** | Neural nets, frames, MIT AI Lab | 1956-2016 |
| **Claude Shannon** | Information theory, communication | 1940s-2001 |
| **Herbert Simon** | Bounded rationality, GPS, Nobel laureate | 1956-2001 |
| **Allen Newell** | Cognitive architecture, GPS, Soar | 1956-1992 |

### The Deep Learning Pioneers

| Name | Contribution | Era |
|------|-------------|-----|
| **Geoffrey Hinton** | Backprop, Boltzmann machines, deep learning | 1970s-present |
| **Yann LeCun** | CNNs, LeNet, self-supervised learning | 1980s-present |
| **Yoshua Bengio** | RNNs, attention, deep learning theory | 1990s-present |
| **Jürgen Schmidhuber** | LSTM, meta-learning, curiosity | 1990s-present |
| **Sepp Hochreiter** | LSTM, vanishing gradients | 1990s-present |

Hinton, LeCun, and Bengio received the **2018 ACM A.M. Turing Award** for conceptual and engineering breakthroughs that made deep neural networks central to computing. That recognition is useful historically because it came after decades in which neural networks moved from promising, to unfashionable, to dominant in several major application areas.

### The Modern Era Leaders

| Name | Contribution | Era |
|------|-------------|-----|
| **Fei-Fei Li** | ImageNet, AI4ALL, human-centered AI | 2000s-present |
| **Andrew Ng** | Coursera, Google Brain, Landing AI | 2000s-present |
| **Demis Hassabis** | DeepMind, AlphaGo, AlphaFold | 2010s-present |
| **Sam Altman** | OpenAI CEO, ChatGPT | 2010s-present |
| **Dario Amodei** | Anthropic CEO, AI safety | 2010s-present |
| **Ilya Sutskever** | AlexNet, GPT, OpenAI co-founder; former Chief Scientist (to 2024) | 2010s-present |
| **Andrej Karpathy** | Neural net education, Tesla AI | 2010s-present |

The modern leadership table is deliberately more volatile than the earlier tables. Company roles, lab affiliations, and product influence change quickly, so use it as a map of recent institutions rather than as a permanent canon. For durable understanding, focus on the research transitions: datasets, architectures, scaling laws, alignment methods, and deployment models.

---

## Part 11: The AI Winters—Lessons Learned

For deeper context, return to [Ch17 the Perceptron's fall](/ai-history/ch-17-the-perceptron-s-fall/), [Ch18 the Lighthill devastation](/ai-history/ch-18-the-lighthill-devastation/), and [Ch28 the second AI winter](/ai-history/ch-28-the-second-ai-winter/), which show that winters were not single-cause events.

### What Caused the Winters?

AI Winters are best understood as expectation failures, not as proof that progress stopped. A winter begins when a funding ecosystem believes a capability will arrive soon, invests around that belief, and then discovers that the underlying methods do not scale to real-world complexity. The visible trigger might be a critical book, a government report, a hardware market crash, or a failed flagship project, but the deeper cause is usually a mismatch between promise, mechanism, evaluation, and infrastructure.

```
AI Winter Causes
================

Winter 1 (1969-1980):
- Perceptrons book highlighted limitations
- Overpromising ("intelligent in a generation")
- Funding bodies lost patience
- Lighthill Report (UK, 1973)

Winter 2 (1987-1993):
- Expert systems didn't scale
- Knowledge acquisition bottleneck
- Lisp machine market collapse
- Fifth Generation Project failure
- Overpromising (again)

Common Pattern:
HYPE → OVERPROMISING → UNDERDELIVERING → BACKLASH → WINTER
```

### Lessons for Today

The first lesson is that capabilities are not the same as general intelligence. Deep Blue defeated Kasparov at chess, but it did not become a general game-playing colleague. A modern language model can write convincing prose, pass some benchmarks, and still fail under a small prompt change or an unfamiliar workflow. The right question is not "is it intelligent?" in the abstract; it is "what distribution of tasks has this system demonstrated, under what tools, with what failure modes, and with what human oversight?"

The second lesson is that extrapolation is dangerous when it ignores bottlenecks. Early symbolic AI underestimated common sense, perception, and combinatorial explosion. Expert-system vendors underestimated knowledge acquisition and maintenance. Modern AI teams can make the same mistake with data quality, evaluation leakage, inference cost, energy demand, copyright, security, safety, or user trust. A curve that rises quickly in one benchmark can flatten when it hits a bottleneck outside the benchmark.

The third lesson is that honest limitation-setting is not pessimism; it is winter prevention. If a team says a model is useful for drafting, retrieval-assisted analysis, code review, or narrow automation, users can test and adopt it responsibly. If the same team claims that the model replaces expertise everywhere, each failure becomes evidence that the entire field was overhyped. The winter pattern punishes inflated narratives more than it punishes careful engineering.

The final lesson is that winter does not mean death. Backpropagation, statistical speech recognition, probabilistic models, and neural-network research all continued through periods when "AI" was commercially unfashionable. A correction today would likely reduce weak products and exaggerated claims, but it would not erase the durable infrastructure: accelerators, open-source frameworks, datasets, evaluation methods, and a generation of engineers trained to build with learned systems.

---

## Part 12: The Bitter Lesson

> **Go deeper:** [Ch55 the scaling laws](/ai-history/ch-55-the-scaling-laws/) — covers Sutton's Bitter Lesson with the verbatim quote and the Kaplan equations that grounded it.

### Richard Sutton's Insight (2019)

In March 2019, reinforcement learning pioneer **Richard Sutton** published a short essay titled "The Bitter Lesson." His core argument:

> "The biggest lesson that can be read from 70 years of AI research is that general methods that leverage computation are ultimately the most effective, and by a large margin."

```
The Bitter Lesson
=================

What Researchers Wanted:
- Encode human knowledge
- Build expert systems
- Hand-craft features
- Design clever algorithms

What Actually Worked:
- General-purpose learning
- Massive scale
- Compute, compute, compute
- Let the model figure it out

Examples:
- Chess: Search + hardware beat knowledge
- Go: Learning beat hand-crafted evaluation
- Speech: Statistical models beat phonetics
- Vision: Neural nets beat feature engineering
- Language: Scaling beat linguistics

The "bitter" part: human knowledge
often helps less than scalable methods
over long horizons.
```

The lesson is bitter because researchers naturally want their domain insight to be the decisive ingredient. Expert knowledge feels elegant, interpretable, and intellectually satisfying. Sutton's historical claim is that methods able to use more computation—search and learning especially—keep improving as hardware and data grow, while hand-coded knowledge often gives an early advantage that becomes a ceiling.

### Evidence for the Bitter Lesson

**Chess** shows the progression clearly. Deep Blue used specialized search, evaluation, and hardware to defeat the world champion in 1997. Later systems pushed further toward learning and self-play, reducing dependence on hand-crafted chess knowledge. The historical arc is not that chess knowledge was useless; it is that scalable search and learning eventually mattered more.

**Go** made the point more dramatically because the search space was too large for the old brute-force style. AlphaGo combined deep learning with Monte Carlo tree search, while AlphaGo Zero learned from self-play without human game records. That result is one of the cleanest examples of a system improving by generating its own training curriculum inside a formal environment.

**Computer vision** moved from hand-crafted features such as SIFT and HOG toward learned representations once large labeled datasets and GPUs made deep convolutional networks practical. Feature engineering did not vanish because it was foolish; it vanished as the central bottleneck because learned features became better at exploiting scale.

**Natural language processing** followed a similar path. Linguistic rules, feature templates, and task-specific architectures gave way to large pre-trained Transformers adapted through prompting, fine-tuning, retrieval, and human feedback. Human knowledge still appears in dataset construction, architecture choices, evaluation design, safety policy, and product constraints, but it is no longer mainly encoded as brittle task rules.

The Bitter Lesson should not be turned into a slogan that "compute beats everything." Compute is expensive, environmentally consequential, and unevenly distributed. Human judgment still decides what to train, what to measure, what risks to accept, and where a system should not be deployed. A better reading is this: when you design an AI system, prefer methods that can improve with more data, more feedback, and more computation, unless you have a strong reason to lock in hand-coded assumptions.

---

## Part 13: Timeline Summary

```
Complete AI Timeline
====================

1943: McCulloch-Pitts neuron
1950: Turing Test proposed
1956: Dartmouth Conference - "AI" coined
1957: Perceptron invented (Rosenblatt)
1958: Mark I Perceptron hardware
1965: DENDRAL expert system
1966: ELIZA chatbot
1969: "Perceptrons" book → First AI Winter begins
1973: Lighthill Report (UK cuts funding)

1980: Expert systems boom begins
1982: Japan Fifth Generation Project announced
1986: Backpropagation paper (Rumelhart, Hinton, Williams)
1987: Lisp machine market crashes → Second AI Winter begins
1989: LeCun's CNNs applied to zip codes
1990: "AI Winter" in full effect

1997: Deep Blue beats Kasparov
1997: LSTM invented (Hochreiter & Schmidhuber)
1998: LeNet-5 for digit recognition
2006: Deep Belief Nets (Hinton)
2009: ImageNet created (Fei-Fei Li)
2011: Watson wins Jeopardy!
2012: AlexNet wins ImageNet → Deep Learning revolution

2014: GANs invented (Goodfellow)
2015: ResNet (152 layers!)
2016: AlphaGo beats Lee Sedol
2017: "Attention Is All You Need" - Transformer
2018: BERT (Google), GPT (OpenAI)
2019: GPT-2 (1.5B parameters)
2020: GPT-3 (175B parameters)
2021: DALL-E, Copilot
2022: ChatGPT (Nov 30) → AI goes mainstream
2023: GPT-4, Claude, Gemini announcements; open-weight ecosystem accelerates
2024: multimodal assistants, long-context systems, and smaller deployable models mature
2025-2026: frontier model families, open-weight releases, agent tooling, and governance debates continue changing quickly
```

Treat this timeline as a scaffold rather than as a complete chronology. Every entry hides disputes about priority, influence, and interpretation, and every modern entry should be verified against current sources before being used in a slide deck, sales claim, or architecture decision. The point is to see the rhythm: theory, demo, boom, bottleneck, correction, infrastructure shift, and renewed capability.

---

## Knowledge Check

**Q1.** Your team is building a simple fraud detector with a single-layer perceptron. It works on linearly separable examples, but it completely fails when the label should be positive only when exactly one of two signals is present. A teammate says the training data must be bad. Based on AI history, what is the more likely explanation, and what historical event exposed this limitation?

<details>
<summary>Answer</summary>
The more likely explanation is that the problem has an XOR-like structure, which a single-layer perceptron cannot learn because it is not linearly separable. This limitation is associated with the perceptron critique made famous by Marvin Minsky and Seymour Papert's 1969 book *Perceptrons*.

The issue is not merely bad data. It is a fundamental architectural limitation of a single linear decision boundary. The practical lesson is to inspect the structure of the target function before assuming that more examples will fix an underpowered model class.
</details>

**Q2.** Your startup just demoed an AI assistant, and the CEO is publicly promising that it will replace most human knowledge workers within a few years. Investors are excited, but you are worried. Which pattern from AI history does this resemble, and what risk usually follows?

<details>
<summary>Answer</summary>
This resembles the overpromising pattern that preceded both AI Winters: impressive demos become broad claims, broad claims attract funding and attention, and then real-world limitations trigger backlash when the systems cannot satisfy the inflated expectations.

The risk is not only technical failure. It is trust collapse. If the organization promises general replacement but delivers narrow assistance with visible errors, users and funders may punish the whole category more harshly than they would have if the original claim had been scoped honestly.
</details>

**Q3.** A hospital wants software to advise on a narrow class of bacterial infections and explain its reasoning step by step. Another team proposes a broad "general intelligence" system instead. Based on the module, which historical approach is the better fit for this narrow task, and what famous system supports your choice?

<details>
<summary>Answer</summary>
The better historical fit is an expert system designed for a narrow domain with explicit rules, uncertainty handling, and explanation facilities. MYCIN is the classic example because it advised on certain infectious-disease treatment decisions rather than claiming general medical intelligence.

The lesson is that constrained scope can make AI useful even when general intelligence is out of reach. A narrow rule-based system may be easier to validate, explain, and govern than a broad assistant if the task boundary is stable and expert knowledge can be maintained.
</details>

**Q4.** Your product manager argues that because a chess engine beat a world champion, the company is close to general AI. Using the module's history, how would you respond?

<details>
<summary>Answer</summary>
Beating a world champion at chess does not prove general intelligence. Deep Blue's 1997 win over Garry Kasparov was a major achievement, but it was a narrow system built around chess search, evaluation, and specialized hardware.

The right response is to separate task mastery from general competence. A system can exceed humans in a formal domain while having no ability to transfer that performance to medicine, law, robotics, conversation, or business operations without new mechanisms and evidence.
</details>

**Q5.** In 2011, your computer vision team says neural networks are too unreliable for large-scale image classification. A year later, a competitor beats everyone by a large margin. According to the module, what three conditions finally came together to make that breakthrough possible?

<details>
<summary>Answer</summary>
The three conditions were data, compute, and algorithms. ImageNet provided a large labeled benchmark, GPUs supplied enough parallel computation to train larger neural networks, and techniques such as ReLU activations, dropout, convolutional architectures, and improved optimization made training effective.

The breakthrough was not caused by one factor alone. Deep learning succeeded when the surrounding stack was ready, which is why earlier neural-network ideas could be technically interesting for decades before becoming dominant in production-relevant systems.
</details>

**Q6.** Your NLP team is debating whether to keep building around recurrent models or switch to an architecture that can process sequences in parallel and capture long-range relationships better. Which historical innovation points to the stronger choice, and why?

<details>
<summary>Answer</summary>
The historical innovation is the Transformer, introduced in "Attention Is All You Need" in 2017. Transformers use self-attention to let tokens relate directly to other tokens, and they avoid recurrence, making training more parallelizable on modern accelerators.

That does not mean recurrent models are useless, but it explains why Transformers became the foundation for much of modern language AI. The architecture fit the scaling era: large datasets, accelerator training, long context, and reusable pre-trained representations.
</details>

**Q7.** Your research lead wants to spend months hand-crafting domain rules for a new AI system, while another engineer argues for a more general learning approach with larger models and more compute. Which side is more aligned with the Bitter Lesson, and what is the core argument?

<details>
<summary>Answer</summary>
The engineer arguing for scalable learning is more aligned with the Bitter Lesson, as long as the task has enough data, feedback, and evaluation to benefit from that scale. Richard Sutton's argument is that general methods that leverage computation tend to outperform hand-coded human knowledge over long time horizons.

The core argument is not that human knowledge has no value. It is that hand-crafted knowledge often creates short-term gains and long-term ceilings, while search and learning methods can continue improving as computation and data grow.
</details>

---

## Hands-On Exercise

This lab asks you to turn the survey into artifacts you can reuse later: a timeline, a tiny historical model, and a written analysis of the Bitter Lesson. The point is not to produce a museum exhibit. The point is to practice converting historical claims into runnable experiments, inspectable evidence, and careful explanations.

**Success Checklist**

- [ ] Your timeline separates theoretical milestones, commercial booms, winters, and modern scaling events instead of presenting every year as equal.
- [ ] Your perceptron experiment demonstrates both a linearly separable task and an XOR-like failure case.
- [ ] Your Bitter Lesson analysis names at least three examples and explains where human knowledge still matters.

### Exercise 1: Build a Timeline Visualization

Create a visual timeline of AI milestones using matplotlib or a tool like TimelineJS. A good timeline should make the winter periods visible, distinguish benchmark wins from methodological inventions, and leave room for uncertainty when a milestone is more interpretive than factual:

```python
"""
AI History Timeline Visualization

Create an interactive timeline showing key AI milestones,
with annotations for AI Winters and breakthrough periods.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime

# Key milestones
milestones = [
    (1943, "McCulloch-Pitts Neuron", "theory"),
    (1950, "Turing Test Proposed", "theory"),
    (1956, "Dartmouth Conference", "breakthrough"),
    (1957, "Perceptron Invented", "breakthrough"),
    (1969, "Perceptrons Book", "setback"),
    (1986, "Backpropagation Paper", "breakthrough"),
    (1997, "Deep Blue beats Kasparov", "milestone"),
    (2012, "AlexNet wins ImageNet", "breakthrough"),
    (2017, "Transformer Architecture", "breakthrough"),
    (2022, "ChatGPT Released", "breakthrough"),
]

# AI Winters
winters = [
    (1969, 1980, "First AI Winter"),
    (1987, 1993, "Second AI Winter"),
]

fig, ax = plt.subplots(figsize=(15, 8))

# Plot winters as shaded regions
for start, end, label in winters:
    ax.axvspan(start, end, alpha=0.3, color='blue', label=label)

# Plot milestones
colors = {'theory': 'purple', 'breakthrough': 'green',
          'setback': 'red', 'milestone': 'orange'}

for year, event, category in milestones:
    ax.scatter(year, 0.5, c=colors[category], s=100, zorder=5)
    ax.annotate(event, (year, 0.5), xytext=(0, 10),
                textcoords='offset points', ha='center',
                fontsize=8, rotation=45)

ax.set_xlim(1940, 2025)
ax.set_xlabel('Year')
ax.set_title('History of AI: Milestones and Winters')
plt.tight_layout()
plt.savefig('ai_timeline.png', dpi=150)
print("Timeline saved to ai_timeline.png")
```

**Challenge**: Extend this to include 50+ events, add tooltips with detailed descriptions, and deploy it as an interactive web page that links each event to a primary source or to the corresponding chapter in the AI History book.

### Exercise 2: Implement a Historical Model

Recreate one of the early AI systems to understand how it worked. The perceptron is a good choice because it is simple enough to implement in a short script, yet historically rich enough to show why linear separability mattered:

```python
"""
Perceptron Implementation (1957 Algorithm)

Build Rosenblatt's perceptron from scratch and train it
on simple binary classification problems.
"""
import numpy as np

class Perceptron:
    """
    The Perceptron as Rosenblatt described it.

    This is historically accurate to the 1957 algorithm:
    - Binary threshold activation
    - Simple additive weight update rule
    - Learning rate (eta)
    """

    def __init__(self, n_inputs: int, learning_rate: float = 0.1):
        # Initialize weights to small random values
        self.weights = np.random.randn(n_inputs) * 0.01
        self.bias = 0.0
        self.lr = learning_rate

    def predict(self, x: np.ndarray) -> int:
        """Binary threshold activation - just like 1957"""
        activation = np.dot(x, self.weights) + self.bias
        return 1 if activation > 0 else 0

    def train(self, X: np.ndarray, y: np.ndarray, epochs: int = 100):
        """
        The perceptron learning rule:
        - If correct: do nothing
        - If should be 1 but was 0: add input to weights
        - If should be 0 but was 1: subtract input from weights
        """
        history = []
        for epoch in range(epochs):
            errors = 0
            for xi, target in zip(X, y):
                prediction = self.predict(xi)
                error = target - prediction

                if error != 0:
                    # Rosenblatt's update rule
                    self.weights += self.lr * error * xi
                    self.bias += self.lr * error
                    errors += 1

            history.append(errors)
            if errors == 0:
                print(f"Converged at epoch {epoch + 1}")
                break

        return history

# Test on AND gate (learnable by perceptron)
X_and = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
y_and = np.array([0, 0, 0, 1])

perceptron = Perceptron(2)
history = perceptron.train(X_and, y_and)
print(f"AND gate predictions: {[perceptron.predict(x) for x in X_and]}")

# Test on XOR (NOT learnable by single perceptron!)
X_xor = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
y_xor = np.array([0, 1, 1, 0])

perceptron_xor = Perceptron(2)
history_xor = perceptron_xor.train(X_xor, y_xor, epochs=1000)
print(f"XOR gate predictions: {[perceptron_xor.predict(x) for x in X_xor]}")
print("XOR fails! This is exactly what Minsky & Papert proved in 1969.")
```

**Challenge**: Implement a multi-layer perceptron to solve XOR and demonstrate why the 1986 backpropagation revival was so important. In your write-up, explain the difference between representing a function and having a practical training method for learning it.

### Exercise 3: Analyze the Bitter Lesson

Read Sutton's "The Bitter Lesson" essay and analyze whether current AI development follows its predictions. Keep the analysis grounded: do not claim that a system proves or disproves the lesson unless you can explain the method, data source, compute path, and evaluation boundary:

```python
"""
Bitter Lesson Analysis Framework

Evaluate whether recent AI developments follow or contradict
the Bitter Lesson's predictions about compute vs. knowledge.
"""

bitter_lesson_claims = {
    "claim_1": "General methods that leverage computation are most effective",
    "claim_2": "Human knowledge is less valuable than scale",
    "claim_3": "Search and learning beat domain knowledge",
    "claim_4": "Short-term benefits of human knowledge are outweighed by long-term compute gains",
}

# Your analysis framework
def analyze_development(development_name: str, description: str,
                        supports_bitter_lesson: bool, reasoning: str):
    """Document whether a development supports or contradicts the Bitter Lesson"""
    return {
        "development": development_name,
        "description": description,
        "supports_bitter_lesson": supports_bitter_lesson,
        "reasoning": reasoning
    }

# Example analyses
analyses = [
    analyze_development(
        "Frontier chat model",
        "Large transformer system trained and adapted at scale",
        True,
        "General pretraining and scale matter more than hand-written linguistic rules"
    ),
    analyze_development(
        "Self-play game system",
        "System that improves by generating training experience through play",
        True,
        "Search and learning improve with compute instead of relying only on expert heuristics"
    ),
    analyze_development(
        "RLHF",
        "Reinforcement Learning from Human Feedback",
        False,  # Arguably contradicts
        "Human preferences guide model behavior - injecting human knowledge"
    ),
    # Add your own analyses...
]

# Tally results
support_count = sum(1 for a in analyses if a["supports_bitter_lesson"])
print(f"\nBitter Lesson Analysis Summary:")
print(f"Developments supporting: {support_count}/{len(analyses)}")
print(f"Developments contradicting: {len(analyses) - support_count}/{len(analyses)}")

# Your conclusion
print("\nYour Analysis:")
print("Does modern AI development follow the Bitter Lesson?")
print("[Write your 2-3 paragraph analysis here]")
```

**Challenge**: Write a 500-word essay arguing for or against the Bitter Lesson based on developments since 2019. A strong essay should include at least one counterexample or qualification, because the lesson is a design lens rather than a law of nature.

### Exercise 4: Pioneer Research Deep Dive

Select one AI pioneer and trace their intellectual lineage. This exercise is useful because AI history is not just a chain of isolated geniuses; it is a network of mentors, collaborators, institutions, funding programs, and reused ideas:

```python
"""
AI Pioneer Research Project

Pick a pioneer, read their seminal papers, and trace
how their ideas evolved and influenced others.
"""

pioneer_template = {
    "name": "[verified name]",
    "birth_year": "[verify or omit]",
    "key_contributions": [
        "[contribution with source]",
        "[contribution with source]",
        "[contribution with source]",
    ],
    "seminal_papers": [
        "[paper title, year, source URL]",
        "[paper title, year, source URL]",
    ],
    "advisors_mentors": ["[verify relationship before listing]"],
    "notable_students": ["[verify relationship before listing]"],
    "awards": ["[award, year, awarding body, source URL]"],
    "intellectual_lineage": """
    Explain the lineage in sourced prose:
    - Which earlier idea did this person inherit?
    - Which bottleneck did they address?
    - Which later systems reused or revised the idea?
    """,
}

# Your assignment: Create profiles for 3 pioneers of your choice
# Suggested: Turing, Minsky, LeCun, Bengio, Schmidhuber, Fei-Fei Li

# Research questions to answer:
questions = [
    "What problem were they trying to solve?",
    "What was the prevailing wisdom they challenged?",
    "How did their background influence their approach?",
    "Who did they collaborate with or learn from?",
    "What is their lasting impact on the field?",
]

print("AI Pioneer Research Project")
print("=" * 40)
for q in questions:
    print(f"• {q}")
```

**Challenge**: Create a network graph showing how major AI pioneers are connected through mentorship, collaboration, and intellectual influence. Label uncertain relationships clearly, and avoid turning proximity in the same lab or company into a stronger claim than the sources support.

---

## Reflection Questions

1. **Why did neural networks take so long to succeed?** What combination of factors (data, compute, algorithms) was missing earlier?

2. **Could there be another AI Winter?** What would cause it? What would need to happen for current progress to stall?

3. **The Bitter Lesson suggests compute beats knowledge. Is this always true?** When might human knowledge and inductive biases still matter?

4. **What patterns from AI history might predict the next decade?** What lessons should guide our expectations?

5. **Who are the "Turings" and "Hintons" of the future?** What problems might the next generation of AI pioneers solve?

---

## Next Module

Next, move from historical survey to day-to-day model-building practice with [Module 1.1: Scikit-learn API & Pipelines](/ai-ml-engineering/machine-learning/module-1.1-scikit-learn-api-and-pipelines/). Keep the history map nearby: when you build pipelines, evaluate leakage, tune models, or compare algorithms, you are working inside the data-and-evaluation culture that replaced the overbroad promises of earlier AI eras.

For further reading beyond this module, use Russell and Norvig's *Artificial Intelligence: A Modern Approach* for broad textbook coverage, Pedro Domingos's *The Master Algorithm* for an accessible tour of machine-learning tribes, Cade Metz's *Genius Makers* for recent deep-learning personalities, and the [AI History book](/ai-history/) for KubeDojo's chapter-length treatment of the same timeline.

## Sources

- [McCulloch and Pitts, "A Logical Calculus of the Ideas Immanent in Nervous Activity"](https://link.springer.com/article/10.1007/BF02478259) — primary bibliographic source for the 1943 threshold-neuron paper.
- [Turing, "Computing Machinery and Intelligence"](https://courses.cs.umbc.edu/471/papers/turing.pdf) — text of the 1950 paper that introduced the imitation-game framing.
- [Shannon, "Programming a Computer for Playing Chess"](https://www.computerhistory.org/chess/doc-431614f453dde/) — Computer History Museum record for Shannon's 1950 chess-programming paper.
- [McCarthy, Minsky, Rochester, and Shannon, Dartmouth proposal](https://dl.acm.org/doi/10.1609/aimag.v27i4.1904) — ACM-hosted record of the 1955 proposal that introduced the artificial-intelligence research label.
- [Rockefeller Archive Center, "A Roomful of Brains"](https://resource.rockarch.org/story/a-roomful-of-brains-early-advances-in-computer-science-and-artificial-intelligence/) — archive-backed account of the Dartmouth proposal's requested \$13,500 and Rockefeller's \$7,500 five-week offer.
- [Cornell, "Professor's perceptron paved the way for AI"](https://news.cornell.edu/stories/2019/09/professors-perceptron-paved-way-ai-60-years-too-soon) — university history source for Rosenblatt, the perceptron, and the public claims around it.
- [Weizenbaum, "ELIZA"](https://dl.acm.org/doi/10.1145/365153.365168) — ACM record for the 1966 ELIZA paper and its pattern-matching conversation mechanism.
- [Grudin, "A Moving Target: The Evolution of Human-Computer Interaction"](https://www.microsoft.com/en-us/research/wp-content/uploads/2017/01/HCIhandbook3rd.pdf) — source for the Life magazine Minsky attribution and the later misquotation caveat.
- [Lighthill, "Artificial Intelligence: A General Survey"](https://aitopics.org/doc/classics%3AD8235CF9/) — AI Topics classic record for the 1973 Lighthill Report and its critique of AI progress.
- [Shortliffe, "MYCIN: A Knowledge-Based Computer Program Applied to Infectious Diseases"](https://pmc.ncbi.nlm.nih.gov/articles/PMC2464549/) — archival medical-informatics source for MYCIN's infectious-disease expert-system role.
- [Stanford archive record discussing XCON and expert systems](https://stacks.stanford.edu/file/druid%3Ark795nw8403/rk795nw8403.pdf) — historical source for commercial expert-system examples and claimed configuration savings.
- [MIT OCW Symbolics case study](https://ocw.mit.edu/courses/6-933j-the-structure-of-engineering-revolutions-fall-2001/30eb0d06f5903c7a4256d397a92f6628_Symbolics.pdf) — source for the installed worldwide base of Lisp machines by 1988.
- [Rumelhart, Hinton, and Williams, "Learning representations by back-propagating errors"](https://www.nature.com/articles/323533a0) — Nature record for the 1986 backpropagation revival.
- [IBM, "Deep Blue"](https://www.ibm.com/history/deep-blue) — IBM history source for the 1997 Kasparov match.
- [Hochreiter and Schmidhuber, "Long Short-Term Memory"](https://direct.mit.edu/neco/article/9/8/1735/6109/Long-Short-Term-Memory) — MIT Press record for the 1997 LSTM paper.
- [Deng et al., "ImageNet: A Large-Scale Hierarchical Image Database"](https://www.image-net.org/static_files/papers/imagenet_cvpr09.pdf) — ImageNet paper source for the dataset and benchmark framing.
- [Hinton, Osindero, and Teh, "A Fast Learning Algorithm for Deep Belief Nets"](https://www.cs.toronto.edu/~fritz/absps/ncfast.pdf) — source for the 2006 layer-wise pretraining discussion.
- [Krizhevsky, Sutskever, and Hinton, "ImageNet Classification with Deep Convolutional Neural Networks"](https://proceedings.neurips.cc/paper/4824-imagenet-classification-with-deep-convolutional-neural-networks.pdf) — primary paper for AlexNet architecture and ILSVRC-2012 error-rate comparison.
- [He et al., "Deep Residual Learning for Image Recognition"](https://arxiv.org/abs/1512.03385) — source for ResNet, residual learning, and ILSVRC 2015 results.
- [Vaswani et al., "Attention Is All You Need"](https://arxiv.org/abs/1706.03762) — source for the Transformer architecture and no-recurrence sequence modeling.
- [Devlin et al., "BERT"](https://arxiv.org/abs/1810.04805) — source for bidirectional Transformer pretraining and BERT's 2018 claims.
- [OpenAI, "Improving language understanding with unsupervised learning"](https://openai.com/index/language-unsupervised/) — source for the original GPT generative-pretraining framing.
- [OpenAI, "Better language models and their implications"](https://openai.com/index/better-language-models/) — source for GPT-2's staged-release and misuse discussion.
- [OpenAI, "Ilya Sutskever to leave OpenAI, Jakub Pachocki announced as Chief Scientist"](https://openai.com/index/jakub-pachocki-announced-as-chief-scientist/) — dated source for Sutskever's 2024 departure from the Chief Scientist role.
- [Brown et al., "Language Models are Few-Shot Learners"](https://arxiv.org/abs/2005.14165) — source for GPT-3's 175B-parameter few-shot learning paper.
- [Ouyang et al., "Training language models to follow instructions with human feedback"](https://arxiv.org/abs/2203.02155) — source for instruction tuning and RLHF in the InstructGPT line.
- [OpenAI, "Introducing ChatGPT"](https://openai.com/index/chatgpt/) — source for the November 30, 2022 ChatGPT release.
- [ACM, 2018 A.M. Turing Award](https://awards.acm.org/about/2018-turing) — source for Bengio, Hinton, and LeCun's Turing Award citation.
- [Sutton, "The Bitter Lesson"](https://www.cs.utexas.edu/~eunsol/courses/data/bitter_lesson.pdf) — reachable copy of Sutton's 2019 essay behind the module's Bitter Lesson section.
- [Silver et al., "Mastering the game of Go without human knowledge"](https://www.nature.com/articles/nature24270) — source for AlphaGo Zero and self-play without human game data.
- [OpenAI model release notes](https://help.openai.com/en/articles/9624314-model-release-notes) — dated official source for fast-changing OpenAI model-family details.
- [Anthropic Claude models overview](https://platform.claude.com/docs/en/about-claude/models/overview) — dated official source for fast-changing Claude model-family details.
- [Google Gemini API models](https://ai.google.dev/gemini-api/docs/models) — dated official source for fast-changing Gemini model-family details.
- [Meta, "The Llama 4 herd"](https://ai.meta.com/blog/llama-4-multimodal-intelligence/) — dated official source for Llama 4 model-family claims used only in the volatile snapshot.
