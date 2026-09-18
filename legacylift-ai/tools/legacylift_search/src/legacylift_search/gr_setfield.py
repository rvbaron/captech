"""The `set-field` write path: the minimal human edit, as a function.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md` (the
five `set-field` paragraphs). Shaped like `gr_state.set_state` on purpose --
a callable function with no CLI dependency -- so the command wires it and the
behaviour is testable without a command.

**It is deliberately unpolished, and its scope is fixed by what Milestone 1
must prove rather than by what a reviewer would want.** It exists because two
of this milestone's acceptance criteria are otherwise unperformable: a human
edit to `statement` must survive re-extraction, and `stats` must report
SME-field fill rates as review progress -- and with no way to write those
fields the first test cannot be set up and the second is structurally zero
forever. Do not grow this into a review tool; that is Milestone 4's, and it
has its own plan at `docs/exec-plans/pending/reqs-review-ui.md`.

Four constraints here are load-bearing rather than incidental:

* **It accepts exactly `HUMAN_WRITABLE_FIELDS | SHADOWED_FIELDS`** -- twelve
  columns -- and refuses everything else **by membership** in
  `EXTRACTOR_OWNED_FIELDS` or `STORE_OWNED_FIELDS`, never by a hand-written
  denial list. So the three `_extracted` shadows and both dedupe keys are
  refused because of which set they are in, not because someone remembered
  them.
* **It never writes `gr.state`.** That is `set_state`'s, the approval gate
  lives there, and the writer census in `tests/test_gr_state.py` fails if a
  second route appears. `state` sits in `STORE_OWNED_FIELDS`, so the
  membership refusal above is what enforces it -- there is no special case.
* **Writing `rule_class` or `pattern` must not recompute either dedupe
  key.** Keys move only on extractor-owned writes (the Decision Log). These
  two are the only human-writable key inputs and so the only place that rule
  is easy to break; this module never imports `gr_keys` at all, and a test
  asserts both keys are byte-identical across such a write.
* **A write of the value the row already holds changes nothing** -- the same
  value-changing-write rule the merge and `set_state` apply, for the same
  reason: `updated_at` is in the JSONL export, so a no-op write that bumped
  it would show every touched record as modified in the next pull request.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Final

from .gr_fields import (
    EXTRACTOR_OWNED_FIELDS,
    STORE_OWNED_FIELDS,
    get_gr_columns,
    set_field_accepted_fields,
)
from .gr_refresh import refresh_gr_derived_sql, refresh_gr_vectors
from .knowledge_store import KnowledgeStore
from .models import EmbedResult, Finding, GRRecord, RefreshResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path

    from .embeddings import Embedder
    from .store import SQLiteStore

__all__ = [
    "COLUMN_ENUMS",
    "NOT_NULL_FIELDS",
    "SetFieldError",
    "SetFieldResult",
    "set_field",
]


#: The `CHECK (col IN (...))` value sets, for the accepted columns that carry
#: one. Refusing here rather than at the database is the point of the
#: paragraph that mandates it: a raw `CHECK constraint failed` names neither
#: the column nor the legal values, and this command's whole audience is a
#: human typing a value at a shell.
#:
#: **Hand-written and probed, not parsed.** A DDL parser for these would be
#: its own fragile thing; instead `tests/test_gr_setfield.py` probes each set
#: against the live schema -- every listed value is accepted by the database
#: and a value outside the set is refused by it -- so a drift between this
#: mapping and the DDL fails a test rather than surfacing as a `set-field`
#: that rejects a legal value.
COLUMN_ENUMS: Final[dict[str, tuple[str, ...]]] = {
    "rule_class": ("behavioral", "definitional"),
    "pattern": (
        "B-COND",
        "B-UNCOND",
        "B-PROHIB",
        "B-RESTRICT",
        "D-NEC",
        "D-IMPOSS",
        "D-RESTRICT",
        "D-COMPUTE",
        "D-INFER",
        "D-CONST",
    ),
    "enforcement_level": (
        "strict",
        "deferred",
        "pre-authorized",
        "post-justified",
        "override",
        "guideline",
    ),
    "confidence_intent": ("High", "Medium", "Low"),
    "disposition": ("captured", "not_applicable", "unreachable", "delegated"),
    "modality": ("requirement", "expectation"),
}

#: Accepted columns the schema declares `NOT NULL`. Clearing one is refused
#: rather than attempted, so the message names the column instead of the
#: constraint. `modality_confirmed` is `NOT NULL DEFAULT 0`, so it is here
#: too -- and note that `0` is a real value ("no human has confirmed the
#: modality"), not a way of clearing the column.
NOT_NULL_FIELDS: Final[frozenset[str]] = frozenset(
    {"statement", "modality", "modality_confirmed"}
)

#: The `disposition` values SPEC-1 S1.4's scoped CHECK accepts in place of a
#: `pattern` on an approved row. Not a second copy of the enum above: this is
#: the subset that satisfies one specific table CHECK.
_PATTERNLESS_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {"not_applicable", "unreachable", "delegated"}
)

#: What `--value` may say for the one boolean column, case-insensitively.
_BOOL_WORDS: Final[dict[str, int]] = {
    "0": 0,
    "1": 1,
    "false": 0,
    "true": 1,
    "no": 0,
    "yes": 1,
    "off": 0,
    "on": 1,
}


class SetFieldError(ValueError):
    """A `set-field` write this module refused, with the reason in the text."""


@dataclass
class SetFieldResult:
    """What `set_field` did -- enough for a CLI to report it.

    ``changed`` is `False` on the no-op path (the row already held this
    value), and on that path `updated_at` was not bumped, nothing was
    written, and neither half of the refresh pair ran. ``findings`` is then
    whatever the record already carried rather than a fresh validator run,
    which is stated because "no findings changed" and "the validator did not
    run" are different facts and `validated` says which.
    """

    gr_id: str
    field: str
    changed: bool
    old_value: Any
    new_value: Any
    validated: bool
    findings: list[Finding] = dataclass_field(default_factory=list)
    refresh: RefreshResult = dataclass_field(default_factory=RefreshResult)
    embed: EmbedResult = dataclass_field(default_factory=EmbedResult)

    @property
    def blocking_findings(self) -> list[Finding]:
        """The evaluated `ERROR` findings, i.e. what now blocks approval.

        A not-evaluated finding is a check that could not be decided, never
        one that failed (`gr_validator.can_approve` ignores exactly those),
        so it must not be reported as a violation this edit introduced.
        """
        return [f for f in self.findings if f.severity == "ERROR" and f.evaluated]


def _coerce(field_name: str, value: str | None) -> Any:
    """Turn a CLI-shaped string into the value the column stores.

    Only two columns need anything: `modality_confirmed` is INTEGER 0/1, and
    everything else is TEXT and passes through untouched. Coercion lives here
    rather than in the command so a caller wiring this from a test writes the
    same strings a human types.

    `None` means **write SQL NULL**, which is distinct from `''`. That
    distinction is not a convenience: `assumptions = ''` means "the agent
    considered assumptions and had none" while NULL means "the field never
    arrived", and a `set-field` that could only write one of them would make
    the second unreachable and the fill-rate figures wrong (see
    `KnowledgeStore.gr_field_fill_counts`).
    """
    if value is None:
        return None
    if field_name == "modality_confirmed":
        word = value.strip().lower()
        if word not in _BOOL_WORDS:
            raise SetFieldError(
                f"modality_confirmed takes a boolean; {value!r} is not one of "
                f"{sorted(_BOOL_WORDS)}. It is `NOT NULL DEFAULT 0`, and `0` "
                "means 'no human has confirmed the modality' -- a real value, "
                "not a way of clearing the column."
            )
        return _BOOL_WORDS[word]
    return value


def _validate_value(field_name: str, coerced: Any) -> None:
    """Nullability and enum membership for one column, before any write."""
    if coerced is None:
        if field_name in NOT_NULL_FIELDS:
            raise SetFieldError(
                f"{field_name} is NOT NULL in the schema and cannot be "
                "cleared. Give it a value."
            )
        return
    if field_name == "statement" and not str(coerced).strip():
        raise SetFieldError(
            "statement cannot be blank: it is the requirement. The schema "
            "would accept '' -- this refusal is set-field's, because a "
            "requirement with no text is not an edit anybody meant to make. "
            "To retire a requirement use `requirements set-state --to "
            "rejected`."
        )
    allowed = COLUMN_ENUMS.get(field_name)
    if allowed is not None and coerced not in allowed:
        raise SetFieldError(
            f"{coerced!r} is not a legal {field_name}; the schema's CHECK "
            f"accepts {list(allowed)}"
        )


def _check_row_constraints(record: GRRecord) -> None:
    """Re-evaluate `gr`'s three table CHECKs against the prospective row.

    Mirrors the DDL exactly -- see `KnowledgeStore._migrate_gr_tables` -- and
    runs against the record **as it would be after the write**, which is the
    only way to catch the cross-column cases. Two of the three are named in
    the plan as the worked examples of what must be refused at the command:
    an `enforcement_level` on a `definitional` rule, and a `pattern` whose
    prefix disagrees with `rule_class`.

    The third is the scoped SPEC-1 S1.4 check, and it is the one a reader
    would not expect `set-field` to be able to trip: clearing `pattern` on an
    **already-approved** row would violate it. That is refused here with the
    words the DDL comment gives, rather than as a `CHECK constraint failed`.
    """
    if (
        record.state == "approved"
        and record.pattern is None
        and record.disposition not in _PATTERNLESS_DISPOSITIONS
    ):
        raise SetFieldError(
            f"{record.gr_id} is `approved`, so it cannot be left with a NULL "
            "`pattern`: SPEC-1 S1.4 requires a notation template on every "
            "settled rule. Set a pattern, or move the record out of "
            "`approved` with `requirements set-state` first."
        )
    if record.rule_class is not None and record.pattern is not None:
        expected = "B-" if record.rule_class == "behavioral" else "D-"
        if not record.pattern.startswith(expected):
            raise SetFieldError(
                f"rule_class {record.rule_class!r} and pattern "
                f"{record.pattern!r} disagree: SPEC-1 S1.7 item 2 partitions "
                f"the ten patterns by class, so a {record.rule_class!r} rule "
                f"takes a {expected}* pattern. Set the other column first if "
                "you are changing both."
            )
    if record.rule_class == "definitional" and record.enforcement_level is not None:
        raise SetFieldError(
            "a `definitional` rule cannot carry an `enforcement_level` "
            f"(here {record.enforcement_level!r}): SPEC-1 S1.7 item 3 -- a "
            "definitional rule cannot be 'suggested but not enforced', "
            "because it cannot be violated. Clear enforcement_level, or make "
            "the rule `behavioral`."
        )


def _same(old: Any, new: Any) -> bool:
    """Would this write change the stored value?

    `None` is compared identically rather than by equality, so clearing an
    already-NULL column is a no-op and not a NULL-vs-NULL comparison that
    yields unknown -- the same trap `gr_shadow_is_unedited` disarms with
    SQLite `IS`. `modality_confirmed` arrives as `int` and is read back off
    `GRRecord` as `bool`, so both sides are normalized before comparing;
    without that every `--value 1` on an already-confirmed row would look
    like a change and bump `updated_at`.
    """
    if old is None or new is None:
        return old is None and new is None
    if isinstance(old, bool) or isinstance(new, bool):
        return bool(old) == bool(new)
    return old == new


def set_field(
    store: KnowledgeStore,
    gr_id: str,
    field_name: str,
    value: str | None,
    *,
    embedder: Embedder | None = None,
    index_store: SQLiteStore | None = None,
    repo_root: Path | None = None,
) -> SetFieldResult:
    """Write one human-owned column on one requirement.

    Args:
        store: The knowledge store holding the `gr` tables.
        gr_id: The requirement to edit.
        field_name: One of the twelve columns
            `gr_fields.set_field_accepted_fields(conn)` returns. Anything
            else is refused **by which ownership set it is in**, with a
            message naming that set -- so the refusal explains itself and
            does not have to be maintained.
        value: The new value as text, or **`None` meaning write SQL NULL**.
            `''` is a real, different value and is written as `''`; see
            `_coerce` for why both must be reachable.
        embedder: Passed to `refresh_gr_vectors`. **`None` is a supported
            degraded success**: the edit lands in SQLite and in `gr_fts`, and
            the record's `gr_statements` vector stays behind until
            `requirements reindex-vectors` runs. It must never be a reason a
            human's edit fails to record.
        index_store: Passed to `refresh_gr_derived_sql`, whose validator
            re-run uses it for `V-STY-03`'s `leaked_terms`. `None` means no
            index and the check falls back to its morphological half.
        repo_root: Threaded through for the same reason
            `refresh_gr_derived_sql` declares it.

    Returns:
        A `SetFieldResult`. On the no-op path `changed` is `False`,
        `validated` is `False`, and nothing at all was written.

    Raises:
        SetFieldError: unknown requirement, a refused column, a value outside
            the schema's CHECK, a cleared `NOT NULL` column, or a prospective
            row that violates one of `gr`'s three table CHECKs. **Nothing is
            written on any of these** -- every check runs before the update.

    **It re-runs the validator after a real write**, because editing
    `statement` changes its findings, and because setting the `pattern` that
    decides whether the three `V-SLOT` checks are evaluable changes them from
    `evaluated = 0` to a real verdict. That happens through the Step 5
    refresh pair in the one order every writer uses it in:
    `refresh_gr_derived_sql` inside the transaction, `store.commit()`, then
    `refresh_gr_vectors` -- once, for the one `gr_id`.
    """
    conn = store._connect()
    accepted = set_field_accepted_fields(conn)
    if field_name not in accepted:
        raise SetFieldError(_refusal_message(conn, field_name, accepted))

    record = store.get_gr(gr_id)
    if record is None:
        raise SetFieldError(f"no requirement {gr_id!r} in this store")

    coerced = _coerce(field_name, value)
    _validate_value(field_name, coerced)

    old_value = getattr(record, field_name)
    if _same(old_value, coerced):
        # The value-changing-write rule: no UPDATE, no `updated_at` bump, and
        # neither half of the refresh pair. Report the findings the record
        # already carries, and say the validator did not run.
        return SetFieldResult(
            gr_id=gr_id,
            field=field_name,
            changed=False,
            old_value=old_value,
            new_value=coerced,
            validated=False,
            findings=store.list_gr_findings(gr_id),
        )

    prospective = record.model_copy(update={field_name: coerced})
    _check_row_constraints(prospective)

    now = datetime.now(timezone.utc).isoformat()
    # **Exactly two columns.** `dedupe_key` and `dedupe_key_anchor_only` are
    # absent from this mapping and this module does not import `gr_keys`:
    # keys move only on extractor-owned writes, and `rule_class`/`pattern`
    # -- both key inputs -- are the only human-writable columns that could
    # tempt a recompute here.
    store.update_gr_row(gr_id, {field_name: coerced, "updated_at": now})

    refresh = refresh_gr_derived_sql(store, [gr_id], index_store, repo_root)
    store.commit()
    embed = refresh_gr_vectors(store, [gr_id], embedder=embedder)

    return SetFieldResult(
        gr_id=gr_id,
        field=field_name,
        changed=True,
        old_value=old_value,
        new_value=coerced,
        validated=True,
        findings=store.list_gr_findings(gr_id),
        refresh=refresh,
        embed=embed,
    )


def _refusal_message(conn: Any, field_name: str, accepted: frozenset[str]) -> str:
    """Explain a refusal by the ownership set the column belongs to.

    Four branches, and the first two are the ones the plan mandates: a
    refusal must be *by membership* so that a column added to `gr` and
    classified into either refused set is refused automatically, with no edit
    here. The fourth branch -- a real `gr` column in none of the four sets --
    cannot happen while `tests/test_gr_fields.py`'s exhaustiveness assertion
    passes, and says so rather than reporting the column as unknown.
    """
    if field_name in EXTRACTOR_OWNED_FIELDS:
        return (
            f"{field_name} is EXTRACTOR_OWNED and set-field refuses it: the "
            "merge writes it on every re-extraction, so a human edit here "
            "would be silently overwritten. The three `_extracted` shadow "
            "columns are in this set too, which is why they are refused."
        )
    if field_name in STORE_OWNED_FIELDS:
        extra = ""
        if field_name == "state":
            extra = (
                " `state` in particular is `requirements set-state`'s alone: "
                "the approval gate lives there, and a second write path is a "
                "way around it."
            )
        elif field_name in ("dedupe_key", "dedupe_key_anchor_only"):
            extra = (
                " A dedupe key moves only on an extractor-owned write; "
                "editing one by hand would silently re-partition the merge."
            )
        elif field_name in ("reviewed_by", "reviewed_at", "review_note"):
            extra = (
                " Those three record an act of review and are written "
                "together by `requirements set-state`."
            )
        return (
            f"{field_name} is STORE_OWNED and set-field refuses it.{extra}"
        )
    if field_name not in get_gr_columns(conn):
        return (
            f"{field_name!r} is not a column of `gr`. set-field accepts "
            f"{sorted(accepted)}."
        )
    return (
        f"{field_name} is a `gr` column in none of the four ownership sets, "
        "which means the partition in gr_fields.py has a gap; "
        "tests/test_gr_fields.py should already be failing. Classify it "
        "there rather than working around this message."
    )
