> **⚠️ SUPERSEDED — historical ExecPlan, do not implement from this.**
> Original semantic-code-search ExecPlan from branch `feature/hybrid-code-search` (last updated 2026-03-23). Superseded by the design in [`../../active/semantic-code-search-graph-index.md`](../../active/semantic-code-search-graph-index.md) and the shipped implementation under [`tools/legacylift_search/`](../../../../tools/legacylift_search) (the `scs` CLI described below is the working name; the delivered tool is `legacylift-search`). Retained for historical reference only — see [`README.md`](./README.md) in this folder.

# Semantic Code Search (SCS) — ExecPlan

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `docs/legacylift/exec-plan.md` (the ExecPlan template and requirements guide at the repository root).

## Purpose / Big Picture

After this change, a coding agent (or human) running LegacyLift skills on a legacy repository will be able to search that repository's code using a combination of vector similarity and keyword matching, trace caller-callee relationships through a graph, and identify dead-code candidates — all from Claude Code skills invoked via the CLI. Today the only search mechanism available to skills is Grep/Glob (pure lexical, no ranking, no semantic understanding). SCS adds a local index (no cloud services required) that makes search results dramatically more relevant, especially for natural-language queries like "where is the claims adjudication logic?" or "what calls the payment processor?".

To see it working after implementation: run `scs index .` on a test repo (e.g., `repos/ctcm-api`), then run `scs query "claims adjudication"` and observe ranked results with file paths, line ranges, and relevance scores. Run `scs trace --symbol "ClaimsController.AdjudicateClaim"` to see a caller-callee graph. Run `scs deadcode` to get a list of unreferenced symbol candidates.

## Progress

- [ ] Milestone 0: Prototyping spike — validate Chonkie CodeChunker, Qwen3-Embedding-0.6B, and Chroma work together on a small code sample.
- [ ] Milestone 1: Project scaffolding — create `src/scs/` package structure, `pyproject.toml`, CLI skeleton.
- [ ] Milestone 2: Indexer — file walker, chunker, embeddings, SQLite schema, Chroma upsert, FTS5 population.
- [ ] Milestone 3: Hybrid search — lexical retrieval, vector retrieval, RRF fusion, evidence-pack output.
- [ ] Milestone 4: Graph build and trace — edge extraction, resolution heuristics, NetworkX analysis, trace CLI.
- [ ] Milestone 5: Dead-code candidate report.
- [ ] Milestone 6: LegacyLift skill wrappers — one skill per CLI command plus a router skill.
- [ ] Milestone 7: Integration testing against `repos/ctcm-api`.
- [ ] Milestone 8: Documentation and cleanup.

## Surprises & Discoveries

(None yet — populate as implementation proceeds.)

- Observation: …
  Evidence: …

## Decision Log

- Decision: Use the ExecPlan skeleton from `docs/legacylift/exec-plan.md` as the structure for this plan.
  Rationale: Repo convention.
  Date/Author: 2026-03-20 / Claude

## Outcomes & Retrospective

(To be completed at major milestones and at plan completion.)

## Context and Orientation

### Repository layout (relevant parts)

The LegacyLift repository is organized as follows (paths are relative to the repo root):

- `.claude/skills/{skill-name}/SKILL.md` — Each LegacyLift skill. A skill is a Claude Code skill: a markdown file with YAML frontmatter (`name`, `description`, `allowed-tools`) followed by instructions that Claude executes when the skill is invoked. Skills are invoked via `claude --skill {skill-name} .` or as `/skill-name` inside Claude Code.
- `.claude/skills/README.md` — Skill ecosystem overview and workflow diagram.
- `.claude/skills/FACT-GRAPH-INTEGRATION.md` — Shared Phase 0 code for loading the fact graph (a pre-built JSON knowledge base of the repository).
- `.claude/skills/STATUS-REPORTING.md` — Shared status-reporting JSON format.
- `docs/legacylift/architecture.md` — Canonical reference for creating and updating skills (section numbering, phase structure, templates, citation standards, output file numbering).
- `docs/legacylift/exec-plans/active/semantic-code-search/` — The design documents for SCS:
  - `hybrid-code-search.md` — Primary design spec (architecture, schema, chunking rules, RRF, graph rules, dead code, CLI).
  - `language-extractor.md` — AST node kinds per language for call-graph extraction.
  - `language-extractor.json` — Machine-readable Language Extractor Profiles for C#, Java, Python, JS, TS, COBOL, SQL.
  - `manifest.json` — Example SCS configuration file (chunking limits, embedding config, hybrid ranking params, graph settings, dead-code settings, entrypoint heuristics).
