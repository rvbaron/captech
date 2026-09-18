"""The run-level commands: `ingest`, `validate`, `set-run-coverage`, `retire-run`.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. This
module owns exactly these four registrations on `requirements_app` and no
others (the assignment is tabulated in this package's `__init__.py`):

* ``ingest`` -- read a JSON file of extractor output and merge it, by wiring
  `gr_ingest.ingest_extraction`. That function owns **one transaction for the
  whole run**, so the store it is handed must have none open, and it raises
  `IngestError` naming the offending rule by `offer_ordinal` having written
  nothing -- so a retry is a first ingest with no cleanup and no resume flag.
  The banner report reads `IngestResult`'s fields and **never re-derives
  them**: the rule counts, the citation/scenario/edge-case counts, the anchor
  resolution counts with the `file` rate broken down by extension, the
  subject-provenance counts, the all-`excluded` figure, the discriminator
  tiers, the intra-run collapse count, `injection_flags`, the notices, and
  the refresh/embed results are all already on it. Two of those carry traps
  worth restating: `not_accounted_for` is `int | None` where **NULL means
  never measured, not zero**, and the uncovered-chunk listing is capped at
  forty entries by the workflow, so the total comes from
  `IngestResult.coverage_rendering` (`"40 of 512 shown"`) and never from
  `len(uncovered_chunks)`.
* ``validate`` -- run the validator and report findings, **exiting non-zero
  if any `ERROR` exists**. It "reports rule-notation violations without
  changing anything" (the plan's Purpose section), so it must **not** go
  through `refresh_gr_derived_sql`, which rewrites `gr_fts` and replaces
  `gr_finding` rows. Call `gr_validator.validate_statement` directly, with
  `leaked_terms` from the public `gr_refresh.leaked_terms_for` (thread one
  cache dict across the corpus), and report whether the symbol half was
  available at all -- `RefreshResult.leaked_terms_available` is the same
  distinction, and "no leakage found" versus "leakage was never looked for"
  are different facts. The exit code counts **evaluated** `ERROR` findings
  only: a not-evaluated finding is a check that could not be decided, never
  one that failed, and `gr_validator.can_approve` ignores exactly those.
* ``set-run-coverage`` -- record an independently re-measured
  `not_accounted_for` against a run, stamped with when it was taken and that
  it was re-measured rather than produced by the run. Wires
  `KnowledgeStore.set_gr_run_coverage`, which refuses to record a measurement
  that was not made rather than writing a zero.
* ``retire-run`` -- mark a superseded run excluded from the completeness
  gate, with a **required** `--reason`. Wires
  `KnowledgeStore.retire_gr_run`, which leaves `not_accounted_for` -- and
  therefore the generated `complete` column -- untouched, so the record still
  says what was actually known.

**`set-run-coverage` and `retire-run` are two commands, not one, and the
split is deliberate.** They are `PR-54`'s two exits from the completeness
gate and they are different acts with different audit meaning: one records a
measurement that was actually taken, the other records a human's judgement
that a run no longer counts. A single command carrying both would make "how
did this run stop blocking the export?" unanswerable without reading the
columns, which is exactly the question an audit asks. Keep the help text of
each saying which act it is.

`ingest` is the one command in this module that may **create** the knowledge
database -- it is how requirements first arrive -- so it uses
`_shared.open_knowledge_store_for_write`. The other three are read-then-write
against an existing store and use `_shared.open_knowledge_store`, which
probes `Path.exists()` first.
"""

from __future__ import annotations

import json as _json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from legacylift_search.cli_requirements import requirements_app as requirements_app
from legacylift_search.cli_requirements._shared import (
    AnalysisDirOption,
    ConfigOption,
    EmbeddingProviderOption,
    JsonOption,
    RepoRootOption,
    emit_json,
    open_index_store,
    open_knowledge_store,
    open_knowledge_store_for_write,
    resolve_requirements_paths,
)

