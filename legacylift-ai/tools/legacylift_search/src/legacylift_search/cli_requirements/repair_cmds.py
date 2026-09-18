"""Repair and transport: `reindex-vectors`, `rederive-subjects`, `export`, `import`.

Milestone 1, Steps 8 and 9 of `docs/exec-plans/active/reqs-to-data-store.md`.
This module owns exactly these four registrations on `requirements_app` and no
others (the assignment is tabulated in this package's `__init__.py`):

* ``reindex-vectors`` -- rebuild the `gr_statements` collection from the `gr`
  rows, by wiring `gr_refresh.reindex_gr_vectors`. Step 5's **single
  documented recovery** for four different failures: a reset that reached the
  collection, a missing embedder, a failed embedding call, and a provider
  switch (under which the collection is unusable rather than stale, because
  its dimension no longer matches). Report what it embedded, skipped and
  deleted; it is safe to run twice.
* ``rederive-subjects`` -- recompute `subject` and `subject_provenance` from
  *current* `file_domains` after a domain retag, by wiring
  `gr_rederive.rederive_subjects`. Report the `llm_named -> derived`
  transitions **and** the reverse `derived -> derived_ambiguous` direction as
  separate figures: the first is the case this command exists for, and the
  second means the corpus now holds rules mined from code the analyst has
  since declared out of scope. Report `skipped` too -- "0 changed, 471
  skipped" on a second run is a positive confirmation, and an unreported
  zero is an ambiguous silence.
* ``export`` -- `--format jsonl` writes one JSON object per requirement,
  sorted by `gr_id`, to `<analysis-dir>/knowledge/requirements.jsonl`, by
  wiring `gr_export.export_jsonl`. It refuses an incomplete corpus
  (`IncompleteCorpusError`, whose `blocking` map already carries the reason
  per run **in the words Step 3 mandates**) unless `--allow-incomplete` is
  passed, in which case the incompleteness is written into the file itself as
  the single reserved `_incomplete` header object. **Nothing that changes
  between two runs over unchanged data may reach the file** -- no timestamp,
  no counter, no tool version -- which is what makes "the second export is
  byte-identical" a real criterion; the function already holds that property,
  so the command must not add a provenance line of its own.
* ``import`` -- `--from-jsonl` reads it back, by wiring
  `gr_export.import_records`. **Import happens only when explicitly invoked
  -- never on open, never implicitly** -- so a stale checkout cannot
  overwrite approved state or human-authored fields behind the analyst's
  back, and the help text must say that. It is the one declared exception to
  "`set_state` is the only writer of `gr.state`", and its four guard rails
  are `gr_export.IMPORT_GUARDRAILS`: **render those words in the help text
  rather than re-describing them**, so a reviewer reading `--help` and a
  reviewer reading the module see the identical rule. It reports
  `rows_refused_downgrade` **and names the protected records**, because
  `rows_changed_state == 0` alone is ambiguous between "the file agreed
  with the store" and "every state change in the file was refused" -- and
  it takes `--embedding-provider` like the other write paths, so its
  vector half is populated rather than degrading unconditionally.

**These four share the resumable-repair shape the plan names**, which is why
they are grouped: each recomputes or restores a durable value, processes only
what is stale, reports what it changed and what it skipped, and is safe to
run twice. `backfill-vectors` (`cli.py`) and Step 2's `backfill-hashes` are
the two earlier members; a fifth will be added, so keep the shape.

Two reporting rules bind every command here. A degraded vector half
(`EmbedResult.reason` is non-None) **exits zero** and names
`requirements reindex-vectors` -- including inside `reindex-vectors` itself,
where a still-missing embedder means the recovery could not run and the
message has to say that rather than reporting a successful rebuild of
nothing. And `import`'s embed half is likewise allowed to degrade.

`import` may **create** the knowledge database -- restoring into a fresh
checkout is a legitimate use -- so it uses
`_shared.open_knowledge_store_for_write`. The other three require an existing
store and use `_shared.open_knowledge_store`, which probes `Path.exists()`
before constructing anything.

One implementation note that is a deliberate choice rather than an oversight.
Every logic import in this module is **deferred into the command body**, and
the four guard-rail sentences `import --help` renders are a verbatim tuple
here rather than an import of `gr_export.IMPORT_GUARDRAILS`. Typer needs a
command's help text at decoration time, so importing that constant at module
scope would pull `pydantic`, `knowledge_store` and the models into every
`legacylift-search --help` -- measured at +0.6s against a 0.3s baseline, and
contradicting `cli.py`'s stated reason for registering this sub-app at module
scope at all ("`cli_requirements` imports only `typer` at module scope"). The
copy is held in step by an **equality** assertion in
`tests/test_cli_req_repair.py` rather than by anyone remembering, which is
strictly stronger than the substring check a hand-written paraphrase would
allow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final, List, Optional

import typer

from legacylift_search.cli_requirements import requirements_app as requirements_app
from legacylift_search.cli_requirements._shared import (
    AnalysisDirOption,
    ConfigOption,
    EmbeddingProviderOption,
    JsonOption,
    RepoRootOption,
    RequirementsPaths,
    build_embedder,
    emit_json,
    open_index_store,
    open_knowledge_store,
    open_knowledge_store_for_write,
    resolve_requirements_paths,
)

__all__ = [
    "REQUIREMENTS_JSONL_NAME",
    "export_cmd",
    "import_cmd",
    "rederive_subjects_cmd",
    "reindex_vectors_cmd",
]


#: The export's filename, a **sibling of `knowledge.sqlite`** inside the
#: resolved knowledge directory -- `analysis/<system>/knowledge/`. Deliberately
#: a sibling, so the relationship between the authoritative store and its
#: diffable mirror is obvious from a directory listing (Step 9).
REQUIREMENTS_JSONL_NAME: Final[str] = "requirements.jsonl"

#: How many individual per-record lines the text mode of `rederive-subjects`
#: (subject changes) and `import` (records protected from a downgrade)
#: prints. A cap, so the count is always rendered as "N of M shown": a
#: listing truncated silently is the same absent-versus-real defect as an
#: unmeasured count stored as zero, and this plan has ten instances of it.
#: `--json` carries the whole list.
_CHANGES_SHOWN: Final[int] = 20

#: A **verbatim** copy of `gr_export.IMPORT_GUARDRAILS`, held here so the
#: `import` help text can be built at decoration time without a module-scope
#: import of `gr_export` (see this module's docstring for the measurement).
#:
#: **The copy is asserted EQUAL, element for element, by
#: `tests/test_cli_req_repair.py`**, so drift fails a test rather than
#: leaving `--help` describing rules the function no longer follows. That is
#: the whole reason this is a tuple compared against the original rather than
#: prose in a docstring: prose cannot be compared.
_IMPORT_GUARDRAILS: Final[tuple[str, ...]] = (
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

_IMPORT_HELP: Final[str] = (
    "Restore requirements from a JSONL export (Step 9).\n\n"
    "IMPORT HAPPENS ONLY WHEN EXPLICITLY INVOKED -- never on open, never "
    "implicitly, never as a side effect of another command -- so a stale "
    "checkout cannot overwrite approved state or human-authored fields "
    "behind an analyst's back.\n\n"
    "It is the ONE declared exception to \"set-state is the only writer of "
    "gr.state\". The rule exists to stop automation approving its own "
    "output; import is not automation deciding anything, it restores "
    "judgements a human already recorded in this same store and which the "
    "JSONL merely transported. Routing it through set-state would re-run "
    "the approval gate, so a requirement legitimately approved on a machine "
    "whose tree matched the citations would be REFUSED on a checkout where "
    "the cited code has since drifted -- approvals would be un-restorable "
    "exactly when the store is most needed.\n\n"
    "The four guard rails, verbatim:\n\n"
    + "\n\n".join(f"  {n}. {rule}" for n, rule in enumerate(_IMPORT_GUARDRAILS, 1))
    + "\n\nA leading `_incomplete` header object written by "
    "`export --allow-incomplete` is skipped rather than treated as a "
    "record, so no requirement is created from it.\n\n"
    "The vector half is populated with the embedder this command resolves, "
    "the same as every other write path -- pass --embedding-provider to "
    "override the manifest. If no provider can be built the rows still "
    "land, keyword search still works, and the report says the semantic "
    "half is behind and names `requirements reindex-vectors` as the "
    "recovery. That is a degraded success and this command exits zero: an "
    "unreachable provider must never look like data loss."
)

#: `--gr-id`, repeatable. Only `rederive-subjects` takes it, so it lives here
#: rather than in `_shared`, which holds only what several commands share.
GrIdOption = Annotated[
    Optional[List[str]],
    typer.Option(
        "--gr-id",
        help=(
            "Restrict to these requirements (repeatable). Default: every "
            "row, which is the ordinary case -- a retag changes the domain "
            "set globally and finding out which rows it moved is the job."
        ),
    ),
]


# ----------------------------------------------------------------------
# Shared plumbing for the four commands in this module
# ----------------------------------------------------------------------


def _resolve_or_exit(
    repo_root: Optional[Path],
    config: Optional[Path],
    analysis_dir: Optional[Path],
) -> RequirementsPaths:
    """`resolve_requirements_paths` with a clean message, not a traceback.

    A missing `--repo-root` or an unreadable manifest is a user error, and a
    traceback buries the one line that says which. The resolved-path banner
    itself goes to stderr inside `resolve_requirements_paths`, so stdout
    stays parseable for a `--json` caller.
    """
    try:
        return resolve_requirements_paths(repo_root, config, analysis_dir)
    except Exception as exc:
        typer.echo(f"could not resolve paths: {exc}", err=True)
        raise typer.Exit(code=1)


def _collection_count_or_none(store, embedder) -> Optional[int]:
    """How many ids `gr_statements` holds, or `None` for **not measured**.

    `None` and `0` are different facts, and this plan's recurring defect is
    exactly the two sharing an encoding. `0` means an empty collection;
    `None` means the collection could not be opened at all -- no embedder
    (chromadb wants the dimension at creation time), no provider, a
    dimension mismatch -- so the run cannot say whether every requirement
    has a vector. A caller must report the difference rather than printing a
    shortfall of zero, which would read as "the rebuild worked".
    """
    if embedder is None:
        return None
    from legacylift_search.gr_refresh import open_gr_collection

    collection = None
    try:
        collection = open_gr_collection(store, embedder)
        return int(collection.count())
    except Exception:
        return None
    finally:
        if collection is not None:
            try:
                collection.close()
            except Exception:  # pragma: no cover - Windows handle release
                pass


def _echo_embed_outcome(embed, *, what: str) -> None:
    """Print an `EmbedResult`'s degradation to **stderr**; nothing if clean.

    `EmbedResult.reason` is non-None exactly when something was skipped, and
    it already names `requirements reindex-vectors` as the recovery, so it is
    printed rather than reworded. It goes to stderr in both output modes so a
    human watching a `--json` run still sees that the semantic half is
    behind, and **no caller exits non-zero on it**: an unreachable provider
    must not read as data loss.
    """
    if embed.reason:
        typer.echo(
            f"{what}: the semantic half is degraded -- {embed.reason}",
            err=True,
        )


# ----------------------------------------------------------------------
# reindex-vectors
# ----------------------------------------------------------------------


@requirements_app.command("reindex-vectors")
def reindex_vectors_cmd(
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    embedding_provider: EmbeddingProviderOption = None,
    json_output: JsonOption = False,
) -> None:
    """Rebuild the gr_statements collection from the gr rows.

    Step 5's SINGLE DOCUMENTED RECOVERY for four different failures, which
    is why it is one command and not four:

      1. an `index --reset` that reached the collection;
      2. a run made with no embedder configured;
      3. an embedding call that failed mid-run;
      4. a switch of embedding provider, under which the existing collection
         is unusable rather than merely stale because its dimension no
         longer matches.

    Each of those leaves SQLite correct and the vector half behind, and a
    stale collection answers a near-duplicate query with zero candidates --
    indistinguishable from "there are no near duplicates".

    It re-embeds EVERY row rather than diffing against the collection: this
    is the recovery path, so the reason a vector is absent is by definition
    unknown here, and an id-by-id diff would trust the very state that is
    suspect. It first sweeps the ids the collection holds that `gr` does
    not, so a requirement deleted while the collection was stale does not
    keep a searchable ghost. Safe to run twice.

    The collection lives under the KNOWLEDGE directory
    (`analysis/<system>/knowledge/chroma`), never the index directory: an
    `index --reset` rmtrees the index directory's collections wholesale, and
    being out of its reach is the whole reason for that location.

    A degraded run EXITS ZERO. An unreachable provider must not read as data
    loss -- the requirements themselves are untouched and keyword search
    works.
    """
    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    store = open_knowledge_store(paths)
    try:
        from legacylift_search.gr_refresh import (
            describe_vector_shortfall,
            reindex_gr_vectors,
        )

        embedder, embedder_reason = build_embedder(paths.manifest, embedding_provider)
        if embedder_reason:
            typer.echo(embedder_reason, err=True)

        gr_count = store.count_gr()
        before_count = _collection_count_or_none(store, embedder)
        before_shortfall = (
            describe_vector_shortfall(gr_count, before_count)
            if before_count is not None
            else None
        )

        # `base_dir` is left to default. `reindex_gr_vectors` resolves it to
        # `store.sqlite_path.parent`, the resolved KNOWLEDGE directory --
        # never pass an index directory here, per the docstring.
        result = reindex_gr_vectors(store, embedder=embedder)

        after_count = _collection_count_or_none(store, embedder)
        after_shortfall = (
            describe_vector_shortfall(gr_count, after_count)
            if after_count is not None
            else None
        )
    finally:
        store.close()

    _echo_embed_outcome(result, what="reindex-vectors")

    if after_count is None:
        # NOT the same as a shortfall of zero: nothing could be counted.
        typer.echo(
            "vector shortfall: NOT MEASURED -- the gr_statements collection "
            "could not be opened, so this run cannot say whether every "
            "requirement has a vector. Configure an embedding provider and "
            "re-run `legacylift-search requirements reindex-vectors`.",
            err=True,
        )
    elif after_shortfall is not None:
        typer.echo(after_shortfall, err=True)

    if json_output:
        emit_json(
            {
                "command": "reindex-vectors",
                "gr_count": gr_count,
                "embedded": result.embedded,
                "skipped": result.skipped,
                "deleted": result.deleted,
                "degraded": result.degraded,
                "reason": result.reason,
                "collection_count_before": before_count,
                "collection_count_after": after_count,
                # A null shortfall is ambiguous on its own, so the measured
                # flag travels beside it: false means "could not look".
                "shortfall_measured": after_count is not None,
                "shortfall_before": before_shortfall,
                "shortfall_after": after_shortfall,
            }
        )
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Reindex Vectors Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("gr_rows", str(gr_count))
    table.add_row("embedded", str(result.embedded))
    table.add_row("skipped", str(result.skipped))
    table.add_row("deleted (orphans + absent rows)", str(result.deleted))
    table.add_row(
        "collection_count",
        "not measured" if after_count is None else str(after_count),
    )
    console.print(table)

    if after_count is not None and after_shortfall is None:
        # Say so rather than printing nothing: silence after a repair is
        # indistinguishable from a repair that never ran.
        console.print(
            f"[green]No shortfall: all {gr_count} requirement(s) have a "
            f"vector in gr_statements.[/green]"
        )
    elif after_count is not None:
        console.print(
            "[yellow]The collection is still behind gr -- see the shortfall "
            "line above.[/yellow]"
        )
    else:
        console.print(
            "[yellow]The rebuild could not run: no usable collection. The "
            "requirements are stored and keyword search works.[/yellow]"
        )


# ----------------------------------------------------------------------
# rederive-subjects
# ----------------------------------------------------------------------


@requirements_app.command("rederive-subjects")
def rederive_subjects_cmd(
    gr_id: GrIdOption = None,
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    embedding_provider: EmbeddingProviderOption = None,
    json_output: JsonOption = False,
) -> None:
    """Recompute subject and subject_provenance from current file_domains.

    THIS COMMAND EXISTS BECAUSE NOTHING ELSE RE-DERIVES A SUBJECT AFTER THE
    DOMAIN SET CHANGES, AND THE STALENESS IS SILENT. Both columns are
    computed from `file_domains` at ingest, so re-running `tag-domains` with
    a changed `domains.json` leaves every subject describing the PREVIOUS
    domain set with nothing anywhere reporting it -- which silently corrupts
    the `derived` rate in `requirements stats`, the one check this
    milestone's Concrete Steps put in front of an implementer.

    It applies the same majority-domain rule, the same statement-[Subject]
    fallback and the same three-value provenance as ingest, through the one
    shipped derivation, so the two can never disagree. It applies the
    two-sentinel rule too, so a file since added to `exclude_globs` moves
    from `derived` to `derived_ambiguous` rather than keeping a subject the
    domain set no longer yields.

    IT DOES NOT TOUCH `statement`, AND IT TOUCHES NO KEY. An earlier design
    had it re-template the statement; the extractor now authors that column,
    so there is no template to re-fill and no mechanical way to substitute a
    new subject into someone else's sentence. The staleness that leaves is
    smaller and honest: a requirement's TEXT may name a subject the domain
    set no longer derives while the `subject` column says what the
    derivation now yields, and the divergence between them is visible in
    `requirements show`. Both dedupe keys, every citation anchor and every
    statement are byte-identical across this command.

    BOTH TRANSITION DIRECTIONS ARE REPORTED, BECAUSE THEY MEAN OPPOSITE
    THINGS. `llm_named -> derived` is a file that was `unassigned` at ingest
    and has since been tagged -- the case this command exists for, and one
    that never resolves without it. `derived -> derived_ambiguous` is a
    newly EXCLUDED file, which means the corpus now holds rules mined from
    code the analyst has since declared out of scope. A `derived` rate that
    can only fall as a corpus ages would quietly undermine the one check the
    plan puts in front of you, so the fall is attributed rather than merely
    observed. A third bucket, `subject_only_changes`, is a renamed domain:
    the subject moved and the provenance did not.

    Resumable and safe to run twice -- the second run finds every derivation
    current, writes nothing, and reports every row as skipped. A degraded
    vector half exits zero.
    """
    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    store = open_knowledge_store(paths)
    index_store = None
    try:
        from legacylift_search.gr_rederive import rederive_subjects

        # Opened inside the `try` so a failure here still closes the
        # knowledge store. `None` is a supported state, not an error path:
        # `V-STY-03` then re-runs on its morphological half alone, and the
        # report below says which of the two it was.
        index_store = open_index_store(paths)

        embedder, embedder_reason = build_embedder(paths.manifest, embedding_provider)
        if embedder_reason:
            typer.echo(embedder_reason, err=True)

        result = rederive_subjects(
            store,
            list(gr_id) if gr_id else None,
            embedder=embedder,
            index_store=index_store,
            repo_root=paths.repo_root,
        )
    finally:
        if index_store is not None:
            index_store.close()
        store.close()

    _echo_embed_outcome(result.embed, what="rederive-subjects")
    if result.changed and not result.refresh.leaked_terms_available:
        typer.echo(
            "no Layer-0 index was reachable, so V-STY-03 re-ran on its "
            "morphological half alone -- identifier leakage was not looked "
            "for, which is not the same as none being found.",
            err=True,
        )

    transitions = [
        {"from": old, "to": new, "count": count}
        for (old, new), count in sorted(
            result.provenance_transitions.items(),
            key=lambda item: (item[0][0] or "", item[0][1]),
        )
    ]

    if json_output:
        emit_json(
            {
                "command": "rederive-subjects",
                "examined": result.examined,
                "changed": result.changed,
                "skipped": result.skipped,
                "llm_named_to_derived": result.llm_named_to_derived,
                "derived_to_derived_ambiguous": result.derived_to_derived_ambiguous,
                "subject_only_changes": result.subject_only_changes,
                # Tuple keys are not JSON, and stringifying them would fold
                # a `None` old provenance into the literal "None". A list of
                # objects keeps the null a null.
                "provenance_transitions": transitions,
                "changes": [
                    {
                        "gr_id": change.gr_id,
                        "old_subject": change.old_subject,
                        "new_subject": change.new_subject,
                        "old_provenance": change.old_provenance,
                        "new_provenance": change.new_provenance,
                    }
                    for change in result.changes
                ],
                "refresh": {
                    "refreshed": result.refresh.refreshed,
                    "findings_written": result.refresh.findings_written,
                    "leaked_terms_available": result.refresh.leaked_terms_available,
                },
                "embed": {
                    "embedded": result.embed.embedded,
                    "skipped": result.embed.skipped,
                    "degraded": result.embed.degraded,
                    "reason": result.embed.reason,
                },
            }
        )
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Rederive Subjects Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("examined", str(result.examined))
    table.add_row("changed", str(result.changed))
    table.add_row("skipped (already current)", str(result.skipped))
    table.add_row("llm_named -> derived", str(result.llm_named_to_derived))
    table.add_row(
        "derived -> derived_ambiguous", str(result.derived_to_derived_ambiguous)
    )
    table.add_row("subject only (domain renamed)", str(result.subject_only_changes))
    table.add_row("vectors re-embedded", str(result.embed.embedded))
    console.print(table)

    if result.llm_named_to_derived:
        console.print(
            f"{result.llm_named_to_derived} requirement(s) stopped being "
            "model-named: their cited files have been tagged since ingest. "
            "Nothing else in the system makes that happen."
        )
    if result.derived_to_derived_ambiguous:
        console.print(
            f"[yellow]{result.derived_to_derived_ambiguous} requirement(s) "
            "moved derived -> derived_ambiguous: their cited code is now "
            "EXCLUDED by domains.json, so this corpus holds rules mined "
            "from code declared out of scope. The `derived` rate in "
            "`requirements stats` falls for that reason, not because the "
            "derivation stopped working.[/yellow]"
        )
    if result.subject_only_changes:
        console.print(
            f"{result.subject_only_changes} requirement(s) kept their "
            "provenance and moved subject -- a renamed domain, not a "
            "reassigned file."
        )

    if transitions:
        console.print("provenance transitions:")
        for entry in transitions:
            console.print(
                f"  {entry['from'] or '(none)'} -> {entry['to']}: "
                f"{entry['count']}"
            )

    if result.changes:
        shown = result.changes[:_CHANGES_SHOWN]
        console.print(
            f"changes ({len(shown)} of {len(result.changes)} shown; --json "
            "carries all):"
        )
        for change in shown:
            old_subject = (
                change.old_subject if change.old_subject is not None else "(none)"
            )
            new_subject = (
                change.new_subject if change.new_subject is not None else "(none)"
            )
            console.print(
                f"  {change.gr_id}: {old_subject} "
                f"[{change.old_provenance or '(none)'}] -> {new_subject} "
                f"[{change.new_provenance}]"
            )
        console.print(
            "Statements were NOT rewritten. A requirement's text may still "
            "name the old subject; `requirements show` makes that divergence "
            "visible."
        )
    else:
        console.print(
            f"[green]Every derivation was already current: 0 changed, "
            f"{result.skipped} skipped.[/green]"
        )


# ----------------------------------------------------------------------
# export
# ----------------------------------------------------------------------


@requirements_app.command("export")
def export_cmd(
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help=(
                "Write here instead of <knowledge-dir>/requirements.jsonl. "
                "A relative value resolves against the current directory, "
                "like every other path flag on this CLI."
            ),
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Export format. `jsonl` is the only one Milestone 1 writes.",
        ),
    ] = "jsonl",
    allow_incomplete: Annotated[
        bool,
        typer.Option(
            "--allow-incomplete",
            help=(
                "Export a corpus whose contributing runs are incomplete or "
                "never measured, writing that fact into the file as one "
                "reserved `_incomplete` header object naming each offending "
                "run_id and its reason IN WORDS. Without this flag such an "
                "export is REFUSED and there is no header line at all."
            ),
        ),
    ] = False,
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    json_output: JsonOption = False,
) -> None:
    """Write the requirements to a git-committable JSONL file.

    One JSON object per requirement, sorted by gr_id, with keys sorted
    within each object and `\\n` line endings regardless of host -- so a
    team can review requirement changes in a pull request and a single
    reworded statement shows up as a one-line diff.

    THIS FILE IS THE DURABLE BACKUP. `knowledge.sqlite` is gitignored, so a
    copy of it inside the repository is NOT protected by git; this JSONL
    sibling is what survives a lost working tree. The database stays
    authoritative and this is a deterministic mirror of it.

    NOTHING THAT VARIES BETWEEN TWO RUNS OVER UNCHANGED DATA REACHES THE
    FILE -- no export timestamp, no run counter, no tool version. That is
    what makes "the second export is byte-identical" a real criterion rather
    than a near-miss, and it is trivial to violate by adding a helpful
    provenance header. Per-record `created_at`/`updated_at` ARE included:
    they are properties of the record, so they move only when the record
    does, which is exactly what a diff should show.

    An incomplete corpus is REFUSED with a non-zero exit unless
    `--allow-incomplete` is passed, because the export is what leaves the
    machine and reaches a client, and an incomplete corpus presented as
    complete is the specific failure the completeness gate exists to
    prevent. Under the flag the file opens with one `_incomplete` object
    naming the offending run_ids and, per run, which of the two reasons
    applies in words -- chunks unaccounted for, or coverage never measured,
    which call for different actions. That header carries no timestamp,
    counter or tool version, so two exports with the flag over an unchanged
    store are still byte-identical.

    Domain data (`file_domains`) is not exported. That is a real gap, and it
    belongs to domain-tagging scope rather than to this command.
    """
    if output_format.lower() != "jsonl":
        typer.echo(
            f"unsupported --format {output_format!r}: `jsonl` is the only "
            "format Milestone 1 writes.",
            err=True,
        )
        raise typer.Exit(code=2)

    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    output_path = (
        output.resolve()
        if output is not None
        else paths.knowledge_dir / REQUIREMENTS_JSONL_NAME
    )
    store = open_knowledge_store(paths)
    try:
        from legacylift_search.gr_export import IncompleteCorpusError, export_jsonl

        try:
            result = export_jsonl(
                store, output_path, allow_incomplete=allow_incomplete
            )
        except IncompleteCorpusError as exc:
            # A clean message and a non-zero exit, not a traceback. The
            # exception already names each blocking run and its reason in the
            # words Step 3 mandates, so it is printed rather than reworded.
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1)
    finally:
        store.close()

    if json_output:
        emit_json(
            {
                "command": "export",
                "format": "jsonl",
                "output_path": str(output_path),
                "requirement_count": result.requirement_count,
                "incomplete_run_ids": list(result.incomplete_run_ids),
                "incomplete_header_written": bool(result.incomplete_run_ids),
            }
        )
        return

    from rich.console import Console

    console = Console()
    console.print(
        f"Exported {result.requirement_count} requirement(s) to {output_path}"
    )
    if result.incomplete_run_ids:
        console.print(
            "[yellow]This corpus is incomplete. The file opens with an "
            "`_incomplete` header naming "
            f"{len(result.incomplete_run_ids)} run(s): "
            f"{', '.join(result.incomplete_run_ids)}.[/yellow]"
        )
    console.print(
        "knowledge.sqlite is gitignored, so a copy of it inside the "
        "repository is not protected by git. This file is what survives -- "
        "commit it."
    )


# ----------------------------------------------------------------------
# import
# ----------------------------------------------------------------------


@requirements_app.command("import", help=_IMPORT_HELP)
def import_cmd(
    from_jsonl: Annotated[
        Optional[Path],
        typer.Option(
            "--from-jsonl",
            help=(
                "The export to restore from. Default: "
                "<knowledge-dir>/requirements.jsonl, the file `export` "
                "writes. A relative value resolves against the current "
                "directory."
            ),
        ),
    ] = None,
    allow_downgrade: Annotated[
        bool,
        typer.Option(
            "--allow-downgrade",
            help=(
                "Permit the import to LOWER a record's state (approved -> "
                "draft, approved -> rejected, superseded -> approved). "
                "Refused by default: a stale checkout's most likely damage "
                "is un-approving work, and this flag makes that deliberate. "
                "Note the ranking puts `superseded` ABOVE `approved` rather "
                "than level with it -- level made the comparison a tie in "
                "both directions, so a stale export would silently restore "
                "`approved` over a record the store had since superseded, "
                "reverting a human's judgement and orphaning superseded_by "
                "with no flag required."
            ),
        ),
    ] = False,
    repo_root: RepoRootOption = None,
    config: ConfigOption = None,
    analysis_dir: AnalysisDirOption = None,
    embedding_provider: EmbeddingProviderOption = None,
    json_output: JsonOption = False,
) -> None:
    paths = _resolve_or_exit(repo_root, config, analysis_dir)
    jsonl_path = (
        from_jsonl.resolve()
        if from_jsonl is not None
        else paths.knowledge_dir / REQUIREMENTS_JSONL_NAME
    )
    # Probed BEFORE the store is opened for write. `import` is one of only
    # two commands permitted to create the database, and a typo'd path must
    # not leave an empty knowledge store behind as the side effect of a
    # failure -- an empty store is indistinguishable from a real one on the
    # next command.
    if not jsonl_path.exists():
        typer.echo(
            f"no export to import at {jsonl_path}. Run `legacylift-search "
            "requirements export` first, or pass --from-jsonl.",
            err=True,
        )
        raise typer.Exit(code=1)

    store = open_knowledge_store_for_write(paths)
    index_store = None
    try:
        from legacylift_search.gr_export import import_records

        # Opened inside the `try` so a failure here still closes the store.
        # `None` is a supported state, not an error path: `V-STY-03` then
        # re-runs on its morphological half alone, and the report below says
        # which of the two it was.
        index_store = open_index_store(paths)

        # The SAME embedder handling every other write path in this group
        # uses. Threading it is what stops `import`'s vector half degrading
        # unconditionally; `None` is still a degraded success and still
        # exits zero.
        embedder, embedder_reason = build_embedder(paths.manifest, embedding_provider)
        if embedder_reason:
            typer.echo(embedder_reason, err=True)

        try:
            result = import_records(
                store,
                jsonl_path,
                allow_downgrade,
                embedder=embedder,
                index_store=index_store,
                repo_root=paths.repo_root,
            )
        except Exception as exc:
            typer.echo(f"import failed, nothing was written: {exc}", err=True)
            raise typer.Exit(code=1)
    finally:
        if index_store is not None:
            index_store.close()
        store.close()

    _echo_embed_outcome(result.embed_result, what="import")
    if result.rows_read and not result.refresh_result.leaked_terms_available:
        typer.echo(
            "no Layer-0 index was reachable, so V-STY-03 re-ran on its "
            "morphological half alone -- identifier leakage was not looked "
            "for, which is not the same as none being found.",
            err=True,
        )
    if result.refused_downgrades:
        # To stderr as well as into the report below, so a human watching a
        # `--json` run sees that the file disagreed with the store and was
        # overruled. A protected approval is the single most useful thing
        # this command can say.
        typer.echo(
            f"import protected {result.rows_refused_downgrade} record(s) "
            "from a state downgrade this file would have applied. Re-export "
            "from the machine holding the newer state, or pass "
            "--allow-downgrade to apply it deliberately.",
            err=True,
        )

    if json_output:
        emit_json(
            {
                "command": "import",
                "source_path": str(jsonl_path),
                "rows_read": result.rows_read,
                "rows_changed_state": result.rows_changed_state,
                # A measured zero, and NOT the same fact as
                # `rows_changed_state == 0`: this one says the guard ran and
                # found nothing to protect, while that one is ambiguous
                # between agreement and wholesale refusal without this key
                # beside it.
                "rows_refused_downgrade": result.rows_refused_downgrade,
                "refused_downgrades": [
                    {
                        "gr_id": refused.gr_id,
                        "stored_state": refused.stored_state,
                        "incoming_state": refused.incoming_state,
                        "stored_reviewed_by": refused.stored_reviewed_by,
                    }
                    for refused in result.refused_downgrades
                ],
                "gr_ids_touched": len(result.gr_ids),
                "allow_downgrade": allow_downgrade,
                "vectors_populated": not result.embed_result.degraded,
                "refresh": {
                    "refreshed": result.refresh_result.refreshed,
                    "findings_written": result.refresh_result.findings_written,
                    "leaked_terms_available": (
                        result.refresh_result.leaked_terms_available
                    ),
                },
                "embed": {
                    "embedded": result.embed_result.embedded,
                    "skipped": result.embed_result.skipped,
                    "degraded": result.embed_result.degraded,
                    "reason": result.embed_result.reason,
                },
            }
        )
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Import Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("source", str(jsonl_path))
    table.add_row("rows_read", str(result.rows_read))
    table.add_row("rows_changed_state", str(result.rows_changed_state))
    table.add_row(
        "rows_refused_downgrade (protected)", str(result.rows_refused_downgrade)
    )
    table.add_row("gr_ids_touched", str(len(result.gr_ids)))
    table.add_row("allow_downgrade", str(allow_downgrade))
    table.add_row("vectors embedded", str(result.embed_result.embedded))
    table.add_row(
        "vectors_populated",
        "no (see the note above)" if result.embed_result.degraded else "yes",
    )
    console.print(table)

    if result.refused_downgrades:
        shown = result.refused_downgrades[:_CHANGES_SHOWN]
        console.print(
            f"[yellow]protected from a downgrade ({len(shown)} of "
            f"{len(result.refused_downgrades)} shown; --json carries "
            "all):[/yellow]"
        )
        for refused in shown:
            reviewer = refused.stored_reviewed_by or "(no reviewer recorded)"
            console.print(
                f"  {refused.gr_id}: kept {refused.stored_state} "
                f"[{reviewer}] rather than the file's "
                f"{refused.incoming_state}"
            )
    elif result.rows_read:
        # Say the zero rather than printing nothing. Silence here would be
        # indistinguishable from a guard that never ran.
        console.print(
            "No state downgrade was refused: every state in the file was at "
            "or above the state the store already held."
        )
