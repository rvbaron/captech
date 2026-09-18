"""Regex CREATE TABLE recovery for bracket-heavy T-SQL (ExecPlan
sql-extractor-temp-cte-fk, Milestone 4).

tree-sitter-sql has no concept of [bracket] quoting and recovers via ERROR
nodes. Three consequences, all reproduced against the running grammar and all
pinned here:

1. **Merge.** A bracketed ``CREATE TABLE`` ending in ``NOT NULL`` swallows the
   FOLLOWING statement into its own ``create_table`` node. The swallowed table
   loses its symbol entirely, its columns are attributed to the preceding table,
   and its FK resolves against that table as a confident (0.85) SELF edge — so
   this one produces WRONG data, not just missing data.
2. **Vanishing columns.** A bracketed column whose name collides with a grammar
   keyword is swallowed by an ERROR node and never becomes a
   ``column_definition`` (``[Name] NVARCHAR(100)`` -> ``keyword_name``). Name,
   Date, Value, Status, Type and Key are everywhere in real schemas.
3. **Mangled types.** The closing ``]`` lands between the name and the type, so
   the type came back as ``']'``.

So regex segmentation decides the table inventory, and the grammar keeps a table
only when it segmented it 1:1 AND the statement has no brackets. The same
segmenter backs the no-grammar fallback path, which previously produced a bare
``fallback_definition`` per statement with no columns and no FKs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from legacylift_search.extractors import (
    SymbolExtractor,
    _sql_columns_from_body,
    _sql_mask_noncode,
    _sql_table_segments,
    load_profiles,
)
from legacylift_search.graph import GraphBuilder
from legacylift_search.languages import get_language
from legacylift_search.models import SourceFile

from .conftest import requires_sql_grammar


PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "extractors.json"
FIXTURES = Path(__file__).parent / "fixtures" / "polyglot_repo"
MULTI_REL = "database/tsql_bracketed_multi.sql"


def _source_file(rel: str, text: str) -> SourceFile:
    return SourceFile(
        absolute_path=(FIXTURES / rel).resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path=rel,
        language="sql",
        size_bytes=len(text.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )


def _extract_text(text: str, rel: str = "database/adhoc.sql"):
    sf = _source_file(rel, text)
    return sf, SymbolExtractor(load_profiles(PROFILE_PATH)).extract(sf, text)


def _extract_multi():
    text = (FIXTURES / MULTI_REL).read_text(encoding="utf-8", errors="replace")
    sf = _source_file(MULTI_REL, text)
    return sf, text, SymbolExtractor(load_profiles(PROFILE_PATH)).extract(sf, text)


def _edges(sf, result):
    by_name: dict[str, list] = {}
    for s in result.symbols:
        by_name.setdefault(s.name, []).append(s)
    return GraphBuilder().build_edges(sf, result.symbols, result.refs, by_name)


def _tables(result) -> dict[str, str]:
    """name -> kind for every table-ish symbol."""
    return {
        s.name: s.kind
        for s in result.symbols
        if s.kind in ("create_table", "create_temp_table")
    }


def _columns(result, table_name: str) -> dict[str, dict]:
    sym = next(s for s in result.symbols if s.name == table_name)
    return {
        f.object: f.attributes
        for f in result.facts
        if f.predicate == "has_column" and f.subject_symbol_id == sym.id
    }


# ---------------------------------------------------------------------------
# Segmenter units — deterministic, no grammar dependency
# ---------------------------------------------------------------------------


def test_segments_every_create_table_variant():
    text = (
        "CREATE TABLE [dbo].[Orders] ([Id] INT NOT NULL);\n"
        "CREATE TABLE dbo.Plain (id int);\n"
        "CREATE TABLE IF NOT EXISTS quoted_tbl (\"id\" int);\n"
        "CREATE TEMPORARY TABLE tmp_scratch (id int);\n"
        "CREATE TABLE #Staging (id int);\n"
        "CREATE TABLE ##GlobalStaging (id int);\n"
        "CREATE TABLE @TableVar (id int);\n"
        "CREATE TABLE [#BracketedStaging] (id int);\n"
    )
    segs = _sql_table_segments(text)
    assert [s.name for s in segs] == [
        "Orders",
        "Plain",
        "quoted_tbl",
        "tmp_scratch",
        "#Staging",
        "##GlobalStaging",
        "@TableVar",
        "#BracketedStaging",
    ]
    # Everything from tmp_scratch on is transient; the first three are durable.
    assert [s.is_temp for s in segs] == [False, False, False, True, True, True, True, True]


def test_commented_out_and_dynamic_sql_ddl_are_not_segments():
    text = (
        "-- CREATE TABLE dbo.GhostLineComment (id int);\n"
        "/* CREATE TABLE dbo.GhostBlockComment (id int); */\n"
        "EXEC('CREATE TABLE dbo.GhostDynamic (id int)');\n"
        "CREATE TABLE dbo.Real (id int);\n"
    )
    assert [s.name for s in _sql_table_segments(text)] == ["Real"]


def test_unbalanced_statement_is_skipped_not_guessed():
    # Truncated DDL (never closes its paren) must not produce a table.
    assert _sql_table_segments("CREATE TABLE dbo.Truncated (id int,\n") == []


def test_mask_noncode_preserves_offsets_and_lines():
    text = "SELECT 1; -- CREATE TABLE x (\n/* two\nlines */ 'a''b' END\n"
    masked = _sql_mask_noncode(text)
    assert len(masked) == len(text)
    assert masked.count("\n") == text.count("\n")
    # Code survives; comment and string contents do not.
    assert masked.startswith("SELECT 1;")
    assert "CREATE" not in masked
    assert "a''b" not in masked
    assert masked.rstrip().endswith("END")


def test_columns_from_body_types_flags_and_constraint_skipping():
    body = (
        "[OrderId] INT NOT NULL PRIMARY KEY,\n"
        "[Total] DECIMAL(18,2) NULL,\n"
        "[Code] VARCHAR(10) NOT NULL UNIQUE,\n"
        "[Amt] DOUBLE PRECISION NULL,\n"
        "CONSTRAINT [FK_x] FOREIGN KEY ([OrderId]) REFERENCES [dbo].[Orders]([OrderId]),\n"
        "PRIMARY KEY ([OrderId])"
    )
    cols = {name: attrs for name, attrs, _off in _sql_columns_from_body(body)}
    # Constraint entries are not columns.
    assert set(cols) == {"OrderId", "Total", "Code", "Amt"}
    assert cols["OrderId"] == {
        "data_type": "INT",
        "nullable": False,
        "primary_key": True,
        "unique": False,
    }
    # The comma inside DECIMAL(18,2) must not split the entry.
    assert cols["Total"]["data_type"] == "DECIMAL(18,2)"
    assert cols["Total"]["nullable"] is True
    assert cols["Code"]["unique"] is True
    assert cols["Amt"]["data_type"] == "DOUBLE PRECISION"


# ---------------------------------------------------------------------------
# The grammar limitation this milestone exists for
# ---------------------------------------------------------------------------


@requires_sql_grammar
def test_grammar_alone_undercounts_the_bracketed_fixture():
    """Pin the limitation: raw tree-sitter finds FEWER tables than exist.

    If a future grammar release fixes bracket quoting this fails, which is the
    signal to re-evaluate whether recovery should still own bracketed tables.
    """
    text = (FIXTURES / MULTI_REL).read_text(encoding="utf-8", errors="replace")
    extractor = SymbolExtractor(load_profiles(PROFILE_PATH))
    parser, _name = extractor._parser_for_language(get_language("sql"))
    tree = parser.parse(text.encode("utf-8"))

    nodes: list = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "create_table":
            nodes.append(node)
        stack.extend(node.children)

    segments = _sql_table_segments(text)
    assert len(segments) == 4
    assert len(nodes) < len(segments), (
        "tree-sitter-sql now segments bracketed multi-table DDL; revisit whether "
        "regex recovery should still take ownership of bracketed statements"
    )
    # And the merge is exactly how it undercounts: one node spans two statements.
    assert any(
        sum(
            1 for s in segments
            if n.start_byte <= s.start_byte < n.end_byte
        ) > 1
        for n in nodes
    )


# ---------------------------------------------------------------------------
# Recovery on the tree-sitter path
# ---------------------------------------------------------------------------


@requires_sql_grammar
def test_all_bracketed_tables_recovered_with_temp_classified():
    _sf, _text, result = _extract_multi()
    assert _tables(result) == {
        "Customer": "create_table",
        "Orders": "create_table",
        "OrderLine": "create_table",
        "#OrderStaging": "create_temp_table",
    }
    # The unbracketed procedure stays with the grammar.
    assert any(
        s.kind == "create_procedure" and s.name == "usp_GetOrders"
        for s in result.symbols
    )


@requires_sql_grammar
def test_no_phantom_tables_from_comments_or_dynamic_sql():
    _sf, _text, result = _extract_multi()
    names = {s.name for s in result.symbols}
    assert not any("Ghost" in n for n in names), names


@requires_sql_grammar
def test_keyword_named_bracketed_column_is_not_lost():
    """``[Name]`` parses as ``keyword_name`` inside an ERROR node, so the grammar
    drops the column outright. Recovery must keep it, with its real type."""
    _sf, _text, result = _extract_multi()
    customer = _columns(result, "Customer")
    assert set(customer) == {"CustomerId", "Region", "Name"}
    assert customer["Name"]["data_type"] == "NVARCHAR(100)"
    assert customer["Name"]["nullable"] is False
    assert customer["CustomerId"]["primary_key"] is True
    assert customer["Region"]["nullable"] is True


@requires_sql_grammar
def test_bracketed_column_types_are_never_the_bracket_artifact():
    _sf, _text, result = _extract_multi()
    types = {
        f.attributes.get("data_type")
        for f in result.facts
        if f.predicate == "has_column"
    }
    assert "]" not in types and None not in types
    assert _columns(result, "#OrderStaging")["Payload"]["data_type"] == "NVARCHAR(MAX)"


@requires_sql_grammar
def test_merged_statement_fks_resolve_to_the_right_tables():
    sf, _text, result = _extract_multi()
    fk = {
        (
            e.caller_symbol_id.split(":")[2],
            e.callee_symbol_id.split(":")[2] if e.callee_symbol_id else None,
        )
        for e in _edges(sf, result)
        if e.edge_kind == "foreign_key"
    }
    assert fk == {("Orders", "Customer"), ("OrderLine", "Orders")}
    # The pre-fix symptom was a confident SELF edge on the swallowing table.
    assert ("Customer", "Customer") not in fk
    assert all(
        e.confidence >= 0.7
        for e in _edges(sf, result)
        if e.edge_kind == "foreign_key"
    )


@requires_sql_grammar
def test_lineage_refs_survive_the_repair():
    """Non-FK refs inside a replaced node are re-anchored, not dropped: the
    procedure's FROM/JOIN still reach Orders and Customer."""
    sf, _text, result = _extract_multi()
    used = {
        (
            e.caller_symbol_id.split(":")[2],
            e.callee_symbol_id.split(":")[2] if e.callee_symbol_id else None,
        )
        for e in _edges(sf, result)
        if e.edge_kind == "uses_table"
    }
    assert ("usp_GetOrders", "Orders") in used
    assert ("usp_GetOrders", "Customer") in used
    # A table's own name in its CREATE statement is not a usage of it, and no
    # lineage ref is left dangling by the re-anchoring.
    assert ("Customer", "Customer") not in used
    assert not any(callee is None for _caller, callee in used)


