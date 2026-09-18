"""Milestone 23: annotation / attribute / decorator extraction.

Covers three concerns:

1. Extractor — annotation facts extract for all FOUR tree-sitter languages,
   proving each language's distinct traversal fires: C# attribute-list children,
   Java ``modifiers`` children, the Python parent ``decorated_definition``
   traversal, and the TypeScript preceding-sibling traversal.
2. Graph — @ManyToOne / @JoinColumn produce ``associates`` / ``foreign_key``
   *edges* (asserted per-edge-kind, never on totals).
3. Cascade cleanup — the two paths deferred from the Shared plumbing
   prerequisite, exercised against real content-driven annotation facts: a
   changed file (upsert_files REPLACE cascade) and a deleted file
   (delete_file_artifacts file_id cascade).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from legacylift_search.config import Manifest
from legacylift_search.extractors import SymbolExtractor, load_profiles
from legacylift_search.graph import GraphBuilder
from legacylift_search.indexer import Indexer
from legacylift_search.models import SourceFile
from legacylift_search.store import SQLiteStore


PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "extractors.json"
FIXTURES = Path(__file__).parent / "fixtures" / "polyglot_repo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract(rel: str, language: str):
    profiles = load_profiles(PROFILE_PATH)
    extractor = SymbolExtractor(profiles)
    path = FIXTURES / rel
    text = path.read_text(encoding="utf-8", errors="replace")
    sf = SourceFile(
        absolute_path=path.resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path=rel,
        language=language,
        size_bytes=len(text.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    return extractor.extract(sf, text)


def _facts_by_predicate(facts, predicate):
    return [f for f in facts if f.predicate == predicate]


# ---------------------------------------------------------------------------
# Extractor tests — one per tree-sitter language (plan line 807, required)
# ---------------------------------------------------------------------------


def test_csharp_attribute_facts() -> None:
    """C# ``[HttpGet(...)]`` -> http_method (attribute-list child walk)."""
    result = _extract("annotations/OrdersController.cs", "csharp")

    verbs = {f.object for f in _facts_by_predicate(result.facts, "http_method")}
    assert "GET" in verbs
    assert "POST" in verbs

    get_fact = next(
        f for f in _facts_by_predicate(result.facts, "http_method")
        if f.object == "GET"
    )
    assert get_fact.attributes["route"] == "orders"
    assert get_fact.confidence == 1.0

    # endpoint / authz / validation / persistence predicates all present.
    assert _facts_by_predicate(result.facts, "exposes_endpoint")
    assert _facts_by_predicate(result.facts, "requires_auth")  # [Authorize]
    assert _facts_by_predicate(result.facts, "is_required")    # [Required]
    assert _facts_by_predicate(result.facts, "is_id")          # [Key]
    ml = _facts_by_predicate(result.facts, "max_length")
    assert ml and ml[0].object == "50"
    col = _facts_by_predicate(result.facts, "is_column")
    assert col and col[0].object == "customer_name"


def test_java_annotation_facts() -> None:
    """Java ``@GetMapping`` -> http_method (walk via the ``modifiers`` child)."""
    result = _extract("annotations/OrderApi.java", "java")

    http = _facts_by_predicate(result.facts, "http_method")
    verbs = {f.object for f in http}
    assert "GET" in verbs
    assert "POST" in verbs
    assert _facts_by_predicate(result.facts, "requires_auth")  # @PreAuthorize
    assert _facts_by_predicate(result.facts, "is_required")    # @NotNull
    assert _facts_by_predicate(result.facts, "is_id")          # @Id
    tables = {f.object for f in _facts_by_predicate(result.facts, "table_name")}
    assert "orders" in tables  # @Table(name = "orders")


def test_python_decorator_facts_parent_traversal() -> None:
    """Python ``@app.get(...)`` proves the node.parent / decorated_definition
    traversal fires — a children-only walk would emit ZERO facts here."""
    result = _extract("annotations/routes.py", "python")

    http = _facts_by_predicate(result.facts, "http_method")
    assert http, "python decorator facts missing (parent traversal did not fire)"
    verbs = {f.object for f in http}
    assert "GET" in verbs
    assert "POST" in verbs
    # @requires_auth (bare identifier decorator).
    assert _facts_by_predicate(result.facts, "requires_auth")
    # Unknown decorator (@staticmethod) is not silently dropped.
    has_ann = {f.object for f in _facts_by_predicate(result.facts, "has_annotation")}
    assert "staticmethod" in has_ann


def test_typescript_decorator_facts_sibling_traversal() -> None:
    """TS decorators prove the preceding-sibling traversal fires for BOTH a
    class decorator (@Controller, sibling in export_statement) and method
    decorators (@Get/@Post, siblings in class_body)."""
    result = _extract("annotations/orders.controller.ts", "typescript")

    http = _facts_by_predicate(result.facts, "http_method")
    assert http, "TS decorator facts missing (sibling traversal did not fire)"
    verbs = {f.object for f in http}
    assert "GET" in verbs
    assert "POST" in verbs
    # Class-level decorator reached by scanning preceding siblings past `export`.
    has_ann = {f.object for f in _facts_by_predicate(result.facts, "has_annotation")}
    assert "Controller" in has_ann