- `repos/` — Test repositories used to validate skills. `repos/ctcm-api` is a .NET 8 / C# / EF Core codebase with ~271K LOC across ~4,500 files.
- `src/` — Does not exist yet. SCS code will be created here at `src/scs/`.

### Key terms

- **SCS (Semantic Code Search)**: The system being built. A Python CLI and library that indexes a codebase into a vector store and SQLite database, then provides hybrid search, graph trace, and dead-code detection.
- **Hybrid search**: Combining two retrieval strategies — lexical (keyword matching via SQLite FTS5) and vector (embedding similarity via Chroma) — and merging their results.
- **RRF (Reciprocal Rank Fusion)**: A formula for merging ranked lists from different retrieval systems. For a document `d` appearing at rank `r` in list `i`, the RRF score is `score(d) = sum_i( w_i / (k + rank_i(d)) )` where `k` is typically 60. Higher score = more relevant.
- **Chonkie**: A Python library for AST-based code chunking using tree-sitter. Its `CodeChunker` class parses source files into an AST and extracts semantic units (functions, classes, etc.) as chunks.
- **Chroma (chromadb)**: A local vector database. In persistent mode it stores embeddings and metadata in a SQLite-backed directory. Supports cosine similarity search and metadata filtering.
- **Qwen3-Embedding-0.6B**: A 0.6-billion-parameter embedding model from Alibaba's Qwen team. Runs locally on CPU or GPU, supports up to 32K context tokens, and allows configurable output dimensions (e.g., 1024 or 512).
- **tree-sitter**: A parser generator that produces fast, incremental parsers. Used by Chonkie under the hood. Language grammars are available as Python packages (e.g., `tree-sitter-languages`).
- **FTS5**: SQLite's full-text search extension. Allows keyword search over text columns with BM25 ranking.
- **NetworkX**: A Python library for graph analysis. Used here as a compute layer over the SQLite-stored call graph to compute reachability, shortest paths, and centrality metrics.
- **Language Extractor Profile**: A JSON configuration block (one per language) that tells the indexer which AST node kinds represent call sites, identifiers, imports, and symbol definitions. Stored in `language-extractor.json` and loaded at index time.
- **Evidence pack**: The output format from `scs query`. Each result includes: code snippet, file path + line range, symbol context (qualified name, kind), match explanation (which retrieval systems matched and at what rank), and optional graph neighbors.
- **Dead-code candidate**: A symbol (function, class, method) that has zero incoming references or calls (excluding self-references, test-only references, and generated/vendor code) and is not marked as exported or an entrypoint. This is a syntactic heuristic, not runtime analysis.

### On-disk artifacts produced by SCS

When `scs index` runs on a repository, it creates:

    <repoRoot>/
      legacylift-docs/
        context/
          scs/
            chroma/                 # Chroma persistence directory (vector store)
            scs.sqlite              # SQLite: symbols, chunks, edges, FTS5, metrics
            manifest.json           # Config, versions, commit hash, stats
            logs/                   # Indexing logs

These artifacts are local to the analyzed repository (not the LegacyLift repo itself). They live under `legacylift-docs/context/scs/`, consistent with where other LegacyLift skills write their output. The `legacylift-docs/` directory is covered by global excludes in the LegacyLift harness.

## Plan of Work

The work is organized into nine milestones. Each milestone is independently verifiable and builds on the prior one. The first milestone is a prototyping spike to validate that the three core libraries (Chonkie, Qwen3-Embedding-0.6B, Chroma) work together as expected before committing to the full architecture.

### Milestone 0: Prototyping Spike

