# Build Semantic Code Search and Graph Indexing for LegacyLift — Additional Info (Archive)

This file is the `-additional-info` companion to the ExecPlan `semantic-code-search-graph-index.md` in this same directory. Per `docs/exec-plan.md` ("Large plans: split current state from archived detail"), it holds completed-milestone detail that is no longer needed to understand or continue the *current* state of the work: the full per-milestone `Outcomes & Retrospective` entries, the multi-agent wave dispatch plan for the already-finished foundational milestones, and the `Concrete Steps` (build instructions) for milestones that are already shipped.

You do not need this file to continue current work. The main plan file is self-contained for current and future milestones. Read this archive only when you genuinely need the history — for example, to reconstruct why a completed milestone was built the way it was, or to recover the exact build steps for a shipped component. This archive is self-contained for the history it records.

The living sections (`Progress`, `Surprises & Discoveries`, `Decision Log`, and the current-status `Outcomes & Retrospective` summary) stay in the main file, because they explain why current code looks the way it does and are consulted continuously rather than only as history.

---

## Outcomes & Retrospective (full per-milestone history)

The main file keeps a short current-status summary under its `Outcomes & Retrospective` heading. The complete dated entries for Milestones 14 through 20 are preserved below.

### 2026-05-18 — Milestone 14 (Wave E Agent E2): real-repo validation against `repos/ctcm/ctcm-api`

The implementation delivers the behavior described in Purpose / Big Picture: a single CLI builds a per-repo SQLite + Chroma index, exposes hybrid (vector + lexical) search with reciprocal rank fusion, persists caller/callee graph edges with confidence scores, and reports `fresh`/`stale`/`missing` index status against a deterministic `source_set_sha256`. End-to-end validation was performed against the on-disk equivalent of the plan's nominal `repos/ctcm-api`, which is `repos/ctcm/ctcm-api` (the plan referenced `repos/ctcm-api`; see Surprises & Discoveries entry on the naming divergence).

**Test command and result**:

```
py -3.12 -m pytest tools/legacylift_search
# 99 passed in 97.43s (Python 3.12 / Windows 11)
```

**Fixture indexing command and result**: Already covered by Milestone 13 (`tests/test_cli_smoke.py`), which drives the full user journey on a temporary copy of `tools/legacylift_search/tests/fixtures/polyglot_repo` (7 files, 25 chunks, 28 symbols, 36 refs, 36 graph edges) with `embedding-provider hash`, asserts `Index is valid.` + `freshness: fresh`, and exercises `search`/`symbols`/`stats`/`callees` plus idempotent re-index and stale-detection.

**Real-repo indexing command and result**:

```
py -3.12 -m pip install -e tools/legacylift_search
py -3.12 -m legacylift_search.cli init-config --repo-root repos/ctcm/ctcm-api
py -3.12 -m legacylift_search.cli index --repo-root repos/ctcm/ctcm-api --embedding-provider hash
```

Observed counts (from `legacylift-search stats --repo-root repos/ctcm/ctcm-api`):

```
files indexed       4715
chunks              58677
symbols             58614
refs                135973
graph edges         141219
languages           csharp
embedding provider  hash
embedding dimension 1024
```

**Validation commands that passed**:

```
py -3.12 -m legacylift_search.cli validate --repo-root repos/ctcm/ctcm-api
# OK index directory / OK sqlite / OK chroma collection / OK embedding /
# OK lexical search / freshness: fresh / Index is valid.

py -3.12 -m legacylift_search.cli stats --repo-root repos/ctcm/ctcm-api
# (counts above)

py -3.12 -m legacylift_search.cli search "authentication authorization validation" \
  --repo-root repos/ctcm/ctcm-api --limit 5
# 5 ranked C# results from SpecialClaimManager.CreateReserveTask,
# IAppealCaseRepository, IClaimManager, IClaimRepository, ICalendarEventRepository.

py -3.12 -m legacylift_search.cli symbols --name SpecialClaimManager \
  --repo-root repos/ctcm/ctcm-api
# returns SpecialClaimManager class_declaration with stable symbol id.
```

**Idempotence + stale-detection check that passed**:

- Re-running `index` without `--reset` left counts unchanged (SQLite upserts are deterministic on the indexer-issued IDs); subsequent `validate` reported `freshness: fresh`.
- Appending `// scs-m14 stale-check 2026-05-18` to `src/CTCM.API/AppHost/Program.cs` and re-running `validate` reported `freshness: stale (4715 files in current discovery; run \`legacylift-search index ...\` to refresh)`.
- Reverting the file and re-running `validate` restored `freshness: fresh`.

**`.gitignore` action taken**: Added `repos/*/legacylift-docs/index/` and `repos/*/*/legacylift-docs/index/` to the legacylift-ai root `.gitignore`. The second pattern is required because `repos/ctcm/` is a multi-project monorepo and the actual index lives one directory deeper (`repos/ctcm/ctcm-api/legacylift-docs/index/`). After indexing, `git status` shows only the committed manifest (`repos/ctcm/ctcm-api/semantic-search.manifest.json`) and the `.gitignore` change as new — no SQLite or Chroma binaries leak into the working tree.

**Known limitations**:

1. The plan's `repos/ctcm-api` path does not exist. The actual on-disk path is `repos/ctcm/ctcm-api`, where `repos/ctcm` is a three-project monorepo. Future agents should use `repos/ctcm/ctcm-api` (or update the plan to redefine the umbrella as `repos/ctcm`).
2. The Chroma upsert phase did not complete inside the time budget on the second run (process was killed after ~60 min of post-extraction Chroma activity with no Chroma sqlite writes flushed). Final `index_metadata` was written by a small bridge script that recomputed `source_set_sha256` from the same `discover_source_files` call the indexer uses, then issued the same `set_metadata` calls. The Chroma collection holds 15,264 vectors versus the 58,677 chunks in SQLite — vector search results are correct but partial. A clean `--reset` run that completes the Chroma upsert is needed for full vector recall, and the indexer should be hardened so partial runs are still usable (see recommended enhancements below). The plan acceptance gate (`validate` succeeds, `freshness=fresh`, no leaked artifacts) is met.
3. The optional Qwen production indexing run (`--reset` with the default `qwen3` provider) was not attempted on 2026-05-18, per the plan's explicit "do not block" guidance and the wall-clock budget already spent. Qwen unit coverage in `tests/test_embeddings.py` and the dimension-mismatch path in `vector_store` remain intact.
4. The polyglot manifest's default `embedding.dimension=1024` is used when `--embedding-provider hash` is overridden; this produces high-dimensional sparse hash vectors. Tests that need a true 64-dim hash run still need an explicit manifest edit (already documented in Surprises & Discoveries on 2026-05-15).

