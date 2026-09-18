"""Tests for the SPEC-1 validator (Milestone 1, Step 4 of `reqs-to-data-store.md`).

Every test here fails before Step 4 (`No module named
'legacylift_search.gr_validator'`) and passes after.

**The tests are driven from `NORMATIVE SPEC-1` §S1.10's ten worked examples,
not from the rest of the plan**, and that is the eighth review round's whole
lesson: a rule can be internally consistent, correctly cross-referenced, and
still not executable, and the way to notice is to walk the specification's own
examples through it by hand. The superseded keyword-anchored two-part split was
coherent, cited §S1.4 correctly, and fired two `ERROR`s on #3 — a statement
SPEC-1 marks conformant. `test_spec_s1_10_conformant_examples_produce_no_error`
is the assertion that fails under it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from legacylift_search.gr_validator import (
    CHECK_IDS,
    FIGURE1_PATTERNS,
    VALUE_PATTERNS,
    can_approve,
    find_keywords,
    split_slots,
    validate_statement,
)
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import Finding, GRRecord

# --------------------------------------------------------------------------
# Fixtures and helpers
# --------------------------------------------------------------------------

_MINIMAL_GR = {
    "gr_id": "GR-01HQ2X0000000000000000000",
    "kind": "business_rule",
    "statement": "",
    "statement_extracted": "",
    "modality": "requirement",
    "modality_extracted": "requirement",
    "dedupe_key": "dk1:0000000000000000",
    "dedupe_key_anchor_only": "dka1:0000000000000000",
    "extractor_payload": "{}",
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": "2026-09-01T00:00:00Z",
}


def gr(statement: str, **overrides) -> GRRecord:
    """A `GRRecord` carrying `statement` and nothing else that matters.

    The eleven NOT NULL columns are filled from one place so a later
    nullability change breaks here rather than in every test.
    """
    fields = {**_MINIMAL_GR, "statement": statement, "statement_extracted": statement}
    fields.update(overrides)
    return GRRecord(**fields)


def ids(findings: list[Finding]) -> set[str]:
    return {f.finding_id for f in findings}


def errors(findings: list[Finding]) -> set[str]:
    """Identifiers of findings that actually block approval."""
    return {f.finding_id for f in findings if f.severity == "ERROR" and f.evaluated}


def slot(statement: str, spans_attr, rule_class=None, pattern=None) -> str | None:
    spans = split_slots(statement, rule_class, pattern)
    span = getattr(spans, spans_attr)
    return None if span is None else statement[span[0] : span[1]]


#: SPEC-1 §S1.10's ten worked examples, verbatim, with the `rule_class` and
#: `pattern` each verdict assigns. The four ✅ rows and #10 (a WARN that
#: "lands, does not block") must produce zero blocking `ERROR`s.
S1_10 = {
    1: (
        "When the vendor number is absent, the Order Service must not accept "
        "the purchase order.",
        "behavioral",
        "B-PROHIB",
    ),
    2: (
        "The interest owed is to be computed as (old balance + purchases "
        "- payments) x interest rate / 10000.",
        "definitional",
        "D-COMPUTE",
    ),
    3: (
        "An inventory item is to be considered category 87 if its purchase "
        "cost is more than 1000.00 and less than 5000.00.",
        "definitional",
        "D-INFER",
    ),
    4: (
        "A closed purchase order never carries an open balance.",
        "definitional",
        "D-IMPOSS",
    ),
    5: ("The system shall validate the order.", "behavioral", "B-UNCOND"),
    6: ("An order always must have a customer.", "behavioral", "B-UNCOND"),
    7: ("The Order Service should reject the order.", "behavioral", "B-UNCOND"),
    8: (
        "It is permitted that an account balance is negative.",
        "behavioral",
        None,
    ),
    9: (
        "The Billing Service must recalculate the balance and notify the "
        "customer.",
        "behavioral",
        "B-UNCOND",
    ),
    10: (
        "When PUR-ORD-QTY is greater than zero, the Order Service must set "
        "WS-QTY-DUE.",
        "behavioral",
        "B-COND",
    ),
}

#: One conformant statement per `pattern`, taken from §S1.4's own template
#: table. Used to exercise `split_slots` across all ten.
S1_4_EXAMPLES = {
    "B-COND": (
        "When the purchase order status is Open, the Order Service must "
        "recalculate the quantity due within the same transaction.",
        "behavioral",
    ),
    "B-UNCOND": (
        "The Order Service must record a vendor number on each purchase order.",
        "behavioral",
    ),
    "B-PROHIB": (
        "When the vendor number is absent, the Order Service must not accept "
        "the purchase order.",
        "behavioral",
    ),
    "B-RESTRICT": (
        "A branch manager may grant a spot discount only if the rental is open.",
        "behavioral",
    ),
    "D-NEC": (
        "A rental always specifies exactly one car group.",
        "definitional",
    ),
    "D-IMPOSS": (
        "A closed purchase order never carries an open balance.",
        "definitional",
    ),
    "D-RESTRICT": (
        "An account balance can be negative only if the account is a credit "
        "account.",
        "definitional",
    ),
    "D-COMPUTE": (
        "The interest owed is to be computed as (old balance + purchases "
        "- payments) x interest rate / 10000.",
        "definitional",
    ),
    "D-INFER": (
        "An inventory item is to be considered category 87 if its purchase "
        "cost is more than 1000.00 and less than 5000.00.",
        "definitional",
    ),
    "D-CONST": (
        "The minimum payment allowed is to be fixed at 10.00.",
        "definitional",
    ),
}


# --------------------------------------------------------------------------
# The closed check set (§S1.6)
# --------------------------------------------------------------------------


def test_check_id_set_is_the_twenty_eight_spec_1_checks():
    """SPEC-1 §S1.6 fixes the check set at 28, breaking down 2/7/3/9/1/3/3.

    Fails if a check is invented or dropped, which §S1.6 forbids without
    amending the specification.
    """
    assert len(CHECK_IDS) == 28
    assert len(set(CHECK_IDS)) == 28
    counts = {}
    for cid in CHECK_IDS:
        counts[cid.rsplit("-", 1)[0]] = counts.get(cid.rsplit("-", 1)[0], 0) + 1
    assert counts == {
        "V-CLASS": 2,
        "V-KW": 7,
        "V-SLOT": 3,
        "V-VAG": 9,
        "V-SING": 1,
        "V-STY": 3,
        "V-ENF": 3,
    }


def test_every_emitted_identifier_is_in_the_closed_set():
    """No check may emit an identifier outside `CHECK_IDS`.

    Sweeps every §S1.10 and §S1.4 example plus a deliberately awful statement,
    so an invented identifier shows up here rather than in a corpus.
    """
    emitted: set[str] = set()
    for statement, rule_class, pattern in list(S1_10.values()):
        emitted |= ids(validate_statement(gr(statement, rule_class=rule_class,
                                             pattern=pattern)))
    for pattern, (statement, rule_class) in S1_4_EXAMPLES.items():
        emitted |= ids(
            validate_statement(gr(statement, rule_class=rule_class, pattern=pattern))
        )
    awful = (
        "It is required that the system shall be able to provide support for "
        "the best or most user friendly outcome, as appropriate, per ISO."
    )
    emitted |= ids(validate_statement(gr(awful)))
    assert emitted <= set(CHECK_IDS)


def test_severity_takes_exactly_two_values_across_every_example():
    """§S1.6 opens "Severity has exactly two values"; `evaluated` is not a third."""
    seen: set[str] = set()
    for statement, rule_class, pattern in S1_10.values():
        for f in validate_statement(
            gr(statement, rule_class=rule_class, pattern=pattern)
        ):
            seen.add(f.severity)
    assert seen <= {"ERROR", "WARN"}


def test_a_third_severity_value_is_refused_by_the_model():
    """`Finding` refuses an invented severity, so the closed set is structural."""
    with pytest.raises(ValueError, match="two SPEC-1"):
        Finding(finding_id="V-KW-01", severity="INFO", span="", message="x")


# --------------------------------------------------------------------------
# §S1.10's worked examples — the assertion the superseded split fails
# --------------------------------------------------------------------------


@pytest.mark.parametrize("number", [1, 2, 3, 4, 10])
def test_spec_s1_10_conformant_examples_produce_no_error(number):
    """Every statement §S1.10 marks conformant produces zero blocking ERRORs.

    #10 is included because §S1.10 marks it ⚠️ — "Lands, does not block" — so
    a WARN there is correct and an ERROR is not. #3 is the one that fails
    under the superseded keyword-anchored two-part split, which fires
    `V-SING-01` on its `and` and `V-SLOT-03` on a condition it cannot find.
    """
    statement, rule_class, pattern = S1_10[number]
    findings = validate_statement(gr(statement, rule_class=rule_class,
                                     pattern=pattern))
    assert errors(findings) == set(), [
        (f.finding_id, f.message) for f in findings if f.severity == "ERROR"
    ]


def test_spec_s1_10_example_3_fires_neither_v_sing_01_nor_v_slot_03():
    """Amendment A3, stated as the single assertion that pins it.

    §S1.10 #3 is a conformant `D-INFER` carrying an `and` in its `[Value]` and
    a `[Condition]` that trails the keyword. Both checks are written against
    `[Action]`, and `D-INFER` has none.
    """
    statement, rule_class, pattern = S1_10[3]
    found = ids(validate_statement(gr(statement, rule_class=rule_class,
                                      pattern=pattern)))
    assert "V-SING-01" not in found
    assert "V-SLOT-03" not in found


def test_spec_s1_10_example_10_warns_on_leakage_and_blocks_nothing():
    """#10's verdict is `V-STY-03` WARN via rubric items 2 and 5."""
    statement, rule_class, pattern = S1_10[10]
    findings = validate_statement(gr(statement, rule_class=rule_class,
                                     pattern=pattern))
    sty = [f for f in findings if f.finding_id == "V-STY-03"]
    assert sty, "PUR-ORD-QTY / WS-QTY-DUE are program symbols in `statement`"
    assert all(f.severity == "WARN" for f in sty)
    assert errors(findings) == set()