**Scope**: Validate feasibility of the three core libraries independently and together on a small code sample (a single C# file from `repos/ctcm-api`). This milestone produces a throwaway script, not production code.

**What exists at the end**: A script at `src/scs/spike/spike_validate.py` that: (a) uses Chonkie CodeChunker to chunk a C# file into SymbolBody chunks, (b) uses `transformers` + `torch` to generate embeddings with Qwen3-Embedding-0.6B, (c) stores them in a Chroma persistent collection, (d) runs a vector query and a keyword query and prints results. The spike also validates that `tree-sitter-language-pack` (or equivalent) provides a C# parser.

**Commands to run** (from repo root):

    cd src/scs/spike
    python spike_validate.py --file ../../../repos/ctcm-api/src/SomeController.cs

**Acceptance**: The script prints chunked symbols with names and line ranges, prints embedding dimensions (should be 1024), prints top-3 vector search results for a test query, and prints top-3 FTS results. No errors. If Chonkie does not support C# or its CodeChunker API differs from what the design assumes, document the gap in `Surprises & Discoveries` and adjust the plan.

**Criteria for promoting or discarding**: If all three libraries work as designed, proceed to Milestone 1. If Chonkie's CodeChunker does not work for the target languages, evaluate alternatives (direct tree-sitter chunking, or using Chonkie's other chunker types with manual AST integration). If Qwen3-Embedding-0.6B requires more than 8GB RAM on CPU, consider GGUF quantized variant via `llama-cpp-python`. Document any such decision in the Decision Log.

### Milestone 1: Project Scaffolding

**Scope**: Create the Python package structure, CLI entry point, configuration loading, and SQLite schema.

**What exists at the end**: A `src/scs/` Python package with:

    src/scs/
      __init__.py
      __main__.py              # CLI entry point (click or argparse)
      cli.py                   # CLI commands: index, query, trace, deadcode
      config.py                # Load and validate manifest.json
      db/
        __init__.py
        schema.py              # SQLite schema creation (tables from hybrid-code-search.md)
        connection.py          # SQLite connection manager
      models.py                # Dataclasses: Chunk, Symbol, Edge, SymbolMetrics, EvidencePack

A `pyproject.toml` at `src/scs/pyproject.toml` (or at repo root if preferred) declaring dependencies: `chonkie`, `chromadb`, `networkx`, `numpy`, `transformers`, `torch`, `tqdm`, `click` (for CLI), `orjson`.

The CLI skeleton responds to `python -m scs --help` and shows four subcommands: `index`, `query`, `trace`, `deadcode` (each prints "not yet implemented").

Running `python -m scs index --init-db --repo-root .` creates the SQLite database at `legacylift-docs/context/scs/scs.sqlite` with all tables from the schema in `hybrid-code-search.md` (chunks, symbols, edges, symbol_metrics, chunks_fts).

**Commands to run**:

    cd src/scs
    pip install -e .
    python -m scs --help
    python -m scs index --init-db --repo-root ../../repos/ctcm-api
    sqlite3 ../../repos/ctcm-api/legacylift-docs/context/scs/scs.sqlite ".tables"

**Acceptance**: `--help` shows the four subcommands. `--init-db` creates the database file and `.tables` shows `chunks`, `symbols`, `edges`, `symbol_metrics`, `chunks_fts`.

### Milestone 2: Indexer

**Scope**: Implement the full indexing pipeline: file walking (with include/exclude globs from manifest.json), chunking (Chonkie CodeChunker), embedding (Qwen3-Embedding-0.6B), SQLite upsert, Chroma upsert, FTS5 population.

**What exists at the end**: Running `python -m scs index --repo-root <path>` walks the repository, chunks all supported source files, generates embeddings, and populates both SQLite and Chroma. The manifest.json is written with stats (file count, chunk count, time elapsed). Incremental indexing (only re-index changed files by content hash) works.

New/modified files:

    src/scs/
      indexer/
        __init__.py
        walker.py              # File walker with glob include/exclude
        chunker.py             # Chonkie CodeChunker wrapper, produces Chunk objects
        embedder.py            # Qwen3-Embedding-0.6B wrapper, batched embedding
        store.py               # Upsert to SQLite + Chroma + FTS5
        manifest.py            # Read/write manifest.json with stats and config

The chunker must produce three chunk types per the design: SymbolBody, Signature, and FileSummary. Each chunk carries metadata: path, language, chunk_type, symbol_name, qualified_name, start_line, end_line, content_hash.

The embedder prepends `doc:` to chunk text before embedding (per manifest.json `text_format` config). It uses the header template from manifest.json to prepend structured metadata to the text before embedding.

**Commands to run**:

    python -m scs index --repo-root ../../repos/ctcm-api

**Acceptance**: After indexing completes, verify:

    sqlite3 ../../repos/ctcm-api/legacylift-docs/context/scs/scs.sqlite "SELECT COUNT(*) FROM chunks;"
    sqlite3 ../../repos/ctcm-api/legacylift-docs/context/scs/scs.sqlite "SELECT COUNT(*) FROM symbols;"
    sqlite3 ../../repos/ctcm-api/legacylift-docs/context/scs/scs.sqlite "SELECT DISTINCT language FROM chunks;"

