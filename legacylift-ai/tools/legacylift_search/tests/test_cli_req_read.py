"""Tests for the four read-only `requirements` commands (M1 Step 8).

`list`, `show`, `search` and `stats` in
`legacylift_search/cli_requirements/read_cmds.py`. Every test here fails
before that module registers its commands (`typer` exits 2, "No such
command") and passes after.

Everything is driven through `typer.testing.CliRunner` against
`legacylift_search.cli:app` with `["requirements", ...]`, so what is
exercised is the **real registration** through the sub-app -- the house
precedent in `tests/test_cli_commands.py` and `tests/test_cli_smoke.py`. A
test against the sub-app in isolation would pass with the `add_typer` call
deleted.

Two things this file leans on that are worth knowing before adding to it.
Click 8.4 keeps `Result.stdout` and `Result.stderr` **separate**, which is
what makes house rule 4 assertable at all: the resolved-path banner and every
diagnostic must be absent from stdout, because all four commands take
`--json`. And the fixtures come from the existing GR test files
(`tests.test_gr_state.insert_gr`, `tests.test_gr_schema.insert_citation`)
rather than being reinvented here.

The assertions worth naming, because each is one this plan's history says a
green suite can hide:

* a NULL must be its own bucket in `stats` and must survive `--json` as a
  real `null` -- the probe that fails under `COALESCE(col, 'none')` and under
  the tempting repair of stringifying the key;
* a NULL `gr_merge_candidate.similarity` must print as `unmeasured`, never
  `0.0`, on exactly the pairs most likely to be real duplicates;
* a NULL `gr_run.not_accounted_for` must print as `unmeasured`, never `0`;
* `--semantic` over a collection that was never built must **exit non-zero**
  and print nothing on stdout, because "nothing matched" and "nothing was
  ever indexed" are different facts;
* `stats` must say whether `V-STY-03`'s symbol half was reachable at all.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.cli_requirements._shared import resolve_requirements_paths
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import Finding, GRMergeCandidate, GRRun, GRRunHit

from tests.test_gr_schema import insert_citation
from tests.test_gr_state import insert_gr

_IS_WINDOWS = sys.platform == "win32"

#: A conformant `B-UNCOND` statement whose `[Subject]` span is locatable, so
#: `show` can be asked about the divergence between the statement's own
#: subject and the derived `subject` column.
STATEMENT = "The Order Service must record a vendor number on each order."


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def repo():
    """A repository root plus an analysis directory, neither populated."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        yield root, root / "analysis"


def paths_for(repo_root: Path, analysis_dir: Path):
    """The resolved paths, with the banner suppressed (this is test setup)."""
    return resolve_requirements_paths(
        repo_root, None, analysis_dir, print_banner=False
    )


def open_store(repo_root: Path, analysis_dir: Path) -> KnowledgeStore:
    """Create/open the knowledge store where the CLI will look for it."""
    return KnowledgeStore(paths_for(repo_root, analysis_dir).knowledge_sqlite_path)


def cli(runner: CliRunner, repo_root: Path, analysis_dir: Path, *args: str):
    """Invoke a `requirements` subcommand with the two path flags appended."""
    return runner.invoke(
        app,
        [
            "requirements",
            *args,
            "--repo-root",
            str(repo_root),
            "--analysis-dir",
            str(analysis_dir),
        ],
    )


def hash_embedder():
    """The deterministic embedder the manifest's `hash` provider builds.

    Dimension 1024 rather than the class default 64, because
    `create_embedder` passes `manifest.embedding.dimension` (1024) for the
    `hash` provider -- so a collection seeded at 64 here would fail
    `validate_dimension` against the CLI's own embedder and the test would
    be measuring a dimension mismatch instead of what it says it measures.
    """
    from legacylift_search.embeddings import HashEmbedder

    return HashEmbedder(dimension=1024)


def embed(store: KnowledgeStore, gr_ids: list[str]) -> None:
    """Populate the `gr_statements` collection for `gr_ids`, hash provider."""
    from legacylift_search.gr_refresh import refresh_gr_vectors

    result = refresh_gr_vectors(store, gr_ids, hash_embedder())
    assert result.reason is None, result.reason


# ==========================================================================
# House rule 2 -- every one of the four probes before it opens
# ==========================================================================


@pytest.mark.parametrize(
    "args",
    [
        ("list",),
        ("show", "GR-01HQ2X0000000000000000000"),
        ("search", "vendor"),
        ("stats",),
    ],
)
def test_every_read_command_reports_a_missing_store_and_creates_nothing(
    runner, repo, args
):
    """Proves all four read commands probe `Path.exists()` before opening.

    `KnowledgeStore.__init__` creates the database **and its parent
    directory**, so a read-only command that constructs one to find out
    whether requirements exist silently materializes an empty store -- and an
    empty knowledge database is indistinguishable from a real one on the next
    command. Only a filesystem assertion can catch this, so that is what this
    makes.
    """
    root, analysis = repo
    paths = paths_for(root, analysis)
    result = cli(runner, root, analysis, *args)
    assert result.exit_code == 1, result.output
    assert "requirements ingest" in result.stderr
    assert not paths.knowledge_sqlite_path.exists()
    assert not paths.knowledge_sqlite_path.parent.exists(), (
        "not even the parent directory may be created by a read path"
    )


# ==========================================================================
# `list`
# ==========================================================================


