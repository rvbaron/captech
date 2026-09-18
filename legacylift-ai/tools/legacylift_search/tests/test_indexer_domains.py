"""Tests for Milestone 5 of `domain-enhancements-plan.md`: the indexer's
7-Auto domain self-resolution, manual-wins precedence, the derived-mirror
invariant on the Chroma side, and `--reset`/backfill parity.

Acceptance scenarios (from the milestone):

(a) reindex-touch: after a tag, a new glob-matching file added under `src/`
    gets a `source='glob'` `file_domains` row and its chunk carries `domain`
    metadata on an incremental reindex, with no `tag-domains` call.
(b) manual-wins on the vector side, two sub-parts:
      (i)  touch a file whose row was hand-edited to `manual` and reindex —
           the row is not overwritten and the manual domain reaches Chroma;
      (ii) edit a *different* file's row to `manual` WITHOUT touching the file
           and run `tag-domains` — the reconcile path flips its Chroma domain.
(c) --reset preserves the knowledge DB + manual rows, mirrors existing glob
    rows into Chroma verbatim (NOT recomputed, issue #53), and a brand-new
    glob-matching file gets a fresh glob row.

Each assertion depends on Milestone-5 behavior (a `domain` key stamped into
Chroma; glob rows written by the indexer on reindex) that does not exist
before the change, so each test fails-before / passes-after.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from legacylift_search.config import (
    Manifest,
    resolve_index_dir,
    resolve_knowledge_dir,
)
from legacylift_search.domain_tagger import DomainTagger
from legacylift_search.embeddings import HashEmbedder
from legacylift_search.indexer import Indexer
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.vector_store import ChromaVectorStore

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


def _manifest() -> Manifest:
    m = Manifest()
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    return m


def _copy_fixture(tmp_path: Path) -> Path:
    import shutil

    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _index(repo: Path, *, reset: bool) -> None:
    Indexer(_manifest(), repo).run(
        reset=reset, embedding_provider_override="hash"
    )


def _knowledge(repo: Path) -> KnowledgeStore:
    return KnowledgeStore(
        resolve_knowledge_dir(repo, Manifest()) / "knowledge.sqlite"
    )


def _domains_json(repo: Path) -> Path:
    return repo / "domains.fixture.json"


def _tag(repo: Path) -> None:
    DomainTagger(Manifest()).tag(repo, _domains_json(repo))


def _row(repo: Path, rel_path: str) -> tuple[str, str] | None:
    """Return `(domain, source)` for a file_domains row, or None."""
    ks = _knowledge(repo)
    try:
        conn = ks._connect()
        r = conn.execute(
            "SELECT domain, source FROM file_domains WHERE relative_path=?",
            (rel_path,),
        ).fetchone()
        return (r["domain"], r["source"]) if r is not None else None
    finally:
        ks.close()


def _set_manual(repo: Path, rel_path: str, domain: str) -> None:
    ks = _knowledge(repo)
    try:
        ks.upsert_file_domain(rel_path, domain, "manual", "hand", 1.0)
    finally:
        ks.close()


def _embedded_chunk_id(repo: Path, rel_path: str) -> str | None:
    """First embedded (vectors_present) chunk id for `rel_path`, or None."""
    manifest = Manifest()
    index_sqlite = (
        resolve_index_dir(repo, manifest) / manifest.index.sqlite_file
    )
    conn = sqlite3.connect(str(index_sqlite))
    try:
        r = conn.execute(
            "SELECT c.id FROM chunks c "
            "JOIN vectors_present v ON v.chunk_id = c.id "
            "WHERE c.relative_path = ? LIMIT 1",
            (rel_path,),
        ).fetchone()
        return r[0] if r is not None else None
    finally:
        conn.close()


def _chroma_domain(repo: Path, chunk_id: str) -> str | None:
    """Read a single chunk's `domain` Chroma metadata (None if unset)."""
    manifest = Manifest()
    index_dir = resolve_index_dir(repo, manifest)
    vs = ChromaVectorStore(
        base_dir=index_dir,
        collection_name=manifest.index.collection_name,
        embedder=HashEmbedder(dimension=64),
        metadata={},
    )
    try:
        got = vs.collection.get(ids=[chunk_id], include=["metadatas"])
        metas = got["metadatas"]
        meta = metas[0] if metas else {}
    finally:
        vs.close()
    return meta.get("domain")


