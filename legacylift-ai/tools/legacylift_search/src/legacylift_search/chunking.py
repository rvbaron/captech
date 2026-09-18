"""Code chunking (Chonkie + deterministic fallback).

Implements Milestone 6 of the ExecPlan
(`docs/exec-plans/active/semantic-code-search-graph-index.md`).

Strategy:
1. Prefer symbol ranges: create chunks from extracted symbols with non-empty ranges.
2. If symbol chunks cover <30% of file lines OR no symbols extracted, try Chonkie.
3. If Chonkie fails or unavailable, fall back to line-based windowing.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from .config import ChunkingConfig
from .models import CodeChunk, ExtractedFile, SourceFile, Symbol

logger = logging.getLogger(__name__)

# Chonkie is optional; track import success
_CHONKIE_AVAILABLE = False
try:
    from chonkie import CodeChunker as ChonkieCodeChunker

    _CHONKIE_AVAILABLE = True
except ImportError:
    logger.debug("Chonkie not available; will use fallback chunking only.")

# Languages that must never reach Chonkie, because Chonkie has no code grammar
# for them and falls back to `language="auto"` detection, which does not
# terminate. Measured on real NNG files 2026-09-08: `.jsp` hung >600s on a
# 13.9 KB file before being killed, `.tld` and `.css` hung >60s, and `.vm`
# took 13.80s to chunk 144 bytes -- the same pathology, merely not yet
# unbounded. `xml` was already excluded by a hardcoded `!= "xml"` check whose
# comment said exactly this; the seven languages added by the 2026-09-08
# coverage widening join it, and the one-off became this set.
#
# `cobol` is deliberately absent: it keeps its existing `"auto"` mapping, and
# behavior for all eight pre-existing languages is byte-identical across the
# widening. Pinned by `tests/test_coverage_config.py`.
_CHONKIE_SKIP_LANGUAGES = frozenset(
    {"xml", "jsp", "properties", "css", "velocity", "xml_entity", "tld", "xmi"}
)


class CodeChunker:
    """Chunks source code into retrievable segments."""

    def __init__(self, config: ChunkingConfig):
        """Initialize the chunker with configuration.

        Args:
            config: ChunkingConfig with overlap_lines, fallback_max_lines, etc.
        """
        self.config = config

    def chunk(
        self, source_file: SourceFile, text: str, extracted: ExtractedFile
    ) -> list[CodeChunk]:
        """Chunk a source file into retrievable code segments.

        Args:
            source_file: Metadata about the source file.
            text: Full text content of the file.
            extracted: Extracted symbols and references.

        Returns:
            List of CodeChunk instances with stable IDs and metadata.
        """
        if not text.strip():
            # Empty file: return empty list
            return []

        # Strategy 1: Try symbol-based chunking
        symbol_chunks = self._chunk_from_symbols(source_file, text, extracted.symbols)
        if symbol_chunks:
            total_lines = text.count("\n") + 1
            symbol_lines = sum(
                c.end_line - c.start_line + 1 for c in symbol_chunks
            )
            coverage = symbol_lines / total_lines if total_lines > 0 else 0
            if coverage >= 0.30:
                logger.debug(
                    f"{source_file.relative_path}: using {len(symbol_chunks)} symbol chunks "
                    f"(coverage={coverage:.1%})"
                )
                return symbol_chunks

        # Strategy 2: Try Chonkie if available and prefer_ast_boundaries is true.
        # XML is deliberately excluded: Chonkie has no XML code grammar, so it
        # falls back to language="auto" detection, which can hang indefinitely
        # on pathological input (e.g. a fully comment-wrapped .hbm.xml mapping).
        # XML symbols come from the framework-aware xml_extractor; anything it
        # cannot structure goes straight to deterministic line-based chunking.
        if (
            self.config.prefer_ast_boundaries
            and _CHONKIE_AVAILABLE
            and source_file.language not in _CHONKIE_SKIP_LANGUAGES
        ):
            chonkie_chunks = self._chunk_with_chonkie(source_file, text)
            if chonkie_chunks:
                logger.debug(
                    f"{source_file.relative_path}: using {len(chonkie_chunks)} Chonkie chunks"
                )
                return chonkie_chunks

        # Strategy 3: Fallback to line-based windowing
        fallback_chunks = self._chunk_fallback(source_file, text)
        logger.debug(
            f"{source_file.relative_path}: using {len(fallback_chunks)} fallback chunks"
        )
        return fallback_chunks

    def _chunk_from_symbols(
        self, source_file: SourceFile, text: str, symbols: list[Symbol]
    ) -> list[CodeChunk]:
        """Create chunks from extracted symbols with non-empty ranges.

        Args:
            source_file: Source file metadata.
            text: Full file text.
            symbols: List of extracted symbols.

        Returns:
            List of symbol-based chunks, or empty if none are suitable.
        """
        chunks: list[CodeChunk] = []
        for idx, symbol in enumerate(symbols):
            # Skip symbols with empty or invalid ranges
            if (
                symbol.range.start_byte >= symbol.range.end_byte
                or symbol.range.start_line > symbol.range.end_line
            ):
                continue

            # Extract text for this symbol
            symbol_text = text[symbol.range.start_byte : symbol.range.end_byte]
            if not symbol_text.strip():
                continue

            # Compute token count estimate
            token_count = self._estimate_tokens(symbol_text)

            # Skip symbols that are too large
            # Note: We don't skip symbols that are too small in the symbol-based path,
            # as even small symbols are valuable for retrieval if they have proper boundaries.
            # The min_tokens threshold is more relevant for arbitrary text chunking.
            if token_count > self.config.max_tokens * 2:
                # Symbol is very large; skip for now (could be split in future)
                continue

            # Create chunk
            text_sha = hashlib.sha256(symbol_text.encode("utf-8")).hexdigest()
            chunk_id = (
                f"chunk:{source_file.relative_path}:{source_file.language}:"
                f"{idx}:{text_sha[:12]}"
            )

            chunks.append(
                CodeChunk(
                    id=chunk_id,
                    file_sha256=source_file.sha256,
                    relative_path=source_file.relative_path,
                    language=source_file.language,
                    chunk_index=idx,
                    chunk_kind="symbol",
                    symbol_id=symbol.id,
                    symbol_path=symbol.qualified_name,
                    start_byte=symbol.range.start_byte,
                    end_byte=symbol.range.end_byte,
                    start_line=symbol.range.start_line,
                    end_line=symbol.range.end_line,
                    text=symbol_text,
                    text_sha256=text_sha,
                    token_count_estimate=token_count,
                )
            )

        return chunks

    def _chunk_with_chonkie(
        self, source_file: SourceFile, text: str
    ) -> list[CodeChunk]:
        """Attempt to chunk using Chonkie's AST-aware CodeChunker.

        Args:
            source_file: Source file metadata.
            text: Full file text.

        Returns:
            List of Chonkie-derived chunks, or empty if Chonkie fails.
        """
        try:
            # Map our language keys to Chonkie's expected language names
            lang_map = {
                "csharp": "c_sharp",
                "javascript": "javascript",
                "typescript": "typescript",
                "python": "python",
                "java": "java",
                "sql": "sql",
                "cobol": "auto",  # Chonkie may not support COBOL
            }
            chonkie_lang = lang_map.get(source_file.language, "auto")

            # Initialize Chonkie's CodeChunker with character tokenizer (no model dependency)
            chunker = ChonkieCodeChunker(
                tokenizer="character",
                chunk_size=self.config.target_tokens,
                language=chonkie_lang,
                include_nodes=False,
            )

            # Chunk the text
            chonkie_chunks = chunker.chunk(text)

            # Convert to our CodeChunk model
            chunks: list[CodeChunk] = []
            for idx, ch in enumerate(chonkie_chunks):
                # Chonkie returns Chunk objects with text, start_index, end_index
                chunk_text = ch.text
                start_byte = ch.start_index
                end_byte = ch.end_index

                # Compute line numbers from byte positions
                start_line = text[:start_byte].count("\n") + 1
                end_line = text[:end_byte].count("\n") + 1

                # Compute text SHA and token estimate
                text_sha = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                token_count = self._estimate_tokens(chunk_text)

                chunk_id = (
                    f"chunk:{source_file.relative_path}:{source_file.language}:"
                    f"{idx}:{text_sha[:12]}"
                )

                chunks.append(
                    CodeChunk(
                        id=chunk_id,
                        file_sha256=source_file.sha256,
                        relative_path=source_file.relative_path,
                        language=source_file.language,
                        chunk_index=idx,
                        chunk_kind="chonkie",
                        symbol_id=None,
                        symbol_path=None,
                        start_byte=start_byte,
                        end_byte=end_byte,
                        start_line=start_line,
                        end_line=end_line,
                        text=chunk_text,
                        text_sha256=text_sha,
                        token_count_estimate=token_count,
                    )
                )

            return chunks

        except Exception as e:
            logger.debug(f"Chonkie chunking failed for {source_file.relative_path}: {e}")
            return []

    def _chunk_fallback(self, source_file: SourceFile, text: str) -> list[CodeChunk]:
        """Fallback line-based chunking with overlap.

        Args:
            source_file: Source file metadata.
            text: Full file text.

        Returns:
            List of line-window chunks.
        """
        lines = text.splitlines(keepends=True)
        total_lines = len(lines)
        if total_lines == 0:
            return []

        chunks: list[CodeChunk] = []
        max_lines = self.config.fallback_max_lines
        overlap_lines = self.config.overlap_lines

        idx = 0
        pos = 0
        while pos < total_lines:
            # Determine window
            window_start = pos
            window_end = min(pos + max_lines, total_lines)

            # Extract lines
            window_lines = lines[window_start:window_end]
            chunk_text = "".join(window_lines)

            # Compute byte range
            start_byte = sum(len(line) for line in lines[:window_start])
            end_byte = start_byte + len(chunk_text)

            # Line numbers (1-based)
            start_line = window_start + 1
            end_line = window_end

            # Compute SHA and token estimate
            text_sha = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
            token_count = self._estimate_tokens(chunk_text)

            chunk_id = (
                f"chunk:{source_file.relative_path}:{source_file.language}:"
                f"{idx}:{text_sha[:12]}"
            )

            chunks.append(
                CodeChunk(
                    id=chunk_id,
                    file_sha256=source_file.sha256,
                    relative_path=source_file.relative_path,
                    language=source_file.language,
                    chunk_index=idx,
                    chunk_kind="fallback",
                    symbol_id=None,
                    symbol_path=None,
                    start_byte=start_byte,
                    end_byte=end_byte,
                    start_line=start_line,
                    end_line=end_line,
                    text=chunk_text,
                    text_sha256=text_sha,
                    token_count_estimate=token_count,
                )
            )

            idx += 1

            # Advance position with overlap
            # If this is the last chunk (window_end == total_lines), stop
            if window_end == total_lines:
                break
            pos = window_end - overlap_lines
            if pos <= window_start:
                # Ensure we make progress
                pos = window_start + 1

        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count by splitting on whitespace and punctuation.

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        # Simple heuristic: split on whitespace and common punctuation
        tokens = re.split(r"[\s\.,;:\(\)\[\]\{\}<>\"\'`!?@#$%^&*+=|\\~]+", text)
        # Filter out empty strings
        tokens = [t for t in tokens if t]
        return len(tokens)
