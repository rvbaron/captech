# Hosted Data Store for Semantic Code Search (AWS Options)

> **Status:** Pending — analysis draft intended to become an execution plan.
> **Scope:** Captures the chunking and embedding performance discussion from Milestone 17/17b of the active `semantic-code-search-graph-index` plan, then evaluates AWS-hosted data-store options for the two stateful halves of the index: the **vector store** (today Chroma) and the **graph store** (today SQLite edges). Lexical search (today SQLite FTS5) is covered where it collapses into a vector-store choice.
> **Audience:** LegacyLift v4 maintainers.
> **Depends on:** `docs/exec-plans/active/semantic-code-search-graph-index.md` (the tool being hosted) and its 2026-06-26 Decision Log entry on relaxing the local-only constraint.

---

## 1. Context

The v4 semantic code search tool builds a per-repository index under `repos/<repo>/legacylift-docs/index/code-search/` with three stateful pieces, all currently **local files**:

| Concern | Today (local) | Engine |
|---|---|---|
| Dense vectors | Chroma persistent dir | HNSW, 1024-dim |
| Lexical search | SQLite `chunk_fts` | FTS5 (BM25) |
| Graph + metadata | SQLite tables | `graph_edges`, `symbols`, `chunks`, `repo_files` |

Two forces are pushing toward a hosted option:

