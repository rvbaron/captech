"""Tests for Step 8's `set-field` write path (`gr_setfield.set_field`).

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. Every
test here fails before this wave with `No module named
'legacylift_search.gr_setfield'` and passes after.

Three assertions carry the weight, and each guards a rule that is easy to
break and silent when broken:

* **`test_writing_rule_class_or_pattern_never_moves_a_dedupe_key`** -- keys
  move only on extractor-owned writes (the Decision Log). `rule_class` and
  `pattern` are the only human-writable key inputs, so this is the one place
  the rule is easy to break, and a broken one silently re-partitions the
  merge.
* **`test_the_accepted_set_is_derived_and_refusals_are_by_membership`** -- the
  twelve accepted columns come from `gr_fields.set_field_accepted_fields`,
  and everything else is refused by which ownership set it is in rather than
  by a hand-written denial list, so a column added to `gr` and classified is
  refused with no edit here.
* **`test_set_field_is_not_a_writer_of_gr_state`** -- `state` sits in
  `STORE_OWNED_FIELDS`, so the membership refusal is what keeps `set_state`
  the only route through the approval gate. The `ast`-based writer census in
  `test_gr_state.py` covers the raw-SQL half; this covers the behavioural
  half.

The enum sets in `COLUMN_ENUMS` are hand-written, so
`test_every_declared_enum_value_is_accepted_by_the_schema` **probes** each
one against the live database rather than inspecting the DDL text: every
listed value must be accepted by SQLite and a value outside the set must be
refused by it, so a drift between the mapping and the schema fails a test
instead of surfacing as a `set-field` that rejects a legal value.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from legacylift_search.embeddings import HashEmbedder
from legacylift_search.gr_fields import (
    EXTRACTOR_OWNED_FIELDS,
    STORE_OWNED_FIELDS,
    set_field_accepted_fields,
)
from legacylift_search.gr_setfield import (
    COLUMN_ENUMS,
    NOT_NULL_FIELDS,
    SetFieldError,
    set_field,
)
from legacylift_search.knowledge_store import KnowledgeStore
from tests.test_gr_state import insert_gr

_IS_WINDOWS = sys.platform == "win32"


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
    return insert_gr(store._connect(), gr_id=f"GR-01HQ2X{n:022d}", **overrides)


# --------------------------------------------------------------------------
# The accepted set, and refusal by membership
# --------------------------------------------------------------------------


def test_the_accepted_set_is_derived_and_refusals_are_by_membership(store):
    """Proves the twelve accepted columns and the two refused sets.

    The acceptance list is not hand-written here: it is
    `gr_fields.set_field_accepted_fields(conn)`, which derives the shadowed
    half from `PRAGMA table_info`. And every refusal names the *set* the
    column belongs to, so a column added to `gr` and classified into either
    refused set is refused automatically with no edit in `gr_setfield.py`.
    """
    conn = store._connect()
    accepted = set_field_accepted_fields(conn)
    assert len(accepted) == 12
    gr_id = _gr(store)

    # Every accepted column takes a write (or an explicit clear) without a
    # membership refusal. This is the reachability half: a column that is
    # nominally accepted but unreachable is the defect `owner`, `rule_class`
    # and `pattern` each were before PR-81.
    values = {
        "rule_class": "behavioral",
        "pattern": "B-COND",
        "enforcement_level": "strict",
        "confidence_intent": "High",
        "disposition": "captured",
        "modality_confirmed": "1",
        "rationale": "Vendor numbers identify the payee.",
        "fit_criterion": "A payment with no vendor number is rejected.",
        "owner": "sme@example.com",
        "statement": "The Order Service must record a vendor number.",
        "assumptions": "",
        "modality": "expectation",
    }
    assert set(values) == accepted
    for field, value in values.items():
        result = set_field(store, gr_id, field, value)
        assert result.field == field

    for field in sorted(EXTRACTOR_OWNED_FIELDS):
        with pytest.raises(SetFieldError, match="EXTRACTOR_OWNED"):
            set_field(store, gr_id, field, "x")
    for field in sorted(STORE_OWNED_FIELDS):
        with pytest.raises(SetFieldError, match="STORE_OWNED"):
            set_field(store, gr_id, field, "x")


def test_the_three_extracted_shadows_are_refused_by_their_set_not_by_name(store):
    """Proves the shadows are refused because of membership, not a special case.

    A human never edits a shadow -- the extractor is its only writer -- and
    the refusal has to come from `EXTRACTOR_OWNED_FIELDS` rather than from a
    rule written against the `_extracted` suffix, or a fourth shadow column
    added later would be accepted by omission.
    """
    gr_id = _gr(store)
    for field in (
        "statement_extracted",
        "assumptions_extracted",
        "modality_extracted",
    ):
        assert field in EXTRACTOR_OWNED_FIELDS
        with pytest.raises(SetFieldError, match="EXTRACTOR_OWNED"):
            set_field(store, gr_id, field, "x")


def test_set_field_is_not_a_writer_of_gr_state(store):
    """Proves `set-state` stays the only route through the approval gate.

    `state` is in `STORE_OWNED_FIELDS`, so no special case is needed; the
    message says so, and the row is unchanged. The raw-SQL half of this
    property is the `ast` writer census in `test_gr_state.py`.
    """
    gr_id = _gr(store, state="draft")
    with pytest.raises(SetFieldError) as exc:
        set_field(store, gr_id, "state", "approved")
    assert "set-state" in str(exc.value)
    assert store.get_gr(gr_id).state == "draft"


def test_both_dedupe_keys_are_refused_as_store_owned(store):
    """Proves a key cannot be hand-edited through this command at all."""
    gr_id = _gr(store)
    for field in ("dedupe_key", "dedupe_key_anchor_only"):
        with pytest.raises(SetFieldError, match="extractor-owned write"):
            set_field(store, gr_id, field, "dk1:deadbeefdeadbeef")


def test_an_unknown_column_and_an_unknown_requirement_are_refused(store):
    gr_id = _gr(store)
    with pytest.raises(SetFieldError, match="not a column of `gr`"):
        set_field(store, gr_id, "no_such_column", "x")
    with pytest.raises(SetFieldError, match="no requirement"):
        set_field(store, "GR-nope", "owner", "sme@example.com")


# --------------------------------------------------------------------------
# The no-key-recompute rule
# --------------------------------------------------------------------------


def test_writing_rule_class_or_pattern_never_moves_a_dedupe_key(store):
    """Proves the Decision Log rule: keys move only on extractor-owned writes.

    `rule_class` and `pattern` are inputs to **both** dedupe keys and the
    only human-writable columns that are, so this is the single place the
    rule is easy to break -- and a broken one silently re-partitions the
    merge, changing which incoming rules match which stored ones with
    nothing reporting it.
    """
    gr_id = _gr(store, rule_class="behavioral", pattern="B-UNCOND")
    before = store.get_gr(gr_id)

    set_field(store, gr_id, "pattern", "B-COND")
    mid = store.get_gr(gr_id)
    assert mid.pattern == "B-COND"
    assert mid.dedupe_key == before.dedupe_key
    assert mid.dedupe_key_anchor_only == before.dedupe_key_anchor_only

    # The prefix tie forbids leaving a definitional rule on a B-* pattern, so
    # the pattern is cleared first; either way the keys must not move.
    set_field(store, gr_id, "pattern", None)
    set_field(store, gr_id, "rule_class", "definitional")
    after = store.get_gr(gr_id)
    assert after.rule_class == "definitional" and after.pattern is None
    assert after.dedupe_key == before.dedupe_key
    assert after.dedupe_key_anchor_only == before.dedupe_key_anchor_only


def test_gr_setfield_does_not_import_the_key_producer():
    """Proves the no-recompute rule structurally, by `ast`, not by text.

    A text grep for `gr_keys` trips on the prose in this module's own
    docstring that *describes* the rule -- the absent-versus-real rule
    applied to source code, which cost three assertions in Wave B. So this
    walks the import statements.
    """
    import ast

    path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legacylift_search"
        / "gr_setfield.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(f"{node.module or ''}.{a.name}" for a in node.names)
    assert not any("gr_keys" in name for name in imported), sorted(imported)
    assert not any("compute_dedupe_keys" in name for name in imported)


# --------------------------------------------------------------------------
# Schema CHECK constraints, refused at the function
# --------------------------------------------------------------------------


def test_every_declared_enum_value_is_accepted_by_the_schema(store):
    """Probes `COLUMN_ENUMS` against the live database, in both directions.

    The mapping is hand-written, so this is what keeps it from drifting from
    the DDL: every declared value must be accepted by SQLite, and a value
    outside the set must be refused by it. A DDL parser would be its own
    fragile thing; a probe cannot be wrong about what the database does.
    """
    import sqlite3

    conn = store._connect()
    gr_id = _gr(store, rule_class=None, pattern=None, enforcement_level=None)
    for column, values in COLUMN_ENUMS.items():
        for value in values:
            conn.execute(
                f'UPDATE gr SET "{column}" = ? WHERE gr_id = ?', (value, gr_id)
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f'UPDATE gr SET "{column}" = ? WHERE gr_id = ?',
                (f"not-a-{column}", gr_id),
            )
        conn.rollback()


def test_a_value_outside_the_enum_is_refused_by_the_function(store):
    """Proves the refusal names the column and the legal values.

    A raw `CHECK constraint failed` names neither, and this command's whole
    audience is a human typing a value at a shell.
    """
    gr_id = _gr(store)
    with pytest.raises(SetFieldError) as exc:
        set_field(store, gr_id, "pattern", "B-NOPE")
    assert "pattern" in str(exc.value) and "B-COND" in str(exc.value)
    with pytest.raises(SetFieldError, match="confidence_intent"):
        set_field(store, gr_id, "confidence_intent", "high")


def test_an_enforcement_level_on_a_definitional_rule_is_refused(store):
    """Proves SPEC-1 S1.7 item 3, in both write orders.

    One of the plan's two named worked examples. A definitional rule cannot
    be "suggested but not enforced" because it cannot be violated, and the
    refusal must fire whichever of the two columns is written second.
    """
    a = _gr(store, 1, rule_class="definitional", pattern="D-NEC")
    with pytest.raises(SetFieldError, match="definitional"):
        set_field(store, a, "enforcement_level", "guideline")
    assert store.get_gr(a).enforcement_level is None

    b = _gr(store, 2, rule_class="behavioral", pattern="B-UNCOND")
    set_field(store, b, "enforcement_level", "guideline")
    with pytest.raises(SetFieldError, match="definitional"):
        set_field(store, b, "rule_class", "definitional")
    assert store.get_gr(b).rule_class == "behavioral"


def test_a_pattern_whose_prefix_disagrees_with_rule_class_is_refused(store):
    """Proves SPEC-1 S1.7 item 2, the plan's other named worked example."""
    gr_id = _gr(store, rule_class="behavioral", pattern="B-UNCOND")
    with pytest.raises(SetFieldError, match="disagree"):
        set_field(store, gr_id, "pattern", "D-NEC")
    with pytest.raises(SetFieldError, match="disagree"):
        set_field(store, gr_id, "rule_class", "definitional")
    assert store.get_gr(gr_id).pattern == "B-UNCOND"