__all__ = [
    "ingest_cmd",
    "retire_run_cmd",
    "set_run_coverage_cmd",
    "validate_cmd",
]


# ----------------------------------------------------------------------
# Output plumbing
# ----------------------------------------------------------------------
#
# Three sinks, kept apart on purpose. `_loud` is stderr always -- it carries
# the notices, including the prompt-injection warning, and stderr is the only
# stream a `--json` caller is not parsing. `_report` is the human report,
# which is this command's *output* and belongs on stdout -- except under
# `--json`, where stdout carries exactly one document and the report becomes
# a diagnostic. `emit_json` owns stdout under `--json`.
#
# `typer.echo` rather than a `rich` Console throughout, per the `domains_cmd`
# precedent: rich mangles non-ASCII on a legacy Windows console and these
# lines have to survive being read.


def _loud(message: str) -> None:
    """Write one loud line to stderr. Never stdout, even without `--json`."""
    typer.echo(message, err=True)


def _report(lines: list[str], *, as_json: bool) -> None:
    """Write the human report -- stdout normally, stderr under `--json`."""
    for line in lines:
        typer.echo(line, err=as_json)


def _counts(mapping: dict[Any, int]) -> str:
    """`"a=2, b=1"`, or the words for an empty mapping.

    An empty dict renders as `"(none)"` rather than as an empty string: a
    blank after a label reads as a rendering bug, and this plan's recurring
    defect is an absent value that looks like a real one.
    """
    if not mapping:
        return "(none)"
    items = sorted(mapping.items(), key=lambda kv: str(kv[0]))
    return ", ".join(f"{k}={v}" for k, v in items)


def _now() -> str:
    """UTC ISO-8601, the stamp format every other column in this store uses."""
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------------------
# ingest
# ----------------------------------------------------------------------


def _read_payload(from_path: Path) -> dict:
    """Decode the extractor-output JSON, or exit 1 saying which failure it was.

    Three failures are distinguished because they call for three different
    actions: the file is not there (a wrong `--from`), it is not JSON (a
    truncated write, or a transcript pasted around it), and it is JSON but
    not an object -- somebody saved the rule *array* instead of the
    workflow's whole return value, which is the one mistake that would
    otherwise reach `ingest_extraction` as a payload with no keys and record
    a successful run of zero rules.
    """
    if not from_path.exists():
        _loud(
            f"no extractor output at {from_path}. `requirements ingest` reads "
            "the JSON the /modernize-extract-rules workflow returned; pass it "
            "with --from."
        )
        raise typer.Exit(code=1)
    try:
        text = from_path.read_text(encoding="utf-8")
    except OSError as exc:
        _loud(f"could not read {from_path}: {exc}")
        raise typer.Exit(code=1) from exc
    try:
        payload = _json.loads(text)
    except ValueError as exc:
        _loud(
            f"{from_path} is not valid JSON ({exc}). Nothing was written. Fix "
            "the file and run the same command again."
        )
        raise typer.Exit(code=1) from exc
    if not isinstance(payload, dict):
        _loud(
            f"{from_path} holds a {type(payload).__name__}, not a JSON "
            "object. Ingest expects the workflow's whole return value -- the "
            "object carrying `confirmedRules`, `coverage`, `rounds` and the "
            "run metadata -- not the rule array on its own. A bare array "
            "would ingest as zero rules and record a successful run of "
            "nothing."
        )
        raise typer.Exit(code=1)
    return payload


