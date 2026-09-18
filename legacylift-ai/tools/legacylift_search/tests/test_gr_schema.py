"""Tests for the GR tables (Milestone 1, Step 3 of `reqs-to-data-store.md`).

Every test here fails before Step 3 (`no such table: gr`) and passes after.

What this file is for, stated plainly because it shapes what belongs in it:
Step 3 is the step that **converts this plan's column list from prose into a
table `PRAGMA table_info` can read**. So these tests assert the schema's own
guarantees — the constraints that make a later step's mechanism work — rather
than any behaviour, because the writers do not exist yet (ingest is Step 6, the
validator Step 4, the CLI Step 8). Each constraint tested below is one a
specific later step depends on, and the docstring names it.

Deliberately NOT asserted here: the four-way ownership partition over `gr`'s
forty-two columns. That belongs to Step 6, which declares the four constants;
Step 3's job is to make the assertion possible at all, and
`test_gr_has_exactly_forty_two_columns` is the part of it that is checkable now.

Two mechanics to know before adding a test to this file. **`KnowledgeStore` sets
`row_factory = sqlite3.Row`**, so `cursor.fetchone() == (1, "x")` is always
false however right the query is — compare element by element. And **four
column names are SQLite keywords** and must be quoted in every statement, not
only in the DDL: `gr_scenario."given"`, `."when"`, `."then"`, and
`gr_dataflow."column"`.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from legacylift_search.knowledge_store import KnowledgeStore

GR_TABLES = (
    "gr",
    "gr_citation",
    "gr_citation_anchor",
    "gr_scenario",
    "gr_edge_case",
    "gr_finding",
    "gr_dataflow",
    "gr_merge_candidate",
    "gr_run",
    "gr_run_hit",
    "gr_import",
)

# A minimal `gr` row: every NOT NULL column and nothing else. Kept as one
# helper so that a later NOT NULL addition breaks in one place rather than in
# every test in this file.
_MINIMAL_GR = {
    "gr_id": "GR-01HQ2X0000000000000000000",
    "kind": "business_rule",
    "statement": "The Order Service must record a vendor number on every order.",
    "statement_extracted": (
        "The Order Service must record a vendor number on every order."
    ),
    "modality": "requirement",
    "modality_extracted": "requirement",
    "dedupe_key": "dk1:0000000000000000",
    "dedupe_key_anchor_only": "dka1:0000000000000000",
    "extractor_payload": "{}",
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": "2026-09-01T00:00:00Z",
}


@pytest.fixture
def store():
    """An open, migrated KnowledgeStore in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ks = KnowledgeStore(Path(tmpdir) / "knowledge" / "knowledge.sqlite")
        try:
            yield ks
        finally:
            ks.close()


def insert_gr(conn: sqlite3.Connection, **overrides) -> str:
    """Insert a `gr` row, overriding or adding columns as given.

    Args:
        conn: The store's connection.
        **overrides: Column values layered over `_MINIMAL_GR`.

    Returns:
        The inserted row's `gr_id`.
    """
    row = {**_MINIMAL_GR, **overrides}
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT INTO gr ({columns}) VALUES ({placeholders})", tuple(row.values())
    )
    return row["gr_id"]


def insert_citation(conn: sqlite3.Connection, gr_id: str, **overrides) -> int:
    """Insert a `gr_citation` row and return its `citation_id`."""
    row = {
        "gr_id": gr_id,
        "anchor_key": "ak1:1111111111111111",
        "anchor_resolution": "symbol",
        "relative_path": "src/Order.java",
        "start_line": 10,
        "end_line": 20,
        "provenance": "extracted",
        **overrides,
    }
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    cursor = conn.execute(
        f"INSERT INTO gr_citation ({columns}) VALUES ({placeholders})",
        tuple(row.values()),
    )
    return int(cursor.lastrowid)


# ----------------------------------------------------------------------
# Shape
# ----------------------------------------------------------------------


