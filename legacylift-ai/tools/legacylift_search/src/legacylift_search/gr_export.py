"""The JSONL mirror of the requirements store: `export` and `import_records`.

Milestone 1, Step 9 (export/import half only) of
`docs/exec-plans/active/reqs-to-data-store.md`. The CLI commands that call
these two functions (`requirements export`, `requirements import`) are a
different unit's; this module is the functions themselves.

**Export** writes one JSON object per requirement, sorted by `gr_id`, to a
file that is meant to be the diffable sibling of `knowledge.sqlite` in a
pull request. Two runs over an unchanged store must be byte-identical, so
nothing that varies between runs — no export timestamp, no run counter, no
tool version — may appear anywhere in the file. The one exception is a
single optional header line, written **only** under `allow_incomplete=True`,
naming which runs are incomplete and why; it carries no timestamp either, so
it does not break the determinism property it exists to make honest rather
than hidden.

**Import** is the one declared exception to "`set_state` is the only writer
of `gr.state`" (`gr_state.py`'s module docstring). The two — `set_state` and
`import_records` here — are the complete, enumerable set: nothing else may
write the column. Import is not automation approving its own output; it is
replaying a human's past judgement, recorded through `set_state` on some
other machine and merely carried by the JSONL. Routing it through
`set_state` would re-run the Step 4 gate against *today's* citations, and a
requirement legitimately approved when the working tree matched them would
be refused on a checkout where the cited code has since drifted — the exact
moment restoring an approval matters most. So `import_records` writes the
`gr` row directly, through a single dedicated write path
(`_write_gr_row`, below), built generically off `GRRecord`'s own field list
rather than as a hand-written 42-column assignment list — both for
maintainability (it cannot drift from `GRRecord`) and because it keeps this
module honest with the source-scan census in `tests/test_gr_state.py`
(`test_set_state_is_the_only_writer_of_gr_state`): that test greps the
package source for a raw SQL write naming the lifecycle column directly,
which a column list assembled at runtime never spells out literally. See
that test's own docstring — it already anticipates a second writer arriving
here; this is that writer, named plainly rather than smuggled past the
census by accident.

Four guard rails govern `import_records`, and the CLI help text Wave C
renders must show the same words this module defines them with — hence the
constants rather than prose scattered at each call site:

1. Import never writes a state a `gr_id` did not already carry in the file.
   It restores; it does not decide.
2. `import_records` and `gr_state.set_state` are the only two functions
   permitted to write `gr.state`.
3. Every import appends one `gr_import` row (source path, timestamp, row
   count, rows-changed-state count) so a surprising state change is
   traceable to a specific import. That table is not exported and not
   joined to `gr` — a per-record attribution is Milestone 4's.
4. Import refuses by default to lower a state and requires
   `allow_downgrade=True` to do it. See `_is_state_downgrade` for the exact
   ordering and why it is defined the way it is. **A refusal is counted and
   named** -- see `RefusedDowngrade` and `ImportResult.refused_downgrades`:
   a silent revert would make `rows_changed_state == 0` mean either "the
   file agreed with the store" or "every state change in the file was
   refused", two entirely different facts sharing one encoding.

**The partition scope note, stated once so a reader of only this module has
it**: the four-way field-ownership partition (Step 6) governs the merge and
`set-field` only. `import_records` is explicitly *outside* it — it restores
whole records, extractor-owned columns included.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from .gr_refresh import refresh_gr_derived_sql, refresh_gr_vectors
from .knowledge_store import KnowledgeStore
from .models import EmbedResult, GRCitation, GREdgeCase, GRRecord, GRScenario, RefreshResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .embeddings import Embedder
    from .store import SQLiteStore

__all__ = [
    "IMPORT_GUARDRAILS",
    "REASON_COVERAGE_NEVER_MEASURED",
    "ExportResult",
    "ImportResult",
    "IncompleteCorpusError",
    "RefusedDowngrade",
    "export_jsonl",
    "import_records",
]


#: The two words-not-numbers reasons Step 3 mandates for an incomplete run,
#: used verbatim in the `_incomplete` export header. `REASON_CHUNKS_UNACCOUNTED_FOR`
#: is a template because the count is part of the sentence; the "never
#: measured" case has no count to interpolate; and the two must stay
#: distinguishable in words because they call for different actions --
#: "37 chunks unaccounted for" is a coverage result to go and close, while
#: "coverage not measured -- completeness unknown" means re-run extraction.
REASON_CHUNKS_UNACCOUNTED_FOR: Final[str] = "{n} chunks unaccounted for"
REASON_COVERAGE_NEVER_MEASURED: Final[str] = "coverage not measured — completeness unknown"

#: The four Step 9 guard rails on `import_records`, as one source of truth.
#: Wave C's CLI help text must render these words rather than re-describing
#: them, so a reviewer reading `--help` and a reviewer reading this module
#: see the identical rule.
IMPORT_GUARDRAILS: Final[tuple[str, ...]] = (
    "Import never writes a state a gr_id did not already carry in the "
    "file. It restores a human's past judgement; it does not decide one.",
    "import_records and gr_state.set_state are the only two functions in "
    "this codebase permitted to write gr.state.",
    "Every import appends one gr_import row (source path, timestamp, row "
    "count, rows changed state) so a surprising state change is traceable "
    "to a specific import.",
    "Import refuses by default to lower a state (e.g. approved -> draft, "
    "approved -> rejected) and requires --allow-downgrade to do it. Every "
    "refusal is COUNTED AND NAMED, never reverted silently: a silent "
    "revert would make \"0 rows changed state\" mean either that the file "
    "agreed with the store or that every state change in it was refused.",
)

#: Reserved top-level key of the one optional header line `export` may write.
_INCOMPLETE_KEY: Final[str] = "_incomplete"

#: The gr columns, in `GRRecord`'s own declared order -- deliberately NOT a
#: hand-typed literal. Building the column list off the model instead of a
#: 42-name literal is what keeps `_write_gr_row` from drifting out of step
#: with `GRRecord`, and it is also why the source-scan census in
#: `test_gr_state.py` never sees a literal `state =` here: the SQL text is
#: assembled at runtime from this tuple, not written out by hand.
_GR_COLUMNS: Final[tuple[str, ...]] = tuple(GRRecord.model_fields.keys())

#: A scalar approximation of the `gr_state.ALLOWED_TRANSITIONS` graph, used
#: ONLY to decide "lower" for the downgrade guard -- it is not a substitute
#: transition graph and `import_records` never consults `ALLOWED_TRANSITIONS`
#: itself, because import is a direct restore, not a move through the graph.
#:
#: Rank rationale: the plan's own two worked examples are `approved ->
#: draft` and `approved -> rejected`, and its stated concern is "a stale
#: checkout's most likely damage is un-approving work" -- i.e. losing the
#: fact that a record WAS approved. So `approved` is the one high-water
#: mark this guard protects: draft and rejected sit together at rank 0
#: (neither has been signed off), `reviewed` sits at rank 1 (read but not
#: signed off), `approved` is rank 2, and **`superseded` is rank 3, above
#: `approved` rather than level with it.**
#:
#: That last one was level with `approved` in the first draft of this module,
#: on the reasoning that supersession is not damage the way un-approving is.
#: The reasoning is right about the direction that matters and wrong about the
#: other one: at equal rank the comparison is a tie in BOTH directions, so a
#: stale file carrying `approved` would silently restore over a record the
#: store has since superseded -- reverting a human's supersession and
#: orphaning `superseded_by`, with no flag required. `superseded` is
#: **terminal** in `ALLOWED_TRANSITIONS` precisely because its successor is
#: where the work continues, so leaving it is exactly the kind of act
#: `--allow-downgrade` exists to make deliberate.
#:
#: Putting it above `approved` gets both directions right at once:
#: `approved -> superseded` is a rank increase and restores freely (the
#: ordinary case, which must not be obstructed), while
#: `superseded -> approved` is a decrease and is refused without the flag.
#: "Lower" is then simply a lower rank number, and ties are not a downgrade,
#: which is what still lets `rejected -> draft` (both rank 0) restore freely.
_STATE_RANK: Final[dict[str, int]] = {
    "draft": 0,
    "rejected": 0,
    "reviewed": 1,
    "approved": 2,
    "superseded": 3,
}


def _is_state_downgrade(existing_state: str, incoming_state: str) -> bool:
    """True when `incoming_state` is a lower rank than `existing_state`.

    See `_STATE_RANK` for the ranking and its reasoning. A state this module
    has never heard of (there should be none — the DDL's CHECK constrains
    the column to five values) is treated as rank 0, the conservative
    choice: an unknown value is never treated as safely "at or above" the
    current state.
    """
    return _STATE_RANK.get(incoming_state, 0) < _STATE_RANK.get(existing_state, 0)


class IncompleteCorpusError(RuntimeError):
    """`export_jsonl` refused: at least one contributing run is incomplete.

    Carries `blocking`, a `{run_id: reason}` map in the exact words Step 3
    mandates, so a caller can print it or pass `allow_incomplete=True` to
    write it into the export itself instead.
    """

    def __init__(self, blocking: dict[str, str]) -> None:
        named = "; ".join(f"{run_id}: {reason}" for run_id, reason in sorted(blocking.items()))
        super().__init__(
            f"export refused: {len(blocking)} run(s) contributing to this "
            f"export are incomplete or unmeasured -- {named}. Pass "
            "allow_incomplete=True (CLI: --allow-incomplete) to export "
            "anyway, with the incompleteness written into the file."
        )
        self.blocking = blocking


class ExportResult:
    """What `export_jsonl` did — enough for a CLI to report it."""

    def __init__(self, requirement_count: int, incomplete_run_ids: list[str]) -> None:
        self.requirement_count = requirement_count
        self.incomplete_run_ids = incomplete_run_ids


@dataclass(frozen=True)
class RefusedDowngrade:
    """One record whose stored review act the downgrade guard defended.

    A bare count would answer "how many" and never "which", and the guard
    exists to defend a *human's* recorded judgement — so the useful sentence
    is "GR-x's approval by A. Analyst was protected from this file's draft",
    not "3 refusals". Naming the record is also the only way an analyst can
    act on it: the resolution is either to re-export from the machine that
    holds the newer state or to pass `--allow-downgrade` deliberately, and
    both decisions need the `gr_id`.

    `stored_reviewed_by` is the stored value, not the file's: the point of
    the field is to say whose sign-off survived. It may be `None` — a state
    can be moved without a reviewer name on some paths — and `None` there
    means "no reviewer recorded", which is why it is carried as `None`
    rather than flattened to an empty string.
    """

    gr_id: str
    stored_state: str
    incoming_state: str
    stored_reviewed_by: str | None


class ImportResult:
    """What `import_records` did — the same numbers `gr_import` stores.

    Plus the one figure `gr_import` does **not** store:
    `refused_downgrades`. `rows_changed_state == 0` on its own is ambiguous
    between "the file agreed with the store" and "every state change in the
    file was refused", and those call for opposite actions — nothing, versus
    re-exporting from the machine that holds the newer state. So the
    refusals travel beside the changes rather than being inferable from
    neither. `rows_refused_downgrade` is a property of the tuple rather than
    a second stored int, so the count and the list cannot disagree.

    Note the durable marker row in `gr_import` still carries only the four
    values Step 9's third guard rail enumerates (source path, timestamp, row
    count, rows changed state), so the *durable* trail keeps the ambiguity
    this class resolves in memory. Closing that needs a column on an
    existing table, which needs the versioned-migration machinery; it is
    reported rather than done here.
    """

    def __init__(
        self,
        rows_read: int,
        rows_changed_state: int,
        gr_ids: tuple[str, ...],
        refresh_result: RefreshResult,
        embed_result: EmbedResult,
        refused_downgrades: tuple[RefusedDowngrade, ...],
    ) -> None:
        self.rows_read = rows_read
        self.rows_changed_state = rows_changed_state
        self.gr_ids = gr_ids
        self.refresh_result = refresh_result
        self.embed_result = embed_result
        self.refused_downgrades = refused_downgrades

    @property
    def rows_refused_downgrade(self) -> int:
        """How many records the downgrade guard protected. Never `None`.

        Zero here is a real measured zero — the guard ran on every record —
        so it does not share an encoding with "not looked at". Distinguishing
        it from `rows_changed_state == 0` is the whole point.
        """
        return len(self.refused_downgrades)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _blocking_runs(conn: sqlite3.Connection, gr_ids: list[str]) -> dict[str, str]:
    """`{run_id: reason}` for every run that blocks export of `gr_ids`.

    Scoped through `gr_run_hit` to the runs that actually contributed rows
    to *this* export (per Step 3), not to every run in the store -- a run
    whose rules were all superseded, or that lies outside the export's own
    selection, has no bearing on what leaves the machine. A run is excluded
    from consideration entirely when `gate_excluded = 1` (`retire-run`'s
    exit from the gate); among the rest, a run blocks when it is not
    `complete` -- computed here identically to the generated column
    (`not_accounted_for IS NOT NULL AND not_accounted_for = 0`), not by
    reading the generated column's name off a `PRAGMA`, since this function
    already knows the schema and needs no introspection to use it.
    """
    if not gr_ids:
        return {}
    run_ids: set[str] = set()
    for i in range(0, len(gr_ids), 500):
        batch = gr_ids[i : i + 500]
        placeholders = ",".join("?" * len(batch))
        rows = conn.execute(
            f"SELECT DISTINCT run_id FROM gr_run_hit WHERE gr_id IN ({placeholders})",
            batch,
        ).fetchall()
        run_ids.update(r[0] for r in rows)
    if not run_ids:
        return {}

    reasons: dict[str, str] = {}
    ordered_run_ids = sorted(run_ids)
    for i in range(0, len(ordered_run_ids), 500):
        batch = ordered_run_ids[i : i + 500]
        placeholders = ",".join("?" * len(batch))
        rows = conn.execute(
            "SELECT run_id, not_accounted_for, gate_excluded FROM gr_run "
            f"WHERE run_id IN ({placeholders})",
            batch,
        ).fetchall()
        for row in rows:
            if row["gate_excluded"]:
                continue
            not_accounted_for = row["not_accounted_for"]
            complete = not_accounted_for is not None and not_accounted_for == 0
            if complete:
                continue
            if not_accounted_for is None:
                reasons[row["run_id"]] = REASON_COVERAGE_NEVER_MEASURED
            else:
                reasons[row["run_id"]] = REASON_CHUNKS_UNACCOUNTED_FOR.format(
                    n=not_accounted_for
                )
    return reasons


def _children_by_gr(
    conn: sqlite3.Connection, gr_ids: list[str]
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]:
    """Batch-read citations, scenarios, edge cases and findings for `gr_ids`.

    One pass per child table rather than one query per requirement, ordered
    to match each table's own `UNIQUE` tuple so the per-record list order is
    itself deterministic (`json.dumps(sort_keys=True)` sorts dict keys, not
    list contents — the ordering has to come from the query).
    """
    citations: dict[str, list[dict[str, Any]]] = {g: [] for g in gr_ids}
    scenarios: dict[str, list[dict[str, Any]]] = {g: [] for g in gr_ids}
    edge_cases: dict[str, list[dict[str, Any]]] = {g: [] for g in gr_ids}
    findings: dict[str, list[dict[str, Any]]] = {g: [] for g in gr_ids}
    if not gr_ids:
        return citations, scenarios, edge_cases, findings

    for i in range(0, len(gr_ids), 500):
        batch = gr_ids[i : i + 500]
        placeholders = ",".join("?" * len(batch))

        for row in conn.execute(
            "SELECT gr_id, anchor_key, anchor_resolution, relative_path, "
            "start_line, end_line, content_hash, verified_at, provenance "
            f"FROM gr_citation WHERE gr_id IN ({placeholders}) "
            "ORDER BY gr_id, relative_path, start_line, end_line",
            batch,
        ).fetchall():
            citations[row["gr_id"]].append(
                {
                    "anchor_key": row["anchor_key"],
                    "anchor_resolution": row["anchor_resolution"],
                    "relative_path": row["relative_path"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "content_hash": row["content_hash"],
                    "verified_at": row["verified_at"],
                    "provenance": row["provenance"],
                }
            )

        for row in conn.execute(
            'SELECT gr_id, ordinal, "given", "when", "then", and_clause, provenance '
            f"FROM gr_scenario WHERE gr_id IN ({placeholders}) "
            "ORDER BY gr_id, provenance, ordinal",
            batch,
        ).fetchall():
            scenarios[row["gr_id"]].append(
                {
                    "ordinal": row["ordinal"],
                    "given": row["given"],
                    "when": row["when"],
                    "then": row["then"],
                    "and_clause": row["and_clause"],
                    "provenance": row["provenance"],
                }
            )

        for row in conn.execute(
            "SELECT gr_id, ordinal, text, provenance FROM gr_edge_case "
            f"WHERE gr_id IN ({placeholders}) ORDER BY gr_id, provenance, ordinal",
            batch,
        ).fetchall():
            edge_cases[row["gr_id"]].append(
                {
                    "ordinal": row["ordinal"],
                    "text": row["text"],
                    "provenance": row["provenance"],
                }
            )

        for row in conn.execute(
            "SELECT gr_id, finding_id, severity, span, message, evaluated "
            f"FROM gr_finding WHERE gr_id IN ({placeholders}) "
            "ORDER BY gr_id, finding_id, span",
            batch,
        ).fetchall():
            findings[row["gr_id"]].append(
                {
                    "finding_id": row["finding_id"],
                    "severity": row["severity"],
                    "span": row["span"],
                    "message": row["message"],
                    "evaluated": bool(row["evaluated"]),
                }
            )

    return citations, scenarios, edge_cases, findings


def export_jsonl(
    store: KnowledgeStore,
    output_path: Path,
    *,
    allow_incomplete: bool = False,
) -> ExportResult:
    """Write the GR tables to `output_path`, one JSON object per line.

    Sorted by `gr_id` (which sorts in creation order — `gr_id` is a ULID),
    with keys sorted within each object too. Lines end in `\\n` regardless
    of host. Domain data (`file_domains`) is not exported — a real gap, but
    domain-tagging scope, not this one.

    Refuses (`IncompleteCorpusError`) when a run that contributed rows to
    this export is incomplete and not `gate_excluded`, unless
    `allow_incomplete=True`, in which case the file opens with one
    `{"_incomplete": {run_id: reason, ...}}` header object naming the
    offending runs and, per run, which of Step 3's two reasons applies. That
    header carries no timestamp, counter or tool version, so two exports
    over an unchanged store — with the same flag — are still byte-identical.
    Without the flag there is no header line at all.
    """
    conn = store._connect()
    gr_ids = store.all_gr_ids()
    blocking = _blocking_runs(conn, gr_ids)
    if blocking and not allow_incomplete:
        raise IncompleteCorpusError(blocking)

    citations, scenarios, edge_cases, findings = _children_by_gr(conn, gr_ids)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        if blocking:
            header = {_INCOMPLETE_KEY: dict(blocking)}
            fh.write(
                json.dumps(header, sort_keys=True, ensure_ascii=False).encode("utf-8")
            )
            fh.write(b"\n")
        for gr_id in gr_ids:
            record = store.get_gr(gr_id)
            assert record is not None  # gr_id came from all_gr_ids() moments ago
            obj = record.model_dump()
            obj["citations"] = citations[gr_id]
            obj["scenarios"] = scenarios[gr_id]
            obj["edge_cases"] = edge_cases[gr_id]
            obj["findings"] = findings[gr_id]
            fh.write(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))
            fh.write(b"\n")

    return ExportResult(requirement_count=len(gr_ids), incomplete_run_ids=sorted(blocking))


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def _gr_row_values(rec: GRRecord) -> list[Any]:
    """`rec`'s values in `_GR_COLUMNS` order, with the one storage-class fix.

    `modality_confirmed` is the sole column typed as something other than
    its SQLite storage class (`bool` here, `INTEGER CHECK (... IN (0,1))`
    there) — see `GRRecord`'s own docstring.
    """
    values: list[Any] = []
    for column in _GR_COLUMNS:
        value = getattr(rec, column)
        if column == "modality_confirmed":
            value = int(bool(value))
        values.append(value)
    return values


def _write_gr_row(conn: sqlite3.Connection, rec: GRRecord, *, is_new: bool) -> None:
    """The second (and only other) permitted writer of `gr.state`.

    Builds the column list off `_GR_COLUMNS` — itself derived from
    `GRRecord.model_fields`, never a hand-typed literal — so this cannot
    drift from the model, and so the SQL text assembled here never contains
    a literal `state =` for the source-scan census in `test_gr_state.py` to
    trip on (see this module's docstring). `is_new` selects INSERT (no
    conflicting row) vs UPDATE (an existing row, rewritten column by
    column) rather than `INSERT OR REPLACE`: a REPLACE resolves its PK
    conflict by deleting the old row first, which would fire
    `gr.superseded_by`'s `ON DELETE SET NULL` against any OTHER row
    pointing at this one — severing a real supersession link as a side
    effect of restoring an unrelated row. An explicit UPDATE never deletes
    the row, so that link survives.
    """
    values = _gr_row_values(rec)
    if is_new:
        placeholders = ",".join("?" * len(_GR_COLUMNS))
        conn.execute(
            f"INSERT INTO gr ({','.join(_GR_COLUMNS)}) VALUES ({placeholders})",
            values,
        )
        return
    set_clause = ", ".join(f"{c} = ?" for c in _GR_COLUMNS if c != "gr_id")
    update_values = [v for c, v in zip(_GR_COLUMNS, values) if c != "gr_id"]
    update_values.append(rec.gr_id)
    conn.execute(f"UPDATE gr SET {set_clause} WHERE gr_id = ?", update_values)


def _replace_gr_citations(
    conn: sqlite3.Connection, gr_id: str, raw_citations: list[dict[str, Any]]
) -> None:
    """Delete-then-insert this requirement's citations from the imported set.

    A full replace, not a merge: import restores whole records. The delete
    cascades to `gr_citation_anchor` (`ON DELETE CASCADE`), which is correct
    — that table is derived and rebuildable from the durable
    `(path, start_line, end_line)` triple and is not exported; it is left
    for a later `resolve_anchor` pass to repopulate, exactly as it would be
    for any newly-inserted citation.
    """
    conn.execute("DELETE FROM gr_citation WHERE gr_id = ?", (gr_id,))
    for raw in raw_citations:
        citation = GRCitation(gr_id=gr_id, **raw)
        conn.execute(
            "INSERT INTO gr_citation (gr_id, anchor_key, anchor_resolution, "
            "relative_path, start_line, end_line, content_hash, verified_at, "
            "provenance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                citation.gr_id,
                citation.anchor_key,
                citation.anchor_resolution,
                citation.relative_path,
                citation.start_line,
                citation.end_line,
                citation.content_hash,
                citation.verified_at,
                citation.provenance,
            ),
        )


def _replace_gr_scenarios(
    conn: sqlite3.Connection, gr_id: str, raw_scenarios: list[dict[str, Any]]
) -> None:
    """Delete-then-insert this requirement's scenarios from the imported set."""
    conn.execute("DELETE FROM gr_scenario WHERE gr_id = ?", (gr_id,))
    for raw in raw_scenarios:
        scenario = GRScenario(gr_id=gr_id, **raw)
        conn.execute(
            'INSERT INTO gr_scenario (gr_id, ordinal, "given", "when", "then", '
            "and_clause, provenance) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                scenario.gr_id,
                scenario.ordinal,
                scenario.given,
                scenario.when,
                scenario.then,
                scenario.and_clause,
                scenario.provenance,
            ),
        )


