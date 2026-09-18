"""Tests for Milestone 4 of `domain-enhancements-plan.md`: the `tag-domains`
command, the `DomainTagger` reconcile, `resolve_file_domains`, and the
`ChromaVectorStore.update_domain_metadata` merge stamp.

Covers: glob resolution + precedence, unmatched -> unassigned rows,
manual-wins (a manual row survives a re-tag), both reaps (a dropped domain
and a deleted file including a manual one), the missing-index error,
idempotence (second run = same row content), and a stamped Chroma record
carrying `domain` plus its original metadata keys (merge).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest, resolve_index_dir, resolve_knowledge_dir
from legacylift_search.domain_tagger import (
    DomainTagger,
    load_domains_json,
    resolve_file_domains,
)
from legacylift_search.indexer import Indexer
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import DomainRecord

IS_WINDOWS = sys.platform == "win32"

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
    return resolve_knowledge_dir(repo, Manifest()) / "knowledge.sqlite"


def _domains_json(repo: Path) -> Path:
    return repo / "domains.fixture.json"


def _snapshot(ks: KnowledgeStore) -> dict:
    """Row-content snapshot (issue #24 — NOT raw bytes; WAL files differ)."""
    conn = ks._connect()
    return {
        "domains": sorted(
            tuple(r)
            for r in conn.execute(
                "SELECT domain_id, name, description, path_globs, "
                "assess_run_id, display_order FROM domains"
            ).fetchall()
        ),
        "edges": sorted(
            tuple(r)
            for r in conn.execute(
                "SELECT from_domain, to_domain, kind, evidence FROM domain_edges"
            ).fetchall()
        ),
        "file_domains": sorted(
            tuple(r)
            for r in conn.execute(
                "SELECT relative_path, domain, source, assess_run_id, "
                "confidence FROM file_domains"
            ).fetchall()
        ),
    }


# ---------------------------------------------------------------------
# resolve_file_domains (unit)
# ---------------------------------------------------------------------


def test_resolve_precedence_first_matching_domain_wins():
    """First domain in argument order whose glob matches wins, even when a
    later domain also matches (issue #14)."""
    domains = [
        DomainRecord(domain_id="a", name="A", path_globs=["src/**"], display_order=0),
        DomainRecord(
            domain_id="b", name="B", path_globs=["src/special/**"], display_order=1
        ),
    ]
    resolved = resolve_file_domains(["src/special/x.py"], domains)
    # Both globs match, but "a" is first in order -> "a" wins.
    assert resolved["src/special/x.py"] == ("a", 1.0)


def test_resolve_unmatched_goes_unassigned():
    domains = [
        DomainRecord(domain_id="a", name="A", path_globs=["src/**"], display_order=0),
    ]
    resolved = resolve_file_domains(["docs/readme.md", "src/x.py"], domains)
    assert resolved["docs/readme.md"] == ("unassigned", 1.0)
    assert resolved["src/x.py"] == ("a", 1.0)


def test_resolve_uses_gitwildmatch_not_fnmatch():
    """`**` spans directories under gitwildmatch; a single `*` does not cross
    a path separator (distinguishes pathspec from fnmatch)."""
    domains = [
        DomainRecord(
            domain_id="deep", name="Deep", path_globs=["src/*.py"], display_order=0
        ),
    ]
    resolved = resolve_file_domains(["src/a.py", "src/sub/b.py"], domains)
    assert resolved["src/a.py"] == ("deep", 1.0)
    # src/*.py must NOT match src/sub/b.py under gitwildmatch.
    assert resolved["src/sub/b.py"] == ("unassigned", 1.0)


# ---------------------------------------------------------------------
# load_domains_json
# ---------------------------------------------------------------------


def test_load_domains_json_roundtrips_vendored_globs_and_own_identities(
    tmp_path: Path,
):
    """`vendored_globs`/`own_identities` (M1 of the gap-detection plan) round-trip
    when present — additive fields, no schema_version bump."""
    dj = tmp_path / "with_both.json"
    dj.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "domains": [],
                "edges": [],
                "vendored_globs": ["**/vendor/**", "**/*.dtd"],
                "own_identities": ["nngco.com"],
            }
        ),
        encoding="utf-8",
    )
    parsed = load_domains_json(dj)
    assert parsed.vendored_globs == ["**/vendor/**", "**/*.dtd"]
    assert parsed.own_identities == ["nngco.com"]


def test_load_domains_json_defaults_vendored_globs_and_own_identities_empty(
    tmp_path: Path,
):
    """A domains.json omitting the two new fields defaults both to empty lists."""
    dj = tmp_path / "without_either.json"
    dj.write_text(
        json.dumps({"schema_version": 1, "domains": [], "edges": []}),
        encoding="utf-8",
    )
    parsed = load_domains_json(dj)
    assert parsed.vendored_globs == []
    assert parsed.own_identities == []