def test_all_eleven_gr_tables_exist(store):
    """All eleven tables Step 3 names exist after construction.

    Proves the Progress line's list is what actually landed. Fails before
    Step 3 (none of them exist) and passes after.
    """
    names = {
        row[0]
        for row in store._connect().execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert set(GR_TABLES) <= names


def test_gr_has_exactly_forty_two_columns(store):
    """`gr` carries exactly the forty-two columns Step 3 enumerates.

    The count is load-bearing rather than incidental: Step 6's four-way
    ownership partition (14/3/9/16) is asserted against this column list, so a
    column added without being classified is what that exhaustiveness test
    exists to catch. This test is the half of it that is checkable in Step 3,
    and it is why the DDL is the thing that ends the field-ownership churn —
    the column list stops being prose.
    """
    expected = {
        # extractor-owned (14)
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
        # shadowed (3)
        "statement",
        "assumptions",
        "modality",
        # human-writable (9)
        "rule_class",
        "pattern",
        "enforcement_level",
        "confidence_intent",
        "disposition",
        "modality_confirmed",
        "rationale",
        "fit_criterion",
        "owner",
        # store-owned (16)
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
    actual = {
        row[1] for row in store._connect().execute("PRAGMA table_info('gr')")
    }
    assert actual == expected
    assert len(actual) == 42


def test_three_shadowed_columns_are_derivable_from_the_schema(store):
    """`SHADOWED_FIELDS` is derivable from `gr`'s own column list.

    Step 6 requires `SHADOWED_FIELDS` to be *derived* rather than declared —
    `{c for c in columns if c + "_extracted" in columns}` — so it cannot drift
    from the shadow columns it describes. That derivation is only possible if
    the DDL actually carries the three pairs, which is what this asserts, and
    it is the concrete sense in which Step 3 makes a Step 6 assertion
    executable.
    """
    columns = {
        row[1] for row in store._connect().execute("PRAGMA table_info('gr')")
    }
    derived = {c for c in columns if c + "_extracted" in columns}
    assert derived == {"statement", "assumptions", "modality"}


def test_gr_tables_appear_on_an_existing_populated_database(store):
    """An existing `knowledge.sqlite` gains the GR tables, keeping its rows.

    This is the upgrade path, and it is why Step 3 needs no
    `KNOWLEDGE_MIGRATIONS` entry: `migrate()` runs from `__init__` on every
    open and uses `CREATE TABLE IF NOT EXISTS`, so a database that predates
    Step 3 gains the eleven tables the next time anything touches it, with no
    version bump and no data loss. Simulated by dropping them from a store
    that also holds a domain row, then reopening.
    """
    path = store.sqlite_path
    store.upsert_domain("orders", "Orders", None, ["src/orders/**"], None, 0)
    conn = store._connect()
    for table in GR_TABLES:
        conn.execute(f"DROP TABLE {table}")
    conn.commit()
    store.close()

    reopened = KnowledgeStore(path)
    try:
        names = {
            row[0]
            for row in reopened._connect().execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert set(GR_TABLES) <= names
        assert [d.domain_id for d in reopened.list_domains()] == ["orders"]
    finally:
        reopened.close()


# ----------------------------------------------------------------------
# `gr` constraints
# ----------------------------------------------------------------------


def test_draft_row_with_null_pattern_and_captured_disposition_inserts(store):
    """A `draft` row with NULL `pattern` and `disposition='captured'` inserts.

    This is the acceptance criterion that proves the `approved`-scoped CHECK
    and Step 6a's ingest defaults do not contradict each other. Step 6a
    defaults `disposition` to `captured` for every confirmed rule *and* leaves
    `pattern` NULL where the G/W/T shape is ambiguous — under an unscoped
    `pattern IS NOT NULL` constraint that INSERT raises, the rule never lands,
    and "nothing gates `draft`" becomes false on exactly the bad extractions
    where it matters most.
    """
    conn = store._connect()
    insert_gr(conn, disposition="captured", pattern=None, rule_class=None)
    assert conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0] == 1


def test_approved_row_with_null_pattern_is_refused(store):
    """The `approved`-scoped CHECK still keeps a NULL `pattern` out of approval.

    Defence in depth behind `set_state`'s gate: a caller that bypasses the
    gate still cannot write an approved row with no `pattern`. The gate must
    fire first, because a raw CHECK failure names no finding — but the CHECK
    is what makes the invariant structural.
    """
    conn = store._connect()
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, state="approved", pattern=None, disposition="captured")


def test_approved_non_rule_disposition_escapes_the_pattern_requirement(store):
    """An approved *non-rule* may carry a NULL `pattern`.

    SPEC-1 S1.4's constraint is conditional on the `disposition` making the GR
    a rule, and `V-KW-06` explicitly routes an advice statement to a non-rule
    disposition and says not to store it "as a GR with a `pattern`". A flat
    NOT NULL would make those rows unstorable.
    """
    conn = store._connect()
    insert_gr(conn, state="approved", pattern=None, disposition="not_applicable")
    assert conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0] == 1


@pytest.mark.parametrize(
    ("rule_class", "pattern"),
    [
        ("behavioral", "D-NEC"),
        ("definitional", "B-COND"),
    ],
)
def test_rule_class_pattern_partition_is_enforced(store, rule_class, pattern):
    """A `pattern` from the wrong partition is refused (SPEC-1 S1.7 item 2).

    `behavioral` takes `B-*` and `definitional` takes `D-*`. This is the
    schema half of `V-KW-02`, whose worked example (S1.10 #6, *"An order
    always must have a customer"*) is called the single most likely LLM
    output.
    """
    conn = store._connect()
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, rule_class=rule_class, pattern=pattern)


def test_partition_check_tolerates_either_side_being_null(store):
    """Both halves of the partition tie may be NULL on a `draft` row.

    Written to tolerate NULLs deliberately rather than relying on comparisons
    against NULL evaluating to unknown, because a `draft` row legitimately has
    neither value yet and nothing may gate `draft`.
    """
    conn = store._connect()
    insert_gr(conn, gr_id="GR-A", rule_class="behavioral", pattern=None)
    insert_gr(conn, gr_id="GR-B", rule_class=None, pattern="D-CONST")
    assert conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0] == 2


def test_pattern_enum_is_the_ten_spec_values(store):
    """`pattern` admits exactly SPEC-1 S1.4's ten values and nothing else.

    The enum is closed because `V-KW-02` and `V-SLOT-03` test against it and
    both dedupe keys hash it — an invented eleventh value would key rules that
    no later run can match.
    """
    conn = store._connect()
    ten = [
        ("behavioral", "B-COND"),
        ("behavioral", "B-UNCOND"),
        ("behavioral", "B-PROHIB"),
        ("behavioral", "B-RESTRICT"),
        ("definitional", "D-NEC"),
        ("definitional", "D-IMPOSS"),
        ("definitional", "D-RESTRICT"),
        ("definitional", "D-COMPUTE"),
        ("definitional", "D-INFER"),
        ("definitional", "D-CONST"),
    ]
    for ordinal, (rule_class, pattern) in enumerate(ten):
        insert_gr(
            conn, gr_id=f"GR-{ordinal}", rule_class=rule_class, pattern=pattern
        )
    assert conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0] == 10

    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, gr_id="GR-X", rule_class="behavioral", pattern="B-MADE-UP")


