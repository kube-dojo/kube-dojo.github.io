---
citations_verified: true
title: "Home-Scale RAG Systems"
slug: ai-ml-engineering/vector-rag/module-1.6-home-scale-rag-systems
sidebar:
  order: 407
---
> **AI/ML Engineering Track** | Complexity: `[MEDIUM]` | Time: 2-3 hours
---
**Reading Time**: 2-3 hours  
**Prerequisites**: Module 1.2 Building RAG Systems, Module 1.4 Embeddings & Semantic Search, and the prerequisites section
---

## Learning Outcomes

By the end of this module, you will be able to:

- design a private, single-machine RAG system that balances corpus size, privacy boundaries, latency, storage, and recovery effort
- evaluate chunking, embedding, and index choices for a laptop, workstation, or home server instead of copying enterprise defaults
- debug retrieval-quality failures by separating corpus problems, chunking problems, metadata gaps, and generator limitations
- compare fully local and hybrid RAG designs, then justify which components must remain local for a given privacy requirement
- build a small evaluation loop that tests retrieval relevance, source traceability, storage growth, indexing time, and answer usefulness

## Why This Module Matters

**Hypothetical scenario:** A developer keeps years of project notes, architecture decisions, shell snippets, and PDF manuals on one workstation.
When a production incident happens at night, the answer is probably somewhere in those files, but the file names are inconsistent,
the PDFs are half-forgotten, and search returns either too much or nothing useful.

**Hypothetical scenario:** Another learner has the same problem in a different shape.
They want a private assistant over study notes, lab writeups, Kubernetes references, and local code comments, but every tutorial they find assumes a managed vector database,
cloud-hosted embeddings, distributed ingestion, and a budget that makes sense for a company rather than one person.

A home-scale RAG system sits between those worlds.
It is serious enough to teach real architecture, but small enough that one learner can understand every moving part,
recover the system after a mistake, and explain why each component exists.

The danger is that small systems are easy to overbuild and easy to under-discipline.
A learner can waste days wiring services together before they have chosen a corpus, or they can throw files into an index without metadata and then wonder why the answers feel untrustworthy.

This module teaches home-scale RAG as a systems design problem.
The goal is not to build a toy, and it is not to pretend that one workstation is an enterprise platform.
The goal is to learn how retrieval-augmented generation behaves when hardware, privacy, cost, and operational patience are all real constraints.

A senior practitioner can look at a RAG design and ask sharper questions before any tool is chosen.
What documents are actually in scope?
Which data is allowed to leave the machine?
How often does the index need to change?
What failure would make users lose trust first?
Those questions shape the architecture more than the brand name of the vector store.

## Core Content

## 1. Define the Home-Scale Boundary Before You Choose Tools

A home-scale RAG system is not defined by being weak, informal, or experimental.
It is defined by the operating boundary: one laptop, one workstation, one small home server, or a tiny private network with limited administrative attention.
That boundary changes which decisions are rational, because every extra service becomes something you must install, monitor, back up, secure, and explain later.

The most important first move is to describe the system in operational terms rather than tool terms.
A tool-first design starts with "I want to use a vector database."
An operations-first design starts with "I have twelve gigabytes of usable memory, a few thousand trusted files, strict local storage requirements, and one human asking questions."
The second version gives you enough information to choose tools responsibly.

Enterprise RAG systems often optimize for many tenants, high concurrency, access-control integration, continuous ingestion, observability pipelines, and centralized governance.
Those concerns are real, but they are not automatically your concerns on day one.
If you copy the shape of an enterprise system without the workload that justifies it, you inherit the complexity without inheriting the benefits.

Home-scale RAG usually optimizes for clarity, privacy, low cost, repeatable recovery, and good-enough latency for one person or a small trusted group.
That does not mean quality is optional.
It means quality comes from a bounded corpus, explicit source metadata, sensible chunking, and a small evaluation loop before it comes from distributed infrastructure.

A helpful boundary statement has five parts.
It names the users, the document set, the privacy rule, the update rate, and the machine constraint.
If one of those parts is missing, the architecture will usually drift toward whatever tool the builder most recently learned about.

For example, this is a weak boundary statement because it hides the decisions that matter.
"The RAG system should answer questions about my documents."
It does not say which documents, how fresh they must be, what privacy rule applies, or whether the system is allowed to trade latency for simplicity.

This is a stronger boundary statement because it constrains the design.
"The system answers one user's questions over a curated folder of Markdown notes and converted PDFs, stores documents and embeddings locally, refreshes weekly, runs on a workstation without a dedicated GPU, and returns cited answers in under ten seconds for normal questions."

That stronger statement already rules out several distracting choices.
You probably do not need a distributed queue for weekly refreshes.
You probably do not need multi-tenant authorization.
You probably do need source metadata, a backup plan for the index, and a way to test whether the right notes are being retrieved.

```text
+----------------------+        +----------------------+        +----------------------+
| Boundary Question    |        | Design Consequence   |        | Home-Scale Default   |
+----------------------+        +----------------------+        +----------------------+
| Who asks questions?  | -----> | concurrency target   | -----> | one user or tiny team|
| Which files matter?  | -----> | corpus size/noise    | -----> | curated folder set   |
| What must stay local?| -----> | privacy boundary     | -----> | local docs + index   |
| How often updates?   | -----> | ingestion complexity | -----> | scheduled refresh    |
| What machine exists? | -----> | model/index choices  | -----> | CPU-first unless not |
+----------------------+        +----------------------+        +----------------------+
```

The diagram is deliberately plain because the architecture is deliberately plain.
Every box has a concrete consequence.
If you cannot answer the boundary question, the corresponding design decision is premature.

> **Stop and think:** If your current document set doubled tonight, which part of the system would hurt first:
> indexing time, disk usage, retrieval quality, answer latency, or your ability to trust sources?
> Your answer is a design signal, not an implementation detail.

The boundary also protects you from false precision.
Many RAG discussions compare embedding models, vector indexes, and rerankers as if the corpus were already clean and the question set already known.
At home scale, the corpus is often the messiest part of the system, and the easiest quality win may be removing stale files before tuning retrieval.

A beginner should leave this section knowing that smaller architecture can still be rigorous.
A senior practitioner should recognize the same pattern from production design: constraints are not excuses, they are the input to system shape.
The difference is that at home scale, you can usually make the system more understandable instead of more distributed.

The practical test is simple.
If you cannot redraw the system from memory and explain how to rebuild it after deleting the index, it is too complicated for a first home-scale version.
That test does not ban advanced tools, but it forces each advanced tool to earn its place.

## 2. Shape the Corpus Before You Shape the Index

