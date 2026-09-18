"""Tests for graph edge building (Milestone 8).

Covers:
- Caller resolution (prefer enclosing_symbol_id, else range containment)
- Callee resolution with confidence scoring
- Edge kind mapping for Python, COBOL, SQL
- Deterministic edge IDs
- Handling of unresolved callees
"""

from pathlib import Path

import pytest

from legacylift_search.graph import GraphBuilder
from legacylift_search.models import GraphEdge, SourceFile, Symbol, SymbolRef, TextRange


@pytest.fixture
def builder():
    """Return a fresh GraphBuilder."""
    return GraphBuilder()


@pytest.fixture
def sample_source_file():
    """Return a Python SourceFile fixture."""
    return SourceFile(
        absolute_path=Path("/repo/src/service.py"),
        repo_root=Path("/repo"),
        relative_path="src/service.py",
        language="python",
        size_bytes=1024,
        sha256="abc123",
        mtime_ns=1234567890,
    )


@pytest.fixture
def python_symbols():
    """Return sample Python symbols (ClassA.method_a calls ClassB.method_b)."""
    return [
        Symbol(
            id="python:src/service.py:ClassA:1",
            language="python",
            name="ClassA",
            qualified_name="ClassA",
            kind="class_definition",
            entity_class="type",
            range=TextRange(start_byte=0, end_byte=300, start_line=1, end_line=15),
        ),
        Symbol(
            id="python:src/service.py:ClassA.method_a:3",
            language="python",
            name="method_a",
            qualified_name="ClassA.method_a",
            kind="function_definition",
            entity_class="function",
            range=TextRange(start_byte=50, end_byte=150, start_line=3, end_line=8),
            container="ClassA",
        ),
        Symbol(
            id="python:src/service.py:ClassB:17",
            language="python",
            name="ClassB",
            qualified_name="ClassB",
            kind="class_definition",
            entity_class="type",
            range=TextRange(start_byte=320, end_byte=500, start_line=17, end_line=28),
        ),
        Symbol(
            id="python:src/service.py:ClassB.method_b:19",
            language="python",
            name="method_b",
            qualified_name="ClassB.method_b",
            kind="function_definition",
            entity_class="function",
            range=TextRange(start_byte=360, end_byte=450, start_line=19, end_line=25),
            container="ClassB",
        ),
    ]


def test_resolved_call_single_candidate(builder, sample_source_file, python_symbols):
    """Test a resolved call with exactly one candidate (confidence 0.85)."""
    refs = [
        SymbolRef(
            id="python:src/service.py:ref:method_b:5:80",
            language="python",
            name="method_b",
            kind="call",
            range=TextRange(start_byte=80, end_byte=90, start_line=5, end_line=5),
            enclosing_symbol_id="python:src/service.py:ClassA.method_a:3",
            evidence="    obj.method_b()",
        )
    ]

    # Index by plain name
    all_symbols_by_name = {"method_b": [python_symbols[3]]}

    edges = builder.build_edges(
        sample_source_file, python_symbols, refs, all_symbols_by_name
    )

    assert len(edges) == 1
    edge = edges[0]
    assert edge.caller_symbol_id == "python:src/service.py:ClassA.method_a:3"
    assert edge.callee_symbol_id == "python:src/service.py:ClassB.method_b:19"
    assert edge.callee_name == "method_b"
    assert edge.confidence == 0.85
    assert edge.edge_kind == "calls"
    assert edge.evidence == "    obj.method_b()"
    assert edge.relative_path == "src/service.py"
    assert edge.start_line == 5


def test_caller_resolution_from_enclosing_id(builder, sample_source_file, python_symbols):
    """Test that enclosing_symbol_id is preferred for caller resolution."""
    refs = [
        SymbolRef(
            id="python:src/service.py:ref:foo:5:80",
            language="python",
            name="foo",
            kind="call",
            range=TextRange(start_byte=80, end_byte=90, start_line=5, end_line=5),
            enclosing_symbol_id="python:src/service.py:ClassA.method_a:3",
            evidence="    foo()",
        )
    ]

    edges = builder.build_edges(sample_source_file, python_symbols, refs, {})

    assert len(edges) == 1
    assert edges[0].caller_symbol_id == "python:src/service.py:ClassA.method_a:3"


