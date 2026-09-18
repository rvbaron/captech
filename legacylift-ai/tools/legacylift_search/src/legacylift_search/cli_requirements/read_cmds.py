"""The four read-only `requirements` commands: `list`, `show`, `search`, `stats`.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. This
module owns exactly these four registrations on `requirements_app` and no
others (the assignment is tabulated in this package's `__init__.py`):

* ``list`` -- `--state`, `--category`, `--kind`, `--subject`, `--disposition`,
  `--limit`, `--json`, and `--candidates` (the unresolved
  `gr_merge_candidate` pairs from Step 3; without it stage two of the merge
  is counted and never seen). Backed by `KnowledgeStore.query_gr` and
  `list_unresolved_gr_merge_candidates`.
* ``show`` -- one requirement with its citations, findings, structured body
  and data flow. Backed by `get_gr`, `list_gr_citations`, `list_gr_findings`
  and `list_gr_dataflow`.
* ``search`` -- FTS5 keyword search through `search_gr_fts`, and with a flag
  the semantic half over the `gr_statements` collection
  (`gr_refresh.open_gr_collection`). An under-populated collection must
  announce itself through `gr_refresh.describe_vector_shortfall` before any
  semantic result is reported, because zero candidates from a stale
  collection is indistinguishable from zero matches.
* ``stats`` -- counts by state, category and disposition (NULL kept as its
  own key, via `count_gr_by`), the absent-subject count apart from
  `llm_named` (`count_gr_null_subjects`), the SME fill figures
  (`gr_field_fill_counts`, whose three-number shape is documented there and
  whose `assumptions` numerator is **not** the same as the others'), the
  all-`excluded` count (`count_gr_all_citations_excluded`), the per-run
  intra-run collapse count (`intra_run_collapse_count`), the finding counts
  by severity with the `evaluated` split intact, and the data-flow block **in
  words** via `gr_dataflow.dataflow_status_text` -- never a rate, because the
  table is empty throughout Milestone 1 and a percentage over an empty set is
  the defect.

**Every command here is read-only and must probe before it opens.** Use
`_shared.open_knowledge_store`, which performs the plain `Path.exists()`
check house rule 2 requires: `KnowledgeStore.__init__` creates the database
and its parent directory, so constructing one to find out whether
requirements exist silently materializes an empty store.

Numbers that already exist must be read, not re-derived: `IngestResult`
carries the anchor-resolution counts, the per-extension `file` breakdown, the
subject-provenance counts, the discriminator tiers, `not_accounted_for` and
its `"40 of 512 shown"` rendering. `stats` reads the store's own columns for
the durable figures and never recomputes a run's numbers from the rules.

Four conventions hold across all four commands, and each of them is a
decision this module had to make because the plan names an observable rather
than a rendering:

1. **`ABSENT` (`"<absent>"`) is how a NULL prints, everywhere.** `count_gr_by`
   returns NULL under the `None` key deliberately, and the natural rendering
   -- `COALESCE(col, 'none')`, or an empty cell -- is the plan's recurring
   defect in display form. Angle brackets because no `CHECK` value in this
   schema can contain them, so the sentinel cannot collide with a real
   value. In `--json` the key is a real JSON `null` instead, which is why
   every grouped count serializes as a **list of `{"value", "count"}`
   objects**: a JSON object cannot carry a null key, and stringifying it
   would re-introduce exactly the collision the sentinel avoids.
2. **`UNMEASURED` (`"unmeasured"`) is how an absent *measurement* prints** --
   a NULL `gr_merge_candidate.similarity` (a `range_overlap` or `drift` pair
   was found structurally and never compared), a NULL
   `gr_run.not_accounted_for` (coverage was never taken), a vector count that
   could not be obtained. It is deliberately a different word from `ABSENT`:
   one means "this record has no value here", the other means "nobody
   looked".
3. **Every score is labelled with what it is.** Nothing in this repository
   pins `hnsw:space` (`ChromaVectorStore` sets `hnsw:sync_threshold` and
   `hnsw:batch_size` and no space), so the semantic half's number is an **L2
   distance on the pinned chromadb 1.5.9** and is printed as `distance=`
   with that caveat in the header -- never as a similarity, and never bare.
   `gr_merge_candidate.similarity` is a *stored* `1/(1+distance)`
   (`gr_ingest._raise_candidate`), so it prints as a similarity and carries
   the same caveat. Move the pin or set a space and both numbers mean
   something else; a labelled number says so and a bare one does not.
4. **Diagnostics go to stderr; only the answer goes to stdout.** House rule
   4, which exists because `list`, `show`, `search` and `stats` all take
   `--json`, and a shortfall warning on stdout corrupts a parsing caller as
   thoroughly as the resolved-path banner would.
"""

from __future__ import annotations

from typing import Annotated, Any, Optional

import typer

from legacylift_search.cli_requirements import requirements_app as requirements_app
from legacylift_search.cli_requirements import _shared

#: How a NULL column value renders in text output. See convention 1 above.
ABSENT = "<absent>"

#: How an absent *measurement* renders in text output. See convention 2.
UNMEASURED = "unmeasured"

#: The one sentence every displayed vector number carries. Nothing pins
#: `hnsw:space`, so the metric is chromadb 1.5.9's default (L2) and a later
#: pin move silently reinterprets every number derived from it.
_METRIC_CAVEAT = (
    "L2 distance on the pinned chromadb 1.5.9 -- no hnsw:space is set "
    "anywhere in this repository, so lower is closer but the scale is the "
    "installed default rather than a pinned one"
)

#: Columns whose fill numerator is `filled + empty`, not `filled`. Exactly
#: one column qualifies today and the reason is specific to it: Step 6a has
#: the extractor always emit `assumptions`, sending `""` where the code
#: assumes nothing beyond the statement, so `''` there means "considered, and
#: none" -- a real answer. Counting it as unfilled reports the exact opposite
#: of the truth for the one column whose empty string is meaningful.
_FILL_NUMERATOR_INCLUDES_EMPTY = frozenset({"assumptions"})

#: Columns for which no fill *rate* is reported at all, only the three
#: counts. `modality_confirmed` is `INTEGER NOT NULL DEFAULT 0`, so every row
#: is `filled` by construction and a rate over it is a guaranteed 100% that
#: measures nothing -- and its `0` is a fact ("no human has confirmed the
#: modality"), not an absence, so it must not be re-encoded as unfilled to
#: manufacture a number. `KnowledgeStore.gr_field_fill_counts` says the same
#: thing from the other side: "it is not a fill question".
_NO_FILL_RATE = frozenset({"modality_confirmed"})


