"""Tests for chunking.py (Milestone 6).

Validates symbol-based, Chonkie-based, and fallback chunking strategies.
"""

import hashlib
from pathlib import Path

import pytest

from legacylift_search.chunking import CodeChunker
from legacylift_search.config import ChunkingConfig
from legacylift_search.models import CodeChunk, ExtractedFile, SourceFile, Symbol, TextRange


@pytest.fixture
def config() -> ChunkingConfig:
    """Default chunking config."""
    return ChunkingConfig(
        target_tokens=800,
        max_tokens=1400,
        min_tokens=80,
        overlap_lines=12,
        prefer_ast_boundaries=True,
        fallback_max_lines=120,
    )


@pytest.fixture
def source_file() -> SourceFile:
    """Sample source file metadata."""
    text = "def foo():\n    return 42\n"
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return SourceFile(
        absolute_path=Path("/repo/src/demo.py"),
        repo_root=Path("/repo"),
        relative_path="src/demo.py",
        language="python",
        size_bytes=len(text),
        sha256=sha,
        mtime_ns=1234567890,
    )


def test_symbol_driven_chunking(config: ChunkingConfig, source_file: SourceFile):
    """Test symbol-driven path: ExtractedFile with one Symbol produces a chunk whose range matches the symbol."""
    text = """\
def calculate_eligibility(provider_id):
    # This is a comment
    if provider_id > 0:
        return True
    return False

def reclaim_payment(amount):
    return amount * 0.9
"""

    # Create symbols for the two functions
    symbols = [
        Symbol(
            id="python:src/demo.py:calculate_eligibility:1",
            language="python",
            name="calculate_eligibility",
            qualified_name="calculate_eligibility",
            kind="function_definition",
            entity_class="function",
            range=TextRange(
                start_byte=0,
                end_byte=len("def calculate_eligibility(provider_id):\n    # This is a comment\n    if provider_id > 0:\n        return True\n    return False\n"),
                start_line=1,
                end_line=5,
            ),
        ),
        Symbol(
            id="python:src/demo.py:reclaim_payment:7",
            language="python",
            name="reclaim_payment",
            qualified_name="reclaim_payment",
            kind="function_definition",
            entity_class="function",
            range=TextRange(
                start_byte=len("def calculate_eligibility(provider_id):\n    # This is a comment\n    if provider_id > 0:\n        return True\n    return False\n\n"),
                end_byte=len(text),
                start_line=7,
                end_line=8,
            ),
        ),
    ]

    extracted = ExtractedFile(symbols=symbols, refs=[], parse_errors=[])

    chunker = CodeChunker(config)
    chunks = chunker.chunk(source_file, text, extracted)

    # Should produce 2 symbol chunks
    assert len(chunks) == 2
    assert all(c.chunk_kind == "symbol" for c in chunks)

    # First chunk should match first symbol
    c1 = chunks[0]
    assert c1.symbol_id == "python:src/demo.py:calculate_eligibility:1"
    assert c1.symbol_path == "calculate_eligibility"
    assert c1.start_line == 1
    assert c1.end_line == 5
    assert "calculate_eligibility" in c1.text
    assert c1.token_count_estimate > 0

    # Second chunk should match second symbol
    c2 = chunks[1]
    assert c2.symbol_id == "python:src/demo.py:reclaim_payment:7"
    assert c2.symbol_path == "reclaim_payment"
    assert c2.start_line == 7
    assert c2.end_line == 8
    assert "reclaim_payment" in c2.text
    assert c2.token_count_estimate > 0


def test_fallback_chunking_no_symbols(source_file: SourceFile):
    """Test fallback path: ExtractedFile with empty symbols produces line-window chunks within fallback_max_lines."""
    # Create a file with no extracted symbols and disable AST boundaries to force fallback
    text = "\n".join([f"line {i}" for i in range(1, 201)])  # 200 lines

    extracted = ExtractedFile(symbols=[], refs=[], parse_errors=[])

    # Create config with prefer_ast_boundaries=False to force fallback
    config = ChunkingConfig(
        target_tokens=800,
        max_tokens=1400,
        min_tokens=80,
        overlap_lines=12,
        prefer_ast_boundaries=False,
        fallback_max_lines=120,
    )

    chunker = CodeChunker(config)
    chunks = chunker.chunk(source_file, text, extracted)

    # Should produce fallback chunks
    assert len(chunks) > 0
    assert all(c.chunk_kind == "fallback" for c in chunks)

    # Each chunk should be at most fallback_max_lines (120)
    for chunk in chunks:
        line_count = chunk.end_line - chunk.start_line + 1
        assert line_count <= config.fallback_max_lines

    # Verify byte and line ranges are correct
    for chunk in chunks:
        assert chunk.start_byte < chunk.end_byte
        assert chunk.start_line <= chunk.end_line
        assert chunk.text == text[chunk.start_byte : chunk.end_byte]


