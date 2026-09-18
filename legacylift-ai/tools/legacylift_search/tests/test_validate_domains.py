"""Tests for Milestone 7 of `domain-enhancements-plan.md`: the `validate`
domains freshness axis.

Conceptual model under test (this is the whole point of the milestone):

- **untagged** = a discovered file with NO `file_domains` row at all. This
  is the staleness signal.
- **unassigned** = a discovered file whose row IS the reserved
  `unassigned` domain. An ACCEPTED gap written only by `tag-domains`,
  reported as coverage info, never staleness.

Four acceptance scenarios (from the milestone), each fail-before /
pass-after against the fixture, plus a `domains: missing` check that also
proves the existence-probe does not create `knowledge.sqlite` as a side
effect (issue #33).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest, resolve_knowledge_dir
from legacylift_search.domain_tagger import DomainTagger
from legacylift_search.indexer import Indexer

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


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
    Indexer(_manifest(), repo).run(reset=reset, embedding_provider_override="hash")


def _domains_json(repo: Path) -> Path:
    return repo / "domains.fixture.json"


def _tag(repo: Path, domains_json: Path | None = None) -> None:
    DomainTagger(_manifest()).tag(repo, domains_json or _domains_json(repo))


def _validate(repo: Path) -> str:
    runner = CliRunner()
    result = runner.invoke(app, ["validate", "--repo-root", str(repo)])
    assert result.exit_code == 0, result.output
    return result.output


def _knowledge_sqlite(repo: Path) -> Path:
    return resolve_knowledge_dir(repo, Manifest()) / "knowledge.sqlite"


# ---------------------------------------------------------------------
# Scenario 1: deliberate unmatched dirs -> fresh, coverage <100%, N unassigned
# ---------------------------------------------------------------------


def test_scenario1_fresh_with_accepted_unassigned_gap(tmp_path: Path) -> None:
    """After a tag with the fixture's deliberately unmatched `annotations/`
    and `hierarchy/` dirs, `validate` reports `fresh` — the gaps are
    ACCEPTED `unassigned` rows written by `tag-domains`, not staleness."""
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    output = _validate(repo)

    assert "domains: fresh" in output
    assert "domains: stale" not in output
    assert "0 unassigned" not in output  # the gap must be non-zero
    # coverage < 100% because annotations/, hierarchy/, mainframe/ are
    # unassigned (accepted gaps), not classified.
    assert "coverage 100%" not in output


# ---------------------------------------------------------------------
# Scenario 2: a brand-new file matching NO domain glob, after reindex ->
# stale, 1 untagged (need assess)
# ---------------------------------------------------------------------


def test_scenario2_unmatched_new_file_after_reindex_is_stale_need_assess(
    tmp_path: Path,
) -> None:
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    # Confirm fresh before the change.
    assert "domains: fresh" in _validate(repo)

    # A brand-new top-level directory that matches NEITHER "src/**" nor
    # "database/**" (the fixture's two authored globs).
    orphan_dir = repo / "orphan"
    orphan_dir.mkdir()
    (orphan_dir / "mystery.py").write_text(
        "def unclaimed_capability():\n"
        "    # matches no domain glob at all\n"
        "    return 42\n",
        encoding="utf-8",
    )

    # Incremental reindex — 7-Auto looks at the new file, finds no glob
    # match, and leaves it UNTAGGED (no row) rather than manufacturing an
    # `unassigned` row.
    _index(repo, reset=False)

    output = _validate(repo)
    assert "domains: stale" in output
    assert "1 untagged" in output
    assert "need assess" in output
    # It matches no glob, so it must NOT be counted as glob-matchable.
    assert "0 glob-matchable" in output


# ---------------------------------------------------------------------
# Scenario 3: a new file under src/ (glob-matchable) WITHOUT reindexing ->
# stale, 1 untagged (glob-matchable); `index` flips it back to fresh with
# zero manual steps
# ---------------------------------------------------------------------


def test_scenario3_glob_matchable_new_file_stale_until_reindex(
    tmp_path: Path,
) -> None:
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)
    assert "domains: fresh" in _validate(repo)

    # New file under src/ -> matches the core-services glob ("src/**").
    (repo / "src" / "newthing.py").write_text(
        "def brand_new_thing():\n"
        "    # added after tag-domains, before any reindex\n"
        "    return 'new'\n",
        encoding="utf-8",
    )

    # No reindex yet: the file is on disk (discovered) but has no
    # file_domains row. It IS glob-matchable against the stored domains,
    # so validate must classify it that way even without reindexing.
    output = _validate(repo)
    assert "domains: stale" in output
    assert "1 untagged" in output
    assert "glob-matchable" in output
    assert "1 glob-matchable" in output

    # Reindex (no tag-domains call): 7-Auto auto-tags the glob-matchable
    # file with zero manual steps.
    _index(repo, reset=False)

    output = _validate(repo)
    assert "domains: fresh" in output


# ---------------------------------------------------------------------
# Scenario 4: extend domains.fixture.json to cover the new directory and
# re-tag -> fresh again
# ---------------------------------------------------------------------


def test_scenario4_extend_domains_and_retag_covers_gap(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    orphan_dir = repo / "orphan"
    orphan_dir.mkdir()
    (orphan_dir / "mystery.py").write_text(
        "def unclaimed_capability():\n    return 42\n", encoding="utf-8"
    )
    _index(repo, reset=False)
    assert "domains: stale" in _validate(repo)

    # Extend the domains.json with a new domain covering orphan/**.
    extended = json.loads(_domains_json(repo).read_text(encoding="utf-8"))
    extended["domains"].append(
        {
            "domain_id": "misc",
            "name": "Misc",
            "description": "Catch-all for orphaned capabilities.",
            "path_globs": ["orphan/**"],
        }
    )
    extended_path = repo / "domains.extended.json"
    extended_path.write_text(json.dumps(extended), encoding="utf-8")

    _tag(repo, extended_path)

    output = _validate(repo)
    assert "domains: fresh" in output


# ---------------------------------------------------------------------
# domains: missing
# ---------------------------------------------------------------------


def test_missing_when_domains_table_empty(tmp_path: Path) -> None:
    """Indexed but never tagged: `knowledge.sqlite` exists (the indexer's
    Milestone-1 open creates it) but the `domains` table is empty ->
    `domains: missing` (issues #19/#33), not an unhandled exception."""
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)  # no tag-domains ever run

    output = _validate(repo)
    assert "domains: missing" in output


def test_missing_probe_does_not_create_knowledge_sqlite(tmp_path: Path) -> None:
    """When `knowledge.sqlite` does not exist at all, `validate` must
    report `domains: missing` WITHOUT constructing `KnowledgeStore` — a
    plain `Path.exists()` probe runs first (issue #33). Confirmed by
    checking the file is still absent after `validate` returns; a buggy
    implementation that constructs `KnowledgeStore` unconditionally would
    materialize the file (and its parent dir) as a side effect."""
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)
    assert "domains: fresh" in _validate(repo)

    knowledge_sqlite = _knowledge_sqlite(repo)
    assert knowledge_sqlite.exists()
    shutil.rmtree(knowledge_sqlite.parent)
    assert not knowledge_sqlite.exists()

    output = _validate(repo)
    assert "domains: missing" in output

    # The probe must not have recreated it.
    assert not knowledge_sqlite.exists()