def test_list_on_an_empty_store_is_a_normal_state_not_an_error(runner, repo):
    """Proves an empty store exits zero and says so in its own words.

    An empty store is a normal state for all four commands, and the sentence
    must differ from "nothing matched your filter" -- otherwise a reviewer
    reads a mis-typed filter as an empty corpus.
    """
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "list")
    assert result.exit_code == 0, result.output
    assert "no requirements in the store" in result.stdout


def test_list_distinguishes_no_match_from_an_empty_store(runner, repo):
    """Proves a filter that matches nothing names the filter it applied."""
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        insert_gr(store._connect(), gr_id="GR-01HQ2X000000000000000000A")
    finally:
        store.close()
    result = cli(runner, root, analysis, "list", "--state", "approved")
    assert result.exit_code == 0, result.output
    assert "no requirements match" in result.stdout
    assert "state='approved'" in result.stdout
    assert "no requirements in the store" not in result.stdout


def test_list_filters_are_exact_and_anded(runner, repo):
    """Proves the five filters AND together as exact equalities.

    `query_gr`'s `None` means "unfiltered", never "match NULL" -- so this
    also proves an omitted filter does not silently become an `IS NULL`
    clause, which would return the wrong rows rather than an error.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        conn = store._connect()
        insert_gr(conn, gr_id="GR-A0000000000000000000000A", state="draft",
                  category="Validation", disposition="captured")
        insert_gr(conn, gr_id="GR-A0000000000000000000000B", state="approved",
                  category="Validation", disposition="captured")
        insert_gr(conn, gr_id="GR-A0000000000000000000000C", state="approved",
                  category="Calculation", disposition="captured")
    finally:
        store.close()

    both = cli(runner, root, analysis, "list", "--state", "approved",
               "--category", "Validation", "--json")
    assert both.exit_code == 0, both.output
    payload = json.loads(both.stdout)
    assert [r["gr_id"] for r in payload["requirements"]] == [
        "GR-A0000000000000000000000B"
    ]
    assert payload["count"] == 1

    one = cli(runner, root, analysis, "list", "--state", "approved", "--json")
    assert len(json.loads(one.stdout)["requirements"]) == 2


def test_list_json_carries_priority_for_the_brief_p0_filter(runner, repo):
    """`list --json` must expose `priority`, because the brief reads P0 here.

    `/modernize-brief` builds its Behavior Contract from the rules tagged
    `Priority: P0`, and `/modernize-extract-rules` renders those tags from
    this listing. The projection omitted `priority` until 2026-09-14, so the
    contract came out empty on every corpus -- silently, because an empty
    P0 set is indistinguishable from a corpus with no P0 rules.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        conn = store._connect()
        insert_gr(conn, gr_id="GR-P0000000000000000000000A", priority="P0")
        insert_gr(conn, gr_id="GR-P0000000000000000000000B", priority="P2")
        insert_gr(conn, gr_id="GR-P0000000000000000000000C", priority=None)
    finally:
        store.close()

    result = cli(runner, root, analysis, "list", "--json")
    assert result.exit_code == 0, result.output
    rows = {r["gr_id"]: r for r in json.loads(result.stdout)["requirements"]}

    assert rows["GR-P0000000000000000000000A"]["priority"] == "P0"
    assert rows["GR-P0000000000000000000000B"]["priority"] == "P2"
    # An untagged rule reports null rather than dropping the key: a caller
    # filtering for P0 must be able to tell "not P0" from "field absent".
    assert rows["GR-P0000000000000000000000C"]["priority"] is None
    assert "priority" in rows["GR-P0000000000000000000000C"]


def test_list_json_is_on_stdout_and_every_banner_is_on_stderr(runner, repo):
    """Proves house rule 4: a parsing caller's stdout is not corrupted.

    The resolved-path banner is the thing most likely to end up on stdout,
    because it is printed by shared code before the command body runs.
    """
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "list", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["count"] == 0
    assert "resolved knowledge directory" in result.stderr
    assert "resolved" not in result.stdout


def test_list_refuses_a_negative_limit_rather_than_reading_it_as_unlimited(
    runner, repo
):
    """Proves `query_gr`'s refusal reaches the operator as a message.

    SQLite's own `LIMIT -1` means unlimited, so a negative limit that was
    passed through would silently do the opposite of what was asked.
    """
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "list", "--limit", "-3")
    assert result.exit_code == 1, result.output
    assert "limit must be >= 0" in result.stderr


# --------------------------------------------------------------------------
# `list --candidates`
# --------------------------------------------------------------------------


def seed_candidates(store: KnowledgeStore) -> None:
    """Two unresolved pairs -- one `semantic` (scored), one `range_overlap`.

    Plus one already-resolved pair, which must not be listed.
    """
    conn = store._connect()
    for suffix in "ABCDEF":
        insert_gr(conn, gr_id=f"GR-A000000000000000000000{suffix}0")
    store.record_gr_merge_candidate(
        GRMergeCandidate(
            gr_id_existing="GR-A000000000000000000000A0",
            gr_id_incoming="GR-A000000000000000000000B0",
            run_id="RUN-1",
            similarity=0.7407,
            reason="semantic",
        )
    )
    store.record_gr_merge_candidate(
        GRMergeCandidate(
            gr_id_existing="GR-A000000000000000000000C0",
            gr_id_incoming="GR-A000000000000000000000D0",
            run_id="RUN-1",
            similarity=None,
            reason="range_overlap",
        )
    )
    store.record_gr_merge_candidate(
        GRMergeCandidate(
            gr_id_existing="GR-A000000000000000000000E0",
            gr_id_incoming="GR-A000000000000000000000F0",
            run_id="RUN-1",
            reason="drift",
            resolution="distinct",
        )
    )
    store.commit()


