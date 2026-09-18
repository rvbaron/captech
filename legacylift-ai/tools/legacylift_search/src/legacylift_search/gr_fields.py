"""The `gr` field-ownership partition.

Milestone 1, Steps 6 and 6a of `docs/exec-plans/active/reqs-to-data-store.md`.
`gr` carries exactly forty-two columns (Step 3), and exactly two write paths
contend for them: the extractor-driven merge (`requirements ingest`) and the
human-driven `set-field` command. Every column falls into exactly one of
four sets answering "who may write this column on those two paths":

| Set                     | The merge                          | `set-field` |
|--------------------------|-------------------------------------|--------------|
| `EXTRACTOR_OWNED_FIELDS` | writes                              | refuses      |
| `SHADOWED_FIELDS`        | writes only if live == its shadow   | accepts      |
| `HUMAN_WRITABLE_FIELDS`  | never                               | accepts      |
| `STORE_OWNED_FIELDS`     | never                               | refuses      |

**Why this module exists at all.** An earlier version of this plan kept two
hand-written lists — one in the merge, one in `set-field` — and they drifted:
`set-field` accepted eight fields while the merge protected five, and the
four-field gap between them was silent. Declaring the membership once, here,
as constants both write paths import, makes that drift a merge conflict
instead of a silent divergence. `set_state` and `import_records` sit outside
this partition entirely (Step 6's "state the partition's scope" paragraph):
`set_state` writes `STORE_OWNED_FIELDS` columns by a different mechanism, and
`import_records` restores whole rows rather than doing a field-mapped write.

**The four counts (14 / 3 / 9 / 16) are the only checksum on a forty-two
column partition maintained by hand**, per Step 6's "write the membership out
rather than leaving it to be classified" paragraph, and `test_gr_fields.py`
asserts them alongside the exhaustiveness property itself. A column added to
`gr` by any future milestone and left unclassified fails that test rather
than silently landing in whichever set happens not to complain — which is
the entire point of writing this module instead of four scattered `if`
statements.
"""

from __future__ import annotations

import sqlite3

__all__ = [
    "EXTRACTOR_OWNED_FIELDS",
    "HUMAN_WRITABLE_FIELDS",
    "STORE_OWNED_FIELDS",
    "INSERT_ONLY_DEFAULTS",
    "EXTRACTOR_FIELD_MAP",
    "UNMAPPED_KEYS",
    "get_gr_columns",
    "get_shadowed_fields",
    "set_field_accepted_fields",
]


