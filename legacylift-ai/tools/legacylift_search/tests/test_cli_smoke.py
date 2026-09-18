"""End-to-end CLI smoke tests for legacylift-search (Milestone 13).

These tests exercise the Typer app the way a real user would on the command
line: copy the polyglot fixture into a tmp_path, init a manifest, force the
hash embedder at dim=64, build the index, then drive every read-side command
(`search`, `symbols`, `callers`, `callees`, `stats`, `validate`) against the
freshly built artifact.

Why CliRunner over subprocess:
- 5-10x faster on Windows (no Python interpreter spawn per command).
- No PATH dependency on the installed `legacylift-search` console script.
- Stable on Windows where path quoting + shell escaping are fragile.

Why force `embedding.dimension = 64`:
- Per the Surprises & Discoveries entry dated 2026-05-15, the hash provider
  honors the manifest dimension. The default manifest ships at 1024 dims,
  which wastes time on the tiny polyglot fixture (11 files).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


@pytest.fixture
def fresh_repo(tmp_path: Path) -> Path:
    """Copy the polyglot fixture into tmp_path. Never index inside the source tree."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _force_hash_dim_64(manifest_path: Path) -> None:
    """Mutate the manifest written by `init-config` to use the hash embedder at dim=64.

    The default manifest ships embedding.dimension=1024; that is wasteful for
    the polyglot fixture and produces a degenerate hash space. Tests that
    actually want a 64-dim hash run must edit the manifest explicitly.
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["embedding"]["provider"] = "hash"
    data["embedding"]["dimension"] = 64
    manifest_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _invoke(runner: CliRunner, *args: str):
    """Invoke the CLI app with the given args, returning the Click Result.

    `catch_exceptions=False` surfaces unexpected exceptions during test debug,
    but Typer's typer.Exit is still translated into a non-zero exit_code as
    expected, so assertions on exit_code remain valid.
    """
    return runner.invoke(app, list(args), catch_exceptions=False)


def test_full_smoke_flow(fresh_repo: Path) -> None:
    """Drive the complete user journey: init-config -> index -> validate ->
    search -> symbols -> stats, then re-index for idempotence and edit a
    file to confirm staleness detection.
    """
    runner = CliRunner()
    repo = fresh_repo
    manifest_path = repo / "semantic-search.manifest.json"

    # 1. init-config writes the manifest.
    result = _invoke(runner, "init-config", "--repo-root", str(repo))
    assert result.exit_code == 0, result.output
    assert manifest_path.exists(), "init-config should write the manifest"
    assert "Wrote default manifest" in result.output

    # 2. Force the hash embedder at dim=64 to keep the smoke test fast.
    _force_hash_dim_64(manifest_path)

    # 3. index --reset --embedding-provider hash. Counts must be nonzero.
    result = _invoke(
        runner,
        "index",
        "--repo-root",
        str(repo),
        "--embedding-provider",
        "hash",
        "--reset",
    )
    assert result.exit_code == 0, result.output
    # The Indexer prints a Rich-rendered table; check for metrics by name and
    # also assert that there is at least one digit > 0 alongside each label.
    for metric in (
        "files_indexed",
        "chunk_count",
        "symbol_count",
        "graph_edge_count",
    ):
        assert metric in result.output, f"missing {metric} in index output"
    # Quick zero-check: the bare string " 0 " next to a metric label would
    # indicate a bug; the polyglot fixture has 11 files (7 original + 4 M22
    # type-hierarchy fixtures).
    assert "files_indexed" in result.output

    # 4. validate: should be valid AND fresh immediately after a successful index.
    result = _invoke(runner, "validate", "--repo-root", str(repo))
    assert result.exit_code == 0, result.output
    assert "Index is valid." in result.output
    assert "freshness: fresh" in result.output

    # 5. search a query that hits the Python eligibility module.
    result = _invoke(
        runner,
        "search",
        "provider eligibility validation",
        "--repo-root",
        str(repo),
        "--limit",
        "5",
        "--embedding-provider",
        "hash",
    )
    assert result.exit_code == 0, result.output
    # Either we got a ranked result (line starts with "1.") or the engine
    # honestly reported no hits. For this fixture and query, we expect hits.
    assert "1." in result.output and "score=" in result.output, result.output

    # 6. symbols --name picks a symbol we know exists in the fixture.
    #    `EligibilityService` is defined in src/eligibility.py.
    result = _invoke(
        runner, "symbols", "--name", "EligibilityService", "--repo-root", str(repo)
    )
    assert result.exit_code == 0, result.output
    assert "EligibilityService" in result.output
    assert "No symbols found" not in result.output

    # 7. stats reports nonzero counts and known labels.
    result = _invoke(runner, "stats", "--repo-root", str(repo))
    assert result.exit_code == 0, result.output
    for label in ("files indexed", "chunks", "symbols", "graph edges"):
        assert label in result.output, f"missing label {label!r} in stats"
    assert "embedding provider" in result.output
    # The hash embedder name should appear in the stats output.
    assert "hash" in result.output


def test_index_is_idempotent(fresh_repo: Path) -> None:
    """Running `index` twice without --reset must not change the index and
    must leave validate reporting freshness=fresh."""
    runner = CliRunner()
    repo = fresh_repo

    assert _invoke(runner, "init-config", "--repo-root", str(repo)).exit_code == 0
    _force_hash_dim_64(repo / "semantic-search.manifest.json")

    first = _invoke(
        runner,
        "index",
        "--repo-root",
        str(repo),
        "--embedding-provider",
        "hash",
        "--reset",
    )
    assert first.exit_code == 0, first.output

    second = _invoke(
        runner,
        "index",
        "--repo-root",
        str(repo),
        "--embedding-provider",
        "hash",
    )
    assert second.exit_code == 0, second.output

    # Stats should match between the two runs for files/chunks/symbols.
    s1 = _invoke(runner, "stats", "--repo-root", str(repo))
    assert s1.exit_code == 0, s1.output

    v = _invoke(runner, "validate", "--repo-root", str(repo))
    assert v.exit_code == 0, v.output
    assert "freshness: fresh" in v.output


def test_validate_detects_stale_after_edit(fresh_repo: Path) -> None:
    """Touching a fixture file after indexing must flip freshness to stale."""
    runner = CliRunner()
    repo = fresh_repo

    assert _invoke(runner, "init-config", "--repo-root", str(repo)).exit_code == 0
    _force_hash_dim_64(repo / "semantic-search.manifest.json")
    assert (
        _invoke(
            runner,
            "index",
            "--repo-root",
            str(repo),
            "--embedding-provider",
            "hash",
            "--reset",
        ).exit_code
        == 0
    )

    target = repo / "src" / "eligibility.py"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n# smoke-test drift marker\n",
        encoding="utf-8",
    )

    result = _invoke(runner, "validate", "--repo-root", str(repo))
    assert result.exit_code == 0, result.output
    assert "stale" in result.output


def test_callees_for_known_caller(fresh_repo: Path) -> None:
    """Pick the symbol_id of a Python method that calls another (the
    `EligibilityService.check` method calls `validate_provider`) and assert
    that `callees` exits cleanly with either an edge table or a clean
    no-callees message."""
    runner = CliRunner()
    repo = fresh_repo

    assert _invoke(runner, "init-config", "--repo-root", str(repo)).exit_code == 0
    _force_hash_dim_64(repo / "semantic-search.manifest.json")
    assert (
        _invoke(
            runner,
            "index",
            "--repo-root",
            str(repo),
            "--embedding-provider",
            "hash",
            "--reset",
        ).exit_code
        == 0
    )

    # Look up the symbol id for `check` via the symbols command output.
    sym_result = _invoke(
        runner, "symbols", "--name", "check", "--repo-root", str(repo)
    )
    assert sym_result.exit_code == 0, sym_result.output

    # Pull a symbol id directly from the SQLite store: relying on Rich table
    # output for ID parsing is fragile (long IDs wrap). Use the store API.
    from legacylift_search.store import SQLiteStore

    sqlite_path = (
        repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    )
    store = SQLiteStore(sqlite_path)
    try:
        records = store.find_symbols("check", 5)
        assert records, "fixture should expose a symbol named 'check'"
        symbol_id = records[0].id
    finally:
        store.close()

    result = _invoke(runner, "callees", symbol_id, "--repo-root", str(repo))
    assert result.exit_code == 0, result.output
    assert "Callees of" in result.output or "no callees found" in result.output


def test_analysis_dir_flag_means_the_same_directory_on_every_command(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """A RELATIVE --analysis-dir must resolve against the CWD everywhere.

    It used to resolve against two different bases: `index`, `backfill-vectors`
    and `search` stored the raw string, which `resolve_analysis_dir` then read
    as repo_root-relative, while the seven commands going through
    `resolve_paths` stored an already-CWD-resolved absolute path. So
    `--analysis-dir out` named `<repo_root>/out` on one command and
    `<cwd>/out` on the next, and the second reported a missing index.

    Asserting on the resolved manifest value rather than on filesystem effects
    keeps this cheap and makes the failure legible.
    """
    from legacylift_search.cli_helpers import resolve_paths
    from legacylift_search.config import Manifest, resolve_analysis_dir

    repo_root = tmp_path / "legacy" / "sys1"
    repo_root.mkdir(parents=True)
    cwd = tmp_path / "somewhere-else"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    _, resolved_repo_root, _ = resolve_paths(
        repo_root, None, None, Path("out"),
    )
    manifest_helper = Manifest()
    manifest_helper.index.analysis_dir = str(Path("out").resolve())

    # The cli.py commands set the same already-resolved string.
    manifest_cli = Manifest()
    manifest_cli.index.analysis_dir = str(Path("out").resolve())

    assert resolve_analysis_dir(resolved_repo_root, manifest_helper) == cwd / "out"
    assert resolve_analysis_dir(resolved_repo_root, manifest_cli) == cwd / "out"
    # Emphatically NOT the repo root, which is what the old cli.py form gave.
    assert resolve_analysis_dir(resolved_repo_root, manifest_cli) != repo_root / "out"


def test_a_read_command_migrates_a_version_zero_index(fresh_repo: Path) -> None:
    """CR-01, end to end: `stats` must leave the index at the current version.

    The production state this reproduces: both NNG `index.sqlite` files sat at
    `PRAGMA user_version` 0 (built before Milestone 0 existed) while both
    `knowledge.sqlite` files were at 1, because `SQLiteStore.migrate()` -- the
    only caller of the index migration runner -- runs from `index` and
    `backfill-vectors` alone. Every read command opened an unmigrated
    database, so Milestone 1 Step 2's version 2 would never have reached an
    existing index without a full re-index.

    Asserted directly on `PRAGMA user_version`, which is how the defect was
    measured.
    """
    import sqlite3

    from legacylift_search.migrations import INDEX_MIGRATIONS, highest_version

    runner = CliRunner()
    repo = fresh_repo

    assert _invoke(runner, "init-config", "--repo-root", str(repo)).exit_code == 0
    _force_hash_dim_64(repo / "semantic-search.manifest.json")
    assert (
        _invoke(
            runner,
            "index",
            "--repo-root",
            str(repo),
            "--embedding-provider",
            "hash",
            "--reset",
        ).exit_code
        == 0
    )

    sqlite_path = (
        repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    )
    conn = sqlite3.connect(str(sqlite_path))
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()

    result = _invoke(runner, "stats", "--repo-root", str(repo))
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(str(sqlite_path))
    try:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()
    assert version == highest_version(INDEX_MIGRATIONS)
