"""SQL extractor: transient-table classification + bracketed/qualified identifier
normalization (ExecPlan: sql-extractor-temp-cte-fk).

Two defects surfaced mapping the NNG DB unit:

1. Temp tables were counted as durable schema tables. They are now classified as
   ``create_temp_table`` so they drop out of the ``create_table`` inventory.
2. Bracketed / schema-qualified FK edges dangled. The FK *ref* was already
   normalized (M24), but the ``create_table`` *symbol name* was not — and
   tree-sitter-sql mangles ``[dbo].[Customer]`` to ``dbo].[Customer``. Both sides
   now run through ``_normalize_sql_identifier`` so the edge resolves.

tree-sitter-sql caveat pinned by these tests: it does not understand [bracket]
quoting and MERGES adjacent bracketed tables when NOT NULL is present, so the
cross-table FK case uses plain table names with a bracketed REFERENCES target,
and a single bracketed table pins definition-side normalization. See the fixture
header for detail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from legacylift_search.extractors import (
    SymbolExtractor,
    _normalize_sql_identifier,
    load_profiles,
)
from legacylift_search.graph import GraphBuilder
from legacylift_search.models import SourceFile


PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "extractors.json"
FIXTURES = Path(__file__).parent / "fixtures" / "polyglot_repo"
SCHEMA_REL = "database/tsql_bracketed.sql"


def _extract():
    path = FIXTURES / SCHEMA_REL
    text = path.read_text(encoding="utf-8", errors="replace")
    sf = SourceFile(
        absolute_path=path.resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path=SCHEMA_REL,
        language="sql",
        size_bytes=len(text.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    return sf, SymbolExtractor(load_profiles(PROFILE_PATH)).extract(sf, text)


# ---------------------------------------------------------------------------
# _normalize_sql_identifier (deterministic unit — no grammar dependency)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("providers", "providers"),                 # plain, unchanged
        ("[dbo].[Customer]", "Customer"),            # T-SQL bracket + schema
        ("dbo].[Customer", "Customer"),              # tree-sitter's MANGLED form
        ("dbo.Customer", "Customer"),                # dotted qualifier
        ('"dbo"."Customer"', "Customer"),            # ANSI double-quoted
        ("`app`.`orders`", "orders"),                # MySQL backticks
        ("[Orders]", "Orders"),                      # bracketed, no schema
    ],
)
def test_normalize_sql_identifier(raw, expected):
    assert _normalize_sql_identifier(raw) == expected


# ---------------------------------------------------------------------------
# Transient tables are classified out of the durable inventory
# ---------------------------------------------------------------------------


def test_temp_tables_excluded_from_durable_inventory():
    _sf, result = _extract()
    durable = {s.name for s in result.symbols if s.kind == "create_table"}
    temp = {s.name for s in result.symbols if s.kind == "create_temp_table"}

    # #StagingRows (#), @LineItems (@), tmp_scratch (TEMPORARY) are transient.
    # The #/@ marker stays in the name (Milestone 4): the grammar drops it, so it
    # is restored deliberately to keep a ``#Orders`` staging table from colliding
    # with the durable ``Orders`` in the graph's name index.
    assert temp == {"#StagingRows", "@LineItems", "tmp_scratch"}
    # None of them leak into the durable-table inventory.
    assert durable.isdisjoint(temp)
    # Real tables remain durable (Widget is the bracketed one, normalized).
    assert {"Customer", "Orders", "Widget"} <= durable


# ---------------------------------------------------------------------------
# Definition-side name normalization: bracketed table -> bare symbol name
# ---------------------------------------------------------------------------


def test_bracketed_table_name_normalized():
    _sf, result = _extract()
    tables = {s.name: s for s in result.symbols if s.kind == "create_table"}
    # [dbo].[Widget] must be the bare 'Widget', never the mangled 'dbo].[Widget'.
    assert "Widget" in tables
    assert not any("[" in s.name or "]" in s.name for s in result.symbols)


# ---------------------------------------------------------------------------
# Bracketed / qualified FK target resolves to its create_table symbol
# ---------------------------------------------------------------------------


def test_bracketed_fk_resolves_cross_table():
    sf, result = _extract()
    fk_refs = [r for r in result.refs if r.kind == "foreign_key"]
    # The FK REFERENCES [dbo].[Customer] normalizes to the bare 'Customer'.
    assert any(r.name == "Customer" for r in fk_refs)

    by_name: dict[str, list] = {}
    for s in result.symbols:
        by_name.setdefault(s.name, []).append(s)
    edges = GraphBuilder().build_edges(sf, result.symbols, result.refs, by_name)

    fk_edges = [e for e in edges if e.edge_kind == "foreign_key"]
    assert fk_edges, "no foreign_key edge produced"
    customer = next(s for s in result.symbols if s.name == "Customer")
    orders = next(s for s in result.symbols if s.name == "Orders")
    # A REAL cross-table edge Orders -> Customer, not a dangling/self ref.
    assert any(
        e.caller_symbol_id == orders.id and e.callee_symbol_id == customer.id
        for e in fk_edges
    ), "bracketed FK edge did not resolve Orders -> Customer"


# ---------------------------------------------------------------------------
# CTEs are not durable tables
# ---------------------------------------------------------------------------


def test_cte_is_not_a_create_table():
    _sf, result = _extract()
    names = {s.name for s in result.symbols if s.kind in ("create_table", "create_temp_table")}
    assert "RankedCustomers" not in names
