"""Milestone 24: SQL columns, constraints, and foreign keys.

Exercised against ``tests/fixtures/polyglot_repo/database/schema.sql``, which
defines two ``CREATE TABLE``s with typed columns + ``INT PRIMARY KEY`` and a
real ``FOREIGN KEY (provider_id) REFERENCES providers(provider_id)`` — so it
covers BOTH the tree-sitter column path and the regex FK supplement.

Covers:
1. ``has_column`` facts for providers/members with correct type / nullability /
   PK attributes (tree-sitter path).
2. A ``foreign_key`` *edge* members -> providers from the regex FK supplement
   (asserted per-edge-kind, never on totals).
3. The ``has_column`` fact's ``subject_symbol_id`` equals the table symbol's
   ``id`` (FK-linkage correctness).
4. Coexistence: a clean-parse table yields columns via tree-sitter while an
   unparseable statement still falls back to regex.
"""

from __future__ import annotations

from pathlib import Path

from legacylift_search.extractors import SymbolExtractor, load_profiles
from legacylift_search.graph import GraphBuilder
from legacylift_search.models import SourceFile

from .conftest import requires_sql_grammar

# Every assertion in this module pins tree-sitter-path output (column typing from
# the AST, one create_table node per statement). Without the grammar the
# extractor legitimately produces the regex-recovery shape instead, so these
# skip rather than fail — see conftest for why that distinction matters.
pytestmark = requires_sql_grammar


PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "extractors.json"
FIXTURES = Path(__file__).parent / "fixtures" / "polyglot_repo"
SCHEMA_REL = "database/schema.sql"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extractor() -> SymbolExtractor:
    return SymbolExtractor(load_profiles(PROFILE_PATH))


