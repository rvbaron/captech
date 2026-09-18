# Fix: Incremental-Reindex Orphan Chroma Vectors (Snapshot-Ordering Fix)

> **Status: DONE — 2026-07-24.** Root cause was diagnosed by reproduction and differs
> from the original draft's premise (see Surprises & Discoveries). The fix is a
> one-block reorder in `indexer.py`, not the new `purge_paths` primitive the draft
> proposed. Carried over from the domains-enhancement work
> (`feature/domains-enhancement`, session handoff 2026-07-24).

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`,
`Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.
Maintain in accordance with `docs/legacylift/exec-plan.md`.


## Purpose / Big Picture

`legacylift-search` builds a Chroma vector collection whose chunk ids are content-hash-keyed:
`chunk:<relative_path>:<lang>:<chunk_index>:<text_sha_prefix>`. When a source file's **body
changes** and the user runs an **incremental** `index` (no `--reset`), the chunker produces new
ids (new hash prefix) and the indexer upserts them — but it never deletes the file's **prior**
vectors. The old ids linger in the collection carrying stale document text **and** stale `domain`
metadata.

**Observed concretely** (NNG domain test, M5(b), 2026-07-23): rewriting one file's body then
incrementally reindexing left `index.sqlite`'s `chunks` table with the correct current 6 chunks,
while Chroma held 6 vectors for that path — 3 current (correct new domain) + 3 orphaned (old hash
ids, stale domain). `index --reset` fully rebuilds Chroma and clears the orphans.

**Actual root cause (found by reproduction, 2026-07-24):** the indexer *already* deletes a changed
file's stale vectors from Chroma by id (`indexer.py` `delete_chunks(all_stale_chunk_ids)`), and
delete-by-id works on the pinned chromadb 1.5.9. The bug was an **ordering** mistake: the
`stale_chunk_ids` snapshot (`SELECT id FROM chunks WHERE relative_path = ?`) ran **after**
`upsert_files(changed_files)`, whose `INSERT OR REPLACE` on `repo_files` cascade-deletes the file's
`chunks` rows (FK `ON DELETE CASCADE`). So the snapshot came back empty for changed files,
`truly_stale_chunk_ids` was empty, and nothing was deleted from Chroma → orphans.

**The fix:** move the snapshot to immediately after the changed/unchanged partition, *before*
`upsert_files` can cascade the rows away. The already-present, already-working delete-by-id path
then removes exactly the stale vectors. This preserves the Milestone-15 within-file embed-skip
optimization (text-identical chunks keep their ids, their vectors are neither deleted nor
re-embedded).

**Scope decision (2026-07-24):** the draft's path-scoped `purge_paths` (delete-by-`where`) approach
was rejected in favor of the minimal ordering fix. Path-purge would self-heal orphans left in
indexes by *prior* buggy runs, but it would also delete text-identical chunks' still-valid vectors
and — because those ids remain in the `vectors_present` skip cache — fail to re-upsert them, turning
orphans into *missing* vectors unless the cache is also invalidated (which re-embeds every chunk of
every changed file, defeating the within-file skip). Existing indexes with pre-fix orphans are
cleared by one `index --reset` (the already-documented workaround).


## Progress

- [x] Milestone 1: Diagnose the true root cause by reproduction — snapshot-ordering bug, not an
      "ids-unknown" problem (2026-07-24)
- [x] Milestone 2: Move the `stale_chunk_ids` snapshot before `upsert_files(changed_files)` so it is
      taken before the FK cascade wipes the changed files' `chunks` rows (2026-07-24)
- [x] Milestone 3: Regression test — change a file body, incremental reindex, assert the Chroma
      vector-id set for the path equals the SQLite chunk-id set (no orphans, nothing missing).
      `tests/test_m15_skip_unchanged.py::test_changed_file_body_leaves_no_orphan_vectors`; verified
      it fails against the pre-fix indexer and passes after (2026-07-24)
- [x] Milestone 4: Full `legacylift_search` suite green on chromadb 1.5.9 (2026-07-24)

The draft's original milestones (add `purge_paths`, wire path-purge into the incremental path) were
superseded — the minimal ordering fix makes them unnecessary.


## Surprises & Discoveries

- The draft's premise was wrong. It assumed the indexer never deletes a changed file's prior
  vectors and that the old ids are unrecoverable. In fact the indexer already snapshots the old ids
  (`stale_chunk_ids`), diffs them to `truly_stale_chunk_ids`, and calls
  `vector_store.delete_chunks(all_stale_chunk_ids)` (`indexer.py`). delete-by-id is fully functional
  on chromadb 1.5.9 (verified with a standalone probe: delete-by-id and delete-by-`where` both work
  and both tolerate no-match without raising).
- The real defect: the snapshot ran *after* `upsert_files(changed_files)`. That `INSERT OR REPLACE`
  on the UNIQUE `relative_path` drops the old `repo_files` row and cascade-deletes its `chunks`
  (FK `ON DELETE CASCADE`), so `SELECT id FROM chunks WHERE relative_path = ?` returned nothing for
  changed files → empty `stale_chunk_ids` → empty `truly_stale_chunk_ids` → no Chroma delete →
  orphans. The in-code comment on the snapshot loop even said "before re-extraction", confirming the
  intent was an early snapshot; it was simply placed after the cascade.
