"""Tests for Step 5: `gr_fts`, the `gr_statements` collection, the refresh pair.

Milestone 1, Step 5 of `docs/exec-plans/active/reqs-to-data-store.md`. Every
test here fails before Step 5 -- most with `No module named
'legacylift_search.gr_refresh'`, the schema ones with `no such table: gr_fts`,
the vector ones with `TypeError` on `upsert_texts`/`count` -- and passes after.

**Nothing writes a `gr` row yet** (ingest is Step 6), so these tests insert
rows directly, reusing `test_gr_state.py`'s `_MINIMAL_GR` and `insert_gr`,
which between them cover the eleven NOT NULL columns in one place.

Three of Step 5's five written acceptance criteria need Step 6 or Step 8 to be
performable end to end (`requirements ingest`, `requirements search`,
`reindex-vectors` are all CLI surfaces that do not exist). Those are written
here in their unit-level form and named as such in the docstring, so the step
that supplies the command knows what is already proved and what is not.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from legacylift_search.embeddings import HashEmbedder
from legacylift_search.gr_refresh import (
    GR_COLLECTION_NAME,
    GR_VECTOR_METADATA_KEYS,
    describe_vector_shortfall,
    open_gr_collection,
    open_index_store_if_present,
    refresh_gr_derived_sql,
    refresh_gr_vectors,
)
from legacylift_search.gr_state import set_state
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.store import SQLiteStore
from tests.test_gr_state import _MINIMAL_GR, insert_gr


#: Chroma's `PersistentClient` keeps its own SQLite files open past `close()`
#: on Windows often enough that the house pattern in `tests/test_vector_store.py`
#: is to tolerate a failed teardown rather than to leak a test failure out of
#: one. Step 5 is the first step whose tests hold *both* stores at once, so both
#: `close()` calls still run in a `finally` — this only covers the handle Chroma
#: does not release on our schedule.
_IS_WINDOWS = sys.platform == "win32"


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(tmp_root):
    """A knowledge store whose `close()` always runs.

    Windows temp-directory teardown fails if the WAL and SHM handles are still
    held, and Step 5 is the first step whose tests hold *two* stores at once.
    """
    ks = KnowledgeStore(tmp_root / "knowledge" / "knowledge.sqlite")
    try:
        yield ks
    finally:
        ks.close()


# --------------------------------------------------------------------------
# The gr_fts table itself
# --------------------------------------------------------------------------


def test_gr_fts_exists_with_the_house_columns_and_gr_id_unindexed(store):
    """Proves `gr_fts` is created by `migrate()` in `chunk_fts`'s shape.

    A *table* addition needs no `KNOWLEDGE_MIGRATIONS` entry -- `migrate()`
    runs from `__init__` on every open -- which is what the second half of
    this test checks by reopening the same file.
    """
    conn = store._connect()
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'gr_fts'"
    ).fetchone()[0]
    assert "USING fts5" in sql
    assert "gr_id UNINDEXED" in sql
    for column in ("name", "statement", "as_built", "rationale"):
        assert column in sql
    # Standalone, not external-content and not contentless: either would stop
    # `requirements search` returning the matched text for a snippet.
    assert "content=" not in sql

    columns = [
        r[1] for r in conn.execute("PRAGMA table_info('gr_fts')").fetchall()
    ]
    assert columns == ["gr_id", "name", "statement", "as_built", "rationale"]


def test_an_existing_knowledge_store_gains_gr_fts_with_no_version_bump(tmp_root):
    """Proves the no-migration claim: a second open creates the table.

    Simulates a `knowledge.sqlite` that predates Step 5 by dropping the table
    and reopening, which is what an existing store on disk looks like.
    """
    path = tmp_root / "knowledge" / "knowledge.sqlite"
    first = KnowledgeStore(path)
    version_before = first._connect().execute("PRAGMA user_version").fetchone()[0]
    first._connect().execute("DROP TABLE gr_fts")
    first._connect().commit()
    first.close()

    second = KnowledgeStore(path)
    try:
        assert (
            second._connect()
            .execute("SELECT count(*) FROM sqlite_master WHERE name = 'gr_fts'")
            .fetchone()[0]
            == 1
        )
        assert (
            second._connect().execute("PRAGMA user_version").fetchone()[0]
            == version_before
        )
    finally:
        second.close()


# --------------------------------------------------------------------------
# refresh_gr_derived_sql
# --------------------------------------------------------------------------


def test_refresh_writes_the_fts_row_and_the_findings(store):
    """Proves one call populates both derived SQL artifacts for a record."""
    gr_id = insert_gr(store._connect(), rationale="Auditors asked for it.")
    result = refresh_gr_derived_sql(store, [gr_id])
    assert result.refreshed == 1
    row = (
        store._connect()
        .execute("SELECT statement, rationale FROM gr_fts WHERE gr_id = ?", (gr_id,))
        .fetchone()
    )
    assert row[0] == _MINIMAL_GR["statement"]
    assert row[1] == "Auditors asked for it."
    # The validator ran: findings were written (this statement is conformant
    # enough to be approvable, so what matters is that the write path fired,
    # which `findings_written` reports either way).
    assert result.findings_written == len(store.list_gr_findings(gr_id))


def test_gr_fts_forgets_old_text_on_an_edit(store):
    """`gr_fts` forgets old text -- the delete-half assertion.

    Step 5's acceptance criterion, in its unit-level form: the end-to-end form
    edits through `requirements set-field`, which is Step 8's. This is the
    specific way a standalone FTS5 table goes wrong: an INSERT with no DELETE
    leaves the pre-edit wording searchable forever.
    """
    gr_id = insert_gr(
        store._connect(),
        statement="The Order Service must record a vendor number on each order.",
    )
    refresh_gr_derived_sql(store, [gr_id])
    assert store.search_gr_fts("vendor")

    store._connect().execute(
        "UPDATE gr SET statement = ? WHERE gr_id = ?",
        ("The Order Service must record a haulier code on each order.", gr_id),
    )
    store._connect().commit()
    refresh_gr_derived_sql(store, [gr_id])

    assert [g for g, _ in store.search_gr_fts("haulier")] == [gr_id]
    assert store.search_gr_fts("vendor") == []


def test_refresh_forgets_a_requirement_that_no_longer_exists(store):
    """Proves a deleted `gr` row does not leave a searchable ghost."""
    gr_id = insert_gr(store._connect())
    refresh_gr_derived_sql(store, [gr_id])
    store._connect().execute("DELETE FROM gr WHERE gr_id = ?", (gr_id,))
    store._connect().commit()

    result = refresh_gr_derived_sql(store, [gr_id])
    assert result.forgotten == 1
    assert result.refreshed == 0
    assert store.search_gr_fts("vendor") == []


def test_refresh_runs_inside_the_callers_transaction_and_rolls_back_with_it(store):
    """Proves the SAVEPOINT nests rather than committing the caller's work.

    This is the property that makes ingest's single run-wide transaction safe:
    a rolled-back ingest must leave no FTS rows and no findings for rules that
    never landed. A nested `BEGIN` would have committed the outer transaction
    silently, which is the failure this asserts against.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    conn.execute("BEGIN")
    conn.execute(
        "UPDATE gr SET statement = 'rolled back' WHERE gr_id = ?", (gr_id,)
    )
    refresh_gr_derived_sql(store, [gr_id])
    conn.execute("ROLLBACK")

    assert store.get_gr(gr_id).statement == _MINIMAL_GR["statement"]
    assert store.search_gr_fts("rolled") == []


