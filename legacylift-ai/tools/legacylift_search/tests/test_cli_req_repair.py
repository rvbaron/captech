"""Tests for the four repair/transport `requirements` commands.

Milestone 1, Steps 8 and 9 of `docs/exec-plans/active/reqs-to-data-store.md`:
`reindex-vectors`, `rederive-subjects`, `export` and `import`, exercised
**through the real registration** (`CliRunner` against
`legacylift_search.cli:app` with `["requirements", "<cmd>", ...]`), so a
command that failed to register fails these tests rather than passing them
against a sub-app nobody wired up.

Every test here is a probe. It reads the `gr` rows back, or the bytes of the
exported file, or the exit code, or what the command printed -- never the
source of the command. This plan's history is nine review rounds in which a
green suite hid a live defect twice, and both times the passing test asserted
something about the code rather than about what the code did. The one
exception is `test_the_import_help_repeats_the_four_guardrails_verbatim`,
which is an *equality* assertion between two constants and is the mechanism
that keeps the help text honest -- see that test's docstring.

Two conventions, stated once. **The human-readable report goes to stdout and
the diagnostics go to stderr**, so a test asserting on a degradation reads
`result.stderr` and a test asserting on JSON reads `result.stdout`; click
8.4's `CliRunner` keeps the two apart. And a bare `--repo-root` with no
manifest resolves the knowledge store to
`<repo>/legacylift-docs/knowledge/knowledge.sqlite`, which `knowledge_path`
below is the single spelling of.
"""

from __future__ import annotations

import json
import sqlite3

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.cli_requirements.repair_cmds import (
    _IMPORT_GUARDRAILS,
    _IMPORT_HELP,
    REQUIREMENTS_JSONL_NAME,
)
from legacylift_search.gr_export import (
    IMPORT_GUARDRAILS,
    REASON_COVERAGE_NEVER_MEASURED,
)
from legacylift_search.gr_refresh import GR_COLLECTION_NAME, open_gr_collection
from legacylift_search.knowledge_store import KnowledgeStore
from tests.test_gr_state import insert_gr

#: A statement whose `[Subject]` span `split_slots` can locate under
#: `behavioral` / `B-UNCOND`, so the subject fallback has something to read.
#: Verified by probe below rather than by reading the template.
STATEMENT = "The Order Service must record a vendor number on each order."

SECOND_ID = "GR-01HQ2X0000000000000000009"
THIRD_ID = "GR-01HQ2X000000000000000000A"


# --------------------------------------------------------------------------
# Fixtures and helpers
# --------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """A repository root with no knowledge store yet. `--repo-root` takes it."""
    root = tmp_path / "repo"
    root.mkdir()
    return root


def knowledge_path(repo):
    """Where `resolve_knowledge_dir` puts the store for a bare repo root."""
    return repo / "legacylift-docs" / "knowledge" / "knowledge.sqlite"


def export_path(repo):
    """The canonical export path -- a sibling of `knowledge.sqlite`."""
    return knowledge_path(repo).parent / REQUIREMENTS_JSONL_NAME


def open_store(repo):
    """Open (creating if needed) the store the CLI will resolve to."""
    return KnowledgeStore(knowledge_path(repo))


def seed(repo, *, rows=1, **overrides):
    """Create the store and `rows` `gr` rows; return their ids in order."""
    ids = [None, SECOND_ID, THIRD_ID]
    store = open_store(repo)
    try:
        created = []
        for n in range(rows):
            row = {"statement": STATEMENT, "enforcement_level": "strict"}
            if ids[n] is not None:
                row["gr_id"] = ids[n]
            row.update(overrides)
            created.append(insert_gr(store._connect(), **row))
        return created
    finally:
        store.close()


def insert_citation(conn: sqlite3.Connection, gr_id: str, path: str) -> None:
    """One `gr_citation` row, which is what the subject derivation reads."""
    conn.execute(
        "INSERT INTO gr_citation (gr_id, anchor_key, anchor_resolution, "
        "relative_path, start_line, end_line, content_hash, verified_at, "
        "provenance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (gr_id, f"file:{path}", "file", path, 1, 5, "abc123", None, "extracted"),
    )
    conn.commit()