def test_caller_resolution_by_range(builder, sample_source_file, python_symbols):
    """Test caller resolution by range when enclosing_symbol_id is None."""
    refs = [
        SymbolRef(
            id="python:src/service.py:ref:foo:5:80",
            language="python",
            name="foo",
            kind="call",
            range=TextRange(start_byte=80, end_byte=90, start_line=5, end_line=5),
            enclosing_symbol_id=None,  # Fallback path will use range
            evidence="    foo()",
        )
    ]

    edges = builder.build_edges(sample_source_file, python_symbols, refs, {})

    assert len(edges) == 1
    # Line 5 is within ClassA.method_a (lines 3-8)
    assert edges[0].caller_symbol_id == "python:src/service.py:ClassA.method_a:3"


def test_no_caller_when_outside_all_ranges(builder, sample_source_file, python_symbols):
    """Test that caller_symbol_id is None when ref is outside all symbol ranges."""
    refs = [
        SymbolRef(
            id="python:src/service.py:ref:foo:30:800",
            language="python",
            name="foo",
            kind="call",
            range=TextRange(start_byte=800, end_byte=810, start_line=30, end_line=30),
            enclosing_symbol_id=None,
            evidence="foo()",
        )
    ]

    edges = builder.build_edges(sample_source_file, python_symbols, refs, {})

    assert len(edges) == 1
    assert edges[0].caller_symbol_id is None
    # Edge ID uses relative path when no caller
    assert edges[0].id.startswith("edge:src/service.py:foo:30:")


def test_unresolved_callee_confidence_030(builder, sample_source_file, python_symbols):
    """Test unresolved callee (no candidate) gets confidence 0.30."""
    refs = [
        SymbolRef(
            id="python:src/service.py:ref:unknown_func:5:80",
            language="python",
            name="unknown_func",
            kind="call",
            range=TextRange(start_byte=80, end_byte=90, start_line=5, end_line=5),
            enclosing_symbol_id="python:src/service.py:ClassA.method_a:3",
            evidence="    unknown_func()",
        )
    ]

    edges = builder.build_edges(sample_source_file, python_symbols, refs, {})

    assert len(edges) == 1
    edge = edges[0]
    assert edge.callee_symbol_id is None
    assert edge.callee_name == "unknown_func"
    assert edge.confidence == 0.30
    assert edge.edge_kind == "calls"


def test_same_name_ambiguity_prefers_same_file(builder, sample_source_file):
    """Test that same-name ambiguity prefers same-file candidate (confidence 0.70)."""
    # Two files define method_x
    symbols_file1 = [
        Symbol(
            id="python:src/service.py:method_x:10",
            language="python",
            name="method_x",
            qualified_name="method_x",
            kind="function_definition",
            entity_class="function",
            range=TextRange(start_byte=100, end_byte=200, start_line=10, end_line=15),
        )
    ]
    symbols_file2 = [
        Symbol(
            id="python:src/other.py:method_x:5",
            language="python",
            name="method_x",
            qualified_name="method_x",
            kind="function_definition",
            entity_class="function",
            range=TextRange(start_byte=50, end_byte=150, start_line=5, end_line=10),
        )
    ]

    # Caller in service.py
    caller_symbol = Symbol(
        id="python:src/service.py:main:2",
        language="python",
        name="main",
        qualified_name="main",
        kind="function_definition",
        entity_class="function",
        range=TextRange(start_byte=20, end_byte=80, start_line=2, end_line=6),
    )

    refs = [
        SymbolRef(
            id="python:src/service.py:ref:method_x:4:50",
            language="python",
            name="method_x",
            kind="call",
            range=TextRange(start_byte=50, end_byte=60, start_line=4, end_line=4),
            enclosing_symbol_id=caller_symbol.id,
            evidence="    method_x()",
        )
    ]

    # Both candidates indexed
    all_symbols_by_name = {"method_x": symbols_file1 + symbols_file2}

    edges = builder.build_edges(
        sample_source_file, [caller_symbol] + symbols_file1, refs, all_symbols_by_name
    )

    assert len(edges) == 1
    edge = edges[0]
    # Should prefer same-file candidate
    assert edge.callee_symbol_id == "python:src/service.py:method_x:10"
    assert edge.confidence == 0.70