RAG quality begins before embeddings.
If the corpus contains duplicated notes, stale runbooks, contradictory PDFs, and files nobody would trust as sources, retrieval will faithfully surface that confusion.
A better vector store can make retrieval faster, but it cannot decide which document is authoritative unless you provide the necessary structure.

Corpus shaping means deciding what belongs in the first version, what should be excluded, and how each source will be identified later.
This is not clerical cleanup.
It is architecture work because it determines the size of the index, the noise level of retrieval, the privacy boundary, and the evaluation questions you can ask.

A bounded corpus is the best friend of a home-scale system.
Start with a folder or small set of folders that answer one domain of questions.
Project documentation, lab notes, local runbooks, and converted PDFs are good candidates.
A whole home directory is usually a bad candidate because it mixes trusted sources with drafts, downloads, cache files, and irrelevant text.

You should also decide how conflicts will be handled.
If two files disagree, the RAG system may retrieve both unless metadata or corpus curation gives it a reason not to.
For learning systems, the simplest answer is often to remove the older file, mark it as archived, or keep only the authoritative version in the indexed folder.

The update cadence determines how much ingestion machinery you need.
A corpus that changes monthly can be rebuilt from scratch on a schedule.
A corpus that changes hourly may need file watching, incremental indexing, deduplication, and freshness metadata.
Many learners accidentally design for hourly updates when their real documents change once a week.

| Corpus Situation | Risk If Ignored | Better Design Move |
|---|---|---|
| duplicated notes from sync folders | repeated retrieval results look falsely important | deduplicate before indexing and keep one authoritative source |
| stale PDFs mixed with current docs | answers cite old guidance without warning | add version or updated-at metadata and archive outdated material |
| tiny snippets indexed as separate chunks | retrieval returns fragments with weak context | merge related text before chunking or use larger chunks |
| broad folders with unrelated files | useful chunks compete with noise | start with one domain-specific corpus and expand later |
| sensitive files beside public files | privacy boundary becomes unclear | separate corpora by privacy class before embedding |

The table shows why corpus design belongs before tool selection.
A local vector database with excellent filtering helps only if you record fields worth filtering on.
If every chunk has the same empty metadata, the filter feature exists in theory but not in your system.

A good home-scale metadata record usually includes source path, source title if available, chunk identifier, modified timestamp, corpus name, and privacy class.
For code repositories, add repository name and branch or commit when possible.
For PDFs converted to text, add the original PDF path and page range if your converter can preserve it.

The privacy class deserves special attention.
Many home projects mix personal notes, work documents, exported chats, public references, and code.
Those categories may have different rules.
If you do not classify them before ingestion, you may later discover that a remote embedding call or remote generator saw text it should not have received.

A useful privacy classification can be simple.
Public means the content can leave the machine if needed.
Private means documents and chunks stay local, but summaries might be sent to a remote model after review.
Restricted means raw chunks, embeddings, and generated prompts stay local.
The exact names matter less than making the boundary explicit.

> **Stop and think:** Suppose two corpora have the same number of files.
> One contains clean, current runbooks from a single project.
> The other contains years of mixed downloads, notes, and obsolete drafts.
> Which corpus should you expect to perform better, and what would you measure to prove it?

Chunking should be chosen after the corpus shape is understood.
Dense factual documents often benefit from smaller chunks because each answer may live in a short section.
Tutorials, design documents, and incident writeups often need larger chunks because the meaning spans several paragraphs.
There is no universal chunk size because documents do not all carry meaning at the same scale.

Overlap is another place where local systems can waste resources.
A small overlap can preserve continuity across chunk boundaries.
A large overlap multiplies storage and can cause near-duplicate retrieval results that crowd out diverse evidence.
On one machine, every extra vector has a visible cost in indexing time, disk usage, and query work.

The right question is not "What chunk size is best?"
The better question is "What chunk size preserves the unit of meaning my users ask about?"
If users ask for exact command flags, smaller chunks may help.
If users ask why an architecture decision was made, chunks need enough surrounding rationale to be useful.

Corpus shaping also gives you the evaluation set.
Write questions from the documents you actually indexed.
Include questions that should retrieve a specific file, questions that need more than one paragraph of context, and questions the corpus should not answer.
That last category is essential because a trustworthy RAG system must know when evidence is missing.

A beginner might treat evaluation as a final polish step.
A senior builder treats evaluation as the steering wheel.
Without a question set, every tuning decision becomes a feeling, and feelings are weak evidence when retrieval systems behave unexpectedly.

The simplest version is a text file with representative questions and expected source files.
That is enough to compare chunking strategies, metadata choices, and index options.
You do not need a full benchmark harness to notice that one design retrieves the right source four times out of five while another design does not.

## 3. Build the Minimal Architecture With Explicit Contracts

A home-scale RAG architecture has a short path from document to answer.
Documents are parsed into text, text is chunked, chunks are embedded or otherwise indexed, relevant chunks are retrieved, and a generator uses retrieved evidence to answer.
Every step should have a clear input, a clear output, and enough metadata to debug failures.

The minimal architecture is powerful because it exposes the failure points.
If a question gets a poor answer, you can ask whether the document was included, whether the chunk preserved meaning, whether retrieval found it, whether the generator used it, and whether the citation identifies it.
That diagnostic path is harder to follow when every stage is hidden behind several services.

```text
+------------------+     +------------------+     +------------------+
| Document Sources | --> | Chunking Pipeline| --> | Chunk Manifest   |
| files, PDFs, md  |     | size + overlap   |     | source metadata  |
+------------------+     +------------------+     +------------------+
          |                       |                         |
          v                       v                         v
+------------------+     +------------------+     +------------------+
| Privacy Boundary |     | Embedding/Index  | --> | Retrieval Results|
| local or hybrid  |     | local or remote  |     | scored chunks    |
+------------------+     +------------------+     +------------------+
                                                            |
                                                            v
                                                   +------------------+
                                                   | Generator        |
                                                   | answer + sources |
                                                   +------------------+
```

Each component should have a contract that a learner can inspect.
The document source contract says which files are included and excluded.
The chunking contract says how chunks are created and named.
The index contract says where vectors or search data live.
The retrieval contract says how many chunks are returned and how scores are interpreted.
The answer contract says that answers must cite sources or say that evidence is insufficient.

Contracts matter more than product names at this scale.
You can replace a simple embedded index with a local vector database later if the contract stays stable.
You can swap an embedding model if chunk records and evaluation questions stay the same.
This is how a small system becomes a learning platform instead of a pile of experiments.

A common first version uses local documents, a script-based chunking pipeline, a file-backed or embedded index, and either a local or remote generator.
That version can be rebuilt, inspected, copied, and deleted without complex orchestration.
It also gives you baseline measurements before adding more advanced pieces.