def test_spec_s1_10_example_5_shall_fires_v_kw_03():
    statement, rule_class, pattern = S1_10[5]
    found = errors(validate_statement(gr(statement, rule_class=rule_class,
                                         pattern=pattern)))
    assert "V-KW-03" in found


def test_spec_s1_10_example_6_fires_v_kw_02_the_disjointness_check():
    """"An order always must have a customer" — one keyword from each class.

    §S1.10 calls this "the single most likely LLM output".
    """
    statement, rule_class, pattern = S1_10[6]
    found = errors(validate_statement(gr(statement, rule_class=rule_class,
                                         pattern=pattern)))
    assert "V-KW-02" in found


def test_spec_s1_10_example_7_should_with_no_enforcement_level_fires_v_kw_05():
    statement, rule_class, pattern = S1_10[7]
    found = errors(validate_statement(gr(statement, rule_class=rule_class,
                                         pattern=pattern)))
    assert "V-KW-05" in found
    # ... and an enforcement level consistent with `should` clears it.
    cleared = errors(
        validate_statement(
            gr(statement, rule_class=rule_class, pattern=pattern,
               enforcement_level="guideline")
        )
    )
    assert "V-KW-05" not in cleared


def test_spec_s1_10_example_8_advice_fires_v_kw_06():
    """"It is permitted that ..." carries no rule keyword — SBVR cl. 12.1.4."""
    statement = "An account balance may be negative."
    found = errors(validate_statement(gr(statement, rule_class="behavioral")))
    assert "V-KW-06" in found