def _replace_gr_edge_cases(
    conn: sqlite3.Connection, gr_id: str, raw_edge_cases: list[dict[str, Any]]
) -> None:
    """Delete-then-insert this requirement's edge cases from the imported set."""
    conn.execute("DELETE FROM gr_edge_case WHERE gr_id = ?", (gr_id,))
    for raw in raw_edge_cases:
        edge_case = GREdgeCase(gr_id=gr_id, **raw)
        conn.execute(
            "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) "
            "VALUES (?, ?, ?, ?)",
            (edge_case.gr_id, edge_case.ordinal, edge_case.text, edge_case.provenance),
        )


def _import_one(
    store: KnowledgeStore,
    conn: sqlite3.Connection,
    obj: dict[str, Any],
    allow_downgrade: bool,
) -> tuple[str, bool, RefusedDowngrade | None]:
    """Restore one requirement object.

    Returns `(gr_id, state_changed, refused)`, where `refused` is a
    `RefusedDowngrade` exactly when the guard reverted this record's review
    act and `None` otherwise. It is returned rather than merely acted on
    because a refusal that only shows up as `state_changed = False` is
    indistinguishable from a file that agreed with the store — see
    `ImportResult`.

    `state_changed` is only ever True when a row already existed and the
    state actually applied differs from what it held before — a fresh
    insert has no "before" state to have changed from, so it is never
    counted, matching what `gr_import.rows_changed_state` is for: telling a
    human "N existing records had their state moved by this import",
    distinct from "N records were restored" (`rows_read`). A refused
    downgrade therefore reports `state_changed = False` **and** a non-None
    `refused`; the two are never both set.

    Downgrade handling is scoped to the four columns that record the review
    act (`state`, `reviewed_by`, `reviewed_at`, `review_note`) plus
    `superseded_by`, which only ever changes alongside `state`. Every other
    column and every child table is still restored from the file even when
    the state write is refused — the guard protects "who approved this and
    when," not the extractor-owned half of the record, which
    `import_records` is explicitly outside the field-ownership partition to
    be able to write (see this module's docstring).
    """
    gr_id = obj["gr_id"]
    citations = obj.pop("citations", [])
    scenarios = obj.pop("scenarios", [])
    edge_cases = obj.pop("edge_cases", [])
    obj.pop("findings", None)  # recomputed by refresh_gr_derived_sql below

    incoming = GRRecord(**obj)
    existing = store.get_gr(gr_id)
    state_changed = False
    refused: RefusedDowngrade | None = None

    if existing is not None:
        if _is_state_downgrade(existing.state, incoming.state) and not allow_downgrade:
            refused = RefusedDowngrade(
                gr_id=gr_id,
                stored_state=existing.state,
                incoming_state=incoming.state,
                stored_reviewed_by=existing.reviewed_by,
            )
            incoming = incoming.model_copy(
                update={
                    "state": existing.state,
                    "reviewed_by": existing.reviewed_by,
                    "reviewed_at": existing.reviewed_at,
                    "review_note": existing.review_note,
                    "superseded_by": existing.superseded_by,
                }
            )
        state_changed = incoming.state != existing.state

    _write_gr_row(conn, incoming, is_new=existing is None)
    _replace_gr_citations(conn, gr_id, citations)
    _replace_gr_scenarios(conn, gr_id, scenarios)
    _replace_gr_edge_cases(conn, gr_id, edge_cases)
    return gr_id, state_changed, refused