# ----------------------------------------------------------------------
# Small shared renderers
# ----------------------------------------------------------------------


def _text(value: Any) -> str:
    """Render one column value for text output, NULL as `ABSENT`.

    `''` renders as `''` rather than as `ABSENT`, because an empty string is
    a value someone wrote and a NULL is not -- the same distinction
    `gr_field_fill_counts` keeps in three numbers.
    """
    if value is None:
        return ABSENT
    if value == "":
        return "''"
    return str(value)


def _measured(value: Any) -> str:
    """Render one *measurement* for text output, NULL as `UNMEASURED`.

    Convention 2, factored out because five columns need it: a NULL
    `gr_run.not_accounted_for`, and the four round-metadata columns
    (`rounds_run`, `round_cap`, `stop_reason`, `new_rules_in_final_round`)
    that are NULL for every run whose workflow predates emitting them. For
    all five, NULL means nobody looked -- and for
    `new_rules_in_final_round` a printed `0` would be an outright lie in the
    opposite direction, because `0` there is the "the final round found
    nothing new" signal.
    """
    if value is None:
        return UNMEASURED
    return str(value)


def _echo(line: str = "") -> None:
    """One line of the answer, on stdout."""
    typer.echo(line)


def _warn(line: str) -> None:
    """One line of diagnostic, on stderr. Never stdout (house rule 4)."""
    typer.echo(line, err=True)


def _rate(numerator: int, denominator: int) -> str:
    """`"3/12 (25%)"`, or `"0/0 (n/a)"` on an empty corpus. Never divides by 0."""
    if denominator == 0:
        return f"{numerator}/{denominator} (n/a)"
    return f"{numerator}/{denominator} ({100.0 * numerator / denominator:.0f}%)"


def _counts_json(counts: dict[str | None, int]) -> list[dict[str, Any]]:
    """A grouped count as JSON: a list of pairs, so NULL stays a real `null`.

    A `dict` cannot carry a null key in JSON, and `str(None)` would put the
    absent bucket in the same namespace as a real value named `"None"`. The
    list preserves `count_gr_by`'s ordering, which puts the `None` key last.
    """
    return [{"value": value, "count": count} for value, count in counts.items()]


def _echo_counts(title: str, counts: dict[str | None, int]) -> None:
    """Print one grouped count block, NULL as its own labelled row."""
    _echo(f"{title}:")
    if not counts:
        _echo("  (no rows)")
        return
    width = max(len(_text(value)) for value in counts)
    for value, count in counts.items():
        _echo(f"  {_text(value):<{width}}  {count}")


def _resolve_or_exit(
    repo_root: Optional[Any], config: Optional[Any], analysis_dir: Optional[Any]
) -> _shared.RequirementsPaths:
    """Resolve paths, turning a resolution failure into `Exit(1)` with a message.

    `resolve_paths` raises on a missing repository root or an unreadable
    manifest; a traceback out of a read-only query command is noise, and the
    message names the path it could not use.
    """
    try:
        return _shared.resolve_requirements_paths(repo_root, config, analysis_dir)
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        _warn(str(exc))
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# `list`
# ----------------------------------------------------------------------

_StateOption = Annotated[
    Optional[str],
    typer.Option("--state", help="Exact `gr.state` filter (draft, reviewed, ...)."),
]
_CategoryOption = Annotated[
    Optional[str], typer.Option("--category", help="Exact `gr.category` filter.")
]
_KindOption = Annotated[
    Optional[str], typer.Option("--kind", help="Exact `gr.kind` filter.")
]
_SubjectOption = Annotated[
    Optional[str], typer.Option("--subject", help="Exact `gr.subject` filter.")
]
_DispositionOption = Annotated[
    Optional[str],
    typer.Option("--disposition", help="Exact `gr.disposition` filter."),
]


@requirements_app.command("list")
def list_cmd(
    state: _StateOption = None,
    category: _CategoryOption = None,
    kind: _KindOption = None,
    subject: _SubjectOption = None,
    disposition: _DispositionOption = None,
    candidates: Annotated[
        bool,
        typer.Option(
            "--candidates",
            help=(
                "List the unresolved gr_merge_candidate pairs instead of "
                "requirements. Stage two of the merge NEVER auto-merges, so "
                "these pairs are the whole of its output and this is the "
                "only way to see them."
            ),
        ),
    ] = False,
    limit: _shared.LimitOption = None,
    as_json: _shared.JsonOption = False,
    repo_root: _shared.RepoRootOption = None,
    config: _shared.ConfigOption = None,
    analysis_dir: _shared.AnalysisDirOption = None,
) -> None:
    """List requirements, or (with `--candidates`) unresolved merge pairs.

    Every filter is an exact match AND-ed with the others, and **a filter
    left off means "do not filter", never "match NULL"** -- `query_gr` cannot
    express `IS NULL` on purpose, and `requirements stats` answers the NULL
    question through `count_gr_by`, which keeps NULL as its own bucket.

    `--candidates` is a **mode switch, not another filter.** The five filters
    are `gr` columns and a candidate row is a pair of `gr_id`s, so combining
    them is refused rather than silently ignored: quietly dropping a filter
    would let a reviewer read a full candidate list as a filtered one and
    conclude a rule has no near-duplicates.
    """
    if candidates:
        offered = [
            name
            for name, value in (
                ("--state", state),
                ("--category", category),
                ("--kind", kind),
                ("--subject", subject),
                ("--disposition", disposition),
            )
            if value is not None
        ]
        if offered:
            _warn(
                "--candidates lists gr_merge_candidate pairs, which carry no "
                f"{', '.join(offered)}; re-run it without those filters (they "
                "are `gr` columns and a candidate is a pair of gr_ids). "
                "Refused rather than ignored, so a full list is never read "
                "as a filtered one."
            )
            raise typer.Exit(code=1)

    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    store = _shared.open_knowledge_store(paths)
    try:
        if candidates:
            _list_candidates(store, limit=limit, as_json=as_json)
        else:
            _list_requirements(
                store,
                state=state,
                category=category,
                kind=kind,
                subject=subject,
                disposition=disposition,
                limit=limit,
                as_json=as_json,
            )
    finally:
        store.close()


