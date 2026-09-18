"""Tests for Milestone 2 of `domain-enhancements-plan.md`: the domain
schema, the KnowledgeStore query API, the `domains` CLI command, and the
`stats` domain summary line.

Covers: schema creation, the `list_domains()` ordering guarantee (issue
#14), per-domain/chunk counts, the reserved-`unassigned` exclusion from
`list_domains()`, and graceful degradation when a sibling database
(`index.sqlite` or `knowledge.sqlite`) is absent.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest, resolve_knowledge_dir
from legacylift_search.indexer import Indexer
from legacylift_search.knowledge_store import KnowledgeStore

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _build_index(repo: Path) -> None:
    manifest = Manifest()
    manifest.embedding.provider = "hash"
    manifest.embedding.dimension = 64
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")


@pytest.fixture
def indexed_repo(tmp_path: Path) -> Path:
    repo = _copy_fixture(tmp_path)
    _build_index(repo)
    return repo


def _knowledge_path(repo: Path) -> Path:
    manifest = Manifest()
    return resolve_knowledge_dir(repo, manifest) / "knowledge.sqlite"


def _seed_two_domains(ks: KnowledgeStore) -> None:
    """Mirror the Concrete Steps `seed_domains.py` helper."""
    ks.upsert_domain("core-services", "Core Services", "", ["src/**"], "manual-test", 0)
    ks.upsert_domain("data-layer", "Data Layer", "", ["database/**"], "manual-test", 1)
    ks.upsert_file_domain("src/eligibility.py", "core-services", "manual", "manual-test", 1.0)
    ks.upsert_file_domain("database/schema.sql", "data-layer", "manual", "manual-test", 1.0)
    ks.upsert_file_domain("mainframe/PROVIDER.cbl", "unassigned", "glob", "manual-test", 1.0)


# ---------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------


def test_migrate_creates_domain_tables():
    """`domains`, `domain_edges`, and `file_domains` exist after migrate(),
    plus the `file_domains(domain)` index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            conn = ks._connect()
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert {"domains", "domain_edges", "file_domains"} <= tables

            indexes = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
            assert "ix_file_domains_domain" in indexes
        finally:
            ks.close()


def test_file_domains_source_check_constraint():
    """`source` must be 'glob' or 'manual' — enforced by the CHECK
    constraint, not just application discipline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                ks.upsert_file_domain("x.py", "unassigned", "bogus-source", None, 1.0)
        finally:
            ks.close()


def test_migrate_is_idempotent_alongside_existing_rows():
    """Re-running migrate() (e.g. on reopen) does not clobber existing rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        ks.upsert_domain("core-services", "Core Services", "", ["src/**"], None, 0)
        ks.close()

        ks2 = KnowledgeStore(sqlite_path)  # migrate() runs again in __init__
        try:
            ks2.migrate()  # explicit re-run too
            domains = ks2.list_domains()
            assert [d.domain_id for d in domains] == ["core-services"]
        finally:
            ks2.close()


# ---------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------