def test_list_candidates_shows_both_ids_the_reason_and_the_score(runner, repo):
    """Proves stage two's output is actionable, not just counted.

    Without `--candidates` the pairs are counted and never seen, and the
    whole under-merge safety argument collapses into a number nobody looks
    at. A reviewer deciding `merged` or `distinct` needs all four fields, so
    all four are asserted.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_candidates(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "list", "--candidates")
    assert result.exit_code == 0, result.output
    out = result.stdout
    assert "GR-A000000000000000000000A0" in out
    assert "GR-A000000000000000000000B0" in out
    assert "reason=semantic" in out
    assert "0.7407" in out


def test_list_candidates_renders_a_null_similarity_as_unmeasured_not_zero(
    runner, repo
):
    """Proves the plan's recurring defect is absent from this rendering.

    A `range_overlap` (or `drift`) candidate was found by line-range
    intersection with no vector comparison at all. Rendering its NULL
    `similarity` as `0.0` reads as "compared, and found maximally
    dissimilar" -- the opposite of what happened, on the pair most likely to
    be a genuine duplicate.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_candidates(store)
    finally:
        store.close()

    text = cli(runner, root, analysis, "list", "--candidates")
    assert text.exit_code == 0, text.output
    assert "similarity=unmeasured" in text.stdout
    assert "similarity=0.0" not in text.stdout

    as_json = cli(runner, root, analysis, "list", "--candidates", "--json")
    rows = {
        (r["gr_id_existing"], r["gr_id_incoming"]): r
        for r in json.loads(as_json.stdout)["candidates"]
    }
    overlap = rows[
        ("GR-A000000000000000000000C0", "GR-A000000000000000000000D0")
    ]
    assert overlap["similarity"] is None
    assert overlap["similarity_measured"] is False
    scored = rows[("GR-A000000000000000000000A0", "GR-A000000000000000000000B0")]
    assert scored["similarity_measured"] is True


def test_list_candidates_lists_only_unresolved_pairs(runner, repo):
    """Proves a resolution a reviewer recorded is not re-surfaced.

    The already-`distinct` pair in the fixture must be absent: re-raising it
    would ask the same question twice and make the resolution worthless.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_candidates(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "list", "--candidates", "--json")
    payload = json.loads(result.stdout)
    assert payload["count"] == 2
    assert all(c["resolution"] == "unresolved" for c in payload["candidates"])
    assert "GR-A000000000000000000000E0" not in result.stdout


def test_list_candidates_refuses_a_gr_column_filter_rather_than_ignoring_it(
    runner, repo
):
    """Proves a full candidate list can never be read as a filtered one.

    The five filters are `gr` columns; a candidate row is a pair of
    `gr_id`s. Silently ignoring `--state` here would let a reviewer conclude
    a specific requirement has no near-duplicates when the list they saw was
    never filtered at all.
    """
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "list", "--candidates", "--state", "draft")
    assert result.exit_code == 1, result.output
    assert "--state" in result.stderr
    assert result.stdout == ""


def test_list_candidates_empty_says_what_it_does_not_prove(runner, repo):
    """Proves an empty candidate list points at the shortfall check.

    Stage two's semantic half only sees requirements that have a vector, so
    "no candidates" over a stale collection is not evidence there are no
    near-duplicates. The empty message has to say so or the safety argument
    is unfalsifiable.
    """
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "list", "--candidates")
    assert result.exit_code == 0, result.output
    assert "no unresolved merge candidates" in result.stdout
    assert "stats" in result.stdout


# ==========================================================================
# `show`
# ==========================================================================


def test_show_reports_an_unknown_gr_id_on_stderr_and_exits_one(runner, repo):
    """Proves an unknown id is an error with a pointer, not empty output."""
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "show", "GR-NOPE")
    assert result.exit_code == 1, result.output
    assert "GR-NOPE" in result.stderr
    assert result.stdout == ""


def seed_one(store: KnowledgeStore, **overrides) -> str:
    """One requirement with a citation, ready for `show`."""
    conn = store._connect()
    gr_id = insert_gr(
        conn,
        gr_id="GR-A0000000000000000000SHOW",
        statement=STATEMENT,
        statement_extracted=STATEMENT,
        rule_class="behavioral",
        pattern="B-UNCOND",
        **overrides,
    )
    insert_citation(conn, gr_id, content_hash=None)
    conn.commit()
    return gr_id


def test_show_prints_step_sevens_words_for_data_flow_and_never_a_rate(
    runner, repo
):
    """Proves the empty data-flow block is reported in words.

    `gr_dataflow` has no writer in Milestone 1 and ships empty, so any rate
    is zero-over-zero. `gr_dataflow.dataflow_status_text` is the one producer
    of that sentence and this asserts the command called it rather than
    composing its own -- the string is compared against the function's own
    return value, so the two cannot drift.
    """
    from legacylift_search.gr_dataflow import dataflow_status_text

    root, analysis = repo
    store = open_store(root, analysis)
    try:
        gr_id = seed_one(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "show", gr_id)
    assert result.exit_code == 0, result.output
    assert dataflow_status_text(total=0, computed=0, llm_inferred=0) in result.stdout
    assert "%" not in result.stdout


def test_show_makes_a_subject_divergence_visible(runner, repo):
    """Proves the one staleness `rederive-subjects` deliberately leaves is shown.

    `rederive-subjects` refreshes `subject` from the current `file_domains`
    and never rewrites `statement` -- Step 6a made the statement
    extractor-authored, so there is no template to re-fill. The divergence
    that leaves (the *text* names a subject the domain set no longer derives
    while the column says what the derivation now yields) is exactly what the
    plan puts in `show`, and hiding it would make a stale corpus read as a
    fresh one.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        gr_id = seed_one(store, subject="billing", subject_provenance="derived")
    finally:
        store.close()
    result = cli(runner, root, analysis, "show", gr_id)
    assert result.exit_code == 0, result.output
    assert "DIVERGENCE" in result.stdout
    # Both halves are named, because either one alone is unactionable.
    assert "'The Order Service'" in result.stdout
    assert "'billing'" in result.stdout