def insert_run(conn: sqlite3.Connection, run_id: str, **overrides) -> None:
    """A `gr_run` row. Default `not_accounted_for = NULL` -- never measured."""
    row = {
        "run_id": run_id,
        "not_accounted_for": None,
        "gate_excluded": 0,
        "gate_excluded_reason": None,
    }
    row.update(overrides)
    conn.execute(
        "INSERT INTO gr_run (run_id, not_accounted_for, gate_excluded, "
        "gate_excluded_reason) VALUES (?, ?, ?, ?)",
        tuple(row.values()),
    )
    conn.commit()


def insert_hit(conn: sqlite3.Connection, gr_id: str, run_id: str) -> None:
    """A `gr_run_hit` row -- what scopes a blocking run to this export."""
    conn.execute(
        "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) "
        "VALUES (?, ?, ?, ?)",
        (gr_id, run_id, 0, "new"),
    )
    conn.commit()


def run(repo, *args, provider="nope"):
    """Invoke a `requirements` subcommand against `repo`.

    `provider="nope"` is the default because an unbuildable provider is the
    fast path *and* the interesting one for most of these tests: the
    degraded-but-zero-exit contract is what they are about. A test that
    needs a real collection passes `provider="hash"`; a test of a command
    that takes no `--embedding-provider` -- `export` alone -- passes
    `provider=None`.

    **`import` used to be in that second group and no longer is** (2026-09-02):
    it gained the flag when `import_records` gained an `embedder` parameter, so
    passing `provider=None` for it now falls through to the manifest default of
    `qwen3` and performs a real model load and an HF Hub request. Measured at
    the time: ~35s and a network dependency added to this file, and one test
    inverted outright, because the embed then *succeeds* and the
    degraded-path assertion has nothing to find.
    """
    argv = list(args) + ["--repo-root", str(repo)]
    if provider is not None:
        argv += ["--embedding-provider", provider]
    return CliRunner().invoke(app, ["requirements"] + argv)


def collection_ids(repo):
    """Every id in `gr_statements`, read through a hash embedder."""
    from legacylift_search.config import Manifest
    from legacylift_search.embeddings import HashEmbedder

    store = open_store(repo)
    collection = None
    try:
        # The manifest default, not a literal 64: the CLI's `hash` provider is
        # built at `manifest.embedding.dimension`, and Chroma fixes a
        # collection's dimension at creation. A 64 here is harmless only while
        # this helper never creates or queries -- one call-ordering change away
        # from creating a 64-dim collection the next command's embedder then
        # fails `validate_dimension` against, which reports as a dimension
        # mismatch while the test claims to measure something else.
        collection = open_gr_collection(
            store, HashEmbedder(dimension=Manifest().embedding.dimension)
        )
        return sorted(collection.collection.get(include=[])["ids"])
    finally:
        if collection is not None:
            collection.close()
        store.close()


# --------------------------------------------------------------------------
# reindex-vectors
# --------------------------------------------------------------------------


def test_reindex_vectors_populates_the_collection_and_says_there_is_no_shortfall(
    repo,
):
    """Proves the recovery actually runs and reports its own success.

    After a successful reindex there is no shortfall, and the command says so
    rather than printing nothing: silence after a repair is indistinguishable
    from a repair that never ran, which is the same absent-versus-real defect
    the shortfall check exists to catch one layer out.
    """
    ids = seed(repo, rows=2)
    result = run(repo, "reindex-vectors", provider="hash")
    assert result.exit_code == 0, result.stderr
    assert "No shortfall" in result.stdout
    assert collection_ids(repo) == sorted(ids)


def test_reindex_vectors_is_safe_to_run_twice(repo):
    """Proves the resumable-repair shape: the second run is not destructive."""
    ids = seed(repo, rows=2)
    first = run(repo, "reindex-vectors", "--json", provider="hash")
    second = run(repo, "reindex-vectors", "--json", provider="hash")
    assert first.exit_code == 0 and second.exit_code == 0, second.stderr
    a = json.loads(first.stdout)
    b = json.loads(second.stdout)
    assert a["embedded"] == b["embedded"] == 2
    assert b["collection_count_after"] == 2
    assert b["shortfall_after"] is None
    assert collection_ids(repo) == sorted(ids)


