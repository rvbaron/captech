"""Tests for vector_store module (Milestone 9b)."""

import os
import sys
import tempfile
from pathlib import Path

import pytest
from legacylift_search.embeddings import HashEmbedder
from legacylift_search.models import CodeChunk
from legacylift_search.vector_store import ChromaVectorStore

# Windows-specific workaround for ChromaDB's persistent SQLite file locks
IS_WINDOWS = sys.platform == "win32"


class TestCloseClearsChromaSystemCache:
    """`close()` must leave nothing a later open would resurrect.

    Regression test for the defect that made the suite green on Windows and red
    on the first Linux CI run. `chromadb.PersistentClient` is cached per path in
    a process-global `SharedSystemClient._identifier_to_system`, so reopening a
    path returns the System -- and the SQLite connection -- from the first open.
    Harmless until `--reset` replaces the directory underneath it, at which
    point Linux raises SQLite 1032 (`SQLITE_READONLY_DBMOVED`), reported as
    "attempt to write a readonly database", while Windows masks it because
    `rmtree(..., ignore_errors=True)` cannot delete held-open files and fails
    silently.

    Asserted on the cache itself rather than by deleting a directory, because
    the deletion half is exactly the part whose behaviour differs per platform:
    this way the invariant is pinned identically everywhere.
    """

    def test_close_empties_the_process_global_system_cache(self):
        from chromadb.api.shared_system_client import SharedSystemClient

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS) as tmpdir:
            store = ChromaVectorStore(
                base_dir=Path(tmpdir),
                collection_name="test_cache_clear",
                embedder=HashEmbedder(dimension=64),
                metadata={},
            )
            # Opening one populates the cache -- if this ever stops being true,
            # the test below would pass vacuously and prove nothing.
            assert SharedSystemClient._identifier_to_system, (
                "chromadb no longer caches Systems by path; re-derive whether "
                "the --reset interaction this guards still exists"
            )

            store.close()

            assert SharedSystemClient._identifier_to_system == {}
            assert SharedSystemClient._identifier_to_refcount == {}

    def test_reopening_a_replaced_directory_works(self):
        """The end-to-end shape of the bug: open, close, replace, reopen, query.

        On Linux before the fix this raised SQLite 1032 from the cached
        connection. It must simply return no results -- the directory is new.
        """
        import shutil

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS) as tmpdir:
            index_dir = Path(tmpdir)
            embedder = HashEmbedder(dimension=64)

            store = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_replaced_dir",
                embedder=embedder,
                metadata={},
            )
            chroma_path = Path(store.client._identifier)  # the on-disk path
            store.close()

            # What `--reset` does.
            shutil.rmtree(chroma_path, ignore_errors=True)

            reopened = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_replaced_dir",
                embedder=embedder,
                metadata={},
            )
            try:
                assert reopened.collection.count() == 0
            finally:
                reopened.close()