def test_list_domains_orders_by_display_order_then_domain_id():
    """Load-bearing ordering (issue #14): ORDER BY display_order, domain_id
    — NOT insertion/PK order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            # Insert deliberately out of both alphabetical and display_order order.
            ks.upsert_domain("zzz-domain", "Zzz", "", ["a/**"], None, 1)
            ks.upsert_domain("bbb-domain", "Bbb", "", ["c/**"], None, 0)
            ks.upsert_domain("aaa-domain", "Aaa", "", ["b/**"], None, 0)

            domains = ks.list_domains()
            assert [d.domain_id for d in domains] == [
                "aaa-domain",
                "bbb-domain",
                "zzz-domain",
            ]
        finally:
            ks.close()


def test_list_domains_round_trips_path_globs_as_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            ks.upsert_domain(
                "claims-management",
                "Claims Management",
                "Intake and adjudication.",
                ["src/Claims/**", "**/Claim*Service/**"],
                "run-1",
                0,
            )
            [rec] = ks.list_domains()
            assert rec.name == "Claims Management"
            assert rec.description == "Intake and adjudication."
            assert rec.path_globs == ["src/Claims/**", "**/Claim*Service/**"]
            assert rec.assess_run_id == "run-1"
            assert rec.display_order == 0
        finally:
            ks.close()


def test_list_domains_never_returns_reserved_unassigned():
    """`unassigned` is a file_domains VALUE only — never a domains-table row,
    so list_domains() must never surface it (issues #28/#30), even when
    file_domains rows carry that value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            ks.upsert_domain("core-services", "Core Services", "", ["src/**"], None, 0)
            ks.upsert_file_domain("weird/file.py", "unassigned", "glob", None, 1.0)
            ks.upsert_file_domain("weird/file2.py", "unassigned", "glob", None, 1.0)

            domain_ids = [d.domain_id for d in ks.list_domains()]
            assert "unassigned" not in domain_ids
            assert domain_ids == ["core-services"]

            # But the reserved value is still queryable via files_for_domain.
            assert sorted(ks.files_for_domain("unassigned")) == [
                "weird/file.py",
                "weird/file2.py",
            ]
        finally:
            ks.close()


def test_domain_edge_default_kind_and_pk():
    """A missing/None `kind` normalizes to "" (issue #51), and the PK is
    (from_domain, to_domain, kind) so INSERT OR REPLACE dedups correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            ks.upsert_domain_edge("workflow", "claims", None, "calls 11x")
            ks.upsert_domain_edge("workflow", "claims", None, "calls 12x")  # replace
            edges = ks.get_domain_edges()
            assert len(edges) == 1
            assert edges[0].kind == ""
            assert edges[0].evidence == "calls 12x"

            ks.upsert_domain_edge("workflow", "claims", "shares-data", "shared DB")
            edges = ks.get_domain_edges()
            assert len(edges) == 2
        finally:
            ks.close()


def test_files_for_domain_and_domain_for_file_and_counts():
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            _seed_two_domains(ks)

            assert ks.files_for_domain("core-services") == ["src/eligibility.py"]
            assert ks.files_for_domain("data-layer") == ["database/schema.sql"]
            assert ks.files_for_domain("unassigned") == ["mainframe/PROVIDER.cbl"]
            assert ks.files_for_domain("no-such-domain") == []

            assert ks.domain_for_file("src/eligibility.py") == "core-services"
            assert ks.domain_for_file("nope.py") is None

            counts = ks.domain_file_counts()
            assert counts == {
                "core-services": 1,
                "data-layer": 1,
                "unassigned": 1,
            }
        finally:
            ks.close()


def test_upsert_file_domain_manual_wins_via_replace():
    """upsert_file_domain is INSERT OR REPLACE keyed on relative_path — a
    second call for the same path overwrites the first."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            ks.upsert_file_domain("src/eligibility.py", "unassigned", "glob", None, 1.0)
            assert ks.domain_for_file("src/eligibility.py") == "unassigned"

            ks.upsert_file_domain(
                "src/eligibility.py", "core-services", "manual", "manual-test", 1.0
            )
            assert ks.domain_for_file("src/eligibility.py") == "core-services"
            assert ks.domain_file_counts() == {"core-services": 1}
        finally:
            ks.close()


# ---------------------------------------------------------------------
# `domains` CLI command
# ---------------------------------------------------------------------


def test_domains_cli_no_knowledge_db(tmp_path: Path):
    """Before any index/tag-domains run, knowledge.sqlite does not exist.
    The command must not construct KnowledgeStore (which would silently
    create it, issue #33) and must print a clear message instead of raising."""
    repo = _copy_fixture(tmp_path)
    knowledge_path = _knowledge_path(repo)
    assert not knowledge_path.exists()

    runner = CliRunner()
    result = runner.invoke(app, ["domains", "--repo-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "no domains" in result.output.lower()
    assert "tag-domains" in result.output
    # The existence probe must not have side-effected a fresh DB into being.
    assert not knowledge_path.exists()


def test_domains_cli_knowledge_db_present_no_rows(indexed_repo: Path):
    """Milestone 1's indexer already opens+migrates the knowledge store, so
    the file exists but has zero domain rows after a plain `index` run."""
    knowledge_path = _knowledge_path(indexed_repo)
    assert knowledge_path.exists()

    runner = CliRunner()
    result = runner.invoke(app, ["domains", "--repo-root", str(indexed_repo)])
    assert result.exit_code == 0, result.output
    assert "no domains" in result.output.lower()


def test_domains_cli_lists_seeded_domains_with_counts(indexed_repo: Path):
    """The full Milestone 2 acceptance: hand-inserted domains list with
    correct file and chunk counts, plus a trailing Unassigned line."""
    knowledge_path = _knowledge_path(indexed_repo)
    ks = KnowledgeStore(knowledge_path)
    try:
        _seed_two_domains(ks)
    finally:
        ks.close()

    runner = CliRunner()
    result = runner.invoke(app, ["domains", "--repo-root", str(indexed_repo)])
    assert result.exit_code == 0, result.output
    output = result.output
    assert "Core Services" in output
    assert "Data Layer" in output
    assert "Unassigned" in output


def test_domains_cli_index_absent_chunk_counts_are_na(tmp_path: Path):
    """If index.sqlite does not exist (repo never indexed), chunk counts
    degrade to 'n/a' instead of raising (issues #19/#33)."""
    repo = _copy_fixture(tmp_path)
    manifest = Manifest()
    knowledge_dir = resolve_knowledge_dir(repo, manifest)
    ks = KnowledgeStore(knowledge_dir / "knowledge.sqlite")
    try:
        ks.upsert_domain("core-services", "Core Services", "", ["src/**"], None, 0)
        ks.upsert_file_domain("src/eligibility.py", "core-services", "manual", None, 1.0)
    finally:
        ks.close()

    index_sqlite = repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    assert not index_sqlite.exists()

    runner = CliRunner()
    result = runner.invoke(app, ["domains", "--repo-root", str(repo)])
    assert result.exit_code == 0, result.output
    assert "n/a" in result.output


def test_domain_counts_intersected_drops_ghost_rows(indexed_repo: Path):
    """A file_domains row for a path the discoverer no longer finds (a
    'ghost row', issue #55) must not be counted — the raw
    `domain_file_counts()` would still show 2, but the discovered-set
    intersection the `domains`/`stats` commands apply must show 1."""
    from legacylift_search.cli import _domain_counts_intersected
    from legacylift_search.config import Manifest

    knowledge_path = _knowledge_path(indexed_repo)
    ks = KnowledgeStore(knowledge_path)
    try:
        ks.upsert_domain("core-services", "Core Services", "", ["src/**"], None, 0)
        ks.upsert_file_domain("src/eligibility.py", "core-services", "manual", None, 1.0)
        # Ghost row: a path that was never discovered in this fixture.
        ks.upsert_file_domain(
            "src/does_not_exist_anymore.py", "core-services", "manual", None, 1.0
        )
        assert ks.domain_file_counts()["core-services"] == 2

        records = ks.list_domains()
        by_domain, discovered_paths = _domain_counts_intersected(
            ks, records, indexed_repo, Manifest()
        )
        assert "src/does_not_exist_anymore.py" not in discovered_paths
        assert by_domain["core-services"] == ["src/eligibility.py"]
    finally:
        ks.close()


# ---------------------------------------------------------------------
# `stats` domain summary
# ---------------------------------------------------------------------


def test_stats_cli_no_domains_yet(indexed_repo: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["stats", "--repo-root", str(indexed_repo)])
    assert result.exit_code == 0, result.output
    assert "domains: no domains yet" in result.output


def test_stats_cli_domain_summary_line(indexed_repo: Path):
    knowledge_path = _knowledge_path(indexed_repo)
    ks = KnowledgeStore(knowledge_path)
    try:
        _seed_two_domains(ks)
    finally:
        ks.close()

    runner = CliRunner()
    result = runner.invoke(app, ["stats", "--repo-root", str(indexed_repo)])
    assert result.exit_code == 0, result.output
    assert "domains: 2 domains" in result.output
    # "files tagged" counts CLASSIFIED files only (excludes the reserved
    # `unassigned`), matching the plan's M2 example and `validate` coverage;
    # the seed has 2 classified (src/eligibility.py, database/schema.sql) + 1
    # unassigned (mainframe/PROVIDER.cbl).
    assert "2 files tagged" in result.output
    assert "1 unassigned" in result.output