Local embeddings are attractive when documents are private, the corpus is modest, and update frequency is low enough that CPU throughput is acceptable.
They reduce data exposure and make the system easier to reason about offline.
Their cost is setup time, model download size, and slower indexing on weaker machines.

Remote embeddings are attractive when privacy allows it and convenience matters.
They can give strong embedding quality with less local setup, especially for small corpora where cost stays predictable.
Their cost is external dependency, possible data exposure, network latency, and the need to understand provider retention and policy boundaries.

> **Landscape snapshot — as of 2026-06. This changes fast; verify against vendor docs before relying on specifics.**
>
> | Component role | Example local/self-hosted options | Typical home-scale fit |
> |---|---|---|
> | Embedding encoder | Sentence Transformers bi-encoders, ONNX-exported models via Hugging Face Optimum | CPU-friendly indexing for modest corpora; pin one model for both ingest and query |
> | Vector index | Faiss flat or IVF indexes, Chroma persistent client, Qdrant local process, sqlite-vec extension | Start embedded or file-backed; add a database service only when filtering or concurrency hurts |
> | Document parsing | Markdown/text natively; PDF via PyMuPDF or pdfplumber; HTML via readability-style extractors | Prefer plain text first; PDF conversion quality often limits retrieval more than the index choice |
> | Local generator | llama.cpp, Ollama, vLLM on a workstation GPU if available | Fully local generation trades setup and hardware for privacy; hybrid designs may keep only the generator remote |
> | Orchestration glue | Plain Python scripts, LangChain, LlamaIndex | Frameworks help prototyping; contracts (manifest, chunk IDs, privacy class) matter more than the wrapper |

A hybrid system can be perfectly reasonable.
For example, documents and the index may remain local while final answer generation uses a remote model.
That design keeps raw corpus storage under local control but still benefits from stronger generation.
It is not fully private, so the prompt construction step must avoid sending restricted text if the policy forbids it.

The phrase "fully local" should not become a slogan.
A fully local system may be the right answer for restricted documents, offline use, or strong personal preference.
It may also impose model-quality limits, hardware pressure, and maintenance work that do not match the actual privacy requirement.
Design begins by deciding what must be local, not by assuming every component has the same rule.

The generator should be treated as an evidence synthesizer, not an oracle.
If retrieval finds weak context, the answer should be weak or abstain.
If retrieval finds strong context, the answer should stay grounded in the cited chunks.
This discipline prevents a small local model or a powerful remote model from covering retrieval mistakes with confident language.

You should also decide whether the system is retrieval-first or chat-first.
A retrieval-first workflow shows sources and retrieved chunks before generation, which is excellent for debugging.
A chat-first workflow hides retrieval details unless the user asks, which may feel smoother but can slow down learning.
For a learner system, retrieval-first mode is worth keeping even if the final user interface becomes conversational later.

The minimal architecture should include a manifest.
A manifest is a machine-readable record of chunks and metadata.
It lets you audit what was indexed, compare variants, remove stale chunks, and rebuild the index.
Without a manifest, debugging becomes a guessing game after the first indexing run.

A useful manifest record can be represented as JSON.
The exact fields can change, but each chunk needs an identity, source path, content hash or timestamp, privacy class, and enough location information for citation.
If the system cannot tell where an answer came from, trust will fail even when the answer happens to be correct.

```json
{
  "chunk_id": "runbooks/networking.md::section-3::chunk-2",
  "source": "runbooks/networking.md",
  "title": "Networking Runbook",
  "updated_at": "2026-04-20T13:00:00Z",
  "privacy": "private",
  "chunk_text_sha256": "example-hash-value",
  "section": "Troubleshooting DNS Resolution"
}
```

This record is not just bookkeeping.
It is the bridge between retrieval quality, privacy review, and user trust.
A cited answer can point to the source field.
A rebuild can compare timestamps or hashes.
A privacy check can block restricted chunks from remote calls.

> **Design checkpoint:** Before adding a new service, write the contract it would own.
> If the contract is vague, the service is probably being added because it feels advanced rather than because the system needs it.

Senior-level home-scale design often looks boring from the outside.
The sophistication is in keeping boundaries explicit, making rebuilds cheap, and measuring the right things.
A complicated architecture with weak metadata is less mature than a simple architecture that can explain every answer.

## 4. Worked Example: Choose Chunking and Storage for a Private Workstation

This worked example demonstrates a specific design choice before you build your own version.
The situation is intentionally ordinary: one user has a private workstation, no dedicated GPU, a curated folder of Markdown notes and converted PDF text, and a requirement that documents and the index stay local.
The user wants cited answers about project decisions, lab procedures, and troubleshooting notes.

The design question is narrower than "What is the best RAG stack?"
The real question is "Which first-version chunking and storage strategy gives useful retrieval without turning one workstation into an operations project?"
A good answer must consider corpus size, update rate, privacy, retrieval quality, storage growth, and recovery.

Step one is to restate the boundary in measurable terms.
The corpus has a few thousand text pages after conversion.
The update rate is weekly.
There is one primary user.
Documents and embeddings must stay local.
The user can tolerate several minutes of indexing but wants interactive question answering.

Those constraints immediately remove some options.
Continuous ingestion is unnecessary because weekly updates are enough.
A distributed queue is unnecessary because one indexing job can run locally.
A cloud vector database violates the local index requirement.
A local file-backed or embedded index is worth trying before operating a separate database service.

Step two is to pick two chunking candidates rather than arguing abstractly.
Candidate A uses medium chunks with small overlap.
Candidate B uses larger chunks with the same small overlap.
Both candidates preserve source path, section title, and modified timestamp.
Testing two candidates keeps the experiment focused and makes the decision evidence-based.

| Candidate | Chunk Shape | Expected Strength | Expected Weakness |
|---|---|---|---|
| A | medium chunks with small overlap | precise retrieval for factual and procedural questions | may miss context for long design explanations |
| B | larger chunks with small overlap | stronger context for architecture and rationale questions | may return broader chunks with extra unrelated text |

The table does not declare a winner.
It gives you hypotheses to test.
If the evaluation questions are mostly factual lookups, Candidate A may win.
If the questions often ask why a choice was made, Candidate B may give the generator better evidence.

Step three is to decide the storage starting point.
Because the index must stay local and the user count is one, an embedded or file-backed store is enough for the first version.
A local vector database can be introduced later if filtering, persistence behavior, or corpus size makes the simpler index painful.
Starting simple protects the learner from operating a service before they have measured the retrieval problem.

Step four is to define the evaluation set before indexing.
The learner writes five to ten realistic questions and expected source files.
At least one question asks for a specific command or setting.
At least one asks for a multi-paragraph explanation.
At least one asks something the corpus should not answer.
This prevents tuning the system only for successful examples.

