"""Milestone 25: field/property type references + method signatures.

Covers (all deliverables of M25):
1. ``has_field_of_type`` (field/property) and ``accepts_dto`` / ``returns_dto``
   (method param / return) edges resolving for a controller -> DTO path.
2. Enum members captured as ``has_enum_value`` facts, including a single-line
   enum proving the id ``object`` segment prevents collapse.
3. Java ``throws`` -> ``throws`` fact.
4. Inner-generic unwrap: ``ActionResult<ClaimDto>`` resolves ``ClaimDto`` (the
   inner payload), never ``ActionResult`` (the M22 outer name).
5. Primitive filter: ``int`` / ``string`` / ``void`` produce NO type-ref edges.
6. Edge-id collision: ``void Save(Claim a, Claim b)`` (two same-type params on
   one line) produces TWO edges, not one (per-edge-kind, distinct edge ids).
7. ``--edge-kind`` traversal filter on both the store methods and the CLI
   commands (including the ``callers`` inline unresolved-by-name fallback path).
8. Regression guard for the shared edge-id widening (M22 hierarchy edges).

Extraction tests use inline source (mirroring test_m24_sql.py's ``_extract_text``
pattern) so they add no polyglot-fixture files and do not perturb the discovery
file count.
"""

from __future__ import annotations

import tracemalloc
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.extractors import (
    SymbolExtractor,
    _base_type_name,
    _inner_type_name,
    load_profiles,
)
from legacylift_search.graph import GraphBuilder
from legacylift_search.models import GraphEdge, SourceFile, Symbol, TextRange
from legacylift_search.store import SQLiteStore

PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "extractors.json"
FIXTURES = Path(__file__).parent / "fixtures" / "polyglot_repo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extractor() -> SymbolExtractor:
    return SymbolExtractor(load_profiles(PROFILE_PATH))