def test_refresh_is_idempotent_and_leaves_exactly_one_fts_row(store):
    """Proves repeated refreshes do not stack rows -- the delete half again."""
    gr_id = insert_gr(store._connect())
    for _ in range(3):
        refresh_gr_derived_sql(store, [gr_id])
    count = (
        store._connect()
        .execute("SELECT count(*) FROM gr_fts WHERE gr_id = ?", (gr_id,))
        .fetchone()[0]
    )
    assert count == 1


def test_refresh_takes_a_list_and_an_empty_list_is_a_no_op(store):
    """Proves the batched shape: ingest calls this once for a whole run."""
    ids = [
        insert_gr(store._connect(), gr_id=f"GR-01HQ2X000000000000000000{i}")
        for i in range(3)
    ]
    result = refresh_gr_derived_sql(store, ids)
    assert result.refreshed == 3
    assert (
        store._connect().execute("SELECT count(*) FROM gr_fts").fetchone()[0] == 3
    )
    assert refresh_gr_derived_sql(store, []).refreshed == 0


# --------------------------------------------------------------------------
# leaked_terms: the absent-versus-real rule applied to a *derived* value
# --------------------------------------------------------------------------


def test_no_index_is_reported_as_unavailable_rather_than_as_no_leakage(store):
    """Proves "leakage was never looked for" is distinguishable from "none found".

    With no index, `V-STY-03` runs on its morphological fallback alone. That is
    a supported state, not a defect -- but it is not the shipped check, and
    `stats` is required to say so, which it cannot do unless the refresh
    reports it.
    """
    gr_id = insert_gr(store._connect())
    result = refresh_gr_derived_sql(store, [gr_id], index_store=None)
    assert result.leaked_terms_available is False
    assert result.leaked_term_count == 0