def _list_requirements(
    store: Any,
    *,
    state: Optional[str],
    category: Optional[str],
    kind: Optional[str],
    subject: Optional[str],
    disposition: Optional[str],
    limit: Optional[int],
    as_json: bool,
) -> None:
    """The default `list` body: `query_gr` plus a projection.

    `--json` emits a projection rather than all forty-two columns:
    `extractor_payload` is the verbatim backstop and is routinely larger than
    every other column combined, so a listing that carried it would be
    unreadable and slow for the one job a listing has. `show --json` is the
    lossless form.

    The projection is a triage set -- identity, classification, review state
    and `priority` -- and is what a caller filters and counts on. Anything
    that renders a requirement in full (a Rule Card's `Source`, `Confidence`,
    scenario, parameters or edge cases) belongs to `show --json`, not here.
    """
    try:
        records = store.query_gr(
            state=state,
            category=category,
            kind=kind,
            subject=subject,
            disposition=disposition,
            limit=limit,
        )
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(code=1)

    filters = {
        "state": state,
        "category": category,
        "kind": kind,
        "subject": subject,
        "disposition": disposition,
        "limit": limit,
    }

    if as_json:
        _shared.emit_json(
            {
                "filters": filters,
                "count": len(records),
                "requirements": [
                    {
                        "gr_id": r.gr_id,
                        "kind": r.kind,
                        "name": r.name,
                        "state": r.state,
                        "subject": r.subject,
                        "subject_provenance": r.subject_provenance,
                        "category": r.category,
                        "disposition": r.disposition,
                        "rule_class": r.rule_class,
                        "pattern": r.pattern,
                        # `priority` is here because `/modernize-brief` builds
                        # its Behavior Contract from the P0 rules and reads
                        # them from this listing. It is a 2-character column,
                        # not the `extractor_payload` bulk the projection
                        # exists to exclude, so carrying it costs nothing and
                        # its absence cost the brief its whole P0 set.
                        "priority": r.priority,
                        "statement": r.statement,
                    }
                    for r in records
                ],
            }
        )
        return

    if not records:
        # An empty store, and an empty filtered result, are both normal
        # states rather than errors -- but they are different sentences, so
        # the reader can tell "nothing is here" from "nothing matched".
        active = {k: v for k, v in filters.items() if v is not None and k != "limit"}
        if active:
            _echo(
                "no requirements match "
                + ", ".join(f"{k}={v!r}" for k, v in sorted(active.items()))
            )
        else:
            _echo("no requirements in the store.")
        return

    for record in records:
        _echo(
            f"{record.gr_id}  {record.state:<10}  "
            f"{_text(record.subject)}/{_text(record.subject_provenance)}  "
            f"{_text(record.category)}"
        )
        _echo(f"    {record.statement}")
    _echo()
    _echo(f"{len(records)} requirement(s).")


def _list_candidates(store: Any, *, limit: Optional[int], as_json: bool) -> None:
    """`list --candidates`: the unresolved stage-two pairs, actionably rendered.

    Both `gr_id`s, the reason and the similarity, because a reviewer's job
    here is to decide `merged` or `distinct` and none of those four can be
    skipped to do it.

    **A NULL `similarity` renders as `UNMEASURED`, never as `0.0`.** Only a
    `'semantic'` candidate carries a score at all; `'range_overlap'` and
    `'drift'` were found by line-range intersection with no vector
    comparison, and `0.0` there would read as "compared, and found maximally
    dissimilar" -- the opposite of what happened, and on the pair most likely
    to be a real duplicate.
    """
    try:
        pairs = store.list_unresolved_gr_merge_candidates(limit)
    except ValueError as exc:
        _warn(str(exc))
        raise typer.Exit(code=1)

    if as_json:
        _shared.emit_json(
            {
                "count": len(pairs),
                "similarity_metric": (
                    "stored as 1/(1+distance) by gr_ingest; " + _METRIC_CAVEAT
                ),
                "candidates": [
                    {
                        "gr_id_existing": p.gr_id_existing,
                        "gr_id_incoming": p.gr_id_incoming,
                        "reason": p.reason,
                        "similarity": p.similarity,
                        # Redundant with `similarity is None` on purpose: a
                        # consumer that reads a missing key as zero cannot
                        # misread an explicit false.
                        "similarity_measured": p.similarity is not None,
                        "run_id": p.run_id,
                        "resolution": p.resolution,
                    }
                    for p in pairs
                ],
            }
        )
        return

    if not pairs:
        _echo(
            "no unresolved merge candidates. Note what this does NOT prove: "
            "stage two's semantic half only sees requirements that have a "
            "vector, so run `requirements stats` and check the "
            "gr_statements shortfall before reading this as 'no near "
            "duplicates exist'."
        )
        return

    _echo(f"{len(pairs)} unresolved merge candidate pair(s).")
    _echo(f"similarity is 1/(1+distance) as stored by ingest ({_METRIC_CAVEAT}).")
    _echo(
        f"{UNMEASURED} means no vector comparison happened at all: only "
        "'semantic' pairs carry a score, and a range_overlap or drift pair "
        "is not a dissimilar one."
    )
    _echo()
    for p in pairs:
        score = UNMEASURED if p.similarity is None else f"{p.similarity:.4f}"
        _echo(
            f"  {p.gr_id_existing}  <->  {p.gr_id_incoming}  "
            f"reason={p.reason:<14} similarity={score}  "
            f"run={_text(p.run_id)}"
        )


# ----------------------------------------------------------------------
# `show`
# ----------------------------------------------------------------------

#: The record fields `show` prints as a flat key/value block, in reading
#: order: identity, then lifecycle, then the notation, then the SME columns,
#: then the keys and stamps. `statement` and `structured_body` are handled
#: separately because they are multi-line, and `extractor_payload` is only in
#: `--json` -- it is the verbatim backstop and belongs in a machine read.
_SHOW_FIELDS: tuple[str, ...] = (
    "kind",
    "name",
    "state",
    "modality",
    "modality_extracted",
    "modality_confirmed",
    "rule_class",
    "pattern",
    "enforcement_level",
    "category",
    "priority",
    "confidence_extraction",
    "confidence_intent",
    "disposition",
    "implementation_notes",
    "parameters",
    "rationale",
    "fit_criterion",
    "assumptions",
    "assumptions_extracted",
    "sme_question",
    "suspected_defect",
    "as_built",
    "derived_from",
    "superseded_by",
    "owner",
    "reviewed_by",
    "reviewed_at",
    "review_note",
    "dedupe_key",
    "dedupe_key_anchor_only",
    "first_seen_run_id",
    "created_at",
    "updated_at",
)


def _statement_subject(record: Any) -> Optional[str]:
    """The `[Subject]` span of the record's own `statement`, or `None`.

    Read through `gr_validator.split_slots` -- the same function
    `gr_subject.derive_subject` uses on its fallback branch -- so `show` and
    the derivation cannot disagree about where a statement's subject is.
    Returns `None` when no template applies (`pattern` is NULL, or the
    keyword is absent), which is the honest answer rather than a guess.
    """
    from legacylift_search.gr_validator import split_slots

    try:
        spans = split_slots(record.statement, record.rule_class, record.pattern)
    except Exception:  # noqa: BLE001 - a display aid must not break `show`
        return None
    if spans.subject is None:
        return None
    return record.statement[spans.subject[0] : spans.subject[1]]