Step five is to run retrieval-only tests.
Generation is deliberately disabled at first because generation can hide retrieval problems.
For each question, inspect the top retrieved chunks and mark whether the expected source appears near the top.
If the right source is not retrieved, changing the prompt will not fix the root problem.

Step six is to compare the candidates with a small scorecard.
The scorecard should include retrieval relevance, source usefulness, index size, indexing time, query latency, and whether the chunk text gives enough context for a cited answer.
This is a better decision process than choosing the index that feels fastest on one impressive question.

| Decision Factor | Candidate A Evidence | Candidate B Evidence | How to Interpret |
|---|---|---|---|
| retrieval relevance | expected source appears for most factual questions | expected source appears for most rationale questions | match the winner to the question types users ask |
| source usefulness | citations point to focused snippets | citations point to broader sections | focused is better for lookup, broader is better for reasoning |
| storage size | usually smaller per chunk set if overlap is controlled | often fewer chunks but larger text payloads | measure actual disk usage rather than guessing |
| indexing time | may create more records | may create fewer records | choose the cost users can tolerate during refresh |
| answer quality | may need multiple chunks to explain context | may provide enough context in one chunk | inspect generated answers only after retrieval works |

Step seven is to make the first decision and write it down.
For this scenario, suppose Candidate B retrieves better support for architecture questions while still answering factual questions well enough.
The design choice might be: use larger chunks with small overlap, local embeddings, an embedded local index, and retrieval-first debugging output.
The justification is not that larger chunks are universally better.
The justification is that this corpus contains decision records and lab explanations where context matters.

A weaker decision would say "use bigger chunks because they seem better."
A stronger decision says "use larger chunks because four of six evaluation questions require surrounding rationale, storage remains acceptable, indexing finishes inside the weekly maintenance window, and citations still point to useful sections."
That difference is the difference between tool preference and engineering judgment.

Step eight is to identify the next trigger for change.
If the corpus grows until indexing takes too long, move to incremental indexing or split the corpus by domain.
If filtering becomes important, introduce a local vector database with metadata filters.
If answer latency becomes unacceptable, reduce retrieved chunk count, use a smaller generator, or precompute summaries for stable documents.
Growth paths should be tied to symptoms, not fashion.

This worked example also shows why "do less" can be a serious design decision.
The design deliberately avoids continuous ingestion, distributed services, and multiple databases because the boundary does not require them.
That restraint gives the learner a system they can understand, evaluate, and improve.

The example is beginner-friendly because every decision is visible.
It is senior-level because every decision is justified by workload, privacy, and measurement.
That is the posture you should carry into the hands-on exercise.

## 5. Debug Retrieval Quality With a Layered Mental Model

When a home-scale RAG system produces a bad answer, the first question should not be "Which model should I buy?"
Bad answers can come from several layers, and each layer has a different fix.
A disciplined debugging process prevents you from changing the expensive part when the real issue is a stale document or a broken chunk.

Start by asking whether the answer exists in the corpus.
If the source document was never indexed, retrieval cannot find it.
If the source document is obsolete, retrieval may find it and still mislead the generator.
This is why corpus manifests and source freshness matter before model tuning.

Next, ask whether the chunk preserves the needed meaning.
A chunk that cuts an explanation in half may retrieve the right file but not the reason behind the answer.
A chunk that is too broad may retrieve the right section while burying the key sentence inside unrelated text.
Chunk quality is about preserving answerable units, not hitting a fashionable token count.

Then ask whether retrieval ranks the useful chunk high enough.
If the correct chunk appears outside the retrieved set, the generator never sees it.
If near-duplicates fill the top results, the generator sees repetitive context instead of diverse evidence.
This is where deduplication, overlap control, hybrid search, reranking, or better metadata filters may help.

After retrieval, ask whether the generator uses the evidence.
Some generators ignore sources, overgeneralize from partial context, or answer from prior knowledge.
A grounded prompt can help, but the stronger habit is to require citations and inspect whether the cited chunks actually support the claim.
If the citation does not support the sentence, the answer is not trustworthy.

Finally, ask whether the user interface exposes enough evidence.
A beautiful answer without visible sources is hard to debug.
For learning systems, show retrieved chunks, scores, source paths, and timestamps somewhere.
A future polished interface can hide details by default, but the debug path should remain available.

```text
Bad Answer
    |
    v
+--------------------------+
| Was the source indexed?  | -- no --> Fix corpus inclusion or conversion
+--------------------------+
    |
   yes
    v
+--------------------------+
| Did the chunk preserve   | -- no --> Adjust chunk size, overlap, or sectioning
| the needed meaning?      |
+--------------------------+
    |
   yes
    v
+--------------------------+
| Was it retrieved near    | -- no --> Tune retrieval, filters, hybrid search, or reranking
| the top results?         |
+--------------------------+
    |
   yes
    v
+--------------------------+
| Did the generator ground | -- no --> Tighten prompt, require citations, reduce noisy context
| the answer in evidence?  |
+--------------------------+
    |
   yes
    v
+--------------------------+
| Is the answer interface  | -- no --> Show sources, timestamps, and retrieved context
| auditable by a human?    |
+--------------------------+
```

This sequence is useful because it follows the request path.
Do not start at the generator when the document was excluded.
Do not start at the vector index when the corpus contains contradictory sources.
Do not start at chunk size when the real issue is that citations are hidden.

> **What would happen if:** You doubled the overlap between chunks without changing the evaluation set?
> Predict the likely effects on storage size, duplicate retrieval results, and answer quality before trying it.

A small evaluation loop can be plain and still effective.
For each test question, record the expected source, the top retrieved sources, whether the chunk is relevant, whether the answer cites it, and whether the answer is acceptable.
That record gives you a before-and-after comparison when you change chunking, embeddings, filters, or the generator.

The evaluation questions should be scenario-like, not trivia.
Instead of asking "What is in file X?", ask "A service cannot resolve DNS after a network change; which local runbook section explains the first checks?"
Instead of asking "What does this note say?", ask "A teammate wants to repeat the lab; which steps should they follow and what caveat matters?"
Scenario questions test whether retrieval supports real use.

Latency should be measured in pieces.
Indexing time matters during refresh.
Retrieval latency matters for interaction.
Generation latency matters for perceived responsiveness.
A slow answer may be acceptable if the system is used for deep research, but the same latency may frustrate a learner using it during a lab.

Storage growth should be measured early because home systems have visible limits.
Chunk count, manifest size, index size, and model cache size all matter.
A design that works on a small folder can become annoying after a few expansions if overlap and duplicate files multiply vectors unnecessarily.