def test_spec_s1_10_example_9_two_actions_fires_v_sing_01():
    statement, rule_class, pattern = S1_10[9]
    found = errors(validate_statement(gr(statement, rule_class=rule_class,
                                         pattern=pattern)))
    assert "V-SING-01" in found


# --------------------------------------------------------------------------
# The keyword matcher
# --------------------------------------------------------------------------


def test_a_discontinuous_restricted_keyword_counts_once():
    """`may ... only` is ONE occurrence, so `V-KW-04` must not fire on it.

    Get this wrong and a conformant `B-RESTRICT` carries two keywords and is
    permanently un-approvable.
    """
    statement, rule_class = S1_4_EXAMPLES["B-RESTRICT"]
    matches = [m for m in find_keywords(statement) if m.is_rule_keyword]
    assert len(matches) == 1
    assert matches[0].canonical == "may ... only"
    assert len(matches[0].parts) == 2
    found = ids(validate_statement(gr(statement, rule_class=rule_class,
                                      pattern="B-RESTRICT")))
    assert "V-KW-04" not in found
    assert "V-KW-06" not in found  # it is a rule, not advice


def test_negative_keywords_match_before_their_positives():
    """`must not` must be tested before `must`, or `[Action]` starts with `not`."""
    statement, _, _ = S1_10[1]
    matches = [m for m in find_keywords(statement) if m.is_rule_keyword]
    assert [m.canonical for m in matches] == ["must not"]
    action = slot(statement, "action", "behavioral", "B-PROHIB")
    assert action == "accept the purchase order"


