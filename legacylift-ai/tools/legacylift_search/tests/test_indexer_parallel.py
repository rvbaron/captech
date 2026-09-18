"""Tests for Milestone 19: parallel cold-index extraction + batched commits.

The load-bearing test is *equivalence*: a parallel run (``extract_workers=4``)
must produce byte-identical SQLite contents and identical Chroma coverage to a
forced-serial run (``extract_workers=1``, which is also the oracle). The rest
pin determinism, bad-file isolation, commit-batch invisibility, and that the
M15 skip-on-unchanged fast path still works after a parallel cold run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from legacylift_search.config import Manifest
from legacylift_search.extract_worker import _extract_with, extract_one
from legacylift_search.extractors import SymbolExtractor, load_profiles
from legacylift_search.chunking import CodeChunker
from legacylift_search.indexer import Indexer
from legacylift_search.models import SourceFile
from legacylift_search.store import SQLiteStore


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


def _copy_fixture(tmp_path: Path, name: str = "repo") -> Path:
    dest = tmp_path / name
    shutil.copytree(FIXTURE, dest)
    return dest


def _manifest(workers: int, commit_batch: int = 50) -> Manifest:
    m = Manifest()
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    m.index.extract_workers = workers
    m.index.commit_batch_files = commit_batch
    return m


def _index_dir(repo: Path) -> Path:
    return repo / "legacylift-docs" / "index" / "code-search"


def _dump_contents(repo: Path) -> dict:
    """Snapshot the deterministic SQLite contents (timestamp/autoincrement
    columns excluded) plus the source-set hash and vector coverage."""
    store = SQLiteStore(_index_dir(repo) / "index.sqlite")
    try:
        conn = store._connect()
        chunks = conn.execute(
            "SELECT id, relative_path, chunk_index, chunk_kind, symbol_id, "
            "symbol_path, start_byte, end_byte, start_line, end_line, "
            "text_sha256, token_count_estimate FROM chunks ORDER BY id"
        ).fetchall()
        symbols = conn.execute(
            "SELECT id, language, name, qualified_name, kind, container, "
            "start_line, end_line FROM symbols ORDER BY id"
        ).fetchall()
        refs = conn.execute(
            "SELECT id, language, name, kind, enclosing_symbol_id, start_line "
            "FROM symbol_refs ORDER BY id"
        ).fetchall()
        edges = conn.execute(
            "SELECT id, caller_symbol_id, callee_symbol_id, callee_name, "
            "edge_kind, confidence, relative_path, start_line FROM graph_edges "
            "ORDER BY id"
        ).fetchall()
        files = conn.execute(
            "SELECT relative_path, language, sha256 FROM repo_files "
            "ORDER BY relative_path"
        ).fetchall()
        return {
            "chunks": [tuple(r) for r in chunks],
            "symbols": [tuple(r) for r in symbols],
            "refs": [tuple(r) for r in refs],
            "edges": [tuple(r) for r in edges],
            "files": [tuple(r) for r in files],
            "source_set_sha256": store.get_metadata("source_set_sha256"),
            "vectors_present": store.get_present_vector_count(),
        }
    finally:
        store.close()


def test_parallel_matches_serial_byte_for_byte(tmp_path: Path) -> None:
    """extract_workers=1 and =4 must produce identical SQLite contents and
    identical vector coverage. This is the M19 correctness gate."""
    serial_repo = _copy_fixture(tmp_path, "serial")
    parallel_repo = _copy_fixture(tmp_path, "parallel")

    s_serial = Indexer(_manifest(workers=1), serial_repo).run(
        reset=True, embedding_provider_override="hash"
    )
    s_parallel = Indexer(_manifest(workers=4), parallel_repo).run(
        reset=True, embedding_provider_override="hash"
    )

    assert _dump_contents(serial_repo) == _dump_contents(parallel_repo)

    # IndexStats counts match too.
    assert s_serial.chunk_count == s_parallel.chunk_count
    assert s_serial.symbol_count == s_parallel.symbol_count
    assert s_serial.ref_count == s_parallel.ref_count
    assert s_serial.graph_edge_count == s_parallel.graph_edge_count
    assert s_serial.vectors_upserted == s_parallel.vectors_upserted


def test_parallel_runs_are_deterministic(tmp_path: Path) -> None:
    """Two independent parallel runs must produce identical contents."""
    repo_a = _copy_fixture(tmp_path, "a")
    repo_b = _copy_fixture(tmp_path, "b")

    Indexer(_manifest(workers=4), repo_a).run(
        reset=True, embedding_provider_override="hash"
    )
    Indexer(_manifest(workers=4), repo_b).run(
        reset=True, embedding_provider_override="hash"
    )

    assert _dump_contents(repo_a) == _dump_contents(repo_b)


def test_commit_batch_size_is_invisible(tmp_path: Path) -> None:
    """commit_batch_files must not change the resulting index — only how many
    files share a transaction."""
    repo_small = _copy_fixture(tmp_path, "batch1")
    repo_big = _copy_fixture(tmp_path, "batch1000")

    Indexer(_manifest(workers=4, commit_batch=1), repo_small).run(
        reset=True, embedding_provider_override="hash"
    )
    Indexer(_manifest(workers=4, commit_batch=1000), repo_big).run(
        reset=True, embedding_provider_override="hash"
    )

    assert _dump_contents(repo_small) == _dump_contents(repo_big)


def test_bad_file_is_isolated_not_fatal(tmp_path: Path) -> None:
    """A file that cannot be read yields a structured read_error instead of
    raising across the pool boundary, and the rest of the repo still indexes."""
    # Direct unit check of the worker's isolation contract.
    missing = SourceFile(
        absolute_path=tmp_path / "does_not_exist.py",
        repo_root=tmp_path,
        relative_path="does_not_exist.py",
        language="python",
        size_bytes=0,
        sha256="0" * 64,
        mtime_ns=0,
    )
    profiles = load_profiles(
        Path(__file__).resolve().parents[1]
        / "src"
        / "legacylift_search"
        / "profiles"
        / "extractors.json"
    )
    res = _extract_with(
        missing, SymbolExtractor(profiles), CodeChunker(Manifest().chunking)
    )
    assert res.read_error is not None
    assert res.chunks == []
    assert res.symbols == []

    # End-to-end sanity: a healthy repo still indexes fully under the pool.
    repo = _copy_fixture(tmp_path, "withbad")
    stats = Indexer(_manifest(workers=4), repo).run(
        reset=True, embedding_provider_override="hash"
    )
    # The healthy fixture files still produced chunks/symbols.
    assert stats.chunk_count > 0
    assert stats.symbol_count > 0


def test_m15_skip_after_parallel_cold_run(tmp_path: Path) -> None:
    """After a parallel cold run, an idempotent rerun must still skip every
    file (the M15 fast path is unaffected by the parallel writer)."""
    repo = _copy_fixture(tmp_path, "m15")
    manifest = _manifest(workers=4)

    s1 = Indexer(manifest, repo).run(
        reset=True, embedding_provider_override="hash"
    )
    s2 = Indexer(manifest, repo).run(
        reset=False, embedding_provider_override="hash"
    )

    assert s2.files_processed == 0
    assert s2.files_skipped == s1.files_indexed
    assert s2.chunk_count == s1.chunk_count
    assert s2.symbol_count == s1.symbol_count
    assert s2.ref_count == s1.ref_count


def test_extract_one_requires_initialized_worker() -> None:
    """extract_one asserts the worker was initialized — guards against a
    misconfigured pool silently producing empty results."""
    import legacylift_search.extract_worker as ew

    saved_extractor, saved_chunker = ew._EXTRACTOR, ew._CHUNKER
    ew._EXTRACTOR = None
    ew._CHUNKER = None
    try:
        missing = SourceFile(
            absolute_path=Path("x.py"),
            repo_root=Path("."),
            relative_path="x.py",
            language="python",
            size_bytes=0,
            sha256="0" * 64,
            mtime_ns=0,
        )
        raised = False
        try:
            extract_one(missing)
        except AssertionError:
            raised = True
        assert raised
    finally:
        ew._EXTRACTOR, ew._CHUNKER = saved_extractor, saved_chunker