@requires_sql_grammar
@pytest.mark.parametrize("table_name", ["[dbo].[B]", "dbo.B"])
def test_commented_out_foreign_key_is_not_an_edge(table_name):
    """Runs on both halves: ``[dbo].[B]`` goes through regex recovery, ``dbo.B``
    stays with the grammar — neither may resurrect a retired constraint."""
    _sf, result = _extract_text(
        "CREATE TABLE dbo.A (Id INT NOT NULL);\n"
        f"CREATE TABLE {table_name} (\n"
        "    Id INT NOT NULL,\n"
        "    -- FOREIGN KEY (Id) REFERENCES dbo.A(Id)\n"
        "    AId INT NOT NULL\n"
        ");\n"
    )
    assert [r for r in result.refs if r.kind == "foreign_key"] == []


@requires_sql_grammar
def test_foreign_key_evidence_is_the_real_source_text():
    """The FK scan runs over a masked copy; evidence must come from the original
    text, not the blanked one."""
    _sf, result = _extract_multi()[0], _extract_multi()[2]
    for ref in [r for r in result.refs if r.kind == "foreign_key"]:
        assert "FOREIGN KEY" in ref.evidence.upper()
        assert "REFERENCES" in ref.evidence.upper()


@requires_sql_grammar
def test_clean_unbracketed_ddl_stays_with_the_grammar():
    """Recovery must not take over where the grammar is fine: an unbracketed
    table keeps AST-derived columns (confidence 1.0)."""
    _sf, result = _extract_text(
        "CREATE TABLE dbo.Plain (\n"
        "    plain_id int NOT NULL PRIMARY KEY,\n"
        "    label varchar(50) NULL\n"
        ");\n"
    )
    assert _tables(result) == {"Plain": "create_table"}
    confidences = {
        f.confidence for f in result.facts if f.predicate == "has_column"
    }
    assert confidences == {1.0}