class TestChromaVectorStore:
    """Tests for ChromaVectorStore."""

    def test_empty_collection_query_returns_empty(self):
        """Query against an empty collection returns no results without error."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS) as tmpdir:
            index_dir = Path(tmpdir)
            embedder = HashEmbedder(dimension=64)

            store = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_empty",
                embedder=embedder,
                metadata={"test": "empty"},
            )

            # Query with an arbitrary embedding
            query_vec = embedder.embed_query("provider enrollment")
            results = store.query(query_vec, limit=5)

            assert results == []

            # Close to release file handles (Windows compatibility)
            store.close()

    def test_upsert_and_query_round_trip(self):
        """Insert chunks and query them back successfully."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS) as tmpdir:
            index_dir = Path(tmpdir)
            embedder = HashEmbedder(dimension=64)

            store = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_roundtrip",
                embedder=embedder,
                metadata={"test": "roundtrip"},
            )

            # Create 3 test chunks
            chunks = [
                CodeChunk(
                    id="chunk:file.py:python:0:abc123",
                    file_sha256="hash1",
                    relative_path="src/file.py",
                    language="python",
                    chunk_index=0,
                    chunk_kind="function",
                    symbol_id="python:src/file.py:check_eligibility:5",
                    symbol_path="check_eligibility",
                    start_byte=0,
                    end_byte=100,
                    start_line=5,
                    end_line=18,
                    text="def check_eligibility(provider_id):\n    return validate(provider_id)",
                    text_sha256="abc123",
                    token_count_estimate=12,
                ),
                CodeChunk(
                    id="chunk:file.py:python:1:def456",
                    file_sha256="hash1",
                    relative_path="src/file.py",
                    language="python",
                    chunk_index=1,
                    chunk_kind="function",
                    symbol_id="python:src/file.py:validate:20",
                    symbol_path="validate",
                    start_byte=101,
                    end_byte=200,
                    start_line=20,
                    end_line=30,
                    text="def validate(provider_id):\n    return True",
                    text_sha256="def456",
                    token_count_estimate=8,
                ),
                CodeChunk(
                    id="chunk:other.py:python:0:ghi789",
                    file_sha256="hash2",
                    relative_path="src/other.py",
                    language="python",
                    chunk_index=0,
                    chunk_kind="class",
                    symbol_id="python:src/other.py:CustomerService:10",
                    symbol_path="CustomerService",
                    start_byte=0,
                    end_byte=150,
                    start_line=10,
                    end_line=25,
                    text="class CustomerService:\n    def enroll(self, customer_id):\n        pass",
                    text_sha256="ghi789",
                    token_count_estimate=10,
                ),
            ]

            # Embed chunks
            texts = [c.text for c in chunks]
            embeddings = embedder.embed_documents(texts)

            # Upsert into store
            store.upsert_chunks(chunks, embeddings)

            # Query with similar text
            query_vec = embedder.embed_query("check eligibility provider")
            results = store.query(query_vec, limit=3)

            # Should get results back
            assert len(results) > 0
            # All results should have valid fields
            for result in results:
                assert result.id
                assert result.document
                assert result.metadata
                assert isinstance(result.distance, float)
                assert "relative_path" in result.metadata
                assert "language" in result.metadata

            # Close to release file handles (Windows compatibility)
            store.close()

    def test_idempotent_upsert(self):
        """Upserting the same chunks twice does not duplicate them."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS) as tmpdir:
            index_dir = Path(tmpdir)
            embedder = HashEmbedder(dimension=64)

            store = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_idempotent",
                embedder=embedder,
                metadata={},
            )

            # Create a single chunk
            chunk = CodeChunk(
                id="chunk:file.py:python:0:abc",
                file_sha256="hash1",
                relative_path="src/file.py",
                language="python",
                chunk_index=0,
                chunk_kind="function",
                symbol_id="python:src/file.py:func:5",
                symbol_path="func",
                start_byte=0,
                end_byte=50,
                start_line=5,
                end_line=10,
                text="def func(): pass",
                text_sha256="abc",
                token_count_estimate=4,
            )

            embedding = embedder.embed_documents([chunk.text])

            # Upsert once
            store.upsert_chunks([chunk], embedding)

            # Query to get initial count
            query_vec = embedder.embed_query("func")
            results1 = store.query(query_vec, limit=10)
            count1 = len(results1)

            # Upsert again
            store.upsert_chunks([chunk], embedding)

            # Query again
            results2 = store.query(query_vec, limit=10)
            count2 = len(results2)

            # Count should be stable (no duplication)
            assert count1 == count2
            assert count1 == 1  # Should be exactly 1 chunk

            # Close to release file handles (Windows compatibility)
            store.close()

    def test_dimension_validation_mismatch_raises(self):
        """Building a collection with one dimension, then another, raises ValueError."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS) as tmpdir:
            index_dir = Path(tmpdir)
            embedder_64 = HashEmbedder(dimension=64)

            # Create a collection with dimension 64
            store_64 = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_dimension",
                embedder=embedder_64,
                metadata={"test": "dimension"},
            )

            # Upsert a chunk so the collection has data
            chunk = CodeChunk(
                id="chunk:file.py:python:0:abc",
                file_sha256="hash1",
                relative_path="src/file.py",
                language="python",
                chunk_index=0,
                chunk_kind="function",
                symbol_id=None,
                symbol_path=None,
                start_byte=0,
                end_byte=50,
                start_line=5,
                end_line=10,
                text="def func(): pass",
                text_sha256="abc",
                token_count_estimate=4,
            )
            embedding = embedder_64.embed_documents([chunk.text])
            store_64.upsert_chunks([chunk], embedding)

            # Now attempt to create a store with dimension 128 on the same collection
            embedder_128 = HashEmbedder(dimension=128)

            store_128 = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_dimension",  # Same collection name
                embedder=embedder_128,
                metadata={"test": "dimension"},
            )

            # validate_dimension should raise ValueError
            with pytest.raises(ValueError) as exc_info:
                store_128.validate_dimension()

            error_msg = str(exc_info.value)
            assert "64" in error_msg
            assert "128" in error_msg
            assert "--reset" in error_msg

            # Close to release file handles (Windows compatibility)
            store_64.close()
            store_128.close()

    def test_metadata_round_trip(self):
        """Stored metadata fields come back unchanged on query (None handled)."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS) as tmpdir:
            index_dir = Path(tmpdir)
            embedder = HashEmbedder(dimension=64)

            store = ChromaVectorStore(
                base_dir=index_dir,
                collection_name="test_metadata",
                embedder=embedder,
                metadata={},
            )

            # Create a chunk with some None values
            chunk = CodeChunk(
                id="chunk:file.py:python:0:abc",
                file_sha256="hash1",
                relative_path="src/file.py",
                language="python",
                chunk_index=0,
                chunk_kind="fallback",
                symbol_id=None,  # None value
                symbol_path=None,  # None value
                start_byte=0,
                end_byte=50,
                start_line=5,
                end_line=10,
                text="some code here",
                text_sha256="abc",
                token_count_estimate=4,
            )

            embedding = embedder.embed_documents([chunk.text])
            store.upsert_chunks([chunk], embedding)

            # Query and retrieve
            query_vec = embedder.embed_query("some code")
            results = store.query(query_vec, limit=1)

            assert len(results) == 1
            result = results[0]

            # Check metadata fields
            assert result.metadata["relative_path"] == "src/file.py"
            assert result.metadata["language"] == "python"
            assert result.metadata["chunk_kind"] == "fallback"
            # None should be coerced to empty string
            assert result.metadata["symbol_id"] == ""
            assert result.metadata["symbol_path"] == ""
            assert result.metadata["start_line"] == "5"
            assert result.metadata["end_line"] == "10"
            assert result.metadata["text_sha256"] == "abc"

            # Close to release file handles (Windows compatibility)
            store.close()


class TestQwenEmbedderErrorMessage:
    """Test QwenEmbedder error message (Milestone 9b)."""

    def test_qwen_embedder_error_message_on_bogus_model(self):
        """QwenEmbedder with bogus model raises RuntimeError mentioning --embedding-provider hash."""
        try:
            import sentence_transformers
        except ImportError:
            pytest.skip("sentence_transformers not installed")

        from legacylift_search.embeddings import QwenEmbedder

        # Create embedder with a bogus model name
        embedder = QwenEmbedder(
            model="bogus/nonexistent-model-xyz",
            dimension=1024,
            normalize=True,
            batch_size=16,
            device="cpu",
        )

        # Attempting to embed should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            embedder.embed_query("test")

        error_msg = str(exc_info.value)
        # Error should mention --embedding-provider hash
        assert "--embedding-provider hash" in error_msg
        # Error should mention the model name
        assert "bogus/nonexistent-model-xyz" in error_msg