@requirements_app.command("show")
def show_cmd(
    gr_id: Annotated[str, typer.Argument(help="The requirement's `gr_id`.")],
    as_json: _shared.JsonOption = False,
    repo_root: _shared.RepoRootOption = None,
    config: _shared.ConfigOption = None,
    analysis_dir: _shared.AnalysisDirOption = None,
) -> None:
    """Show one requirement: columns, citations, findings, body and data flow.

    Two things this command is responsible for making **visible** rather than
    merely correct.

    **The data-flow block prints Step 7's words and never a rate.**
    `gr_dataflow` has no writer in Milestone 1 and ships empty, so a
    percentage there is zero-over-zero; `gr_dataflow.dataflow_status_text` is
    the one producer of that sentence and this command calls it rather than
    composing its own.

    **A subject divergence is shown, not hidden.** `rederive-subjects`
    refreshes `subject` from the current `file_domains` and deliberately never
    rewrites `statement` -- Step 6a made the statement extractor-authored, so
    there is no template to re-fill and no mechanical way to substitute a new
    subject into someone else's sentence. The staleness that leaves is small
    and honest: the *text* may name a subject the domain set no longer
    derives while the column says what the derivation now yields, and the
    plan puts that divergence's visibility here.
    """
    from legacylift_search.gr_dataflow import dataflow_status_text

    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    store = _shared.open_knowledge_store(paths)
    try:
        record = store.get_gr(gr_id)
        if record is None:
            _warn(
                f"no requirement {gr_id!r} in {paths.knowledge_sqlite_path}. "
                "Run `legacylift-search requirements list` to see what is "
                "there."
            )
            raise typer.Exit(code=1)

        citations = store.list_gr_citations(gr_id)
        findings = store.list_gr_findings(gr_id)
        scenarios = store.list_gr_scenarios(gr_id)
        edge_cases = store.list_gr_edge_cases(gr_id)
        dataflow = store.list_gr_dataflow(gr_id)
    finally:
        store.close()

    statement_subject = _statement_subject(record)
    diverged = (
        record.subject is not None
        and statement_subject is not None
        and record.subject.strip().casefold()
        != statement_subject.strip().casefold()
    )
    status = dataflow_status_text(
        total=len(dataflow),
        computed=sum(1 for e in dataflow if e.provenance == "computed"),
        llm_inferred=sum(1 for e in dataflow if e.provenance == "llm_inferred"),
    )

    if as_json:
        _shared.emit_json(
            {
                "requirement": record.model_dump(),
                "subject_divergence": {
                    "column": record.subject,
                    "column_provenance": record.subject_provenance,
                    "statement_subject": statement_subject,
                    "diverged": diverged,
                },
                "citations": [c.model_dump() for c in citations],
                "findings": [f.model_dump() for f in findings],
                "scenarios": [s.model_dump() for s in scenarios],
                "edge_cases": [e.model_dump() for e in edge_cases],
                "dataflow": {
                    "entries": [e.model_dump() for e in dataflow],
                    "status": status,
                },
            }
        )
        return

    _echo(f"{record.gr_id}")
    _echo()
    _echo("statement:")
    _echo(f"  {record.statement}")
    if record.statement_extracted != record.statement:
        _echo("statement (as extracted -- a human has since edited the live one):")
        _echo(f"  {record.statement_extracted}")
    _echo()

    _echo("subject:")
    _echo(f"  column              {_text(record.subject)}")
    _echo(f"  provenance          {_text(record.subject_provenance)}")
    _echo(
        "  statement subject   "
        + (
            statement_subject
            if statement_subject is not None
            else f"{ABSENT} (no template applies: pattern is "
            f"{_text(record.pattern)})"
        )
    )
    if diverged:
        _echo(
            "  DIVERGENCE          the statement names "
            f"{statement_subject!r} while the derivation now yields "
            f"{record.subject!r}. rederive-subjects refreshes the column "
            "from the current domain set and never rewrites the statement, "
            "so after a domain retag the column is the current answer and "
            "the sentence is the extractor's original wording."
        )
    _echo()

    width = max(len(name) for name in _SHOW_FIELDS)
    for name in _SHOW_FIELDS:
        _echo(f"{name:<{width}}  {_text(getattr(record, name))}")
    _echo()

    _echo(f"structured body ({_text(record.structured_body_type)}):")
    _echo(f"  {_text(record.structured_body)}")
    _echo()

    _echo(f"citations ({len(citations)}):")
    for c in citations:
        _echo(
            f"  {c.relative_path}:{c.start_line}-{c.end_line}  "
            f"anchor_resolution={c.anchor_resolution}  "
            f"provenance={c.provenance}"
        )
        _echo(
            f"    anchor_key={c.anchor_key}  "
            f"content_hash={_text(c.content_hash)}  "
            f"verified_at={_text(c.verified_at)}"
        )
    if not citations:
        _echo("  (none)")
    _echo()

    _echo(f"findings ({len(findings)}):")
    for f in findings:
        # `evaluated = 0` is not a third severity: the check could not be
        # decided, and `can_approve` ignores exactly those. Printing it
        # beside the severity is what stops a not-evaluated ERROR from
        # reading as a blocking one.
        mark = "" if f.evaluated else "  [NOT EVALUATED]"
        _echo(
            f"  {f.severity:<5} {f.finding_id:<12} span={f.span or '(record)'}"
            f"{mark}"
        )
        _echo(f"    {f.message}")
    if not findings:
        _echo("  (none)")
    _echo()

    _echo(f"scenarios ({len(scenarios)}):")
    for s in scenarios:
        _echo(
            f"  {s.ordinal}. given={_text(s.given)} | when={_text(s.when)} | "
            f"then={_text(s.then)} | and={_text(s.and_clause)}"
        )
    if not scenarios:
        _echo("  (none)")
    _echo()

    _echo(f"edge cases ({len(edge_cases)}):")
    for e in edge_cases:
        _echo(f"  {e.ordinal}. {e.text}")
    if not edge_cases:
        _echo("  (none)")
    _echo()

    _echo(f"data flow ({len(dataflow)} entry/entries):")
    for e in dataflow:
        _echo(
            f"  {e.direction:<6} {e.datastore}"
            + (f".{e.column}" if e.column else "")
            + f"  provenance={e.provenance}"
        )
    _echo(f"  {status}")


# ----------------------------------------------------------------------
# `search`
# ----------------------------------------------------------------------


