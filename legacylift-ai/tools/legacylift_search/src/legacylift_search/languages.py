"""Language detection and language specification registry.

Implements Milestone 3 of the ExecPlan
(`docs/exec-plans/active/semantic-code-search-graph-index.md`).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class LanguageSpec(BaseModel):
    """Specification for a supported programming language.

    Attributes:
        key: Unique identifier (csharp, java, python, javascript, typescript, cobol, sql).
        display_name: Human-readable name for display and logs.
        extensions: File extensions (including dot, e.g., .cs, .py).
        tree_sitter_names: Parser names to try with tree_sitter_language_pack.get_parser().
        supports_tree_sitter: Whether tree-sitter parsing is expected to work reliably.
    """

    key: str
    display_name: str
    extensions: list[str]
    tree_sitter_names: list[str]
    supports_tree_sitter: bool = True


# Language registry covering the seven required languages for Milestone 3.
_LANGUAGE_REGISTRY: dict[str, LanguageSpec] = {
    "csharp": LanguageSpec(
        key="csharp",
        display_name="C#",
        extensions=[".cs"],
        tree_sitter_names=["c_sharp", "c-sharp", "csharp"],
        supports_tree_sitter=True,
    ),
    "java": LanguageSpec(
        key="java",
        display_name="Java",
        extensions=[".java"],
        tree_sitter_names=["java"],
        supports_tree_sitter=True,
    ),
    "python": LanguageSpec(
        key="python",
        display_name="Python",
        extensions=[".py"],
        tree_sitter_names=["python"],
        supports_tree_sitter=True,
    ),
    "javascript": LanguageSpec(
        key="javascript",
        display_name="JavaScript",
        extensions=[".js", ".jsx", ".mjs", ".cjs"],
        tree_sitter_names=["javascript", "jsx"],
        supports_tree_sitter=True,
    ),
    "typescript": LanguageSpec(
        key="typescript",
        display_name="TypeScript",
        extensions=[".ts", ".tsx"],
        tree_sitter_names=["typescript", "tsx"],
        supports_tree_sitter=True,
    ),
    "cobol": LanguageSpec(
        key="cobol",
        display_name="COBOL",
        extensions=[".cbl", ".cob", ".cpy", ".copy", ".pco"],
        tree_sitter_names=["cobol"],
        supports_tree_sitter=False,
    ),
    "sql": LanguageSpec(
        key="sql",
        display_name="SQL",
        extensions=[".sql", ".ddl", ".dml", ".psql", ".pgsql", ".tsql"],
        tree_sitter_names=["sql", "sqlite"],
        supports_tree_sitter=True,
    ),
    # XML is handled by a dedicated ElementTree-based extractor
    # (xml_extractor.py), not tree-sitter — it understands framework
    # semantics (Hibernate class/table mappings, Spring WebFlow states and
    # bean evaluations) rather than generic element structure. Registered so
    # discovery does not skip .xml files (notably Hibernate .hbm.xml mappings
    # and WebFlow flow definitions, which carry real data-lineage and
    # entry-point edges).
    "xml": LanguageSpec(
        key="xml",
        display_name="XML",
        extensions=[".xml"],
        tree_sitter_names=["xml"],
        supports_tree_sitter=False,
    ),
    # --- The 2026-09-08 coverage widening
    # (`active/layer0-extraction-gap-detection.md`). Registered so
    # `detect_language` stops returning None for them, which is the gate after
    # `include_globs`: an allow-list pattern with no registry entry buys
    # nothing, because `discover_source_files` then drops the file for having
    # no language.
    #
    # **All seven are symbol-dead**, and the gate is `extractors.json` profile
    # presence -- NOT grammar availability. `properties` and `css` have
    # tree-sitter grammars that load fine from `tree_sitter_language_pack` and
    # still yield nothing, because `SymbolExtractor.extract` returns an empty
    # `ExtractedFile` before it ever reaches `_get_parser_for`. They
    # contribute retrieval coverage only, as fallback text chunks reachable by
    # FTS5 and vector search. See `SymbolExtractor.has_extractor`.
    #
    # `supports_tree_sitter` below is set for accuracy but is **dead code** --
    # read by nothing in this package outside two assertions in
    # `tests/test_discovery.py`. Do not reach for it as the "expected to have
    # no symbols" discriminator; it answers a different question.
    #
    # Four of these (`jsp`, `css`, `tld`, and `velocity` by degree) also hang
    # Chonkie and are listed in `chunking._CHONKIE_SKIP_LANGUAGES`. A registry
    # entry alone is not sufficient for them.
    "jsp": LanguageSpec(
        key="jsp",
        display_name="Java Server Pages",
        extensions=[".jsp"],
        tree_sitter_names=[],
        supports_tree_sitter=False,
    ),
    "properties": LanguageSpec(
        key="properties",
        display_name="Java Properties",
        extensions=[".properties"],
        tree_sitter_names=["properties"],
        supports_tree_sitter=True,
    ),
    "css": LanguageSpec(
        key="css",
        display_name="CSS",
        extensions=[".css"],
        tree_sitter_names=["css"],
        supports_tree_sitter=True,
    ),
    "velocity": LanguageSpec(
        key="velocity",
        display_name="Velocity Template",
        extensions=[".vm"],
        tree_sitter_names=[],
        supports_tree_sitter=False,
    ),
    "xml_entity": LanguageSpec(
        key="xml_entity",
        display_name="XML Entity Declarations",
        extensions=[".ent"],
        tree_sitter_names=[],
        supports_tree_sitter=False,
    ),
    "tld": LanguageSpec(
        key="tld",
        display_name="JSP Tag Library Descriptor",
        extensions=[".tld"],
        tree_sitter_names=[],
        supports_tree_sitter=False,
    ),
    "xmi": LanguageSpec(
        key="xmi",
        display_name="XMI Model Interchange",
        extensions=[".xmi"],
        tree_sitter_names=[],
        supports_tree_sitter=False,
    ),
}

# Build a reverse mapping from extension to language key for fast detection.
_EXTENSION_TO_KEY: dict[str, str] = {}
for lang_key, spec in _LANGUAGE_REGISTRY.items():
    for ext in spec.extensions:
        # If multiple languages share an extension, last one wins.
        # In this registry, no overlap exists.
        _EXTENSION_TO_KEY[ext.lower()] = lang_key


def detect_language(path: Path) -> LanguageSpec | None:
    """Detect language from file extension.

    Args:
        path: File path to inspect (only extension matters).

    Returns:
        LanguageSpec if extension is recognized, None otherwise.
    """
    suffix = path.suffix.lower()
    if not suffix:
        return None
    lang_key = _EXTENSION_TO_KEY.get(suffix)
    if lang_key is None:
        return None
    return _LANGUAGE_REGISTRY[lang_key]


def get_language(key: str) -> LanguageSpec:
    """Get language spec by key.

    Args:
        key: Language key (csharp, java, python, javascript, typescript, cobol, sql).

    Returns:
        LanguageSpec for the requested language.

    Raises:
        KeyError: If the language key is not in the registry.
    """
    return _LANGUAGE_REGISTRY[key]


__all__ = [
    "LanguageSpec",
    "detect_language",
    "get_language",
]