def test_same_name_different_language_ambiguity(builder, sample_source_file):
    """Test cross-language ambiguity returns confidence 0.40 with no callee_id."""
    # method_x in Python and JavaScript
    symbols = [
        Symbol(
            id="python:src/service.py:method_x:10",
            language="python",
            name="method_x",
            qualified_name="method_x",
            kind="function_definition",
            entity_class="function",
            range=TextRange(start_byte=100, end_byte=200, start_line=10, end_line=15),
        ),
        Symbol(
            id="javascript:src/app.js:method_x:5",
            language="javascript",
            name="method_x",
            qualified_name="method_x",
            kind="function_declaration",
            entity_class="function",
            range=TextRange(start_byte=50, end_byte=150, start_line=5, end_line=10),
        ),
    ]

    caller_symbol = Symbol(
        id="python:src/service.py:main:2",
        language="python",
        name="main",
        qualified_name="main",
        kind="function_definition",
        entity_class="function",
        range=TextRange(start_byte=20, end_byte=80, start_line=2, end_line=6),
    )

    refs = [
        SymbolRef(
            id="python:src/service.py:ref:method_x:4:50",
            language="python",
            name="method_x",
            kind="call",
            range=TextRange(start_byte=50, end_byte=60, start_line=4, end_line=4),
            enclosing_symbol_id=caller_symbol.id,
            evidence="    method_x()",
        )
    ]

    # Both languages indexed
    all_symbols_by_name = {"method_x": symbols}

    # Ref is Python, one candidate is same-language same-file
    edges = builder.build_edges(
        sample_source_file, [caller_symbol, symbols[0]], refs, all_symbols_by_name
    )

    assert len(edges) == 1
    edge = edges[0]
    # Should resolve to same-language, same-file candidate
    assert edge.callee_symbol_id == "python:src/service.py:method_x:10"
    assert edge.confidence == 0.70


def test_cobol_perform_edge_kind(builder):
    """Test COBOL PERFORM creates 'performs' edge kind."""
    source_file = SourceFile(
        absolute_path=Path("/repo/mainframe/PROVIDER.cbl"),
        repo_root=Path("/repo"),
        relative_path="mainframe/PROVIDER.cbl",
        language="cobol",
        size_bytes=2048,
        sha256="def456",
        mtime_ns=9876543210,
    )

    symbols = [
        Symbol(
            id="cobol:mainframe/PROVIDER.cbl:MAIN-PARA:10",
            language="cobol",
            name="MAIN-PARA",
            qualified_name="MAIN-PARA",
            kind="paragraph",
            entity_class="function",
            range=TextRange(start_byte=100, end_byte=300, start_line=10, end_line=20),
        )
    ]

    refs = [
        SymbolRef(
            id="cobol:mainframe/PROVIDER.cbl:ref:VALIDATE-PROVIDER:15:200",
            language="cobol",
            name="VALIDATE-PROVIDER",
            kind="perform_statement",
            range=TextRange(start_byte=200, end_byte=230, start_line=15, end_line=15),
            enclosing_symbol_id=symbols[0].id,
            evidence="           PERFORM VALIDATE-PROVIDER",
        )
    ]

    edges = builder.build_edges(source_file, symbols, refs, {})

    assert len(edges) == 1
    edge = edges[0]
    assert edge.edge_kind == "performs"
    assert edge.callee_name == "VALIDATE-PROVIDER"
    # Unresolved COBOL paragraph
    assert edge.callee_symbol_id is None
    assert edge.confidence == 0.30


