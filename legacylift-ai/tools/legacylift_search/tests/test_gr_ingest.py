"""Tests for Step 6: the two-stage merge with dedupe.

Milestone 1, Step 6 of `docs/exec-plans/active/reqs-to-data-store.md`. Every
test here fails before Step 6 with
`No module named 'legacylift_search.gr_ingest'` and passes after.

`ingest_extraction` is a callable function with no CLI dependency (Step 8
wires `requirements ingest` to it), so these tests drive it directly. Two
consequences for how they are written:

* **The human write path is Step 8's `set-field`, which does not exist yet.**
  Where a test needs a human-edited column it writes it through
  `KnowledgeStore.update_gr_row`, which is the mechanical writer `set-field`
  will use, and says so. What is being tested is the merge's protection, not
  the command.
* **"Exits zero" is asserted as "returns normally".** There is no process to
  exit, so the observable at this layer is that a degraded vector phase
  produces an `IngestResult` carrying `embed.reason` rather than an
  exception.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

from legacylift_search.embeddings import HashEmbedder
from legacylift_search.gr_fields import EXTRACTOR_FIELD_MAP, HUMAN_WRITABLE_FIELDS
from legacylift_search.gr_ingest import (
    CHILD_MAPPED_KEYS,
    VERBATIM_KEYS,
    IngestError,
    ingest_extraction,
    unmapped_rule_keys,
)
from legacylift_search.gr_keys import TIER_SPAN_HASHES, TIER_STRUCTURED_BODY
from legacylift_search.gr_refresh import (
    GR_COLLECTION_NAME,
    open_gr_collection,
    refresh_gr_vectors,
)
from legacylift_search.knowledge_store import KnowledgeStore

#: Chroma's `PersistentClient` keeps its own SQLite files open past `close()`
#: on Windows often enough that the house pattern in `tests/test_vector_store.py`
#: is to tolerate a failed teardown rather than leak a test failure out of one.
_IS_WINDOWS = sys.platform == "win32"


# ----------------------------------------------------------------------
# Fixtures and payload builders
# ----------------------------------------------------------------------


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def repo(tmp_root):
    """A tiny working tree, deliberately never indexed.

    Most of these tests do not need a Layer-0 index: the file-level anchor is
    the *total* floor and is index-independent by construction, so a citation
    resolving to `anchor_resolution = 'file'` is correct rather than
    degraded. The tests that care about the index say so.
    """
    root = tmp_root / "repo"
    root.mkdir()
    (root / "Order.java").write_text(
        "\n".join(f"// order line {i}" for i in range(1, 61)), encoding="utf-8"
    )
    (root / "Vendor.java").write_text(
        "\n".join(f"// vendor line {i}" for i in range(1, 61)), encoding="utf-8"
    )
    return root


@pytest.fixture
def store(tmp_root):
    ks = KnowledgeStore(tmp_root / "knowledge" / "knowledge.sqlite")
    try:
        yield ks
    finally:
        ks.close()


@pytest.fixture
def index_path(tmp_root):
    """Where `index.sqlite` *would* be. Deliberately not created.

    Acceptance requires that ingesting against an unindexed repository
    creates no `index.sqlite`, so the path is handed to ingest and its
    continued absence is asserted.
    """
    return tmp_root / "index" / "index.sqlite"


def rule(**overrides):
    """One conforming rule object carrying every `RULES_SCHEMA` key.

    Every key is present so the completeness test has a full object to work
    over — `RULES_SCHEMA` marks several optional, and a fixture that omitted
    them would make the mapping assertion weaker than the real input.
    """
    base = {
        "name": "Vendor number required",
        "category": "Validation",
        "priority": "P0",
        "source": "Order.java:10-20",
        "plainEnglish": "The code rejects an order with no vendor number.",
        "ruleClass": "behavioral",
        "pattern": "B-UNCOND",
        "statement": "An order must record a vendor number.",
        "modality": "requirement",
        "assumptions": "",
        "implementationNotes": "OrderDAO.save() throws MissingVendorException.",
        "given": "an order with no vendor number",
        "when": "it is saved",
        "then": "the save is rejected",
        "and": "an error is recorded",
        "parameters": "none",
        "edgeCases": ["a blank string", "whitespace only"],
        "suspectedDefect": "",
        "confidence": "High",
        "smeQuestion": "",
    }
    base.update(overrides)
    return base


def payload(*rules, **overrides):
    """One extractor-output payload. `coverage` defaults to measured."""
    body = {
        "system": "demo",
        "rounds": 2,
        "confirmedRules": list(rules),
        "rejectedRules": [],
        "injectionFlags": [],
        "coverage": {
            "total": 100,
            "claimed": 100,
            "uncovered": 0,
            "pct": 100.0,
            "uncovered_chunks": [],
        },
    }
    body.update(overrides)
    return body


def counts(store: KnowledgeStore) -> dict[str, int]:
    conn = store._connect()
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "gr",
            "gr_citation",
            "gr_citation_anchor",
            "gr_scenario",
            "gr_edge_case",
            "gr_run",
            "gr_run_hit",
            "gr_merge_candidate",
        )
    }


def one_gr(store: KnowledgeStore) -> sqlite3.Row:
    return store._connect().execute("SELECT * FROM gr").fetchone()


def ingest(store, body, repo_root, index_sqlite_path=None, **kwargs):
    """`ingest_extraction` with the notices captured instead of printed."""
    notices: list[str] = []
    kwargs.setdefault("on_notice", notices.append)
    return ingest_extraction(
        store, body, repo_root, index_sqlite_path=index_sqlite_path, **kwargs
    )


# ----------------------------------------------------------------------
# The headline merge criteria
# ----------------------------------------------------------------------


def test_reingesting_the_same_json_changes_no_count_at_any_level(
    store, repo, index_path
):
    """Proves the merge is idempotent at all four grains, not just at `gr`.

    The headline acceptance criterion, stated against a **fixed input**: the
    same saved extractor-output JSON twice leaves the requirement count
    unchanged *and* the citation, scenario and edge-case counts unchanged,
    while `gr_run` gains a second row whose `rules_merged` equals the first
    run's `rules_in`.

    All four counts are named because a flat requirement count over any
    growing child table is the same bug one level down — and `gr_scenario` is
    the largest of them, so a merge that inserted a second full set of
    scenarios every run would pass a requirement-count-only test.
    """
    body = payload(rule(), rule(name="Second", source="Vendor.java:5-9"))
    first = ingest(store, body, repo, index_path)
    before = counts(store)
    assert before["gr"] == 2
    assert before["gr_citation"] == 2
    assert before["gr_scenario"] == 2
    assert before["gr_edge_case"] == 4

    second = ingest(store, body, repo, index_path)
    after = counts(store)

    assert after["gr"] == before["gr"]
    assert after["gr_citation"] == before["gr_citation"]
    assert after["gr_scenario"] == before["gr_scenario"]
    assert after["gr_edge_case"] == before["gr_edge_case"]
    assert after["gr_run"] == 2
    assert second.rules_merged == first.rules_in == 2
    assert second.rules_new == 0

    stored_merged = (
        store._connect()
        .execute("SELECT rules_merged FROM gr_run WHERE run_id = ?", (second.run_id,))
        .fetchone()[0]
    )
    assert stored_merged == first.rules_in


def test_a_value_preserving_reingest_does_not_move_updated_at(
    store, repo, index_path
):
    """Proves a write that changes no value does not bump `updated_at`.

    Two headline claims are false without this: re-ingesting the same output
    *changes nothing*, and the second export is *byte-identical* while
    explicitly including the per-record timestamps on the grounds that they
    "change only when the record does". Stamp `updated_at` unconditionally
    and the export diff that should make a single reviewed wording change
    visible in a pull request instead shows all several hundred records as
    modified, which is the same as showing nothing.
    """
    body = payload(rule())
    ingest(store, body, repo, index_path)
    before = one_gr(store)

    ingest(store, body, repo, index_path)
    after = one_gr(store)

    assert after["updated_at"] == before["updated_at"]
    assert after["created_at"] == before["created_at"]
    # And the citation's own drift columns held still for the same reason.
    citation = (
        store._connect().execute("SELECT verified_at FROM gr_citation").fetchone()
    )
    assert citation["verified_at"] == before["created_at"]


def test_a_no_change_merge_still_records_a_run_hit(store, repo, index_path):
    """Proves being *seen* by a run and being *changed* by it are separate facts.

    The value-changing-write rule must not be read as contradicting
    `gr_run_hit`: a run that merges an identical rule still records its hit
    with outcome `merged`, and the hit table is what records the first fact.
    Without this, "which runs saw this rule" would silently lose every run
    that changed nothing — which on an idempotent re-ingest is every run.
    """
    body = payload(rule())
    ingest(store, body, repo, index_path)
    second = ingest(store, body, repo, index_path)

    assert second.merges_with_no_change == 1
    outcomes = (
        store._connect()
        .execute(
            "SELECT outcome FROM gr_run_hit WHERE run_id = ?", (second.run_id,)
        )
        .fetchall()
    )
    assert [r[0] for r in outcomes] == ["merged"]


def test_the_seven_protected_human_fields_survive_reingest(store, repo, index_path):
    """Proves the merge never overwrites a human's recorded judgement.

    `HUMAN_WRITABLE_FIELDS` is nine columns and the merge must touch none of
    them. Seven are asserted here as *protected*: `enforcement_level`,
    `confidence_intent`, `disposition`, `modality_confirmed`, `rationale`,
    `fit_criterion` and `owner`.

    `rule_class` and `pattern` are deliberately **not** asserted the way the
    other seven are, and that is the point of this test's name: they are
    untouched **by construction rather than by protection** — both feed both
    dedupe keys, so an exact-key hit implies the incoming values already
    agree and an anchor-only hit inserts rather than updates. A test that
    passed only because the merge protected them would be testing the wrong
    mechanism, so the test that covers them is
    `test_changing_rule_class_re_keys_and_inserts_rather_than_merging`.

    The three shadowed fields have their own test below. The writes here go
    through `update_gr_row`, the mechanical writer Step 8's `set-field` will
    use.
    """
    body = payload(rule())
    ingest(store, body, repo, index_path)
    gr_id = one_gr(store)["gr_id"]

    human = {
        "enforcement_level": "deferred",
        "confidence_intent": "High",
        "disposition": "delegated",
        "modality_confirmed": 1,
        "rationale": "The SME confirmed this on 2026-09-02.",
        "fit_criterion": "No order saves without a vendor number.",
        "owner": "dnorton@captechconsulting.com",
    }
    assert set(human) <= HUMAN_WRITABLE_FIELDS
    store.update_gr_row(gr_id, human)
    store.commit()

    ingest(store, body, repo, index_path)

    after = one_gr(store)
    for column, value in human.items():
        assert after[column] == value, f"the merge overwrote {column}"


def test_the_three_shadowed_fields_keep_the_human_value_and_refresh_the_shadow(
    store, repo, index_path
):
    """Proves the shadow write is unconditional and the live write is not.

    For each of `statement`, `assumptions` and `modality`, the incoming value
    goes to its `_extracted` shadow **always**, and to the live column **only
    if the live column equals its shadow on the stored row**. Where they
    differ the human's version stands and the new extractor value is still
    captured in the shadow, so a reviewer can see what the extractor would
    now say.
    """
    ingest(store, payload(rule()), repo, index_path)
    gr_id = one_gr(store)["gr_id"]

    store.update_gr_row(
        gr_id,
        {
            "statement": "An order must carry a vendor number.",
            "assumptions": "The vendor master is authoritative.",
            "modality": "expectation",
        },
    )
    store.commit()

    ingest(
        store,
        payload(
            rule(
                statement="An order must record a vendor identifier.",
                assumptions="Nothing is assumed.",
                modality="requirement",
            )
        ),
        repo,
        index_path,
    )

    after = one_gr(store)
    assert after["statement"] == "An order must carry a vendor number."
    assert after["assumptions"] == "The vendor master is authoritative."
    assert after["modality"] == "expectation"
    assert after["statement_extracted"] == "An order must record a vendor identifier."
    assert after["assumptions_extracted"] == "Nothing is assumed."
    assert after["modality_extracted"] == "requirement"


def test_an_unedited_rule_with_no_assumptions_is_not_read_as_human_edited(
    store, repo, index_path
):
    """Proves the shadow equality is SQLite `IS` and not `=`.

    `assumptions` is the nullable shadowed field, and `=` over two NULLs
    yields NULL rather than true — so under `=` an unedited rule with no
    assumptions reads as human-edited and the merge stops updating it,
    permanently and silently. This is the test that fails if the equality
    was written as `=`, or if it was got right for `statement` and `modality`
    (both `NOT NULL`, where the two operators agree) and wrong for the third.

    The absence is genuine: the first payload omits the key entirely, so both
    the live column and its shadow are NULL.
    """
    first = rule()
    del first["assumptions"]
    ingest(store, payload(first), repo, index_path)
    before = one_gr(store)
    assert before["assumptions"] is None
    assert before["assumptions_extracted"] is None
    assert store.gr_shadow_is_unedited(before["gr_id"], "assumptions") is True

    second = rule(assumptions="The upstream feed is trusted.")
    ingest(store, payload(second), repo, index_path)

    after = one_gr(store)
    assert after["assumptions"] == "The upstream feed is trusted."
    assert after["assumptions_extracted"] == "The upstream feed is trusted."


def test_an_empty_assumptions_string_is_stored_as_itself_not_as_null(
    store, repo, index_path
):
    """Proves `''` and NULL keep different meanings in `assumptions`.

    The extractor now always emits `assumptions`, sending `""` where the code
    assumes nothing. `""` means the agent considered assumptions and had
    none; NULL means the field never arrived. Normalizing `""` to NULL is
    this plan's recurring absent-versus-real defect.
    """
    ingest(store, payload(rule(assumptions="")), repo, index_path)
    row = one_gr(store)
    assert row["assumptions"] == ""
    assert row["assumptions_extracted"] == ""


# ----------------------------------------------------------------------
# Stage one's fallback, and stage two
# ----------------------------------------------------------------------


def test_a_drifted_citation_produces_a_drift_candidate_not_a_cold_miss(
    store, repo, index_path
):
    """Proves stage one's anchor-only fallback recognises drifted code.

    Tier 2 of the discriminator is the span-level `content_hash`, so *any*
    edit to the cited code re-keys the rule and it misses on the full key.
    Routing it to review is correct on the merits — but on a repository under
    active modernization drift is the *normal* case, so it must not arrive
    indistinguishable from a genuinely new rule. It matches
    `dedupe_key_anchor_only`, lands in `gr_merge_candidate` with
    `reason = 'drift'`, and **inserts a row as well**: a candidate is never a
    merge.
    """
    body = payload(rule())
    ingest(store, body, repo, index_path)
    original = one_gr(store)["gr_id"]

    lines = (repo / "Order.java").read_text(encoding="utf-8").splitlines()
    lines[14] = "// EDITED inside the cited range"
    (repo / "Order.java").write_text("\n".join(lines), encoding="utf-8")

    second = ingest(store, body, repo, index_path)

    assert second.rules_candidate == 1
    assert second.rules_new == 0
    assert second.rules_merged == 0
    assert counts(store)["gr"] == 2
    candidates = (
        store._connect()
        .execute(
            "SELECT gr_id_existing, gr_id_incoming, reason, similarity, "
            "resolution FROM gr_merge_candidate"
        )
        .fetchall()
    )
    assert len(candidates) == 1
    assert candidates[0]["gr_id_existing"] == original
    assert candidates[0]["reason"] == "drift"
    # NULL, not zero: found structurally, so it has no similarity score at
    # all and must not read back as "semantically unrelated".
    assert candidates[0]["similarity"] is None
    assert candidates[0]["resolution"] == "unresolved"
    hits = (
        store._connect()
        .execute("SELECT outcome FROM gr_run_hit WHERE run_id = ?", (second.run_id,))
        .fetchall()
    )
    assert [r[0] for r in hits] == ["candidate"]


def test_changing_rule_class_re_keys_and_inserts_rather_than_merging(
    store, repo, index_path
):
    """Proves an exact-key merge can never change `rule_class` or `pattern`.

    This is the mechanism behind those two columns' exemption from the
    protected-field test: both feed **both** keys, so a run that reclassifies
    the same code re-keys the rule in both columns, misses stage one
    entirely, and inserts a new row. The stored row's values are therefore
    reachable by a merge only if they already agree.

    It also records the behaviour Step 6 names as a measurement: the
    second-run `rules_candidate` count over an unchanged working tree is a
    direct reading of key instability under extractor nondeterminism.
    """
    ingest(store, payload(rule()), repo, index_path)
    original = one_gr(store)
    assert original["rule_class"] == "behavioral"

    second = ingest(
        store,
        payload(rule(ruleClass="definitional", pattern="D-NEC")),
        repo,
        index_path,
    )

    assert second.rules_merged == 0
    assert counts(store)["gr"] == 2
    rows = (
        store._connect()
        .execute("SELECT gr_id, rule_class, pattern FROM gr ORDER BY gr_id")
        .fetchall()
    )
    stored = {r["gr_id"]: (r["rule_class"], r["pattern"]) for r in rows}
    assert stored[original["gr_id"]] == ("behavioral", "B-UNCOND")
    assert ("definitional", "D-NEC") in stored.values()


def test_stage_two_raises_a_range_overlap_candidate_and_never_merges(
    store, repo, index_path
):
    """Proves intersection is the candidate search while equality is the key.

    A second rule citing an *overlapping but not identical* line range on the
    same file misses the full key by construction, because the span hash
    covers different lines. It must also miss the anchor-only key for stage
    two to be the thing under test, so this rule carries a different
    `pattern` — which is exactly the case Step 6 says stage two exists to
    catch, a run that reshaped its judgement of the rule. Stage two's
    structural half then finds it by line-range **intersection** and
    surfaces the pair; the row is still inserted, because no similarity
    signal auto-merges anything at any confidence.

    Exact range equality is right for a *key* and intersection is right for a
    *candidate search*: different jobs, both needed.
    """
    ingest(store, payload(rule(source="Order.java:10-20")), repo, index_path)
    second = ingest(
        store,
        payload(
            rule(
                name="Overlapping",
                source="Order.java:15-25",
                pattern="B-COND",
                statement=(
                    "When the vendor number is absent, an order must be "
                    "rejected."
                ),
            )
        ),
        repo,
        index_path,
    )

    assert second.rules_candidate == 1
    assert counts(store)["gr"] == 2
    row = (
        store._connect()
        .execute("SELECT reason, similarity FROM gr_merge_candidate")
        .fetchone()
    )
    assert row["reason"] == "range_overlap"
    assert row["similarity"] is None


def test_a_candidate_pair_is_raised_once_and_a_resolution_survives(
    store, repo, index_path
):
    """Proves `run_id` is outside `gr_merge_candidate`'s primary key.

    The pair *is* the relationship's identity, so surfacing it again updates
    one row rather than raising it a second time — and a reviewer's
    judgement that two records are genuinely `distinct` sticks, so the pair
    does not resurface on every subsequent run. This is the assertion that
    fails if `run_id` is inside the uniqueness tuple: run N+2 would re-raise
    a pair resolved in run N, reintroducing through the constraint the exact
    behaviour the constraint exists to stop.
    """
    ingest(store, payload(rule(source="Order.java:10-20")), repo, index_path)
    overlapping = payload(rule(name="Overlapping", source="Order.java:15-25"))
    ingest(store, overlapping, repo, index_path)
    assert counts(store)["gr_merge_candidate"] == 1

    ingest(store, overlapping, repo, index_path)
    assert counts(store)["gr_merge_candidate"] == 1

    conn = store._connect()
    conn.execute(
        "UPDATE gr_merge_candidate SET resolution = 'distinct', "
        "resolved_at = '2026-09-02T00:00:00Z'"
    )
    conn.commit()

    ingest(store, overlapping, repo, index_path)
    row = conn.execute(
        "SELECT resolution, resolved_at FROM gr_merge_candidate"
    ).fetchone()
    assert counts(store)["gr_merge_candidate"] == 1
    assert row["resolution"] == "distinct"
    assert row["resolved_at"] == "2026-09-02T00:00:00Z"


def test_stage_twos_semantic_half_surfaces_a_pair_and_never_merges(
    store, repo, index_path
):
    """Proves the `gr_statements` search raises candidates without merging.

    The second rule cites a different file and carries a different
    `pattern`, so both keys miss and the line-range intersection finds
    nothing — the semantic half is the only thing that can see it. Its
    `statement` is byte-identical to the first rule's, which under
    `HashEmbedder` is the same vector and so distance zero: a deterministic
    hit that does not depend on an embedding model's judgement.

    The row is still inserted and `similarity` is recorded rather than left
    NULL, because unlike a `drift` or `range_overlap` pair this one *does*
    have a score. **No similarity threshold auto-merges anything at any
    confidence**, so the outcome is `candidate` and the corpus keeps both
    rows for a reviewer to judge.
    """
    embedder = HashEmbedder()
    shared = "An order must record a vendor number."
    ingest(
        store,
        payload(rule(statement=shared, source="Order.java:10-20")),
        repo,
        index_path,
        embedder=embedder,
    )
    first = one_gr(store)["gr_id"]

    second = ingest(
        store,
        payload(
            rule(
                name="Same wording elsewhere",
                statement=shared,
                pattern="B-COND",
                source="Vendor.java:40-45",
            )
        ),
        repo,
        index_path,
        embedder=embedder,
    )

    assert counts(store)["gr"] == 2
    assert second.rules_candidate == 1
    assert second.rules_merged == 0
    row = (
        store._connect()
        .execute(
            "SELECT gr_id_existing, reason, similarity FROM gr_merge_candidate"
        )
        .fetchone()
    )
    assert row["gr_id_existing"] == first
    assert row["reason"] == "semantic"
    assert row["similarity"] is not None
    assert row["similarity"] > 0.0


# ----------------------------------------------------------------------
# The child sets
# ----------------------------------------------------------------------


def test_the_child_sets_do_not_double_and_a_human_row_survives(
    store, repo, index_path
):
    """Proves the merge refreshes the `extracted` subset and nothing else.

    Scenarios and edge cases are not *fields*, so the ownership partition
    says nothing about them and an implementer working from the partition
    alone writes a merge that inserts a second full set every run. The rule
    is: compare the incoming set against the stored `provenance = 'extracted'`
    rows; if identical do nothing at all, otherwise delete that subset and
    insert the incoming one. Scoping the delete to `extracted` is what
    preserves a reviewer's own scenarios, which a blanket delete would
    destroy.
    """
    body = payload(rule())
    ingest(store, body, repo, index_path)
    gr_id = one_gr(store)["gr_id"]

    conn = store._connect()
    conn.execute(
        'INSERT INTO gr_scenario (gr_id, ordinal, "given", "when", "then", '
        "and_clause, provenance) VALUES (?, 0, ?, ?, ?, NULL, 'human')",
        (gr_id, "a reviewer's own case", "it happens", "this is expected"),
    )
    conn.execute(
        "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) "
        "VALUES (?, 0, ?, 'human')",
        (gr_id, "a reviewer's own edge case"),
    )
    conn.commit()

    ingest(store, body, repo, index_path)

    assert counts(store)["gr_scenario"] == 2
    assert counts(store)["gr_edge_case"] == 3
    assert len(store.list_gr_scenarios(gr_id, "extracted")) == 1
    human = store.list_gr_scenarios(gr_id, "human")
    assert len(human) == 1
    assert human[0].given == "a reviewer's own case"
    assert len(store.list_gr_edge_cases(gr_id, "human")) == 1


def test_a_scenario_absent_from_the_second_input_actually_disappears(
    store, repo, index_path
):
    """Proves the refresh is delete-then-insert rather than an upsert.

    An upsert satisfies `UNIQUE (gr_id, provenance, ordinal)` and still
    leaves the stale rows behind, so a scenario the extractor no longer emits
    would be stranded on the record forever. The delete half is what makes it
    actually disappear.
    """
    ingest(store, payload(rule()), repo, index_path)
    gr_id = one_gr(store)["gr_id"]
    assert len(store.list_gr_scenarios(gr_id)) == 1
    assert len(store.list_gr_edge_cases(gr_id)) == 2

    stripped = rule()
    for key in ("given", "when", "then", "and"):
        del stripped[key]
    stripped["edgeCases"] = ["a blank string"]
    ingest(store, payload(stripped), repo, index_path)

    assert store.list_gr_scenarios(gr_id) == []
    assert [e.text for e in store.list_gr_edge_cases(gr_id)] == ["a blank string"]


def test_a_repeated_citation_range_inserts_one_row_and_a_new_one_is_added(
    store, repo, index_path
):
    """Proves "add any new citations" means insert on the uniqueness tuple.

    A citation already present is left alone; a new one is inserted. Without
    this the requirement count stays flat across two ingests — the headline
    acceptance test — while the citation count doubles underneath it, the
    same bug one level down.

    A second citation is added by widening the rule's `source`, which does
    change the dedupe key, so this asserts the citation *rows*: the second
    ingest of the widened rule inserts one requirement carrying two
    citations, and re-ingesting it adds no third row.
    """
    widened = rule(source='["Order.java:10-20", "Vendor.java:5-9"]')
    ingest(store, payload(widened), repo, index_path)
    assert counts(store)["gr_citation"] == 2

    result = ingest(store, payload(widened), repo, index_path)
    assert counts(store)["gr_citation"] == 2
    assert result.citations_seen == 2
    assert result.citations_inserted == 0


# ----------------------------------------------------------------------
# Failure and degradation
# ----------------------------------------------------------------------


def test_ingest_with_no_embedder_stores_every_rule_and_says_so(
    store, repo, index_path
):
    """Proves `embedder=None` is a degraded success, not a failure.

    The rules are committed before the vector phase runs, so a missing
    embedder must leave the store correct and merely under-populated. Ingest
    reports `EmbedResult.reason`, that reason names `reindex-vectors` as the
    single recovery, and the caller **exits zero** — asserted here as
    "returns normally", since there is no process to exit. A non-zero exit
    would read as "the ingest failed" and invite re-running the extraction,
    which is hours of model time to recover something that was never lost.
    """
    result = ingest(store, payload(rule(), rule(name="B", source="Vendor.java:1-3")), repo, index_path)

    assert counts(store)["gr"] == 2
    assert result.rules_in == 2
    assert result.vectors_degraded is True
    assert result.embed is not None
    assert result.embed.skipped == 2
    assert "reindex-vectors" in (result.embed.reason or "")
    assert any("reindex-vectors" in n for n in result.notices)


def test_a_subsequent_reindex_populates_the_collection(store, repo, index_path):
    """Proves the documented recovery works with no re-extraction.

    The second half of the criterion above: after an ingest with no embedder,
    running the vector refresh once an embedder is available populates
    `gr_statements` so stage two starts working — and nothing in that
    sequence re-runs the extraction.
    """
    ingest(store, payload(rule()), repo, index_path)
    gr_ids = store.all_gr_ids()
    assert gr_ids

    embedder = HashEmbedder()
    embed = refresh_gr_vectors(store, gr_ids, embedder)
    assert embed.embedded == len(gr_ids)
    assert embed.skipped == 0

    collection = open_gr_collection(store, embedder)
    try:
        assert collection.collection_name == GR_COLLECTION_NAME
        assert collection.count() == len(gr_ids)
    finally:
        collection.close()


def test_ingest_against_an_unindexed_repository_is_loud_and_creates_no_index(
    store, repo, index_path
):
    """Proves the `Path.exists()` guard is in place and the banner is loud.

    `SQLiteStore.__init__` only records the path; `_connect()` opens lazily
    and SQLite creates the file on that first query — so constructing a store
    against a missing `index.sqlite` materializes an empty database and then
    fails on `no such table: symbols`. An empty index database beside an
    unindexed repository is indistinguishable from a real one on the next
    command, so acceptance requires that **no `index.sqlite` is created**.

    The banner must name the *resolved* index path, because a mis-resolved
    path under the new output layout and a repository that genuinely was
    never indexed produce identical corpora and call for opposite fixes.
    """
    notices: list[str] = []
    result = ingest_extraction(
        store,
        payload(rule()),
        repo,
        index_sqlite_path=index_path,
        on_notice=notices.append,
    )

    assert not index_path.exists()
    assert not index_path.parent.exists()
    assert result.index_present is False
    assert any(str(index_path) in n for n in notices)
    resolutions = (
        store._connect()
        .execute("SELECT DISTINCT anchor_resolution FROM gr_citation")
        .fetchall()
    )
    assert [r[0] for r in resolutions] == ["file"]
    assert result.anchor_resolution_counts == {"file": 1}
    # Correct rather than degraded: the floor is total, so the rule landed.
    assert counts(store)["gr"] == 1


def test_a_citation_naming_an_absent_path_is_unresolved_with_a_null_hash(
    store, repo, index_path
):
    """Proves `unresolved` means one specific thing and is wired up.

    `unresolved` is reserved for the citation whose `relative_path` is simply
    not in the working tree — the one case where a file-level anchor is
    *computable but describes nothing*. So the anchor is computed anyway (the
    key space must stay bounded by path) and the label says what it is, with
    a NULL `content_hash` beside it. A permanent zero on this rate would mean
    the label was never wired up rather than that the corpus is clean.
    """
    ingest(store, payload(rule(source="NotInTheTree.java:1-5")), repo, index_path)
    row = (
        store._connect()
        .execute(
            "SELECT anchor_key, anchor_resolution, content_hash FROM gr_citation"
        )
        .fetchone()
    )
    assert row["anchor_resolution"] == "unresolved"
    assert row["content_hash"] is None
    assert row["anchor_key"].startswith("ak1:")
    assert row["anchor_key"] != ""


def test_a_failed_ingest_leaves_no_gr_run_row_and_no_gr_rows(
    store, repo, index_path
):
    """Proves the whole SQLite half is one transaction.

    Per-rule commits would leave a `gr_run` describing a run that
    half-happened, and a retry would append a second run so `rules_in`
    double-counts the rules the first attempt already wrote. Because the
    whole half is one transaction, a failure leaves **no `gr_run` row at
    all** — so a retry is a first ingest needing no cleanup, no resume flag
    and no deduplication of run metadata.

    The failure is placed at the *second* rule deliberately: the first rule
    has already been written to the connection when it fires.
    """
    ragged = rule(
        name="Ragged table",
        source="Vendor.java:5-9",
        structuredBodyType="decision_table",
        structuredBody={
            "hitPolicy": "UNIQUE",
            "inputs": [
                {"label": "status", "expression": "o.status", "typeRef": "string"},
                {"label": "amount", "expression": "o.amount", "typeRef": "number"},
            ],
            "outputs": [{"label": "action", "typeRef": "string"}],
            "rules": [{"inputEntries": ["Open"], "outputEntries": ["reject"]}],
        },
    )
    with pytest.raises(IngestError):
        ingest(store, payload(rule(), ragged), repo, index_path)

    after = counts(store)
    assert after["gr"] == 0
    assert after["gr_run"] == 0
    assert after["gr_run_hit"] == 0
    assert after["gr_citation"] == 0
    assert after["gr_scenario"] == 0

    # And the retry is a clean first ingest: no cleanup, no resume flag.
    ok = ingest(store, payload(rule()), repo, index_path)
    assert ok.rules_new == 1
    assert counts(store)["gr_run"] == 1


def test_a_ragged_decision_table_fails_naming_the_rule_by_offer_ordinal(
    store, repo, index_path
):
    """Proves the error names the offending rule and the field that failed.

    "ingest failed" over a 470-rule file tells the analyst nothing and sends
    them back to an extraction that cost hours of model time. A ragged table
    converts to invalid DMN and the conversion is what the executability
    argument rests on, so the failure has to land at ingest — where the
    offending rule can still be named — and not months later.
    """
    ragged = rule(
        structuredBodyType="decision_table",
        structuredBody={
            "hitPolicy": "UNIQUE",
            "inputs": [
                {"label": "status", "expression": "o.status", "typeRef": "string"},
                {"label": "amount", "expression": "o.amount", "typeRef": "number"},
            ],
            "outputs": [{"label": "action", "typeRef": "string"}],
            "rules": [{"inputEntries": ["Open"], "outputEntries": ["reject"]}],
        },
    )
    with pytest.raises(IngestError) as excinfo:
        ingest(store, payload(rule(source="Vendor.java:1-2"), ragged), repo, index_path)

    assert excinfo.value.offer_ordinal == 1
    assert excinfo.value.field == "structuredBody"
    message = str(excinfo.value)
    assert "offer_ordinal 1" in message
    assert "structuredBody" in message
    assert "inputEntries" in message


def test_a_structured_body_without_its_type_is_a_rejected_row(
    store, repo, index_path
):
    """Proves the pair is all-or-nothing rather than defaulted.

    The type is what selects the validation schema, and a guessed type
    validates against the wrong one — so a body arriving without a type is a
    rejected row, never a defaulted one.
    """
    with pytest.raises(IngestError) as excinfo:
        ingest(
            store,
            payload(rule(structuredBody={"expression": "a", "scope": "b",
                                         "notation": "prose"})),
            repo,
            index_path,
        )
    assert excinfo.value.field == "structuredBodyType"
    assert counts(store)["gr"] == 0


def test_a_valid_structured_body_round_trips_and_selects_tier_one(
    store, repo, index_path
):
    """Proves a typed body stores verbatim and becomes the tier-1 discriminator.

    `len(rules)` is exactly the per-table rule count Step 10 must measure, so
    the stored JSON has to keep the rows. And the canonical form of the body
    is the tier-1 discriminator, which outranks the span-hash set — asserted
    through `IngestResult.discriminator_tiers`, because the tier is not
    recoverable from the key itself.
    """
    body = {
        "hitPolicy": "UNIQUE",
        "inputs": [{"label": "status", "expression": "o.status",
                    "typeRef": "string"}],
        "outputs": [{"label": "action", "typeRef": "string"}],
        "rules": [
            {"inputEntries": ["Open"], "outputEntries": ["recalculate"]},
            {"inputEntries": ["Closed"], "outputEntries": ["reject"]},
        ],
    }
    result = ingest(
        store,
        payload(rule(structuredBodyType="decision_table", structuredBody=body)),
        repo,
        index_path,
    )
    assert result.discriminator_tiers == {TIER_STRUCTURED_BODY: 1}
    # And the same rule with the body removed falls to tier 2, which is what
    # makes the tier-1 assertion above a statement about precedence rather
    # than about the only tier ingest can reach.
    assert TIER_SPAN_HASHES not in result.discriminator_tiers
    row = one_gr(store)
    assert row["structured_body_type"] == "decision_table"
    assert len(json.loads(row["structured_body"])["rules"]) == 2


def test_an_empty_statement_gets_the_pattern_free_fallback(store, repo, index_path):
    """Proves `gr.statement` is never empty and the fallback adds no `pattern`.

    `statement` is `NOT NULL` because four things downstream read it — the
    validator, the FTS5 index, the `gr_statements` embedding, and the
    `statement = statement_extracted` equality that is the *sole* definition
    of "a human edited this". The fallback's load-bearing property is that it
    produces **text only and never a `pattern` value**, so both dedupe keys,
    the `approved`-scoped `CHECK` and the approval gate are unaffected and
    the honest NULL recording "the shape was undecided" survives.
    """
    result = ingest(
        store,
        payload(rule(statement="", ruleClass="definitional", pattern=None)),
        repo,
        index_path,
    )
    row = one_gr(store)
    assert row["statement"]
    assert row["statement"] == row["statement_extracted"]
    assert "always" in row["statement"]
    assert row["pattern"] is None
    assert row["rule_class"] == "definitional"
    assert result.rules_new == 1

    # A NULL `pattern` and `disposition = 'captured'` insert successfully,
    # which is the CHECK's `state <> 'approved'` scoping doing its job.
    assert row["disposition"] == "captured"
    assert row["state"] == "draft"


# ----------------------------------------------------------------------
# Coverage and the completeness gate
# ----------------------------------------------------------------------


def test_an_unmeasured_run_leaves_not_accounted_for_null_and_complete_zero(
    store, repo, index_path
):
    """Proves NULL means never measured and is not stored as zero.

    Both shapes are covered: `coverage: null`, which is what the workflow
    really produces when `repoRoot` was omitted, no index existed, or the
    coverage command failed; and one carrying `skipped: true`, which the
    workflow normalizes away but the field map must still handle. Store a
    zero for such a run and the arithmetic says the run is complete,
    `complete` goes to 1, and `export` waves through a corpus whose coverage
    nobody ever looked at — the gate passing most confidently in the one case
    it should stop.
    """
    conn = store._connect()

    null_coverage = ingest(
        store, payload(rule(), coverage=None), repo, index_path
    )
    assert null_coverage.not_accounted_for is None
    assert null_coverage.complete is False
    assert null_coverage.coverage_rendering is None

    skipped = ingest(
        store,
        payload(
            rule(name="Second", source="Vendor.java:1-4"),
            coverage={
                "skipped": True,
                "total": 0,
                "claimed": 0,
                "uncovered": 0,
                "pct": 0,
                "uncovered_chunks": [],
            },
        ),
        repo,
        index_path,
    )
    assert skipped.not_accounted_for is None
    assert skipped.complete is False

    for run_id in (null_coverage.run_id, skipped.run_id):
        row = conn.execute(
            "SELECT not_accounted_for, complete, coverage_source FROM gr_run "
            "WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert row["not_accounted_for"] is None
        assert row["complete"] == 0
        assert row["coverage_source"] is None


def test_not_accounted_for_comes_from_the_payload_total_not_the_capped_list(
    store, repo, index_path
):
    """Proves the count is 512 and the list length is rendered as such.

    `uncovered_chunks` is a display list the workflow caps at forty entries,
    so deriving the count from its length silently reports 40 for a corpus
    with 512 unaccounted chunks. This is the assertion that fails the moment
    anyone writes `len(uncovered_chunks)`, and it also pins the rendering —
    *40 of 512 shown* — so a reader is never shown a capped list as a total.
    """
    result = ingest(
        store,
        payload(
            rule(),
            coverage={
                "total": 2048,
                "claimed": 1536,
                "uncovered": 512,
                "pct": 75.0,
                "uncovered_chunks": [
                    {"path": f"f{i}.java", "start_line": 1, "end_line": 2}
                    for i in range(40)
                ],
            },
        ),
        repo,
        index_path,
    )
    assert result.not_accounted_for == 512
    assert result.coverage_rendering == "40 of 512 shown"
    assert result.complete is False
    row = (
        store._connect()
        .execute(
            "SELECT not_accounted_for, complete, final_round_chunk_coverage_pct, "
            "coverage_source FROM gr_run WHERE run_id = ?",
            (result.run_id,),
        )
        .fetchone()
    )
    assert row["not_accounted_for"] == 512
    assert row["complete"] == 0
    assert row["final_round_chunk_coverage_pct"] == 75.0
    assert row["coverage_source"] == "extraction"


def test_a_measured_run_with_nothing_left_over_is_complete(store, repo, index_path):
    """Proves zero and NULL are genuinely different in this column.

    NULL means never measured; zero means measured and nothing left over.
    Without a case asserting the second, a bug that stored NULL for
    everything would pass every other coverage test here.
    """
    result = ingest(store, payload(rule()), repo, index_path)
    assert result.not_accounted_for == 0
    assert result.complete is True
    assert result.coverage_rendering == "0 of 0 shown"
    row = (
        store._connect()
        .execute("SELECT complete FROM gr_run WHERE run_id = ?", (result.run_id,))
        .fetchone()
    )
    assert row["complete"] == 1


def test_run_metadata_and_injection_flags_are_recorded_and_loud(
    store, repo, index_path
):
    """Proves `rounds_run`/`round_cap`/`stop_reason` land where carried.

    Recorded "where the payload carries them", so absence must be normal
    rather than an error. The workflow emits all four as of 2026-09-02, but
    every run ingested before that carries `rounds` alone, so tolerating the
    absence is still load-bearing. `tests/test_gr_run_metadata.py` covers the
    complementary all-four-NULL case.
    `injectionFlags` gets the same loud treatment as the missing-index
    banner, because a prompt-injection suspect nobody reads is worse than
    never having scanned.
    """
    notices: list[str] = []
    result = ingest_extraction(
        store,
        payload(
            rule(),
            rounds=3,
            roundCap=5,
            stopReason="dry",
            newRulesInFinalRound=0,
            injectionFlags=["Order.java:10-20 (rule: Vendor number required)"],
            rejectedRules=[{"name": "rejected one"}],
        ),
        repo,
        index_sqlite_path=index_path,
        on_notice=notices.append,
    )
    row = (
        store._connect()
        .execute(
            "SELECT system, rounds_run, round_cap, stop_reason, "
            "new_rules_in_final_round, injection_flags, rules_in, rules_new, "
            "rules_merged, rules_candidate, rules_rejected FROM gr_run "
            "WHERE run_id = ?",
            (result.run_id,),
        )
        .fetchone()
    )
    assert row["system"] == "demo"
    assert row["rounds_run"] == 3
    assert row["round_cap"] == 5
    assert row["stop_reason"] == "dry"
    assert row["new_rules_in_final_round"] == 0
    assert json.loads(row["injection_flags"]) == [
        "Order.java:10-20 (rule: Vendor number required)"
    ]
    assert row["rules_rejected"] == 1
    # `rules_rejected` sits OUTSIDE the count identity: rejected rules never
    # become `gr` rows, so the four numbers do not sum.
    assert row["rules_in"] == row["rules_new"] + row["rules_merged"] + (
        row["rules_candidate"]
    )
    assert any("PROMPT-INJECTION" in n for n in notices)


def test_run_metadata_absent_from_the_payload_is_stored_as_null(
    store, repo, index_path
):
    """Proves the run-metadata reads tolerate the shape the workflow emits."""
    result = ingest(store, payload(rule()), repo, index_path)
    row = (
        store._connect()
        .execute(
            "SELECT round_cap, stop_reason, new_rules_in_final_round, "
            "injection_flags FROM gr_run WHERE run_id = ?",
            (result.run_id,),
        )
        .fetchone()
    )
    assert row["round_cap"] is None
    assert row["stop_reason"] is None
    assert row["new_rules_in_final_round"] is None
    assert row["injection_flags"] is None


# ----------------------------------------------------------------------
# Completeness of the mapping
# ----------------------------------------------------------------------


def test_every_key_of_an_ingested_rule_object_reaches_a_declared_destination(
    store, repo, index_path
):
    """Proves nothing the extractor produced is silently dropped.

    Step 3's completeness rule is a three-way disjunction: every key of every
    ingested rule object must be mapped to a named column, **or** to a
    child-table row, **or** appear in `gr_fields.UNMAPPED_KEYS` as knowingly
    unpromoted. All three routes are needed and the third column route —
    `ruleClass`/`pattern`, written verbatim *outside* `EXTRACTOR_FIELD_MAP`
    because they are `HUMAN_WRITABLE_FIELDS` — has to be named explicitly or
    this fails on first real data.

    It also asserts the verbatim backstop separately: `extractor_payload`
    holds the whole object, and `gr_scenario` holds the Given/When/Then.
    """
    fixture = rule()
    assert unmapped_rule_keys(fixture) == set()
    assert CHILD_MAPPED_KEYS <= set(fixture)
    assert set(VERBATIM_KEYS) <= set(fixture)
    # `structuredBody`/`structuredBodyType` are the map's only optional pair
    # and are all-or-nothing, so they are absent from a rule with no typed
    # body; `test_a_valid_structured_body_round_trips_and_selects_tier_one`
    # covers them. Everything else in the map is present on every rule.
    assert set(EXTRACTOR_FIELD_MAP) - {"structuredBody", "structuredBodyType"} <= (
        set(fixture)
    )
    assert {"structuredBody", "structuredBodyType"} <= set(EXTRACTOR_FIELD_MAP)

    ingest(store, payload(fixture), repo, index_path)
    row = one_gr(store)
    assert json.loads(row["extractor_payload"]) == fixture
    scenario = store.list_gr_scenarios(row["gr_id"])[0]
    assert (scenario.given, scenario.when, scenario.then, scenario.and_clause) == (
        fixture["given"],
        fixture["when"],
        fixture["then"],
        fixture["and"],
    )
    assert row["implementation_notes"] == fixture["implementationNotes"]


def test_the_mapping_completeness_check_is_not_vacuous(store, repo, index_path):
    """Proves the completeness assertion is testing the declared routes.

    Adding a key to a fixture rule object that is neither mapped nor in
    `UNMAPPED_KEYS` must make it fail. This is the only way to know the test
    above is not vacuous — and a completeness test phrased against
    `extractor_payload` alone *would* be vacuous, because the payload is
    verbatim and so preserves any key whatsoever.
    """
    fixture = rule(brandNewSchemaField="a later RULES_SCHEMA addition")
    assert unmapped_rule_keys(fixture) == {"brandNewSchemaField"}

    # The new key still reaches the lossless backstop, which is why an
    # unaccounted key does not abort a several-hundred-rule ingest.
    ingest(store, payload(fixture), repo, index_path)
    stored = json.loads(one_gr(store)["extractor_payload"])
    assert stored["brandNewSchemaField"] == "a later RULES_SCHEMA addition"


def test_the_field_map_and_ingest_cannot_drift_apart(store, repo, index_path):
    """Proves ingest reads exactly the keys `EXTRACTOR_FIELD_MAP` declares.

    The map is the single source of which columns an incoming key may write,
    and ingest is its only consumer — so a key added to the map and not read
    at the call site would be declared and silently dropped. The guard is in
    the ingest path itself and this asserts it fires.
    """
    from legacylift_search import gr_ingest

    original = dict(gr_ingest.EXTRACTOR_FIELD_MAP)
    gr_ingest.EXTRACTOR_FIELD_MAP["somethingNew"] = ("name",)
    try:
        with pytest.raises(IngestError) as excinfo:
            ingest(store, payload(rule()), repo, index_path)
        assert excinfo.value.field == "EXTRACTOR_FIELD_MAP"
    finally:
        gr_ingest.EXTRACTOR_FIELD_MAP.clear()
        gr_ingest.EXTRACTOR_FIELD_MAP.update(original)


# ----------------------------------------------------------------------
# Measurement
# ----------------------------------------------------------------------


def test_the_intra_run_collapse_count_is_computable_from_the_run_hits(
    store, repo, index_path
):
    """Proves the false-same residue is measurable before anyone trusts a corpus.

    Two rules offered in *one* run can collide: if they cite the same line
    range they share their anchors and the tier-2 discriminator is the span
    hash of exactly those lines, identical for both, so the entire
    discrimination between them is `rule_class` and `pattern`. Stage one
    matches, merges automatically, and stage two never runs because there was
    no miss — so a real rule never enters the corpus and nothing reports it.
    The extractor's own in-run dedupe does not prevent this: it keys on
    `path::lowercased-name`, which collapses same-*name* rules, not
    same-*lines* rules.

    `gr_run_hit.offer_ordinal` makes the residue one query, and **on a first
    ingest into an empty store that figure *is* the intra-run collapse
    rate**, uncontaminated by cross-run merging. It is a count of *offers*,
    because the question is how many mined rules lost their own row.
    """
    twins = payload(
        rule(name="Vendor number present"),
        rule(name="Vendor number populated"),
    )
    result = ingest(store, twins, repo, index_path)

    assert counts(store)["gr"] == 1
    assert counts(store)["gr_run_hit"] == 2
    assert result.rules_in == 2
    assert result.rules_new == 1
    assert result.rules_merged == 1
    assert result.intra_run_collapse == 2
    assert store.intra_run_collapse_count(result.run_id) == 2

    ordinals = (
        store._connect()
        .execute(
            "SELECT offer_ordinal, outcome FROM gr_run_hit WHERE run_id = ? "
            "ORDER BY offer_ordinal",
            (result.run_id,),
        )
        .fetchall()
    )
    assert [(r[0], r[1]) for r in ordinals] == [(0, "new"), (1, "merged")]


def test_rows_inserted_is_new_plus_candidate_and_not_new_alone(
    store, repo, index_path
):
    """Proves `rules_new` is not the number of rows inserted.

    Outcomes are defined so every offered rule produces exactly one
    `gr_run_hit` per run, and a `candidate` outcome **also inserts a row** —
    so `rules_new + rules_candidate` is the insert count. Reading
    `rules_new` as the row count under-reports a corpus every time stage two
    fires.
    """
    ingest(store, payload(rule(source="Order.java:10-20")), repo, index_path)
    result = ingest(
        store,
        payload(
            rule(name="Overlapping", source="Order.java:15-25"),
            rule(name="Elsewhere", source="Vendor.java:40-45"),
        ),
        repo,
        index_path,
    )
    assert result.rules_new == 1
    assert result.rules_candidate == 1
    assert result.rows_inserted == 2
    assert counts(store)["gr"] == 3


# ----------------------------------------------------------------------
# The domain-retag invariant, behaviourally
# ----------------------------------------------------------------------


def test_a_domain_retag_moves_the_subject_and_neither_dedupe_key(
    store, repo, index_path
):
    """Proves no key takes a domain as an input, over a real retag.

    `NORMATIVE SPEC-3` §S3.6's invariant, in its executable form at this
    layer: change a cited file's `file_domains` row, re-ingest, and every
    `dedupe_key`, `dedupe_key_anchor_only` and citation `anchor_key` is
    byte-identical. `subject` is excluded from both keys precisely so
    domain-retag churn stays out of the hash, and it is redundant there
    anyway since `anchor_key` already carries the path.

    **The merge deliberately does not move `subject` either**, and that is
    not an omission: `subject` and `subject_provenance` are
    `STORE_OWNED_FIELDS`, which the merge never writes apart from the four
    bookkeeping columns. Step 8's `rederive-subjects` is the command that
    recomputes them after a retag — a separate act, so that a retag is not
    silently coupled to whether anyone happened to re-run extraction. The
    assertion here is therefore that the retag reached *nothing* in `gr`
    through the merge path, which is the stronger half of the invariant.
    """
    store.upsert_file_domain("Order.java", "ordering", "glob", None, 1.0)
    body = payload(rule())
    ingest(store, body, repo, index_path)

    conn = store._connect()
    before = conn.execute(
        "SELECT gr_id, subject, subject_provenance, dedupe_key, "
        "dedupe_key_anchor_only FROM gr"
    ).fetchone()
    anchors_before = [
        r[0] for r in conn.execute("SELECT anchor_key FROM gr_citation").fetchall()
    ]
    assert before["subject"] == "ordering"
    assert before["subject_provenance"] == "derived"

    store.upsert_file_domain("Order.java", "vendor-master", "glob", None, 1.0)
    ingest(store, body, repo, index_path)

    after = conn.execute(
        "SELECT gr_id, subject, dedupe_key, dedupe_key_anchor_only FROM gr"
    ).fetchone()
    anchors_after = [
        r[0] for r in conn.execute("SELECT anchor_key FROM gr_citation").fetchall()
    ]
    assert counts(store)["gr"] == 1
    assert after["gr_id"] == before["gr_id"]
    assert after["dedupe_key"] == before["dedupe_key"]
    assert after["dedupe_key_anchor_only"] == before["dedupe_key_anchor_only"]
    assert anchors_after == anchors_before
    assert after["subject"] == before["subject"] == "ordering"

    # But the derivation itself follows the retag, so `rederive-subjects` has
    # a different answer to write when it lands: a fresh row over the same
    # citation derives the new domain.
    fresh = ingest(
        store,
        payload(rule(name="Another", source="Order.java:30-35")),
        repo,
        index_path,
    )
    derived = conn.execute(
        "SELECT subject FROM gr WHERE gr_id = ?", (fresh.gr_ids[0],)
    ).fetchone()
    assert derived["subject"] == "vendor-master"


def test_neither_reserved_domain_ever_becomes_a_subject(store, repo, index_path):
    """Proves the two sentinels are not collapsed and never leak into `subject`.

    `unassigned` means nobody has classified the file yet and `tag-domains`
    fixes it, so an all-`unassigned` requirement gets `llm_named` — the
    provenance whose whole meaning is "fixable by re-tagging". `excluded`
    means the file was deliberately declared out of scope and re-tagging
    changes nothing, so an all-`excluded` requirement gets
    `derived_ambiguous`. Routing the unfixable case into the bucket meaning
    "fixable" would quietly depress the one rate a reader is told to check
    before trusting the derivation.
    """
    store.upsert_file_domain("Order.java", "excluded", "glob", None, 1.0)
    result = ingest(
        store,
        payload(
            rule(),
            rule(name="Untagged", source="Vendor.java:5-9"),
        ),
        repo,
        index_path,
    )

    rows = (
        store._connect()
        .execute("SELECT subject, subject_provenance FROM gr ORDER BY gr_id")
        .fetchall()
    )
    provenances = {r["subject_provenance"] for r in rows}
    assert provenances == {"derived_ambiguous", "llm_named"}
    for row in rows:
        assert row["subject"] not in ("excluded", "unassigned")
    assert result.all_excluded_requirements == 1
    assert result.subject_provenance_counts == {
        "derived_ambiguous": 1,
        "llm_named": 1,
    }


def test_the_refresh_pair_runs_once_for_the_whole_run(store, repo, index_path):
    """Proves findings and FTS rows exist after ingest, from one refresh call.

    Ingest calls each half of the refresh pair **once for the whole run** —
    per record would mean several hundred separate validator runs and several
    hundred single-item embed calls. The SQL half runs inside the ingest
    transaction (a `SAVEPOINT`, never a nested `BEGIN`) and the vector half
    after the commit, which is why a rolled-back ingest cannot leave vectors
    behind for rules that never landed.

    `leaked_terms_available` is False here because this repository has no
    index — the difference between "no leaked identifier was found" and
    "leakage was never looked for".
    """
    result = ingest(
        store,
        payload(rule(), rule(name="Second", source="Vendor.java:5-9")),
        repo,
        index_path,
    )
    assert result.refresh is not None
    assert result.refresh.refreshed == 2
    assert result.refresh.leaked_terms_available is False

    conn = store._connect()
    assert conn.execute("SELECT COUNT(*) FROM gr_fts").fetchone()[0] == 2
    hits = store.search_gr_fts("vendor")
    assert len(hits) == 2
