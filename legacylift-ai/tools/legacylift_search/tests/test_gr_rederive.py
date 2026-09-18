"""Tests for Step 8's `rederive-subjects` (`gr_rederive.rederive_subjects`).

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. Every
test here fails before this wave with `No module named
'legacylift_search.gr_rederive'` and passes after.

The command exists because nothing else re-derives a subject after the domain
set changes, **and the staleness is silent**: re-running `tag-domains` with a
changed `domains.json` leaves every subject describing the previous domain
set, which corrupts the `derived` rate in `requirements stats` -- the one
check the plan's Concrete Steps put in front of an implementer.

Two assertions carry the weight:

* **`test_no_key_no_anchor_and_no_statement_moves`** -- the same invariant as
  the domain-retag test one layer up, from the other side. No dedupe key
  takes a domain as input, so a retag plus a rederive must leave both keys,
  every citation anchor and every `statement` byte-identical. The two
  assertions are complements, not duplicates: keys are supposed to hold
  still and subjects are supposed to move.
* **`test_the_citation_grain_is_per_citation_not_per_distinct_file`** -- the
  derivation is a majority over *citations*, so a file cited three times
  votes three times. `citation_paths_for_gr` is DISTINCT-path and exists for
  `leaked_terms`; substituting it here would silently change the arithmetic
  on any requirement citing one file more than once, and every other test in
  this file would still pass.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from legacylift_search.embeddings import HashEmbedder
from legacylift_search.gr_rederive import rederive_subjects
from legacylift_search.gr_subject import DOMAIN_EXCLUDED, DOMAIN_UNASSIGNED
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import GRCitation
from tests.test_gr_state import insert_gr

_IS_WINDOWS = sys.platform == "win32"

#: A statement whose `[Subject]` span is locatable under `B-UNCOND`, so the
#: fallback branch has something to find. Verified by probe:
#: `derive_subject([], STATEMENT, "behavioral", "B-UNCOND").subject` is
#: `"The Order Service"`.
_STATEMENT = "The Order Service must record a vendor number on each order."
_FALLBACK_SUBJECT = "The Order Service"


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(tmp_root):
    ks = KnowledgeStore(tmp_root / "knowledge" / "knowledge.sqlite")
    try:
        yield ks
    finally:
        ks.close()


def _gr(store, n: int = 1, **overrides) -> str:
    row = {
        "statement": _STATEMENT,
        "statement_extracted": _STATEMENT,
        "rule_class": "behavioral",
        "pattern": "B-UNCOND",
    }
    row.update(overrides)
    return insert_gr(store._connect(), gr_id=f"GR-01HQ2X{n:022d}", **row)


def _cite(store, gr_id: str, path: str, start: int = 1, end: int = 2) -> None:
    store.upsert_gr_citation(
        GRCitation(
            gr_id=gr_id,
            anchor_key=f"java::method::{path}::{start}",
            anchor_resolution="symbol",
            relative_path=path,
            start_line=start,
            end_line=end,
            content_hash="ch1:0000000000000000",
            provenance="extracted",
        )
    )


def _tag(store, path: str, domain: str) -> None:
    store.upsert_file_domain(path, domain, "glob", None, 1.0)


# --------------------------------------------------------------------------
# The transition this command exists for
# --------------------------------------------------------------------------


def test_a_newly_tagged_file_moves_llm_named_to_derived(store):
    """Proves the case the finding behind this command exposed.

    A file that was `unassigned` at ingest and has since been tagged should
    stop being model-named. Without this command it never does, and the
    `derived` rate in `stats` stays wrong with nothing reporting it.
    """
    gr_id = _gr(store, subject=_FALLBACK_SUBJECT, subject_provenance="llm_named")
    _cite(store, gr_id, "src/orders/OrderService.java")
    _cite(store, gr_id, "src/orders/OrderRepo.java", 5, 9)
    store.commit()

    # Before the retag: nothing tagged, so the derivation still yields
    # llm_named and the run is a no-op.
    first = rederive_subjects(store)
    assert first.changed == 0 and first.skipped == 1

    _tag(store, "src/orders/OrderService.java", "orders")
    _tag(store, "src/orders/OrderRepo.java", "orders")

    result = rederive_subjects(store)
    assert result.changed == 1
    assert result.llm_named_to_derived == 1
    assert result.derived_to_derived_ambiguous == 0
    record = store.get_gr(gr_id)
    assert record.subject == "orders"
    assert record.subject_provenance == "derived"


def test_a_newly_excluded_file_moves_derived_to_derived_ambiguous(store):
    """Proves the reverse direction is reported as its own figure.

    It means the corpus now holds rules mined from code the analyst has since
    declared out of scope. Since the Concrete Steps say to check the
    `derived` rate before believing the derivation works at all, a rate that
    can only fall as a corpus ages would quietly undermine that check -- so
    the fall has to be attributed rather than merely observed.
    """
    gr_id = _gr(store, subject="orders", subject_provenance="derived")
    _cite(store, gr_id, "src/orders/OrderService.java")
    _tag(store, "src/orders/OrderService.java", "orders")
    store.commit()
    assert rederive_subjects(store).changed == 0

    _tag(store, "src/orders/OrderService.java", DOMAIN_EXCLUDED)
    result = rederive_subjects(store)
    assert result.changed == 1
    assert result.derived_to_derived_ambiguous == 1
    assert result.llm_named_to_derived == 0
    record = store.get_gr(gr_id)
    assert record.subject_provenance == "derived_ambiguous"
    assert record.subject not in (DOMAIN_EXCLUDED, DOMAIN_UNASSIGNED), (
        "neither reserved sentinel may ever become a subject"
    )


def test_both_directions_are_reported_from_one_run(store):
    """Proves the two figures are independent counts, not one net number.

    A run in which one requirement improves and another degrades must report
    1 and 1, not 0 -- the two facts have different owners and different
    remedies.
    """
    up = _gr(store, 1, subject=_FALLBACK_SUBJECT, subject_provenance="llm_named")
    _cite(store, up, "src/orders/A.java")
    down = _gr(store, 2, subject="billing", subject_provenance="derived")
    _cite(store, down, "src/billing/B.java")
    _tag(store, "src/billing/B.java", "billing")
    store.commit()
    rederive_subjects(store)

    _tag(store, "src/orders/A.java", "orders")
    _tag(store, "src/billing/B.java", DOMAIN_EXCLUDED)
    result = rederive_subjects(store)
    assert result.llm_named_to_derived == 1
    assert result.derived_to_derived_ambiguous == 1
    assert result.changed == 2
    assert result.provenance_transitions == {
        ("llm_named", "derived"): 1,
        ("derived", "derived_ambiguous"): 1,
    }


def test_the_two_sentinels_are_not_collapsed(store):
    """Proves Step 3's two-sentinel rule survives a rederive.

    `unassigned` means nobody has classified the file and `tag-domains` fixes
    it, so an all-`unassigned` requirement gets `llm_named` -- the provenance
    whose whole meaning is "fixable by re-tagging". `excluded` means the file
    was deliberately declared out of scope and re-tagging changes nothing, so
    an all-`excluded` requirement gets `derived_ambiguous`. Routing the
    unfixable case into the bucket that means "fixable" would depress the one
    rate the plan says to read.
    """
    unassigned = _gr(store, 1)
    _cite(store, unassigned, "src/never/tagged.java")
    excluded = _gr(store, 2)
    _cite(store, excluded, "src/legacy/old.java")
    _tag(store, "src/legacy/old.java", DOMAIN_EXCLUDED)
    store.commit()

    rederive_subjects(store)
    assert store.get_gr(unassigned).subject_provenance == "llm_named"
    assert store.get_gr(excluded).subject_provenance == "derived_ambiguous"


def test_a_sentinel_leaves_the_denominator_not_just_the_candidate_set(store):
    """Proves one excluded citation among two real ones still derives.

    The sentinel leaves the count entirely rather than merely losing the
    vote, so two `orders` citations out of three entries is still a strict
    majority of the two that count.
    """
    gr_id = _gr(store)
    _cite(store, gr_id, "src/legacy/old.java")
    _cite(store, gr_id, "src/orders/A.java", 5, 9)
    _cite(store, gr_id, "src/orders/B.java", 11, 14)
    _tag(store, "src/legacy/old.java", DOMAIN_EXCLUDED)
    _tag(store, "src/orders/A.java", "orders")
    _tag(store, "src/orders/B.java", "orders")
    store.commit()

    rederive_subjects(store)
    assert store.get_gr(gr_id).subject == "orders"
    assert store.get_gr(gr_id).subject_provenance == "derived"


def test_the_citation_grain_is_per_citation_not_per_distinct_file(store):
    """Proves a file cited three times votes three times.

    `gr_citation` is one-to-many and Step 3's majority is a majority over
    *citations*. Using `citation_paths_for_gr` -- which is DISTINCT-path and
    exists for `leaked_terms` -- would make this a 1-vs-1 tie with no
    majority and land the record on the fallback branch, and every other test
    in this file would still pass.
    """
    gr_id = _gr(store)
    for start in (10, 20, 30):
        _cite(store, gr_id, "src/orders/Big.java", start, start + 4)
    _cite(store, gr_id, "src/billing/One.java", 1, 2)
    _tag(store, "src/orders/Big.java", "orders")
    _tag(store, "src/billing/One.java", "billing")
    store.commit()

    # Per citation: 3 orders vs 1 billing -> a strict majority for orders.
    # Per distinct file: 1 vs 1 -> no majority, so the fallback branch and a
    # `derived_ambiguous` provenance instead.
    rederive_subjects(store)
    record = store.get_gr(gr_id)
    assert record.subject == "orders"
    assert record.subject_provenance == "derived"
    assert len(store.list_gr_citations(gr_id)) == 4
    assert len(store.citation_paths_for_gr(gr_id)) == 2, (
        "the DISTINCT reader really would give a different answer here"
    )


# --------------------------------------------------------------------------
# What must not move
# --------------------------------------------------------------------------


def test_no_key_no_anchor_and_no_statement_moves(store):
    """Proves the invariant: keys, anchors and statements are byte-identical.

    No dedupe key takes a domain as input, which is the whole point of how
    they are computed -- so a retag followed by a rederive must leave both
    keys, every `anchor_key` and every `statement` exactly as they were,
    while the subject columns move. The complement of the domain-retag test
    one layer up.

    `statement` in particular: an earlier version of this plan had this
    command re-template the statement, which was correct while ingest built
    statements from a S1.4 template. Step 6a no longer does that, so there is
    no template to re-fill and no mechanical way to substitute a new subject
    into someone else's sentence.
    """
    gr_id = _gr(store, subject=_FALLBACK_SUBJECT, subject_provenance="llm_named")
    _cite(store, gr_id, "src/orders/A.java")
    _cite(store, gr_id, "src/orders/B.java", 5, 9)
    store.commit()

    before = store.get_gr(gr_id)
    anchors_before = [
        (c.relative_path, c.start_line, c.end_line, c.anchor_key, c.content_hash)
        for c in store.list_gr_citations(gr_id)
    ]

    _tag(store, "src/orders/A.java", "orders")
    _tag(store, "src/orders/B.java", "orders")
    result = rederive_subjects(store)
    assert result.changed == 1

    after = store.get_gr(gr_id)
    assert after.dedupe_key == before.dedupe_key
    assert after.dedupe_key_anchor_only == before.dedupe_key_anchor_only
    assert after.statement == before.statement
    assert after.statement_extracted == before.statement_extracted
    assert [
        (c.relative_path, c.start_line, c.end_line, c.anchor_key, c.content_hash)
        for c in store.list_gr_citations(gr_id)
    ] == anchors_before
    # The subject columns are the surface that IS supposed to move.
    assert after.subject != before.subject


def test_the_columns_it_writes_are_exactly_three(store):
    """Proves no other column drifts, compared field by field.

    Cheaper than a schema assertion and stronger than reading the update
    dict: everything but `subject`, `subject_provenance` and `updated_at`
    must come back identical.
    """
    gr_id = _gr(store, subject=None, subject_provenance=None)
    _cite(store, gr_id, "src/orders/A.java")
    _tag(store, "src/orders/A.java", "orders")
    store.commit()

    before = store.get_gr(gr_id).model_dump()
    rederive_subjects(store)
    after = store.get_gr(gr_id).model_dump()
    moved = {k for k in before if before[k] != after[k]}
    assert moved == {"subject", "subject_provenance", "updated_at"}


def test_gr_rederive_does_not_import_the_key_producer():
    """Proves the no-key rule structurally, by `ast` rather than by text.

    A text grep trips on this module's own docstring, which describes the
    rule -- the absent-versus-real rule applied to source code, which cost
    three assertions in Wave B.
    """
    import ast

    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legacylift_search"
        / "gr_rederive.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(f"{node.module or ''}.{a.name}" for a in node.names)
    assert not any("gr_keys" in n for n in names), sorted(names)
    # It also must not reach for `citation_paths_for_gr`, the DISTINCT reader.
    calls = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    assert "citation_paths_for_gr" not in calls
    assert "list_gr_citations" in calls


def test_it_calls_the_one_shipped_derivation(store):
    """Proves one implementation, two callers -- not a second copy of the rule.

    Patching `gr_subject.derive_subject` as this module resolved it must
    change what the command produces; if it does not, the majority rule has
    been reimplemented here.
    """
    from legacylift_search import gr_rederive

    gr_id = _gr(store)
    _cite(store, gr_id, "src/orders/A.java")
    _tag(store, "src/orders/A.java", "orders")
    store.commit()

    from legacylift_search.gr_subject import SubjectDerivation

    original = gr_rederive.derive_subject
    try:
        gr_rederive.derive_subject = lambda *a, **k: SubjectDerivation(
            subject="SENTINEL", subject_provenance="derived"
        )
        rederive_subjects(store)
    finally:
        gr_rederive.derive_subject = original
    assert store.get_gr(gr_id).subject == "SENTINEL"


# --------------------------------------------------------------------------
# The resumable-repair shape
# --------------------------------------------------------------------------


def test_it_processes_only_what_is_stale_and_is_safe_to_run_twice(store):
    """Proves the repair-command shape: only the stale rows are written.

    A second run finds every derivation current, writes nothing, and reports
    every row under `skipped`. Reporting `skipped` is what makes
    "0 changed, 3 skipped" a positive confirmation rather than an ambiguous
    silence.
    """
    for n in (1, 2, 3):
        gr_id = _gr(store, n)
        _cite(store, gr_id, f"src/orders/F{n}.java")
        _tag(store, f"src/orders/F{n}.java", "orders")
    store.commit()

    first = rederive_subjects(store)
    assert (first.examined, first.changed, first.skipped) == (3, 3, 0)

    stamps = {r.gr_id: r.updated_at for r in store.query_gr()}
    second = rederive_subjects(store)
    assert (second.examined, second.changed, second.skipped) == (3, 0, 3)
    assert second.refresh.refreshed == 0, "a no-op run refreshes nothing"
    assert second.embed.embedded == 0
    assert {r.gr_id: r.updated_at for r in store.query_gr()} == stamps


def test_a_subset_and_an_unknown_id_are_both_handled(store):
    """Proves `gr_ids` scopes the run, and an absent id is skipped silently."""
    a = _gr(store, 1)
    b = _gr(store, 2)
    for gr_id, n in ((a, 1), (b, 2)):
        _cite(store, gr_id, f"src/orders/F{n}.java")
        _tag(store, f"src/orders/F{n}.java", "orders")
    store.commit()

    result = rederive_subjects(store, [a, "GR-does-not-exist"])
    assert result.examined == 1 and result.changed == 1
    assert store.get_gr(a).subject == "orders"
    assert store.get_gr(b).subject is None, "b was out of scope"


def test_an_empty_store_is_a_clean_no_op(store):
    """Proves the command reports zeroes rather than failing on nothing."""
    result = rederive_subjects(store)
    assert (result.examined, result.changed, result.skipped) == (0, 0, 0)
    assert result.embed.reason is None


def test_a_subject_only_change_is_attributed_rather_than_unexplained(store):
    """Proves a renamed domain does not land in `changed` with no transition.

    The provenance stays `derived` while the subject text moves, which is
    what a retag that renamed a domain produces. Without its own figure those
    rows appear in `changed` and in no transition bucket, which reads like a
    bookkeeping error.
    """
    gr_id = _gr(store, subject="orders", subject_provenance="derived")
    _cite(store, gr_id, "src/orders/A.java")
    _tag(store, "src/orders/A.java", "order-management")
    store.commit()

    result = rederive_subjects(store)
    assert result.changed == 1
    assert result.subject_only_changes == 1
    assert result.provenance_transitions == {}
    assert store.get_gr(gr_id).subject == "order-management"


def test_the_refresh_pair_runs_for_the_touched_rows_only(store):
    """Proves `subject` reaches `gr_statements`, and only for changed rows.

    `subject` is vector metadata, so a changed subject must reach the
    collection or a subject-filtered semantic search reads the old value.
    """
    from legacylift_search.gr_refresh import open_gr_collection

    moved = _gr(store, 1, subject=_FALLBACK_SUBJECT, subject_provenance="llm_named")
    _cite(store, moved, "src/orders/A.java")
    # Already current: no citations, so the fallback branch yields exactly
    # this pair -- the row is not stale and must not be touched.
    still = _gr(
        store, 2, subject=_FALLBACK_SUBJECT, subject_provenance="derived_ambiguous"
    )
    store.commit()
    _tag(store, "src/orders/A.java", "orders")

    result = rederive_subjects(store, embedder=HashEmbedder(dimension=64))
    assert result.changed == 1
    assert result.refresh.refreshed == 1, "one row, not the whole corpus"
    assert result.embed.embedded == 1

    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        got = collection.collection.get(ids=[moved], include=["metadatas"])
        assert got["metadatas"][0]["subject"] == "orders"
        # The untouched row was never embedded, which is the "only what is
        # stale" half seen from the vector side.
        assert collection.collection.get(ids=[still], include=[])["ids"] == []
    finally:
        collection.close()


def test_the_vector_half_may_degrade_and_the_subjects_still_land(store):
    """Proves `embedder=None` is a degraded success here too."""
    gr_id = _gr(store)
    _cite(store, gr_id, "src/orders/A.java")
    _tag(store, "src/orders/A.java", "orders")
    store.commit()

    result = rederive_subjects(store, embedder=None)
    assert result.changed == 1
    assert store.get_gr(gr_id).subject == "orders"
    assert result.embed.reason is not None
    assert "reindex-vectors" in result.embed.reason
