"""`rederive-subjects`: recompute `subject` after a domain retag.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md` (the
`rederive-subjects` paragraphs). A callable function with no CLI dependency,
like `gr_state.set_state` and `gr_setfield.set_field`, so the command wires it
and the behaviour is testable without a command.

**It exists because nothing else re-derives a subject after the domain set
changes, and the staleness is silent.** `subject` and `subject_provenance` are
computed from `file_domains` at ingest, so re-running `tag-domains` with a
changed `domains.json` leaves every subject describing the *previous* domain
set with nothing anywhere reporting it -- which silently corrupts the
`derived` rate in `requirements stats`, the one check the plan's Concrete
Steps put in front of an implementer.

**One implementation, two callers.** `gr_subject.derive_subject` is that
implementation; ingest is the other caller. This module re-reads the domains
and calls it. It does not reimplement the majority rule, the two-sentinel
rule or the statement fallback, and it must never grow a second copy of any
of them.

**It touches exactly two columns, plus `updated_at`.** It does not touch
`statement` -- an earlier version of this plan had it re-template the
statement, which was correct while ingest built statements from a §S1.4
template, but Step 6a no longer does that: `statement` is authored by the
extractor, so there is no template to re-fill and no mechanical way to
substitute a new subject into someone else's sentence. The staleness that
leaves is smaller and honest: a requirement's *text* may name a subject the
domain set no longer derives, while the refreshed `subject` column says what
the derivation now yields, and the divergence between them is visible in
`show`. It touches **no key** either, which is the same invariant as the
domain-retag test one layer up -- no dedupe key takes a domain as input, so a
retag plus a rederive must leave both keys byte-identical.

**The fourth resumable repair command**, after `backfill-vectors`,
`backfill-hashes` and `reindex-vectors`. They share a shape worth naming:
each recomputes a derived value from a durable source, processes only what is
stale, reports what it changed and what it skipped, and is safe to run twice.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Sequence

from .gr_refresh import refresh_gr_derived_sql, refresh_gr_vectors
from .gr_subject import DOMAIN_UNASSIGNED, derive_subject
from .identity import normalize_path
from .knowledge_store import KnowledgeStore
from .models import EmbedResult, RefreshResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pathlib import Path

    from .embeddings import Embedder
    from .store import SQLiteStore

__all__ = ["RederiveResult", "SubjectChange", "rederive_subjects"]


@dataclass(frozen=True)
class SubjectChange:
    """One requirement whose derivation moved, before and after."""

    gr_id: str
    old_subject: str | None
    new_subject: str | None
    old_provenance: str | None
    new_provenance: str


@dataclass
class RederiveResult:
    """What `rederive_subjects` did.

    ``examined`` counts every row the derivation ran over; ``changed`` counts
    the rows actually written; ``skipped`` counts the rows whose derivation
    came out identical and which were therefore **not** written -- that is
    the "processes only what is stale" half of the repair-command shape, and
    reporting it is what makes a second run's output ("0 changed, 471
    skipped") a positive confirmation rather than an ambiguous silence.

    Two directions are reported as their own figures rather than being left
    inside ``provenance_transitions``, because they answer different
    questions and the plan asks for both by name:

    * ``llm_named_to_derived`` is the case the finding behind this command
      exposed -- a file that was `unassigned` at ingest and has since been
      tagged should stop being model-named, and without this command it never
      does.
    * ``derived_to_derived_ambiguous`` is the reverse, which is what a
      newly-**excluded** file produces. It means the corpus now holds rules
      mined from code the analyst has since declared out of scope. Since the
      Concrete Steps tell you to check the `derived` rate before believing
      the derivation works at all, a rate that can only fall as a corpus ages
      would quietly undermine that check -- so the fall has to be attributed
      rather than merely observed.

    ``provenance_transitions`` carries every `(old, new)` pair with a count,
    so a direction nobody anticipated is visible too. A `None` old provenance
    is a row that predates the derivation and is kept as `None` rather than
    folded into any of the three real values.

    ``subject_only_changes`` counts rows whose provenance stayed put while
    the subject text moved -- a retag that renamed a domain rather than
    reassigning a file. Without it those rows appear in ``changed`` and in no
    transition bucket, which reads like a bookkeeping error.
    """

    examined: int = 0
    changed: int = 0
    skipped: int = 0
    llm_named_to_derived: int = 0
    derived_to_derived_ambiguous: int = 0
    subject_only_changes: int = 0
    provenance_transitions: dict[tuple[str | None, str], int] = dataclass_field(
        default_factory=dict
    )
    changes: list[SubjectChange] = dataclass_field(default_factory=list)
    refresh: RefreshResult = dataclass_field(default_factory=RefreshResult)
    embed: EmbedResult = dataclass_field(default_factory=EmbedResult)


def rederive_subjects(
    store: KnowledgeStore,
    gr_ids: Sequence[str] | None = None,
    *,
    embedder: Embedder | None = None,
    index_store: SQLiteStore | None = None,
    repo_root: Path | None = None,
) -> RederiveResult:
    """Recompute `subject`/`subject_provenance` from *current* `file_domains`.

    Args:
        store: The knowledge store holding the `gr` tables and, in the same
            database, `file_domains`.
        gr_ids: Restrict to these requirements, or `None` for every row --
            the ordinary case, since a retag changes the domain set globally
            and the command's job is to find out which rows that moved. A
            `gr_id` with no row is skipped silently, matching
            `KnowledgeStore.list_gr`.
        embedder: Passed to `refresh_gr_vectors`. **`None` is a supported
            degraded success**: the rederived subjects are in SQLite, and the
            `gr_statements` metadata stays behind until
            `requirements reindex-vectors` runs. `subject` *is* vector
            metadata, so a degraded run leaves state-and-subject-filtered
            semantic search reading the old values -- which is why the result
            carries `EmbedResult.reason` for the caller to print, while still
            exiting zero.
        index_store: Passed to `refresh_gr_derived_sql` for `V-STY-03`'s
            `leaked_terms`. `None` means no index.
        repo_root: Threaded for the same reason `refresh_gr_derived_sql`
            declares it.

    Returns:
        A `RederiveResult`.

    **Safe to run twice.** The second run finds every derivation already
    current, writes nothing, and reports every row under ``skipped``.
    """
    result = RederiveResult()
    ids = list(gr_ids) if gr_ids is not None else store.all_gr_ids()
    if not ids:
        return result

    # The `file_domains` lookup is cached per normalized path because a
    # corpus's requirements cite the same handful of files repeatedly --
    # the same reasoning as `gr_refresh`'s leaked-terms cache.
    domain_cache: dict[str, str] = {}

    def domain_of(relative_path: str) -> str:
        key = normalize_path(relative_path)
        if key not in domain_cache:
            domain_cache[key] = store.domain_for_file(key) or DOMAIN_UNASSIGNED
        return domain_cache[key]

    now = datetime.now(timezone.utc).isoformat()
    transitions: Counter[tuple[str | None, str]] = Counter()
    touched: list[str] = []

    for record in store.list_gr(ids):
        result.examined += 1
        # **One entry per citation, not per distinct file.** Step 3's
        # majority is a majority over citations, so a file cited three times
        # contributes three entries -- exactly what ingest does. This is why
        # `list_gr_citations` is used and NOT `citation_paths_for_gr`, which
        # is DISTINCT-path and exists for `leaked_terms`; substituting it
        # here would silently change the derivation's arithmetic on any
        # requirement citing one file more than once.
        citation_domains = [
            domain_of(c.relative_path) for c in store.list_gr_citations(record.gr_id)
        ]
        derivation = derive_subject(
            citation_domains,
            record.statement,
            record.rule_class,
            record.pattern,
        )
        if (
            derivation.subject == record.subject
            and derivation.subject_provenance == record.subject_provenance
        ):
            result.skipped += 1
            continue

        # Exactly three columns. No key, and not `statement` -- a test
        # asserts both dedupe keys, every citation anchor and every
        # `statement` are byte-identical across this call.
        store.update_gr_row(
            record.gr_id,
            {
                "subject": derivation.subject,
                "subject_provenance": derivation.subject_provenance,
                "updated_at": now,
            },
        )
        result.changed += 1
        touched.append(record.gr_id)
        result.changes.append(
            SubjectChange(
                gr_id=record.gr_id,
                old_subject=record.subject,
                new_subject=derivation.subject,
                old_provenance=record.subject_provenance,
                new_provenance=derivation.subject_provenance,
            )
        )
        if record.subject_provenance == derivation.subject_provenance:
            result.subject_only_changes += 1
        else:
            pair = (record.subject_provenance, derivation.subject_provenance)
            transitions[pair] += 1
            if pair == ("llm_named", "derived"):
                result.llm_named_to_derived += 1
            elif pair == ("derived", "derived_ambiguous"):
                result.derived_to_derived_ambiguous += 1

    result.provenance_transitions = dict(transitions)

    if not touched:
        # Nothing was written, so there is nothing to commit and no derived
        # artifact to refresh. Returning here is not an optimization: calling
        # the pair anyway would rewrite every `gr_fts` row and every
        # `gr_finding` row for rows this command did not change, bumping
        # nothing in `gr` but doing a corpus-sized write on a no-op run.
        return result

    result.refresh = refresh_gr_derived_sql(store, touched, index_store, repo_root)
    store.commit()
    result.embed = refresh_gr_vectors(store, touched, embedder=embedder)
    return result