def test_show_reports_no_divergence_when_the_column_matches_the_statement(
    runner, repo
):
    """Proves the divergence notice is a real branch, not printed always.

    A notice that fired unconditionally would be indistinguishable from no
    notice at all, which is the same absent-versus-real defect in prose form.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        gr_id = seed_one(
            store, subject="The Order Service", subject_provenance="llm_named"
        )
    finally:
        store.close()
    result = cli(runner, root, analysis, "show", gr_id)
    assert result.exit_code == 0, result.output
    assert "DIVERGENCE" not in result.stdout
    assert "statement subject   The Order Service" in result.stdout


def test_show_json_carries_the_whole_record_and_the_divergence_flag(runner, repo):
    """Proves `show --json` is the lossless form `list --json` is not.

    `list --json` emits a projection on purpose (`extractor_payload` is the
    verbatim backstop and dwarfs every other column), so exactly one command
    has to be able to hand a caller every column.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        gr_id = seed_one(store, subject="billing", subject_provenance="derived")
    finally:
        store.close()
    result = cli(runner, root, analysis, "show", gr_id, "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["requirement"]["dedupe_key_anchor_only"]
    assert payload["requirement"]["extractor_payload"] is not None
    assert payload["subject_divergence"] == {
        "column": "billing",
        "column_provenance": "derived",
        "statement_subject": "The Order Service",
        "diverged": True,
    }
    assert payload["dataflow"]["entries"] == []
    assert len(payload["citations"]) == 1


def test_show_marks_a_not_evaluated_finding_as_such(runner, repo):
    """Proves a check that could not be decided does not read as one that failed.

    `evaluated = 0` is not a third severity value: `can_approve` ignores
    exactly those rows, so an ERROR-severity finding carrying it must not
    look like a blocking one in the only place a human reads findings.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        gr_id = seed_one(store)
        store.replace_gr_findings(
            gr_id,
            [
                Finding(
                    finding_id="V-SLOT-01",
                    severity="ERROR",
                    span="",
                    message="no template applies; pattern is NULL",
                    evaluated=False,
                ),
                Finding(
                    finding_id="V-STY-03",
                    severity="WARN",
                    span="4-17",
                    message="leaked identifier",
                ),
            ],
        )
        store.commit()
    finally:
        store.close()
    result = cli(runner, root, analysis, "show", gr_id)
    assert result.exit_code == 0, result.output
    assert "[NOT EVALUATED]" in result.stdout
    lines = [ln for ln in result.stdout.splitlines() if "V-STY-03" in ln]
    assert lines and "[NOT EVALUATED]" not in lines[0]


def test_show_renders_a_null_content_hash_as_absent_not_as_a_value(runner, repo):
    """Proves an unhashable citation span is visibly absent, not blank.

    `gr_citation.content_hash` is nullable because a citation whose line
    range cannot be read inserts with NULL rather than being hashed over a
    guess. An empty cell there is indistinguishable from a hash nobody
    noticed was missing.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        gr_id = seed_one(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "show", gr_id)
    assert result.exit_code == 0, result.output
    assert "content_hash=<absent>" in result.stdout


# ==========================================================================
# `search` -- the FTS5 half
# ==========================================================================


def seed_for_search(store: KnowledgeStore) -> list[str]:
    """Two requirements in different states, both in `gr_fts`."""
    conn = store._connect()
    first = insert_gr(
        conn,
        gr_id="GR-A00000000000000000000FT1",
        statement=STATEMENT,
        statement_extracted=STATEMENT,
        state="approved",
    )
    second_text = "The Billing Service must reject a duplicate invoice number."
    second = insert_gr(
        conn,
        gr_id="GR-A00000000000000000000FT2",
        statement=second_text,
        statement_extracted=second_text,
        state="draft",
    )
    for gr_id in (first, second):
        store.replace_gr_fts(store.get_gr(gr_id))
    store.commit()
    return [first, second]


def test_search_keyword_finds_a_statement_through_fts5(runner, repo):
    """Proves the default half is the FTS5 index, not a LIKE scan."""
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_for_search(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "search", "vendor")
    assert result.exit_code == 0, result.output
    assert "GR-A00000000000000000000FT1" in result.stdout
    assert "GR-A00000000000000000000FT2" not in result.stdout


def test_search_keyword_no_match_exits_zero_and_says_no_match(runner, repo):
    """Proves an unmatched query is a normal answer, not a failure.

    Distinct from the semantic half, where "the search could not run" exits
    non-zero -- the two must not be conflated in either direction.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_for_search(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "search", "zzznosuchtoken")
    assert result.exit_code == 0, result.output
    assert "no keyword matches" in result.stdout


def test_search_keyword_state_filter_declares_that_it_ran_after_ranking(
    runner, repo
):
    """Proves the keyword half's `--state` does not silently hide matches.

    FTS5 ranks first and the state filter is applied to the ranked page, so a
    small `--limit` can drop matching rows. Saying so is the difference
    between a filter and a trap.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_for_search(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "search", "must", "--state", "approved")
    assert result.exit_code == 0, result.output
    assert "GR-A00000000000000000000FT1" in result.stdout
    assert "GR-A00000000000000000000FT2" not in result.stdout
    assert "AFTER ranking" in result.stdout

    payload = json.loads(
        cli(
            runner, root, analysis, "search", "must", "--state", "approved",
            "--json",
        ).stdout
    )
    assert payload["state_filter_applied_after_ranking"] is True
    assert payload["hits_dropped_by_state_filter"] == 1


def test_search_json_stdout_stays_parseable(runner, repo):
    """Proves the keyword half's `--json` is uncorrupted by the banner."""
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_for_search(store)
    finally:
        store.close()
    result = cli(runner, root, analysis, "search", "vendor", "--json")
    payload = json.loads(result.stdout)
    assert payload["mode"] == "keyword"
    assert payload["count"] == 1
    assert "resolved" not in result.stdout


# ==========================================================================
# `search --semantic`
# ==========================================================================


def test_semantic_search_on_an_empty_store_is_a_normal_state(runner, repo):
    """Proves an empty store needs no embedder and no collection.

    With zero requirements there is nothing that could have been indexed, so
    this is not a shortfall and must not be reported as one.
    """
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "search", "vendor", "--semantic")
    assert result.exit_code == 0, result.output
    assert "no requirements in the store" in result.stdout