def test_enforcement_level_is_refused_on_a_definitional_rule(store):
    """`enforcement_level` must be NULL when `rule_class` is `definitional`.

    SPEC-1 S1.7 item 3. A definitional rule cannot be "suggested but not
    enforced" because it cannot be violated at all.
    """
    conn = store._connect()
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(
            conn,
            rule_class="definitional",
            pattern="D-NEC",
            enforcement_level="strict",
        )


def test_enforcement_level_is_allowed_while_rule_class_is_still_null(store):
    """A `draft` row with NULL `rule_class` may carry an `enforcement_level`.

    This is why the constraint is phrased against `definitional` rather than
    as "only when behavioral": the two differ for exactly this row, and the
    SPEC form is the one that lets it exist. `V-ENF-01` catches the real
    conflict at validation time.
    """
    conn = store._connect()
    insert_gr(conn, rule_class=None, enforcement_level="guideline")
    assert (
        conn.execute("SELECT enforcement_level FROM gr").fetchone()[0] == "guideline"
    )


def test_six_enforcement_levels_are_admitted(store):
    """The six SBVR-derived `enforcement_level` values are the closed set.

    Cited as an example set given by SBVR and derived from BMM, never as a
    normative SBVR enum — the attribution constraint is mandatory in any
    client-facing deliverable.
    """
    conn = store._connect()
    for ordinal, level in enumerate(
        (
            "strict",
            "deferred",
            "pre-authorized",
            "post-justified",
            "override",
            "guideline",
        )
    ):
        insert_gr(
            conn, gr_id=f"GR-{ordinal}", rule_class="behavioral", enforcement_level=level
        )
    assert conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0] == 6
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, gr_id="GR-X", enforcement_level="advisory")


@pytest.mark.parametrize(
    "column",
    ["statement", "statement_extracted", "modality", "modality_extracted"],
)
def test_shadowed_not_null_columns_reject_null(store, column):
    """`statement`/`modality` and their shadows are NOT NULL, deliberately.

    Not a free choice: the merge's edited-test is `live IS shadow`, and if a
    NULL were possible the natural `=` spelling would yield NULL rather than
    true, so every value-less row would read as human-edited and the merge
    would stop updating it — silently and permanently. `assumptions` is the
    nullable exception, which is exactly why the shared helper must use `IS`.
    """
    conn = store._connect()
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, **{column: None})


def test_assumptions_and_its_shadow_are_nullable(store):
    """`assumptions` and `assumptions_extracted` are nullable on purpose.

    Assumptions are genuinely absent on many rules, so the absent value must
    be encodable. This is the row that turns a `=`-spelled edited-test into a
    permanent no-update bug, and Step 6's shared `IS` helper is the fix.
    """
    conn = store._connect()
    insert_gr(conn, assumptions=None, assumptions_extracted=None)
    assert conn.execute(
        "SELECT COUNT(*) FROM gr WHERE assumptions IS assumptions_extracted"
    ).fetchone()[0] == 1


def test_subject_is_nullable_and_provenance_is_a_closed_three_value_set(store):
    """`subject` may be NULL, and `subject_provenance` takes three values.

    NULL `subject` means "no `[Subject]` slot could be located" — the
    absent-versus-real rule — and `stats` counts those NULLs as their own
    figure rather than folding them into `llm_named`. The third provenance
    value exists because `derived_ambiguous` and `llm_named` are different
    failures and only one of them is fixable by re-running `tag-domains`.
    """
    conn = store._connect()
    insert_gr(conn, subject=None, subject_provenance="derived_ambiguous")
    for ordinal, provenance in enumerate(("derived", "llm_named")):
        insert_gr(conn, gr_id=f"GR-{ordinal}", subject="order", subject_provenance=provenance)
    assert conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0] == 3
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, gr_id="GR-X", subject_provenance="guessed")


def test_five_lifecycle_states_and_nothing_else(store):
    """`state` is the closed five-value lifecycle, defaulting to `draft`."""
    conn = store._connect()
    for ordinal, state in enumerate(
        ("draft", "reviewed", "rejected", "superseded")
    ):
        insert_gr(conn, gr_id=f"GR-{ordinal}", state=state)
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, gr_id="GR-X", state="in_review")

    insert_gr(conn, gr_id="GR-DEFAULT")
    assert (
        conn.execute("SELECT state FROM gr WHERE gr_id = 'GR-DEFAULT'").fetchone()[0]
        == "draft"
    )


def test_dispositions_are_the_four_rule_scoped_values(store):
    """`gr.disposition` takes four values; `not_accounted_for` is not one.

    The design draft's five-value set mixes two scopes: the first four
    describe a rule the extractor actually found, while `not_accounted_for`
    describes *code* it could not account for, which has no `gr` row to sit on.
    It lives on `gr_run` as a count instead.
    """
    conn = store._connect()
    for ordinal, disposition in enumerate(
        ("captured", "not_applicable", "unreachable", "delegated")
    ):
        insert_gr(conn, gr_id=f"GR-{ordinal}", disposition=disposition)
    assert conn.execute("SELECT COUNT(*) FROM gr").fetchone()[0] == 4
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, gr_id="GR-X", disposition="not_accounted_for")


def test_both_dedupe_keys_and_the_payload_are_not_null(store):
    """Both dedupe keys and `extractor_payload` are NOT NULL.

    A NULL key is not a nullable column here, it is an ambiguity: the merge
    matches on equality, and NULL is not equal to itself, so a keyless row
    could never merge and nothing would say so. `extractor_payload` is the
    lossless backstop that makes "nothing the extractor produced is silently
    dropped" testable, so an insert without it is a defect rather than a
    variant.
    """
    conn = store._connect()
    for column in ("dedupe_key", "dedupe_key_anchor_only", "extractor_payload"):
        with pytest.raises(sqlite3.IntegrityError):
            insert_gr(conn, **{column: None})