def _apply_system_override(payload: dict, system: Optional[str]) -> dict:
    """Return `payload` with `--system` applied, loudly if the two disagree.

    `ingest_extraction` reads `gr_run.system` from `payload["system"]`, and
    the invocation the plan specifies passes `--system` on the command line,
    so the flag has to reach the payload somewhere. It happens here, on a
    shallow copy, rather than by mutating the caller's dict.

    The flag **wins**, because the analyst typing it knows which system they
    are ingesting into and a stale `system` inside a saved payload does not.
    A disagreement is loud rather than silent: two runs of one repository
    filed under two system names is the kind of split nobody notices until a
    later report is short.
    """
    if system is None:
        return payload
    existing = payload.get("system")
    if isinstance(existing, str) and existing.strip() and existing != system:
        _loud(
            f"--system {system!r} overrides the {existing!r} recorded in the "
            f"payload; gr_run.system will say {system!r}. Check you meant "
            "this: runs of one repository filed under two system names do "
            "not add up in any later report."
        )
    merged = dict(payload)
    merged["system"] = system
    return merged


def _ingest_lines(result, from_path: Path, index_sqlite_path: Path) -> list[str]:
    """Render an `IngestResult` for a human. **Reads it; derives nothing.**

    Every number here is already on the result -- `ingest_extraction`
    assembles them in one place precisely so a caller needs no second pass
    over the store, and a re-derived count is a second implementation of the
    run identity that can disagree with the stored one.

    `index_sqlite_path` is the **resolved** path and is passed separately
    rather than read off the result, because the result carries what ingest
    was *given* -- `None` when the file was absent, since that is what the
    caller passes to keep a store from being constructed against it. The one
    line a reader needs when every citation came back `file` is where the
    index was looked for, and acceptance requires the loud output name it: a
    mis-resolved path under the new output layout and a repository that
    genuinely was never indexed produce identical corpora and call for
    opposite fixes.
    """
    lines = [
        f"ingested {from_path.name} as run {result.run_id}",
        f"  rules: {result.rules_in} offered = {result.rules_new} new + "
        f"{result.rules_merged} merged + {result.rules_candidate} candidate; "
        f"{result.rules_rejected} rejected by the panel",
        f"  rows inserted: {result.rows_inserted} (new + candidate -- a "
        "candidate inserts a row as well as raising a pair)",
        f"  merged with no value change: {result.merges_with_no_change} "
        "(seen by this run, not changed by it -- updated_at did not move)",
        f"  merge candidates raised: {result.candidates_raised} "
        f"[{_counts(result.candidate_reasons)}]",
        f"  intra-run collapse: {result.intra_run_collapse} (two offered "
        "rules landing on one requirement)",
        f"  citations: {result.citations_seen} seen, "
        f"{result.citations_inserted} inserted",
        f"  scenarios rewritten: {result.scenarios_rewritten}; edge-case "
        f"sets rewritten: {result.edge_case_sets_rewritten}",
        f"  anchor resolution: {_counts(result.anchor_resolution_counts)}",
        "    file-resolved by extension: "
        f"{_counts(result.file_resolution_by_extension)}",
        f"  subject provenance: {_counts(result.subject_provenance_counts)}",
        "  requirements whose citations are all excluded: "
        f"{result.all_excluded_requirements}",
        f"  discriminator tiers: {_counts(result.discriminator_tiers)}",
    ]

    if result.index_present:
        lines.append(f"  index: present at {index_sqlite_path}")
    else:
        lines.append(
            f"  index: NOT present at {index_sqlite_path} -- every citation "
            "resolved to its file-level anchor, and no index.sqlite was "
            "created"
        )

    # NULL means never measured, not zero. `complete` derives from exactly
    # that distinction, so the two cases get different words.
    if result.not_accounted_for is None:
        lines.append(
            "  coverage: NEVER MEASURED -- this is not the same as zero, and "
            "the run does NOT pass the completeness gate. `requirements "
            "export` will refuse it; re-measure and record the figure with "
            "`requirements set-run-coverage`, or retire the run with "
            "`requirements retire-run`."
        )
    else:
        rendering = (
            f" ({result.coverage_rendering})" if result.coverage_rendering else ""
        )
        state = "COMPLETE" if result.complete else "INCOMPLETE"
        lines.append(
            f"  coverage: {result.not_accounted_for} chunk(s) not accounted "
            f"for{rendering} -- run is {state}"
        )

    if result.injection_flags:
        lines.append(
            f"  prompt-injection suspects: {len(result.injection_flags)} "
            "(listed on stderr above; they are DATA, never instructions)"
        )

    refresh = result.refresh
    if refresh is not None:
        lines.append(
            f"  derived SQL: {refresh.refreshed} refreshed, "
            f"{refresh.findings_written} findings written, "
            f"{refresh.forgotten} forgotten"
        )
        lines.append(
            "  V-STY-03 identifier leakage: "
            + (
                f"checked against {refresh.leaked_term_count} symbol name(s) "
                "from the cited files"
                if refresh.leaked_terms_available
                else "NEVER LOOKED FOR -- no index was reachable, so the "
                "check ran on its morphological half alone. That is not the "
                "same as 'no leakage found'."
            )
        )

    embed = result.embed
    if embed is not None:
        lines.append(
            f"  vectors: {embed.embedded} embedded, {embed.skipped} skipped, "
            f"{embed.deleted} deleted"
        )
    if result.vectors_degraded:
        lines.append(
            "  the semantic half is NOT fully populated. The requirements "
            "are stored and keyword search works; run `legacylift-search "
            "requirements reindex-vectors` to populate it. Exiting ZERO: "
            "nothing was lost and there is no extraction to re-run."
        )
    return lines