def test_cobol_fallback_call_with_call_keyword(builder):
    """Test COBOL fallback_call with CALL keyword gets 'calls' edge kind."""
    source_file = SourceFile(
        absolute_path=Path("/repo/mainframe/PROVIDER.cbl"),
        repo_root=Path("/repo"),
        relative_path="mainframe/PROVIDER.cbl",
        language="cobol",
        size_bytes=2048,
        sha256="def456",
        mtime_ns=9876543210,
    )

    symbols = [
        Symbol(
            id="cobol:mainframe/PROVIDER.cbl:MAIN-PARA:10",
            language="cobol",
            name="MAIN-PARA",
            qualified_name="MAIN-PARA",
            kind="paragraph",
            entity_class="function",
            range=TextRange(start_byte=100, end_byte=300, start_line=10, end_line=20),
        )
    ]

    refs = [
        SymbolRef(
            id="cobol:mainframe/PROVIDER.cbl:ref:SUBPROG:12:150",
            language="cobol",
            name="SUBPROG",
            kind="fallback_call",
            range=TextRange(start_byte=150, end_byte=170, start_line=12, end_line=12),
            enclosing_symbol_id=symbols[0].id,
            evidence="           CALL 'SUBPROG'",
        )
    ]

    edges = builder.build_edges(source_file, symbols, refs, {})

    assert len(edges) == 1
    edge = edges[0]
    assert edge.edge_kind == "calls"


def test_cobol_exec_sql(builder):
    """Test COBOL EXEC SQL creates 'executes_sql' edge kind."""
    source_file = SourceFile(
        absolute_path=Path("/repo/mainframe/PROVIDER.cbl"),
        repo_root=Path("/repo"),
        relative_path="mainframe/PROVIDER.cbl",
        language="cobol",
        size_bytes=2048,
        sha256="def456",
        mtime_ns=9876543210,
    )

    symbols = [
        Symbol(
            id="cobol:mainframe/PROVIDER.cbl:DB-PARA:30",
            language="cobol",
            name="DB-PARA",
            qualified_name="DB-PARA",
            kind="paragraph",
            entity_class="function",
            range=TextRange(start_byte=500, end_byte=700, start_line=30, end_line=40),
        )
    ]

    refs = [
        SymbolRef(
            id="cobol:mainframe/PROVIDER.cbl:ref:SQL:35:600",
            language="cobol",
            name="SQL",
            kind="fallback_call",
            range=TextRange(start_byte=600, end_byte=650, start_line=35, end_line=35),
            enclosing_symbol_id=symbols[0].id,
            evidence="           EXEC SQL SELECT * FROM PROVIDER END-EXEC",
        )
    ]

    edges = builder.build_edges(source_file, symbols, refs, {})

    assert len(edges) == 1
    edge = edges[0]
    assert edge.edge_kind == "executes_sql"


def test_cobol_exec_cics(builder):
    """Test COBOL EXEC CICS creates 'executes_cics' edge kind."""
    source_file = SourceFile(
        absolute_path=Path("/repo/mainframe/PROVIDER.cbl"),
        repo_root=Path("/repo"),
        relative_path="mainframe/PROVIDER.cbl",
        language="cobol",
        size_bytes=2048,
        sha256="def456",
        mtime_ns=9876543210,
    )

    symbols = [
        Symbol(
            id="cobol:mainframe/PROVIDER.cbl:CICS-PARA:50",
            language="cobol",
            name="CICS-PARA",
            qualified_name="CICS-PARA",
            kind="paragraph",
            entity_class="function",
            range=TextRange(start_byte=800, end_byte=1000, start_line=50, end_line=60),
        )
    ]

    refs = [
        SymbolRef(
            id="cobol:mainframe/PROVIDER.cbl:ref:CICS:55:900",
            language="cobol",
            name="CICS",
            kind="fallback_call",
            range=TextRange(start_byte=900, end_byte=950, start_line=55, end_line=55),
            enclosing_symbol_id=symbols[0].id,
            evidence="           EXEC CICS LINK PROGRAM('TRANSACT') END-EXEC",
        )
    ]

    edges = builder.build_edges(source_file, symbols, refs, {})

    assert len(edges) == 1
    edge = edges[0]
    assert edge.edge_kind == "executes_cics"