def _index_with_symbol(path: Path, relative_path: str, name: str) -> SQLiteStore:
    """A minimal real `index.sqlite` carrying one file and one symbol.

    Written with raw SQL rather than through `upsert_symbols`, which re-reads
    the file from disk to compute `content_hash` — there is no checkout here,
    and the identity columns are not what this test is about.
    """
    index = SQLiteStore(path)
    index.migrate()
    conn = index._connect()
    conn.execute(
        "INSERT INTO repo_files (id, repo_root, relative_path, language, "
        "sha256, size_bytes, mtime_ns) "
        "VALUES (1, '/repo', ?, 'java', 'abc', 10, 0)",
        (relative_path,),
    )
    conn.execute(
        "INSERT INTO symbols (id, file_id, language, name, qualified_name, "
        "kind, container, signature, start_byte, end_byte, start_line, "
        "end_line, anchor_key, entity_class, content_hash) "
        "VALUES ('sym-1', 1, 'java', ?, ?, 'method_declaration', NULL, NULL, "
        "0, 10, 1, 2, 'ak1:x', 'function', NULL)",
        (name, f"com.example.{name}"),
    )
    conn.commit()
    return index


def test_leaked_terms_are_built_from_the_requirements_own_cited_files(
    store, tmp_root
):
    """Proves the cross-store join that `V-STY-03`'s sharpest evidence needs.

    `symbols` is in `index.sqlite` and `gr_citation` is in `knowledge.sqlite`;
    the join is done in Python because the two databases are never `ATTACH`ed.
    """
    gr_id = insert_gr(store._connect())
    store._connect().execute(
        "INSERT INTO gr_citation (gr_id, anchor_key, anchor_resolution, "
        "relative_path, start_line, end_line, provenance) "
        "VALUES (?, 'ak1:x', 'symbol', 'src/Order.java', 1, 9, 'extracted')",
        (gr_id,),
    )
    store._connect().commit()

    index = _index_with_symbol(
        tmp_root / "index.sqlite", "src/Order.java", "calcVendorRebate"
    )
    try:
        result = refresh_gr_derived_sql(store, [gr_id], index_store=index)
    finally:
        index.close()

    assert result.leaked_terms_available is True
    # Both `name` and `qualified_name` land in the set.
    assert result.leaked_term_count == 2