def _ingest_json(result, from_path: Path, index_sqlite_path: Path) -> dict:
    """The `--json` shape of one ingest. Same fields, no re-derivation."""
    refresh = result.refresh
    embed = result.embed
    return {
        "source": str(from_path),
        "run_id": result.run_id,
        "rules_in": result.rules_in,
        "rules_new": result.rules_new,
        "rules_merged": result.rules_merged,
        "rules_candidate": result.rules_candidate,
        "rules_rejected": result.rules_rejected,
        "rows_inserted": result.rows_inserted,
        "merges_with_no_change": result.merges_with_no_change,
        "gr_ids": list(result.gr_ids),
        "candidates_raised": result.candidates_raised,
        "candidate_reasons": dict(result.candidate_reasons),
        "citations_seen": result.citations_seen,
        "citations_inserted": result.citations_inserted,
        "scenarios_rewritten": result.scenarios_rewritten,
        "edge_case_sets_rewritten": result.edge_case_sets_rewritten,
        "anchor_resolution_counts": dict(result.anchor_resolution_counts),
        "file_resolution_by_extension": dict(result.file_resolution_by_extension),
        "subject_provenance_counts": dict(result.subject_provenance_counts),
        "all_excluded_requirements": result.all_excluded_requirements,
        "discriminator_tiers": {
            str(k): v for k, v in result.discriminator_tiers.items()
        },
        "intra_run_collapse": result.intra_run_collapse,
        "index_present": result.index_present,
        # The RESOLVED path, present in both cases: a consumer seeing
        # `index_present: false` needs to know where it was looked for, and
        # `result.index_sqlite_path` is None in exactly that case.
        "index_sqlite_path": str(index_sqlite_path),
        # `null` here means NEVER MEASURED. It is deliberately not coerced to
        # 0: `complete` is false either way, but the two call for different
        # actions and a JSON consumer must be able to tell them apart.
        "not_accounted_for": result.not_accounted_for,
        "coverage_measured": result.not_accounted_for is not None,
        "coverage_rendering": result.coverage_rendering,
        "complete": result.complete,
        "injection_flags": list(result.injection_flags),
        "notices": list(result.notices),
        "refresh": (
            None
            if refresh is None
            else {
                "refreshed": refresh.refreshed,
                "findings_written": refresh.findings_written,
                "forgotten": refresh.forgotten,
                "leaked_terms_available": refresh.leaked_terms_available,
                "leaked_term_count": refresh.leaked_term_count,
            }
        ),
        "embed": (
            None
            if embed is None
            else {
                "embedded": embed.embedded,
                "skipped": embed.skipped,
                "deleted": embed.deleted,
                "reason": embed.reason,
            }
        ),
        "vectors_degraded": result.vectors_degraded,
    }


