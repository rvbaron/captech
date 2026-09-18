"""Tests for extractor profile loading (Milestone 4, Agent A3) and the
full SymbolExtractor / fallback / dump-ast paths (Milestone 5, Agent B1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from legacylift_search.extractors import (
    ExtractorProfiles,
    SymbolExtractor,
    get_profile,
    load_profiles,
)
from legacylift_search.models import SourceFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "extractors.json"
FIXTURES = Path(__file__).parent / "fixtures" / "polyglot_repo"


def _load() -> ExtractorProfiles:
    return load_profiles(PROFILE_PATH)


def _source_file(rel: str, language: str) -> tuple[SourceFile, str]:
    path = FIXTURES / rel
    text = path.read_text(encoding="utf-8", errors="replace")
    sf = SourceFile(
        absolute_path=path.resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path=rel.replace("\\", "/"),
        language=language,
        size_bytes=len(text.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    return sf, text


# ---------------------------------------------------------------------------
# Loader-only tests (preserved from Agent A3)
# ---------------------------------------------------------------------------


def test_load_bundled_profiles():
    """Load the bundled extractors.json and verify all 7 languages are present."""
    assert PROFILE_PATH.exists(), f"Bundled profile not found at {PROFILE_PATH}"
    profiles = load_profiles(PROFILE_PATH)
    assert profiles.schema_version == 1
    required = {"csharp", "java", "python", "javascript", "typescript", "cobol", "sql"}
    assert set(profiles.profiles.keys()) == required
    csharp = profiles.profiles["csharp"]
    assert len(csharp.definition_node_kinds) > 0
    assert len(csharp.call_node_kinds) > 0
    assert len(csharp.fallback_patterns.definitions) > 0
    assert len(csharp.fallback_patterns.calls) > 0
    python = profiles.profiles["python"]
    assert "class_definition" in python.definition_node_kinds
    assert "function_definition" in python.definition_node_kinds
    assert "call" in python.call_node_kinds


def test_load_profiles_schema_version_mismatch(tmp_path: Path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 2, "profiles": {}}), encoding="utf-8")
    with pytest.raises(ValidationError) as exc_info:
        load_profiles(bad)
    assert "schema_version" in str(exc_info.value).lower()


def test_load_profiles_missing_languages(tmp_path: Path):
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profiles": {
                    "python": {
                        "definition_node_kinds": {"class_definition": "type"},
                        "call_node_kinds": ["call"],
                        "import_node_kinds": ["import_statement"],
                        "name_node_kinds": ["identifier"],
                        "container_node_kinds": ["class_definition"],
                        "fallback_patterns": {
                            "definitions": ["^\\s*class\\s+([A-Za-z_][A-Za-z0-9_]*)"],
                            "calls": ["([A-Za-z_][A-Za-z0-9_\\.]*?)\\s*\\("],
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError) as exc_info:
        load_profiles(incomplete)
    error_str = str(exc_info.value).lower()
    assert "missing" in error_str and "language" in error_str


def test_load_profiles_file_not_found(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_profiles(nonexistent)
    assert "not found" in str(exc_info.value).lower()
    assert str(nonexistent) in str(exc_info.value)


def test_get_profile():
    profiles = _load()
    python_profile = get_profile(profiles, "python")
    assert python_profile is not None
    assert "class_definition" in python_profile.definition_node_kinds
    assert get_profile(profiles, "nonexistent_language") is None


def test_fallback_patterns_structure():
    profiles = _load()
    cobol = profiles.profiles["cobol"]
    assert len(cobol.fallback_patterns.definitions) >= 3
    assert any("PROGRAM-ID" in p for p in cobol.fallback_patterns.definitions)
    assert any("PERFORM" in p for p in cobol.fallback_patterns.calls)
    sql = profiles.profiles["sql"]
    assert len(sql.fallback_patterns.definitions) >= 1
    assert any("CREATE" in p for p in sql.fallback_patterns.definitions)
    assert len(sql.fallback_patterns.calls) >= 4


# ---------------------------------------------------------------------------
# Per-language extraction (Milestone 5, Agent B1)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def extractor() -> SymbolExtractor:
    return SymbolExtractor(_load())


def _names(items) -> set[str]:
    return {x.name for x in items}


def _has_id_format(items, language: str, relative: str) -> bool:
    for it in items:
        if it.id.startswith(f"{language}:{relative}:"):
            return True
    return False


def test_extract_python(extractor: SymbolExtractor):
    sf, text = _source_file("src/eligibility.py", "python")
    result = extractor.extract(sf, text)
    assert any(s.name == "EligibilityService" for s in result.symbols)
    assert any(s.name == "check" for s in result.symbols)
    # Qualified name should include container nesting.
    assert any(
        s.qualified_name == "EligibilityService.check" for s in result.symbols
    )
    assert len(result.refs) >= 1
    # Symbol id format
    for s in result.symbols:
        parts = s.id.split(":")
        assert parts[0] == "python"
        assert parts[1] == "src/eligibility.py"


def test_extract_javascript(extractor: SymbolExtractor):
    sf, text = _source_file("src/reclaim.js", "javascript")
    result = extractor.extract(sf, text)
    assert any(s.name == "ReclaimService" for s in result.symbols)
    assert len(result.refs) >= 1


def test_extract_typescript(extractor: SymbolExtractor):
    sf, text = _source_file("src/enrollment.ts", "typescript")
    result = extractor.extract(sf, text)
    assert any(s.name == "EnrollmentService" for s in result.symbols)
    # processMember call OR push call
    assert len(result.refs) >= 1


def test_extract_java(extractor: SymbolExtractor):
    sf, text = _source_file("src/Demo.java", "java")
    result = extractor.extract(sf, text)
    assert any(s.name == "AccountService" for s in result.symbols)
    assert any(s.name == "verifyAccount" for s in result.symbols)
    # Method invocation reference should exist (e.g., processVerification, isEmpty)
    assert any(r.name in {"processVerification", "isEmpty", "length"} for r in result.refs)


def test_extract_csharp(extractor: SymbolExtractor):
    sf, text = _source_file("src/Demo.cs", "csharp")
    result = extractor.extract(sf, text)
    assert any(s.name == "CustomerService" for s in result.symbols)
    # Qualified name from namespace + class + method
    assert any(
        s.qualified_name == "Demo.Services.CustomerService.Validate"
        for s in result.symbols
    )
    assert len(result.refs) >= 1


def test_extract_sql(extractor: SymbolExtractor):
    sf, text = _source_file("database/schema.sql", "sql")
    result = extractor.extract(sf, text)
    # SQL may use tree-sitter or fallback. Either way we must see CREATE
    # definitions (TABLE/PROCEDURE) and at least one ref (FROM/JOIN/UPDATE/EXEC).
    assert len(result.symbols) >= 1, f"no SQL symbols extracted; errors={result.parse_errors}"
    assert len(result.refs) >= 1
    names = _names(result.symbols)
    assert any(
        n.lower() in {"providers", "members", "validate_provider", "log_validation",
                      "table", "view", "procedure", "function"}
        or n.lower().startswith("provider")
        or n.lower().startswith("member")
        or n.lower().startswith("validate_")
        or n.lower().startswith("log_")
        for n in names
    )


def test_extract_cobol_fallback(extractor: SymbolExtractor):
    sf, text = _source_file("mainframe/PROVIDER.cbl", "cobol")
    result = extractor.extract(sf, text)
    # COBOL has no tree-sitter grammar; fallback regex must produce results.
    assert len(result.symbols) >= 1
    assert len(result.refs) >= 1
    names = _names(result.symbols)
    # Should detect the PROGRAM-ID and at least one paragraph
    assert "PROVIDER" in names or any("PROVIDER" in n for n in names)
    # PERFORM and CALL references
    ref_names = _names(result.refs)
    assert any(n in {"VALIDATE-PROVIDER", "UPDATE-RECORDS", "ELIGIBILITY-CHECK",
                     "WRITE-DATABASE"}
               for n in ref_names)
    # Fallback should record a parse error noting fallback was used
    assert any("fallback" in e.lower() for e in result.parse_errors)


def test_extract_fallback_does_not_raise_on_malformed(extractor: SymbolExtractor):
    # A SourceFile pointing at nothing meaningful — text intentionally bizarre.
    sf = SourceFile(
        absolute_path=Path("/tmp/fake.cbl"),
        repo_root=Path("/tmp"),
        relative_path="fake.cbl",
        language="cobol",
        size_bytes=0,
        sha256="0" * 64,
        mtime_ns=0,
    )
    weird = "\x00\x01\x02 PERFORM ((( malformed source ]]] no terminator"
    result = extractor.extract(sf, weird)
    # Must not raise; result is a valid ExtractedFile.
    assert isinstance(result.symbols, list)
    assert isinstance(result.refs, list)


# ---------------------------------------------------------------------------
# Milestone 22: type-hierarchy (inherits / implements) reference extraction
# ---------------------------------------------------------------------------


def _inheritance_refs(result):
    return [
        r for r in result.refs
        if r.kind in {"extends", "implements", "inherits_or_implements"}
    ]


def test_extract_inheritance_csharp(extractor: SymbolExtractor):
    sf, text = _source_file("hierarchy/Shapes.cs", "csharp")
    result = extractor.extract(sf, text)
    inh = _inheritance_refs(result)
    names = {r.name for r in inh}
    # Bare base, in-repo interface, generic base (unwrapped), qualified base
    # (unwrapped to last segment), positional-record base, generic record base.
    assert {"Shape", "IShape", "IComparable", "IDisposable", "ShapeDto",
            "IEquatable"} <= names, names
    # C# base_list is syntactically ambiguous.
    assert all(r.kind == "inherits_or_implements" for r in inh)
    # Generic args and qualifiers are stripped to the plain name.
    assert "IComparable<Circle>" not in names
    assert "System.IDisposable" not in names
    # Regression: enum `ShapeKind : byte` underlying type is a predefined_type,
    # not a base-type reference — no hierarchy ref to `byte`.
    assert "byte" not in names
    # Subtype end comes from the enclosing definition's symbol id.
    circle_bases = [r for r in inh if r.name == "Shape"]
    assert circle_bases and circle_bases[0].enclosing_symbol_id is not None
    assert "Circle" in circle_bases[0].enclosing_symbol_id


def test_extract_inheritance_java(extractor: SymbolExtractor):
    sf, text = _source_file("hierarchy/Shapes.java", "java")
    result = extractor.extract(sf, text)
    inh = _inheritance_refs(result)
    by_name_kind = {(r.name, r.kind) for r in inh}
    # class Dog extends Animal (superclass -> extends) implements Drawable, Comparable<Dog>
    assert ("Animal", "extends") in by_name_kind
    assert ("Drawable", "implements") in by_name_kind
    assert ("Comparable", "implements") in by_name_kind  # generic unwrapped
    # interface Renderable extends Drawable, Serializable -> extends (inherits)
    assert ("Serializable", "extends") in by_name_kind


def test_extract_inheritance_python(extractor: SymbolExtractor):
    sf, text = _source_file("hierarchy/shapes.py", "python")
    result = extractor.extract(sf, text)
    inh = _inheritance_refs(result)
    names = {r.name for r in inh}
    assert {"Base", "Mixin"} <= names, names
    # Python has no interface concept; bases are `extends`.
    assert all(r.kind == "extends" for r in inh)
    # Standalone class has no bases -> contributes nothing.


def test_extract_inheritance_typescript(extractor: SymbolExtractor):
    sf, text = _source_file("hierarchy/shapes.ts", "typescript")
    result = extractor.extract(sf, text)
    inh = _inheritance_refs(result)
    by_name_kind = {(r.name, r.kind) for r in inh}
    # class Dog extends Animal implements Drawable, Serializable
    assert ("Animal", "extends") in by_name_kind
    assert ("Drawable", "implements") in by_name_kind
    assert ("Serializable", "implements") in by_name_kind
    # interface Renderable extends Drawable, Serializable -> extends
    assert ("Drawable", "extends") in by_name_kind


def test_inheritance_fallback_java_split_emit():
    """The regex fallback path (parse failure / no parser) splits a base list
    and preserves extends-vs-implements from Java's captured keyword."""
    profiles = _load()
    extractor = SymbolExtractor(profiles)
    # Force the fallback path directly with a Java-like snippet.
    sf = SourceFile(
        absolute_path=Path("/tmp/X.java"),
        repo_root=Path("/tmp"),
        relative_path="X.java",
        language="java",
        size_bytes=0,
        sha256="0" * 64,
        mtime_ns=0,
    )
    text = "class Foo extends Bar implements Baz, Qux {}\n"
    result = extractor._extract_fallback(
        sf, profiles.profiles["java"], text, reason="test"
    )
    inh = _inheritance_refs(result)
    by_name_kind = {(r.name, r.kind) for r in inh}
    assert ("Bar", "extends") in by_name_kind
    assert ("Baz", "implements") in by_name_kind
    assert ("Qux", "implements") in by_name_kind


