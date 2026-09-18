"""Tests for `gr_dataflow` (Milestone 1 Step 7 of `reqs-to-data-store.md`).

**`gr_dataflow` has no writer in Milestone 1 and the table ships empty.**
This file proves the *computed* path's mechanism works correctly when
forced on against fixtures — never against production data, since
`GR_DATAFLOW_COMPUTED_ENABLED` stays `False` until Milestone 26 of
`docs/exec-plans/active/semantic-code-search-graph-index.md` lands — and
proves `dataflow_status_text` cannot report a rate over the empty table
`requirements stats` sees throughout this milestone.

Two SQLite databases are involved and are opened as two separate
connections throughout, exactly like `domains_cmd` (`cli.py`):
`knowledge.sqlite` (via `KnowledgeStore`, holding `gr`/`gr_citation`) and
`index.sqlite` (via `SQLiteStore`, holding `symbols`/`graph_edges`/
`symbol_facts`). No statement anywhere in `gr_dataflow.py` or here uses
`ATTACH`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import re

import pytest

from legacylift_search.gr_dataflow import (
    GR_DATAFLOW_COMPUTED_ENABLED,
    compute_dataflow_entries,
    dataflow_status_text,
)
from legacylift_search.identity import anchor_key as compute_anchor_key
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import GraphEdge, SourceFile, Symbol, SymbolFact, TextRange
from legacylift_search.store import SQLiteStore

GR_ID = "GR-01HQ2X0000000000000000001"

# A minimal `gr` row: every NOT NULL column and nothing else, matching
# `tests/test_gr_schema.py`'s `_MINIMAL_GR` helper (kept local rather than
# imported, since a test file's fixtures are not another test file's API).
_MINIMAL_GR = {
    "gr_id": GR_ID,
    "kind": "business_rule",
    "statement": "The order procedure must record vendor lineage.",
    "statement_extracted": "The order procedure must record vendor lineage.",
    "modality": "requirement",
    "modality_extracted": "requirement",
    "dedupe_key": "dk1:1111111111111111",
    "dedupe_key_anchor_only": "dka1:1111111111111111",
    "extractor_payload": "{}",
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": "2026-09-01T00:00:00Z",
}


def _insert_gr(conn: sqlite3.Connection) -> None:
    row = _MINIMAL_GR
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT INTO gr ({columns}) VALUES ({placeholders})", tuple(row.values())
    )


def _insert_citation(conn: sqlite3.Connection, anchor_key: str, relative_path: str) -> None:
    conn.execute(
        """
        INSERT INTO gr_citation
            (gr_id, anchor_key, anchor_resolution, relative_path,
             start_line, end_line, provenance)
        VALUES (?, ?, 'symbol', ?, 1, 5, 'extracted')
        """,
        (GR_ID, anchor_key, relative_path),
    )


def _source_file(tmp_path: Path, relative_path: str) -> SourceFile:
    return SourceFile(
        absolute_path=tmp_path / relative_path,
        repo_root=tmp_path,
        relative_path=relative_path,
        language="sql",
        size_bytes=10,
        sha256="0" * 64,
        mtime_ns=0,
    )


def _symbol(symbol_id: str, qualified_name: str, entity_class: str, kind: str) -> Symbol:
    return Symbol(
        id=symbol_id,
        language="sql",
        name=qualified_name.rsplit(".", 1)[-1],
        qualified_name=qualified_name,
        kind=kind,
        entity_class=entity_class,
        range=TextRange(start_byte=0, end_byte=10, start_line=1, end_line=5),
    )


class _Fixture:
    """A knowledge store + index store pair wired up for the join tests.

    One requirement (`GR_ID`) cites two symbols: a procedure that reads
    `dbo.Orders`, writes `dbo.Customers` and has a `foreign_key` dependency
    on `dbo.Vendors`; and the `dbo.Orders` table symbol itself, which
    carries two `has_column` facts. Building this once keeps the five
    expected `DataflowEntry` rows traceable to a single, documented graph.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.knowledge_path = tmp_path / "knowledge" / "knowledge.sqlite"
        self.index_path = tmp_path / "index" / "index.sqlite"

        self.ks = KnowledgeStore(self.knowledge_path)

        # Unlike `KnowledgeStore`, `SQLiteStore` does not create its parent
        # directory -- that is Milestone 1 Step 8's read-only-command concern
        # (`Path.exists()` before construction), not this constructor's job.
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_store = SQLiteStore(self.index_path)
        self.index_store.migrate()

        proc_file = _source_file(tmp_path, "src/dbo/GetOpenOrders.sql")
        orders_file = _source_file(tmp_path, "src/dbo/Orders.sql")
        customers_file = _source_file(tmp_path, "src/dbo/Customers.sql")
        vendors_file = _source_file(tmp_path, "src/dbo/Vendors.sql")
        self.index_store.upsert_files(
            [proc_file, orders_file, customers_file, vendors_file]
        )

        proc_symbol = _symbol(
            "sql:src/dbo/GetOpenOrders.sql:dbo.GetOpenOrders:1",
            "dbo.GetOpenOrders",
            "function",
            "procedure",
        )
        orders_symbol = _symbol(
            "sql:src/dbo/Orders.sql:dbo.Orders:1", "dbo.Orders", "table", "create_table"
        )
        customers_symbol = _symbol(
            "sql:src/dbo/Customers.sql:dbo.Customers:1",
            "dbo.Customers",
            "table",
            "create_table",
        )
        vendors_symbol = _symbol(
            "sql:src/dbo/Vendors.sql:dbo.Vendors:1", "dbo.Vendors", "table", "create_table"
        )
        self.proc_symbol = proc_symbol
        self.orders_symbol = orders_symbol

        self.index_store.upsert_symbols(proc_file, [proc_symbol])
        self.index_store.upsert_symbols(orders_file, [orders_symbol])
        self.index_store.upsert_symbols(customers_file, [customers_symbol])
        self.index_store.upsert_symbols(vendors_file, [vendors_symbol])

        self.index_store.upsert_edges(
            [
                GraphEdge(
                    id="edge:reads-orders",
                    caller_symbol_id=proc_symbol.id,
                    callee_symbol_id=orders_symbol.id,
                    callee_name="Orders",
                    edge_kind="uses_table",
                    confidence=0.85,
                    evidence="SELECT * FROM dbo.Orders",
                    source_ref_id=None,
                    relative_path=proc_file.relative_path,
                    start_line=2,
                ),
                GraphEdge(
                    id="edge:writes-customers",
                    caller_symbol_id=proc_symbol.id,
                    callee_symbol_id=customers_symbol.id,
                    callee_name="Customers",
                    edge_kind="uses_table",
                    confidence=0.85,
                    evidence="UPDATE dbo.Customers SET Status = 'closed'",
                    source_ref_id=None,
                    relative_path=proc_file.relative_path,
                    start_line=3,
                ),
                GraphEdge(
                    id="edge:fk-vendors",
                    caller_symbol_id=proc_symbol.id,
                    callee_symbol_id=vendors_symbol.id,
                    callee_name="Vendors",
                    edge_kind="foreign_key",
                    confidence=1.0,
                    evidence="FOREIGN KEY (VendorId) REFERENCES Vendors(Id)",
                    source_ref_id=None,
                    relative_path=proc_file.relative_path,
                    start_line=4,
                ),
            ]
        )

        self.index_store.upsert_facts(
            orders_file,
            [
                SymbolFact(
                    id="fact:orders:has_column:OrderId",
                    subject_symbol_id=orders_symbol.id,
                    predicate="has_column",
                    object="OrderId",
                    evidence="OrderId INT PRIMARY KEY",
                    confidence=1.0,
                    relative_path=orders_file.relative_path,
                    start_line=2,
                    language="sql",
                ),
                SymbolFact(
                    id="fact:orders:has_column:CustomerId",
                    subject_symbol_id=orders_symbol.id,
                    predicate="has_column",
                    object="CustomerId",
                    evidence="CustomerId INT NOT NULL",
                    confidence=1.0,
                    relative_path=orders_file.relative_path,
                    start_line=3,
                    language="sql",
                ),
            ],
        )

        conn = self.ks._connect()
        _insert_gr(conn)
        _insert_citation(
            conn,
            compute_anchor_key("sql", "function", "dbo.GetOpenOrders", proc_file.relative_path),
            proc_file.relative_path,
        )
        _insert_citation(
            conn,
            compute_anchor_key("sql", "table", "dbo.Orders", orders_file.relative_path),
            orders_file.relative_path,
        )
        conn.commit()

    def close(self) -> None:
        self.index_store.close()
        self.ks.close()