@requires_sql_grammar
def test_recovered_ranges_are_byte_offsets_under_non_ascii():
    """Segment offsets are converted char -> UTF-8 byte; a non-ASCII comment
    ahead of the DDL would otherwise slide every recovered range."""
    text = (
        "-- naïve café — non-ASCII prelude\n"
        "CREATE TABLE [dbo].[Café] ([Id] INT NOT NULL);\n"
    )
    _sf, result = _extract_text(text)
    raw = text.encode("utf-8")
    table = next(s for s in result.symbols if s.name == "Café")
    assert raw[table.range.start_byte:].startswith(b"CREATE TABLE")
    assert raw[table.range.start_byte:table.range.end_byte].endswith(b")")


@requires_sql_grammar
def test_symbol_order_is_source_order_and_repeatable():
    """Recovery order must not depend on set iteration (per-process string
    hashing), or a parallel index run would diverge from a serial one."""
    _sf, first = _extract_multi()[0], _extract_multi()[2]
    _sf2, second = _extract_multi()[0], _extract_multi()[2]
    recovered = [
        s.name for s in first.symbols
        if s.kind in ("create_table", "create_temp_table")
    ]
    assert recovered == ["Customer", "Orders", "OrderLine", "#OrderStaging"]
    assert [s.id for s in first.symbols] == [s.id for s in second.symbols]