Chunks count should be in the thousands (ctcm-api has ~4,500 files). Symbols count should be in the hundreds or thousands. Languages should include `c_sharp`. Running the index command a second time (without code changes) should complete quickly (incremental mode skips unchanged files).

### Milestone 3: Hybrid Search with RRF

**Scope**: Implement lexical retrieval (FTS5), vector retrieval (Chroma), and RRF fusion. The `scs query` command returns ranked evidence packs.

New/modified files:

    src/scs/
      search/
        __init__.py
        lexical.py             # FTS5 search, returns ranked chunk_ids
        vector.py              # Chroma query, returns ranked chunk_ids
        rrf.py                 # RRF fusion: merge two ranked lists
        filters.py             # Metadata filters (language, path prefix, chunk_type)
        evidence.py            # Build EvidencePack from fused results

The `scs query` command accepts a natural-language query string and optional filters. It:

1. Runs FTS5 query against `chunks_fts`, returning top `k_lex` (default 40) chunk IDs with ranks.
2. Runs Chroma vector query (embedding the query with `query:` prefix) returning top `k_vec` (default 40) chunk IDs with ranks.
3. Fuses results using RRF with `k=60`, `w_lex=1.0`, `w_vec=1.0` (configurable in manifest.json).
4. Applies metadata filters if provided.
5. Returns top `top_k` (default 20) results as evidence packs.

Each evidence pack contains: code snippet, file path, start/end line, symbol name, qualified name, language, chunk type, RRF score, which retrieval systems matched (lex/vec/both) and at what rank.

**Commands to run**:

    python -m scs query "claims adjudication" --repo-root ../../repos/ctcm-api
    python -m scs query "ClaimsController" --repo-root ../../repos/ctcm-api --filter-language c_sharp
    python -m scs query "database migration" --repo-root ../../repos/ctcm-api --top-k 5

**Acceptance**: The first query returns results related to claims adjudication with file paths and line ranges. The identifier query ("ClaimsController") should rank the controller definition highly (lexical match should be strong). Results include both `lex_rank` and `vec_rank` fields showing which retrieval systems contributed. The `--top-k 5` flag limits output to 5 results.

### Milestone 4: Graph Build and Trace

**Scope**: Extract call/reference/import edges from chunks using Language Extractor Profiles, resolve edges heuristically, load into NetworkX for analysis, and implement the `scs trace` command.

New/modified files:

    src/scs/
      graph/
        __init__.py
        extractor.py           # AST-based edge extraction using language-extractor.json profiles
        resolver.py            # Heuristic edge resolution (same-file, same-dir, repo-wide)
        analyzer.py            # NetworkX loader, reachability, SCCs, centrality
        trace.py               # Forward/backward trace with evidence

Edge extraction walks each SymbolBody chunk's AST (via tree-sitter) and emits edges per the Language Extractor Profile for that language. Each edge has: src_chunk_id, src_symbol_id, edge_type (CALLS, REFERENCES, IMPORTS, DEFINES), dst_name (unresolved text), confidence, evidence_start_line, evidence_end_line, evidence_text.

Resolution heuristic tries to resolve `dst_name` to a `symbol_id` in this order (per the design):
1. Same file exact name match.
2. Same directory/module name match.
3. Repo-wide unique name match.
4. Language-specific heuristics (namespace/class receiver parsing).

When resolved, the edge gets `dst_symbol_id` set and confidence bumped by the `resolved_link_bonus` (0.25 per `language-extractor.json` defaults).

The `scs trace` command accepts a symbol name or symbol ID and direction (forward, backward, or both). It traverses the edge graph up to a configurable depth (default 3, max 8) and returns a list of hops, each with: symbol name, file path, line range, edge type, confidence, evidence snippet.

**Commands to run**:

    python -m scs trace --symbol "ClaimsController" --direction both --depth 3 --repo-root ../../repos/ctcm-api
    python -m scs trace --symbol "ClaimsService.ProcessClaim" --direction forward --repo-root ../../repos/ctcm-api

**Acceptance**: The trace output shows a tree of callers (backward) and callees (forward) with file paths and evidence snippets. Each hop shows confidence and edge type. The output is structured (JSON or formatted text) so skills can parse it.