@pytest.fixture
def fixture(tmp_path: Path):
    fx = _Fixture(tmp_path)
    try:
        yield fx
    finally:
        fx.close()


# ----------------------------------------------------------------------
# 1. Flag off (the default) -- nothing computed, nothing written.
# ----------------------------------------------------------------------


def test_flag_off_by_default_produces_nothing(fixture):
    """With `GR_DATAFLOW_COMPUTED_ENABLED` untouched, the computed path is
    inert: `compute_dataflow_entries` returns no entries, and `gr_dataflow`
    -- which this module never writes to at all -- stays empty.
    """
    assert GR_DATAFLOW_COMPUTED_ENABLED is False

    entries = compute_dataflow_entries(fixture.ks, fixture.index_store, GR_ID)

    assert entries == []
    count = fixture.ks._connect().execute(
        "SELECT COUNT(*) FROM gr_dataflow"
    ).fetchone()[0]
    assert count == 0


def test_flag_explicitly_off_also_produces_nothing(fixture):
    """Passing `enabled=False` explicitly is the same as the default -- the
    override is not a one-way switch that can only turn the path on.
    """
    entries = compute_dataflow_entries(
        fixture.ks, fixture.index_store, GR_ID, enabled=False
    )
    assert entries == []


# ----------------------------------------------------------------------
# 2. Flag forced on against a fixture -- entries match what it implies.
# ----------------------------------------------------------------------


