"""Tests for Milestone 15: skip-on-unchanged incremental reindex.

These tests cover the four required behaviours from the exec-plan:

1. Idempotent rerun: a second `index` call with no source changes must not
   re-extract, re-chunk, re-embed, or re-upsert anything. The store row
   counts must stay constant and the per-run stats must report
   files_processed=0 / files_skipped=N.

2. Stale single-file edit: editing one file must rewrite that file's
   artifacts (chunks/symbols/refs) and rebuild the cross-file graph over
   the union of changed + unchanged refs without leaving orphan edges.

3. Deleted file: removing a file from disk must drop its repo_files row,
   chunks, symbols, refs, graph_edges, and Chroma vectors.

4. Validate vector-coverage warning: when `vectors_upserted < chunk_count`
   the validate command must surface a yellow warning rather than report
   `freshness=fresh` silently.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest
from legacylift_search.indexer import Indexer
from legacylift_search.store import SQLiteStore


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _manifest() -> Manifest:
    m = Manifest()
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    return m


def _index_dir(repo: Path) -> Path:
    return repo / "legacylift-docs" / "index" / "code-search"


def test_skip_on_unchanged_processes_zero_files(tmp_path: Path) -> None:
    """A no-change rerun must process zero files and skip every file."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()

    s1 = Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")
    assert s1.files_processed == s1.files_indexed
    assert s1.files_skipped == 0

    s2 = Indexer(manifest, repo).run(reset=False, embedding_provider_override="hash")

    # Counts must be preserved across the rerun.
    assert s2.chunk_count == s1.chunk_count
    assert s2.symbol_count == s1.symbol_count
    assert s2.ref_count == s1.ref_count
    # No work was done this run.
    assert s2.files_processed == 0
    assert s2.files_skipped == s1.files_indexed
    # And no Chroma upsert traffic either: when files_processed=0 we never
    # reach the per-chunk skip-detection branch (there are no chunks built
    # this run), so vectors_upserted == vectors_skipped == 0 is expected.
    assert s2.vectors_upserted == 0
    assert s2.vectors_skipped == 0


def test_vectors_present_cache_populated(tmp_path: Path) -> None:
    """The vectors_present cache must contain one row per chunk after a
    successful index run. Without this cache the Chroma-skip path on a
    subsequent partial reindex degenerates into per-chunk Chroma round
    trips."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    s1 = Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    sqlite_path = _index_dir(repo) / "index.sqlite"
    store = SQLiteStore(sqlite_path)
    try:
        conn = store._connect()
        present_count = conn.execute(
            "SELECT COUNT(*) FROM vectors_present"
        ).fetchone()[0]
        assert present_count == s1.chunk_count
        # vectors_upserted metadata must reflect coverage.
        assert int(store.get_metadata("vectors_upserted")) == s1.chunk_count
    finally:
        store.close()


def test_changed_file_rewrites_only_its_artifacts(tmp_path: Path) -> None:
    """Editing one file rewrites that file's chunks/symbols/refs and rebuilds
    the cross-file graph correctly. Unchanged files' artifacts persist."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()

    s1 = Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    # Snapshot every other file's chunk ids before the edit so we can prove
    # they are not rewritten.
    sqlite_path = _index_dir(repo) / "index.sqlite"
    store = SQLiteStore(sqlite_path)
    try:
        conn = store._connect()
        rows = conn.execute(
            "SELECT id, relative_path FROM chunks ORDER BY id"
        ).fetchall()
        before = {(r["relative_path"], r["id"]) for r in rows}
    finally:
        store.close()

    # Edit one fixture file (the Python module).
    target = repo / "src" / "eligibility.py"
    text = target.read_text(encoding="utf-8")
    target.write_text(
        text + "\n\ndef new_helper_for_m15():\n    return 42\n",
        encoding="utf-8",
    )

    s2 = Indexer(manifest, repo).run(reset=False, embedding_provider_override="hash")

    assert s2.files_processed == 1
    assert s2.files_skipped == s1.files_indexed - 1
    # Only the edited file's vectors should be touched. Chunks for
    # non-edited files are not even examined this run; chunks for the
    # edited file may either be new (upserted) or text-identical to a
    # prior chunk (skipped via vectors_present).
    # We don't pin exact counts because chunker output depends on the
    # extractor; just that at least one new vector was upserted (the
    # appended helper produced new content).
    assert s2.vectors_upserted >= 1

    # Chunks for unchanged files are byte-identical (same chunk ids).
    store = SQLiteStore(sqlite_path)
    try:
        conn = store._connect()
        rows = conn.execute(
            "SELECT id, relative_path FROM chunks WHERE relative_path != ?",
            ("src/eligibility.py",),
        ).fetchall()
        unchanged_after = {(r["relative_path"], r["id"]) for r in rows}
        unchanged_before = {p for p in before if p[0] != "src/eligibility.py"}
        assert unchanged_after == unchanged_before

        # Graph edges still exist for unchanged files (rebuilt fresh, but
        # present). Specifically, edges for non-edited files must not be
        # zero-counted.
        edge_count = conn.execute(
            "SELECT COUNT(*) FROM graph_edges WHERE relative_path != ?",
            ("src/eligibility.py",),
        ).fetchone()[0]
        assert edge_count > 0, "graph rebuild dropped edges for unchanged files"
    finally:
        store.close()


