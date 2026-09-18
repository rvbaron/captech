# Build Semantic Code Search and Graph Indexing for LegacyLift

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

If a `PLANS.md` file is checked into the repository, this document must be maintained in accordance with that file. If no `PLANS.md` file exists, this ExecPlan is the governing implementation plan.

This is a large effort split into two files per `docs/exec-plan.md` ("Large plans: split current state from archived detail"). This file holds the **current state**: purpose, the full `Progress` checklist, the living `Surprises & Discoveries` and `Decision Log`, a current-status `Outcomes & Retrospective` summary, the orientation and design narrative, the active/paused/upcoming milestone steps, and the validation/interface sections. Completed-milestone detail — full per-milestone retrospective entries, the foundational wave dispatch plan, and the `Concrete Steps` for shipped milestones — lives in the companion archive `semantic-code-search-graph-index-additional-info.md`. **You do not need the archive to continue current work; this file is self-contained for that. Open the archive only when you need the history** (e.g., how a shipped milestone was built or why). When a milestone moves from active to complete, migrate its `Concrete Steps` and write its retrospective entry into the archive, and update this file's `Progress` and `Outcomes & Retrospective` summary to match.

## Purpose / Big Picture

After this change, a LegacyLift analysis agent can index a software repository once and then retrieve high-quality code context using semantic search, lexical search, and caller/callee graph traversal instead of relying on raw grep. A user will be able to run one command to build a local index, then ask questions such as “where is provider enrollment reclaimed,” “who calls this method,” or “show the code path that validates eligibility,” and receive ranked chunks with file paths, line numbers, symbols, and related call graph context.

This work is the start of LegacyLift v4, a clean rewrite. The existing v3 skills under `.claude/skills/` (including `fact-graph` and the documentation generators) remain in the repository for reference only. They MUST NOT be used as inputs, dependencies, or fallback data sources for the semantic code search. v4 components must derive everything they need from the source repository directly.

The working behavior is observable from the command line. After implementation, running `legacylift-search index --repo-root repos/<repo-name>` creates a per-repository index directory under `repos/<repo-name>/legacylift-docs/index/code-search/` containing a Chroma vector store and a SQLite graph/search database. Running `legacylift-search search "provider enrollment reclaim validation" --limit 5` returns ranked results with file paths, line ranges, languages, matched symbols, and snippets. Running `legacylift-search callees <symbol-id>` or `legacylift-search callers <symbol-id>` returns graph relationships extracted from code.

This plan creates a self-contained Python CLI package in the repository. It does not assume any existing application framework. If the repository already has a Python package, keep this tool isolated under `tools/legacylift_search` unless the maintainer decides to integrate it later.

## Progress

