---
citations_verified: true
title: "Embeddings & Semantic Search"
slug: ai-ml-engineering/generative-ai/module-1.4-embeddings-semantic-search
sidebar:
  order: 305
---

> **AI/ML Engineering Track** | Complexity: `[COMPLEX]` | Time: 5-6 hours
>
> **Reading Time**: Approximately 2-3 hours
>
> **Prerequisites**: Python basics, vector intuition from linear algebra, basic API usage, and earlier generative AI modules on tokens and retrieval.

---

## Learning Outcomes

By the end of this module, you will be able to:

- **Implement** a runnable semantic search workflow that embeds documents, embeds queries, ranks candidates, and returns relevant results.
- **Compare** sparse keyword retrieval, dense embedding retrieval, and hybrid retrieval for real search and recommendation scenarios.
- **Debug** common embedding failures such as poor chunking, model mismatch, stale caches, over-broad matches, and weak evaluation data.
- **Evaluate** embedding models using task-specific retrieval metrics instead of relying only on generic benchmark scores.
- **Design** a production-oriented embedding pipeline with caching, metadata filters, re-ranking, monitoring, and privacy-aware model selection.

---

## Why This Module Matters

A support engineer is on call during a major customer incident. The database cluster is healthy, the application pods are running, and every dashboard says the platform is alive, yet customers cannot complete checkout. The engineer searches the internal runbook portal for "payment timeout after cart submit" and gets nothing useful because the runbook says "gateway callback latency during order finalization." The answer exists, but keyword search cannot bridge the vocabulary gap between the incident report and the documented fix.

A product manager sees the same failure from a different angle. Customers type "warm winter jacket" into an e-commerce search box, but the catalog uses "insulated parka," "thermal shell," and "cold-weather coat." The search system technically works because it returns exact matches, yet it fails the business because it cannot recognize that different words can describe the same intent. When search misses relevant items, users leave, support tickets rise, and teams start maintaining fragile synonym lists by hand.

An AI platform team faces a more subtle version of the problem. They build a retrieval-augmented generation system, but the model answers from irrelevant context because the retrieval layer returns documents that share words with the question rather than documents that answer the question. The language model looks like the failure point, but the root cause is earlier in the pipeline. Bad retrieval produces bad context, and bad context makes even a strong model behave like it is guessing.

Embeddings matter because they turn text into geometry. Once a sentence, document, ticket, query, or product description becomes a vector, software can measure semantic closeness instead of only checking exact words. That single shift powers semantic search, recommendations, duplicate detection, ticket routing, clustering, anomaly detection, and many production RAG systems. The rest of this module teaches how to make that shift carefully enough that it improves systems instead of adding a new opaque failure mode.

---

## The Meaning Problem Before Embeddings

Computers handle strings naturally, but strings are not meaning. The text `"restart failed service"` and the text `"recover crashed daemon"` share almost no exact tokens, even though an operator would treat them as close matches. Traditional search engines can improve keyword matching with stemming, synonyms, and ranking features, but each addition still starts from surface form. The more specialized the domain, the more vocabulary mismatch hurts retrieval quality.

The problem becomes clearer when you inspect what a keyword system sees. It receives a query, splits it into tokens, checks which documents contain those tokens, and ranks matches based on frequency and rarity. That process is useful for many workloads, especially when exact terms matter, but it struggles when the user asks in one vocabulary and the author wrote in another. The system can find "restart" when the document says "restart," but it cannot naturally infer that "recover" and "reinitialize" might be useful neighbors.

| User Query | Relevant Document Text | Keyword Search Risk | Semantic Search Opportunity |
|---|---|---|---|
| "restart failed service" | "recover crashed daemon after process exit" | Few exact words overlap, so the document may rank low. | The concepts of service recovery and daemon failure can rank close together. |
| "refund duplicate charge" | "payment reversal for double billing" | Exact terms differ across finance and support vocabulary. | Payment, duplicate billing, and reversal can be connected by meaning. |
| "pod cannot reach database" | "network policy blocks egress to PostgreSQL" | The query describes symptoms while the runbook describes cause. | Symptom language and cause language can become retrievable neighbors. |
| "new hire laptop setup" | "developer workstation provisioning checklist" | Informal phrasing misses formal documentation titles. | The intent of preparing a workstation can dominate wording differences. |

Embeddings solve this by representing text as a list of numbers. Those numbers are learned by models trained to place related texts near one another in a high-dimensional space. A vector is not a definition, and it is not a database row with human-readable fields. It is a compact numeric representation that lets software compare meaning using mathematical operations such as dot product, cosine similarity, and nearest-neighbor search.

```ascii
+-------------------------------+        +-------------------------------+
| Raw text                       |        | Embedding vector              |
| "recover crashed daemon"       | -----> | [0.018, -0.224, ..., 0.091]   |
+-------------------------------+        +-------------------------------+
                                                        |
                                                        v
+-------------------------------+        +-------------------------------+
| Raw query                      |        | Query vector                  |
| "restart failed service"       | -----> | [0.021, -0.219, ..., 0.087]   |
+-------------------------------+        +-------------------------------+
                                                        |
                                                        v
                                      +-----------------------------+
                                      | Compare direction/distance  |
                                      | Return nearest documents    |
                                      +-----------------------------+
```

The key beginner mistake is thinking that an embedding model "stores" the original sentence in the vector. It does not. The vector preserves patterns that are useful for the model's training objective, usually patterns about relatedness, context, or retrieval relevance. Some details survive strongly, some details blur, and some details vanish. That is why embeddings are powerful for finding candidates but often need filters, re-rankers, or exact checks when precision matters.

> **Active Learning Prompt: Predict the Retrieval Failure**
>
> Imagine a runbook has the title "OAuth token refresh loop after identity provider failover." A developer searches for "login keeps asking users to sign in again." Before reading further, decide whether keyword search or embedding search is more likely to find the runbook. Then name one reason the other approach might still be useful.

A strong search system rarely treats "semantic" and "keyword" as enemies. Keyword search is excellent when the exact term is decisive, such as an error code, API field, customer ID, package name, or Kubernetes object name. Embedding search is excellent when the query expresses intent, symptoms, or paraphrases. Production systems often combine both because users search with a mixture of exact identifiers and fuzzy human language.

---

## What an Embedding Actually Represents

An embedding is a dense vector representation of an input. "Dense" means most positions in the vector contain non-zero values, unlike a sparse bag-of-words vector where each dimension corresponds to a vocabulary term and most positions are empty. Dense vectors are not directly interpretable by humans, but their geometry is useful. If two texts mean similar things to the embedding model, their vectors tend to point in similar directions.

A sentence embedding compresses an entire piece of text into one vector. That text might be a short query, a paragraph, a document chunk, a product title, a support ticket, or a category description. The output length depends on the model. Some models produce a few hundred dimensions, some produce around a thousand, and commercial embedding APIs may produce larger vectors with configurable dimensionality. The exact dimension count matters for storage and compatibility, but the more important question is whether the model ranks your relevant items above irrelevant ones.