def test_open_index_store_if_present_creates_no_database(tmp_root):
    """Proves the `Path.exists()` guard.

    `SQLiteStore._connect` creates the file on its first query, so probing by
    constructing the store materializes an empty `index.sqlite` beside a
    repository that has never been indexed -- indistinguishable from a real one
    on the next command.
    """
    missing = tmp_root / "index.sqlite"
    assert open_index_store_if_present(missing) is None
    assert not missing.exists()

    real = _index_with_symbol(tmp_root / "real.sqlite", "src/A.java", "a")
    real.close()
    opened = open_index_store_if_present(tmp_root / "real.sqlite")
    assert opened is not None
    opened.close()


# --------------------------------------------------------------------------
# refresh_gr_vectors and the gr_statements collection
# --------------------------------------------------------------------------


def test_the_collection_lives_under_the_knowledge_directory(store, tmp_root):
    """Proves `index --reset` cannot reach the requirements vectors.

    `index --reset` rmtrees `index_dir/chroma` wholesale, so a `gr_statements`
    collection created under the index directory is destroyed by a routine
    reindex -- and stage two of the merge would then return no candidates,
    which is indistinguishable from finding no near-duplicates.
    """
    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        assert collection.collection_name == GR_COLLECTION_NAME
        assert collection.base_dir == store.sqlite_path.parent
    finally:
        collection.close()
    assert (tmp_root / "knowledge" / "chroma").exists()
    assert not (tmp_root / "index").exists()


def test_refresh_vectors_embeds_the_statement_with_its_five_metadata_keys(
    store,
):
    """Proves the record reaches the collection carrying its filter metadata."""
    gr_id = insert_gr(store._connect(), category="Policy", subject="Ordering")
    result = refresh_gr_vectors(store, [gr_id], embedder=HashEmbedder(dimension=64))
    assert result.embedded == 1
    assert result.skipped == 0
    assert result.reason is None

    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        got = collection.collection.get(ids=[gr_id])
        assert got["documents"][0] == _MINIMAL_GR["statement"]
        meta = got["metadatas"][0]
        for key in GR_VECTOR_METADATA_KEYS:
            assert key in meta
        assert meta["state"] == "draft"
        assert meta["category"] == "Policy"
        assert collection.count() == 1
    finally:
        collection.close()


def test_a_null_subject_is_stored_as_empty_string_not_dropped(store):
    """Proves the chromadb-1.5.9 absent-versus-real defect is coerced away.

    chromadb 1.5.9 does not reject a `None` metadata value, it *silently drops
    the key*, so "this requirement has no derivable subject" and "nobody wrote
    a subject" would be byte-identical in the collection. `subject` and
    `category` are both nullable on `gr`, so this is not hypothetical.
    """
    gr_id = insert_gr(store._connect(), subject=None, category=None)
    refresh_gr_vectors(store, [gr_id], embedder=HashEmbedder(dimension=64))

    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        meta = collection.collection.get(ids=[gr_id])["metadatas"][0]
        assert meta["subject"] == ""
        assert meta["category"] == ""
        # And the coerced value is filterable, which is what makes '' a real
        # encoding of "absent" rather than a hole.
        hits = collection.collection.get(where={"subject": ""})
        assert hits["ids"] == [gr_id]
    finally:
        collection.close()


def test_no_embedder_degrades_and_names_the_recovery(store):
    """Ingest with no embedder available still stores every rule.

    Step 5's acceptance criterion, unit-level: the end-to-end form runs
    `requirements ingest` and `requirements reindex-vectors`, both Step 8's.
    What is proved here is the contract those commands rest on -- the rules are
    untouched, nothing raises, and the reason names the recovery.
    """
    gr_id = insert_gr(store._connect())
    result = refresh_gr_vectors(store, [gr_id], embedder=None)
    assert result.embedded == 0
    assert result.skipped == 1
    assert result.degraded is True
    assert "reindex-vectors" in result.reason
    # The requirement itself is untouched and keyword search still works.
    refresh_gr_derived_sql(store, [gr_id])
    assert store.search_gr_fts("vendor")


