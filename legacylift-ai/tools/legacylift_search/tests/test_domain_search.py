"""Tests for Milestone 6 of `domain-enhancements-plan.md`: the `--domain`
filter on `search`.

Two acceptance parts (from the milestone):

Part 1 (filtering correctness, catches an absent `--domain` filter / #23):
    a term that appears in BOTH `src/**` and `database/**` files, searched with
    `--domain "Data Layer"`, returns only `database/**` results; the same query
    unfiltered spans both.

Part 2 (lexical recall under `--domain`, issue #58 — the LOAD-BEARING part):
    a distinctive token that appears lexically in a `database/**` file but is
    buried at a DEEP global FTS rank (because it also appears in many `src/**`
    files) must still surface in the returned top-N under `--domain`. This
    passes ONLY with the #54 dense pre-RRF re-rank; without it the survivor
    keeps its deep global rank (`1/(60+deep)`-class weight) and never cracks
    the top-N. Part 1 passes even with #54 removed (the fusion-loop drop alone
    keeps results in-domain), so part 2 is the only part that pins the recall
    fix.

Part 2 controls the VECTOR arm with a stub (a `MagicMock` vector store) so the
target `database/**` chunk cannot be a vector freebie — it can only reach the
top-N via the lexical arm. The lexical arm runs against the REAL SQLite FTS5
index, so the deep global rank and the dense re-rank are genuine. This is the
strongest form of "not semantically close to the query embedding": the vector
arm provably never returns it.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import (
    Manifest,
    resolve_index_dir,
    resolve_knowledge_dir,
)
from legacylift_search.domain_tagger import DomainTagger
from legacylift_search.embeddings import HashEmbedder
from legacylift_search.indexer import Indexer
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.search import SearchEngine
from legacylift_search.store import SQLiteStore
from legacylift_search.vector_store import ChromaVectorStore, VectorResult

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"

MARKER = "qzxmarker"  # distinctive; single FTS token, appears once in database


# -- helpers -----------------------------------------------------------------


def _manifest() -> Manifest:
    m = Manifest()
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    return m


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _index(repo: Path, *, reset: bool = True) -> None:
    Indexer(_manifest(), repo).run(
        reset=reset, embedding_provider_override="hash"
    )


def _tag(repo: Path) -> None:
    DomainTagger(_manifest()).tag(repo, repo / "domains.fixture.json")


def _open_real(repo: Path) -> tuple[SQLiteStore, ChromaVectorStore, HashEmbedder]:
    manifest = _manifest()
    index_dir = resolve_index_dir(repo, manifest)
    store = SQLiteStore(index_dir / manifest.index.sqlite_file)
    embedder = HashEmbedder(dimension=64)
    vstore = ChromaVectorStore(
        base_dir=index_dir,
        collection_name=manifest.index.collection_name,
        embedder=embedder,
        metadata={},
    )
    return store, vstore, embedder


def _in_domain_paths(repo: Path, domain_id: str) -> set[str]:
    ks = KnowledgeStore(
        resolve_knowledge_dir(repo, _manifest()) / "knowledge.sqlite"
    )
    try:
        return set(ks.files_for_domain(domain_id))
    finally:
        ks.close()


def _database_chunk_ids(repo: Path, *, exclude_path: str) -> list[str]:
    """Real chunk ids for `database/**` files, excluding one path."""
    manifest = _manifest()
    index_sqlite = resolve_index_dir(repo, manifest) / manifest.index.sqlite_file
    conn = sqlite3.connect(str(index_sqlite))
    try:
        rows = conn.execute(
            "SELECT id FROM chunks WHERE relative_path LIKE 'database/%' "
            "AND relative_path <> ? ORDER BY id",
            (exclude_path,),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


# ===========================================================================
# Part 1 — filtering correctness (end-to-end, real vector + lexical arms)
# ===========================================================================


def test_part1_domain_filter_restricts_to_in_domain(tmp_path: Path) -> None:
    """`provider` appears in both src and database; --domain narrows to db."""
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    store, vstore, embedder = _open_real(repo)
    try:
        engine = SearchEngine(store, vstore, embedder, _manifest().search)

        # Unfiltered: spans both src and database.
        unfiltered = engine.search("provider validation", limit=10)
        prefixes = {r.relative_path.split("/")[0] for r in unfiltered}
        assert unfiltered, "expected unfiltered results"
        assert "src" in prefixes, f"expected src hits, got {prefixes}"
        assert "database" in prefixes, f"expected database hits, got {prefixes}"

        # Filtered to Data Layer: ONLY database/** results.
        db_paths = _in_domain_paths(repo, "data-layer")
        filtered = engine.search(
            "provider validation",
            limit=10,
            domain_id="data-layer",
            in_domain_paths=db_paths,
        )
        assert filtered, "expected filtered results"
        for r in filtered:
            assert r.relative_path.startswith("database/"), (
                f"out-of-domain result leaked: {r.relative_path}"
            )
    finally:
        vstore.close()
        store.close()


# ===========================================================================
# Part 2 — lexical recall under --domain (LOAD-BEARING, issue #58)
# ===========================================================================


def _build_part2_fixture(tmp_path: Path) -> Path:
    """Copy the fixture and engineer the #58 recall scenario.

    * MARKER appears ONCE, as an identifier inside a chunked CREATE TABLE in
      `database/marker.sql` (in-domain, distinctive on the database side).
      It must live inside a chunked statement: the SQL chunker only emits a
      chunk per CREATE statement and drops trailing/standalone comments, so a
      bare comment would never reach FTS.
    * MARKER appears with high term-frequency in MANY `src/**` files, so the
      GLOBAL FTS5 list is dominated by out-of-domain hits and the single
      database occurrence is pushed to a deep global rank.
    * Extra `database/**` DDL files exist so the (stubbed) vector arm has
      >limit real in-domain chunk ids to fill the top-N — the pressure that
      keeps the weak, non-re-ranked lexical survivor out of the top-N.

    The marker's in-domain database file is ``database/marker.sql``.
    """
    repo = _copy_fixture(tmp_path)

    # MARKER once, as a column identifier inside a chunked CREATE TABLE.
    (repo / "database" / "marker.sql").write_text(
        "CREATE TABLE audit_marker (\n"
        "    marker_id INT PRIMARY KEY,\n"
        f"    {MARKER} VARCHAR(255)\n"
        ");\n",
        encoding="utf-8",
    )

    # Many src files with high-TF MARKER -> bury the database hit globally.
    tokens = " ".join([MARKER] * 5)
    for n in range(30):
        content = (
            f"# Noise module {n}: {tokens}.\n\n"
            f"def handler_{n}(payload):\n"
            f"    # {MARKER} processing path {MARKER}\n"
            f"    return payload\n"
        )
        (repo / "src" / f"noise_{n:02d}.py").write_text(
            content, encoding="utf-8"
        )

    # Extra database DDL files (no MARKER) -> plenty of in-domain chunks for
    # the stubbed vector arm.
    for n in range(12):
        (repo / "database" / f"extra_{n:02d}.sql").write_text(
            f"CREATE TABLE widget_{n} (\n"
            f"    widget_id INT PRIMARY KEY,\n"
            f"    widget_name VARCHAR(255) NOT NULL,\n"
            f"    widget_state VARCHAR(50)\n"
            f");\n\n"
            f"CREATE PROCEDURE touch_widget_{n}\n"
            f"    @widget_id INT\n"
            f"AS\n"
            f"BEGIN\n"
            f"    UPDATE widget_{n} SET widget_state = 'SEEN'\n"
            f"    WHERE widget_id = @widget_id;\n"
            f"END;\n",
            encoding="utf-8",
        )

    return repo


def _run_part2(
    repo: Path, *, rerank_enabled: bool
) -> tuple[list, int]:
    """Run the part-2 --domain search. Returns (results, global_marker_rank).

    When `rerank_enabled` is False the #54 dense pre-RRF re-rank is stubbed
    out (survivors keep their global FTS ranks), reproducing the pre-#54
    behavior to prove the test goes RED without the fix.
    """
    store, _vstore_unused, embedder = _open_real(repo)
    # Stub the vector arm so the target can ONLY arrive via the lexical arm.
    mock_vstore = MagicMock(spec=ChromaVectorStore)
    db_ids = _database_chunk_ids(repo, exclude_path="database/marker.sql")
    assert len(db_ids) >= 12, f"need >=12 in-domain vector chunks, got {len(db_ids)}"
    mock_vstore.query.return_value = [
        VectorResult(id=cid, document="", metadata={}, distance=0.01 * (i + 1))
        for i, cid in enumerate(db_ids)
    ]

    try:
        engine = SearchEngine(store, mock_vstore, embedder, _manifest().search)

        # Precondition: unfiltered, the marker's database hit is buried deep.
        global_ranks = engine._lexical_ranks(MARKER, limit=500)
        # Find the marker (schema.sql) chunk's global rank.
        marker_rank = None
        for cid, rank in global_ranks.items():
            ch = store.get_chunk(cid)
            if ch is not None and ch.relative_path == "database/marker.sql":
                marker_rank = rank
                break

        if not rerank_enabled:
            # Reproduce pre-#54 behavior: filter to in-domain but KEEP the
            # global FTS ranks (no dense re-enumeration).
            orig = SearchEngine._lexical_ranks

            def _no_rerank(self, query, limit=None, in_domain_paths=None):
                results = self.store.search_lexical(
                    query,
                    limit=(
                        limit if limit is not None
                        else self.config.lexical_candidates
                    ),
                )
                san = query  # already a bare token in this test
                if in_domain_paths is None:
                    return {r.chunk_id: i + 1 for i, r in enumerate(results)}
                # Keep global ranks (the BROKEN behavior #54 fixes).
                return {
                    r.chunk_id: i + 1
                    for i, r in enumerate(results)
                    if r.relative_path in in_domain_paths
                }

            engine._lexical_ranks = _no_rerank.__get__(engine, SearchEngine)

        db_paths = _in_domain_paths(repo, "data-layer")
        results = engine.search(
            MARKER, limit=10, domain_id="data-layer", in_domain_paths=db_paths
        )
        return results, marker_rank
    finally:
        store.close()


def test_part2_deep_rank_lexical_hit_surfaces_with_rerank(tmp_path: Path) -> None:
    """WITH #54: the deep-global-rank in-domain lexical hit reaches top-N."""
    repo = _build_part2_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    results, marker_rank = _run_part2(repo, rerank_enabled=True)

    # The scenario is only meaningful if the marker was actually buried deep.
    assert marker_rank is not None, "marker never matched FTS — fixture broken"
    assert marker_rank > 10, (
        f"marker global rank {marker_rank} not deep enough to exercise #54"
    )

    paths = [r.relative_path for r in results]
    assert "database/marker.sql" in paths, (
        f"deep-rank in-domain lexical hit did NOT surface with re-rank; "
        f"top-N was {paths}"
    )
    # And every result is in-domain (part-1 invariant still holds).
    for r in results:
        assert r.relative_path.startswith("database/"), (
            f"out-of-domain leak: {r.relative_path}"
        )