@requirements_app.command("search")
def search_cmd(
    query: Annotated[str, typer.Argument(help="FTS5 or free-text query.")],
    semantic: Annotated[
        bool,
        typer.Option(
            "--semantic",
            help=(
                "Search the gr_statements vector collection instead of the "
                "FTS5 index. Needs an embedding provider and a populated "
                "collection; a missing one is reported, never returned as an "
                "empty result."
            ),
        ),
    ] = False,
    state: _StateOption = None,
    limit: _shared.LimitOption = None,
    as_json: _shared.JsonOption = False,
    embedding_provider: _shared.EmbeddingProviderOption = None,
    repo_root: _shared.RepoRootOption = None,
    config: _shared.ConfigOption = None,
    analysis_dir: _shared.AnalysisDirOption = None,
) -> None:
    """Search requirements: FTS5 keyword by default, `--semantic` for vectors.

    **"Nothing matched" and "nothing was ever indexed" must not print the
    same way**, which is the whole reason `--semantic` has three failure
    exits rather than one empty list:

    * no embedding provider, no `gr_statements` collection on disk, or a
      collection built under a different provider -- the search **could not
      run**, so it exits non-zero with the reason and prints nothing on
      stdout. Returning zero hits there would be a lie a caller cannot
      detect.
    * a collection that merely lags `gr` -- the search **did** run over real
      vectors, so it exits zero with results, and
      `gr_refresh.describe_vector_shortfall`'s sentence goes to stderr first,
      naming `requirements reindex-vectors`.

    `--state` filters both halves but by different mechanisms, and the text
    output says which: semantically it is a Chroma metadata `where` filter
    applied *inside* the query, so `--limit` counts matching rows; on the
    keyword half FTS5 ranks first and the filter is applied to the ranked
    page afterwards, so a small `--limit` can hide matching rows.
    """
    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    store = _shared.open_knowledge_store(paths)
    try:
        if semantic:
            _search_semantic(
                paths,
                store,
                query=query,
                state=state,
                limit=limit,
                as_json=as_json,
                embedding_provider=embedding_provider,
            )
        else:
            _search_keyword(
                store, query=query, state=state, limit=limit, as_json=as_json
            )
    finally:
        store.close()


def _search_keyword(
    store: Any,
    *,
    query: str,
    state: Optional[str],
    limit: Optional[int],
    as_json: bool,
) -> None:
    """The FTS5 half, through `KnowledgeStore.search_gr_fts`."""
    effective_limit = 20 if limit is None else limit
    try:
        hits = store.search_gr_fts(query, effective_limit)
    except Exception as exc:  # noqa: BLE001 - an FTS5 syntax error is user input
        _warn(
            f"the FTS5 query {query!r} was rejected ({exc}). FTS5 treats "
            "characters like '-' and '\"' as operators; quote the phrase or "
            "escape them."
        )
        raise typer.Exit(code=1)

    rows = [{"gr_id": gr_id, "statement": statement} for gr_id, statement in hits]
    filtered_out = 0
    if state is not None and rows:
        ids = [row["gr_id"] for row in rows]
        states = {r.gr_id: r.state for r in store.list_gr(ids)}
        kept = [row for row in rows if states.get(row["gr_id"]) == state]
        filtered_out = len(rows) - len(kept)
        rows = kept

    if as_json:
        _shared.emit_json(
            {
                "mode": "keyword",
                "query": query,
                "state": state,
                "limit": effective_limit,
                "count": len(rows),
                "state_filter_applied_after_ranking": state is not None,
                "hits_dropped_by_state_filter": filtered_out,
                "hits": rows,
            }
        )
        return

    if not rows:
        _echo(f"no keyword matches for {query!r}.")
        if filtered_out:
            _echo(
                f"{filtered_out} ranked hit(s) were dropped by --state "
                f"{state!r}; the filter runs after FTS5 ranking, so raise "
                "--limit if you expect more."
            )
        return

    for row in rows:
        _echo(f"  {row['gr_id']}  {row['statement']}")
    _echo()
    _echo(f"{len(rows)} keyword match(es) (FTS5 rank order, limit {effective_limit}).")
    if state is not None:
        _echo(
            f"--state {state!r} was applied AFTER ranking and dropped "
            f"{filtered_out} hit(s); raise --limit if you expect more."
        )