def test_bare_may_is_advice_and_warns_under_v_kw_07():
    statement = "A branch manager may grant a spot discount."
    matches = find_keywords(statement)
    assert [m.kind for m in matches] == ["advice"]
    found = validate_statement(gr(statement, rule_class="behavioral"))
    assert "V-KW-07" in ids(found)
    assert {f.severity for f in found if f.finding_id == "V-KW-07"} == {"WARN"}


# --------------------------------------------------------------------------
# split_slots across all ten patterns
# --------------------------------------------------------------------------


@pytest.mark.parametrize("pattern", sorted(S1_4_EXAMPLES))
def test_split_slots_finds_a_subject_on_all_ten_patterns(pattern):
    statement, rule_class = S1_4_EXAMPLES[pattern]
    spans = split_slots(statement, rule_class, pattern)
    assert spans.degraded is False
    assert spans.subject is not None
    assert statement[spans.subject[0] : spans.subject[1]].strip()


@pytest.mark.parametrize("pattern", sorted(S1_4_EXAMPLES))
def test_action_and_value_are_mutually_exclusive(pattern):
    """`action` on the seven Figure-1 patterns, `value` on the other three.

    Note the count: the ExecPlan's interface sketch says "the six Figure-1
    patterns", but §S1.4's own tables carry ten patterns of which three are
    the D5 deviations, so seven follow Figure 1. Recorded as a correction
    rather than implemented as six.
    """
    statement, rule_class = S1_4_EXAMPLES[pattern]
    spans = split_slots(statement, rule_class, pattern)
    if pattern in FIGURE1_PATTERNS:
        assert spans.action is not None
        assert spans.value is None
    else:
        assert pattern in VALUE_PATTERNS
        assert spans.value is not None
        assert spans.action is None
    assert len(FIGURE1_PATTERNS) + len(VALUE_PATTERNS) == 10


@pytest.mark.parametrize("pattern", ["B-RESTRICT", "D-RESTRICT", "D-INFER"])
def test_a_trailing_condition_is_found(pattern):
    """The half the superseded two-part split got wrong.

    A pre-keyword search finds nothing on these three, so `V-SLOT-03` fired an
    ERROR on every conformant instance.
    """
    statement, rule_class = S1_4_EXAMPLES[pattern]
    spans = split_slots(statement, rule_class, pattern)
    assert spans.condition is not None
    assert statement[spans.condition[0] : spans.condition[1]].strip()
    assert "V-SLOT-03" not in errors(
        validate_statement(gr(statement, rule_class=rule_class, pattern=pattern))
    )