def test_semantic_search_over_a_collection_that_was_never_built_exits_nonzero(
    runner, repo
):
    """Proves "nothing was ever indexed" does not print as "nothing matched".

    This is the load-bearing one. A `--semantic` query against a store whose
    collection has never been created would otherwise return zero hits,
    which is byte-identical to a real search that matched nothing -- and the
    caller has no way to tell. So it exits non-zero, writes nothing to
    stdout, and the stderr message carries
    `describe_vector_shortfall`'s own sentence naming the recovery command.

    It also proves no collection is created as a side effect:
    `get_or_create_collection` would have made an empty one, and an empty
    collection is indistinguishable from a real one on the next command.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_for_search(store)
    finally:
        store.close()
    paths = paths_for(root, analysis)
    result = cli(
        runner, root, analysis, "search", "vendor", "--semantic",
        "--embedding-provider", "hash",
    )
    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    assert "has ever been indexed" in result.stderr
    assert "reindex-vectors" in result.stderr
    assert not (paths.knowledge_dir / "chroma").exists()


def test_semantic_search_reports_a_missing_provider_rather_than_zero_hits(
    runner, repo
):
    """Proves an unbuildable provider is reported, not answered with silence.

    `build_embedder` returns `(None, reason)` rather than raising, and the
    reason is returned so the caller routes it -- here to stderr, exiting
    non-zero, because the question asked could not be answered at all.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_for_search(store)
    finally:
        store.close()
    result = cli(
        runner, root, analysis, "search", "vendor", "--semantic",
        "--embedding-provider", "not-a-provider",
    )
    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    assert "--semantic cannot run" in result.stderr
    assert "without --semantic" in result.stderr


def test_semantic_search_labels_its_score_as_an_unpinned_distance(runner, repo):
    """Proves a displayed score cannot be silently reinterpreted later.

    `ChromaVectorStore` sets no `hnsw:space`, so the number is an L2 distance
    on the pinned chromadb 1.5.9. Printing it as a bare score -- or worse, as
    a similarity -- means moving the pin or setting a space changes what
    every recorded number meant, with nothing to say so.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        ids = seed_for_search(store)
        embed(store, ids)
    finally:
        store.close()
    result = cli(
        runner, root, analysis, "search", "vendor number", "--semantic",
        "--embedding-provider", "hash",
    )
    assert result.exit_code == 0, result.output
    assert "distance=" in result.stdout
    assert "L2 distance" in result.stdout
    assert "hnsw:space" in result.stdout

    payload = json.loads(
        cli(
            runner, root, analysis, "search", "vendor number", "--semantic",
            "--embedding-provider", "hash", "--json",
        ).stdout
    )
    assert payload["score_kind"] == "distance"
    assert "hnsw:space" in payload["score_metric"]
    assert payload["hits"][0]["gr_id"] in ids


def test_semantic_search_filters_on_the_collections_state_metadata(runner, repo):
    """Proves `state` reached the vector metadata and filters inside the query.

    This is the assertion that fails if a state change never reaches the
    collection: an approved requirement whose vector is still tagged `draft`
    is invisible to every state-filtered semantic search, and nothing
    reports it.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        ids = seed_for_search(store)
        embed(store, ids)
    finally:
        store.close()
    approved = json.loads(
        cli(
            runner, root, analysis, "search", "must", "--semantic", "--state",
            "approved", "--embedding-provider", "hash", "--json",
        ).stdout
    )
    assert [h["gr_id"] for h in approved["hits"]] == [
        "GR-A00000000000000000000FT1"
    ]
    assert all(h["state"] == "approved" for h in approved["hits"])