def test_load_domains_json_parses_edges_and_defaults_kind(tmp_path: Path):
    parsed = load_domains_json(_domains_json(FIXTURE))
    assert parsed.schema_version == 1
    assert [d.domain_id for d in parsed.domains] == ["core-services", "data-layer"]
    assert parsed.edges[0].from_ == "core-services"
    assert parsed.edges[0].to_ == "data-layer"
    assert parsed.edges[0].kind == "reads"

    # A missing edge `kind` defaults to "" (issue #51).
    no_kind = tmp_path / "no_kind.json"
    no_kind.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assess_run_id": "r",
                "domains": [
                    {"domain_id": "a", "name": "A", "path_globs": ["src/**"]}
                ],
                "edges": [{"from": "a", "to": "a"}],
            }
        ),
        encoding="utf-8",
    )
    parsed2 = load_domains_json(no_kind)
    assert parsed2.edges[0].kind == ""


# ---------------------------------------------------------------------
# DomainTagger.tag — glob rows, unassigned, domains catalog
# ---------------------------------------------------------------------


def test_tag_writes_glob_and_unassigned_rows(indexed_repo: Path):
    stats = DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))

    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        # src and database files carry glob rows for their domain.
        assert ks.domain_for_file("src/eligibility.py") == "core-services"
        assert ks.domain_for_file("database/schema.sql") == "data-layer"
        # annotations/, hierarchy/, mainframe/ are deliberately unmatched.
        assert ks.domain_for_file("annotations/routes.py") == "unassigned"
        assert ks.domain_for_file("hierarchy/shapes.py") == "unassigned"
        assert ks.domain_for_file("mainframe/PROVIDER.cbl") == "unassigned"

        # Two authored domains; unassigned is NOT a domains-table row.
        domain_ids = [d.domain_id for d in ks.list_domains()]
        assert domain_ids == ["core-services", "data-layer"]

        conn = ks._connect()
        # Unmatched rows are source='glob' with domain='unassigned' (issue #43).
        row = conn.execute(
            "SELECT domain, source FROM file_domains WHERE relative_path=?",
            ("annotations/routes.py",),
        ).fetchone()
        assert row["domain"] == "unassigned"
        assert row["source"] == "glob"
    finally:
        ks.close()

    assert stats.glob_count > 0
    assert stats.unassigned_count > 0
    assert stats.domains_ingested == 2
    assert stats.edges_ingested == 1


def test_tag_stamps_chroma_domain_merge(indexed_repo: Path):
    """A stamped Chroma record carries `domain` PLUS its original metadata
    keys (chromadb 1.5.9 MERGES — issue #4/#15)."""
    DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))

    manifest = Manifest()
    index_dir = resolve_index_dir(indexed_repo, manifest)
    index_sqlite = index_dir / manifest.index.sqlite_file

    conn = sqlite3.connect(str(index_sqlite))
    try:
        row = conn.execute(
            "SELECT c.id FROM chunks c "
            "JOIN vectors_present v ON v.chunk_id = c.id "
            "WHERE c.relative_path LIKE 'src/%' LIMIT 1"
        ).fetchone()
        assert row is not None, "expected at least one embedded src chunk"
        chunk_id = row[0]
    finally:
        conn.close()

    from legacylift_search.embeddings import HashEmbedder
    from legacylift_search.vector_store import ChromaVectorStore

    vs = ChromaVectorStore(
        base_dir=index_dir,
        collection_name=manifest.index.collection_name,
        embedder=HashEmbedder(dimension=64),
        metadata={},
    )
    try:
        got = vs.collection.get(ids=[chunk_id], include=["metadatas"])
        meta = got["metadatas"][0]
    finally:
        vs.close()

    assert meta["domain"] == "core-services"
    original_keys = {
        "relative_path",
        "language",
        "chunk_kind",
        "symbol_id",
        "symbol_path",
        "start_line",
        "end_line",
        "text_sha256",
    }
    assert original_keys <= set(meta), (
        f"merge lost original keys: {original_keys - set(meta)}"
    )


# ---------------------------------------------------------------------
# manual-wins
# ---------------------------------------------------------------------


def test_manual_row_survives_retag(indexed_repo: Path):
    DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))

    # Hand-set a manual override to a DIFFERENT domain than its glob answer.
    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        ks.upsert_file_domain(
            "src/eligibility.py", "data-layer", "manual", "hand", 1.0
        )
    finally:
        ks.close()

    stats = DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))

    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        conn = ks._connect()
        row = conn.execute(
            "SELECT domain, source FROM file_domains WHERE relative_path=?",
            ("src/eligibility.py",),
        ).fetchone()
        # manual-wins: glob resolution did NOT overwrite it.
        assert row["domain"] == "data-layer"
        assert row["source"] == "manual"
    finally:
        ks.close()

    assert "src/eligibility.py" in stats.manual_preserved