def test_a_leading_comma_condition_is_found_on_b_cond():
    statement, rule_class = S1_4_EXAMPLES["B-COND"]
    assert (
        slot(statement, "condition", rule_class, "B-COND")
        == "When the purchase order status is Open"
    )
    assert slot(statement, "subject", rule_class, "B-COND") == "the Order Service"


def test_restricted_action_sits_between_the_two_keyword_parts():
    statement, rule_class = S1_4_EXAMPLES["B-RESTRICT"]
    assert slot(statement, "action", rule_class, "B-RESTRICT") == "grant a spot discount"


# --------------------------------------------------------------------------
# Degradation: not-evaluated rather than a guessed boundary
# --------------------------------------------------------------------------


def test_a_null_pattern_emits_the_three_v_slot_checks_not_evaluated():
    """A check nobody could run and a check that ran clean are different facts."""
    statement, rule_class, _ = S1_10[1]
    findings = validate_statement(gr(statement, rule_class=rule_class, pattern=None))
    slots = {f.finding_id: f for f in findings if f.finding_id.startswith("V-SLOT")}
    assert set(slots) == {"V-SLOT-01", "V-SLOT-02", "V-SLOT-03"}
    assert all(f.evaluated is False for f in slots.values())
    assert all(f.severity == "ERROR" for f in slots.values())
    assert all(f.span == "" for f in slots.values())
    # ... and a not-evaluated ERROR does not block approval.
    assert "V-SLOT-01" not in errors(findings)


@pytest.mark.parametrize("number", [5, 6])
def test_a_statement_that_does_not_match_its_pattern_produces_one_finding_not_four(
    number,
):
    """§S1.10 #5 (no keyword) and #6 (one keyword from each class).

    The `V-KW` ERROR names the real defect precisely; three more findings
    derived from a boundary that was never found would name the wrong problem
    three times over. This is the assertion that fails if `split_slots`
    guesses rather than degrading.
    """
    statement, rule_class, pattern = S1_10[number]
    findings = validate_statement(gr(statement, rule_class=rule_class,
                                     pattern=pattern))
    assert any(f.finding_id.startswith("V-KW") for f in findings if f.evaluated)
    slots = [f for f in findings if f.finding_id.startswith("V-SLOT")]
    assert len(slots) == 3
    assert all(f.evaluated is False for f in slots)


def test_a_null_pattern_still_locates_the_condition_structurally():
    """Amendment A3: `V-VAG-04`'s carve-out must survive on unclassified rows.

    Skip this and a conformant `or` inside a condition becomes an ERROR on the
    least-reviewed part of the corpus.
    """
    statement = (
        "When the order is open or on hold, the Order Service must record a "
        "vendor number."
    )
    spans = split_slots(statement, None, None)
    assert spans.degraded is True
    assert spans.condition is not None
    assert "or" in statement[spans.condition[0] : spans.condition[1]]
    assert "V-VAG-04" not in errors(validate_statement(gr(statement)))


def test_a_null_pattern_still_runs_v_vag_04_over_the_post_keyword_region():
    """The other half of A3: the `or` prohibition keeps its site."""
    statement = "The Order Service must accept the order or the quote."
    assert "V-VAG-04" in errors(
        validate_statement(gr(statement, rule_class="behavioral"))
    )


def test_a_null_rule_class_leaves_the_two_class_keyword_checks_undecided():
    """`V-KW-01`/`V-KW-02` are written against "its rule_class's set"."""
    statement, _, pattern = S1_10[1]
    findings = validate_statement(gr(statement, rule_class=None, pattern=pattern))
    assert "V-CLASS-01" in errors(findings)
    undecided = {f.finding_id for f in findings if not f.evaluated}
    assert {"V-KW-01", "V-KW-02"} <= undecided