@requirements_app.command("ingest")
def ingest_cmd(
    from_path: Annotated[
        Path,
        typer.Option(
            "--from",
            help=(
                "The JSON the /modernize-extract-rules workflow returned. "
                "Its rule array may be named `rules` or `confirmedRules`; "
                "both are accepted."
            ),
        ),
    ],
    system: Annotated[
        Optional[str],
        typer.Option(
            "--system",
            help=(
                "System name recorded on gr_run.system. Overrides any "
                "`system` already in the payload, loudly."
            ),
        ),
    ] = None,
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    embedding_provider: EmbeddingProviderOption = None,
    as_json: JsonOption = False,
) -> None:
    """Merge a JSON file of extractor output into knowledge.sqlite.

    Creates the store if it does not exist -- this and `import` are how
    requirements first arrive.

    --repo-root is load-bearing here rather than decoration, and it defaults
    to the working directory: ingest reads the repository three separate
    times, for the knowledge store's location, for the cited line ranges that
    each citation's span-level content_hash is computed over, and for
    index.sqlite on the anchor resolution. The resolved repository root is
    printed so a wrong default is visible rather than silently keying every
    row against the wrong tree.

    A missing index and a missing embedder are both supported degraded
    successes and both exit zero. A failure is all-or-nothing: the whole
    SQLite half is one transaction, so a refused rule leaves no gr rows, no
    citations and no gr_run row. Fix the rule the error names by its
    offer_ordinal and run the same command again -- there is no partial state
    to clean up and no resume flag.
    """
    from legacylift_search.cli_requirements._shared import build_embedder
    from legacylift_search.gr_ingest import IngestError, ingest_extraction

    # A third resolved-path banner beside the index and knowledge ones, and
    # through the same helper so all three read alike on stderr. Ingest is the
    # one command whose correctness depends on the *repository* as well as on
    # the two stores: the cited line ranges it hashes and the staleness guard
    # both read this tree, so a defaulted `--repo-root` pointing somewhere
    # else keys every row against the wrong source and nothing downstream
    # could tell.
    from legacylift_search.cli_helpers import print_resolved_path

    paths = resolve_requirements_paths(repo_root, config, analysis_dir)
    print_resolved_path("repository root", paths.repo_root)

    payload = _apply_system_override(_read_payload(from_path), system)

    # A plain `Path.exists()`, taken BEFORE any store is constructed, and
    # `None` when absent. `SQLiteStore` connects lazily, so asking the store
    # whether an index exists is itself what creates an empty index.sqlite
    # beside an unindexed repository -- and acceptance requires that none is
    # created.
    index_sqlite_path = paths.index_sqlite_path if paths.index_exists else None

    embedder, embed_reason = build_embedder(paths.manifest, embedding_provider)
    if embed_reason is not None:
        _loud(embed_reason)

    store = open_knowledge_store_for_write(paths)
    try:
        try:
            # `vector_base_dir` is deliberately NOT passed: it defaults to
            # `store.sqlite_path.parent`, the resolved knowledge directory,
            # which is the only correct answer. An index directory would put
            # gr_statements where `index --reset` rmtrees it wholesale.
            result = ingest_extraction(
                store,
                payload,
                paths.repo_root,
                index_sqlite_path=index_sqlite_path,
                embedder=embedder,
                on_notice=_loud,
            )
        except IngestError as exc:
            _loud(
                f"ingest refused: {exc}\n"
                "NOTHING WAS WRITTEN -- no requirements, no citations and no "
                "gr_run row, because the whole SQLite half is one "
                "transaction. Correct that rule in the extractor output and "
                "run the same command again; there is no partial state to "
                "clean up and no resume flag to pass."
            )
            raise typer.Exit(code=1) from exc

        if result.rules_in == 0:
            # Loud, and exiting zero: the gr_run row IS written, so a
            # non-zero exit would tell the caller nothing was stored, which
            # is false. What makes this dangerous is that it looks like a
            # successful ingest in every count, so the loudness is the whole
            # defence -- and the payload's own keys are named because a
            # field-map or file-selection mistake is diagnosable from them.
            _loud(
                f"NO RULES WERE INGESTED. The payload at {from_path} offered "
                f"zero rule objects, so run {result.run_id} records an "
                "extraction of nothing. This is reported rather than treated "
                "as a success: the rule array is named `confirmedRules` by "
                "the workflow and `rules` by older fixtures, and a payload "
                "carrying neither -- or a rule array saved on its own "
                "instead of the workflow's whole return value -- ingests as "
                "zero without failing. The payload's top-level keys were: "
                + (", ".join(sorted(payload)) or "(none)")
            )

        if as_json:
            emit_json(_ingest_json(result, from_path, paths.index_sqlite_path))
        _report(
            _ingest_lines(result, from_path, paths.index_sqlite_path),
            as_json=as_json,
        )
    finally:
        store.close()