def test_surrogate_identity_columns_refuse_null(store):
    """`gr.gr_id` and `gr_run.run_id` reject NULL, which `PRIMARY KEY` alone does not.

    A SQLite rowid table lets a PRIMARY KEY column that is not
    `INTEGER PRIMARY KEY` hold NULL, and the unique index treats NULLs as
    distinct — so `TEXT PRIMARY KEY` on its own accepts *two* keyless rows in
    the column this plan calls the immutable surrogate identity. Fails against
    the DDL as first written and passes with the explicit `NOT NULL`, which is
    why the redundant-looking clause is there.
    """
    conn = store._connect()
    with pytest.raises(sqlite3.IntegrityError):
        insert_gr(conn, gr_id=None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO gr_run (run_id, system) VALUES (NULL, 'x')")


def test_superseded_by_self_reference_is_cleared_when_its_target_goes(store):
    """`superseded_by` is a self-reference with ON DELETE SET NULL."""
    conn = store._connect()
    insert_gr(conn, gr_id="GR-NEW")
    insert_gr(conn, gr_id="GR-OLD", state="superseded", superseded_by="GR-NEW")
    conn.execute("DELETE FROM gr WHERE gr_id = 'GR-NEW'")
    assert (
        conn.execute(
            "SELECT superseded_by FROM gr WHERE gr_id = 'GR-OLD'"
        ).fetchone()[0]
        is None
    )


# ----------------------------------------------------------------------
# Citations and anchors
# ----------------------------------------------------------------------


def test_empty_anchor_key_is_refused_on_both_anchor_tables(store):
    """No citation and no anchor row may carry an empty `anchor_key`.

    An acceptance criterion in its own right, made structural here: the empty
    string is the value that silently collapses stage-one dedupe into a
    corpus-wide auto-merge, because every unresolved anchor would then hash
    identically. The file-level anchor is the floor, so a real value always
    exists.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    with pytest.raises(sqlite3.IntegrityError):
        insert_citation(conn, gr_id, anchor_key="")

    citation_id = insert_citation(conn, gr_id)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_citation_anchor "
            "(citation_id, anchor_key, containment, is_primary) VALUES (?,?,?,?)",
            (citation_id, "", "contains", 1),
        )


def test_citation_identity_tuple_is_unique(store):
    """`(gr_id, relative_path, start_line, end_line)` is the citation's identity.

    This is what Step 6's "add any new citations" tests against. Without the
    constraint a re-ingest quietly accumulates duplicate citation rows under a
    correctly deduplicated requirement — the headline merge test passing while
    the same bug runs one level down.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    insert_citation(conn, gr_id)
    with pytest.raises(sqlite3.IntegrityError):
        insert_citation(conn, gr_id)
    # A different range on the same file is a different citation.
    insert_citation(conn, gr_id, start_line=30, end_line=40)
    assert conn.execute("SELECT COUNT(*) FROM gr_citation").fetchone()[0] == 2


def test_citation_content_hash_is_nullable_with_unresolved_resolution(store):
    """An unreadable citation inserts with NULL `content_hash`, not dropped.

    Two columns together distinguish "the file is there but the range is not"
    (`symbol`/`file` with a NULL hash) from "the path is not in the tree at
    all" (`unresolved`) — different diagnoses calling for different fixes, and
    the second usually means the extraction was taken against a different
    checkout.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    insert_citation(
        conn,
        gr_id,
        anchor_resolution="unresolved",
        content_hash=None,
        relative_path="gone/Missing.java",
    )
    row = conn.execute(
        "SELECT anchor_resolution, content_hash FROM gr_citation"
    ).fetchone()
    assert row[0] == "unresolved"
    assert row[1] is None


def test_three_anchor_resolutions_and_three_citation_provenances(store):
    """`anchor_resolution` and `gr_citation.provenance` are closed enums.

    `provenance` has three values because "who put this citation here" is a
    different question from every other provenance field in the schema: the
    drift story needs to distinguish a `repaired` anchor from an original one.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    for ordinal, resolution in enumerate(("symbol", "file", "unresolved")):
        insert_citation(conn, gr_id, anchor_resolution=resolution, start_line=ordinal)
    for ordinal, provenance in enumerate(("extracted", "repaired", "human"), start=10):
        insert_citation(conn, gr_id, provenance=provenance, start_line=ordinal)
    with pytest.raises(sqlite3.IntegrityError):
        insert_citation(conn, gr_id, anchor_resolution="guessed", start_line=99)
    with pytest.raises(sqlite3.IntegrityError):
        insert_citation(conn, gr_id, provenance="inferred", start_line=98)


def test_anchor_rows_cascade_from_their_citation(store):
    """`gr_citation_anchor` rows disappear with their citation.

    The child table is derived and rebuildable from the durable
    (path, start_line, end_line) triple, so cascading is correct: a
    re-resolution pass after a reindex rebuilds it.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    citation_id = insert_citation(conn, gr_id)
    for ordinal, containment in enumerate(("contains", "intersects")):
        conn.execute(
            "INSERT INTO gr_citation_anchor "
            "(citation_id, anchor_key, containment, is_primary) VALUES (?,?,?,?)",
            (citation_id, f"ak1:{ordinal:016d}", containment, 1 - ordinal),
        )
    assert conn.execute("SELECT COUNT(*) FROM gr_citation_anchor").fetchone()[0] == 2
    conn.execute("DELETE FROM gr_citation WHERE citation_id = ?", (citation_id,))
    assert conn.execute("SELECT COUNT(*) FROM gr_citation_anchor").fetchone()[0] == 0


def test_one_citation_holds_many_anchors_keyed_by_pair(store):
    """A citation spanning three siblings gets three rows and one primary.

    `(citation_id, anchor_key)` is the primary key, so the same anchor cannot
    be recorded twice for one citation, while three distinct siblings can.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    citation_id = insert_citation(conn, gr_id)
    for ordinal in range(3):
        conn.execute(
            "INSERT INTO gr_citation_anchor "
            "(citation_id, anchor_key, containment, is_primary) VALUES (?,?,?,?)",
            (citation_id, f"ak1:{ordinal:016d}", "intersects", 1 if ordinal == 0 else 0),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_citation_anchor "
            "(citation_id, anchor_key, containment, is_primary) VALUES (?,?,?,?)",
            (citation_id, "ak1:0000000000000000", "contains", 0),
        )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gr_citation_anchor WHERE is_primary = 1"
        ).fetchone()[0]
        == 1
    )