# ---------------------------------------------------------------------
# reaps
# ---------------------------------------------------------------------


def test_reap_dropped_domain(indexed_repo: Path, tmp_path: Path):
    """A domain absent from a later domains.json is reaped from the authored
    tables and its files reclassified (issue #41)."""
    DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))

    # Second ingest drops "data-layer" entirely.
    dropped_json = tmp_path / "dropped.json"
    dropped_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assess_run_id": "run-2",
                "domains": [
                    {
                        "domain_id": "core-services",
                        "name": "Core Services",
                        "path_globs": ["src/**"],
                    }
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    stats = DomainTagger(Manifest()).tag(indexed_repo, dropped_json)

    assert "data-layer" in stats.dropped_domains
    assert stats.reclassified_counts["data-layer"] >= 1

    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        assert [d.domain_id for d in ks.list_domains()] == ["core-services"]
        # database/ files fall back to unassigned now that data-layer is gone.
        assert ks.domain_for_file("database/schema.sql") == "unassigned"
        # The dropped edge is gone too.
        assert ks.get_domain_edges() == []
    finally:
        ks.close()


def test_reap_deleted_file_including_manual(indexed_repo: Path):
    """A file removed from disk has its file_domains row reaped regardless of
    source — including a `manual` row (issues #38/#42)."""
    DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))

    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        ks.upsert_file_domain(
            "src/eligibility.py", "data-layer", "manual", "hand", 1.0
        )
        assert ks.domain_for_file("src/eligibility.py") == "data-layer"
    finally:
        ks.close()

    # Delete the manually-tagged file from disk, then re-tag.
    (indexed_repo / "src" / "eligibility.py").unlink()
    DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))

    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        # The manual row for the deleted file is gone (not immortal).
        assert ks.domain_for_file("src/eligibility.py") is None
    finally:
        ks.close()


# ---------------------------------------------------------------------
# missing index
# ---------------------------------------------------------------------


def test_missing_index_raises_clear_error(tmp_path: Path):
    repo = _copy_fixture(tmp_path)  # never indexed
    with pytest.raises(FileNotFoundError) as exc:
        DomainTagger(Manifest()).tag(repo, _domains_json(repo))
    msg = str(exc.value)
    assert "no code-search index found" in msg
    assert "legacylift-search index" in msg


# ---------------------------------------------------------------------
# idempotence
# ---------------------------------------------------------------------


def test_tag_is_idempotent(indexed_repo: Path):
    """A second tag-domains run yields logically identical rows (issue #24 —
    assert on row CONTENT, not raw bytes)."""
    DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))
    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        snap1 = _snapshot(ks)
    finally:
        ks.close()

    DomainTagger(Manifest()).tag(indexed_repo, _domains_json(indexed_repo))
    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        snap2 = _snapshot(ks)
    finally:
        ks.close()

    assert snap1 == snap2


# ---------------------------------------------------------------------
# CLI end-to-end
# ---------------------------------------------------------------------


def test_tag_domains_cli(indexed_repo: Path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tag-domains",
            "--repo-root",
            str(indexed_repo),
            "--domains",
            str(_domains_json(indexed_repo)),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "tagged:" in result.output

    # `domains` now lists both plus an Unassigned trailer.
    result2 = runner.invoke(app, ["domains", "--repo-root", str(indexed_repo)])
    assert result2.exit_code == 0, result2.output
    assert "Core Services" in result2.output
    assert "Data Layer" in result2.output
    assert "Unassigned" in result2.output


def test_tag_domains_cli_missing_index(tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tag-domains",
            "--repo-root",
            str(repo),
            "--domains",
            str(_domains_json(repo)),
        ],
    )
    assert result.exit_code == 1, result.output
    assert "no code-search index found" in result.output


# ---------------------------------------------------------------------
# Excluded-by-design tier
# ---------------------------------------------------------------------


def _domains_json_with_excludes(repo: Path, exclude_globs: list) -> Path:
    """Write a domains.json (fixture domains + edges) carrying exclude_globs."""
    base = json.loads(_domains_json(repo).read_text(encoding="utf-8"))
    base["exclude_globs"] = exclude_globs
    dest = repo / "domains.excl.json"
    dest.write_text(json.dumps(base), encoding="utf-8")
    return dest


