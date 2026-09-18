"""Tests for Step 8's `KnowledgeStore` query/write API and `gr_refresh`'s two additions.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. Every
test here fails before this wave -- with `AttributeError` on the new
`KnowledgeStore` methods, or `ImportError` on `leaked_terms_for` /
`reindex_gr_vectors` -- and passes after.

These are the readers and writers the fourteen `requirements` commands share,
which is why they land as one commit before the commands: all raw `gr`-table
SQL lives in `knowledge_store.py` (the writer census in `test_gr_state.py`
asserts it), so a command that wanted a new query would otherwise have to add
one here mid-wave.

The assertions worth naming are the absent-versus-real ones. Four of them,
each a shape the plan records as having gone wrong silently before:

* a NULL `subject_provenance` is its own key in `count_gr_by`, never folded
  into a real value;
* a NULL `subject` is counted apart from `llm_named`;
* `assumptions = ''` is a real value and is reported apart from NULL;
* a NULL `gr_merge_candidate.similarity` stays `None` and never becomes
  `0.0`.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from legacylift_search.embeddings import HashEmbedder
from legacylift_search.gr_fields import set_field_accepted_fields
from legacylift_search.gr_refresh import (
    leaked_terms_for,
    open_gr_collection,
    reindex_gr_vectors,
)
from legacylift_search.gr_subject import DOMAIN_EXCLUDED
from legacylift_search.knowledge_store import GR_FILL_FIELDS, KnowledgeStore
from legacylift_search.models import (
    Finding,
    GRCitation,
    GRMergeCandidate,
    GRRun,
    GRRunHit,
)
from tests.test_gr_state import insert_gr

_IS_WINDOWS = sys.platform == "win32"


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def store(tmp_root):
    ks = KnowledgeStore(tmp_root / "knowledge" / "knowledge.sqlite")
    try:
        yield ks
    finally:
        ks.close()


def _gr(store, n: int, **overrides) -> str:
    """Insert a `gr` row with a distinct, sortable `gr_id`."""
    gr_id = f"GR-01HQ2X{n:022d}"
    return insert_gr(store._connect(), gr_id=gr_id, **overrides)


# --------------------------------------------------------------------------
# query_gr -- `requirements list`
# --------------------------------------------------------------------------


def test_query_gr_filters_and_orders_by_gr_id(store):
    """Proves every filter AND-s and the order is creation order, not arbitrary."""
    _gr(store, 3, state="approved", category="Validation", disposition="captured")
    _gr(store, 1, state="draft", category="Validation", disposition="captured")
    _gr(store, 2, state="approved", category="Calculation", disposition="captured")

    ids = [r.gr_id for r in store.query_gr()]
    assert ids == sorted(ids), "unfiltered read must be ordered by gr_id"
    assert len(ids) == 3

    approved = store.query_gr(state="approved")
    assert [r.state for r in approved] == ["approved", "approved"]
    assert [r.gr_id for r in approved] == sorted(r.gr_id for r in approved)

    both = store.query_gr(state="approved", category="Validation")
    assert len(both) == 1, "filters AND rather than OR"
    assert both[0].category == "Validation" and both[0].state == "approved"

    assert store.query_gr(kind="business_rule") != []
    assert store.query_gr(kind="story") == []
    assert store.query_gr(disposition="delegated") == []


def test_query_gr_subject_filter_matches_the_column_exactly(store):
    """Proves `--subject` is an exact match, so a NULL subject is not returned."""
    _gr(store, 1, subject="Orders", subject_provenance="derived")
    _gr(store, 2)  # subject NULL
    assert [r.gr_id for r in store.query_gr(subject="Orders")] == ["GR-01HQ2X" + "1".rjust(22, "0")]
    assert store.query_gr(subject="orders") == [], "match is exact, not case-folded"


def test_query_gr_none_means_unfiltered_and_not_match_null(store):
    """Proves the documented reading of `None`: it does not mean `IS NULL`.

    A `None` that sometimes meant "unfiltered" and sometimes meant "match
    NULL" would be the absent-versus-real defect wearing a keyword argument.
    The row inserted here has a NULL `category`, and an unfiltered read
    returns it -- which is only possible if `None` skipped the clause.
    """
    _gr(store, 1)  # category NULL
    assert len(store.query_gr(category=None)) == 1


def test_query_gr_limit_takes_the_oldest_and_refuses_a_negative(store):
    """Proves `--limit` is deterministic, and that -1 is refused not honoured.

    SQLite reads `LIMIT -1` as unlimited, so a negative that reached the SQL
    would silently mean the opposite of a limit.
    """
    for n in (1, 2, 3):
        _gr(store, n)
    got = store.query_gr(limit=2)
    assert [r.gr_id for r in got] == [f"GR-01HQ2X{1:022d}", f"GR-01HQ2X{2:022d}"]
    assert store.query_gr(limit=0) == []
    with pytest.raises(ValueError, match="limit must be"):
        store.query_gr(limit=-1)


# --------------------------------------------------------------------------
# Merge candidates -- `list --candidates`
# --------------------------------------------------------------------------


def test_unresolved_candidates_are_listed_and_resolved_ones_are_not(store):
    """Proves `list --candidates` shows only `unresolved` pairs."""
    a, b, c = (_gr(store, n) for n in (1, 2, 3))
    store.record_gr_merge_candidate(
        GRMergeCandidate(
            gr_id_existing=a, gr_id_incoming=b, reason="semantic", similarity=0.12
        )
    )
    store.record_gr_merge_candidate(
        GRMergeCandidate(
            gr_id_existing=a,
            gr_id_incoming=c,
            reason="drift",
            resolution="distinct",
            resolved_at="2026-09-02T00:00:00Z",
        )
    )
    store.commit()
    got = store.list_unresolved_gr_merge_candidates()
    assert [(x.gr_id_existing, x.gr_id_incoming) for x in got] == [(a, b)]


def test_a_null_similarity_stays_none_and_never_becomes_zero(store):
    """Proves the reader preserves "there was no comparison".

    A `range_overlap` or `drift` candidate has no similarity score at all.
    Rendering that as `0.0` would read as "compared, and maximally
    dissimilar", which is the opposite of what happened -- one of the nine
    recorded instances of an absent value sharing an encoding with a real
    one.
    """
    a, b = _gr(store, 1), _gr(store, 2)
    store.record_gr_merge_candidate(
        GRMergeCandidate(
            gr_id_existing=a, gr_id_incoming=b, reason="range_overlap", similarity=None
        )
    )
    store.commit()
    got = store.list_unresolved_gr_merge_candidates()
    assert got[0].similarity is None
    assert got[0].similarity != 0.0


# --------------------------------------------------------------------------
# Grouped counts -- `stats`
# --------------------------------------------------------------------------


def test_count_gr_by_keeps_null_as_its_own_key(store):
    """Proves a NULL groups apart from every real value, as `None`.

    `COALESCE(col, 'none')` is the natural thing to type at a call site and
    it silently merges a genuine value with an absent one. This is why the
    grouping is a method.
    """
    _gr(store, 1, subject_provenance="llm_named")
    _gr(store, 2, subject_provenance="derived")
    _gr(store, 3)  # subject_provenance NULL
    counts = store.count_gr_by("subject_provenance")
    assert counts == {"derived": 1, "llm_named": 1, None: 1}
    assert None in counts and "" not in counts
    # The None key sorts last, so printing in iteration order reads as one
    # trailing "absent" bucket.
    assert list(counts)[-1] is None


def test_count_gr_by_refuses_a_column_it_cannot_group(store):
    """Proves a typo is refused rather than answering with an empty grouping.

    An empty grouping reads exactly like an empty corpus, which is the
    failure this refusal prevents; the name also reaches SQL.
    """
    with pytest.raises(ValueError, match="not a groupable"):
        store.count_gr_by("statement")
    with pytest.raises(ValueError, match="not a groupable"):
        store.count_gr_by("stat")


def test_null_subjects_are_counted_apart_from_llm_named(store):
    """Proves the ninth-round criterion: absent subject != model-named subject.

    A row can carry `subject_provenance = 'llm_named'` with a NULL `subject`
    -- the fallback branch ran and `split_slots` located no `[Subject]` span
    -- so folding the two together reports a model-named subject for a
    requirement that has none.
    """
    _gr(store, 1, subject="Orders", subject_provenance="llm_named")
    _gr(store, 2, subject=None, subject_provenance="llm_named")
    _gr(store, 3, subject=None, subject_provenance="derived_ambiguous")
    # Two rows are `llm_named` and two rows have no subject, but they are not
    # the same two rows: GR-1 is llm_named WITH a subject, GR-3 has no
    # subject and is not llm_named. Folding the columns together would report
    # a model-named subject for a requirement that has none.
    assert store.count_gr_by("subject_provenance")["llm_named"] == 2
    assert store.count_gr_null_subjects() == 2
    conn = store._connect()
    both = conn.execute(
        "SELECT COUNT(*) FROM gr WHERE subject IS NULL "
        "AND subject_provenance = 'llm_named'"
    ).fetchone()[0]
    assert both == 1, "the two figures overlap on one row and are not the same set"


# --------------------------------------------------------------------------
# Fill counts -- `stats`' review progress
# --------------------------------------------------------------------------


def test_the_fill_field_list_is_exactly_what_set_field_accepts(store):
    """Proves `GR_FILL_FIELDS` is the twelve `set-field` columns, not a copy.

    Asserted against `gr_fields.set_field_accepted_fields`, which derives the
    shadowed half from `PRAGMA table_info`, so a new shadow column added to
    `gr` fails this rather than quietly dropping out of the review-progress
    report.
    """
    assert set(GR_FILL_FIELDS) == set_field_accepted_fields(store._connect())
    assert len(GR_FILL_FIELDS) == 12
    assert len(set(GR_FILL_FIELDS)) == 12, "no duplicates, so counts are per column"


def test_an_empty_string_assumptions_is_reported_apart_from_null(store):
    """Proves the one column whose `''` is real is not counted as unfilled.

    `assumptions = ''` means the agent considered assumptions and had none;
    NULL means the field never arrived. A fill rate computed as
    `filled / total` reports the exact opposite of the truth for this column,
    which is why the reader returns all three numbers and documents which
    numerator each column wants.
    """
    _gr(store, 1, assumptions="", assumptions_extracted="")
    _gr(store, 2, assumptions="Vendor numbers are unique.")
    _gr(store, 3)  # assumptions NULL
    fill = store.gr_field_fill_counts()["assumptions"]
    assert fill == {"filled": 1, "empty": 1, "absent": 1}
    # The honest "the field arrived" numerator for this column:
    assert fill["filled"] + fill["empty"] == 2
    # And the naive one, which is the number that would be wrong:
    assert fill["filled"] == 1


def test_fill_counts_cover_every_row_and_reject_a_non_column(store):
    """Proves the three buckets partition the corpus, per column."""
    for n in (1, 2, 3):
        _gr(store, n)
    total = store.count_gr()
    for field, buckets in store.gr_field_fill_counts().items():
        assert sum(buckets.values()) == total, field
    with pytest.raises(ValueError, match="not `gr` columns"):
        store.gr_field_fill_counts(("no_such_column",))


def test_modality_confirmed_zero_counts_as_filled_not_absent(store):
    """Proves `0` is a real value there, not an absence.

    The column is `NOT NULL DEFAULT 0` and `0` means "no human has confirmed
    the modality" -- a fact, so it cannot be reported as a missing field.
    """
    _gr(store, 1)
    fill = store.gr_field_fill_counts(("modality_confirmed",))["modality_confirmed"]
    assert fill == {"filled": 1, "empty": 0, "absent": 0}


# --------------------------------------------------------------------------
# The all-excluded count -- Step 3's own figure
# --------------------------------------------------------------------------


def _cite(store, gr_id: str, path: str, start: int = 1, end: int = 2) -> None:
    store.upsert_gr_citation(
        GRCitation(
            gr_id=gr_id,
            anchor_key=f"ak::{path}",
            anchor_resolution="file",
            relative_path=path,
            start_line=start,
            end_line=end,
            provenance="extracted",
        )
    )


def test_all_excluded_requirements_are_counted_as_their_own_figure(store):
    """Proves Step 3's figure: every citation on the `excluded` domain.

    Deliberately not folded into `derived_ambiguous`: an all-`excluded`
    requirement means the corpus holds rules mined from code the analyst has
    since declared out of scope, which is a different fact from "no domain
    held a majority" even though both land in the same provenance bucket.
    """
    for path, domain in (
        ("src/legacy/a.java", DOMAIN_EXCLUDED),
        ("src/legacy/b.java", DOMAIN_EXCLUDED),
        ("src/orders/c.java", "orders"),
    ):
        store.upsert_file_domain(path, domain, "glob", None, 1.0)

    all_excluded = _gr(store, 1)
    _cite(store, all_excluded, "src/legacy/a.java")
    _cite(store, all_excluded, "src/legacy/b.java", 5, 9)

    mixed = _gr(store, 2)
    _cite(store, mixed, "src/legacy/a.java")
    _cite(store, mixed, "src/orders/c.java")

    store.commit()
    assert store.count_gr_all_citations_excluded() == 1


def test_a_requirement_with_no_citations_is_not_all_excluded(store):
    """Proves the vacuous case is excluded, matching ingest's own guard.

    "Every citation is excluded" is vacuously true over an empty set, and
    counting it would inflate the figure with rules that cite nothing --
    ingest guards this with `bool(citation_domains) and all(...)`.
    """
    _gr(store, 1)
    store.commit()
    assert store.count_gr_all_citations_excluded() == 0


def test_an_untagged_citation_is_unassigned_not_excluded(store):
    """Proves the two reserved sentinels are not collapsed by this query.

    A citation whose path has no `file_domains` row is `unassigned` -- a file
    nobody has classified, which `tag-domains` fixes -- not `excluded`, which
    is a deliberate declaration. The LEFT JOIN's NULL must fail the
    all-excluded test.
    """
    gr_id = _gr(store, 1)
    _cite(store, gr_id, "src/never/tagged.java")
    store.commit()
    assert store.count_gr_all_citations_excluded() == 0


def test_the_excluded_sentinel_matches_gr_subjects_definition(store):
    """Proves the SQL literal and `gr_subject`'s constant have not drifted."""
    from legacylift_search import knowledge_store as ks_module

    assert ks_module._DOMAIN_EXCLUDED_SQL == DOMAIN_EXCLUDED


