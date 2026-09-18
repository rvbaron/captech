"""Tests for SQLite store (Milestone 7).

Verifies:
- Migration creates expected tables.
- File/chunk/symbol upsert operations are idempotent.
- FTS5 lexical search works.
- Symbol lookup and graph queries work.
- Metadata storage works.
"""

import tempfile
from pathlib import Path

import pytest

from legacylift_search.models import (
    CodeChunk,
    GraphEdge,
    SourceFile,
    Symbol,
    SymbolRef,
    TextRange,
)
from legacylift_search.store import SQLiteStore


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite"
        yield db_path


@pytest.fixture
def store(temp_db):
    """Create a SQLiteStore with migrations applied."""
    s = SQLiteStore(temp_db)
    s.migrate()
    yield s
    s.close()


def test_migration_creates_tables(store, temp_db):
    """Migration should create all expected tables."""
    conn = store._connect()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [row["name"] for row in tables]

    expected = [
        "chunks",
        "chunk_fts",
        "chunk_fts_config",
        "chunk_fts_content",
        "chunk_fts_data",
        "chunk_fts_docsize",
        "chunk_fts_idx",
        "graph_edges",
        "index_metadata",
        "repo_files",
        "symbol_refs",
        "symbols",
    ]
    # FTS5 creates internal tables, so we check presence of main tables
    assert "repo_files" in table_names
    assert "chunks" in table_names
    assert "chunk_fts" in table_names
    assert "symbols" in table_names
    assert "symbol_refs" in table_names
    assert "graph_edges" in table_names
    assert "index_metadata" in table_names


def test_upsert_files_and_chunks_roundtrip(store):
    """Upsert files and chunks, verify idempotence."""
    repo_root = Path("/fake/repo")
    source_file = SourceFile(
        absolute_path=repo_root / "src/test.py",
        repo_root=repo_root,
        relative_path="src/test.py",
        language="python",
        size_bytes=512,
        sha256="abc123",
        mtime_ns=1234567890,
    )

    # First upsert
    store.upsert_files([source_file])
    stats = store.stats()
    assert stats.file_count == 1
    assert stats.languages == ["python"]

    # Idempotent: upsert same file again
    store.upsert_files([source_file])
    stats = store.stats()
    assert stats.file_count == 1

    # Upsert chunks
    chunk = CodeChunk(
        id="chunk:src/test.py:python:0:abc123",
        file_sha256="abc123",
        relative_path="src/test.py",
        language="python",
        chunk_index=0,
        chunk_kind="function",
        symbol_id=None,
        symbol_path=None,
        start_byte=0,
        end_byte=100,
        start_line=1,
        end_line=10,
        text="def hello():\n    pass",
        text_sha256="def456",
        token_count_estimate=5,
    )
    store.upsert_chunks([chunk])

    stats = store.stats()
    assert stats.chunk_count == 1

    # Idempotent: upsert same chunk again
    store.upsert_chunks([chunk])
    stats = store.stats()
    assert stats.chunk_count == 1

    # Retrieve chunk
    retrieved = store.get_chunk(chunk.id)
    assert retrieved is not None
    assert retrieved.relative_path == "src/test.py"
    assert retrieved.language == "python"
    assert retrieved.text == "def hello():\n    pass"


def test_fts5_lexical_search(store):
    """Insert chunk text and verify FTS5 search returns it."""
    repo_root = Path("/fake/repo")
    source_file = SourceFile(
        absolute_path=repo_root / "src/eligibility.py",
        repo_root=repo_root,
        relative_path="src/eligibility.py",
        language="python",
        size_bytes=1024,
        sha256="eligibility123",
        mtime_ns=9876543210,
    )
    store.upsert_files([source_file])

    chunk = CodeChunk(
        id="chunk:src/eligibility.py:python:0:xyz",
        file_sha256="eligibility123",
        relative_path="src/eligibility.py",
        language="python",
        chunk_index=0,
        chunk_kind="function",
        symbol_id="python:src/eligibility.py:check_eligibility:1",
        symbol_path="check_eligibility",
        start_byte=0,
        end_byte=200,
        start_line=1,
        end_line=20,
        text="def check_eligibility(provider_id):\n    return validate(provider_id)",
        text_sha256="xyz",
        token_count_estimate=10,
    )
    store.upsert_chunks([chunk])

    # Search for a known token
    results = store.search_lexical("eligibility", limit=5)
    assert len(results) == 1
    assert results[0].chunk_id == chunk.id
    assert results[0].relative_path == "src/eligibility.py"

    # Search for another token
    results = store.search_lexical("provider_id", limit=5)
    assert len(results) == 1

    # Search for non-existent token
    results = store.search_lexical("nonexistent", limit=5)
    assert len(results) == 0