def test_reindex_vectors_sweeps_the_vector_of_a_deleted_requirement(repo):
    """Proves the orphan sweep: a stale collection keeps no searchable ghost.

    `refresh_gr_vectors` only deletes among the ids it is *given*, so a
    requirement deleted while the collection was stale would otherwise keep
    its vector forever. A recovery path has to distrust the collection.
    """
    ids = seed(repo, rows=2)
    run(repo, "reindex-vectors", provider="hash")
    assert len(collection_ids(repo)) == 2

    store = open_store(repo)
    try:
        store._connect().execute("DELETE FROM gr WHERE gr_id = ?", (ids[1],))
        store.commit()
    finally:
        store.close()

    result = run(repo, "reindex-vectors", "--json", provider="hash")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["deleted"] >= 1
    assert collection_ids(repo) == [ids[0]]


def test_reindex_vectors_exits_zero_with_no_provider_and_says_it_could_not_look(
    repo,
):
    """Proves a degraded recovery is a zero exit, and an honest one.

    An unreachable provider must not read as data loss -- the requirements
    are untouched and keyword search works. And the shortfall must come back
    as NOT MEASURED rather than as zero: with no embedder the collection
    cannot even be opened, so "every requirement has a vector" is not
    something this run is in a position to claim.
    """
    seed(repo, rows=2)
    result = run(repo, "reindex-vectors", "--json", provider="not-a-provider")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["collection_count_after"] is None
    assert payload["shortfall_measured"] is False
    assert payload["reason"] is not None
    assert "reindex-vectors" in payload["reason"]
    assert "NOT MEASURED" in result.stderr


def test_reindex_vectors_on_an_empty_store_is_a_rebuild_of_nothing(repo):
    """Proves an empty store is a success, not an error.

    `reindex_gr_vectors` returns all-zero with no reason on an empty store,
    and the command must say "0 requirements" rather than treating it as a
    failure -- a fresh store is the ordinary state before the first ingest.
    """
    open_store(repo).close()
    result = run(repo, "reindex-vectors", "--json", provider="hash")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["gr_count"] == 0
    assert payload["embedded"] == 0
    assert payload["reason"] is None


def test_reindex_vectors_refuses_to_create_the_database(repo):
    """Proves house rule 2: a read path probes before it constructs.

    `KnowledgeStore.__init__` creates the file *and its parent*, so a missing
    probe would leave an empty store that answers every later command with
    "no requirements" indistinguishably from a real one.
    """
    result = run(repo, "reindex-vectors", provider="hash")
    assert result.exit_code == 1
    assert not knowledge_path(repo).exists()


# --------------------------------------------------------------------------
# rederive-subjects
# --------------------------------------------------------------------------


def seed_for_rederive(repo, *, path, domain, subject, provenance):
    """One requirement citing `path`, with `path` tagged `domain`.

    The stored `subject`/`subject_provenance` are set to what an *earlier*
    domain set yielded, which is exactly the staleness this command exists
    to find: nothing else re-derives them and nothing reports it.
    """
    store = open_store(repo)
    try:
        gr_id = insert_gr(
            store._connect(),
            statement=STATEMENT,
            enforcement_level="strict",
            subject=subject,
            subject_provenance=provenance,
        )
        insert_citation(store._connect(), gr_id, path)
        store.upsert_file_domain(path, domain, "glob", None, 1.0)
        return gr_id
    finally:
        store.close()


def read_row(repo, gr_id):
    store = open_store(repo)
    try:
        return store.get_gr(gr_id)
    finally:
        store.close()


def test_rederive_reports_llm_named_to_derived_after_a_retag(repo):
    """Proves the case this command exists for, end to end.

    A file that was `unassigned` at ingest and has since been tagged should
    stop being model-named, and without this command it never does. The
    figure is reported separately because nothing else in the system will
    ever surface it.
    """
    gr_id = seed_for_rederive(
        repo,
        path="src/foo.py",
        domain="Ordering",
        subject="The Order Service",
        provenance="llm_named",
    )
    result = run(repo, "rederive-subjects", "--json")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["examined"] == 1
    assert payload["changed"] == 1
    assert payload["llm_named_to_derived"] == 1
    assert payload["derived_to_derived_ambiguous"] == 0
    assert {"from": "llm_named", "to": "derived", "count": 1} in payload[
        "provenance_transitions"
    ]

    row = read_row(repo, gr_id)
    assert row.subject == "Ordering"
    assert row.subject_provenance == "derived"