def test_required_lookup_indexes_exist(store):
    """The four lookup indexes later steps depend on by name exist.

    `gr_citation(anchor_key)` serves the Step 1 move auto-repair's
    `WHERE anchor_key = ?`; `gr_citation_anchor(anchor_key)` serves the
    reverse query, "which requirements touch this symbol"; the two `gr` dedupe
    indexes serve the merge's two stage-one lookups, which run once per
    offered rule.
    """
    names = {
        row[0]
        for row in store._connect().execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }
    assert {
        "ix_gr_citation_anchor_key",
        "ix_gr_citation_anchor_anchor_key",
        "ix_gr_dedupe_key",
        "ix_gr_dedupe_key_anchor_only",
    } <= names


# ----------------------------------------------------------------------
# Scenarios, edge cases, findings, data flow
# ----------------------------------------------------------------------


def test_scenario_uniqueness_includes_provenance(store):
    """`UNIQUE (gr_id, provenance, ordinal)` on `gr_scenario`, provenance inside.

    Without the constraint a re-ingest silently accumulates a second full set
    of scenarios under a correctly deduplicated requirement — the largest
    child table in the store, since G/W/T is required on every rule of every
    run. `provenance` is *inside* the tuple so a human scenario added during
    review can take an ordinal without colliding with an extracted one.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    args = (gr_id, 0, "an open order", "the vendor is absent", "reject it")
    conn.execute(
        'INSERT INTO gr_scenario (gr_id, ordinal, "given", "when", "then", provenance) '
        "VALUES (?,?,?,?,?,'extracted')",
        args,
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            'INSERT INTO gr_scenario (gr_id, ordinal, "given", "when", "then", '
            "provenance) VALUES (?,?,?,?,?,'extracted')",
            args,
        )
    # Same ordinal, human provenance: allowed, and this is the point.
    conn.execute(
        'INSERT INTO gr_scenario (gr_id, ordinal, "given", "when", "then", provenance) '
        "VALUES (?,?,?,?,?,'human')",
        args,
    )
    assert conn.execute("SELECT COUNT(*) FROM gr_scenario").fetchone()[0] == 2


def test_scenario_provenance_has_no_repaired_value(store):
    """`gr_scenario.provenance` is `extracted`/`human` — never `repaired`.

    Nothing repairs a scenario: unlike an anchor it is not derived from
    anything the store can recompute.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            'INSERT INTO gr_scenario (gr_id, ordinal, "given", provenance) '
            "VALUES (?,0,'x','repaired')",
            (gr_id,),
        )


def test_edge_case_carries_the_same_shape_as_scenario(store):
    """`gr_edge_case` mirrors `gr_scenario`, `provenance` included.

    Milestone 1 writes only `extracted`, but the two tables have identical
    lifecycles and are refreshed by the same merge rule, and a Milestone 4
    that lets a reviewer add an edge case must not have to migrate a table.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    conn.execute(
        "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) "
        "VALUES (?,0,'zero-quantity order','extracted')",
        (gr_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) "
            "VALUES (?,0,'again','extracted')",
            (gr_id,),
        )
    conn.execute(
        "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) "
        "VALUES (?,0,'reviewer addition','human')",
        (gr_id,),
    )
    assert conn.execute("SELECT COUNT(*) FROM gr_edge_case").fetchone()[0] == 2


def test_children_cascade_when_their_requirement_is_deleted(store):
    """Every child row goes when its `gr` row does.

    Milestone 1 never deletes a requirement, but the cascades are what make
    the child tables unable to outlive their parent — an orphan child row is
    the kind of state that reads as real data on the next query.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    insert_citation(conn, gr_id)
    conn.execute(
        'INSERT INTO gr_scenario (gr_id, ordinal, "given", provenance) '
        "VALUES (?,0,'x','extracted')",
        (gr_id,),
    )
    conn.execute(
        "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) "
        "VALUES (?,0,'x','extracted')",
        (gr_id,),
    )
    conn.execute(
        "INSERT INTO gr_finding (gr_id, finding_id, severity, span, message) "
        "VALUES (?,'V-CLASS-01','ERROR','','rule_class is NULL')",
        (gr_id,),
    )
    conn.execute(
        "INSERT INTO gr_dataflow (gr_id, direction, datastore, provenance) "
        "VALUES (?,'reads','ORDERS','computed')",
        (gr_id,),
    )
    conn.execute(
        "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) "
        "VALUES (?,'RUN-1',0,'new')",
        (gr_id,),
    )
    conn.execute("DELETE FROM gr WHERE gr_id = ?", (gr_id,))
    for table in (
        "gr_citation",
        "gr_scenario",
        "gr_edge_case",
        "gr_finding",
        "gr_dataflow",
        "gr_run_hit",
    ):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


