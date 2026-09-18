"""Tree-sitter and fallback symbol/reference extractors.

Milestone 4 (Agent A3) defined the profile loader and the JSON profile
contract. Milestone 5 (Agent B1) adds the SymbolExtractor: tree-sitter
parsing for the languages whose grammars are available, regex-based
fallback extraction for everything else (notably COBOL), and an
``ast_dump`` helper used by the ``dump-ast`` CLI command.

See ``docs/exec-plans/active/semantic-code-search-graph-index.md``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable, Iterable, NamedTuple

from pydantic import BaseModel, Field, field_validator

from .identity import ENTITY_CLASSES
from .languages import LanguageSpec, get_language
from .models import ExtractedFile, Symbol, SymbolFact, SymbolRef, TextRange, SourceFile

logger = logging.getLogger(__name__)

# Milestone 24: the tree-sitter-sql grammar mis-parses the FK clause (it can
# come back as an ``ERROR`` node), so foreign keys are recovered by regex over
# the CREATE TABLE source text rather than the AST. Captures the local
# column(s), the referenced table, and the referenced column(s).
_SQL_FK_RE = re.compile(
    r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+([\w\.\[\]\"]+)\s*\(([^)]+)\)",
    re.IGNORECASE,
)

# Column-level constraint keywords tree-sitter-sql emits as children of a
# ``column_definition`` (as opposed to the data-type node). Used to separate the
# type from the nullability / key flags.
_SQL_COLUMN_CONSTRAINT_KEYWORDS = {
    "keyword_not",
    "keyword_null",
    "keyword_primary",
    "keyword_key",
    "keyword_unique",
}

# Milestone 25: type-node kind sets used by ``_inner_type_name`` to descend a
# field/property/parameter/return type to its innermost payload type name.
_M25_GENERIC_KINDS = ("generic_name", "generic_type")
_M25_TYPE_ARG_KINDS = ("type_argument_list", "type_arguments")
_M25_NAME_LEAF_KINDS = ("identifier", "type_identifier", "property_identifier")
_M25_QUALIFIED_KINDS = (
    "qualified_name",
    "scoped_type_identifier",
    "nested_type_identifier",
    "scoped_identifier",
    "member_expression",
)
# Wrappers that hold a single inner type node (TS ``: Foo`` type_annotation,
# Python ``type`` wrapper, C# ``Foo?`` / ``Foo[]``).
_M25_WRAPPER_KINDS = (
    "type_annotation",
    "type",
    "nullable_type",
    "array_type",
    "optional_type",
)

# Milestone 25: per-language primitive / builtin type names dropped BEFORE
# resolution. Emitting a type-ref for these is pure noise — it either fails to
# resolve (0.30 junk) or falsely resolves to an unrelated same-named user
# symbol. Generics are unwrapped first, so ``Task<ClaimDto>`` still yields
# ``ClaimDto``; only a bare ``Task`` return is dropped.
_PRIMITIVE_TYPES: dict[str, set[str]] = {
    "csharp": {
        "int", "uint", "long", "ulong", "short", "ushort", "byte", "sbyte",
        "nint", "nuint", "bool", "char", "string", "object", "void", "decimal",
        "double", "float", "dynamic", "var", "Task", "ValueTask", "DateTime",
        "DateTimeOffset", "TimeSpan", "Guid",
    },
    "java": {
        "int", "long", "short", "byte", "char", "boolean", "float", "double",
        "void", "String", "Object", "Integer", "Long", "Short", "Byte",
        "Character", "Boolean", "Float", "Double", "Void", "CharSequence",
    },
    "python": {
        "int", "str", "float", "bool", "bytes", "bytearray", "complex",
        "object", "None", "list", "dict", "set", "tuple", "frozenset", "type",
        "Any", "Optional", "Union", "List", "Dict", "Set", "Tuple", "Sequence",
        "Mapping", "Iterable", "Callable",
    },
    "typescript": {
        "string", "number", "boolean", "any", "void", "unknown", "never",
        "null", "undefined", "object", "symbol", "bigint", "this", "Promise",
        "Array",
    },
    "javascript": {
        "string", "number", "boolean", "any", "void", "object", "undefined",
        "null",
    },
}


class FallbackPatterns(BaseModel):
    """Regex patterns for fallback extraction when tree-sitter parsing is unavailable."""

    definitions: list[str]
    calls: list[str]
    # Milestone 22: regex patterns for base-type (inherits/implements) extraction
    # on the regex fallback path (parse failure / no parser only). Defaults to
    # empty so profiles without it stay valid; Pydantic v2 silently drops unknown
    # JSON keys, so this field must exist for the JSON regexes to load at all.
    inheritance: list[str] = Field(default_factory=list)


class ProfileEntry(BaseModel):
    """Configuration for symbol and call extraction for a single language."""

    definition_node_kinds: dict[str, str] = Field(
        description=(
            "Tree-sitter node kind -> entity_class (Milestone 1 Step 2 of "
            "docs/exec-plans/active/reqs-to-data-store.md, NORMATIVE SPEC-3 "
            "§S3.1.2). A dict rather than a list-plus-sibling-map on purpose: "
            "one source cannot drift from itself. Every entry must carry an "
            "explicit, non-derived class in identity.ENTITY_CLASSES; a reader "
            "that wants only the kind list takes .keys()."
        )
    )
    call_node_kinds: list[str] = Field(
        description="Tree-sitter node kinds that represent calls or references"
    )
    import_node_kinds: list[str] = Field(
        description="Tree-sitter node kinds for imports/using directives"
    )
    name_node_kinds: list[str] = Field(
        description="Tree-sitter node kinds that represent names/identifiers"
    )
    container_node_kinds: list[str] = Field(
        description="Tree-sitter node kinds that can contain other symbols"
    )
    inheritance_node_kinds: list[str] = Field(
        default_factory=list,
        description=(
            "Milestone 22: tree-sitter node kinds that, when found as a child of "
            "a definition node, hold its base-type list (C# base_list, Java "
            "superclass/super_interfaces, TS class_heritage, Python argument_list "
            "via the superclasses field). Defaults to [] so existing profiles stay "
            "valid without a schema_version bump."
        ),
    )
    annotation_semantics: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Milestone 23: annotation/attribute/decorator name -> intent map. "
            "Intents: route_get/route_post/route_put/route_delete/route_patch/"
            "route_any (endpoint routing), authz, required, max_length, table, "
            "column, id (attribute-facts), and foreign_key / associates "
            "(relational edges). Unmapped annotations become a generic "
            "has_annotation fact so nothing is silently dropped. Keys are matched "
            "against both the full dotted annotation name and its last segment "
            "(so a Python '@app.get' matches on 'get'). Defaults to {} (a "
            "name->intent MAP, not a list) so existing profiles stay valid "
            "without a schema_version bump."
        ),
    )
    annotation_node_kinds: list[str] = Field(
        default_factory=list,
        description=(
            "Milestone 23: reserved for profiles that need to name the "
            "annotation-bearing node kinds explicitly. The current handler "
            "derives them per-language from the definition node's structure, so "
            "this defaults to [] and is unused today; present for forward "
            "compatibility without a schema_version bump."
        ),
    )
    fallback_patterns: FallbackPatterns = Field(
        description="Regex patterns used when tree-sitter parsing fails"
    )

    @field_validator("definition_node_kinds")
    @classmethod
    def check_entity_classes_closed(cls, v: dict[str, str]) -> dict[str, str]:
        bad = {kind: cls_ for kind, cls_ in v.items() if cls_ not in ENTITY_CLASSES}
        if bad:
            raise ValueError(
                f"definition_node_kinds declares entity_class values outside "
                f"the closed set {sorted(ENTITY_CLASSES)}: {bad}"
            )
        return v


class ExtractorProfiles(BaseModel):
    """Complete set of language profiles for symbol extraction."""

    schema_version: int = Field(
        description="Profile schema version; must be 1 for this implementation"
    )
    profiles: dict[str, ProfileEntry] = Field(
        description="Mapping from language key (e.g., 'csharp', 'python') to its profile"
    )

    @field_validator("schema_version")
    @classmethod
    def check_schema_version(cls, v: int) -> int:
        if v != 1:
            raise ValueError(
                f"Unsupported extractor profile schema_version: {v}. "
                "This implementation requires schema_version=1."
            )
        return v

    @field_validator("profiles")
    @classmethod
    def check_required_languages(cls, v: dict[str, ProfileEntry]) -> dict[str, ProfileEntry]:
        required = {"csharp", "java", "python", "javascript", "typescript", "cobol", "sql"}
        missing = required - set(v.keys())
        if missing:
            raise ValueError(
                f"Missing required language profiles: {', '.join(sorted(missing))}. "
                f"All seven languages must be present in extractors.json."
            )
        return v


def load_profiles(path: Path) -> ExtractorProfiles:
    """Load and validate extractor profiles from JSON.

    Preserved unchanged from Milestone 4 (Agent A3).
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Extractor profile file not found: {path}. "
            "Ensure profiles/extractors.json exists in the package."
        )

    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    return ExtractorProfiles.model_validate(data)


def get_profile(profiles: ExtractorProfiles, language_key: str) -> ProfileEntry | None:
    """Retrieve a profile for a specific language.

    Preserved unchanged from Milestone 4 (Agent A3).
    """
    return profiles.profiles.get(language_key)


# ---------------------------------------------------------------------------
# Tree-sitter parser loading
# ---------------------------------------------------------------------------
#
# Wave A originally specified using ``tree_sitter_language_pack.get_parser``.
# Starting with the Rust-backed pack (observed on 1.8.0), the Parser returned by
# ``get_parser`` is opaque and cannot be used with the standard ``tree_sitter``
# Python bindings to actually parse source code. This is captured in Surprises &
# Discoveries.
#
# To keep extraction working we layer parser loading:
#   1. PRIMARY: pull the grammar via ``tree_sitter_language_pack.get_language(name)``
#      and wrap it in a real ``tree_sitter.Parser`` so ``.parse(bytes)`` works
#      (see ``_load_via_lang_pack``). Verified working on tree-sitter-language-pack
#      1.8.1 + tree-sitter 0.25.2 for csharp/java/python/typescript (2026-07-13).
#   2. FALLBACK: per-language packages (``tree_sitter_python``, ``tree_sitter_c_sharp``,
#      etc.) exposing a stable ``language()`` C-capsule we can wrap. NOTE: none of
#      these are currently installed in the tool venv, so this tier is inert today —
#      it only matters if a future pack version breaks path 1. It is NOT a live
#      safety net right now; keep it, but don't rely on it.
#   3. If neither path produces a parser, the extractor records a parse
#      error and uses regex fallback extraction.
#
# COBOL has no published tree-sitter grammar wheel for Python; it always goes
# through the regex fallback path.


def _load_via_lang_pack(name: str):
    """Best-effort: return a parser whose ``.parse(bytes)`` returns a tree.

    Newer ``tree-sitter`` (>=0.22) ships a ``Parser.parse`` that rejects
    ``bytes`` from the pack's bundled ``get_parser`` binding. We instead pull
    the grammar via ``get_language`` and wrap it in a real ``tree_sitter.Parser``
    so ``.parse(bytes)`` keeps working.
    """
    try:
        import tree_sitter  # type: ignore
        from tree_sitter_language_pack import get_language  # type: ignore
    except Exception:
        return None
    try:
        lang = get_language(name)
        return tree_sitter.Parser(lang)
    except Exception:
        return None


def _load_via_individual(language_key: str):
    """Return a tree_sitter.Parser for ``language_key`` using a per-language package."""
    try:
        import tree_sitter
    except Exception:
        return None

    loaders: dict[str, Callable[[], Any]] = {
        "python": lambda: __import__("tree_sitter_python").language(),
        "javascript": lambda: __import__("tree_sitter_javascript").language(),
        "typescript": lambda: __import__(
            "tree_sitter_typescript"
        ).language_typescript(),
        "java": lambda: __import__("tree_sitter_java").language(),
        "csharp": lambda: __import__("tree_sitter_c_sharp").language(),
        "sql": lambda: __import__("tree_sitter_sql").language(),
    }
    loader = loaders.get(language_key)
    if loader is None:
        return None
    try:
        capsule = loader()
        lang = tree_sitter.Language(capsule)
        return tree_sitter.Parser(lang)
    except Exception:
        return None


def _get_parser_for(language: LanguageSpec) -> tuple[Any, str | None]:
    """Return (parser_or_none, parser_source_name).

    ``parser_source_name`` is the tree-sitter grammar name that succeeded, or
    None if no parser could be loaded.
    """
    # 1. Try tree-sitter-language-pack against each candidate name.
    for name in language.tree_sitter_names:
        p = _load_via_lang_pack(name)
        if p is not None:
            return p, name
    # 2. Fall back to per-language packages.
    p = _load_via_individual(language.key)
    if p is not None:
        return p, language.key
    return None, None


# ---------------------------------------------------------------------------
# SymbolExtractor
# ---------------------------------------------------------------------------