# ---------------------------------------------------------------------------
# The no-grammar path (Milestone 4's defensive half)
# ---------------------------------------------------------------------------


@pytest.fixture()
def no_sql_grammar(monkeypatch):
    """Simulate a deps-less interpreter: no tree-sitter parser at all."""
    monkeypatch.setattr(
        SymbolExtractor,
        "_parser_for_language",
        lambda self, language: (None, None),
    )


def test_fallback_path_yields_real_tables_columns_and_resolved_fks(no_sql_grammar):
    sf, _text, result = _extract_multi()
    assert "no tree-sitter parser available" in " ".join(result.parse_errors)
    assert _tables(result) == {
        "Customer": "create_table",
        "Orders": "create_table",
        "OrderLine": "create_table",
        "#OrderStaging": "create_temp_table",
    }
    assert _columns(result, "Customer")["Name"]["data_type"] == "NVARCHAR(100)"
    fk = {
        (
            e.caller_symbol_id.split(":")[2],
            e.callee_symbol_id.split(":")[2] if e.callee_symbol_id else None,
        )
        for e in _edges(sf, result)
        if e.edge_kind == "foreign_key"
    }
    assert fk == {("Orders", "Customer"), ("OrderLine", "Orders")}


def test_fallback_path_keeps_non_table_definitions(no_sql_grammar):
    _sf, result = _extract_text(
        "CREATE PROCEDURE [dbo].[usp_Get] AS BEGIN SELECT 1; END;\n"
        "CREATE VIEW dbo.v_Orders AS SELECT 1;\n"
    )
    # Bracketed/qualified names are normalized on this path too.
    assert {s.name for s in result.symbols} == {"usp_Get", "v_Orders"}


