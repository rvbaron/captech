"""Typed schemas for `gr.structured_body`, one per `structured_body_type`.

Milestone 1, Step 3 of `docs/exec-plans/active/reqs-to-data-store.md`.

`gr.structured_body` is **one JSON column discriminated by
`gr.structured_body_type`**, zero-or-one per requirement, and it is validated
against a per-type schema **on write**. The four schemas are kept together
here, expressed with the `pydantic` already in the dependency set rather than
by adding a JSON-Schema validator, because Step 6a's extractor prompt asks for
exactly these shapes and the two must agree *exactly*: a payload shape invented
at implementation time cannot be asked for in advance.

The four types, and where each shape comes from:

* `decision_table` — a transcription of **DMN 1.5's `<decisionTable>`
  element**, not a format this plan invented. `hitPolicy`,
  `input`/`inputExpression`, `output`, and `rule` with its
  `inputEntry`/`outputEntry` children are that element's own field set, so a
  body conforming to this schema serializes to DMN 1.5 XML mechanically. That
  is what "DMN-shaped" means, and it is why an ad-hoc table format is
  forbidden: Step 10's executability argument depends on the payload being
  convertible without a second design step. One consequence for that step:
  **`len(rules)` is exactly the per-table rule count Step 10 must measure**,
  so the mandatory measurement is one query rather than a bespoke count.
* `state_transition` — states plus guarded transitions.
* `formula` — **Planguage's `Scale` and `Meter`** plus the expression itself.
* `invariant` — a hand- or model-authored invariant. **Automatic invariant
  inference is out of scope**; do not add it here.

Two rules about how strictly these validate, both deliberate:

* **Ragged decision tables are refused.** Each `inputEntries` list must be the
  same length as `inputs`, and each `outputEntries` list the same length as
  `outputs`. Enforced in the model rather than left to fail later at DMN
  conversion time — Step 6's ingest transaction fails and names the offending
  rule by its `offer_ordinal`.
* **Unknown keys are ignored rather than rejected.** `gr.extractor_payload`
  stores the incoming rule object verbatim, so an unrecognised key is never
  lost; aborting a several-hundred-rule ingest (hours of model time) over a
  stray field the typed body does not need would trade a real cost for no
  gain. Drift in `RULES_SCHEMA` is caught instead by Step 6a's mapping
  completeness test, which is the assertion built for that job.
"""

from __future__ import annotations

import json
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "STRUCTURED_BODY_SCHEMAS",
    "STRUCTURED_BODY_TYPES",
    "DecisionTableBody",
    "DecisionTableInput",
    "DecisionTableOutput",
    "DecisionTableRule",
    "FormulaBody",
    "FormulaVariable",
    "InvariantBody",
    "StateTransition",
    "StateTransitionBody",
    "canonical_structured_body",
    "validate_structured_body",
]


# ----------------------------------------------------------------------
# decision_table (DMN 1.5 <decisionTable>)
# ----------------------------------------------------------------------


class DecisionTableInput(BaseModel):
    """One input column: DMN's `input` with its `inputExpression`."""

    label: str
    expression: str
    typeRef: str  # noqa: N815 - DMN's own attribute name, kept verbatim


class DecisionTableOutput(BaseModel):
    """One output column: DMN's `output`."""

    label: str
    typeRef: str  # noqa: N815 - DMN's own attribute name, kept verbatim


class DecisionTableRule(BaseModel):
    """One rule row: DMN's `rule` with its `inputEntry`/`outputEntry` children.

    `annotation` is optional, matching DMN's own optional description.
    """

    inputEntries: list[str]  # noqa: N815 - DMN's own element name
    outputEntries: list[str]  # noqa: N815 - DMN's own element name
    annotation: str | None = None


class DecisionTableBody(BaseModel):
    """A DMN-shaped decision table.

    The width check is the substance of this class rather than a nicety: a
    ragged table converts to invalid DMN, and the conversion is what Step 10's
    executability argument rests on, so the failure has to land at ingest —
    where the offending rule can still be named — and not months later.
    """

    model_config = ConfigDict(extra="ignore")

    hitPolicy: Literal["UNIQUE", "FIRST", "PRIORITY", "ANY", "COLLECT"]  # noqa: N815
    inputs: list[DecisionTableInput]
    outputs: list[DecisionTableOutput]
    rules: list[DecisionTableRule]

    @model_validator(mode="after")
    def _entries_match_column_counts(self) -> DecisionTableBody:
        """Refuse a ragged table, naming the row and both counts.

        Returns:
            Self, unchanged, when every row is the right width.

        Raises:
            ValueError: If any row's `inputEntries` or `outputEntries` length
                differs from the number of `inputs` or `outputs`.
        """
        expected_in = len(self.inputs)
        expected_out = len(self.outputs)
        for ordinal, rule in enumerate(self.rules):
            if len(rule.inputEntries) != expected_in:
                raise ValueError(
                    f"decision_table rule {ordinal} has "
                    f"{len(rule.inputEntries)} inputEntries but the table "
                    f"declares {expected_in} inputs"
                )
            if len(rule.outputEntries) != expected_out:
                raise ValueError(
                    f"decision_table rule {ordinal} has "
                    f"{len(rule.outputEntries)} outputEntries but the table "
                    f"declares {expected_out} outputs"
                )
        return self