def _decode(raw: bytes | None) -> str:
    if raw is None:
        return ""
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _node_text(node, source_bytes: bytes) -> str:
    try:
        return source_bytes[node.start_byte:node.end_byte].decode(
            "utf-8", errors="replace"
        )
    except Exception:
        return ""


def _unquote(s: str) -> str:
    """Strip a single pair of surrounding quotes (", ', or `) from a string
    literal's source text. Milestone 23 annotation-argument helper."""
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'`" and s[-1] == s[0]:
        return s[1:-1]
    return s


def _normalize_sql_identifier(raw: str) -> str:
    """Normalize a SQL object identifier to the bare, unqualified name used for
    graph resolution.

    Strips quoting/bracketing and drops any schema qualifier so both sides of
    the exact-name match in ``GraphBuilder._resolve_callee`` agree — e.g. the
    ``create_table`` symbol name and the ``foreign_key`` ref name must both be
    ``Customer``, not ``[dbo].[Customer]``.

    tree-sitter-sql does not understand T-SQL bracket-quoted identifiers: it
    surfaces ``[dbo].[Customer]`` as a mangled ``object_reference`` whose text is
    ``dbo].[Customer`` (the outer brackets land in sibling ``ERROR`` nodes). The
    ``split(".")[-1]`` + bracket strip below de-mangles that form as well as a
    clean ``dbo.Customer`` / ``"dbo"."Customer"``. The raw DDL is retained on the
    Symbol's ``signature`` (and each fact's ``evidence``) as an audit trail.
    """
    s = _unquote(raw.strip())
    # Last dotted segment = the object name (drop schema/db qualifier).
    s = s.split(".")[-1]
    # Strip any residual bracket / quote characters left by the mangled parse.
    return s.strip('[]"`').strip()


# T-SQL temp markers (``#local`` / ``##global`` / ``@table-variable``) that may
# appear immediately after the ``TABLE`` keyword, plus the ANSI/Postgres/SQLite
# ``TEMP``/``TEMPORARY`` modifier keyword nodes. Used to keep transient objects
# out of the durable-table inventory (Milestone: sql-extractor-temp-cte-fk).
_SQL_TEMP_NAME_RE = re.compile(r"\bTABLE\b\s*\[?\s*(#{1,2}|@)", re.IGNORECASE)
_SQL_TEMP_KEYWORDS = {"keyword_temp", "keyword_temporary"}


def _sql_is_temp_table(node, source_bytes: bytes) -> bool:
    """True if a ``create_table`` node defines a transient/temp table rather than
    a durable schema table.

    Detects the ``TEMP``/``TEMPORARY`` modifier (its own keyword child) and the
    T-SQL ``#``/``##``/``@`` name prefixes. The prefix check runs against the raw
    node text because name extraction drops the leading ``#`` (it lands in an
    ``ERROR`` node), so the prefix is not recoverable from the extracted name.
    """
    for c in node.children:
        if c.type in _SQL_TEMP_KEYWORDS:
            return True
    return bool(_SQL_TEMP_NAME_RE.search(_node_text(node, source_bytes)))


def _sql_temp_marker(node, source_bytes: bytes) -> str:
    """The ``#`` / ``##`` / ``@`` marker a temp table's name was declared with,
    or "" for a ``TEMP``/``TEMPORARY`` table (whose name carries no marker).

    The marker has to be put back on the extracted name: the grammar drops it
    into an ERROR node, so ``CREATE TABLE #Orders`` would otherwise yield the
    name ``Orders`` and collide with the DURABLE ``Orders`` table in the graph's
    name index — and staging tables named after their target table are the norm
    in T-SQL. Keeping the marker also matches what the regex recovery path emits.
    """
    m = _SQL_TEMP_NAME_RE.search(_node_text(node, source_bytes))
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Regex CREATE TABLE recovery (ExecPlan sql-extractor-temp-cte-fk, Milestone 4)
# ---------------------------------------------------------------------------
# tree-sitter-sql does not understand T-SQL [bracket] quoting; it recovers via
# ERROR nodes, and the resulting damage is not merely sparse data (all reproduced
# 2026-07-30):
#   * a bracketed CREATE TABLE containing NOT NULL SWALLOWS the following
#     statement into its own ``create_table`` node: the swallowed table gets no
#     symbol, its columns are attributed to the preceding table (plus junk like a
#     ``has_column`` named ``GO``), and its FK resolves against that table as a
#     confident (0.85) SELF edge — a wrong fact, not a missing one;
#   * a bracketed column whose name collides with a grammar keyword VANISHES
#     (``[Name] NVARCHAR(100)`` -> ``keyword_name`` inside ERROR, no
#     ``column_definition``), and Name/Date/Value/Status/Type/Key are everywhere;
#   * the closing ``]`` lands between name and type, so types came back as ``']'``.
# So CREATE TABLE statements are segmented by regex — the same
# regex-supplements-the-grammar approach as ``_SQL_FK_RE`` — and the grammar keeps
# a table only when it segmented it 1:1 AND the statement has no brackets.
# The same segmenter powers the no-grammar fallback path, where the profile's
# generic definition regex yields a bare ``fallback_definition`` and no columns.

# A single SQL identifier: [bracketed], "quoted", `backticked`, or bare with an
# optional T-SQL temp marker (#local / ##global / @table-variable).
_SQL_IDENT = r"(?:\[[^\]\n]+\]|\"[^\"\n]+\"|`[^`\n]+`|[#@]{0,2}[A-Za-z_][\w$]*)"
_SQL_QUALIFIED_IDENT = rf"{_SQL_IDENT}(?:\s*\.\s*{_SQL_IDENT})*"

_SQL_CREATE_TABLE_RE = re.compile(
    rf"\bCREATE\s+(?:(?:GLOBAL|LOCAL)\s+)?(?:(TEMP|TEMPORARY)\s+)?TABLE\s+"
    rf"(?:IF\s+NOT\s+EXISTS\s+)?({_SQL_QUALIFIED_IDENT})\s*\(",
    re.IGNORECASE,
)

# ``ALTER TABLE <child> [WITH [NO]CHECK] ADD [CONSTRAINT <name>] FOREIGN KEY
# (cols) REFERENCES <parent> (cols)`` — the out-of-line FK form.
#
# This is the DOMINANT way real schemas declare foreign keys: an SSMS
# script-folder export puts the columns in ``CREATE TABLE`` and every constraint
# in a separate trailing ``ALTER TABLE`` batch. ``_SQL_FK_RE`` only ever runs
# over a CREATE TABLE node/segment body, so out-of-line constraints were invisible
# and such a schema produced ZERO foreign_key edges (found re-indexing the NNG DB
# unit, where all 81 FKs take this form). ``child`` owns the FK, ``parent`` is
# referenced, and ``fk`` spans the clause itself so the emitted ref can be
# anchored exactly where the in-table scans anchor theirs.
_SQL_ALTER_TABLE_FK_RE = re.compile(
    rf"\bALTER\s+TABLE\s+(?P<child>{_SQL_QUALIFIED_IDENT})\s+"
    rf"(?:WITH\s+(?:NO)?CHECK\s+)?"
    rf"ADD\s+(?:CONSTRAINT\s+{_SQL_QUALIFIED_IDENT}\s+)?"
    rf"(?P<fk>FOREIGN\s+KEY\s*\([^)]+\)\s*"
    rf"REFERENCES\s+(?P<parent>{_SQL_QUALIFIED_IDENT})\s*\([^)]+\))",
    re.IGNORECASE,
)

# A table-element entry that is a table-level constraint, not a column.
_SQL_TABLE_CONSTRAINT_RE = re.compile(
    r"^\s*(?:CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|KEY|INDEX|EXCLUDE|PERIOD|WITH)\b",
    re.IGNORECASE,
)
# ``<name> <type>[(args)]`` at the head of a column entry. The optional trailing
# ``]`` on the name tolerates tree-sitter-sql's mangled column text
# (``[Qty] DECIMAL(9,3)`` reaches us as ``Qty] DECIMAL(9,3)``); the name is
# normalized afterwards, which strips it.
#
# The TYPE is a full (possibly bracket-quoted, possibly schema-qualified)
# identifier, not a bare word. SSMS scripts every type: a script-folder export
# reads ``[PLACE_FIPS] [varchar] (5) NOT NULL``, and a user-defined type reads
# ``[phone] [dbo].[PhoneNumber]``. A bare ``[A-Za-z_][\w]*`` type pattern fails
# to match those entries at all, which silently dropped EVERY column of EVERY
# table in a real SSMS-exported schema (found re-indexing the NNG DB unit).
_SQL_COLUMN_HEAD_RE = re.compile(
    rf"^\s*({_SQL_IDENT}\]?)\s+({_SQL_QUALIFIED_IDENT})\s*(\([^)]*\))?",
    re.IGNORECASE,
)
# Second word of a two-word data type (DOUBLE PRECISION, CHARACTER VARYING).
_SQL_TYPE_SECOND_WORD_RE = re.compile(r"^\s*(PRECISION|VARYING)\b", re.IGNORECASE)


class _SqlTableSegment(NamedTuple):
    """One ``CREATE TABLE`` statement located by regex over the raw text.

    Offsets are carried in BOTH units on purpose: ``start_byte``/``end_byte``
    compare against tree-sitter node ranges (UTF-8 bytes) during reconciliation,
    while ``*_char`` index back into the Python ``str`` for slicing.
    """

    raw_name: str
    name: str
    is_temp: bool
    start_char: int
    end_char: int
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    header: str
    body: str
    body_char: int


