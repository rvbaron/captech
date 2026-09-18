> **⚠️ SUPERSEDED — historical design, do not implement from this.**
> Original semantic-code-search spec from branch `feature/hybrid-code-search` (last updated 2026-03-23). Superseded by the design in [`../../active/semantic-code-search-graph-index.md`](../../active/semantic-code-search-graph-index.md) and the shipped implementation under [`tools/legacylift_search/`](../../../../tools/legacylift_search). Retained for historical reference only — see [`README.md`](./README.md) in this folder.

# Semantic Code Search 

## Goal 
Build an enhanced code search (vector + lexical) and graph capabilities for a repo before running the LegacyLift skills. 

## Benefits
- Improve discovery by surfacing hybrid search (vector + lexical).
- Increase accuracy by creating a searchable vector store with all code.
- Reduce context impacts by providing enhanced search results instead of just GREP.

## High-level Requirements
- Hybrid search (vector + lexcial) with Reciprocal Rank Fusion (RRF) ranking of search results on the code.
- A graph database (caller-callee) of the code.
- Ability to find code that is not referenced ("dead code").
- Ability to trace through code the application from some starting point, or to start in the middle and work backwards and forwards to see where it goes.

## High-level Design
1. Chunk, index, and tokenize code using a AST tree-sitter: Chonkie looks good (https://github.com/chonkie-inc/chonkie)
2. Embedding model - Qwen3-Embedding-0.6B
3. Local vector data store: Chroma
4. Graph on data store option? E.g., NetworkX for analysis, store data in Sqlite

## Design Constraints
Concrete V1 design that matches stated opinions (Chonkie + Qwen3-Embedding-0.6B + Chroma + graph via NetworkX/SQLite) while staying realistic for **polyglot / 2M LOC / agent-step latency / laptop-first**

Optimizing for: 
1. **Repeatable ingestion**
2. **Hybrid retrieval with RRF**
3. **Traceability with evidence**
4. **“Dead code” candidates**
5. **Minimal moving parts**

## Implementation Notes
- The code for Semantic Code Search (scs) should live in the ./src/scs directory and any sub-directories (organize as appropriate).
- The scs should be a CLI that can be used by LegacyLift skills. Details are below.
- A skill should be created for each CLI option (which currently includes):
  - * `scs index` (build/update index)
  - * `scs query` (hybrid search + RRF)
  - * `scs trace` (graph traversal)
  - * `scs deadcode` (candidate report)
- A top-level scs skill should also be created to direct the coding agent to the appropriate skill based on what information it is looking for.

## Architecture Overview

### Components

1. **Indexer (offline)**

   * Walk repo(s) under a single root
   * Chunk with **Chonkie CodeChunker** (tree-sitter + auto language detection) ([Chonkie][1])
   * Generate embeddings with **Qwen3-Embedding-0.6B** (local; 32K context; configurable embedding dims) ([Hugging Face][2])
   * Store vectors + documents in **Chroma**
   * Store graph + metadata in **SQLite** (single file)
   * Build lexical retrieval via **SQLite FTS5** (or fallback to ripgrep if FTS5 unavailable)

2. **Query service (library/CLI used by skills/agents)**

   * Lexical search (FTS5/ripgrep)
   * Vector search (Chroma)
   * Merge results via **RRF** (Reciprocal Rank Fusion) ([Chroma Docs][3])
   * Optional graph expansion (forward/backward trace)

3. **Graph analyzer**

   * Load edges from SQLite into **NetworkX** for reachability/pathing
   * Persist computed metrics (in/out degree, reachability flags, candidate-dead-code) back into SQLite

---

## Data stores and on-disk layout

### Repo layout

```
<repoRoot>/
  .legacylift/
    scs/
      chroma/                 # Chroma persistence directory
      scs.sqlite              # SQLite: symbols, chunks metadata, edges, FTS
      manifest.json           # versions, commit hash, config, stats
      logs/
```

**Why this split?**

* Chroma gives you vector retrieval + metadata filtering.
* SQLite gives you a portable, inspectable system-of-record for symbol graph + FTS + metrics.

**Caution for “copy DB around”**: Chroma persistence is SQLite-backed in persistent mode; treat the directory as a coherent unit and avoid copying while open. There have been reports of SQLite locking/corruption if you move/upload while the client is alive. ([GitHub][4])

---

## Chunking rules (AST-first, but controllable)

You want stable “semantic units” that work across languages (COBOL → Python). Chonkie’s CodeChunker is AST-based and designed for multi-language chunking. ([Chonkie][1])

### Chunk types

Create **multiple chunk views** per file; this improves retrieval and trace without inflating vector cost too much.

1. **SymbolBody chunk** (primary)

* One chunk per:

  * function/method/procedure
  * class/interface/type definition body (optional, if huge)
  * COBOL paragraph/section (by AST node kinds if supported; otherwise heuristic by keywords)
* Include:

  * body + immediate signature
  * leading docstring/comments immediately attached to symbol (bounded)

2. **Signature chunk** (cheap, high value)

* One per function/method/class signature (no body)
* Useful for queries like “where is X defined” or “public API shapes”.

3. **FileSummary chunk** (optional but useful for navigation)

* imports/includes + top-level declarations list + module docstring
* Helps “what does this file do?” queries.

### Size / boundaries

* Hard cap: ~300–800 lines per SymbolBody chunk (language-dependent). If larger:

  * split by AST subnodes (e.g., method-level blocks, case statements, regions)
  * keep boundaries aligned to AST nodes (never mid-token)
* Preserve:

  * file path
  * start/end line/col
  * symbol name + qualified name (best-effort)
  * language

### Directory exclusions (default)

* vendor/generated/test/build artifacts:

  * `node_modules/`, `dist/`, `bin/`, `obj/`, `.git/`, `.venv/`, `target/`, etc.
* configurable allowlist/denylist in `manifest.json`

---

## Embeddings configuration

### Model: Qwen3-Embedding-0.6B

Key properties you should rely on (per model docs/registries):

* 32K context
* supports configurable output dimensions (“MRL support”) and instruction-aware usage ([Hugging Face][2])

### Practical embedding policy

* Embed **SymbolBody**, **Signature**, and (optionally) **FileSummary**.
* Use instruction/prefixes consistently:

  * `doc:` for code chunks
  * `query:` for natural language queries
* Dimension strategy:

  * Start with 1024 (or the model default if you don’t want to choose)
  * If storage grows too large, reduce to 512 using supported “custom dims” (one of the reasons to pick this model).

---

## Storage schema

### Chroma collections

Use **one collection per repo-root** (monorepo) to keep retrieval and filtering unified.

**Collection:** `code_chunks_v1`
**IDs:** stable UUIDs derived from `(path, chunk_type, start_line, end_line, hash)`.

**Stored document:** chunk text (body/signature/summary)
**Metadata fields (minimum):**

* `path`
* `language`
* `chunk_type` (`SymbolBody|Signature|FileSummary`)
* `symbol_name`
* `qualified_name` (best-effort)
* `start_line`, `end_line`
* `repo_root_id`
* `content_hash`
* `is_test`, `is_generated` (bool)
* `git_commit` (optional)

Chroma will persist locally (SQLite-backed persistent mode is widely described in docs/tutorials). ([DataCamp][5])

### SQLite schema (system-of-record)

```sql
-- Chunks metadata (source of truth)
CREATE TABLE chunks (
  chunk_id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  language TEXT,
  chunk_type TEXT NOT NULL,          -- SymbolBody | Signature | FileSummary
  symbol_id TEXT,                    -- FK to symbols
  symbol_name TEXT,
  qualified_name TEXT,
  start_line INTEGER,
  end_line INTEGER,
  content_hash TEXT NOT NULL,
  text_len INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Symbols (best-effort cross-language)
CREATE TABLE symbols (
  symbol_id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  language TEXT,
  kind TEXT,                         -- function|method|class|proc|module|...
  symbol_name TEXT NOT NULL,
  qualified_name TEXT,               -- namespace::class.method etc (best-effort)
  start_line INTEGER,
  end_line INTEGER,
  signature_text TEXT,
  is_exported INTEGER DEFAULT 0,
  is_entrypoint INTEGER DEFAULT 0
);

-- Edges: calls + references (unresolved first)
CREATE TABLE edges (
  edge_id TEXT PRIMARY KEY,
  src_chunk_id TEXT NOT NULL,        -- caller chunk
  src_symbol_id TEXT,                -- optional
  edge_type TEXT NOT NULL,           -- CALLS | REFERENCES | DEFINES | IMPORTS
  dst_symbol_id TEXT,                -- resolved target symbol when known
  dst_name TEXT,                     -- unresolved name/call text otherwise
  confidence REAL NOT NULL,          -- 0..1
  evidence_start_line INTEGER,
  evidence_end_line INTEGER,
  evidence_text TEXT,                -- small snippet
  created_at TEXT NOT NULL,
  FOREIGN KEY(src_chunk_id) REFERENCES chunks(chunk_id)
);

-- Precomputed metrics for dead-code + ranking
CREATE TABLE symbol_metrics (
  symbol_id TEXT PRIMARY KEY,
  in_refs INTEGER DEFAULT 0,
  in_calls INTEGER DEFAULT 0,
  out_calls INTEGER DEFAULT 0,
  reachable_from_entry INTEGER DEFAULT 0,
  unreferenced_candidate INTEGER DEFAULT 0,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(symbol_id) REFERENCES symbols(symbol_id)
);

-- Lexical search (hybrid)
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  chunk_id UNINDEXED,
  text,
  path,
  symbol_name,
  qualified_name,
  content='',
  tokenize='unicode61'
);
```

**FTS population rule:** index `SymbolBody` + `Signature`; optionally skip FileSummary if it adds noise.

---

## Hybrid search with RRF

You explicitly want RRF; Chroma’s docs describe using RRF to combine ranking strategies for hybrid search. ([Chroma Docs][3])

### Retrieval contract

For any query:

1. **Lexical retrieval**

* FTS query against `chunks_fts` returning top `k_lex` chunk_ids with rank `r_lex`
* (fallback: ripgrep, returning pseudo-ranks by file order + proximity)

2. **Vector retrieval**

* Chroma query returning top `k_vec` chunk_ids with rank `r_vec`

3. **Fuse with RRF**
   RRF score for a chunk `d`:

```
score(d) = Σ_i w_i * 1 / (k + rank_i(d))
```

* `i ∈ {lex, vec}`
* Typical: `k=60`, `w_lex=1.0`, `w_vec=1.0`
* If you see identifier-heavy queries, bump `w_lex`.

4. **Rerank / filter**

* Apply metadata filters (language, path prefix, chunk_type)
* Boost:

  * Signature chunks when query looks like symbol lookup
  * Same directory/module
  * Higher graph centrality (optional)

### Output shape (for skills)

Return “evidence packs”:

* snippet
* path + line range
* symbol context (qualified name, kind)
* why it matched (lex terms; vector score rank)
* optional trace neighbors (1 hop)

---

## Graph build rules (V1 best-effort)

### Extraction (fast, broad coverage)

From each SymbolBody chunk:

* `DEFINES` edges: File → Symbol (from chunk metadata)
* `IMPORTS` edges: from AST import/include nodes (unresolved strings)
* `REFERENCES` edges: identifier nodes (dst_name = identifier; confidence ~0.3–0.6)
* `CALLS` edges: call_expression/invocation nodes (dst_name = callee token/text; confidence ~0.4–0.7)

**Resolution heuristic (still V1)**
Try resolving dst_name → a `symbol_id` using:

1. same file exact name match
2. same directory/module name match
3. repo-wide name match (if unique)
4. language-specific heuristics (namespace/class receiver parsing)

When resolved, set `dst_symbol_id` and bump confidence.

### Trace APIs

* **Forward trace:** from `symbol_id` find `CALLS` outgoing edges; traverse up to depth N.
* **Backward trace:** incoming edges where `dst_symbol_id = X` OR `dst_name` matches symbol’s name.
* Always return **evidence_text + file/line** per hop.

### NetworkX usage

NetworkX is good for:

* strongly connected components (SCCs)
* shortest paths
* reachability from entrypoints
* centrality metrics used for ranking/prioritization

But keep SQLite as the persisted store; NetworkX is a compute layer.

---

## Dead code (V1 “unreferenced candidate”)

Given your requirement (“clients don’t want requirements for dead code”), ship a conservative candidate list:

A symbol is an **unreferenced candidate** if:

* `in_refs + in_calls == 0` after filtering out:

  * self-references within its own chunk
  * test-only references (if symbol is not test)
  * generated/vendor dirs
* AND symbol is not marked:

  * exported/public API (`is_exported=1`)
  * entrypoint (`is_entrypoint=1`)

This is “syntactic unreferenced,” not runtime dead. That’s fine for V1 and still highly valuable.

---

## Packages and runtime (Python-first)

### Python packages (core)

* `chonkie` (CodeChunker / AST chunking) ([Chonkie][1])
* `tree-sitter-language-pack` transitively (per Chonkie docs)
* `chromadb` (local persistent client)
* `sqlite` (stdlib) + FTS5 enabled
* `networkx`
* `numpy`
* Embedding runtime:

  * `transformers` + `torch` **or** `llama-cpp-python` if you standardize on GGUF variants (Qwen provides GGUF listings for embedding model variants) ([Hugging Face][6])

### Optional (but recommended)

* `ripgrep` (binary) as a fallback lexical retriever / debugging tool
* `tqdm` progress bars
* `orjson` for manifest speed

### CLI

* `scs index` (build/update index)
* `scs query` (hybrid search + RRF)
* `scs trace` (graph traversal)
* `scs deadcode` (candidate report)

---

## Indexing workflow

### `scs index <repoRoot>`

1. Determine repo identity: `repo_root_id` = hash of canonical path + git remote (optional)
2. Load `manifest.json` (prior run); compute changed files by hash or git diff
3. For each changed file:

   * chunk via Chonkie
   * generate symbols/chunks records
   * extract edges (calls/references/imports)
   * upsert into SQLite
   * upsert into Chroma (add/update embeddings)
   * update FTS5 row(s)
4. Post-pass:

   * resolve edges heuristically (best-effort)
   * compute metrics (in/out degrees, reachability from entrypoints if configured)
   * write `symbol_metrics`

### Entrypoint marking

Config-driven + heuristics:

* `main`, `Program.Main`, web route handlers, cron/schedulers, COBOL `PROCEDURE DIVISION` entry, etc.
* Let clients add entrypoints via a config file to improve reachability.

---

## Notes on your chosen tech decisions

* **Chonkie for chunking:** good fit for polyglot, AST-based code chunking; it explicitly positions CodeChunker as tree-sitter based, multi-language, with language detection. ([Chonkie][1])
* **Chroma for vectors:** good for local-first persistence; Chroma docs and ecosystem examples explicitly discuss hybrid search + RRF patterns. ([Chroma Docs][3])
* **Qwen3-Embedding-0.6B:** good “local accuracy vs footprint” point; supports long context and configurable embedding dimension per model listings. ([Hugging Face][2])

---

## What I’d do as “V1 defaults” (so you can ship)

* `chunk_type` indexed: **SymbolBody + Signature**
* `k_vec=40`, `k_lex=40`, `RRF_k=60`
* `w_vec=1.0`, `w_lex=1.0`
* “dead code”: **unreferenced candidate**, exclude exported/entrypoints/tests/generated
* Graph confidence + evidence on every edge (so downstream skills can justify conclusions)

## Configuration

* See `manifest.json` for an example config (exclude globs, entrypoints, embedding dims)

## Language Extraction

* See [language-extractor.md](./language-extractor.md) for information on language extraction, configuration, etc.

---

[1]: https://docs.chonkie.ai/oss/chunkers/code-chunker?utm_source=chatgpt.com "Code Chunker"
[2]: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B?utm_source=chatgpt.com "Qwen/Qwen3-Embedding-0.6B"
[3]: https://docs.trychroma.com/cloud/search-api/hybrid-search?utm_source=chatgpt.com "Hybrid Search with RRF - Chroma Docs"
[4]: https://github.com/chroma-core/chroma/issues/5868?utm_source=chatgpt.com "[Bug]: Unable to Close Persistent Client · Issue #5868"
[5]: https://www.datacamp.com/tutorial/chromadb-tutorial-step-by-step-guide?utm_source=chatgpt.com "Chroma DB Tutorial: A Step-By-Step Guide"
[6]: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF?utm_source=chatgpt.com "Qwen/Qwen3-Embedding-0.6B-GGUF"
