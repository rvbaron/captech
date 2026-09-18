"""Tests for `gr_fields.py` -- the four-way `gr` field-ownership partition.

Milestone 1, Steps 6 / 6a of `docs/exec-plans/active/reqs-to-data-store.md`.
The seven numbered assertions in `## Validation and Acceptance` this file
covers are transcribed into the docstring of each test below rather than
paraphrased in this header, so a stale copy here cannot drift from the
plan the way the sixth review round found in `## Validation and
Acceptance` itself.

Every fixture-mutation test (adding a column, adding a shadow pair) works
against a **real** `KnowledgeStore`-migrated `gr` table in a fresh temporary
directory, then mutates that one connection's schema directly with a raw
`ALTER TABLE`. Nothing here touches `knowledge_store.py`.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from legacylift_search import gr_fields
from legacylift_search.knowledge_store import KnowledgeStore

# The four sets, spot-checked against the plan's own membership table
# (Step 6) so a typo in this file's understanding of the module is caught
# independently of the exhaustiveness test below.
_EXPECTED_EXTRACTOR_OWNED = frozenset(
    {
        "name",
        "as_built",
        "category",
        "priority",
        "confidence_extraction",
        "structured_body",
        "structured_body_type",
        "implementation_notes",
        "parameters",
        "sme_question",
        "suspected_defect",
        "statement_extracted",
        "assumptions_extracted",
        "modality_extracted",
    }
)
_EXPECTED_SHADOWED = frozenset({"statement", "assumptions", "modality"})
_EXPECTED_HUMAN_WRITABLE = frozenset(
    {
        "rule_class",
        "pattern",
        "enforcement_level",
        "confidence_intent",
        "disposition",
        "modality_confirmed",
        "rationale",
        "fit_criterion",
        "owner",
    }
)
_EXPECTED_STORE_OWNED = frozenset(
    {
        "gr_id",
        "kind",
        "state",
        "subject",
        "subject_provenance",
        "derived_from",
        "superseded_by",
        "dedupe_key",
        "dedupe_key_anchor_only",
        "reviewed_by",
        "reviewed_at",
        "review_note",
        "extractor_payload",
        "first_seen_run_id",
        "created_at",
        "updated_at",
    }
)

# Step 6's own writer list for the two `STORE_OWNED_FIELDS` columns nothing
# obvious writes, plus the rest of what `set_state` touches. Kept local to
# this test file (not exported from `gr_fields`) because the reachability
# assertion is the only place in Milestone 1 that needs it named as a set.
_SET_STATE_WRITTEN_FIELDS = frozenset(
    {
        "state",
        "subject",
        "subject_provenance",
        "reviewed_by",
        "reviewed_at",
        "review_note",
        "superseded_by",
    }
)


@pytest.fixture
def store():
    """An open, migrated `KnowledgeStore` in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ks = KnowledgeStore(Path(tmpdir) / "knowledge" / "knowledge.sqlite")
        try:
            yield ks
        finally:
            ks.close()


def _assert_exhaustive_partition(conn: sqlite3.Connection) -> None:
    """Raise `AssertionError` unless the four sets exhaustively partition
    `gr`'s current column list.

    A small local helper rather than something exported from `gr_fields`,
    so that the "does this still pass" question and the "prove it can
    fail" question (test below) share exactly one implementation of the
    property being tested.
    """
    shadowed = gr_fields.get_shadowed_fields(conn)
    sets = (
        gr_fields.EXTRACTOR_OWNED_FIELDS,
        shadowed,
        gr_fields.HUMAN_WRITABLE_FIELDS,
        gr_fields.STORE_OWNED_FIELDS,
    )
    union = frozenset().union(*sets)
    total = sum(len(s) for s in sets)
    assert total == len(union), "the four sets are not pairwise disjoint"
    assert union == gr_fields.get_gr_columns(conn), (
        "the four sets do not exactly cover gr's column list"
    )


class TestExhaustivePartition:
    """Assertion 1: pairwise disjoint, union == gr's columns, and the four
    counts 14/3/9/16 are the only checksum on that partition.
    """

    def test_counts(self):
        assert len(gr_fields.EXTRACTOR_OWNED_FIELDS) == 14
        assert len(_EXPECTED_SHADOWED) == 3
        assert len(gr_fields.HUMAN_WRITABLE_FIELDS) == 9
        assert len(gr_fields.STORE_OWNED_FIELDS) == 16

    def test_membership_matches_the_plans_table(self):
        assert gr_fields.EXTRACTOR_OWNED_FIELDS == _EXPECTED_EXTRACTOR_OWNED
        assert gr_fields.HUMAN_WRITABLE_FIELDS == _EXPECTED_HUMAN_WRITABLE
        assert gr_fields.STORE_OWNED_FIELDS == _EXPECTED_STORE_OWNED

    def test_gr_has_exactly_forty_two_columns(self, store):
        assert len(gr_fields.get_gr_columns(store.conn)) == 42

    def test_pairwise_disjoint_and_union_is_exactly_gr(self, store):
        _assert_exhaustive_partition(store.conn)

    def test_unclassified_column_fails_the_partition(self, store):
        """Assertion 2: a column added to the table fails the test until
        it is classified.

        `some_future_field` is deliberately not in any of the four sets;
        the ALTER TABLE happens on this one connection's schema only and
        never touches `knowledge_store.py`.
        """
        store.conn.execute("ALTER TABLE gr ADD COLUMN some_future_field TEXT")
        with pytest.raises(AssertionError):
            _assert_exhaustive_partition(store.conn)