### Milestone 5: Dead-Code Candidate Report

**Scope**: Compute symbol metrics (in_refs, in_calls, out_calls, reachable_from_entry) and generate a dead-code candidate report via `scs deadcode`.

New/modified files:

    src/scs/
      analysis/
        __init__.py
        deadcode.py            # Compute metrics, identify unreferenced candidates
        metrics.py             # Populate symbol_metrics table

A symbol is an unreferenced candidate if (per the design): `in_refs + in_calls == 0` after filtering out self-references within its own chunk, test-only references, and generated/vendor directories. Additionally, the symbol must not be marked as exported (`is_exported=1`) or an entrypoint (`is_entrypoint=1`).

Entrypoint marking uses the heuristics and explicit entries from manifest.json (`entrypoints` section).

The `scs deadcode` command outputs a report: list of unreferenced candidate symbols grouped by file, with symbol name, kind, file path, line range, and a confidence score. It also reports summary stats (total symbols, total candidates, percentage).

**Commands to run**:

    python -m scs deadcode --repo-root ../../repos/ctcm-api
    python -m scs deadcode --repo-root ../../repos/ctcm-api --format json

**Acceptance**: The report lists candidate dead-code symbols. Known public API controllers should NOT appear (they are exported). Test classes should NOT appear (filtered by path glob). The JSON format is parseable by skills.

### Milestone 6: LegacyLift Skill Wrappers

**Scope**: Create Claude Code skills that invoke the SCS CLI commands. Each CLI subcommand gets a corresponding skill, plus a router skill that directs the agent to the right sub-skill.

New files:

    .claude/skills/scs/SKILL.md                    # Router skill (user-invocable)
    .claude/skills/scs-index/SKILL.md               # Wraps `scs index`
    .claude/skills/scs-query/SKILL.md               # Wraps `scs query`
    .claude/skills/scs-trace/SKILL.md               # Wraps `scs trace`
    .claude/skills/scs-deadcode/SKILL.md             # Wraps `scs deadcode`

Each skill's SKILL.md has YAML frontmatter (`name`, `description`, `allowed-tools`) and instructions that tell Claude how to invoke the corresponding CLI command, what parameters to pass, and how to interpret the output.

The router skill (`scs`) is user-invocable and determines which sub-skill to delegate to based on the user's intent. For example, if the user says "find all code related to claims processing," the router invokes `scs-query`. If the user says "index this repository for search," it invokes `scs-index`.

The sub-skills (`scs-index`, `scs-query`, `scs-trace`, `scs-deadcode`) should have `user-invocable: true` so they can also be called directly.

Skill allowed-tools should include at minimum: `Bash` (to invoke the CLI), `Read` (to read results), `Write` (to write reports if needed).

**Acceptance**: Running `/scs index this repository` from Claude Code invokes `scs index` on the current directory. Running `/scs-query "claims adjudication"` returns ranked search results. The skills are visible in the `/` menu.

### Milestone 7: Integration Testing

**Scope**: End-to-end test against `repos/ctcm-api`. Validate the full pipeline: index, query, trace, deadcode.

**Commands to run**:

    cd repos/ctcm-api
    python -m scs index --repo-root .
    python -m scs query "claims adjudication" --repo-root .
    python -m scs query "ClaimsController" --repo-root . --filter-language c_sharp
    python -m scs trace --symbol "ClaimsController" --direction both --repo-root .
    python -m scs deadcode --repo-root .

**Acceptance**: All commands complete without error. Query results are relevant (claims-related code ranks high for claims queries). Trace shows meaningful caller/callee chains. Dead-code report excludes controllers and public API symbols. Indexing time for ctcm-api (~4,500 files, ~271K LOC) is documented for reference.

### Milestone 8: Documentation and Cleanup

**Scope**: Update this ExecPlan with final outcomes, update `.claude/skills/README.md` to list the new SCS skills, add SCS to the skill catalog in `docs/legacylift/architecture.md`, remove the prototyping spike code, and ensure all dependencies are documented.

**Acceptance**: The README lists the SCS skills. The architecture doc includes SCS in the skill catalog. This ExecPlan's `Outcomes & Retrospective` section is complete.

## Concrete Steps

(This section will be updated as each milestone is implemented. Below are the initial setup steps.)

### Setup