# ----------------------------------------------------------------------
# validate
# ----------------------------------------------------------------------


@requirements_app.command("validate")
def validate_cmd(
    gr_id: Annotated[
        Optional[str],
        typer.Option(
            "--gr-id",
            help="Validate one requirement instead of the whole corpus.",
        ),
    ] = None,
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    as_json: JsonOption = False,
) -> None:
    """Report rule-notation violations. Changes nothing; exits 1 on an ERROR.

    Findings carry the stable SPEC-1 identifiers -- V-CLASS-01, V-KW-04,
    V-SLOT-02 and the rest of the twenty-eight -- so a reviewer can cite one.

    This command writes NOTHING. It calls the validator directly rather than
    going through the Step 5 refresh pair, because that pair rewrites gr_fts
    and replaces gr_finding rows, which is a write. The stored gr_finding
    rows are whatever the last ingest, set-field or set-state left; the
    findings reported here are computed live against the current statements
    and are not persisted.

    Only *evaluated* ERROR findings set the exit code. A not-evaluated
    finding is a check that could not be decided -- the pattern is NULL, or
    the slot split degraded rather than guessing a boundary -- and that is
    not the same as passing. Both counts are reported.
    """
    from legacylift_search.gr_refresh import leaked_terms_for
    from legacylift_search.gr_validator import CHECK_IDS, validate_statement

    paths = resolve_requirements_paths(repo_root, config, analysis_dir)
    store = open_knowledge_store(paths)
    index_store = open_index_store(paths)

    # An empty `leaked_terms` because no index was reachable is a DIFFERENT
    # fact from an empty one because the cited files declare no symbols. Only
    # the first is reportable here, and it is the one a reader would
    # otherwise mistake for "V-STY-03 found nothing".
    leaked_terms_available = index_store is not None
    cache: dict[str, frozenset[str]] = {}

    try:
        if gr_id is not None:
            records = store.list_gr([gr_id])
            if not records:
                _loud(
                    f"no requirement {gr_id!r} in "
                    f"{paths.knowledge_sqlite_path}"
                )
                raise typer.Exit(code=1)
        else:
            records = store.list_gr(store.all_gr_ids())

        rows: list[dict] = []
        counts: dict[str, dict[str, int]] = {}
        blocking = 0
        leaked_term_total = 0
        for record in records:
            terms: frozenset[str] = frozenset()
            if index_store is not None:
                terms = leaked_terms_for(store, index_store, record.gr_id, cache)
            leaked_term_total += len(terms)
            for finding in validate_statement(record, terms):
                bucket = counts.setdefault(
                    finding.severity, {"evaluated": 0, "not_evaluated": 0}
                )
                key = "evaluated" if finding.evaluated else "not_evaluated"
                bucket[key] += 1
                if finding.severity == "ERROR" and finding.evaluated:
                    blocking += 1
                rows.append(
                    {
                        "gr_id": record.gr_id,
                        "finding_id": finding.finding_id,
                        "severity": finding.severity,
                        "span": finding.span,
                        "message": finding.message,
                        "evaluated": finding.evaluated,
                    }
                )
    finally:
        if index_store is not None:
            index_store.close()
        store.close()

    lines = [
        f"validated {len(records)} requirement(s) against {len(CHECK_IDS)} "
        "SPEC-1 checks; nothing was written"
    ]
    for row in rows:
        mark = "" if row["evaluated"] else " [NOT EVALUATED]"
        span = row["span"] or "record"
        lines.append(
            f"  {row['gr_id']}  {row['finding_id']}  {row['severity']}{mark}"
            f"  ({span})  {row['message']}"
        )
    for severity in sorted(counts):
        bucket = counts[severity]
        lines.append(
            f"  {severity}: {bucket['evaluated']} evaluated, "
            f"{bucket['not_evaluated']} not evaluated"
        )
    if not counts:
        lines.append("  no findings")
    lines.append(
        "  V-STY-03 identifier leakage: "
        + (
            f"checked against {leaked_term_total} symbol name(s) from the "
            "cited files"
            if leaked_terms_available
            else "NEVER LOOKED FOR -- no index.sqlite at "
            f"{paths.index_sqlite_path}, so the check ran on its "
            "morphological half alone. That is not the same as 'no leakage "
            "found'."
        )
    )
    lines.append(
        f"  blocking (evaluated ERROR) findings: {blocking}"
        + ("" if blocking else " -- nothing blocks approval")
    )

    if as_json:
        emit_json(
            {
                "requirements_validated": len(records),
                "checks_run": len(CHECK_IDS),
                "findings": rows,
                "counts_by_severity": counts,
                "blocking_findings": blocking,
                "leaked_terms_available": leaked_terms_available,
                "leaked_term_count": leaked_term_total,
                "index_sqlite_path": str(paths.index_sqlite_path),
                "wrote_nothing": True,
            }
        )
    _report(lines, as_json=as_json)

    if blocking:
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# set-run-coverage and retire-run -- the two exits from the gate
# ----------------------------------------------------------------------