def test_part2_fails_without_rerank(tmp_path: Path) -> None:
    """WITHOUT #54: the buried in-domain lexical hit is NOT in top-N.

    This is the fail-before mirror of the test above: it proves the previous
    assertion genuinely depends on the dense pre-RRF re-rank rather than on
    the vector arm or the fusion-loop drop.
    """
    repo = _build_part2_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    results, marker_rank = _run_part2(repo, rerank_enabled=False)

    assert marker_rank is not None and marker_rank > 10
    paths = [r.relative_path for r in results]
    # All still in-domain (the #23 drop keeps part 1 green even here)...
    for r in results:
        assert r.relative_path.startswith("database/")
    # ...but the buried marker does NOT surface without the dense re-rank.
    assert "database/marker.sql" not in paths, (
        "marker surfaced WITHOUT the re-rank — the test does not isolate #54; "
        f"top-N was {paths}"
    )


# ===========================================================================
# CLI-level --domain resolution and error paths (cli.py Milestone 6 logic)
# ===========================================================================


def _write_hash_manifest(repo: Path) -> None:
    (repo / "semantic-search.manifest.json").write_text(
        json.dumps(
            {"embedding": {"provider": "hash", "dimension": 64}}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )


def _cli_index_and_tag(repo: Path) -> None:
    _write_hash_manifest(repo)
    runner = CliRunner()
    r = runner.invoke(
        app,
        ["index", "--repo-root", str(repo), "--embedding-provider", "hash",
         "--reset"],
        catch_exceptions=False,
    )
    assert r.exit_code == 0, r.output
    _tag(repo)  # DomainTagger against domains.fixture.json


def test_cli_missing_knowledge_store_errors(tmp_path: Path) -> None:
    """--domain when knowledge.sqlite is absent errors, does not create DB.

    Milestone 1's indexer creates knowledge.sqlite on every `index` run, so an
    indexed repo normally has the (empty) file. The "no knowledge store"
    branch (#50) covers the genuinely-absent case — e.g. an index built before
    Milestone 1, or the knowledge dir removed. We simulate absence by removing
    the knowledge dir after indexing, then assert the probe errors WITHOUT
    recreating the file (issue #33).
    """
    repo = _copy_fixture(tmp_path)
    _write_hash_manifest(repo)
    runner = CliRunner()
    r = runner.invoke(
        app,
        ["index", "--repo-root", str(repo), "--embedding-provider", "hash",
         "--reset"],
        catch_exceptions=False,
    )
    assert r.exit_code == 0, r.output

    knowledge = (
        resolve_knowledge_dir(repo, _manifest()) / "knowledge.sqlite"
    )
    # Simulate an absent knowledge store (index predating Milestone 1).
    shutil.rmtree(knowledge.parent, ignore_errors=True)
    assert not knowledge.exists(), "precondition: knowledge store removed"

    r = runner.invoke(
        app,
        ["search", "provider", "--repo-root", str(repo),
         "--embedding-provider", "hash", "--domain", "Data Layer"],
        catch_exceptions=False,
    )
    assert r.exit_code == 1, r.output
    assert "no knowledge store" in r.output
    assert "tag-domains" in r.output
    # The probe must NOT have materialized an empty knowledge DB (issue #33).
    assert not knowledge.exists(), "existence-probe leaked an empty DB"


def test_cli_unknown_domain_errors(tmp_path: Path) -> None:
    """An unrecognized --domain errors and lists available domains (#39)."""
    repo = _copy_fixture(tmp_path)
    _cli_index_and_tag(repo)
    runner = CliRunner()
    r = runner.invoke(
        app,
        ["search", "provider", "--repo-root", str(repo),
         "--embedding-provider", "hash", "--domain", "Nonexistent Domain"],
        catch_exceptions=False,
    )
    assert r.exit_code == 1, r.output
    assert "unknown domain 'Nonexistent Domain'" in r.output
    assert "domains" in r.output  # points to the `domains` command
    assert "Data Layer" in r.output  # lists available domains


def test_cli_domain_filter_by_display_name(tmp_path: Path) -> None:
    """--domain accepts a case-insensitive display name and filters to it."""
    repo = _copy_fixture(tmp_path)
    _cli_index_and_tag(repo)
    runner = CliRunner()
    r = runner.invoke(
        app,
        ["search", "provider validation", "--repo-root", str(repo),
         "--embedding-provider", "hash", "--limit", "10",
         "--domain", "data layer"],  # lower-case display name
        catch_exceptions=False,
    )
    assert r.exit_code == 0, r.output
    # Every rendered result path is under database/ (in-domain only).
    import re

    paths = re.findall(r"(?:src|database|annotations|hierarchy|mainframe)/\S+",
                       r.output)
    assert paths, f"no result paths parsed from:\n{r.output}"
    assert all(p.startswith("database/") for p in paths), (
        f"out-of-domain leak in CLI output paths: {paths}"
    )


def test_cli_domain_by_slug_and_unassigned(tmp_path: Path) -> None:
    """--domain accepts the exact slug, and the reserved 'unassigned' slug."""
    repo = _copy_fixture(tmp_path)
    _cli_index_and_tag(repo)
    runner = CliRunner()

    # Exact domain_id slug.
    r = runner.invoke(
        app,
        ["search", "provider", "--repo-root", str(repo),
         "--embedding-provider", "hash", "--domain", "data-layer"],
        catch_exceptions=False,
    )
    assert r.exit_code == 0, r.output

    # Reserved 'unassigned' resolves without a domains-table row (annotations/
    # + hierarchy/ + mainframe/ are unmatched by the fixture globs).
    r = runner.invoke(
        app,
        ["search", "order", "--repo-root", str(repo),
         "--embedding-provider", "hash", "--domain", "Unassigned"],
        catch_exceptions=False,
    )
    assert r.exit_code == 0, r.output