def _extract(text: str, language: str, rel: str):
    sf = SourceFile(
        absolute_path=(FIXTURES / rel).resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path=rel,
        language=language,
        size_bytes=len(text.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    return sf, _extractor().extract(sf, text)


def _edges(sf, result):
    by_name: dict[str, list] = {}
    for s in result.symbols:
        by_name.setdefault(s.name, []).append(s)
    return GraphBuilder().build_edges(sf, result.symbols, result.refs, by_name)


_CSHARP_CONTROLLER = """namespace Demo.Api
{
    public enum Status { Open, Closed, Void }

    public class Provider { public int Id { get; set; } }
    public class LineItem { public int Id { get; set; } }
    public class ClaimDto { public int Id { get; set; } }
    public class ClaimFilter { public int Page { get; set; } }

    public class Claim
    {
        public int Id { get; set; }
        public Provider Provider { get; set; }
        public List<LineItem> Items { get; set; }
    }

    public class ClaimsController
    {
        public ActionResult<ClaimDto> GetClaim(int id, ClaimFilter filter)
        {
            return null;
        }

        public void Save(Claim a, Claim b)
        {
        }

        public string Describe(int count)
        {
            return null;
        }
    }
}
"""


# ---------------------------------------------------------------------------
# Inner-generic unwrap helper (distinct from _base_type_name)
# ---------------------------------------------------------------------------


def test_inner_type_name_is_distinct_from_base_type_name() -> None:
    """``ActionResult<ClaimDto>``: _base_type_name -> outer (ActionResult),
    _inner_type_name -> inner payload (ClaimDto)."""
    src = "class C { public ActionResult<ClaimDto> M() { return null; } }"
    lang = __import__(
        "legacylift_search.languages", fromlist=["get_language"]
    ).get_language("csharp")
    from legacylift_search.extractors import _get_parser_for

    parser, _ = _get_parser_for(lang)
    b = src.encode()
    tree = parser.parse(b)

    def find(node, t):
        if node.type == t:
            return node
        for c in node.children:
            r = find(c, t)
            if r is not None:
                return r
        return None

    gen = find(tree.root_node, "generic_name")
    assert gen is not None
    assert _base_type_name(gen, b) == "ActionResult"  # outer (M22)
    assert _inner_type_name(gen, b) == "ClaimDto"  # inner payload (M25)


# ---------------------------------------------------------------------------
# 1. Controller -> DTO edges (has_field_of_type / accepts_dto / returns_dto)
# ---------------------------------------------------------------------------


def test_field_property_and_signature_edges_resolve() -> None:
    sf, result = _extract(_CSHARP_CONTROLLER, "csharp", "Controller.cs")
    edges = _edges(sf, result)

    def names(kind: str) -> set[str]:
        return {e.callee_name for e in edges if e.edge_kind == kind}

    # Field/property types -> has_field_of_type (Provider, and List<LineItem>
    # unwrapped to LineItem).
    assert "Provider" in names("has_field_of_type")
    assert "LineItem" in names("has_field_of_type")

    # Method param types -> accepts_dto; return types -> returns_dto.
    assert "ClaimFilter" in names("accepts_dto")
    assert "Claim" in names("accepts_dto")
    assert "ClaimDto" in names("returns_dto")

    # The DTO edges resolve to a real symbol (not left unresolved).
    dto_edges = [
        e for e in edges
        if e.edge_kind in ("has_field_of_type", "accepts_dto", "returns_dto")
        and e.callee_name in ("Provider", "LineItem", "ClaimFilter", "ClaimDto")
    ]
    assert dto_edges
    assert all(e.callee_symbol_id is not None for e in dto_edges)


# ---------------------------------------------------------------------------
# 4. Inner-generic unwrap end-to-end
# ---------------------------------------------------------------------------


def test_inner_generic_unwrap_resolves_inner_payload() -> None:
    sf, result = _extract(_CSHARP_CONTROLLER, "csharp", "Controller.cs")
    edges = _edges(sf, result)
    returns = {e.callee_name for e in edges if e.edge_kind == "returns_dto"}
    # ActionResult<ClaimDto> -> ClaimDto (inner), NOT ActionResult (outer).
    assert "ClaimDto" in returns
    assert "ActionResult" not in returns
    assert not any(r.name == "ActionResult" for r in result.refs
                   if r.kind == "returns_dto")


# ---------------------------------------------------------------------------
# 5. Primitive / builtin filter
# ---------------------------------------------------------------------------


def test_primitives_produce_no_type_ref_edges() -> None:
    sf, result = _extract(_CSHARP_CONTROLLER, "csharp", "Controller.cs")
    edges = _edges(sf, result)
    m25_kinds = {"has_field_of_type", "accepts_dto", "returns_dto"}
    banned = {"int", "string", "void", "decimal", "bool", "object"}
    for e in edges:
        if e.edge_kind in m25_kinds:
            assert e.callee_name not in banned, (
                f"primitive {e.callee_name!r} leaked as {e.edge_kind}"
            )
    for r in result.refs:
        if r.kind in m25_kinds:
            assert r.name not in banned


# ---------------------------------------------------------------------------
# 6. Edge-id collision: two same-type params on one line -> two edges
# ---------------------------------------------------------------------------


def test_two_same_type_params_produce_two_edges() -> None:
    sf, result = _extract(_CSHARP_CONTROLLER, "csharp", "Controller.cs")
    edges = _edges(sf, result)
    claim_params = [
        e for e in edges
        if e.edge_kind == "accepts_dto" and e.callee_name == "Claim"
    ]
    # void Save(Claim a, Claim b) -> two accepts_dto refs on the same line, same
    # kind, same name. Without folding ref.id into the edge id they collapse to
    # one edge on upsert; the fix makes their ids distinct.
    assert len(claim_params) == 2
    assert len({e.id for e in claim_params}) == 2


# ---------------------------------------------------------------------------
# 2. Enum values -> has_enum_value facts (single-line collapse guard)
# ---------------------------------------------------------------------------


def test_enum_values_captured_singleline_no_collapse() -> None:
    _sf, result = _extract(_CSHARP_CONTROLLER, "csharp", "Controller.cs")
    enum_facts = [f for f in result.facts if f.predicate == "has_enum_value"]
    values = {f.object for f in enum_facts}
    assert values == {"Open", "Closed", "Void"}
    # Single-line enum: same subject/predicate/start_line, three facts, and the
    # id ``object`` segment keeps them distinct (no collapse to one).
    assert len({f.id for f in enum_facts}) == 3
    assert len({f.start_line for f in enum_facts}) == 1
    for f in enum_facts:
        assert f.confidence == 1.0
        assert f.evidence


def test_ts_enum_values_captured() -> None:
    src = "enum Status { Open, Closed }\n"
    _sf, result = _extract(src, "typescript", "status.ts")
    values = {f.object for f in result.facts if f.predicate == "has_enum_value"}
    assert values == {"Open", "Closed"}


# ---------------------------------------------------------------------------
# 3. Java throws -> throws fact
# ---------------------------------------------------------------------------


def test_java_throws_fact() -> None:
    src = (
        "public class OrderService {\n"
        "    public List<Claim> findClaims(ClaimFilter filter, int page)\n"
        "            throws IOException, SQLException {\n"
        "        return null;\n"
        "    }\n"
        "}\n"
    )
    _sf, result = _extract(src, "java", "OrderService.java")
    throws = {f.object for f in result.facts if f.predicate == "throws"}
    assert throws == {"IOException", "SQLException"}
    # Multi-valued on one line: distinct ids (object segment).
    tf = [f for f in result.facts if f.predicate == "throws"]
    assert len({f.id for f in tf}) == 2
    # Signature refs also fire for Java (return List<Claim> -> Claim inner).
    edges = _edges(_sf, result)
    assert "ClaimFilter" in {e.callee_name for e in edges if e.edge_kind == "accepts_dto"}
    assert "Claim" in {e.callee_name for e in edges if e.edge_kind == "returns_dto"}


def test_python_and_ts_signature_refs() -> None:
    py = (
        "class Service:\n"
        "    def find(self, filter: ClaimFilter, page: int) -> ClaimDto:\n"
        "        return None\n"
    )
    _sf, result = _extract(py, "python", "svc.py")
    kinds = {(r.kind, r.name) for r in result.refs}
    assert ("accepts_dto", "ClaimFilter") in kinds
    assert ("returns_dto", "ClaimDto") in kinds
    assert ("accepts_dto", "int") not in kinds  # primitive filtered

    ts = (
        "class Service {\n"
        "    find(filter: ClaimFilter, page: number): ClaimDto { return null; }\n"
        "}\n"
    )
    _sf2, result2 = _extract(ts, "typescript", "svc.ts")
    kinds2 = {(r.kind, r.name) for r in result2.refs}
    assert ("accepts_dto", "ClaimFilter") in kinds2
    assert ("returns_dto", "ClaimDto") in kinds2
    assert ("accepts_dto", "number") not in kinds2  # primitive filtered


# ---------------------------------------------------------------------------
# 7. --edge-kind filter: store methods
# ---------------------------------------------------------------------------


@pytest.fixture
def store_with_mixed_edges(tmp_path):
    """A store with a caller X and callee Y linked by both a ``calls`` edge and
    a ``returns_dto`` / ``has_field_of_type`` edge, for edge-kind filtering."""
    db = tmp_path / "index.sqlite"
    store = SQLiteStore(db)
    store.migrate()
    repo_root = Path("/fake/repo")
    sf = SourceFile(
        absolute_path=repo_root / "src/a.cs",
        repo_root=repo_root,
        relative_path="src/a.cs",
        language="csharp",
        size_bytes=100,
        sha256="a" * 64,
        mtime_ns=0,
    )
    store.upsert_files([sf])
    x = Symbol(
        id="csharp:src/a.cs:X:1", language="csharp", name="X",
        qualified_name="X", kind="method_declaration",
        entity_class="function",
        range=TextRange(start_byte=0, end_byte=10, start_line=1, end_line=5),
    )
    y = Symbol(
        id="csharp:src/a.cs:Y:10", language="csharp", name="Y",
        qualified_name="Y", kind="class_declaration",
        entity_class="type",
        range=TextRange(start_byte=20, end_byte=30, start_line=10, end_line=15),
    )
    store.upsert_symbols(sf, [x, y])
    edges = [
        GraphEdge(
            id="edge:X:Y:2:calls:r1", caller_symbol_id=x.id,
            callee_symbol_id=y.id, callee_name="Y", edge_kind="calls",
            confidence=0.85, evidence="Y()", source_ref_id=None,
            relative_path="src/a.cs", start_line=2,
        ),
        GraphEdge(
            id="edge:X:Y:3:returns_dto:r2", caller_symbol_id=x.id,
            callee_symbol_id=y.id, callee_name="Y", edge_kind="returns_dto",
            confidence=0.85, evidence="Y M()", source_ref_id=None,
            relative_path="src/a.cs", start_line=3,
        ),
    ]
    store.upsert_edges(edges)
    yield store, x, y
    store.close()


def test_store_callees_edge_kind_filter(store_with_mixed_edges) -> None:
    store, x, y = store_with_mixed_edges
    # Default None -> all kinds.
    all_kinds = {e.edge_kind for e in store.callees(x.id, depth=1)}
    assert all_kinds == {"calls", "returns_dto"}
    # Filtered -> only calls, excludes returns_dto.
    filtered = store.callees(x.id, depth=1, edge_kinds=["calls"])
    assert {e.edge_kind for e in filtered} == {"calls"}


def test_store_callers_edge_kind_filter(store_with_mixed_edges) -> None:
    store, x, y = store_with_mixed_edges
    all_kinds = {e.edge_kind for e in store.callers(y.id, depth=1)}
    assert all_kinds == {"calls", "returns_dto"}
    filtered = store.callers(y.id, depth=1, edge_kinds=["calls"])
    assert {e.edge_kind for e in filtered} == {"calls"}


# ---------------------------------------------------------------------------
# 7. --edge-kind filter: CLI (callees, and callers inline-fallback path)
# ---------------------------------------------------------------------------


def _cli_index_dir(tmp_path):
    """Build a store at ``<dir>/index.sqlite`` for CLI --index-dir resolution."""
    d = tmp_path / "idx"
    d.mkdir()
    return d, d / "index.sqlite"


def test_cli_callees_edge_kind_filter(tmp_path) -> None:
    d, db = _cli_index_dir(tmp_path)
    store = SQLiteStore(db)
    store.migrate()
    repo_root = Path("/fake/repo")
    sf = SourceFile(
        absolute_path=repo_root / "a.cs", repo_root=repo_root,
        relative_path="a.cs", language="csharp", size_bytes=1,
        sha256="a" * 64, mtime_ns=0,
    )
    store.upsert_files([sf])
    x = Symbol(id="csharp:a.cs:X:1", language="csharp", name="X",
               qualified_name="X", kind="method_declaration",
               entity_class="function",
               range=TextRange(start_byte=0, end_byte=1, start_line=1, end_line=1))
    y = Symbol(id="csharp:a.cs:Y:2", language="csharp", name="Y",
               qualified_name="Y", kind="class_declaration",
               entity_class="type",
               range=TextRange(start_byte=2, end_byte=3, start_line=2, end_line=2))
    store.upsert_symbols(sf, [x, y])
    store.upsert_edges([
        GraphEdge(id="e1", caller_symbol_id=x.id, callee_symbol_id=y.id,
                  callee_name="Y", edge_kind="calls", confidence=0.9,
                  evidence="Y()", source_ref_id=None, relative_path="a.cs",
                  start_line=1),
        GraphEdge(id="e2", caller_symbol_id=x.id, callee_symbol_id=y.id,
                  callee_name="Y", edge_kind="returns_dto", confidence=0.9,
                  evidence="Y M()", source_ref_id=None, relative_path="a.cs",
                  start_line=1),
    ])
    store.close()

    runner = CliRunner()
    # Without the flag: both kinds render.
    res_all = runner.invoke(app, ["callees", x.id, "--index-dir", str(d)])
    assert res_all.exit_code == 0, res_all.output
    assert "calls" in res_all.output and "returns_dto" in res_all.output
    # With --edge-kind calls: returns_dto excluded.
    res = runner.invoke(
        app, ["callees", x.id, "--index-dir", str(d), "--edge-kind", "calls"]
    )
    assert res.exit_code == 0, res.output
    assert "calls" in res.output
    assert "returns_dto" not in res.output


def test_cli_callers_edge_kind_filter_inline_fallback(tmp_path) -> None:
    """The callers command's inline unresolved-by-name fallback SELECT must also
    honor --edge-kind, or type-association edges leak through it."""
    d, db = _cli_index_dir(tmp_path)
    store = SQLiteStore(db)
    store.migrate()
    repo_root = Path("/fake/repo")
    sf = SourceFile(
        absolute_path=repo_root / "a.cs", repo_root=repo_root,
        relative_path="a.cs", language="csharp", size_bytes=1,
        sha256="a" * 64, mtime_ns=0,
    )
    store.upsert_files([sf])
    # Target symbol Foo with NO resolved incoming edges (so store.callers is
    # empty and the inline fallback path runs), but two unresolved-by-name
    # edges pointing at "Foo" with different kinds.
    foo = Symbol(id="csharp:a.cs:Foo:1", language="csharp", name="Foo",
                 qualified_name="Foo", kind="class_declaration",
                 entity_class="type",
                 range=TextRange(start_byte=0, end_byte=1, start_line=1, end_line=1))
    store.upsert_symbols(sf, [foo])
    store.upsert_edges([
        GraphEdge(id="u1", caller_symbol_id=None, callee_symbol_id=None,
                  callee_name="Foo", edge_kind="calls", confidence=0.30,
                  evidence="Foo()", source_ref_id=None, relative_path="a.cs",
                  start_line=5),
        GraphEdge(id="u2", caller_symbol_id=None, callee_symbol_id=None,
                  callee_name="Foo", edge_kind="associates", confidence=0.30,
                  evidence="Foo field", source_ref_id=None, relative_path="a.cs",
                  start_line=6),
    ])
    store.close()

    runner = CliRunner()
    # No flag -> fallback returns both kinds.
    res_all = runner.invoke(app, ["callers", foo.id, "--index-dir", str(d)])
    assert res_all.exit_code == 0, res_all.output
    assert "calls" in res_all.output and "associates" in res_all.output
    # --edge-kind calls -> the associates edge must NOT leak through the fallback.
    res = runner.invoke(
        app, ["callers", foo.id, "--index-dir", str(d), "--edge-kind", "calls"]
    )
    assert res.exit_code == 0, res.output
    assert "calls" in res.output
    assert "associates" not in res.output


# ---------------------------------------------------------------------------
# 8. Regression: shared edge-id widening is a no-op for M22 hierarchy edges
# ---------------------------------------------------------------------------


def test_hierarchy_edge_ids_unique_after_widening() -> None:
    """The edge-id widening (folding ref.id) must not collapse or duplicate M22
    hierarchy edges — a C# class hierarchy still yields one edge per base with a
    unique id."""
    src = (
        "public interface IShape { }\n"
        "public class Shape : IShape { }\n"
        "public class Circle : Shape, IShape { }\n"
    )
    sf, result = _extract(src, "csharp", "Shapes.cs")
    edges = _edges(sf, result)
    hierarchy = [e for e in edges if e.edge_kind in ("inherits", "implements")]
    assert hierarchy, "expected hierarchy edges"
    # Every hierarchy edge id is unique (no collapse); the ref.id suffix keeps
    # Circle's two bases (Shape, IShape) distinct even on one line.
    assert len({e.id for e in hierarchy}) == len(hierarchy)


# ---------------------------------------------------------------------------
# Perf/memory instrumentation hook (proves the at-scale measurement mechanism)
# ---------------------------------------------------------------------------


def test_graph_build_tracemalloc_hook() -> None:
    """Trivial in-test proof that ``tracemalloc`` can measure the graph-build
    phase's Python-object peak (the mechanism the deferred at-scale ctcm-api
    measurement will use). Not a threshold assertion — just that the hook works
    and edges are produced."""
    sf, result = _extract(_CSHARP_CONTROLLER, "csharp", "Controller.cs")
    by_name: dict[str, list] = {}
    for s in result.symbols:
        by_name.setdefault(s.name, []).append(s)

    tracemalloc.start()
    edges = GraphBuilder().build_edges(sf, result.symbols, result.refs, by_name)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert edges
    assert peak > 0