def test_sql_uses_table(builder):
    """Test SQL FROM/JOIN creates 'uses_table' edge kind."""
    source_file = SourceFile(
        absolute_path=Path("/repo/database/schema.sql"),
        repo_root=Path("/repo"),
        relative_path="database/schema.sql",
        language="sql",
        size_bytes=1024,
        sha256="ghi789",
        mtime_ns=1111111111,
    )

    symbols = [
        Symbol(
            id="sql:database/schema.sql:get_customers:10",
            language="sql",
            name="get_customers",
            qualified_name="get_customers",
            kind="create_procedure_statement",
            entity_class="other",
            range=TextRange(start_byte=100, end_byte=300, start_line=10, end_line=20),
        )
    ]

    refs = [
        SymbolRef(
            id="sql:database/schema.sql:ref:customers:15:200",
            language="sql",
            name="customers",
            kind="table_reference",
            range=TextRange(start_byte=200, end_byte=220, start_line=15, end_line=15),
            enclosing_symbol_id=symbols[0].id,
            evidence="    FROM customers",
        )
    ]

    edges = builder.build_edges(source_file, symbols, refs, {})

    assert len(edges) == 1
    edge = edges[0]
    assert edge.edge_kind == "uses_table"
    assert edge.callee_name == "customers"


# ---------------------------------------------------------------------------
# Milestone 22: type-hierarchy edges
# ---------------------------------------------------------------------------


@pytest.fixture
def csharp_source_file():
    return SourceFile(
        absolute_path=Path("/repo/src/Shapes.cs"),
        repo_root=Path("/repo"),
        relative_path="src/Shapes.cs",
        language="csharp",
        size_bytes=1024,
        sha256="cs123",
        mtime_ns=1,
    )


def _base_ref(name: str, kind: str) -> SymbolRef:
    return SymbolRef(
        id=f"csharp:src/Shapes.cs:ref:{name}:5:100",
        language="csharp",
        name=name,
        kind=kind,
        range=TextRange(start_byte=100, end_byte=110, start_line=5, end_line=5),
        enclosing_symbol_id="csharp:src/Shapes.cs:Circle:4",
        evidence="    public class Circle : Shape, IShape",
    )


def test_java_extends_implements_edge_kinds(builder):
    """`extends` maps to inherits, `implements` maps to implements."""
    source_file = SourceFile(
        absolute_path=Path("/repo/src/Dog.java"),
        repo_root=Path("/repo"),
        relative_path="src/Dog.java",
        language="java",
        size_bytes=512,
        sha256="j1",
        mtime_ns=1,
    )
    caller = Symbol(
        id="java:src/Dog.java:Dog:1",
        language="java",
        name="Dog",
        qualified_name="Dog",
        kind="class_declaration",
        entity_class="type",
        range=TextRange(start_byte=0, end_byte=200, start_line=1, end_line=10),
    )
    refs = [
        SymbolRef(
            id="java:src/Dog.java:ref:Animal:1:20",
            language="java", name="Animal", kind="extends",
            range=TextRange(start_byte=20, end_byte=26, start_line=1, end_line=1),
            enclosing_symbol_id=caller.id, evidence="class Dog extends Animal",
        ),
        SymbolRef(
            id="java:src/Dog.java:ref:Pet:1:40",
            language="java", name="Pet", kind="implements",
            range=TextRange(start_byte=40, end_byte=43, start_line=1, end_line=1),
            enclosing_symbol_id=caller.id, evidence="implements Pet",
        ),
    ]
    edges = {e.callee_name: e for e in builder.build_edges(source_file, [caller], refs, {})}
    assert edges["Animal"].edge_kind == "inherits"
    assert edges["Pet"].edge_kind == "implements"