def test_semantic_search_warns_on_a_lagging_collection_but_still_answers(
    runner, repo
):
    """Proves a partial collection degrades loudly and still returns results.

    A collection that lags `gr` did run over real vectors, so the hits are
    real and the exit code is zero -- but the shortfall sentence has to reach
    stderr first, or a reviewer reads a partial answer as a complete one.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        ids = seed_for_search(store)
        embed(store, ids[:1])
    finally:
        store.close()
    result = cli(
        runner, root, analysis, "search", "vendor number", "--semantic",
        "--embedding-provider", "hash",
    )
    assert result.exit_code == 0, result.output
    assert "holds 1 of 2 requirements" in result.stderr
    assert "reindex-vectors" in result.stderr
    assert "distance=" in result.stdout


# ==========================================================================
# `stats`
# ==========================================================================


def test_stats_keeps_null_as_its_own_bucket_and_a_real_null_in_json(
    runner, repo
):
    """Proves `COALESCE(col, 'none')` is not what produced these counts.

    `count_gr_by` returns NULL under the Python `None` key deliberately, and
    the natural SQL -- `COALESCE(col, 'none')` -- silently merges an
    untriaged requirement with a triaged one. Two buckets of one is the
    outcome that proves the merge did not happen.

    The JSON half is the sharper assertion, and it is why every grouped count
    serializes as a **list of pairs** rather than an object: a JSON object
    cannot carry a null key, so the tempting repair is to stringify it -- and
    a bucket keyed `"None"` or `"<absent>"` is then indistinguishable from a
    real value spelled that way. The text sentinel must not leak into the
    machine-readable form, so this asserts the value is a real `null`.

    (Every groupable `gr` column carries a `CHECK`, so a *real* value
    literally spelled `'none'` cannot be inserted to collide with the
    coalesced one -- which is why the collision is asserted against the
    encoding rather than against a planted row.)
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        conn = store._connect()
        insert_gr(conn, gr_id="GR-A00000000000000000000N01", disposition=None)
        insert_gr(
            conn, gr_id="GR-A00000000000000000000N02", disposition="captured"
        )
    finally:
        store.close()

    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    rows = payload["counts"]["disposition"]
    assert len(rows) == 2
    assert {r["value"] for r in rows} == {None, "captured"}
    assert all(r["count"] == 1 for r in rows)
    assert "None" not in {r["value"] for r in rows}
    assert "<absent>" not in {r["value"] for r in rows}
    # `count_gr_by` orders the absent bucket last, and the rendering keeps it.
    assert rows[-1]["value"] is None

    text = cli(runner, root, analysis, "stats").stdout
    disposition_block = text.split("by disposition:")[1].split("by subject")[0]
    assert "<absent>" in disposition_block
    assert "captured" in disposition_block


def test_stats_counts_null_subjects_apart_from_llm_named(runner, repo):
    """Proves the ninth-round criterion: the two figures are separate.

    A row can carry `subject_provenance = 'llm_named'` with a NULL `subject`
    -- the fallback branch ran and `split_slots` located no `[Subject]` span
    because `pattern` is NULL. Folding the two together reports a
    model-named subject for a requirement that has none.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        conn = store._connect()
        insert_gr(
            conn, gr_id="GR-A00000000000000000000S01",
            subject=None, subject_provenance="llm_named", pattern=None,
        )
        insert_gr(
            conn, gr_id="GR-A00000000000000000000S02",
            subject="The Order Service", subject_provenance="llm_named",
        )
    finally:
        store.close()

    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    provenance = {r["value"]: r["count"] for r in payload["counts"]["subject_provenance"]}
    assert provenance["llm_named"] == 2
    assert payload["null_subjects"]["count"] == 1

    text = cli(runner, root, analysis, "stats").stdout
    assert "subject absent (no subject was locatable): 1 of 2" in text
    assert "APART from llm_named" in text


def test_stats_states_the_numerator_of_every_fill_rate(runner, repo):
    """Proves the rate this command invents says which question it answered.

    `gr_field_fill_counts` returns three numbers rather than a rate because
    the numerator differs per column and it refuses to choose. So the chooser
    has to publish the choice: `assumptions` counts `filled+empty` (its `''`
    means "considered, and none"), every other free-text column counts
    `filled` alone, and `modality_confirmed` gets **no rate at all** --
    `NOT NULL DEFAULT 0` makes a rate a guaranteed 100% measuring nothing,
    and its `0` is a fact rather than an absence.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        conn = store._connect()
        insert_gr(conn, gr_id="GR-A00000000000000000000F01", assumptions="")
        insert_gr(conn, gr_id="GR-A00000000000000000000F02", assumptions=None)
        insert_gr(
            conn, gr_id="GR-A00000000000000000000F03",
            assumptions="the vendor number is always present", owner="dnorton",
        )
    finally:
        store.close()

    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    fill = payload["review_progress"]
    assert fill["assumptions"] == {
        "filled": 1,
        "empty": 1,
        "absent": 1,
        "total": 3,
        "numerator": "filled+empty",
        "numerator_count": 2,
        "rate": "2/3 (67%)",
    }
    assert fill["owner"]["numerator"] == "filled"
    assert fill["owner"]["rate"] == "1/3 (33%)"
    assert fill["modality_confirmed"]["numerator"] is None
    assert fill["modality_confirmed"]["rate"] is None

    text = cli(runner, root, analysis, "stats").stdout
    assert "of filled+empty" in text
    assert "no rate reported" in text