def _run_lines(run, prefix: str) -> list[str]:
    """One run's four gate-relevant columns, in words for both coverage cases."""
    if run.not_accounted_for is None:
        coverage = "NEVER MEASURED (not zero)"
    else:
        coverage = str(run.not_accounted_for)
    return [
        f"  {prefix} not_accounted_for={coverage}"
        f", coverage_source={run.coverage_source or '(none)'}"
        f", coverage_measured_at={run.coverage_measured_at or '(none)'}"
        f", gate_excluded={1 if run.gate_excluded else 0}"
        f", complete={1 if run.complete else 0}"
    ]


@requirements_app.command("set-run-coverage")
def set_run_coverage_cmd(
    run_id: Annotated[str, typer.Argument(help="The gr_run.run_id to stamp.")],
    not_accounted_for: Annotated[
        int,
        typer.Option(
            "--not-accounted-for",
            help=(
                "The re-measured count of indexed chunks no citation claims. "
                "Required, and 0 is a real measurement meaning 'nothing left "
                "over'. There is deliberately no way to record 'not "
                "measured' here -- that is what the column already says "
                "before you run this."
            ),
        ),
    ],
    measured_at: Annotated[
        Optional[str],
        typer.Option(
            "--measured-at",
            help="When the measurement was taken (default: now, UTC ISO-8601).",
        ),
    ] = None,
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    as_json: JsonOption = False,
) -> None:
    """Record a coverage figure that was independently RE-MEASURED.

    The first of the two exits from the completeness gate, and it records a
    measurement somebody actually took: it stamps coverage_source =
    'remeasured' and coverage_measured_at, so the audit question -- why did
    this run stop blocking the export? -- is answered by "because it was
    measured, on this date".

    Use retire-run instead when no measurement was taken and the run is
    simply superseded. The two are separate commands because they are
    different acts with different audit meaning, and one command carrying
    both would make that question unanswerable without reading the columns.
    """
    paths = resolve_requirements_paths(repo_root, config, analysis_dir)
    store = open_knowledge_store(paths)
    try:
        before = store.get_gr_run(run_id)
        stamp = measured_at or _now()
        try:
            store.set_gr_run_coverage(
                run_id, not_accounted_for=not_accounted_for, measured_at=stamp
            )
        except ValueError as exc:
            _loud(f"set-run-coverage refused: {exc}")
            raise typer.Exit(code=1) from exc
        after = store.get_gr_run(run_id)
    finally:
        store.close()

    # `set_gr_run_coverage` raises on an unknown run_id, so `after` is a row.
    if after is None:  # pragma: no cover - unreachable via the writer above
        raise typer.Exit(code=1)
    lines = [
        f"run {run_id}: coverage re-measured as {not_accounted_for} at {stamp}"
    ]
    if before is not None:
        lines += _run_lines(before, "before:")
    lines += _run_lines(after, " after:")
    if not after.complete:
        lines.append(
            "  the run still does NOT pass the completeness gate: "
            f"{after.not_accounted_for} chunk(s) remain unaccounted for. "
            "`requirements export` will refuse it without --allow-incomplete."
        )
    if as_json:
        emit_json(
            {
                "run_id": run_id,
                "not_accounted_for": after.not_accounted_for,
                "coverage_source": after.coverage_source,
                "coverage_measured_at": after.coverage_measured_at,
                "gate_excluded": bool(after.gate_excluded),
                "complete": after.complete,
            }
        )
    _report(lines, as_json=as_json)