def test_fallback_path_does_not_invent_symbols_from_prose(no_sql_grammar):
    """The generic definition regex used to match prose in comments — "a
    bracketed CREATE TABLE that also contains NOT NULL" became a symbol named
    ``that``."""
    _sf, _text, result = _extract_multi()
    assert "that" not in {s.name for s in result.symbols}
    # The only generic fallback_definition left is the real CREATE PROCEDURE;
    # every CREATE TABLE was claimed by the segmenter instead.
    assert [
        s.name for s in result.symbols if s.kind == "fallback_definition"
    ] == ["usp_GetOrders"]


def test_fallback_path_normalizes_table_references(no_sql_grammar):
    _sf, result = _extract_text(
        "CREATE TABLE [dbo].[Orders] ([Id] INT NOT NULL);\n"
        "SELECT * FROM [dbo].[Orders] o JOIN #Staging s ON s.Id = o.Id;\n"
    )
    call_names = {r.name for r in result.refs if r.kind == "fallback_call"}
    assert "Orders" in call_names
    assert not any("[" in n for n in call_names)


# ---------------------------------------------------------------------------
# Milestone 5: the SSMS script-folder shape (bracketed TYPES + out-of-line FKs)
#
# The M4 fixtures were hand-written: bare-word types and inline FK constraints.
# Real SQL Server schemas reach us as an SSMS export, which brackets every type
# and puts every constraint in its own trailing ALTER TABLE batch. Each of those
# broke one half of the extractor on the NNG DB unit — 0 columns across all 143
# tables, and 0 foreign keys across all 81 constraints.
# ---------------------------------------------------------------------------


SSMS_REL = "database/tsql_ssms_scripted.sql"


def _extract_ssms():
    text = (FIXTURES / SSMS_REL).read_text(encoding="utf-8", errors="replace")
    sf = _source_file(SSMS_REL, text)
    return sf, text, SymbolExtractor(load_profiles(PROFILE_PATH)).extract(sf, text)


def _fk_pairs(sf, result) -> set[tuple[str | None, str | None]]:
    return {
        (
            e.caller_symbol_id.split(":")[2] if e.caller_symbol_id else None,
            e.callee_symbol_id.split(":")[2] if e.callee_symbol_id else None,
        )
        for e in _edges(sf, result)
        if e.edge_kind == "foreign_key"
    }


def test_bracketed_data_types_still_yield_columns():
    """``[STATE_FIPS] [varchar] (2) NOT NULL`` — a bracketed type with a space
    before its length. The type group used to require a bare word, so the entry
    matched nothing and the column was dropped silently."""
    body = (
        "[STATE_FIPS] [varchar] (2) NOT NULL,\n"
        "[Value] [decimal] (9, 3) NULL,\n"
        "[phone] [dbo].[PhoneNumber] NULL,\n"
        "[systemAssignedKey] [int] IDENTITY(1, 1) NOT NULL\n"
    )
    cols = {name: attrs for name, attrs, _off in _sql_columns_from_body(body)}
    assert set(cols) == {"STATE_FIPS", "Value", "phone", "systemAssignedKey"}
    # Types are normalized to the same bare spelling the AST path reports.
    assert cols["STATE_FIPS"]["data_type"] == "varchar(2)"
    assert cols["Value"]["data_type"] == "decimal(9, 3)"
    # A user-defined type keeps its name, drops the schema qualifier.
    assert cols["phone"]["data_type"] == "PhoneNumber"
    assert cols["phone"]["nullable"] is True
    assert cols["systemAssignedKey"]["nullable"] is False


@requires_sql_grammar
def test_ssms_scripted_schema_has_every_column():
    _sf, _text, result = _extract_ssms()
    assert set(_tables(result)) == {"FipsState", "FipsCounty", "FipsCity"}
    assert set(_columns(result, "FipsState")) == {
        "STATE_FIPS", "STATE_NAME", "Status",
    }
    # Name/Value are grammar keywords — they vanish from the AST entirely.
    assert set(_columns(result, "FipsCounty")) == {
        "FIPS", "COUNTY_NAME", "STATE_FIPS", "Name", "Value",
    }
    assert set(_columns(result, "FipsCity")) == {
        "PLACE_FIPS", "CITY_NAME", "FIPS", "STATE_FIPS", "phone",
        "systemAssignedKey",
    }
    # IDENTITY(1, 1) is part of the column, never a column of its own.
    assert "IDENTITY" not in _columns(result, "FipsCity")


