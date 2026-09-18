"""Tests for the resumable `backfill-vectors` subcommand.

The backfill path drives the embed/upsert phase off the SQLite `chunks`
table filtered against the `vectors_present` cache, so it can complete an
interrupted `--reset` run that the M15 skip-on-unchanged fast path would
otherwise leave empty (a plain rerun sees all files unchanged and feeds
nothing to the embedder).

Required behaviours:

1. After a cold index with `vectors_present` artificially cleared (and the
   Chroma collection emptied), `backfill-vectors` restores full coverage.
2. A second `backfill-vectors` is a no-op (0 backfilled).
3. The CLI command works end-to-end on the polyglot fixture.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest
from legacylift_search.indexer import Indexer
from legacylift_search.store import SQLiteStore
from legacylift_search.vector_store import ChromaVectorStore
from legacylift_search.embeddings import HashEmbedder


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


def _clear_vectors(repo: Path, manifest: Manifest) -> None:
    """Simulate an interrupted upsert: empty the Chroma collection, clear the
    vectors_present cache, and zero the vectors_upserted high-water mark."""
    index_dir = _index_dir(repo)
    sqlite_path = index_dir / "index.sqlite"

    store = SQLiteStore(sqlite_path)
    try:
        conn = store._connect()
        chunk_ids = [
            r["id"] for r in conn.execute("SELECT id FROM chunks").fetchall()
        ]
        conn.execute("DELETE FROM vectors_present")
        conn.commit()
        store.set_metadata("vectors_upserted", "0")
    finally:
        store.close()

    # Empty the Chroma collection too so the backfill genuinely re-embeds.
    vs = ChromaVectorStore(
        base_dir=index_dir,
        collection_name=manifest.index.collection_name,
        embedder=HashEmbedder(dimension=manifest.embedding.dimension),
        metadata={},
    )
    try:
        vs.delete_chunks(chunk_ids)
    finally:
        vs.close()


def test_backfill_restores_coverage_after_cleared_cache(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()

    s1 = Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )
    assert s1.vectors_upserted == s1.chunk_count

    _clear_vectors(repo, manifest)

    # Sanity: coverage is now zero.
    sqlite_path = _index_dir(repo) / "index.sqlite"
    store = SQLiteStore(sqlite_path)
    try:
        assert store.get_present_vector_count() == 0
        assert int(store.get_metadata("vectors_upserted")) == 0
    finally:
        store.close()

    b = Indexer(manifest, repo).backfill_vectors(
        embedding_provider_override="hash"
    )

    assert b.chunks_missing == s1.chunk_count
    assert b.vectors_backfilled == s1.chunk_count
    assert b.vectors_upserted_total == s1.chunk_count
    assert b.chunk_count == s1.chunk_count

    # The vectors_present cache and metadata now reflect full coverage.
    store = SQLiteStore(sqlite_path)
    try:
        assert store.get_present_vector_count() == s1.chunk_count
        assert int(store.get_metadata("vectors_upserted")) == s1.chunk_count
    finally:
        store.close()


def test_second_backfill_is_noop(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()

    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    # A fresh index already has full coverage, so the first backfill is a
    # no-op too. Clear once, backfill once to full, then confirm the next
    # backfill does nothing.
    _clear_vectors(repo, manifest)
    Indexer(manifest, repo).backfill_vectors(
        embedding_provider_override="hash"
    )

    b2 = Indexer(manifest, repo).backfill_vectors(
        embedding_provider_override="hash"
    )
    assert b2.chunks_missing == 0
    assert b2.vectors_backfilled == 0
    assert b2.vectors_upserted_total == b2.chunk_count


def test_backfill_on_fresh_index_is_noop(tmp_path: Path) -> None:
    """A backfill immediately after a successful index finds nothing to do."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()

    s1 = Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )
    b = Indexer(manifest, repo).backfill_vectors(
        embedding_provider_override="hash"
    )
    assert b.chunks_missing == 0
    assert b.vectors_backfilled == 0
    assert b.vectors_upserted_total == s1.chunk_count


def test_backfill_missing_index_errors(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["backfill-vectors", "--repo-root", str(repo), "--embedding-provider", "hash"],
    )
    assert result.exit_code == 1, result.output
    assert "No index found" in result.output


def test_backfill_cli_smoke(tmp_path: Path) -> None:
    import json

    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    # Persist the manifest so the CLI resolves hash/dim=64 and the backfill
    # embedder matches the dim=64 Chroma collection built below.
    manifest_path = repo / "semantic-search.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")
    _clear_vectors(repo, manifest)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "backfill-vectors",
            "--repo-root",
            str(repo),
            "--embedding-provider",
            "hash",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "vectors_backfilled" in result.output
    assert "Vector coverage complete." in result.output

    # A second CLI invocation reports nothing to do.
    result2 = runner.invoke(
        app,
        [
            "backfill-vectors",
            "--repo-root",
            str(repo),
            "--embedding-provider",
            "hash",
        ],
    )
    assert result2.exit_code == 0, result2.output
    assert "Vector coverage complete." in result2.output