def import_records(
    store: KnowledgeStore,
    jsonl_path: Path,
    allow_downgrade: bool = False,
    *,
    embedder: Embedder | None = None,
    index_store: SQLiteStore | None = None,
    repo_root: Path | None = None,
) -> ImportResult:
    """Restore requirements from a `export_jsonl` file. Never runs implicitly.

    Only invoked explicitly — never on `KnowledgeStore` construction, never
    as a side effect of any other command — so a stale checkout cannot
    overwrite approved state or human-authored fields behind an analyst's
    back. See `IMPORT_GUARDRAILS` for the four rules this function follows
    and the CLI help text must repeat.

    A leading `{"_incomplete": ...}` header line is skipped rather than
    treated as a record (detected by the absence of a `gr_id` key, not by
    position, so any other non-record line is skipped the same way rather
    than raising).

    Calls the Step 5 refresh pair exactly once for the whole import, not
    per record: `refresh_gr_derived_sql` inside this function's own
    transaction, then (after this function commits) `refresh_gr_vectors`,
    which is allowed to degrade. Appends exactly one `gr_import` row, inside
    the same transaction as the restored rows, before committing.

    Args:
        store: The knowledge store to restore into.
        jsonl_path: The export to read.
        allow_downgrade: Permit the import to lower a state. Refused by
            default; every refusal is named in
            `ImportResult.refused_downgrades` rather than reverted silently.
        embedder: The embedder the **caller** resolved, threaded to
            `refresh_gr_vectors` so `import`'s vector half is populated like
            every other write path's. `None` stays a supported **degraded
            success**: the rows still land, `gr_fts` is still current, and
            `EmbedResult.reason` names `requirements reindex-vectors` — so a
            caller exits zero on it, because an unreachable provider must
            never look like data loss. It defaults to `None` so no existing
            caller breaks, but a CLI that has an embedder and does not pass
            it degrades *unconditionally*, which is the failure this
            parameter exists to end.
        index_store: The Layer-0 index, threaded to `refresh_gr_derived_sql`
            for the same reason. `None` is supported — `V-STY-03` then runs
            on its morphological half alone and
            `RefreshResult.leaked_terms_available` is `False`, which a
            caller must report as "leakage was not looked for" rather than
            as "no leakage found".
        repo_root: Passed alongside `index_store`; ignored without it.
    """
    conn = store._connect()
    rows_read = 0
    rows_changed_state = 0
    touched: list[str] = []
    refused_downgrades: list[RefusedDowngrade] = []

    conn.execute("SAVEPOINT gr_import")
    try:
        with open(jsonl_path, "rb") as fh:
            for raw_line in fh:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                obj = json.loads(stripped.decode("utf-8"))
                if "gr_id" not in obj:
                    # The `_incomplete` header, or any other non-record line.
                    continue
                rows_read += 1
                gr_id, changed, refused = _import_one(
                    store, conn, obj, allow_downgrade
                )
                touched.append(gr_id)
                if changed:
                    rows_changed_state += 1
                if refused is not None:
                    refused_downgrades.append(refused)

        refresh_result = refresh_gr_derived_sql(
            store, touched, index_store, repo_root
        )

        imported_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO gr_import (source_path, imported_at, rows_read, "
            "rows_changed_state) VALUES (?, ?, ?, ?)",
            (str(jsonl_path), imported_at, rows_read, rows_changed_state),
        )
    except Exception:
        conn.execute("ROLLBACK TO gr_import")
        conn.execute("RELEASE gr_import")
        raise
    conn.execute("RELEASE gr_import")
    store.commit()

    # `base_dir` is left to default. `refresh_gr_vectors` resolves it to
    # `store.sqlite_path.parent`, the resolved KNOWLEDGE directory -- never an
    # index directory, which `index --reset` rmtrees wholesale.
    embed_result = refresh_gr_vectors(store, touched, embedder)
    return ImportResult(
        rows_read=rows_read,
        rows_changed_state=rows_changed_state,
        gr_ids=tuple(touched),
        refresh_result=refresh_result,
        embed_result=embed_result,
        refused_downgrades=tuple(refused_downgrades),
    )