def _search_semantic(
    paths: _shared.RequirementsPaths,
    store: Any,
    *,
    query: str,
    state: Optional[str],
    limit: Optional[int],
    as_json: bool,
    embedding_provider: Optional[str],
) -> None:
    """The vector half, over the `gr_statements` collection.

    `open_gr_collection` is called with **no `base_dir`**, which is not an
    omission: its default is `store.sqlite_path.parent`, the resolved
    knowledge directory, and that default is the whole protection --
    `index --reset` rmtrees the index directory's `chroma` wholesale, so a
    `gr_statements` collection under the index directory is destroyed by a
    routine reindex and stage two then queries an empty collection. Passing
    an index directory here is the one thing this call must never do, so it
    passes nothing.
    """
    from legacylift_search.gr_refresh import (
        GR_COLLECTION_NAME,
        describe_vector_shortfall,
        open_gr_collection,
    )

    gr_count = store.count_gr()
    if gr_count == 0:
        # An empty store is a normal state for all four commands. There is
        # nothing to have indexed, so this is not a shortfall.
        if as_json:
            _shared.emit_json(
                {
                    "mode": "semantic",
                    "query": query,
                    "state": state,
                    "count": 0,
                    "hits": [],
                    "shortfall": None,
                }
            )
        else:
            _echo("no requirements in the store.")
        return

    embedder, reason = _shared.build_embedder(
        paths.manifest, provider_override=embedding_provider
    )
    if embedder is None:
        _warn(
            f"--semantic cannot run: {reason} Keyword search still works: "
            "re-run without --semantic."
        )
        raise typer.Exit(code=1)

    chroma_dir = paths.knowledge_dir / "chroma"
    if not chroma_dir.exists():
        # Probe rather than open: `get_or_create_collection` would create an
        # empty collection here, and an empty one is indistinguishable from
        # a real one on the next command. The sentence comes from
        # `describe_vector_shortfall` so this command and stage two say the
        # same thing about the same state.
        _warn(
            f"no {GR_COLLECTION_NAME} collection exists yet ({chroma_dir} is "
            "absent), so nothing has ever been indexed for semantic search "
            "-- this is not an empty result set. "
            + (describe_vector_shortfall(gr_count, 0) or "")
        )
        raise typer.Exit(code=1)

    try:
        collection = open_gr_collection(store, embedder)
    except Exception as exc:  # noqa: BLE001 - chromadb/provider dependent
        _warn(
            f"the {GR_COLLECTION_NAME} collection could not be opened "
            f"({exc}). Run `legacylift-search requirements reindex-vectors`."
        )
        raise typer.Exit(code=1)

    try:
        try:
            collection.validate_dimension()
        except ValueError as exc:
            _warn(
                f"the {GR_COLLECTION_NAME} collection was built with a "
                f"different embedding provider ({exc}); it is unusable rather "
                "than stale. Delete it and run `legacylift-search "
                "requirements reindex-vectors`."
            )
            raise typer.Exit(code=1)

        collection_count = collection.count()
        shortfall = describe_vector_shortfall(gr_count, collection_count)
        if collection_count == 0:
            _warn(
                f"the {GR_COLLECTION_NAME} collection is empty, so no "
                "semantic result is possible -- this is not 'nothing "
                f"matched'. {shortfall or ''}"
            )
            raise typer.Exit(code=1)
        if shortfall is not None:
            _warn(shortfall)

        effective_limit = 20 if limit is None else limit
        where = {"state": state} if state is not None else None
        try:
            results = collection.query(
                embedder.embed_query(query), effective_limit, where=where
            )
        except Exception as exc:  # noqa: BLE001 - provider/chromadb dependent
            _warn(
                f"the semantic query failed ({exc}); keyword search still "
                "works: re-run without --semantic."
            )
            raise typer.Exit(code=1)
    finally:
        collection.close()

    hits = [
        {
            "gr_id": r.id,
            "distance": r.distance,
            "statement": r.document,
            "state": r.metadata.get("state"),
            "subject": r.metadata.get("subject"),
        }
        for r in results
    ]

    if as_json:
        _shared.emit_json(
            {
                "mode": "semantic",
                "query": query,
                "state": state,
                "limit": effective_limit,
                "count": len(hits),
                # Named `distance`, never `score` or `similarity`: the metric
                # is unpinned, so a later chromadb pin or an explicit
                # hnsw:space silently changes what the number means.
                "score_kind": "distance",
                "score_metric": _METRIC_CAVEAT,
                "collection_count": collection_count,
                "gr_count": gr_count,
                "shortfall": shortfall,
                "hits": hits,
            }
        )
        return

    if not hits:
        _echo(
            f"no semantic matches for {query!r} "
            f"(searched {collection_count} vector(s))."
        )
        return

    _echo(f"distance ({_METRIC_CAVEAT}):")
    for hit in hits:
        _echo(
            f"  distance={hit['distance']:.4f}  {hit['gr_id']}  "
            f"state={_text(hit['state'])}"
        )
        _echo(f"    {hit['statement']}")
    _echo()
    _echo(
        f"{len(hits)} semantic match(es) of {collection_count} vector(s) "
        f"over {gr_count} requirement(s)."
    )


# ----------------------------------------------------------------------
# `stats`
# ----------------------------------------------------------------------


def _vector_shortfall_report(
    paths: _shared.RequirementsPaths,
    store: Any,
    *,
    embedding_provider: Optional[str],
) -> dict[str, Any]:
    """The `gr_statements` shortfall for `stats`, or why it is `UNMEASURED`.

    Three outcomes and they must not share an encoding. A **measured** count
    gives `collection_count` an integer and `shortfall` either the sentence
    or `None`. A collection that does not exist yet gives
    `collection_count = 0` -- a real measurement, because "no collection"
    genuinely means "no vectors" -- and the sentence from
    `describe_vector_shortfall`. **No embedder, or a collection that will not
    open, leaves `collection_count` as `None`**: nobody looked, which is not
    the same as zero, and printing `0 of N` there would invent the worst
    number in the report.
    """
    from legacylift_search.gr_refresh import (
        GR_COLLECTION_NAME,
        describe_vector_shortfall,
        open_gr_collection,
    )

    gr_count = store.count_gr()
    out: dict[str, Any] = {
        "collection": GR_COLLECTION_NAME,
        "gr_count": gr_count,
        "collection_count": None,
        "shortfall": None,
        "unmeasured_reason": None,
    }

    chroma_dir = paths.knowledge_dir / "chroma"
    if not chroma_dir.exists():
        out["collection_count"] = 0
        out["shortfall"] = describe_vector_shortfall(gr_count, 0)
        out["collection_absent"] = True
        return out
    out["collection_absent"] = False

    embedder, reason = _shared.build_embedder(
        paths.manifest, provider_override=embedding_provider
    )
    if embedder is None:
        out["unmeasured_reason"] = reason
        return out

    try:
        collection = open_gr_collection(store, embedder)
    except Exception as exc:  # noqa: BLE001 - chromadb/provider dependent
        out["unmeasured_reason"] = (
            f"the {GR_COLLECTION_NAME} collection could not be opened "
            f"({exc}); run `legacylift-search requirements reindex-vectors`."
        )
        return out
    try:
        count = collection.count()
    except Exception as exc:  # noqa: BLE001 - chromadb dependent
        out["unmeasured_reason"] = f"the collection count failed ({exc})."
        return out
    finally:
        collection.close()

    out["collection_count"] = count
    out["shortfall"] = describe_vector_shortfall(gr_count, count)
    return out


def _fill_report(store: Any) -> dict[str, dict[str, Any]]:
    """Per-column review progress, with **the numerator named in the output**.

    `gr_field_fill_counts` returns three numbers rather than a rate on
    purpose: the numerator differs per column, and it refuses to pick. This
    is where the pick happens, and it is reported alongside every rate so a
    reader never has to guess which question a percentage answered.

    * `assumptions` -- numerator `filled+empty`. `''` there means
      "considered, and none" (Step 6a has the extractor always emit the key),
      so counting it as unfilled reports the opposite of the truth.
    * `modality_confirmed` -- **no rate at all**. `INTEGER NOT NULL DEFAULT
      0` makes every row `filled`, so a rate is a guaranteed 100% measuring
      nothing, and re-encoding its `0` as unfilled to manufacture a number
      would treat a fact as an absence.
    * everything else -- numerator `filled`. An empty string in a free-text
      SME column is a human who typed nothing.
    """
    from legacylift_search.knowledge_store import GR_FILL_FIELDS

    counts = store.gr_field_fill_counts(GR_FILL_FIELDS)
    total = store.count_gr()
    out: dict[str, dict[str, Any]] = {}
    for field in GR_FILL_FIELDS:
        c = counts[field]
        if field in _NO_FILL_RATE:
            numerator_name: Optional[str] = None
            numerator: Optional[int] = None
        elif field in _FILL_NUMERATOR_INCLUDES_EMPTY:
            numerator_name = "filled+empty"
            numerator = c["filled"] + c["empty"]
        else:
            numerator_name = "filled"
            numerator = c["filled"]
        out[field] = {
            "filled": c["filled"],
            "empty": c["empty"],
            "absent": c["absent"],
            "total": total,
            "numerator": numerator_name,
            "numerator_count": numerator,
            "rate": None if numerator is None else _rate(numerator, total),
        }
    return out