- Reproduction (hash embedder, polyglot_repo fixture): edit one file's method body, incremental
  reindex → SQLite held 4 current chunks for the path while Chroma held 6 (4 current + 2 orphaned
  old-hash ids). After the fix: Chroma held exactly the 4 current ids, and the run still reported
  "Skipped 2 vectors already present / Upserted 2 new" — the within-file skip optimization is intact.


## Decision Log

- Decision (SUPERSEDED): purge by `relative_path` metadata equality (`where` filter).
  Original rationale ("chunk ids embed the content hash, so the old ids are unknown at reindex
  time") turned out to be false — the old ids are in SQLite and only need to be read before the
  cascade. Kept here for the record.
  Date/Author: 2026-07-24 / draft

- Decision (ADOPTED): fix the snapshot ordering — move the `stale_chunk_ids` capture to just after
  the changed/unchanged partition, before `upsert_files`. Reuse the existing, working delete-by-id
  path. Rejected the path-purge approach because it would delete text-identical chunks' valid
  vectors and, with those ids still in the `vectors_present` cache, leave them un-re-upserted
  (orphans → missing) unless the cache is also invalidated, which re-embeds every chunk of every
  changed file and defeats the Milestone-15 within-file skip. Pre-existing orphaned indexes are
  cleared by one `index --reset`.
  Date/Author: 2026-07-24 / adopted


## Context and Orientation

Key files (all under `tools/legacylift_search/src/legacylift_search/`):

- `indexer.py`
  - `run(...)` — the incremental pipeline. The changed/unchanged partition and the (now relocated)
    `stale_chunk_ids` snapshot sit just before `store.upsert_files(changed_files)`. `truly_stale_chunk_ids`
    is diffed post-extraction and passed to `vector_store.delete_chunks(all_stale_chunk_ids)` in the
    Chroma-upsert phase.
  - `store.upsert_files(...)` → `INSERT OR REPLACE INTO repo_files` on UNIQUE `relative_path`; the
    `chunks`/`symbols`/`symbol_refs`/facts tables FK to `repo_files` with `ON DELETE CASCADE`
    (`store.py`), which is why an early snapshot is mandatory.
- `vector_store.py`
  - `delete_chunks(ids)` — batched, best-effort `collection.delete(ids=...)`; the delete path the fix
    relies on. Confirmed working on chromadb 1.5.9.

Memory: `[[legacylift-incremental-reindex-orphan-vectors]]`. Related: `[[chromadb-version-pin]]`
(validated on the pinned 1.5.9), `[[nng-domain-test-plan-status]]`.


## Plan of Work

**Step 1 — reproduce & diagnose (done).** Standalone repro (hash embedder, polyglot_repo): edit a
method body, incremental reindex, then read the persisted Chroma collection and diff per-path ids
against SQLite. Confirmed 2 orphans and that they came from an empty `stale_chunk_ids` snapshot
(the `upsert_files` cascade had already deleted the rows). Confirmed delete-by-id works on 1.5.9.

**Step 2 — fix the ordering (done).** In `indexer.py`, move the `stale_chunk_ids` snapshot to
immediately after the changed/unchanged partition, before `upsert_files(changed_files)`. Leave the
`truly_stale_chunk_ids` diff and the `delete_chunks(all_stale_chunk_ids)` call untouched. No change
to `vector_store.py`.

**Step 3 — regression test (done).** `test_changed_file_body_leaves_no_orphan_vectors` in
`tests/test_m15_skip_unchanged.py`: index the fixture, rewrite a method body, incremental reindex,
then read the real Chroma collection and assert its per-path id set equals SQLite's per-path chunk
id set (no orphans, nothing missing). Verified red against the pre-fix indexer, green after.


## Validation and Acceptance

1. After incrementally reindexing a changed file, Chroma holds exactly the current chunks for that
   path (id set matches `index.sqlite` `chunks`) — no old-hash orphans, no missing vectors. ✅
2. The within-file embed-skip is preserved: text-identical chunks are neither deleted nor re-embedded
   (run reports "Skipped N vectors already present"). ✅
3. Deleting a source file and reindexing removes its vectors without `--reset` (unchanged;
   `test_deleted_file_drops_artifacts` still green). ✅
4. `--reset` behavior unchanged. ✅
5. Full `legacylift_search` suite passes on chromadb **1.5.9**. ✅


## Idempotence and Recovery

The fix changes only *when* the stale-id snapshot is taken; the delete path is already idempotent
(Chroma delete-by-id tolerates absent ids). Re-running an incremental `index` on unchanged files is
a no-op. `--reset` remains the full-rebuild escape hatch and the one-time cleanup for any index that
still carries pre-fix orphans. No schema migration.


## Outcomes & Retrospective

- **Delivered:** a two-block reorder in `indexer.py` (snapshot moved ahead of the FK cascade) plus a
  regression test. No new API, no `vector_store.py` change, no schema change.
- **Lesson:** the original draft encoded a plausible-but-unverified diagnosis ("ids are unknown at
  reindex time") and prescribed a heavier fix around it. A 60-line reproduction that read the actual
  Chroma collection overturned the premise in minutes and pointed at a one-block ordering bug — cheaper
  to build, cheaper to review, and it keeps the Milestone-15 skip optimization. Reproduce before
  designing the fix.
- **Known residual:** indexes built before this fix may still contain orphaned vectors; they are not
  self-healed by an incremental run and require one `index --reset`. Accepted (see Decision Log).