def test_fact_ids_are_deterministic_and_distinct_per_object() -> None:
    """Two http_method facts on distinct lines get distinct ids; re-extraction
    is idempotent (identical ids)."""
    r1 = _extract("annotations/OrdersController.cs", "csharp")
    r2 = _extract("annotations/OrdersController.cs", "csharp")
    ids1 = {f.id for f in r1.facts}
    ids2 = {f.id for f in r2.facts}
    assert ids1 == ids2                      # deterministic
    assert len(ids1) == len(r1.facts)        # no id collisions


# ---------------------------------------------------------------------------
# Graph test — relational edges, asserted per edge kind (never on totals)
# ---------------------------------------------------------------------------


def test_relational_annotations_produce_foreign_key_and_associates_edges() -> None:
    """@ManyToOne -> associates edge, @JoinColumn -> foreign_key edge."""
    result = _extract("annotations/OrderApi.java", "java")

    # The handler emits these as SymbolRefs with explicit kinds.
    ref_kinds = {r.kind for r in result.refs}
    assert "associates" in ref_kinds
    assert "foreign_key" in ref_kinds

    by_name: dict[str, list] = {}
    for s in result.symbols:
        by_name.setdefault(s.name, []).append(s)

    sf = SourceFile(
        absolute_path=(FIXTURES / "annotations/OrderApi.java").resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path="annotations/OrderApi.java",
        language="java",
        size_bytes=1,
        sha256="0" * 64,
        mtime_ns=0,
    )
    edges = GraphBuilder().build_edges(sf, result.symbols, result.refs, by_name)

    # Per-edge-kind counts (NOT the total): both typed edges must be present.
    kind_counts: dict[str, int] = {}
    for e in edges:
        kind_counts[e.edge_kind] = kind_counts.get(e.edge_kind, 0) + 1
    assert kind_counts.get("foreign_key", 0) == 1
    assert kind_counts.get("associates", 0) == 1


# ---------------------------------------------------------------------------
# Cascade-cleanup tests (deferred from the Shared plumbing prerequisite)
# ---------------------------------------------------------------------------


def _manifest() -> Manifest:
    m = Manifest()
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    return m


def _sqlite_path(repo: Path) -> Path:
    return repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"


def _endpoint_rows(repo: Path, rel: str) -> set[tuple[str | None, int]]:
    """(object, start_line) of exposes_endpoint facts for one file."""
    store = SQLiteStore(_sqlite_path(repo))
    try:
        conn = store._connect()
        rows = conn.execute(
            """
            SELECT object, start_line FROM symbol_facts
            WHERE relative_path = ? AND predicate = 'exposes_endpoint'
            """,
            (rel,),
        ).fetchall()
        return {(r["object"], r["start_line"]) for r in rows}
    finally:
        store.close()


def test_changed_file_fact_cleanup_via_upsert_files_cascade(tmp_path: Path) -> None:
    """Editing an annotated file so a fact changes, then a plain reindex (NO
    --reset), must leave only the NEW fact — the old one is purged by the
    upsert_files REPLACE -> file_id cascade (indexer.py:302)."""
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURES, repo)
    rel = "annotations/OrdersController.cs"
    manifest = _manifest()

    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    before = _endpoint_rows(repo, rel)
    # The @HttpGet("orders") endpoint is on line 8.
    assert ("orders", 8) in before

    # Change the route template on line 8 so the exposes_endpoint fact's
    # object (part of its deterministic id) changes: orders -> neworders.
    target = repo / rel
    text = target.read_text(encoding="utf-8")
    target.write_text(
        text.replace('[HttpGet("orders")]', '[HttpGet("neworders")]'),
        encoding="utf-8",
    )

    s2 = Indexer(manifest, repo).run(reset=False, embedding_provider_override="hash")
    assert s2.files_processed == 1  # only the edited file re-extracted

    after = _endpoint_rows(repo, rel)
    # OLD fact gone, NEW fact present — proves the cascade purged stale facts.
    assert ("orders", 8) not in after
    assert ("neworders", 8) in after
    # The unrelated @HttpPost endpoint on line 14 is untouched.
    assert ("orders", 14) in after


def test_deleted_file_fact_cleanup_via_file_id_cascade(tmp_path: Path) -> None:
    """Deleting an annotated file then reindexing must drop all its facts via
    the delete_file_artifacts repo_files -> symbol_facts file_id cascade."""
    repo = tmp_path / "repo"
    shutil.copytree(FIXTURES, repo)
    rel = "annotations/OrdersController.cs"
    manifest = _manifest()

    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    store = SQLiteStore(_sqlite_path(repo))
    try:
        conn = store._connect()
        n_before = conn.execute(
            "SELECT COUNT(*) FROM symbol_facts WHERE relative_path = ?", (rel,)
        ).fetchone()[0]
    finally:
        store.close()
    assert n_before > 0, "fixture produced no facts to delete"

    (repo / rel).unlink()

    Indexer(manifest, repo).run(reset=False, embedding_provider_override="hash")

    store = SQLiteStore(_sqlite_path(repo))
    try:
        conn = store._connect()
        n_after = conn.execute(
            "SELECT COUNT(*) FROM symbol_facts WHERE relative_path = ?", (rel,)
        ).fetchone()[0]
    finally:
        store.close()
    assert n_after == 0, "deleted file's facts were not cascade-purged"