def _source_file(rel: str) -> SourceFile:
    path = FIXTURES / rel
    text = path.read_text(encoding="utf-8", errors="replace")
    return SourceFile(
        absolute_path=path.resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path=rel,
        language="sql",
        size_bytes=len(text.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )


def _extract_schema():
    sf = _source_file(SCHEMA_REL)
    text = (FIXTURES / SCHEMA_REL).read_text(encoding="utf-8", errors="replace")
    return sf, _extractor().extract(sf, text)


def _extract_text(text: str, rel: str = "adhoc.sql"):
    sf = SourceFile(
        absolute_path=(FIXTURES / rel).resolve(),
        repo_root=FIXTURES.resolve(),
        relative_path=rel,
        language="sql",
        size_bytes=len(text.encode("utf-8")),
        sha256="0" * 64,
        mtime_ns=0,
    )
    return _extractor().extract(sf, text)


def _columns_for_table(result, table_symbol_id: str) -> dict[str, dict]:
    """Map column name -> attributes for has_column facts of one table."""
    out: dict[str, dict] = {}
    for f in result.facts:
        if f.predicate == "has_column" and f.subject_symbol_id == table_symbol_id:
            out[f.object] = f.attributes
    return out


def _table_symbol(result, name: str):
    for s in result.symbols:
        if s.name == name and s.kind == "create_table":
            return s
    raise AssertionError(f"no create_table symbol named {name!r}")


# ---------------------------------------------------------------------------
# Prerequisite: SQL is now on the tree-sitter definition path (identity churn)
# ---------------------------------------------------------------------------


def test_sql_tables_are_treesitter_symbols_not_fallback() -> None:
    """Option (a): correcting the profile node names moves SQL tables off the
    regex ``fallback_definition`` path onto ``create_table`` (one symbol per
    table, table name recoverable)."""
    _sf, result = _extract_schema()
    tables = {s.name: s for s in result.symbols if s.kind == "create_table"}
    assert set(tables) == {"providers", "members"}
    # Name recoverability: the symbol name is the TABLE name, not a column.
    assert tables["providers"].qualified_name == "providers"
    assert tables["members"].qualified_name == "members"
    # No SQL table remained on the regex fallback path.
    assert not any(
        s.kind == "fallback_definition" and s.name in ("providers", "members")
        for s in result.symbols
    )


# ---------------------------------------------------------------------------
# has_column facts (tree-sitter path)
# ---------------------------------------------------------------------------


def test_has_column_facts_for_providers() -> None:
    _sf, result = _extract_schema()
    providers = _table_symbol(result, "providers")
    cols = _columns_for_table(result, providers.id)

    assert set(cols) == {"provider_id", "provider_name", "eligibility_status"}

    # provider_id INT PRIMARY KEY
    assert cols["provider_id"]["data_type"] == "INT"
    assert cols["provider_id"]["primary_key"] is True
    assert cols["provider_id"]["unique"] is False

    # provider_name VARCHAR(255) NOT NULL
    assert cols["provider_name"]["data_type"] == "VARCHAR(255)"
    assert cols["provider_name"]["nullable"] is False
    assert cols["provider_name"]["primary_key"] is False

    # eligibility_status VARCHAR(50)  (no NOT NULL -> nullable)
    assert cols["eligibility_status"]["data_type"] == "VARCHAR(50)"
    assert cols["eligibility_status"]["nullable"] is True


def test_has_column_facts_for_members() -> None:
    _sf, result = _extract_schema()
    members = _table_symbol(result, "members")
    cols = _columns_for_table(result, members.id)

    assert set(cols) == {"member_id", "provider_id", "enrollment_date"}
    assert cols["member_id"]["data_type"] == "INT"
    assert cols["member_id"]["primary_key"] is True
    assert cols["provider_id"]["data_type"] == "INT"
    assert cols["provider_id"]["primary_key"] is False
    assert cols["enrollment_date"]["data_type"] == "DATE"


def test_has_column_facts_are_deterministic_confidence_and_evidence() -> None:
    _sf, result = _extract_schema()
    col_facts = [f for f in result.facts if f.predicate == "has_column"]
    assert col_facts, "no has_column facts emitted"
    for f in col_facts:
        assert f.confidence == 1.0  # deterministic AST-derived
        assert f.evidence  # NOT NULL, node text
        assert f.language == "sql"


def test_has_column_subject_symbol_id_matches_table_id() -> None:
    """FK-linkage correctness: every has_column fact's subject_symbol_id is a
    real table symbol id, and members' columns point at the members table."""
    _sf, result = _extract_schema()
    table_ids = {s.id for s in result.symbols if s.kind == "create_table"}
    members = _table_symbol(result, "members")

    col_facts = [f for f in result.facts if f.predicate == "has_column"]
    assert col_facts
    for f in col_facts:
        assert f.subject_symbol_id in table_ids

    members_cols = [
        f for f in col_facts if f.subject_symbol_id == members.id
    ]
    assert {f.object for f in members_cols} == {
        "member_id",
        "provider_id",
        "enrollment_date",
    }


# ---------------------------------------------------------------------------
# Foreign key: regex supplement -> foreign_key edge
# ---------------------------------------------------------------------------


def test_foreign_key_ref_emitted_by_regex_supplement() -> None:
    _sf, result = _extract_schema()
    fk_refs = [r for r in result.refs if r.kind == "foreign_key"]
    assert len(fk_refs) == 1
    fk = fk_refs[0]
    assert fk.name == "providers"  # referenced table
    members = _table_symbol(result, "members")
    assert fk.enclosing_symbol_id == members.id  # FK lives on the members table


def test_foreign_key_edge_members_to_providers() -> None:
    """A foreign_key EDGE members -> providers, asserted per-edge-kind."""
    sf, result = _extract_schema()
    by_name: dict[str, list] = {}
    for s in result.symbols:
        by_name.setdefault(s.name, []).append(s)

    edges = GraphBuilder().build_edges(sf, result.symbols, result.refs, by_name)

    kind_counts: dict[str, int] = {}
    for e in edges:
        kind_counts[e.edge_kind] = kind_counts.get(e.edge_kind, 0) + 1
    assert kind_counts.get("foreign_key", 0) == 1

    members = _table_symbol(result, "members")
    providers = _table_symbol(result, "providers")
    fk_edges = [e for e in edges if e.edge_kind == "foreign_key"]
    assert len(fk_edges) == 1
    assert fk_edges[0].caller_symbol_id == members.id
    assert fk_edges[0].callee_symbol_id == providers.id


# ---------------------------------------------------------------------------
# Coexistence: tree-sitter columns AND regex fallback for unparseable DDL
# ---------------------------------------------------------------------------


def test_clean_table_columns_and_regex_fallback_coexist() -> None:
    # Clean CREATE TABLE -> tree-sitter symbol + has_column facts.
    clean = _extract_text(
        "CREATE TABLE widgets (\n"
        "    widget_id INT PRIMARY KEY,\n"
        "    label VARCHAR(100) NOT NULL\n"
        ");\n",
        rel="clean.sql",
    )
    table = next(s for s in clean.symbols if s.kind == "create_table")
    assert table.name == "widgets"
    cols = _columns_for_table(clean, table.id)
    assert set(cols) == {"widget_id", "label"}
    assert cols["widget_id"]["primary_key"] is True
    assert cols["label"]["nullable"] is False

    # An unparseable statement (tree-sitter yields no definition) still falls
    # back to a regex fallback_definition symbol — both paths coexist.
    unparseable = _extract_text(
        "CREATE TRIGGER trg_x AFTER INSERT ON providers FOR EACH ROW "
        "BEGIN INSERT INTO audit_log VALUES (1); END;\n",
        rel="trigger.sql",
    )
    kinds = {(s.kind, s.name) for s in unparseable.symbols}
    assert ("fallback_definition", "trg_x") in kinds
    # No has_column facts from the regex fallback path.
    assert not [f for f in unparseable.facts if f.predicate == "has_column"]
