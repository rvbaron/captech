"""Tests for the Indexer end-to-end pipeline (Milestone 10)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from legacylift_search.cli import app
from legacylift_search.config import Manifest
from legacylift_search.embeddings import HashEmbedder
from legacylift_search.indexer import Indexer, IndexStats
from legacylift_search.store import SQLiteStore


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


def _copy_fixture(tmp_path: Path) -> Path:
    """Copy the polyglot fixture into tmp_path/repo and return the path."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _default_manifest_for(repo_root: Path) -> Manifest:
    m = Manifest()
    # Force hash provider so tests don't need network/Qwen.
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    return m


def test_index_run_creates_artifacts(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)
    indexer = Indexer(manifest, repo)

    stats = indexer.run(reset=True, embedding_provider_override="hash")

    assert isinstance(stats, IndexStats)
    index_dir = repo / "legacylift-docs" / "index" / "code-search"
    assert (index_dir / "index.sqlite").exists()
    assert (index_dir / "chroma").exists()
    assert (index_dir / "manifest.snapshot.json").exists()

    assert stats.files_indexed > 0
    assert stats.chunk_count > 0
    assert stats.symbol_count > 0
    assert stats.graph_edge_count >= 0
    assert stats.embedder_name == "hash"
    assert stats.embedding_dimension == 64


def test_index_idempotent_rerun(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)

    s1 = Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )
    s2 = Indexer(manifest, repo).run(
        reset=False, embedding_provider_override="hash"
    )

    assert s1.chunk_count == s2.chunk_count
    assert s1.symbol_count == s2.symbol_count


def test_index_reset_path_safety(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)
    # Point index_dir at the repo root itself — must refuse on reset.
    manifest.index.index_dir = str(repo)

    indexer = Indexer(manifest, repo)
    with pytest.raises(ValueError):
        indexer.run(reset=True, embedding_provider_override="hash")

    # Sanity: repo root contents unchanged (fixture file still present).
    assert (repo / "src" / "eligibility.py").exists()


def test_index_dimension_mismatch(tmp_path: Path, monkeypatch) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)

    # First run with hash dimension=64 (default).
    Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )

    # Now monkey-patch HashEmbedder so a fresh hash embedder reports dim=128.
    original_init = HashEmbedder.__init__

    def _patched_init(self, dimension: int = 128) -> None:
        original_init(self, dimension=128)

    monkeypatch.setattr(HashEmbedder, "__init__", _patched_init)

    with pytest.raises(ValueError) as excinfo:
        Indexer(manifest, repo).run(
            reset=False, embedding_provider_override="hash"
        )
    msg = str(excinfo.value)
    assert "Existing Chroma collection uses dimension" in msg
    assert "Re-run with --reset" in msg


def test_index_metadata_set(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)
    Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )

    index_dir = repo / "legacylift-docs" / "index" / "code-search"
    store = SQLiteStore(index_dir / "index.sqlite")
    try:
        for key in [
            "schema_version",
            "indexed_at",
            "repo_root",
            "manifest_sha256",
            "embedder_name",
            "embedding_dimension",
            "chunk_count",
            "symbol_count",
            "graph_edge_count",
            "source_set_sha256",
        ]:
            assert store.get_metadata(key) is not None, f"missing metadata: {key}"
        assert store.get_metadata("embedder_name") == "hash"
        assert store.get_metadata("embedding_dimension") == "64"
    finally:
        store.close()

    # Snapshot is valid JSON
    snap = (index_dir / "manifest.snapshot.json").read_text(encoding="utf-8")
    json.loads(snap)


def test_index_log_records_upsert_progress(tmp_path: Path) -> None:
    """The chroma-upsert phase must emit per-batch progress lines (with
    percent, rate, and ETA) so a long embedding pass is observable, and the
    log must be written through to disk so a killed run still leaves a trail.
    """
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)
    # batch_size=1 guarantees multiple batches over the fixture chunks; the
    # last batch always emits regardless of the time-based throttle.
    manifest.embedding.batch_size = 1

    stats = Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )
    assert stats.vectors_upserted > 0

    index_dir = repo / "legacylift-docs" / "index" / "code-search"
    log_text = (index_dir / "index.log").read_text(encoding="utf-8")

    assert "[chroma-upsert] progress" in log_text
    # Progress line carries the assessable metrics.
    assert "embedded" in log_text
    assert "rate=" in log_text
    assert "eta=" in log_text
    # Final batch reports 100% coverage.
    assert "(100.0%)" in log_text


def test_embed_min_tokens_keeps_full_vector_coverage(tmp_path: Path) -> None:
    """With embed_min_tokens set, low-value chunks are skipped at embed time
    but marked present, so coverage stays exact (vectors_upserted ==
    chunk_count) and validate reports no divergence warning. All chunks remain
    in SQLite/FTS5 for lexical recall."""
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)
    manifest.chunking.embed_min_tokens = 80  # aggressive filter on a tiny repo

    stats = Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )

    index_dir = repo / "legacylift-docs" / "index" / "code-search"
    store = SQLiteStore(index_dir / "index.sqlite")
    try:
        # Every chunk is resolved w.r.t. the vector store (embedded or
        # deliberately skipped) so coverage is exact and backfill terminates.
        present = store.get_present_vector_count()
        assert present == stats.chunk_count
        assert int(store.get_metadata("vectors_upserted")) == stats.chunk_count
        # Chunks still all present in SQLite (nothing was dropped).
        conn = store._connect()
        chunk_rows = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        assert chunk_rows == stats.chunk_count
        # FTS index still covers every chunk for lexical recall.
        fts_rows = conn.execute("SELECT COUNT(*) FROM chunk_fts").fetchone()[0]
        assert fts_rows == stats.chunk_count
    finally:
        store.close()


def test_index_log_records_dedup_and_filter(tmp_path: Path) -> None:
    """When the filter and dedup engage, the log records them so the operator
    can see why the embed count is below chunk_count."""
    repo = _copy_fixture(tmp_path)
    manifest = _default_manifest_for(repo)
    manifest.chunking.embed_min_tokens = 80
    manifest.embedding.batch_size = 4

    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")
    index_dir = repo / "legacylift-docs" / "index" / "code-search"
    log_text = (index_dir / "index.log").read_text(encoding="utf-8")
    # At least the embed-phase line is present; filter line appears when any
    # low-value chunk is found (the polyglot fixture has small symbols).
    assert "distinct chunks in" in log_text


def test_index_cli_smoke(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    repo = _copy_fixture(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "index",
            "--repo-root",
            str(repo),
            "--embedding-provider",
            "hash",
            "--reset",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "files_indexed" in result.output