def test_rederive_reports_the_reverse_direction_for_a_newly_excluded_file(repo):
    """Proves the opposite direction is its own figure, and why that matters.

    `derived -> derived_ambiguous` is what a newly **excluded** file
    produces, and it means the corpus now holds rules mined from code the
    analyst has since declared out of scope. Since the plan's Concrete Steps
    tell an implementer to check the `derived` rate before believing the
    derivation works at all, a rate that can only fall as a corpus ages must
    be attributed rather than merely observed.
    """
    gr_id = seed_for_rederive(
        repo,
        path="src/legacy/bar.py",
        domain="excluded",
        subject="Ordering",
        provenance="derived",
    )
    result = run(repo, "rederive-subjects", "--json")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["derived_to_derived_ambiguous"] == 1
    assert payload["llm_named_to_derived"] == 0

    row = read_row(repo, gr_id)
    assert row.subject_provenance == "derived_ambiguous"

    # And the human-readable half names the meaning, not just the number.
    text = run(repo, "rederive-subjects").stdout
    assert "derived -> derived_ambiguous" in text


def test_rederive_reports_a_renamed_domain_as_a_subject_only_change(repo):
    """Proves the third bucket exists, so `changed` always reconciles.

    A retag that renames a domain moves the subject and leaves the
    provenance alone. Without its own figure those rows land in `changed`
    and in no transition bucket, which reads like a bookkeeping error.
    """
    seed_for_rederive(
        repo,
        path="src/foo.py",
        domain="Order Management",
        subject="Ordering",
        provenance="derived",
    )
    payload = json.loads(run(repo, "rederive-subjects", "--json").stdout)
    assert payload["changed"] == 1
    assert payload["subject_only_changes"] == 1
    assert payload["llm_named_to_derived"] == 0
    assert payload["derived_to_derived_ambiguous"] == 0
    assert payload["provenance_transitions"] == []


def test_rederive_moves_subjects_without_moving_keys_or_statements(repo):
    """Proves the invariant the plan calls "the assertion that matters".

    Both dedupe keys, every citation `anchor_key` and every `statement` are
    byte-identical before and after -- edited or not, because the command
    does not touch `statement` at all. This is the same invariant as the
    domain-retag test one layer up, and it fails loudly the moment someone
    wires key recomputation or statement re-templating into this command.
    """
    gr_id = seed_for_rederive(
        repo,
        path="src/foo.py",
        domain="Ordering",
        subject="The Order Service",
        provenance="llm_named",
    )

    def snapshot():
        store = open_store(repo)
        try:
            row = store.get_gr(gr_id)
            return (
                row.dedupe_key,
                row.dedupe_key_anchor_only,
                row.statement,
                [c.anchor_key for c in store.list_gr_citations(gr_id)],
            )
        finally:
            store.close()

    before = snapshot()
    result = run(repo, "rederive-subjects", "--json")
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["changed"] == 1
    after = snapshot()
    assert before == after
    # The subject really did move, so the invariance above is not vacuous.
    assert read_row(repo, gr_id).subject == "Ordering"


def test_rederive_a_second_time_changes_nothing_and_says_so(repo):
    """Proves the repair shape: safe to run twice, and a positive report.

    "0 changed, 1 skipped" on a second run is a confirmation that the
    derivation is current. An unreported zero is an ambiguous silence.
    """
    seed_for_rederive(
        repo,
        path="src/foo.py",
        domain="Ordering",
        subject="The Order Service",
        provenance="llm_named",
    )
    run(repo, "rederive-subjects")
    second = run(repo, "rederive-subjects")
    assert second.exit_code == 0, second.stderr
    payload = json.loads(run(repo, "rederive-subjects", "--json").stdout)
    assert payload["changed"] == 0
    assert payload["skipped"] == 1
    assert "0 changed, 1 skipped" in second.stdout


