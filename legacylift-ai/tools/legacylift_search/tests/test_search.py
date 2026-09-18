"""Tests for hybrid search with RRF fusion (Milestone 11)."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from legacylift_search.config import Manifest, SearchConfig
from legacylift_search.embeddings import HashEmbedder
from legacylift_search.indexer import Indexer
from legacylift_search.models import SearchResult
from legacylift_search.search import SearchEngine, sanitize_fts_query
from legacylift_search.store import LexicalResult, SQLiteStore
from legacylift_search.vector_store import ChromaVectorStore, VectorResult


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


# -- helpers -----------------------------------------------------------------


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _hash_manifest() -> Manifest:
    m = Manifest()
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    return m


def _build_index(tmp_path: Path) -> tuple[Path, Manifest]:
    repo = _copy_fixture(tmp_path)
    manifest = _hash_manifest()
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")
    return repo, manifest


# -- pure scoring math (no I/O) ---------------------------------------------


def _make_engine_with_fakes(
    vector_ids_in_order: list[str],
    lexical_ids_in_order: list[str],
    chunks_by_id: dict[str, MagicMock],
    config: SearchConfig | None = None,
) -> SearchEngine:
    """Build a SearchEngine wired to mock store/vector_store/embedder."""
    store = MagicMock(spec=SQLiteStore)
    store.search_lexical.return_value = [
        LexicalResult(
            chunk_id=cid,
            relative_path=chunks_by_id[cid].relative_path,
            language=chunks_by_id[cid].language,
            symbol_path=chunks_by_id[cid].symbol_path,
            start_line=chunks_by_id[cid].start_line,
            end_line=chunks_by_id[cid].end_line,
            rank=float(i),
        )
        for i, cid in enumerate(lexical_ids_in_order)
    ]
    store.get_chunk.side_effect = lambda cid: chunks_by_id.get(cid)

    vector_store = MagicMock(spec=ChromaVectorStore)
    vector_store.query.return_value = [
        VectorResult(
            id=cid,
            document=chunks_by_id[cid].text or "",
            metadata={},
            distance=0.1 * (i + 1),
        )
        for i, cid in enumerate(vector_ids_in_order)
    ]

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.0] * 8

    return SearchEngine(
        store, vector_store, embedder, config or SearchConfig()
    )


def _fake_chunk(
    cid: str,
    rel: str = "src/foo.py",
    text: str = "def foo():\n    return 1\n",
    symbol_path: str | None = "foo",
) -> MagicMock:
    m = MagicMock()
    m.id = cid
    m.relative_path = rel
    m.language = "python"
    m.start_line = 1
    m.end_line = 2
    m.symbol_path = symbol_path
    m.text = text
    return m


def test_rrf_score_math() -> None:
    """RRF: score = 1/(k+vrank) + 1/(k+lrank). k=60."""
    chunks = {
        "a": _fake_chunk("a"),
        "b": _fake_chunk("b", rel="src/bar.py"),
    }
    engine = _make_engine_with_fakes(
        vector_ids_in_order=["a", "b"],
        lexical_ids_in_order=["b"],
        chunks_by_id=chunks,
        config=SearchConfig(rrf_rank_constant=60),
    )
    results = engine.search("foo")
    by_id = {r.chunk_id: r for r in results}

    # a: vector_rank=1, lexical_rank=None -> 1/61
    assert by_id["a"].vector_rank == 1
    assert by_id["a"].lexical_rank is None
    assert by_id["a"].score == pytest.approx(1.0 / 61.0)

    # b: vector_rank=2, lexical_rank=1 -> 1/62 + 1/61
    assert by_id["b"].vector_rank == 2
    assert by_id["b"].lexical_rank == 1
    assert by_id["b"].score == pytest.approx(1.0 / 62.0 + 1.0 / 61.0)

    # b should outrank a (higher score).
    assert results[0].chunk_id == "b"
    assert results[1].chunk_id == "a"


def test_limit_override() -> None:
    chunks = {f"c{i}": _fake_chunk(f"c{i}", rel=f"src/f{i}.py") for i in range(5)}
    engine = _make_engine_with_fakes(
        vector_ids_in_order=list(chunks),
        lexical_ids_in_order=[],
        chunks_by_id=chunks,
        config=SearchConfig(default_limit=10),
    )
    results = engine.search("any", limit=2)
    assert len(results) == 2

    results_default = engine.search("any")
    assert len(results_default) == 5  # below default_limit


def test_sanitize_fts_query_handles_punctuation() -> None:
    # Must not raise and must not embed special characters.
    assert sanitize_fts_query("foo bar") == "foo bar"
    assert sanitize_fts_query("foo'bar; DROP TABLE chunks;") == (
        "foo bar DROP TABLE chunks"
    )
    assert sanitize_fts_query('"hello" (world) AND \'or\' 1=1') == (
        "hello world AND or 1 1"
    )
    assert sanitize_fts_query("---") == ""
    assert sanitize_fts_query("") == ""


def test_lexical_search_punctuation_does_not_raise(tmp_path: Path) -> None:
    """Real SQLite FTS5 search with punctuation-heavy query should not raise."""
    repo, _manifest = _build_index(tmp_path)
    sqlite_path = (
        repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    )
    store = SQLiteStore(sqlite_path)
    try:
        for q in [
            "eligibility validation",
            'foo "bar" baz',
            "(check) AND or; DROP",
            "x' OR 1=1 --",
            "func(a, b)",
        ]:
            sanitized = sanitize_fts_query(q)
            if sanitized:
                store.search_lexical(sanitized, 5)  # must not raise
    finally:
        store.close()


def test_search_returns_result_with_path_and_snippet(tmp_path: Path) -> None:
    """End-to-end search against the fixture index returns a usable result."""
    repo, manifest = _build_index(tmp_path)
    index_dir = repo / "legacylift-docs" / "index" / "code-search"
    sqlite_path = index_dir / manifest.index.sqlite_file

    store = SQLiteStore(sqlite_path)
    embedder = HashEmbedder(dimension=64)
    vstore = ChromaVectorStore(
        base_dir=index_dir,
        collection_name=manifest.index.collection_name,
        embedder=embedder,
        metadata={},
    )
    try:
        engine = SearchEngine(store, vstore, embedder, manifest.search)
        # "eligibility validation" should match something in the fixture.
        results = engine.search("eligibility validation", limit=5)
        assert results, "expected at least one search result"
        first = results[0]
        assert isinstance(first, SearchResult)
        assert first.relative_path
        assert first.start_line >= 1
        assert first.end_line >= first.start_line
        assert first.snippet  # non-empty
        assert first.language
    finally:
        vstore.close()
        store.close()