class TestShadowedFieldsIsDerived:
    """Assertion 3: `SHADOWED_FIELDS` is derived from the schema, not
    declared, so a fixture that adds a shadow pair grows it.
    """

    def test_matches_the_declared_three(self, store):
        assert gr_fields.get_shadowed_fields(store.conn) == _EXPECTED_SHADOWED

    def test_adding_a_shadow_pair_grows_the_set(self, store):
        store.conn.execute("ALTER TABLE gr ADD COLUMN foo TEXT")
        store.conn.execute("ALTER TABLE gr ADD COLUMN foo_extracted TEXT")
        grown = gr_fields.get_shadowed_fields(store.conn)
        assert grown == _EXPECTED_SHADOWED | {"foo"}
        assert len(grown) == 4

    def test_a_lone_extracted_column_with_no_live_pair_does_not_count(self, store):
        # `bar_extracted` alone has no `bar` column, so it must not appear
        # as the *key* half of a shadow pair (it already sits in
        # EXTRACTOR_OWNED_FIELDS by construction once it is classified, but
        # that classification is Step 6's job, not this derivation's).
        store.conn.execute("ALTER TABLE gr ADD COLUMN bar_extracted TEXT")
        grown = gr_fields.get_shadowed_fields(store.conn)
        assert "bar" not in grown
        assert grown == _EXPECTED_SHADOWED


class TestExtractorFieldMap:
    """Assertions 4 and 5: the map's value union equals the 17 owned-plus-
    shadowed columns, the three shadow keys are two-element tuples, and the
    equality is not vacuously true.
    """

    def test_union_equals_owned_plus_shadowed(self, store):
        shadowed = gr_fields.get_shadowed_fields(store.conn)
        mapped = frozenset().union(*gr_fields.EXTRACTOR_FIELD_MAP.values())
        assert mapped == gr_fields.EXTRACTOR_OWNED_FIELDS | shadowed
        assert len(mapped) == 17

    def test_the_three_shadowed_keys_carry_two_element_tuples(self):
        for key in ("statement", "assumptions", "modality"):
            value = gr_fields.EXTRACTOR_FIELD_MAP[key]
            assert isinstance(value, tuple)
            assert len(value) == 2
            assert value[1] == f"{key}_extracted"

    def test_every_other_key_carries_a_one_element_tuple(self):
        for key, value in gr_fields.EXTRACTOR_FIELD_MAP.items():
            if key in ("statement", "assumptions", "modality"):
                continue
            assert len(value) == 1

    def test_the_assertion_is_not_vacuous(self, store):
        """Adding `disposition` to the map must fail the assertion above.

        Without this, assertion 4 could pass on a map that covers
        "everything ingest happens to write" rather than specifically
        `EXTRACTOR_OWNED_FIELDS | SHADOWED_FIELDS` -- `disposition` is
        written by ingest (via `INSERT_ONLY_DEFAULTS`) but must never be
        reachable through the extractor field map, because the merge must
        never touch it (Step 6).
        """
        shadowed = gr_fields.get_shadowed_fields(store.conn)
        tampered = dict(gr_fields.EXTRACTOR_FIELD_MAP)
        tampered["disposition"] = ("disposition",)
        mapped = frozenset().union(*tampered.values())
        assert mapped != gr_fields.EXTRACTOR_OWNED_FIELDS | shadowed


class TestInsertOnlyDefaults:
    """Assertion 6: `INSERT_ONLY_DEFAULTS` is a subset of
    `HUMAN_WRITABLE_FIELDS`.
    """

    def test_keys_are_a_subset_of_human_writable(self):
        assert set(gr_fields.INSERT_ONLY_DEFAULTS) <= gr_fields.HUMAN_WRITABLE_FIELDS

    def test_exact_membership_and_values(self):
        assert gr_fields.INSERT_ONLY_DEFAULTS == {
            "disposition": "captured",
            "modality_confirmed": False,
        }


class TestReachability:
    """Assertion 7: every column in `EXTRACTOR_OWNED_FIELDS |
    SHADOWED_FIELDS | HUMAN_WRITABLE_FIELDS` -- the three *non-store* sets
    -- has at least one writer among the extractor field map, the
    insert-only defaults, `set-field`'s accepted set, or `set_state`.

    This is a different property from membership (assertion 1) and both
    are required: a column can be correctly classified into one of the
    four sets and still have nothing in the system able to write it, which
    membership alone cannot catch.
    """

    def test_every_non_store_column_has_a_writer(self, store):
        shadowed = gr_fields.get_shadowed_fields(store.conn)
        target = gr_fields.EXTRACTOR_OWNED_FIELDS | shadowed | gr_fields.HUMAN_WRITABLE_FIELDS

        writers = frozenset().union(
            *gr_fields.EXTRACTOR_FIELD_MAP.values(),
            gr_fields.INSERT_ONLY_DEFAULTS.keys(),
            gr_fields.set_field_accepted_fields(store.conn),
            _SET_STATE_WRITTEN_FIELDS,
        )

        unreachable = target - writers
        assert not unreachable, f"no writer for: {sorted(unreachable)}"

    def test_the_two_named_store_owned_writers_are_covered_by_set_state(self):
        # Recorded here, not asserted as part of the exhaustive-42 test:
        # `superseded_by` is written by `set_state` on the `-> superseded`
        # transition. `derived_from` has NO writer in Milestone 1 at all --
        # reserved for Milestone 2's rollups, and its permanent emptiness
        # is correct. The reachability assertion above deliberately covers
        # only the three non-store sets and says nothing about either of
        # these two STORE_OWNED_FIELDS columns.
        assert "superseded_by" in _SET_STATE_WRITTEN_FIELDS
        assert "derived_from" not in _SET_STATE_WRITTEN_FIELDS
        assert "derived_from" in gr_fields.STORE_OWNED_FIELDS