def test_rederive_json_keeps_an_absent_old_provenance_as_null(repo):
    """Proves a NULL old provenance is not folded into the string "None".

    `provenance_transitions` is keyed by a tuple in Python, and the obvious
    JSON encoding -- stringify the key -- turns a row that predates the
    derivation into the literal `"None"`, sharing an encoding with a real
    value. A list of objects keeps the null a null.
    """
    store = open_store(repo)
    try:
        gr_id = insert_gr(
            store._connect(),
            statement=STATEMENT,
            enforcement_level="strict",
            subject=None,
            subject_provenance=None,
        )
        insert_citation(store._connect(), gr_id, "src/foo.py")
        store.upsert_file_domain("src/foo.py", "Ordering", "glob", None, 1.0)
    finally:
        store.close()

    payload = json.loads(run(repo, "rederive-subjects", "--json").stdout)
    assert payload["provenance_transitions"] == [
        {"from": None, "to": "derived", "count": 1}
    ]
    assert payload["changes"][0]["old_provenance"] is None


def test_rederive_restricted_to_one_gr_id_leaves_the_others_alone(repo):
    """Proves `--gr-id` is honoured, so a targeted repair stays targeted."""
    first = seed_for_rederive(
        repo,
        path="src/foo.py",
        domain="Ordering",
        subject="The Order Service",
        provenance="llm_named",
    )
    store = open_store(repo)
    try:
        second = insert_gr(
            store._connect(),
            gr_id=SECOND_ID,
            statement=STATEMENT,
            enforcement_level="strict",
            subject="The Order Service",
            subject_provenance="llm_named",
        )
        insert_citation(store._connect(), second, "src/bar.py")
        store.upsert_file_domain("src/bar.py", "Billing", "glob", None, 1.0)
    finally:
        store.close()

    payload = json.loads(
        run(repo, "rederive-subjects", "--gr-id", first, "--json").stdout
    )
    assert payload["examined"] == 1
    assert payload["changed"] == 1
    assert read_row(repo, first).subject == "Ordering"
    assert read_row(repo, second).subject_provenance == "llm_named"


def test_rederive_refuses_to_create_the_database(repo):
    """Proves the read-path probe on the second repair command too."""
    result = run(repo, "rederive-subjects")
    assert result.exit_code == 1
    assert not knowledge_path(repo).exists()


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------


def test_export_writes_the_sibling_of_knowledge_sqlite(repo):
    """Proves the default output path is the diffable mirror's home.

    `<analysis>/knowledge/requirements.jsonl`, deliberately a sibling of
    `knowledge.sqlite`, so the relationship between the authoritative store
    and its export is obvious from a directory listing.
    """
    ids = seed(repo, rows=2)
    result = run(repo, "export", provider=None)
    assert result.exit_code == 0, result.stderr
    assert export_path(repo).exists()
    lines = export_path(repo).read_bytes().splitlines()
    assert [json.loads(line)["gr_id"] for line in lines] == sorted(ids)


def test_export_is_byte_identical_on_a_second_run(repo):
    """Proves the determinism rule: nothing that varies reaches the file.

    No export timestamp, no run counter, no tool version. This is the
    criterion a helpful provenance header silently breaks.
    """
    seed(repo, rows=2)
    assert run(repo, "export", provider=None).exit_code == 0
    first = export_path(repo).read_bytes()
    assert run(repo, "export", provider=None).exit_code == 0
    assert export_path(repo).read_bytes() == first


def test_export_uses_newline_endings_and_sorted_keys(repo):
    """Proves the file is diffable in a pull request on any host.

    `\\n` regardless of host, and keys sorted within each object, so a single
    reworded statement is a one-line diff rather than a whole-file rewrite.
    """
    seed(repo, rows=1)
    run(repo, "export", provider=None)
    raw = export_path(repo).read_bytes()
    assert b"\r\n" not in raw
    keys = list(json.loads(raw.splitlines()[0]).keys())
    assert keys == sorted(keys)


def seed_incomplete(repo, *, rows=1):
    """Seed `rows` requirements attributed to a run that was never measured.

    `not_accounted_for IS NULL` is the "coverage never measured" half of the
    gate -- NULL means nobody looked, which is a different fact from zero
    and calls for a different action.
    """
    ids = seed(repo, rows=rows)
    store = open_store(repo)
    try:
        insert_run(store._connect(), "RUN-01HQ2X000000000000000000")
        for gr_id in ids:
            insert_hit(store._connect(), gr_id, "RUN-01HQ2X000000000000000000")
    finally:
        store.close()
    return ids