def test_a_failing_embedder_degrades_rather_than_raising(store):
    """Proves the hosted-provider failure mode leaves the rules in the store."""

    class _Broken:
        name = "broken"
        dimension = 64

        def embed_documents(self, texts):
            raise RuntimeError("provider unreachable")

        def embed_query(self, text):
            raise RuntimeError("provider unreachable")

    gr_id = insert_gr(store._connect())
    result = refresh_gr_vectors(store, [gr_id], embedder=_Broken())
    assert result.skipped == 1
    assert "provider unreachable" in result.reason
    assert "reindex-vectors" in result.reason
    assert store.get_gr(gr_id) is not None


def test_a_dimension_mismatch_is_reported_as_unusable_not_stale(store):
    """Proves a switched embedding provider points at the rebuild.

    `validate_dimension()` only raises when the collection *already* carries
    an `embedding_dimension`, which `get_or_create_collection` writes at
    creation and thereafter ignores -- so the case that matters is a
    pre-existing collection under a switched provider, which this sets up.
    """
    gr_id = insert_gr(store._connect())
    refresh_gr_vectors(store, [gr_id], embedder=HashEmbedder(dimension=64))

    result = refresh_gr_vectors(store, [gr_id], embedder=HashEmbedder(dimension=128))
    assert result.embedded == 0
    assert result.skipped == 1
    assert "reindex-vectors" in result.reason


def test_a_deleted_requirement_loses_its_vector(store):
    """Proves the collection does not keep records no `gr` row explains."""
    gr_id = insert_gr(store._connect())
    refresh_gr_vectors(store, [gr_id], embedder=HashEmbedder(dimension=64))
    store._connect().execute("DELETE FROM gr WHERE gr_id = ?", (gr_id,))
    store._connect().commit()

    result = refresh_gr_vectors(store, [gr_id], embedder=HashEmbedder(dimension=64))
    assert result.deleted == 1
    assert result.embedded == 0
    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        assert collection.count() == 0
    finally:
        collection.close()


# --------------------------------------------------------------------------
# The shortfall check
# --------------------------------------------------------------------------


def test_a_short_collection_reports_words_rather_than_zero_candidates():
    """Proves stage two can tell "behind" from "no near duplicates".

    An unsearched collection and a collection with no matches must never
    present the same way -- the same discipline as `not_accounted_for` being
    NULL rather than 0.
    """
    words = describe_vector_shortfall(gr_count=10, collection_count=4)
    assert words is not None
    assert "4 of 10" in words
    assert "reindex-vectors" in words
    assert describe_vector_shortfall(10, 10) is None
    # A surplus is not a shortfall: ids nothing asked about cannot be returned
    # as a candidate for a rule that exists.
    assert describe_vector_shortfall(10, 12) is None


def test_the_shortfall_is_computed_against_the_live_counts(store):
    """Proves the two counts the check compares are both readable."""
    ids = [
        insert_gr(store._connect(), gr_id=f"GR-01HQ2X000000000000000000{i}")
        for i in range(3)
    ]
    refresh_gr_vectors(store, ids[:1], embedder=HashEmbedder(dimension=64))
    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        words = describe_vector_shortfall(store.count_gr(), collection.count())
    finally:
        collection.close()
    assert words is not None
    assert "1 of 3" in words
    assert store.all_gr_ids() == sorted(ids)


# --------------------------------------------------------------------------
# set_state calls the pair -- the seam Step 4 left open
# --------------------------------------------------------------------------