def test_computed_entries_match_the_fixture(fixture):
    """With the flag forced on, the five entries the fixture's graph data
    implies come back, each with the right `direction`, `datastore`,
    `column` and `provenance='computed'`:

    * the procedure's `uses_table` read of `dbo.Orders` (evidence has no
      write verb -> `reads`)
    * its `uses_table` write to `dbo.Customers` (evidence has `UPDATE`)
    * its `foreign_key` dependency on `dbo.Vendors` (always `reads`)
    * the `dbo.Orders` table symbol's own two `has_column` facts, cited
      directly, each a `reads` entry naming that column
    """
    entries = compute_dataflow_entries(
        fixture.ks, fixture.index_store, GR_ID, enabled=True
    )

    got = {(e.direction, e.datastore, e.column) for e in entries}
    assert got == {
        ("reads", "dbo.Orders", ""),
        ("writes", "dbo.Customers", ""),
        ("reads", "dbo.Vendors", ""),
        ("reads", "dbo.Orders", "OrderId"),
        ("reads", "dbo.Orders", "CustomerId"),
    }
    assert all(e.gr_id == GR_ID for e in entries)
    assert all(e.provenance == "computed" for e in entries)


def test_computed_entries_are_deduplicated(fixture):
    """Two edges/facts that would resolve to the same
    `(direction, datastore, column)` triple collapse to one entry, matching
    `gr_dataflow`'s own `UNIQUE` constraint -- calling twice must not double
    the count either.
    """
    first = compute_dataflow_entries(fixture.ks, fixture.index_store, GR_ID, enabled=True)
    second = compute_dataflow_entries(fixture.ks, fixture.index_store, GR_ID, enabled=True)
    assert len(first) == len(second) == 5
    triples = [(e.direction, e.datastore, e.column) for e in first]
    assert len(triples) == len(set(triples))


def test_no_citations_produces_nothing(fixture):
    """A requirement with no citations at all yields no entries -- there is
    nothing to resolve against `index.sqlite`.
    """
    entries = compute_dataflow_entries(
        fixture.ks, fixture.index_store, "GR-DOES-NOT-EXIST", enabled=True
    )
    assert entries == []


# ----------------------------------------------------------------------
# 3. `column` is '' and never NULL for a table-grain entry.
# ----------------------------------------------------------------------


def test_column_is_empty_string_never_none(fixture):
    """Every table-grain entry's `column` is `''`, never `None`. The
    `UNIQUE (gr_id, direction, datastore, "column")` constraint treats NULLs
    as distinct, so a NULL would let the same entry insert repeatedly.
    """
    entries = compute_dataflow_entries(
        fixture.ks, fixture.index_store, GR_ID, enabled=True
    )
    assert any(e.column == "" for e in entries)  # the three table-grain entries
    for e in entries:
        assert e.column is not None
        assert isinstance(e.column, str)


# ----------------------------------------------------------------------
# 4. Two connections, no ATTACH.
# ----------------------------------------------------------------------


def test_cross_database_join_uses_two_connections(fixture):
    """`ks` and `index_store` are genuinely separate `sqlite3.Connection`
    objects over two different files, and the join still produces the right
    answer -- proving the read is done in Python, not via a single
    cross-database statement.
    """
    assert fixture.ks._connect() is not fixture.index_store.connection()
    assert fixture.knowledge_path != fixture.index_path

    entries = compute_dataflow_entries(
        fixture.ks, fixture.index_store, GR_ID, enabled=True
    )
    assert len(entries) == 5


def test_module_never_attaches_databases():
    """Static check: no SQL in `gr_dataflow.py` ever `ATTACH`es a database --
    the cross-database read is joined in Python (the `domains_cmd` pattern),
    never via a single-statement cross-database join.
    """
    import legacylift_search.gr_dataflow as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    # The word "ATTACH" appears in prose (explaining what this module does
    # NOT do); the SQL statement form "ATTACH DATABASE" is what must be
    # absent.
    assert "ATTACH DATABASE" not in source.upper()


# ----------------------------------------------------------------------
# 5. The status text: words, never a rate, over an empty table.
# ----------------------------------------------------------------------