def test_export_refuses_an_incomplete_corpus_without_the_flag(repo):
    """Proves the completeness gate is enforced at the point of departure.

    The export is what leaves the machine and reaches a client, and an
    incomplete corpus presented as complete is the specific failure the gate
    exists to prevent. A refusal is a non-zero exit, a clean message naming
    the offending run and its reason in words, and **no file**.
    """
    seed_incomplete(repo)
    result = run(repo, "export", provider=None)
    assert result.exit_code == 1
    assert "RUN-01HQ2X000000000000000000" in result.stderr
    assert "--allow-incomplete" in result.stderr
    assert REASON_COVERAGE_NEVER_MEASURED in result.stderr
    assert not export_path(repo).exists()


def test_allow_incomplete_is_deterministic_and_names_the_runs_in_words(repo):
    """Proves the ninth-round acceptance criterion, all three parts.

    Two exports of an incomplete corpus **with** the flag are byte-identical;
    both open with an `_incomplete` object naming the offending `run_id`s and
    their reason in words; and the same store **without** the flag is
    refused. The determinism is what the header's lack of a timestamp,
    counter or tool version buys.
    """
    seed_incomplete(repo, rows=2)

    assert run(repo, "export", "--allow-incomplete", provider=None).exit_code == 0
    first = export_path(repo).read_bytes()
    assert run(repo, "export", "--allow-incomplete", provider=None).exit_code == 0
    assert export_path(repo).read_bytes() == first

    header = json.loads(first.splitlines()[0])
    assert list(header) == ["_incomplete"]
    assert list(header["_incomplete"]) == ["RUN-01HQ2X000000000000000000"]
    assert (
        header["_incomplete"]["RUN-01HQ2X000000000000000000"]
        == REASON_COVERAGE_NEVER_MEASURED
    )

    # Without the flag: refused, and the good file is left as it was.
    refused = run(repo, "export", provider=None)
    assert refused.exit_code == 1
    assert export_path(repo).read_bytes() == first


def test_the_incomplete_header_carries_no_timestamp_counter_or_tool_version(repo):
    """Proves what makes the byte-identity above possible rather than lucky.

    The header is exactly one reserved key mapping run ids to reason
    sentences. Anything a second run could change -- a stamp, a count, a
    version -- would break the criterion in a way a single export cannot
    reveal, so the shape is asserted directly.
    """
    seed_incomplete(repo)
    run(repo, "export", "--allow-incomplete", provider=None)
    header = json.loads(export_path(repo).read_bytes().splitlines()[0])
    assert set(header) == {"_incomplete"}
    assert all(isinstance(v, str) for v in header["_incomplete"].values())


def test_export_without_the_flag_writes_no_header_line_at_all(repo):
    """Proves the header is the flag's doing, not a permanent fixture."""
    seed(repo, rows=1)
    run(repo, "export", provider=None)
    lines = export_path(repo).read_bytes().splitlines()
    assert len(lines) == 1
    assert "_incomplete" not in json.loads(lines[0])


def test_export_honours_an_explicit_output_path(repo, tmp_path):
    """Proves `--output` is wired, so an export can go to a review branch."""
    seed(repo, rows=1)
    target = tmp_path / "elsewhere" / "reqs.jsonl"
    result = run(repo, "export", "--output", str(target), provider=None)
    assert result.exit_code == 0, result.stderr
    assert target.exists()
    assert not export_path(repo).exists()


def test_export_refuses_an_unknown_format(repo):
    """Proves `--format` is validated rather than ignored.

    Silently writing JSONL for `--format csv` would hand a caller a file in
    a format it did not ask for and cannot parse.
    """
    seed(repo, rows=1)
    result = run(repo, "export", "--format", "csv", provider=None)
    assert result.exit_code != 0
    assert "jsonl" in result.stderr
    assert not export_path(repo).exists()


