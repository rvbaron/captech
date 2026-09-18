"""The two human write commands: `set-state` and `set-field`.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. This
module owns exactly these two registrations on `requirements_app` and no
others (the assignment is tabulated in this package's `__init__.py`):

* ``set-state GR-... --to <state>`` -- how a human records a judgement, and
  the **only** way a requirement leaves `draft` (Step 9's `import_records` is
  the one declared exception). It wires `gr_state.set_state` and **adds
  nothing**: the transition graph, the required reviewer, the
  `draft -> approved` gate, the `pattern IS NOT NULL` precondition, the
  same-state no-op and the refresh pair all live in that function already.
  The command's own job is the flags (`--to`, `--reviewer`, `--note`,
  `--superseded-by`), turning `StateTransitionError` and
  `ApprovalBlockedError` into a non-zero exit whose message **names the
  blocking finding by identifier**, and passing the configured embedder plus
  the index store through.
* ``set-field GR-... --field <name> --value <text>`` -- the minimal,
  deliberately unpolished human write path. It wires `gr_setfield.set_field`
  and likewise adds nothing: the twelve accepted columns, the
  refusal-by-ownership-set, the schema CHECK re-evaluation, the
  no-key-recompute rule and the refresh pair are all in that module.

**Neither command may contain a `gr`-table write statement.** The writer
census (`tests/test_gr_state.py`) reads real string literals through `ast`
and asserts the set of modules containing one is exactly
`{knowledge_store.py, gr_export.py}`, and `tests/test_gr_queries.py` reuses
that scan against this package, because the original census globs
`src/legacylift_search/*.py` -- flat, so it never reached a sub-package. So a
CLI module that composed its own update statement would fail it, which is the
point: the layering is enforced rather than conventional. Go through
`gr_state.set_state` and `gr_setfield.set_field`.

Three things the CLI layer genuinely owns, because none is decidable inside
either function:

1. **Where a reviewer identity comes from.** The plan requires `set-state` to
   take it from `--reviewer` "falling back to a configured default", and
   forbids a placeholder. `Manifest` has no reviewer setting and adding one
   is outside this step's scope, so the one configured source here is the
   ``LEGACYLIFT_REVIEWER`` environment variable; with neither the flag nor
   the variable the command refuses to run.

   **Git's `user.name`/`user.email` is deliberately *not* consulted**, though
   it was the obvious third candidate. It answers "who authors commits in
   this checkout", which is a different claim from "who reviewed this
   requirement": on a shared workstation or in CI it is routinely a service
   account, and silently attributing a human's sign-off to a bot is the exact
   audit failure the reviewer requirement exists to prevent. An identity that
   might be someone else's is a placeholder wearing a real name, and the plan
   rules out placeholders rather than one particular spelling of one.
2. **A way to say NULL as distinct from the empty string.** `set_field` takes
   `value: str | None` where `None` writes SQL NULL and `''` writes `''`, and
   that distinction is load-bearing: `assumptions = ''` means "the agent
   considered assumptions and had none" while NULL means the field never
   arrived, which is why the shadow equality is `IS` and not `=` (Step 6) and
   why `gr_field_fill_counts` reports three numbers rather than a rate. A CLI
   that can only pass a string cannot write NULL, so ``--null`` exists and is
   mutually exclusive with ``--value``.
3. **Saying out loud what degraded**, and exiting zero anyway.

Two reporting rules this module must not soften:

* A degraded vector half **exits zero** and names `requirements
  reindex-vectors`. A non-zero exit reads as "the edit failed" when the edit
  is durably recorded, and an unreachable embedding provider must never be a
  reason a human's recorded judgement fails.
* `set-field`'s no-op path (`SetFieldResult.changed is False`) must say so.
  It did not bump `updated_at`, did not re-run the validator, and printing it
  as a successful write would make the JSONL export's byte-identity property
  look broken to whoever checks it next. `set-state`'s same-state no-op is
  reported the same way, and for the same reason.

Do not grow either command into a review tool. The review experience -- work
queues, `as_built`-versus-`statement` diffs, bulk triage, reviewer assignment
-- is Milestone 4's, with its own plan at
`docs/exec-plans/pending/reqs-review-ui.md`.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import typer

from legacylift_search.cli_requirements import _shared
from legacylift_search.cli_requirements import requirements_app as requirements_app

__all__ = ["REVIEWER_ENV_VAR", "set_field_cmd", "set_state_cmd"]


#: The one configured source of a reviewer identity, and the only fallback
#: `--reviewer` has. See the module docstring for why git's committer identity
#: is not a second one.
REVIEWER_ENV_VAR = "LEGACYLIFT_REVIEWER"


def _fail(message: str) -> None:
    """Print `message` to stderr and exit 1. Never `rich` -- see house rule 6."""
    typer.echo(message, err=True)
    raise typer.Exit(code=1)


def _resolve_reviewer(explicit: Optional[str]) -> str:
    """`--reviewer`, else `$LEGACYLIFT_REVIEWER`, else refuse to run.

    Whitespace-only counts as absent in both positions, so `--reviewer " "`
    cannot smuggle an empty identity past the check. `set_state` refuses a
    blank reviewer too; this refusal sits on top of that one because it can
    name the two places a value could have come from, which a library
    function cannot.
    """
    for candidate in (explicit, os.environ.get(REVIEWER_ENV_VAR)):
        if candidate and candidate.strip():
            return candidate.strip()
    _fail(
        "set-state requires a reviewer identity and refuses to run without "
        "one. Pass --reviewer NAME, or set the "
        f"{REVIEWER_ENV_VAR} environment variable. There is deliberately no "
        "placeholder default and git's committer identity is not consulted: "
        "an approved corpus that cannot say who approved each record fails "
        "the exact audit claim the lifecycle exists to support, and identity "
        "is the one thing in this schema that cannot be reconstructed after "
        "the fact."
    )
    raise AssertionError("unreachable")  # pragma: no cover - _fail exits


def _abbrev(value: Any, width: int = 100) -> str:
    """A one-line rendering of a stored value, for a human-readable report.

    NULL is spelled `NULL` and the empty string is spelled `''`, because the
    whole reason `--null` exists is that those two are different values; a
    report rendering both as nothing would undo the distinction it just let
    the caller express.
    """
    if value is None:
        return "NULL"
    text = str(value)
    if text == "":
        return "''"
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3] + "..."


def _findings_payload(findings: list[Any]) -> list[dict[str, Any]]:
    """`Finding` rows as JSON, keeping `evaluated` beside `severity`.

    `evaluated` is not a third severity value (SPEC-1 S1.6 has exactly two),
    so it travels as its own key: a not-evaluated `ERROR` is a check that
    could not be decided, never one that failed, and flattening the two into
    one field is this plan's recurring absent-versus-real defect.
    """
    return [
        {
            "finding_id": f.finding_id,
            "severity": f.severity,
            "evaluated": f.evaluated,
            "span": f.span,
            "message": f.message,
        }
        for f in findings
    ]


def _echo_findings(findings: list[Any]) -> None:
    """Report findings to stderr, saying which block approval and which could
    not be decided."""
    if not findings:
        typer.echo("findings: none.", err=True)
        return
    blocking = [f for f in findings if f.severity == "ERROR" and f.evaluated]
    not_evaluated = [f for f in findings if not f.evaluated]
    typer.echo(
        f"findings: {len(findings)} ({len(blocking)} blocking approval, "
        f"{len(not_evaluated)} not evaluated).",
        err=True,
    )
    for f in findings:
        if f in blocking:
            marker = " [BLOCKING]"
        elif not f.evaluated:
            marker = " [not evaluated]"
        else:
            marker = ""
        typer.echo(f"  {f.finding_id} {f.severity}{marker}: {f.message}", err=True)


# ----------------------------------------------------------------------
# set-state
# ----------------------------------------------------------------------


@requirements_app.command("set-state")
def set_state_cmd(
    gr_id: str = typer.Argument(..., help="The requirement to move, e.g. GR-01H..."),
    to: str = typer.Option(
        ...,
        "--to",
        help=(
            "The lifecycle state to move to. The legal moves are "
            "gr_state.ALLOWED_TRANSITIONS; an illegal or unknown move is "
            "refused with a message naming both states and the moves that "
            "are allowed from the current one."
        ),
    ),
    reviewer: Optional[str] = typer.Option(
        None,
        "--reviewer",
        help=(
            "Who is recording this judgement; lands in gr.reviewed_by. "
            f"Required -- falls back to ${REVIEWER_ENV_VAR} and to nothing "
            "else. There is no placeholder default."
        ),
    ),
    note: Optional[str] = typer.Option(
        None,
        "--note",
        help="Free text recording why; lands in gr.review_note.",
    ),
    superseded_by: Optional[str] = typer.Option(
        None,
        "--superseded-by",
        help=(
            "Required with `--to superseded`: the gr_id of the successor. It "
            "is recorded in gr.superseded_by on THIS record, never in "
            "derived_from (which means 'the rules this rollup summarizes' "
            "and nothing else)."
        ),
    ),
    repo_root: _shared.RepoRootOption = None,
    config: _shared.ConfigOption = None,
    analysis_dir: _shared.AnalysisDirOption = None,
    embedding_provider: _shared.EmbeddingProviderOption = None,
    json_out: _shared.JsonOption = False,
) -> None:
    """Record a human judgement about one requirement.

    The only way a requirement leaves `draft`, and **nothing automated may
    call it**: `ingest` writes `draft` and never anything else, so an
    extractor can never approve its own output.

    Refuses `--to approved` while any evaluated ERROR-severity finding stands,
    naming the blocking findings by identifier, and refuses it on a NULL
    `pattern` (set one with `requirements set-field` first). A move to the
    state the record already holds is a no-op: it stamps nothing, bumps
    nothing, and re-embeds nothing.

    Exits **zero** when only the semantic half degraded -- the judgement is
    durably recorded either way, and `requirements reindex-vectors` is the
    single documented recovery.
    """
    from legacylift_search.gr_state import (
        ApprovalBlockedError,
        StateTransitionError,
        set_state,
    )

    identity = _resolve_reviewer(reviewer)

    try:
        paths = _shared.resolve_requirements_paths(repo_root, config, analysis_dir)
    except Exception as exc:
        _fail(str(exc))
        return
    store = _shared.open_knowledge_store(paths)
    index_store = _shared.open_index_store(paths)
    embedder, embed_reason = _shared.build_embedder(paths.manifest, embedding_provider)

    try:
        before = store.get_gr(gr_id)
        if before is None:
            _fail(f"no requirement {gr_id!r} in {paths.knowledge_sqlite_path}.")
            return
        # The before-state is read for the *report* only -- the arrow in
        # "draft -> approved", and telling a same-state call apart from a real
        # move so the no-op can say it wrote nothing. The rules (which moves
        # are legal, what a no-op must not stamp) stay in `set_state`; a
        # second copy here is the sixth review round's stale-copy defect.
        from_state = before.state
        try:
            set_state(
                store,
                gr_id,
                to,
                identity,
                note,
                superseded_by=superseded_by,
                embedder=embedder,
                index_store=index_store,
                repo_root=paths.repo_root,
            )
        except ApprovalBlockedError as exc:
            if json_out:
                _shared.emit_json(
                    {
                        "gr_id": gr_id,
                        "from_state": from_state,
                        "to_state": to,
                        "changed": False,
                        "refused": "approval_blocked",
                        "blocking_findings": _findings_payload(exc.findings),
                        "message": str(exc),
                    }
                )
            _fail(str(exc))
            return
        except StateTransitionError as exc:
            if json_out:
                _shared.emit_json(
                    {
                        "gr_id": gr_id,
                        "from_state": from_state,
                        "to_state": to,
                        "changed": False,
                        "refused": "transition_refused",
                        "message": str(exc),
                    }
                )
            _fail(str(exc))
            return

        after = store.get_gr(gr_id)
        changed = from_state != to
        payload = {
            "gr_id": gr_id,
            "from_state": from_state,
            "to_state": after.state,
            "changed": changed,
            "reviewed_by": after.reviewed_by,
            "reviewed_at": after.reviewed_at,
            "review_note": after.review_note,
            "superseded_by": after.superseded_by,
            "derived_from": after.derived_from,
            "vectors_degraded": bool(embed_reason) and changed,
            "vectors_degraded_reason": embed_reason if changed else None,
        }
        if json_out:
            _shared.emit_json(payload)
        elif not changed:
            typer.echo(
                f"{gr_id}: already {after.state!r} -- no-op. Nothing was "
                "written: no reviewer stamp, no review note, no updated_at "
                "bump, and nothing re-embedded.",
                err=True,
            )
        else:
            typer.echo(f"{gr_id}: {from_state} -> {after.state}", err=True)
            typer.echo(f"  reviewed_by:  {_abbrev(after.reviewed_by)}", err=True)
            typer.echo(f"  reviewed_at:  {_abbrev(after.reviewed_at)}", err=True)
            typer.echo(f"  review_note:  {_abbrev(after.review_note)}", err=True)
            if after.state == "superseded":
                typer.echo(
                    f"  superseded_by: {_abbrev(after.superseded_by)} "
                    "(derived_from untouched)",
                    err=True,
                )
        # Degradation is reported and the exit stays zero. `set_state` returns
        # None and drops its own `EmbedResult`, so the signal the CLI actually
        # holds is whether an embedder could be built at all; that is what
        # `vectors_degraded` reports, and it is honest about being that.
        if changed and embed_reason:
            typer.echo(f"vectors: {embed_reason}", err=True)
    finally:
        if index_store is not None:
            index_store.close()
        store.close()


# ----------------------------------------------------------------------
# set-field
# ----------------------------------------------------------------------


@requirements_app.command("set-field")
def set_field_cmd(
    gr_id: str = typer.Argument(..., help="The requirement to edit, e.g. GR-01H..."),
    field: str = typer.Option(
        ...,
        "--field",
        help=(
            "The column to write. set-field accepts exactly the nine "
            "human-writable columns plus the three shadowed ones -- twelve "
            "in all -- and refuses everything else by which ownership set it "
            "belongs to. Pass an unrecognized name and the refusal prints "
            "the accepted list."
        ),
    ),
    value: Optional[str] = typer.Option(
        None,
        "--value",
        help=(
            'The new value, as text. `--value ""` writes the EMPTY STRING, '
            "which is a real value (considered, and none); to write SQL NULL "
            "(the field never arrived) pass --null instead. Exactly one of "
            "--value and --null is required."
        ),
    ),
    null: bool = typer.Option(
        False,
        "--null",
        help=(
            'Write SQL NULL, clearing the column. Distinct from `--value ""`, '
            "which writes the empty string: NULL means the field never "
            "arrived, '' means it arrived empty, and the fill-rate figures in "
            "`requirements stats` count them differently. Refused on a NOT "
            "NULL column."
        ),
    ),
    repo_root: _shared.RepoRootOption = None,
    config: _shared.ConfigOption = None,
    analysis_dir: _shared.AnalysisDirOption = None,
    embedding_provider: _shared.EmbeddingProviderOption = None,
    json_out: _shared.JsonOption = False,
) -> None:
    """Write one human-owned column on one requirement. Minimal by design.

    It re-runs the validator after a real write and reports the findings,
    because editing a `statement` -- or setting the `pattern` that decides
    whether the three V-SLOT checks are evaluable -- changes them. Writing
    `rule_class` or `pattern` recomputes **neither** dedupe key: keys move
    only on extractor-owned writes.

    It does **not** write `gr.state`; that is `requirements set-state`'s, and
    the approval gate lives there. Writing the value the row already holds is
    a no-op that bumps nothing and re-runs nothing.

    Exits **zero** when only the semantic half degraded.
    """
    from legacylift_search.gr_setfield import SetFieldError, set_field

    if null and value is not None:
        _fail(
            "--value and --null are mutually exclusive: --null writes SQL "
            'NULL and `--value ""` writes the empty string, and they are '
            "different values in this schema. Pass one."
        )
        return
    if not null and value is None:
        _fail(
            'one of --value or --null is required. `--value ""` writes the '
            "empty string (considered, and none); --null writes SQL NULL "
            "(the field never arrived)."
        )
        return

    try:
        paths = _shared.resolve_requirements_paths(repo_root, config, analysis_dir)
    except Exception as exc:
        _fail(str(exc))
        return
    store = _shared.open_knowledge_store(paths)
    index_store = _shared.open_index_store(paths)
    embedder, embed_reason = _shared.build_embedder(paths.manifest, embedding_provider)

    try:
        try:
            result = set_field(
                store,
                gr_id,
                field,
                None if null else value,
                embedder=embedder,
                index_store=index_store,
                repo_root=paths.repo_root,
            )
        except SetFieldError as exc:
            if json_out:
                _shared.emit_json(
                    {
                        "gr_id": gr_id,
                        "field": field,
                        "changed": False,
                        "refused": True,
                        "message": str(exc),
                    }
                )
            _fail(str(exc))
            return

        # `build_embedder`'s reason is preferred when it exists because it
        # names *why* no embedder could be built (an unknown provider, absent
        # credentials); `EmbedResult.reason` is the generic one in that case.
        # When an embedder did build, only the embed half can have failed, so
        # its reason is the only one there is.
        vector_reason = (embed_reason if result.changed else None) or (
            result.embed.reason
        )
        payload = {
            "gr_id": result.gr_id,
            "field": result.field,
            "changed": result.changed,
            "old_value": result.old_value,
            "new_value": result.new_value,
            "validated": result.validated,
            "findings": _findings_payload(result.findings),
            "blocking_findings": _findings_payload(result.blocking_findings),
            "leaked_terms_available": result.refresh.leaked_terms_available,
            "vectors_degraded": bool(vector_reason),
            "vectors_degraded_reason": vector_reason,
        }
        if json_out:
            _shared.emit_json(payload)
        else:
            if not result.changed:
                typer.echo(
                    f"{gr_id}: {result.field} already holds "
                    f"{_abbrev(result.old_value)} -- no-op. Nothing was "
                    "written, updated_at was not bumped, and the validator "
                    "did not re-run, so the findings below are the ones the "
                    "record already carried.",
                    err=True,
                )
            else:
                typer.echo(f"{gr_id}: {result.field} written.", err=True)
                typer.echo(f"  was: {_abbrev(result.old_value)}", err=True)
                typer.echo(f"  now: {_abbrev(result.new_value)}", err=True)
                typer.echo(
                    "  validator re-ran: "
                    + (
                        "V-STY-03 used the indexed symbol names "
                        f"({result.refresh.leaked_term_count} term(s)) "
                        "plus its morphological half."
                        if result.refresh.leaked_terms_available
                        else "no index was reachable, so V-STY-03 ran on its "
                        "morphological half alone -- no leakage found and "
                        "leakage was never looked for are different facts."
                    ),
                    err=True,
                )
            _echo_findings(result.findings)
            if result.blocking_findings:
                named = ", ".join(f.finding_id for f in result.blocking_findings)
                typer.echo(
                    f"approval is blocked by {named}. Reviewing them is "
                    "Milestone 4's job, not this command's.",
                    err=True,
                )
        if vector_reason:
            typer.echo(f"vectors: {vector_reason}", err=True)
    finally:
        if index_store is not None:
            index_store.close()
        store.close()
