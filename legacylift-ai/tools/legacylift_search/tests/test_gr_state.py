"""Tests for the lifecycle transition function and the `draft -> approved` gate.

Milestone 1, Step 4 of `docs/exec-plans/active/reqs-to-data-store.md` (the
gate) with the transition graph Step 8 writes down. Every test here fails
before Step 4 (`No module named 'legacylift_search.gr_state'`) and passes
after.

The assertion worth naming: `test_set_state_is_the_only_writer_of_gr_state`
is the executable form of "no producer may write `gr.state` by any other
route". It is a source scan rather than a behavioural test because the
property is about code that does not exist yet — a future producer's second
write path — and behaviour cannot assert the absence of one.
"""

from __future__ import annotations

import ast
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from legacylift_search.gr_state import (
    ALLOWED_TRANSITIONS,
    ApprovalBlockedError,
    StateTransitionError,
    set_state,
)
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import Finding

#: Any write statement targeting the `gr` table. It deliberately does **not**
#: mention `state`: a runtime-built SET clause or column list hides the column
#: name from any source scan, so the census asks "does this module write `gr`
#: rows at all?" and requires every module that does to be declared. See
#: `test_the_gr_state_writer_census_cannot_be_evaded` for the shapes this
#: catches and the one it must not.
_WRITES_GR_ROWS = re.compile(
    r"UPDATE\s+gr\s+SET"
    r"|INSERT(?:\s+OR\s+\w+)?\s+INTO\s+gr\s*\("
    r"|REPLACE\s+INTO\s+gr\s*\(",
    re.IGNORECASE,
)


def _sql_literals(text: str) -> list[str]:
    """Every real string literal in `text`, docstrings excluded.

    Docstrings are excluded because prose describing a write path is not one;
    comments are excluded for free, since they never reach the AST. An
    f-string contributes its literal parts with each interpolation replaced by
    a placeholder, which is what lets the scan see through
    ``f"UPDATE gr SET {set_clause}"``. Adjacent string literals are folded by
    the parser into one constant, which covers the concatenation case.
    """
    tree = ast.parse(text)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.append(
                "".join(
                    part.value
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                    else " ? "
                    for part in node.values
                )
            )
    return out