def test_a_state_change_reaches_the_vector_metadata(store):
    """A state change reaches the vector metadata.

    Step 5's acceptance criterion in its unit-level form (the end-to-end form
    runs `requirements search --semantic --state approved`, which is Step 8's).
    **This is the assertion that fails if `set_state` is left off the refresh
    pair's caller list** -- it writes no text, so the vector half looks
    skippable, and skipping it answers a state-filtered semantic search with
    rules still tagged `draft`, silently and forever.
    """
    embedder = HashEmbedder(dimension=64)
    gr_id = insert_gr(store._connect())
    refresh_gr_vectors(store, [gr_id], embedder=embedder)

    set_state(store, gr_id, "approved", "reviewer@example.com", embedder=embedder)

    collection = open_gr_collection(store, embedder)
    try:
        assert (
            collection.collection.get(ids=[gr_id])["metadatas"][0]["state"]
            == "approved"
        )
        assert collection.collection.get(where={"state": "approved"})["ids"] == [
            gr_id
        ]
    finally:
        collection.close()


def test_a_same_state_no_op_re_embeds_nothing(store):
    """Proves the value-changing-write rule reaches the refresh pair.

    A move to the state a record already holds returns before the pair, so no
    embedding call is made -- asserted through an embedder that counts.
    """

    class _CountingEmbedder(HashEmbedder):
        calls = 0

        def embed_documents(self, texts):
            type(self).calls += 1
            return super().embed_documents(texts)

    embedder = _CountingEmbedder(dimension=64)
    gr_id = insert_gr(store._connect(), state="approved")
    _CountingEmbedder.calls = 0
    set_state(store, gr_id, "approved", "reviewer@example.com", embedder=embedder)
    assert _CountingEmbedder.calls == 0


def test_set_state_refreshes_the_fts_row_even_though_it_writes_no_text(store):
    """Proves `set_state` calls the FULL pair, not the vector half alone.

    On one row the SQL half is one delete-and-insert plus one validator run.
    Calling half the pair on a per-site judgement about which halves matter is
    the reasoning that produces a half-synced store.
    """
    gr_id = insert_gr(store._connect())
    assert store.search_gr_fts("vendor") == []
    set_state(store, gr_id, "reviewed", "reviewer@example.com")
    assert [g for g, _ in store.search_gr_fts("vendor")] == [gr_id]


def test_set_state_records_the_review_and_still_refuses_a_blocked_approval(store):
    """Proves wiring the pair did not disturb the Step 4 gate."""
    from legacylift_search.gr_state import StateTransitionError

    gr_id = insert_gr(store._connect(), pattern=None, rule_class=None)
    with pytest.raises(StateTransitionError):
        set_state(store, gr_id, "approved", "reviewer@example.com")
    assert store.get_gr(gr_id).state == "draft"


# --------------------------------------------------------------------------
# upsert_texts' own contract
# --------------------------------------------------------------------------


def test_upsert_texts_refuses_ragged_input(store):
    """Proves the four lists are checked rather than silently zipped short."""
    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        with pytest.raises(ValueError):
            collection.upsert_texts(
                ids=["a", "b"],
                texts=["x"],
                embeddings=[[0.0] * 64],
                metadatas=[{"gr_id": "a"}],
            )
    finally:
        collection.close()


def test_count_reports_zero_on_a_fresh_collection(store):
    """Proves the count wrapper the shortfall check needs exists and is honest."""
    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        assert collection.count() == 0
    finally:
        collection.close()


def test_the_collection_name_is_chroma_legal():
    """Proves the name passes Chroma's 3-512 char `[a-zA-Z0-9._-]` validation.

    A short fixture name like `"c"` raises `InvalidArgumentError` from
    `get_or_create_collection`, which reads as a configuration failure and is
    not one -- worth pinning so nobody shortens this constant.
    """
    assert 3 <= len(GR_COLLECTION_NAME) <= 512
    assert GR_COLLECTION_NAME[0].isalnum() and GR_COLLECTION_NAME[-1].isalnum()
    assert all(c.isalnum() or c in "._-" for c in GR_COLLECTION_NAME)


def test_requirements_vectors_are_not_in_the_code_chunks_collection():
    """Proves requirements get a dedicated collection.

    Putting them in `code_chunks` would poison code search and force every
    existing query to carry a type filter.
    """
    from legacylift_search.config import IndexConfig

    assert GR_COLLECTION_NAME != IndexConfig.model_fields["collection_name"].default