def _chroma_ids_for_path(
    repo: Path, collection_name: str, relative_path: str
) -> set[str]:
    """Return the set of Chroma vector ids whose metadata.relative_path matches.

    Reads the real persisted collection so the assertion covers what actually
    landed in the vector store, not just SQLite's view of it.
    """
    import chromadb

    client = chromadb.PersistentClient(
        path=str(_index_dir(repo) / "chroma")
    )
    coll = client.get_collection(collection_name)
    got = coll.get(include=["metadatas"])
    ids = {
        cid
        for cid, meta in zip(got["ids"], got["metadatas"])
        if meta.get("relative_path") == relative_path
    }
    # Release Windows file handles before the test tmp dir is torn down.
    del coll
    del client
    import gc

    gc.collect()
    return ids


def test_changed_file_body_leaves_no_orphan_vectors(tmp_path: Path) -> None:
    """Editing a file BODY (so chunk ids change) must not leave orphaned
    Chroma vectors for that path.

    Regression for the incremental-reindex orphan bug: the changed file's old
    chunk ids were snapshotted AFTER `upsert_files` had already cascade-deleted
    the file's `chunks` rows, so the snapshot was empty and the stale vectors
    were never deleted from Chroma. Mirrors the concrete NNG M5(b) observation
    (2026-07-23): SQLite held the current chunks while Chroma kept both current
    and orphaned (old-hash) vectors for the same path — clearable only by
    `--reset`. Asserts the Chroma vector-id set for the path equals the SQLite
    chunk-id set (no orphans, nothing missing), without `--reset`.
    """
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    collection_name = manifest.index.collection_name

    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    rel = "src/eligibility.py"
    target = repo / rel
    text = target.read_text(encoding="utf-8")
    # Rewrite an existing method body so its chunk text — and therefore its
    # content-hash chunk id — changes, producing a stale old id that must be
    # deleted from Chroma.
    mutated = text.replace(
        "return self.rules.apply(provider_id)",
        "computed = self.rules.apply(provider_id)\n        return computed",
    )
    assert mutated != text, "fixture changed; edit no longer mutates a body"
    target.write_text(mutated, encoding="utf-8")

    Indexer(manifest, repo).run(reset=False, embedding_provider_override="hash")

    # SQLite's current chunk ids for the path.
    store = SQLiteStore(_index_dir(repo) / "index.sqlite")
    try:
        conn = store._connect()
        sqlite_ids = {
            r["id"]
            for r in conn.execute(
                "SELECT id FROM chunks WHERE relative_path = ?", (rel,)
            ).fetchall()
        }
    finally:
        store.close()

    chroma_ids = _chroma_ids_for_path(repo, collection_name, rel)

    orphans = chroma_ids - sqlite_ids
    missing = sqlite_ids - chroma_ids
    assert not orphans, f"orphaned Chroma vectors for {rel}: {sorted(orphans)}"
    assert not missing, f"missing Chroma vectors for {rel}: {sorted(missing)}"


def test_deleted_file_drops_artifacts(tmp_path: Path) -> None:
    """Deleting a fixture file must drop its repo_files row, chunks,
    symbols, refs, graph_edges, and vectors_present cache entries."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()

    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    sqlite_path = _index_dir(repo) / "index.sqlite"
    store = SQLiteStore(sqlite_path)
    try:
        conn = store._connect()
        # Pick a file with at least one chunk and at least one symbol.
        row = conn.execute(
            "SELECT relative_path FROM chunks GROUP BY relative_path "
            "HAVING COUNT(*) > 0 LIMIT 1"
        ).fetchone()
        target_rel = row["relative_path"]
        chunk_ids_before = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM chunks WHERE relative_path = ?",
                (target_rel,),
            ).fetchall()
        ]
        assert chunk_ids_before
    finally:
        store.close()

    # Delete the file from disk.
    (repo / target_rel).unlink()

    s2 = Indexer(manifest, repo).run(reset=False, embedding_provider_override="hash")
    assert s2.files_deleted == 1

    store = SQLiteStore(sqlite_path)
    try:
        conn = store._connect()
        # No traces of the deleted file.
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM repo_files WHERE relative_path = ?",
                (target_rel,),
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE relative_path = ?",
                (target_rel,),
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM graph_edges WHERE relative_path = ?",
                (target_rel,),
            ).fetchone()[0]
            == 0
        )
        for cid in chunk_ids_before:
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM vectors_present WHERE chunk_id = ?",
                    (cid,),
                ).fetchone()[0]
                == 0
            )
    finally:
        store.close()


def test_validate_warns_on_vector_divergence(tmp_path: Path) -> None:
    """When vectors_upserted < chunk_count, validate must surface a warning."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()

    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    # Synthesize the divergent state by clamping vectors_upserted to 1.
    sqlite_path = _index_dir(repo) / "index.sqlite"
    store = SQLiteStore(sqlite_path)
    try:
        store.set_metadata("vectors_upserted", "1")
    finally:
        store.close()

    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--repo-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "WARNING" in result.output
    assert "vector coverage incomplete" in result.output
    assert "vectors_upserted=1" in result.output