_MINIMAL_GR = {
    "gr_id": "GR-01HQ2X0000000000000000000",
    "kind": "business_rule",
    "statement": "The Order Service must record a vendor number on each order.",
    "statement_extracted": (
        "The Order Service must record a vendor number on each order."
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
    with tempfile.TemporaryDirectory() as tmpdir:
        ks = KnowledgeStore(Path(tmpdir) / "knowledge" / "knowledge.sqlite")
        try:
            yield ks
        finally:
            ks.close()


def insert_gr(conn: sqlite3.Connection, **overrides) -> str:
    """Insert a `gr` row that is approvable unless a test says otherwise."""
    row = {**_MINIMAL_GR, "rule_class": "behavioral", "pattern": "B-UNCOND"}
    row.update(overrides)
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT INTO gr ({columns}) VALUES ({placeholders})", tuple(row.values())
    )
    conn.commit()
    return row["gr_id"]


# --------------------------------------------------------------------------
# The transition graph
# --------------------------------------------------------------------------


def test_the_graph_is_enumerable_and_superseded_is_terminal():
    assert set(ALLOWED_TRANSITIONS) == {
        "draft",
        "reviewed",
        "approved",
        "rejected",
        "superseded",
    }
    assert ALLOWED_TRANSITIONS["superseded"] == frozenset()
    # `draft -> approved` is permitted directly: Milestone 1 has no review
    # queue, so requiring two calls for one act of signing off is ceremony.
    assert "approved" in ALLOWED_TRANSITIONS["draft"]
    # `rejected -> draft` reopens a rule someone rejected in error.
    assert ALLOWED_TRANSITIONS["rejected"] == frozenset({"draft"})


@pytest.mark.parametrize(
    "start,target",
    sorted(
        (start, target)
        for start, targets in ALLOWED_TRANSITIONS.items()
        for target in targets
    ),
)
def test_every_allowed_move_succeeds_from_the_right_starting_state(
    store, start, target
):
    """Enumerated from the mapping itself, so a graph edit cannot outrun it."""
    gr_id = insert_gr(store._connect(), state=start)
    kwargs = (
        {"superseded_by": "GR-01HQ2X0000000000000000001"}
        if target == "superseded"
        else {}
    )
    if target == "superseded":
        insert_gr(store._connect(), gr_id="GR-01HQ2X0000000000000000001")
    set_state(store, gr_id, target, "reviewer@example.com", **kwargs)
    assert store.get_gr(gr_id).state == target


@pytest.mark.parametrize(
    "start,target",
    sorted(
        (start, target)
        for start, targets in ALLOWED_TRANSITIONS.items()
        for target in ALLOWED_TRANSITIONS
        if target not in targets and target != start
    ),
)
def test_every_move_outside_the_graph_is_refused_naming_both_states(
    store, start, target
):
    gr_id = insert_gr(store._connect(), state=start)
    with pytest.raises(StateTransitionError) as exc:
        set_state(store, gr_id, target, "reviewer@example.com")
    assert start in str(exc.value)
    assert target in str(exc.value)
    assert store.get_gr(gr_id).state == start


def test_an_unknown_state_is_refused_rather_than_written(store):
    gr_id = insert_gr(store._connect())
    with pytest.raises(StateTransitionError, match="unknown state"):
        set_state(store, gr_id, "signed-off", "reviewer@example.com")
    assert store.get_gr(gr_id).state == "draft"


def test_an_unknown_requirement_is_refused(store):
    with pytest.raises(StateTransitionError, match="no requirement"):
        set_state(store, "GR-nope", "approved", "reviewer@example.com")


# --------------------------------------------------------------------------
# The review act
# --------------------------------------------------------------------------


def test_an_approval_records_reviewer_timestamp_and_note(store):
    gr_id = insert_gr(store._connect())
    set_state(store, gr_id, "approved", "dnorton", note="checked against the DDL")
    row = store.get_gr(gr_id)
    assert row.state == "approved"
    assert row.reviewed_by == "dnorton"
    assert row.reviewed_at
    assert row.review_note == "checked against the DDL"
    assert row.updated_at != _MINIMAL_GR["updated_at"]


def test_a_same_state_move_is_a_no_op_that_stamps_nothing(store):
    """The value-changing-write rule, one layer up from the merge."""
    gr_id = insert_gr(store._connect())
    set_state(store, gr_id, "approved", "dnorton", note="first")
    before = store.get_gr(gr_id)
    set_state(store, gr_id, "approved", "someone-else", note="second")
    after = store.get_gr(gr_id)
    assert after.reviewed_at == before.reviewed_at
    assert after.review_note == before.review_note
    assert after.reviewed_by == before.reviewed_by
    assert after.updated_at == before.updated_at


def test_set_state_refuses_to_run_without_a_reviewer(store):
    """Identity is the one thing in this schema that cannot be reconstructed
    after the fact, so there is no default and no placeholder."""
    gr_id = insert_gr(store._connect())
    for bad in ("", "   "):
        with pytest.raises(StateTransitionError, match="reviewer"):
            set_state(store, gr_id, "approved", bad)
    assert store.get_gr(gr_id).state == "draft"


def test_superseded_requires_and_records_its_successor(store):
    conn = store._connect()
    old = insert_gr(conn, state="approved")
    new = insert_gr(conn, gr_id="GR-01HQ2X0000000000000000001")
    with pytest.raises(StateTransitionError, match="successor"):
        set_state(store, old, "superseded", "dnorton")
    set_state(store, old, "superseded", "dnorton", superseded_by=new)
    row = store.get_gr(old)
    assert row.state == "superseded"
    assert row.superseded_by == new
    # Never `derived_from`, which means "the rules this rollup summarizes".
    assert row.derived_from is None


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


def test_approval_is_refused_while_an_error_finding_stands(store):
    gr_id = insert_gr(store._connect())
    store.replace_gr_findings(
        gr_id,
        [
            Finding(
                finding_id="V-CLASS-01",
                severity="ERROR",
                span="",
                message="rule_class is NULL.",
            )
        ],
    )
    store._connect().commit()
    with pytest.raises(ApprovalBlockedError) as exc:
        set_state(store, gr_id, "approved", "dnorton")
    assert "V-CLASS-01" in str(exc.value)
    assert "rule_class is NULL." in str(exc.value)
    assert [f.finding_id for f in exc.value.findings] == ["V-CLASS-01"]
    assert store.get_gr(gr_id).state == "draft"
    # ... and the same command succeeds once the finding is resolved.
    store.replace_gr_findings(gr_id, [])
    store._connect().commit()
    set_state(store, gr_id, "approved", "dnorton")
    assert store.get_gr(gr_id).state == "approved"


def test_a_warn_finding_never_blocks(store):
    gr_id = insert_gr(store._connect())
    store.replace_gr_findings(
        gr_id,
        [
            Finding(
                finding_id="V-STY-03",
                severity="WARN",
                span="4-9",
                message="implementation leakage.",
            )
        ],
    )
    store._connect().commit()
    set_state(store, gr_id, "approved", "dnorton")
    assert store.get_gr(gr_id).state == "approved"


def test_a_not_evaluated_error_never_blocks(store):
    """A check nobody could run is not a check that failed."""
    gr_id = insert_gr(store._connect())
    store.replace_gr_findings(
        gr_id,
        [
            Finding(
                finding_id="V-SLOT-01",
                severity="ERROR",
                span="",
                message="not evaluated: pattern is NULL.",
                evaluated=False,
            )
        ],
    )
    store._connect().commit()
    set_state(store, gr_id, "approved", "dnorton")
    assert store.get_gr(gr_id).state == "approved"


def test_a_null_pattern_row_inserts_and_is_refused_by_the_gate(store):
    """Nothing gates `draft`, and the gate names a precondition rather than
    letting a raw `CHECK constraint failed` reach a reviewer."""
    gr_id = insert_gr(
        store._connect(), rule_class=None, pattern=None, disposition="captured"
    )
    assert store.get_gr(gr_id).state == "draft"
    with pytest.raises(StateTransitionError) as exc:
        set_state(store, gr_id, "approved", "dnorton")
    assert "pattern" in str(exc.value)
    assert "CHECK" not in str(exc.value)
    # ... but nothing gates the other moves out of draft.
    set_state(store, gr_id, "rejected", "dnorton")
    assert store.get_gr(gr_id).state == "rejected"


def test_a_rule_the_extractor_left_undecided_can_be_approved_by_a_human(store):
    """The end-to-end proof that the un-approvable dead-end is closed."""
    gr_id = insert_gr(store._connect(), rule_class=None, pattern=None)
    with pytest.raises(StateTransitionError):
        set_state(store, gr_id, "approved", "dnorton")
    conn = store._connect()
    conn.execute(
        "UPDATE gr SET rule_class = 'behavioral', pattern = 'B-UNCOND' "
        "WHERE gr_id = ?",
        (gr_id,),
    )
    conn.commit()
    set_state(store, gr_id, "approved", "dnorton")
    assert store.get_gr(gr_id).state == "approved"


# --------------------------------------------------------------------------
# Findings storage
# --------------------------------------------------------------------------


def test_revalidating_deletes_findings_that_no_longer_fire(store):
    """Delete-then-insert, not an upsert: an upsert satisfies the UNIQUE
    constraint and still strands the stale rows."""
    gr_id = insert_gr(store._connect())
    store.replace_gr_findings(
        gr_id,
        [
            Finding(finding_id="V-VAG-01", severity="ERROR", span="4-8", message="a"),
            Finding(finding_id="V-VAG-03", severity="ERROR", span="9-11", message="b"),
        ],
    )
    store._connect().commit()
    store.replace_gr_findings(
        gr_id,
        [Finding(finding_id="V-VAG-01", severity="ERROR", span="4-8", message="a")],
    )
    store._connect().commit()
    assert [f.finding_id for f in store.list_gr_findings(gr_id)] == ["V-VAG-01"]


def test_the_same_record_level_finding_cannot_insert_twice(store):
    """`span` is `''` rather than NULL precisely so the UNIQUE tuple bites."""
    gr_id = insert_gr(store._connect())
    finding = Finding(finding_id="V-CLASS-01", severity="ERROR", span="", message="x")
    with pytest.raises(sqlite3.IntegrityError):
        store.replace_gr_findings(gr_id, [finding, finding])


# --------------------------------------------------------------------------
# The writer-set assertion
# --------------------------------------------------------------------------


def test_set_state_is_the_only_writer_of_gr_state():
    """No producer may write `gr.state` by any other route.

    Two properties, checked over the package source: no module writes the
    column with raw SQL except `knowledge_store.apply_gr_state`, and nothing
    calls that mechanical writer except `gr_state.set_state`. Step 9's
    `import_records` is the single declared exception and will have to be
    added here deliberately when it lands, which is the point.
    """
    src = Path(__file__).resolve().parents[1] / "src" / "legacylift_search"
    writers: set[str] = set()
    callers: set[str] = set()
    for path in sorted(src.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(_WRITES_GR_ROWS.search(sql) for sql in _sql_literals(text)):
            writers.add(path.name)
        if "apply_gr_state" in text:
            callers.add(path.name)
    assert writers == {"knowledge_store.py", "gr_export.py"}
    assert callers == {"knowledge_store.py", "gr_state.py"}


def test_the_gr_state_writer_census_cannot_be_evaded():
    """The census sees the write shapes a real second writer would use.

    This is the meta-test, and it exists because the census it guards was
    provably evadable. The superseded form was a raw-text regex for
    ``UPDATE gr SET ... state =``, which **missed three shapes, and one of
    them was already live**: `gr_export.py` writes the column through
    ``f"UPDATE gr SET {set_clause}"`` and ``f"INSERT INTO gr ({columns})"``,
    where the column names are built at runtime and so never appear as
    literal text beside ``state``. A source regex cannot see a
    dynamically-built SET clause, and that is the ordinary way to write a
    column-mapped update -- which is what the merge and `set-field` both do.

    So the census no longer looks for the *column*; it looks for any write
    statement targeting the `gr` table at all, and every module containing one
    must be named in the assertion above deliberately. That converts
    "invisible" into "must be declared", which is the property the plan's
    acceptance criterion actually wants: `set_state` and `import_records` are
    the complete set of writers of `gr.state`.

    It also no longer trips on prose. The scan reads real string literals via
    `ast` and skips docstrings, and comments never reach the AST at all -- so
    a comment or docstring *describing* the mechanism is not a writer. The
    superseded form flagged any file whose docstring merely contained the
    phrase, which cost one module its clearest wording.
    """
    evasions = {
        "adjacent string concatenation": (
            'conn.execute(\n    "UPDATE gr "\n    "SET state = ?",\n)'
        ),
        "upsert, the merge's own shape": (
            'conn.execute("INSERT INTO gr (gr_id, state) VALUES (?,?) "\n'
            '             "ON CONFLICT(gr_id) DO UPDATE SET state = ?")'
        ),
        "REPLACE INTO": (
            'conn.execute("REPLACE INTO gr (gr_id, state) VALUES (?,?)")'
        ),
        "runtime-built SET clause": (
            'conn.execute(f"UPDATE gr SET {set_clause} WHERE gr_id = ?", vals)'
        ),
        "runtime-built column list": (
            'conn.execute(f"INSERT INTO gr ({cols}) VALUES ({places})", vals)'
        ),
    }
    for label, code in evasions.items():
        assert any(_WRITES_GR_ROWS.search(sql) for sql in _sql_literals(code)), (
            f"the census would not see a writer using {label}"
        )

    # And the false positive that cost `gr_export.py` its clearest docstring:
    # prose describing a write path is not one.
    prose = '\'\'\'Why this is not an UPDATE gr SET ... state = write.\'\'\''
    assert not any(_WRITES_GR_ROWS.search(sql) for sql in _sql_literals(prose))