def test_resolve_excluded_tier_and_domain_precedence():
    """A file matching no domain but an exclude glob -> 'excluded'; a file
    matching neither -> 'unassigned'; and a DOMAIN always wins over an
    exclusion (exclusion only claims otherwise-unassigned files)."""
    domains = [
        DomainRecord(
            domain_id="core", name="Core", path_globs=["src/**"], display_order=0
        ),
    ]
    resolved = resolve_file_domains(
        ["src/app.py", "tests/test_app.py", "docs/readme.md"],
        domains,
        exclude_globs=["tests/**", "src/**"],  # src/** overlaps the domain glob
    )
    # domain wins over the overlapping exclusion
    assert resolved["src/app.py"] == ("core", 1.0)
    # matched only by an exclusion -> excluded (not unassigned)
    assert resolved["tests/test_app.py"] == ("excluded", 1.0)
    # matched by neither -> unassigned
    assert resolved["docs/readme.md"] == ("unassigned", 1.0)


def test_resolve_no_exclude_globs_is_backward_compatible():
    """Omitting exclude_globs preserves the original unassigned behavior."""
    domains = [
        DomainRecord(
            domain_id="core", name="Core", path_globs=["src/**"], display_order=0
        ),
    ]
    resolved = resolve_file_domains(["tests/t.py"], domains)
    assert resolved["tests/t.py"] == ("unassigned", 1.0)


def test_knowledge_store_exclusions_roundtrip(tmp_path: Path):
    """set_exclusions is replace-all; list_exclusions returns them sorted."""
    ks = KnowledgeStore(tmp_path / "knowledge.sqlite")
    try:
        assert ks.list_exclusions() == []
        ks.set_exclusions(["b/**", "a/**"])
        assert ks.list_exclusions() == ["a/**", "b/**"]
        # replace-all: the previous set is gone
        ks.set_exclusions(["c/**"])
        assert ks.list_exclusions() == ["c/**"]
        ks.set_exclusions([])
        assert ks.list_exclusions() == []
    finally:
        ks.close()


def test_tag_writes_excluded_rows(indexed_repo: Path):
    """tag-domains routes exclude-glob matches to domain='excluded' (source
    glob), keeps true gaps as 'unassigned', and counts them separately."""
    dj = _domains_json_with_excludes(
        indexed_repo, ["annotations/**", "hierarchy/**"]
    )
    stats = DomainTagger(Manifest()).tag(indexed_repo, dj)

    ks = KnowledgeStore(_knowledge_path(indexed_repo))
    try:
        # domain matches unaffected
        assert ks.domain_for_file("src/eligibility.py") == "core-services"
        assert ks.domain_for_file("database/schema.sql") == "data-layer"
        # exclude-glob matches -> excluded
        assert ks.domain_for_file("annotations/routes.py") == "excluded"
        assert ks.domain_for_file("hierarchy/shapes.py") == "excluded"
        # neither domain nor exclusion -> still a true unassigned gap
        assert ks.domain_for_file("mainframe/PROVIDER.cbl") == "unassigned"
        # 'excluded' is a file_domains VALUE, never a domains-table row
        assert "excluded" not in [d.domain_id for d in ks.list_domains()]
        # persisted for the indexer's incremental 7-Auto
        assert ks.list_exclusions() == ["annotations/**", "hierarchy/**"]
        # excluded rows are source='glob' (auto-resolved), not 'manual'
        conn = ks._connect()
        row = conn.execute(
            "SELECT source FROM file_domains WHERE relative_path=?",
            ("annotations/routes.py",),
        ).fetchone()
        assert row["source"] == "glob"
    finally:
        ks.close()

    assert stats.excluded_count >= 2
    assert stats.unassigned_count >= 1
    # glob_count is real-domain matches only (excludes excluded & unassigned)
    assert stats.glob_count >= 2


def test_tag_domains_cli_excluded_reporting(indexed_repo: Path):
    """CLI surfaces the excluded tier in tag/domains/stats/validate, and
    coverage drops excluded from the denominator (never the gap hint)."""
    dj = _domains_json_with_excludes(indexed_repo, ["annotations/**"])
    runner = CliRunner()

    r = runner.invoke(
        app,
        ["tag-domains", "--repo-root", str(indexed_repo), "--domains", str(dj)],
    )
    assert r.exit_code == 0, r.output
    assert "excluded" in r.output

    r2 = runner.invoke(app, ["domains", "--repo-root", str(indexed_repo)])
    assert r2.exit_code == 0, r2.output
    assert "Excluded (excluded)" in r2.output

    r3 = runner.invoke(app, ["validate", "--repo-root", str(indexed_repo)])
    assert r3.exit_code == 0, r3.output
    assert "excluded" in r3.output
    # the coverage-gap remediation hint fires only for a true unassigned gap,
    # never for excluded-by-design files
    assert "unassigned (coverage gap)" in r3.output