| Representation | Shape | Strength | Weakness | Typical Use |
|---|---|---|---|---|
| One-hot vector | One dimension per token or category | Simple and exact for small controlled sets | Cannot represent similarity between different tokens | Toy examples and categorical features |
| TF-IDF vector | Sparse vocabulary-sized vector | Fast, interpretable, strong exact-term baseline | Weak on synonyms and paraphrases | Keyword search, hybrid retrieval, legal exact matching |
| Dense embedding | Fixed-length learned vector | Captures semantic similarity and paraphrase | Less interpretable, model-dependent, can blur details | Semantic search, RAG, recommendations, clustering |
| Cross-encoder score | Query-document pair scored together | Strong precision because both texts are read jointly | Slower and not suitable for indexing every pair | Re-ranking top candidates after retrieval |

A helpful mental model is a map. On a normal map, nearby cities are physically close. In embedding space, nearby vectors are semantically close according to the training data and objective. "Laptop battery replacement" may sit near "notebook power repair," while "battery chicken recipe" should be far away despite sharing the token "battery." This geometry is not perfect, but it gives software a way to search by meaning rather than only by spelling.

The map analogy also has limits. A real map has two or three visible dimensions, but embedding spaces often have hundreds or thousands of dimensions. You cannot inspect dimension 192 and say it always means "security" or "urgency." Individual dimensions may participate in many patterns at once. Engineers should treat the vector as a learned feature representation, then evaluate its behavior empirically on the specific retrieval task.

```python
import numpy as np

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a, dtype=np.float64)
    b = np.array(vec_b, dtype=np.float64)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        raise ValueError("Cosine similarity is undefined for a zero vector.")
    return float(np.dot(a, b) / denominator)

restart_service = [0.9, 0.1, 0.2]
recover_daemon = [0.86, 0.12, 0.22]
cook_pasta = [-0.1, 0.8, 0.3]

print(round(cosine_similarity(restart_service, recover_daemon), 3))
print(round(cosine_similarity(restart_service, cook_pasta), 3))
```

This tiny example uses three dimensions so you can read it, but production embeddings use far more dimensions. The function is still the same idea: convert both vectors to numeric arrays, compute their dot product, normalize by their magnitudes, and compare the resulting score. In many text retrieval systems, a higher cosine similarity means the candidate is more likely to be relevant to the query.

---

## Sparse Retrieval, Dense Retrieval, and Hybrid Search

Sparse retrieval represents documents by the words they contain. TF-IDF and BM25 are common examples. If a word is rare across the corpus but appears in a document, that word becomes a strong signal. This works very well for error codes, identifiers, exact product names, legal phrases, and technical commands. A query for `CrashLoopBackOff` should not need semantic imagination; it should find the documents containing that exact Kubernetes status.

Dense retrieval represents documents by learned vectors. Instead of asking whether the document contains the query words, it asks whether the query vector is near the document vector. This is useful when the query describes the need in different words from the document. Dense retrieval can find "recover crashed daemon" for "restart failed service," but it may also retrieve documents that are topically related without being exact answers.

Hybrid retrieval combines sparse and dense scores. This is common in production because exact terms and semantic intent both matter. A user searching for "PostgreSQL FATAL remaining connection slots reserved" wants the exact error message preserved, but they may also benefit from documents titled "database pool exhaustion during deploy." Hybrid search gives the system a way to reward both lexical overlap and semantic closeness.

| Retrieval Mode | What It Rewards | Where It Wins | Where It Fails | Production Pattern |
|---|---|---|---|---|
| Sparse keyword retrieval | Exact or near-exact token overlap | Error codes, names, commands, regulated phrases | Vocabulary mismatch and paraphrase | Keep as a baseline and exact-match safety net |
| Dense embedding retrieval | Semantic closeness in vector space | Symptoms, intent, recommendations, similar cases | Over-broad topical matches and missed exact constraints | Use for candidate generation and discovery |
| Hybrid retrieval | Both lexical and semantic evidence | Mixed technical searches with exact terms and natural language | Requires score tuning and evaluation data | Combine scores, then re-rank top candidates |
| Re-ranked retrieval | Pairwise relevance after candidate generation | Precision-sensitive answer contexts | Higher latency and cost at query time | Apply to top twenty to one hundred candidates |

A mature retrieval pipeline usually has stages. It normalizes documents, chunks them, embeds chunks, stores vectors with metadata, receives a query, retrieves candidates, filters by metadata, optionally re-ranks, and returns a result set. Each stage can fail independently. A weak embedding model is only one possible problem; poor chunking, missing metadata, stale vectors, and bad ranking thresholds are just as common.

```mermaid
flowchart LR
    A[Source Documents] --> B[Clean and Normalize]
    B --> C[Chunk with Boundaries]
    C --> D[Generate Embeddings]
    D --> E[Store Vectors and Metadata]
    F[User Query] --> G[Embed Query]
    G --> H[Nearest Neighbor Search]
    E --> H
    H --> I[Metadata Filters]
    I --> J[Optional Re-ranker]
    J --> K[Ranked Results]
```

The diagram shows why semantic search is not just a model call. The embedding model is important, but it sits inside a data pipeline. If you split documents badly, the vector index stores weak representations. If you forget metadata, users cannot filter by version, product, language, or access control. If you skip evaluation, you may ship a system that feels impressive on demos and fails on real support tickets.

> **Active Learning Prompt: Choose the Retrieval Stack**
>
> Your team is searching internal incident reports. Queries often include exact service names, but users also describe symptoms in plain English. Pick sparse, dense, or hybrid retrieval, and justify your choice. Then name one metric you would collect before declaring the system better than the old search.

---

## The Embedding Workflow From Text to Results

The simplest semantic search workflow has four steps. First, generate embeddings for documents. Second, store those embeddings beside document identifiers and metadata. Third, generate an embedding for each user query. Fourth, compare the query embedding with document embeddings and return the nearest matches. This workflow is small enough to build in a local script, yet it contains the same core mechanics used by larger vector databases.

A worked example is the fastest way to build intuition. Suppose a documentation portal has four pages: service restart, service recovery, failed process troubleshooting, and pasta recipes. A user searches for "fix a crashed daemon." Keyword search might miss some relevant phrasing, but an embedding model should place the first three documents closer to the query than the recipe page. The code below runs locally with a sentence-transformers model and does not require an API key.

```bash
mkdir semantic-search-lab
cd semantic-search-lab
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install sentence-transformers numpy scikit-learn
```

```python
from sentence_transformers import SentenceTransformer
import numpy as np

DOCUMENTS = [
    "How to restart a service after a failed deployment",
    "Service recovery procedures for crashed daemons",
    "Troubleshooting failed processes on Linux servers",
    "Cooking pasta recipes for weeknight dinners",
]

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    denominator = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denominator == 0:
        raise ValueError("Cannot compare a zero-length vector.")
    return float(np.dot(vec_a, vec_b) / denominator)

model = SentenceTransformer("all-MiniLM-L6-v2")
document_embeddings = model.encode(DOCUMENTS, normalize_embeddings=False)
query = "fix a crashed daemon"
query_embedding = model.encode(query, normalize_embeddings=False)

scores = [
    (document, cosine_similarity(query_embedding, document_embedding))
    for document, document_embedding in zip(DOCUMENTS, document_embeddings)
]

for document, score in sorted(scores, key=lambda item: item[1], reverse=True):
    print(f"{score:.3f} - {document}")
```