@requirements_app.command("retire-run")
def retire_run_cmd(
    run_id: Annotated[str, typer.Argument(help="The gr_run.run_id to retire.")],
    reason: Annotated[
        str,
        typer.Option(
            "--reason",
            help=(
                "Why this run no longer counts. Required and non-empty: the "
                "audit question is why the run stopped blocking the gate, "
                "and a blank reason has no answer to it."
            ),
        ),
    ],
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    as_json: JsonOption = False,
) -> None:
    """Exclude a superseded run from the completeness gate, with a reason.

    The second of the two exits from the gate, and it records a human's
    judgement rather than a measurement. It writes gate_excluded and
    gate_excluded_reason and leaves not_accounted_for -- and therefore the
    generated `complete` column -- untouched, so the record still says what
    was actually known about the run. Overwriting the coverage figure while
    retiring a run would forge a measurement to justify the judgement.

    Use set-run-coverage instead when a figure was actually re-measured.
    """
    paths = resolve_requirements_paths(repo_root, config, analysis_dir)
    store = open_knowledge_store(paths)
    try:
        before = store.get_gr_run(run_id)
        try:
            store.retire_gr_run(run_id, reason=reason)
        except ValueError as exc:
            _loud(f"retire-run refused: {exc}")
            raise typer.Exit(code=1) from exc
        after = store.get_gr_run(run_id)
    finally:
        store.close()

    # `retire_gr_run` raises on an unknown run_id, so `after` is a row.
    if after is None:  # pragma: no cover - unreachable via the writer above
        raise typer.Exit(code=1)
    lines = [f"run {run_id} retired from the completeness gate: {reason}"]
    if before is not None:
        lines += _run_lines(before, "before:")
    lines += _run_lines(after, " after:")
    lines.append(
        "  not_accounted_for and `complete` are deliberately unchanged: this "
        "records a judgement, not a measurement, and the record still says "
        "what was actually known."
    )
    if as_json:
        emit_json(
            {
                "run_id": run_id,
                "gate_excluded": bool(after.gate_excluded),
                "gate_excluded_reason": after.gate_excluded_reason,
                "not_accounted_for": after.not_accounted_for,
                "complete": after.complete,
            }
        )
    _report(lines, as_json=as_json)