def test_clearing_pattern_on_an_approved_row_is_refused(store):
    """Proves the scoped S1.4 CHECK is re-evaluated against the new row.

    The one a reader would not expect `set-field` to be able to trip:
    clearing `pattern` is legal on a `draft` row and violates the table's
    scoped CHECK on an `approved` one. Refusing it here means the message
    names the state and the column instead of the constraint.
    """
    approved = _gr(store, 1, state="approved", pattern="B-UNCOND")
    with pytest.raises(SetFieldError, match="approved"):
        set_field(store, approved, "pattern", None)
    assert store.get_gr(approved).pattern == "B-UNCOND"

    # ... and the same clear is fine on a draft row, which is why the CHECK
    # is scoped at all: nothing gates `draft`.
    draft = _gr(store, 2, state="draft", pattern="B-UNCOND", rule_class="behavioral")
    set_field(store, draft, "pattern", None)
    assert store.get_gr(draft).pattern is None

    # And an approved row whose disposition satisfies the CHECK's third arm
    # may be left pattern-less.
    delegated = _gr(
        store, 3, state="approved", pattern="B-UNCOND", disposition="delegated"
    )
    set_field(store, delegated, "pattern", None)
    assert store.get_gr(delegated).pattern is None


def test_a_not_null_column_cannot_be_cleared(store):
    """Proves the message names the column, not the constraint."""
    gr_id = _gr(store)
    for field in sorted(NOT_NULL_FIELDS):
        with pytest.raises(SetFieldError, match="NOT NULL"):
            set_field(store, gr_id, field, None)