- [x] (2026-05-08 00:00Z) Initial design captured as an executable, self-contained implementation plan.
- [x] (2026-05-12) Plan finalized with v4 scoping decisions: index artifacts live under `repos/<repo>/legacylift-docs/index/code-search/` (gitignored, with freshness check); validation runs against repos in `./repos/`; tree-sitter via `tree-sitter-language-pack`; existing v3 fact-graph artifacts are reference-only and not consumed.
- [x] (2026-05-12) Confirmed no `PLANS.md` exists at the repository root; this ExecPlan governs.
- [x] (2026-05-13) Create the Python package skeleton for the semantic code search CLI. Verified `legacylift-search --help` lists all 9 commands (init-config, index, validate, search, symbols, callers, callees, stats, dump-ast). Work landed on branch `worktree-agent-adffebef39d39605d` in 5 commits (2992ee0, 6ca2e5c, f6e5a73, 0b899be, 5d18b55).
- [x] (2026-05-14) Add manifest loading, validation, and default configuration (Milestone 2, Wave A Agent A1). Pydantic v2 models (ProjectConfig, IndexConfig, ChunkingConfig, EmbeddingConfig, SearchConfig, LanguagesConfig, Manifest), load_manifest, write_default_manifest, resolve_index_dir, init-config CLI command, sample manifest at repo root, and 9 passing tests. Work landed on branch `feature/scs-m2-config` in 4 commits (485a956, 56e4648, f34d19d, a96d1d4).
- [x] (2026-05-14) Add repository discovery and language detection (Milestone 3, Wave A Agent A2). LanguageSpec model with 7-language registry (C#, Java, Python, JavaScript, TypeScript, COBOL, SQL), detect_language and get_language functions, discover_source_files with pathspec gitignore-style include/exclude globs and SHA-256 file hashing, polyglot fixture repo with 7 source files + 2 excluded files (node_modules, dist), and 4 passing tests. Work landed in commit 52a72f0 on branch `feature/scs-m2-config`.
- [x] (2026-05-14) Add extractor profiles JSON and loader (Milestone 4, Wave A Agent A3). `extractors.json` with 7 language profiles (csharp, java, python, javascript, typescript, cobol, sql) matching spec verbatim. ExtractorProfiles, ProfileEntry, FallbackPatterns Pydantic models with schema_version=1 validation. load_profiles() and get_profile() functions. 6 loader-only tests pass. Branch `feature/scs-m4-profiles`, commit ef08697. Full SymbolExtractor body remains pending for Wave B Agent B1.
- [x] (2026-05-14) Add embeddings module (Milestone 9a, Wave A Agent A4). Embedder protocol (dimension, name, embed_documents, embed_query), HashEmbedder (deterministic blake2b tokenization and L2-normalization, dimension=64 default), QwenEmbedder stub (raises NotImplementedError for Agent B4), create_embedder dispatch (supports hash/qwen3 providers with override), and 11 passing tests. Work included in merge commit a56d5f6 on branch `feature/scs-m2-config`.
- [x] (2026-05-15) Add code chunking using Chonkie where available and deterministic fallback chunking where Chonkie cannot parse a file (Milestone 6, Wave B Agent B2). Implemented CodeChunker with three-tier strategy: (1) symbol-based chunks from extracted symbols with non-empty ranges, (2) Chonkie AST-aware chunking when symbol coverage <30%, (3) line-based windowing with configurable overlap as fallback. Deterministic chunk IDs, token count estimation without tokenizer dependency, correct byte/line range preservation. Chonkie successfully installed on Python 3.12/Windows 11. 8 passing tests. Work landed on branch `feature/scs-m6-chunking`, commit ca3dc2e.
- [x] (2026-05-15) Add tree-sitter-based symbol and call extraction for mainstream languages (Milestone 5, Wave B Agent B1). `SymbolExtractor` with per-language tree-sitter parsing for Python, JavaScript, TypeScript, Java, C#, and SQL. Regex fallback for all 7 profiles; deterministic Symbol IDs and Ref IDs; qualified-name building from container nesting. `dump-ast` CLI command implemented. 16 passing tests. Branch `feature/scs-m5-extractors`.
- [x] (2026-05-15) Add COBOL extractor spike and fallback implementation (Milestone 5). COBOL uses the regex fallback path, which correctly extracts `PROGRAM-ID`, paragraphs, and PERFORM/CALL/GO TO references from the polyglot fixture without raising.
- [x] (2026-05-15) Add SQLite schema, migrations, and upsert logic (Milestone 7, Wave B Agent B3). SQLiteStore with DDL verbatim from spec: WAL mode, foreign keys, all tables (index_metadata, repo_files, chunks, chunk_fts FTS5, symbols, symbol_refs, graph_edges) with indexes. Full upsert operations, FTS5 MATCH lexical search with query sanitization, graph queries (callers/callees), symbol lookup, stats, metadata storage. 7 passing tests. FTS5 confirmed available on Windows Python 3.12. Work landed on branch `feature/scs-m6-chunking` (worktree drift), commit f13a921.
- [x] (2026-05-15) Add Chroma persistent vector indexing (Milestone 9b, Wave B Agent B4). ChromaVectorStore with upsert_chunks, query, validate_dimension, close methods. VectorResult Pydantic model. Handles None metadata by coercing to empty string. Close method with gc.collect for Windows SQLite file lock compatibility. 6 passing tests. Branch `feature/scs-m9b-vector`, commit 19550c4.
- [x] (2026-05-15) Add production Qwen3 embedder implementation (Milestone 9b, Wave B Agent B4). QwenEmbedder with lazy model loading via sentence-transformers, batching, normalization, RuntimeError with --embedding-provider hash suggestion on model load failure. 17 tests passing (11 from A4 + 6 from B4). Branch `feature/scs-m9b-vector`, commit 19550c4.
- [x] (2026-05-15) Add indexing orchestration end-to-end (Milestone 10, Wave C Agent C2). `Indexer` class with 15-step pipeline: resolve index dir, optional safe reset, manifest snapshot, SQLite migrations, file discovery, per-file extract+chunk+upsert, cross-file graph edge build with name+qualified-name index, batched embedding and Chroma upsert with dimension validation, full metadata write (schema_version, indexed_at, repo_root, manifest_sha256, embedder_name, embedding_dimension, chunk_count, symbol_count, graph_edge_count, source_set_sha256), index.log, 25%-zero-chunk failure threshold, path-safety check for `--reset`. CLI `legacylift-search index` wired with `--repo-root`, `--config`, `--index-dir`, `--reset`, `--embedding-provider` and rich-rendered IndexStats. Smoke run on bundled `polyglot_repo` fixture: 7 files indexed, 25 chunks, 28 symbols, 36 refs, 36 graph edges. 6 new tests (test_indexer.py); full suite 83 passing. Branch `feature/scs-m10-indexer`.
- [x] (2026-05-15) Add graph edge builder with confidence-scored callee resolution (Milestone 8, Wave C Agent C1). GraphBuilder.build_edges() constructs caller/callee edges from extracted symbols and references. Caller resolution prefers ref.enclosing_symbol_id, else finds nearest symbol by range. Callee resolution with confidence: 0.85 (exactly one candidate), 0.70 (multiple in same language, prefer same-file), 0.40 (cross-file/language ambiguity), 0.30 (unresolved). Edge kind mapping from ref.kind and language: COBOL PERFORM→performs, CALL→calls, EXEC SQL→executes_sql, EXEC CICS→executes_cics (evidence-based detection); SQL FROM/JOIN/UPDATE/INTO→uses_table; generic calls→calls, imports→imports. Deterministic edge IDs. 14 passing tests. Branch `feature/scs-m8-graph`, commit cdff08b.
- [x] (2026-05-15) Add lexical search using SQLite FTS5 (Milestone 11). Already shipped by Milestone 7 (`SQLiteStore.search_lexical`); Milestone 11 adds the `sanitize_fts_query` helper and the `SearchEngine` rank-extractor that consumes it.
- [x] (2026-05-15) Add reciprocal-rank-fusion hybrid ranking across vector and lexical results (Milestone 11, Wave D Agent D1). `SearchEngine` combines `ChromaVectorStore.query` and `SQLiteStore.search_lexical` results via RRF: `score = 1/(k+vrank) + 1/(k+lrank)` with `k=config.rrf_rank_constant` (default 60), 1-based ranks. Sort descending by score; tie-break by best available rank, then `relative_path`. Free-text queries are tokenized to `\w+` terms before reaching FTS5 (`sanitize_fts_query`); SQL bindings everywhere. Snippets trimmed to `2*snippet_radius_lines`. `legacylift-search search` CLI wired with `--repo-root`, `--config`, `--index-dir`, `--limit`, `--embedding-provider`, rendered through Rich in the format `<rank>. score=<s> <path>:<sl>-<el> <lang> <symbol_path>` followed by indented snippet lines. 5 new tests in `test_search.py` cover RRF math, `--limit` override, punctuation-heavy FTS sanitization (no-raise on real SQLite), and end-to-end fixture search. Full suite: 87 passing. Branch `feature/scs-m11-search`, commit 25e0ff1.
- [x] (2026-05-15) Add symbols, callers, callees, stats, and validate CLI commands (Milestone 12, Wave D Agent D2). Wired the five remaining query commands against the existing SQLiteStore + ChromaVectorStore. Added a small `cli_helpers` module to centralize the `--repo-root` / `--config` / `--index-dir` resolution pattern. `symbols` uses exact-match-then-contains via `SQLiteStore.find_symbols`; `callers` falls back to unresolved-edge name matching when no resolved callers exist; `callees` prints "no callees found" and exits 0 when empty; `stats` reports counts plus embedder metadata; `validate` checks SQLite/Chroma existence, required metadata keys, FTS5 smoke query, Chroma open, dimension consistency, and recomputes `source_set_sha256` from current discovery for `fresh`/`stale` reporting. 9 new tests (test_cli_commands.py); full suite 87 passing. Branch `feature/scs-m12-cli-commands`, commit 5862edb.
- [x] (2026-05-19) Add caller/callee graph persistence and traversal commands. Already completed by M8/M12 — `legacylift-search callers <symbol-id>` and `legacylift-search callees <symbol-id>` commands exist and work end-to-end. Validated against `repos/ctcm/ctcm-api` on 2026-05-19 (see M15+M16 retrospective below).
- [x] (2026-05-18) Add end-to-end CLI smoke tests (Milestone 13, Wave E Agent E1). `tests/test_cli_smoke.py` drives the full user journey via `typer.testing.CliRunner` on a tmp_path copy of `polyglot_repo`: `init-config` -> manifest edit forcing `embedding.dimension=64` -> `index --reset --embedding-provider hash` -> `validate` (assert `Index is valid.` and `freshness: fresh`) -> `search "provider eligibility validation"` (assert ranked result) -> `symbols --name EligibilityService` -> `stats` (assert nonzero counts and `hash` provider). Three additional tests cover idempotent re-index without `--reset`, staleness detection after touching `src/eligibility.py`, and `callees` for a known caller. 4 new tests; full suite 99 passing on Python 3.12 / Windows 11 in ~48s. Branch `feature/scs-m13-cli-smoke`, commit 946a614.
- [x] (2026-05-18) Validate against a polyglot fixture repo and document observed command output (Milestone 14, Wave E Agent E2). End-to-end validation against `repos/ctcm/ctcm-api` (the plan's nominal `repos/ctcm-api`; the actual on-disk path is `repos/ctcm/ctcm-api`, with `repos/ctcm` containing three subprojects: `ctcm-api`, `ctcm-db`, `ctcm-web`). Hash-embedder index produced 4,715 files, 58,677 chunks, 58,614 symbols, 135,973 refs, 141,219 graph edges. `validate`/`stats`/`search` all succeed; `freshness=fresh`; stale-detection confirmed by appending a comment to `src/CTCM.API/AppHost/Program.cs`. Added top-level `.gitignore` rule `repos/*/legacylift-docs/index/` and `repos/*/*/legacylift-docs/index/` to keep index artifacts untracked. Full pytest still 99 passing on Python 3.12. Branch `feature/scs-m14-validation`.
- [x] (2026-05-18) Write final Outcomes & Retrospective entry after implementation.
- [x] (2026-05-18) Speed up Chroma upsert and harden index metadata (post-Milestone-14 perf bundle). Three changes addressing the Chroma upsert bottleneck observed against `repos/ctcm/ctcm-api` (3,668 round trips / vectors not flushing within budget): (1) raise default `embedding.batch_size` from 16 to 512 — Chroma's per-call overhead dominates at small batch sizes; SQLite parameter cap allows up to ~5,461; (2) tune Chroma HNSW persistence in collection metadata (`hnsw:sync_threshold=100000`, `hnsw:batch_size=10000`) to buffer more inserts before fsync; (3) persist all `index_metadata` keys (incl. `source_set_sha256`) before the Chroma upsert phase, plus a new `vectors_upserted` counter that updates per batch — interrupted indexes now report `freshness=fresh` with `vectors_upserted < chunk_count` instead of `freshness=missing`. Full suite still 99 passing on Python 3.12. Polyglot smoke run confirms metadata is written and matches chunk count after success. Branch `feature/scs-perf-chroma-upsert`, commit f1efbb1. **Verified on `repos/ctcm/ctcm-api`**: cold `index --reset --embedding-provider hash` completed in **44 minutes** (vs. baseline 2+ hours, aborted) with `vectors_upserted == chunk_count == 58,677` (vs. baseline 15,264 / 58,677 = 26%). `validate` reports `freshness: fresh` automatically — no bridge-script workaround needed.
- [x] (2026-05-19) **Milestone 15: Skip-on-unchanged reindex (idempotent fast-path).** Per-file SHA short-circuit, partial-reindex graph rebuild over the union of changed+unchanged refs, Chroma upsert skip via a new local `vectors_present(chunk_id, text_sha256)` cache, deleted-file artifact removal (chunks/symbols/refs/edges/vectors), and a `validate` warning when `vectors_upserted < chunk_count`. Critical fix: `upsert_files` now only runs against changed files because `repo_files.relative_path` is UNIQUE and `INSERT OR REPLACE` cascades through chunks/symbols/symbol_refs FKs — re-upserting unchanged files would defeat the optimization. Polyglot fixture timing: cold `index --reset` 1.83s, idempotent rerun **0.29s (6.3x faster)**; `[extract+chunk]` and `[chroma-upsert]` phases drop to near-zero per the M16 timestamps. 5 new tests in `tests/test_m15_skip_unchanged.py`; full suite 104 passing on Python 3.12 / Windows 11. Branch `feature/scs-m15-skip-unchanged`.
- [x] (2026-05-19) Per-phase indexing log timestamps (Milestone 16). Added timestamped phase-boundary lines to `Indexer.run` emitted via the existing `_log` helper: `[discovery] start/end`, `[extract+chunk] start/end`, `[graph-edge-build] start/end`, `[metadata-write] start/end`, `[chroma-upsert] start/end`, `[indexing] end`. Each line prefixed with `datetime.now(timezone.utc).isoformat()` for accurate wall-clock attribution between SQLite and Chroma phases. No CLI/manifest changes. All 99 tests pass on Python 3.12. Polyglot smoke test shows phase lines correctly timestamped, enabling detailed perf analysis without filesystem mtime fallback. Branch `feature/scs-m16-phase-timestamps`, commit TBD.
- [x] (2026-06-25) **Per-batch embedding progress logging + write-through index.log.** Addresses the M17 observability gap: the chroma-upsert phase previously emitted no output between `[chroma-upsert] start` and the single end-of-loop `Upserted N vectors` line, so a 60–90 min Qwen pass was an opaque black box and a harness-killed run left no way to tell whether it died at 5% or 95%. Two changes in `Indexer.run`: (1) **write-through logging** — `_log` now opens `index.log` in append mode and flushes per line instead of buffering `log_lines` in memory and writing only at end-of-run; a run killed mid-phase now leaves a complete trail on disk (previously interrupted runs produced an *empty* `index.log` — exactly when it's most needed). (2) **Throttled per-batch progress** inside the upsert loop: every ~30s (and always on the first/last batch) emits `[chroma-upsert] progress batch B/T embedded N/M chunks (P%) rate=R chunks/s eta=Em` to both `index.log` and stdout, so a background run is observable and a time budget can be judged from the ETA. Also removed a wasted `SELECT COUNT(*) FROM vectors_present` that ran every batch (full-table count on a 58k-row table per iteration); replaced with an in-memory running total seeded once via a new `SQLiteStore.get_present_vector_count()` helper, and the per-batch `vectors_upserted` metadata write is preserved so interrupted runs still report accurate coverage to `validate`. 1 new test (`test_index_log_records_upsert_progress`); full suite 105 passing on Python 3.12 / Windows 11. Branch `feature/semantic-code-search-graph-index`.
- [x] (2026-06-25) **`backfill-vectors` resumable subcommand.** The M17 retrospective established that an interrupted `--reset` run **cannot** be completed by a plain rerun — under the M15 skip-on-unchanged fast-path the second invocation sees all files unchanged, so `all_chunks` is empty and the embedder is never fed. With per-batch progress logging now in place (above), the operator can see *where* a run died; `backfill-vectors` provides the means to *resume* from there. **Shipped**: `legacylift-search backfill-vectors --repo-root repos/<name>` (`Indexer.backfill_vectors`) drives the embed/upsert phase off a new `SQLiteStore.get_chunks_missing_vectors()` query (LEFT JOIN `chunks` against `vectors_present` on `(chunk_id, text_sha256)`, excluding NULL-text chunks) rather than the in-memory `all_chunks` list, so it processes only chunks missing from Chroma and is safe to call repeatedly. It reuses the throttled `[backfill] progress` write-through logging and the per-batch `vectors_present` + `vectors_upserted` metadata writes (seeded once via `get_present_vector_count()`), so each invocation makes monotonic forward progress under the harness wall-clock cap and a final call drives `vectors_upserted` to `chunk_count`. Validates Chroma dimension before any work and errors clearly (`No index found`) when SQLite/Chroma are absent. Returns a `BackfillStats` model rendered as a Rich table with a complete/incomplete footer. 5 new tests in `tests/test_backfill_vectors.py` (cleared-cache restore, second-call no-op, fresh-index no-op, missing-index error, CLI smoke + idempotent CLI rerun); full suite **110 passing** on Python 3.12 / Windows 11. Branch `feature/semantic-code-search-graph-index`. **Validation deferred**: completing the M17 Qwen upsert on `repos/ctcm/ctcm-api` across repeated `backfill-vectors` calls (and the Qwen-vs-hash ranking delta) still requires a host without the harness wall-clock cap; the mechanism is now in place to do it incrementally.
- [x] (2026-06-26) **Milestone 19: Parallelize cold-index extraction + batch SQLite commits (chunking C1 + C2).** (C1) the pure `read → extract → chunk` work now runs in a `ProcessPoolExecutor` — a new `extract_worker.py` with a `spawn`-safe `_init_worker(profiles_path, chunking_config_json)` that builds one `SymbolExtractor` + `CodeChunker` per worker, and an `extract_one`/`_extract_with` that returns a picklable `ExtractResult` (symbols/refs/chunks + structured `read_error`/`extract_error`/`chunk_error`/`parse_notes` fields) and never raises across the pool boundary. The main process stays the **sole SQLite writer**. (C2) `changed_files` is sorted by `relative_path` up front; `ProcessPoolExecutor.map` preserves input order, so the writer streams results in deterministic order *as workers produce them* (extraction and SQLite writing overlap inside one `ExitStack`-scoped pool) and commits in `commit_batch_files` groups via new `commit=False` params on `upsert_files/upsert_chunks/upsert_symbols/upsert_refs` + a `store.commit()` and `store.clear_reindex_artifacts()` helper. New config `index.extract_workers` (0 → `os.cpu_count()`, 1 → forced-serial in-process oracle) and `index.commit_batch_files` (default 50). Graph build, metadata, and embed/Chroma phases are untouched. 6 new tests in `tests/test_indexer_parallel.py` — the load-bearing byte-for-byte equivalence test (`extract_workers=1` vs `4` → identical chunks/symbols/refs/edges/`source_set_sha256`/vector coverage), two-run determinism, commit-batch-size invisibility, bad-file isolation, M15 skip-after-parallel, and an uninitialized-worker guard; full suite **134 passing** on Python 3.12 / Windows 11. Branch `feature/semantic-code-search-graph-index`. **Validated on `repos/ctcm/ctcm-api`** (22-core host, hash embedder, `--reset`): `[extract+chunk]` **44m 14s vs. the 63m 41s M17 baseline (~30% faster)**, identical 4,715 files / 58,677 chunks / 58,614 symbols / 135,973 refs / 141,219 edges, `Index is valid.`, `freshness: fresh`, no new tracked files. **Short of the ~6–10 min target**: with extraction parallelized, the binding constraint moved to the *single-threaded SQLite writer* — FTS5 `chunk_fts` tokenization is itself CPU-bound and is starved while 22 extraction workers saturate the cores (a non-overlapping drain-then-write prototype clocked ~45 min, i.e. overlap bought almost nothing because the writer never gets idle cores until the pool drains). See the 2026-06-26 retrospective for the writer-bound analysis and follow-up levers (FTS5 as an external-content table / deferred bulk FTS build / `PRAGMA synchronous=OFF` during cold load).
- [~] **⏸ PAUSED (2026-06-26) — reason: Embedding approach evaluation.** The corrected ~80-minute filtered idle-CPU Qwen pass is still too long to be the production embedding path; the local Qwen route is on hold pending the hosted Bedrock embedding evaluation (see Milestone 20). The structural work below stands as-is; only the local-Qwen *completion* is paused. **Milestone 17: Production Qwen3 embedding run end-to-end against `repos/ctcm/ctcm-api`.** Partial completion — Qwen path validated end-to-end (model loads from local HF cache in ~0.13s, embedder metadata `qwen3:Qwen/Qwen3-Embedding-0.6B`/dim=1024 persisted to SQLite, all extract+chunk+graph phases ran with Qwen-mode embedder configured), but the chroma-upsert phase (58,677 chunks × ~0.5–1s per Qwen forward pass on CPU) exceeds the harness per-task wall-clock budget (~10 min cap on background bash tasks). Two `--reset` runs were killed mid-embedding: run 1 killed during/after extract+chunk (60 min in); run 2 killed during chroma-upsert (60 min in, model weights loaded successfully). Final state: `vectors_upserted=0` (Chroma collection empty), all SQLite-side metadata correct, `validate` reports `Index is valid.` with `WARNING: vector coverage incomplete`. See full M17 retrospective entry dated 2026-05-19 for run logs, partial timing, and recovery path. **Recovery / completion path**: the embed-then-upsert step is checkpointable in principle (the `vectors_present` cache tracks per-chunk completion), so a future run on a host without the harness time-cap (or one that breaks the upsert into resumable chunks) will complete cleanly. Search functionality validated against the lexical-only path (Qwen embedder loads correctly when invoked from `search`).
- [x] (2026-06-25) **Embedding-cost reduction spikes (#1 low-value filter + #2 text dedup).** Two changes to cut the per-chunk forward-pass count that dominates embedding wall-clock (the M17 bottleneck), without losing recall. New side-effect-free `embed_filter.py`: (#1) `should_embed(chunk, embed_min_tokens)` skips a dense vector for chunks below the token floor **only when they carry no business logic** — `has_business_logic()` keeps any chunk with a validation/mapping attribute or annotation (`[Required]`, `[StringLength]`, `[Column]`, `[Key]`, `@NotNull`, `@Size`, `@field_validator`, EF/Hibernate/pydantic terms), branching/comparison logic, or SQL constraints. **Empirically verified the maintainer's caveat**: via `dump-ast`, C# `property_declaration` ranges *include* the decorating attribute lines (a `[Required]` property spans the attribute through the accessor), so the validation logic is in the chunk text; a 7-token `[Required]` property is embedded while a 6-token bare getter/setter is skipped — a content-driven, not size-driven, distinction. Filtered chunks stay in SQLite + FTS5 (full lexical/`symbols` recall) and are marked present in `vectors_present` so coverage stays exact (`vectors_upserted == chunk_count`) and `backfill-vectors` still terminates. (#2) `dedupe_by_text_sha()` embeds each distinct `text_sha256` once and fans the resulting vector out to every chunk sharing that text, so every chunk still gets a Chroma vector (zero recall loss) but identical boilerplate (generated equality members, repeated DTOs) is embedded once. Both apply in a shared `Indexer._embed_and_upsert` used by `run()` and `backfill_vectors()`. New manifest knob `chunking.embed_min_tokens` (default **0 = legacy behavior, filter off**; lowering it later requires `--reset`, matching the M15 precedent). 18 new tests (`test_embed_filter.py` + 2 indexer integration tests pinning exact coverage and FTS recall); full suite **128 passing** on Python 3.12 / Windows 11. Branch `feature/semantic-code-search-graph-index`. **Note on GPU**: the single biggest lever (10–50×) remains running the Qwen embedder on CUDA — already supported via `embedding.device`, gated only on host availability, no code change needed.
- [~] **⏸ PAUSED (2026-06-26) — reason: Embedding approach evaluation.** Even the corrected ~80-minute filtered idle-CPU pass is too long for routine cold indexing, so the local Qwen completion is on hold while the hosted Bedrock embedding path (Milestone 20) is evaluated. The `backfill-vectors` mechanism, cost filter, and benchmark findings all remain valid and carry over to whichever embedder wins. **Milestone 17b: Complete the Qwen3 upsert on `repos/ctcm/ctcm-api` with the cost filter enabled (`embed_min_tokens=80`).** **Re-scoped (2026-06-26): the "~7s/chunk → 20+ hours" blocker was a measurement artifact of CPU contention, not a hardware floor. Benchmarked in isolation on this host, Qwen3-Embedding-0.6B runs at ~350 ms/chunk, so the filtered 14,093-pass job is ~80 minutes on an *idle* CPU host — tractable via repeated `backfill-vectors` calls at `batch_size=32`. See the 2026-06-26 correction entry in Surprises & Discoveries (benchmark table + corrected wall-clock).** Completion paths, in priority order: (a) **idle-CPU `backfill-vectors`** at `batch_size=32` (~80 min, resumable, no new deps — runnable now on an unloaded host); (b) **GPU** (`embedding.device="cuda"`, 10–50×, single-digit minutes — biggest lever, gated on an NVIDIA box); (c) **hosted batch-embedding API** — now a live option since an upcoming project may relax the local-only constraint (see Decision Log entry 2026-06-26). The embedding-cost spikes (#1 low-value filter + #2 text dedup) were measured against the existing 58,677-chunk ctcm-api SQLite index on 2026-06-25 (no re-index; read directly from `index.sqlite` via the production `embed_filter` functions). **Result: at `embed_min_tokens=80`, the embedder sees 14,093 forward passes instead of 58,677 — a 76.0% reduction** (filter skips 70.7% of chunks; text-dedup then collapses the survivors to distinct text). The `has_business_logic` guard rescues 13,768 sub-threshold chunks that carry validation/branching/SQL-constraint signal, so recall-critical small chunks are retained. The curve flattens after 80 (`min_tokens=160` buys only 0.6% more), so **80 is the chosen threshold**. See the 2026-06-25 measurement entry in Surprises & Discoveries for the full table. **At the corrected ~350 ms/chunk idle-CPU rate, this 76% cut makes the filtered Qwen pass an ~80-minute job** (down from ~5.7 h unfiltered) — small enough to finish via repeated kill-survivable `backfill-vectors` calls. **Run this in a fresh agent context, on an idle host (do not run it concurrently with the extract+chunk phase or other CPU-heavy tasks — that contention is what produced the original 7 s/chunk figure).** Procedure:
  1. Edit `repos/ctcm/ctcm-api/semantic-search.manifest.json`: set `chunking.embed_min_tokens` to `80`. Changing this knob from its default of `0` requires a `--reset` per the M15 precedent — it will NOT be picked up by a backfill onto the current hash-embedder index.
  2. Confirm the manifest still selects Qwen (default: `embedding.provider="qwen3"`, `embedding.model="Qwen/Qwen3-Embedding-0.6B"`, `embedding.dimension=1024`). Do NOT pass `--embedding-provider hash`. **On a CPU host, set `embedding.batch_size=32`** — the default 512 is a GPU value, delays the first durable commit by ~hours, and is actively slower per chunk on CPU (one batch already saturates all cores; bigger batches just add padding). On a GPU host, leave it at 512.
  3. Run `py -3.12 -m legacylift_search.cli index --repo-root repos/ctcm/ctcm-api --reset` (consider `run_in_background=true` with periodic polling; the per-batch `[chroma-upsert] progress ...` lines now stream to `index.log`, so progress and ETA are observable mid-run). **Run on an idle host** — the original 7 s/chunk blowup was this embed phase contending with the CPU-bound extract+chunk phase; in isolation the rate is ~350 ms/chunk.
  4. If the harness still kills the run before `vectors_upserted == chunk_count`, finish it incrementally with repeated `py -3.12 -m legacylift_search.cli backfill-vectors --repo-root repos/ctcm/ctcm-api` calls (each makes monotonic forward progress and is safe to call repeatedly — it embeds only chunks missing from Chroma, off the SQLite chunks rather than the in-memory list).
  5. Confirm completion: `validate` reports no `WARNING: vector coverage incomplete` and `freshness: fresh`; `stats` shows `embedding provider qwen3:...`. Filtered chunks are marked present in `vectors_present`, so `vectors_upserted == chunk_count` even though only ~14k were actually embedded.
  6. **Then record the deferred M17 quality goal**: re-run the five M14 queries (`authentication authorization validation`, `SpecialClaimManager`, …) against the completed Qwen vectors and capture the Qwen-vs-hash ranking delta in a new Outcomes & Retrospective entry. Also record the actual wall-clock for the filtered Qwen pass vs. the 76% predicted reduction.

- [ ] **⏸ PAUSED (2026-06-26) — reason: Embedding approach evaluation.** This milestone wraps the Qwen3-Reranker; it is held with the other Qwen-related work until the embedding approach is settled (Milestone 20). The reranker is independent of the embedder in principle, but is paused alongside the rest of the Qwen stack pending that decision. **Milestone 18: Add Qwen3-Reranker as an optional second-stage reranker.** Top-5 hash-embedder scores on `repos/ctcm/ctcm-api` were 0.0154–0.0164 — essentially undifferentiated. Even with real Qwen embeddings (Milestone 17), RRF scores are small by design (`1/(k+rank)`); a cross-encoder reranker on the top-K consistently sharpens ordering for code retrieval. **Implementation**: add a `Reranker` class in a new `reranker.py` module wrapping Qwen3-Reranker via sentence-transformers' `CrossEncoder` (lazy-load, same error-handling pattern as `QwenEmbedder` — clear message recommending `search.rerank: false` if model load fails). Add `SearchConfig.rerank: bool` (default false) and `SearchConfig.rerank_top_k: int` (default 50) to the manifest. In `SearchEngine.search`, when `rerank=true`, take the top `rerank_top_k` results from the existing RRF blend, score `(query, chunk_text)` pairs with the cross-encoder, and re-sort the limited final result set by reranker score (preserving the original RRF-blended score in the result for transparency). Add `--rerank/--no-rerank` CLI flag on `search` for ad-hoc override. Tests: a `FakeReranker` that returns deterministic scores covering the SearchEngine integration + ordering, a config-roundtrip test, and an end-to-end CLI test on the polyglot fixture using the fake reranker (real Qwen3-Reranker is gated behind the live model and only smoke-tested manually). **Validation**: rerun the M17 ctcm-api top-5 queries with `--rerank` and record the reordering in the retrospective. Document any wall-clock cost per query (typical cross-encoder reranking on K=50 should be sub-second on CPU but worth measuring).

- [x] **Milestone 19: Parallelize cold-index extraction and batch SQLite commits (chunking C1 + C2).** The `[extract+chunk]` phase is the longest part of a cold index (~63 min on `repos/ctcm/ctcm-api`, M17 baseline) and is a serial per-file loop with ~4–5 self-committing SQLite transactions per file. Once embedding is fast (GPU per M17b, or hosted per the pending hosted-data-store plan), this phase is the long pole regardless of where vectors are stored. **Implementation**: (C1) move the pure `read → extract → chunk` work into a `ProcessPoolExecutor` (process-isolated because the work is CPU-bound under the GIL; `spawn`-safe `initializer` builds one `SymbolExtractor` + `CodeChunker` per worker from the picklable `profiles_path` + `manifest.chunking`), keeping the main process as the sole SQLite writer; workers return a picklable `ExtractResult` (symbols/refs/chunks + structured read/extract/chunk error fields) and never raise across the pool boundary. (C2) the writer persists results in a **deterministic order** (sorted by `relative_path`, not arrival order) and wraps each `commit_batch_files` group in a single transaction instead of committing per upsert. New config `index.extract_workers` (0 → `os.cpu_count()`, 1 → forced-serial fallback/oracle) and `index.commit_batch_files` (default 50). Everything after the extract loop (graph build, metadata, embed/Chroma upsert) is untouched. **Tests** (`tests/test_indexer_parallel.py`): the load-bearing equivalence test (`extract_workers=1` vs `4` produce byte-identical SQLite contents — chunk ids/ordering, symbol/ref/edge counts, `source_set_sha256` — and identical Chroma counts); determinism across two parallel runs; bad-file isolation; commit-batch-size invisibility; and M15 skip-on-unchanged interaction. **Validation**: cold `index --reset --embedding-provider hash` on `repos/ctcm/ctcm-api` (hash isolates the extract phase from embedding cost); record `[extract+chunk]` wall-clock against the 63m 41s baseline (target ~6–10 min) and confirm identical file/chunk/symbol/ref/edge counts, `Index is valid.`, `freshness: fresh`, and no new tracked files under the index dir.

- [x] (2026-06-26) **Milestone 20: Add a hosted Amazon Bedrock embedding provider (`provider="api"`).** **Shipped.** New `BedrockEmbedder` (`embeddings.py`) implements the `Embedder` protocol over `bedrock-runtime` `InvokeModel`; `create_embedder` gained a `provider="api"` branch (with a Titan fallback when `model` is still the Qwen default). New `EmbeddingConfig` fields `region` (default `us-east-2`, **not** inherited from `AWS_REGION`) and `max_concurrency` (default 16). Credentials are read from `AWS_BEARER_TOKEN_BEDROCK` by botocore — never stored in the manifest; a clear `RuntimeError` names that var when absent and recommends the `hash`/`qwen3` fallback (same pattern for import/invoke/auth/throttle failures). The `name` string `api:bedrock:<model>` is persisted to `index_metadata.embedder_name`; dimension-consistency and `--reset` rules are unchanged, and `vectors_present`/`backfill-vectors` resumability carry over. **Throughput**: Titan embeds one text per request, so `embed_documents` issues `max_concurrency` concurrent `InvokeModel` calls via a `ThreadPoolExecutor` (boto3 client is thread-safe; pool sized to match, adaptive retries); live timing on this host showed **~94 ms/chunk at concurrency=16** vs. 317 ms sequential (concurrency=32 hit throttling and was slower). 14 new tests in `tests/test_bedrock_embedder.py` (config round-trip, dispatch incl. Titan fallback + unknown-provider listing `api`, `FakeBedrockClient` batching/ordering/determinism, missing-token / invoke-failure / missing-embedding-field error paths, and a full indexer run on the polyglot fixture with the fake client patched in). No live AWS call in the unit suite. Added `boto3>=1.40` as the `aws` optional-dependency extra. **Verified live (2026-06-26)** against real Bedrock in `us-east-2` via the env-var token: single `embed_query` returns a normalized 1024-dim vector; a cold `index --reset` of the polyglot fixture with `provider="api"` embedded all 25 chunks (`vectors_upserted == chunk_count`, `embedder_name=api:bedrock:amazon.titan-embed-text-v2:0`), and a vector `search` returned ranked results through the same provider's query embedding.

  **Oversized-input fix (2026-06-26, found during Part 1 validation):** the first real at-scale run revealed `BedrockEmbedder` was sending chunk text to Titan with no length guard. Titan v2 enforces **both** a 50,000-byte and an 8,192-token cap; a single 50,974-byte chunk (`ClaimDtoFactory.cs:11-1010`) raised a `ValidationException` that aborted the embed phase, and `backfill-vectors` retried the same chunk forever (never converging). Fixed in `_invoke`: pre-truncate to the byte cap on a UTF-8 boundary, then **retry with halved input on any residual length error** (the token cap is content-density-dependent, so a fixed byte cap can't guarantee it). Full text stays in SQLite/FTS5 for lexical recall — only the dense vector is computed from a bounded prefix, like local embedders truncating at `max_seq_length`. 6 new tests cover truncation, UTF-8 boundary safety, the halving-retry, and the persistent-rejection backstop; full suite **154 passing**. See Surprises & Discoveries.

  **✅ Part 1 (embed-phase benchmark) COMPLETE (2026-06-26):** with the fix in place, `backfill-vectors` drove the `repos/ctcm/ctcm-api` index to full coverage. With `embed_min_tokens=80`, **17,212 chunks were dense-embedded** (the other 41,465 marked-present via FTS5 per the filter) — the final backfill call embedded the last 13,069 distinct chunks (26 batches of 512) in **170 s (~2.84 min)** at **~13 ms/chunk effective @ concurrency=16**, i.e. **~25–30× faster than the local-Qwen ~80-min estimate**. `validate` → `Index is valid.` / `freshness: fresh` / no coverage warning; `stats` → `api:bedrock:amazon.titan-embed-text-v2:0` dim 1024, counts unchanged (4715/58677/58614/135973/141219); `vectors_upserted == chunk_count == 58677`; live Chroma holds exactly 17,212 vectors (reconciles: 58,677 − 41,465 filtered). No throttling, clean single pass; `git status` clean under the index dir. See the Part-1 retrospective entry. **Deferred (Part 2)**: the hash-vs-Bedrock retrieval-quality A/B on the pinned five queries — see the runbook section. Branch `feature/semantic-code-search-graph-index`.

  **Original specification (for reference):** Add a hosted Amazon Bedrock embedding provider (`provider="api"`). **This is the chosen production embedding path** — the local Qwen route (M17/M17b) is paused because even the filtered ~80-minute idle-CPU pass is too long for routine cold indexing. A hosted embedding API removes per-host compute entirely: the 14,093 filtered ctcm-api chunks embed in a few minutes over the network, with no GPU box and no idle-host requirement. **Code egress to AWS is approved for this embedding use case** (see Decision Log entry 2026-06-26), so this is no longer gated on a data-handling sign-off; the local `qwen3`/`hash` providers remain first-class fallbacks for engagements where egress is *not* approved.

  **AWS environment (confirmed 2026-06-26):**
  - **Region: `us-east-2`.** (Note: `.claude/settings.json` sets `AWS_REGION=us-east-1` for Claude Code's own model access — M20 must use `us-east-2` explicitly via `embedding.region`, not inherit that env value.)
  - **Auth: `AWS_BEARER_TOKEN_BEDROCK`** — already present in `.claude/settings.local.json` (the same Bedrock instance used for Claude Code direct model access). This is the Bedrock **API-key / bearer-token** mechanism, NOT SigV4 — the AWS SDK (botocore ≥ 1.39 / boto3) reads this env var automatically and uses it for `bedrock-runtime` calls, so no profile, access key, or role is needed. The embedder should rely on this env var being set (do not read or store the token in the manifest); fail with a clear message naming `AWS_BEARER_TOKEN_BEDROCK` if it is absent.
  - **Model access: auto-provisioned.** Per-model opt-in is no longer required in this account — `bedrock:InvokeModel` works without a prior "request model access" step, so there is no console action to take before the validation run.
  - **✅ Verified live (2026-06-26):** a smoke `InvokeModel` against `amazon.titan-embed-text-v2:0` in `us-east-2`, authenticating solely via the `AWS_BEARER_TOKEN_BEDROCK` env var loaded from `.claude/settings.local.json` (boto3 1.40.12), returned a normalized **1024-dim** embedding with no `AccessDenied`/opt-in error. This confirms all four assumptions above (token auth, region reachability, auto-provisioned model access, 1024-dim matching the existing Chroma collection). The implementation embedder need only reproduce that call (`bedrock-runtime` `invoke_model`, body `{"inputText":..., "dimensions":1024, "normalize":true}`).

  **Implementation**: add a new `provider="api"` branch to `create_embedder` (the existing dispatch already keys on `embedding.provider`, so this is the entire integration surface). New `EmbeddingConfig` fields: `region` (default `us-east-2`) and `model` (e.g. `amazon.titan-embed-text-v2:0` or a Cohere Embed v4 model id); credentials come from the `AWS_BEARER_TOKEN_BEDROCK` env var via the SDK — do NOT add a key/token field to the manifest. The provider calls `bedrock-runtime` `InvokeModel` (boto3). The provider must implement the existing `Embedder` protocol (`dimension`, `name`, `embed_documents`, `embed_query`) — note the **same provider must also serve query-time embedding** (one call per `search`), since index and query vectors must share a model. Batch `embed_documents` calls to the Bedrock per-request limit. The `name` string (e.g. `api:bedrock:amazon.titan-embed-text-v2:0`) is persisted to `index_metadata.embedder_name`, and `dimension` must match the Chroma collection — switching providers requires `--reset` per the existing dimension-consistency rule. The `vectors_present` checkpointing and `backfill-vectors` resumability carry over unchanged (network failures mid-run are resumable exactly like the CPU path). Clear error on missing-`AWS_BEARER_TOKEN_BEDROCK`/auth/throttle failures recommending the `qwen3`/`hash` fallback. **Tests**: a `FakeBedrockClient` returning deterministic fixed-dimension vectors covering `embed_documents` batching + `embed_query` + the `create_embedder` dispatch + error-path messaging; a config-roundtrip test for the new `EmbeddingConfig` fields; an end-to-end indexer test on the polyglot fixture using the fake client (real Bedrock is gated behind the live env token and only smoke-tested manually). No live AWS call in the unit suite. **Validation**: with `AWS_BEARER_TOKEN_BEDROCK` set and `region=us-east-2`, cold `index --reset` on `repos/ctcm/ctcm-api`; record the embed-phase wall-clock vs. the local-Qwen ~80-minute estimate, confirm `vectors_upserted == chunk_count`, `Index is valid.`, `freshness: fresh`, and `stats` shows the `api:bedrock:...` provider. **Then run the deferred M17 quality A/B**: re-run the five M14 queries against the Bedrock vectors and capture the ranking delta vs. hash (and vs. Qwen if ever completed) in a new Outcomes & Retrospective entry — Titan/Cohere are general-purpose, not code-specialized, so gate adoption-for-quality (not just speed) on this comparison.

- [ ] **Milestone 21: Does semantic code search + the code graph beat `fact-graph`? — value comparison against the incumbent.** **This now precedes M20 Part 2.** The whole tool only earns its place if it helps the LegacyLift workflow *more than the existing `fact-graph` skill does* (`.claude/skills/fact-graph/`), which already produces a structured JSON knowledge graph (entities/relations/facts with evidence) that the documentation skills consume. Until that is established, tuning the embedder's ranking (M20 Part 2) is premature. **Strong prior:** the index almost certainly helps — `fact-graph` is deterministic grep/AST extraction with no semantic retrieval, no embedding-based "find code like this," and no ranked cross-file relevance — but "almost certainly" is not evidence, so measure it. **What to compare** (both already exist on `repos/ctcm/ctcm-api`: the Bedrock-embedded `code-search` index from M20 Part 1, and a `fact-graph` run): (1) **Retrieval/lookup** — for a fixed task set (e.g. "where is provider eligibility validated?", "what calls `SpecialClaimManager.CreateReserveTask`?", "find the appeal-case repository"), can each approach surface the right code, and how directly? `fact-graph` answers via entity/relation/fact JSON lookups + its `callers`/`callees`-style relations; the index answers via hybrid `search` + graph `callers`/`callees`. (2) **Coverage** — what does each *miss*? (semantic search finds conceptually-related code with no name match; `fact-graph` finds explicitly-extracted facts with evidence/confidence the index lacks). (3) **Cost/freshness** — `fact-graph` is an LLM-driven multi-phase run vs. the index's deterministic cold-build + cheap incremental reindex (M15). (4) **Consumability** — `fact-graph`'s JSON packs are built to be loaded by other skills; the index is a query-time CLI. **Define the evaluation first**: pick the task set and a simple scoring rubric (hit\@k / "did it answer" / analyst-judged usefulness) *before* running, so the result is auditable, not post-hoc. **Likely outcome & framing**: they are probably **complementary, not either/or** — `fact-graph` for exhaustive evidence-backed facts feeding doc generation, the index for ad-hoc semantic/graph exploration during analysis. If so, the deliverable is a recommendation on *how the two compose* (e.g. index as an interactive front-end over the same repo `fact-graph` documents), not a winner. **Deliverable**: an Outcomes & Retrospective entry recording the task set, the rubric, per-task results for both approaches, and a go/no-go-or-compose recommendation. **Gate**: M20 Part 2 (embedder-quality A/B) resumes only if this milestone concludes the index adds value worth tuning.

  > **▸ 2026-08-25 — MEASURED INPUT FOR M21. The task set above is now partly obsolete; read this before defining the evaluation.** Produced while closing question **D7** of `docs/exec-plans/pending/reqs-to-data-store-plan-draft.md` by **counting the only `fact-graph` output tracked in git** — the 58 files / 30 MB under `repos/ctcm/ctcm-api/legacylift-docs/context/` (6,047 entities / 3,928 relations / 38,618 facts, run of 2026-06-29). Full tables in [`fact-graph-decision.md` §5a.5](../pending/fact-graph-decision.md) and [`fact-graph-explanation.md` §9](../pending/fact-graph-explanation.md). **Every prior comparison — including §5a — scored `fact-graph` against its *schema* and its `SKILL.md`; this is the first count of what it actually emitted.**
  >
  > **What this does to M21's four comparison axes:**
  >
  > 1. **Axis (2) "Coverage — what does each miss?" has largely collapsed as a differentiator.** `fact-graph` emitted **5 predicates, not the ~45 its §4.1 advertises**: `has_property` 34,488 (89.3%), `is_required` 1,268, `accepts_param` 1,223, `http_method` 1,019, and **`business_rule` 620 (1.6%)**. Layer 0 already owns the first four (symbols; M23; M25; M23). **98.4% of the facts layer is Layer-0's.** The parenthetical in axis (2) — "`fact-graph` finds explicitly-extracted facts with evidence/confidence the index lacks" — is now false for all but 1.6% of its output, and `symbol_facts` carries evidence and confidence too.
  > 2. **The ~18 interpretive predicates emitted ZERO facts.** `validates`, `ensures`, `integrates_with`, `authenticates_via`, `authorizes_via`, `publishes_to`, `subscribes_to`, `stores_in`, `reads_from`, `writes_to`, `caches_in`, `logs_to`, `default_value`, `triggers_on`, `timeout_after`, `state_transition`, `process_step`, `has_cardinality`, `returns_response` — **0 each.** Do **not** build M21 tasks around them; there is nothing to retrieve.
  > 3. **The 620 `business_rule` facts are shallow.** Sampled `fact-449e22ed2ba7`: `object = "ObjectNotFoundException: transaction associated user"`, `confidence = 0.8`, evidence a bare `throw new ObjectNotFoundException(...)` at `TransactionPartyManager.cs:727`. A throw statement, not a business rule. If M21 keeps a business-rule task, the honest comparator is **`code-mod extract-rules`** (adversarially-verified Rule Cards) or the GR store — not `fact-graph`.
  > 4. **Axis (4) "Consumability" is the ONE axis where `fact-graph` still wins outright, and it is pure packaging.** Layer 0 has **no pack emitter**: none of its 15 CLI commands writes `legacylift-docs/context/`, so all 13 Phase-0 consumer skills still resolve their fast path to `fact-graph`. Layer 0 holds every *field* the packs carry — this is a format gap, not a data gap.
  > 5. **`fact-graph` also still wins on semantic entity typing** — measured at **8 types over 6,047 entities** (`dto` 2,352 · `class` 1,594 · `endpoint` 753 · `interface` 444 · `service` 317 · `enum` 308 · `controller` 173 · `repository` 106). `symbols.kind` is the raw tree-sitter node type and **no mapping layer exists in the package**, so `find_entities_by_type('controller')` has no Layer-0 answer. Add this to M21's task set — it is a real, currently-failing query.
  > 6. **Relations: 4 types emitted** (`inherits` 1,826 · `contains` 1,002 · `implements` 884 · `routes_to` 216). Layer 0 owns `inherits`/`implements` (M22) and `routes_to` (M23). **Only `contains` (1,002) has no Layer-0 edge equivalent** — containment lives in `qualified_name` + the container stack.
  > 7. **Identity: drop it from M21's differentiator list — it is a non-differentiator in BOTH directions.** `fact-graph` **does** carry both hash grains: `attributes.content_hash` on **6,047/6,047** (12 hex, 5,888 distinct — the 159 repeats are clones, since a real 48-bit collision at this scale is ~7x10⁻⁸ likely) and `evidence.snippet_hash` on **38,618/38,618**. So `fact-graph-decision.md` §5a.1 item 3 ("still true — and Layer 0 is actively worse") **stands**. Layer 0 closes the gap when `NORMATIVE SPEC-3` §S3.1/§S3.2 lands (`anchor_key` as a computed column on `symbols`), and SPEC-3's keys are better *constructed* — `` delimiter instead of `:` (which occurs inside both `qualified_name` and `file_path`), a coarse `entity_class` instead of the volatile raw `entity_type`, 16 hex instead of 12, and `domain` excluded from the key rather than sitting in the visible id prefix (`:912`) — but that is construction quality, not capability. ⚠️ *An earlier draft of this block wrongly reported `content_hash` missing; it reads `attributes.content_hash`, not a top-level field.*
  > 8. **Cost/freshness (axis 3) is unchanged and still favors the index.** Add one operational caveat in `fact-graph`'s favor that no prior comparison credited: **zero install** — it is a skill, so no venv, tree-sitter, Chroma or boto3, and no ~100-minute cold index. That matters on a locked-down client box.
  > 9. ⚠️ **But "language-agnostic" is NOT a `fact-graph` advantage** (owner correction 2026-08-25, then verified). Its extraction logic is **hardcoded per-language `grep` blocks inside `SKILL.md`** — §2.2 "Extraction Techniques by Language" (`:653-775`) has one bash block each for C# (`:656-671`), Java (`:680-693`), Python (`:701-714`), TS/JS (`:719-731`) and SQL, all literal regexes for that language's syntax and framework idioms. The *Other Languages (Go, Rust, Ruby, PHP, etc.)* escape hatch (`:769-772`) is **one sentence with no patterns**. Mention counts: Java 52, Python 37, SQL 26, C# 15, TS 8, JS 5 — **VB6, Delphi, ABAP, PL/SQL, COBOL: 0 each.** Adding a language costs Layer 0 a grammar + extractor profile and costs `fact-graph` a hand-authored grep block: cheaper and toolchain-free, but **editing the skill, not running it.**
  >
  > **⚠️ Consequence for THIS PLAN, not just for M21.** `fact-graph-decision.md` §5a.4 reduces a refactored `fact-graph` to four residue pieces. **Two are now closed or homed:** **(c)** content-hashed position-independent entity IDs → `NORMATIVE SPEC-3` in the GR-store plan; **(d)** LLM-inferred facts → the GR store (its **Q7**, scoped to *adding* the Layer-1 store, not retiring `fact-graph`). **The two that remain — (a) the pack-emitter shim and (b) the semantic-typing pass — are deterministic, well-scoped Layer-0 work that is a milestone on NO plan, including this one** (this plan has M17, M18, M20, M21, M22, M23–25, M26, M27). **So this plan, which is generally described as the one that retires `fact-graph`, does not contain the work required to retire it.** Until (a) and (b) are filed as milestones the way M26/M27 were, "retire fact-graph" is not an executable statement — and M21 cannot conclude "replace" no matter how the tasks score, because the 13 Phase-0 consumers would have nothing to read. **⚠️ And a THIRD unowned piece was identified 2026-08-25 — (e): re-key `symbols.id` so the PK is not line-bearing.** `NORMATIVE SPEC-3` §S3.1 adds `anchor_key` as a **computed column beside** the primary key; it does **not** re-key `symbols`. `symbols.id` is still `f"{language}:{relative_path}:{qualified}:{start_line}"` (`extractors.py:1112-1115`), and five surfaces key off it: `symbols.id` PK (`store.py:209`), `graph_edges.caller_symbol_id`/`callee_symbol_id` FKs (`:309`/`:310`, CASCADE / SET NULL), `symbol_facts.subject_symbol_id` (`:359`, NOT NULL CASCADE), plus plain columns `chunks.symbol_id` (`:216`) and `symbol_refs.enclosing_symbol_id` (`:278`). **So an edit above a symbol still mints a new id and cascades its edges and facts away** — harmless while all 12 predicates are deterministic and regenerated, not harmless once anything durable hangs off a symbol row. (`chunks.id` is separately unstable: `chunking.py:143`/`:222`/`:295`.) This **corrects `fact-graph-decision.md` §7 open question #6**, which was recorded as "answered — fix it in Layer 0" when only half of it was. **It is now implementable for the first time**, because the GR plan's **D3 Milestone 0** builds `PRAGMA user_version` + forward-only migrations for both DBs — before that there was no `ALTER TABLE` in `src/` at all. Scope if filed: re-key the PK, migrate two FK constraints and three plain columns, and **verify through a real edit-and-reindex cycle** — mandatory, because SPEC-3 §S3.7 records that this identity design has **never** been exercised that way by either tool. **None of (a), (b) or (e) gates GR-store Milestone 1**, which is why deferring the filing costs nothing.
  >
  > **Filing (a), (b) and (e) is an open action, not yet ratified — but the information needed to file them is now written down and needs no re-derivation:** [`fact-graph-explanation.md` §9.7](../pending/fact-graph-explanation.md) is the **measured field-level pack contract** (every `index.json` key, all four pack record shapes with per-field counts, and the Layer-0 source for each field), and **§9.8** is the **eight `type` values with the shipped M22–M25 signal available to derive each** — two already in `symbols.kind`, four derivable from existing facts/edges, one default, and only `service` needing a heuristic. **All three pieces are consolidated in [`fact-graph-decision.md` §5a.6](../pending/fact-graph-decision.md), with (e)'s surface-by-surface scope in §5a.6.1.**
  >
  > **Net effect on M21's framing.** Its stated "likely outcome" — *complementary, not either/or* — survives, but the reason changes. It is **not** that `fact-graph` holds an exhaustive evidence-backed facts layer the index lacks (measured: 1.6%, shallow). It is that `fact-graph` holds **a delivery format and a semantic type vocabulary that Layer 0 has not built yet**, plus a zero-install execution mode. Score M21 on those, and treat the facts layer, identity, inheritance, routes, columns and domains as **settled non-differentiators**.

- [x] (2026-07-15) **Milestone 22: Add type-hierarchy (`inherits` / `implements`) edges to the graph.** **Shipped.** All four layers landed as specified (Steps 1–4) with 12 new tests; full suite **196 passing** on Python 3.12 / Windows 11. (Step 1) `ProfileEntry.inheritance_node_kinds` + `FallbackPatterns.inheritance` fields (both default `[]`, **no** `schema_version` bump) and per-language `inheritance_node_kinds` in `extractors.json` (csharp `base_list`; java `superclass`/`super_interfaces`/`extends_interfaces`; ts `class_heritage`/`extends_type_clause`; js `class_heritage`; python `argument_list`; cobol/sql `[]`), plus fallback `inheritance` regexes (Java keyword captured as a group; a keyword-boundary lookahead added during impl so a two-clause `extends X implements Y` splits correctly — the plan's bare `[\w.,<>\s]+` greedily swallowed the second keyword). (Step 2) module-level `_base_type_name` unwrapper (identifier/type_identifier direct; `generic_name`/`generic_type` → inner name; `qualified_name`/`attribute`/`scoped_*` → last segment; C# `primary_constructor_base_type` → recursive descent; everything else, incl. `predefined_type`, → `""`), and `_extract_inheritance_refs` fired from the definition-node branch of `_walk_tree` (Python anchored on `class_definition.child_by_field_name("superclasses")`, never a bare `argument_list` match), emitting `extends`/`implements`/`inherits_or_implements` refs; plus the third split-emit loop in `_extract_fallback`. (Step 3) `_resolve_callee` widened to `(id, confidence, callee_kind)` and `_edge_kind_from_ref` widened to accept `callee_kind`; C# `inherits_or_implements` reclassifies via **exact `==`** (not substring `in`) — resolved `interface_declaration` → `implements`, other resolved kinds → `inherits`, unresolved (`callee_kind is None`) → `^I[A-Z]` heuristic; `extends` → `inherits`, `implements` → `implements`; `import re` added. (Step 4) 4 hierarchy fixtures under `tests/fixtures/polyglot_repo/hierarchy/` (C#/Java/Python/TS, incl. generic + qualified + positional-record + enum-underlying-type C# bases); extractor + graph tests incl. the enum-`byte` regression guard, the `implements`-substring-hazard guard, and the fallback split-emit test; `test_discovery.py` file-count updated 7→11. An independent code-review subagent verified all five plan-flagged risk areas with no defects. **Step 5 validated on `repos/ctcm/ctcm-api`:** before = 141,219 edges with **zero** hierarchy edges (`references` + `calls` only); after = **2,750 hierarchy edges (`inherits` 2,112 + `implements` 638)**, matching the 2,750 extracted inheritance refs and the same order of magnitude as the v3 fact-graph baseline (1,826 + 884 ≈ 2,710 — total is the meaningful cross-check per the plan; the more-inherits split is expected since most unresolved C# bases fall to `inherits`). Unresolved-base ratio 358/2,750 = **13.0%** (confidence 0.30). Chunk/symbol counts unchanged (58,677 / 58,614); refs 135,973 → 138,723 (+2,750). A decisive stash-and-rebuild A/B confirmed **zero regression**: pre-M22 code on the identical SQLite yields `calls` = 37,514 (identical to M22) and folds the 2,750 inheritance refs into generic `references` (95,428), which M22 correctly splits out. Branch `feature/milestone-22`. **Implementation note:** re-index used the M15 partial-graph-rebuild path, not `--reset` — the plan's `--reset` requirement holds for a *cold* profile change, but here the `--reset` extraction (which completed: all files/chunks/symbols/refs incl. the new inheritance refs written to SQLite) was killed at the instant graph-build started, so a plain `index` rerun rebuilt `graph_edges` over the union of stored refs (fast, ~min) and produced the hierarchy edges without repeating the ~100-min extraction; Bedrock vectors (wiped by the `--reset`) restored via `backfill-vectors`. The graph is call/reference/import/data-access only through M20 — it does **not** capture inheritance or interface implementation. A class/interface *declaration* is a `symbol`, but its base type is neither a symbol attribute nor a `symbol_ref` (the inheritance clause node is in no extractor profile), so `GraphBuilder` can never emit an `inherits`/`implements` edge; inheritance survives only as raw chunk text an agent must re-parse. This gap matters because the v3 fact-graph relations the doc skills consume are ~74% inheritance on `ctcm-api` (`inherits` 1,826 + `implements` 884), so it is a prerequisite for the fact-graph Option-A refactor (`docs/exec-plans/pending/fact-graph-decision.md`). Change spans four layers — extractor profiles (`inheritance_node_kinds`; add the new key to `ProfileEntry` with a `[]` default but do **not** bump `schema_version`), `SymbolExtractor` (emit base-type refs, unwrapping C# `generic_name`/`qualified_name` bases, not just bare identifiers), `GraphBuilder` (map to `inherits`/`implements`; reclassify C# `base_list` from the resolved target's kind — requires widening `_resolve_callee` to return the callee kind, which it currently discards; keep unresolved external base types at confidence 0.30), and tests. **Re-index requires `--reset`** — a plain reindex skips unchanged files (M15) and emits zero new edges since a profile edit changes no file SHA. See the Milestone 22 build steps under Concrete Steps (corrected 2026-07-13 per code review of Steps 1–5; further corrected 2026-07-15 — `^I[A-Z]` interface heuristic promoted from optional to required for unresolved C# bases, `primary_constructor_base_type` added to the Step 2 unwrap whitelist for positional records, Java fallback keyword made a capturing group, Step 5 sanity-check re-based on combined hierarchy-edge count rather than the per-kind split, and an enum-underlying-type regression test added). Identified 2026-07-13 while scoping fact-graph Option A.

- [x] (2026-07-17) **Milestones 23–25: Extract the remaining high-value first-class AST nodes. — IMPLEMENTED + CI-VALIDATED; at-scale ctcm validation deferred.** Landed in four commits on `feature/milestone-23-25`: **shared plumbing prerequisite** (`59d7d770` — `SymbolFact` model, `symbol_facts` table + FK cascades on `repo_files`/`symbols`, `facts` threaded `ExtractedFile`→`ExtractResult`→M19 batched writer, `upsert_facts` mirroring `upsert_refs` with a per-INSERT `try/except sqlite3.IntegrityError` orphan crash-guard, `DELETE FROM symbol_facts` in `clear_reindex_artifacts`, `fact_count` in both `IndexStats` models + both render sites, new `facts --predicate/--symbol` CLI command; 10 tests); **M23 annotations/attributes/decorators** (`3114dbb7` — `_walk_tree` widened to return `(symbols, refs, facts)`; annotation handler at the def-node branch inspecting `node.parent`/`decorated_definition` for Python and preceding siblings for TS; `annotation_semantics` profile map; facts `http_method`/`exposes_endpoint`/`requires_auth`/`is_required`/`max_length`/`is_column`/`is_id`/`table_name`/`has_annotation`; `@JoinColumn`/`@ManyToOne`→`foreign_key`/`associates` edges; the two deferred cascade-cleanup tests + 4-language CI tests); **M24 SQL columns/constraints/FKs** (`6b9ac4b3` — dump-ast-verified SQL was on the regex path; corrected `definition_node_kinds` to `create_table`/`create_view`/`create_function`/`create_procedure` [option a; `create_trigger`/`create_index` mis-parse to `ERROR`, left on regex]; `has_column` facts with type/nullability/PK attributes; `foreign_key` edges via the regex FK supplement since tree-sitter mis-parses the FK clause; table-name recoverability confirmed; no `fallback_definition` test churn found; fixture CI tests on `schema.sql`); **M25 field/property type refs + method signatures** (`23894237` — new `_inner_type_name` inner-generic-unwrap helper distinct from `_base_type_name`; per-language primitive skip-sets applied before resolution; `has_field_of_type`/`accepts_dto`/`returns_dto` edges + `throws`/`has_enum_value` facts; edge-id widened with `ref.id` to fix the same-type-refs-on-one-line collision, M22/M23/M24 graph counts unchanged; `--edge-kind`/`--kind` repeatable filter on `callers`/`callees` threaded into `SQLiteStore.callers`/`callees` after `depth` **and** the `callers` CLI inline fallback SELECT). Integrated smoke on the polyglot fixture (`index --reset --embedding-provider hash`): 15 files → 84 chunks/symbols, **fact_count=38** across all M23–25 predicates (`http_method` 8, `exposes_endpoint` 8, `has_column` 6, `requires_auth` 3, `has_enum_value`/`is_column`/`is_id`/`is_required`/`table_name`/`has_annotation` 2 each, `max_length` 1) and new edge kinds (`accepts_dto` 5, `returns_dto` 2, `foreign_key` 2, `has_field_of_type`/`associates` 1); `--edge-kind calls` correctly excludes `accepts_dto` edges from `callees`. **Deferred to an unconstrained host (harness ~10-min bash wall-clock cap, per M17/M20 precedent):** the at-scale `index --reset` + `backfill-vectors` on `repos/ctcm/ctcm-api` (M23 predicate counts + M25 ref/edge/fact deltas + graph-build peak-RSS via `tracemalloc` + primitive-filter edge-count delta — one combined rebuild per the plan's combined-rebuild note) and on `repos/ctcm/ctcm-db` (M24 `has_column`/`foreign_key` at scale). Full CI suite green except the pre-existing `test_bedrock_embedder.py::test_indexer_end_to_end_with_fake_bedrock` (`botocore` not installed — optional `aws` extra, unrelated). Original spec below retained for the deferred at-scale runbook. A `dump-ast` sweep (2026-07-13, C#/Java/Python/TS/SQL) confirmed several first-class nodes the profiles ignore, each feeding a LegacyLift skill. **M23 — annotations/attributes/decorators** (verified: C# `attribute_list→attribute`, Java `marker_annotation`/`annotation`, Python `decorator`, TS `decorator→call_expression`): routes/HTTP verbs, authz, validation, JPA/EF mapping — the biggest gap, legacylift-search has zero annotation awareness today. **M24 — SQL columns/constraints/FKs** (verified: `column_definition`, `constraints→constraint`; FK clause mis-parses to `ERROR` → regex supplement required): data model + FK graph for the data/table skills. **M25 — field/property type refs + method signatures** (verified typed params/returns + `type_argument_list` generic unwrap + Java `throws` + `enum_member_declaration`): association graph, typed API surface, DTO-usage edges. **Shared prerequisite to land first (blocking):** attribute-facts (`http_method`, `is_required`, …) have no target symbol so they don't fit `graph_edges` — add a fact-graph-shaped `symbol_facts` table (this is where Layer 0 starts absorbing fact-graph's facts layer; see `fact-graph-decision.md` §5). Critically, facts are a **new data type with no channel through the pipeline**: since M19, extraction runs in a `ProcessPoolExecutor` and only `ExtractResult` (symbols/refs/chunks) crosses the process boundary, so facts must be threaded through `ExtractedFile` → `ExtractResult` → the M19 batched writer, with `symbol_facts` FK-cascaded on both `repo_files` and `symbols` for M15 incremental correctness. Relational items (type refs, FK) instead ride M22's existing ref→edge plumbing. **Every one of M23–25 requires `index --reset`** (a profile/extractor change alters no file SHA, so M15 skips everything; M22's graph-only rebuild shortcut does not apply because the new facts/refs aren't stored until re-extraction). "Facts as Chroma metadata" is de-scoped to a future optional enhancement. See the corrected M23–25 build steps under Concrete Steps (corrected 2026-07-16 per code review — second pass same day fixed: fact `id` now includes `object` so single-line multi-valued predicates like `throws A, B` / single-line enums don't collapse; `subject_symbol_id` made `NOT NULL` and the changed-file fact-cleanup mechanism re-attributed to the `upsert_files` REPLACE→`file_id` cascade rather than `clear_reindex_artifacts`; the write-ordering invariant relative to `upsert_files`/`upsert_symbols` made explicit; `_edge_kind_from_ref`'s silent `references` default called out with a per-`edge_kind` assertion requirement; the M25 edge-id collision fix (`ref.id` disambiguation); the two `IndexStats` classes + `stats` CLI rendering all flagged; SQL option (a) preferred for symbol-id consistency; and the `--reset` re-embed cost documented as an accepted trade-off). Further corrected 2026-07-16 (third pass, code-review verification against source): a writer-side crash-guard added so a dangling `subject_symbol_id` (NOT NULL FK, IMMEDIATE) is dropped-and-logged instead of aborting the run; `subject_symbol_id` mandated to reuse the symbol's exact `.id` verbatim; fact cleanup hardened with an explicit `DELETE FROM symbol_facts` in `clear_reindex_artifacts` (the `INSERT OR REPLACE` cascade empirically confirmed to fire, now belt-and-suspendered); the `fact_count` render sites corrected from three to four (both `IndexStats` models + the `index` run-summary render at `cli.py:117` AND the `stats` render at `cli.py:680`); M24 required to dump-ast-verify each SQL node name individually and to flag SQL symbol-id churn for downstream skills; M23 annotation coverage documented as tree-sitter-path-only; and fact ids noted as opaque (free-text `object` with `:`/`/` is safe). Further corrected 2026-07-16 (fourth pass, source-verified review): (1) **new** — `callers`/`callees` traversal has no `edge_kind` filter (`SQLiteStore.callers` at `store.py:739`, `callees` at `store.py:777` — no `get_` prefix, both `(symbol_id, depth)`), so M22's and M25's non-call edge kinds flood the call graph; M25 must add an optional `--edge-kind` filter threaded into `SQLiteStore.callers`/`callees` (after `depth`) **and** into the `callers` CLI command's inline fallback SELECT at `cli.py:564–591`; (2) the M23 annotation handler re-anchored from `extractors.py:409` (only the branch's `ExtractedFile` return) to the definition-node visit at `extractors.py:473–509`; (3) M24 now **requires** fixture-based CI tests on `polyglot_repo/database/schema.sql` (it has typed columns + PK + a real FK at schema.sql:13, exercising both the tree-sitter column path and the regex FK supplement) rather than relying on `ctcm-db` manual validation; (4) `upsert_facts` must default `commit=True` to mirror `upsert_refs` (`store.py:500`) and be *called* with `commit=False`, not invert the default; (5) the `clear_reindex_artifacts` insertion point corrected to `store.py:357–358` (inside the `if file_id_row is not None:` guard, keyed on `fid`), not the method opener at `store.py:328`; (6) the prerequisite's two cascade-cleanup tests (Step 3 (a)/(b)) flagged as un-runnable on a purely synthetic fact — they land with M23 or a content-driven test double; (7) edge-id f-string precisely at `graph.py:74`; and (8) profiles path is `profiles/extractors.json`. All other source claims (indexer.py:302/429/457/458, both `IndexStats`, the `INSERT OR REPLACE` cascade, the crash-guard, schema FKs) verified accurate against current source. Identified 2026-07-13.

- [ ] **Milestone 26: `uses_table` data-lineage correctness — alias binding and self-reference suppression.** **Reproduced against the running grammar 2026-08-24**, not inferred: a nine-line T-SQL fixture (two `CREATE TABLE`s + one procedure with `FROM dbo.Orders o INNER JOIN dbo.Customers c`) yields **10 `uses_table` edges, of which 5 are junk**. Two distinct defects, and the earlier one-line caveat ("T-SQL `uses_table` reports aliases as datastores") was **imprecise about both**. **(1) Alias edges are emitted but they are UNRESOLVED at confidence 0.30** — `GetOpenOrders → callee_name='o'` ×3 and `→ 'c'` ×2, `callee_symbol_id=None` — while the genuine tables resolve at **0.85** (`→ Orders`, `→ Customers`). So aliases are *distinguishable today* by `callee_symbol_id IS NOT NULL`, which makes the naive fix far cheaper than assumed; **but a confidence filter alone is wrong**, because a real table with no indexed DDL (cross-database reference, synonym, linked server) is *also* unresolved 0.30, so filtering silently discards genuine lineage. The fix must **bind the alias to its table** at extraction time (the `FROM`/`JOIN` alias binding is in the same statement, so this is recoverable, not a guess) and then either drop the alias ref or re-point it at the bound table — leaving *unbound* 0.30 refs to mean what they should mean: "a table we have no DDL for." **(2) A separate, worse defect — confident self-edges.** `Orders → Orders`, `Customers → Customers` and `GetOpenOrders → GetOpenOrders` are all emitted at **0.85**: an object's own name inside its own `CREATE` statement becomes a `uses_table` usage of itself. This is wrong data at high confidence, not missing data. Note `tests/test_sql_table_recovery.py::test_lineage_refs_survive_the_repair` already asserts `("Customer","Customer") not in used` — but **only on the bracketed regex-recovery path**; the clean tree-sitter path has no such guard, which is why this survived. **Why it matters beyond SQL hygiene:** `uses_table` is the substrate for the requirements store's computed `reads[]`/`writes[]` block (`docs/exec-plans/pending/reqs-to-data-store-plan-draft.md`, Q3h), whose whole value rests on the computed path being trustworthy per that plan's `NORMATIVE PRINCIPLE-1`. Until this lands, that block emits junk table names (`o`, `po`, `v`) — **wrong rather than merely incomplete**, which is the worse failure. It equally affects `data-documenter`, `data-dictionary-generator` and `database-layer-documenter`. **Deliverable:** alias binding + self-reference suppression, fixture CI tests pinning both (including the "unbound 0.30 still means unknown-table" case so the fix does not over-correct), and a before/after `uses_table` edge count on a real T-SQL corpus. Identified 2026-08-24 while deciding Q3h of the requirements-store plan.

- [ ] **Milestone 27: Make the unresolved-dispatch population visible (and decide whether to resolve it from framework config).** **The premise needed correcting before the work could be scoped.** It is *not* true that the index "emits no dispatch edges": §2 of `code-graph-construction.md` and `_resolve_callee` (`graph.py`) show every ref is graded — **0.85** exactly one match, **0.70** ambiguous same-language (prefer same file), **0.40** cross-language ambiguous, **0.30** zero matches — and the zero-match edge is **kept, with `callee_name` preserved** (the deliberate "preserve unresolved edges" decision). So the edge exists; what it lacks is a **callee symbol id**, which is what any traversal (`callees`, data-lineage, reads/writes) actually needs. Framework-mediated dispatch — MVC action → controller method, DI-resolved service → implementation, Spring/WebFlow transitions — is the main population, and it is concentrated in exactly the web-action layer that the NNG coverage work showed is hardest to reach. **Two separable deliverables; the second is optional and gated on the first.** **(a) Visibility (do this regardless).** An unresolved edge is currently indistinguishable from an absent one at the point of consumption, so every downstream count silently under-reports without saying so. Add a first-class way to *ask* — a `--unresolved` filter or an `unresolved_edges` breakdown in `stats`, by `edge_kind` and by enclosing file/domain — so a consumer can report a lower bound **as a floor rather than as a total**. This is the Layer-0 half of `NORMATIVE PRINCIPLE-1` clause 5 ("report the inference rate"): a consumer cannot report what the graph will not tell it. **(b) Resolution from framework config (decide, do not assume).** `/modernize-map` already resolves dispatch edges from framework configuration rather than from the index, which is evidence both that it is doable and that the logic exists somewhere to be lifted. Whether it belongs *in* Layer 0 is a genuine design question — it is configuration-shaped, framework-specific, and arguably not deterministic-AST work — so scope (b) only after (a) quantifies how large the unresolved population actually is per framework. **Measure first:** on `repos/ctcm/ctcm-api` and the NNG app unit, report unresolved-edge counts by `edge_kind` and the share attributable to framework dispatch. **Consumer:** the requirements store's Q3h block, whose `llm_inferred` fallback fires precisely on this population — a smaller unresolved set means fewer LLM-inferred entries and a stronger deterministic claim. Identified 2026-08-24 while deciding Q3h of the requirements-store plan.

## Surprises & Discoveries

- Observation: Python 3.14 is too new for the dependency stack; pin development to the most recent supported Python where wheels exist for all required packages.
  Evidence: On 2026-05-13, attempting `pip install -e tools/legacylift_search` under Python 3.14.3 (Windows 11) failed building `tokie` (a `chonkie` dependency) because no 3.14 wheel exists and its `maturin` (Rust) source build raised `PermissionError: ... AppData\Local\Temp\pip-build-env-*\overlay\Lib\site-packages\maturin\__init__.py`. Endpoint security policy blocks pip's build-isolation overlay under `%LOCALAPPDATA%\Temp` even after redirecting `TMP`/`TEMP`. The exec-plan's `tree-sitter-language-pack` decision also assumes prebuilt wheels, which currently target up to Python 3.13. **Decision**: standardize on the most recent supported Python (currently 3.13) for development and CI; revisit Python 3.14 once `chonkie`, `tokie`, `tree-sitter-language-pack`, and `chromadb` publish 3.14 wheels. For Milestone 1 acceptance only, `--help` was verified by installing `typer`/`rich`/`pydantic` and then running `pip install --no-build-isolation --no-deps -e tools/legacylift_search`.

- Observation: COBOL tree-sitter support is less standardized than C#, Java, Python, JavaScript, TypeScript, and SQL.
  Evidence: Implementation must include a COBOL parser spike and a regex/procedure-division fallback so the index remains useful for mainframe repositories even if a specific tree-sitter COBOL grammar cannot be installed reliably on the execution machine.

- Observation: `tree-sitter-languages` (the originally-named bundle) has unreliable wheels on Python 3.12+ on Windows.
  Evidence: The plan uses `tree-sitter-language-pack` (https://github.com/kreuzberg-dev/tree-sitter-language-pack), an actively-maintained replacement that bundles ~100 grammars and ships wheels for current Python versions including 3.12 and 3.13 on Windows, macOS, and Linux. It exposes `get_language(name)` and `get_parser(name)` similar to the older package. If a specific grammar is unavailable in the pack, fall back to per-language packages (`tree-sitter-c-sharp`, `tree-sitter-java`, etc.).

- Observation: SQLite and Chroma index files are large, churn on every reindex, and do not diff usefully.
  Evidence: The `legacylift-docs/index/code-search/` directory is gitignored. A freshness check stored as `source_set_sha256` in `index_metadata` (SHA-256 of the sorted list of `(relative_path, file_sha256)` pairs) lets `validate` and `search` report `fresh | stale | missing` status against current discovery, so drift is visible without forcing rebuilds.

- Observation: Chroma enforces consistent embedding dimensions within a collection.
  Evidence: The implementation must store the embedding provider, model name, and dimension in SQLite metadata and in the Chroma collection metadata. If the user changes from the deterministic test embedder to Qwen3-Embedding-0.6B, the tool must either rebuild the collection or fail with a clear message.

- Observation: This tool must be useful before perfect static analysis exists.
  Evidence: Caller/callee relationships should store a `confidence` value and preserve unresolved call names. A graph edge with an unresolved callee is still valuable because it lets a LegacyLift agent search for likely targets later.

- Observation: `tree-sitter-language-pack` 1.8.0 (Rust-backed) no longer exposes a parser usable from the standard `tree_sitter` Python bindings.
  Evidence: On 2026-05-15 (Python 3.12.9, Windows), `tree_sitter_language_pack.get_parser("python")` returns a `builtins.Parser` object that lacks a `parse(bytes)` method; `get_language("python")` returns a `builtins.Language` that the std `tree_sitter.Parser.language` setter rejects with `TypeError: language must be assigned a tree_sitter.Language object, not builtins.Language`. The pack now exposes a different higher-level API (`process(source, config)`). Milestone 5 therefore loads grammars via the per-language packages instead: `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-java`, `tree-sitter-c-sharp`, `tree-sitter-sql`. The exec-plan's "Decision: Use `tree-sitter-language-pack`" still stands as the *intent* (unified bundle), but the implementation falls back to per-language packages for Wave B because the pack's API has diverged. No COBOL wheel exists at all (`pip install tree-sitter-cobol` -> `No matching distribution found`), so COBOL uses regex fallback.

- Observation (follow-up, 2026-07-13): the current implementation loads grammars via the **language-pack `get_language` path, not the per-language packages** — reversing the mitigation recorded in the 2026-05-15 observation above.
  Evidence: The installed stack is `tree-sitter-language-pack` **1.8.1** + `tree-sitter` **0.25.2**. On this stack, `_load_via_lang_pack` (`extractors.py`) — `tree_sitter.Parser(get_language(name))`, passing the grammar to the `Parser` *constructor* rather than the `.language` *setter* that failed on 1.8.0 — works, and `dump-ast` produced valid trees for csharp/java/python/typescript on 2026-07-13 with `parser=<lang>` headers confirming path 1 succeeded. Consequently the per-language packages (`tree_sitter_python`, `tree_sitter_c_sharp`, …) named in `_load_via_individual` are **not installed** in the tool venv (`pip list` shows only `tree-sitter` and `tree-sitter-language-pack`), so that fallback tier is **inert today** — it is retained only as insurance against a future pack regression, and must not be treated as a live safety net. COBOL still has no wheel and uses regex fallback regardless.

- Observation: tree-sitter-sql node kinds diverge from the names listed in `extractors.json`.
  Evidence: `tree-sitter-sql` 0.3.11 emits `create_table`/`select`/`update`/`insert` node types, while the profile lists `create_table_statement`/`select_statement`/etc. To keep SQL useful, `SymbolExtractor.extract` supplements with regex fallback definitions when tree-sitter parsed the file but produced zero matching definition nodes; existing tree-sitter call/ref matches are kept. This keeps both code paths covered without needing to re-author the SQL profile.

- Observation: `--embedding-provider hash` honors `embedding.dimension` from the manifest rather than forcing dim=64.
  Evidence: On 2026-05-15, Milestone 10 wiring revealed that `create_embedder(config, provider_override="hash")` returns a `HashEmbedder` whose dimension equals `config.dimension` (only falls back to 64 if the manifest's dimension is falsy). Smoke runs against the polyglot fixture with the default manifest (`embedding.dimension=1024`) therefore embed at 1024 dims with zero-buckets dominating. This is intentional per the existing dispatch logic and enables dimension-mismatch tests without manifest edits, but tests that want a true 64-dim hash run must set `manifest.embedding.dimension = 64` explicitly. Documented for future agents who write end-to-end tests.

- Observation: The plan's repository name `repos/ctcm-api` does not exist; the actual on-disk path is `repos/ctcm/ctcm-api`.
  Evidence: On 2026-05-18, Milestone 14 (Agent E2) discovered that `repos/ctcm/` is a multi-project monorepo containing `ctcm-api/` (4,715 .cs files), `ctcm-db/`, and `ctcm-web/`. The plan's "Decision: Validation target is repositories under `./repos/`" and the Validation/Acceptance section both name `repos/ctcm-api`, but no such directory exists. An initial validation attempt against the umbrella `repos/ctcm` (10,599 source files across all three subprojects) had to be aborted after ~2 hours because indexing scaled past the available time budget. Switching to `repos/ctcm/ctcm-api` produced a usable end-to-end index. Future references in the plan and skill instructions should use `repos/ctcm/ctcm-api`.

- Observation: Indexer Chroma upsert phase is the wall-clock bottleneck on a real .NET repo.
  Evidence: On 2026-05-18, the SQLite-side phases (file discovery, extraction, chunk/symbol/ref upsert, graph build) for `repos/ctcm/ctcm-api` (4,715 files) completed in approximately 90–110 minutes. The subsequent Chroma upsert phase, with the default `embedding.batch_size=16` and `embedding.dimension=1024` against ~58,677 chunks, was still running after another 60 minutes with no observable Chroma sqlite or HNSW data file modification (process CPU was high but writes were buffered). The validation run completed only after manually writing `index_metadata` from the indexer's deterministic source-set hash and observed counts. The Chroma collection committed before the kill held 15,264 vectors out of 58,677 chunks. Recommended fix candidates: (a) flush/checkpoint Chroma collection inside the upsert loop, not only at process exit; (b) raise default `batch_size` to 64–128 for hash embedder; (c) write `index_metadata` and `index.log` incrementally so a partial index is still usable after interruption; (d) emit per-batch stdout progress so background runs are observable.

- Observation: Hash-embedder default dimension of 1024 with the polyglot manifest produces sparse vectors but works for validate/search smoke testing.
  Evidence: On 2026-05-18, `legacylift-search search "authentication authorization validation" --repo-root repos/ctcm/ctcm-api --limit 5` returned five ranked C# results from `SpecialClaimManager.CreateReserveTask`, `IAppealCaseRepository`, `IClaimManager`, `IClaimRepository`, and `ICalendarEventRepository`. RRF still produces useful ordering even though the partial Chroma index covered only ~26% of chunks. With a full index and the production Qwen embedder, ranking quality should improve materially.

- Observation: The Qwen production embedding path was not exercised against `repos/ctcm/ctcm-api` in Milestone 14.
  Evidence: Per the plan's explicit "do not block" guidance for Qwen failures, and given the 5+ hour wall-clock budget already spent on the hash-embedder validation runs, the optional `legacylift-search index --repo-root repos/ctcm/ctcm-api --reset` with the Qwen provider was not attempted on 2026-05-18. Unit coverage around Qwen configuration and error messaging from Wave A/B remains intact.

- Observation: Qwen3-Embedding-0.6B end-to-end run against `repos/ctcm/ctcm-api` is blocked by the Claude Code harness per-task wall-clock cap.
  Evidence: On 2026-05-19, two `legacylift-search index --repo-root repos/ctcm/ctcm-api --reset` runs were attempted with the manifest-default Qwen embedder (no `--embedding-provider` override). Run 1 (started 2026-05-19T17:02 UTC) was killed at the 60-minute mark, having completed extract+chunk and graph-edge-build phases (4,715 files / 58,677 chunks / 58,614 symbols / 135,973 refs / 141,219 graph edges in SQLite) but before chroma-upsert started. Run 2 (started 2026-05-19T18:11 UTC) was killed at the 60-minute mark in the chroma-upsert phase, after the Qwen model loaded successfully from local cache (`Loading weights: 100%|##########| 310/310 [00:00<00:00, 2362.41it/s]`) but before any embedding batches were committed to Chroma. Both kills were the harness signaling background bash tasks at ~600s — the underlying Python process was still healthy and the embedder/SQLite state was consistent at kill time. Final state after the second kill: `embedder_name='qwen3:Qwen/Qwen3-Embedding-0.6B'`, `embedding_dimension=1024`, `vectors_upserted=0`, `chunk_count=58677`, Chroma `code_chunks` collection has 0 vectors. `validate` reports `Index is valid.` with `WARNING: vector coverage incomplete: vectors_upserted=0 < chunk_count=58677`.
  Resolution path: the chroma-upsert loop in `Indexer.run` already commits the `vectors_present` SQLite cache and Chroma per batch (see `indexer.py:606-625`), so a longer-lived execution context (manual run from a developer machine, or a CI job without the 600s cap) can complete the upsert in one pass; alternatively, a future enhancement could split the upsert into a separate `legacylift-search backfill-vectors` subcommand that processes one batch at a time and is safe to call repeatedly under the harness cap. The cap itself is environmental and out of scope for the LegacyLift implementation. The Qwen production path is structurally working — model loads, dimensions are correct, batch_size=512 + HNSW tuning from the M14 perf bundle remains in place — so Milestone 18 (reranker) does not need to wait on the upsert backfill.

- Observation: Chonkie 1.6.6 successfully installs and runs on Python 3.12 on Windows 11.
  Evidence: On 2026-05-15, Milestone 6 (Agent B2) installed `chonkie==1.6.6` on Python 3.12.9/Windows 11 without build issues. The `tokie` dependency (Rust-based tokenizer) had prebuilt wheels. Chonkie's CodeChunker with `tokenizer="character"` and `language="python"` successfully chunked test fixtures. Chonkie is wrapped in try/except so parse failures fall through to deterministic line-based chunking.

- Observation: The embedding-cost filter cuts the Qwen forward-pass count on `repos/ctcm/ctcm-api` by 76%, which should bring the M17 Qwen pass under the harness wall-clock cap.
  Evidence: On 2026-06-25, the production `embed_filter` functions (`partition_for_embedding`, `dedupe_by_text_sha`, `has_business_logic`) were applied directly to the 58,677 text-bearing chunks in the existing ctcm-api `index.sqlite` (read-only, no re-index; load took 3.1s). Results:
  - **Spike #2 (text dedup, threshold-independent):** 37,456 distinct `text_sha256` representatives; 21,221 chunks (36.2%) are exact-text duplicates collapsed onto a representative. So dedup alone — even with the filter off — cuts forward passes 58,677 → 37,456 at zero recall loss.
  - **Spike #1 (low-value filter), skip% and `has_business_logic` rescues per threshold:**

    | min_tokens | embedded | skipped | skip% | rescued by logic |
    | --- | --- | --- | --- | --- |
    | 0 (default/off) | 58,677 | 0 | 0.0% | — |
    | 40 | 18,192 | 40,485 | 69.0% | 11,570 |
    | 80 | 17,212 | 41,465 | 70.7% | 13,768 |
    | 120 | 16,913 | 41,764 | 71.2% | 14,723 |
    | 160 | 16,819 | 41,858 | 71.3% | 15,219 |

  - **Combined (filter THEN dedup), actual forward passes fed to the embedder:**

    | min_tokens | forward passes | reduction vs 58,677 |
    | --- | --- | --- |
    | 0 | 37,456 | 36.2% |
    | **80** | **14,093** | **76.0%** |
    | 160 | 13,714 | 76.6% |

  Conclusion: `embed_min_tokens=80` is the chosen threshold — 76.0% fewer forward passes, and the reduction curve flattens after 80 (160 buys only 0.6% more while skipping more potentially-useful chunks). The `has_business_logic` guard is doing real work (rescuing 13,768 sub-threshold chunks at thr=80 that carry validation/branching/SQL-constraint signal), so the cut is content-aware, not a blind size cutoff. Filtered-out chunks keep full lexical/FTS5/`symbols` recall. This measurement justifies Milestone 17b: a Qwen `--reset` with the filter enabled should complete inside the harness cap that blocked the unfiltered M17 run.

- Observation: **The 76% forward-pass cut does NOT unblock the Qwen upsert — the real wall is per-chunk CPU inference throughput (~7s/chunk), not chunk count.** The M17b prediction (that cutting forward passes 76% would bring the run under the harness cap) was wrong about *which* quantity was the binding constraint.
  Evidence: On 2026-06-25 the M17b procedure was executed live against `repos/ctcm/ctcm-api`. The filter behaved exactly as measured the same day: the embedder reported `Skipped dense vectors for 41465 low-value chunks`, `Deduplicated 3119 chunks`, and `Embedding 14093 distinct chunks` — the predicted 58,677 → 14,093 (76.0%) reduction, confirmed in a real index run, not just a read-only measurement. But the per-chunk cost on this host (Windows 11, CPU only, no CUDA) is ~6–7 seconds per Qwen3-Embedding-0.6B forward pass — roughly 100× the plan's optimistic "tens of ms" estimate. At that rate the 14,093 distinct forward passes still require **~20+ hours** of pure compute. Two runs were attempted:
    - **Run 1** (`index --reset`, default `batch_size=512`): SQLite phases completed cleanly — `[discovery]` ~20s, `[extract+chunk]` ~96 min (17:53→19:30 UTC; slower than the M15 baseline of 63 min, attributed to host load), `[graph-edge-build]` ~2 min, all 58,677 chunks / 58,614 symbols / 135,973 refs / 141,219 edges persisted. The embedding phase then ran ~60 min on a single 512-chunk batch without committing: under `_embed_and_upsert`, `vectors_present` and `vectors_upserted` are written only **after** a full batch's forward passes complete (indexer.py:796–802), so a 512-chunk batch at ~7s/chunk = ~60 min/commit. The harness killed the run before the first batch became durable → **0 vectors saved**, all embedding compute lost.
    - **Run 2** (`backfill-vectors`, after lowering `batch_size` to 32 in the manifest): chosen to make commits land every ~3–4 min (32 × 7s) and survive a kill, driving off `get_chunks_missing_vectors()` (17,212 missing → 14,093 distinct → `441 batches of 32`). Confirmed the resumable path runs correctly, but it was stopped by operator request before the first batch committed (the run is a multi-hour proposition regardless of batch size — small batches make it *resumable*, not *faster*).
  Final index state after stopping (consistent, not corrupted): 58,677 chunks / 58,614 symbols / 135,973 refs in SQLite; `vectors_present` = 41,465 (the filtered low-value chunks, marked present at filter time and fully FTS5-searchable); 17,212 chunks (14,093 distinct) still missing dense vectors; `embedder_name='qwen3:Qwen/Qwen3-Embedding-0.6B'`, `embedding_dimension=1024`; `validate` passes with the `WARNING: vector coverage incomplete` line.
  Resolution path: the binding constraint is per-chunk CPU inference, so the lever is hardware/throughput, not the filter. Options to evaluate (handed to a fresh discovery agent): (a) run the Qwen embedder on CUDA via `embedding.device="cuda"` — already supported, the plan's own note estimates 10–50× and `backfill-vectors` would then complete in well under an hour; (b) run the embedding on any host without the harness wall-clock cap (developer machine / CI job), where even CPU finishes given ~20h; (c) a hosted/batch embedding API; (d) a smaller/faster local embedding model. The `backfill-vectors` mechanism + per-batch `vectors_present` checkpointing is proven and will complete the upsert incrementally once the per-chunk cost drops. `batch_size` was left at 32 in the manifest to favor frequent, kill-survivable commits on the eventual completion run; revert to 512 if running on a GPU host where batch throughput dominates.

- Observation: **CORRECTION to the entry above — the "~7 s/chunk / ~20+ hours" figure was a measurement artifact of CPU contention, not the hardware floor. Benchmarked in isolation on the same host, Qwen3-Embedding-0.6B runs at ~350 ms/chunk, so the filtered pass is an ~80-minute job, not a 20-hour one.** The binding constraint in the M17b run was that the embedding ran *concurrently* with (or immediately after) the CPU-saturating extract+chunk phase and parallel monitoring tasks, not that a single forward pass costs 7 s.
  Evidence: On 2026-06-26, Qwen3-Embedding-0.6B was benchmarked directly (idle CPU, this host: 22 cores, `torch 2.12.0+cpu`, MKL available, model warm) against realistic ~25-token C# chunks:

    | batch_size | chunks | wall-clock | per-chunk |
    | --- | --- | --- | --- |
    | 32 | 256 | 90.2 s | **352 ms** |
    | 64 | 256 | 110.6 s | 432 ms |

  Two facts compound this: (1) the ctcm-api corpus is tiny per pass — from `index.sqlite`, **avg 25 tokens/chunk**, max 2,795, and only 316 of 58,677 chunks (0.5%) exceed 512 tokens; the model's `max_seq_length` is 32,768 but the actual sequences are short. (2) Larger CPU batches are *slower* per chunk (bs=64 > bs=32), because one batch already saturates all cores and bigger batches just add padding/compute — so the GPU-oriented default `batch_size=512` is actively wrong for the CPU path; **32 is the right CPU batch size** (it also makes per-batch commits land every ~11 s and survive a kill). Recomputed idle-CPU wall-clock at 350 ms/chunk:

    | scenario | forward passes | idle-CPU compute |
    | --- | --- | --- |
    | no filter | 58,677 | ~5.7 h |
    | dedup only | 37,456 | ~3.6 h |
    | **filter+dedup @ `embed_min_tokens=80`** | **14,093** | **~80 min** |

  Conclusion: the M17b cost filter (76% cut) **does** bring the Qwen pass into a tractable, resumable window — ~80 min on an *idle* CPU host via repeated `backfill-vectors` calls at `batch_size=32`, not 20+ hours. The earlier entry's "wall is per-chunk CPU throughput, not chunk count" framing was right that the filter alone wasn't the whole story, but wrong about the magnitude: the real wall was running the embed under contention. CPU multiprocessing is NOT a useful additional lever here — since one batch saturates all cores, sharding across processes would only contend. GPU (`embedding.device="cuda"`) remains the biggest single lever (10–50×, single-digit minutes) and a hosted batch-embedding API is the next option to evaluate now that an upcoming project may relax the local-only constraint (see Decision Log).

- Observation: **Amazon Bedrock Titan Text Embeddings v2 enforces TWO independent input limits — 50,000 bytes AND 8,192 tokens — and a real C# repo has chunks that exceed both. A hosted embedder must guard length or one oversized chunk poisons the whole embed phase (and makes `backfill-vectors` non-convergent).**
  Evidence: On 2026-06-26, the first at-scale Bedrock embed of `repos/ctcm/ctcm-api` aborted on a single chunk — `src/CTCM.API/CTCM.API.ClaimService/Dto/ClaimDtoFactory.cs` lines 11–1010, **50,974 UTF-8 bytes (~2,795 est. tokens, itself above the manifest `chunking.max_tokens=1400`)** — with `ValidationException: ... maxLength: 50000`. The original `BedrockEmbedder._invoke` sent `inputText` verbatim with no guard, so the 512-text batch containing it raised and aborted `embed_documents`; repeated `backfill-vectors` calls deterministically died on the same chunk's batch (17,212 → 15,063 missing, never reaching 0). Adding a 50,000-byte pre-truncation then surfaced the *second*, tighter limit on a synthetic 55,020-byte input: `ValidationException: Too many input tokens. Max input tokens: 8192, request input token count: 27267` — i.e. dense code is ~2 bytes/token, so a fixed byte cap cannot guarantee the token cap. Fix: `_invoke` pre-truncates to the byte cap on a UTF-8 boundary, then **retries with halved input on any length-class `ValidationException`** until it fits (bounded to 12 halvings, with a clear backstop error if every input is rejected). The full chunk text remains in SQLite/FTS5 for lexical recall; only the dense vector is computed from a bounded prefix — the same trade local embedders make at `max_seq_length`. Verified live: the 55,020-byte input that previously failed now embeds to a 1024-dim vector, and the full ctcm-api backfill completed in one clean pass with zero length/throttle errors. Lesson for future hosted embedders (Cohere, OpenAI, etc.): always interrogate *both* the byte and token request limits and make the embedder self-correcting, because the chunker's token cap is an *estimate* and generated/DTO code blows past it.

- Observation: With `embed_min_tokens=80`, the live Chroma vector count is far below `chunk_count`, and that is correct — not an incomplete index.
  Evidence: After the completed Bedrock run on `repos/ctcm/ctcm-api`, `index_metadata.vectors_upserted` and the `vectors_present` cache both reach `chunk_count=58,677` and `validate` reports no coverage warning, yet the live Chroma `code_chunks` collection holds exactly **17,212** vectors. This reconciles precisely: 58,677 total − **41,465** chunks below the `embed_min_tokens=80` filter (marked present via FTS5, never dense-embedded) = 17,212 actually embedded. The 41,465 figure matches the 2026-06-25 filter measurement for this same repo. So `vectors_upserted` counts *resolved* chunks (embedded **or** deliberately filtered-and-marked-present), which is what keeps coverage exact and `backfill-vectors` terminating; the raw Chroma `count()` counts only real dense vectors. A future operator who diffs `count()` against `chunk_count` should subtract the filtered set before suspecting a bug.

## Decision Log

- Decision: Domain capture & back-annotation (assess domains → durable SQLite knowledge store, Chroma domain-filtered search, derived ARCHITECTURE.mmd) is being planned as a **separate execplan**, not appended here.
  Rationale: It introduces a new durable `knowledge.sqlite` store (distinct lifecycle from the throwaway code-search index), relocates the M23–25 `symbol_facts` table into it, modifies the Apache-licensed `modernize-assess` skill to emit a transient `domains.json`, and has its own consumer/future-work roadmap (fact-graph Option-A follow-on). Building directly on M22–25, it is a distinct architectural component. The governing execplan is [`docs/exec-plans/completed/domain-enhancements-plan.md`](../completed/domain-enhancements-plan.md) (decision-interview notes: `docs/exec-plans/completed/domain-plan-notes.md`; source direction: `docs/exec-plans/pending/fact-graph-decision.md` §6a).
  Date/Author: 2026-07-17 / Darrell Norton (with Claude).

- Decision: Implement the capability as an isolated Python CLI package under `tools/legacylift_search`.
  Rationale: The target repositories may be .NET, Java, Python, JavaScript, COBOL, SQL, or mixed-language systems. An isolated Python tool avoids coupling the indexer to any one application runtime and lets Codex add it safely to almost any repository.
  Date/Author: 2026-05-08 / Initial ExecPlan author.

- Decision: Use Chonkie as the primary code chunker and keep a deterministic fallback chunker.
  Rationale: Chonkie provides AST-aware code chunking, which should preserve semantic boundaries better than fixed-size text splitting. A fallback is still required because legacy repositories often include generated code, malformed files, proprietary dialects, and copybook-heavy COBOL that may fail strict parsing.
  Date/Author: 2026-05-08 / Initial ExecPlan author.

- Decision: Use Chroma persistent local storage for vectors and SQLite for metadata, lexical search, and graph data.
  Rationale: Chroma is a practical local vector store. SQLite is file-backed, portable, inspectable, supports transactions, and includes FTS5 lexical search in common Python distributions. The combination allows the generated index directory to be shared with another agent or checked into a controlled branch when appropriate.
  Date/Author: 2026-05-08 / Initial ExecPlan author.

- Decision: Use Qwen3-Embedding-0.6B as the production local embedding model and a deterministic hash embedder for tests.
  Rationale: Qwen3-Embedding-0.6B is small enough for local use relative to larger embedding models and is suitable for code retrieval. Tests must not download models or require GPU hardware, so they use a deterministic local embedder that produces stable vectors.
  Date/Author: 2026-05-08 / Initial ExecPlan author.

- Decision: Use reciprocal rank fusion, abbreviated RRF, for hybrid ranking.
  Rationale: RRF combines independently ranked vector and lexical results without requiring scores to be on the same scale. This is robust for mixed systems where dense similarity and keyword relevance have different distributions.
  Date/Author: 2026-05-08 / Initial ExecPlan author.

- Decision: Persist unresolved graph edges instead of discarding them.
  Rationale: Static call resolution across dynamic languages, reflection, dependency injection, SQL, CICS, and COBOL paragraphs is inherently imperfect. Preserving unresolved calls with evidence makes the graph useful to downstream agents and enables later refinement.
  Date/Author: 2026-05-08 / Initial ExecPlan author.

- Decision: Put extractor rules in JSON profiles rather than hard-coding all node kinds.
  Rationale: The top six languages are known now, but LegacyLift will encounter additional languages. JSON profiles let a future agent add or tune language support without rewriting core indexing logic.
  Date/Author: 2026-05-08 / Initial ExecPlan author.

- Decision: This is the first component of LegacyLift v4 (rewrite). v3 skills under `.claude/skills/` are reference-only and are NOT inputs to this tool.
  Rationale: v4 starts clean. Avoiding any data dependency on v3 fact-graph packs keeps the new tool self-contained, prevents stale-input bugs, and gives v4 freedom to redefine entity/relation models. Existing v3 outputs (e.g., `repos/ctcm-api/legacylift-docs/context/`) are left untouched as reference until v4 replacements exist.
  Date/Author: 2026-05-12 / Plan finalization.

- Decision: Index artifacts live per-repo at `repos/<repo-name>/legacylift-docs/index/code-search/` and are gitignored, with a `source_set_sha256` freshness check.
  Rationale: SQLite + Chroma are derived binary artifacts that churn on every reindex and don't diff in git. Treating them as build artifacts (gitignored) avoids repo bloat and PR noise. Storing a SHA-256 of the sorted `(relative_path, file_sha256)` list in `index_metadata` lets `validate` and `search` report `fresh | stale | missing` so drift is loud without forcing rebuilds. The path follows the existing `legacylift-docs/` convention used by v3 (e.g., `legacylift-docs/context/packs/` for fact-graph) but uses a new `index/` namespace reserved for retrieval indexes.
  Date/Author: 2026-05-12 / Plan finalization.

- Decision: Use `tree-sitter-language-pack` instead of `tree-sitter-languages`.
  Rationale: `tree-sitter-language-pack` (https://github.com/kreuzberg-dev/tree-sitter-language-pack) is actively maintained, bundles ~100 grammars, and publishes wheels for Python 3.12/3.13 on Windows, macOS, and Linux. The legacy `tree-sitter-languages` package has stale wheels and frequently fails to install on current Python on Windows. The pack exposes `get_language(name)` and `get_parser(name)` similar to the older API, so adapter code is minimal.
  Date/Author: 2026-05-12 / Plan finalization.

- Decision: For Milestone 15's Chroma skip-detection, use a local SQLite `vectors_present(chunk_id, text_sha256)` cache rather than `chromadb.Collection.get(ids=[...])`.
  Rationale: One local SELECT per upsert batch is dramatically faster than a Chroma round trip per batch, the cache write piggy-backs on the existing per-batch SQLite commit at zero extra wall-clock cost, and storing `text_sha256` alongside the chunk_id lets us detect chunk-text changes even when the deterministic chunk_id is stable (e.g. whitespace-only edits inside a method body — same id, different text). The plan offered both options as candidates ("`collection.get(ids=[...])` to check, or maintain a `vectors_present` table in SQLite for speed"); we picked the SQLite path explicitly.
  Date/Author: 2026-05-19 / Milestone 15.

- Decision: `Indexer.run` only re-upserts `repo_files` rows for *changed* files on incremental runs.
  Rationale: `repo_files.relative_path` is `UNIQUE`, and `chunks`/`symbols`/`symbol_refs` have `ON DELETE CASCADE` foreign keys back to `repo_files`. `INSERT OR REPLACE` on an unchanged row replaces it (delete-then-insert in SQLite semantics) and cascades the deletion through every artifact downstream — silently undoing the skip-on-unchanged optimization. The Milestone 14 codepath upserted every file every run, which was correct only because every file was also re-extracted on the same run. With M15's fast path, that no longer holds. This decision was discovered via test failure (`test_index_idempotent_rerun` reported `chunk_count=0` after rerun) and is non-obvious enough to warrant its own log entry so a future refactor doesn't re-introduce the regression.
  Date/Author: 2026-05-19 / Milestone 15.

- Decision: Validation target is repositories under `./repos/`, not the legacylift-ai repo itself.
  Rationale: `legacylift-ai` is mostly markdown and skill definitions; it has no .cs/.java/.py code paths to index meaningfully. Real validation must run against client codebases under `./repos/` (currently `repos/ctcm-api`, with more to come). The Milestone 14 validation step is rewritten accordingly.
  Date/Author: 2026-05-12 / Plan finalization.

- Decision: Keep the local Qwen path as the default, but treat a **hosted/batch embedding API** as a first-class supported embedder once the local-only constraint relaxes.
  Rationale: The original "must remain local only" constraint (Decision 2026-05-08 on Qwen3-Embedding-0.6B) ruled out a network embedder. An upcoming project is expected to relax that. With the constraint relaxed, a hosted embedding API (or a batch-embedding endpoint) is the most operationally robust fix for the embed bottleneck: it removes the per-chunk CPU cost entirely, has no GPU-provisioning dependency, and scales to many repos without per-host setup. It slots cleanly into the existing design — `create_embedder` already dispatches on `embedding.provider`, so a new `provider` value (e.g. `"api"`) plus an `EmbeddingConfig` endpoint/model/key field is the whole surface; the `vectors_present` checkpointing and `backfill-vectors` resumability carry over unchanged. Trade-offs to weigh when implemented: (1) source code leaves the machine — must be gated on per-engagement data-handling approval and is NOT acceptable for every client; keep `qwen3`/`hash` as the local fallback. (2) cost and rate limits — batch endpoints amortize both; size requests to the provider's batch limit. (3) dimension must still match the Chroma collection, so switching providers requires a `--reset` per the existing dimension-consistency rule. Priority among completion paths: idle-CPU backfill now (no deps), GPU when a box is available (biggest local lever), hosted API as the durable cross-repo answer once approved.
  Date/Author: 2026-06-26 / Embedding-time options analysis.

- Decision: Adopt a hosted **Amazon Bedrock** embedding provider as the chosen production embedding path (Milestone 20); pause the local Qwen embedding milestones (M17, M17b, and the Qwen3-Reranker M18) with the reason "Embedding approach evaluation."
  Rationale: The corrected idle-CPU Qwen benchmark (~350 ms/chunk → ~80 min for the filtered 14,093-pass ctcm-api job) is still too long for routine cold indexing. A hosted Bedrock embedder removes per-host compute entirely (few-minutes embed phase, no GPU box, no idle-host requirement) and is the durable cross-repo answer. **Code egress to AWS is approved for this embedding use case**, so the prior data-handling gate is cleared for this work — the local `qwen3`/`hash` providers remain first-class fallbacks for engagements where egress is not approved. The integration surface is small: a `provider="api"` branch in `create_embedder` plus region/model `EmbeddingConfig` fields. **Confirmed AWS environment (2026-06-26):** region `us-east-2`; auth via the `AWS_BEARER_TOKEN_BEDROCK` env var already present in `.claude/settings.local.json` (Bedrock API-key/bearer mechanism read automatically by the SDK — not SigV4, no profile/role/manifest token); per-model access is auto-provisioned in this account, so no console "request model access" step is needed. The token is never stored in the manifest. **Verified live 2026-06-26**: a smoke `InvokeModel` on `amazon.titan-embed-text-v2:0` in `us-east-2` via the env-var token (boto3 1.40.12) returned a normalized 1024-dim embedding with no access error — token auth, region, auto-provisioning, and the 1024-dim collection match are all confirmed. `vectors_present` checkpointing and `backfill-vectors` resumability carry over unchanged. A quality A/B (deferred M17 Qwen-vs-hash, extended to Bedrock) should still gate adopting the hosted embedder for *retrieval quality*, since Titan/Cohere are general-purpose, not code-specialized.
  Date/Author: 2026-06-26 / Bedrock embedding adoption + egress approval.

- Decision: The graph is intentionally a **call/reference/import/data-access** graph and (through Milestone 20) does **not** capture **type-hierarchy** edges (`inherits`, `implements`). Milestone 22 adds them.
  Rationale: The original extractor profiles list only `call_node_kinds` and `import_node_kinds`; the class/interface *declaration* is captured as a `symbol`, but its base class / implemented interfaces are neither a `symbol` attribute (the `Symbol` model has no `base_type` field) nor a `symbol_ref` (the inheritance clause node — C# `base_list`, Java `superclass`/`super_interfaces`, TS/JS `class_heritage`, Python `superclasses` — is in no profile), so `GraphBuilder._edge_kind_from_ref` can never emit an `inherits`/`implements` edge. Inheritance therefore survives only as **raw text inside chunks** (FTS5/vector-retrievable, but an agent must re-parse the `: Base` clause itself) — it is not a queryable, resolved, confidence-scored edge. This was an implicit scoping consequence, not an explicit decision, so it is recorded here now that it matters. It matters because the v3 fact-graph relations that downstream doc skills consume are, on `ctcm-api`, ~74% inheritance (`inherits` 1,826 + `implements` 884 of the 4 relation types actually produced). Any plan to let this Layer-0 index "own structure" for a refactored fact-graph (see `docs/exec-plans/pending/fact-graph-decision.md`, Option A) has a real gap until type-hierarchy edges exist here. Adding them also extends the existing "preserve unresolved edges" decision naturally: external base types (`ControllerBase`, `DbContext`, framework interfaces) will not resolve to an indexed symbol and are kept as unresolved `inherits`/`implements` edges with confidence 0.30.
  Date/Author: 2026-07-13 / Inheritance-edge gap identified while scoping fact-graph Option A.

## Outcomes & Retrospective

This is a current-status summary. The full per-milestone retrospective entries (Milestones 14–20, with run logs, timings, and gate evidence) have been moved to the companion archive `semantic-code-search-graph-index-additional-info.md` to keep this file focused on the live state — see `docs/exec-plan.md`, "Large plans: split current state from archived detail." Read the archive only if you need that history.

**Where the work stands (2026-07-15):**

- **Shipped and validated** — the full foundational build (Milestones 1–14): an isolated Python CLI package `tools/legacylift_search` that builds a per-repo SQLite + Chroma index, runs hybrid (vector + lexical) search with reciprocal rank fusion, persists caller/callee graph edges with confidence scores, and reports `fresh`/`stale`/`missing` index status. Validated end-to-end against `repos/ctcm/ctcm-api` (4,715 files / 58,677 chunks / 58,614 symbols / 135,973 refs / 141,219 edges).
- **Shipped** — incremental and performance milestones: M15 (skip-on-unchanged reindex), M16 (per-phase log timestamps), per-batch embedding progress + write-through `index.log`, the `backfill-vectors` resumable subcommand, the embedding-cost filter (`embed_min_tokens`, ~76% forward-pass cut) + text dedup, and M19 (parallelized extraction + batched SQLite commits, ~30% faster cold extract).
- **Shipped and adopted as the production embedding path** — Milestone 20 (hosted Amazon Bedrock `provider="api"`). Part 1 (embed-phase benchmark) is complete: the full ctcm-api index is Bedrock-embedded (`api:bedrock:amazon.titan-embed-text-v2:0`, dim 1024), embed work in single-digit minutes (~25–30× faster than the local-Qwen estimate), all gates green.
- **Paused** — the local Qwen embedding milestones (M17, M17b) and the Qwen3-Reranker (M18), held under "Embedding approach evaluation" now that Bedrock is the adopted path. The structural work and benchmark findings carry over; only the local-Qwen *completion* is paused.
- **Paused, gated behind Milestone 21** — M20 Part 2 (the hash-vs-Bedrock retrieval-quality A/B). It answers "adopt Bedrock *for quality*?" — premature until M21 establishes whether the semantic-search + code-graph index helps the LegacyLift workflow more than the existing `fact-graph` skill.
- **Shipped and validated** — Milestone 22 (type-hierarchy `inherits`/`implements` edges). The graph now captures inheritance/interface-implementation, closing the relation family that dominates the v3 fact-graph output. Validated on `repos/ctcm/ctcm-api`: 2,750 net-new hierarchy edges (`inherits` 2,112 + `implements` 638), same order of magnitude as fact-graph's 1,826 + 884 ≈ 2,710; 13.0% unresolved (external framework bases, confidence 0.30). Zero regression to call/reference edges (proven by a stash-and-rebuild A/B). This is a prerequisite for the fact-graph Option-A refactor (`docs/exec-plans/pending/fact-graph-decision.md`). Full suite 196 passing.
- **Next up** — Milestone 21 (value comparison of the index against `fact-graph`) — ⚠️ **read the `▸ 2026-08-25` measured-input block on M21 before defining its evaluation; the facts layer, identity, inheritance, routes, columns and domains are settled non-differentiators, and §5a.4 residue (a) pack emitter + (b) semantic typing are unowned** — then Milestones 23–25 (annotations/attributes, SQL columns/FKs, field/method type refs — building on the M22 pattern). See the `Progress` checklist for the full milestone definitions.

## Context and Orientation

This repository may be any client codebase that LegacyLift needs to analyze. The implementation must therefore add a new tool without assuming that the repository is already a Python project.

Create all new source code under:

    tools/legacylift_search/

The Python package inside that directory is named:

    legacylift_search

The command-line program installed by the package is named:

    legacylift-search

The tool creates an index directory inside the target repository, following the existing `legacylift-docs/` convention. By default, given a repository at `<repo-root>`, the directory is:

    <repo-root>/legacylift-docs/index/code-search/

The index directory contains:

    <repo-root>/legacylift-docs/index/code-search/index.sqlite
    <repo-root>/legacylift-docs/index/code-search/chroma/
    <repo-root>/legacylift-docs/index/code-search/manifest.snapshot.json
    <repo-root>/legacylift-docs/index/code-search/index.log

`index.sqlite` is the authoritative metadata, lexical search, and graph database. `chroma/` is the persistent Chroma vector database. `manifest.snapshot.json` is a copy of the manifest used for the last successful index run. `index.log` records indexing progress and recoverable parse errors.

The entire `legacylift-docs/index/` tree is treated as a derived build artifact and MUST be gitignored. The implementation must add or update `repos/<repo-name>/.gitignore` (or the legacylift-ai root `.gitignore` with a `repos/*/legacylift-docs/index/` rule) so committed history never includes SQLite or Chroma binaries. To detect drift without forcing rebuilds, the indexer stores a `source_set_sha256` value in the SQLite `index_metadata` table — the SHA-256 of the sorted list of `(relative_path, file_sha256)` pairs from the last successful run. The `validate`, `search`, `stats`, and graph commands compare this hash to a fresh discovery and report status as one of:

- `fresh` — index exists and `source_set_sha256` matches current source files.
- `stale` — index exists but source files have changed; commands still run but emit a warning recommending reindex.
- `missing` — no index directory or migrations have not been run; commands fail with a clear message telling the user to run `legacylift-search index`.

A “chunk” means a contiguous piece of source code selected for retrieval. The chunk should usually be a function, method, class, SQL procedure, COBOL paragraph, or a bounded part of a large construct. A chunk stores the source text, file path, line range, language, and nearby symbol information.

An “embedding” means a numeric vector representing text meaning. The production embedder uses Qwen3-Embedding-0.6B. The test embedder uses deterministic hashing so tests run without network access, model downloads, or GPU hardware.

A “vector search” compares embeddings to find semantically similar chunks. This helps when the query uses different words than the code.

A “lexical search” uses literal tokens and BM25-style ranking through SQLite FTS5. This helps when exact identifiers, class names, table names, error codes, or acronyms matter.

A “graph” means relationships between symbols. A symbol is a named code entity such as a class, method, function, COBOL paragraph, SQL procedure, or table. A caller/callee edge means one symbol appears to call or reference another. The graph is not expected to be perfect; each edge stores a confidence value and evidence text.

A “profile” means a JSON configuration describing file extensions, tree-sitter language names, symbol node kinds, call node kinds, import node kinds, and fallback extraction rules for a language.

The first implementation must support these language groups:

C#:
    Extensions: .cs
    Primary use: enterprise .NET services, APIs, and business logic.

Java:
    Extensions: .java
    Primary use: enterprise services, batch jobs, and legacy middleware.

Python:
    Extensions: .py
    Primary use: scripts, data processing, agents, and utilities.

JavaScript and TypeScript:
    Extensions: .js, .jsx, .mjs, .cjs, .ts, .tsx
    Primary use: front ends, Node services, and test automation.

COBOL:
    Extensions: .cbl, .cob, .cpy, .copy, .pco
    Primary use: mainframe programs, copybooks, batch jobs, CICS, DB2, and transaction logic.

SQL:
    Extensions: .sql, .ddl, .dml, .psql, .pgsql, .tsql
    Primary use: schema, stored procedures, views, queries, and migrations.

## Plan of Work

Begin by checking for repository-specific planning requirements. From the repository root, look for `PLANS.md`. If it exists, read it completely and update this ExecPlan if the file imposes additional conventions for directory layout, tests, commit style, or validation. Do not ask the user for clarification. Resolve any conflict by choosing the safer, more local, more testable implementation.

Create a new Python project at `tools/legacylift_search`. The package must be installable in editable mode with `pip install -e tools/legacylift_search`. Use a `src` layout so source code lives under `tools/legacylift_search/src/legacylift_search`. Add tests under `tools/legacylift_search/tests`.

Create the following files:

    tools/legacylift_search/pyproject.toml
    tools/legacylift_search/README.md
    tools/legacylift_search/src/legacylift_search/__init__.py
    tools/legacylift_search/src/legacylift_search/cli.py
    tools/legacylift_search/src/legacylift_search/config.py
    tools/legacylift_search/src/legacylift_search/discovery.py
    tools/legacylift_search/src/legacylift_search/chunking.py
    tools/legacylift_search/src/legacylift_search/languages.py
    tools/legacylift_search/src/legacylift_search/extractors.py
    tools/legacylift_search/src/legacylift_search/embeddings.py
    tools/legacylift_search/src/legacylift_search/store.py
    tools/legacylift_search/src/legacylift_search/vector_store.py
    tools/legacylift_search/src/legacylift_search/search.py
    tools/legacylift_search/src/legacylift_search/graph.py
    tools/legacylift_search/src/legacylift_search/indexer.py
    tools/legacylift_search/src/legacylift_search/models.py
    tools/legacylift_search/src/legacylift_search/profiles/extractors.json
    tools/legacylift_search/tests/fixtures/polyglot_repo/
    tools/legacylift_search/tests/test_config.py
    tools/legacylift_search/tests/test_discovery.py
    tools/legacylift_search/tests/test_extractors.py
    tools/legacylift_search/tests/test_store.py
    tools/legacylift_search/tests/test_search.py
    tools/legacylift_search/tests/test_cli_smoke.py

If the repository already has a root-level `pyproject.toml`, do not merge this package into it during the first implementation. Keep the tool isolated. Integration can happen later after the CLI works.

Create a sample manifest at the legacylift-ai repository root named:

    semantic-search.manifest.json

This file is the default configuration template. It is safe to commit because it contains no secrets. Per-repository copies are written into each target repo when `legacylift-search init-config --repo-root repos/<name>` runs, producing `repos/<name>/semantic-search.manifest.json`. The manifest points the indexer at the repository root being indexed, sets default ignore rules, configures chunking, identifies the embedding provider, and configures search ranking.

The manifest content should be:

    {
      "schema_version": 1,
      "project": {
        "name": "current-repository",
        "repo_roots": ["."],
        "include_globs": [
          "**/*.cs",
          "**/*.java",
          "**/*.py",
          "**/*.js",
          "**/*.jsx",
          "**/*.mjs",
          "**/*.cjs",
          "**/*.ts",
          "**/*.tsx",
          "**/*.cbl",
          "**/*.cob",
          "**/*.cpy",
          "**/*.copy",
          "**/*.pco",
          "**/*.sql",
          "**/*.ddl",
          "**/*.dml",
          "**/*.psql",
          "**/*.pgsql",
          "**/*.tsql"
        ],
        "exclude_globs": [
          "**/.git/**",
          "**/.svn/**",
          "**/.hg/**",
          "**/node_modules/**",
          "**/bin/**",
          "**/obj/**",
          "**/target/**",
          "**/dist/**",
          "**/build/**",
          "**/.venv/**",
          "**/venv/**",
          "**/__pycache__/**",
          "**/.pytest_cache/**",
          "**/.mypy_cache/**",
          "**/legacylift-docs/index/**",
          "**/.legacylift/**",
          "**/*.min.js",
          "**/*.bundle.js",
          "**/*.map",
          "**/*.lock",
          "**/package-lock.json",
          "**/yarn.lock",
          "**/pnpm-lock.yaml"
        ],
        "max_file_bytes": 2000000
      },
      "index": {
        "index_dir": "legacylift-docs/index/code-search",
        "sqlite_file": "index.sqlite",
        "chroma_dir": "chroma",
        "collection_name": "code_chunks",
        "reset_before_index": false,
        "store_full_chunk_text_in_sqlite": true
      },
      "chunking": {
        "target_tokens": 800,
        "max_tokens": 1400,
        "min_tokens": 80,
        "overlap_lines": 12,
        "prefer_ast_boundaries": true,
        "fallback_max_lines": 120
      },
      "embedding": {
        "provider": "qwen3",
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "dimension": 1024,
        "batch_size": 16,
        "normalize": true,
        "device": "auto"
      },
      "search": {
        "default_limit": 10,
        "vector_candidates": 40,
        "lexical_candidates": 40,
        "rrf_rank_constant": 60,
        "graph_neighbor_depth": 1,
        "snippet_radius_lines": 8
      },
      "languages": {
        "enabled": ["csharp", "java", "python", "javascript", "typescript", "cobol", "sql"],
        "profile_file": "tools/legacylift_search/src/legacylift_search/profiles/extractors.json"
      }
    }

The manifest loader must tolerate comments only if implemented explicitly. The first implementation should use strict JSON to avoid ambiguity.

Add the following package dependencies in `tools/legacylift_search/pyproject.toml`:

    typer
    rich
    pydantic
    pathspec
    chonkie
    chromadb
    sentence-transformers
    numpy
    networkx
    tree-sitter
    tree-sitter-language-pack
    pytest

The implementation may add `orjson` for speed, but it is not required. Do not require a GPU. The Qwen embedder should use whatever device `sentence-transformers` can use locally. The tests must use the deterministic hash embedder and must not download Qwen.

The CLI must expose these commands. All commands accept either `--repo-root <path>` (preferred — resolves config and index automatically from the repo) or explicit `--config` and `--index-dir` paths. When `--repo-root` is given, config defaults to `<repo-root>/semantic-search.manifest.json` and index defaults to `<repo-root>/legacylift-docs/index/code-search/`.

    legacylift-search init-config --repo-root repos/<name>
    legacylift-search index --repo-root repos/<name>
    legacylift-search validate --repo-root repos/<name>
    legacylift-search search "query text" --repo-root repos/<name> --limit 10
    legacylift-search symbols --name CustomerService --repo-root repos/<name>
    legacylift-search callers <symbol-id> --repo-root repos/<name> --depth 1
    legacylift-search callees <symbol-id> --repo-root repos/<name> --depth 1
    legacylift-search stats --repo-root repos/<name>
    legacylift-search dump-ast path/to/file.py --max-depth 6

The `dump-ast` command exists to de-risk parser profile work. It should print tree-sitter node kinds and line ranges for one file. It is especially useful for COBOL and SQL dialect differences.

## Concrete Steps

The `Concrete Steps` (build instructions) for the already-shipped milestones — the foundational build (Milestones 1–14) and Milestone 19 — have been moved to the companion archive `semantic-code-search-graph-index-additional-info.md`. They are not needed to continue current work; consult the archive only to reconstruct how a completed component was built. The steps below cover the milestones that are still active, paused, or upcoming.

### Milestone 17: Production Qwen3 embedding run against `repos/ctcm/ctcm-api`

Through Milestone 16, all real-repo validation has used `--embedding-provider hash`. The hash embedder produces deterministic, dimension-correct vectors but they encode no semantic meaning — they are reproducible hash buckets. This means the vector half of the RRF blend has been contributing essentially noise to ranking, and any observed search quality has come from the lexical FTS5 side. The Qwen production path has unit coverage (configuration, lazy model load, error message on load failure) but has never been exercised end-to-end on a non-trivial codebase.

This milestone closes that gap. It is primarily a validation exercise; no code changes are expected unless the run uncovers a bug.

Run the production embedding index:

    legacylift-search index --repo-root repos/ctcm/ctcm-api --reset

Do not pass `--embedding-provider`; the manifest default selects Qwen3-Embedding-0.6B. The `--reset` is required because the existing index (post-M15) was built with the hash embedder and Chroma enforces consistent dimensions per collection — the existing `vector_store` dimension-mismatch path will fire otherwise, and this milestone wants a clean Qwen-from-scratch build.

If Qwen model loading fails (no network access to HuggingFace cache, no GPU, insufficient memory, or sentence-transformers dependency issue), do not block. Record the exact error in Surprises & Discoveries together with the resolution path used by the next agent. The existing fallback message ("Use --embedding-provider hash for a local smoke test, or ensure the Qwen model is available to sentence-transformers.") remains the user-facing recovery.

Capture observations:
- Total wall-clock and per-phase wall-clock from `index.log` (M16 timestamps). Compare each phase against the M15+M16 hash-embedder cold run (cold reset 71m 22s; extract+chunk 63m 41s; chroma-upsert 6m 10s). Qwen will add real embedding compute; expect the chroma-upsert phase wall-clock to grow primarily because of embedding time on the producer side, not because Chroma fsync is slower.
- Final counts from `legacylift-search stats --repo-root repos/ctcm/ctcm-api`. File/chunk/symbol/ref/edge counts must match the M15 hash run; only the embedder metadata should differ.
- `embedder_name` and `embedding_dimension` in SQLite `index_metadata` must reflect Qwen3-Embedding-0.6B and its native dimension (1024 — same as the hash default, by manifest configuration), not the hash embedder.

Run the same query set used in the M14 retrospective so ranking quality is directly comparable:

    legacylift-search search "authentication authorization validation" --repo-root repos/ctcm/ctcm-api --limit 5
    legacylift-search search "provider eligibility validation" --repo-root repos/ctcm/ctcm-api --limit 5
    legacylift-search search "claim reserve task creation" --repo-root repos/ctcm/ctcm-api --limit 5
    legacylift-search search "calendar event repository" --repo-root repos/ctcm/ctcm-api --limit 5
    legacylift-search search "appeal case repository" --repo-root repos/ctcm/ctcm-api --limit 5

Record both the hash-embedder top-5 (from M14) and the Qwen top-5 in the Outcomes & Retrospective entry so the ranking-quality delta is auditable. Note where ordering changes meaningfully and where it does not. Note absolute scores, but expect them to remain small (RRF math is `1/(k+rank)`); the relative ordering is what matters.

Confirm `validate --repo-root repos/ctcm/ctcm-api` reports `Index is valid.` and `freshness: fresh`. Confirm `git status` shows no new tracked files under `repos/ctcm/ctcm-api/legacylift-docs/index/`.

If Qwen runs successfully but produces obviously poor ranking (e.g., top-5 unchanged from hash), do not patch the embedder — that is a Milestone 18 (reranker) signal rather than an M17 failure. Document the observation and proceed.

Update Progress after this milestone.

### Milestone 18: Add Qwen3-Reranker as an optional second-stage reranker

After Milestone 17 produces a real semantic-embedding baseline against `repos/ctcm/ctcm-api`, add cross-encoder reranking so a LegacyLift agent can request sharper top-K ordering when needed. RRF scores are small by design (`1/(k+rank)` with k=60) and absolute differentiation between top-5 results is poor on either embedding backend; a cross-encoder that re-scores `(query, chunk_text)` pairs jointly typically produces materially better top-5 ordering for code retrieval.

This is an additive feature behind a config flag — default off, no behavior change for existing callers.

Configuration changes (`SearchConfig` in `config.py`):

    rerank: bool = False
    rerank_top_k: int = 50
    rerank_model: str = "Qwen/Qwen3-Reranker-0.6B"

The `rerank_top_k` is the size of the candidate set the reranker re-scores; the `--limit` value passed to `search` still controls how many results the user sees. The reranker runs only on the top `rerank_top_k` from the existing RRF-blended list.

New module `reranker.py`:

    class Reranker:
        def __init__(self, config: SearchConfig) -> None: ...
        @property
        def name(self) -> str: ...
        def score(self, query: str, passages: list[str]) -> list[float]: ...
        def close(self) -> None: ...

    def create_reranker(config: SearchConfig) -> Reranker | None:
        # Returns None when config.rerank is False, so SearchEngine
        # can skip lazy load entirely on the cold path.

Implementation should mirror `QwenEmbedder`: lazy `sentence_transformers.CrossEncoder` load on first `score` call; on load failure, raise a `RuntimeError` whose message recommends setting `search.rerank: false` in the manifest or passing `--no-rerank`. Do not download models in tests; use a `FakeReranker` for unit and integration tests.

`SearchEngine.search` change:

    rrf_results = ... existing RRF-blended results ...
    if reranker is not None and rrf_results:
        candidates = rrf_results[: config.rerank_top_k]
        passages = [r.snippet for r in candidates]
        rerank_scores = reranker.score(query, passages)
        for r, rs in zip(candidates, rerank_scores):
            r.rerank_score = rs
        candidates.sort(key=lambda r: r.rerank_score, reverse=True)
        # Replace the top slice with the reranked order; trailing
        # results past rerank_top_k keep their RRF order.
        rrf_results = candidates + rrf_results[config.rerank_top_k :]
    return rrf_results[: limit]

Add `rerank_score: float | None = None` to the `SearchResult` model so reranker output is observable in CLI output. The Rich renderer should print the rerank score next to the RRF score when present (e.g., `score=0.0325 rerank=0.812 ...`) so users can see both signals.

CLI: add `--rerank/--no-rerank` flags to `legacylift-search search` for ad-hoc override of the manifest setting.

Tests in `tests/test_reranker.py`:
- `FakeReranker` returning deterministic per-passage scores; `SearchEngine` integration test confirming the reranked order replaces only the top `rerank_top_k` slice and that `--limit` still controls the output count.
- Config roundtrip: `Manifest` with `search.rerank: true` parses, defaults backfill correctly when omitted.
- CLI end-to-end on the polyglot fixture using the `FakeReranker` injected via a small dependency-injection seam (e.g., a `create_reranker` patch fixture).
- A unit test confirming `create_reranker` returns `None` when `config.rerank=False` so the cold path performs no model load.

The real Qwen3-Reranker is exercised manually against `repos/ctcm/ctcm-api`, not in CI:

    legacylift-search search "authentication authorization validation" \
      --repo-root repos/ctcm/ctcm-api --limit 5 --rerank

Repeat the same five queries used in M14 and M17. Record the reranked top-5 alongside both prior result sets so ranking quality is comparable across all three embedding configurations (hash → Qwen embeddings only → Qwen embeddings + Qwen reranker). Capture per-query wall-clock cost of the reranker step. Cross-encoder rerank on K=50 with a 0.6B model is typically sub-second on CPU; record the observed value.

If Qwen3-Reranker model loading fails for the same reasons listed in M17, document and proceed without blocking the implementation. The default-off flag means non-rerank search continues to work.

Update Progress after this milestone.

### Milestone 20: Hosted Amazon Bedrock embedding provider — DEFERRED VALIDATION runbook

**⏸ PAUSED — Part 2 only (2026-06-29) — reason: wrong question first.** Part 1 (embed-phase benchmark) is **complete**; Bedrock is the adopted production embedding path. Part 2 (the hash-vs-Bedrock retrieval-quality A/B) is **paused** because it answers "should we adopt Bedrock *for quality*?" before the prior, higher-order question is settled: **is the semantic-code-search + code-graph index helpful *at all* relative to LegacyLift's existing `fact-graph` skill?** Tuning the embedder's ranking is premature until the index has earned its place against the incumbent. The Part-2 runbook below stands as-is and resumes once Milestone 21 establishes that the index adds value. See **Milestone 21** for the comparison that now precedes this.

**Status (2026-06-26):** The M20 *code* is shipped and unit-tested (148 passing, `tests/test_bedrock_embedder.py`), and the provider is verified live end-to-end on the small `polyglot_repo` fixture (25/25 vectors, ranked search through the Bedrock query embedding). Two acceptance pieces were deferred because they require a multi-tens-of-minutes run against the real C# repo. **This section is the self-contained runbook for a fresh agent to complete them** (Part 2 now gated behind Milestone 21 per the pause above). It absorbs the long-deferred Milestone 17 retrieval-quality goal — there is no separate "benchmark milestone"; this *is* M20's validation gate.

**Goal:** (1) record the Bedrock embed-phase wall-clock on `repos/ctcm/ctcm-api` against the local-Qwen ~80-min estimate; (2) capture the retrieval-quality A/B (hash vs. Bedrock) on the pinned five-query set, so adoption-for-quality is auditable (Titan is general-purpose, not code-specialized).

**Preconditions / environment (all confirmed 2026-06-26 — re-verify, don't assume):**
- **Run in a fresh agent context on an idle host.** No GPU or idle-CPU requirement (embedding is network-bound), but a full cold index of this repo also re-runs the `[extract+chunk]` phase (~44 min parallelized per M19), so budget for that too — see the resume note below.
- **`AWS_BEARER_TOKEN_BEDROCK`** must be in the environment. It is present in `.claude/settings.local.json` (132-char bearer token) and is loaded into the session env automatically; confirm with a non-printing length check (`test -n "$AWS_BEARER_TOKEN_BEDROCK"`). Do NOT echo or store the token. If absent, the embedder raises a clear error naming the var — surface it and stop.
- **Region is `us-east-2`** (the manifest default for `provider="api"`); do NOT rely on `AWS_REGION` (Claude Code sets it to `us-east-1` for its own model access).
- **boto3 must be installed in the package venv.** It is the `aws` optional extra and is NOT in the base deps. Install once:

      tools/legacylift_search/.venv/Scripts/python.exe -m pip install "boto3>=1.40" -q

  (or `pip install -e tools/legacylift_search[aws]`). On this host boto3 1.40.x is confirmed working against live Bedrock.

**Step 1 — point the manifest at Bedrock.** Edit `repos/ctcm/ctcm-api/semantic-search.manifest.json` `embedding` block to:

    "embedding": {
      "provider": "api",
      "model": "amazon.titan-embed-text-v2:0",
      "dimension": 1024,
      "region": "us-east-2",
      "max_concurrency": 16,
      "normalize": true
    }

`dimension` MUST stay 1024 (matches the existing Chroma collection and the verified Titan output). `max_concurrency=16` is the measured sweet spot — 32 hit throttling and was *slower*. Switching providers requires `--reset` per the dimension-consistency rule (the prior index is hash@1024; a same-dim switch still needs `--reset` because the embedder identity changes). Consider keeping `chunking.embed_min_tokens=80` (the M17b-chosen filter) to cut the embed count 76% — but note that changing it also forces `--reset`, which is already happening here.

**Step 2 — cold index against live Bedrock.** Prefer `run_in_background=true` with periodic polling of `index.log`:

    py -3.12 -m legacylift_search.cli index --repo-root repos/ctcm/ctcm-api --reset

The `[chroma-upsert] progress ...` lines stream rate/ETA to `index.log` so the run is observable. **Projected embed phase** at the measured ~94 ms/chunk @ concurrency=16: ~92 min for all 58,677 chunks, or ~22 min for the filtered 14,093 (before text-dedup, which cuts further). **If the harness wall-clock cap kills the run mid-embed**, the partial index is consistent (vectors_present checkpointed per batch); finish it with repeated calls — this is the whole point of the resumable design:

    py -3.12 -m legacylift_search.cli backfill-vectors --repo-root repos/ctcm/ctcm-api

Each `backfill-vectors` call embeds only the chunks still missing from Chroma and is safe to call repeatedly until `vectors_upserted == chunk_count`. (Do NOT rely on a plain `index` rerun to finish it — under the M15 skip-on-unchanged fast path a second `index` sees all files unchanged and feeds the embedder nothing.)

**Step 3 — confirm completion.**

    py -3.12 -m legacylift_search.cli validate --repo-root repos/ctcm/ctcm-api
    py -3.12 -m legacylift_search.cli stats --repo-root repos/ctcm/ctcm-api

`validate` must report `Index is valid.`, `freshness: fresh`, and NO `WARNING: vector coverage incomplete`. `stats` must show `embedding provider api:bedrock:amazon.titan-embed-text-v2:0`, dimension 1024, and file/chunk/symbol/ref counts matching the M15/M19 hash runs (4,715 / 58,677 / 58,614 / 135,973 — only the embedder metadata should differ). Confirm `git status` shows no new tracked files under `repos/ctcm/ctcm-api/legacylift-docs/index/`.

**Step 4 — retrieval-quality A/B (the deferred M17 goal).** This compares Bedrock vs. hash on the SAME pinned five queries. **Read this carefully — the hash baseline is NOT already on disk and only one of the five queries was ever recorded against hash, so you must regenerate the hash side yourself.**

Two facts that shape the procedure:
- **The ctcm-api index is now fully Bedrock-embedded** (Part 1 left it that way on purpose). There is no hash index in `repos/ctcm/ctcm-api/legacylift-docs/index/code-search/` anymore.
- **The recorded M14 hash baseline covers only ONE of the five queries** (`authentication authorization validation` → top-5 `SpecialClaimManager.CreateReserveTask`, `IAppealCaseRepository`, `IClaimManager`, `IClaimRepository`, `ICalendarEventRepository`, scores 0.0154–0.0164). The other four queries were never run against hash, so there is no baseline to diff against for them.

Therefore: build a hash index **into a separate `--index-dir`** so it coexists with the Bedrock index (do NOT `--reset` the Bedrock index — that would destroy Part 1's ~3-min-of-Bedrock + ~59-min-of-extract work). Both `index` and `search` accept `--index-dir` and `--embedding-provider`.

4a. **Build the side-by-side hash index** (separate dir; reuses the same manifest, so same chunking/filter — only the embedder differs). The extract+chunk phase re-runs here (~44–59 min on this host) because it's a fresh index dir; the hash embed phase is fast:

    py -3.12 -m legacylift_search.cli index \
      --repo-root repos/ctcm/ctcm-api \
      --index-dir repos/ctcm/ctcm-api/legacylift-docs/index/code-search-hash \
      --embedding-provider hash --reset

  (`--embedding-provider hash` overrides the manifest's `api` provider for this index only; the manifest on disk stays on `api`.) The `code-search-hash` dir is under `legacylift-docs/index/`, which is gitignored, so it won't leak into git. Confirm with `validate --index-dir ...code-search-hash`.

4b. **Run all five queries against BOTH indexes.** Each `search` against the Bedrock index makes ONE live Bedrock `embed_query` call (same provider serves query-time embedding), so the host needs `AWS_BEARER_TOKEN_BEDROCK` for the Bedrock side; the hash side needs `--embedding-provider hash` to match its index:

    # Bedrock (default index dir, manifest provider=api)
    for Q in "authentication authorization validation" "provider eligibility validation" "claim reserve task creation" "calendar event repository" "appeal case repository"; do
      py -3.12 -m legacylift_search.cli search "$Q" --repo-root repos/ctcm/ctcm-api --limit 5
    done

    # Hash (separate index dir + matching provider)
    for Q in "authentication authorization validation" "provider eligibility validation" "claim reserve task creation" "calendar event repository" "appeal case repository"; do
      py -3.12 -m legacylift_search.cli search "$Q" \
        --repo-root repos/ctcm/ctcm-api \
        --index-dir repos/ctcm/ctcm-api/legacylift-docs/index/code-search-hash \
        --embedding-provider hash --limit 5
    done

  (Windows note: if the `for ... ; do` bash loop is awkward in the harness shell, just run the ten `search` invocations individually — five queries × two indexes.) Capture the top-5 (path:line, symbol, score) for every query under both embedders. The single recorded M14 hash result above is a cross-check that your regenerated hash index matches the historical baseline for that query; the other four hash results are newly generated here.

4c. **Cleanup**: once results are captured, delete the throwaway hash index dir (`rm -rf repos/ctcm/ctcm-api/legacylift-docs/index/code-search-hash`) so only the production Bedrock index remains. It was gitignored, so there's nothing to revert in git.

**Step 5 — write the Outcomes & Retrospective entry.** Part 1's timing is already recorded (see the Part-1 results subsection in the M20 retrospective); this entry is the Part-2 quality A/B. Record: for all five queries, the Bedrock top-5 alongside the hash top-5 (both regenerated in step 4b), noting where ordering changes meaningfully and where it doesn't (absolute RRF scores stay small by design — relative ordering is what matters). Cross-check that your regenerated hash result for `authentication authorization validation` matches the historical M14 top-5; flag it if it diverged (would indicate chunking/extraction drift since M14). If Bedrock ranking is no better than hash, that is a reranker signal (the paused Milestone 18), not an M20 failure — document and proceed. The manifest stays on `api` (Part 1 left it there and Bedrock is the adopted production path); note that, and confirm the throwaway `code-search-hash` index dir was deleted.

### Milestone 22: Add type-hierarchy (`inherits` / `implements`) edges to the graph

**Status: not started.** Through Milestone 20 the graph captures call, import, data-access, and framework/XML edges (see `GraphBuilder._edge_kind_from_ref` in `graph.py`: `calls`, `performs`, `executes_sql`, `executes_cics`, `uses_table`, `uses_column`, `imports`, `references`, plus the Hibernate/Spring/WebFlow mappings). It does **not** capture inheritance or interface implementation. This milestone closes that gap so the graph can answer "what are the subtypes/supertypes of X" — the relation family that dominates the v3 fact-graph output the documentation skills consume, and a prerequisite for the fact-graph Option-A refactor (`docs/exec-plans/pending/fact-graph-decision.md`).

The change touches four layers; keep each isolated so the JSON-profile philosophy (Decision 2026-05-08) holds as far as it can here. **Caveat (weaker than for calls):** the profile can name *which* node kinds carry base types (`inheritance_node_kinds`), but the extends-vs-implements *semantics* per node kind (`superclass`→inherits, `super_interfaces`→implements, C# `base_list`→ambiguous, TS clause-type discrimination) live in `SymbolExtractor` code, not the JSON. So a new language whose grammar lists its base types under an already-handled node kind is pure JSON; a language with a novel inheritance shape needs a small core-code edit to map its node types to kinds. (A cleaner future option: make `inheritance_node_kinds` a `{node_kind: kind}` map so the semantic is data-driven — deferred, not required for M22.)

**Node shapes verified via `dump-ast` (2026-07-13)** — the kinds below are confirmed against the installed grammars (c_sharp, java, python, typescript), not assumed. Two of them (Python, and the multi-base enumeration in Step 2) diverge from the obvious approach; the corrections are baked into the steps.

**Step 1 — extend the extractor profiles (`profiles/extractors.json`).** Add a new key `inheritance_node_kinds` to each profile. **Semantics differ from `call_node_kinds`:** these name the tree-sitter node types that, *when found as a child of a definition node*, hold the base-type list — the handler in Step 2 fires from the definition node and inspects these children, it does **not** match them as free-standing top-level nodes (that distinction is what makes Python safe — see below). Update `ProfileEntry` / the profiles loader (`extractors.py`) to accept and default the new key (`inheritance_node_kinds: list[str] = Field(default=[])`, so existing profiles without it stay valid). **Do NOT bump `schema_version`.** The `check_schema_version` validator (`extractors.py:65-73`) hard-requires `v == 1` and raises on anything else; because the new key defaults to `[]`, old profiles remain valid with no version change, so bumping is both unnecessary and breaking. If a future change genuinely needs a version bump, widen that validator in the same commit. Per-language, with the verified child structure:

- **csharp**: `base_list` — a comma-separated sequence after the `:`. Bare bases are `identifier` (verified: `base_list` over `BaseController`, `IClaimApi`, `IDisposable`), **but generic bases are `generic_name` and qualified bases are `qualified_name`** — neither is a bare `identifier`, so Step 2's name extraction must unwrap those two node kinds too (see Step 2). **Class-vs-interface is not syntactically distinguishable** → emit `inherits_or_implements`; Step 3 reclassifies from the resolved target's kind. **Re-verify with `dump-ast` before coding on both a `class Foo : IRepository<Claim>, System.IDisposable, Base` example AND a positional `record ClaimDto(int Id) : BaseDto(Id)` example** — the original 2026-07-13 sweep only covered bare-identifier bases. The positional-record case matters because its base is wrapped in a `primary_constructor_base_type` node (see Step 2), not a bare identifier, and `ctcm-api` DTOs are very likely positional records.
- **java**: two distinct nodes on a **class** — `superclass` (contains one `type_identifier`, the `extends` target → `inherits`) and `super_interfaces` (contains a `type_list` of `type_identifier`s, the `implements` targets → `implements`). A Java **interface** extending interfaces uses a *third* node, `extends_interfaces` (also a `type_list`) on `interface_declaration` → `inherits`; include it in `inheritance_node_kinds` so interface-extends-interface is not missed. **Distinction is syntactic — no resolution needed to classify.**
- **typescript**: `class_heritage` wraps `extends_clause` (→ `inherits`) and `implements_clause` (→ `implements`), each holding its own identifier/`type_identifier` children. Interfaces use `extends_type_clause` on `interface_declaration` (interface-extends-interface → `inherits`). **Syntactic.**
- **javascript**: `class_heritage` with an `extends` clause only (no interfaces) → `inherits`.
- **python**: the `class_definition` node's **`superclasses` field**, whose node type is `argument_list` → all bases become `inherits` (no interface concept). **⚠️ `argument_list` is the SAME node type Python uses for ordinary call arguments** — matching it by bare node type would turn every function call into a false inheritance edge. The handler MUST reach it via `class_definition.child_by_field_name("superclasses")` (or gate on `parent.type == "class_definition"`), never by a top-level `node.type == "argument_list"` test. This is why Step 2's handler is anchored on the definition node, not on a generic node-kind sweep like the call-ref path.
- **cobol / sql**: none — leave `inheritance_node_kinds: []`.

Add matching `fallback_patterns.inheritance` regexes for the regex path (parse failure / no parser only — never the primary path for these languages): C# `\bclass\s+\w+\s*:\s*([\w\.,<>\s]+?)(?:\bwhere\b|\{|$)` (the trailing guard avoids swallowing a `where T : IComparable` generic constraint, which also contains a colon), Java `\b(extends|implements)\s+([\w\.,<>\s]+)` (the keyword is a **capturing** group, not `(?:…)`, so the split-emit loop below can assign `inherits` vs `implements` per match from the captured keyword — a non-capturing group would force every Java fallback base to the ambiguous kind, defeating the one advantage Java fallback has over C#), Python `\bclass\s+\w+\s*\(([\w\.,\s]+)\)`, TS/JS `\b(?:extends|implements)\s+([\w\.,<>\s]+)`. Each captured group is a comma-separated base-type list to split. **Two wiring changes are required for these regexes to be live, not dead config** (the current fallback machinery handles neither): (a) add an `inheritance: list[str] = Field(default=[])` field to the `FallbackPatterns` model (`extractors.py:25-29`) — Pydantic v2 **silently ignores** unknown JSON keys, so without the field the regexes load as nothing; (b) `_extract_fallback` (`extractors.py:557-648`) currently has only a `definitions` loop and a `calls` loop, each taking a single `_last_capture` per match — add a third loop that **splits the base-list capture on commas and emits one `SymbolRef` per base**, because a single capture holds the whole base list. Kind assignment differs by language and is driven off the match, not `_last_capture`: Java's two-group pattern yields the keyword (`extends`→`inherits` / `implements`→`implements`) in group 1 and the base list in group 2; C#/Python/TS single-list patterns can't tell extends from implements, so they emit `inherits_or_implements` (Python has no interfaces, so `inherits` is also acceptable there). Fallback fidelity is genuinely lower (it cannot reliably separate extends from implements in C#, and multi-line base lists escape a line-oriented regex) — acceptable only because inheritance-bearing languages hit fallback solely on parse failure. If the fallback split-emit loop is not worth the effort now, it is acceptable to ship M22 with tree-sitter-only inheritance and leave `fallback_patterns.inheritance` out entirely — but do NOT add the regexes to the JSON without the two changes above, or they will be silently inert.

**Step 2 — emit inheritance references (`SymbolExtractor._walk_tree` in `extractors.py`).** This is a **dedicated handler fired when a definition node is visited**, not an addition to the generic `node.type in call_kinds` ref path (which extracts exactly one name via `_extract_name` and would therefore drop all but the first base — verified: `dump-ast` shows `_extract_name` returning only `BaseController` from a three-base `base_list`). **Do NOT hardcode the anchor to `class_declaration`/`class_definition`/`interface_declaration`** (code-review finding, 2026-07-13): C# `record_declaration` and `struct_declaration` also carry a `base_list` (`record ClaimDto : IEquatable<ClaimDto>`, `struct Foo : IComparable`), and both are in the C# `definition_node_kinds` (`extractors.json:8-10`) — `ctcm-api` DTOs are very likely records, so a class/interface-only anchor would silently drop their inheritance. Instead, fire on **any** definition node (`node.type in def_kinds`, which the walk already tests at `extractors.py:411`) and act only if one of its children's `type` is in the profile's `inheritance_node_kinds`. That naturally covers class/interface/record/struct without enumerating them and keeps the JSON-profile philosophy intact. Having located its inheritance children per the profile, **enumerate every base-type identifier and emit one `SymbolRef` each** (reusing the `SymbolRef` model unchanged):
- `name` = each base type's plain identifier, stripping generic args (`IRepository<Claim>` → `IRepository`) and qualifiers (`System.IDisposable` → `IDisposable`, to match the plain-name resolution index). **Do not iterate only `identifier`/`type_identifier` children** — that drops the common C# generic and qualified bases (finding from the code review: `IRepository<Claim>` is a `generic_name` node, `System.IDisposable` is a `qualified_name` node, neither a bare `identifier`). Instead, for each base-list child that is a base-type node, unwrap by kind: `identifier`/`type_identifier` → use text directly; `generic_name` → take its inner name identifier (drop the `type_argument_list`); `qualified_name`/`member_access`/Python `attribute` → take the last segment; **C# `primary_constructor_base_type` → descend to its inner type node and unwrap that by the same rules** (a positional `record ClaimDto(int Id) : BaseDto(Id)` wraps its base in this node — omitting it silently drops inheritance for exactly the record DTOs this milestone most wants, so it is not optional). Node kinds that are not base-type references (e.g. C# `predefined_type` from an `enum Foo : byte` underlying-type clause) are simply not in this whitelist and are skipped — that is the intended filter, not an oversight (see the Step 4 test note). Skip `,`/`:`/keyword tokens. For Java's `super_interfaces`/`extends_interfaces`, descend into its `type_list`; for TS, handle `extends_clause` and `implements_clause` separately.
- `kind` = `extends` for a class/`extends`-clause/`superclass` base, `implements` for an interface/`implements_clause`/`super_interfaces`/`extends_interfaces` base, and `inherits_or_implements` for C# `base_list` (ambiguous). Step 3 maps these to edge kinds.
- **Python dotted-base caution:** `attribute` is in Python's `call_node_kinds` (`extractors.json:98`), so a dotted base like `class Foo(mod.Base)` **already** emits a spurious generic `references` edge via the existing call-ref path; the new handler will add an `inherits` edge on top, double-counting that base. Bare-identifier Python bases are unaffected (`identifier` is not a call kind). Either dedupe the inheritance ref against a same-name/same-line `attribute` ref, or accept the duplicate and note it — Python is low-volume in the target repos, so this is a low-priority annoyance, not a blocker.
- `enclosing_symbol_id` = the deriving type's symbol id. During the existing DFS, `current_id` is already set to the enclosing definition's symbol id when its children are visited, so the subtype end of the edge comes for free — no extra lookup.
- `evidence` = the declaration line text; `range` = the base-type node range.
No new `Symbol` records and no `Symbol`-model change — inheritance is an edge, consistent with keeping the node model minimal.

**Step 3 — map to edge kinds (`GraphBuilder._edge_kind_from_ref` + `_resolve_callee`, `graph.py`).** Callee resolution is unchanged — base-type identifiers resolve against `all_symbols_by_name` exactly like call targets, inheriting the existing confidence tiers (0.85 unique / 0.70 same-language / 0.40 ambiguous / 0.30 unresolved). Add to `_edge_kind_from_ref`, ahead of the generic-call block:

    if ref_kind == "inherits_or_implements":
        # C# base_list: reclassify from the resolved target's kind when known;
        # when the base is external/unresolved (callee_kind is None), fall back
        # to the .NET interface-naming heuristic rather than defaulting to
        # inherits (see the paragraph below — most C# bases are external
        # framework interfaces).
        if callee_kind == "interface_declaration":
            return "implements"
        if callee_kind is not None:
            return "inherits"
        # unresolved: heuristic on the base-type name (add `import re` at the
        # top of graph.py — it currently imports only typing + models)
        return "implements" if re.match(r"^I[A-Z]", ref.name) else "inherits"
    if ref_kind == "implements":  return "implements"
    if ref_kind == "extends":     return "inherits"

**⚠️ Ordering and matching (code-review finding, 2026-07-13):** test the exact C# `inherits_or_implements` case **first** and use exact equality (`==`), **not** substring membership (`in`). `"implements" in "inherits_or_implements"` is `True`, so an `if "implements" in ref_kind` guard placed ahead of the C# branch would catch every C# base, return `implements` unconditionally, and render the reclassification below dead code — every C# base class would be mislabeled `implements`, silently defeating this step and breaking the Step 4 reclassification assertion. The Step 2 kinds are exactly `extends` / `implements` / `inherits_or_implements`, so substring matching buys nothing and only creates this hazard.

To reclassify the C# case you need the resolved target's `kind`, and **`build_edges` does not currently have it** (code-review finding): `_resolve_callee` (`graph.py:116-157`) returns only `(callee_symbol_id, confidence)` — a string id and a float — and the id string (`lang:path:qname:line`) does **not** encode `kind`, so the chosen `Symbol` is thrown away. Re-looking-up by name in `build_edges` is *unsafe* when there are multiple same-name candidates, because you would not know which one `_resolve_callee` actually picked (0.70/0.40 tiers). **The correct change is to widen `_resolve_callee` to also return the chosen `Symbol` (or just its `kind`)** — e.g. `(callee_symbol_id, confidence, callee_kind)` — and thread `callee_kind` into the reclassification: target `kind == "interface_declaration"` → `implements`, else `inherits`. **The reclassification lives in a *separate* method, `_edge_kind_from_ref(self, ref, language)` (`graph.py:167`), called at `graph.py:65` — so that method's signature must ALSO be widened to `_edge_kind_from_ref(self, ref, language, callee_kind)`, and `build_edges` must pass the new third element from `_resolve_callee` (resolved at `graph.py:60`, available before the edge-kind call at `:65`).** So this is two contained signature changes, not one: widen `_resolve_callee`'s return and widen `_edge_kind_from_ref`'s params. If unresolved (external base type — the common C# case for framework interfaces like `IDisposable`), `callee_kind` is `None` (the 0.30 no-candidate path, `graph.py:136`, returns no symbol) and the edge stays unresolved at confidence 0.30 per the preserve-unresolved-edges decision, with `callee_name` recording the base-type name for later refinement. **Do NOT blindly default the unresolved C# case to `inherits`** — in a real .NET app the *majority* of base-list entries are external framework interfaces (`IDisposable`, `IEnumerable<T>`, `ILogger<T>`, `IActionResult`, …), so an unconditional `inherits` default would mislabel most of them and badly skew the inherits/implements split. **Instead, for the unresolved C# case (`callee_kind is None`), apply the `^I[A-Z]` heuristic by default:** a base whose plain name matches `^I[A-Z]` → `implements` (the near-universal .NET interface-naming convention); otherwise → `inherits`. This is now part of the milestone, not optional. Resolved C# bases still reclassify from the real `callee_kind` (which is authoritative and overrides the heuristic); the heuristic only fills the gap where no repo symbol was found.

**Step 4 — surface and test.** These edges land in `graph_edges` automatically, so `callers`/`callees` traversal already returns them (a subtype appears as a "caller" of its base). No required CLI change; optionally add an `--edge-kind` filter to `callers`/`callees` (defaulting to all) so an agent can ask specifically for hierarchy edges, and note it in the README if added. **Edge-id note:** `GraphBuilder` builds `edge_id = edge:{caller}:{ref.name}:{start_line}:{edge_kind}` (`graph.py:69-71`) — it omits the base-type byte offset and target id, so two same-name bases on one declaration line collapse to one edge on upsert (e.g. `class Foo : IBar<A>, IBar<B>` after generic-stripping both → `IBar`). Language rules mostly forbid this (C# CS0695 bars implementing the same generic interface twice), so it is a corner case; if a test surfaces it, add `ref.range.start_byte` to the edge id. Extend `tests/test_extractors.py` (assert `inherits`/`implements` refs are produced for a C#, Java, Python, and TS fixture — add a small class hierarchy to `tests/fixtures/polyglot_repo/` if none exists; include a **generic and a qualified C# base** so the Step 2 unwrap is covered) and add a `graph`-level test asserting the edge kinds, the C# `inherits_or_implements`→`implements` reclassification against an in-repo `interface_declaration`, that an external/unresolved base produces a confidence-0.30 edge with a non-null `callee_name`, that an unresolved `^I[A-Z]` base is classified `implements` while an unresolved non-`I` base is `inherits` (the Step 3 heuristic), and — as a regression guard — that a C# `enum Foo : byte` produces **no** hierarchy edge to `byte` (the `predefined_type` filter), so a future widening of the Step 2 unwrap whitelist can't silently reintroduce enum-underlying-type noise as fake `inherits` edges.

**Step 5 — re-validate on `repos/ctcm/ctcm-api` and record.** Re-index with `--reset` — `legacylift-search index --repo-root repos/ctcm/ctcm-api --reset`. **A plain reindex will NOT work here** (code-review finding): the M15 skip-on-unchanged fast path (`indexer.py:252-314`) partitions files by **file-content SHA**, and editing `extractors.json` changes no source file's SHA and is covered by neither `source_set_sha256` nor `manifest_sha256`. So a non-`--reset` run classifies every file as unchanged, reloads the *old* (pre-inheritance) symbols/refs from SQLite for the graph rebuild (`indexer.py:504-556`), and emits **zero** new `inherits`/`implements` edges while reporting success. `--reset` forces full re-extraction under the new profile. (This does re-embed vectors; that is the price of a profile change until/unless a profile-hash is folded into the freshness check as a follow-up — worth noting as a future improvement, since profile edits are otherwise invisible to staleness detection.) Confirm via `stats` that `graph_edges` now contains `inherits` and `implements` kinds. Sanity-check the **combined** magnitude against the v3 fact-graph baseline for the same repo (`inherits` 1,826 + `implements` 884 ≈ 2,710 total hierarchy edges; expect the same order of magnitude, not an exact match — different resolvers). **Do not treat the per-kind split as a pass/fail target:** the inherits-vs-implements ratio can legitimately diverge from fact-graph because most C# bases are external framework interfaces resolved via the `^I[A-Z]` heuristic (Step 3), not by symbol lookup — so total hierarchy-edge count is the meaningful cross-check, and a per-kind split that differs from 1,826/884 is expected, not a regression. Also record the unresolved-base ratio (confidence-0.30 edges) so the heuristic's coverage is visible. Chunk/symbol counts must be unchanged; only edge count rises. Record before/after edge-kind counts and any surprising unresolved-base ratio in Outcomes & Retrospective.

---

### Milestones 23–25: Extract the remaining high-value first-class AST nodes

**Status: not started.** M22 closes the inheritance gap; a `dump-ast` sweep on 2026-07-13 (C#/Java/Python/TS/SQL) confirmed several other first-class nodes tree-sitter hands us that the profiles currently ignore, each mapping to a LegacyLift consumer. These three milestones extract them. All node kinds below are **verified via `dump-ast`**, not assumed. They build on M22's pattern (extend `extractors.json` → handler in `SymbolExtractor` → map in `GraphBuilder` → tests), so read M22 first — **but M22 only added new `SymbolRef`s + `GraphEdge`s, which already have a channel through the pipeline. Facts are a brand-new data type with no channel today; the Shared plumbing prerequisite below must land before any of M23–25 can persist a single fact.**

**Shared architectural decision — where attribute-facts live (settle before M23).** These milestones split into two shapes:
- **Relational** (symbol → symbol): field/property type references, DTO types in signatures, FK/`@JoinColumn`. These fit the existing `graph_edges` table — new `edge_kind`s only. They are emitted as `SymbolRef`s (new `kind`) during extraction and mapped to edges in `GraphBuilder`, exactly like M22 inheritance, so they inherit M22's plumbing for free. **Silent-default hazard — each new ref `kind` MUST get an explicit branch in `_edge_kind_from_ref` (`graph.py`).** That function's final fallthrough is `return "references"` (`graph.py:279`), so a new ref `kind` with no matching branch still produces an edge — just mislabeled `references`. The edge *count* rises exactly as expected, so any validation that only checks ref/edge totals passes while the actual deliverable (the new typed edges) is missing. M22 added explicit `extends`/`implements`/`inherits_or_implements` branches for this reason; M23–25 must do the same for `foreign_key`, `associates`, `accepts_dto`, `returns_dto`, `has_field_of_type`, `exposes_endpoint`, etc., and the tests/validation MUST assert **per-`edge_kind` counts**, never just the total.

  **Traversal-pollution hazard — `callers`/`callees` do NOT filter by `edge_kind` today, so these new edge kinds flood the call graph (land the fix in M25).** The store methods are named **`callers` (`store.py:739`)** and **`callees` (`store.py:777`)** — note there is **no `get_` prefix** (grepping `get_callers` finds nothing), and both already take the signature `(self, symbol_id: str, depth: int)`. Each is a bare `SELECT ... FROM graph_edges` — `callers` filters `WHERE callee_symbol_id = ?` (`store.py:756`, incoming edges) and `callees` filters `WHERE caller_symbol_id = ?` (`store.py:794`, outgoing edges) — with **no `edge_kind` predicate**, so they return every edge touching the symbol. M22 already mixed `inherits`/`implements` into the results; M25 adds `associates`/`has_field_of_type`/`accepts_dto`/`returns_dto`, so `callers <PopularDtoId>` would return every field/param/return that *mentions* the type — potentially hundreds of rows — intermixed with actual callers, changing what the command means (the tool's stated purpose is call-graph traversal, see Purpose §). The CLI already renders `edge_kind` as a column (`cli.py:599` callers, `cli.py:643` callees), so kinds are distinguishable but not filterable. **As part of M25, add an optional `--edge-kind`/`--kind` repeatable filter to the `callers`/`callees` commands and thread an `edge_kinds: list[str] | None = None` predicate into `SQLiteStore.callers`/`callees`** — add it *after* the existing `depth` param (`callers(self, symbol_id, depth, edge_kinds=None)`), keep the default None = current all-kinds behavior so nothing breaks, and when supplied add `AND edge_kind IN (...)`. **Note the `depth` param is currently a no-op** — both `SQLiteStore.callers` (`store.py:739`) and `callees` (`store.py:777`) document it as *"currently ignored; returns direct callers only"* and issue a single non-recursive `SELECT`, so today the filter is just one `AND edge_kind IN (...)` predicate on that one query. There is no multi-hop traversal to thread it through yet. **Forward-looking caveat (only if/when `depth` is actually implemented as a recursive traversal):** the predicate must be applied at *every* hop, not just the first — otherwise a filtered query would still follow type-association edges once it is one hop deep, re-polluting the result the filter is meant to clean. **Second site — do not miss it:** the `callers` **CLI command** carries its own *inline* fallback `SELECT` for unresolved-by-name edges (`cli.py:564–591`, `WHERE callee_symbol_id IS NULL AND callee_name = ?`), which also lacks an `edge_kind` predicate; the same filter must be applied there or filtered queries will still leak type-association edges through the fallback path. At minimum, if the filter is deferred, the M25 retrospective MUST document the semantic shift so a call-graph query returning type-association edges reads as expected, not a bug.
- **Attribute-facts** (symbol → predicate → value, no target symbol): `http_method=GET`, `requires_auth`, `is_required`, `max_length=50`, column type/nullability, enum values. These do **not** fit `graph_edges` (there is no target symbol) and there is **no facts store today**.

Recommendation: add a new SQLite table `symbol_facts` — deliberately fact-graph-shaped. This is the point where Layer 0 begins to absorb what fact-graph calls "facts" (see `docs/exec-plans/pending/fact-graph-decision.md` §5 and the Option-A discussion); doing it here, deterministically from AST nodes, is strictly better than re-deriving it with an LLM. Alternative (rejected): a JSON blob column on `symbols` — not independently queryable, no evidence/confidence per fact. Expose `symbol_facts` through a new `facts --predicate <p>` / `facts --symbol <id>` CLI command.

> **De-scoped (was in the original recommendation): "facts as Chroma chunk metadata."** Facts attach to *symbols*; Chroma metadata attaches to *chunks*, written in a much later phase (`Indexer._embed_and_upsert`). Worse, the embed low-value filter + text-dedup (`embed_filter.py`) mean many chunks never reach Chroma at all, so a `http_method` chunk-metadata filter would be silently incomplete. The deliverable is the `symbol_facts` table + `facts` CLI command; chunk-metadata projection is a **future, optional** enhancement, not part of M23–25.

#### Shared plumbing prerequisite (land before M23 — the biggest gap in the original plan)

The M22 recipe ("extractors.json → `SymbolExtractor` → `GraphBuilder` → tests") is **not sufficient for facts**. Since **M19**, extraction runs in a `ProcessPoolExecutor` and the *only* data that crosses the process boundary is the picklable `ExtractResult` (`extract_worker.py`), which carries `symbols / refs / chunks` — **not facts**. The main process is the sole SQLite writer and never re-parses. A fact produced inside `SymbolExtractor.extract` in a worker is therefore **silently discarded** unless every link in the chain below is added first. This is the single most important change in M23–25.

**Land and test this prerequisite as its own commit before writing any M23/M24/M25 extraction handler.** It is the highest-risk piece (the silent-discard failure mode is invisible to totals-only tests), and its **round-trip and orphan-guard** parts are fully testable in isolation with a synthetic fact: add the model/worker-field/schema/writer-call/CLI wiring, feed one hand-built `SymbolFact` through the pipeline end-to-end (worker → `ExtractResult` → batched writer → `symbol_facts` row → `facts` CLI), assert it survives, and feed a second fact with a bogus `subject_symbol_id` to prove the crash-guard (Step 4) drops-and-logs it. **Sequencing caveat — the two cleanup tests (Step 3, paths (a)/(b)) cannot be exercised by a purely hand-injected fact.** Cleanup test (a) requires re-extraction to emit a *different* fact when a file's content changes, and a synthetic fact injected outside the extractor does not vary with file content (a re-run re-injects the identical fact, so "old gone / new present" is untestable). Land the round-trip + orphan-guard here as the prerequisite commit; land the two cascade-cleanup tests **with M23** (the first real content-driven handler), or drive them from a small test-only handler that emits a content-derived fact. Only once a fact provably round-trips should the per-milestone handlers start emitting real facts. Track the prerequisite as a distinct deliverable from M23–25 so it can be marked done independently.

1. **Model** (`models.py`): add a `SymbolFact` model — fields `id`, `subject_symbol_id` (**required `str`, not nullable** — every fact M23–25 emits is anchored on a definition symbol; see the Step 3 cascade note for why this matters), `predicate`, `object` (str | None), `attributes` (dict | None, for extra args like a route template), `evidence`, `confidence`, `relative_path`, `start_line`, `language` — and add `facts: list[SymbolFact] = []` to `ExtractedFile`. **`subject_symbol_id` MUST be the emitting symbol's exact `.id` string, reused verbatim — never recompute it at fact-emission time.** The handler already has the `Symbol` object in hand (facts fire on the same definition node that produced the symbol), so read `symbol.id` off it. Recomputing risks a one-character drift from `SymbolExtractor`'s canonical id builder, which — because `subject_symbol_id` is a `NOT NULL` FK checked IMMEDIATE — would make `upsert_facts` raise and abort the run (see the Step 4 crash-guard). Deterministic AST-derived facts get **`confidence = 1.0`** (unlike resolver-scored edges); reserve lower confidence for any heuristic fact. **`evidence` is `NOT NULL` (Step 3), so every handler MUST populate it consistently — use the trimmed source text of the annotation/column/signature node the fact was derived from (the same convention `SymbolRef` uses), never an empty string; a mix of empty-string and node-text evidence across handlers is a silent data-quality regression.** Deterministic `id` — **`fact:<subject_symbol_id>:<predicate>:<object>:<start_line>`** — so re-extraction is idempotent and dedupe-by-id works like symbols/refs/edges. The id is **opaque** — it is only ever compared for equality / used as a PK, never parsed back into fields — so a free-text `object` containing `:` or `/` (route templates, annotation args) is harmless. **The `object` is load-bearing in the id, not decorative:** several predicates are multi-valued *on a single line* — a Java `throws IOException, SQLException` and a single-line `enum Status { Open, Closed, Void }` (`has_enum_value`) each emit multiple facts with identical `subject`/`predicate`/`start_line`. An id keyed only on those three would collapse them to one and silently drop the rest. Where `object` is None (a bare `requires_auth` fact), it contributes an empty segment, which is fine because such predicates are single-valued per symbol. **Invariant to preserve:** this only holds while every None-`object` predicate stays single-valued per (subject, start_line). If a future None-`object` predicate ever becomes multi-valued on one line, two facts would collapse to one id — so any new None-`object` predicate must either be single-valued per symbol or carry a disambiguating `object`.
2. **Worker boundary** (`extract_worker.py`): add `facts: list[SymbolFact] = []` to `ExtractResult` and populate it from `extracted.facts` in `_extract_with`, so facts survive the pickle across the pool boundary. Workers must still never raise — facts extraction lives inside the same `try` that already guards `extractor.extract`.
3. **Schema** (`store.py`): create `symbol_facts(id TEXT PRIMARY KEY, file_id INTEGER NOT NULL, subject_symbol_id TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT, attributes TEXT, evidence TEXT NOT NULL, confidence REAL NOT NULL, language TEXT NOT NULL, relative_path TEXT NOT NULL, start_line INTEGER NOT NULL, FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE, FOREIGN KEY(subject_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE)`. **The `file_id` FK is the load-bearing one for M15 incremental correctness — get its mechanism right.** A changed file's stale facts are removed by the `INSERT OR REPLACE INTO repo_files` in `upsert_files` (`indexer.py:302`), which runs **before** the extract/writer loop and, on the unique-`relative_path` conflict, deletes the old `repo_files` row and cascades through `symbol_facts.file_id` — the *same* mechanism M15 already documents for chunks/symbols/symbol_refs. **This cascade is empirically confirmed** to fire under `INSERT OR REPLACE` with `foreign_keys=ON` (a fresh AUTOINCREMENT id is assigned and the old row's `ON DELETE CASCADE` children are purged), so it is the primary cleanup path. **Which delete actually cleans changed-file facts — get the execution order right, or you will test the wrong thing.** The real cleanup happens at `upsert_files` (`indexer.py:302`), which runs for **all** changed files *before* the writer loop and cascade-purges each file's old chunks/symbols/refs/facts on the unique-`relative_path` REPLACE. `clear_reindex_artifacts` runs per-file **inside** the writer loop at **`indexer.py:429`** — i.e. *after* 302 has already emptied that file's `file_id`. Consequently both its existing `DELETE FROM symbols` cascade **and** the explicit `DELETE FROM symbol_facts` proposed below are **no-ops in the changed-file path** (they operate on the freshly-reassigned, empty `file_id`). This is not a reason to skip them — they are cheap insurance that keeps working if the REPLACE mechanism is ever weakened — but it means **the incremental test below must drive the real path (302), and a `clear_reindex_artifacts` unit test in isolation will NOT demonstrate fact cleanup** (its `file_id` is empty by then). Do not conclude cleanup works because that isolated test passes.

**Belt-and-suspenders (do this too):** add an explicit `DELETE FROM symbol_facts WHERE file_id = ?` to `clear_reindex_artifacts` — the method opens at `store.py:328`, but its two existing deletes are at **`store.py:357` (`DELETE FROM symbol_refs WHERE file_id = ?`) and `store.py:358` (`DELETE FROM symbols WHERE file_id = ?`)**, both **inside the `if file_id_row is not None:` guard (store.py:355) and keyed on the local `fid` variable (store.py:356), not the raw `relative_path`.** Place the new `symbol_facts` delete inside that same guard, using `fid`, **before** the `symbols` delete (store.py:358) so it does not depend on the `subject_symbol_id` cascade firing first. (`subject_symbol_id` stays `NOT NULL` regardless: a NULL-subject fact would be reachable by neither the `symbols` cascade nor a future weakening of the `upsert_files` REPLACE, and would leak.) For **deleted** files, `delete_file_artifacts` (`store.py:982`) drops the `repo_files` row and the **direct** `repo_files → symbol_facts` `file_id` cascade removes the facts — this is a single-hop cascade (not a chain through `symbols`), so it is already robust and needs no new code; note it here so the asymmetry with `clear_reindex_artifacts` (explicit delete there, cascade-only here) reads as deliberate, not an oversight. In **all** paths, cleanup depends on `PRAGMA foreign_keys=ON` (which `migrate()` already sets at `store.py:156`) — without it, neither `INSERT OR REPLACE` nor `ON DELETE CASCADE` fires and facts silently accumulate. Add an `ix_symbol_facts_predicate` and `ix_symbol_facts_subject` index. Add `upsert_facts` mirroring `upsert_refs` — whose real signature is `def upsert_refs(self, source_file, refs, commit: bool = True)` at **`store.py:500`**, i.e. the parameter **defaults to `True`** and the writer loop passes `commit=False` explicitly. Match that exactly: declare `def upsert_facts(self, source_file, facts, commit: bool = True)` (serialize `attributes` via `json.dumps`, `object` may be NULL) and pass `commit=False` at the writer-loop call site (Step 4) so facts join the batched transaction — **do not invert the default to `False`**, or a direct caller that relies on the mirror-of-`upsert_refs` behavior will silently stop committing. Also add a `facts_by_predicate` / `facts_for_symbol` query pair for the CLI. **Test the cleanup on BOTH real paths explicitly**: (a) *changed file* — index → edit an annotated file so a fact changes → plain reindex (no `--reset`) → assert the old fact is gone and only the new one remains (this pins the `upsert_files` cascade at 302, the one thing most likely to regress silently); and (b) *deleted file* — index → delete an annotated file → reindex → assert its facts are gone (pins the `delete_file_artifacts` `file_id` cascade, a genuinely different route).
4. **Writer loop** (`indexer.py`): call `store.upsert_facts(source_file, res.facts, commit=False)` right after `upsert_refs` (indexer.py `458`), so facts join the **M19 batched `commit_batch_files` transaction** — do not add a self-committing write here (it would break the batching invariant). **Ordering invariant (do not reorder):** `upsert_facts` in the loop runs *after* `upsert_files` (`indexer.py:302`), so the fresh facts are written after the REPLACE-cascade has already purged the file's old facts; and it runs *after* `upsert_symbols` (`indexer.py:457`) in the same iteration, so the `subject_symbol_id` FK target already exists (required with `foreign_keys=ON`). Facts are written during the extract phase only; they do **not** participate in the graph-rebuild phase, so the M15 partial-reindex path needs no facts-specific logic beyond the FK cascade above (unchanged-file facts are simply left intact).

   **Crash-guard — a dangling `subject_symbol_id` will abort the whole run, not just skip a fact (do not omit).** `symbol_facts.subject_symbol_id` is a `NOT NULL` FK checked IMMEDIATE, so if `upsert_facts` is ever handed a fact whose subject is not among the symbols persisted by `upsert_symbols` in this same transaction, the INSERT raises `sqlite3.IntegrityError` **in the sole writer**, killing a ~100-minute cold index at the write step (workers never raise — `extract_worker.py` — but the writer is unguarded). Reusing the symbol's exact `.id` (Step 1) makes this shouldn't-happen, but "shouldn't" is not "can't" (a fact emitted on a node that didn't become a persisted symbol; a symbol dropped by dedup; a future id-builder change). Defend at the boundary by **wrapping each fact's `INSERT` in `try/except sqlite3.IntegrityError`**: on the FK violation, `_log` `FACT_ORPHAN <path>: <predicate> subject=<id>` and `continue` to the next fact rather than letting the exception propagate to the sole writer. **Use try/except, not a pre-check set-membership test, and keep the Step 3 signature intact (`def upsert_facts(self, source_file, facts, commit: bool = True)` — no symbols parameter).** A pre-check built from `res.symbols` would (a) require deviating from the mandated mirror-of-`upsert_refs` signature or an extra `SELECT id FROM symbols WHERE file_id = ?` per file, and (b) miss the dedup-dropped-symbol case, because `res.symbols` is the *pre*-upsert list and can contain an id that the `INSERT OR REPLACE` collapse left absent from the table. The try/except catches the actual DB state, needs no symbols set, and adds no signature change. (Note: because the FK is checked IMMEDIATE, the failed `INSERT` is a per-statement error inside the still-open batch transaction and does not roll back the batch — the loop simply moves on.) **Test:** feed `upsert_facts` a fact with a subject id that no symbol row carries and assert the run completes, the orphan is logged, and valid facts in the same batch are still written.

**The `file_id` FK has a *different* failure mode — silent drop, not crash — and it is by-design.** `symbol_facts` has two `NOT NULL` FKs: `subject_symbol_id` (crash-guarded above) and `file_id`. Because `upsert_facts` mirrors `upsert_refs`, it resolves `file_id` via `_get_file_id(source_file.relative_path)` and — like `upsert_refs` (`store.py:509–510`) — **silently returns/skips when that lookup is None** rather than raising. This is the intended, ref-consistent behavior: `upsert_files` (`indexer.py:302`) runs for all changed files *before* the writer loop, so `file_id` is always present by the time facts are written, and a missing `repo_files` row is a shouldn't-happen that mirrors how refs already behave. Do **not** add a crash-guard for `file_id` (that would diverge from `upsert_refs`); just be aware the two FKs fail differently — `subject_symbol_id` raises (hence the try/except), `file_id` silently no-ops (inherited from the mirror).
5. **Stats/validate/CLI**: add `fact_count`. **There are FOUR touch points, not three — miss any one and `fact_count` silently fails to surface** (the exact bug this note guards against): (1) the `store.py:85` `IndexStats` model returned by `store.stats()` — add the field and a `SELECT COUNT(*) FROM symbol_facts`; (2) the `indexer.py:47` `IndexStats` model (the `index` run summary) — add the field and populate it; (3) the `index` command's **run-summary render block** (`cli.py:117–124`, the `table.add_row(...)` group that renders the *indexer* stats — the `graph_edge_count` row is `cli.py:121`, mid-block, with `embedder`/`embedding_dimension`/`index_dir` following at 122–124, so add the `fact_count` row anywhere in that group, e.g. right after 121) — add a `fact_count` row; and (4) the `stats` command's render block (`cli.py:680–684`, where `table.add_row("graph edges", …)` is `cli.py:684`, followed by `languages`/`embedding provider`/… at 685–698, that renders the *store* stats) — add a `facts` row. Touch points (1)+(4) and (2)+(3) are the two model→render pairs; both pairs must be updated. Then wire the new `facts` command in `cli.py` (reuse the `cli_helpers` `--repo-root`/`--config`/`--index-dir` resolution pattern).

**`schema_version` policy (unchanged from M22):** the profiles file is at `tools/legacylift_search/src/legacylift_search/profiles/extractors.json` (under `profiles/`, **not** the package root — all `extractors.json` references below mean that path). New keys added by M23–25 (`annotation_semantics`, any new `*_node_kinds`) are added to `ProfileEntry`/`FallbackPatterns` **with empty defaults matching each key's type (`annotation_semantics` is a name→intent map, so default `{}`, NOT `[]`; the `*_node_kinds` lists default `[]`) and NO `schema_version` bump** — the validator hard-requires `schema_version == 1` (`extractors.py`), and Pydantic drops unknown JSON keys, so a bump would gratuitously invalidate existing snapshots. Same trade-off M22 documented.

**`--reset` is MANDATORY for every one of M23–25 (do not skip — this bit M22).** All three change extractor profiles and/or extraction logic but change no file's SHA, so the M15 skip-on-unchanged fast path skips every file and produces **zero** new facts/refs/edges on a plain reindex. M22's graph-only rebuild shortcut (rebuild `graph_edges` over *already-stored* refs, no re-extraction) does **NOT** apply here: M23–25 facts and relational refs do not exist in SQLite until files are re-extracted. Each validation run below therefore requires `index --reset` (a full cold re-extraction), then `backfill-vectors` to restore the Bedrock vectors the `--reset` wiped (per the M20/M22 pattern).

> **Efficiency note (accepted cost, not a blocker):** M23 and M25 do not change chunk text — only facts/refs/edges — yet `--reset` wipes Chroma and forces `backfill-vectors` to re-embed *every* chunk purely to add data that never touches the vector store. On `ctcm-api` that is ~17k Bedrock calls (~4 min at the M20-measured ~13 ms/chunk), so it is tolerable today only because Bedrock is fast; on a slower/local embedder it would be pure waste. The clean fix is a future `--reextract-only` mode (re-run extraction over all files, rebuild graph, but leave Chroma untouched since chunk ids/text are unchanged). Out of scope for M23–25 — noted here so the re-embed cost is a known, deliberate trade-off rather than a surprise.
>
> **Combine the M23 + M25 validation rebuilds (both target `ctcm-api`).** The naive reading — one `--reset` + `backfill-vectors` per milestone — pays the ~100-min extraction + re-embed **twice** on the same repo for no reason. Because facts/refs/edges are additive and both milestones re-extract the same files, **implement M23 and M25, then do a single combined `ctcm-api` cold `--reset` + `backfill-vectors`** and read both milestones' deliverables off it (M23 predicate counts + M25 ref/edge/fact deltas). M24 legitimately needs its own run — it targets `ctcm-db` (SQL DDL), a different repo. So the validation cost is **two** cold rebuilds (`ctcm-api` shared by M23/M25, `ctcm-db` for M24), not three.

#### Milestone 23: Annotations / attributes / decorators

The single largest gap — legacylift-search has **zero** annotation awareness today (the XML extractor only covers *XML-config* Hibernate/Spring; annotation-based Spring/JPA and all ASP.NET attribute routing/validation/auth are invisible). Feeds `si-documenter` (API/routes), security, `business-documenter`/`detailed-req-documenter` (validation rules), and the data-model skills (JPA/EF attributes).

**Verified nodes:** C# `attribute_list → attribute` (name), args in `attribute_argument_list → attribute_argument`; Java `marker_annotation` (no args) and `annotation` (args in `annotation_argument_list → element_value_pair`), both under a `modifiers` node; Python `decorator` (child of `decorated_definition`) whose body is an `identifier` (`@requires_auth`) or a `call` whose `attribute`/`identifier` is the name (`@app.get`); TypeScript `decorator → call_expression` (name) appearing in `export_statement` before a class and inside `class_body` before a `method_definition`, plus param decorators inside `formal_parameters`.

**Approach:** a handler fired on definition nodes, anchored on the definition — annotations are always attached to the annotated symbol, giving `subject_symbol_id` for free. **But "walk the definition node's annotation children" is correct ONLY for C# and Java** — where the annotation is a child of the def node (`attribute_list` under the member; `annotation`/`marker_annotation` under the def's `modifiers`). **For Python and TypeScript the annotation is NOT a child of the def node, and a children-only walk emits ZERO facts (a silent undercount — exactly the failure mode the Shared prerequisite warns about):** a Python decorated def parses as `decorated_definition → (decorator … + function_definition/class_definition)`, so the handler fires on the `function_definition` def node (`extractors.py:473`) while the `decorator` nodes are children of its **parent** (`decorated_definition`), reachable via `node.parent`; a TS class decorator "appears in `export_statement` before a class" — i.e. a **preceding sibling**, not a child, reached by scanning the def node's parent (`export_statement`/`class_body`) and its preceding siblings. **The handler MUST inspect `node.parent` and preceding siblings for the Python/TS decorator cases, not only `node`'s children.** Split by intent, driven by a small name-map in the profile (`annotation_semantics`): routing (`Route`/`HttpGet`/`GetMapping`/`@app.get`) → an `exposes_endpoint` edge/fact with `http_method`; authz (`Authorize`/`@PreAuthorize`) → `requires_auth` fact; validation (`Required`/`MaxLength`/`@NotNull`/`Field(max_length=)`) → `is_required`/`max_length` facts; persistence (`@Entity`/`@Table`/`@Column`/`@Id`) → column/table facts, and `@JoinColumn`/`@ManyToOne` → a `foreign_key`/`associates` **edge**. Unknown annotations still recorded as a generic `has_annotation` fact (name + args) so nothing is silently dropped. Capture annotation arguments (route template, column name, max length) as the fact `object`/attributes.

**Coverage is tree-sitter-path-only (state this, don't let it read as a bug later).** The annotation handler fires only on the tree-sitter definition-node path in `SymbolExtractor`. **Hook it where definition nodes are actually visited and Symbols are built — the `node.type in def_kinds` branch of `_walk_tree`/`visit` at `extractors.py:473–509` (the same site M22's `_extract_inheritance_refs` fires from), where the `Symbol` object is in hand so `subject_symbol_id` is `symbol.id` for free.** (Do **not** anchor on `extractors.py:409` — that line is only the `return ExtractedFile(symbols=…, refs=…, parse_errors=…)` that *assembles* the tree-sitter branch's result; by then per-node context is gone.) The regex-fallback path (`extractors.py:883`, the terminal `return` of `_extract_fallback`, used for COBOL and any file tree-sitter can't parse) and the `xml_extractor` emit **zero** annotation facts. That is acceptable — annotations are a typed-source construct and ctcm-api (.NET, tree-sitter C#) exercises the real path — but it means a COBOL or XML-config repo will show no `http_method`/`requires_auth`/validation facts by design, not by defect. Note this in the retrospective so it isn't later mistaken for missing extraction. (`ExtractedFile.facts` defaults to `[]`, so the fallback/XML constructors need no change — they simply contribute no facts.)

**Automated CI tests (required, not optional — the ctcm-api validation exercises C# only).** ctcm-api is .NET, so the *only* annotation path the at-scale run covers is C# `attribute_list` children. The Python/TS parent/sibling path (see the Approach caveat) and the Java `modifiers` path get **zero** scale coverage, so a children-only regression there would be invisible. Add polyglot-fixture unit tests — mirroring M24's required fixture tests — that assert annotation facts are extracted for **all four** tree-sitter languages: a C# attribute (e.g. `[HttpGet("...")]` → `http_method`/`exposes_endpoint`), a Java annotation (`@GetMapping`), a **Python decorator** (`@app.get(...)` — proves the `node.parent`/`decorated_definition` traversal fires), and a **TS class/method decorator** (proves the preceding-sibling traversal fires). Do not rely on ctcm-api manual validation alone; the multi-language claim must have automated coverage.

**Validate on `repos/ctcm/ctcm-api`** (.NET, attribute-heavy; requires `index --reset`, then `backfill-vectors` — see the Shared prerequisite; **combine this rebuild with M25's per the combined-rebuild note — both target `ctcm-api`**): confirm `symbol_facts` now holds `http_method`, `requires_auth`, and validation predicates, and spot-check a known controller's route/verb against source. Record predicate counts.

#### Milestone 24: SQL columns, constraints, and foreign keys

Turns `create_table` symbols into a real data model + FK graph for `data-documenter`, `data-dictionary-generator`, and `table-validation`. Run against `repos/ctcm/ctcm-db` (SQL DDL), not just ctcm-api.

**Verified nodes:** `column_definition` (name + type node `int`/`varchar`/`decimal` + `keyword_not`/`keyword_null`/`keyword_primary`/`keyword_key`/`keyword_unique`); table-level `constraints → constraint`.

**Prerequisite the original plan glossed over — the column subtree is NOT reachable on the current definition path.** The SQL profile's `definition_node_kinds` list `create_table_statement`/`table_definition`/etc. (`extractors.json`), but tree-sitter-sql actually emits `create_table` — the documented 2026-05-15 SQL-divergence. Because of that mismatch, `_walk_tree` finds **zero** SQL definition nodes and falls through to the **regex-definition supplement** (`extractors.py`, the "tree-sitter produced no definition matches" branch). So today SQL "symbols" are `kind="fallback_definition"` from regex, and the `create_table → column_definition` subtree M24 wants to walk is **never visited**. M24 must therefore do one of the following *first*, as an explicit step:
- **(preferred)** correct the SQL profile node names (`create_table`, `create_view`, …) so tree-sitter definitions are used, OR
- add a dedicated tree-sitter SQL table/column walker that runs regardless of the definition-path outcome.

**Prefer option (a).** Option (b) makes the tree-sitter table walker and the regex `fallback_definition` path both capable of emitting a table symbol for the *same* `create_table`, and unless both use the **identical symbol-id scheme** (`<language>:<relative-path>:<qualified-name>:<start-line>`), you get duplicate table symbols and a `has_column` fact whose `subject_symbol_id` points at whichever symbol the extractor happened to emit — breaking the FK linkage and per-symbol dedupe. Correcting the profile node names (option a) sidesteps this entirely: tree-sitter then produces the table symbol on the normal definition path, the regex supplement only fires for genuinely unparseable dialects, and there is exactly one symbol per table.

**dump-ast-verify EACH corrected node name — the divergence is per-node, and only `create_table` has been confirmed.** The 2026-07-13 sweep verified `create_table`; the other names in the current SQL `definition_node_kinds` (`create_view_statement`, `create_function_statement`, `create_procedure_statement`, `create_trigger_statement`, `create_index_statement`, plus `table_definition`/`view_definition`) are **assumed** to follow the `create_*` pattern but have not been checked against tree-sitter-sql on this stack. Run `dump-ast` on one DDL example of each before editing `extractors.json`, and correct each to whatever the grammar actually emits (do not batch-rename on the assumption they all drop the `_statement` suffix).

**Correcting `definition_node_kinds` is necessary but NOT sufficient — verify the table *name* is recoverable too.** A corrected `create_table` node only yields a symbol if `_extract_name` (`extractors.py:549`) returns non-empty. That method does a BFS descent over descendants against `name_node_kinds` (currently `identifier`/`object_reference`/`qualified_name`/`bare_identifier`) and **returns the first match**, so for a `create_table` node whose subtree also contains `column_definition` identifiers there is a real hazard it returns a *column* name rather than the *table* name if the table name isn't the first name-kind descendant in child order. When you `dump-ast` each corrected node, confirm (a) `name_node_kinds` covers whatever node actually holds the table name, and (b) the emitted symbol's `name`/`qualified_name` is the **table** name, not a column's. If BFS picks the wrong node, prefer `child_by_field_name("name")` (step 1 of `_extract_name`, which fires first) or narrow `name_node_kinds` for the table case.

**Expected side effect — SQL symbol identity churns; call it out for downstream consumers.** Moving SQL off the regex path changes each table symbol's `kind` from `fallback_definition` to the tree-sitter node kind (`create_table`, …) and can change its `qualified_name` (hence its `id`, which encodes qualified-name). This is fine under the mandated `--reset` (full rebuild, no stale ids), but `table-validation`, `data-documenter`, and `data-dictionary-generator` consume SQL symbol ids/kinds — flag the churn in the retrospective so a changed symbol id downstream reads as an expected M24 effect, not a regression.

**Audit the existing SQL *tests* for the same churn — this is inside our own codebase, so it's a hard failure, not just a downstream note.** Any existing test that asserts a SQL symbol's `kind == "fallback_definition"` (in `test_store.py`, `test_indexer*.py`, or the extractor tests) will break the moment option (a) lands, because those symbols become `kind="create_table"` (etc.). Before editing `extractors.json`, grep the test suite for `fallback_definition` and update the SQL expectations; do not let the equivalence/count tests mask this by only checking totals.

**If the load-bearing assumption is wrong, option (a) is a no-op — have the fallback ready.** All of M24 pivots on tree-sitter-sql emitting a node whose name is absent from the current `definition_node_kinds` (the 2026-07-13 sweep saw bare `create_table`; the profile lists only `create_table_statement`/`table_definition`, so SQL currently falls to the regex path — the premise). The `dump-ast`-per-node step above is what confirms the corrected name. **If `dump-ast` shows the grammar already emits a name the profile matches (so SQL was NOT actually on the regex path), option (a) changes nothing and you must use option (b) — the dedicated tree-sitter column walker — with the identical symbol-id scheme.** Decide this from the `dump-ast` output, not from the 2026-07-13 note, since `ctcm-db` is the first *large* SQL corpus. **But the polyglot fixture SQL is not too small to test M24 in CI — it is sufficient and MUST be used.** `tests/fixtures/polyglot_repo/database/schema.sql` (package-relative — the real path is `tools/legacylift_search/tests/fixtures/polyglot_repo/database/schema.sql`; every `tests/fixtures/...` reference in M23–25 means that prefix, as with the `extractors.json` convention above) already defines two `CREATE TABLE`s with typed columns + `INT PRIMARY KEY`, **plus a real `FOREIGN KEY (provider_id) REFERENCES providers(provider_id)` (schema.sql:13)** — exactly the FK clause the tree-sitter-sql grammar mis-parses to `ERROR`, so it exercises **both** the tree-sitter column path and the regex FK supplement. Do not treat `ctcm-db` as the only place M24 is verified.

Either way, verify the change does not regress the existing "supplement with regex when tree-sitter finds no definitions" behavior for dialects the grammar still can't parse — the two paths now coexist and the tests must pin that both a clean-parse table (columns via tree-sitter) and an unparseable statement (regex fallback) still produce the right symbols, and that the `has_column` fact's `subject_symbol_id` matches the table symbol's `id` under both paths.

**Approach:** once `create_table` nodes are visited, emit one `has_column` fact per `column_definition` (object = column name; attributes = data type, nullability, PK/unique flags from the keyword children). Emit `foreign_key` **edges** (table → referenced table) from FK constraints — as `SymbolRef`s with a new `kind` mapped in `GraphBuilder`, per the Shared prerequisite (relational → edge, not fact).

**Verified caveat (must handle):** the tree-sitter-sql grammar **mis-parses the FK clause** — `FOREIGN KEY (PolicyId) REFERENCES Policy(PolicyId)` came back partly as an `ERROR` node. Columns/PK/unique are clean from tree-sitter, but **FK extraction requires a regex supplement** over the constraint text (`FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+([\w\.\[\]"]+)\s*\(([^)]+)\)`), reusing the existing SQL "tree-sitter + regex-fallback" hybrid pattern (see the 2026-05-15 SQL-divergence observation). `log()` the FK count found via regex vs. columns found via tree-sitter so the split is visible.

**Automated CI tests (required, not optional):** add fixture-based unit tests against `tests/fixtures/polyglot_repo/database/schema.sql` that assert (1) `has_column` facts for `providers`/`members` with correct type/nullability/PK attributes, (2) a `foreign_key` edge `members → providers` from the regex FK supplement, and (3) the `has_column` fact's `subject_symbol_id` equals the table symbol's `id` under whichever path (option a or b) is chosen. M24's core deliverable must have automated coverage — do **not** rely on `ctcm-db` manual validation alone.

**Validate at scale (requires `index --reset` on `repos/ctcm/ctcm-db`, then `backfill-vectors` — see the Shared prerequisite):** `symbol_facts` holds `has_column` for known tables; `graph_edges` holds `foreign_key` edges. This is the exact family `table-validation` compares against ORM mappings — cross-check a few against the v3 fact-graph / known DDL. Confirm a `create_table`-clean table yields columns via tree-sitter and record the tree-sitter-column vs. regex-FK split from the log.

#### Milestone 25: Field/property type references + method signatures

Builds the data-model association graph and typed API surface. Feeds `data-documenter` (associations), `si-documenter` (API params/returns), and DTO-usage analysis.

**Verified nodes:** field/property types — C# `predefined_type`/`identifier`/`generic_name`+`type_argument_list`, Java `type_identifier`, Python `assignment` with a `type` child, TS `type_annotation`; method signatures — C# `parameter_list → parameter` + return `generic_name`/`predefined_type`, Java `formal_parameters` + `void_type`/`type_identifier`, Python `typed_parameter` + `-> type`, TS `formal_parameters` + `type_annotation`; and Java `throws` (name = exception type).

**Approach:** resolve each type identifier against `all_symbols_by_name` (the M22/graph resolver + confidence tiers). Field/property type → an `associates` (or `has_field_of_type`) edge subtype→type. Method param/return types → `accepts_dto`/`returns_dto` edges when the resolved target is a known DTO/model. Java `throws` → a `throws` fact. Enum members (`enum_member_declaration`) → `has_enum_value` facts (reference/state data).

**Generic unwrap — do NOT reuse `_base_type_name` verbatim.** M22's `_base_type_name` returns the **outer** name of a `generic_name` (`ActionResult<ClaimDto>` → `ActionResult`), which is correct for M22 (the base type *is* the outer name) but exactly wrong for M25, which wants the **inner** payload type (`ActionResult<ClaimDto>`/`List<Claim>` → `ClaimDto`/`Claim`). M25 needs new logic that descends one level into `type_argument_list` (verified: C# `type_argument_list` exposes `ClaimDto`) and takes the innermost type argument, falling back to the outer name when there is no type argument. Treat this as a distinct helper, not a call into `_base_type_name`.

**Filter primitives/builtins BEFORE resolving (required — omitted from the original plan).** Emitting a type ref for `int`/`string`/`bool`/`decimal`/`Task`/`void` etc. is pure noise: it either resolves to nothing (0.30 unresolved junk) or *falsely* resolves to an unrelated same-named user symbol. Maintain a per-language primitive/builtin skip-set (C# `int`/`string`/`bool`/`object`/`void`/`decimal`/`Task`/…, Java `int`/`long`/`String`/`void`/…, TS `string`/`number`/`boolean`/`any`/`void`/…) and drop those type names before resolution. Only user-defined types become edges.

**Edge-id collision — will silently undercount M25 edges unless the id is widened.** `GraphBuilder` builds edge ids as `edge:{caller_or_file}:{ref.name}:{ref.range.start_line}:{edge_kind}` — the assignment opens at `graph.py:73` (`edge_id = (`) and the f-string itself is at **`graph.py:74`**; `{caller_or_file}` is `caller_id if caller_id else source_file.relative_path` (`graph.py:72`). This is unique enough for M22 (one base type per line) but **not** for M25: a signature like `void Save(Claim a, Claim b)` or a field `Dictionary<Claim, Claim> map` emits two `Claim` refs with identical `name`/`start_line`/`edge_kind`, so they collapse to one edge id and one is dropped by dedupe — directly corrupting the "record the exact ref/edge delta" deliverable. Fold `ref.id` (already unique per ref) into the edge id — e.g. `edge:{caller_or_file}:{ref.name}:{ref.range.start_line}:{edge_kind}:{ref.id}` — or otherwise disambiguate multiple same-type refs on one line. This is a change to `GraphBuilder` shared by all edge kinds, so re-run the M22 hierarchy-edge tests to confirm counts are unchanged (M22 never had per-line duplicates, so widening the id is a no-op for it).

**Scale/perf concern (call out in the retrospective).** Unlike M22's ~2,750 inheritance refs, M25 emits a ref for every typed field, property, parameter, and return across ctcm-api's ~58k symbols — plausibly **hundreds of thousands** of new refs/edges, all flowing through the single-threaded SQLite writer and the graph-build phase (`Indexer.run`, graph-edge-build). Budget for a materially longer cold index and a larger `index.sqlite`, and record the actual ref/edge delta. **The writer is not the only pressure point — the in-memory graph-build phase grows too.** `GraphBuilder.build_edges` holds `all_symbols_by_name` plus the full edge accumulator/dedup dict in memory for the whole repo at once; per-ref resolution stays O(1) (dict lookup), so *time* scales linearly, but *peak memory* for the edge dict grows with the ref count and could dominate on a large repo. **Measure peak RSS of the graph-build phase, not just wall-clock,** and record it (wrap the phase in `tracemalloc.start()` / `tracemalloc.get_traced_memory()` for the Python-object peak, and/or sample `psutil.Process().memory_info().rss` — `tracemalloc` is stdlib and works on Windows without extra deps). The primitive filter above is the main lever keeping both bounded; measure edge count (and memory) with and without it on a sample before committing to the full run.

**Validate on `repos/ctcm/ctcm-api` (requires `index --reset`, then `backfill-vectors` — see the Shared prerequisite; combine this rebuild with M23's per the combined-rebuild note):** `associates`/`returns_dto` edges resolve for a known controller→DTO path; enum values captured for a known status enum. Confirm **chunk and symbol counts unchanged** — but note that **`ref_count` and `edge_count` will rise substantially** (they are the deliverable), and `symbol_facts` gains `throws`/`has_enum_value` rows. Record the before/after ref/edge/fact deltas.

### Milestone 26: `uses_table` alias binding and self-reference suppression

> ⚠️ **A downstream plan is BLOCKED on this milestone (added 2026-08-25).**
> `docs/exec-plans/active/reqs-to-data-store.md` Milestone 1 Step 7 computes a `reads[]`/`writes[]`
> data-flow block per requirement from `uses_table` / `has_column` / `foreign_key`. Until M26
> lands, that block emits SQL table **aliases** (`o`, `c`, `po`) as datastore names and confident
> self-edges (`Orders -> Orders`), so it would be **wrong, not merely incomplete** — which breaks
> that plan's provenance principle ("the computed path is trustworthy"). **It therefore ships
> DISABLED behind a flag**, and enabling that flag is the acceptance signal for this milestone's
> downstream value. When you finish M26, flip it and re-run that plan's Step 7 tests.

**Reproduce first — the defect is already pinned by a runnable probe.** Extract this through
`SymbolExtractor` + `GraphBuilder` (the harness in `tests/test_sql_table_recovery.py` —
`_source_file` / `_extract_text` / `_edges` — does this in three lines):

    CREATE TABLE dbo.Orders (OrderId INT NOT NULL, CustomerId INT, Status VARCHAR(10));
    CREATE TABLE dbo.Customers (CustomerId INT NOT NULL, CustomerName VARCHAR(50));
    CREATE PROCEDURE dbo.GetOpenOrders
    AS
    BEGIN
        SELECT o.OrderId, c.CustomerName
        FROM dbo.Orders o
        INNER JOIN dbo.Customers c ON c.CustomerId = o.CustomerId
        WHERE o.Status = 'Open';
    END

Observed 2026-08-24 — **10 `uses_table` edges, 5 of them junk**:

| caller | `callee_name` | resolved | conf | verdict |
|---|---|---|---|---|
| `Orders` | `Orders` | `Orders` | 0.85 | **junk — self-edge** |
| `Customers` | `Customers` | `Customers` | 0.85 | **junk — self-edge** |
| `GetOpenOrders` | `GetOpenOrders` | `GetOpenOrders` | 0.85 | **junk — self-edge** |
| `GetOpenOrders` | `Orders` | `Orders` | 0.85 | correct |
| `GetOpenOrders` | `Customers` | `Customers` | 0.85 | correct |
| `GetOpenOrders` | `o` ×3, `c` ×2 | — | 0.30 | **junk — aliases** |

**Step 1 — alias binding.** In the SQL path of `SymbolExtractor`, collect the alias→table
bindings declared in each statement (`FROM <table> <alias>`, `JOIN <table> <alias>`, with and
without `AS`, bracketed and schema-qualified) before emitting refs. Then, for each
`object_reference` ref whose text matches a declared alias in the same statement scope, either
**suppress** it or **re-point** it at the bound table. Prefer re-pointing only if it does not
double-count a table already referenced in the same statement; suppression is the safer default
and loses nothing, since the `FROM`/`JOIN` clause already emitted the real table ref.

⚠️ **Do not "fix" this with a confidence filter.** It is tempting, because every alias in the
probe is unresolved at 0.30 while every real table resolves at 0.85. But a genuine table with no
indexed DDL — cross-database reference, synonym, linked server — is **also** unresolved at 0.30.
Filtering on confidence discards real lineage to remove aliases. **After this milestone an
unbound 0.30 `uses_table` edge must mean exactly one thing: a table we have no DDL for.** Pin
that with a test.

**Step 2 — self-reference suppression on the clean grammar path.** An object's own name inside
its own `CREATE` statement is not a usage of it. The regex-recovery path already implements this
(`extractors.py` — the header-span drop, guarded by
`test_sql_table_recovery.py::test_lineage_refs_survive_the_repair`, which asserts
`("Customer","Customer") not in used`), but the **tree-sitter path has no equivalent guard**,
which is why `Orders → Orders` survives at 0.85. Apply the same header-span rule to refs emitted
on the clean path, for `create_table`, `create_view`, `create_procedure` and `create_function`
alike — the probe shows the procedure self-edge too, so this is not a table-only fix.

**Step 3 — CI tests (required, not optional).** Add to `tests/test_sql_table_recovery.py` (or a
sibling `test_sql_lineage.py`): (a) the probe above yields exactly **two** `uses_table` edges,
`GetOpenOrders → Orders` and `GetOpenOrders → Customers`; (b) no self-edge for any of the four
`create_*` kinds; (c) an alias that shadows a real table name (`FROM dbo.Orders Customers`) binds
to `Orders` and does **not** produce a spurious `Customers` usage; (d) **the over-correction
guard** — `FROM ExternalDb.dbo.Ledger` with no DDL in the index still yields one unresolved 0.30
`uses_table` edge with `callee_name` preserved. Also cover `UPDATE`/`INSERT INTO`/`DELETE FROM`
and a CTE (`WITH x AS (...) SELECT ... FROM x`), where `x` is neither a table nor an alias.

**Step 4 — before/after at scale.** Re-index a real T-SQL corpus (`repos/ctcm/ctcm-db`, and the
NNG DB unit if available) and record the `uses_table` edge count before and after, plus the
resolved/unresolved split. **Expect a large drop** — the probe's ratio is 5 junk in 10 — and
report it as a *correctness* improvement, not a regression. Per the M22 precedent, a graph-only
rebuild suffices if extraction output is unchanged; an extractor change means `--reset`.

**Downstream note:** flag the edge-count change for `data-documenter`,
`data-dictionary-generator`, `database-layer-documenter` and `table-validation` in the
retrospective, so a shrunken `uses_table` count downstream reads as an expected M26 effect rather
than a regression — the same courtesy M24 extended for SQL symbol-id churn.

### Milestone 27: Unresolved-dispatch visibility

> **Downstream note (added 2026-08-25).** `docs/exec-plans/active/reqs-to-data-store.md` Step 7
> depends on this one **softly for correctness but hard for its honesty claim**: without part (a),
> an unresolved edge is indistinguishable from an absent one at the point of consumption, so that
> plan's data-flow block can report a total but not an honest **floor**, and its stated coverage
> story cannot be made truthfully. The LLM-inferred fallback still functions without M27.

**Get the premise right before building anything.** The graph does **not** discard unresolved
calls. `_resolve_callee` (`graph.py`) grades every ref — **0.85** exactly one match, **0.70**
ambiguous same-language (prefer same file), **0.40** cross-language ambiguous, **0.30** zero
matches — and the zero-match edge is **kept with `callee_name` preserved**, per the "preserve
unresolved edges" decision recorded in `code-graph-construction.md` §2. The edge exists; it has
no **callee symbol id**, which is what traversal needs. Everything below is about making that
population *legible*, not about inventing edges.

**Part (a) — visibility. Do this regardless; it is the whole milestone's floor.**

1. Add an `unresolved_edges` breakdown to `stats`: total, and split by `edge_kind` and by
   confidence band (0.30 / 0.40 / 0.70). The 0.70 band matters — it is *resolved* but ambiguous,
   and a consumer may reasonably want to treat it differently from 0.85.
2. Add a `--unresolved` (or `--max-confidence`) filter to the edge-facing commands so a consumer
   can enumerate the population rather than infer it from a missing row.
3. Group by enclosing file, and — where domain tagging is present — by domain, so "which part of
   the system is the graph blind in?" is answerable. Domain tagging lives in `knowledge.sqlite`
   and is a separate pass (`code-graph-construction.md` §5), so treat the domain grouping as
   optional enrichment, not a hard dependency.

**Why (a) is not cosmetic:** at the point of consumption an unresolved edge and an absent edge are
indistinguishable, so every downstream count under-reports **silently**. A consumer that cannot
ask "how much did you not resolve?" cannot honour `NORMATIVE PRINCIPLE-1` clause 5 in the
requirements-store plan ("report the inference rate"), and cannot present its own numbers as a
floor rather than a total.

**Part (b) — resolution from framework config. DECIDE, do not assume.**

`/modernize-map` already resolves dispatch edges from framework configuration rather than from
the index — evidence both that it is tractable and that logic exists to lift. But whether it
belongs *in Layer 0* is a real question: it is configuration-shaped and framework-specific, where
the rest of the graph is deterministic AST work over source text. Pulling it in widens Layer 0's
contract.

**Therefore: measure before scoping.** With (a) shipped, report on `repos/ctcm/ctcm-api` and the
NNG app unit: unresolved counts by `edge_kind`, and the share attributable to framework dispatch
(MVC routes, DI registrations, Spring/WebFlow transitions) versus genuinely external targets
(third-party libraries, system calls) which **no** framework-config pass would ever resolve.
**Only the first share is addressable**, and if it is small, (b) is not worth Layer 0's contract
widening — say so and close it.

**Deliverable:** the `stats` breakdown + filter, the measured unresolved profile for both repos,
and a recorded go/no-go on (b) with the number that decided it.

**Consumer:** the requirements-store plan's Q3h computed `reads[]`/`writes[]` block, whose
`llm_inferred` fallback fires precisely on this population. Shrinking the unresolved set directly
shrinks the LLM-inferred share and strengthens the deterministic claim; **and even without (b),
part (a) is what lets that block report its floor honestly.**


## Validation and Acceptance

The implementation is accepted when all of the following behaviors are true.

From the repository root:

    python -m pip install -e tools/legacylift_search

succeeds.

Running:

    legacylift-search --help

shows all commands.

Running:

    legacylift-search init-config --repo-root repos/<name> --overwrite

creates a valid JSON manifest at `repos/<name>/semantic-search.manifest.json`.

Running (against the bundled fixture repo for CI smoke validation):

    legacylift-search index --repo-root tools/legacylift_search/tests/fixtures/polyglot_repo --embedding-provider hash --reset

creates:

    tools/legacylift_search/tests/fixtures/polyglot_repo/legacylift-docs/index/code-search/index.sqlite
    tools/legacylift_search/tests/fixtures/polyglot_repo/legacylift-docs/index/code-search/chroma/
    tools/legacylift_search/tests/fixtures/polyglot_repo/legacylift-docs/index/code-search/manifest.snapshot.json

(The end-to-end test harness should copy the fixture to a temp directory so test artifacts never pollute the source tree.)

Running (against a real repo under `./repos/`):

    legacylift-search index --repo-root repos/ctcm-api --embedding-provider hash --reset

creates the same files under `repos/ctcm-api/legacylift-docs/index/code-search/` and these paths must be matched by `.gitignore`.

Running:

    legacylift-search validate --repo-root repos/ctcm-api

prints:

    Index is valid.
    freshness: fresh

Running:

    legacylift-search search "provider eligibility validation" --repo-root repos/ctcm-api --limit 5

returns at least one ranked result with:
    a score,
    a file path,
    line numbers,
    a language,
    and a snippet.

Running:

    legacylift-search symbols --name <KnownSymbolFromRepo> --repo-root repos/ctcm-api

returns at least one symbol with a stable symbol ID.

Running:

    legacylift-search callees <symbol-id> --repo-root repos/ctcm-api

returns outgoing graph relationships when the symbol has detectable calls. If a specific symbol has no calls, the command must still return a clear "no callees found" message and exit with code 0.

After indexing, `git status` must not show any new files under `repos/<name>/legacylift-docs/index/`.

Running:

    cd tools/legacylift_search
    pytest

passes all tests.

At least these test categories must exist:
    manifest load/write tests,
    discovery tests,
    extractor tests,
    SQLite persistence tests,
    vector store tests using HashEmbedder,
    hybrid search tests,
    CLI end-to-end smoke tests.

The new tests should fail before implementation because commands and modules do not exist, and pass after implementation.

## Idempotence and Recovery

All commands must be safe to rerun.

`legacylift-search init-config` must not overwrite an existing config unless `--overwrite` is passed.

`legacylift-search index` must use upsert behavior for SQLite and Chroma. Re-running it against the same repository and index directory should not duplicate files, chunks, symbols, refs, or graph edges.

`legacylift-search index --reset` may delete and recreate only the configured index directory contents. It must refuse to reset if the resolved index directory is the repository root, the user home directory, a drive root, or any path not ending in a clearly index-like directory such as `code-search`, `legacylift-docs/index/code-search`, `.legacylift`, or `legacylift-index`. The resolved path must also be a descendant of `<repo-root>/legacylift-docs/` unless an explicit override flag is provided.

If indexing fails halfway, rerun the same command. SQLite transactions should keep committed file batches valid, and Chroma upsert should overwrite matching chunk IDs. The first implementation may use a single transaction per file plus a separate transaction for graph edges.

If the embedding dimension changes, fail with a clear message:

    Existing Chroma collection uses dimension 64 but configured embedder uses dimension 1024. Re-run with --reset or choose a different index directory.

If a parser fails for one file, record the error in `index.log` and continue using fallback extraction or fallback chunking. If more than 25 percent of files produce zero chunks, fail the index run because the output is probably not useful.

If Qwen model loading fails, the error message must recommend:

    Use --embedding-provider hash for a local smoke test, or ensure the Qwen model is available to sentence-transformers.

Do not store secrets in the manifest, SQLite metadata, Chroma metadata, or logs.

## Artifacts and Notes

The implementation should produce these artifacts under each indexed repository:

    repos/<name>/semantic-search.manifest.json                                  (committed)
    repos/<name>/legacylift-docs/index/code-search/index.sqlite                 (gitignored)
    repos/<name>/legacylift-docs/index/code-search/chroma/                      (gitignored)
    repos/<name>/legacylift-docs/index/code-search/manifest.snapshot.json       (gitignored)
    repos/<name>/legacylift-docs/index/code-search/index.log                    (gitignored)

The legacylift-ai repository's `.gitignore` (or a per-repo `.gitignore` under `repos/<name>/`) must include:

    legacylift-docs/index/

The SQLite database can be inspected with:

    sqlite3 repos/<name>/legacylift-docs/index/code-search/index.sqlite ".tables"
    sqlite3 repos/<name>/legacylift-docs/index/code-search/index.sqlite "select language, count(*) from chunks group by language;"

Expected table list includes:

    index_metadata
    repo_files
    chunks
    chunk_fts
    symbols
    symbol_refs
    graph_edges

A concise successful indexing transcript should look like:

    Discovered 128 source files
    Indexed 128 files
    Created 947 chunks
    Extracted 612 symbols
    Extracted 1403 references
    Created 981 graph edges
    Upserted 947 vectors into Chroma collection code_chunks
    Wrote index to repos/<name>/legacylift-docs/index/code-search

A concise successful search transcript should look like:

    1. score=0.0325 src/eligibility.py:5-18 python EligibilityService.check
       def check(self, provider_id):
           return self.rules.validate(provider_id)

    2. score=0.0161 database/schema.sql:20-35 sql create procedure validate_provider
       CREATE PROCEDURE validate_provider ...

## Interfaces and Dependencies

The package must expose stable internal interfaces so future LegacyLift agents can import them directly if needed.

In `models.py`, define the Pydantic models described in the milestones:
    TextRange
    SourceFile
    Symbol
    SymbolRef
    ExtractedFile
    CodeChunk
    GraphEdge
    SearchResult

In `config.py`, define:
    load_manifest(path: Path) -> Manifest
    write_default_manifest(path: Path, overwrite: bool = False) -> None
    resolve_index_dir(repo_root: Path, manifest: Manifest) -> Path

In `discovery.py`, define:
    discover_source_files(repo_root: Path, manifest: Manifest) -> list[SourceFile]

In `languages.py`, define:
    detect_language(path: Path) -> LanguageSpec | None
    get_language(key: str) -> LanguageSpec

In `extractors.py`, define:
    load_profiles(path: Path) -> ExtractorProfiles
    class SymbolExtractor

In `chunking.py`, define:
    class CodeChunker

In `embeddings.py`, define:
    class Embedder
    class HashEmbedder
    class QwenEmbedder
    def create_embedder(config: EmbeddingConfig, provider_override: str | None = None) -> Embedder

In `store.py`, define:
    class SQLiteStore

In `vector_store.py`, define:
    class ChromaVectorStore

In `graph.py`, define:
    class GraphBuilder

In `search.py`, define:
    class SearchEngine

In `indexer.py`, define:
    class Indexer

The CLI in `cli.py` should be thin. It should parse arguments, call these classes, and render results. Business logic belongs in the modules above, not in CLI command functions.

## Implementation Notes for Codex

Prefer small commits if the environment supports git. A good sequence is:
    package skeleton,
    config/discovery,
    profiles/extraction,
    chunking,
    SQLite,
    Chroma/embeddings,
    indexer,
    search/graph CLI,
    tests and docs.

Do not prompt the user for next steps. Proceed through the milestones. If a library behaves differently than expected, inspect its installed source or use a small spike, then update this ExecPlan before continuing.

When updating this ExecPlan during implementation, keep it self-contained. Do not replace important detail with “see commit” or “see previous notes.” The next agent must be able to restart from this file alone.

At the end of implementation, add an Outcomes & Retrospective entry with:
    the test command and result,
    the fixture indexing command and result,
    the current repository indexing command and result,
    any known limitations,
    and recommended next enhancements.

Recommended next enhancements after the first accepted implementation:
    Add reranking with Qwen3-Reranker if local performance is acceptable.
    Add MCP tool wrappers for LegacyLift agents.
    Add a small HTTP server mode for multi-agent use.
    Add language profiles for XML, YAML, JSON, C/C++, Go, Ruby, PHP, and shell.
    Add import/package graph extraction.
    Add repository-level architectural summaries generated from indexed chunks.
    Add call graph visualization export in Mermaid and GraphML.
    Add DB2-specific SQL extraction for mainframe modernization.
    Add copybook expansion for COBOL.
    Add Roslyn-based C# extraction as an optional high-precision path.
    Add JavaParser-based Java extraction as an optional high-precision path.
    Add TypeScript compiler API extraction as an optional high-precision path.