def test_stats_prints_the_dataflow_block_in_words_and_never_a_rate(runner, repo):
    """Proves the empty data-flow table is never reported as a percentage.

    Compared against `dataflow_status_text`'s own return value, so `stats`
    and Step 7 cannot drift into two different sentences about one empty
    table.
    """
    from legacylift_search.gr_dataflow import dataflow_status_text

    root, analysis = repo
    store = open_store(root, analysis)
    try:
        insert_gr(store._connect(), gr_id="GR-A00000000000000000000D01")
    finally:
        store.close()
    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    assert payload["dataflow"]["total"] == 0
    assert payload["dataflow"]["status"] == dataflow_status_text(
        total=0, computed=0, llm_inferred=0
    )
    assert "%" not in payload["dataflow"]["status"]


def seed_runs(store: KnowledgeStore) -> None:
    """Two runs: one whose coverage was measured, one whose never was.

    The measured one also carries two offered rules that landed on the same
    `gr_id`, which is the intra-run collapse Step 10 makes mandatory.
    """
    conn = store._connect()
    gr_id = insert_gr(conn, gr_id="GR-A00000000000000000000R01")
    store.insert_gr_run(
        GRRun(run_id="RUN-MEASURED", system="nng", rules_in=7, rules_new=5,
              rules_merged=1, rules_candidate=1, rules_rejected=0,
              not_accounted_for=0, coverage_source="extraction",
              coverage_measured_at="2026-09-02T00:00:00Z")
    )
    store.insert_gr_run(
        GRRun(run_id="RUN-UNMEASURED", system="nng", rules_in=2,
              not_accounted_for=None)
    )
    for ordinal in (0, 1):
        store.insert_gr_run_hit(
            GRRunHit(
                gr_id=gr_id, run_id="RUN-MEASURED", offer_ordinal=ordinal,
                outcome="new" if ordinal == 0 else "merged",
            )
        )
    store.commit()


def test_stats_reports_an_unmeasured_coverage_as_unmeasured_not_zero(runner, repo):
    """Proves the completeness gate's own distinction survives to the report.

    `gr_run.not_accounted_for` is nullable and NULL means coverage was never
    measured; zero means it was measured and nothing was left over.
    `complete` is a GENERATED column deriving from exactly that distinction,
    so printing `0` for NULL would put an unmeasured run on the confident
    side of the gate in the report even though the column has it right.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_runs(store)
    finally:
        store.close()

    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    runs = {r["run_id"]: r for r in payload["runs"]}
    assert runs["RUN-UNMEASURED"]["not_accounted_for"] is None
    assert runs["RUN-UNMEASURED"]["complete"] is False
    assert runs["RUN-MEASURED"]["not_accounted_for"] == 0
    assert runs["RUN-MEASURED"]["complete"] is True

    text = cli(runner, root, analysis, "stats").stdout
    assert "not_accounted_for=unmeasured" in text
    assert "not_accounted_for=0" in text


def test_stats_reports_the_intra_run_collapse_count_per_run(runner, repo):
    """Proves Step 10's mandatory measurement is reported per run, not summed.

    Two offered rules landing on one `gr_id` inside one run is the
    extractor's own in-run dedupe missing a same-lines pair; a corpus-wide
    total would make it impossible to say which extraction was affected.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_runs(store)
    finally:
        store.close()
    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    runs = {r["run_id"]: r for r in payload["runs"]}
    # Two, not one: the figure counts *offers* that lost their own row, not
    # the `gr_id`s they collapsed onto -- the question is how many mined rules
    # stopped existing separately.
    assert runs["RUN-MEASURED"]["intra_run_collapse"] == 2
    assert runs["RUN-UNMEASURED"]["intra_run_collapse"] == 0


def test_stats_surfaces_the_stored_run_figures_and_does_not_recompute_them(
    runner, repo
):
    """Proves `stats` reads `gr_run`'s columns rather than re-deriving them.

    The fixture's `RUN-MEASURED` claims `rules_in = 7` while the store holds
    one requirement. A `stats` that recounted from the rules would report 1
    -- and two answers to one question is exactly what the plan says twice
    not to build, because `IngestResult` already carried the figure.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        seed_runs(store)
    finally:
        store.close()
    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    runs = {r["run_id"]: r for r in payload["runs"]}
    assert payload["requirements"] == 1
    assert runs["RUN-MEASURED"]["rules_in"] == 7
    assert runs["RUN-MEASURED"]["rules_new"] == 5


def test_stats_reports_the_all_citations_excluded_count_as_its_own_figure(
    runner, repo
):
    """Proves Step 3's figure is not folded into `derived_ambiguous`.

    A requirement all of whose citations land on the `excluded` domain means
    the corpus holds rules mined from code the analyst has since declared out
    of scope. That is a different fact from "no domain held a majority", even
    though both land in the same provenance bucket -- so it is counted
    separately or it is invisible.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        conn = store._connect()
        excluded = insert_gr(conn, gr_id="GR-A00000000000000000000X01",
                             subject_provenance="derived_ambiguous")
        mixed = insert_gr(conn, gr_id="GR-A00000000000000000000X02",
                          subject_provenance="derived_ambiguous")
        insert_citation(conn, excluded, relative_path="gen/Stub.java")
        insert_citation(conn, mixed, relative_path="gen/Stub.java")
        insert_citation(conn, mixed, relative_path="src/Order.java")
        store.upsert_file_domain("gen/Stub.java", "excluded", "glob", None, 1.0)
        store.upsert_file_domain("src/Order.java", "ordering", "glob", None, 1.0)
        store.commit()
    finally:
        store.close()
    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    assert payload["all_citations_excluded"] == 1
    provenance = {
        r["value"]: r["count"] for r in payload["counts"]["subject_provenance"]
    }
    assert provenance["derived_ambiguous"] == 2, (
        "the excluded figure is reported BESIDE the provenance bucket, not "
        "carved out of it"
    )