This is a complete runnable search system, but it is not production-ready. It embeds every document every time the script runs, stores nothing, has no chunking, has no metadata, and performs a linear scan over all vectors. Those choices are acceptable for a classroom example because they keep the mechanism visible. They become wasteful or incorrect when the corpus grows, documents change, or users need reliable retrieval latency.

The next version separates indexing from querying. Indexing is the work you do when documents change: load content, split it into meaningful chunks, generate embeddings, and persist the vectors. Querying is the work you do for each user request: embed the query, search the stored vectors, and return the best chunks. Separating these phases is one of the first production design moves because document embeddings are expensive enough to cache and stable enough to reuse.

| Pipeline Stage | Input | Output | Common Failure | Practical Fix |
|---|---|---|---|---|
| Load | Markdown, tickets, product records, runbooks | Raw text plus source metadata | Hidden boilerplate pollutes chunks | Strip navigation, footers, and irrelevant templates |
| Chunk | Clean documents | Searchable text segments | Important ideas split across boundaries | Split by headings and paragraphs, then add overlap |
| Embed | Chunks | Dense vectors | Mixed models in the same index | Store model name and dimension with every index |
| Store | Vectors plus metadata | Searchable index | Lost access-control or version metadata | Persist source path, title, owner, language, and permissions |
| Query | User request | Query vector | Query too vague or overloaded | Rewrite, expand, or ask clarifying questions when needed |
| Retrieve | Query vector and index | Candidate chunks | Topical but non-answer results | Combine filters, hybrid search, and re-ranking |
| Evaluate | Queries and judged results | Retrieval quality metrics | Demo examples hide real misses | Build a labeled test set from actual user behavior |

Notice that the table treats retrieval as a system, not a model feature. A team can choose a strong embedding model and still fail because the chunk boundaries are poor. Another team can choose a modest local model and succeed because its corpus is clean, its metadata filters are correct, and its evaluation set matches real user queries. Senior engineers debug retrieval by walking the pipeline stage by stage rather than blaming the vector database first.

---

## Chunking: The Quiet Source of Retrieval Quality

Chunking is the process of splitting long documents into smaller pieces before embedding them. It matters because most embedding models have input limits and because a single vector must represent the whole chunk. If the chunk is too large, the vector becomes a blurred summary of many topics. If the chunk is too small, the vector lacks enough context to match realistic questions. Good chunking preserves meaning at the level users search for.

A common beginner approach is to split every document every fixed number of tokens. That is easy to implement, but it often cuts through sections, examples, or troubleshooting flows. A query about "why the rollout stalls after two replicas" may need the heading, the symptom paragraph, and the remediation steps in the same chunk. If those pieces land in separate vectors, none of the chunks fully represents the answer.

Better chunking starts with document structure. Markdown headings, paragraphs, list items, code blocks, and tables are signals. A chunk should usually contain a coherent section, not a random slice of text. For technical documentation, useful chunks often include the section title because the title carries intent that individual sentences may not repeat. Overlap can help preserve context near boundaries, but too much overlap creates duplicate results and wastes storage.

| Chunking Strategy | When It Helps | Risk | Senior-Level Adjustment |
|---|---|---|---|
| Fixed token windows | Quick baseline for unstructured text | Splits ideas and code examples arbitrarily | Use only as a fallback after structure-aware splitting |
| Heading-based chunks | Markdown docs, runbooks, tutorials | Very large sections can become too broad | Split large sections further by paragraphs or examples |
| Paragraph chunks | Articles, support knowledge bases | Small chunks may lack title context | Prefix each chunk with document and section title |
| Sliding overlap | Boundary-sensitive explanations | Duplicate results and inflated index size | Tune overlap using retrieval evaluation, not guesses |
| Semantic chunking | Documents with irregular structure | More complex and sometimes unstable | Use when simpler rules fail on real queries |

The best chunk size depends on the task. A FAQ answer may fit in a short chunk. A legal argument may need a longer passage to preserve qualifiers. A code troubleshooting guide may need both narrative and command output together. Avoid universal rules such as "always use five hundred tokens" unless you have measured the trade-off. Treat chunking as an experiment with a retrieval metric, not a formatting preference.

A practical chunk record should include more than text. Store the source path, document title, section heading, chunk index, language, version, product area, and access-control label. These fields let you filter results before or after vector search. They also make debugging possible when a user asks why a result appeared. Without metadata, every retrieval failure becomes a mystery vector in a database.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Chunk:
    source_id: str
    title: str
    heading: str
    index: int
    text: str
    product_area: str
    version: str

def build_chunk_text(chunk: Chunk) -> str:
    return (
        f"Document: {chunk.title}\n"
        f"Section: {chunk.heading}\n"
        f"Product: {chunk.product_area}\n"
        f"Version: {chunk.version}\n\n"
        f"{chunk.text}"
    )

example = Chunk(
    source_id="runbooks/payments.md",
    title="Payments Runbook",
    heading="Gateway callback latency",
    index=3,
    text="If checkout succeeds but callbacks time out, inspect the gateway queue depth.",
    product_area="payments",
    version="2026.04",
)