def test_a_blank_statement_is_refused_by_set_field_not_by_the_schema(store):
    """Proves a decision this module makes: '' is not an edit anybody meant.

    The schema would accept `''` -- `statement` is `NOT NULL`, not
    `CHECK (statement <> '')` -- so this refusal is `set-field`'s own and the
    message says so, pointing at `set-state --to rejected` for retiring a
    requirement instead.
    """
    gr_id = _gr(store)
    with pytest.raises(SetFieldError, match="cannot be blank"):
        set_field(store, gr_id, "statement", "   ")
    assert store.get_gr(gr_id).statement != "   "


def test_assumptions_accepts_the_empty_string_because_it_means_something(store):
    """Proves the one column whose `''` is a real value can be written as one.

    `assumptions = ''` means the agent considered assumptions and had none;
    NULL means the field never arrived. Both must be reachable or the fill
    figures cannot distinguish them.
    """
    gr_id = _gr(store, assumptions=None)
    set_field(store, gr_id, "assumptions", "")
    assert store.get_gr(gr_id).assumptions == ""
    set_field(store, gr_id, "assumptions", None)
    assert store.get_gr(gr_id).assumptions is None


def test_modality_confirmed_takes_a_boolean_word_and_refuses_a_number(store):
    """Proves the one non-text column's coercion, and that `0` is a real value."""
    gr_id = _gr(store)
    set_field(store, gr_id, "modality_confirmed", "true")
    assert store.get_gr(gr_id).modality_confirmed is True
    set_field(store, gr_id, "modality_confirmed", "0")
    assert store.get_gr(gr_id).modality_confirmed is False
    with pytest.raises(SetFieldError, match="boolean"):
        set_field(store, gr_id, "modality_confirmed", "2")