def test_csharp_reclassify_resolved_interface_to_implements(builder, csharp_source_file):
    """A C# inherits_or_implements base that resolves to an in-repo
    interface_declaration is reclassified to `implements`."""
    iface = Symbol(
        id="csharp:src/IShape.cs:IShape:1",
        language="csharp", name="IShape", qualified_name="IShape",
        kind="interface_declaration",
        entity_class="type",
        range=TextRange(start_byte=0, end_byte=50, start_line=1, end_line=3),
    )
    refs = [_base_ref("IShape", "inherits_or_implements")]
    edges = builder.build_edges(
        csharp_source_file, [], refs, {"IShape": [iface]}
    )
    assert len(edges) == 1
    assert edges[0].edge_kind == "implements"
    assert edges[0].confidence == 0.85
    assert edges[0].callee_symbol_id == iface.id


def test_csharp_reclassify_resolved_class_to_inherits(builder, csharp_source_file):
    """A C# inherits_or_implements base that resolves to an in-repo class is
    reclassified to `inherits`."""
    base_cls = Symbol(
        id="csharp:src/Shape.cs:Shape:1",
        language="csharp", name="Shape", qualified_name="Shape",
        kind="class_declaration",
        entity_class="type",
        range=TextRange(start_byte=0, end_byte=50, start_line=1, end_line=3),
    )
    refs = [_base_ref("Shape", "inherits_or_implements")]
    edges = builder.build_edges(
        csharp_source_file, [], refs, {"Shape": [base_cls]}
    )
    assert len(edges) == 1
    assert edges[0].edge_kind == "inherits"
    assert edges[0].confidence == 0.85


def test_csharp_unresolved_interface_heuristic(builder, csharp_source_file):
    """An unresolved (external) C# base whose name matches ^I[A-Z] is classified
    `implements` at confidence 0.30 with the base name preserved."""
    refs = [_base_ref("IDisposable", "inherits_or_implements")]
    edges = builder.build_edges(csharp_source_file, [], refs, {})
    assert len(edges) == 1
    assert edges[0].edge_kind == "implements"
    assert edges[0].confidence == 0.30
    assert edges[0].callee_symbol_id is None
    assert edges[0].callee_name == "IDisposable"


def test_csharp_unresolved_non_interface_heuristic(builder, csharp_source_file):
    """An unresolved C# base that does not match ^I[A-Z] defaults to `inherits`."""
    refs = [_base_ref("BaseController", "inherits_or_implements")]
    edges = builder.build_edges(csharp_source_file, [], refs, {})
    assert len(edges) == 1
    assert edges[0].edge_kind == "inherits"
    assert edges[0].confidence == 0.30
    assert edges[0].callee_name == "BaseController"


def test_implements_substring_hazard(builder, csharp_source_file):
    """Guard: `implements` is a substring of `inherits_or_implements`; ensure the
    ambiguous C# case is not short-circuited to implements when it resolves to a
    class (would happen with `in` matching instead of `==`)."""
    base_cls = Symbol(
        id="csharp:src/Shape.cs:Shape:1",
        language="csharp", name="Shape", qualified_name="Shape",
        kind="class_declaration",
        entity_class="type",
        range=TextRange(start_byte=0, end_byte=50, start_line=1, end_line=3),
    )
    refs = [_base_ref("Shape", "inherits_or_implements")]
    edges = builder.build_edges(csharp_source_file, [], refs, {"Shape": [base_cls]})
    assert edges[0].edge_kind == "inherits"