def test_stats_says_whether_the_v_sty_03_symbol_half_was_available(runner, repo):
    """Proves "no leakage found" cannot be confused with "never looked for".

    `RefreshResult.leaked_terms_available` is False when no index was
    reachable, under which `V-STY-03` ran on its morphological fallback
    alone. `stats`' route to that fact is whether the index exists, and both
    branches are asserted so the message is a real branch rather than a
    constant.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        insert_gr(store._connect(), gr_id="GR-A00000000000000000000V01")
    finally:
        store.close()
    paths = paths_for(root, analysis)

    without = cli(runner, root, analysis, "stats", "--json")
    assert json.loads(without.stdout)["v_sty_03_symbol_half"]["available"] is False
    assert "NOT available" in cli(runner, root, analysis, "stats").stdout

    paths.index_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(paths.index_sqlite_path).close()
    with_index = cli(runner, root, analysis, "stats", "--json")
    assert json.loads(with_index.stdout)["v_sty_03_symbol_half"]["available"] is True
    text = cli(runner, root, analysis, "stats").stdout
    assert "V-STY-03 symbol half:" in text
    assert "NOT available" not in text


def test_stats_reports_an_unmeasurable_vector_count_as_unmeasured_not_zero(
    runner, repo
):
    """Proves a count nobody could take is not reported as a count of zero.

    A collection directory that exists but no embedder to open it with means
    the vector half was **not looked at**. Reporting `0 of N` there would
    invent the worst number in the report and send someone to rebuild a
    collection that may be perfectly populated.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        insert_gr(store._connect(), gr_id="GR-A00000000000000000000W01")
    finally:
        store.close()
    (paths_for(root, analysis).knowledge_dir / "chroma").mkdir(
        parents=True, exist_ok=True
    )
    result = cli(
        runner, root, analysis, "stats", "--json",
        "--embedding-provider", "not-a-provider",
    )
    assert result.exit_code == 0, result.output
    vectors = json.loads(result.stdout)["vectors"]
    assert vectors["collection_count"] is None
    assert vectors["shortfall"] is None
    assert "reindex-vectors" in vectors["unmeasured_reason"]

    text = cli(
        runner, root, analysis, "stats", "--embedding-provider", "not-a-provider"
    ).stdout
    assert "count is unmeasured" in text
    assert "NOT a count of zero" in text


def test_stats_makes_a_degraded_vector_collection_visible(runner, repo):
    """Proves the shortfall is reported here, not only where it was caused.

    A collection that lags `gr` answers a near-duplicate query with zero
    candidates, which is indistinguishable from there being no near
    duplicates -- so the degraded state has to be visible in the standing
    report and not only in the output of the command that degraded it.
    """
    root, analysis = repo
    store = open_store(root, analysis)
    try:
        ids = seed_for_search(store)
        embed(store, ids[:1])
    finally:
        store.close()
    result = cli(
        runner, root, analysis, "stats", "--embedding-provider", "hash"
    )
    assert result.exit_code == 0, result.output
    assert "holds 1 of 2 requirement" in result.stdout
    assert "reindex-vectors" in result.stdout

    payload = json.loads(
        cli(
            runner, root, analysis, "stats", "--json",
            "--embedding-provider", "hash",
        ).stdout
    )
    assert payload["vectors"]["collection_count"] == 1
    assert payload["vectors"]["gr_count"] == 2
    assert "reindex-vectors" in payload["vectors"]["shortfall"]


def test_stats_on_an_empty_store_reports_no_rate_over_an_empty_set(runner, repo):
    """Proves an empty corpus never yields a division by zero or a false 100%.

    Every rate in this command has a denominator that is a row count, so an
    empty store is the case where a naive implementation either raises or
    reports perfection.
    """
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "stats")
    assert result.exit_code == 0, result.output
    assert "requirements: 0" in result.stdout
    assert "(n/a)" in result.stdout
    assert "100%" not in result.stdout

    payload = json.loads(cli(runner, root, analysis, "stats", "--json").stdout)
    assert payload["review_progress"]["owner"]["rate"] == "0/0 (n/a)"


def test_stats_json_stdout_is_pure_and_the_banner_is_on_stderr(runner, repo):
    """Proves house rule 4 for the largest of the four payloads."""
    root, analysis = repo
    open_store(root, analysis).close()
    result = cli(runner, root, analysis, "stats", "--json")
    assert json.loads(result.stdout)["requirements"] == 0
    assert "resolved knowledge directory" in result.stderr
    assert "resolved" not in result.stdout