def test_export_json_mode_keeps_stdout_parseable(repo):
    """Proves the banner and the report do not corrupt `--json` on stdout."""
    seed(repo, rows=2)
    result = run(repo, "export", "--json", provider=None)
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["requirement_count"] == 2
    assert payload["incomplete_header_written"] is False
    assert "resolved knowledge directory" in result.stderr


def test_export_refuses_to_create_the_database(repo):
    """Proves the read-path probe on `export` too."""
    result = run(repo, "export", provider=None)
    assert result.exit_code == 1
    assert not knowledge_path(repo).exists()


# --------------------------------------------------------------------------
# import
# --------------------------------------------------------------------------


def test_import_round_trips_an_incomplete_header_without_creating_a_record(repo):
    """Proves the other half of the ninth-round criterion.

    A leading `_incomplete` object is skipped rather than treated as a
    record, so importing a file written under `--allow-incomplete` restores
    the requirements and creates nothing from the header.
    """
    ids = seed_incomplete(repo, rows=2)
    run(repo, "export", "--allow-incomplete", provider=None)
    assert "_incomplete" in json.loads(
        export_path(repo).read_bytes().splitlines()[0]
    )

    result = run(repo, "import", "--json")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["rows_read"] == 2
    assert payload["gr_ids_touched"] == 2

    store = open_store(repo)
    try:
        assert sorted(store.all_gr_ids()) == sorted(ids)
        assert store.count_gr() == 2
    finally:
        store.close()


def test_import_says_the_vector_half_was_not_populated_and_exits_zero(repo):
    """Proves a degraded vector half is stated in words, not implied.

    **Rewritten 2026-09-02.** It used to assert that the degradation was
    *unconditional*, on the true premise that "`import_records` takes no
    embedder, so nothing it restores can reach the `gr_statements` collection
    whatever the provider configuration says". That premise is gone:
    `import_records` now takes an `embedder` and `import` takes
    `--embedding-provider`, so the vector half degrades only when no embedder
    can be built -- which is what `run`'s default `provider="nope"` produces
    here. The contract under test is unchanged and is the part that always
    mattered: the command says so in words, names `reindex-vectors` as the
    recovery, and exits zero, because a non-zero exit reads as "the import
    failed" and invites a re-run that changes nothing.
    """
    seed(repo, rows=1)
    run(repo, "export", provider=None)
    result = run(repo, "import", "--json")
    assert result.exit_code == 0, result.stderr
    assert "reindex-vectors" in result.stderr
    assert json.loads(result.stdout)["vectors_populated"] is False


def test_import_refuses_a_state_downgrade_by_default(repo):
    """Proves the guard rail that protects a human's approval.

    A stale checkout's most likely damage is un-approving work, so an
    import that would lower a state leaves the review columns alone unless
    `--allow-downgrade` is passed. The approval is recorded through the real
    `set_state` path, and the assertion reads `gr.state` back rather than
    reading the ranking.
    """
    from legacylift_search.gr_state import set_state

    (gr_id,) = seed(repo, rows=1, state="draft")
    run(repo, "export", provider=None)  # a file carrying state='draft'

    store = open_store(repo)
    try:
        set_state(store, gr_id, "approved", "A. Analyst")
    finally:
        store.close()
    assert read_row(repo, gr_id).state == "approved"

    result = run(repo, "import")
    assert result.exit_code == 0, result.stderr
    assert read_row(repo, gr_id).state == "approved", "the downgrade was applied"

    allowed = run(repo, "import", "--allow-downgrade")
    assert allowed.exit_code == 0, allowed.stderr
    assert read_row(repo, gr_id).state == "draft"


def test_import_may_create_the_database_but_a_missing_file_does_not(repo, tmp_path):
    """Proves both halves of `import`'s create permission.

    `import` is one of only two commands allowed to create the store --
    restoring into a fresh checkout is a legitimate use. But a typo'd
    `--from-jsonl` must not leave an empty knowledge store behind as the
    side effect of a failure, because an empty store is indistinguishable
    from a real one on the next command. So the file is probed first.
    """
    missing = run(repo, "import", "--from-jsonl", str(tmp_path / "nope.jsonl"))
    assert missing.exit_code == 1
    assert not knowledge_path(repo).exists()

    # Now produce a real export from a different repo and restore it here.
    source = tmp_path / "source"
    source.mkdir()
    ids = seed(source, rows=2)
    run(source, "export", provider=None)

    restored = run(repo, "import", "--from-jsonl", str(export_path(source)))
    assert restored.exit_code == 0, restored.stderr
    assert knowledge_path(repo).exists()
    store = open_store(repo)
    try:
        assert sorted(store.all_gr_ids()) == sorted(ids)
    finally:
        store.close()