def test_dump_ast_python_smoke(extractor: SymbolExtractor):
    out = extractor.dump_ast(
        FIXTURES / "src" / "eligibility.py",
        language_key=None,
        max_depth=4,
    )
    assert "function_definition" in out, out
    # Ranges look like [line:col-line:col]
    assert "[" in out and ":" in out and "-" in out


def test_dump_ast_cobol_no_parser(extractor: SymbolExtractor):
    # COBOL has no tree-sitter parser available; dump_ast must return a clear
    # message rather than crashing.
    out = extractor.dump_ast(
        FIXTURES / "mainframe" / "PROVIDER.cbl",
        language_key="cobol",
        max_depth=2,
    )
    assert "no tree-sitter parser" in out.lower() or "parser" in out.lower()


# ---------------------------------------------------------------------------
# entity_class declaration (Milestone 1 Step 2 of
# docs/exec-plans/active/reqs-to-data-store.md, NORMATIVE SPEC-3 §S3.1.2)
# ---------------------------------------------------------------------------


def test_every_definition_node_kind_declares_a_closed_entity_class():
    """Every entry (not just every distinct kind) in every profile's
    ``definition_node_kinds``, read from the bundled JSON at test time, must
    carry an explicit ``entity_class`` that is a member of the closed
    ``identity.ENTITY_CLASSES`` set.

    This is the assertion that fails the build when someone tunes extraction
    by adding a node kind to ``extractors.json`` — otherwise a silent re-key
    with no code review anywhere near it, because ``entity_class`` feeds
    ``identity.anchor_key`` and there is deliberately no ``entity_class_of(kind)``
    function anywhere to catch a missed one at runtime.

    Iterates entries, not distinct kinds: the same kind (e.g.
    ``class_declaration``) recurs across several language profiles, and the
    spec requires a class declared per entry, per language.
    """
    from legacylift_search.identity import ENTITY_CLASSES

    with open(PROFILE_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    entries_checked = 0
    for lang, profile in raw["profiles"].items():
        def_kinds = profile["definition_node_kinds"]
        assert isinstance(def_kinds, dict), (
            f"{lang}.definition_node_kinds must be a kind -> entity_class "
            f"dict, not a bare list of kinds"
        )
        for kind, entity_class in def_kinds.items():
            entries_checked += 1
            assert entity_class in ENTITY_CLASSES, (
                f"{lang}.definition_node_kinds[{kind!r}] declares "
                f"entity_class {entity_class!r}, which is not one of the "
                f"seven closed values {sorted(ENTITY_CLASSES)}"
            )

    # Measured against extractors.json on disk (see the ExecPlan): 52 entries
    # across seven language profiles. Not asserted as a hard equality here —
    # a future profile addition is legitimate — but recorded so a silent drop
    # is visible in a diff of this test rather than only in the plan's prose.
    assert entries_checked > 0


def test_definition_node_kinds_is_a_dict_not_a_parallel_list():
    """``definition_node_kinds`` is the single source for both the kind set
    and its entity_class, per the ExecPlan: "one source cannot drift from
    itself, and a sibling entity_classes object can hold a kind the list does
    not." There must be no such sibling key anywhere in the profile.
    """
    with open(PROFILE_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    for lang, profile in raw["profiles"].items():
        assert "entity_classes" not in profile, (
            f"{lang} profile has a sibling 'entity_classes' map; "
            f"definition_node_kinds must be the single kind -> class source"
        )


# ---------------------------------------------------------------------------
# CR-08: the regex fallback must emit BYTE offsets, not character indices
# ---------------------------------------------------------------------------
def test_fallback_emits_byte_offsets_not_character_indices(tmp_path: Path) -> None:
    """`CR-08`. `re` matches a `str`, so `m.start()` is a CHARACTER index,
    but `TextRange.start_byte`/`end_byte` are byte offsets into the
    extractors' byte space. Storing the character index there was inert
    while the bounds only drove chunking, and became a correctness bug in
    M1 Step 2: `store.symbol_body_text` slices `SourceText.byte_space` with
    them, and a character index is always <= the byte index, so its bounds
    guard still passes and it returns a SHIFTED body -- a stable but WRONG
    `content_hash`, with nothing raising.

    The file below puts ten non-ASCII characters ahead of the definition, so
    the two offsets differ by exactly ten bytes.
    """
    from legacylift_search.store import source_text, symbol_body_text

    text = "-- café " * 10 + "\nCREATE PROCEDURE dbo.DoThing AS BEGIN SELECT 1 END\n"
    raw = text.encode("utf-8")
    path = tmp_path / "p.sql"
    path.write_bytes(raw)
    assert len(raw) == len(text) + 10, "the fixture must not be pure ASCII"

    source = source_text(raw)
    sf = SourceFile(
        absolute_path=path.resolve(),
        repo_root=tmp_path.resolve(),
        relative_path="p.sql",
        language="sql",
        size_bytes=len(raw),
        sha256="0" * 64,
        mtime_ns=0,
    )
    extractor = SymbolExtractor(_load())
    # Drive the regex fallback directly: this is the path taken whenever a
    # grammar is unavailable or tree-sitter parsing failed.
    result = extractor._extract_fallback(
        sf, _load().profiles["sql"], source.text, reason="test: grammar unavailable"
    )

    fallbacks = [s for s in result.symbols if s.kind == "fallback_definition"]
    assert fallbacks, "the fixture must produce a fallback_definition"
    for symbol in fallbacks:
        body = symbol_body_text(
            source,
            symbol.range.start_byte,
            symbol.range.end_byte,
            symbol.range.start_line,
            symbol.range.end_line,
        )
        # The body recovered from the byte space must be the real definition,
        # not a slice shifted left by the preceding multi-byte characters.
        assert body is not None
        assert body.startswith("CREATE PROCEDURE"), body
        # And the bounds must genuinely be byte offsets into that space.
        assert (
            source.byte_space[
                symbol.range.start_byte : symbol.range.end_byte
            ].decode("utf-8")
            == body
        )


def test_fallback_offsets_are_unchanged_for_pure_ascii(tmp_path: Path) -> None:
    """The `CR-08` conversion is skipped for ASCII text, where the two
    offsets coincide. This pins that the fast path is still exact."""
    from legacylift_search.store import source_text, symbol_body_text

    text = "-- plain ascii header\nCREATE PROCEDURE dbo.DoThing AS BEGIN SELECT 1 END\n"
    raw = text.encode("utf-8")
    path = tmp_path / "a.sql"
    path.write_bytes(raw)
    source = source_text(raw)
    sf = SourceFile(
        absolute_path=path.resolve(),
        repo_root=tmp_path.resolve(),
        relative_path="a.sql",
        language="sql",
        size_bytes=len(raw),
        sha256="0" * 64,
        mtime_ns=0,
    )
    extractor = SymbolExtractor(_load())
    result = extractor._extract_fallback(
        sf, _load().profiles["sql"], source.text, reason="test"
    )
    fallbacks = [s for s in result.symbols if s.kind == "fallback_definition"]
    assert fallbacks
    for symbol in fallbacks:
        body = symbol_body_text(
            source,
            symbol.range.start_byte,
            symbol.range.end_byte,
            symbol.range.start_line,
            symbol.range.end_line,
        )
        assert body is not None and body.startswith("CREATE PROCEDURE"), body