# --------------------------------------------------------------------------
# The value-changing-write rule
# --------------------------------------------------------------------------


def test_writing_the_value_the_row_already_holds_changes_nothing(store):
    """Proves `updated_at` is not bumped and the validator does not re-run.

    `updated_at` is in the JSONL export, so a no-op write that bumped it
    would show every touched record as modified in the next pull request --
    which is the same value-changing-write rule the merge and `set_state`
    apply, for the same reason.
    """
    gr_id = _gr(store, owner="sme@example.com")
    before = store.get_gr(gr_id)
    result = set_field(store, gr_id, "owner", "sme@example.com")
    assert result.changed is False
    assert result.validated is False
    after = store.get_gr(gr_id)
    assert after.updated_at == before.updated_at


def test_clearing_an_already_null_column_is_a_no_op(store):
    """Proves NULL-to-NULL is compared identically, not by SQL equality.

    `=` over two NULLs yields NULL rather than true -- the same trap
    `gr_shadow_is_unedited` disarms with `IS` -- so a comparison written the
    obvious way would treat every clear of an empty column as a change.
    """
    gr_id = _gr(store, rationale=None)
    before = store.get_gr(gr_id)
    result = set_field(store, gr_id, "rationale", None)
    assert result.changed is False
    assert store.get_gr(gr_id).updated_at == before.updated_at


def test_a_real_write_bumps_updated_at(store):
    """The other half of the rule: a value change does bump the column."""
    gr_id = _gr(store, owner=None)
    before = store.get_gr(gr_id)
    result = set_field(store, gr_id, "owner", "sme@example.com")
    assert result.changed is True
    assert store.get_gr(gr_id).updated_at != before.updated_at


# --------------------------------------------------------------------------
# The validator re-run and the refresh pair
# --------------------------------------------------------------------------


def test_editing_the_statement_re_runs_the_validator_and_rewrites_the_fts_row(store):
    """Proves both derived artifacts follow the edit.

    Editing `statement` changes its findings, and the FTS row holds its own
    copy of the text -- so without the delete half of `replace_gr_fts` the
    record stays searchable by wording it no longer contains.
    """
    gr_id = _gr(
        store,
        statement="The Order Service must record a vendor number on each order.",
    )
    set_field(store, gr_id, "statement", "The system shall do stuff.")

    conn = store._connect()
    assert store.search_gr_fts("stuff") != []
    assert store.search_gr_fts("vendor") == [], (
        "the pre-edit wording must stop matching"
    )
    # The validator ran: `V-SLOT-02` bans "the system" as a subject literal,
    # so the edited statement must now carry at least one finding.
    findings = store.list_gr_findings(gr_id)
    assert findings != []
    assert conn.execute(
        "SELECT COUNT(*) FROM gr_finding WHERE gr_id = ?", (gr_id,)
    ).fetchone()[0] == len(findings)