# --------------------------------------------------------------------------
# The two mandatory carve-outs (§S1.6)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("pattern", ["D-NEC", "D-IMPOSS"])
def test_v_vag_08_exempts_the_definitional_rule_keyword(pattern):
    """Deviation D6. Without it the validator rejects every definitional rule."""
    statement, rule_class = S1_4_EXAMPLES[pattern]
    assert "V-VAG-08" not in errors(
        validate_statement(gr(statement, rule_class=rule_class, pattern=pattern))
    )


def test_v_vag_08_still_fires_on_a_non_keyword_totality_term():
    """The carve-out is scoped to the rule-keyword occurrence, nothing wider."""
    statement = "A rental always specifies all car groups."
    assert "V-VAG-08" in errors(
        validate_statement(gr(statement, rule_class="definitional", pattern="D-NEC"))
    )


@pytest.mark.parametrize("pattern", ["D-COMPUTE", "D-INFER", "D-CONST"])
def test_v_sty_01_exempts_the_three_special_definitional_keywords(pattern):
    """Deviation D5: they are required passives. Every computation rule fails
    without this carve-out."""
    statement, rule_class = S1_4_EXAMPLES[pattern]
    assert "V-STY-01" not in errors(
        validate_statement(gr(statement, rule_class=rule_class, pattern=pattern))
    )


def test_v_sty_01_still_fires_on_a_real_passive():
    assert "V-STY-01" in errors(
        validate_statement(gr("It is required that the vendor number is present."))
    )


def test_v_sty_02_fires_on_a_capability_statement():
    assert "V-STY-02" in errors(
        validate_statement(gr("The Order Service must be able to reject an order."))
    )


# --------------------------------------------------------------------------
# V-STY-03 — amendment A1
# --------------------------------------------------------------------------


def test_v_sty_03_fires_on_a_symbol_name_from_the_cited_file():
    """Rubric item 2, using Layer 0's own `symbols.name` — literally the check."""
    statement = "The Order Service must call recalcQtyDue on the purchase order."
    findings = validate_statement(
        gr(statement, rule_class="behavioral", pattern="B-UNCOND"),
        leaked_terms=frozenset({"recalcQtyDue"}),
    )
    sty = [f for f in findings if f.finding_id == "V-STY-03"]
    assert sty
    start, _, end = sty[0].span.partition("-")
    assert statement[int(start) : int(end)] == "recalcQtyDue"


def test_v_sty_03_works_with_an_empty_leaked_terms_set():
    """Empty is a supported state, not an error — the morphological fallback
    is a real check rather than a stub."""
    statement = "The Order Service must set order_qty_due on the purchase order."
    findings = validate_statement(
        gr(statement, rule_class="behavioral", pattern="B-UNCOND"),
        leaked_terms=frozenset(),
    )
    assert "V-STY-03" in ids(findings)


def test_v_sty_03_exempts_the_value_slot_of_d_infer():
    """Amendment A1's mandatory carve-out. §S1.10 #3 is conformant and carries
    *category 87* and *1000.00*; a naive magic-number test fires on it."""
    statement, rule_class, pattern = S1_10[3]
    findings = validate_statement(
        gr(statement, rule_class=rule_class, pattern=pattern),
        leaked_terms=frozenset({"category"}),
    )
    assert "V-STY-03" not in ids(findings)


def test_v_sty_03_never_blocks():
    """It stays a WARN even after the vocabulary layer ships (§S1.11 item 3)."""
    statement, rule_class, pattern = S1_10[10]
    findings = validate_statement(gr(statement, rule_class=rule_class,
                                     pattern=pattern))
    assert can_approve(findings)