def _run_report(store: Any) -> list[dict[str, Any]]:
    """Per-run figures, **read from the store's own columns, never re-derived**.

    `IngestResult` already carried every one of these at ingest time and
    `gr_run` stored them; recomputing any of them from the rules would put
    two answers to one question in the tree, which the plan warns about
    twice.

    `not_accounted_for` is `int | None` and **NULL means never measured, not
    zero** -- `complete` is a GENERATED column deriving from exactly that
    distinction, so this renders NULL as `UNMEASURED` and reports `complete`
    beside it.

    The same rule governs the four round-metadata columns, and they are here
    because Step 10 requires them per run. `stop_reason` is one of `'dry'`,
    `'round_cap'` and `'budget_exhausted'` -- the extraction loop's three
    real termination paths, all three now emitted by
    `workflows/extract-rules.js` -- and only `'dry'` says the extractor ran
    out of rules to find; the other two say the loop was cut off while still
    producing, which makes the corpus a floor rather than a sweep.
    `new_rules_in_final_round` distinguishes NULL ("no round ever ran") from
    `0` ("the last round that ran found nothing new"), so it is the one
    column here where printing `0` for NULL would assert the opposite of the
    truth rather than merely overstate confidence. Every one of the four is
    NULL for runs ingested from a payload that did not carry it, which is
    normal rather than an error.
    """
    out: list[dict[str, Any]] = []
    for run in store.list_gr_runs():
        out.append(
            {
                "run_id": run.run_id,
                "system": run.system,
                "rules_in": run.rules_in,
                "rules_new": run.rules_new,
                "rules_merged": run.rules_merged,
                "rules_candidate": run.rules_candidate,
                "rules_rejected": run.rules_rejected,
                # Step 10's per-run termination record. All four are
                # `| None` and a NULL is "never measured", never zero.
                "rounds_run": run.rounds_run,
                "round_cap": run.round_cap,
                "stop_reason": run.stop_reason,
                "new_rules_in_final_round": run.new_rules_in_final_round,
                "not_accounted_for": run.not_accounted_for,
                "coverage_source": run.coverage_source,
                "coverage_measured_at": run.coverage_measured_at,
                "final_round_chunk_coverage_pct": (
                    run.final_round_chunk_coverage_pct
                ),
                "complete": run.complete,
                "gate_excluded": run.gate_excluded,
                "gate_excluded_reason": run.gate_excluded_reason,
                "injection_flags": run.injection_flags,
                # Step 6/10's mandatory measurement, per run.
                "intra_run_collapse": store.intra_run_collapse_count(run.run_id),
            }
        )
    return out