Quality measurement should include abstention.
[A good RAG system should say when the corpus does not contain enough evidence.](https://arxiv.org/abs/2605.03534)
If every question receives a confident answer, including questions outside the corpus, the system is not grounded enough.
Test at least one "not enough evidence" question whenever you compare designs.

A senior debugging habit is to preserve failed examples.
When the system gives a poor answer, save the question, retrieved chunks, and expected source.
Those examples become regression tests.
The next time you change chunking or embeddings, you can check whether you fixed the failure or merely moved it.

## 6. Operate the System and Know When to Grow

A home-scale RAG system still needs operations.
The operations are smaller than enterprise operations, but they are not optional.
Backups, rebuilds, privacy checks, evaluation records, and upgrade notes are what keep a learning project from becoming an unrepeatable experiment.

The first operational requirement is rebuildability.
You should be able to delete the generated index and recreate it from source documents, chunking code, metadata rules, and configuration.
If the index contains irreplaceable state, you have made recovery harder than it needs to be.
Generated artifacts should be backed up only when rebuild time is expensive enough to justify it.

The second requirement is source backup.
Documents are the real asset.
If the index is lost, it can be rebuilt.
If the curated corpus is lost, the system loses its knowledge.
Keep the corpus under ordinary backup discipline before spending time on elaborate index backup.

The third requirement is configuration capture.
Write down chunk size, overlap, embedding model, index location, retrieval count, generator model, and privacy rule.
A future you should not have to infer those choices from old shell history.
Configuration capture also makes comparisons honest because you can see what changed between evaluation runs.

The fourth requirement is privacy review.
Whenever you add a remote component, ask what text leaves the machine, whether embeddings leave the machine, whether prompts contain raw chunks, and whether outputs are logged by another service.
This review should happen before integration, not after a convenient demo is already working.

The fifth requirement is routine evaluation.
A small set of representative questions should run after major corpus or configuration changes.
You do not need perfect automation at first.
Even a spreadsheet or Markdown log is useful if it records the same signals consistently.

Growth should be triggered by pain you can name.
Move beyond a simple local index when metadata filtering is actually needed.
Add incremental indexing when rebuild time becomes a real burden.
Add a service when multiple users need reliable concurrent access.
Add monitoring when the system becomes important enough that silent failure would matter.

Growth should not be triggered by embarrassment that the architecture looks simple.
A simple system with explicit contracts, good sources, and measured behavior is more mature than a complex system that cannot explain why it returned an answer.
Home-scale rigor is about choosing the smallest architecture that can be trusted.

There are clear signs that a design is no longer home-scale.
The corpus no longer fits comfortably on one machine.
Many users need simultaneous access and predictable uptime.
Ingestion is continuous and operationally expensive.
Metadata filtering becomes central to correctness.
Governance, audit, and access control matter more than experimentation.

When those signs appear, the next step is not to panic.
The home-scale system has done its job if it taught you the corpus, question patterns, privacy requirements, and evaluation criteria.
Those lessons become requirements for the next architecture.
You move up with evidence instead of starting from a blank enterprise template.

A practical migration path is to keep the contracts and replace one component at a time.
Move the index to a local vector database while keeping the same chunk manifest.
Add hybrid keyword and vector retrieval while keeping the same evaluation questions.
Introduce a service API while keeping retrieval-only debug output.
This keeps migration incremental and testable.

The operating lesson is that home-scale does not mean careless.
It means you can be strict about the few things that matter most.
Source discipline, rebuildability, privacy boundaries, and evaluation loops are not enterprise luxuries.
They are the reason a small RAG system can be trusted.

## Did You Know?

- **Fact 1:** Many useful private RAG systems are limited more by corpus quality than by embedding throughput, because duplicated or stale sources create bad evidence before retrieval even begins.
- **Fact 2:** A local index can be easier to trust than a managed service when the learner needs to inspect files, rebuild artifacts, and verify exactly what stayed on the machine.
- **Fact 3:** [Larger chunks are not automatically less precise; for design notes and incident reports, a larger chunk may preserve the reasoning that a small snippet would cut away.](https://arxiv.org/abs/2505.21700)
- **Fact 4:** Retrieval-only testing often finds problems faster than full chat testing, because it exposes whether the right evidence reached the generator in the first place.

## Common Mistakes

| Mistake | What Goes Wrong | Better Move |
|---|---|---|
| copying enterprise RAG architecture too early | the learner operates queues, services, and databases before proving the retrieval problem needs them | start with a rebuildable one-machine architecture and add services only when measured pain appears |
| indexing every available file | stale, duplicated, private, and irrelevant documents compete with trusted sources during retrieval | curate a bounded corpus and expand by domain after evaluation improves |
| over-chunking documents | the index grows quickly, retrieval returns fragments, and the generator lacks surrounding rationale | chunk around units of meaning and compare variants with the same evaluation questions |
| assuming privacy requires every component to be local | the system may become harder to run than the actual privacy requirement demands | decide which artifacts must stay local: documents, chunks, embeddings, prompts, index, or final generation |
| blaming the vector store for corpus quality issues | tool changes hide the real problem while bad sources continue producing bad answers | inspect source inclusion, freshness, duplicates, and metadata before replacing storage |
| skipping source metadata | users cannot verify answers, debug stale chunks, or rebuild trust after a wrong citation | store source path, section, timestamp or version, privacy class, and chunk identifier for every chunk |
| testing only successful questions | the system appears better than it is and may answer unsupported questions confidently | include factual, reasoning, and not-enough-evidence questions in every evaluation run |
| adding remote services without a privacy review | restricted text may leave the machine through embeddings, prompts, logs, or telemetry | review the data path before integration and block restricted chunks from remote calls |

## Quiz

**Q1.** Your teammate proposes a distributed queue, a managed vector database, and three services for a private assistant over a few folders of weekly updated lab notes. The workstation has enough disk and memory for local indexing. What design would you recommend first, and what evidence would make you change your mind?

<details>
<summary>Answer</summary>

Start with a one-machine design: curated documents, a chunking pipeline, source metadata, local embeddings or a privacy-approved embedding choice, a local index, retrieval-only debug output, and a generator that cites sources. The current workload has one machine, low update frequency, and no stated concurrency requirement, so distributed ingestion and managed storage add operating burden before they solve a measured problem.

You would change your mind if rebuild time became unacceptable, multiple users needed reliable concurrent access, filtering requirements outgrew the local index, or the corpus no longer fit comfortably on one machine. The key is to move up because a measured symptom appears, not because the smaller design looks less impressive.
</details>

**Q2.** You compare two chunking strategies over the same project documentation. The smaller chunks retrieve exact command snippets well, but answers about architecture decisions miss important reasoning. The larger chunks cite broader sections and answer decision questions better, with acceptable latency. Which strategy should win for this corpus, and why?

<details>
<summary>Answer</summary>

The larger chunks should probably win for this corpus because the dominant questions require surrounding rationale, not only exact snippets. The decision is justified by workload fit: architecture decisions usually span multiple paragraphs, so preserving context improves the generator's evidence.

The smaller chunks may still be useful for command-heavy subcorpora, but the module teaches that chunk size should preserve the unit of meaning users ask about. A senior design could split corpora by document type later, but the first decision should follow evaluation results.
</details>

**Q3.** A learner reports that their RAG system confidently answers questions, but users do not trust it because the answers only say "source: chunk 12" with no file path, timestamp, or section. What is the root design failure, and how should they fix it?

<details>
<summary>Answer</summary>

The root failure is missing source discipline. The system may retrieve useful text, but the citation is not auditable by a human because it does not identify where the evidence came from or whether it is current.

They should add manifest metadata for every chunk, including source path, section or page range, chunk identifier, timestamp or version, and privacy class. Then the answer contract should require citations that point to those fields, so users can inspect the evidence and debug stale or unsupported answers.
</details>

**Q4.** Your corpus contains current runbooks and archived runbooks with conflicting procedures. Retrieval often returns both, and the generator blends them into an unsafe answer. What should you fix before changing the embedding model?

<details>
<summary>Answer</summary>

Fix corpus and metadata discipline first. The system is retrieving contradictory evidence because the corpus does not clearly distinguish current authoritative sources from archived sources.

Better moves include removing archived documents from the active corpus, adding status metadata, filtering retrieval to current sources by default, or splitting archived material into a separate corpus. Changing the embedding model may improve similarity scores, but it will not decide which conflicting procedure is authoritative unless the data model exposes that distinction.
</details>

**Q5.** A home server uses local embeddings because documents are restricted, but the owner wants to use a remote generator for final answers. The current prompt sends raw retrieved chunks to that generator. How do you evaluate whether this hybrid design is acceptable?

<details>
<summary>Answer</summary>

Evaluate the privacy boundary by asking which artifacts are allowed to leave the machine. If restricted raw chunks cannot leave, then sending them to a remote generator violates the requirement even though embeddings and the index remain local.

The design may still be acceptable if the policy allows selected private chunks to be sent, or if the system summarizes or redacts content locally before remote generation. The module's guidance is to decide which parts must remain local rather than assuming that "hybrid" is automatically safe.
</details>

**Q6.** After increasing overlap heavily, a learner sees a larger index and top retrieval results that repeat nearly the same passage. Answer quality has not improved. What happened, and what should they test next?

<details>
<summary>Answer</summary>

The overlap likely created near-duplicate chunks that consume storage and crowd the top results without adding new evidence. The generator receives repeated context instead of diverse supporting material, so answer quality does not improve.

They should reduce overlap, deduplicate similar chunks, and rerun the same evaluation questions. If boundary loss is still a problem, they can try section-aware chunking or a slightly larger chunk size rather than multiplying overlap.
</details>

**Q7.** A private RAG project becomes popular inside a small organization. Several teams now need concurrent access, ingestion runs throughout the day, metadata filtering controls correctness, and uptime matters. What does this indicate, and how should the team migrate without losing what they learned?

<details>
<summary>Answer</summary>

This indicates the system is moving beyond home scale. The workload now includes concurrency, continuous ingestion, correctness-critical filtering, and uptime expectations that justify more serious infrastructure.

The team should migrate incrementally while preserving contracts. Keep the chunk manifest and evaluation questions, replace the local index with a service or database that supports the needed filters, add an API for shared access, and maintain retrieval-only debugging. The home-scale system becomes the evidence base for the larger architecture.
</details>

## Hands-On Exercise

**Goal:** Build and evaluate a small private RAG-style retrieval prototype on one machine, compare two chunking strategies, and justify a home-scale design using evidence rather than tool preference.

This exercise uses a lightweight retrieval harness so you can focus on architecture, corpus discipline, chunking, metadata, and evaluation.
It does not require cloud services or a GPU.
If you already have an embedding model and vector index, you may adapt the same steps, but keep the evaluation structure unchanged.

### Step 1: Create a Bounded Corpus

Choose a small local folder with trusted documents.
Markdown notes, text exports, converted PDFs, project documentation, or runbooks are good choices.
Avoid indexing a whole home directory because the noise will hide the lesson.

If you do not already have a suitable folder, create a working directory and populate it with the tiny sample corpus below so every later step shares the same trusted files.

```bash
mkdir -p home-rag-lab/corpus home-rag-lab/eval
cat > home-rag-lab/corpus/networking.md <<'EOF'
# Networking Runbook

## DNS checks
When a service cannot resolve a hostname, first confirm the local resolver configuration, then query the expected DNS server directly.
Record the failing hostname, the resolver address, and whether the failure affects one application or the whole machine.

## Routing checks
If DNS works but connections still fail, inspect the route table and confirm that the expected default gateway is present.
A missing route usually points to host networking or VPN configuration rather than application code.
EOF

cat > home-rag-lab/corpus/architecture.md <<'EOF'
# Architecture Decision Notes

## Local index decision
The first version keeps the document corpus and retrieval index on the workstation because the notes contain private project details.
The team accepts weekly rebuilds because the corpus changes slowly and one user asks questions at a time.

## Remote generation exception
The generator may be remote only when prompts exclude restricted documents.
Restricted chunks must not leave the workstation, even when the model would produce better prose.
EOF

cat > home-rag-lab/corpus/lab-procedure.md <<'EOF'
# Lab Procedure

## Rebuild workflow
Delete the generated index, recreate chunks from the corpus, build the retrieval files, and run the evaluation questions.
A rebuild is successful only when cited answers point back to source files and stale documents are not included.
EOF
```

Before moving on, confirm the step-one success criteria in the checklist below and make sure each item reflects what you would require in a real home-scale corpus review.

- [ ] The corpus is intentionally bounded rather than "everything available."
- [ ] You can name which documents are trusted and which documents are excluded.
- [ ] Sensitive or restricted files are not mixed accidentally with public files.
- [ ] You can delete the generated index later without losing the source documents.

After the checklist passes, run the filesystem commands below to inspect file count, word count, and on-disk size before you invest time in chunking variants.

```bash
find home-rag-lab/corpus -type f | sort
wc -w home-rag-lab/corpus/*
du -sh home-rag-lab/corpus
```

### Step 2: Write the Boundary Statement

Before building anything, write the operating boundary in a boundary note so the prototype cannot drift into a tool tour; use the template below to capture users, corpus scope, privacy rules, update cadence, hardware assumptions, and the answer contract.

```bash
cat > home-rag-lab/boundary.txt <<'EOF'
users: one learner on one workstation
documents: curated local Markdown and text files
privacy: documents and index stay local
update_rate: weekly or manual rebuild
hardware: CPU-first; no GPU assumed
answer_contract: cite source files or say evidence is insufficient
EOF
cat home-rag-lab/boundary.txt
```

Review the boundary note against the checklist below and treat any missing field as a design gap that would block a trustworthy home-scale deployment.

- [ ] The user count is explicit.
- [ ] The document scope is explicit.
- [ ] The privacy boundary is explicit.
- [ ] The update rate is explicit.
- [ ] The answer contract mentions citations or abstention.

### Step 3: Create Evaluation Questions Before Tuning

Write questions that represent real use.
Include a factual lookup, a reasoning question, and a question that should not be answered from the corpus.

```bash
cat > home-rag-lab/eval/questions.txt <<'EOF'
What should I check first when a service cannot resolve a hostname?
Why did the first version keep the index on the workstation?
When is remote generation allowed in this design?
How do I rebuild the local retrieval files?
What Kubernetes admission controller should this project use?
EOF
nl -ba home-rag-lab/eval/questions.txt
```

Use the checklist below to confirm that your evaluation set covers lookup, reasoning, and abstention cases before you compare chunking variants or touch any embedding model.

- [ ] At least one question should retrieve a specific operational procedure.
- [ ] At least one question should retrieve design rationale rather than a single fact.
- [ ] At least one question should return not enough evidence.
- [ ] The questions are written before comparing chunking variants.

### Step 4: Create a Runnable Retrieval Harness

The following script uses standard-library lexical retrieval so the exercise runs everywhere.
It is not a replacement for embedding-based retrieval, but it is enough to test corpus boundaries, chunking, metadata, source traceability, and evaluation habits.
You can later replace the scoring function with embeddings while keeping the manifest and questions.

```bash
cat > home-rag-lab/home_rag.py <<'PY'
#!/usr/bin/env python3
import argparse
import json
import math
import re
import time
from collections import Counter
from pathlib import Path

TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")

def tokenize(text):
    return [token.lower() for token in TOKEN_RE.findall(text)]

def read_documents(corpus_dir):
    docs = []
    for path in sorted(Path(corpus_dir).rglob("*")):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            docs.append({"source": str(path), "text": text})
    return docs

def chunk_words(words, size, overlap):
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap >= size:
        raise ValueError("overlap must be smaller than chunk size")
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        yield start, end, words[start:end]
        if end == len(words):
            break
        start = end - overlap

def build(args):
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = out_dir / "chunks.jsonl"
    meta_path = out_dir / "manifest.jsonl"
    chunk_count = 0
    started = time.time()

    with chunks_path.open("w", encoding="utf-8") as chunks_file, meta_path.open("w", encoding="utf-8") as meta_file:
        for doc in read_documents(args.corpus):
            words = doc["text"].split()
            for index, (start, end, chunk_words_list) in enumerate(chunk_words(words, args.size, args.overlap), start=1):
                chunk_text = " ".join(chunk_words_list)
                chunk_id = f"{doc['source']}::chunk-{index}"
                record = {
                    "chunk_id": chunk_id,
                    "source": doc["source"],
                    "word_start": start,
                    "word_end": end,
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(Path(doc["source"]).stat().st_mtime)),
                    "privacy": args.privacy,
                    "text": chunk_text,
                }
                chunks_file.write(json.dumps(record, sort_keys=True) + "\n")
                meta_file.write(json.dumps({key: record[key] for key in record if key != "text"}, sort_keys=True) + "\n")
                chunk_count += 1

    elapsed = time.time() - started
    print(json.dumps({"chunks": chunk_count, "out": str(out_dir), "seconds": round(elapsed, 3)}, sort_keys=True))

def load_chunks(index_dir):
    path = Path(index_dir) / "chunks.jsonl"
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]

def score(query_tokens, chunk_tokens):
    if not query_tokens or not chunk_tokens:
        return 0.0
    query_counts = Counter(query_tokens)
    chunk_counts = Counter(chunk_tokens)
    overlap = set(query_counts) & set(chunk_counts)
    raw = sum(query_counts[token] * chunk_counts[token] for token in overlap)
    norm = math.sqrt(sum(value * value for value in query_counts.values())) * math.sqrt(sum(value * value for value in chunk_counts.values()))
    return raw / norm if norm else 0.0

def query(args):
    chunks = load_chunks(args.index)
    questions = Path(args.questions).read_text(encoding="utf-8").splitlines()
    for question in [line for line in questions if line.strip()]:
        query_tokens = tokenize(question)
        ranked = []
        for chunk in chunks:
            ranked.append((score(query_tokens, tokenize(chunk["text"])), chunk))
        ranked.sort(key=lambda item: item[0], reverse=True)
        print(f"\nQUESTION: {question}")
        useful = [item for item in ranked[: args.top_k] if item[0] > 0]
        if not useful:
            print("ANSWER: not enough evidence in the local corpus")
            continue
        for rank, (chunk_score, chunk) in enumerate(useful, start=1):
            preview = chunk["text"][:220].replace("\n", " ")
            print(f"RESULT {rank}: score={chunk_score:.3f} source={chunk['source']} chunk={chunk['chunk_id']}")
            print(f"PREVIEW: {preview}")

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build")
    build_parser.add_argument("--corpus", required=True)
    build_parser.add_argument("--out", required=True)
    build_parser.add_argument("--size", type=int, required=True)
    build_parser.add_argument("--overlap", type=int, required=True)
    build_parser.add_argument("--privacy", default="private")
    build_parser.set_defaults(func=build)

    query_parser = sub.add_parser("query")
    query_parser.add_argument("--index", required=True)
    query_parser.add_argument("--questions", required=True)
    query_parser.add_argument("--top-k", type=int, default=3)
    query_parser.set_defaults(func=query)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
PY
chmod +x home-rag-lab/home_rag.py
```

Confirm the harness meets the step-four success criteria below, especially the requirement that every retrieved chunk remains traceable to a source path without calling any network service.

- [ ] The script is local and uses no network service.
- [ ] The script writes both chunk text and a metadata manifest.
- [ ] The script can return source paths for retrieved chunks.
- [ ] You understand that the scoring method is a stand-in for the retrieval layer, not the whole lesson.

### Step 5: Build Two Chunking Variants

Build one index with smaller chunks and one with larger chunks.
Keep overlap modest so you can observe the effect without flooding retrieval with duplicates.

```bash
./home-rag-lab/home_rag.py build \
  --corpus home-rag-lab/corpus \
  --out home-rag-lab/index-small \
  --size 55 \
  --overlap 8

./home-rag-lab/home_rag.py build \
  --corpus home-rag-lab/corpus \
  --out home-rag-lab/index-large \
  --size 110 \
  --overlap 12
```

After both builds finish, compare chunk counts and on-disk size using the commands below so your later design decision cites measured storage and indexing cost rather than intuition alone.

```bash
wc -l home-rag-lab/index-small/chunks.jsonl home-rag-lab/index-large/chunks.jsonl
head -n 2 home-rag-lab/index-small/manifest.jsonl
du -sh home-rag-lab/index-small home-rag-lab/index-large
```

Use the checklist below to confirm that both variants were built fairly over the same corpus with identical metadata fields.

- [ ] Both variants use the same corpus.
- [ ] Both variants preserve source metadata.
- [ ] The larger variant changes chunk size without changing the evaluation questions.
- [ ] You can compare chunk count and disk usage for both variants.

### Step 6: Run Retrieval-Only Tests

Run the same questions against both variants.
Do not add generation yet.
First prove that the retrieval layer can find useful evidence.

```bash
./home-rag-lab/home_rag.py query \
  --index home-rag-lab/index-small \
  --questions home-rag-lab/eval/questions.txt \
  --top-k 3

./home-rag-lab/home_rag.py query \
  --index home-rag-lab/index-large \
  --questions home-rag-lab/eval/questions.txt \
  --top-k 3
```

Inspect the retrieval-only output against the checklist below and explain, in your own words, which variant surfaces more useful evidence for lookup versus rationale questions.

- [ ] Relevant sources appear for the DNS troubleshooting question.
- [ ] Relevant sources appear for the local index design question.
- [ ] Relevant sources appear for the remote generation boundary question.
- [ ] The unsupported Kubernetes admission-controller question does not receive strong evidence.
- [ ] You can explain which chunking variant gives more useful previews.

### Step 7: Record a Design Decision

Create a short decision record based on evidence.
Do not write "I chose it because it seemed better."
Tie the decision to retrieval relevance, source usefulness, storage size, indexing effort, and privacy.

```bash
cat > home-rag-lab/decision.md <<'EOF'
# Home-Scale RAG Design Decision

Chosen variant: index-large or index-small

Reasoning:
- Retrieval relevance:
- Source usefulness:
- Storage and indexing cost:
- Privacy boundary:
- Rebuild plan:

Next trigger for change:
- Move to a stronger local vector index only if filtering, corpus size, or latency becomes painful in measured evaluation runs.
EOF
sed -n '1,120p' home-rag-lab/decision.md
```

Your decision record should satisfy the checklist below by tying the chosen variant to observed retrieval behavior, privacy boundaries, and a measurable trigger for the next architecture change.

- [ ] The decision names the chosen variant.
- [ ] The reasoning cites observed retrieval behavior.
- [ ] The privacy boundary matches the boundary statement.
- [ ] The next growth trigger is tied to a measurable problem.
- [ ] The design remains rebuildable from source documents.

### Step 8: Extend the Prototype Carefully

If you have an embedding model available, replace the lexical scoring function with embedding similarity.
Keep the same corpus, manifest fields, evaluation questions, and decision record.
That is how you learn whether embeddings improve the system rather than merely changing the stack.

If you have a local generator available, add an answer step that prints cited sources before the answer.
Require the generator to say "not enough evidence" when retrieved chunks do not support the question.
Do not hide retrieval results until you have debugged several failures.

If you extend the prototype with embeddings or a generator, use the optional-step checklist below to ensure the boundary statement still governs what may leave the machine.

- [ ] Any embedding or generator addition preserves source metadata.
- [ ] Remote services are used only if the boundary statement allows them.
- [ ] Retrieval-only debug output remains available.
- [ ] The same evaluation questions can be rerun after the change.

### Final Exercise Success Criteria

- [ ] The corpus is bounded, curated, and separated from generated artifacts.
- [ ] The boundary statement names users, documents, privacy, update rate, hardware, and answer contract.
- [ ] Two chunking strategies were built over the same source documents.
- [ ] Every chunk has source metadata that can support citations.
- [ ] Retrieval-only tests were run before answer generation was added.
- [ ] At least one unsupported question was tested for abstention behavior.
- [ ] The chosen design is justified with evidence rather than tool preference.
- [ ] The next migration step is tied to a measured symptom, not architectural fashion.

## Next Module

- [Local Inference Stack for Learners](../ai-infrastructure/module-1.4-local-inference-stack-for-learners/)
- [Advanced RAG Patterns](../module-1.3-advanced-rag-patterns/)
- [Notebooks to Production for ML/LLMs](../mlops/module-1.11-notebooks-to-production-for-ml-llms/)

## Sources

- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) — Foundational RAG paper covering the retrieve-then-generate pattern that this module adapts to smaller local systems.
- [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://arxiv.org/abs/1908.10084) — Background on bi-encoder sentence embeddings used in many local semantic search pipelines.
- [Faiss](https://github.com/facebookresearch/faiss) — Upstream reference for lightweight local dense-vector indexing on a single machine.
- [Rethinking Chunk Size For Long-Document Retrieval: A Multi-Dataset Analysis](https://arxiv.org/abs/2505.21700) — Empirical analysis showing that smaller chunks help factual lookups while larger chunks preserve contextual reasoning.
- [SURE-RAG: Sufficiency and Uncertainty-Aware Evidence Verification for Selective Retrieval-Augmented Generation](https://arxiv.org/abs/2605.03534) — Selective answering framework emphasizing abstention when retrieved evidence is insufficient.
- [Magic Mushroom: A Customizable Benchmark for Fine-grained Analysis of Retrieval Noise Erosion in RAG Systems](https://arxiv.org/abs/2506.03901) — Benchmark for diagnosing how corpus and retrieval noise erode answer quality before blaming the generator.
- [RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation](https://arxiv.org/abs/2408.08067) — Diagnostic framework separating retrieval failures from generation failures during evaluation.
- [Build a RAG App (LangChain tutorial)](https://python.langchain.com/docs/tutorials/rag/) — End-to-end reference for loaders, splitters, retrievers, and prompt chains in a local Python workflow.
- [Chroma documentation](https://docs.trychroma.com/) — Embedded persistent vector store often used for single-machine prototypes with metadata filtering.
- [Qdrant Quickstart](https://qdrant.tech/documentation/quickstart/) — Local or in-process vector database setup patterns when an embedded index outgrows flat files.
- [Sentence Transformers — Pretrained Models](https://www.sbert.net/docs/pretrained_models.html) — Catalog of bi-encoder models suitable for CPU-first home indexing and query encoding.
- [Ollama documentation](https://github.com/ollama/ollama/blob/main/docs/README.md) — Local model serving option for fully on-machine or hybrid answer generation.

## Learner check

> Home-scale RAG succeeds when you define the operating boundary first, curate a bounded corpus with auditable metadata, keep contracts explicit across chunking and indexing, test retrieval before generation, and grow the architecture only when measured pain—not tool fashion—demands it.