# --------------------------------------------------------------------------
# Vagueness, enforcement and class
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "check,statement",
    [
        ("V-VAG-01", "The Order Service must pick the best vendor."),
        ("V-VAG-02", "The Order Service must present an easy to use summary."),
        ("V-VAG-03", "It must reject the order."),
        ("V-VAG-05", "The Order Service must provide support for vendors."),
        ("V-VAG-06", "The Order Service must be better than the prior release."),
        ("V-VAG-07", "The Order Service must notify the vendor if possible."),
        ("V-VAG-08", "The Order Service must reject every order."),
        ("V-VAG-09", "The Order Service must comply with the standard."),
    ],
)
def test_each_vagueness_class_fires_on_its_seed_term(check, statement):
    assert check in errors(
        validate_statement(gr(statement, rule_class="behavioral", pattern="B-UNCOND"))
    )


def test_v_vag_03_fires_only_on_a_bare_pronoun_subject():
    """Amendment A4: `V-VAG-03`'s site is the `[Subject]` slot.

    Its class is *vague pronouns*, so the words only count where they stand as
    the subject. Read as a seed list over the whole statement the check fired
    on 20% of the first real corpus, and none of those 26 findings was a
    pronoun without an antecedent in its own sentence.
    """
    bare = gr("It must reject the order.", rule_class="behavioral", pattern="B-UNCOND")
    assert "V-VAG-03" in errors(validate_statement(bare))


@pytest.mark.parametrize(
    "statement,pattern",
    [
        # `that` as a determiner -- the shape of 21 of the 26 measured findings.
        (
            "When another legal entity already holds the short name, a legal "
            "entity must not record that short name.",
            "B-PROHIB",
        ),
        # `that` as a relative pronoun.
        (
            "A meter station must not be flagged as the physical volume "
            "location for that point.",
            "B-PROHIB",
        ),
        # `it` as an object pronoun with its antecedent in the same sentence.
        ("The Order Service must reject it.", "B-UNCOND"),
    ],
)
def test_v_vag_03_is_silent_outside_the_subject_slot(statement, pattern):
    """A4's cost, stated as a test: a pronoun elsewhere no longer fires.

    The third case is the example this check was previously pinned on. It is
    kept here deliberately -- the amendment gave the check a narrower site,
    and that trade was made knowing this statement stops being flagged.
    """
    findings = validate_statement(
        gr(statement, rule_class="behavioral", pattern=pattern)
    )
    assert "V-VAG-03" not in errors(findings)


def test_v_vag_03_is_not_evaluated_when_no_template_locates_a_subject():
    """A3's rule, applied to A4's site: no site means not evaluated.

    A silent pass would make a check that never ran look verified -- the
    distinction this module keeps for the three `V-SLOT` checks.
    """
    degraded = gr("The order is validated by the service.", rule_class=None, pattern=None)
    findings = validate_statement(degraded)
    vag03 = [f for f in findings if f.finding_id == "V-VAG-03"]
    assert len(vag03) == 1
    assert vag03[0].evaluated is False


def test_v_vag_09_is_discharged_by_an_adjacent_number():
    """Amendment A2's test is "no adjacent number, date or part designator"."""
    statement = "The Order Service must comply with ISO 8601."
    assert "V-VAG-09" not in errors(
        validate_statement(gr(statement, rule_class="behavioral", pattern="B-UNCOND"))
    )


def test_v_vag_04_permits_or_inside_the_condition():
    """§S1.6's mandatory carve-out: cl. 5.2.5 Singular NOTE 2 permits multiple
    conditions."""
    statement = (
        "When the order is open or on hold, the Order Service must record a "
        "vendor number."
    )
    assert "V-VAG-04" not in errors(
        validate_statement(gr(statement, rule_class="behavioral", pattern="B-COND"))
    )


def test_v_vag_04_fires_on_or_inside_the_action():
    statement = "The Order Service must accept the order or the quote."
    assert "V-VAG-04" in errors(
        validate_statement(gr(statement, rule_class="behavioral", pattern="B-UNCOND"))
    )


def test_v_sing_01_does_not_fire_on_a_conjoined_object():
    """Conditions may be conjoined and so may objects; only actions may not."""
    statement = (
        "The Order Service must record a vendor number and a shipping address."
    )
    assert "V-SING-01" not in errors(
        validate_statement(gr(statement, rule_class="behavioral", pattern="B-UNCOND"))
    )