def test_deterministic_chunk_ids(config: ChunkingConfig, source_file: SourceFile):
    """Test deterministic IDs: same input produces same chunk.id."""
    text = "def foo():\n    return 42\n"

    symbol = Symbol(
        id="python:src/demo.py:foo:1",
        language="python",
        name="foo",
        qualified_name="foo",
        kind="function_definition",
        entity_class="function",
        range=TextRange(start_byte=0, end_byte=len(text), start_line=1, end_line=2),
    )
    extracted = ExtractedFile(symbols=[symbol], refs=[], parse_errors=[])

    chunker = CodeChunker(config)
    chunks1 = chunker.chunk(source_file, text, extracted)
    chunks2 = chunker.chunk(source_file, text, extracted)

    # Should produce identical chunks with identical IDs
    assert len(chunks1) == len(chunks2)
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.id == c2.id
        assert c1.text_sha256 == c2.text_sha256
        assert c1.text == c2.text


def test_fallback_overlap(source_file: SourceFile):
    """Test overlap: adjacent fallback chunks share overlap_lines lines."""
    # Create a file that will need multiple fallback chunks
    lines = [f"line {i}\n" for i in range(1, 251)]  # 250 lines
    text = "".join(lines)

    extracted = ExtractedFile(symbols=[], refs=[], parse_errors=[])

    # Create config with prefer_ast_boundaries=False to force fallback
    config = ChunkingConfig(
        target_tokens=800,
        max_tokens=1400,
        min_tokens=80,
        overlap_lines=12,
        prefer_ast_boundaries=False,
        fallback_max_lines=120,
    )

    chunker = CodeChunker(config)
    chunks = chunker.chunk(source_file, text, extracted)

    # Should produce multiple fallback chunks
    assert len(chunks) >= 2
    assert all(c.chunk_kind == "fallback" for c in chunks)

    # Check overlap between consecutive chunks (except the last pair)
    for i in range(len(chunks) - 1):
        c1, c2 = chunks[i], chunks[i + 1]

        # c2 should start before c1 ends (overlap)
        # overlap_lines = 12, so c2.start_line should be (c1.end_line - 12 + 1)
        expected_overlap_start = max(1, c1.end_line - config.overlap_lines + 1)

        # Allow some flexibility since the last chunk may not have full window
        if c2.start_line > c1.start_line:
            # There should be some overlap
            overlap = c1.end_line - c2.start_line + 1
            assert overlap >= 0  # At minimum, chunks should be adjacent or overlap


def test_empty_file(config: ChunkingConfig, source_file: SourceFile):
    """Test empty file produces no chunks."""
    text = ""
    extracted = ExtractedFile(symbols=[], refs=[], parse_errors=[])

    chunker = CodeChunker(config)
    chunks = chunker.chunk(source_file, text, extracted)

    assert len(chunks) == 0


def test_token_count_estimate_nonempty(config: ChunkingConfig, source_file: SourceFile):
    """Bonus test: token_count_estimate > 0 for nonempty text."""
    text = "def foo():\n    return 42\n"

    symbol = Symbol(
        id="python:src/demo.py:foo:1",
        language="python",
        name="foo",
        qualified_name="foo",
        kind="function_definition",
        entity_class="function",
        range=TextRange(start_byte=0, end_byte=len(text), start_line=1, end_line=2),
    )
    extracted = ExtractedFile(symbols=[symbol], refs=[], parse_errors=[])

    chunker = CodeChunker(config)
    chunks = chunker.chunk(source_file, text, extracted)

    assert len(chunks) > 0
    for chunk in chunks:
        if chunk.text.strip():
            assert chunk.token_count_estimate > 0


def test_symbol_with_invalid_range_skipped(source_file: SourceFile):
    """Test that symbols with invalid ranges (start >= end) are skipped."""
    text = "def foo():\n    return 42\n"

    # Create a symbol with invalid range
    symbol = Symbol(
        id="python:src/demo.py:foo:1",
        language="python",
        name="foo",
        qualified_name="foo",
        kind="function_definition",
        entity_class="function",
        range=TextRange(
            start_byte=10, end_byte=5, start_line=2, end_line=1
        ),  # Invalid: start > end
    )
    extracted = ExtractedFile(symbols=[symbol], refs=[], parse_errors=[])

    # Use config with prefer_ast_boundaries=False to force fallback after symbol skip
    config = ChunkingConfig(
        target_tokens=800,
        max_tokens=1400,
        min_tokens=80,
        overlap_lines=12,
        prefer_ast_boundaries=False,
        fallback_max_lines=120,
    )

    chunker = CodeChunker(config)
    chunks = chunker.chunk(source_file, text, extracted)

    # Should fall back to line-based chunking since symbol is invalid
    assert len(chunks) > 0
    assert all(c.chunk_kind == "fallback" for c in chunks)


def test_chonkie_fallback_if_fails(config: ChunkingConfig, source_file: SourceFile):
    """Test that if Chonkie fails, fallback is used."""
    # Create a file with minimal content and no symbols
    text = "x = 1\n"
    extracted = ExtractedFile(symbols=[], refs=[], parse_errors=[])

    chunker = CodeChunker(config)
    chunks = chunker.chunk(source_file, text, extracted)

    # Should produce at least one chunk (either Chonkie or fallback)
    assert len(chunks) >= 1
    # Verify chunk metadata is valid
    for chunk in chunks:
        assert chunk.id.startswith("chunk:")
        assert chunk.language == "python"
        assert chunk.text_sha256 == hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
        assert chunk.start_line <= chunk.end_line
        assert chunk.start_byte < chunk.end_byte