@requirements_app.command("stats")
def stats_cmd(
    as_json: _shared.JsonOption = False,
    embedding_provider: _shared.EmbeddingProviderOption = None,
    repo_root: _shared.RepoRootOption = None,
    config: _shared.ConfigOption = None,
    analysis_dir: _shared.AnalysisDirOption = None,
) -> None:
    """Report the requirements corpus: counts, review progress and coverage.

    **This command surfaces the numbers the store already holds; it does not
    recompute them.** `IngestResult` carried every per-run figure and
    `gr_run` stored it, so re-deriving one here is how two answers to one
    question appear.

    Eight blocks, each of which the plan names as an observable:

    1. counts by `state`, `category`, `disposition` and `subject_provenance`,
       with **NULL as its own row** -- `count_gr_by` keeps it under the `None`
       key and `COALESCE(col, 'none')` is the natural thing to type and the
       defect;
    2. the absent-subject count, **apart from `llm_named`**: a row can carry
       `subject_provenance = 'llm_named'` with a NULL `subject` (the fallback
       branch ran and `split_slots` located nothing), so folding the two
       reports a model-named subject for a requirement that has none;
    3. review progress over the twelve SME-writable columns, with the
       numerator named in the output;
    4. the data-flow block **in Step 7's words, never a rate**;
    5. per-run figures including the intra-run collapse count and the
       four round-metadata columns -- `rounds_run`, `round_cap`,
       `stop_reason`, `new_rules_in_final_round` -- each of which prints
       `unmeasured` when NULL, because a run whose workflow never
       emitted them has no termination record at all and `0` would
       invent one;
    6. the count of requirements whose citations **all** land on the
       `excluded` domain -- Step 3's own figure, deliberately not folded into
       `derived_ambiguous`, because "mined from code the analyst has since
       declared out of scope" is a different fact from "no domain held a
       majority";
    7. the `gr_statements` vector shortfall, so a degraded collection is
       visible here and not only in the output of the command that degraded
       it;
    8. whether `V-STY-03`'s symbol half was available at all. "No leakage
       found" and "leakage was never looked for" are different facts and this
       says which one it is.
    """
    from legacylift_search.gr_dataflow import dataflow_status_text

    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    store = _shared.open_knowledge_store(paths)
    try:
        total = store.count_gr()
        grouped = {
            column: store.count_gr_by(column)
            for column in ("state", "category", "disposition", "subject_provenance")
        }
        null_subjects = store.count_gr_null_subjects()
        fill = _fill_report(store)
        dataflow_total = store.count_gr_dataflow()
        dataflow_provenance = store.gr_dataflow_provenance_counts()
        dataflow_status = dataflow_status_text(
            total=dataflow_total,
            computed=dataflow_provenance.get("computed", 0),
            llm_inferred=dataflow_provenance.get("llm_inferred", 0),
        )
        runs = _run_report(store)
        all_excluded = store.count_gr_all_citations_excluded()
        findings = store.gr_finding_counts_by_severity()
        vectors = _vector_shortfall_report(
            paths, store, embedding_provider=embedding_provider
        )
    finally:
        store.close()

    # `RefreshResult.leaked_terms_available` is False when no index was
    # reachable, and this command's route to that fact is the same plain
    # `Path.exists()` the refresh itself uses -- `paths.index_exists`. It is
    # asked here rather than read off a stored flag because the answer is a
    # property of the environment now, not of the last refresh.
    symbol_half_available = paths.index_exists

    if as_json:
        _shared.emit_json(
            {
                "requirements": total,
                "counts": {
                    column: _counts_json(counts)
                    for column, counts in grouped.items()
                },
                "null_subjects": {
                    "count": null_subjects,
                    "note": (
                        "counted apart from llm_named: a row can carry "
                        "subject_provenance='llm_named' with a NULL subject"
                    ),
                },
                "review_progress": fill,
                "dataflow": {
                    "total": dataflow_total,
                    "by_provenance": dataflow_provenance,
                    "status": dataflow_status,
                },
                "runs": runs,
                "all_citations_excluded": all_excluded,
                "findings_by_severity": findings,
                "vectors": vectors,
                "v_sty_03_symbol_half": {
                    "available": symbol_half_available,
                    "index_sqlite_path": str(paths.index_sqlite_path),
                    "note": (
                        "when false, V-STY-03 ran on its morphological "
                        "fallback alone: 'no leakage found' would mean "
                        "'leakage was never looked for'"
                    ),
                },
            }
        )
        return

    _echo(f"requirements: {total}")
    if total == 0:
        _echo("(an empty store is a normal state, not an error.)")
    _echo()

    for column, counts in grouped.items():
        _echo_counts(f"by {column}", counts)
        _echo()
    _echo(f"{ABSENT} above is a NULL column, kept as its own row.")
    _echo()

    _echo(
        f"subject absent (no subject was locatable): {null_subjects} "
        f"of {total}"
    )
    _echo(
        "  counted APART from llm_named: a row can carry "
        "subject_provenance='llm_named' with a NULL subject, when the "
        "fallback branch ran and split_slots located no [Subject] span."
    )
    _echo()

    _echo("review progress (SME-writable columns):")
    _echo(
        "  the numerator is named per row, because it differs per column: "
        "assumptions counts filled+empty ('' means considered-and-none), "
        "every other free-text column counts filled alone."
    )
    width = max(len(name) for name in fill)
    for name, row in fill.items():
        if row["rate"] is None:
            rate = (
                "no rate reported (NOT NULL DEFAULT 0: every row is "
                "'filled' and a 0 is a fact, not an absence)"
            )
        else:
            rate = f"{row['rate']} of {row['numerator']}"
        _echo(
            f"  {name:<{width}}  filled={row['filled']:<5} "
            f"empty={row['empty']:<5} absent={row['absent']:<5} {rate}"
        )
    _echo()

    _echo("data flow:")
    _echo(f"  {dataflow_status}")
    _echo()

    _echo(f"runs ({len(runs)}):")
    if not runs:
        _echo("  (none -- nothing has been ingested into this store)")
    for run in runs:
        _echo(f"  {run['run_id']}  system={_text(run['system'])}")
        _echo(
            f"    rules in={_text(run['rules_in'])} new={_text(run['rules_new'])} "
            f"merged={_text(run['rules_merged'])} "
            f"candidate={_text(run['rules_candidate'])} "
            f"rejected={_text(run['rules_rejected'])}"
        )
        _echo(
            f"    stop_reason={_measured(run['stop_reason'])}  "
            f"rounds_run={_measured(run['rounds_run'])}  "
            f"round_cap={_measured(run['round_cap'])}  "
            "new_rules_in_final_round="
            f"{_measured(run['new_rules_in_final_round'])}"
        )
        not_accounted = _measured(run["not_accounted_for"])
        _echo(
            f"    not_accounted_for={not_accounted}  "
            f"complete={run['complete']}  "
            f"coverage_source={_text(run['coverage_source'])}  "
            f"measured_at={_text(run['coverage_measured_at'])}"
        )
        if run["gate_excluded"]:
            _echo(
                "    gate_excluded=True  reason="
                f"{_text(run['gate_excluded_reason'])}"
            )
        _echo(f"    intra_run_collapse={run['intra_run_collapse']}")
    _echo(
        f"  {UNMEASURED} not_accounted_for means coverage was never taken, "
        "which is NOT zero: `complete` is 1 only when the figure is both "
        "present and zero."
    )
    _echo(
        f"  {UNMEASURED} on any of stop_reason/rounds_run/round_cap/"
        "new_rules_in_final_round means the extraction that produced this "
        "run never reported it, so how the loop ended is unrecorded."
    )
    _echo(
        "  stop_reason: 'dry' = two consecutive rounds found nothing new "
        "(extraction ran out); 'round_cap' = the maxRounds cap cut the loop "
        "off; 'budget_exhausted' = the token budget did. Under the last two "
        "the corpus is a floor, not a sweep."
    )
    _echo(
        f"  new_rules_in_final_round={UNMEASURED} is NOT 0: 0 means the last "
        "round that ran found nothing new, and unmeasured means no round ran "
        "(or the figure was never reported)."
    )
    _echo()

    _echo(
        "requirements whose citations ALL land on the excluded domain: "
        f"{all_excluded}"
    )
    _echo(
        "  reported as its own figure, not folded into derived_ambiguous: "
        "it means the corpus holds rules mined from code the analyst has "
        "since declared out of scope."
    )
    _echo()

    _echo("findings by severity:")
    if not findings:
        _echo("  (none)")
    for severity, split in sorted(findings.items()):
        _echo(
            f"  {severity:<5} evaluated={split['evaluated']}  "
            f"not_evaluated={split['not_evaluated']}"
        )
    _echo(
        "  a not-evaluated finding is a check that could not be decided, "
        "never one that failed -- can_approve ignores exactly those."
    )
    _echo()

    _echo("vectors:")
    if vectors["collection_count"] is None:
        _echo(
            f"  {vectors['collection']} count is {UNMEASURED}: "
            f"{vectors['unmeasured_reason']}"
        )
        _echo(
            "  this is NOT a count of zero -- nobody looked, so no shortfall "
            "can be reported either way."
        )
    else:
        absent_note = (
            " (the collection does not exist yet)"
            if vectors.get("collection_absent")
            else ""
        )
        _echo(
            f"  {vectors['collection']} holds "
            f"{vectors['collection_count']} of {vectors['gr_count']} "
            f"requirement(s){absent_note}"
        )
        if vectors["shortfall"] is None:
            _echo("  no shortfall.")
        else:
            _echo(f"  {vectors['shortfall']}")
    _echo()

    _echo("V-STY-03 symbol half:")
    if symbol_half_available:
        _echo(
            f"  available -- an index exists at {paths.index_sqlite_path}, so "
            "the check compared each statement against symbol names declared "
            "in its own cited files."
        )
    else:
        _echo(
            f"  NOT available -- no index at {paths.index_sqlite_path}, so "
            "V-STY-03 ran on its morphological fallback alone. 'No leakage "
            "found' here would mean 'leakage was never looked for'; build an "
            "index and re-validate before reading the finding counts above "
            "as evidence of abstraction."
        )