# ----------------------------------------------------------------------
# EXTRACTOR_OWNED_FIELDS -- 14 columns, written by the merge, refused by
# set-field
# ----------------------------------------------------------------------
#
# Includes the three `_extracted` shadow columns themselves
# (`statement_extracted`, `assumptions_extracted`, `modality_extracted`):
# the extractor is their *only* writer (a human never edits a shadow), so
# they belong here rather than in a fifth set, and `set-field` refuses them
# by this membership rather than by a special case written against their
# name (Step 6, "the three `_extracted` shadows themselves sit in
# EXTRACTOR_OWNED_FIELDS").
EXTRACTOR_OWNED_FIELDS: frozenset[str] = frozenset(
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

# ----------------------------------------------------------------------
# HUMAN_WRITABLE_FIELDS -- 9 columns, never written by the merge, accepted
# by set-field
# ----------------------------------------------------------------------
#
# `rule_class` and `pattern` sit here even though the *value* always comes
# from the extractor (Step 6a stores them verbatim, never re-derives them):
# they need no shadow column because both are inputs to *both* dedupe keys,
# so an exact-key merge match implies they already agree, and an
# anchor-only match inserts a new row rather than updating one -- the merge
# can never change them (Step 6, "Neither needs a shadow column"). They are
# written by ingest on insert only, exactly like the two `INSERT_ONLY_DEFAULTS`
# below, and a human corrects an extractor's undecided call through
# `set-field` -- without that route a NULL `rule_class` or `pattern` was
# **permanently un-approvable** with no command able to fix it, which is the
# defect this membership closes.
#
# `disposition` and `modality_confirmed` are the two `INSERT_ONLY_DEFAULTS`
# (below): human-writable because a reviewer sets them, never merge-written
# because that would erase a reviewer's triage on every re-extraction.
#
# `rationale`, `fit_criterion`, `enforcement_level`, `confidence_intent` and
# `owner` are SME-only and extractor-*forbidden* (Step 3): any non-NULL value
# in them is human by construction, so they need no shadow either.
HUMAN_WRITABLE_FIELDS: frozenset[str] = frozenset(
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

# ----------------------------------------------------------------------
# STORE_OWNED_FIELDS -- 16 columns, never written by either contended path
# ----------------------------------------------------------------------
#
# Membership is not reachability (Step 6). Two of these have no *obvious*
# writer and are named here so a later reader does not rediscover the
# question: `superseded_by` is written by `set_state` on the `-> superseded`
# transition, and `derived_from` has **no writer at all in Milestone 1** --
# it is reserved for Milestone 2's rollups, and its permanent emptiness here
# is correct, not a gap. `reviewed_by`, `reviewed_at` and `review_note` are
# written by `set_state` on a state-changing move. `dedupe_key`,
# `dedupe_key_anchor_only`, `updated_at` and `extractor_payload` are written
# by the store itself on both the merge and (where applicable) `set-field`,
# despite sitting in this "neither path writes it" set -- Step 6 calls this
# out explicitly as four columns of store bookkeeping outside the
# partition's field-mapped scope, so the partition test's *membership*
# assertion is unaffected even though those four are not literally
# untouched in practice.
STORE_OWNED_FIELDS: frozenset[str] = frozenset(
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

# ----------------------------------------------------------------------
# INSERT_ONLY_DEFAULTS -- the two HUMAN_WRITABLE_FIELDS ingest defaults on
# insert only
# ----------------------------------------------------------------------
#
# Named apart from STORE_OWNED_FIELDS deliberately (Step 6a): these two sit
# in HUMAN_WRITABLE_FIELDS, ingest touches them only when a row is first
# inserted and never on a merge of an existing row, and folding them in with
# the store-assigned columns is exactly what makes the ownership assertion
# below come out wrong -- a merge that "protects" `disposition` because it
# looks store-owned would in fact just be it never being reached, for the
# wrong reason.
INSERT_ONLY_DEFAULTS: dict[str, object] = {
    "disposition": "captured",
    "modality_confirmed": False,
}

# ----------------------------------------------------------------------
# EXTRACTOR_FIELD_MAP -- incoming extractor rule-object key -> gr columns
# ----------------------------------------------------------------------
#
# **The value is a tuple, and that is forced, not stylistic** (Step 6a).
# `EXTRACTOR_OWNED_FIELDS | SHADOWED_FIELDS` is 17 columns, but only 14
# incoming keys reach them: `statement`, `assumptions` and `modality` each
# write *two* columns -- the live one and its shadow. Under a
# `dict[str, str]` the mandated assertion
# `set().union(*EXTRACTOR_FIELD_MAP.values()) == EXTRACTOR_OWNED_FIELDS |
# get_shadowed_fields(conn)` could never pass -- at most 14 values against
# 17 columns -- and the tempting repair, dropping the shadows from the
# right-hand side, removes exactly the columns whose writer is easiest to
# forget.
#
# `ruleClass` and `pattern` are deliberately **absent** from this map: Step
# 6a stores them verbatim outside the field-map mechanism (see
# `HUMAN_WRITABLE_FIELDS` above) because the merge can never contend for
# them, so they need no map entry at all -- only fields that are genuinely
# in play on a merge belong here.
EXTRACTOR_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "name": ("name",),
    "category": ("category",),
    "priority": ("priority",),
    "suspectedDefect": ("suspected_defect",),
    "smeQuestion": ("sme_question",),
    "parameters": ("parameters",),
    "confidence": ("confidence_extraction",),
    "plainEnglish": ("as_built",),
    "implementationNotes": ("implementation_notes",),
    "structuredBody": ("structured_body",),
    "structuredBodyType": ("structured_body_type",),
    "statement": ("statement", "statement_extracted"),
    "assumptions": ("assumptions", "assumptions_extracted"),
    "modality": ("modality", "modality_extracted"),
}

# ----------------------------------------------------------------------
# UNMAPPED_KEYS -- incoming keys deliberately left out of the column/child-
# row mapping
# ----------------------------------------------------------------------
#
# Step 3's completeness rule for `extractor_payload` is a three-way
# disjunction: every key of every ingested rule object must be mapped to a
# named column, **or** to a child-table row, **or** it must appear here,
# explicitly, as knowingly unpromoted. The first two branches already cover
# every key in the extended `RULES_SCHEMA` that Step 6a specifies:
#
#   * `EXTRACTOR_FIELD_MAP` (above) and the verbatim `ruleClass` / `pattern`
#     writes account for every column-mapped key.
#   * `given`, `when`, `then` and `and` land as `gr_scenario` rows;
#     `edgeCases` lands as `gr_edge_case` rows; `source` lands as
#     `gr_citation` rows (Step 6a, "What maps directly") -- all child-table
#     mapped, which is the disjunction's *second* branch, not this one.
#
# So this constant is empty today: nothing in the currently-specified
# schema is knowingly unpromoted. It stays declared, not deleted, because
# it is the reviewable record Step 3 asks for -- the moment a future
# `RULES_SCHEMA` field is deliberately left to live only in
# `extractor_payload` (rather than mapped), it is named here rather than
# silently passing the completeness test by omission.
UNMAPPED_KEYS: frozenset[str] = frozenset()


def get_gr_columns(conn: sqlite3.Connection) -> frozenset[str]:
    """Return `gr`'s column names, read from `PRAGMA table_info`.

    The one place this partition's exhaustiveness test gets its "the
    actual column list" input, so a column added to the DDL and left
    unclassified is caught against the schema itself rather than against a
    second hand-copied list.
    """
    return frozenset(row[1] for row in conn.execute("PRAGMA table_info('gr')"))


def get_shadowed_fields(conn: sqlite3.Connection) -> frozenset[str]:
    """Derive `SHADOWED_FIELDS` from the schema rather than declaring it.

    `{c for c in columns if c + "_extracted" in columns}`, per Step 6. This
    is strictly better than a fourth hand-kept list -- the entire mechanism
    this module exists to replace -- because it cannot drift from the shadow
    columns it describes: adding a new `<field>_extracted` column to `gr`
    grows this set automatically, with no second edit required here.
    """
    columns = get_gr_columns(conn)
    return frozenset(c for c in columns if f"{c}_extracted" in columns)


def set_field_accepted_fields(conn: sqlite3.Connection) -> frozenset[str]:
    """Columns `set-field` accepts: `HUMAN_WRITABLE_FIELDS | SHADOWED_FIELDS`.

    Per Step 6's table: the merge writes `SHADOWED_FIELDS` conditionally and
    `set-field` accepts it unconditionally (subject to the same shadow-write
    semantics `set-field` itself implements), while `EXTRACTOR_OWNED_FIELDS`
    and `STORE_OWNED_FIELDS` are refused by `set-field` either way.
    """
    return HUMAN_WRITABLE_FIELDS | get_shadowed_fields(conn)