@requires_sql_grammar
def test_out_of_line_alter_table_foreign_keys_resolve():
    """The dominant real-world FK form. Both in-table scans are scoped to a
    CREATE TABLE body, so these were invisible and the schema had no FK edges."""
    sf, _text, result = _extract_ssms()
    assert _fk_pairs(sf, result) == {
        ("FipsCounty", "FipsState"),
        ("FipsCity", "FipsCounty"),
        ("FipsCity", "FipsState"),
    }
    # Every edge resolved — none dangling, none a self edge.
    fks = [e for e in _edges(sf, result) if e.edge_kind == "foreign_key"]
    assert len(fks) == 3
    assert all(e.confidence == 0.85 for e in fks)
    assert all(e.caller_symbol_id != e.callee_symbol_id for e in fks)


@requires_sql_grammar
def test_commented_out_alter_table_foreign_key_is_not_an_edge():
    _sf, _text, result = _extract_ssms()
    assert "GhostTable" not in {r.name for r in result.refs}


@requires_sql_grammar
def test_alter_table_primary_key_is_not_a_foreign_key():
    """``ADD CONSTRAINT ... PRIMARY KEY CLUSTERED`` sits in the same batch shape
    as the FK constraints and must not be mistaken for one."""
    _sf, result = _extract_text(
        "CREATE TABLE [dbo].[A] ([Id] [int] NOT NULL);\n"
        "GO\n"
        "ALTER TABLE [dbo].[A] ADD CONSTRAINT [PK_A] PRIMARY KEY CLUSTERED ([Id])\n"
        "GO\n"
    )
    assert [r for r in result.refs if r.kind == "foreign_key"] == []


@requires_sql_grammar
def test_alter_table_fk_is_attributed_to_the_altered_table():
    """The edge must read child -> parent. The ALTER statement is outside every
    table's range, so without an explicit enclosing symbol the caller would be
    unresolved (``_resolve_caller`` finds no symbol containing that line)."""
    sf, _text, result = _extract_ssms()
    fk = next(
        r for r in result.refs
        if r.kind == "foreign_key" and r.name == "FipsCounty"
    )
    assert fk.enclosing_symbol_id is not None
    assert fk.enclosing_symbol_id.split(":")[2] == "FipsCity"
    # Evidence is the real ALTER text, not the masked copy.
    assert "FK_City_County" in fk.evidence
    assert "ALTER TABLE" in fk.evidence


@requires_sql_grammar
def test_alter_table_fk_emitted_once_not_per_scan():
    """A clause both the ALTER scan and a grammar create_table node see must
    dedupe — the two anchor a ref at the same absolute offset on purpose."""
    sf, _text, result = _extract_ssms()
    fk_ids = [r.id for r in result.refs if r.kind == "foreign_key"]
    assert len(fk_ids) == len(set(fk_ids)) == 3


def test_alter_table_fks_resolve_on_the_fallback_path(no_sql_grammar):
    sf, _text, result = _extract_ssms()
    assert _fk_pairs(sf, result) == {
        ("FipsCounty", "FipsState"),
        ("FipsCity", "FipsCounty"),
        ("FipsCity", "FipsState"),
    }
    assert _columns(result, "FipsState")["STATE_FIPS"]["data_type"] == "varchar(2)"


def test_constraints_only_script_still_emits_fk_refs(no_sql_grammar):
    """A schema can put its constraints in a separate file from its tables. There
    is no local table symbol to anchor to, so the ref carries no enclosing
    symbol — but it must still exist rather than being dropped."""
    _sf, result = _extract_text(
        "ALTER TABLE [dbo].[Orders] ADD CONSTRAINT [FK_O_C] "
        "FOREIGN KEY ([CustomerId]) REFERENCES [dbo].[Customer] ([Id])\n"
        "GO\n",
        rel="database/constraints_only.sql",
    )
    fks = [r for r in result.refs if r.kind == "foreign_key"]
    assert [r.name for r in fks] == ["Customer"]
    assert fks[0].enclosing_symbol_id is None