1. **The embedding bottleneck** (this section, §2). The local Qwen3 embedding pass is the single slowest part of indexing, and the cleanest durable fix removes per-host compute entirely.
2. **A relaxing constraint.** The original design mandated everything stay local (no code leaves the machine). An upcoming project is expected to relax that, which puts hosted embedding APIs *and* hosted data stores on the table for the first time (see the active plan's Decision Log, 2026-06-26).

This document does **not** assume the move happens — it lays out options so the decision can be made deliberately. The local Chroma + SQLite path remains the default and the fallback for clients who never approve code leaving the machine.

---

## 2. The chunking & embedding discussion (captured)

This is the substance that prompted the plan, preserved here so it isn't lost when the active plan's M17b entry scrolls into history.

### 2.1 Embedding — the real bottleneck and the corrected numbers

The embedding phase runs one Qwen3-Embedding-0.6B forward pass per distinct chunk. The active plan's M17/M17b retrospective originally recorded this at **~7 s/chunk → 20+ hours** for `repos/ctcm/ctcm-api` (58,677 chunks) and concluded the per-chunk CPU rate was the hard wall.

**That figure was a CPU-contention artifact.** Benchmarked in isolation on the dev host (22 cores, `torch 2.12.0+cpu`, MKL, warm model, realistic ~25-token C# chunks):

| batch_size | chunks | wall-clock | per-chunk |
|---|---|---|---|
| 32 | 256 | 90.2 s | **~350 ms** |
| 64 | 256 | 110.6 s | ~430 ms |

Two compounding facts: (1) the corpus is tiny per pass — avg **25 tokens/chunk**, only 316 of 58,677 chunks exceed 512 tokens; (2) larger CPU batches are *slower* per chunk because one batch already saturates all cores, so the GPU-oriented default `batch_size=512` is wrong for CPU — **32 is the right CPU batch size**. Recomputed idle-CPU wall-clock at ~350 ms/chunk:

| scenario | forward passes | idle-CPU compute |
|---|---|---|
| no filter | 58,677 | ~5.7 h |
| dedup only (spike #2) | 37,456 | ~3.6 h |
| **filter + dedup @ `embed_min_tokens=80`** | **14,093** | **~80 min** |

The M17b cost filter (the content-aware low-value filter + text-dedup, already shipped) cuts forward passes 76% and makes the filtered pass an **~80-minute, resumable** job on an idle CPU host via repeated `backfill-vectors` calls — not the 20-hour job originally feared.

**Embedding options, in priority order:**

| # | Option | Speed | Cost / dependency | Notes |
|---|---|---|---|---|
| E1 | **Idle-CPU `backfill-vectors`**, `batch_size=32` | ~80 min (filtered) | None (no new deps) | Runnable now on an unloaded host. Resumable, kill-survivable. |
| E2 | **GPU** (`embedding.device="cuda"`) | single-digit min | NVIDIA box + CUDA torch wheel | Biggest local lever (10–50×). Already supported; only env setup. |
| E3 | **Hosted embedding API** (e.g. Amazon Bedrock Titan V2 / Cohere Embed v4) | minutes, no local compute | Network egress of code; per-token cost; data-handling approval | Durable cross-repo answer once local-only relaxes. Ties directly to the AWS discussion below (§3.4). |
| E4 | CPU int8 / ONNX quantization | ~25–40 min (filtered) | New embedder backend | Only if no GPU and must stay local. |
| E5 | Smaller local model | 5–10× faster | Manifest-only (`embedding.model`) | Retrieval-quality trade-off. |

CPU **multiprocessing is not a useful lever** — one batch already saturates all cores, so sharding only contends.

**Embedding-only hosting (E3): what total cold-index runtime does it buy?** Hosting *only* the embedding call (everything else stays local) does not get to "minutes" — it shifts the bottleneck. The two heavy cold phases run **sequentially** (a chunk can't be embedded before it's extracted):

| Phase | All-local (E1, CPU batch 32) | Embedding via Bedrock (E3) |
|---|---|---|
| `extract+chunk` | ~63 min | ~63 min (unchanged) |
| `embed` (14,093 filtered chunks) | ~80 min | ~few min (no local compute) |
| **Total cold** | **~143 min (~2.4 h)** | **~65–70 min (~1 h)** |

So E3 roughly **halves** cold-index time, but the moment embedding leaves the CPU the **63-minute serial `extract+chunk` phase (§2.2) becomes the long pole.** Getting to single-digit minutes requires *also* parallelizing chunking (C1 → ~6–10 min); C1 **+** E3 ≈ **~10–15 min cold**. Reruns are unaffected either way — M15 skip-on-unchanged keeps those near-instant.

**Retrieval stays local — but with a query-time embedding call.** Embedding-only hosting is purely an index-build/write-path decision: Chroma, FTS5, and the SQLite graph stay local, and HNSW + BM25 + RRF search runs entirely on the host. The one caveat is the **query string must be embedded with the same model that built the index** (the dimension-consistency rule, §3.4). If the index is built with Bedrock Titan V2, that model is no longer local, so **each retrieval needs one small Bedrock call** (a single short string, sub-second) to vectorize the query before the local search. So "only calling AWS for embedding" is two touch-points, not one: ~14k calls at index build, then 1 call per query. Fully-offline retrieval (zero AWS at query time) requires a local query embedder — which forces building the index with that same local model, i.e. back to local embedding. This tension is the reason E3 is an index-speed lever, not a "no local model needed" lever.

### 2.2 Chunking — the 63-minute extract+chunk phase

The `[extract+chunk]` phase on `repos/ctcm/ctcm-api` takes ~63 min cold. It is a **serial per-file loop** (tree-sitter parse + regex fallback + Chonkie + several committing SQLite transactions per file, ~0.8 s/file × 4,715 files). The M15 skip-on-unchanged fast-path already makes *reruns* near-instant, so this only bites on cold indexes.

| # | Option | Target | Effort |
|---|---|---|---|
| C1 | **Parallelize extraction** across a `ProcessPoolExecutor`, single writer thread for SQLite | ~6–10 min | Real change in `indexer.py`; per-file extract is embarrassingly parallel |
| C2 | **Batch SQLite commits** (one txn per N files instead of ~4–5 commits/file) | shaves I/O | Small, safe; stacks with C1 |
| C3 | Accept it (cold-index is one-time; M15 covers reruns) | — | None |

**Relevance to hosting:** if the graph/metadata store moves off local SQLite (§4), the per-file commit pattern (C2) changes shape entirely — a network round-trip per file would be *worse* than local SQLite unless batched. Chunking parallelism (C1) is orthogonal to where data lands and is worth doing regardless.

> **C1 + C2 are now specified as Milestone 19** in the active plan (`docs/exec-plans/active/semantic-code-search-graph-index.md`), since they pay off in the all-local, GPU, and hosted-embedding scenarios alike. The work below in §7 tracks the *hosting* items; the extract/commit parallelization lives there.

---

## 3. AWS vector data store options

### 3.1 Workload shape (what we are actually optimizing for)

The right choice falls out of the workload, which is unusual for a vector store:

- **Per-repo, many repos.** Each client repo is an independent index (tens of thousands to low-hundreds-of-thousands of chunks). This is many small-to-medium collections, not one giant one.
- **Low, bursty QPS.** Retrieval is agent-driven during an analysis engagement, not a high-traffic production endpoint. Most indexes sit idle most of the time.
- **Latency-tolerant.** Sub-second is plenty; this is not a user-facing autocomplete.
- **1024-dim** vectors (Qwen3) today; dimension must match whatever embedder is chosen (§3.4).
- **Hybrid is required.** Search fuses vector + lexical (FTS5) via RRF. A store that does *both* lets us retire SQLite FTS5 too.
- **Filtering by metadata** (path, language, symbol) is used.

The dominant cost axis is therefore **idle cost**, not peak throughput. A provisioned always-on cluster per repo is the wrong shape; serverless / object-storage / shared-cluster-with-namespaces is the right shape.

### 3.2 The options

| Option | Type | Hybrid (vec+lexical)? | Cost model | Fit for this workload |
|---|---|---|---|---|
| **Amazon OpenSearch Service** (managed domain), k-NN plugin | Provisioned cluster | **Yes** — BM25 + k-NN + filtering in one engine | Always-on instances (hourly) | Strong functionally (collapses Chroma *and* FTS5), but a per-repo domain is expensive when idle. Use one domain with an index per repo. Disk-based / quantized vectors (faiss PQ up to 64×, binary 32×, `mode: on_disk`) cut memory cost sharply if kept. |
| **Amazon OpenSearch Serverless** (vector collection) | Serverless | Yes | Pay for OCU compute + storage | **The idle-floor objection is largely gone.** *NextGen* collection groups (GA 2026-05-28) default to **min 0 OCU and scale to zero** after 10 min idle (compute billing stops; ~10–30 s cold-start on wake). Legacy *Classic* collections still carry a 2-OCU (or 1-OCU dev/test) always-on floor. NextGen makes "many idle collections" viable; vector collections use GPU-backed HNSW builds (separate billing). |
| **Amazon S3 Vectors** | Object-storage native vector index | Vector only (pair with separate lexical) | **Pay-per-storage/query**, AWS claims up to ~90% cheaper than conventional vector DBs | **Best fit for idle cost — and now GA (2026-12-02).** Purpose-built for large, low-QPS, cost-sensitive vector sets: ~100 ms for frequent queries, sub-second otherwise (AWS explicitly positions it for *infrequent* queries). Up to 2 B vectors/index, 1–4,096 dims, 10,000 indexes/bucket. Many idle repo indexes cost almost nothing at rest. No built-in lexical — keep FTS5, or use the S3 Vectors↔OpenSearch integration (export to OpenSearch Serverless, or `engine: S3_Vectors` on a managed domain) for hybrid. |
| **Aurora PostgreSQL / RDS PostgreSQL + pgvector** | Relational + extension | Partial — vector + SQL `LIKE`/`tsvector` full-text in the same DB | Aurora Serverless v2 scales to low ACUs | **Compelling consolidation:** one Postgres holds vectors *and* the graph edges (§4) *and* metadata — replaces Chroma + SQLite in a single managed store. **pgvector 0.8.1** on current Aurora engines (17.9/16.13): HNSW with parallel index builds (up to 67× faster vs 0.5.1) and 0.8.0 iterative scans that fix overfiltering. Postgres `tsvector` covers lexical adequately (less rich than FTS5/BM25 but workable). *(Note: Aurora DSQL — GA 2025-05 — is **not** a candidate; no `CREATE EXTENSION`, so no pgvector.)* |
| **Amazon MemoryDB for Redis** (vector search) | In-memory, durable | Vector + basic filtering | In-memory pricing (highest at rest) | Overkill — we don't need millisecond latency, and in-memory at-rest cost is the worst fit for idle-heavy. |
| **Amazon DocumentDB** (vector search) | Document DB | Vector + query | Cluster pricing | No advantage here unless already standardized on DocumentDB. |
| **Amazon Neptune Analytics** | Graph engine w/ vector similarity | Vector + graph in one engine | In-memory graph pricing (m-NCU) | Interesting because it answers **both** the vector and graph questions in one service (§4.2) — but in-memory cost (m-NCU, smallest tiers 32/64 m-NCU) and a graph-first model make it a niche, not default, pick. It is the backing store for Bedrock Knowledge Bases **GraphRAG** (GA 2025-03). |
| **Amazon Bedrock Knowledge Bases** | Managed RAG (wraps a backing store) | Depends on backing store | Backing store + Bedrock | Not a store itself — it orchestrates chunking + embedding + a backing vector store. Backends now (8): OpenSearch Serverless, OpenSearch managed cluster (added 2025-03), Aurora pgvector, **S3 Vectors** (GA 2025-12), Neptune Analytics (GraphRAG), Pinecone, MongoDB Atlas, Redis Enterprise Cloud. Relevant as a *fast path* that also solves embedding (§3.4), at the cost of ceding control over our tuned chunking/extraction. |
| **Self-managed (Qdrant / Weaviate / Milvus on EKS/EC2)** | Self-hosted OSS | Varies | EC2/EKS always-on | Closest to "Chroma but hosted." More ops than managed; only if a specific OSS feature is needed. |

### 3.3 Vector-store verdict

Two finalists, depending on what else we consolidate:

- **If we want the smallest, cheapest footprint and are happy keeping lexical local/separate → Amazon S3 Vectors** (now GA, 2026-12-02, so no longer a preview bet). It matches the idle-heavy, many-repos, low-QPS profile better than anything else: near-zero cost at rest, ~100 ms / sub-second query, scales per repo without per-repo cluster cost. Pair with FTS5 (kept local) or a lightweight lexical index. This is the lowest-risk "just host the vectors" move.
- **If we want to collapse the whole index into one managed store → Aurora PostgreSQL + pgvector** (0.8.1 on current engines). One Aurora Serverless v2 instance holds vectors (pgvector/HNSW), graph edges (§4.1), lexical (`tsvector`), and all metadata — retiring both Chroma and SQLite. Operationally simplest *long-term*; the trade-off is `tsvector` is a step down from FTS5/BM25, and Aurora has a non-trivial idle floor (low-ACU, not zero).

**OpenSearch (managed or serverless)** is the answer if hybrid search *quality* (true BM25 + k-NN fusion + rich filtering in one query) is the priority — it's the most capable single-store option for hybrid, and would let us delete the RRF-over-two-stores code in favor of one engine. **The historical idle-cost objection has largely dissolved:** OpenSearch Serverless *NextGen* collections (GA 2026-05-28) scale to **0 OCU** after 10 min idle, so many idle repo collections no longer carry the old 2-OCU floor — at the cost of a ~10–30 s cold-start on first query (well within this workload's latency tolerance). This makes OpenSearch a credible default for hybrid, not just a quality-at-a-cost pick.

### 3.4 The embedding tie-in (Bedrock)

Hosting the vector store and fixing embedding (§2.1, E3) can be the same decision:

- **Amazon Bedrock embedding models** remove local embedding compute entirely and batch well. Current first-party/partner options: **Titan Text Embeddings V2** (configurable 256/512/1024 dims, 8K-token input), **Cohere Embed v4** (multimodal, 128K context; Cohere's own docs describe configurable 256/512/1024/1536 dims and code/document retrieval — not stated on the AWS model card), and the newer **Amazon Nova Multimodal Embeddings** (text/image/audio/video, but *not* code-tuned). **Dimension must match the chosen store's collection** (Titan V2 at 1024 lines up with today's Qwen dim; switching embedder still requires a `--reset` per the existing dimension-consistency rule).
- A new `provider="api"` branch in `create_embedder` (the entire integration surface, per the active plan's decision entry) plus an endpoint/model/region config is the whole code change. `vectors_present` checkpointing and `backfill-vectors` resumability carry over unchanged.
- **Code-vs-general-text caveat:** Titan, Nova, and Cohere are general-purpose/multimodal embedders — **none of the AWS-first-party models is marketed as code-specialized**; Qwen3-Embedding is competitive on *code* retrieval. A quality A/B (the deferred M17 Qwen-vs-hash comparison, extended to Bedrock) should gate adopting a hosted embedder for retrieval quality, not just speed.
- **Bedrock Knowledge Bases** would additionally take over chunking + ingestion. That conflicts with the tuned tree-sitter/symbol chunking and the graph extraction this tool is built around, so KB is likely the wrong altitude for us — we want Bedrock *embeddings*, not Bedrock *RAG orchestration*.

---

## 4. AWS graph data store options

### 4.1 What the graph workload actually is

Be precise here, because it determines whether a real graph DB earns its cost:

- The graph is `graph_edges(caller_symbol_id, callee_symbol_id, callee_name, edge_kind, confidence, evidence, ...)` — edges with confidence scores and **preserved unresolved targets**.
- **Today's queries are 1-hop:** `callers <symbol-id>` and `callees <symbol-id>`. `graph_neighbor_depth` defaults to **1**. These are trivial indexed lookups — a relational table does them perfectly well (which is exactly what SQLite does now).
- **But the stated product vision is multi-hop:** the active plan's Purpose section promises *"show the code path that validates eligibility"* — that is a **path/traversal query** (variable-length, possibly cyclic), which is precisely where relational recursive CTEs get awkward and a graph engine shines.

So the graph-store choice hinges on a roadmap decision: **do we commit to multi-hop path queries, or stay 1-hop?**

### 4.2 The options

| Option | Type | Query model | Cost model | Fit |
|---|---|---|---|---|
| **Aurora/RDS PostgreSQL** (edges as a table) | Relational | SQL; multi-hop via recursive CTE | Aurora Serverless v2 | **Best if staying 1-hop**, and the natural choice if pgvector already won §3 — vectors + edges + metadata in one store. Recursive CTEs handle modest multi-hop but degrade on deep/cyclic traversal. |
| **Amazon Neptune** (Database) | Managed graph DB | **openCypher / Gremlin / SPARQL** | Provisioned, or **Neptune Serverless** (NCUs, 1 NCU = 2 GiB, range 1–128, 0.5 increments) | **Best if committing to multi-hop path queries.** Native variable-length path traversal, cycle handling, confidence-weighted paths. Serverless mitigates idle cost across many repos. Heaviest new dependency. |
| **Amazon Neptune Analytics** | In-memory graph analytics + **vector similarity** | openCypher + graph algorithms + k-NN | In-memory pricing (m-NCU, 1 m-NCU = 1 GB; paused ≈ 10% cost) | Uniquely answers **both** §3 and §4 in one engine (graph algorithms *and* vector search on the same nodes). Powerful for "rank code by graph centrality + semantic similarity," but in-memory cost and load-from-source model make it a specialized pick, not a default. Backs Bedrock KB GraphRAG (GA 2025-03). |
| **Apache AGE on PostgreSQL** | Postgres graph extension (Cypher) | openCypher inside Postgres | — | Cypher-on-Postgres would be ideal consolidation, **but it is still not an available managed RDS/Aurora extension** (re-verified mid-2026: `age` appears nowhere in the RDS/Aurora supported-extensions release notes) — it means self-managing Postgres on EC2. Do not rely on it as managed. |
| **Self-managed Neo4j** (AMI / Aura on AWS) | Graph DB | Cypher | EC2 always-on / Aura subscription | Mature graph tooling; more ops or a third-party subscription. Only if Neptune's model is a poor fit. |

### 4.3 Graph-store verdict

- **Default / lowest-risk: keep the graph relational in Aurora PostgreSQL** (the same instance as pgvector, if §3 picks pgvector). This serves today's 1-hop queries perfectly, consolidates stores, and handles modest multi-hop via recursive CTEs. Revisit only if path queries become a real, used feature.
- **If multi-hop "code path" queries become a committed feature: Amazon Neptune (Serverless).** That is the use case graph databases exist for, and Serverless keeps idle cost sane across many repo graphs.
- **Neptune Analytics** is the option to keep in the back pocket if a future feature wants *graph-structure-aware ranking fused with semantic similarity* (e.g., "most central, most semantically-relevant code for this concern") — it does graph + vector in one engine, at in-memory cost.

---

## 5. Combined-architecture view

The vector and graph decisions interact. Four coherent target shapes, from least to most hosted:

1. **Embedding-only (no hosted store):** keep the entire index local (Chroma + FTS5 + SQLite graph), and call Bedrock (E3) *only* to vectorize chunks at index build and queries at retrieval time. The smallest possible hosted footprint — no store moves to AWS, no idle store cost, no per-repo namespace management. Halves cold-index time (~2.4 h → ~1 h; ~10–15 min if paired with chunking C1) and removes the local embedding-compute requirement. Caveat (§2.1): retrieval is no longer fully offline — each query makes one small Bedrock call, because the query must be embedded with the same model that built the index. Best first step: it solves the actual bottleneck (embedding) with the least surface and least data-handling exposure (only embedding inputs egress, not a resident store).
2. **Minimal host (vectors only):** S3 Vectors for dense vectors; keep SQLite (FTS5 + graph + metadata) local per repo. Smallest change *to where data lives at rest*, lowest idle cost of the hosted-store options, but the index is now split across cloud + local — freshness/coverage bookkeeping spans two places. Pairs naturally with Bedrock embeddings (E3) to also kill the embedding bottleneck.
3. **One relational store (consolidate everything):** Aurora PostgreSQL Serverless v2 holds vectors (pgvector), graph edges, lexical (`tsvector`), and metadata. Retires both Chroma and SQLite; one connection, one freshness model. Trade-off: `tsvector` < FTS5/BM25, and an idle floor. Best long-term operability if we're hosting at all.
4. **Best-in-class per concern:** OpenSearch (hybrid vector+lexical) + Neptune (graph). Highest capability (true BM25+kNN fusion, native path traversal) and highest cost/ops. Justified only if both hybrid-quality and multi-hop traversal become first-class.

**Cross-cutting concerns for any hosted shape:**

- **Data residency & approval.** Chunk text, symbols, and edges are derived from client code; the SQLite store holds *full chunk text*. Whatever store holds chunk text inherits the per-engagement data-handling approval that gates the hosted-embedding decision. Per-client VPC isolation, encryption at rest/in transit, and a documented retention/teardown policy are mandatory. Some clients will never approve this — **the local Chroma+SQLite path must remain a first-class fallback.**
- **Per-repo isolation.** Many repos → many namespaces/indexes/collections. Favor cost models that don't impose a per-repo floor (S3 Vectors, shared Aurora with per-repo schema/tables, OpenSearch index-per-repo on a shared domain).
- **Teardown.** Engagements end; indexes must be cheap to delete and cheap to leave idle. This argues against always-on provisioned clusters per repo.
- **Freshness model.** The `source_set_sha256` / per-chunk `text_sha256` drift detection and the M15 skip-on-unchanged path must survive the move — they assume cheap local reads of "what's already indexed." A network store changes that cost; the `vectors_present` cache (already a separate local SQLite concept) may need rethinking if SQLite goes away.

---

## 6. Open questions / decisions needed

1. **Is the move actually happening, and for which clients?** The local-only fallback stays regardless; this only matters for clients who approve code-derived data leaving the host.
2. **How much to host?** §5 shapes #1–#4 (embedding-only → vectors-only → one relational store → best-in-class) — driven by (a) whether the embedding bottleneck alone is the problem, (b) how much we value hybrid-search *quality*, and (c) whether multi-hop path queries become real.
3. **Multi-hop graph: committed or not?** This single roadmap call decides relational-edges vs. Neptune (§4.1).
4. **Hosted embedder for quality, or just speed?** Requires the deferred Qwen-vs-hash-vs-Bedrock retrieval-quality A/B before adopting a hosted embedder for anything but speed.
5. **Idle-cost ceiling per repo.** Sets the cost model (object-storage vs serverless vs provisioned) more than any feature does.

---

## 7. Candidate work items (for the eventual exec-plan)

These assume the local-only constraint is relaxed for at least some engagements.

1. **Add a hosted embedding provider** (`provider="api"` in `create_embedder`, e.g. Bedrock Titan/Cohere) with endpoint/model/region/dimension config. Reuses `vectors_present` checkpointing and `backfill-vectors`. This is shape #1 (§5) on its own — the highest-leverage, lowest-surface change (also listed in the active plan). Note the same provider must serve **query-time** embedding (one call per retrieval), since the query and index vectors must share a model (§2.1).
2. **Abstract the vector store behind the existing `ChromaVectorStore` interface** so a second backend (S3 Vectors, pgvector, or OpenSearch) can be selected by manifest, mirroring the embedder dispatch.
3. **Run the deferred retrieval-quality A/B** — Qwen vs. hash vs. a hosted embedder — to gate any embedder change on quality, not just speed.
4. **Spike S3 Vectors** as the minimal-host vector backend (shape #2): cost-at-rest and query-latency measurement against the ctcm-api index.
5. **Spike Aurora pgvector consolidation** (shape #3): vectors + edges + lexical + metadata in one Serverless v2 instance; compare `tsvector` lexical quality against FTS5 on the M14 queries.
6. **Decide the multi-hop graph question** (§6.3); if yes, spike Neptune Serverless with openCypher path queries for the "code path that validates eligibility" use case.
7. **Parallelize cold-index extraction** (chunking C1) and **batch SQLite commits** (C2) — orthogonal to hosting, valuable regardless.
8. **Write the data-handling / teardown policy** for hosted client-derived indexes (residency, encryption, retention, per-engagement approval gate), and keep local Chroma+SQLite as the documented fallback.

---

*Draft analysis — to be developed into an execution plan. AWS service capabilities were re-verified against current AWS documentation in June 2026 (S3 Vectors GA 2025-12-02; OpenSearch Serverless NextGen scale-to-zero GA 2026-05-28; Neptune Analytics GraphRAG GA 2025-03; pgvector 0.8.1 on Aurora; Apache AGE still not managed on RDS/Aurora). These services evolve quickly — re-verify the load-bearing facts (especially pricing minimums and region availability) before any spike.*