def test_v_class_02_warns_on_a_category_rule_class_mismatch():
    statement, rule_class, pattern = S1_10[1]
    findings = validate_statement(
        gr(statement, rule_class=rule_class, pattern=pattern, category="Calculation")
    )
    assert "V-CLASS-02" in ids(findings)
    assert {f.severity for f in findings if f.finding_id == "V-CLASS-02"} == {"WARN"}
    assert can_approve(findings)


def test_v_enf_01_refuses_an_enforcement_level_on_a_definitional_rule():
    statement, rule_class, pattern = S1_10[4]
    assert "V-ENF-01" in errors(
        validate_statement(
            gr(statement, rule_class=rule_class, pattern=pattern,
               enforcement_level="strict")
        )
    )


def test_v_enf_02_refuses_a_value_outside_the_six():
    statement, rule_class, pattern = S1_10[1]
    assert "V-ENF-02" in errors(
        validate_statement(
            gr(statement, rule_class=rule_class, pattern=pattern,
               enforcement_level="advisory")
        )
    )


def test_v_enf_03_is_review_progress_and_never_blocks():
    statement, rule_class, pattern = S1_10[1]
    findings = validate_statement(gr(statement, rule_class=rule_class,
                                     pattern=pattern))
    assert "V-ENF-03" in ids(findings)
    assert can_approve(findings)


def test_v_slot_02_rejects_all_four_placeholder_subjects():
    """All four are ERRORs, so reaching for "the application" gains nothing."""
    for placeholder in (
        "The system",
        "The application",
        "The software",
        "The program",
    ):
        statement = f"{placeholder} must record a vendor number."
        assert "V-SLOT-02" in errors(
            validate_statement(
                gr(statement, rule_class="behavioral", pattern="B-UNCOND")
            )
        ), placeholder


# --------------------------------------------------------------------------
# Determinism, spans, and the model/schema tie
# --------------------------------------------------------------------------


def test_findings_are_deterministic_across_runs():
    """Two validations of one record produce the same list in the same order."""
    statement, rule_class, pattern = S1_10[10]
    record = gr(statement, rule_class=rule_class, pattern=pattern)
    first = validate_statement(record)
    second = validate_statement(record)
    assert [f.model_dump() for f in first] == [f.model_dump() for f in second]


def test_every_span_is_either_empty_or_a_real_offset_range():
    """`span` is stored as "start-end" and is `''` for a record-level finding —
    never NULL, because it is inside `gr_finding`'s UNIQUE tuple."""
    for statement, rule_class, pattern in S1_10.values():
        for f in validate_statement(
            gr(statement, rule_class=rule_class, pattern=pattern)
        ):
            assert f.span == "" or re.fullmatch(r"\d+-\d+", f.span), f
            if f.span:
                start, _, end = f.span.partition("-")
                assert 0 <= int(start) < int(end) <= len(statement)


def test_gr_record_fields_match_the_gr_table_exactly(tmp_path):
    """The DDL is the definitive column list; this model must not drift from it.

    Fails the moment a column is added to `gr` without being added here, which
    is what makes the forty-two-column count load-bearing rather than
    decorative.
    """
    store = KnowledgeStore(Path(tmp_path) / "knowledge" / "knowledge.sqlite")
    try:
        columns = {
            row["name"]
            for row in store._connect().execute("PRAGMA table_info('gr')")
        }
    finally:
        store.close()
    assert set(GRRecord.model_fields) == columns
    assert len(columns) == 42


def test_can_approve_ignores_a_not_evaluated_error():
    findings = [
        Finding(
            finding_id="V-SLOT-01",
            severity="ERROR",
            span="",
            message="not evaluated: pattern is NULL",
            evaluated=False,
        )
    ]
    assert can_approve(findings) is True
    findings.append(
        Finding(finding_id="V-CLASS-01", severity="ERROR", span="", message="x")
    )
    assert can_approve(findings) is False