print(build_chunk_text(example))
```

This example shows a small but important design choice. The vector should represent enough context for retrieval, not merely the raw paragraph. Prefixing a chunk with title and section information can improve matching because user queries often refer to the broader topic rather than a sentence inside the chunk. However, do not add noisy metadata just because you have it. Metadata should clarify the chunk's meaning or support filtering.

---

## Measuring Similarity Without Fooling Yourself

Cosine similarity is widely used because it compares vector direction instead of absolute magnitude. If two vectors point in the same direction, their cosine similarity is high even if one vector is longer. This often fits text embeddings because direction tends to encode semantic pattern more reliably than raw length. Some systems normalize vectors at indexing time so cosine similarity becomes equivalent to a dot product over normalized vectors.

Euclidean distance can also be useful depending on the model and index configuration, but engineers must not mix metrics casually. A vector database configured for dot product may produce different rankings from one configured for cosine distance. Some embedding models are trained or documented with a preferred similarity metric. The safest habit is to read the model guidance, store the metric in index metadata, and evaluate the chosen metric against real queries.

| Similarity Measure | Intuition | Best Fit | Risk |
|---|---|---|---|
| Cosine similarity | Compares direction between vectors | Text embeddings where orientation captures meaning | Scores are relative and model-specific, not universal truth |
| Dot product | Rewards alignment and magnitude | Normalized vectors or models trained for dot-product retrieval | Magnitude can dominate if vectors are not normalized appropriately |
| Euclidean distance | Measures straight-line distance | Some clustering and geometric analyses | Length effects may distort text relevance |
| Cross-encoder score | Reads query and candidate together | Precision re-ranking after retrieval | Too slow for comparing against every document |

Similarity scores are not confidence scores. A cosine score of `0.82` from one model and corpus does not mean the same thing as `0.82` from another model and corpus. Score distributions shift with chunk size, domain, language, query length, and preprocessing. In production, thresholds should be calibrated with examples. If you need to decide whether to show "no results," collect queries, judge candidate relevance, and choose a threshold based on measured precision and recall.

A worked threshold example makes the danger concrete. Suppose your first demo query returns three relevant documents above `0.75`, so you set `0.75` as a global threshold. The next day, users search for exact error codes, and relevant chunks score lower because the embedding model does not care strongly about that identifier. Later, broad conceptual queries return many weakly related chunks above the threshold. The single number looked clean, but the retrieval behavior was more complex.

The better approach is to evaluate ranked results. For search, common metrics include Recall@K, Precision@K, Mean Reciprocal Rank, and nDCG. Recall@K asks whether at least one relevant result appeared in the top K. Precision@K asks what fraction of the top K results were relevant. Mean Reciprocal Rank rewards placing the first relevant answer near the top. These metrics align better with user experience than raw similarity thresholds.

| Metric | Question It Answers | Use When | Watch Out For |
|---|---|---|---|
| Recall@K | Did the relevant item appear in the top K results? | Candidate retrieval for RAG or support search | High recall can still include many irrelevant candidates |
| Precision@K | How many top results are actually relevant? | User-facing search results | Requires judged results and can punish diverse useful answers |
| Mean Reciprocal Rank | How high is the first useful result? | Navigational queries with one best answer | Less useful when many answers are equally acceptable |
| nDCG | Are highly relevant results ranked above partially relevant ones? | Graded relevance evaluation | Requires more careful human labels |
| Latency percentile | How long do users wait at p50, p95, and p99? | Production readiness | Fast bad results are still bad results |
| Cost per query | What does each search cost in model and infrastructure spend? | Model and architecture selection | Low cost is not useful if recall collapses |

Evaluation begins with a small set of realistic queries. Do not create only easy examples that mirror document titles. Mine search logs, support tickets, incident summaries, product questions, and user interviews. For each query, identify which chunks should be considered relevant. Then compare retrieval variants: sparse only, dense only, hybrid, different chunk sizes, different embedding models, and optional re-ranking. The winning system is the one that improves the metric that matches the product goal.

---

## Worked Example: Build a Cached Local Semantic Search Index

The next example builds a small search index with disk caching. It uses local sentence-transformers so you can run it without sending data to a hosted API. The goal is not to replace a vector database. The goal is to make the indexing and query phases concrete before you add production infrastructure. Once you can explain this script, a managed vector database becomes an optimization rather than magic.

Create a file named `search.py` in the lab directory. The script accepts a directory of markdown files, embeds their content, caches vectors in a compressed NumPy archive, and supports a non-interactive query mode. It intentionally keeps the storage format simple so you can inspect the moving parts. For a real system, you would add chunking by headings, permissions, incremental updates, and a real approximate nearest neighbor index.

```python
import argparse
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
CACHE_FILE = "semantic_index.npz"