def test_import_is_idempotent_and_the_re_export_is_byte_identical(repo):
    """Proves export/import/export is a fixed point, not a slow rewrite.

    Step 6's value-changing-write rule is what makes this hold: a write that
    changes no value must not bump `updated_at`, or every record would show
    as modified in the diff after any round trip -- which is the same as
    showing nothing.
    """
    seed(repo, rows=2)
    run(repo, "export", provider=None)
    original = export_path(repo).read_bytes()
    assert run(repo, "import").exit_code == 0
    assert run(repo, "export", provider=None).exit_code == 0
    assert export_path(repo).read_bytes() == original


def test_import_reports_a_broken_file_without_writing_anything(repo):
    """Proves a malformed export is a clean failure, not a partial restore."""
    seed(repo, rows=1)
    run(repo, "export", provider=None)
    export_path(repo).write_bytes(b'{"gr_id": "GR-broken", not json\n')
    result = run(repo, "import")
    assert result.exit_code == 1
    assert "nothing was written" in result.stderr
    store = open_store(repo)
    try:
        assert store.count_gr() == 1
    finally:
        store.close()


# --------------------------------------------------------------------------
# The help text
# --------------------------------------------------------------------------


def test_the_import_help_repeats_the_four_guardrails_verbatim():
    """Proves `--help` and `gr_export` cannot drift apart.

    Step 9 requires the CLI help text to *repeat* the four guard rails
    rather than re-describe them. Typer needs help text at decoration time,
    so importing `gr_export.IMPORT_GUARDRAILS` at module scope would pull
    pydantic and the models into every `legacylift-search --help`; the
    module keeps a verbatim tuple instead. This equality assertion is what
    makes that copy safe -- it is strictly stronger than the substring check
    a paraphrase would permit, and it is the reason the copy is a tuple
    rather than prose in a docstring.
    """
    assert _IMPORT_GUARDRAILS == IMPORT_GUARDRAILS
    for rule in IMPORT_GUARDRAILS:
        assert rule in _IMPORT_HELP


def test_the_import_help_states_that_import_never_runs_implicitly():
    """Proves the rendered help says the thing Step 9 asks it to say."""
    result = CliRunner().invoke(app, ["requirements", "import", "--help"])
    assert result.exit_code == 0, result.stderr
    flat = " ".join(result.stdout.split())
    assert "never on open, never implicitly" in flat
    assert "--allow-downgrade" in flat
    assert "reindex-vectors" in flat


def test_the_reindex_help_names_all_four_recovery_situations():
    """Proves Step 5's single documented recovery documents what it recovers.

    A reset, a missing embedder, a failed call and a provider switch. Naming
    them is what stops the command reading as a maintenance chore nobody
    knows when to run.
    """
    result = CliRunner().invoke(app, ["requirements", "reindex-vectors", "--help"])
    assert result.exit_code == 0, result.stderr
    flat = " ".join(result.stdout.split())
    assert "index --reset" in flat
    assert "no embedder configured" in flat
    assert "embedding call that failed" in flat
    assert "switch of embedding provider" in flat


def test_the_export_help_states_that_the_jsonl_is_the_durable_backup():
    """Proves the plain fact reaches the person running the command.

    `knowledge.sqlite` is gitignored, so a copy of it inside the repository
    is not protected by git. This file is what survives.
    """
    result = CliRunner().invoke(app, ["requirements", "export", "--help"])
    assert result.exit_code == 0, result.stderr
    flat = " ".join(result.stdout.split())
    assert "gitignored" in flat
    assert "DURABLE BACKUP" in flat


def test_the_gr_statements_collection_name_is_the_one_the_commands_use():
    """Proves the reindex probe above targets the collection Step 5 names."""
    assert GR_COLLECTION_NAME == "gr_statements"