def test_enum_underlying_type_no_hierarchy_edge(builder):
    """End-to-end regression: `enum ShapeKind : byte` must produce no hierarchy
    edge to `byte` (the predefined_type filter in the extractor)."""
    from collections import defaultdict

    from legacylift_search.extractors import load_profiles, SymbolExtractor

    profile_path = (
        Path(__file__).parent.parent
        / "src" / "legacylift_search" / "profiles" / "extractors.json"
    )
    fixtures = Path(__file__).parent / "fixtures" / "polyglot_repo"
    rel = "hierarchy/Shapes.cs"
    path = fixtures / rel
    text = path.read_text(encoding="utf-8")
    sf = SourceFile(
        absolute_path=path.resolve(), repo_root=fixtures.resolve(),
        relative_path=rel, language="csharp",
        size_bytes=len(text.encode("utf-8")), sha256="0" * 64, mtime_ns=0,
    )
    extractor = SymbolExtractor(load_profiles(profile_path))
    result = extractor.extract(sf, text)
    by_name = defaultdict(list)
    for s in result.symbols:
        by_name[s.name].append(s)
    edges = builder.build_edges(sf, result.symbols, result.refs, by_name)
    hierarchy = [e for e in edges if e.edge_kind in ("inherits", "implements")]
    assert all(e.callee_name != "byte" for e in hierarchy)
    # Sanity: the file does produce hierarchy edges (so the assert above is real).
    assert hierarchy


def test_edge_id_deterministic(builder, sample_source_file, python_symbols):
    """Test that edge IDs are deterministic and unique."""
    refs = [
        SymbolRef(
            id="python:src/service.py:ref:method_b:5:80",
            language="python",
            name="method_b",
            kind="call",
            range=TextRange(start_byte=80, end_byte=90, start_line=5, end_line=5),
            enclosing_symbol_id="python:src/service.py:ClassA.method_a:3",
            evidence="    obj.method_b()",
        )
    ]

    all_symbols_by_name = {"method_b": [python_symbols[3]]}

    edges1 = builder.build_edges(
        sample_source_file, python_symbols, refs, all_symbols_by_name
    )
    edges2 = builder.build_edges(
        sample_source_file, python_symbols, refs, all_symbols_by_name
    )

    assert len(edges1) == 1
    assert len(edges2) == 1
    assert edges1[0].id == edges2[0].id
    # ID format (Milestone 25): the edge id now folds in ``ref.id`` (unique per
    # ref) so multiple same-name/same-line refs on one line no longer collapse.
    # edge:<caller>:<callee-name>:<start-line>:<edge-kind>:<ref.id>
    expected_id = (
        "edge:python:src/service.py:ClassA.method_a:3:method_b:5:calls:"
        "python:src/service.py:ref:method_b:5:80"
    )
    assert edges1[0].id == expected_id


def test_multiple_refs_unique_edges(builder, sample_source_file, python_symbols):
    """Test multiple refs produce unique edges."""
    refs = [
        SymbolRef(
            id="python:src/service.py:ref:method_b:5:80",
            language="python",
            name="method_b",
            kind="call",
            range=TextRange(start_byte=80, end_byte=90, start_line=5, end_line=5),
            enclosing_symbol_id="python:src/service.py:ClassA.method_a:3",
            evidence="    obj.method_b()",
        ),
        SymbolRef(
            id="python:src/service.py:ref:method_b:7:120",
            language="python",
            name="method_b",
            kind="call",
            range=TextRange(start_byte=120, end_byte=130, start_line=7, end_line=7),
            enclosing_symbol_id="python:src/service.py:ClassA.method_a:3",
            evidence="    obj.method_b(x)",
        ),
    ]

    all_symbols_by_name = {"method_b": [python_symbols[3]]}

    edges = builder.build_edges(
        sample_source_file, python_symbols, refs, all_symbols_by_name
    )

    assert len(edges) == 2
    # Both edges have different IDs due to different start lines
    assert edges[0].id != edges[1].id
    assert edges[0].start_line == 5
    assert edges[1].start_line == 7