def test_record_level_finding_stores_empty_span_and_cannot_duplicate(store):
    """A record-level finding stores `span = ''`, never NULL.

    `span` is part of the UNIQUE tuple and SQLite treats NULLs as distinct, so
    a NULL span would let the identical finding insert on every re-validation,
    forever. `V-CLASS-01` and `V-ENF-03` are the record-level checks that make
    this a live case rather than a hypothetical.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    conn.execute(
        "INSERT INTO gr_finding (gr_id, finding_id, severity, span, message) "
        "VALUES (?,'V-CLASS-01','ERROR','','rule_class is NULL')",
        (gr_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_finding (gr_id, finding_id, severity, span, message) "
            "VALUES (?,'V-CLASS-01','ERROR','','rule_class is NULL')",
            (gr_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_finding (gr_id, finding_id, severity, span, message) "
            "VALUES (?,'V-SLOT-01','ERROR',NULL,'no subject')",
            (gr_id,),
        )


def test_severity_takes_exactly_two_values_and_evaluated_is_separate(store):
    """`severity` is two-valued; not-evaluated lives on `evaluated`, not there.

    SPEC-1 S1.6 opens "Severity has exactly two values" and forbids adding,
    removing or re-severitying a check without amending SPEC-1 — and Step 4's
    claim that the slot split is not an amendment rests on that. So a check
    nobody could run keeps the severity it *would* have carried and sets
    `evaluated = 0`, leaving the closed two-value set untouched.
    """
    conn = store._connect()
    gr_id = insert_gr(conn, pattern=None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_finding (gr_id, finding_id, severity, span, message) "
            "VALUES (?,'V-SLOT-01','NOT_EVALUATED','','no template')",
            (gr_id,),
        )
    conn.execute(
        "INSERT INTO gr_finding "
        "(gr_id, finding_id, severity, span, message, evaluated) "
        "VALUES (?,'V-SLOT-01','ERROR','',"
        "'not evaluated: pattern is NULL, so no template locates [Subject]',0)",
        (gr_id,),
    )
    row = conn.execute(
        "SELECT severity, evaluated FROM gr_finding"
    ).fetchone()
    assert (row[0], row[1]) == ("ERROR", 0)
    assert (
        conn.execute("SELECT COUNT(DISTINCT severity) FROM gr_finding").fetchone()[0]
        == 1
    )


def test_findings_default_to_evaluated(store):
    """`evaluated` defaults to 1, so an ordinary finding needs no ceremony.

    The approval gate reads
    `severity = 'ERROR' AND evaluated = 1`, so a default of 0 would make every
    ERROR non-blocking — the gate silently passing everything.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    conn.execute(
        "INSERT INTO gr_finding (gr_id, finding_id, severity, span, message) "
        "VALUES (?,'V-VAG-03','WARN','4-11','vague term')",
        (gr_id,),
    )
    assert conn.execute("SELECT evaluated FROM gr_finding").fetchone()[0] == 1