def read_markdown_files(docs_dir: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for path in sorted(docs_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        compact_text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if compact_text:
            records.append((str(path), compact_text))
    return records

def build_or_load_index(docs_dir: Path, rebuild: bool) -> tuple[list[str], list[str], np.ndarray]:
    cache_path = docs_dir / CACHE_FILE
    if cache_path.exists() and not rebuild:
        cached = np.load(cache_path, allow_pickle=True)
        paths = cached["paths"].tolist()
        texts = cached["texts"].tolist()
        embeddings = cached["embeddings"]
        return paths, texts, embeddings

    records = read_markdown_files(docs_dir)
    if not records:
        raise SystemExit(f"No markdown files found under {docs_dir}")

    paths = [path for path, _ in records]
    texts = [text for _, text in records]
    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(texts, normalize_embeddings=True)

    np.savez_compressed(
        cache_path,
        paths=np.array(paths, dtype=object),
        texts=np.array(texts, dtype=object),
        embeddings=embeddings,
    )
    return paths, texts, embeddings

def search(query: str, paths: list[str], texts: list[str], embeddings: np.ndarray, top_k: int) -> list[dict]:
    model = SentenceTransformer(MODEL_NAME)
    query_embedding = model.encode([query], normalize_embeddings=True)[0]
    scores = embeddings @ query_embedding
    ranked_indices = np.argsort(scores)[::-1][:top_k]

    results: list[dict] = []
    for index in ranked_indices:
        snippet = texts[index][:240].replace("\n", " ")
        results.append(
            {
                "path": paths[index],
                "score": round(float(scores[index]), 4),
                "snippet": snippet,
            }
        )
    return results

def main() -> None:
    parser = argparse.ArgumentParser(description="Local semantic search over markdown files.")
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    paths, texts, embeddings = build_or_load_index(args.docs_dir, args.rebuild)
    results = search(args.query, paths, texts, embeddings, args.top_k)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            print(f"{result['score']:.4f}  {result['path']}")
            print(f"  {result['snippet']}")
            print()

if __name__ == "__main__":
    main()
```

Run the script against a small directory of markdown files. On the first run, it builds the cache. On later runs, it loads embeddings from disk and only embeds the query. That difference is the operational pattern you want: document embeddings are generated when content changes, while query embeddings are generated when users search.

```bash
.venv/bin/python search.py --docs-dir ./docs --query "how do I recover a failed service" --top-k 3
.venv/bin/python search.py --docs-dir ./docs --query "how do I recover a failed service" --top-k 3 --json
.venv/bin/python search.py --docs-dir ./docs --query "database connection timeout" --top-k 5 --rebuild
```

This script uses normalized embeddings and matrix multiplication, so cosine similarity becomes a fast dot product. That is fine for a small local corpus. At larger scale, a linear scan over every vector becomes expensive. Vector databases and approximate nearest neighbor libraries solve that by trading a small amount of exactness for much faster lookup. The conceptual query path remains the same: embed the query, find nearby vectors, apply filters, and rank results.

---

## Provider Choices and Model Selection

Embedding model selection is a product and systems decision, not a popularity contest. A hosted embedding API may offer strong quality and low operational burden, but it sends text to a third party unless your contract and deployment model say otherwise. A local open-weight encoder may satisfy privacy and latency goals, but it requires model hosting, versioning, hardware planning, and quality evaluation. A retrieval-specialized encoder may outperform a general-purpose one on search tasks, but you still need to measure it against your corpus rather than trusting benchmark headlines.

The durable question is not which model is "best in general." It is which encoder gives the best measured result for this corpus under your privacy, latency, and cost constraints. Hosted APIs, self-hosted open-weight encoders, and managed retrieval services each sit on a different point of that trade-off surface. Your evaluation set should reflect real queries, not only public leaderboard tasks.

| Selection Criterion | Hosted API Tends to Fit | Self-Hosted Encoder Tends to Fit | What to Measure |
|---|---|---|---|
| Privacy and data residency | When policy allows external processing | When text must stay inside controlled infrastructure | Data classification, audit requirements, retention policy |
| Latency | When network latency is acceptable | When low-latency local inference is required | p50, p95, and p99 query latency |
| Quality | Often strong out of the box on general text | Varies by model and domain | Recall@K, precision, MRR, and failure examples |
| Cost | Good for low to moderate volume | Good for high steady volume if infrastructure is efficient | Total cost including engineering and operations |
| Operations | Minimal model-serving burden | Requires deployment, monitoring, and upgrades | On-call load and release process maturity |
| Custom domain | May work well without tuning | May need domain-specific model choice or fine-tuning | Domain query set and judged relevance |

A model migration needs a plan. Embeddings from different models generally live in different vector spaces, so you cannot compare vectors from one model with vectors from another as if they were compatible. If you change models, create a new index, embed the corpus again, and cut traffic over intentionally. Store `model_name`, `model_version`, `dimensions`, normalization choice, and similarity metric with the index so future engineers know what they are querying.

Dimensionality also has trade-offs. More dimensions can preserve more information, but they increase storage, memory bandwidth, and index size. Fewer dimensions can reduce cost and improve speed, but may lose retrieval quality. Some encoders expose configurable output width. Treat that as another evaluation variable: compare smaller and larger dimensions on your actual retrieval set before deciding the storage savings are worth it.

> **Landscape snapshot — as of 2026-06. This changes fast; verify against vendor docs before relying on specifics.**
>
> | Tier | Example identifiers (illustrative) | Typical use | Verify before relying |
> |---|---|---|---|
> | Hosted compact embedding API | `text-embedding-3-small` | General retrieval at lower cost | Default dimensions and pricing in current provider docs |
> | Hosted high-capacity embedding API | `text-embedding-3-large` | Higher-quality dense retrieval | Dimension options and rate limits in current provider docs |
> | Local sentence encoder (lab examples) | `all-MiniLM-L6-v2` | Offline prototypes without API keys | Model card on Hugging Face Hub |
> | Multilingual sentence encoder | `paraphrase-multilingual-MiniLM-L12-v2` | Cross-language retrieval experiments | Language coverage on the model card |
>
> Treat this table as a lookup aid, not a product recommendation. Model names, dimensions, and pricing change frequently.

```python
import os
from openai import OpenAI

# Replace with a current model identifier from the snapshot above.
EMBEDDING_MODEL = "text-embedding-3-small"

def embed_with_hosted_api(texts: list[str]) -> list[list[float]]:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        encoding_format="float",
    )
    return [item.embedding for item in response.data]

if __name__ == "__main__":
    vectors = embed_with_hosted_api(
        [
            "Recover a failed service after a bad deployment.",
            "Cook pasta in salted boiling water.",
        ]
    )
    print(len(vectors))
    print(len(vectors[0]))
```

This hosted API example is complete, but it assumes the `openai` package is installed and `OPENAI_API_KEY` is set. In production, you would add retries, batching, timeout handling, rate-limit handling, request logging without sensitive text, and a clear policy for which content may be sent to the provider. The embedding call itself is simple; the operational wrapper is where reliability and governance live.

---

## From Semantic Search to RAG

Retrieval-augmented generation depends on retrieval quality. The language model can only answer from the context it receives, and embedding search is often the first step that chooses that context. If retrieval returns the wrong chunks, the generator may produce a polished answer grounded in irrelevant text. When a RAG system fails, always inspect the retrieved chunks before rewriting the prompt. Many "prompt problems" are retrieval problems wearing a prompt-shaped mask.

A basic RAG retrieval path embeds the user query, retrieves the top chunks, and inserts those chunks into a prompt. A stronger path may use hybrid retrieval, metadata filters, query rewriting, re-ranking, and context packing. The goal is to pass the generator a compact set of chunks that are relevant, current, authorized, and non-duplicative. More context is not automatically better because irrelevant context can distract the model and increase cost.

| RAG Retrieval Concern | Bad Symptom | Likely Cause | Engineering Response |
|---|---|---|---|
| Missing answer | Model says it does not know, but docs contain the answer | Chunking, model choice, or sparse-only mismatch | Inspect top candidates and measure Recall@K |
| Plausible wrong answer | Model uses unrelated context confidently | Topical but non-answer chunks ranked high | Add re-ranking and stricter context selection |
| Stale answer | Model cites old process after docs changed | Index not rebuilt or metadata version missing | Add incremental indexing and freshness checks |
| Unauthorized answer | User sees restricted content in context | Access control not applied during retrieval | Enforce permissions before prompt construction |
| Repetitive context | Prompt includes many near-duplicate chunks | Overlap too high or no diversity step | Deduplicate by source and section before generation |
| Slow response | Search dominates end-to-end latency | Large scan, remote model calls, no cache | Use cached document vectors and ANN search |

One senior-level design habit is to separate candidate generation from final ranking. Candidate generation should be broad enough to include likely answers. Final ranking should be precise enough to place true answers near the top. Dense vectors are often good candidate generators, while cross-encoders or LLM-based re-rankers can improve precision on the top set. This two-stage pattern is common because comparing a query against every document with a heavy model is too expensive.

Another design habit is to preserve citation traceability. Each chunk should carry a stable source identifier, title, section, and location. When the generator uses a chunk, the answer should be able to cite the source. This is not only a UX feature. It helps debugging, compliance review, and quality evaluation. If you cannot trace an answer back to the retrieval result that produced it, you cannot reliably improve the system.

---

## Recommendations, Clustering, and Classification

Semantic search is the most obvious use case, but embeddings are more general. A recommendation system can represent articles, products, lessons, or videos as vectors and then find similar items. A support system can represent historical tickets and route new tickets based on nearest resolved cases. A content platform can cluster documents to discover duplicate tutorials, missing categories, or topic drift. The same geometry supports several application patterns.

Recommendation systems often start by embedding items. A user's profile can then be represented by one or more vectors derived from items they viewed, liked, bought, or completed. Averaging those item vectors is simple, but it can blur distinct interests. If a learner studies both Kubernetes networking and Python data analysis, the average may land between clusters and recommend odd cross-topic content. A stronger design keeps multiple interest vectors or ranks against recent interactions separately.

Clustering uses embeddings to group similar items without predefined labels. This can reveal topic clusters in support tickets, incident reports, or course content. The output still requires human interpretation because clusters are mathematical groupings, not guaranteed business categories. A cluster of "database timeout" tickets may represent a real product problem, a noisy logging pattern, or a documentation gap. The embedding model can surface the pattern, but engineers must validate the meaning.

Zero-shot classification compares a text embedding with label description embeddings. For example, a ticket can be compared against descriptions of "Billing," "Authentication," and "Infrastructure." The nearest label becomes the predicted category. This is useful when you lack training data, but it is not a replacement for evaluation. Labels must be written carefully because the category description is the anchor the model uses for comparison.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

labels = {
    "Billing": "payments, invoices, refunds, duplicate charges, subscription plans",
    "Authentication": "login, sign-in, password reset, OAuth, identity provider, sessions",
    "Infrastructure": "servers, databases, networking, deployments, latency, outages",
}

ticket = "Users are asked to sign in again every few minutes after the identity provider failover."

label_names = list(labels.keys())
label_vectors = model.encode(list(labels.values()), normalize_embeddings=True)
ticket_vector = model.encode([ticket], normalize_embeddings=True)[0]

scores = label_vectors @ ticket_vector
winner_index = int(np.argmax(scores))

print(label_names[winner_index])
for name, score in sorted(zip(label_names, scores), key=lambda item: item[1], reverse=True):
    print(f"{name}: {score:.3f}")
```

This example uses category descriptions instead of single-word labels because descriptions carry richer meaning. The label "Infrastructure" alone is vague, while "servers, databases, networking, deployments, latency, outages" gives the embedding model more semantic material. The same trick applies to search: chunk text should include enough context for the model to position it correctly.

---

## Production Architecture Patterns

A production embedding system needs more than a vector table. It needs ingestion, indexing, query serving, monitoring, access control, evaluation, and migration paths. The architecture can be small at first, but the responsibilities should be explicit. Otherwise, teams discover too late that they cannot rebuild indexes safely, explain result quality, remove deleted content, or prevent restricted chunks from entering prompts.

A common architecture has separate ingestion and query services. The ingestion service watches source systems, normalizes content, chunks documents, generates embeddings in batches, and writes vectors to an index. The query service embeds user queries, applies filters, searches the index, re-ranks candidates, and returns results. Evaluation jobs run offline against a judged query set. Monitoring captures latency, empty-result rate, click-through, feedback, and drift in query patterns.

```ascii
+------------------+      +-------------------+      +----------------------+
| Source Systems   | ---> | Ingestion Worker  | ---> | Vector Index         |
| docs, tickets,   |      | clean, chunk,     |      | vectors + metadata   |
| products, logs   |      | embed, version    |      | model + metric       |
+------------------+      +-------------------+      +----------------------+
                                                              ^
                                                              |
+------------------+      +-------------------+      +----------------------+
| User Query       | ---> | Query Service     | ---> | Filters + ANN Search |
| natural language |      | embed, retrieve,  |      | permissions, version |
| exact terms      |      | re-rank, package  |      | nearest candidates   |
+------------------+      +-------------------+      +----------------------+
```

Index versioning is essential. Every index should know which source snapshot, embedding model, chunking algorithm, normalization choice, and similarity metric produced it. Without that information, a retrieval regression becomes difficult to reproduce. If a new model improves benchmark scores but hurts your support queries, you need to compare old and new indexes side by side. Versioned indexes make that comparison routine.

Access control must be part of retrieval, not a UI afterthought. If restricted content is stored in the vector database, the query path must filter candidates by the user's permissions before returning results or constructing prompts. Filtering after generation is too late because the model may already have seen sensitive context. Metadata design and authorization checks are therefore security controls, not just search features.

Deletion and update behavior also matter. When a document is removed, its chunks must be removed from the index. When a document changes, stale chunks must be replaced. When a model changes, all chunks need re-embedding into a new compatible space. Production teams should treat vector indexes as derived artifacts that can be rebuilt from source content. If the index is the only place content exists, recovery and compliance become fragile.

| Production Concern | Design Question | Practical Control |
|---|---|---|
| Freshness | How quickly do document changes appear in search? | Incremental indexing plus scheduled full rebuilds |
| Authorization | Can a user retrieve only content they are allowed to see? | Metadata filters enforced before result return |
| Observability | Can engineers explain why a result appeared? | Log query ID, index version, top candidates, and ranking features |
| Rollback | Can the team return to the previous retrieval behavior? | Blue-green index deployment with versioned aliases |
| Cost control | Can high-volume ingestion avoid surprise spend? | Batching, rate limits, cache keys, and budget alerts |
| Data retention | Can deleted content be removed from derived indexes? | Source-of-truth rebuilds and deletion propagation checks |
| Evaluation | Can quality be measured before release? | Fixed test set plus sampled human review |
| Reliability | Can query service survive provider or index errors? | Timeouts, fallbacks, degraded keyword mode, and alerts |

A practical fallback is worth designing early. If the embedding provider is unavailable, a search product may still return keyword results. If the vector database is slow, the system may show cached popular answers. If re-ranking exceeds a latency budget, the query path may skip it and mark the response as lower confidence. Reliable systems define degraded behavior before outages force rushed decisions.

---

## Debugging Retrieval Failures

When semantic search returns bad results, start with the specific query and inspect the ranked candidates. Do not begin by swapping models. Ask what the query meant, what documents should have matched, which candidates appeared, and which pipeline stage lost the answer. This turns an opaque "embeddings are bad" complaint into a tractable investigation.

A useful debugging record includes the raw query, normalized query, query embedding model, index version, filters applied, top candidate IDs, scores, source text, and user feedback. If the expected document is absent from the top candidates, the problem may be chunking, embedding model choice, missing source ingestion, or overly restrictive filters. If the expected document appears low in the list, ranking or re-ranking may be the issue. If the expected document appears high but the final answer is wrong, the generator or context packing may be the issue.

| Symptom | First Check | Likely Root Cause | Fix Direction |
|---|---|---|---|
| Relevant document missing entirely | Confirm it was ingested and embedded | Source connector or indexing gap | Repair ingestion and add index coverage tests |
| Relevant chunk exists but ranks low | Compare chunk text against query wording | Chunk lacks title context or model misses domain language | Improve chunk text, hybrid retrieval, or model choice |
| Irrelevant topical chunks rank high | Inspect whether they share broad concepts | Dense retrieval is too broad for precision needs | Add keyword constraints, metadata filters, or re-ranking |
| Old information appears | Check index build timestamp and source version | Stale cache or failed update propagation | Add freshness monitoring and rebuild checks |
| Restricted content appears | Inspect metadata filter path | Authorization applied too late or not at all | Enforce permissions during retrieval |
| Duplicate results dominate | Check chunk overlap and source diversity | Overlap too high or no deduplication | Collapse by source and tune overlap |
| Scores look high for weak matches | Compare score distribution across many queries | Threshold calibrated from too few examples | Build judged query set and recalibrate |
| New model performs worse | Compare old and new rankings on fixed queries | Benchmark mismatch with local domain | Keep old index until task-specific metrics improve |

The most effective debugging practice is creating regression tests from failures. When a user reports that "login keeps asking users to sign in again" failed to find the OAuth token refresh runbook, add that query to the evaluation set with the expected chunks. Then test future chunking and model changes against it. Retrieval systems improve through accumulated failure examples, not only through model upgrades.

Senior teams also separate "retrieval relevance" from "business usefulness." A document can be semantically relevant but outdated, unauthorized, too advanced for the user, or not actionable. Search ranking may need business features such as freshness, product version, audience, ownership, popularity, or incident severity. Embeddings give a strong semantic signal, but production ranking often blends several signals.

---

## Embeddings in Kubernetes and Platform Engineering Workflows

KubeDojo learners will encounter embeddings in platform engineering because internal developer platforms are full of text. Runbooks, postmortems, Terraform modules, Helm chart values, pull request discussions, incident timelines, and service catalogs all contain knowledge that engineers need during high-pressure work. Keyword search over that material is useful, but semantic retrieval can reduce the time between symptom and fix.

A platform team might embed runbooks and incident reports to support on-call search. A query such as "pods restart after secret rotation" could retrieve an incident report titled "certificate reload triggered deployment churn" even if the words differ. The retrieved document should still be filtered by cluster, service, environment, and date. Semantics help find candidates, while metadata keeps the result operationally relevant.

A developer portal might embed service catalog descriptions and ownership notes. When a new engineer searches for "team that owns checkout authorization," the system can find the identity service or payments platform even if the catalog uses formal component names. The same embedding index can power recommendations such as "similar services," "related runbooks," and "incidents involving this dependency."

A learning platform can use embeddings to recommend modules. If a learner completes a lesson on semantic search, the system can recommend vector databases, RAG evaluation, or information retrieval metrics. But the recommendation should not be based only on vector similarity. It should also respect prerequisites, track progression, difficulty, and the learner's goals. Embeddings are a useful signal, not a curriculum designer.

---

## Did You Know?

- **Fact 1**: [Word2Vec made word-vector arithmetic famous](https://arxiv.org/abs/1310.4546), but [modern retrieval systems usually embed sentences, passages, or document chunks rather than isolated words](https://arxiv.org/abs/1908.10084).
- **Fact 2**: A vector database does not create semantic meaning by itself; the embedding model creates vectors, and the database stores and searches them efficiently.
- **Fact 3**: Many RAG quality failures come from retrieval and chunking problems, even when the final answer appears to be a language-model problem.
- **Fact 4**: Hybrid search remains common because exact identifiers, error strings, names, and commands often matter as much as semantic paraphrase.

---

## Common Mistakes

| Mistake | What Goes Wrong | Better Practice |
|---|---|---|
| Embedding whole long documents as one vector | The vector blurs multiple topics, so specific queries retrieve broad documents instead of answer-sized passages. | Chunk by headings and paragraphs, include useful title context, and evaluate chunk sizes. |
| Comparing vectors from different models | Scores become meaningless because the vectors were learned in different spaces and may have different dimensions. | Rebuild the index when changing models and store model metadata with each index version. |
| Treating similarity as confidence | A high score may mean topical relatedness, not that the candidate answers the user's question. | Calibrate thresholds with judged queries and inspect top candidates during evaluation. |
| Re-embedding unchanged documents on every query | Query latency and cost rise because stable document vectors are recomputed unnecessarily. | Separate indexing from querying and cache document embeddings until source content changes. |
| Ignoring metadata filters | Search returns stale, unauthorized, wrong-language, or wrong-version content even when vectors are close. | Store metadata with each chunk and enforce filters before returning results or building prompts. |
| Using demo queries as the only evaluation | The system looks strong on examples written by the builder but fails on real user language. | Build a test set from logs, tickets, incidents, and human judgments. |
| Assuming bigger vectors always win | Larger embeddings can increase storage and latency without improving the target task. | Compare dimensions and models with task-specific metrics and production constraints. |
| Skipping fallback behavior | Provider, index, or re-ranker failures turn search into a hard outage. | Define degraded modes such as keyword-only search, cached answers, or reduced re-ranking. |

---

## Quiz

<details>
<summary><strong>Question 1: Your team ships semantic search for internal runbooks. A query for "login keeps asking users to sign in again" returns broad identity-provider architecture docs, but misses the runbook titled "OAuth token refresh loop after failover." What would you inspect first, and what changes might improve retrieval?</strong></summary>

Start by inspecting the exact ranked candidates, the missing runbook's indexed chunks, and the query path metadata. Check whether the runbook was ingested, whether the relevant section was split away from its heading, whether the chunk text includes enough context, and whether filters excluded it. Good fixes might include heading-aware chunking, prefixing chunks with document and section titles, adding hybrid retrieval for terms like OAuth, and adding this query to the retrieval evaluation set so future changes are tested against it.
</details>

<details>
<summary><strong>Question 2: A legal discovery tool using dense embeddings retrieves many documents about contract negotiations for the query "breach of contract," but reviewers need documents that discuss an actual alleged breach. How should you adjust the retrieval architecture?</strong></summary>

Dense retrieval is finding topical contract-related material, but the legal workflow needs higher precision around a critical concept. Use dense retrieval for broad candidate generation, then add exact-term or phrase-aware constraints for terms such as breach when legally required. A hybrid search layer can combine semantic and lexical evidence, and a re-ranker can score whether the candidate actually addresses the query. The evaluation set should include hard negatives such as contract negotiations that are related but not responsive.
</details>

<details>
<summary><strong>Question 3: A documentation search index was rebuilt with a new embedding model, but the team reused old vectors for half the corpus to save time. Search quality became erratic, and some queries return nonsensical rankings. What is the likely design error, and how do you fix it safely?</strong></summary>

The team mixed vectors from different embedding models in the same index, which makes similarity comparisons invalid. The safe fix is to create a new complete index for the new model, embed the entire corpus into that model's vector space, store model name and dimensions with the index, and compare old and new indexes using a fixed judged query set. Traffic should move through a controlled cutover only after the new index improves or at least preserves the target metrics.
</details>

<details>
<summary><strong>Question 4: A RAG assistant answers with outdated deployment instructions even though the current documentation was updated yesterday. The language model receives the stale chunk in its context. Which pipeline stages should you debug, and what controls prevent recurrence?</strong></summary>

Debug the ingestion, cache invalidation, index freshness, and metadata filtering stages before changing the prompt. Confirm that the updated document was detected, old chunks were removed, new chunks were embedded, and the query service points to the latest index version. Prevent recurrence with incremental indexing, scheduled full rebuilds, source-version metadata, freshness checks, and monitoring that alerts when the index lags behind the source system.
</details>

<details>
<summary><strong>Question 5: An e-commerce team averages all products a shopper viewed into one profile vector. Users who viewed hiking boots and camera lenses start receiving recommendations for outdoor camera mounts, but they expected separate recommendations for both interests. What geometric issue caused this, and how would you redesign the profile?</strong></summary>

Averaging creates a centroid between the user's interest clusters, so the profile vector can land near blended concepts rather than representing each interest separately. Keep multiple profile vectors for distinct recent interests, score candidates against individual viewed items, or cluster user history before recommending. The system can then produce diverse recommendations from each interest area instead of collapsing the user into one mixed vector.
</details>

<details>
<summary><strong>Question 6: A platform search system performs well in English but poorly for Ukrainian translations of the same docs. The team assumed semantic search would automatically work across languages. What should they evaluate and adjust?</strong></summary>

They should evaluate whether the chosen embedding model is multilingual enough for the target language and whether English and Ukrainian content are embedded into a shared space reliably. Build a bilingual query set with judged results, compare multilingual models, and measure Recall@K separately by language. Also inspect chunking and metadata because translated documents may have different headings or structure. If needed, maintain language-specific indexes or use a model designed for multilingual retrieval.
</details>

<details>
<summary><strong>Question 7: Your vector search service has strong Recall@K offline, but users complain that the top result is often only loosely related and the actual answer is third or fourth. Which metric and architecture change should you consider?</strong></summary>

Recall@K shows that the answer appears somewhere in the candidate set, but it does not guarantee the answer is ranked first. Add metrics such as Mean Reciprocal Rank, Precision@K, or nDCG to measure ranking quality. Architecturally, keep dense retrieval for candidate generation, then add a re-ranking stage over the top candidates. You may also blend keyword scores, freshness, source authority, and metadata features to place the most useful answer higher.
</details>

---

## Hands-On Exercise

You will build and evaluate a local semantic search system over markdown documents. The exercise starts with the cached script from the worked example, then pushes it toward production behavior. Keep the corpus small enough to inspect manually, but large enough that keyword matching would not be enough to judge relevance. A good target is at least one hundred markdown files from a docs directory or a representative sample of internal notes.

### Scenario

Your team maintains a documentation portal, and engineers complain that they cannot find relevant troubleshooting pages when they describe symptoms instead of exact runbook titles. You have been asked to prototype semantic search and report whether it improves retrieval. The prototype must be repeatable, measurable, and safe to extend later.

### Step 1: Prepare the Environment

Create a new lab directory and install dependencies into a local virtual environment. Use the explicit virtual environment Python path so every command runs with the same interpreter and packages. If your machine already has these packages cached, installation may be fast; otherwise, the sentence-transformers model downloads on first use.

```bash
mkdir semantic-search-evaluation
cd semantic-search-evaluation
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install sentence-transformers numpy scikit-learn
```

### Step 2: Build the Baseline Index

Use the `search.py` script from the worked example, then point it at a markdown corpus. Run at least five queries that use symptom language rather than document titles. Record the top three results for each query. Do not tune anything yet because the first run is your baseline.

```bash
.venv/bin/python search.py --docs-dir ./docs --query "service keeps restarting after deployment" --top-k 3 --json
.venv/bin/python search.py --docs-dir ./docs --query "users have to sign in repeatedly" --top-k 3 --json
.venv/bin/python search.py --docs-dir ./docs --query "database requests timeout during checkout" --top-k 3 --json
```

### Step 3: Create a Judged Query Set

Create a small file named `queries.json` that lists realistic queries and the documents you expect to retrieve. This is not busywork; it is the difference between demo-driven development and retrieval engineering. Include at least one query where exact keywords matter and at least one where paraphrase matters.

```json
[
  {
    "query": "service keeps restarting after deployment",
    "expected_path_contains": "deployment"
  },
  {
    "query": "users have to sign in repeatedly",
    "expected_path_contains": "auth"
  },
  {
    "query": "database requests timeout during checkout",
    "expected_path_contains": "database"
  }
]
```

### Step 4: Add a Simple Evaluation Script

Create `evaluate.py` to run each query and check whether an expected document appears in the top results. This script uses path substring checks for simplicity, but a stronger version would store stable document IDs and human relevance labels. The important move is turning retrieval quality into a repeatable test.

```python
import argparse
import json
import subprocess
from pathlib import Path

def run_query(search_script: Path, docs_dir: Path, query: str, top_k: int) -> list[dict]:
    result = subprocess.run(
        [
            ".venv/bin/python",
            str(search_script),
            "--docs-dir",
            str(docs_dir),
            "--query",
            query,
            "--top-k",
            str(top_k),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate semantic search Recall@K.")
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    cases = json.loads(args.queries.read_text(encoding="utf-8"))
    hits = 0

    for case in cases:
        results = run_query(Path("search.py"), args.docs_dir, case["query"], args.top_k)
        expected = case["expected_path_contains"]
        matched = any(expected in result["path"] for result in results)
        hits += int(matched)
        status = "HIT" if matched else "MISS"
        print(f"{status}: {case['query']}")
        for result in results:
            print(f"  {result['score']:.4f} {result['path']}")

    recall = hits / len(cases)
    print(f"Recall@{args.top_k}: {recall:.2%}")

if __name__ == "__main__":
    main()
```

Run the evaluation script after building the index. If a query misses, inspect the top candidates and the expected document. Decide whether the miss comes from missing ingestion, bad chunking, poor query wording, weak model behavior, or overly broad document vectors.

```bash
.venv/bin/python evaluate.py --docs-dir ./docs --queries queries.json --top-k 3
```

### Step 5: Improve One Pipeline Stage

Choose one improvement and measure again. Good beginner improvements include prefixing document text with the filename and first heading, splitting large documents into section chunks, or adding a keyword fallback for exact terms. Do not change multiple variables at once. The goal is to learn which pipeline stage affects your corpus, not to accidentally improve one query while breaking another.

If you choose chunking, preserve enough context. A section chunk should include the document title and section heading, not only the paragraph body. If you choose hybrid search, keep the dense scores visible so you can compare the effect. If you choose a different model, rebuild the whole index and record the model name. The evaluation result should tell a story about the design choice you made.

### Step 6: Write a Short Engineering Report

Document the baseline metric, the change you made, the new metric, and two failure examples. Include one example where semantic search helped and one where it still failed. This report is part of the exercise because real retrieval work requires communicating uncertainty. A prototype that says "it works" is less useful than a prototype that says "it improves symptom queries, but exact error-code queries still need keyword search."

### Success Criteria

- [ ] The semantic search script indexes at least one hundred markdown documents or a representative smaller corpus with a clear explanation of the limitation.
- [ ] Document embeddings are cached to disk, and repeated queries do not re-embed unchanged documents.
- [ ] The query command supports non-interactive usage with `--query` and `--json`.
- [ ] The evaluation script reports Recall@K or an equivalent repeatable metric over a judged query set.
- [ ] At least one retrieval failure is debugged by inspecting chunk text, candidate rankings, and expected results.
- [ ] The final report recommends sparse, dense, or hybrid retrieval for the corpus and justifies that recommendation with evidence.
- [ ] The implementation records the embedding model name and avoids mixing vectors from incompatible models.
- [ ] The prototype includes a practical next step such as chunking improvement, metadata filters, re-ranking, or access-control integration.

## Learner check

> Embeddings turn text into geometry so software can search by meaning, not only by exact tokens. Production quality depends on chunking, metadata, hybrid retrieval, evaluation on real queries, and treating similarity scores as ranking signals rather than confidence — not on choosing a model name from a leaderboard.

## Next Module

Next module: [Vector Space Visualization](../module-1.5-vector-space-visualization/)

Embeddings give you searchable vectors, but high-dimensional spaces are hard to inspect directly. The next module teaches projection and visualization techniques so you can debug clusters, spot outliers, and communicate retrieval behavior to teammates who do not live inside cosine-similarity tables.

## Sources

- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings) — Provider documentation for hosted embedding APIs, dimension options, and usage patterns.
- [Efficient Estimation of Word Representations in Vector Space](https://arxiv.org/abs/1301.3781) — The original 2013 Word2Vec paper anchors efficient neural word-vector learning.
- [Distributed Representations of Words and Phrases and their Compositionality](https://arxiv.org/abs/1310.4546) — Covers compositional vector behavior that made embedding analogies famous.
- [Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks](https://arxiv.org/abs/1908.10084) — Canonical reference for practical sentence embeddings and semantic similarity with BERT-derived encoders.
- [MTEB: Massive Text Embedding Benchmark](https://arxiv.org/abs/2210.07316) — Benchmark framework for comparing embedding models across retrieval and classification tasks.
- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401) — Foundational RAG paper linking retrieval quality to downstream generation.
- [Passage Re-ranking with BERT](https://arxiv.org/abs/1901.04085) — Cross-encoder architecture for pairwise relevance scoring (re-ranking) after first-stage candidate retrieval.
- [Hugging Face Sentence Transformers Documentation](https://sbert.net/) — Practical guide for encoding sentences locally and computing similarity.
- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki) — Reference for building and querying approximate nearest-neighbor indexes at scale.
- [OpenSearch k-NN Plugin](https://opensearch.org/docs/latest/search-plugins/knn/index/) — Documents vector search integration in OpenSearch for production retrieval workloads.
- [Elasticsearch kNN Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html) — Official guide to dense vector fields and k-nearest-neighbor search in Elasticsearch.
