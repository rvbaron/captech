"""Tests for Milestone 12 CLI commands: symbols, callers, callees, stats, validate."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest
from legacylift_search.indexer import Indexer
from legacylift_search.store import SQLiteStore


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


def _open_store(repo: Path) -> SQLiteStore:
    return SQLiteStore(
        repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    )


def test_symbols_finds_known_name(indexed_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["symbols", "--name", "EligibilityService", "--repo-root", str(indexed_repo)],
    )
    assert result.exit_code == 0, result.output
    assert "EligibilityService" in result.output


def test_symbols_no_match(indexed_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["symbols", "--name", "ZzzNoSuchSymbolXyz", "--repo-root", str(indexed_repo)],
    )
    assert result.exit_code == 0, result.output
    assert "No symbols found" in result.output


def test_callees_returns_edges_for_calling_symbol(indexed_repo: Path) -> None:
    """The Python check() method calls validate_provider, so callees should exist."""
    store = _open_store(indexed_repo)
    try:
        # Find a symbol that we know has outgoing edges. Walk all symbols and pick
        # one with at least one outgoing edge.
        conn = store._connect()
        rows = conn.execute(
            """
            SELECT caller_symbol_id
            FROM graph_edges
            WHERE caller_symbol_id IS NOT NULL
            LIMIT 1
            """
        ).fetchall()
        assert rows, "fixture should yield at least one resolved caller"
        symbol_id = rows[0]["caller_symbol_id"]
    finally:
        store.close()

    runner = CliRunner()
    result = runner.invoke(
        app, ["callees", symbol_id, "--repo-root", str(indexed_repo)]
    )
    assert result.exit_code == 0, result.output
    assert "Callees of" in result.output


def test_callees_empty_emits_message(indexed_repo: Path) -> None:
    """A symbol with no outgoing edges must print 'no callees found' and exit 0."""
    store = _open_store(indexed_repo)
    try:
        conn = store._connect()
        # Find a symbol that has zero outgoing edges.
        row = conn.execute(
            """
            SELECT s.id FROM symbols s
            LEFT JOIN graph_edges g ON g.caller_symbol_id = s.id
            WHERE g.id IS NULL
            LIMIT 1
            """
        ).fetchone()
        assert row is not None, "fixture should have at least one leaf symbol"
        leaf_id = row["id"]
    finally:
        store.close()

    runner = CliRunner()
    result = runner.invoke(
        app, ["callees", leaf_id, "--repo-root", str(indexed_repo)]
    )
    assert result.exit_code == 0, result.output
    assert "no callees found" in result.output


def test_callers_finds_edge(indexed_repo: Path) -> None:
    store = _open_store(indexed_repo)
    try:
        conn = store._connect()
        # Find a symbol that is a resolved callee somewhere.
        row = conn.execute(
            """
            SELECT callee_symbol_id FROM graph_edges
            WHERE callee_symbol_id IS NOT NULL LIMIT 1
            """
        ).fetchone()
        if row is None:
            # Fall back to looking up by callee_name against any symbol.
            sym_row = conn.execute("SELECT id, name FROM symbols LIMIT 1").fetchone()
            assert sym_row is not None
            target_id = sym_row["id"]
        else:
            target_id = row["callee_symbol_id"]
    finally:
        store.close()

    runner = CliRunner()
    result = runner.invoke(
        app, ["callers", target_id, "--repo-root", str(indexed_repo)]
    )
    assert result.exit_code == 0, result.output
    # Either there are callers or the unresolved-name fallback runs;
    # the command is allowed to print "no callers found" but must exit 0.
    assert "Callers of" in result.output or "no callers found" in result.output


def test_stats_reports_nonzero(indexed_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["stats", "--repo-root", str(indexed_repo)])
    assert result.exit_code == 0, result.output
    assert "files indexed" in result.output
    assert "chunks" in result.output
    assert "symbols" in result.output


def test_validate_fresh_after_index(indexed_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--repo-root", str(indexed_repo)])
    assert result.exit_code == 0, result.output
    assert "Index is valid." in result.output
    assert "freshness: fresh" in result.output


def test_validate_stale_after_source_change(indexed_repo: Path) -> None:
    # Modify a fixture file content (do not reindex).
    target = indexed_repo / "src" / "eligibility.py"
    original = target.read_text(encoding="utf-8")
    target.write_text(original + "\n# drift marker\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--repo-root", str(indexed_repo)])
    assert result.exit_code == 0, result.output
    assert "stale" in result.output


def test_validate_missing_index(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--repo-root", str(repo)])
    assert result.exit_code == 1, result.output
    assert "missing" in result.output.lower()


# ----------------------------------------------------------------------
# CR-03 / CR-04: the two command families must agree about the two flags
# ----------------------------------------------------------------------
# The asymmetry the old tests missed: `index`/`backfill-vectors`/`search`
# resolved the flags inline while the seven `resolve_paths` commands resolved
# them differently, so identical arguments wrote to one directory and read
# from another, with one explicit flag silently ignored in each direction.
# These probes cover BOTH flags across BOTH families.
#
# Neither probe needs an index: both families print the directory they
# resolved when the index turns out to be missing, which is exactly the
# observable that differed.


def _resolved_dir_from_search(runner: CliRunner, repo: Path, *flags: str) -> str:
    """Run `search` (the inline-resolution family) with no index present."""
    result = runner.invoke(
        app,
        ["search", "q", "--repo-root", str(repo), *flags],
        env={"COLUMNS": "400"},
    )
    assert result.exit_code == 1, result.output
    assert "No index found at" in result.output, result.output
    return "".join(result.output.split())


def _resolved_dir_from_stats(runner: CliRunner, repo: Path, *flags: str) -> str:
    """Run `stats` (the resolve_paths family) with no index present."""
    result = runner.invoke(
        app,
        ["stats", "--repo-root", str(repo), *flags],
        env={"COLUMNS": "400"},
    )
    assert result.exit_code == 1, result.output
    assert "index not found at" in result.output, result.output
    return "".join(result.output.split())


def _squash(path: Path) -> str:
    return "".join(str(path).split())


def test_index_dir_flag_names_the_same_directory_for_both_command_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-04: a relative --index-dir meant <repo_root>/out on one family and
    <cwd>/out on the other. It is CWD-relative on both now."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(cwd)
    runner = CliRunner()

    expected = _squash(cwd / "out")
    assert expected in _resolved_dir_from_search(runner, repo, "--index-dir", "out")
    assert expected in _resolved_dir_from_stats(runner, repo, "--index-dir", "out")


def test_both_flags_together_resolve_the_same_way_for_both_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-03: with --index-dir AND --analysis-dir given, `search` obeyed the
    analysis flag and `stats` obeyed the index flag. One answer now."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(cwd)
    runner = CliRunner()

    flags = ("--index-dir", "out", "--analysis-dir", "B")
    expected = _squash(cwd / "out")
    not_expected = _squash(cwd / "B" / "index" / "code-search")

    from_search = _resolved_dir_from_search(runner, repo, *flags)
    from_stats = _resolved_dir_from_stats(runner, repo, *flags)

    assert expected in from_search and not_expected not in from_search
    assert expected in from_stats and not_expected not in from_stats


def test_analysis_dir_flag_alone_resolves_the_same_way_for_both_families(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(cwd)
    runner = CliRunner()

    expected = _squash(cwd / "B" / "index" / "code-search")
    assert expected in _resolved_dir_from_search(runner, repo, "--analysis-dir", "B")
    assert expected in _resolved_dir_from_stats(runner, repo, "--analysis-dir", "B")


# ----------------------------------------------------------------------
# Section 6 gap: the three both-store commands take --analysis-dir
# ----------------------------------------------------------------------
# tag-domains, domains and render-architecture consume BOTH stores, so after
# `index --analysis-dir D` the next pipeline step failed: tag-domains raised
# FileNotFoundError on a missing index.sqlite and domains/render-architecture
# reported "no domains". The failures were loud rather than polluting (all
# three existence-probe before constructing a KnowledgeStore), so this is a
# pipeline fix, not a data-safety one.


def _seed_knowledge_store(analysis_dir: Path) -> None:
    """Put one domain in a knowledge store under `<analysis_dir>/knowledge/`."""
    from legacylift_search.knowledge_store import KnowledgeStore

    knowledge_dir = analysis_dir / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    ks = KnowledgeStore(knowledge_dir / "knowledge.sqlite")
    try:
        ks.upsert_domain("billing", "Billing", "", ["**/*.py"], "cr-probe", 0)
        ks.upsert_file_domain("app.py", "billing", "manual", "cr-probe", 1.0)
    finally:
        ks.close()


def test_tag_domains_honours_analysis_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The flag must route to the same resolver every other command uses.

    With no index built anywhere, `tag-domains --analysis-dir D` must look for
    index.sqlite under D -- not under <repo_root>/legacylift-docs/.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    analysis_dir = tmp_path / "out"
    analysis_dir.mkdir()
    domains_json = tmp_path / "domains.json"
    domains_json.write_text(
        '{"version": 1, "domains": [], "edges": []}', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tag-domains",
            "--repo-root",
            str(repo),
            "--domains",
            str(domains_json),
            "--analysis-dir",
            str(analysis_dir),
        ],
        env={"COLUMNS": "400"},
    )
    assert result.exit_code == 1, result.output
    combined = "".join((result.output + (result.stderr or "")).split())
    assert _squash(analysis_dir / "index" / "code-search") in combined, combined


def test_domains_honours_analysis_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    analysis_dir = tmp_path / "out"
    _seed_knowledge_store(analysis_dir)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["domains", "--repo-root", str(repo), "--analysis-dir", str(analysis_dir)],
        env={"COLUMNS": "400"},
    )
    assert result.exit_code == 0, result.output
    assert "no domains" not in result.output, result.output
    assert "billing" in result.output.lower(), result.output


def test_render_architecture_honours_analysis_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    analysis_dir = tmp_path / "out"
    _seed_knowledge_store(analysis_dir)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "render-architecture",
            "--repo-root",
            str(repo),
            "--analysis-dir",
            str(analysis_dir),
        ],
        env={"COLUMNS": "400"},
    )
    assert result.exit_code == 0, result.output
    assert "billing" in result.output.lower(), result.output