From the repository root:

    python --version
    # Expect Python 3.10+ (required for Chonkie and transformers)

    pip install chonkie chromadb networkx numpy transformers torch tqdm click orjson
    # Or: create a virtual environment first

    # Verify tree-sitter language support
    python -c "from chonkie import CodeChunker; print('Chonkie imported OK')"

### Milestone 0 commands

    mkdir -p src/scs/spike
    # (create spike_validate.py — see Milestone 0 description)
    cd src/scs/spike
    python spike_validate.py --file ../../../repos/ctcm-api/src/CTCM.Api/Controllers/ClaimsController.cs

Expected output (approximate):

    Chunks found: 12
      - ClaimsController (class, lines 15-180)
      - GetClaim (method, lines 22-45)
      - ProcessClaim (method, lines 47-89)
      ...
    Embedding dimensions: 1024
    Vector search results for "process a claim":
      1. ProcessClaim (ClaimsController.cs:47-89) score=0.82
      2. ...
    FTS results for "process a claim":
      1. ...

## Validation and Acceptance

The overall acceptance criteria for the complete SCS implementation:

1. **Indexing works**: `scs index` processes a polyglot repository (ctcm-api is C# with SQL files), creates `legacylift-docs/context/scs/` artifacts, and completes without error. Re-running is incremental (fast for unchanged files).

2. **Hybrid search returns relevant results**: `scs query "claims adjudication"` returns claims-related code in the top results. Pure identifier queries (e.g., `"ClaimsController"`) also rank well (lexical boost).

3. **Trace shows caller/callee chains**: `scs trace --symbol "ClaimsController"` shows meaningful edges with evidence snippets and confidence scores.

4. **Dead-code report is conservative**: Public/exported symbols and entrypoints are excluded. Test code is excluded. The report includes file paths and line ranges.

5. **Skills are functional**: The four SCS skills (`scs-index`, `scs-query`, `scs-trace`, `scs-deadcode`) and the router skill (`scs`) are invocable from Claude Code and produce useful output.

6. **Performance is acceptable**: Indexing ctcm-api (~271K LOC) completes in a reasonable time on a laptop (target: under 30 minutes for full index, under 2 minutes for incremental). Queries return in under 5 seconds.

## Idempotence and Recovery

All steps can be run multiple times safely:

- `scs index` is incremental by design. It checks content hashes and only re-indexes changed files. Running it twice with no code changes is a no-op (fast).
- The SQLite schema uses `CREATE TABLE IF NOT EXISTS` and upserts (INSERT OR REPLACE).
- Chroma upserts by chunk ID (stable UUIDs derived from path + chunk_type + start_line + end_line + content_hash).
- If indexing fails midway, re-running it picks up where it left off (unchanged files are skipped, and upserts are safe for already-indexed files).
- The `--init-db` flag recreates the database from scratch if needed (destructive, but explicit).

## Artifacts and Notes

### SQLite schema

The full schema is defined in `hybrid-code-search.md` lines 196-265. The five tables are:

- `chunks` — Chunk metadata (path, language, chunk_type, symbol info, line ranges, content_hash).
- `symbols` — Symbol definitions (function, method, class, etc.) with kind, qualified name, export/entrypoint flags.
- `edges` — Caller/callee/reference/import edges with confidence scores and evidence text.
- `symbol_metrics` — Precomputed metrics for dead-code detection and ranking (in/out degree, reachability).
- `chunks_fts` — FTS5 virtual table for lexical search over chunk text, path, and symbol names.

### Language Extractor Profiles

The file `language-extractor.json` in the design directory contains profiles for 7 languages: C#, Java, Python, JavaScript, TypeScript, COBOL, SQL. Each profile specifies:

- `call_site_nodes` — AST node types that represent function/method invocations.
- `callee_extractors` — How to extract the callee name from each call site node type.
- `symbol_definitions` — AST node types for function/class/interface definitions.
- `imports` — AST node types for import/using statements.
- `references` — AST node types for identifier references.

This file should be loaded at index time and copied into the SCS package (or referenced from the design directory). New languages can be added by creating a new block in this JSON.

### Manifest.json configuration

The file `manifest.json` in the design directory is the example/default configuration. Key settings:

- Chunking: max 600 lines per SymbolBody, 24K chars per chunk, AST boundary preference.
- Embeddings: Qwen3-Embedding-0.6B, 1024 dimensions, `doc:` / `query:` prefixes, batched (16).
- Hybrid ranking: RRF with k=60, equal weights, 40 candidates from each retriever, top 20 results.
- Graph: resolution strategy order (same_file → same_dir → repo_unique → repo_best_effort), min confidence 0.65 to link, trace depth default 3 / max 8.
- Dead code: unreferenced candidate mode, exclude exported/entrypoint, ignore test paths.

## Interfaces and Dependencies

### Python dependencies

- `chonkie` — CodeChunker for AST-based chunking. Install: `pip install chonkie[code]` (the `[code]` extra pulls in tree-sitter dependencies).
- `chromadb` — Local vector database. Install: `pip install chromadb`.
- `networkx` — Graph analysis. Install: `pip install networkx`.
- `numpy` — Numeric support. Install: `pip install numpy`.
- `transformers` — Hugging Face model loading for Qwen3-Embedding-0.6B. Install: `pip install transformers`.
- `torch` — PyTorch backend for transformers. Install: `pip install torch`.
- `tqdm` — Progress bars. Install: `pip install tqdm`.
- `click` — CLI framework. Install: `pip install click`.
- `orjson` — Fast JSON serialization. Install: `pip install orjson`.

### External tools (optional)

- `ripgrep` (`rg`) — Fallback lexical search if FTS5 is unavailable. Usually already present on dev machines.

### Key interfaces to implement

In `src/scs/indexer/chunker.py`:

    class CodeChunkerWrapper:
        def __init__(self, config: dict):
            """Initialize with chunking config from manifest.json."""
            ...

        def chunk_file(self, file_path: str, language: str) -> list[Chunk]:
            """Parse file with Chonkie CodeChunker, return Chunk objects."""
            ...

In `src/scs/indexer/embedder.py`:

    class Embedder:
        def __init__(self, model_name: str, device: str, output_dim: int):
            """Load Qwen3-Embedding-0.6B model."""
            ...

        def embed_batch(self, texts: list[str]) -> np.ndarray:
            """Generate embeddings for a batch of texts. Returns array of shape (N, output_dim)."""
            ...

In `src/scs/search/rrf.py`:

    def reciprocal_rank_fusion(
        ranked_lists: list[list[tuple[str, int]]],  # list of (chunk_id, rank) lists
        weights: list[float],
        k: int = 60,
    ) -> list[tuple[str, float]]:
        """Fuse ranked lists using RRF. Returns list of (chunk_id, score) sorted descending."""
        ...

In `src/scs/graph/extractor.py`:

    class EdgeExtractor:
        def __init__(self, profiles: dict):
            """Initialize with language extractor profiles from language-extractor.json."""
            ...

        def extract_edges(self, chunk: Chunk, ast_tree) -> list[Edge]:
            """Extract CALLS, REFERENCES, IMPORTS, DEFINES edges from a chunk's AST."""
            ...

In `src/scs/graph/trace.py`:

    def trace(
        symbol_name: str,
        direction: str,  # "forward", "backward", "both"
        depth: int,
        db_path: str,
    ) -> list[TraceHop]:
        """Traverse the edge graph from a symbol. Returns list of hops with evidence."""
        ...

In `src/scs/analysis/deadcode.py`:

    def find_unreferenced_candidates(db_path: str, config: dict) -> list[DeadCodeCandidate]:
        """Find symbols with zero incoming references after applying exclusion rules."""
        ...

### CLI commands (click)

    scs index [--repo-root PATH] [--init-db] [--full-rebuild] [--config PATH]
    scs query QUERY [--repo-root PATH] [--top-k N] [--filter-language LANG] [--filter-path PREFIX] [--format text|json]
    scs trace [--symbol NAME] [--direction forward|backward|both] [--depth N] [--repo-root PATH] [--format text|json]
    scs deadcode [--repo-root PATH] [--format text|json] [--min-confidence FLOAT]

### Skill YAML frontmatter (for Milestone 6)

The router skill:

    ---
    name: scs
    description: Semantic Code Search — hybrid vector + lexical search, graph trace, and dead-code detection for any codebase.
    allowed-tools: Bash, Read, Write, Glob, Grep
    user-invocable: true
    ---

Each sub-skill (e.g., scs-index):

    ---
    name: scs-index
    description: Index a codebase for semantic code search (builds vector store, SQLite database, and call graph).
    allowed-tools: Bash, Read
    user-invocable: true
    ---

---

## Design Questions

The following questions are unresolved and should be discussed before or during implementation. Answers should be recorded in the Decision Log.

1. **Package location and installation**: Should `src/scs/` be a standalone installable package with its own `pyproject.toml`, or should it be a subdirectory within the LegacyLift repo with dependencies declared at the repo root? The repo currently has no `src/` directory or root-level `pyproject.toml`.

2. **Python environment management**: What Python environment should SCS run in? Should it use a virtual environment within the repo (e.g., `.venv/`), or expect a system-wide install? How does this interact with Claude Code's execution environment (which may be running in a container or on the user's local machine)?