def test_dataflow_table_level_entry_uses_empty_column_not_null(store):
    """A table-level `gr_dataflow` entry stores `column = ''` and cannot stack.

    SQLite treats NULLs as distinct in a UNIQUE index, so a NULL `column`
    would let the identical entry insert on every recompute, without error,
    forever. The column-level entry beside it is a genuinely different row.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    conn.execute(
        "INSERT INTO gr_dataflow (gr_id, direction, datastore, provenance) "
        "VALUES (?,'reads','ORDERS','computed')",
        (gr_id,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_dataflow (gr_id, direction, datastore, provenance) "
            "VALUES (?,'reads','ORDERS','computed')",
            (gr_id,),
        )
    conn.execute(
        'INSERT INTO gr_dataflow (gr_id, direction, datastore, "column", provenance) '
        "VALUES (?,'reads','ORDERS','VENDOR_NO','computed')",
        (gr_id,),
    )
    assert conn.execute("SELECT COUNT(*) FROM gr_dataflow").fetchone()[0] == 2
    assert (
        conn.execute(
            'SELECT "column" FROM gr_dataflow ORDER BY "column"'
        ).fetchone()[0]
        == ""
    )


# ----------------------------------------------------------------------
# Merge candidates
# ----------------------------------------------------------------------


def test_a_candidate_pair_is_raised_once_across_runs(store):
    """`(gr_id_existing, gr_id_incoming)` is the key; `run_id` is outside it.

    This is the assertion that fails if `run_id` is inside the uniqueness
    tuple: including it keys the pair per run, so run N+2 re-raises a pair a
    reviewer marked `distinct` in run N — precisely the behaviour `resolution`
    exists to prevent, reintroduced by the constraint meant to enforce it.
    """
    conn = store._connect()
    existing = insert_gr(conn, gr_id="GR-EXISTING")
    incoming = insert_gr(conn, gr_id="GR-INCOMING")
    conn.execute(
        "INSERT INTO gr_merge_candidate "
        "(gr_id_existing, gr_id_incoming, run_id, similarity, reason) "
        "VALUES (?,?,'RUN-1',0.91,'semantic')",
        (existing, incoming),
    )
    conn.execute(
        "UPDATE gr_merge_candidate SET resolution = 'distinct', "
        "resolved_at = '2026-09-01T00:00:00Z'"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_merge_candidate "
            "(gr_id_existing, gr_id_incoming, run_id, similarity, reason) "
            "VALUES (?,?,'RUN-2',0.93,'drift')",
            (existing, incoming),
        )
    row = conn.execute(
        "SELECT COUNT(*), MAX(resolution) FROM gr_merge_candidate"
    ).fetchone()
    assert (row[0], row[1]) == (1, "distinct")


def test_candidate_reasons_and_resolutions_are_closed_sets(store):
    """`reason` is three-valued, `resolution` three-valued and defaults open.

    `drift` is a reason in its own right because an anchor-only key hit is a
    high-confidence candidate rather than a cold miss — and never an
    auto-merge, at any confidence.
    """
    conn = store._connect()
    left = insert_gr(conn, gr_id="GR-L")
    for ordinal, reason in enumerate(("semantic", "range_overlap", "drift")):
        right = insert_gr(conn, gr_id=f"GR-R{ordinal}")
        conn.execute(
            "INSERT INTO gr_merge_candidate "
            "(gr_id_existing, gr_id_incoming, reason) VALUES (?,?,?)",
            (left, right, reason),
        )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM gr_merge_candidate WHERE resolution = 'unresolved'"
        ).fetchone()[0]
        == 3
    )
    other = insert_gr(conn, gr_id="GR-OTHER")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_merge_candidate "
            "(gr_id_existing, gr_id_incoming, reason) VALUES (?,?,'hunch')",
            (left, other),
        )


# ----------------------------------------------------------------------
# Runs and hits
# ----------------------------------------------------------------------


def insert_run(conn: sqlite3.Connection, run_id: str = "RUN-1", **overrides) -> str:
    """Insert a `gr_run` row and return its `run_id`."""
    row = {"run_id": run_id, "system": "customer.ple.nng.app", **overrides}
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT INTO gr_run ({columns}) VALUES ({placeholders})", tuple(row.values())
    )
    return run_id


def test_unmeasured_coverage_is_null_and_is_not_complete(store):
    """NULL `not_accounted_for` means "never measured" and `complete` is 0.

    This is the difference between a gate and the appearance of one. The
    workflow returns `coverage: null` whenever `repoRoot` was omitted, no
    index existed, or the coverage command failed; store a zero for such a run
    and the arithmetic says it is complete, so `export` waves through a corpus
    whose coverage nobody ever looked at — the gate passing most confidently
    in the one case it should stop.
    """
    conn = store._connect()
    insert_run(conn, "RUN-UNMEASURED", not_accounted_for=None)
    insert_run(conn, "RUN-CLEAN", not_accounted_for=0)
    insert_run(conn, "RUN-GAPS", not_accounted_for=37)
    rows = dict(
        conn.execute("SELECT run_id, complete FROM gr_run").fetchall()
    )
    assert rows == {"RUN-UNMEASURED": 0, "RUN-CLEAN": 1, "RUN-GAPS": 0}


def test_complete_is_generated_and_therefore_unwritable(store):
    """`complete` is a generated column, so no writer can contradict it.

    It is defined as `not_accounted_for IS NOT NULL AND not_accounted_for = 0`
    in the schema rather than at each of its writers, which is what makes
    "unmeasured falls to the same side as incomplete without pretending to be
    it" structural. **Note the quirk this brings and that this test pins:
    `PRAGMA table_info` omits generated columns**, so anything enumerating
    `gr_run`'s columns must use `PRAGMA table_xinfo` or read `complete` as
    missing.
    """
    conn = store._connect()
    insert_run(conn, "RUN-1", not_accounted_for=12)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("UPDATE gr_run SET complete = 1")

    info = {row[1] for row in conn.execute("PRAGMA table_info('gr_run')")}
    xinfo = {row[1] for row in conn.execute("PRAGMA table_xinfo('gr_run')")}
    assert "complete" not in info
    assert "complete" in xinfo

    # Re-measuring clears it on its merits, and `complete` follows for free.
    conn.execute(
        "UPDATE gr_run SET not_accounted_for = 0, coverage_source = 'remeasured', "
        "coverage_measured_at = '2026-09-01T12:00:00Z'"
    )
    assert conn.execute("SELECT complete FROM gr_run").fetchone()[0] == 1


def test_retiring_a_run_requires_a_reason_and_leaves_complete_alone(store):
    """`gate_excluded = 1` demands a reason and does not touch `complete`.

    Retiring a run is a human judgement and is logged as one: the audit
    question is "why did this stop blocking?", and a NULL reason has no answer
    to it. `complete` is left untouched so the record still says what was
    actually known — which is what keeps `retire-run` and `set-run-coverage`
    distinguishable after the fact.
    """
    conn = store._connect()
    insert_run(conn, "RUN-1", not_accounted_for=None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE gr_run SET gate_excluded = 1")
    conn.execute(
        "UPDATE gr_run SET gate_excluded = 1, "
        "gate_excluded_reason = 'superseded exploratory run'"
    )
    row = conn.execute(
        "SELECT gate_excluded, gate_excluded_reason, complete, coverage_source "
        "FROM gr_run"
    ).fetchone()
    assert row[0] == 1
    assert row[1] == "superseded exploratory run"
    assert row[2] == 0
    assert row[3] is None


def test_stop_reason_has_three_values_not_a_boolean(store):
    """`stop_reason` is a three-value enum; `cap_reached` would be wrong.

    There are three termination paths, not two: running dry, hitting
    `maxRounds`, and the token-budget break that exits the loop early. A
    boolean folds the third into whichever branch it happens to resemble.
    `round_cap` is stored beside `rounds_run` because "we stopped at the cap"
    means nothing without knowing what the cap was — the workflow's clamp
    silently turns a requested 20 into 8.
    """
    conn = store._connect()
    for ordinal, reason in enumerate(("dry", "round_cap", "budget_exhausted")):
        insert_run(
            conn, f"RUN-{ordinal}", stop_reason=reason, rounds_run=3, round_cap=8
        )
    assert conn.execute("SELECT COUNT(*) FROM gr_run").fetchone()[0] == 3
    with pytest.raises(sqlite3.IntegrityError):
        insert_run(conn, "RUN-X", stop_reason="cap_reached")


def test_two_hits_from_one_run_may_land_on_one_requirement(store):
    """No uniqueness on `(gr_id, run_id)` — and that is load-bearing.

    One row means one *offered* rule, not one requirement. The extractor's own
    in-run dedupe keys on `path::lowercased-name`, so two rules mined from the
    same lines under different names survive it and can then collide on
    `dedupe_key`. Under a natural key one of them is refused or silently
    absorbed, `rules_in` under-counts, and the count identity fails for a
    reason that is not a defect in the merge.
    """
    conn = store._connect()
    gr_id = insert_gr(conn)
    insert_run(conn, "RUN-1")
    conn.execute(
        "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) "
        "VALUES (?,'RUN-1',0,'new')",
        (gr_id,),
    )
    conn.execute(
        "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) "
        "VALUES (?,'RUN-1',7,'merged')",
        (gr_id,),
    )
    assert conn.execute("SELECT COUNT(*) FROM gr_run_hit").fetchone()[0] == 2
    # The collapse is countable from `offer_ordinal` alone: this is Step 10's
    # intra-run collapse rate on a first ingest into an empty store.
    collapsed = conn.execute(
        "SELECT COUNT(*) FROM gr_run_hit WHERE gr_id IN ("
        "  SELECT gr_id FROM gr_run_hit WHERE run_id = 'RUN-1'"
        "  GROUP BY gr_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    assert collapsed == 2


def test_run_counts_are_derivable_from_hits(store):
    """`rules_in = rules_new + rules_merged + rules_candidate` over real rows.

    Deriving the counts from `gr_run_hit` is what makes the identity
    *checkable* rather than merely asserted. `rules_rejected` sits outside it:
    rejected rules never become `gr` rows at all, so the four numbers are not
    meant to sum.
    """
    conn = store._connect()
    insert_run(conn, "RUN-1")
    for ordinal, outcome in enumerate(("new", "new", "merged", "candidate")):
        gr_id = insert_gr(conn, gr_id=f"GR-{ordinal}")
        conn.execute(
            "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) "
            "VALUES (?,'RUN-1',?,?)",
            (gr_id, ordinal, outcome),
        )
    counts = dict(
        conn.execute(
            "SELECT outcome, COUNT(*) FROM gr_run_hit WHERE run_id = 'RUN-1' "
            "GROUP BY outcome"
        ).fetchall()
    )
    rules_in = conn.execute(
        "SELECT COUNT(*) FROM gr_run_hit WHERE run_id = 'RUN-1'"
    ).fetchone()[0]
    assert rules_in == counts.get("new", 0) + counts.get("merged", 0) + counts.get(
        "candidate", 0
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) "
            "VALUES ('GR-0','RUN-1',99,'skipped')"
        )


def test_injection_flags_round_trip_as_json(store):
    """`injection_flags` holds the workflow's `injectionFlags` as JSON text.

    Surfacing it is Step 8's job — a distinct, unmissable line in
    `requirements stats` whenever it is non-empty, never folded into a general
    table. This is the one field in the schema whose value is entirely in
    being read.
    """
    conn = store._connect()
    flags = ["src/Order.java:112", "src/legacy/Batch.cbl:9"]
    insert_run(conn, "RUN-1", injection_flags=json.dumps(flags))
    stored = conn.execute("SELECT injection_flags FROM gr_run").fetchone()[0]
    assert json.loads(stored) == flags


def test_gr_import_is_append_only_provenance(store):
    """`gr_import` records one row per import, with no join back to `gr`.

    Import is the single declared exception to "`set_state` is the only writer
    of `gr.state`", so a state change arriving through it must be traceable to
    a specific import rather than appearing to have happened spontaneously.
    Attributing each individual row to the import that last touched it would
    be a per-record audit trail, which is Milestone 4's.
    """
    conn = store._connect()
    conn.execute(
        "INSERT INTO gr_import "
        "(source_path, imported_at, rows_read, rows_changed_state) "
        "VALUES ('legacylift-docs/knowledge/requirements.jsonl',"
        "'2026-09-01T00:00:00Z',470,3)"
    )
    row = conn.execute(
        "SELECT import_id, rows_read, rows_changed_state FROM gr_import"
    ).fetchone()
    assert row[0] == 1
    assert (row[1], row[2]) == (470, 3)
    foreign_keys = conn.execute(
        "PRAGMA foreign_key_list('gr_import')"
    ).fetchall()
    assert foreign_keys == []


# ----------------------------------------------------------------------
# The invariant that ties it together
# ----------------------------------------------------------------------


def test_no_gr_column_takes_a_domain_and_retagging_moves_no_key(store):
    """Re-tagging domains leaves every stored key byte-identical.

    The unit-scale form of Step 3's required invariant: because no key takes a
    domain as an input, re-tagging is a single `UPDATE ... SET domain = ?` on
    one `file_domains` row — nothing re-keys, no row is orphaned, no citation
    breaks. `subject` is domain-derived and is *expected* to move, which is
    exactly why it is excluded from both dedupe keys; `rederive-subjects`
    (Step 8) is what moves it.
    """
    conn = store._connect()
    store.upsert_file_domain("src/Order.java", "orders", "glob", None, 1.0)
    gr_id = insert_gr(conn, subject="order", subject_provenance="derived")
    insert_citation(conn, gr_id, content_hash="ch1:2222222222222222")
    before = conn.execute(
        "SELECT g.dedupe_key, g.dedupe_key_anchor_only, c.anchor_key, c.content_hash "
        "FROM gr g JOIN gr_citation c ON c.gr_id = g.gr_id"
    ).fetchall()

    store.upsert_file_domain("src/Order.java", "billing", "glob", None, 1.0)

    after = conn.execute(
        "SELECT g.dedupe_key, g.dedupe_key_anchor_only, c.anchor_key, c.content_hash "
        "FROM gr g JOIN gr_citation c ON c.gr_id = g.gr_id"
    ).fetchall()
    assert before == after
    assert store.domain_for_file("src/Order.java") == "billing"
