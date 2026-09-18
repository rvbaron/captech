"""Tests for `gr_body_schemas` (Milestone 1, Step 3).

Every test here fails before Step 3 (the module does not exist) and passes
after.

Two of them are acceptance criteria in their own right: a ragged decision table
must be refused at ingest rather than at DMN-conversion time, and the canonical
form of a body must be stable against key order, because it is the tier-1
`dedupe_key` discriminator and a discriminator that moves with formatting
re-keys a rule whose typed body never changed.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from legacylift_search.gr_body_schemas import (
    STRUCTURED_BODY_SCHEMAS,
    STRUCTURED_BODY_TYPES,
    canonical_structured_body,
    validate_structured_body,
)
from legacylift_search.knowledge_store import KnowledgeStore

DECISION_TABLE = {
    "hitPolicy": "FIRST",
    "inputs": [
        {"label": "Order status", "expression": "order.status", "typeRef": "string"},
        {"label": "Vendor", "expression": "order.vendorNo", "typeRef": "string"},
    ],
    "outputs": [{"label": "Action", "typeRef": "string"}],
    "rules": [
        {
            "inputEntries": ['"Open"', "not(null)"],
            "outputEntries": ['"recalculate"'],
            "annotation": "the normal path",
        },
        {"inputEntries": ['"Open"', "null"], "outputEntries": ['"reject"']},
    ],
}

STATE_TRANSITION = {
    "states": ["Open", "Closed", "Cancelled"],
    "initial": "Open",
    "transitions": [
        {"from": "Open", "to": "Closed", "trigger": "receiveAll"},
        {
            "from": "Open",
            "to": "Cancelled",
            "trigger": "cancel",
            "guard": "no receipts posted",
        },
    ],
}

FORMULA = {
    "scale": "currency (USD)",
    "meter": "recomputed on every statement run",
    "expression": "(old_balance + purchases - payments) * interest_rate / 10000",
    "variables": [
        {"name": "interest_rate", "meaning": "annual rate in basis points"},
        {"name": "payments", "meaning": "payments received in period", "unit": "USD"},
    ],
}

INVARIANT = {
    "expression": "a closed purchase order never carries an open balance",
    "scope": "PurchaseOrder",
    "notation": "prose",
}


def test_the_four_types_are_exactly_the_four_the_column_admits():
    """`STRUCTURED_BODY_TYPES` matches `gr.structured_body_type`'s CHECK.

    The map and the DDL must stay in step: a fifth type is a schema change,
    not an addition to this module. Asserted by driving the CHECK from the
    module's own key set, so the two cannot drift silently.
    """
    assert STRUCTURED_BODY_TYPES == {
        "decision_table",
        "state_transition",
        "formula",
        "invariant",
    }
    assert set(STRUCTURED_BODY_SCHEMAS) == STRUCTURED_BODY_TYPES

    with tempfile.TemporaryDirectory() as tmpdir:
        store = KnowledgeStore(Path(tmpdir) / "knowledge" / "knowledge.sqlite")
        try:
            conn = store._connect()
            base = {
                "gr_id": "GR-1",
                "kind": "business_rule",
                "statement": "x must y.",
                "statement_extracted": "x must y.",
                "modality": "requirement",
                "modality_extracted": "requirement",
                "dedupe_key": "dk1:0",
                "dedupe_key_anchor_only": "dka1:0",
                "extractor_payload": "{}",
                "created_at": "2026-09-01T00:00:00Z",
                "updated_at": "2026-09-01T00:00:00Z",
            }
            for ordinal, body_type in enumerate(sorted(STRUCTURED_BODY_TYPES)):
                row = {**base, "gr_id": f"GR-{ordinal}", "structured_body_type": body_type}
                conn.execute(
                    f"INSERT INTO gr ({', '.join(row)}) "
                    f"VALUES ({', '.join('?' for _ in row)})",
                    tuple(row.values()),
                )
            with pytest.raises(sqlite3.IntegrityError):
                row = {**base, "gr_id": "GR-X", "structured_body_type": "lookup_table"}
                conn.execute(
                    f"INSERT INTO gr ({', '.join(row)}) "
                    f"VALUES ({', '.join('?' for _ in row)})",
                    tuple(row.values()),
                )
        finally:
            store.close()


@pytest.mark.parametrize(
    ("body_type", "payload"),
    [
        ("decision_table", DECISION_TABLE),
        ("state_transition", STATE_TRANSITION),
        ("formula", FORMULA),
        ("invariant", INVARIANT),
    ],
)
def test_each_payload_shape_round_trips(body_type, payload):
    """All four Step 3 payload shapes validate and survive canonicalization.

    The shapes are fixed here rather than at implementation time because Step
    6a's extractor prompt asks for the same shapes, and a payload invented
    later cannot be asked for in advance.
    """
    body = validate_structured_body(body_type, payload)
    canonical = canonical_structured_body(body)
    revalidated = validate_structured_body(body_type, json.loads(canonical))
    assert canonical_structured_body(revalidated) == canonical


def test_decision_table_rule_count_is_the_step_ten_measurement():
    """`len(rules)` is exactly the per-table rule count Step 10 must measure.

    A consequence of the payload being a transcription of DMN 1.5's
    `<decisionTable>` rather than an invented format: the mandatory
    decision-table rule-collapse measurement becomes one query instead of a
    bespoke count.
    """
    body = validate_structured_body("decision_table", DECISION_TABLE)
    assert len(body.rules) == 2


@pytest.mark.parametrize(
    ("field", "entries"),
    [("inputEntries", ['"Open"']), ("outputEntries", ['"a"', '"b"'])],
)
def test_a_ragged_decision_table_is_refused(field, entries):
    """A row whose width differs from the column count is refused, by name.

    Enforced in the model rather than left to fail later at DMN conversion:
    Step 10's executability argument depends on a body converting without a
    second design step, and Step 6's ingest names the offending rule by its
    `offer_ordinal` when this raises. `ValidationError` is a `ValueError`
    subclass, so one `except ValueError` at the call site covers it.
    """
    payload = {
        **DECISION_TABLE,
        "rules": [{**DECISION_TABLE["rules"][0], field: entries}],
    }
    with pytest.raises(ValueError) as excinfo:
        validate_structured_body("decision_table", payload)
    assert field in str(excinfo.value)


def test_unknown_body_type_is_refused():
    """An unrecognised `structured_body_type` raises rather than passing through.

    One entry point rather than four so a caller cannot validate against the
    wrong schema, and so this case has exactly one home.
    """
    with pytest.raises(ValueError) as excinfo:
        validate_structured_body("lookup_table", {})
    assert "lookup_table" in str(excinfo.value)


def test_canonical_form_is_stable_against_key_order():
    """Two byte-different payloads for the same body canonicalize identically.

    This is the tier-1 `dedupe_key` discriminator, so it must not move with
    formatting: field order comes from the model, keys are sorted, separators
    carry no optional whitespace. A discriminator that moved with key order
    would re-key a rule whose typed body never changed and send it to review
    as a cold miss.
    """
    reordered = {
        "outputs": DECISION_TABLE["outputs"],
        "rules": DECISION_TABLE["rules"],
        "hitPolicy": DECISION_TABLE["hitPolicy"],
        "inputs": DECISION_TABLE["inputs"],
    }
    assert canonical_structured_body(
        validate_structured_body("decision_table", DECISION_TABLE)
    ) == canonical_structured_body(
        validate_structured_body("decision_table", reordered)
    )


def test_canonical_form_moves_when_the_body_really_changes():
    """A changed body changes the discriminator — the other half of stability.

    Without this, "stable" would be satisfiable by a constant.
    """
    changed = {**DECISION_TABLE, "hitPolicy": "UNIQUE"}
    assert canonical_structured_body(
        validate_structured_body("decision_table", DECISION_TABLE)
    ) != canonical_structured_body(
        validate_structured_body("decision_table", changed)
    )


def test_transition_from_keyword_uses_its_alias_in_both_directions():
    """`from` is accepted and re-emitted as `from`, not as a Python artifact.

    `from` is a Python keyword, so the field is `from_`; the alias keeps the
    stored JSON in the shape the extractor and DMN both speak, which matters
    because the canonical form is hashed.
    """
    body = validate_structured_body("state_transition", STATE_TRANSITION)
    assert body.transitions[0].from_ == "Open"
    assert '"from":"Open"' in canonical_structured_body(body)


def test_absent_initial_state_stays_none():
    """`initial: None` means "not stated" and is not filled in from `states`.

    The absent-versus-real rule applied inside a payload: guessing the first
    state would make an unstated initial state indistinguishable from a
    declared one.
    """
    payload = {k: v for k, v in STATE_TRANSITION.items() if k != "initial"}
    body = validate_structured_body("state_transition", payload)
    assert body.initial is None
    assert '"initial":null' in canonical_structured_body(body)


def test_unknown_keys_are_ignored_rather_than_aborting_an_ingest():
    """A stray key does not fail validation, because the payload is the backstop.

    `gr.extractor_payload` stores the incoming rule object verbatim, so an
    unrecognised key is never lost; aborting a several-hundred-rule ingest —
    hours of model time — over a field the typed body does not need would
    trade a real cost for no gain. Drift in `RULES_SCHEMA` is caught instead
    by Step 6a's mapping completeness test, which is the assertion built for
    that job.
    """
    body = validate_structured_body(
        "invariant", {**INVARIANT, "confidenceInNotation": "High"}
    )
    assert "confidenceInNotation" not in canonical_structured_body(body)


def test_invariant_notation_is_a_closed_three_value_set():
    """`notation` says how to read `expression`, and takes three values."""
    for notation in ("prose", "ocl", "sql"):
        validate_structured_body("invariant", {**INVARIANT, "notation": notation})
    with pytest.raises(ValueError):
        validate_structured_body("invariant", {**INVARIANT, "notation": "python"})


def test_hit_policy_is_dmns_own_five_value_set():
    """`hitPolicy` is DMN 1.5's own enum, not a set this plan invented."""
    for policy in ("UNIQUE", "FIRST", "PRIORITY", "ANY", "COLLECT"):
        validate_structured_body(
            "decision_table", {**DECISION_TABLE, "hitPolicy": policy}
        )
    with pytest.raises(ValueError):
        validate_structured_body(
            "decision_table", {**DECISION_TABLE, "hitPolicy": "LAST"}
        )