# ----------------------------------------------------------------------
# state_transition
# ----------------------------------------------------------------------


class StateTransition(BaseModel):
    """One transition. `guard` is the optional condition on taking it.

    `from` is a Python keyword, so the field is `from_` with `from` as its
    alias. Populate by either name; serialization uses the alias, so the
    stored JSON carries DMN-adjacent `from`/`to` rather than a Python
    artifact.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    trigger: str
    guard: str | None = None


class StateTransitionBody(BaseModel):
    """A state machine: the state set, an optional initial state, transitions.

    `initial` is `str | None` and **None means "not stated"**, not "the first
    state" — the absent-versus-real rule this plan applies everywhere else.
    """

    model_config = ConfigDict(extra="ignore")

    states: list[str]
    initial: str | None = None
    transitions: list[StateTransition]


# ----------------------------------------------------------------------
# formula (Planguage Scale + Meter)
# ----------------------------------------------------------------------


class FormulaVariable(BaseModel):
    """One variable in a formula: its name, what it means, and its unit."""

    name: str
    meaning: str
    unit: str | None = None


class FormulaBody(BaseModel):
    """A computation. `scale` and `meter` are Planguage's, per Q3c.

    This is the typed form of what `gr.parameters` carries verbatim; the two
    coexist rather than one replacing the other.
    """

    model_config = ConfigDict(extra="ignore")

    scale: str
    meter: str
    expression: str
    variables: list[FormulaVariable] = Field(default_factory=list)


# ----------------------------------------------------------------------
# invariant
# ----------------------------------------------------------------------


class InvariantBody(BaseModel):
    """A hand- or model-authored invariant.

    `notation` says how to read `expression`. Automatic invariant inference is
    out of scope for this plan; this type exists for invariants somebody wrote.
    """

    model_config = ConfigDict(extra="ignore")

    expression: str
    scope: str
    notation: Literal["prose", "ocl", "sql"]


STRUCTURED_BODY_SCHEMAS: Final[dict[str, type[BaseModel]]] = {
    "decision_table": DecisionTableBody,
    "state_transition": StateTransitionBody,
    "formula": FormulaBody,
    "invariant": InvariantBody,
}
"""`structured_body_type` -> model. The keys are exactly the four values
`gr.structured_body_type`'s CHECK constraint admits, and the two must stay in
step: a fifth type is a schema change, not an addition here."""

STRUCTURED_BODY_TYPES: Final[frozenset[str]] = frozenset(STRUCTURED_BODY_SCHEMAS)
"""The four permitted `structured_body_type` values, derived from the map so it
cannot drift from it."""


def validate_structured_body(structured_body_type: str, payload: Any) -> BaseModel:
    """Validate one structured body against the schema its type selects.

    **This is the single entry point the ingest path calls.** It is one
    function rather than four so that a caller cannot validate against the
    wrong schema, and so the unknown-type case has exactly one home.

    Args:
        structured_body_type: One of `STRUCTURED_BODY_TYPES`.
        payload: The decoded JSON body (a mapping).

    Returns:
        The validated model. Its `canonical_structured_body` form is the
        tier-1 `dedupe_key` discriminator (Step 3).

    Raises:
        ValueError: If `structured_body_type` is not one of the four, or if
            the payload does not conform. `pydantic.ValidationError` is a
            subclass of `ValueError`, so one `except ValueError` at the ingest
            call site covers both — which is what lets Step 6 name the
            offending rule by its `offer_ordinal` and fail the whole ingest
            transaction.
    """
    schema = STRUCTURED_BODY_SCHEMAS.get(structured_body_type)
    if schema is None:
        raise ValueError(
            f"structured_body_type {structured_body_type!r} is not one of "
            f"{sorted(STRUCTURED_BODY_TYPES)}"
        )
    return schema.model_validate(payload)


def canonical_structured_body(body: BaseModel) -> str:
    """Serialize a validated body to its canonical string form.

    This is the **tier-1 `dedupe_key` discriminator** (Step 3), so it must be
    stable in a way that a plain `json.dumps` of the incoming payload is not.
    Three properties make it so, and each is load-bearing rather than tidy:
    field order comes from the model rather than from whatever order the
    extractor emitted, key order is sorted, and separators carry no optional
    whitespace. Two byte-different payloads describing the same table
    therefore produce the same discriminator, which is the whole point — a
    discriminator that moves with formatting would re-key a rule whose typed
    body never changed.

    Aliases are used (`from` rather than `from_`), so the canonical form is the
    shape the extractor and DMN both speak.

    Args:
        body: A model returned by `validate_structured_body`.

    Returns:
        A compact, key-sorted JSON string.
    """
    return json.dumps(
        body.model_dump(by_alias=True, mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