def _sql_mask_noncode(text: str) -> str:
    """Blank out comment and string-literal spans, preserving length and newlines.

    Segmentation and paren balancing run over this mask so a commented-out or
    dynamic-SQL (``EXEC('CREATE TABLE ...')``) statement never becomes a phantom
    table, and so parens/quotes inside comments cannot desynchronize the scan.
    Because every replacement is one space per character and newlines survive,
    offsets and line numbers are identical to the original text.
    """
    # Fast path: nothing to mask. Worth the check because this runs per SQL file
    # and again per table body / column entry, all in a Python-level char loop.
    if "--" not in text and "/*" not in text and "'" not in text:
        return text
    out = list(text)
    i, n = 0, len(text)

    def blank(start: int, stop: int) -> None:
        for k in range(start, min(stop, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            j = text.find("\n", i)
            j = n if j == -1 else j
            blank(i, j)
            i = j
        elif ch == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            blank(i, j)
            i = j
        elif ch == "'":
            j = i + 1
            while j < n:
                if text[j] == "'":
                    # '' is an escaped quote inside the literal, not the end.
                    if j + 1 < n and text[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            blank(i, j)
            i = j
        else:
            i += 1
    return "".join(out)


def _sql_match_paren(masked: str, open_index: int) -> int | None:
    """Index of the ``)`` closing the ``(`` at ``open_index``, or None if unbalanced."""
    depth = 0
    for i in range(open_index, len(masked)):
        c = masked[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _char_to_byte_offsets(text: str, char_offsets: Iterable[int]) -> dict[int, int]:
    """Map char offsets to UTF-8 byte offsets in a single left-to-right pass.

    tree-sitter ranges are byte-based while ``re`` offsets are char-based; on a
    file with any non-ASCII byte (a comment with an accent is enough) comparing
    the two directly would misalign the reconciliation. One pass keeps this O(n)
    instead of O(n * segments).
    """
    if text.isascii():  # one byte per char — the common case
        return {max(0, min(o, len(text))): max(0, min(o, len(text)))
                for o in char_offsets}
    result: dict[int, int] = {}
    prev_char = 0
    prev_byte = 0
    for off in sorted({max(0, min(o, len(text))) for o in char_offsets}):
        prev_byte += len(text[prev_char:off].encode("utf-8"))
        prev_char = off
        result[off] = prev_byte
    return result


def _sql_table_segments(text: str) -> list[_SqlTableSegment]:
    """Locate every ``CREATE TABLE`` statement in ``text`` by regex.

    Returns one segment per statement whose parenthesized element list is
    balanced; an unbalanced (truncated) statement is skipped rather than guessed
    at. Temp status comes from the ``TEMP``/``TEMPORARY`` modifier or a
    ``#``/``##``/``@`` name prefix — the prefix is KEPT in ``name`` so a
    ``#Orders`` staging table cannot collide with the durable ``Orders`` in the
    graph's name index.
    """
    masked = _sql_mask_noncode(text)
    raw: list[tuple] = []
    for m in _SQL_CREATE_TABLE_RE.finditer(masked):
        open_paren = m.end() - 1
        close = _sql_match_paren(masked, open_paren)
        if close is None:
            continue
        raw_name = text[m.start(2):m.end(2)]
        name = _normalize_sql_identifier(raw_name)
        if not name:
            continue
        # Temp marker: from the TEMP/TEMPORARY modifier, or a #/##/@ prefix on
        # either the raw name (``#Staging``) or the de-bracketed one
        # (``[#Staging]`` — valid T-SQL, and the brackets hide the marker).
        is_temp = (
            bool(m.group(1))
            or raw_name.strip()[:1] in ("#", "@")
            or name[:1] in ("#", "@")
        )
        raw.append((m.start(), close + 1, raw_name, name, is_temp, open_paren))

    if not raw:
        return []

    byte_of = _char_to_byte_offsets(
        text, [o for seg in raw for o in (seg[0], seg[1])]
    )
    segments: list[_SqlTableSegment] = []
    for start, end, raw_name, name, is_temp, open_paren in raw:
        segments.append(
            _SqlTableSegment(
                raw_name=raw_name,
                name=name,
                is_temp=is_temp,
                start_char=start,
                end_char=end,
                start_byte=byte_of[start],
                end_byte=byte_of[end],
                start_line=text.count("\n", 0, start) + 1,
                end_line=text.count("\n", 0, end) + 1,
                header=text[start:open_paren + 1],
                body=text[open_paren + 1:end - 1],
                body_char=open_paren + 1,
            )
        )
    return segments


def _sql_split_top_level(body: str) -> list[tuple[str, int]]:
    """Split a table's element list on top-level commas.

    Returns ``(entry_text, offset_into_body)`` pairs. Nesting is tracked on the
    masked copy so ``DECIMAL(18,2)`` and commas inside comments/strings do not
    split an entry.
    """
    masked = _sql_mask_noncode(body)
    entries: list[tuple[str, int]] = []
    depth = 0
    start = 0
    for i, c in enumerate(masked):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "," and depth == 0:
            entries.append((body[start:i], start))
            start = i + 1
    entries.append((body[start:], start))
    return [(e, off) for e, off in entries if e.strip()]


def _sql_columns_from_body(body: str) -> list[tuple[str, dict, int]]:
    """Parse ``(name, attributes, offset_into_body)`` for each column entry.

    Mirrors the attribute shape the tree-sitter column path emits
    (``data_type`` / ``nullable`` / ``primary_key`` / ``unique``) so a recovered
    table's ``has_column`` facts are interchangeable with a cleanly-parsed one's.
    Table-level constraint entries are skipped — they are not columns.
    """
    out: list[tuple[str, dict, int]] = []
    for entry, offset in _sql_split_top_level(body):
        if _SQL_TABLE_CONSTRAINT_RE.match(entry):
            continue
        head = _SQL_COLUMN_HEAD_RE.match(entry)
        if not head:
            continue
        col_name = _normalize_sql_identifier(head.group(1))
        if not col_name:
            continue
        # Normalize the type the same way names are, so a scripted
        # ``[varchar] (5)`` reads ``varchar(5)`` and a UDT ``[dbo].[PhoneNumber]``
        # reads ``PhoneNumber`` — matching what the AST path reports for the same
        # column. Fall back to the raw text if normalization empties it.
        data_type = _normalize_sql_identifier(head.group(2)) or head.group(2)
        args = head.group(3)
        rest = entry[head.end():]
        second = _SQL_TYPE_SECOND_WORD_RE.match(rest)
        if second and not args:
            data_type = f"{data_type} {second.group(1)}"
            rest = rest[second.end():]
        if args:
            data_type = f"{data_type}{args}"
        flags = _sql_mask_noncode(entry).upper()
        out.append(
            (
                col_name,
                {
                    "data_type": data_type,
                    "nullable": not re.search(r"\bNOT\s+NULL\b", flags),
                    "primary_key": bool(re.search(r"\bPRIMARY\s+KEY\b", flags)),
                    "unique": bool(re.search(r"\bUNIQUE\b", flags)),
                },
                offset,
            )
        )
    return out


def _base_type_name(node, source_bytes: bytes) -> str:
    """Milestone 22: unwrap a base-type node to its plain, unqualified name.

    Strips generic arguments (``IRepository<Claim>`` -> ``IRepository``) and
    qualifiers (``System.IDisposable`` -> ``IDisposable``) so the name matches
    the plain-name resolution index used by ``GraphBuilder``. Returns "" for
    node kinds that are not base-type references (punctuation, keywords, C#
    ``predefined_type`` from an ``enum Foo : byte`` underlying-type clause) —
    that empty return is the intended filter, not an oversight.
    """
    t = node.type
    if t in ("identifier", "type_identifier"):
        return _node_text(node, source_bytes).strip()
    # C# generic_name / Java generic_type: take the inner name, drop the
    # type_argument_list / type_arguments.
    if t in ("generic_name", "generic_type"):
        for c in node.children:
            if c.type in ("identifier", "type_identifier"):
                return _node_text(c, source_bytes).strip()
        return ""
    # Qualified / dotted bases: take the last segment.
    if t in (
        "qualified_name",
        "attribute",
        "member_expression",
        "scoped_type_identifier",
        "nested_type_identifier",
        "scoped_identifier",
    ):
        segs = [
            c for c in node.children
            if c.type in ("identifier", "type_identifier", "property_identifier")
        ]
        if segs:
            return _node_text(segs[-1], source_bytes).strip()
        return ""
    # C# positional record base: `record ClaimDto(int Id) : BaseDto(Id)` wraps
    # its base in primary_constructor_base_type; descend to the inner type node.
    if t == "primary_constructor_base_type":
        for c in node.children:
            name = _base_type_name(c, source_bytes)
            if name:
                return name
        return ""
    return ""


def _inner_type_name(node, source_bytes: bytes) -> str:
    """Milestone 25: return the INNERMOST payload type name of a type node.

    Distinct from ``_base_type_name`` (Milestone 22), which returns the OUTER
    generic name (``ActionResult<ClaimDto>`` -> ``ActionResult``). Here we
    descend one level into the generic's ``type_argument_list`` /
    ``type_arguments`` and take the innermost type argument
    (``ActionResult<ClaimDto>`` -> ``ClaimDto``, ``List<Claim>`` -> ``Claim``,
    ``Task<ActionResult<ClaimDto>>`` -> ``ClaimDto``), recursing through nested
    generics, and fall back to the outer/base name when there is no type
    argument. Unwraps language type wrappers (TS ``type_annotation``, Python
    ``type``, C# nullable / array) on the way down. Returns "" when no name can
    be recovered.
    """
    cur = node
    for _ in range(24):  # bounded descent, defensive against grammar quirks
        if cur is None:
            return ""
        t = cur.type
        if t in _M25_NAME_LEAF_KINDS or t == "predefined_type":
            return _node_text(cur, source_bytes).strip()
        if t in _M25_GENERIC_KINDS:
            arglist = None
            for c in cur.children:
                if c.type in _M25_TYPE_ARG_KINDS:
                    arglist = c
                    break
            if arglist is not None:
                arg = None
                for c in arglist.children:
                    if c.is_named:
                        arg = c
                        break
                if arg is not None:
                    cur = arg
                    continue
            # No type argument -> outer base name.
            for c in cur.children:
                if c.type in _M25_NAME_LEAF_KINDS:
                    return _node_text(c, source_bytes).strip()
            return _node_text(cur, source_bytes).split("<", 1)[0].strip()
        if t in _M25_QUALIFIED_KINDS:
            segs = [c for c in cur.children if c.type in _M25_NAME_LEAF_KINDS]
            if segs:
                return _node_text(segs[-1], source_bytes).strip()
            return _node_text(cur, source_bytes).rsplit(".", 1)[-1].strip()
        if t in _M25_WRAPPER_KINDS:
            inner = None
            for c in cur.children:
                if c.is_named:
                    inner = c
                    break
            if inner is None:
                return (
                    _node_text(cur, source_bytes)
                    .strip(": []?")
                    .split("<", 1)[0]
                    .strip()
                )
            cur = inner
            continue
        if t == "subscript":
            # Python generics: ``List[Claim]`` -> descend into the subscript arg.
            sub = None
            try:
                sub = cur.child_by_field_name("subscript")
            except Exception:
                sub = None
            if sub is not None:
                cur = sub
                continue
            return _node_text(cur, source_bytes).split("[", 1)[0].strip()
        # Unknown node: descend to the first name/generic child if present.
        nxt = None
        for c in cur.children:
            if c.type in _M25_NAME_LEAF_KINDS or c.type in _M25_GENERIC_KINDS:
                nxt = c
                break
        if nxt is None:
            return (
                _node_text(cur, source_bytes)
                .split("<", 1)[0]
                .split("[", 1)[0]
                .strip()
            )
        cur = nxt
    return ""


def _byte_offset_table(text: str) -> list[int] | None:
    r"""A dense char-index -> UTF-8 byte-offset table, or `None` for ASCII.

    The sibling `_char_to_byte_offsets` maps a KNOWN set of offsets in one
    pass, which is the right shape for the SQL segment reconciliation that
    collects its offsets before converting any. The regex fallback discovers
    its offsets while iterating and queries them out of order across three
    independent loops, so it needs O(1) random access instead.

    `CR-08`. `re` matches a `str`, so `m.start()` / `m.end()` are CHARACTER
    indices, while `TextRange.start_byte` / `end_byte` are contracted to be
    byte offsets into the extractors' byte space (`store.SourceText`). The
    fallback used to store the character index in the byte field. That was
    inert while the bounds only drove chunking and display, and became
    consequential in Milestone 1 Step 2: `store.symbol_body_text` slices
    `SourceText.byte_space` with them, and because a character index is
    always <= the byte index its bounds guard still passes -- so a file with
    any non-ASCII before a definition yields a shifted body and a
    stable-but-WRONG `content_hash`, with nothing raising. Measured on the
    three real corpora the current damage is zero (394 `fallback_definition`
    symbols, none preceded by non-ASCII), which is a property of those
    repositories rather than of this code.

    Args:
        text: The decoded source text the regexes are matched against.

    Returns:
        A list of `len(text) + 1` byte offsets, so an end-of-match index is
        addressable; or `None` when `text` is ASCII and the two coincide.
    """
    if text.isascii():
        return None
    offsets = [0] * (len(text) + 1)
    total = 0
    for i, ch in enumerate(text):
        offsets[i] = total
        total += len(ch.encode("utf-8"))
    offsets[len(text)] = total
    return offsets


def _line_text(text: str, line_number_1based: int) -> str:
    if line_number_1based < 1:
        return ""
    lines = text.splitlines()
    idx = line_number_1based - 1
    if 0 <= idx < len(lines):
        return lines[idx]
    return ""


class SymbolExtractor:
    """Extract symbols and references from a single source file.

    Uses tree-sitter where available, falling back to regex-based extraction
    when no parser can be loaded for the language.
    """

    def __init__(self, profiles: ExtractorProfiles) -> None:
        self.profiles = profiles
        # Cache parsers across files for speed.
        self._parser_cache: dict[str, tuple[Any, str | None]] = {}

    # -- Parser cache -------------------------------------------------------

    def _parser_for_language(self, language: LanguageSpec) -> tuple[Any, str | None]:
        cached = self._parser_cache.get(language.key)
        if cached is not None:
            return cached
        parser, name = _get_parser_for(language)
        self._parser_cache[language.key] = (parser, name)
        return parser, name

    # -- Public API ---------------------------------------------------------

    def has_extractor(self, language_key: str) -> bool:
        """Can this language produce symbols at all?

        The discriminator between "the extractor found nothing, which is
        suspicious" and "no extractor exists for this language, which is
        expected" -- a distinction the gap detector's M3 check two has to draw
        and could not before the 2026-09-08 coverage widening, when the
        registry held only languages that all had extractors.

        Note the two clauses. Profile presence in `extractors.json` is the
        main gate, but `xml` is dispatched to the framework-aware
        `xml_extractor` *above* the profile lookup and has no profile of its
        own -- so a check written as profile-presence alone calls `.xml`
        symbol-dead, and it is the one widened language that is not. On NNG
        all 21 symbols the widening added came from `.xml`.

        **Not** `LanguageSpec.supports_tree_sitter`, which is dead code: it is
        declared, set on the eight pre-existing entries, and read by nothing
        in the package outside two test assertions. It also answers a
        different question -- `.css` and `.properties` have grammars that load
        fine and still yield no symbols, because `extract` never reaches the
        parser without a profile.
        """
        return language_key == "xml" or language_key in self.profiles.profiles

    def extract(self, source_file: SourceFile, text: str) -> ExtractedFile:
        language_key = source_file.language

        # XML is handled by a dedicated framework-aware extractor (Hibernate
        # mappings, Spring WebFlow, Spring beans), not the tree-sitter/regex
        # profile machinery. It has no entry in extractors.json.
        if language_key == "xml":
            from .xml_extractor import extract_xml

            stem = Path(source_file.relative_path).name
            # Strip compound extensions (e.g. Foo.hbm.xml -> Foo).
            for _ in range(2):
                stem = stem.rsplit(".", 1)[0] if "." in stem else stem
            return extract_xml(
                language_key, source_file.relative_path, text, stem
            )

        profile = self.profiles.profiles.get(language_key)
        if profile is None:
            return ExtractedFile(
                symbols=[],
                refs=[],
                parse_errors=[f"no extractor profile for language '{language_key}'"],
            )

        try:
            language = get_language(language_key)
        except KeyError:
            return ExtractedFile(
                symbols=[],
                refs=[],
                parse_errors=[f"unknown language key '{language_key}'"],
            )

        parser, _name = self._parser_for_language(language)

        if parser is None:
            return self._extract_fallback(
                source_file,
                profile,
                text,
                reason="no tree-sitter parser available; using regex fallback",
            )

        try:
            source_bytes = text.encode("utf-8", errors="replace")
            tree = parser.parse(source_bytes)
        except Exception as exc:  # pragma: no cover — defensive
            return self._extract_fallback(
                source_file,
                profile,
                text,
                reason=f"tree-sitter parse failed ({exc!r}); using regex fallback",
            )

        symbols, refs, facts = self._walk_tree(
            tree.root_node, source_bytes, source_file, profile, text
        )

        # Milestone 4 (sql-extractor-temp-cte-fk): tree-sitter-sql cannot segment
        # bracketed multi-table DDL, so regex segmentation decides the table
        # inventory and the grammar keeps only the tables it parsed 1:1.
        if language_key == "sql" and symbols:
            symbols, refs, facts = self._reconcile_sql_tables(
                source_file, text, symbols, refs, facts
            )
            # Out-of-line ``ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY``.
            # Runs after reconciliation so the altered table's symbol is the final
            # (possibly recovered) one. A clause the grammar also happened to
            # swallow into a create_table node yields the same ref id, so the
            # correctly-attributed one replaces it rather than double-counting.
            alter_fks = self._sql_alter_table_fk_refs(source_file, text, symbols)
            if alter_fks:
                shadowed = {r.id for r in alter_fks}
                refs = [r for r in refs if r.id not in shadowed] + alter_fks

        # If tree-sitter produced nothing at all, fall back to regex.
        parse_errors: list[str] = []
        if not symbols and not refs and text.strip():
            return self._extract_fallback(
                source_file,
                profile,
                text,
                reason="tree-sitter produced no matches; using regex fallback",
            )

        # If tree-sitter found references but no definitions (common for SQL
        # where the grammar's node names diverge from our profile), supplement
        # with regex definitions only — keep the tree-sitter refs.
        if not symbols and text.strip():
            fb = self._extract_fallback(
                source_file,
                profile,
                text,
                reason=(
                    "tree-sitter produced no definition matches; "
                    "supplementing with regex fallback definitions"
                ),
            )
            symbols = fb.symbols
            parse_errors = fb.parse_errors
            # The SQL fallback recovers columns/FKs for the tables it segments,
            # so those facts must travel with its symbols — dropping them here
            # would silently lose the has_column inventory on this path. Only
            # the FK refs are merged in: this branch deliberately keeps the
            # tree-sitter refs and does NOT want the generic fallback_call ones.
            facts = facts + fb.facts
            refs = self._dedupe_by_id(
                refs + [r for r in fb.refs if r.kind == "foreign_key"]
            )
        return ExtractedFile(
            symbols=symbols, refs=refs, parse_errors=parse_errors, facts=facts
        )

    def dump_ast(
        self, path: Path, language_key: str | None, max_depth: int
    ) -> str:
        """Pretty-print node kinds and ranges for a single source file."""
        text = path.read_text(encoding="utf-8", errors="replace")
        if language_key is None:
            from .languages import detect_language

            spec = detect_language(path)
            if spec is None:
                return f"(no language detected for {path})"
            language = spec
        else:
            language = get_language(language_key)

        parser, parser_name = self._parser_for_language(language)
        if parser is None:
            return (
                f"(no tree-sitter parser available for language "
                f"'{language.key}' on this platform)"
            )

        source_bytes = text.encode("utf-8", errors="replace")
        try:
            tree = parser.parse(source_bytes)
        except Exception as exc:
            return f"(parse failed: {exc!r})"

        profile = self.profiles.profiles.get(language.key)
        name_kinds = set(profile.name_node_kinds) if profile else set()

        out: list[str] = [f"# language={language.key} parser={parser_name}"]
        self._dump_node(
            tree.root_node, source_bytes, depth=0, max_depth=max_depth,
            out=out, name_kinds=name_kinds,
        )
        return "\n".join(out)

    # -- Tree walking -------------------------------------------------------

    def _walk_tree(
        self,
        root,
        source_bytes: bytes,
        source_file: SourceFile,
        profile: ProfileEntry,
        text: str,
    ) -> tuple[list[Symbol], list[SymbolRef], list[SymbolFact]]:
        def_kinds = set(profile.definition_node_kinds)
        call_kinds = set(profile.call_node_kinds)
        container_kinds = set(profile.container_node_kinds)
        name_kinds = set(profile.name_node_kinds)

        # Facts are a first-class output of the tree-sitter walk alongside
        # symbols/refs (Milestones 23-25). Keeping a shared accumulator here
        # means every M23-25 handler emits through the same path — the one that
        # actually survives the M19 process-pool boundary via ``ExtractedFile``.
        symbols: list[Symbol] = []
        refs: list[SymbolRef] = []
        facts: list[SymbolFact] = []

        # Track containers by depth-first descent so we can build qualified
        # names. ``container_stack`` holds the names of currently-enclosing
        # containers in source order.
        def visit(node, container_stack: list[str], enclosing_id: str | None) -> None:
            current_id = enclosing_id
            extended_stack = container_stack
            if node.type in def_kinds:
                name = self._extract_name(node, source_bytes, name_kinds)
                # SQL identifiers are normalized to their bare name so a
                # bracketed/qualified definition (``[dbo].[Customer]``, which
                # tree-sitter-sql mangles to ``dbo].[Customer``) matches the
                # already-normalized ``foreign_key`` / ``uses_table`` ref names in
                # graph resolution. The raw DDL survives on ``signature``.
                if name and source_file.language == "sql":
                    name = _normalize_sql_identifier(name)
                # Transient SQL objects (temp tables / table variables) get a
                # distinct kind so they drop out of the durable-table inventory
                # (consumers filter ``kind == "create_table"``) while remaining
                # present and identifiable. The name keeps its ``#``/``##``/``@``
                # marker — restored here because the grammar drops it — so a
                # ``#Orders`` staging table cannot collide with the durable
                # ``Orders`` in the graph's name index.
                kind = node.type
                # entity_class comes from the profile dict, keyed on the
                # *original* node.type — never re-derived from `kind`, which
                # for a SQL temp table has already been remapped below. The
                # profile only knows "create_table", and a temp table is a
                # `table` like any other (§S3.1.2), so the pre-remap lookup is
                # exactly right, not a workaround.
                entity_class = profile.definition_node_kinds[node.type]
                if (
                    source_file.language == "sql"
                    and node.type == "create_table"
                    and _sql_is_temp_table(node, source_bytes)
                ):
                    kind = "create_temp_table"
                    marker = _sql_temp_marker(node, source_bytes)
                    if marker and name:
                        name = f"{marker}{name.lstrip('#@')}"
                if name:
                    qualified = (
                        ".".join(container_stack + [name]) if container_stack else name
                    )
                    rng = self._range_of(node)
                    sym_id = (
                        f"{source_file.language}:{source_file.relative_path}:"
                        f"{qualified}:{rng.start_line}"
                    )
                    container = ".".join(container_stack) if container_stack else None
                    signature = self._first_line(_node_text(node, source_bytes))
                    sym = Symbol(
                        id=sym_id,
                        language=source_file.language,
                        name=name,
                        qualified_name=qualified,
                        kind=kind,
                        range=rng,
                        container=container,
                        signature=signature,
                        entity_class=entity_class,
                    )
                    symbols.append(sym)
                    if node.type in container_kinds:
                        extended_stack = container_stack + [name]
                    current_id = sym_id
                    # Milestone 22: emit inherits/implements refs for this
                    # definition's base types. Anchored on the definition node
                    # (not a generic node-kind sweep) so Python's argument_list
                    # can be reached safely via the superclasses field.
                    refs.extend(
                        self._extract_inheritance_refs(
                            node, source_bytes, source_file, profile, text,
                            current_id,
                        )
                    )
                    # Milestone 23: emit annotation/attribute/decorator facts
                    # (and relational refs) for this definition. Anchored on the
                    # same definition node so the Symbol just built (``sym``)
                    # provides subject_symbol_id for free.
                    ann_facts, ann_refs = self._extract_annotation_facts(
                        node, source_bytes, source_file, profile, text, sym,
                    )
                    facts.extend(ann_facts)
                    refs.extend(ann_refs)
                    # Milestone 24: SQL CREATE TABLE -> has_column facts (columns
                    # via tree-sitter) plus foreign_key refs (via regex, because
                    # tree-sitter-sql mis-parses the FK clause). Same def-node
                    # site, so the table Symbol (``sym``) supplies
                    # subject_symbol_id verbatim for the column facts.
                    sql_facts, sql_refs = self._extract_sql_table_facts(
                        node, source_bytes, source_file, text, sym,
                    )
                    facts.extend(sql_facts)
                    refs.extend(sql_refs)
                    # Milestone 25: field/property type refs, method
                    # parameter/return type refs, Java ``throws`` facts, and
                    # enum-member ``has_enum_value`` facts. Same def-node site,
                    # so the just-built Symbol (``sym``) supplies
                    # subject_symbol_id / enclosing_symbol_id verbatim.
                    m25_facts, m25_refs = self._extract_type_refs(
                        node, source_bytes, source_file, text, sym,
                    )
                    facts.extend(m25_facts)
                    refs.extend(m25_refs)
                else:
                    # Container without a recognizable name: still push a
                    # placeholder so nested defs aren't misqualified.
                    if node.type in container_kinds:
                        extended_stack = container_stack + ["<anon>"]
            elif node.type in container_kinds:
                # E.g., C# namespace_declaration is a container but not a
                # definition_node_kind in some configs.
                name = self._extract_name(node, source_bytes, name_kinds)
                if name:
                    extended_stack = container_stack + [name]

            if node.type in call_kinds:
                name = self._extract_name(node, source_bytes, name_kinds)
                # Same normalization as SQL definitions so a ``FROM
                # [dbo].[Customer]`` / ``JOIN`` table reference resolves to its
                # normalized ``create_table`` symbol.
                if name and source_file.language == "sql":
                    name = _normalize_sql_identifier(name)
                if name:
                    rng = self._range_of(node)
                    ref_id = (
                        f"{source_file.language}:{source_file.relative_path}:ref:"
                        f"{name}:{rng.start_line}:{rng.start_byte}"
                    )
                    evidence = _line_text(text, rng.start_line).strip()
                    refs.append(
                        SymbolRef(
                            id=ref_id,
                            language=source_file.language,
                            name=name,
                            kind=node.type,
                            range=rng,
                            enclosing_symbol_id=current_id,
                            evidence=evidence,
                        )
                    )

            for child in node.children:
                visit(child, extended_stack, current_id)

        visit(root, [], None)
        return symbols, refs, facts

    def _extract_name(self, node, source_bytes: bytes, name_kinds: set[str]) -> str:
        # 1. child-by-field-name "name"
        try:
            named = node.child_by_field_name("name")
        except Exception:
            named = None
        if named is not None:
            t = _node_text(named, source_bytes).strip()
            if t:
                return t
        # 2. first descendant whose type is in name_kinds
        if name_kinds:
            stack = list(node.children)
            while stack:
                cur = stack.pop(0)
                if cur.type in name_kinds:
                    t = _node_text(cur, source_bytes).strip()
                    if t:
                        return t
                stack.extend(cur.children)
        # 3. first identifier-like child (last-ditch)
        for c in node.children:
            if c.type == "identifier":
                t = _node_text(c, source_bytes).strip()
                if t:
                    return t
        return ""

    def _extract_inheritance_refs(
        self,
        node,
        source_bytes: bytes,
        source_file: SourceFile,
        profile: ProfileEntry,
        text: str,
        enclosing_id: str | None,
    ) -> list[SymbolRef]:
        """Milestone 22: emit one SymbolRef per base type of a definition node.

        Fired when a definition node is visited. Locates the node's inheritance
        children per ``profile.inheritance_node_kinds`` and enumerates every
        base-type identifier, emitting an ``extends`` / ``implements`` /
        ``inherits_or_implements`` ref for each. The extends-vs-implements
        semantics per node kind live here (not in the JSON) because the profile
        can only name *which* node holds the base list, not what it means.
        """
        inh_kinds = set(profile.inheritance_node_kinds)
        if not inh_kinds:
            return []

        lang = source_file.language
        refs: list[SymbolRef] = []

        def emit(base_node, kind: str) -> None:
            name = _base_type_name(base_node, source_bytes)
            if not name:
                return
            rng = self._range_of(base_node)
            ref_id = (
                f"{source_file.language}:{source_file.relative_path}:ref:"
                f"{name}:{rng.start_line}:{rng.start_byte}"
            )
            evidence = _line_text(text, rng.start_line).strip()
            refs.append(
                SymbolRef(
                    id=ref_id,
                    language=source_file.language,
                    name=name,
                    kind=kind,
                    range=rng,
                    enclosing_symbol_id=enclosing_id,
                    evidence=evidence,
                )
            )

        # Python: reach the base list only through the class_definition's
        # `superclasses` field, never a bare argument_list node-type match
        # (argument_list is also ordinary call args — see the plan's warning).
        if lang == "python":
            if node.type != "class_definition":
                return []
            try:
                supers = node.child_by_field_name("superclasses")
            except Exception:
                supers = None
            if supers is not None and supers.type in inh_kinds:
                for b in supers.children:
                    emit(b, "extends")  # Python has no interfaces -> inherits
            return refs

        for child in node.children:
            ctype = child.type
            if ctype not in inh_kinds:
                continue
            if lang == "csharp":
                # base_list: class-vs-interface not syntactically distinguishable.
                for b in child.children:
                    emit(b, "inherits_or_implements")
            elif lang == "java":
                if ctype == "superclass":
                    for b in child.children:
                        emit(b, "extends")
                elif ctype == "super_interfaces":
                    for b in self._type_list_children(child):
                        emit(b, "implements")
                elif ctype == "extends_interfaces":
                    # interface extends interface(s) -> inherits
                    for b in self._type_list_children(child):
                        emit(b, "extends")
            elif lang == "typescript":
                if ctype == "class_heritage":
                    for clause in child.children:
                        if clause.type == "extends_clause":
                            for b in clause.children:
                                emit(b, "extends")
                        elif clause.type == "implements_clause":
                            for b in clause.children:
                                emit(b, "implements")
                elif ctype == "extends_type_clause":
                    # interface extends interface(s) -> inherits
                    for b in child.children:
                        emit(b, "extends")
            elif lang == "javascript":
                if ctype == "class_heritage":
                    for b in child.children:
                        emit(b, "extends")  # JS has no interfaces
        return refs

    @staticmethod
    def _type_list_children(node) -> list:
        """Return the base-type children of a Java super_interfaces /
        extends_interfaces node, descending through its ``type_list``."""
        for c in node.children:
            if c.type == "type_list":
                return list(c.children)
        # Defensive: some grammars may inline the types.
        return list(node.children)

    # -- Annotation / attribute / decorator facts (Milestone 23) -----------

    def _extract_annotation_facts(
        self,
        node,
        source_bytes: bytes,
        source_file: SourceFile,
        profile: ProfileEntry,
        text: str,
        sym: Symbol,
    ) -> tuple[list[SymbolFact], list[SymbolRef]]:
        """Milestone 23: emit facts (and relational refs) for a definition's
        annotations / attributes / decorators.

        Fired on the same definition-node site as ``_extract_inheritance_refs``,
        so the just-built ``Symbol`` (``sym``) supplies ``subject_symbol_id``
        verbatim. Splits by intent via ``profile.annotation_semantics``:
        routing -> http_method / exposes_endpoint facts; authz -> requires_auth;
        validation -> is_required / max_length; persistence -> table_name /
        is_column / is_id; @JoinColumn/@ManyToOne etc. -> foreign_key /
        associates *refs* (mapped to edges in GraphBuilder). Unknown annotations
        become a generic has_annotation fact so nothing is silently dropped.

        Traversal differs per language (the critical M23 caveat): C# attributes
        and Java annotations are children of the definition node (via a
        ``modifiers`` child for Java), but a Python decorator is a child of the
        node's *parent* ``decorated_definition`` and a TypeScript decorator is a
        *preceding sibling* of the definition. A children-only walk would emit
        ZERO facts for Python/TS.
        """
        lang = source_file.language
        ann_nodes = self._annotation_nodes(node, lang)
        if not ann_nodes:
            return [], []

        semantics = profile.annotation_semantics
        facts: list[SymbolFact] = []
        refs: list[SymbolRef] = []

        def make_fact(predicate: str, obj, attributes, rng, evidence) -> SymbolFact:
            obj_seg = obj if obj is not None else ""
            fid = (
                f"fact:{sym.id}:{predicate}:{obj_seg}:{rng.start_line}"
            )
            return SymbolFact(
                id=fid,
                subject_symbol_id=sym.id,
                predicate=predicate,
                object=obj,
                attributes=attributes or None,
                evidence=evidence,
                confidence=1.0,
                relative_path=source_file.relative_path,
                start_line=rng.start_line,
                language=lang,
            )

        for ann in ann_nodes:
            name_full, name_last, arg_nodes = self._parse_annotation(
                ann, lang, source_bytes
            )
            if not name_full:
                continue
            intent = semantics.get(name_full) or semantics.get(name_last)
            positional, named = self._annotation_arg_values(arg_nodes, source_bytes)
            rng = self._range_of(ann)
            evidence = _node_text(ann, source_bytes).strip()[:200]

            if intent and intent.startswith("route"):
                verb = intent.split("_", 1)[1].upper() if "_" in intent else "ANY"
                route = (
                    positional[0] if positional
                    else named.get("path") or named.get("value")
                )
                attrs: dict = {"annotation": name_full}
                if route:
                    attrs["route"] = route
                facts.append(make_fact("http_method", verb, attrs, rng, evidence))
                facts.append(
                    make_fact(
                        "exposes_endpoint",
                        route or name_full,
                        {"annotation": name_full, "http_method": verb},
                        rng,
                        evidence,
                    )
                )
            elif intent == "authz":
                policy = positional[0] if positional else None
                facts.append(
                    make_fact(
                        "requires_auth", policy, {"annotation": name_full},
                        rng, evidence,
                    )
                )
            elif intent == "required":
                facts.append(
                    make_fact(
                        "is_required", None, {"annotation": name_full}, rng, evidence
                    )
                )
            elif intent == "max_length":
                val = (
                    named.get("max")
                    or named.get("max_length")
                    or named.get("length")
                    or (positional[0] if positional else None)
                )
                facts.append(
                    make_fact(
                        "max_length",
                        str(val) if val is not None else None,
                        {"annotation": name_full},
                        rng,
                        evidence,
                    )
                )
            elif intent == "table":
                tbl = (
                    named.get("name")
                    or (positional[0] if positional else None)
                    or sym.name
                )
                facts.append(
                    make_fact(
                        "table_name", tbl, {"annotation": name_full}, rng, evidence
                    )
                )
            elif intent == "column":
                col = named.get("name") or (positional[0] if positional else None)
                facts.append(
                    make_fact(
                        "is_column", col, {"annotation": name_full}, rng, evidence
                    )
                )
            elif intent == "id":
                facts.append(
                    make_fact(
                        "is_id", None, {"annotation": name_full}, rng, evidence
                    )
                )
            elif intent in ("foreign_key", "associates"):
                # Relational: point at the annotated field/property's type, which
                # names another entity. Emitted as a SymbolRef whose kind maps to
                # a foreign_key / associates edge in GraphBuilder.
                target = (
                    self._annotated_member_type(node, source_bytes)
                    or named.get("name")
                    or (positional[0] if positional else None)
                )
                if target:
                    ref_id = (
                        f"{lang}:{source_file.relative_path}:ref:"
                        f"{target}:{rng.start_line}:{rng.start_byte}"
                    )
                    refs.append(
                        SymbolRef(
                            id=ref_id,
                            language=lang,
                            name=target,
                            kind=intent,
                            range=rng,
                            enclosing_symbol_id=sym.id,
                            evidence=evidence,
                        )
                    )
            else:
                # Unknown annotation: record it so nothing is silently dropped.
                attrs = {}
                if positional:
                    attrs["args"] = positional
                if named:
                    attrs["named"] = named
                facts.append(
                    make_fact(
                        "has_annotation", name_full, attrs or None, rng, evidence
                    )
                )

        return facts, refs

    def _extract_sql_table_facts(
        self,
        node,
        source_bytes: bytes,
        source_file: SourceFile,
        text: str,
        sym: Symbol,
    ) -> tuple[list[SymbolFact], list[SymbolRef]]:
        """Milestone 24: emit a ``has_column`` fact per column of a SQL
        ``create_table`` and a ``foreign_key`` ref per FK constraint.

        Fired on the same definition-node site as the M22/M23 handlers, so the
        just-built table ``Symbol`` (``sym``) supplies ``subject_symbol_id``
        verbatim for the column facts. Columns come cleanly from the tree-sitter
        ``column_definition`` subtree; foreign keys are recovered by regex over
        the table's source text because the tree-sitter-sql grammar mis-parses
        the ``FOREIGN KEY ... REFERENCES`` clause (it can surface as an ``ERROR``
        node). The two paths are logged separately so the split is visible.
        """
        if source_file.language != "sql" or node.type != "create_table":
            return [], []

        facts: list[SymbolFact] = []
        refs: list[SymbolRef] = []

        # --- Columns via tree-sitter -------------------------------------
        for col in self._descendants_of_type(node, "column_definition"):
            col_name = self._sql_column_name(col, source_bytes)
            if not col_name:
                continue
            data_type = self._sql_column_type(col, source_bytes)
            child_types = {c.type for c in col.children}
            has_not_null = "keyword_not" in child_types
            primary_key = "keyword_primary" in child_types
            unique = "keyword_unique" in child_types
            attributes: dict = {
                "data_type": data_type,
                "nullable": not has_not_null,
                "primary_key": primary_key,
                "unique": unique,
            }
            rng = self._range_of(col)
            evidence = _node_text(col, source_bytes).strip()[:200]
            fid = f"fact:{sym.id}:has_column:{col_name}:{rng.start_line}"
            facts.append(
                SymbolFact(
                    id=fid,
                    subject_symbol_id=sym.id,
                    predicate="has_column",
                    object=col_name,
                    attributes=attributes,
                    evidence=evidence,
                    confidence=1.0,
                    relative_path=source_file.relative_path,
                    start_line=rng.start_line,
                    language=source_file.language,
                )
            )

        # --- Foreign keys via regex supplement ---------------------------
        node_text = _node_text(node, source_bytes)
        node_start_line = node.start_point[0] + 1
        # Matched against a comment/string-masked copy (same offsets) so a
        # commented-out constraint cannot emit a live FK edge; evidence is still
        # sliced from the real text.
        for m in _SQL_FK_RE.finditer(_sql_mask_noncode(node_text)):
            # Normalize identically to the create_table symbol name so the edge
            # resolves (shared helper keeps both sides in lockstep).
            referenced_table = _normalize_sql_identifier(m.group(2))
            if not referenced_table:
                continue
            # Map the match offset back to an absolute line for the ref range.
            line_offset = node_text.count("\n", 0, m.start())
            fk_line = node_start_line + line_offset
            evidence = node_text[m.start():m.end()].strip()[:200]
            ref_id = (
                f"{source_file.language}:{source_file.relative_path}:ref:"
                f"{referenced_table}:{fk_line}:{node.start_byte + m.start()}"
            )
            refs.append(
                SymbolRef(
                    id=ref_id,
                    language=source_file.language,
                    name=referenced_table,
                    kind="foreign_key",
                    range=TextRange(
                        start_byte=node.start_byte + m.start(),
                        end_byte=node.start_byte + m.end(),
                        start_line=fk_line,
                        end_line=fk_line,
                    ),
                    enclosing_symbol_id=sym.id,
                    evidence=evidence,
                )
            )

        if facts or refs:
            logger.info(
                "SQL %s table %s: %d has_column facts (tree-sitter), "
                "%d foreign_key refs (regex)",
                source_file.relative_path,
                sym.name,
                len(facts),
                len(refs),
            )
        return facts, refs

    def _sql_recovered_table_artifacts(
        self,
        source_file: SourceFile,
        text: str,
        segments: list[_SqlTableSegment],
    ) -> tuple[list[Symbol], list[SymbolRef], list[SymbolFact]]:
        """Build the symbol, ``has_column`` facts, and ``foreign_key`` refs for
        regex-segmented ``CREATE TABLE`` statements (Milestone 4 recovery).

        Emits exactly the shapes the tree-sitter path emits — same id scheme,
        same ``create_table``/``create_temp_table`` kinds, same fact attributes —
        so downstream consumers cannot tell a recovered table from a parsed one
        except by the column facts' 0.9 confidence (regex-derived, not AST) and
        the raw DDL kept on ``signature`` / ``evidence`` as the audit trail.
        """
        symbols: list[Symbol] = []
        refs: list[SymbolRef] = []
        facts: list[SymbolFact] = []

        for seg in segments:
            kind = "create_temp_table" if seg.is_temp else "create_table"
            # Both `create_table` and `create_temp_table` classify as `table`
            # (§S3.1.2's SQL row); this path emits only those two kinds, so
            # the class is hardcoded rather than looked up in a profile this
            # function is never handed.
            sym_id = (
                f"{source_file.language}:{source_file.relative_path}:"
                f"{seg.name}:{seg.start_line}"
            )
            sym = Symbol(
                id=sym_id,
                language=source_file.language,
                name=seg.name,
                qualified_name=seg.name,
                kind=kind,
                range=TextRange(
                    start_byte=seg.start_byte,
                    end_byte=seg.end_byte,
                    start_line=seg.start_line,
                    end_line=seg.end_line,
                ),
                container=None,
                signature=self._first_line(seg.header.strip()),
                entity_class="table",
            )
            symbols.append(sym)

            body_line = text.count("\n", 0, seg.body_char) + 1
            for col_name, attributes, offset in _sql_columns_from_body(seg.body):
                line = body_line + seg.body.count("\n", 0, offset)
                entry_start = seg.body_char + offset
                facts.append(
                    SymbolFact(
                        id=f"fact:{sym.id}:has_column:{col_name}:{line}",
                        subject_symbol_id=sym.id,
                        predicate="has_column",
                        object=col_name,
                        attributes=attributes,
                        evidence=text[entry_start:entry_start + 200].strip(),
                        confidence=0.9,
                        relative_path=source_file.relative_path,
                        start_line=line,
                        language=source_file.language,
                    )
                )

            # Masked copy (same offsets) so a commented-out constraint cannot
            # emit a live FK edge; evidence is sliced from the real body.
            for m in _SQL_FK_RE.finditer(_sql_mask_noncode(seg.body)):
                referenced_table = _normalize_sql_identifier(m.group(2))
                if not referenced_table:
                    continue
                fk_line = body_line + seg.body.count("\n", 0, m.start())
                raw_match = seg.body[m.start():m.end()]
                start_byte = seg.start_byte + len(
                    text[seg.start_char:seg.body_char + m.start()].encode("utf-8")
                )
                end_byte = start_byte + len(raw_match.encode("utf-8"))
                refs.append(
                    SymbolRef(
                        id=(
                            f"{source_file.language}:{source_file.relative_path}:ref:"
                            f"{referenced_table}:{fk_line}:{start_byte}"
                        ),
                        language=source_file.language,
                        name=referenced_table,
                        kind="foreign_key",
                        range=TextRange(
                            start_byte=start_byte,
                            end_byte=end_byte,
                            start_line=fk_line,
                            end_line=fk_line,
                        ),
                        enclosing_symbol_id=sym.id,
                        evidence=raw_match.strip()[:200],
                    )
                )

        return symbols, refs, facts

    def _sql_alter_table_fk_refs(
        self,
        source_file: SourceFile,
        text: str,
        symbols: list[Symbol],
    ) -> list[SymbolRef]:
        """Emit ``foreign_key`` refs for out-of-line ``ALTER TABLE ... ADD
        CONSTRAINT ... FOREIGN KEY`` statements.

        Both in-table FK scans (the M24 AST supplement and the M4 segment scan)
        are scoped to a single ``CREATE TABLE``'s body, so they cannot see a
        constraint declared in its own statement. That is how SSMS scripts a
        schema, so a script-folder export yielded no FK edges at all.

        The ref is anchored on the ``FOREIGN KEY`` clause at an absolute file
        offset — the same anchor the two in-table scans use — so a clause seen by
        both produces the same ref id and dedupes instead of double-counting.
        ``enclosing_symbol_id`` is the ALTERED table's symbol, which is what makes
        the edge read child -> parent; when the ``CREATE TABLE`` lives in another
        file there is no local symbol to anchor to and the ref carries None,
        leaving a file-anchored edge rather than a wrong one.
        """
        table_kinds = ("create_table", "create_temp_table")
        by_name: dict[str, list[Symbol]] = {}
        for s in symbols:
            if s.kind in table_kinds:
                by_name.setdefault(s.name, []).append(s)

        refs: list[SymbolRef] = []
        # Masked copy (same offsets) so a commented-out or dynamically-built
        # constraint cannot become a live edge; evidence is sliced from the real
        # text.
        for m in _SQL_ALTER_TABLE_FK_RE.finditer(_sql_mask_noncode(text)):
            child_table = _normalize_sql_identifier(m.group("child"))
            referenced_table = _normalize_sql_identifier(m.group("parent"))
            if not referenced_table:
                continue
            # Anchor on the FOREIGN KEY clause, not the ALTER keyword, to match
            # the in-table scans' anchor.
            clause_start = m.start("fk")
            fk_line = text.count("\n", 0, clause_start) + 1
            start_byte = len(text[:clause_start].encode("utf-8"))
            end_byte = len(text[:m.end("fk")].encode("utf-8"))
            # Several same-named tables in one file is pathological; prefer the
            # last one declared before this ALTER so the pairing stays positional.
            candidates = by_name.get(child_table, [])
            enclosing = next(
                (
                    s for s in reversed(candidates)
                    if s.range.start_byte <= start_byte
                ),
                candidates[0] if candidates else None,
            )
            refs.append(
                SymbolRef(
                    id=(
                        f"{source_file.language}:{source_file.relative_path}:ref:"
                        f"{referenced_table}:{fk_line}:{start_byte}"
                    ),
                    language=source_file.language,
                    name=referenced_table,
                    kind="foreign_key",
                    range=TextRange(
                        start_byte=start_byte,
                        end_byte=end_byte,
                        start_line=fk_line,
                        end_line=fk_line,
                    ),
                    enclosing_symbol_id=enclosing.id if enclosing else None,
                    evidence=text[m.start():m.end("fk")].strip()[:200],
                )
            )
        if refs:
            logger.info(
                "SQL %s: %d out-of-line ALTER TABLE foreign_key ref(s)",
                source_file.relative_path,
                len(refs),
            )
        return refs

    def _reconcile_sql_tables(
        self,
        source_file: SourceFile,
        text: str,
        symbols: list[Symbol],
        refs: list[SymbolRef],
        facts: list[SymbolFact],
    ) -> tuple[list[Symbol], list[SymbolRef], list[SymbolFact]]:
        """Milestone 4: take the SQL table inventory back from the grammar
        wherever tree-sitter-sql's bracket handling makes it untrustworthy.

        Regex segmentation decides *how many* tables a file declares; the grammar
        keeps a table only when its node maps 1:1 to a single statement AND that
        statement is free of [bracket] quoting (there its column typing is the
        better of the two). Three repairs happen here — the first two are missing
        data, the third is WRONG data:

        * a ``create_table`` node spanning MORE than one statement (the
          bracketed-DDL + ``NOT NULL`` merge) describes several tables at once:
          the swallowed table loses its symbol and its FK resolves against the
          preceding table as a confident SELF edge.
        * a statement the grammar produced no table node for at all.
        * a bracket-quoted statement the grammar *did* segment 1:1. Its column
          subtree still cannot be trusted: a bracketed column whose name collides
          with a grammar keyword is swallowed by an ERROR node and VANISHES
          (``[Name] NVARCHAR(100)`` -> ``keyword_name`` inside ERROR, no
          ``column_definition``), and Name/Date/Value/Status/Type/Key are
          everywhere in real schemas. Silently short columns are worse than
          regex-derived ones, so recovery owns these tables too.

        In every case the grammar's symbol, its facts, and its ``foreign_key``
        refs are discarded and re-emitted from regex. Non-FK refs enclosed by a
        discarded node are re-anchored to whichever recovered table now contains
        them, rather than dropped, so data lineage survives the repair.

        Cost: a bracket-heavy file has its columns parsed twice (once by the M24
        AST path, then again here) — measured at ~0.5s per 100 KiB of pathological
        DDL on top of ~1.4s of grammar parse + walk. Skipping the AST pass up
        front would need the segments before the walk, and would silently lose
        facts for any statement the segmenter cannot balance; the redundant work
        is the cheaper trade.
        """
        segments = _sql_table_segments(text)
        if not segments:
            return symbols, refs, facts

        table_kinds = ("create_table", "create_temp_table")
        ts_tables = [s for s in symbols if s.kind in table_kinds]
        owned: dict[str, list[_SqlTableSegment]] = {}
        # Owner id per segment, parallel to ``segments``. Everything downstream
        # is derived in SEGMENT (source) order — never by iterating an id set —
        # because string hashing is per-process, so set order would make the
        # emitted symbol order differ between a serial and a parallel index run.
        seg_owner: list[str | None] = []
        for seg in segments:
            owner = next(
                (
                    s for s in ts_tables
                    if s.range.start_byte <= seg.start_byte < s.range.end_byte
                ),
                None,
            )
            seg_owner.append(owner.id if owner else None)
            if owner is not None:
                owned.setdefault(owner.id, []).append(seg)

        merged_ids = {sid for sid, segs in owned.items() if len(segs) > 1}
        bracketed_ids = {
            sid
            for sid, segs in owned.items()
            if sid not in merged_ids and "[" in segs[0].header + segs[0].body
        }
        replaced_ids = merged_ids | bracketed_ids
        unclaimed = [seg for seg, oid in zip(segments, seg_owner) if oid is None]
        recover = [
            seg
            for seg, oid in zip(segments, seg_owner)
            if oid is None or oid in replaced_ids
        ]
        if not recover:
            return symbols, refs, facts

        new_symbols, new_refs, new_facts = self._sql_recovered_table_artifacts(
            source_file, text, recover
        )

        if replaced_ids:
            # ``CREATE TABLE <name> (`` byte spans. The grammar also reports a
            # table's own name as an ``object_reference`` — harmless while the
            # grammar owned the table (it self-resolved), but once recovery owns
            # it the two spellings can disagree (``OrderStaging`` from the
            # grammar vs ``#OrderStaging`` recovered, since the marker must stay
            # in the name) and the artifact would surface as a dangling
            # uses_table edge. A definition's own name is not a usage: drop it.
            header_spans = [
                (
                    seg.start_byte,
                    seg.start_byte
                    + len(text[seg.start_char:seg.body_char].encode("utf-8")),
                )
                for seg in recover
            ]
            symbols = [s for s in symbols if s.id not in replaced_ids]
            facts = [f for f in facts if f.subject_symbol_id not in replaced_ids]
            kept_refs: list[SymbolRef] = []
            for r in refs:
                if r.enclosing_symbol_id not in replaced_ids:
                    kept_refs.append(r)
                    continue
                if r.kind == "foreign_key":
                    continue  # re-emitted per statement below
                if any(lo <= r.range.start_byte < hi for lo, hi in header_spans):
                    continue
                reanchored = next(
                    (
                        s for s in new_symbols
                        if s.range.start_byte <= r.range.start_byte < s.range.end_byte
                    ),
                    None,
                )
                kept_refs.append(
                    r.model_copy(
                        update={
                            "enclosing_symbol_id": reanchored.id if reanchored else None
                        }
                    )
                )
            refs = kept_refs

        logger.info(
            "SQL %s: regex CREATE TABLE recovery -> %d table(s) recovered "
            "(%d unsegmented by the grammar, %d merged node(s), %d bracketed "
            "node(s) replaced)",
            source_file.relative_path,
            len(new_symbols),
            len(unclaimed),
            len(merged_ids),
            len(bracketed_ids),
        )
        return (
            self._dedupe_by_id(symbols + new_symbols),
            self._dedupe_by_id(refs + new_refs),
            self._dedupe_by_id(facts + new_facts),
        )

    @staticmethod
    def _descendants_of_type(node, node_type: str) -> list:
        """Return all descendants of ``node`` whose type is ``node_type``."""
        out: list = []
        stack = list(node.children)
        while stack:
            cur = stack.pop(0)
            if cur.type == node_type:
                out.append(cur)
            stack.extend(cur.children)
        return out

    def _sql_column_name(self, col_node, source_bytes: bytes) -> str:
        """Column name: the ``name`` field if present, else the first
        ``identifier`` child of a ``column_definition``. Normalized so a
        bracket-quoted column matches its plain form."""
        try:
            named = col_node.child_by_field_name("name")
        except Exception:
            named = None
        if named is not None:
            t = _normalize_sql_identifier(_node_text(named, source_bytes))
            if t:
                return t
        for c in col_node.children:
            if c.type == "identifier":
                t = _normalize_sql_identifier(_node_text(c, source_bytes))
                if t:
                    return t
        return ""

    def _sql_column_type(self, col_node, source_bytes: bytes) -> str | None:
        """Data type: the first child after the column-name identifier that is
        neither punctuation nor a column-constraint keyword. Handles both
        dedicated type nodes (``int``/``varchar(255)``) and keyword types
        (``DATE`` -> ``keyword_date``)."""
        name_seen = False
        for c in col_node.children:
            if c.type == "identifier" and not name_seen:
                name_seen = True
                continue
            if c.type in _SQL_COLUMN_CONSTRAINT_KEYWORDS:
                continue
            if c.type in (",", "(", ")"):
                continue
            # Milestone 4 (sql-extractor-temp-cte-fk): a bracket-quoted column
            # leaves the closing ``]`` in an ERROR sibling between the name and
            # the type (``[Qty] DECIMAL(9,3)`` -> identifier, ERROR ']', decimal).
            # Skipping those bracket artifacts like punctuation is what lets the
            # real type node be reached; otherwise every bracketed column's
            # data_type came back as ``']'``.
            if c.type == "ERROR" or c.type in ("[", "]"):
                continue
            t = _node_text(c, source_bytes).strip()
            if t:
                if re.match(r"^[A-Za-z_]", t):
                    return t
                break
        # Milestone 4 (sql-extractor-temp-cte-fk): tree-sitter-sql mangles
        # bracket-quoted columns — ``[Total] DECIMAL(18,2)`` surfaces its type as
        # a stray ``]`` token — so anything that is not identifier-shaped is
        # re-derived from the entry text with the same regex the CREATE TABLE
        # recovery path uses. Without this, every column of a cleanly-parsed
        # bracketed T-SQL table carries ``data_type=']'``.
        recovered = _sql_columns_from_body(_node_text(col_node, source_bytes))
        if recovered:
            return recovered[0][1]["data_type"]
        return None

    def _annotation_nodes(self, node, language: str) -> list:
        """Locate the annotation-bearing nodes for a definition, per language.

        C#: ``attribute`` nodes inside the definition's ``attribute_list``
        children. Java: ``annotation`` / ``marker_annotation`` inside the
        definition's ``modifiers`` child. Python: ``decorator`` children of the
        parent ``decorated_definition``. TypeScript/JavaScript: the contiguous
        run of ``decorator`` preceding siblings (skipping keyword tokens such as
        ``export``).
        """
        out: list = []
        if language == "csharp":
            for child in node.children:
                if child.type == "attribute_list":
                    for a in child.children:
                        if a.type == "attribute":
                            out.append(a)
        elif language == "java":
            for child in node.children:
                if child.type == "modifiers":
                    for a in child.children:
                        if a.type in ("annotation", "marker_annotation"):
                            out.append(a)
        elif language == "python":
            if node.type in ("function_definition", "class_definition"):
                parent = node.parent
                if parent is not None and parent.type == "decorated_definition":
                    for a in parent.children:
                        if a.type == "decorator":
                            out.append(a)
        elif language in ("typescript", "javascript"):
            parent = node.parent
            if parent is not None:
                siblings = list(parent.children)
                try:
                    idx = siblings.index(node)
                except ValueError:
                    idx = -1
                # Scan backwards over the contiguous decorator run, skipping
                # keyword/punctuation tokens (e.g. ``export``) which are not
                # named nodes. Stop at the first real (named, non-decorator)
                # sibling so a previous method's decorators are not attached.
                for prev in reversed(siblings[:idx] if idx >= 0 else []):
                    if prev.type == "decorator":
                        out.append(prev)
                    elif not prev.is_named:
                        continue
                    else:
                        break
                out.reverse()
        return out

    def _parse_annotation(
        self, ann, language: str, source_bytes: bytes
    ) -> tuple[str, str, list]:
        """Return ``(full_name, last_segment, arg_value_nodes)`` for one
        annotation node. ``arg_value_nodes`` are the named children of the
        annotation's argument-list container (punctuation filtered out)."""
        name_node = None
        arg_container = None

        if language == "csharp":
            for c in ann.children:
                if c.type in ("identifier", "qualified_name", "generic_name"):
                    name_node = c
                    break
            arg_container = self._first_child_of_type(
                ann, ("attribute_argument_list",)
            )
        elif language == "java":
            try:
                name_node = ann.child_by_field_name("name")
            except Exception:
                name_node = None
            if name_node is None:
                for c in ann.children:
                    if c.type in ("identifier", "scoped_identifier"):
                        name_node = c
                        break
            arg_container = self._first_child_of_type(
                ann, ("annotation_argument_list",)
            )
        else:
            # Python decorator / TS-JS decorator: the name-bearing node is the
            # first named child after ``@`` (identifier | attribute | call |
            # call_expression | member_expression).
            inner = None
            for c in ann.children:
                if c.type == "@" or not c.is_named:
                    continue
                inner = c
                break
            if inner is None:
                return "", "", []
            if inner.type in ("call", "call_expression"):
                try:
                    fn = inner.child_by_field_name("function")
                except Exception:
                    fn = None
                if fn is None:
                    for c in inner.children:
                        if c.is_named:
                            fn = c
                            break
                name_node = fn
                arg_container = self._first_child_of_type(
                    inner, ("argument_list", "arguments")
                )
            else:
                name_node = inner

        if name_node is None:
            return "", "", []
        raw = _node_text(name_node, source_bytes).strip()
        # Strip any call/generic tail and take the plain dotted name.
        raw = raw.split("(", 1)[0].split("<", 1)[0].strip()
        if not raw:
            return "", "", []
        last = raw.rsplit(".", 1)[-1].strip()

        arg_nodes: list = []
        if arg_container is not None:
            arg_nodes = [c for c in arg_container.children if c.is_named]
        return raw, last, arg_nodes

    @staticmethod
    def _first_child_of_type(node, types: tuple[str, ...]):
        for c in node.children:
            if c.type in types:
                return c
        return None

    def _annotation_arg_values(
        self, arg_nodes: list, source_bytes: bytes
    ) -> tuple[list[str], dict[str, str]]:
        """Split annotation arguments into positional values and named args.

        Text-based (robust across the four grammars' differing arg node kinds):
        a ``key = value`` / ``key=value`` argument becomes ``named[key]``, any
        other argument is positional. All values are unquoted.
        """
        positional: list[str] = []
        named: dict[str, str] = {}
        for a in arg_nodes:
            txt = _node_text(a, source_bytes).strip()
            if not txt:
                continue
            if txt[0] not in "\"'`":
                m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", txt, re.S)
                if m:
                    named[m.group(1).lower()] = _unquote(m.group(2).strip())
                    continue
            positional.append(_unquote(txt))
        return positional, named

    def _annotated_member_type(self, node, source_bytes: bytes) -> str:
        """Return the plain type name of an annotated field/property definition
        (the associated entity for @ManyToOne/@JoinColumn etc.), or ""."""
        try:
            type_node = node.child_by_field_name("type")
        except Exception:
            type_node = None
        if type_node is None:
            for c in node.children:
                if c.type in (
                    "type_identifier", "generic_type", "qualified_name",
                    "scoped_type_identifier", "generic_name",
                ):
                    type_node = c
                    break
        if type_node is None:
            return ""
        name = _base_type_name(type_node, source_bytes)
        if name:
            return name
        return _node_text(type_node, source_bytes).split("<", 1)[0].strip()

    # -- Type refs / signatures / enum values (Milestone 25) ---------------

    def _extract_type_refs(
        self,
        node,
        source_bytes: bytes,
        source_file: SourceFile,
        text: str,
        sym: Symbol,
    ) -> tuple[list[SymbolFact], list[SymbolRef]]:
        """Milestone 25: emit type-reference refs and signature/enum facts for a
        definition node.

        Fired on the same definition-node site as the M22/M23/M24 handlers, so
        the just-built ``Symbol`` (``sym``) supplies ``subject_symbol_id`` /
        ``enclosing_symbol_id`` verbatim.

        - Field/property type -> ``has_field_of_type`` ref (mapped to a
          ``has_field_of_type`` edge in GraphBuilder).
        - Method parameter types -> ``accepts_dto`` refs; return type ->
          ``returns_dto`` ref.
        - Java ``throws`` -> ``throws`` facts (object = exception type).
        - Enum members -> ``has_enum_value`` facts (object = member name).

        Generic types are unwrapped to their INNERMOST payload via
        ``_inner_type_name`` (NOT ``_base_type_name``), and primitive / builtin
        type names are dropped via ``_PRIMITIVE_TYPES`` BEFORE any ref is
        emitted, so only user-defined types become edges.
        """
        lang = source_file.language
        ntype = node.type
        facts: list[SymbolFact] = []
        refs: list[SymbolRef] = []

        # --- Enum members -> has_enum_value facts ------------------------
        if ntype in ("enum_declaration",):
            facts.extend(self._enum_value_facts(node, source_bytes, source_file, sym))
            return facts, refs

        # --- Field / property type -> has_field_of_type ref --------------
        field_kinds = {
            "csharp": ("property_declaration", "field_declaration"),
            "java": ("field_declaration",),
        }.get(lang, ())
        if ntype in field_kinds:
            type_node = self._field_type_node(node, lang)
            r = self._make_type_ref(
                type_node, "has_field_of_type", lang, source_bytes,
                source_file, text, sym,
            )
            if r is not None:
                refs.append(r)
            return facts, refs

        # --- Method / constructor / function signature -------------------
        method_kinds = {
            "csharp": ("method_declaration", "constructor_declaration"),
            "java": ("method_declaration", "constructor_declaration"),
            "python": ("function_definition",),
            "typescript": ("method_definition", "function_declaration"),
            "javascript": ("method_definition", "function_declaration"),
        }.get(lang, ())
        if ntype in method_kinds:
            # Parameters -> accepts_dto refs.
            for ptype in self._param_type_nodes(node, lang):
                r = self._make_type_ref(
                    ptype, "accepts_dto", lang, source_bytes,
                    source_file, text, sym,
                )
                if r is not None:
                    refs.append(r)
            # Return type -> returns_dto ref.
            rtype = self._return_type_node(node, lang)
            r = self._make_type_ref(
                rtype, "returns_dto", lang, source_bytes,
                source_file, text, sym,
            )
            if r is not None:
                refs.append(r)
            # Java throws -> throws facts.
            if lang == "java":
                facts.extend(
                    self._throws_facts(node, source_bytes, source_file, sym)
                )
            return facts, refs

        return facts, refs

    def _make_type_ref(
        self,
        type_node,
        kind: str,
        lang: str,
        source_bytes: bytes,
        source_file: SourceFile,
        text: str,
        sym: Symbol,
    ) -> SymbolRef | None:
        """Build one M25 type-ref, unwrapping generics to the inner payload and
        dropping primitives/builtins. Returns None when there is no type node or
        the resolved name is a primitive/builtin (so no edge is emitted)."""
        if type_node is None:
            return None
        name = _inner_type_name(type_node, source_bytes)
        if not name:
            return None
        if name in _PRIMITIVE_TYPES.get(lang, ()):  # primitive filter (required)
            return None
        # Defensive: never emit refs for empty / punctuation-only names.
        if not name[0].isalpha() and name[0] != "_":
            return None
        rng = self._range_of(type_node)
        ref_id = (
            f"{lang}:{source_file.relative_path}:ref:"
            f"{name}:{rng.start_line}:{rng.start_byte}"
        )
        evidence = _line_text(text, rng.start_line).strip()
        return SymbolRef(
            id=ref_id,
            language=lang,
            name=name,
            kind=kind,
            range=rng,
            enclosing_symbol_id=sym.id,
            evidence=evidence,
        )

    def _field_type_node(self, node, lang: str):
        """Return the type node of a C#/Java field/property definition."""
        if lang == "csharp":
            if node.type == "property_declaration":
                return node.child_by_field_name("type")
            if node.type == "field_declaration":
                vd = self._first_child_of_type(node, ("variable_declaration",))
                if vd is not None:
                    return vd.child_by_field_name("type")
                return None
        if lang == "java":
            return node.child_by_field_name("type")
        return None

    def _param_type_nodes(self, node, lang: str) -> list:
        """Return the type nodes of a method/function's parameters."""
        out: list = []
        params = node.child_by_field_name("parameters")
        if params is None:
            # C# uses parameter_list; some grammars omit the field name.
            params = self._first_child_of_type(
                node, ("parameter_list", "formal_parameters", "parameters")
            )
        if params is None:
            return out
        param_kinds = (
            "parameter",
            "formal_parameter",
            "spread_parameter",
            "typed_parameter",
            "required_parameter",
            "optional_parameter",
        )
        for c in params.children:
            if c.type not in param_kinds:
                continue
            tnode = c.child_by_field_name("type")
            if tnode is not None:
                out.append(tnode)
        return out

    def _return_type_node(self, node, lang: str):
        """Return the return-type node of a method/function, or None."""
        # C# method_declaration uses the ``returns`` field; Java uses ``type``;
        # Python / TS use ``return_type``.
        for field in ("returns", "return_type", "type"):
            try:
                rn = node.child_by_field_name(field)
            except Exception:
                rn = None
            if rn is not None:
                return rn
        return None

    def _throws_facts(
        self, node, source_bytes: bytes, source_file: SourceFile, sym: Symbol
    ) -> list[SymbolFact]:
        """Java ``throws`` clause -> one ``throws`` fact per exception type."""
        throws_node = self._first_child_of_type(node, ("throws",))
        if throws_node is None:
            return []
        facts: list[SymbolFact] = []
        for c in throws_node.children:
            if c.type not in _M25_NAME_LEAF_KINDS and c.type not in _M25_QUALIFIED_KINDS:
                continue
            name = _inner_type_name(c, source_bytes)
            if not name:
                continue
            rng = self._range_of(c)
            fid = f"fact:{sym.id}:throws:{name}:{rng.start_line}"
            facts.append(
                SymbolFact(
                    id=fid,
                    subject_symbol_id=sym.id,
                    predicate="throws",
                    object=name,
                    attributes=None,
                    evidence=_node_text(throws_node, source_bytes).strip()[:200],
                    confidence=1.0,
                    relative_path=source_file.relative_path,
                    start_line=rng.start_line,
                    language=source_file.language,
                )
            )
        return facts

    def _enum_value_facts(
        self, node, source_bytes: bytes, source_file: SourceFile, sym: Symbol
    ) -> list[SymbolFact]:
        """Enum members -> ``has_enum_value`` facts (reference / state data).

        A single-line enum (``enum Status { Open, Closed }``) emits multiple
        facts sharing subject/predicate/start_line; the fact id includes the
        ``object`` (member name) segment, so they do not collapse to one row.
        """
        member_kinds = ("enum_member_declaration", "enum_constant")
        members: list = []
        for m in self._descendants_of_type_any(node, member_kinds):
            members.append(m)
        facts: list[SymbolFact] = []

        def emit(name: str, rng: TextRange, evidence: str) -> None:
            if not name:
                return
            fid = f"fact:{sym.id}:has_enum_value:{name}:{rng.start_line}"
            facts.append(
                SymbolFact(
                    id=fid,
                    subject_symbol_id=sym.id,
                    predicate="has_enum_value",
                    object=name,
                    attributes=None,
                    evidence=evidence,
                    confidence=1.0,
                    relative_path=source_file.relative_path,
                    start_line=rng.start_line,
                    language=source_file.language,
                )
            )

        if members:
            for m in members:
                name = self._extract_name(m, source_bytes, {"identifier"})
                emit(
                    name,
                    self._range_of(m),
                    _node_text(m, source_bytes).strip()[:120],
                )
            return facts

        # TypeScript: enum members are bare ``property_identifier`` children of
        # an ``enum_body`` (no dedicated member node kind).
        body = self._first_child_of_type(node, ("enum_body",))
        if body is not None:
            for c in body.children:
                if c.type in ("property_identifier", "identifier"):
                    name = _node_text(c, source_bytes).strip()
                    emit(name, self._range_of(c), name)
                elif c.type in ("enum_assignment",):
                    inner = self._first_child_of_type(
                        c, ("property_identifier", "identifier")
                    )
                    if inner is not None:
                        name = _node_text(inner, source_bytes).strip()
                        emit(name, self._range_of(inner), _node_text(c, source_bytes).strip()[:120])
        return facts

    @staticmethod
    def _descendants_of_type_any(node, node_types: tuple[str, ...]) -> list:
        """Return all descendants of ``node`` whose type is in ``node_types``."""
        out: list = []
        stack = list(node.children)
        while stack:
            cur = stack.pop(0)
            if cur.type in node_types:
                out.append(cur)
            stack.extend(cur.children)
        return out

    def _range_of(self, node) -> TextRange:
        return TextRange(
            start_byte=node.start_byte,
            end_byte=node.end_byte,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )

    def _first_line(self, text: str) -> str:
        for line in text.splitlines():
            if line.strip():
                return line.strip()[:200]
        return ""

    def _dump_node(
        self,
        node,
        source_bytes: bytes,
        *,
        depth: int,
        max_depth: int,
        out: list[str],
        name_kinds: set[str],
    ) -> None:
        if depth > max_depth:
            return
        sp = node.start_point
        ep = node.end_point
        loc = f"[{sp[0] + 1}:{sp[1] + 1}-{ep[0] + 1}:{ep[1] + 1}]"
        name_str = ""
        try:
            named = node.child_by_field_name("name")
        except Exception:
            named = None
        if named is not None:
            name_str = f" name={_node_text(named, source_bytes).strip()}"
        elif name_kinds:
            for c in node.children:
                if c.type in name_kinds:
                    name_str = f" name={_node_text(c, source_bytes).strip()}"
                    break
        indent = "  " * depth
        out.append(f"{indent}{node.type} {loc}{name_str}")
        for child in node.children:
            self._dump_node(
                child, source_bytes,
                depth=depth + 1, max_depth=max_depth,
                out=out, name_kinds=name_kinds,
            )

    # -- Fallback regex extraction -----------------------------------------

    def _extract_fallback(
        self,
        source_file: SourceFile,
        profile: ProfileEntry,
        text: str,
        *,
        reason: str,
    ) -> ExtractedFile:
        symbols: list[Symbol] = []
        refs: list[SymbolRef] = []
        facts: list[SymbolFact] = []
        parse_errors: list[str] = [reason]
        # Milestone 4 (sql-extractor-temp-cte-fk): with no grammar available the
        # profile's generic definition regex would yield a bare
        # ``fallback_definition`` per CREATE TABLE and no columns or FKs at all.
        # Reuse the same segmenter the tree-sitter path uses for recovery so this
        # path produces a real ``create_table`` inventory with columns and FK
        # refs, then let the generic patterns cover views/procs/functions.
        sql_segments: list[_SqlTableSegment] = []
        if source_file.language == "sql":
            try:
                sql_segments = _sql_table_segments(text)
            except Exception as exc:  # pragma: no cover — fallback must not raise
                parse_errors.append(f"sql table segmentation error: {exc!r}")
            if sql_segments:
                s, r, f = self._sql_recovered_table_artifacts(
                    source_file, text, sql_segments
                )
                symbols.extend(s)
                refs.extend(r)
                facts.extend(f)
            # Out-of-line FK constraints, same as the tree-sitter path. Runs even
            # with no segments: the ALTER may sit in a constraints-only script
            # whose CREATE TABLEs live elsewhere.
            refs.extend(self._sql_alter_table_fk_refs(source_file, text, symbols))

        # SQL patterns are matched against a comment/string-masked copy (same
        # length and line breaks, so every offset below still indexes ``text``).
        # Otherwise prose in a header comment — "a bracketed CREATE TABLE that
        # also contains NOT NULL" — becomes a symbol named ``that``, and a
        # ``FROM`` inside a comment becomes a table reference.
        scan = _sql_mask_noncode(text) if source_file.language == "sql" else text

        # CR-08: `m.start()` / `m.end()` below are CHARACTER indices into
        # `text`, but `TextRange` carries BYTE offsets. Convert at every
        # TextRange construction in this method. `line_starts` and
        # `_offset_to_line` stay on character indices -- they index `text`
        # too, so converting them would break the line numbers instead.
        char_to_byte = _byte_offset_table(text)

        def to_byte(char_index: int) -> int:
            return char_index if char_to_byte is None else char_to_byte[char_index]

        try:
            line_starts = self._line_start_offsets(text)
            for pat in profile.fallback_patterns.definitions:
                try:
                    rgx = re.compile(pat, re.MULTILINE)
                except re.error as exc:
                    parse_errors.append(f"bad definition regex {pat!r}: {exc}")
                    continue
                for m in rgx.finditer(scan):
                    name = self._last_capture(m)
                    if not name:
                        continue
                    start = m.start()
                    end = m.end()
                    if source_file.language == "sql":
                        # A CREATE TABLE already recovered above (with its
                        # columns) must not also land as a bare duplicate.
                        if any(
                            seg.start_char <= start < seg.end_char
                            for seg in sql_segments
                        ):
                            continue
                        # Same normalization as the tree-sitter path so a
                        # bracketed/qualified view or procedure resolves.
                        name = _normalize_sql_identifier(name)
                        if not name:
                            continue
                    start_line = self._offset_to_line(line_starts, start)
                    end_line = self._offset_to_line(line_starts, max(end - 1, start))
                    rng = TextRange(
                        start_byte=to_byte(start), end_byte=to_byte(end),
                        start_line=start_line, end_line=end_line,
                    )
                    qualified = name
                    sym_id = (
                        f"{source_file.language}:{source_file.relative_path}:"
                        f"{qualified}:{start_line}"
                    )
                    symbols.append(
                        Symbol(
                            id=sym_id,
                            language=source_file.language,
                            name=name,
                            qualified_name=qualified,
                            kind="fallback_definition",
                            range=rng,
                            container=None,
                            signature=_line_text(text, start_line).strip()[:200],
                            # `other` by construction: the regex fallback fires
                            # only when tree-sitter parsing failed or is
                            # unavailable, so the real kind is genuinely
                            # unknown here (§S3.1.2). Promoting this later to
                            # anything more specific is an `ak2:` event.
                            entity_class="other",
                        )
                    )

            for pat in profile.fallback_patterns.calls:
                try:
                    rgx = re.compile(pat, re.MULTILINE | re.IGNORECASE)
                except re.error as exc:
                    parse_errors.append(f"bad call regex {pat!r}: {exc}")
                    continue
                for m in rgx.finditer(scan):
                    name = self._last_capture(m) or m.group(0).strip()
                    if source_file.language == "sql":
                        # ``FROM [dbo].[Customer]`` must resolve to the same bare
                        # name the recovered create_table symbol carries.
                        name = _normalize_sql_identifier(name)
                    if not name:
                        continue
                    start = m.start()
                    end = m.end()
                    start_line = self._offset_to_line(line_starts, start)
                    end_line = self._offset_to_line(line_starts, max(end - 1, start))
                    rng = TextRange(
                        start_byte=to_byte(start), end_byte=to_byte(end),
                        start_line=start_line, end_line=end_line,
                    )
                    ref_id = (
                        f"{source_file.language}:{source_file.relative_path}:ref:"
                        f"{name}:{start_line}:{start}"
                    )
                    refs.append(
                        SymbolRef(
                            id=ref_id,
                            language=source_file.language,
                            name=name,
                            kind="fallback_call",
                            range=rng,
                            enclosing_symbol_id=self._enclosing_symbol_for_line(
                                symbols, start_line
                            ),
                            evidence=_line_text(text, start_line).strip(),
                        )
                    )

            # Milestone 22: inheritance fallback (parse failure / no parser
            # only). Each pattern captures a comma-separated base-type list;
            # split it and emit one ref per base. Java's two-group pattern
            # yields the keyword (extends/implements) in group 1 so extends vs
            # implements is preserved; the single-list C#/Python/TS patterns
            # cannot tell them apart and emit inherits_or_implements.
            for pat in profile.fallback_patterns.inheritance:
                try:
                    rgx = re.compile(pat, re.MULTILINE)
                except re.error as exc:
                    parse_errors.append(f"bad inheritance regex {pat!r}: {exc}")
                    continue
                keyword_driven = rgx.groups >= 2
                for m in rgx.finditer(text):
                    if keyword_driven:
                        keyword = (m.group(1) or "").lower()
                        base_list = m.group(2) or ""
                        kind = "implements" if keyword == "implements" else "extends"
                    else:
                        base_list = self._last_capture(m)
                        kind = "inherits_or_implements"
                    if not base_list:
                        continue
                    start_line = self._offset_to_line(line_starts, m.start())
                    for raw in base_list.split(","):
                        base = raw.strip()
                        # Strip generic args and qualifiers to the plain name.
                        base = base.split("<", 1)[0].strip()
                        base = base.rsplit(".", 1)[-1].strip()
                        if not base or not re.match(r"^[A-Za-z_$]", base):
                            continue
                        rng = TextRange(
                            start_byte=to_byte(m.start()),
                            end_byte=to_byte(m.end()),
                            start_line=start_line, end_line=start_line,
                        )
                        ref_id = (
                            f"{source_file.language}:{source_file.relative_path}:ref:"
                            f"{base}:{start_line}:{m.start()}"
                        )
                        refs.append(
                            SymbolRef(
                                id=ref_id,
                                language=source_file.language,
                                name=base,
                                kind=kind,
                                range=rng,
                                enclosing_symbol_id=self._enclosing_symbol_for_line(
                                    symbols, start_line
                                ),
                                evidence=_line_text(text, start_line).strip(),
                            )
                        )
        except Exception as exc:  # pragma: no cover — fallback must never raise
            parse_errors.append(f"fallback extraction error: {exc!r}")

        # Dedupe symbols and refs by id (regex variants can overlap).
        symbols = self._dedupe_by_id(symbols)
        refs = self._dedupe_by_id(refs)
        facts = self._dedupe_by_id(facts)
        return ExtractedFile(
            symbols=symbols, refs=refs, parse_errors=parse_errors, facts=facts
        )

    @staticmethod
    def _last_capture(match: re.Match) -> str:
        groups = match.groups()
        for g in reversed(groups):
            if g:
                return g.strip()
        return ""

    @staticmethod
    def _line_start_offsets(text: str) -> list[int]:
        offsets = [0]
        for i, ch in enumerate(text):
            if ch == "\n":
                offsets.append(i + 1)
        return offsets

    @staticmethod
    def _offset_to_line(line_starts: list[int], offset: int) -> int:
        # Binary search for the largest start <= offset; line is 1-based.
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    @staticmethod
    def _enclosing_symbol_for_line(
        symbols: list[Symbol], line: int
    ) -> str | None:
        best: Symbol | None = None
        for s in symbols:
            if s.range.start_line <= line <= s.range.end_line:
                if best is None or (
                    s.range.start_line >= best.range.start_line
                    and s.range.end_line <= best.range.end_line
                ):
                    best = s
        return best.id if best else None

    @staticmethod
    def _dedupe_by_id(items: Iterable) -> list:
        seen: set[str] = set()
        out: list = []
        for it in items:
            if it.id in seen:
                continue
            seen.add(it.id)
            out.append(it)
        return out


__all__ = [
    "FallbackPatterns",
    "ProfileEntry",
    "ExtractorProfiles",
    "SymbolExtractor",
    "load_profiles",
    "get_profile",
]