def test_status_text_names_both_deferred_reasons():
    """The empty-table sentence names both independent reasons the block is
    empty -- the computed path's M26 gate and the missing extractor-source
    field -- because they are cleared by different work.
    """
    text = dataflow_status_text(total=0, computed=0, llm_inferred=0)
    assert "M26" in text
    assert "extractor" in text.lower()


def test_status_text_has_no_percent_sign_or_rate_looking_digits():
    """No percent sign, and no digit sequence that could be mistaken for a
    computed rate (an isolated number or an N/M fraction) -- the milestone
    number `M26` is the one digit sequence allowed, and it is anchored to a
    letter so it cannot be misread as a percentage or a fraction.
    """
    import re

    text = dataflow_status_text(total=0, computed=0, llm_inferred=0)
    assert "%" not in text
    assert not re.search(r"\d+\s*/\s*\d+", text)
    # Strip the one allowed digit sequence -- the "M26" milestone reference,
    # a letter-anchored token, not a bare number -- and confirm nothing
    # number-shaped remains.
    without_milestone_refs = re.sub(r"\bM\d+\b", "", text)
    assert not re.search(r"\d", without_milestone_refs)


def test_status_text_never_returns_a_number_for_an_empty_table():
    """There is no code path in `dataflow_status_text` that returns a bare
    number, or anything computed from `computed`/`llm_inferred`, while
    `total` is `0` -- varying the other two arguments cannot change the
    fixed sentence.
    """
    baseline = dataflow_status_text(total=0, computed=0, llm_inferred=0)
    assert dataflow_status_text(total=0, computed=5, llm_inferred=3) == baseline
    assert dataflow_status_text(total=0, computed=0, llm_inferred=0) == baseline


def test_status_text_reports_an_unexpected_nonempty_table_without_a_rate():
    """A non-zero `total` is reported as an anomaly, with counts, never a rate
    — and never by raising.

    Milestone 1 has no writer, so a non-zero total can only mean a bug
    elsewhere. An earlier form raised `NotImplementedError` here, which is the
    wrong failure for this caller: `requirements stats` is read-only and is
    where Step 10's three mandatory measurements are read from, so raising out
    of it would cost the operator the state counts, the SME fill rates, the
    intra-run collapse rate and the anchor-resolution breakdown in order to
    describe one empty table. Degrade loudly instead — the same choice
    ingest makes when no embedder is reachable.

    The no-rate guarantee is unaffected, and is structural: there is no
    division anywhere in the module.
    """
    text = dataflow_status_text(total=7, computed=5, llm_inferred=2)

    # Loud, and it names the counts it actually has.
    assert "UNEXPECTED" in text
    assert "7" in text and "5" in text and "2" in text

    # But no rate, in any of the shapes a rate takes.
    assert "%" not in text
    assert not re.search(r"\d+\s*/\s*\d+", text)
    assert not re.search(r"\d+\.\d+", text)

    # And the module performs no division anywhere, so a rate is unreachable
    # rather than merely unwritten. Asserted over the AST, not the text: the
    # module's own docstring names `computed / total` as the thing it avoids,
    # and a substring check trips on that prose -- the same false-positive
    # class as the gr.state writer census, which had to be fixed for exactly
    # this reason. Prose describing a division is not one.
    import ast

    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legacylift_search"
        / "gr_dataflow.py"
    ).read_text(encoding="utf-8")
    divisions = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.BinOp)
        and isinstance(node.op, (ast.Div, ast.FloorDiv))
    ]
    assert not divisions, (
        "gr_dataflow.py performs division; a rate over an empty table must be "
        "structurally unreachable, not merely unwritten"
    )


# ----------------------------------------------------------------------
# 6. `index_store=None` is handled without ever creating index.sqlite.
# ----------------------------------------------------------------------


def test_none_index_store_creates_no_database(tmp_path: Path):
    """`compute_dataflow_entries(ks, None, gr_id)` must never construct a
    `SQLiteStore` (which would create `index.sqlite` on its first query) --
    the caller is the one required to probe `Path.exists()` first and pass
    `None` when the file is absent. This asserts the file never appears.
    """
    knowledge_path = tmp_path / "knowledge" / "knowledge.sqlite"
    index_path = tmp_path / "index" / "index.sqlite"
    assert not index_path.exists()

    ks = KnowledgeStore(knowledge_path)
    try:
        conn = ks._connect()
        _insert_gr(conn)
        _insert_citation(
            conn,
            compute_anchor_key("sql", "function", "dbo.GetOpenOrders", "src/dbo/GetOpenOrders.sql"),
            "src/dbo/GetOpenOrders.sql",
        )
        conn.commit()

        entries = compute_dataflow_entries(ks, None, GR_ID, enabled=True)

        assert entries == []
        assert not index_path.exists()
    finally:
        ks.close()