def test_symbol_upsert_and_find(store):
    """Upsert symbols and verify find_symbols returns them."""
    repo_root = Path("/fake/repo")
    source_file = SourceFile(
        absolute_path=repo_root / "src/service.py",
        repo_root=repo_root,
        relative_path="src/service.py",
        language="python",
        size_bytes=2048,
        sha256="service123",
        mtime_ns=111222333,
    )
    store.upsert_files([source_file])

    symbol = Symbol(
        id="python:src/service.py:EligibilityService:5",
        language="python",
        name="EligibilityService",
        qualified_name="EligibilityService",
        kind="class",
        entity_class="other",
        range=TextRange(start_byte=50, end_byte=250, start_line=5, end_line=15),
        container=None,
        signature=None,
    )
    store.upsert_symbols(source_file, [symbol])

    stats = store.stats()
    assert stats.symbol_count == 1

    # Exact name match
    results = store.find_symbols("EligibilityService", limit=10)
    assert len(results) == 1
    assert results[0].name == "EligibilityService"
    assert results[0].kind == "class"

    # Case-insensitive contains (fallback)
    results = store.find_symbols("Eligibility", limit=10)
    assert len(results) == 1

    # Retrieve by ID
    retrieved = store.get_symbol(symbol.id)
    assert retrieved is not None
    assert retrieved.qualified_name == "EligibilityService"


def test_graph_edges_caller_callee(store):
    """Insert a resolved edge and verify callers/callees queries."""
    repo_root = Path("/fake/repo")
    source_file = SourceFile(
        absolute_path=repo_root / "src/graph.py",
        repo_root=repo_root,
        relative_path="src/graph.py",
        language="python",
        size_bytes=1024,
        sha256="graph123",
        mtime_ns=987654321,
    )
    store.upsert_files([source_file])

    caller = Symbol(
        id="python:src/graph.py:main:1",
        language="python",
        name="main",
        qualified_name="main",
        kind="function",
        entity_class="other",
        range=TextRange(start_byte=0, end_byte=100, start_line=1, end_line=10),
    )
    callee = Symbol(
        id="python:src/graph.py:helper:12",
        language="python",
        name="helper",
        qualified_name="helper",
        kind="function",
        entity_class="other",
        range=TextRange(start_byte=101, end_byte=200, start_line=12, end_line=20),
    )
    store.upsert_symbols(source_file, [caller, callee])

    edge = GraphEdge(
        id="edge:main:helper:5:calls",
        caller_symbol_id=caller.id,
        callee_symbol_id=callee.id,
        callee_name="helper",
        edge_kind="calls",
        confidence=0.85,
        evidence="helper()",
        source_ref_id=None,
        relative_path="src/graph.py",
        start_line=5,
    )
    store.upsert_edges([edge])

    stats = store.stats()
    assert stats.edge_count == 1

    # Query callers of 'helper'
    callers_of_helper = store.callers(callee.id, depth=1)
    assert len(callers_of_helper) == 1
    assert callers_of_helper[0].caller_symbol_id == caller.id
    assert callers_of_helper[0].callee_name == "helper"

    # Query callees of 'main'
    callees_of_main = store.callees(caller.id, depth=1)
    assert len(callees_of_main) == 1
    assert callees_of_main[0].callee_symbol_id == callee.id
    assert callees_of_main[0].edge_kind == "calls"


def test_metadata_storage(store):
    """set_metadata and get_metadata should round-trip."""
    store.set_metadata("schema_version", "1")
    store.set_metadata("indexed_at", "2026-05-15T12:00:00Z")

    assert store.get_metadata("schema_version") == "1"
    assert store.get_metadata("indexed_at") == "2026-05-15T12:00:00Z"
    assert store.get_metadata("nonexistent") is None

    # Update existing key
    store.set_metadata("schema_version", "2")
    assert store.get_metadata("schema_version") == "2"


def test_upsert_refs(store):
    """Upsert symbol references and verify count."""
    repo_root = Path("/fake/repo")
    source_file = SourceFile(
        absolute_path=repo_root / "src/refs.py",
        repo_root=repo_root,
        relative_path="src/refs.py",
        language="python",
        size_bytes=512,
        sha256="refs123",
        mtime_ns=1111111111,
    )
    store.upsert_files([source_file])

    ref = SymbolRef(
        id="python:src/refs.py:ref:validate:10:50",
        language="python",
        name="validate",
        kind="call",
        range=TextRange(start_byte=50, end_byte=60, start_line=10, end_line=10),
        enclosing_symbol_id="python:src/refs.py:check:5",
        evidence="validate(x)",
    )
    store.upsert_refs(source_file, [ref])

    stats = store.stats()
    assert stats.ref_count == 1

    # Idempotent
    store.upsert_refs(source_file, [ref])
    stats = store.stats()
    assert stats.ref_count == 1