def test_setting_the_pattern_makes_the_slot_checks_evaluable(store):
    """Proves the second reason the validator must re-run after this write.

    With a NULL `pattern` the three `V-SLOT` checks cannot be decided and
    report `evaluated = 0`; setting the pattern is what turns them into a
    real verdict. A `set-field` that skipped the re-run would leave a record
    permanently carrying undecided findings for a decision that had been
    made.
    """
    gr_id = _gr(
        store,
        rule_class="behavioral",
        pattern=None,
        statement=(
            "The Order Service must record a vendor number on each order."
        ),
    )
    # Seed the findings for the pattern-less shape.
    set_field(store, gr_id, "rationale", "seed the validator run")
    undecided_before = [
        f for f in store.list_gr_findings(gr_id) if not f.evaluated
    ]
    assert undecided_before != [], "a NULL pattern leaves slot checks undecided"

    set_field(store, gr_id, "pattern", "B-UNCOND")
    undecided_after = [f for f in store.list_gr_findings(gr_id) if not f.evaluated]
    assert len(undecided_after) < len(undecided_before)


def test_the_result_reports_blocking_findings_using_the_evaluated_rule(store):
    """Proves an undecided finding is not reported as a violation.

    `gr_validator.can_approve` ignores not-evaluated findings, so
    `SetFieldResult.blocking_findings` must too -- a check that could not be
    decided is never one that failed.
    """
    gr_id = _gr(store, rule_class=None, pattern=None)
    result = set_field(store, gr_id, "owner", "sme@example.com")
    assert all(f.evaluated for f in result.blocking_findings)
    assert all(f.severity == "ERROR" for f in result.blocking_findings)
    # V-CLASS-01 blocks approval on a NULL rule_class and is evaluated.
    assert "V-CLASS-01" in {f.finding_id for f in result.blocking_findings}


def test_the_vector_half_may_degrade_and_the_edit_still_lands(store):
    """Proves `embedder=None` is a degraded success, not an error path.

    The edit must never fail because an embedding provider is unreachable:
    the SQLite half is committed unconditionally, and the reason names
    `requirements reindex-vectors` as the recovery.
    """
    gr_id = _gr(store, owner=None)
    result = set_field(store, gr_id, "owner", "sme@example.com", embedder=None)
    assert result.changed is True
    assert store.get_gr(gr_id).owner == "sme@example.com"
    assert result.embed.reason is not None
    assert "reindex-vectors" in result.embed.reason


def test_the_edit_reaches_the_vector_collection_when_an_embedder_exists(store):
    """Proves the second half of the refresh pair runs after the commit."""
    from legacylift_search.gr_refresh import open_gr_collection

    gr_id = _gr(store, statement="Rule one must hold.")
    result = set_field(
        store,
        gr_id,
        "statement",
        "Rule one must hold for every order.",
        embedder=HashEmbedder(dimension=64),
    )
    assert result.embed.embedded == 1
    assert result.embed.reason is None
    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        got = collection.collection.get(ids=[gr_id], include=["documents"])
        assert got["documents"] == ["Rule one must hold for every order."]
    finally:
        collection.close()


def test_nothing_is_written_when_a_refusal_fires(store):
    """Proves every check runs before the update, not after it.

    A refusal that had already written the column would leave the row in the
    state the message says it refused to create.
    """
    gr_id = _gr(store, rule_class="behavioral", pattern="B-UNCOND", owner=None)
    before = store.get_gr(gr_id)
    for field, value in (
        ("pattern", "D-NEC"),
        ("pattern", "B-NOPE"),
        ("statement", None),
        ("state", "approved"),
        ("name", "x"),
    ):
        with pytest.raises(SetFieldError):
            set_field(store, gr_id, field, value)
    assert store.get_gr(gr_id).model_dump() == before.model_dump()