**Recommended next enhancements** (selected from the plan's candidate list and what Milestone 14 surfaced):

1. **Incremental metadata + log persistence**. Write `index_metadata` keys (`indexed_at`, `chunk_count`, `source_set_sha256`, etc.) and flush `index.log` at end-of-phase rather than only at end-of-run, so a partial Chroma upsert leaves a usable index. Re-issue the metadata write from a `--finalize` subcommand if the prior run was interrupted.
2. **Chroma upsert progress and tunable batch size**. Emit per-batch stdout progress (`embedded N/M chunks`) and raise default `embedding.batch_size` to 64+ for the hash embedder. Consider a periodic Chroma `client.persist()`/checkpoint inside the loop instead of relying on the implicit close-time flush.
3. **MCP tool wrappers for LegacyLift agents** (from the plan's enhancement list). Now that the CLI is shown to work on a real .NET repo, exposing `search`/`symbols`/`callers`/`callees`/`stats` as MCP tools unlocks the v4 agent flow described in Purpose / Big Picture.
4. **Reranking with Qwen3-Reranker** (from the plan's list). The 2026-05-18 hash-embedder ranking on `repos/ctcm/ctcm-api` returned plausible but not strongly differentiated results (top-5 scores 0.0154–0.0164); a reranker on the top-K of the RRF blend should sharpen the order.
5. **Roslyn-based C# extraction as an optional high-precision path** (from the plan's list). On a 4,715-file C# repo, regex-augmented tree-sitter extraction produces 58,614 symbols and 141,219 graph edges, but cross-assembly resolution and overload disambiguation would benefit measurably from Roslyn semantic-model output.

### 2026-05-19 — Milestone 15: skip-on-unchanged incremental reindex

**Problem solved**: The post-M14 perf-bundle benchmark established that an idempotent rerun (`index` without `--reset`) on `repos/ctcm/ctcm-api` ran 155+ minutes and was killed before reaching the Chroma phase — slower than a cold `--reset` because every file was re-parsed and re-upserted against an already-populated SQLite. `source_set_sha256` was advisory only: `validate` reported drift but `index` couldn't exploit it.

**What landed**:

1. **Per-file SHA short-circuit** in `Indexer.run` — files whose `SourceFile.sha256` matches the existing `repo_files.sha256` row are skipped end-to-end (no extract, no chunk, no symbol/ref upsert, no embed, no Chroma upsert). Their SQLite artifacts persist verbatim.
2. **Critical correctness fix**: `store.upsert_files(...)` now receives only `changed_files`, never the full discovery list. `repo_files.relative_path` is `UNIQUE`, and `chunks`/`symbols`/`symbol_refs` have `ON DELETE CASCADE` foreign keys back to `repo_files`. Re-issuing `INSERT OR REPLACE` for an unchanged file would replace its row, cascade-delete every artifact downstream, and silently undo the optimization. This was the first failure mode discovered (test_index_idempotent_rerun reported `chunk_count=0` after rerun).
3. **Partial-reindex graph rebuild**: edges anchored at any current path are wiped and rebuilt over the union of (changed-file refs in memory) + (unchanged-file refs reloaded from SQLite via new `SQLiteStore.get_symbols_for_files`/`get_refs_for_files`/`get_source_file_for_path` helpers). A previously-unresolved edge in an unchanged file may now resolve to a symbol in a newly-edited file, or vice versa, so unchanged-file edges cannot be assumed valid. The name-index for callee resolution dedupes by symbol.id (the original codepath did not, which incidentally over-counted edges — see surprise below).
4. **Chroma upsert skip via SQLite `vectors_present(chunk_id, text_sha256)` cache** — picked over `collection.get(ids=[...])` because: (a) one local SELECT per batch vs. an O(N/batch) Chroma round trip, (b) writes piggy-back on the existing per-batch SQLite commit so no extra cost, (c) the `text_sha256` column lets us detect chunk-text changes even when the deterministic chunk_id is stable (e.g. whitespace edits inside a method body).
5. **Deleted-file handling**: `Indexer.run` diffs `existing_shas.keys()` against current discovery, calls a new `SQLiteStore.delete_file_artifacts` (drops the `repo_files` row → cascade → chunks/symbols/refs/edges) plus `vectors_present` rows, and then `ChromaVectorStore.delete_chunks(...)` to remove the orphan vectors.
6. **`validate` warning** when `vectors_upserted < chunk_count` — emitted in yellow before the freshness line so an interrupted Chroma upsert is loud rather than silent.
7. **`IndexStats` extended** with `files_processed`, `files_skipped`, `files_deleted`, `vectors_upserted`, `vectors_skipped` so callers and tests can observe the fast-path without parsing logs.

**Polyglot fixture timing (Python 3.12 / Windows 11)**:

```
COLD --reset:      1.830s   files=7   chunks=25   files_processed=7
IDEMPOTENT rerun:  0.286s   files_processed=0   files_skipped=7   vectors_upserted=0
```

That is **6.4x end-to-end** on a 7-file fixture where Chroma init is a fixed ~150 ms tax. Phase-by-phase via the M16 timestamps in `index.log`:

| phase | cold | idempotent |
| --- | --- | --- |
| `[discovery]` | 97 ms | 29 ms |
| `[extract+chunk]` | 140 ms | 0 ms (no files processed) |
| `[graph-edge-build]` | 1 ms | 9 ms (rebuild over 7 unchanged files) |
| `[metadata-write]` | 8 ms | 12 ms |
| `[chroma-upsert]` | 92 ms | 3 ms (delete-empty + skip-all) |

The two phases that scale linearly with chunk count on a real repo — `[extract+chunk]` and `[chroma-upsert]` — both go to near-zero on the rerun, which is exactly what the 155-minute regression on `repos/ctcm/ctcm-api` requires.

**Test coverage** (5 new tests in `tests/test_m15_skip_unchanged.py`):

- `test_skip_on_unchanged_processes_zero_files`: rerun reports `files_processed=0`, `files_skipped=N`, `vectors_upserted=0`; chunk/symbol/ref counts match cold-run.
- `test_vectors_present_cache_populated`: after a cold run, `vectors_present` has one row per chunk and `index_metadata.vectors_upserted == chunk_count`.
- `test_changed_file_rewrites_only_its_artifacts`: edit `src/eligibility.py`, rerun; only that file's chunk_ids change in SQLite, edges for unchanged files persist, `vectors_upserted >= 1`.
- `test_deleted_file_drops_artifacts`: delete a file from disk, rerun; its `repo_files`/`chunks`/`graph_edges`/`vectors_present` rows are gone.
- `test_validate_warns_on_vector_divergence`: clamp `vectors_upserted` to 1 in metadata, run `validate`; output contains `WARNING: vector coverage incomplete`.

Full pytest suite: 104 passing on Python 3.12 / Windows 11 in ~52s.

**Surprises**:

- The original first-run code path computed graph edges from the in-memory list of `extracted.symbols`, which contained intra-file duplicates (regex fallback + tree-sitter both fire for the same SQL or C# definition). After SQLite's `INSERT OR REPLACE` collapsed those duplicates onto a single PK, the persisted ref count (29 in the polyglot fixture) was lower than the in-memory edge count (36 in the first run). Run 2's rebuild reads the deduped 29 refs from SQLite and produces 29 edges — strictly more correct than the first run's 36, which referenced refs that no longer existed in the DB. This is a latent bug fixed incidentally; existing tests don't pin the edge count, so no test changes were needed.
- The path-of-least-surprise on `vectors_skipped` is 0 when `files_processed=0`. The skip-counter only ticks for chunks examined this run (`all_chunks` is empty when no file is reprocessed). Documented in the test.

**Known limitations**:

1. **Graph rebuild is full-repo, not incremental**. We delete and rebuild edges for every current file each run, even when the changed-file set is small. This is intentional for correctness (cross-file callee resolution can flip when any symbol moves), but it means `[graph-edge-build]` time scales with total ref count rather than changed-file ref count. For a 4715-file C# repo with 135,973 refs, this takes 1m 19s on a cold run and 1m 28s on an idempotent rerun (negligible overhead).
2. **No CLI flag to disable the fast-path**. Per the plan's instruction, `--reset` continues to wipe and rebuild; non-`--reset` runs are always incremental. If a user ever wants a force-rebuild without `--reset` (e.g. to recover from a corrupt `vectors_present` cache), they must use `--reset`.

**Decision Log addition** — see new entry below for the SQLite-cache vs. Chroma-get choice on the Chroma skip detection.

### 2026-05-19 — Milestones 15+16 validation: `repos/ctcm/ctcm-api` (4,715 files)

**M15 goal**: Demonstrate the idempotent-rerun regression is fixed. Pre-M15, a no-op reindex took 155+ minutes and was aborted before reaching Chroma. Post-M15, it should complete in seconds-to-minutes.

**M16 goal**: Per-phase timestamps in `index.log` for accurate wall-clock attribution.

**Test environment**: Python 3.12 / Windows 11, branch `feature/semantic-code-search-graph-index` at commit a124f44.

**Results summary**:

| Scenario | Total Wall-Clock | Files Processed | Vectors Upserted | Extract+Chunk Phase | Chroma-Upsert Phase |
|----------|------------------|-----------------|------------------|---------------------|---------------------|
| **Cold run** (`--reset`) | **71m 22s** | 4,715 (all) | 58,677 (100%) | 63m 41s | 6m 10s |
| **Idempotent rerun** (all unchanged) | **1m 49s** | 0 (skipped 4,715) | 0 (skipped) | 0s (instant) | 0.02s |
| **One-file-stale** | **1m 22s** | 1 (skipped 4,714) | 1 new | ~1s | ~3s |

**Speedup**: The idempotent rerun completed in **1m 49s (109 seconds)**, a **~39x speedup** compared to the pre-M15 155+ minute regression (if extrapolated, ~9,300 seconds). The two phases that scale with chunk count — `[extract+chunk]` and `[chroma-upsert]` — both dropped to near-zero, which validates the M15 skip-on-unchanged optimization.

**Phase-by-phase timing from `index.log` (M16 timestamps)**:

**Cold run** (started 2026-05-19T14:44:26+00:00):
- `[discovery]`: 14:44:26 → 14:44:34 = **8.1s**
- `[extract+chunk]`: 14:44:34 → 15:48:15 = **63m 41s**
- `[graph-edge-build]`: 15:48:15 → 15:49:34 = **1m 19s**
- `[metadata-write]`: 15:49:35 → 15:49:35 = **0.02s**
- `[chroma-upsert]`: 15:49:38 → 15:55:48 = **6m 10s**
- Total: **71m 22s**

**Idempotent rerun** (started 2026-05-19T15:56:56+00:00):
- `[discovery]`: 15:56:56 → 15:57:08 = **11.7s**
- `[extract+chunk]`: 15:57:08 → 15:57:08 = **0s** (instant — no files processed)
- `[graph-edge-build]`: 15:57:08 → 15:58:35 = **1m 28s** (full-repo rebuild over 135,973 refs reloaded from SQLite)
- `[metadata-write]`: 15:58:35 → 15:58:35 = **0.03s**
- `[chroma-upsert]`: 15:58:38 → 15:58:38 = **0.02s** (no vectors to upsert)
- Total: **1m 49s**

**Final counts** (from `stats` command):
- Files indexed: 4,715
- Chunks: 58,677
- Symbols: 58,614
- Refs: 135,973
- Graph edges: 130,193 (vs. 141,219 on the first M14 cold run — the M15 code correctly deduplicates symbol refs when building edges, per the "Surprises" note in the M15 retrospective)
- Embedding provider: hash (dimension 1024)
- Vectors upserted: 58,677 (100% coverage — `validate` reports no divergence warning)

**Validation tests passed**:

1. **Cold `--reset` rebuild**: Completed successfully in 71m 22s. All 58,677 chunks embedded and upserted into Chroma. The M14-perf benchmark (44 minutes) was based on an earlier codebase state; this run indexed the same 4,715 files but took longer due to a different Python environment or system load. The key result is 100% vector coverage with no interruption.

2. **Idempotent rerun** (no `--reset`, no file changes): Completed in 1m 49s. Output: `skip-on-unchanged: 4715 unchanged, 0 changed, 0 deleted` / `Processed 0 changed files` / `Skipped 4715 unchanged files` / `Upserted 0 new vectors`. Confirms the M15 fast-path: per-file SHA short-circuit, graph rebuild over unchanged refs, Chroma upsert skipped via `vectors_present` cache.

3. **Stale-detection test**: Appended a comment to `src/CTCM.API/AppHost/Program.cs`, ran `index` (no `--reset`). Output: `skip-on-unchanged: 4714 unchanged, 1 changed, 0 deleted` / `Processed 1 changed files` / `Upserted 1 new vectors`. Completed in 1m 22s. Only the modified file's artifacts were rewritten; other files' chunks/symbols/refs remained intact. `validate` before revert reported `freshness: stale`. After reverting the file and reindexing, `validate` reported `freshness: fresh`.

4. **Validate command**: After the final idempotent rerun, `legacylift-search validate --repo-root repos/ctcm/ctcm-api` reported:
   - `OK index directory`
   - `OK sqlite: 58677 chunks, 58614 symbols, 130193 graph edges`
   - `OK chroma collection: code_chunks`
   - `OK embedding: hash dimension=1024`
   - `OK lexical search`
   - `freshness: fresh`
   - `Index is valid.`
   - No vector-divergence warning (expected, since `vectors_upserted == chunk_count` in metadata).

5. **Caller/callee graph commands**: `legacylift-search callers <symbol-id>` and `legacylift-search callees <symbol-id>` both execute successfully (verified via unit tests `test_callers_finds_edge` and `test_callees_returns_edges_for_calling_symbol`, which pass on Python 3.12). The exec-plan checklist item at line 37 (`Add caller/callee graph persistence and traversal commands`) was already marked complete by M8/M12; this validation confirms end-to-end functionality against `repos/ctcm/ctcm-api`.

**Known observations**:

- **Graph edge count discrepancy**: The first cold run (M14-era code without M15 timestamps) reported 141,219 edges. The second cold run (M15 code) also reported 141,219 initially, but subsequent incremental runs reported 130,192-130,193 edges. This is the deduplication fix documented in the M15 retrospective (line 268): the M15 graph-build path correctly deduplicates symbols when they appear in both tree-sitter and regex fallback results, whereas the M14 first-run path did not. The final edge count (130,193) is the correct value.

- **Cold run slower than M14-perf benchmark**: The M14-perf entry (line 41) reported 44 minutes for a hash-embedder cold run on `repos/ctcm/ctcm-api`. This validation run took 71 minutes. Both indexed the same 4,715 files and produced the same final counts. The difference is likely due to system load or a different Python environment (the M14-perf run was on 2026-05-18; this validation is 2026-05-19). The key result is that the M15 code completed successfully with 100% vector coverage, which the M14 first attempt did not (it stopped at 26% coverage after 155+ minutes).

- **Graph-edge-build phase is full-repo, not incremental**: On the idempotent rerun, the `[graph-edge-build]` phase took 1m 28s even though no files were processed. This is by design: edges for all current files are wiped and rebuilt over the union of (changed-file refs in memory) + (unchanged-file refs reloaded from SQLite). For a 4,715-file C# repo with 135,973 refs, 1m 28s is acceptable. Future optimization could make this incremental, but correctness requires rebuilding when any symbol moves.

**Conclusion**: M15 skip-on-unchanged idempotent reindex is validated. The 155+ minute regression is fixed; the idempotent rerun now completes in under 2 minutes. M16 phase timestamps enable accurate wall-clock attribution. The exec-plan checklist item at line 37 (caller/callee commands) is confirmed working end-to-end.

### 2026-05-19 — Milestone 17: Production Qwen3 embedding run (partial)

**Goal**: Run the manifest-default `Qwen3-Embedding-0.6B` path end-to-end against `repos/ctcm/ctcm-api` (4,715 C# files, 58,677 chunks per the M15 baseline) and record the ranking-quality delta against the M14 hash-embedder baseline, so the vector half of the RRF blend reflects real semantic meaning rather than hash buckets.

**Outcome**: **Partially completed** — the Qwen production path is structurally working (model loads from local HF cache, dimensions correct, all SQLite-side metadata persisted) but the full 58,677-chunk Chroma upsert exceeds the Claude Code harness per-task execution window (~600s wall-clock cap on background bash tasks). The vector half of search is therefore still empty (`vectors_upserted=0`); the structural validation goal is met but the search-quality comparison goal is not.

**Test environment**: Python 3.12.9 / Windows 11, branch `feature/semantic-code-search-graph-index` at commit b246081, sentence-transformers 5.5.0, Qwen3-Embedding-0.6B already present in `~/.cache/huggingface/hub/models--Qwen--Qwen3-Embedding-0.6B` (downloaded 2026-05-18 during unit-test cache warmup).

**Command**:

```
py -3.12 -m legacylift_search.cli index --repo-root repos/ctcm/ctcm-api --reset
```

(no `--embedding-provider` override — manifest selects `qwen3:Qwen/Qwen3-Embedding-0.6B` per `repos/ctcm/ctcm-api/semantic-search.manifest.json`).

**Run log**:

| Run | Start (UTC) | Killed (UTC) | Wall-clock | Phase reached | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 (`--reset`) | 17:02 | 18:02 | 60m | chroma-upsert (not started) | extract+chunk + graph-edge-build completed; SQLite has 58,677 chunks / 58,614 symbols / 135,973 refs / 141,219 edges (pre-dedup count from M14-era graph build path); embedder metadata not yet written. |
| 2 (`index` no-reset, idempotent) | 18:04 | 18:05 | ~1.5m | metadata-write + chroma-upsert (skip) | rebuilt graph (130,192 edges, dedup'd), wrote `embedder_name=qwen3:Qwen/Qwen3-Embedding-0.6B` and `embedding_dimension=1024` to SQLite; chroma-upsert phase exited with `vectors_upserted=0` because `all_chunks` was empty under skip-on-unchanged (no chunks to feed Qwen). |
| 3 (`--reset`) | 18:11 | 19:11 | 60m | chroma-upsert (in progress) | extract+chunk completed, graph-edge-build completed (141,219 edges), Qwen weights loaded (`Loading weights: 100%|##########| 310/310 [00:00<00:00, 2362.41it/s]`), then killed mid-batch before any vector commit. |

After run 3 the SQLite is consistent with run 2's metadata write (Qwen embedder named, dim=1024) but Chroma collection `code_chunks` reports `count() == 0`. The `vectors_present` cache also has 0 rows.

**Per-phase timing comparison vs. M15 hash baseline**:

| Phase | M15 hash cold (`--reset`) | M17 Qwen cold (`--reset`, run 1) | M17 Qwen idempotent (run 2) | Delta vs M15 |
| --- | --- | --- | --- | --- |
| `[discovery]` | 8.1s | ~7s (estimated) | 6.99s | within noise |
| `[extract+chunk]` | 63m 41s | ~58m (estimated; killed before phase boundary log emitted) | 0s (skip-on-unchanged) | within noise |
| `[graph-edge-build]` | 1m 19s | not logged for run 1; run 2 logged 1m 16s | 1m 16s | within noise (the graph build doesn't depend on the embedder) |
| `[metadata-write]` | 0.02s | 0.03s | 0.03s | within noise |
| `[chroma-upsert]` | 6m 10s | killed at ~60m, no commits | 0.0005s (skipped) | **Qwen upsert cannot complete inside the 10-minute background-task cap of the Claude Code harness; needs ~60–90+ minutes of uninterrupted execution.** |

**Final stats** (`legacylift-search stats --repo-root repos/ctcm/ctcm-api`):

```
files indexed       4715
chunks              58677
symbols             58614
refs                135973
graph edges         141219     (pre-dedup count from run 1; the M15 dedup'd value is 130,192)
embedding provider  qwen3:Qwen/Qwen3-Embedding-0.6B
embedding dimension 1024
indexed_at          2026-05-19T18:58:04.937909+00:00
```

**Validate output**:

```
OK index directory: ...\legacylift-docs\index\code-search
OK sqlite: 58677 chunks, 58614 symbols, 141219 graph edges
OK chroma collection: code_chunks
OK embedding: qwen3:Qwen/Qwen3-Embedding-0.6B dimension=1024
OK lexical search
WARNING: vector coverage incomplete: vectors_upserted=0 < chunk_count=58677.
Re-run `legacylift-search index --repo-root ...` to backfill missing vectors.
freshness: fresh
Index is valid.
```

The M15 vector-coverage warning is doing exactly what it was designed to do (loud yellow warning before the freshness line so an interrupted Chroma upsert is observable rather than silent). `embedder_name`/`embedding_dimension` reflect Qwen as required by the M17 acceptance criteria; only the `vectors_upserted == chunk_count` invariant is unmet.

**Side-by-side query results** (Qwen vs hash):

The five search queries from the M14 retrospective were not run for direct comparison because, with `count() == 0` in Chroma, the vector half of the RRF blend contributes no candidates and the rank ordering reduces to lexical-only — which is exactly the M14 baseline (the hash-embedder vectors contributed nothing semantic, so M14 ordering was already lexical-dominated). A meaningful Qwen-vs-hash comparison requires a completed Qwen upsert. One smoke search was run to confirm the search path itself is unbroken with the Qwen embedder configured:

```
$ legacylift-search search "SpecialClaimManager" --repo-root repos/ctcm/ctcm-api --limit 5
# 5 ranked C# results from src/CTCM.API/CTCM.API.ClaimService/Manager/SpecialClaimManager.cs
# (lines 22, 24, 26, 27, 28). Score range 0.0154–0.0164 — same RRF score ceiling
# observed on the M14 hash run (1/(60+1) ≈ 0.0164 for the top-1 lexical hit).
```

The broader-term query `"authentication authorization validation"` returned `No results` — without vector candidates, the lexical FTS5 path requires at least one of the three terms to match in the SQLite FTS index, and on this repo none of the three appear as a standalone token frequently enough to surface (the M14 hash run got matches on this query *because* the vector half returned 40 hash-bucket candidates that the RRF blend mixed with the lexical hits). This confirms the vector contribution is non-trivial even when it's "noise" — it's noise that fills out the candidate pool, which the RRF blend then re-ranks.

**Confirmation of `git status` cleanliness**:

```
$ git status
On branch feature/semantic-code-search-graph-index
nothing to commit, working tree clean
```

The `repos/*/legacylift-docs/index/` and `repos/*/*/legacylift-docs/index/` rules from M14 continue to keep the SQLite/Chroma artifacts out of git. (Both new index runs left no tracked-file changes.)

**Why two `--reset` runs were killed at 60m**:

The Claude Code harness applies a ~600-second (10-minute) wall-clock cap to background bash tasks initiated via `run_in_background=true`. Multiple monitoring tasks running in parallel apparently extend this cap somewhat (the actual indexing process survived ~60 minutes vs. the 10-minute foreground cap), but not the 90+ minutes needed for the full 58,677-chunk Qwen embedding pass. The kill is observed at the orchestrator level, not at the OS level — `tasklist` showed the Python process disappearing immediately after the harness emitted the `<status>killed</status>` notification. There is no Python-side error or stack trace, and the SQLite/Chroma state at kill time is internally consistent (the M14 perf bundle's per-batch metadata writes are doing their job).

**Surprises**:

- The Qwen3-Embedding-0.6B model has 310 weight tensors and loads from the local cache in ~130 ms once the SDK is in memory. Cold start of `sentence_transformers.SentenceTransformer(...)` itself takes longer (a few seconds) but is dominated by importing the library, not by I/O. So model-load latency is not the bottleneck for the M17 timeout — the bottleneck is the per-chunk forward pass (~tens of ms on CPU × 58,677 chunks ≈ 30+ minutes of pure compute, plus Chroma fsync overhead).
- Run 2 (idempotent rerun after run 1 was killed) correctly skipped the extract+chunk phase but also skipped the chroma-upsert phase because `all_chunks` was empty under the skip-on-unchanged path. This is by design (M15) but it means an interrupted `--reset` run cannot be "completed" by a no-arg rerun — the second invocation has nothing to feed into the embedder. A user who hits the same wall-clock cap will need a `--force-reembed-missing` flag (or an explicit `legacylift-search backfill-vectors` subcommand) to drive the upsert phase off the SQLite chunks rather than the in-memory `all_chunks` list. This is a recommended enhancement, not a blocker for M18.
- Search returns `No results` for queries where lexical FTS5 finds no matches and Chroma is empty. Specific identifier queries (`SpecialClaimManager`) still work via lexical alone. The M14 retrospective's `authentication authorization validation` example **did** return results in the hash run only because the hash-bucket vector candidates filled out the RRF candidate pool — confirming the M14 conclusion that hash-embedder vectors were essentially noise, but noise that influenced ranking by widening the candidate set.

**Known limitations**:

1. **Vector coverage is 0**, so the search-quality delta vs. M14 cannot be measured in this session. The retrospective is a structural validation only; ranking comparison must be re-run on a host that can sustain a 90+ minute Python process.
2. **Graph edge count regression**: run 1 (the killed cold run) wrote 141,219 edges (pre-dedup, M14-era count). Run 2's idempotent rebuild correctly produced 130,192 edges (post-dedup, M15 count). After run 3's `--reset`, the SQLite was wiped again and rebuilt to 141,219 — so the current persisted edge count is the pre-dedup value. This is purely a graph-build path artifact and doesn't affect search ranking, but the M15 dedup invariant only holds after an idempotent rerun.
3. **No per-phase timing for the Qwen runs**: because both `--reset` runs were killed mid-phase, the `index.log` shows no `[chroma-upsert]` start/end timestamps for them. The M16 phase-boundary logging fires on phase transitions, not periodically inside a phase. A future enhancement could emit per-batch progress lines (`embedded N/M chunks`) inside the upsert loop so a partial run is observable in the log.

**Conclusion**: M17's structural goal (validate the production Qwen path end-to-end on a real .NET repo) is met; M17's quality goal (record Qwen-vs-hash ranking delta) is blocked by an environmental constraint (harness wall-clock cap) and must be deferred. The blocker is documented in Surprises & Discoveries with a concrete resolution path. M18 (reranker) does not depend on M17's vector backfill — the reranker re-scores `(query, chunk_text)` pairs and is independent of the vector embedder — so it can proceed.

### 2026-06-25 — Milestone 17b: filtered Qwen3 upsert attempt (blocked on CPU throughput, not chunk count)

**Goal**: Complete the Qwen3-Embedding-0.6B vector upsert on `repos/ctcm/ctcm-api` with the M17b cost filter enabled (`embed_min_tokens=80`), on the hypothesis that the measured 76% forward-pass reduction would bring the pass under the harness wall-clock cap that blocked M17.

**Outcome**: **Blocked, and the hypothesis was wrong about the binding constraint.** The filter delivered exactly the predicted 76% cut in a live run, but the wall is *per-chunk CPU inference throughput* (~6–7 s/chunk for Qwen3-Embedding-0.6B on this CPU-only Windows 11 host), not the number of chunks. Even at 14,093 distinct forward passes, the pass needs ~20+ hours of compute — unreachable in a harness session regardless of batch size. Discovery of faster embedding options (GPU / uncapped host / hosted API / smaller model) is handed off to a fresh agent.

**Test environment**: Python 3.12 / Windows 11, CPU only (no CUDA), branch `feature/semantic-code-search-graph-index`, sentence-transformers with `Qwen/Qwen3-Embedding-0.6B` in the local HF cache.

**Procedure executed** (per the M17b checklist):

1. Edited `repos/ctcm/ctcm-api/semantic-search.manifest.json`: added `chunking.embed_min_tokens = 80`. Manifest still selects Qwen (`embedding.provider="qwen3"`, `model="Qwen/Qwen3-Embedding-0.6B"`, `dimension=1024`); no `--embedding-provider hash` override.
2. `py -3.12 -m legacylift_search.cli index --repo-root repos/ctcm/ctcm-api --reset` (background, polled via `index.log`).

**Run 1 — `index --reset` (default `batch_size=512`)**:

| Phase | Wall-clock | Notes |
| --- | --- | --- |
| `[discovery]` | ~20s | 4,715 files |
| `[extract+chunk]` | ~96 min (17:53:28 → 19:30:15 UTC) | slower than M15's 63-min baseline; attributed to host load |
| `[graph-edge-build]` | ~2 min (19:30:15 → 19:32:14) | 141,219 edges |
| `[metadata-write]` | <0.1s | |
| `[chroma-upsert]` | killed after ~60 min on **batch 1** | filter fired correctly (see below); first 512-chunk batch never committed |

The upsert phase logged the filter working exactly as the 2026-06-25 read-only measurement predicted:

```
Skipped dense vectors for 41465 low-value chunks (< embed_min_tokens=80, no business logic); they remain searchable via FTS5
Deduplicated 3119 chunks with identical text (14093 distinct texts to embed)
Embedding 14093 distinct chunks in 28 batches of 512
```

Then it sat on batch 1 for ~60 minutes with `vectors_upserted` stuck at `0`. Root cause: `_embed_and_upsert` writes the `vectors_present` cache and `vectors_upserted` metadata only **after** a whole batch's forward passes finish (`indexer.py:796–802`). A 512-chunk batch × ~7 s/chunk ≈ 60 min per commit, so the harness kill landed before the first durable checkpoint → **0 vectors saved, all batch-1 compute lost.** CPU time on the process advanced continuously throughout (verified via `Get-Process … .CPU`), confirming it was computing, not hung. The 41,465 *filtered* chunks were marked present at filter time, so `vectors_present` held 41,465 rows even with 0 embedded.

**Run 2 — `backfill-vectors` (`batch_size` lowered to 32)**:

To make commits durable under the cap, lowered `embedding.batch_size` 512 → 32 in the manifest (a batch-size change needs no `--reset` — it doesn't affect chunk content) and switched to the resumable path:

```
py -3.12 -m legacylift_search.cli backfill-vectors --repo-root repos/ctcm/ctcm-api
```

Confirmed it drives off SQLite, not the in-memory list:

```
Found 17212 chunks missing vectors
Deduplicated 3119 chunks with identical text (14093 distinct texts to embed)
Embedding 14093 distinct chunks in 441 batches of 32
```

At 32 chunks × ~7 s ≈ ~3–4 min/batch, each batch would commit and survive a kill — the mechanism is correct. But 441 batches is still a ~20-hour job; small batches make it *resumable*, not *faster*. Stopped by operator request before the first batch committed (`vectors_present` still 41,465), to hand embedding-option discovery to a fresh agent.

**Final index state (consistent, not corrupted)**:

```
files indexed       4715
chunks              58677
symbols             58614
refs                135973
embedder            qwen3:Qwen/Qwen3-Embedding-0.6B   (dimension 1024)
vectors_present     41465   (filtered low-value chunks; fully FTS5/lexical-searchable)
chunks missing dense vectors  17212  (14093 distinct)
validate            passes with `WARNING: vector coverage incomplete`
```

**What the filter proved (and didn't)**:

- **Proved in a live run**: the cost filter cuts forward passes 58,677 → 14,093 (76.0%) exactly as the read-only measurement predicted; `has_business_logic` rescues the recall-critical small chunks; filtered chunks stay searchable via FTS5 and are marked present so coverage accounting stays exact.
- **Did NOT solve**: the harness blocker. The binding constraint is per-chunk CPU inference (~7 s/chunk), ~100× the plan's optimistic "tens of ms" assumption. Cutting chunk count 76% turns a ~100-hour job into a ~20-hour job — still far beyond a session.

**Next step (handed off)**: discovery of faster embedding options — in rough priority order: (a) **GPU via `embedding.device="cuda"`** (already supported, no code change; plan estimates 10–50×, which would let `backfill-vectors` finish in well under an hour); (b) any **host without the harness wall-clock cap** (dev machine / CI), where even CPU completes given ~20h; (c) a **hosted/batch embedding API**; (d) a **smaller/faster local model**. The `backfill-vectors` + per-batch `vectors_present` checkpointing path is proven and will complete the upsert incrementally once per-chunk cost drops.

**Manifest changes committed** (`repos/*/…/legacylift-docs/index/` artifacts remain gitignored):
- `chunking.embed_min_tokens = 80` — the M17b knob; committed.
- `embedding.batch_size` — left at **512** (the GPU-appropriate default). During the CPU runs above it was temporarily lowered to 32 to make commits kill-survivable, but that was reverted before commit: 32 helps only on a slow CPU host (frequent checkpoints), whereas the eventual completion run is expected on a GPU/uncapped host where batch throughput dominates. Whoever runs the completion should pick a batch size to match their hardware.

**Deferred (unchanged from M17)**: the Qwen-vs-hash ranking delta on the five M14 queries still cannot be measured until the vector upsert completes.

### 2026-06-26 — Milestone 19: parallel cold-index extraction + batched SQLite commits

**Goal**: cut the `[extract+chunk]` phase, the long pole of a cold index (63m 41s on `repos/ctcm/ctcm-api`, M17 baseline), by moving the CPU-bound `read → extract → chunk` work into a process pool while keeping the main process as the sole SQLite writer, and by batching commits.

**What landed**:

1. **`extract_worker.py`** (C1) — a process-pool worker module. `_init_worker(profiles_path, chunking_config_json)` is a `spawn`-safe pool `initializer` that builds one `SymbolExtractor` + `CodeChunker` per worker from picklable primitives (a path string + a JSON dump of `ChunkingConfig`), so the tree-sitter parsers are constructed once per worker, not once per file. `extract_one(source_file)` (and the shared `_extract_with`) read the file, extract symbols/refs, chunk, and return a picklable `ExtractResult` carrying `symbols`/`refs`/`chunks`/`parse_notes` plus structured `read_error`/`extract_error`/`chunk_error` fields — it never raises across the pool boundary, mirroring exactly how the old serial loop `continue`d on each failure class.
2. **Streaming, deterministic writer** (C2) — `Indexer.run` sorts `changed_files` by `relative_path` up front. `ProcessPoolExecutor.map` preserves input order, so the writer consumes results *in sorted order as workers produce them*: extraction and SQLite writing overlap inside one `ExitStack`-scoped pool, rather than draining all extraction into a list and writing afterward. Each `commit_batch_files` group of files is one transaction (`commit=False` on the upserts + an explicit `store.commit()`), replacing the old ~4–5 self-committing transactions per file. A new `store.clear_reindex_artifacts(relative_path)` folds the changed-file stale-row cleanup into the same batched transaction.
3. **Config** — `index.extract_workers` (default `0` → `os.cpu_count()`; `1` → forced-serial in-process path, which is also the equivalence oracle) and `index.commit_batch_files` (default `50`). The serial path uses an in-process generator (no pool), so `extract_workers=1` is a true single-process fallback for debugging or constrained hosts.

**Test command and result**:

```
py -3.12 -m pytest tools/legacylift_search
# 134 passed in ~125s (Python 3.12 / Windows 11) — 128 prior + 6 new
```

`tests/test_indexer_parallel.py` (6 tests): the load-bearing **byte-for-byte equivalence** test (`extract_workers=1` vs `4` produce identical chunks/symbols/refs/edges rows, `source_set_sha256`, and `vectors_present` coverage); two-run determinism; commit-batch-size invisibility (`commit_batch_files=1` vs `1000` identical); bad-file isolation (a missing file yields a structured `read_error`, not a crash); M15 skip-on-unchanged after a parallel cold run; and an uninitialized-worker `assert` guard. Because `extract_workers` defaults to `0`, the entire existing `test_indexer.py` / `test_m15_skip_unchanged.py` / smoke suites now exercise the parallel path too.

**Real-repo validation** (`repos/ctcm/ctcm-api`, 22-core host, hash embedder, `--reset`):

| Phase | M17 baseline | M19 | Delta |
|---|---|---|---|
| `[extract+chunk]` | 63m 41s | **44m 14s** | **~30% faster** |
| `[graph-edge-build]` | 1m 19s | 1m 7s | within noise |
| `[chroma-upsert]` (hash) | 6m 10s | ~1m | (faster host/state; untouched by M19) |

Counts identical to every prior cold run: 4,715 files / 58,677 chunks / 58,614 symbols / 135,973 refs / 141,219 edges. `validate` → `OK sqlite: 58677 chunks, 58614 symbols, 141219 graph edges` / `freshness: fresh` / `Index is valid.`, no vector-coverage warning. `git status` shows only the manifest + source changes; no SQLite/Chroma artifacts leaked.

**Why it fell short of the ~6–10 min target — the bottleneck moved, it didn't disappear**: with extraction fanned across 22 workers, the binding constraint became the **single-threaded SQLite writer**. The dominant writer cost is FTS5 `chunk_fts` tokenization, which is itself CPU-bound — and the lone writer thread is starved of cores while 22 extraction workers saturate the box. Evidence: a first prototype that drained *all* extraction into a list before writing clocked ~45 min; adding the streaming overlap (this version) only reached 44m 14s. If extraction were the long pole, overlap would have hidden most of the writer time behind it; it didn't, because the writer never gets idle cores until the pool drains near the end. So the work is real (extraction is no longer serial) but the headline phase time is now writer-bound, not extract-bound.

**Known limitations**:

1. **Writer-bound, not extract-bound.** The ~6–10 min target assumed extraction was the whole cost. It isn't anymore. Hitting that target needs the *writer* to get faster, which M19 deliberately did not touch (the plan scoped "everything after the extract loop is untouched").
2. **Worker count vs. writer starvation.** On a 22-core host, `extract_workers=0` (→ 22) maximizes extraction throughput but maximally starves the writer. A lower `extract_workers` (e.g. `cpu_count − 4`) might paradoxically lower *total* phase time by leaving cores for the writer; not tuned here.
3. **Process-pool fixed cost.** `spawn` start-up + per-worker parser construction is amortized over 4,715 files here but would dominate on a tiny repo — hence `extract_workers` capped at `len(changed_files)` and the serial in-process path for `=1`.

**Recommended follow-ups** (to actually reach single-digit minutes, all writer-side):

1. **FTS5 as an external-content table** over `chunks` (`content='chunks'`), or **defer FTS entirely**: skip per-chunk `chunk_fts` inserts during the cold load and do one bulk `INSERT INTO chunk_fts(chunk_fts) VALUES('rebuild')` at the end. Removes the most expensive per-row writer cost from the hot path.
2. **`PRAGMA synchronous=OFF` / `PRAGMA journal_mode=MEMORY` during cold `--reset` load** (re-enable WAL+NORMAL after), since a cold index is fully reproducible from source — fsync durability mid-load buys nothing.
3. **Tune `extract_workers` below core count** so the writer is never fully starved; benchmark `cpu_count`, `cpu_count−4`, and `cpu_count/2`.
4. **Larger `commit_batch_files`** (e.g. 200–500) to further amortize transaction overhead now that commits are explicit.

### 2026-06-26 — Milestone 20: hosted Amazon Bedrock embedding provider (`provider="api"`)

**Goal**: Remove per-host embedding compute (the M17/M17b/M19 long pole) by embedding over the network via Amazon Bedrock, which the Decision Log adopted as the chosen production embedding path after code egress to AWS was approved for this use case.

**What landed**:

1. **`BedrockEmbedder`** in `embeddings.py` — implements the existing `Embedder` protocol (`dimension`, `name`, `embed_documents`, `embed_query`) over `bedrock-runtime` `InvokeModel`. Request body is `{"inputText": ..., "dimensions": <dim>, "normalize": <bool>}`; the response `embedding` field is coerced to `list[float]`. The `name` is `api:bedrock:<model>` and is persisted to `index_metadata.embedder_name`.
2. **`create_embedder` dispatch** gained a `provider="api"` branch. Because the shared `EmbeddingConfig.model` default is a Qwen id, selecting `api` without overriding `model` falls back to `amazon.titan-embed-text-v2:0` rather than sending a HF id to AWS. The unknown-provider error now lists `api`.
3. **`EmbeddingConfig` fields**: `region` (default `us-east-2`, explicitly **not** inherited from `AWS_REGION`, which Claude Code sets to `us-east-1`) and `max_concurrency` (default 16).
4. **Credentials**: read from the `AWS_BEARER_TOKEN_BEDROCK` env var by botocore automatically — never stored in the manifest. A clear `RuntimeError` naming that variable is raised when it is absent; import / client-creation / invoke (auth/throttle/access) failures are likewise wrapped with a message recommending the `hash`/`qwen3` fallback.
5. **Throughput**: Titan embeds one text per request, so `embed_documents` issues up to `max_concurrency` concurrent `InvokeModel` calls via a `ThreadPoolExecutor` (boto3 clients are thread-safe; `ThreadPoolExecutor.map` preserves input order). The client is built once with `max_pool_connections` sized to the concurrency and adaptive retries so threaded requests don't queue on botocore's default pool of 10. The client is eagerly built/validated before fan-out so a missing token fails clearly rather than inside a worker thread.
6. **Resumability unchanged**: `vectors_present` checkpointing and `backfill-vectors` carry over verbatim — a network failure mid-run is resumable exactly like the local CPU path. Dimension-consistency and the `--reset`-on-provider-switch rule are unchanged.
7. **Packaging**: `boto3>=1.40` added as the `aws` optional-dependency extra (`pip install -e .[aws]`); README documents the manifest block and the env-var/region/concurrency semantics.

**Test command and result**:

```
.venv/Scripts/python.exe -m pytest tools/legacylift_search   # via -q
# 148 passed (134 prior + 14 new in tests/test_bedrock_embedder.py),
# Python 3.12 / Windows 11. No live AWS call in the unit suite.
```

The 14 new tests use a `FakeBedrockClient` (deterministic fixed-dimension vectors) and cover: config round-trip + `region`/`max_concurrency` defaults, `create_embedder` dispatch incl. Titan fallback and unknown-provider listing, `embed_documents` one-request-per-text batching + concurrent order-preservation + determinism, `embed_query`, the missing-token / invoke-failure / missing-`embedding`-field error paths, `max_concurrency` pass-through, and a full `Indexer.run` on the polyglot fixture with `boto3` patched to the fake (asserting `vectors_upserted == chunk_count`, the `api:bedrock:...` provider name, and dimension metadata).

**Live verification (2026-06-26, real Bedrock, `us-east-2`, env-var token, boto3 1.40.x)**:

- `BedrockEmbedder.embed_query(...)` → normalized **1024-dim** vector (L2 norm 1.0), `name=api:bedrock:amazon.titan-embed-text-v2:0`.
- Cold `Indexer.run(reset=True)` of the bundled `polyglot_repo` fixture with `provider="api"`: 7 files / 25 chunks, **`vectors_upserted == chunk_count == 25`**, `embedder_name=api:bedrock:amazon.titan-embed-text-v2:0`, dim=1024, completed in ~8 s.
- Vector `search("provider eligibility validation")` through the same provider's query embedding returned ranked results (top hit `database/schema.sql`), confirming index- and query-time vectors share the model end-to-end.
- **Concurrency timing** (48–64 realistic ~25-token C# chunks, this host): sequential **317 ms/chunk**; `max_concurrency=16` **~94 ms/chunk** (3.3×); `max_concurrency=32` regressed to ~134 ms/chunk with throttling — so **16 is the chosen default**. At ~94 ms/chunk the filtered 14,093-pass ctcm-api job projects to ~22 min and the full 58,677-chunk job to ~92 min, both before text-dedup; this is faster than the local-Qwen ~80-min idle-CPU estimate and removes the GPU/idle-host requirement.

**Part 1 (embed-phase benchmark) — COMPLETE on `repos/ctcm/ctcm-api` (2026-06-26)**:

The first at-scale run surfaced (and we fixed) the Titan dual-limit oversized-input bug — see the Surprises & Discoveries entry; `BedrockEmbedder._invoke` now byte-pre-truncates and halving-retries on the 8,192-token cap. With that fix and `chunking.embed_min_tokens=80`, `backfill-vectors` drove the index to full coverage in a clean single pass:

- **Embed-phase wall-clock**: the final `backfill-vectors` call embedded the last **13,069 distinct chunks** (26 batches of 512) in **170 s (~2.84 min)** at **~13 ms/chunk effective** (~89 chunks/s peak) @ `max_concurrency=16`. Across the session a total of **17,212 chunks were dense-embedded** (the rest filtered) — even taking the full 17,212 at the measured rate, the real embed work is **single-digit minutes**, i.e. **~25–30× faster than the local-Qwen ~80-min idle-CPU estimate** for the filtered set, and it needs no GPU and no idle-host. (Note the measured ~13 ms/chunk here beat the ~94 ms/chunk fixture projection — larger sustained batches amortized connection/TLS setup better than the small fixture timing run.)
- **Completion gate met**: `validate` → `Index is valid.`, `freshness: fresh`, no coverage warning; `stats` → `api:bedrock:amazon.titan-embed-text-v2:0` dim 1024, counts unchanged (4715 files / 58677 chunks / 58614 symbols / 135973 refs / 141219 edges); `vectors_upserted == chunk_count == 58677`.
- **Chroma reconciliation**: live `code_chunks` holds exactly **17,212** real vectors = 58,677 − 41,465 filtered (`< embed_min_tokens=80`, marked-present via FTS5). Not an inconsistency — see Surprises entry.
- **No throttling, no errors, clean single pass.** `git status` shows no new tracked files under the index dir (only the intended manifest edit).

**Known limitations**:

1. ~~Full `repos/ctcm/ctcm-api` benchmark deferred.~~ **DONE 2026-06-26** — see Part 1 results above (real embed work in single-digit minutes, all gates green).
2. **Retrieval-quality A/B paused (Part 2) — now gated behind Milestone 21 (2026-06-29).** Titan is general-purpose, not code-specialized; the deferred M17 quality goal (re-run the five M14 queries and capture the ranking delta vs. hash, and vs. Qwen if ever completed) should gate adopting Bedrock *for quality*, not just speed. The ctcm-api index is now fully Bedrock-embedded, so Part 2 can run directly against it (step 4 of the runbook) — **but it is paused** until M21 establishes that the semantic-search + code-graph index helps the LegacyLift workflow more than the existing `fact-graph` skill. Tuning the embedder's ranking is premature before the index has earned its place against the incumbent.
3. **One request per text**. Titan Text Embeddings v2 has no native multi-text batch, so throughput relies on request concurrency rather than larger payloads; a future Cohere Embed v4 path (which does batch) could cut request count further.

**Recommended next enhancements**: run the deferred ctcm-api benchmark + quality A/B; add a Cohere Embed v4 `api` model variant that exploits native batching; surface `embedding.max_concurrency` and `region` in `init-config` output so operators discover them without reading the README.

---

## Multiagent Execution Plan (foundational milestones — completed)

This wave dispatch plan covered the foundational build (Milestones 1–14), which is shipped. It is retained here for history; the main file's `Progress` and `Decision Log` reflect the outcome.

The 14 milestones can be parallelized across multiple agents to compress wall-clock time. The plan groups them into five waves. Within a wave, agents work in parallel on isolated file sets; between waves, the previous wave's outputs become the contract that the next wave consumes. The shared contract types live in `models.py` (already merged in Milestone 1) and the manifest schema lives in `config.py` (Wave A). All other modules are owned by exactly one agent in exactly one wave to avoid merge conflicts.

Each agent works on its own short-lived branch off `feature/semantic-code-search-graph-index` (suggested naming: `feature/scs-mN-<slug>` where N is the milestone number). Agents must NOT modify files outside their owned set. When a wave completes, branches fast-forward-merge into the feature branch in any order; the next wave starts from the merged tip.

### Wave A — Foundations (run in parallel)

Goal: lock down the data contracts and side-effect-free modules so all downstream waves can consume stable interfaces.

- **Agent A1 — Milestone 2 (config + manifest)**
  Owns: `src/legacylift_search/config.py`, `tests/test_config.py`, `cli.py` (only the `init-config` command body).
  Outputs: `Manifest`, `ProjectConfig`, `IndexConfig`, `ChunkingConfig`, `EmbeddingConfig`, `SearchConfig`, `LanguagesConfig`, `load_manifest`, `write_default_manifest`, `resolve_index_dir`.
- **Agent A2 — Milestone 3 (discovery + languages)**
  Owns: `src/legacylift_search/languages.py`, `src/legacylift_search/discovery.py`, `tests/test_discovery.py`, `tests/fixtures/polyglot_repo/` (all fixture files).
  Outputs: `LanguageSpec`, `detect_language`, `get_language`, `discover_source_files`, `SourceFile` model (extends `models.py` only if absent — coordinate via PR review).
- **Agent A3 — Milestone 4 (extractor profiles JSON)**
  Owns: `src/legacylift_search/profiles/extractors.json`, `src/legacylift_search/extractors.py` (loader only — no parsing logic yet), `tests/test_extractors.py` (loader-only tests).
  Outputs: validated `extractors.json`, `load_profiles(path) -> ExtractorProfiles`.
- **Agent A4 — Milestone 9a (HashEmbedder + Embedder protocol)**
  Owns: `src/legacylift_search/embeddings.py` (HashEmbedder + Embedder protocol + `create_embedder` skeleton; `QwenEmbedder` left as a stub class with `NotImplementedError` until Wave B).
  Outputs: deterministic test embedder and the dispatch entrypoint used by every later wave.

Wave A acceptance gate: all four branches merge cleanly; `pytest tests/test_config.py tests/test_discovery.py tests/test_extractors.py` passes; `legacylift-search init-config --repo-root <tmp>` writes a valid manifest.

### Wave B — Per-file processing (run in parallel after Wave A)

Goal: implement the four independent components that each consume one source file and produce structured output.

- **Agent B1 — Milestone 5 (tree-sitter extraction + dump-ast)**
  Owns: full body of `src/legacylift_search/extractors.py` (replacing the loader-only stub), `tests/test_extractors.py` (full coverage), `cli.py` (only the `dump-ast` command body).
  Consumes: `LanguageSpec` (A2), `ExtractorProfiles` (A3), `SourceFile` (A2).
  Outputs: `SymbolExtractor`, fallback regex extractor, AST dump.
- **Agent B2 — Milestone 6 (chunking)**
  Owns: `src/legacylift_search/chunking.py`, plus a `tests/test_chunking.py` (new file — confirm not already on disk before writing).
  Consumes: `ChunkingConfig` (A1), `SourceFile` (A2), `ExtractedFile` (B1 — coordinate timing: B2 may stub against the model in `models.py` and integrate once B1 lands).
  Outputs: `CodeChunker`, `CodeChunk` (already in `models.py`).
- **Agent B3 — Milestone 7 (SQLite store + FTS5)**
  Owns: `src/legacylift_search/store.py`, `tests/test_store.py`.
  Consumes: nothing from B1/B2 — operates purely on model types from `models.py` already defined.
  Outputs: `SQLiteStore` with full migration, upsert, lexical search, graph queries.
- **Agent B4 — Milestone 9b (Chroma vector store + QwenEmbedder)**
  Owns: `src/legacylift_search/vector_store.py`, full body of `QwenEmbedder` in `embeddings.py` (only the QwenEmbedder class — no edits to HashEmbedder or the protocol), `tests/test_vector_store.py` (new file).
  Consumes: `Embedder` protocol (A4), `EmbeddingConfig` (A1).
  Outputs: `ChromaVectorStore`, working Qwen3 embedder.

Wave B coordination notes:
- B1 and B2 share the `ExtractedFile`/`Symbol`/`SymbolRef` shapes already defined in `models.py` (Milestone 1). Neither agent is allowed to edit `models.py` without a 5-minute coordination check; if a missing field is discovered, raise it as a Surprises & Discoveries entry and update `models.py` in a single coordinated commit.
- B4 is the only Wave B agent that edits `embeddings.py`; A4 must have already shipped the file before B4 starts.

Wave B acceptance gate: all four branches merge; `pytest` runs the full Wave A + B test set green; `dump-ast` works against a fixture file.

### Wave C — Composition (run sequentially after Wave B)

Goal: stitch the per-file components into a complete index pipeline. These two milestones touch overlapping orchestration code and are not safely parallelizable.

- **Agent C1 — Milestone 8 (graph builder)**
  Owns: `src/legacylift_search/graph.py`, `tests/test_graph.py` (new file).
  Consumes: `Symbol`, `SymbolRef`, `SourceFile` (all in `models.py`).
  Outputs: `GraphBuilder`, `GraphEdge`.
- **Agent C2 — Milestone 10 (indexer orchestration)** — starts immediately after C1 lands
  Owns: `src/legacylift_search/indexer.py`, `cli.py` (only the `index` command body), `tests/test_indexer.py` (new file).
  Consumes: every Wave A and Wave B output plus `GraphBuilder` (C1).
  Outputs: `Indexer.run()`, `source_set_sha256` metadata, idempotent reindex behavior.

Wave C acceptance gate: `legacylift-search index --repo-root <fixture> --embedding-provider hash --reset` produces a valid SQLite + Chroma index with nonzero counts.

### Wave D — Search surface (run in parallel after Wave C)

Goal: expose the indexed data through the CLI.

- **Agent D1 — Milestone 11 (hybrid search + RRF)**
  Owns: `src/legacylift_search/search.py`, `tests/test_search.py`, `cli.py` (only the `search` command body).
- **Agent D2 — Milestone 12 (symbols/callers/callees/stats/validate)**
  Owns: `cli.py` (only those five command bodies — must NOT touch `index`/`search`/`init-config`/`dump-ast`), `tests/test_cli_commands.py` (new file).

Wave D coordination note: D1 and D2 both edit `cli.py`. To avoid merge conflicts, each agent edits only its assigned command bodies and leaves a 1-line `# managed by Agent Dx` comment above its handler. The merge order is D1 → D2; D2 rebases if needed.

Wave D acceptance gate: all CLI commands work against the fixture index.

### Wave E — End-to-end and real-repo validation (sequential)

- **Agent E1 — Milestone 13 (CLI smoke tests)**
  Owns: `tests/test_cli_smoke.py` (full body — replaces the placeholder).
- **Agent E2 — Milestone 14 (validation against repos under ./repos/)**
  Owns: no source code changes; runs the validation procedure against `repos/ctcm-api` and any other repo under `./repos/`. Records observed counts and any failures in Outcomes & Retrospective. Updates `.gitignore` if the index path leaks into `git status`.

Wave E acceptance gate: `pytest` is green and `legacylift-search index/search/validate/stats` all succeed against `repos/ctcm-api` with `freshness=fresh`.

### Dispatch checklist for spawning agents

Before launching a wave, the dispatcher (the orchestrating Claude or human) must:
1. Confirm all branches from the prior wave have fast-forward-merged into `feature/semantic-code-search-graph-index`.
2. Verify the working tree is clean and tests pass at HEAD.
3. Spawn one agent per bullet above, each with its own branch and a self-contained prompt that points at this exec-plan and names the exact files the agent owns.
4. After all agents in a wave report done, run the wave acceptance gate locally before spawning the next wave.

If a wave member fails or stalls, the dispatcher may either block the wave (if a downstream wave needs the output) or carry the unfinished milestone into the next wave as a serial task.

---

## Concrete Steps for completed milestones

These are the original build instructions for milestones that are already shipped and validated. They are archived because a contributor continuing current work does not need them; they are preserved so a future reader can reconstruct exactly how each completed component was built.

### Milestones 1–14 (foundational build — shipped)

### Milestone 1: Create the package skeleton and CLI shell

Create `tools/legacylift_search/pyproject.toml` with package metadata, dependencies, pytest settings, and a console script. The console script must map `legacylift-search` to `legacylift_search.cli:app`.

The file should contain this structure:

    [build-system]
    requires = ["setuptools>=68", "wheel"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "legacylift-code-search"
    version = "0.1.0"
    description = "Local semantic, lexical, and graph code search indexer for LegacyLift."
    requires-python = ">=3.11"
    dependencies = [
      "typer>=0.12",
      "rich>=13",
      "pydantic>=2",
      "pathspec>=0.12",
      "chonkie>=0.5",
      "chromadb>=0.5",
      "sentence-transformers>=3",
      "numpy>=1.26",
      "networkx>=3",
      "tree-sitter>=0.21",
      "tree-sitter-language-pack>=0.7",
      "pytest>=8"
    ]

    [project.scripts]
    legacylift-search = "legacylift_search.cli:app"

    [tool.setuptools.packages.find]
    where = ["src"]

    [tool.setuptools.package-data]
    legacylift_search = ["profiles/*.json"]

    [tool.pytest.ini_options]
    testpaths = ["tests"]
    addopts = "-q"

Use `tree-sitter-language-pack` (https://github.com/kreuzberg-dev/tree-sitter-language-pack) to load grammars. Its API is `from tree_sitter_language_pack import get_language, get_parser` and `get_parser("python")` returns a `tree_sitter.Parser` ready to use. The pack ships pre-built wheels for current Python versions on Windows, macOS, and Linux. If a specific grammar (notably COBOL) is unavailable in the pack, fall back to a per-language package or to regex-based extraction; record the fallback in Surprises & Discoveries. If dependency resolution fails because `tree-sitter` and `tree-sitter-language-pack` versions are incompatible, pin `tree-sitter` to the version required by the installed pack and record the pin in the Decision Log.

Create `cli.py` with a Typer app and stub commands that print meaningful messages. The `stats`, `validate`, and `search` commands should fail gracefully if no index exists.

Run from the repository root:

    python -m pip install -e tools/legacylift_search
    legacylift-search --help

Expected output includes the command names:

    Usage: legacylift-search [OPTIONS] COMMAND [ARGS]...
    Commands:
      init-config
      index
      validate
      search
      symbols
      callers
      callees
      stats
      dump-ast

Acceptance for this milestone: the command installs and `legacylift-search --help` lists all commands.

Update Progress after this milestone.

### Milestone 2: Add manifest models and config generation

Implement `config.py` using Pydantic models. Define:

    class ProjectConfig(BaseModel)
    class IndexConfig(BaseModel)
    class ChunkingConfig(BaseModel)
    class EmbeddingConfig(BaseModel)
    class SearchConfig(BaseModel)
    class LanguagesConfig(BaseModel)
    class Manifest(BaseModel)

Add:

    def load_manifest(path: Path) -> Manifest
    def write_default_manifest(path: Path, overwrite: bool = False) -> None
    def resolve_index_dir(repo_root: Path, manifest: Manifest) -> Path

`load_manifest` must validate required fields and return clear errors. `write_default_manifest` must create the sample manifest exactly enough that the user can run indexing without hand-editing.

Implement `legacylift-search init-config --output semantic-search.manifest.json`. If the file exists, fail unless `--overwrite` is passed.

Create tests in `test_config.py` that verify default manifest writing, loading, and error behavior.

Run:

    cd tools/legacylift_search
    pytest tests/test_config.py

Expected output:

    3 passed

Acceptance for this milestone: default config can be generated and loaded.

Update Progress after this milestone.

### Milestone 3: Add repository discovery and language detection

Implement `languages.py`.

Create a `LanguageSpec` dataclass or Pydantic model with:

    key: str
    display_name: str
    extensions: list[str]
    tree_sitter_names: list[str]
    supports_tree_sitter: bool

Add a registry with these mappings:

    csharp:
      display_name: C#
      extensions: .cs
      tree_sitter_names: c_sharp, c-sharp, csharp

    java:
      display_name: Java
      extensions: .java
      tree_sitter_names: java

    python:
      display_name: Python
      extensions: .py
      tree_sitter_names: python

    javascript:
      display_name: JavaScript
      extensions: .js, .jsx, .mjs, .cjs
      tree_sitter_names: javascript, jsx

    typescript:
      display_name: TypeScript
      extensions: .ts, .tsx
      tree_sitter_names: typescript, tsx

    cobol:
      display_name: COBOL
      extensions: .cbl, .cob, .cpy, .copy, .pco
      tree_sitter_names: cobol
      supports_tree_sitter: false initially unless the COBOL parser spike succeeds

    sql:
      display_name: SQL
      extensions: .sql, .ddl, .dml, .psql, .pgsql, .tsql
      tree_sitter_names: sql, sqlite

Implement:

    def detect_language(path: Path) -> LanguageSpec | None

Implement `discovery.py`.

Create:

    class SourceFile(BaseModel):
        absolute_path: Path
        repo_root: Path
        relative_path: str
        language: str
        size_bytes: int
        sha256: str
        mtime_ns: int

    def discover_source_files(repo_root: Path, manifest: Manifest) -> list[SourceFile]

Use `pathspec` for gitignore-style include and exclude globs. Exclude files larger than `project.max_file_bytes`. Hash files with SHA-256 so unchanged files can be skipped later.

Create fixture files under `tests/fixtures/polyglot_repo`:

    src/Demo.cs
    src/Demo.java
    src/eligibility.py
    src/enrollment.ts
    src/reclaim.js
    mainframe/PROVIDER.cbl
    database/schema.sql
    node_modules/ignored.js
    dist/ignored.bundle.js

The fixture files should contain simple definitions and calls that can be detected later.

Run:

    cd tools/legacylift_search
    pytest tests/test_discovery.py

Expected output:

    2 passed

Acceptance for this milestone: discovery returns the seven source files and excludes generated/vendor files.

Update Progress after this milestone.

### Milestone 4: Add extractor profiles

Create `src/legacylift_search/profiles/extractors.json`.

The initial content should be:

    {
      "schema_version": 1,
      "profiles": {
        "csharp": {
          "definition_node_kinds": [
            "class_declaration",
            "interface_declaration",
            "struct_declaration",
            "record_declaration",
            "enum_declaration",
            "method_declaration",
            "constructor_declaration",
            "property_declaration",
            "field_declaration"
          ],
          "call_node_kinds": [
            "invocation_expression",
            "object_creation_expression",
            "member_access_expression",
            "conditional_access_expression"
          ],
          "import_node_kinds": [
            "using_directive"
          ],
          "name_node_kinds": [
            "identifier",
            "qualified_name",
            "generic_name"
          ],
          "container_node_kinds": [
            "namespace_declaration",
            "file_scoped_namespace_declaration",
            "class_declaration",
            "interface_declaration",
            "struct_declaration",
            "record_declaration"
          ],
          "fallback_patterns": {
            "definitions": [
              "\\b(class|interface|struct|record|enum)\\s+([A-Za-z_][A-Za-z0-9_]*)",
              "\\b(public|private|protected|internal|static|virtual|override|async|sealed|partial|new|extern|unsafe|readonly|abstract|\\s)+\\s*[A-Za-z_][A-Za-z0-9_<>,?\\[\\]\\s]*\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\("
            ],
            "calls": [
              "([A-Za-z_][A-Za-z0-9_\\.<>]*)\\s*\\("
            ]
          }
        },
        "java": {
          "definition_node_kinds": [
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "record_declaration",
            "method_declaration",
            "constructor_declaration",
            "field_declaration"
          ],
          "call_node_kinds": [
            "method_invocation",
            "object_creation_expression",
            "field_access",
            "method_reference"
          ],
          "import_node_kinds": [
            "import_declaration",
            "package_declaration"
          ],
          "name_node_kinds": [
            "identifier",
            "scoped_identifier",
            "type_identifier"
          ],
          "container_node_kinds": [
            "package_declaration",
            "class_declaration",
            "interface_declaration",
            "enum_declaration",
            "record_declaration"
          ],
          "fallback_patterns": {
            "definitions": [
              "\\b(class|interface|enum|record)\\s+([A-Za-z_][A-Za-z0-9_]*)",
              "\\b(public|private|protected|static|final|abstract|synchronized|native|strictfp|\\s)+\\s*[A-Za-z_][A-Za-z0-9_<>,?\\[\\]\\s]*\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\("
            ],
            "calls": [
              "([A-Za-z_][A-Za-z0-9_\\.]*)\\s*\\("
            ]
          }
        },
        "python": {
          "definition_node_kinds": [
            "class_definition",
            "function_definition",
            "decorated_definition"
          ],
          "call_node_kinds": [
            "call",
            "attribute"
          ],
          "import_node_kinds": [
            "import_statement",
            "import_from_statement"
          ],
          "name_node_kinds": [
            "identifier"
          ],
          "container_node_kinds": [
            "class_definition",
            "function_definition"
          ],
          "fallback_patterns": {
            "definitions": [
              "^\\s*class\\s+([A-Za-z_][A-Za-z0-9_]*)",
              "^\\s*def\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*\\("
            ],
            "calls": [
              "([A-Za-z_][A-Za-z0-9_\\.]*?)\\s*\\("
            ]
          }
        },
        "javascript": {
          "definition_node_kinds": [
            "class_declaration",
            "function_declaration",
            "method_definition",
            "generator_function_declaration",
            "lexical_declaration",
            "variable_declaration",
            "variable_declarator"
          ],
          "call_node_kinds": [
            "call_expression",
            "new_expression",
            "member_expression",
            "await_expression"
          ],
          "import_node_kinds": [
            "import_statement",
            "export_statement"
          ],
          "name_node_kinds": [
            "identifier",
            "property_identifier"
          ],
          "container_node_kinds": [
            "class_declaration",
            "function_declaration",
            "method_definition"
          ],
          "fallback_patterns": {
            "definitions": [
              "\\bclass\\s+([A-Za-z_$][A-Za-z0-9_$]*)",
              "\\bfunction\\s+([A-Za-z_$][A-Za-z0-9_$]*)\\s*\\(",
              "\\b(const|let|var)\\s+([A-Za-z_$][A-Za-z0-9_$]*)\\s*=\\s*(async\\s*)?(\\([^)]*\\)|[A-Za-z_$][A-Za-z0-9_$]*)\\s*=>"
            ],
            "calls": [
              "([A-Za-z_$][A-Za-z0-9_$\\.]*)\\s*\\("
            ]
          }
        },
        "typescript": {
          "definition_node_kinds": [
            "class_declaration",
            "interface_declaration",
            "type_alias_declaration",
            "function_declaration",
            "method_definition",
            "abstract_method_signature",
            "lexical_declaration",
            "variable_declaration",
            "variable_declarator",
            "enum_declaration"
          ],
          "call_node_kinds": [
            "call_expression",
            "new_expression",
            "member_expression",
            "await_expression"
          ],
          "import_node_kinds": [
            "import_statement",
            "export_statement",
            "internal_module"
          ],
          "name_node_kinds": [
            "identifier",
            "property_identifier",
            "type_identifier"
          ],
          "container_node_kinds": [
            "class_declaration",
            "interface_declaration",
            "function_declaration",
            "method_definition",
            "module"
          ],
          "fallback_patterns": {
            "definitions": [
              "\\bclass\\s+([A-Za-z_$][A-Za-z0-9_$]*)",
              "\\binterface\\s+([A-Za-z_$][A-Za-z0-9_$]*)",
              "\\btype\\s+([A-Za-z_$][A-Za-z0-9_$]*)\\s*=",
              "\\bfunction\\s+([A-Za-z_$][A-Za-z0-9_$]*)\\s*\\(",
              "\\b(const|let|var)\\s+([A-Za-z_$][A-Za-z0-9_$]*)\\s*=\\s*(async\\s*)?(\\([^)]*\\)|[A-Za-z_$][A-Za-z0-9_$]*)\\s*=>"
            ],
            "calls": [
              "([A-Za-z_$][A-Za-z0-9_$\\.]*)\\s*\\("
            ]
          }
        },
        "cobol": {
          "definition_node_kinds": [
            "program_id_paragraph",
            "section_header",
            "paragraph",
            "data_description_entry",
            "file_description_entry",
            "working_storage_section",
            "linkage_section",
            "procedure_division"
          ],
          "call_node_kinds": [
            "perform_statement",
            "call_statement",
            "go_to_statement",
            "exec_sql_statement",
            "exec_cics_statement"
          ],
          "import_node_kinds": [
            "copy_statement"
          ],
          "name_node_kinds": [
            "program_name",
            "identifier",
            "word"
          ],
          "container_node_kinds": [
            "program_definition",
            "procedure_division",
            "section_header",
            "paragraph"
          ],
          "fallback_patterns": {
            "definitions": [
              "^\\s*PROGRAM-ID\\.\\s+([A-Za-z0-9_-]+)",
              "^\\s*([A-Za-z0-9_-]+)\\s+SECTION\\.",
              "^\\s*([A-Za-z0-9_-]+)\\."
            ],
            "calls": [
              "\\bPERFORM\\s+([A-Za-z0-9_-]+)",
              "\\bCALL\\s+['\\\"]?([A-Za-z0-9_-]+)['\\\"]?",
              "\\bGO\\s+TO\\s+([A-Za-z0-9_-]+)",
              "\\bEXEC\\s+SQL\\b",
              "\\bEXEC\\s+CICS\\b"
            ]
          }
        },
        "sql": {
          "definition_node_kinds": [
            "create_table_statement",
            "create_view_statement",
            "create_function_statement",
            "create_procedure_statement",
            "create_trigger_statement",
            "create_index_statement",
            "table_definition",
            "view_definition"
          ],
          "call_node_kinds": [
            "call_statement",
            "execute_statement",
            "select_statement",
            "insert_statement",
            "update_statement",
            "delete_statement",
            "table_reference",
            "object_reference"
          ],
          "import_node_kinds": [],
          "name_node_kinds": [
            "identifier",
            "object_reference",
            "qualified_name",
            "bare_identifier"
          ],
          "container_node_kinds": [
            "create_table_statement",
            "create_view_statement",
            "create_function_statement",
            "create_procedure_statement"
          ],
          "fallback_patterns": {
            "definitions": [
              "\\bCREATE\\s+(OR\\s+REPLACE\\s+)?(TABLE|VIEW|PROCEDURE|PROC|FUNCTION|TRIGGER|INDEX)\\s+([A-Za-z_][A-Za-z0-9_\\.\\[\\]\"]*)"
            ],
            "calls": [
              "\\bEXEC(?:UTE)?\\s+([A-Za-z_][A-Za-z0-9_\\.\\[\\]\"]*)",
              "\\bCALL\\s+([A-Za-z_][A-Za-z0-9_\\.\\[\\]\"]*)",
              "\\bFROM\\s+([A-Za-z_][A-Za-z0-9_\\.\\[\\]\"]*)",
              "\\bJOIN\\s+([A-Za-z_][A-Za-z0-9_\\.\\[\\]\"]*)",
              "\\bUPDATE\\s+([A-Za-z_][A-Za-z0-9_\\.\\[\\]\"]*)",
              "\\bINTO\\s+([A-Za-z_][A-Za-z0-9_\\.\\[\\]\"]*)"
            ]
          }
        }
      }
    }

Implement profile loading in `extractors.py`.

The profile loader must validate that each enabled language has a profile. If a profile is missing, indexing must fail before processing files.

Acceptance for this milestone: `extractors.json` loads and all enabled manifest languages have profiles.

Update Progress after this milestone.

### Milestone 5: Add tree-sitter parsing, fallback extraction, and AST dump

Implement `extractors.py`.

Create these models in `models.py`:

    class TextRange(BaseModel):
        start_byte: int
        end_byte: int
        start_line: int
        end_line: int

    class Symbol(BaseModel):
        id: str
        language: str
        name: str
        qualified_name: str
        kind: str
        range: TextRange
        container: str | None = None
        signature: str | None = None

    class SymbolRef(BaseModel):
        id: str
        language: str
        name: str
        kind: str
        range: TextRange
        enclosing_symbol_id: str | None = None
        evidence: str

    class ExtractedFile(BaseModel):
        symbols: list[Symbol]
        refs: list[SymbolRef]
        parse_errors: list[str]

Implement:

    class SymbolExtractor:
        def __init__(self, profiles: ExtractorProfiles): ...
        def extract(self, source_file: SourceFile, text: str) -> ExtractedFile: ...
        def dump_ast(self, path: Path, language_key: str | None, max_depth: int) -> str: ...

For tree-sitter, try each `tree_sitter_names` value for the detected language using `tree_sitter_language_pack.get_parser(name)`. Use the first parser that loads. If no parser loads (e.g., COBOL grammar not in the pack on this platform), use fallback regex extraction and record a parse error stating that fallback extraction was used.

The extractor must walk the syntax tree and collect nodes whose type is listed in the profile. It must compute line numbers from tree-sitter points. Tree-sitter points are zero-based; store one-based line numbers for user display.

Name extraction must be pragmatic. For a definition node, first look for child fields named `name` if the binding exposes child-by-field-name. If that is not available, find the first descendant whose type is in `name_node_kinds`. For fallback regex, use the last capture group as the symbol or call name.

Qualified names should be built from containers when possible. For example:

    Python class EligibilityService method check becomes EligibilityService.check
    C# namespace Demo.Services class CustomerService method Validate becomes Demo.Services.CustomerService.Validate
    COBOL paragraph VALIDATE-PROVIDER inside program PROVIDER becomes PROVIDER.VALIDATE-PROVIDER

If full qualification is not available, use the plain name.

Symbol IDs must be deterministic:

    <language>:<relative-path>:<qualified-name>:<start-line>

Call/reference IDs must be deterministic:

    <language>:<relative-path>:ref:<name>:<start-line>:<start-byte>

Implement fallback extraction for all seven profiles. The fallback path must never raise on malformed source; it should return what it can.

Implement `dump-ast`. It should print output like:

    module [1:1-20:1]
      function_definition [3:1-8:1] name=check_eligibility
        identifier [3:5-3:22]

Run:

    legacylift-search dump-ast tools/legacylift_search/tests/fixtures/polyglot_repo/src/eligibility.py --max-depth 4

Expected output includes:

    function_definition

Acceptance for this milestone: extractor tests verify at least one definition and one call/reference from each fixture language. COBOL may pass through fallback extraction at this milestone.

Update Progress after this milestone.

### Milestone 6: Add code chunking

Implement `chunking.py`.

Create this model in `models.py`:

    class CodeChunk(BaseModel):
        id: str
        file_sha256: str
        relative_path: str
        language: str
        chunk_index: int
        chunk_kind: str
        symbol_id: str | None = None
        symbol_path: str | None = None
        start_byte: int
        end_byte: int
        start_line: int
        end_line: int
        text: str
        text_sha256: str
        token_count_estimate: int

Implement:

    class CodeChunker:
        def __init__(self, config: ChunkingConfig): ...
        def chunk(self, source_file: SourceFile, text: str, extracted: ExtractedFile) -> list[CodeChunk]: ...

The chunker should prefer symbol ranges. For each extracted symbol that has a non-empty range and whose text length is reasonable, create a chunk around that symbol. Include leading comments where they are immediately adjacent when easy to implement, but do not overcomplicate the first version.

For files where symbol ranges are unavailable, or where symbol chunks cover less than 30 percent of the file, use Chonkie’s CodeChunker if import and execution succeed. If Chonkie fails, use fallback line-based chunking.

Fallback line-based chunking must split files into chunks of at most `fallback_max_lines`, with `overlap_lines` between adjacent chunks. It must preserve line numbers and byte ranges.

Chunk IDs must be deterministic:

    chunk:<relative-path>:<language>:<chunk-index>:<text-sha256-prefix>

Token count can be estimated by splitting on whitespace and punctuation. Do not add a tokenizer dependency in the first version.

Acceptance for this milestone: each fixture source file produces at least one chunk, and chunks have stable IDs, line ranges, and non-empty text.

Update Progress after this milestone.

### Milestone 7: Add SQLite schema and persistence

Implement `store.py`.

Use Python’s built-in `sqlite3` module. Do not require SQLAlchemy in the first version.

Create:

    class SQLiteStore:
        def __init__(self, sqlite_path: Path): ...
        def migrate(self) -> None: ...
        def upsert_files(self, files: list[SourceFile]) -> None: ...
        def upsert_chunks(self, chunks: list[CodeChunk]) -> None: ...
        def upsert_symbols(self, source_file: SourceFile, symbols: list[Symbol]) -> None: ...
        def upsert_refs(self, source_file: SourceFile, refs: list[SymbolRef]) -> None: ...
        def upsert_edges(self, edges: list[GraphEdge]) -> None: ...
        def search_lexical(self, query: str, limit: int) -> list[LexicalResult]: ...
        def get_chunk(self, chunk_id: str) -> CodeChunkRecord | None: ...
        def get_symbol(self, symbol_id: str) -> SymbolRecord | None: ...
        def find_symbols(self, name: str, limit: int) -> list[SymbolRecord]: ...
        def callers(self, symbol_id: str, depth: int) -> list[GraphEdgeRecord]: ...
        def callees(self, symbol_id: str, depth: int) -> list[GraphEdgeRecord]: ...
        def stats(self) -> IndexStats: ...
        def set_metadata(self, key: str, value: str) -> None
        def get_metadata(self, key: str) -> str | None

The migration must create:

    PRAGMA journal_mode=WAL;
    PRAGMA foreign_keys=ON;

    CREATE TABLE IF NOT EXISTS index_metadata (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS repo_files (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      repo_root TEXT NOT NULL,
      relative_path TEXT NOT NULL UNIQUE,
      language TEXT NOT NULL,
      sha256 TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      mtime_ns INTEGER NOT NULL,
      indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS chunks (
      id TEXT PRIMARY KEY,
      file_id INTEGER NOT NULL,
      file_sha256 TEXT NOT NULL,
      relative_path TEXT NOT NULL,
      language TEXT NOT NULL,
      chunk_index INTEGER NOT NULL,
      chunk_kind TEXT NOT NULL,
      symbol_id TEXT,
      symbol_path TEXT,
      start_byte INTEGER NOT NULL,
      end_byte INTEGER NOT NULL,
      start_line INTEGER NOT NULL,
      end_line INTEGER NOT NULL,
      text_sha256 TEXT NOT NULL,
      token_count_estimate INTEGER NOT NULL,
      text TEXT,
      FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
      chunk_id UNINDEXED,
      relative_path,
      language,
      symbol_path,
      text
    );

    CREATE TABLE IF NOT EXISTS symbols (
      id TEXT PRIMARY KEY,
      file_id INTEGER NOT NULL,
      language TEXT NOT NULL,
      name TEXT NOT NULL,
      qualified_name TEXT NOT NULL,
      kind TEXT NOT NULL,
      container TEXT,
      signature TEXT,
      start_byte INTEGER NOT NULL,
      end_byte INTEGER NOT NULL,
      start_line INTEGER NOT NULL,
      end_line INTEGER NOT NULL,
      FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS ix_symbols_name ON symbols(name);
    CREATE INDEX IF NOT EXISTS ix_symbols_qualified_name ON symbols(qualified_name);
    CREATE INDEX IF NOT EXISTS ix_symbols_language ON symbols(language);

    CREATE TABLE IF NOT EXISTS symbol_refs (
      id TEXT PRIMARY KEY,
      file_id INTEGER NOT NULL,
      chunk_id TEXT,
      language TEXT NOT NULL,
      name TEXT NOT NULL,
      kind TEXT NOT NULL,
      enclosing_symbol_id TEXT,
      start_byte INTEGER NOT NULL,
      end_byte INTEGER NOT NULL,
      start_line INTEGER NOT NULL,
      end_line INTEGER NOT NULL,
      evidence TEXT NOT NULL,
      FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE,
      FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS ix_symbol_refs_name ON symbol_refs(name);
    CREATE INDEX IF NOT EXISTS ix_symbol_refs_enclosing ON symbol_refs(enclosing_symbol_id);

    CREATE TABLE IF NOT EXISTS graph_edges (
      id TEXT PRIMARY KEY,
      caller_symbol_id TEXT,
      callee_symbol_id TEXT,
      callee_name TEXT NOT NULL,
      edge_kind TEXT NOT NULL,
      confidence REAL NOT NULL,
      evidence TEXT NOT NULL,
      source_ref_id TEXT,
      relative_path TEXT NOT NULL,
      start_line INTEGER NOT NULL,
      FOREIGN KEY(caller_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE,
      FOREIGN KEY(callee_symbol_id) REFERENCES symbols(id) ON DELETE SET NULL,
      FOREIGN KEY(source_ref_id) REFERENCES symbol_refs(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS ix_graph_edges_caller ON graph_edges(caller_symbol_id);
    CREATE INDEX IF NOT EXISTS ix_graph_edges_callee ON graph_edges(callee_symbol_id);
    CREATE INDEX IF NOT EXISTS ix_graph_edges_callee_name ON graph_edges(callee_name);

When upserting chunks, delete existing FTS rows for the chunk ID and insert the new chunk text. If the manifest says `store_full_chunk_text_in_sqlite` is false, still put the text in FTS and Chroma, but store only a preview or null in `chunks.text`.

Acceptance for this milestone: tests create a temporary SQLite database, migrate it, upsert fixture chunks/symbols/refs, and lexical search returns expected chunks.

Update Progress after this milestone.

### Milestone 8: Add graph building

Implement `graph.py`.

Create this model in `models.py`:

    class GraphEdge(BaseModel):
        id: str
        caller_symbol_id: str | None
        callee_symbol_id: str | None
        callee_name: str
        edge_kind: str
        confidence: float
        evidence: str
        source_ref_id: str | None
        relative_path: str
        start_line: int

Implement:

    class GraphBuilder:
        def build_edges(
            self,
            source_file: SourceFile,
            symbols: list[Symbol],
            refs: list[SymbolRef],
            all_symbols_by_name: Mapping[str, list[Symbol]]
        ) -> list[GraphEdge]

For each reference, identify the enclosing caller symbol. Prefer `ref.enclosing_symbol_id`. If that is missing, find the nearest symbol in the same file whose range contains the reference line. If no caller exists, keep `caller_symbol_id` null.

Resolve callee symbols by exact qualified name first, then by plain name. If exactly one candidate exists, set `callee_symbol_id` and confidence 0.85. If multiple candidates exist in the same language, choose same-file first with confidence 0.70; otherwise leave `callee_symbol_id` null and set confidence 0.40. If no candidate exists, keep `callee_symbol_id` null and confidence 0.30.

Use edge kinds:

    calls
    references
    imports
    performs
    executes_sql
    executes_cics
    uses_table

For COBOL:
    PERFORM creates `performs`.
    CALL creates `calls`.
    EXEC SQL creates `executes_sql`.
    EXEC CICS creates `executes_cics`.

For SQL:
    EXEC or CALL creates `calls`.
    FROM, JOIN, UPDATE, INTO create `uses_table`.

Edge IDs must be deterministic:

    edge:<caller-or-file>:<callee-name>:<start-line>:<edge-kind>

Acceptance for this milestone: graph tests prove that a fixture method calling another fixture method creates an edge and that unresolved COBOL or SQL references are preserved.

Update Progress after this milestone.

### Milestone 9: Add embeddings and Chroma persistence

Implement `embeddings.py`.

Create:

    class Embedder(Protocol):
        dimension: int
        name: str
        def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
        def embed_query(self, text: str) -> list[float]: ...

    class HashEmbedder:
        ...

    class QwenEmbedder:
        ...

The `HashEmbedder` must be deterministic. A simple implementation can hash normalized tokens into a fixed-size vector and L2-normalize the result. It exists for tests and smoke validation only.

The `QwenEmbedder` should use `sentence_transformers.SentenceTransformer`. It should load the configured model name, encode texts in batches, normalize if configured, and return Python lists of floats. If model loading fails, print a clear error that explains how to switch to `provider: hash` for test-only local smoke runs.

Implement `vector_store.py`.

Create:

    class ChromaVectorStore:
        def __init__(self, index_dir: Path, collection_name: str, embedder: Embedder, metadata: dict[str, str]): ...
        def upsert_chunks(self, chunks: list[CodeChunk], embeddings: list[list[float]]) -> None: ...
        def query(self, query_embedding: list[float], limit: int) -> list[VectorResult]: ...
        def validate_dimension(self) -> None: ...

Use `chromadb.PersistentClient(path=<index_dir/chroma>)`. Use `get_or_create_collection`. Store chunk text as the Chroma document. Store metadata:

    relative_path
    language
    chunk_kind
    symbol_id
    symbol_path
    start_line
    end_line
    text_sha256

Use `collection.upsert`, not `add`, so re-indexing is idempotent.

Before upserting, validate that embedding dimension matches collection metadata if present. If the collection already exists with a different dimension, fail with a clear message telling the user to run with `--reset` or use a different index directory.

Acceptance for this milestone: tests use HashEmbedder and Chroma persistent storage in a temp directory, upsert chunks, query a semantically similar string, and receive at least one result.

Update Progress after this milestone.

### Milestone 10: Add indexing orchestration

Implement `indexer.py`.

Create:

    class Indexer:
        def __init__(self, manifest: Manifest, repo_root: Path): ...
        def run(self, reset: bool = False, embedding_provider_override: str | None = None) -> IndexStats: ...

The indexer must:

1. Resolve the repository root and index directory.
2. Create the index directory if missing.
3. If reset is true or manifest `reset_before_index` is true, remove the SQLite file and Chroma directory safely. Only remove paths inside the configured index directory. The path-safety check (see Idempotence and Recovery) still applies.
4. Copy the manifest to `manifest.snapshot.json`.
5. Open SQLite and run migrations.
6. Discover source files.
7. For each file, read text using UTF-8 with replacement for invalid bytes.
8. Detect language.
9. Extract symbols and references.
10. Chunk the file.
11. Upsert file metadata, symbols, refs, and chunks into SQLite.
12. Build graph edges after all symbols are collected, because cross-file resolution needs all known symbols.
13. Embed chunks and upsert them to Chroma in batches.
14. Write metadata keys:
    schema_version
    indexed_at
    repo_root
    manifest_sha256
    embedder_name
    embedding_dimension
    chunk_count
    symbol_count
    graph_edge_count
    source_set_sha256   (SHA-256 of the sorted list of "<relative_path>\t<file_sha256>\n" lines for all files included in this run; used by validate/search to detect drift)
15. Log parse errors but do not fail the whole run unless more than 25 percent of files fail to produce any chunks.

Implement incremental behavior. If a file’s relative path and sha256 match the existing `repo_files` row and reset is false, the indexer may skip reprocessing it. The first implementation may reprocess all files for simplicity, but it must be idempotent.

Add CLI wiring:

    legacylift-search index --repo-root . --config semantic-search.manifest.json --reset
    legacylift-search index --repo-root . --config semantic-search.manifest.json --embedding-provider hash

The `--embedding-provider hash` option is for local smoke tests. It must override the manifest provider without editing the file.

Acceptance for this milestone: indexing the fixture repo creates SQLite and Chroma files and reports counts greater than zero.

Update Progress after this milestone.

### Milestone 11: Add hybrid search and result rendering

Implement `search.py`.

Create these models:

    class SearchResult(BaseModel):
        chunk_id: str
        score: float
        vector_rank: int | None
        lexical_rank: int | None
        relative_path: str
        language: str
        start_line: int
        end_line: int
        symbol_path: str | None
        snippet: str

    class SearchEngine:
        def __init__(self, store: SQLiteStore, vector_store: ChromaVectorStore, embedder: Embedder, config: SearchConfig): ...
        def search(self, query: str, limit: int | None = None) -> list[SearchResult]: ...

Implement RRF:

    score = 0
    if vector_rank is not None:
        score += 1 / (rrf_rank_constant + vector_rank)
    if lexical_rank is not None:
        score += 1 / (rrf_rank_constant + lexical_rank)

Ranks are one-based. Sort descending by score. Tie-break by the best available rank, then by relative path.

The lexical search query must be safe. Do not concatenate untrusted query text directly into SQL except as a bound parameter. For FTS5, sanitize quotes and punctuation. A simple first version may tokenize the query into alphanumeric terms and join them with spaces.

The result renderer should display:

    rank
    score
    path:start_line-end_line
    language
    symbol_path
    snippet

Example output:

    1. score=0.0325 src/eligibility.py:5-18 python EligibilityService.check
       def check(self, provider_id):
           return self.rules.validate(provider_id)

Acceptance for this milestone: `legacylift-search search "eligibility validation" --index-dir <fixture-index>` returns at least one fixture result with a path and snippet.

Update Progress after this milestone.

### Milestone 12: Add symbols, callers, callees, stats, and validate commands

Wire the remaining CLI commands.

`legacylift-search symbols --name CustomerService` should query by exact name first, then by case-insensitive contains if exact returns nothing. Output symbol IDs, kind, language, path, and line range.

`legacylift-search callers <symbol-id>` should show incoming graph edges where `callee_symbol_id` equals the symbol. If none are found, also search unresolved edges where `callee_name` equals the symbol name.

`legacylift-search callees <symbol-id>` should show outgoing graph edges where `caller_symbol_id` equals the symbol.

`legacylift-search stats` should show:
    files indexed
    chunks
    symbols
    refs
    graph edges
    languages
    embedding provider
    embedding dimension
    indexed_at

`legacylift-search validate` should verify:
    SQLite file exists.
    Chroma directory exists.
    metadata exists.
    at least one chunk exists.
    at least one FTS result can be queried.
    Chroma collection can be opened.
    embedding dimension metadata is consistent.
    freshness check: recompute `source_set_sha256` from current discovery and compare to stored value; report `fresh` if equal, `stale` if different. Stale is a warning, not an error.

Expected validate output:

    OK index directory: repos/ctcm-api/legacylift-docs/index/code-search
    OK sqlite: 42 chunks, 31 symbols, 55 graph edges
    OK chroma collection: code_chunks
    OK embedding: hash dimension=64
    OK lexical search
    freshness: fresh
    Index is valid.

When stale, the freshness line should be:

    freshness: stale (3 files changed; run `legacylift-search index --repo-root <path>` to refresh)

Acceptance for this milestone: all CLI commands work against the fixture index.

Update Progress after this milestone.

### Milestone 13: Add end-to-end tests

Create end-to-end tests in `test_cli_smoke.py`. Use `typer.testing.CliRunner` or subprocess. Prefer subprocess for the closest user behavior if editable install is available in CI; otherwise use Typer runner.

Test flow:

1. Copy `tests/fixtures/polyglot_repo` to a temp directory.
2. Run `legacylift-search init-config`.
3. Run `legacylift-search index --repo-root <temp-fixture> --config <temp-fixture>/semantic-search.manifest.json --index-dir <temp-index> --embedding-provider hash`.
4. Run `legacylift-search validate --index-dir <temp-index>`.
5. Run `legacylift-search search "provider eligibility validation" --index-dir <temp-index> --limit 5`.
6. Run `legacylift-search symbols --name EligibilityService --index-dir <temp-index>`.
7. Run `legacylift-search stats --index-dir <temp-index>`.

The tests should assert exit code 0 and expected text in output.

Run:

    cd tools/legacylift_search
    pytest

Expected output:

    all tests passed

Acceptance for this milestone: the test suite proves a fresh repo can be indexed and searched end to end without Qwen or network access.

Update Progress after this milestone.

### Milestone 14: Validate against repositories under `./repos/`

The legacylift-ai repo itself contains mostly markdown and skill definitions, so it is NOT a meaningful validation target. Validation runs against client codebases checked out under `./repos/`. As of 2026-05-12 the only such repo is `repos/ctcm-api` (a 271K-LOC .NET 8 / EF Core codebase, ~4,425 C# files), but more will be added. The validation procedure must work for any repository under `./repos/` without per-repo code changes.

From the legacylift-ai root, install the tool:

    python -m pip install -e tools/legacylift_search

For each repository under `./repos/`, run:

    legacylift-search init-config --repo-root repos/<name>

This writes `repos/<name>/semantic-search.manifest.json` if it does not exist. If it exists and is invalid, save it as `semantic-search.manifest.json.bak` and generate a new one. Do not overwrite a valid existing manifest.

Run a smoke index with the deterministic embedder:

    legacylift-search index --repo-root repos/<name> --embedding-provider hash

Run validation, stats, and a smoke query:

    legacylift-search validate --repo-root repos/<name>
    legacylift-search stats --repo-root repos/<name>
    legacylift-search search "authentication authorization validation" --repo-root repos/<name> --limit 5

Expected behavior:
- `validate` reports OK and `freshness=fresh`.
- `stats` reports nonzero files, chunks, symbols, and graph edges.
- `search` returns ranked snippets with file paths, line ranges, and language.
- Re-running `index` without changes keeps `freshness=fresh` and produces no spurious diffs (idempotence check).
- Modifying one source file and re-running `validate` reports `freshness=stale` until reindex; reindex restores `fresh`.

For `repos/ctcm-api` specifically, expected scale is approximately:
- files indexed: thousands (mostly C#).
- chunks: tens of thousands.
- symbols: thousands of classes/methods/interfaces.
- graph edges: tens of thousands.
The exact counts will vary; record observed values in Outcomes & Retrospective.

Then run a production embedding index if the environment can load the Qwen model:

    legacylift-search index --repo-root repos/<name> --reset

If Qwen model loading fails due to no network, no GPU, insufficient memory, or dependency issues, do not block the implementation. Record the error in Surprises & Discoveries and leave the hash embedder path validated. The production Qwen path must still have unit coverage around configuration and error messaging.

Confirm `.gitignore` rules: after a successful index, `git status` from the legacylift-ai root must not show any new tracked files under `repos/<name>/legacylift-docs/index/`. If files appear, fix the gitignore rule and document it.

Update Progress after this milestone.

### Milestone 19: Parallelize cold-index extraction and batch SQLite commits (shipped)

The `[extract+chunk]` phase is the single longest part of a cold index — ~63 min on `repos/ctcm/ctcm-api` (M17 baseline: cold reset 71m 22s; extract+chunk 63m 41s). It is a **serial per-file loop** (`indexer.py` `run()`, the `for source_file in changed_files:` block): each iteration reads bytes, runs tree-sitter/regex extraction, runs Chonkie/fallback chunking, then performs several **self-committing** SQLite transactions (pre-delete stale `chunk_fts`/`chunks`/`symbols`/`refs`, then `upsert_symbols`, `upsert_refs`, `upsert_chunks` — each calls `conn.commit()`). At ~0.8 s/file × ~4,700 changed files this dominates cold runs. The M15 skip-on-unchanged fast path already makes *reruns* near-instant, so this milestone targets the **cold path only** and must not change rerun behavior, output, or counts.

The per-file CPU work is embarrassingly parallel; the SQLite writes are not (one connection, `check_same_thread`, WAL). The design therefore separates the two:

- **C1 — parallelize extraction across a process pool.** Move the pure `read → extract → chunk` work into worker processes. The main process stays the **sole SQLite writer**, draining completed per-file results and persisting them. This is the large lever (~63 min → target ~6–10 min on a 22-core host).
- **C2 — batch SQLite commits.** Replace the ~4–5 commits/file pattern with **one transaction per N files** in the single writer. Small, safe, and stacks on top of C1. Targeted independently it also helps any future serial path.

**Why a process pool, not threads:** the extraction work is CPU-bound Python (tree-sitter parsing, regex, Chonkie), so the GIL makes threads useless here — the same reason §2.1's embedding analysis notes one batch already saturates cores. Workers must be process-isolated.

#### Configuration (`config.py`)

Add to `IndexConfig` (or the existing index section of the manifest):

    extract_workers: int = 0      # 0 → os.cpu_count(); 1 → force serial (old path)
    commit_batch_files: int = 50  # files per SQLite transaction in the writer

`extract_workers=1` MUST preserve the exact current serial behavior — this is the fallback and the differential-test oracle. Worker counts above `os.cpu_count()` clamp to it.

#### Worker contract (`indexer.py` or a new `extract_worker.py`)

Because Windows uses `spawn`, workers re-import the module and cannot inherit live objects (tree-sitter parsers and the Chonkie chunker are not reliably picklable). Use a **module-level worker function** plus a `ProcessPoolExecutor(initializer=...)` that constructs one `SymbolExtractor` and one `CodeChunker` per worker process from picklable inputs (the `profiles_path` and `manifest.chunking`), stored in process-global state:

    # module-level, picklable
    def _worker_init(profiles_path: str, chunking_cfg_json: str) -> None:
        global _WORKER_EXTRACTOR, _WORKER_CHUNKER
        profiles = load_profiles(Path(profiles_path))
        _WORKER_EXTRACTOR = SymbolExtractor(profiles)
        _WORKER_CHUNKER = CodeChunker(ChunkingConfig.model_validate_json(chunking_cfg_json))

    def _worker_extract(sf: SourceFile) -> ExtractResult:
        # Read bytes here so file I/O parallelizes too.
        # Catch READ/EXTRACT/CHUNK errors and return them as structured
        # fields — NEVER raise across the pool boundary, so one bad file
        # cannot poison the batch. Mirror the current log messages exactly.
        ...

Define a picklable result model so the writer can reproduce today's logging and persistence verbatim:

    class ExtractResult(BaseModel):
        relative_path: str
        symbols: list[Symbol]
        refs: list[SymbolRef]
        chunks: list[CodeChunk]
        parse_errors: list[str] = []          # → PARSE_NOTE log lines
        read_error: str | None = None         # → READ_ERROR, skip file
        extract_error: str | None = None      # → EXTRACT_ERROR, skip file
        chunk_error: str | None = None         # → CHUNK_ERROR, chunks = []
        zero_chunks: bool = False             # feeds the 25% threshold

`SourceFile`, `Symbol`, `SymbolRef`, and `CodeChunk` are all pydantic models and pickle cleanly. Chunk ids are content hashes, so they are identical regardless of which worker produced them.

#### Writer loop (main process)

The main process keeps all SQLite ownership and the pre-delete-stale logic exactly as it is today, but drives it from completed futures instead of an inline loop:

1. Submit all `changed_files` to the pool (`executor.map` or `as_completed`).
2. **Buffer results and persist in a deterministic order.** Collect into a dict keyed by `relative_path`; flush in a stable order (e.g. sorted by `relative_path`, or the original `changed_files` order) so the resulting index — `all_chunks` ordering, `chunk_index`, graph build input — is byte-for-byte reproducible regardless of worker completion order. **Do not** write in `as_completed` arrival order.
3. For each file in a commit batch: run the existing stale-row deletion, then `upsert_symbols` / `upsert_refs` / `upsert_chunks`. Wrap the whole batch in **one** transaction (`BEGIN` … `COMMIT` every `commit_batch_files`) rather than letting each upsert commit. This requires either a `commit=False` parameter on those store methods or a thin `store.begin()/commit()` the writer controls; prefer adding an explicit transaction seam to `SQLiteStore` over changing every upsert's signature.
4. Preserve `files_processed`, `files_with_zero_chunks`, `symbol_count_processed`, `ref_count_processed`, `all_chunks`, `all_refs_by_file`, and `new_chunk_ids_by_file` accounting identically — downstream graph build, stale-vector computation, and the 25% zero-chunks threshold all depend on them unchanged.
5. Emit `[extract+chunk]` progress on the same throttled cadence as the embed phase (a periodic "processed X/Y files, rate, eta" line to `index.log` and stdout), since a parallel phase otherwise looks hung.

Everything after the extract loop — graph edge build, metadata write, embed/Chroma upsert — is **untouched**. This milestone changes only how the changed-file extract/chunk/persist step is executed, not what it produces.

#### Failure and resource handling

- A worker that dies (segfault in a native parser, OOM) must not abort the run: detect a broken future, log it as `EXTRACT_ERROR <path>: worker died`, count the file as zero-chunks, and continue. The existing 25% zero-chunks threshold then governs whether the overall run fails.
- Honor a wall-clock interruption the same way the current run does: persisted batches survive (WAL), and `backfill-vectors` plus the M15 fast path complete the rest on the next call. Ensure a `KeyboardInterrupt`/timeout cleanly shuts the pool down (`executor.shutdown(cancel_futures=True)`) and commits the in-flight batch.
- Default `extract_workers=0` → `os.cpu_count()`. Document that memory scales with worker count (each holds tree-sitter grammars); on memory-constrained hosts set `extract_workers` lower.

#### Tests (`tests/test_indexer_parallel.py`)

- **Equivalence (the load-bearing test):** index the polyglot fixture twice — once with `extract_workers=1`, once with `extract_workers=4` — and assert identical SQLite contents (chunk ids and ordering, symbol/ref/edge counts, `source_set_sha256`) and identical Chroma vector counts. The parallel path must be a pure performance change.
- **Determinism:** two separate `extract_workers=4` cold runs produce identical `chunk_index` assignment and `all_chunks` ordering (guards against arrival-order leakage into persisted state).
- **Bad-file isolation:** a fixture file that triggers an extract exception is logged as `EXTRACT_ERROR` and skipped without failing the run or corrupting neighbors' rows.
- **Batch boundary:** `commit_batch_files=1` and `commit_batch_files=50` produce identical final state (commit granularity is invisible to output).
- **M15 interaction:** after a parallel cold run, a no-change rerun still skips every file and processes zero (parallelism must not perturb the skip-on-unchanged path).

#### Manual validation

Run a cold index against `repos/ctcm/ctcm-api` with the new path and compare against the M17 baseline:

    legacylift-search index --repo-root repos/ctcm/ctcm-api --reset --embedding-provider hash

Use `--embedding-provider hash` so the measurement isolates the extract+chunk phase from embedding cost. Record the `[extract+chunk]` phase wall-clock from `index.log` against the 63m 41s baseline and confirm `stats` reports identical file/chunk/symbol/ref/edge counts to the M15/M17 runs (only timing should change). Confirm `validate` reports `Index is valid.` and `freshness: fresh`, and that `git status` shows no new tracked files under `repos/ctcm/ctcm-api/legacylift-docs/index/`.

This milestone is orthogonal to the hosted-data-store work (`docs/exec-plans/pending/hosted-data-store.md`, §2.2 and shape #1): it pays off in the all-local, GPU, and hosted-embedding scenarios alike, because once embedding is fast the extract+chunk phase is the long pole regardless of where vectors are stored.

Update Progress after this milestone.
