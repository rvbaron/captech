"""Process-pool worker for the cold-index extract+chunk phase.

Milestone 19 (chunking C1): the pure ``read → extract → chunk`` work is
CPU-bound and serial-per-file, and dominates a cold index (~63 min on
``repos/ctcm/ctcm-api``). This module runs that work in a
``ProcessPoolExecutor`` so it parallelizes across cores, while the main
process stays the sole SQLite writer.

Process isolation (not threads) is required because the work is CPU-bound
under the GIL. The pool ``initializer`` builds one ``SymbolExtractor`` +
``CodeChunker`` per worker from picklable inputs (``profiles_path`` +
``ChunkingConfig``), so the heavy tree-sitter parsers are constructed once
per worker rather than once per file. Workers return a picklable
``ExtractResult`` and never raise across the pool boundary — read/extract/
chunk failures are captured as structured fields and handled by the writer,
exactly as the original serial loop logged them.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .chunking import CodeChunker
from .config import ChunkingConfig
from .extractors import SymbolExtractor, load_profiles
from .models import CodeChunk, SourceFile, Symbol, SymbolFact, SymbolRef


class ExtractResult(BaseModel):
    """Picklable result of extracting + chunking one source file.

    Mirrors what the original serial loop produced in-memory. Errors are
    structured fields rather than exceptions so the worker never raises
    across the process-pool boundary.
    """

    source_file: SourceFile
    symbols: list[Symbol] = []
    refs: list[SymbolRef] = []
    facts: list[SymbolFact] = []
    chunks: list[CodeChunk] = []
    parse_notes: list[str] = []
    read_error: str | None = None
    extract_error: str | None = None
    chunk_error: str | None = None


# Per-process singletons, built once by ``_init_worker``. Module-level so a
# ``spawn``-started worker rebuilds them after re-importing this module.
_EXTRACTOR: SymbolExtractor | None = None
_CHUNKER: CodeChunker | None = None


def _init_worker(profiles_path: str, chunking_config_json: str) -> None:
    """ProcessPool initializer: build one extractor + chunker per worker.

    Args are picklable primitives (a path string and a JSON dump of the
    ChunkingConfig) so this is ``spawn``-safe on Windows and macOS.
    """
    global _EXTRACTOR, _CHUNKER
    profiles = load_profiles(Path(profiles_path))
    _EXTRACTOR = SymbolExtractor(profiles)
    _CHUNKER = CodeChunker(ChunkingConfig.model_validate_json(chunking_config_json))


def extract_one(source_file: SourceFile) -> ExtractResult:
    """Read, extract, and chunk a single file. Never raises.

    Used both as the process-pool task and (with a locally-built extractor/
    chunker) as the forced-serial in-process oracle path.
    """
    assert _EXTRACTOR is not None and _CHUNKER is not None, (
        "extract_one called before _init_worker"
    )
    return _extract_with(source_file, _EXTRACTOR, _CHUNKER)


def _extract_with(
    source_file: SourceFile,
    extractor: SymbolExtractor,
    chunker: CodeChunker,
) -> ExtractResult:
    """Core read → extract → chunk, parameterized on the extractor/chunker so
    the serial fallback can pass its own instances without touching globals.
    """
    # Read text as UTF-8 with replacement (matches the original loop).
    try:
        raw = source_file.absolute_path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
    except OSError as exc:
        return ExtractResult(source_file=source_file, read_error=str(exc))

    try:
        extracted = extractor.extract(source_file, text)
    except Exception as exc:  # defensive — mirror serial loop
        return ExtractResult(source_file=source_file, extract_error=repr(exc))

    chunks: list[CodeChunk]
    chunk_error: str | None = None
    try:
        chunks = chunker.chunk(source_file, text, extracted)
    except Exception as exc:
        chunks = []
        chunk_error = repr(exc)

    return ExtractResult(
        source_file=source_file,
        symbols=extracted.symbols,
        refs=extracted.refs,
        facts=extracted.facts,
        chunks=chunks,
        parse_notes=list(extracted.parse_errors),
        chunk_error=chunk_error,
    )


__all__ = ["ExtractResult", "extract_one", "_init_worker", "_extract_with"]