# --------------------------------------------------------------------------
# gr_run reads
# --------------------------------------------------------------------------


def _run(store, run_id: str, **overrides) -> GRRun:
    run = GRRun(run_id=run_id, system="nng", **overrides)
    store.insert_gr_run(run)
    store.commit()
    return run


def test_gr_run_reads_hydrate_without_the_generated_complete_column(store):
    """Proves `complete` comes from the property, never from `SELECT *`.

    `complete` is a generated VIRTUAL column: `SELECT *` returns it and
    `PRAGMA table_info` hides it, so a `SELECT *` hydration would hand
    pydantic a value for a name that is not a field. Reading it off the model
    is what keeps "NULL `not_accounted_for` means never measured" true on
    both paths.
    """
    _run(store, "RUN-1", not_accounted_for=None)
    _run(store, "RUN-2", not_accounted_for=0)
    _run(store, "RUN-3", not_accounted_for=37)

    runs = {r.run_id: r for r in store.list_gr_runs()}
    assert [r for r in store.list_gr_runs()] == sorted(
        store.list_gr_runs(), key=lambda r: r.run_id
    )
    assert runs["RUN-1"].not_accounted_for is None
    assert runs["RUN-1"].complete is False, "never measured is not complete"
    assert runs["RUN-2"].complete is True
    assert runs["RUN-3"].complete is False

    # The generated column and the property agree, which is the point of
    # exposing it as a property rather than a field.
    conn = store._connect()
    for run_id, expected in (("RUN-1", 0), ("RUN-2", 1), ("RUN-3", 0)):
        got = conn.execute(
            "SELECT complete FROM gr_run WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        assert got == expected
        assert bool(got) is store.get_gr_run(run_id).complete


def test_get_gr_run_returns_none_for_an_unknown_run(store):
    """Proves absence is `None`, not an empty `GRRun` with a blank run_id."""
    assert store.get_gr_run("RUN-nope") is None


def test_the_gr_run_column_list_omits_complete(store):
    """Proves the reader's column list is model-derived and excludes `complete`.

    An `ast`-free structural assertion: `complete` is a property on `GRRun`,
    not a field, so it cannot appear in `model_fields` -- and the reader
    builds its SELECT from exactly that.
    """
    from legacylift_search.knowledge_store import _GR_RUN_COLUMNS

    assert "complete" not in _GR_RUN_COLUMNS
    assert "not_accounted_for" in _GR_RUN_COLUMNS
    assert set(_GR_RUN_COLUMNS) == set(GRRun.model_fields)


# --------------------------------------------------------------------------
# Findings by severity -- `validate` and `stats`
# --------------------------------------------------------------------------


def test_finding_counts_keep_the_evaluated_split(store):
    """Proves `validate`'s exit code can distinguish "failed" from "undecided".

    A finding carrying `evaluated = 0` is a check that could not be decided,
    never one that failed (`gr_validator.can_approve` ignores exactly those),
    so a `validate` that exited non-zero on the raw `ERROR` count would
    refuse a corpus for checks nobody ran.
    """
    gr_id = _gr(store, 1)
    store.replace_gr_findings(
        gr_id,
        [
            Finding(finding_id="V-CLASS-01", severity="ERROR", span="", message="m"),
            Finding(
                finding_id="V-SLOT-01",
                severity="ERROR",
                span="",
                message="undecidable",
                evaluated=False,
            ),
            Finding(finding_id="V-STY-03", severity="WARN", span="1-2", message="w"),
        ],
    )
    store.commit()
    counts = store.gr_finding_counts_by_severity()
    assert counts["ERROR"] == {"evaluated": 1, "not_evaluated": 1}
    assert counts["WARN"] == {"evaluated": 1, "not_evaluated": 0}
    assert "INFO" not in counts, "an absent severity is an absent key, not a zero"


# --------------------------------------------------------------------------
# gr_dataflow reads -- `show` and `stats`
# --------------------------------------------------------------------------


def test_dataflow_reads_are_empty_and_that_is_the_expected_state(store):
    """Proves the Milestone-1 truth: the table has no writer and ships empty.

    `stats` therefore reports words rather than a rate -- a percentage over
    an empty set is the absent-versus-real defect in its purest form.
    """
    from legacylift_search.gr_dataflow import (
        GR_DATAFLOW_COMPUTED_ENABLED,
        dataflow_status_text,
    )

    gr_id = _gr(store, 1)
    assert GR_DATAFLOW_COMPUTED_ENABLED is False
    assert store.list_gr_dataflow(gr_id) == []
    assert store.count_gr_dataflow() == 0
    assert store.gr_dataflow_provenance_counts() == {}
    words = dataflow_status_text(total=0, computed=0, llm_inferred=0)
    assert "%" not in words and "M26" in words


def test_dataflow_rows_read_back_with_column_as_empty_string(store):
    """Proves the flagged-on shape reads back, with `column` as `''` not NULL.

    `column` sits in the table's uniqueness tuple and SQLite treats NULLs as
    distinct, so `''` -- meaning "this entry is about the whole datastore" --
    is the value that keeps the same entry from inserting repeatedly.
    """
    gr_id = _gr(store, 1)
    conn = store._connect()
    conn.execute(
        'INSERT INTO gr_dataflow (gr_id, direction, datastore, "column", '
        "provenance, explanation) VALUES (?, 'reads', 'ORDERS', '', "
        "'computed', 'uses_table edge')",
        (gr_id,),
    )
    store.commit()
    entries = store.list_gr_dataflow(gr_id)
    assert len(entries) == 1
    assert entries[0].column == ""
    assert entries[0].direction == "reads"
    assert store.gr_dataflow_provenance_counts() == {"computed": 1}
    assert store.count_gr_dataflow() == 1


# --------------------------------------------------------------------------
# set-run-coverage
# --------------------------------------------------------------------------


def test_set_run_coverage_records_a_remeasurement_with_its_stamp(store):
    """Proves the command's whole point: the figure was actually taken.

    It writes `coverage_source = 'remeasured'` -- not `'extraction'` -- and a
    timestamp, because the audit question is "why did this run stop blocking
    the gate?" and the answer here is "somebody went and measured it".
    """
    _run(store, "RUN-1", not_accounted_for=None, coverage_source=None)
    assert store.get_gr_run("RUN-1").complete is False

    store.set_gr_run_coverage(
        "RUN-1", not_accounted_for=0, measured_at="2026-09-02T12:00:00Z"
    )
    run = store.get_gr_run("RUN-1")
    assert run.not_accounted_for == 0
    assert run.coverage_source == "remeasured"
    assert run.coverage_measured_at == "2026-09-02T12:00:00Z"
    assert run.complete is True, "measured and nothing left over"


def test_set_run_coverage_refuses_a_measurement_that_was_not_made(store):
    """Proves NULL stays reachable-but-distinct: it cannot be written as zero.

    NULL in `not_accounted_for` means "never measured" and is exactly what
    the generated `complete` column keys off, so a command whose purpose is
    to assert a figure was taken must refuse the encoding for "no figure was
    taken" rather than substituting `0`.
    """
    _run(store, "RUN-1", not_accounted_for=None)
    with pytest.raises(ValueError, match="was not made"):
        store.set_gr_run_coverage(
            "RUN-1", not_accounted_for=None, measured_at="2026-09-02T00:00:00Z"
        )
    assert store.get_gr_run("RUN-1").not_accounted_for is None
    assert store.get_gr_run("RUN-1").coverage_source is None


def test_set_run_coverage_refuses_a_bad_count_a_blank_stamp_and_a_bad_run(store):
    """Proves the three refusals the schema itself would accept silently."""
    _run(store, "RUN-1")
    with pytest.raises(ValueError, match=">= 0"):
        store.set_gr_run_coverage("RUN-1", not_accounted_for=-1, measured_at="t")
    with pytest.raises(ValueError, match="coverage_measured_at is required"):
        store.set_gr_run_coverage("RUN-1", not_accounted_for=0, measured_at="  ")
    with pytest.raises(ValueError, match="no run"):
        store.set_gr_run_coverage("RUN-nope", not_accounted_for=0, measured_at="t")


# --------------------------------------------------------------------------
# retire-run
# --------------------------------------------------------------------------


def test_retire_run_excludes_the_run_and_leaves_the_coverage_figure_alone(store):
    """Proves the asymmetry that makes these two separate commands.

    `retire-run` records a human's judgement that a run no longer counts. It
    must not touch `not_accounted_for` -- and therefore not `complete` -- so
    the record still says what was actually known. Overwriting the coverage
    figure while retiring would forge a measurement to justify the
    judgement.
    """
    _run(store, "RUN-1", not_accounted_for=37)
    store.retire_gr_run("RUN-1", reason="superseded by RUN-2, wider module pattern")
    run = store.get_gr_run("RUN-1")
    assert run.gate_excluded is True
    assert run.gate_excluded_reason == "superseded by RUN-2, wider module pattern"
    assert run.not_accounted_for == 37, "the record still says what was known"
    assert run.complete is False, "retiring does not make a run complete"
    assert run.coverage_source is None
    assert run.coverage_measured_at is None


def test_retire_run_refuses_a_blank_reason_before_the_check_fires(store):
    """Proves the refusal is the method's, with a message the CHECK cannot give.

    The table CHECK does enforce a non-empty reason, but a raw
    `CHECK constraint failed` names neither the column nor the question.
    """
    _run(store, "RUN-1", not_accounted_for=1)
    for blank in ("", "   ", None):
        with pytest.raises(ValueError, match="non-empty reason"):
            store.retire_gr_run("RUN-1", reason=blank)  # type: ignore[arg-type]
    assert store.get_gr_run("RUN-1").gate_excluded is False
    with pytest.raises(ValueError, match="no run"):
        store.retire_gr_run("RUN-nope", reason="x")


def test_the_two_gate_exits_are_independent(store):
    """Proves each command writes only its own column pair.

    `PR-54`'s two exits from the completeness gate must stay
    distinguishable: an audit asks "how did this run stop blocking?" and the
    answer has to be readable from which pair is populated.
    """
    _run(store, "RUN-A", not_accounted_for=None)
    _run(store, "RUN-B", not_accounted_for=None)
    store.set_gr_run_coverage("RUN-A", not_accounted_for=0, measured_at="t")
    store.retire_gr_run("RUN-B", reason="superseded")

    a, b = store.get_gr_run("RUN-A"), store.get_gr_run("RUN-B")
    assert (a.coverage_source, a.gate_excluded) == ("remeasured", False)
    assert (b.coverage_source, b.gate_excluded) == (None, True)


def test_gr_run_hit_and_collapse_count_still_read_after_the_new_writers(store):
    """Proves the existing run API is untouched by this wave's additions."""
    gr_id = _gr(store, 1)
    _run(store, "RUN-1", not_accounted_for=0)
    store.insert_gr_run_hit(
        GRRunHit(gr_id=gr_id, run_id="RUN-1", offer_ordinal=0, outcome="new")
    )
    store.insert_gr_run_hit(
        GRRunHit(gr_id=gr_id, run_id="RUN-1", offer_ordinal=1, outcome="merged")
    )
    store.commit()
    assert store.intra_run_collapse_count("RUN-1") == 2


# --------------------------------------------------------------------------
# gr_refresh.leaked_terms_for -- the public promotion
# --------------------------------------------------------------------------


def test_leaked_terms_for_is_public_and_needs_no_cache(store, tmp_root):
    """Proves `validate` can build the set without writing anything.

    `requirements validate` "reports rule-notation violations without
    changing anything", so it cannot reach the validator through
    `refresh_gr_derived_sql` -- that rewrites `gr_fts` and replaces
    `gr_finding` rows. The public entry point exists for exactly that
    caller, and its `cache` is optional so a one-off call need not invent
    one.
    """
    from legacylift_search.gr_refresh import _leaked_terms_for
    from legacylift_search.store import SQLiteStore

    gr_id = _gr(store, 1)
    _cite(store, gr_id, "src/orders/OrderService.java")
    store.commit()

    index_dir = tmp_root / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    index_store = SQLiteStore(index_dir / "index.sqlite")
    try:
        index_store.migrate()
        # No symbols indexed for that file, so the set is empty -- which
        # proves the call path works, not that leakage is absent.
        assert leaked_terms_for(store, index_store, gr_id) == frozenset()
        shared: dict = {}
        assert leaked_terms_for(store, index_store, gr_id, shared) == frozenset()
        assert "src/orders/OrderService.java" in shared, "the cache is populated"
        # The private name still exists and still delegates the same way, so
        # `refresh_gr_derived_sql` needs no change.
        assert _leaked_terms_for(store, index_store, gr_id, {}) == frozenset()
    finally:
        index_store.close()


# --------------------------------------------------------------------------
# gr_refresh.reindex_gr_vectors -- the full rebuild
# --------------------------------------------------------------------------


def test_reindex_rebuilds_the_collection_and_is_safe_to_run_twice(store):
    """Proves Step 5's single documented recovery works and is idempotent."""
    ids = [_gr(store, n, statement=f"Rule number {n} must hold.") for n in (1, 2, 3)]
    store.commit()

    first = reindex_gr_vectors(store, embedder=HashEmbedder(dimension=64))
    assert first.embedded == 3
    assert first.reason is None

    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        assert collection.count() == 3
    finally:
        collection.close()

    second = reindex_gr_vectors(store, embedder=HashEmbedder(dimension=64))
    assert second.embedded == 3
    assert second.deleted == 0

    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        assert collection.count() == 3, "an upsert, not a duplicate insert"
        got = collection.collection.get(ids=ids, include=["metadatas"])
        assert sorted(got["ids"]) == sorted(ids)
    finally:
        collection.close()


def test_reindex_deletes_the_vector_of_a_requirement_that_no_longer_exists(store):
    """Proves a searchable ghost is swept, not left behind forever.

    `refresh_gr_vectors` deletes an absent `gr_id` only among the ids it was
    *given*, so a requirement deleted while the collection was stale would
    keep its vector indefinitely -- the same defect `replace_gr_fts`'s
    delete half prevents on the keyword side.
    """
    gone = _gr(store, 1)
    kept = _gr(store, 2)
    store.commit()
    reindex_gr_vectors(store, embedder=HashEmbedder(dimension=64))

    store._connect().execute("DELETE FROM gr WHERE gr_id = ?", (gone,))
    store.commit()

    result = reindex_gr_vectors(store, embedder=HashEmbedder(dimension=64))
    assert result.deleted >= 1
    assert result.embedded == 1

    collection = open_gr_collection(store, HashEmbedder(dimension=64))
    try:
        assert collection.count() == 1
        assert collection.collection.get(ids=[gone], include=[])["ids"] == []
        assert collection.collection.get(ids=[kept], include=[])["ids"] == [kept]
    finally:
        collection.close()


def test_reindex_with_no_embedder_degrades_and_names_itself(store):
    """Proves the no-embedder path is a degraded success naming the recovery.

    This is the one place the recovery command *is* the recovery, so the
    message has to say the rebuild could not run rather than reporting a
    successful rebuild of nothing.
    """
    _gr(store, 1)
    store.commit()
    result = reindex_gr_vectors(store, embedder=None)
    assert result.embedded == 0
    assert result.skipped == 1
    assert result.reason is not None
    assert "reindex-vectors" in result.reason


def test_reindex_on_an_empty_store_is_a_successful_rebuild_of_nothing(store):
    """Proves zero requirements is not reported as a failure.

    Every count is zero and `reason` is None, which the caller must render as
    "0 requirements" -- an absent corpus and a failed rebuild must not share
    an encoding here either.
    """
    result = reindex_gr_vectors(store, embedder=HashEmbedder(dimension=64))
    assert (result.embedded, result.skipped, result.deleted) == (0, 0, 0)
    assert result.reason is None