3. **Chonkie CodeChunker API validation**: The design assumes Chonkie's `CodeChunker` can produce three chunk types (SymbolBody, Signature, FileSummary) and exposes symbol names, qualified names, and line ranges. This needs validation in Milestone 0. What is the actual API? Does it support all the languages we need (especially C# and COBOL)?

4. **Qwen3-Embedding-0.6B resource requirements**: What are the actual RAM/VRAM requirements on CPU vs GPU? The design calls for a laptop-first approach. If the model requires more than 8GB RAM, should we default to the GGUF variant via `llama-cpp-python` instead of `transformers + torch`?

5. **tree-sitter language availability**: Which tree-sitter language grammars are available via the `tree-sitter-language-pack` (Chonkie's dependency)? Does it include C#, COBOL, and SQL? If not, how do we install additional grammars?

6. **Edge extraction timing**: Should edge extraction (graph building) happen during the indexing pass (Milestone 2) or as a separate post-pass (Milestone 4)? The design in `hybrid-code-search.md` describes it as part of the indexing workflow (step 3), but implementing it separately would allow Milestones 2 and 4 to be more independent.

7. **Skill output format**: When a skill like `scs-query` returns results to the agent, what format should it use? Plain text (human-readable), JSON (machine-parseable), or both? Should the skill write results to a file, or print to stdout for the agent to read?

8. **Chroma collection naming**: The design uses `code_chunks_v1` as the collection name. If a repo is re-indexed with a different schema version, should we create a new collection (e.g., `code_chunks_v2`) or drop and recreate? How do we handle schema migrations?

9. **Incremental indexing with git**: The manifest.json includes `use_git_diff_for_incremental: true`. Should we use `git diff` to find changed files (fast but requires git), or content-hash comparison (works without git but slower)? What happens for repos that are not git repositories?

10. **FTS5 availability**: SQLite's FTS5 extension is not available in all Python sqlite3 builds. Should the code check for FTS5 at startup and fall back to ripgrep if unavailable? Or should we require FTS5 and document the dependency?

11. **Embedding model download**: Qwen3-Embedding-0.6B needs to be downloaded from Hugging Face (~1.2GB). Should this happen automatically on first `scs index` run, or should there be a separate `scs setup` command? How do we handle air-gapped / offline environments?

12. **Relationship to fact-graph**: SCS and the fact-graph skill both analyze code structure and extract entities/relationships. Should SCS consume the fact-graph output (if available) to bootstrap its symbol table and reduce redundant parsing? Or are they independent systems? Could the fact-graph skill eventually use SCS as its analysis backend?

13. **Performance targets for large repos**: The design says "2M LOC / laptop-first". What is the actual performance target for indexing? Is 30 minutes acceptable for a full index of a 2M LOC repo? What about query latency — is 5 seconds acceptable, or do we need sub-second?

14. **COBOL and SQL tree-sitter parser selection**: The `language-extractor.json` references specific tree-sitter parser repos (e.g., `yutaro-sakamoto/tree-sitter-cobol`, `derekstride/tree-sitter-sql`). Are these the parsers that Chonkie / `tree-sitter-language-pack` uses? If not, there may be AST node-kind mismatches.

15. **Skill integration with existing LegacyLift workflow**: Where does SCS fit in the existing skill execution order (Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 as described in `architecture.md`)? Is `scs index` a prerequisite like `fact-graph`? Should other documentation skills be updated to use `scs query` instead of (or in addition to) Grep?

---

## Revision Notes

- **2026-03-20**: Initial ExecPlan created from design documents in `docs/legacylift/exec-plans/active/semantic-code-search/`. All four source files were read: `hybrid-code-search.md` (primary architecture), `language-extractor.md` (AST node kinds), `language-extractor.json` (machine-readable extractor profiles), `manifest.json` (default configuration). Design questions captured for unresolved areas. No implementation has begun.