def _file_domain_via_chroma(repo: Path, rel_path: str) -> str | None:
    cid = _embedded_chunk_id(repo, rel_path)
    assert cid is not None, f"no embedded chunk for {rel_path}"
    return _chroma_domain(repo, cid)


# ---------------------------------------------------------------------
# (a) reindex-touch: a new glob-matching file auto-tags on reindex
# ---------------------------------------------------------------------


def test_a_new_glob_file_autotagged_on_reindex(tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    # Add a brand-new file under src/ (matches the core-services glob).
    new_rel = "src/newmod.py"
    (repo / "src" / "newmod.py").write_text(
        "def brand_new_capability(payload):\n"
        "    # a distinctive new function so it chunks\n"
        "    return payload * 2\n",
        encoding="utf-8",
    )

    # Incremental reindex — NO tag-domains call.
    _index(repo, reset=False)

    # The new file got a source='glob' row for its matched domain.
    assert _row(repo, new_rel) == ("core-services", "glob")
    # And its chunk carries the domain metadata in Chroma.
    assert _file_domain_via_chroma(repo, new_rel) == "core-services"


# ---------------------------------------------------------------------
# (b)(i) manual-wins across a reindex-touch, propagated to Chroma
# ---------------------------------------------------------------------


def test_b_manual_row_survives_reindex_and_reaches_chroma(tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    rel = "src/eligibility.py"
    # Sanity: glob resolution assigned it to core-services.
    assert _row(repo, rel) == ("core-services", "glob")

    # Hand-edit its row to a DIFFERENT domain than the glob answer.
    _set_manual(repo, rel, "data-layer")

    # Rewrite the file body so the chunk text_sha256 actually changes and the
    # chunk is re-embedded (a trailing comment would leave the function chunk's
    # text unchanged, so its vector would be skipped as already-present and
    # never re-stamped — the skip-on-unchanged-vector fast path).
    p = repo / "src" / "eligibility.py"
    p.write_text(
        "def check_eligibility(member, plan):\n"
        "    # substantially rewritten so the chunk re-embeds\n"
        "    total = 0\n"
        "    for rule in plan.rules:\n"
        "        total += rule.weight * member.factor\n"
        "    return total >= plan.threshold\n",
        encoding="utf-8",
    )
    _index(repo, reset=False)

    # (i) 7-Auto did NOT overwrite the manual row.
    assert _row(repo, rel) == ("data-layer", "manual")
    # (ii) the manual decision reached the vector index (not left at
    #      core-services).
    assert _file_domain_via_chroma(repo, rel) == "data-layer"


# ---------------------------------------------------------------------
# (b)(ii) manual edit on an UNCHANGED file reaches Chroma via tag-domains
# ---------------------------------------------------------------------


def test_b_manual_on_unchanged_file_reconciled_by_tag_domains(tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    rel = "src/reclaim.js"
    assert _row(repo, rel) == ("core-services", "glob")
    assert _file_domain_via_chroma(repo, rel) == "core-services"

    # Edit the row to manual WITHOUT touching the file (no reindex).
    _set_manual(repo, rel, "data-layer")

    # The reconcile path is tag-domains — it re-stamps Chroma from the row.
    _tag(repo)

    assert _row(repo, rel) == ("data-layer", "manual")
    assert _file_domain_via_chroma(repo, rel) == "data-layer"


# ---------------------------------------------------------------------
# (c) --reset preserves knowledge DB + manual rows; mirrors glob rows
#     verbatim; new glob-matching file gets a fresh row
# ---------------------------------------------------------------------


def test_c_reset_preserves_and_mirrors_verbatim(tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag(repo)

    # A manual override whose domain DIFFERS from what glob would recompute —
    # this is what proves "mirrored verbatim, NOT recomputed" (issue #53).
    manual_rel = "src/enrollment.ts"
    _set_manual(repo, manual_rel, "data-layer")

    # A brand-new glob-matching file added before the reset.
    new_rel = "src/fresh_after_reset.py"
    (repo / "src" / "fresh_after_reset.py").write_text(
        "def fresh():\n    return 'hello from a new module'\n",
        encoding="utf-8",
    )

    # Cold --reset: index.sqlite + Chroma are rebuilt from scratch;
    # knowledge.sqlite must survive untouched.
    _index(repo, reset=True)

    # Knowledge DB survived: both authored domains still present.
    ks = _knowledge(repo)
    try:
        assert [d.domain_id for d in ks.list_domains()] == [
            "core-services",
            "data-layer",
        ]
    finally:
        ks.close()

    # The manual row survived the reset (domain + source intact).
    assert _row(repo, manual_rel) == ("data-layer", "manual")
    # ...and was mirrored VERBATIM into the freshly-rebuilt Chroma — the glob
    # answer (core-services) was NOT recomputed.
    assert _file_domain_via_chroma(repo, manual_rel) == "data-layer"

    # An existing glob row also survived and was mirrored verbatim.
    assert _row(repo, "database/schema.sql") == ("data-layer", "glob")
    assert _file_domain_via_chroma(repo, "database/schema.sql") == "data-layer"

    # The brand-new glob-matching file got a fresh glob row + Chroma domain.
    assert _row(repo, new_rel) == ("core-services", "glob")
    assert _file_domain_via_chroma(repo, new_rel) == "core-services"


# ---------------------------------------------------------------------
# Guard: never-tagged repo => the indexer does nothing domain-related
# ---------------------------------------------------------------------


def test_untagged_repo_writes_no_domain_metadata(tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)  # no tag-domains ever run

    # No file_domains rows at all.
    ks = _knowledge(repo)
    try:
        conn = ks._connect()
        assert (
            conn.execute("SELECT COUNT(*) FROM file_domains").fetchone()[0]
            == 0
        )
    finally:
        ks.close()

    # And no chunk carries a `domain` key.
    assert _file_domain_via_chroma(repo, "src/eligibility.py") is None


# ---------------------------------------------------------------------
# Excluded-by-design tier: incremental 7-Auto honors persisted exclusions
# ---------------------------------------------------------------------


def _tag_with_excludes(repo: Path, exclude_globs: list) -> None:
    import json

    base = json.loads(_domains_json(repo).read_text(encoding="utf-8"))
    base["exclude_globs"] = exclude_globs
    dj = repo / "domains.excl.json"
    dj.write_text(json.dumps(base), encoding="utf-8")
    DomainTagger(Manifest()).tag(repo, dj)


def test_new_excluded_file_autotagged_excluded_on_reindex(tmp_path: Path):
    """A new file matching a persisted exclusion glob gets a source='glob'
    row with domain='excluded' (and Chroma stamp) on an incremental reindex —
    NO tag-domains call — so it does not linger untagged and flip the repo to
    `stale`. This proves exclusions survive in knowledge.sqlite for 7-Auto."""
    repo = _copy_fixture(tmp_path)
    _index(repo, reset=True)
    _tag_with_excludes(repo, ["mainframe/**"])

    # A brand-new file under the excluded mainframe/ tree.
    new_rel = "mainframe/NEWJOB.cbl"
    (repo / "mainframe" / "NEWJOB.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. NEWJOB.\n"
        "       PROCEDURE DIVISION.\n"
        "           DISPLAY 'BRAND NEW BATCH JOB FOR CHUNKING'.\n"
        "           STOP RUN.\n",
        encoding="utf-8",
    )

    # Incremental reindex — NO tag-domains call.
    _index(repo, reset=False)

    # Auto-resolved to the reserved 'excluded' value via the persisted glob.
    assert _row(repo, new_rel) == ("excluded", "glob")
    assert _file_domain_via_chroma(repo, new_rel) == "excluded"
