"""Tests for the four run-level `requirements` commands (Step 8, Wave C2-RUN).

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. Every
test here fails before this wave with `No such command 'ingest'` (or
`'validate'`, `'set-run-coverage'`, `'retire-run'`) and passes after.

Three things about how these are written, each of which is a deliberate
choice rather than a convenience:

* **They drive the real registration.** `CliRunner` against
  `legacylift_search.cli:app` with `["requirements", "ingest", ...]`, not the
  sub-app in isolation and not the command function called directly, because
  the thing under test includes `app.add_typer`, the `Annotated` option
  aliases and the exit codes -- none of which a direct call exercises.
* **The payload fixtures are imported from `tests/test_gr_ingest.py`** rather
  than rewritten. That module's `rule()` carries every `RULES_SCHEMA` key and
  its `payload()` names the rule array `confirmedRules`, which is what
  `extract-rules.js` really returns; a hand-written fixture spelling it
  `rules` would keep working (ingest accepts both) and would quietly stop
  testing the real shape.
* **stdout and stderr are asserted apart.** click 8.4's `CliRunner` keeps
  them separate (`result.stdout`, `result.stderr`, with `result.output`
  interleaving both), and the whole point of the banner/notice routing is
  that a `--json` caller's stdout stays parseable. A test that read
  `result.output` would pass with every line on the wrong stream.
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
from legacylift_search.gr_validator import CHECK_IDS
from legacylift_search.knowledge_store import KnowledgeStore
from tests.test_gr_ingest import payload, rule
from tests.test_gr_state import insert_gr

#: Chroma's `PersistentClient` keeps its own SQLite files open past `close()`
#: on Windows often enough that the house pattern (`tests/test_vector_store.py`)
#: is to tolerate a failed teardown rather than leak a test failure out of one.
_IS_WINDOWS = sys.platform == "win32"


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def repo(tmp_root):
    """A tiny working tree carrying the two files the fixtures cite.

    Deliberately never indexed: a missing `index.sqlite` is a *supported*
    state for this command group, so it is the default here and the tests
    that need an index build one explicitly.

    A manifest is written pinning the hash embedder at 64 dimensions, because
    `EmbeddingConfig.provider` defaults to `qwen3` and a default manifest
    would have every ingest test try to load a transformer model.
    """
    root = tmp_root / "repo"
    root.mkdir()
    for name in ("Order.java", "Vendor.java"):
        (root / name).write_text(
            "\n".join(f"// {name} line {i}" for i in range(1, 61)), encoding="utf-8"
        )
    (root / "semantic-search.manifest.json").write_text(
        json.dumps({"embedding": {"provider": "hash", "dimension": 64}}),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def analysis(tmp_root):
    """The `--analysis-dir` override. Both stores resolve underneath it."""
    return tmp_root / "analysis"


@pytest.fixture
def runner():
    return CliRunner()


def paths_of(repo: Path, analysis: Path):
    """Resolve the same paths the command resolves, with no banner.

    Tests assert against the *resolved* paths rather than against a guessed
    layout, because the index lives at `<analysis>/index/...` while the
    knowledge store is `<analysis>/knowledge/` -- they are not siblings, and
    a test that hard-coded either would encode a layout the resolver owns.
    """
    return resolve_requirements_paths(repo, None, analysis, print_banner=False)


def two_rules():
    """The two-rule payload the merge criteria are stated against.

    Two rather than one so a merge that collapsed everything onto a single
    requirement would show as a count change rather than as a pass, and the
    second cites a different file so the two carry distinct dedupe keys.
    """
    return payload(rule(), rule(name="Second", source="Vendor.java:5-9"))


def write_payload(tmp_root: Path, body, name: str = "extract.json") -> Path:
    path = tmp_root / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def invoke(runner: CliRunner, *args: str):
    """Invoke the real app. `catch_exceptions=False` so a bug is a traceback."""
    return runner.invoke(app, list(args), catch_exceptions=False)


def ingest_args(repo: Path, analysis: Path, from_path: Path, *extra: str):
    return [
        "requirements",
        "ingest",
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
        "--from",
        str(from_path),
        *extra,
    ]


def table_counts(sqlite_path: Path) -> dict:
    """Row counts at all four grains the headline criterion names, plus runs.

    Read with a plain `sqlite3` connection rather than through
    `KnowledgeStore`, so the assertion cannot be satisfied by a store-level
    cache and so opening it here cannot create the file the test is checking.
    """
    conn = sqlite3.connect(sqlite_path)
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "gr",
                "gr_citation",
                "gr_scenario",
                "gr_edge_case",
                "gr_run",
                "gr_finding",
            )
        }
    finally:
        conn.close()


def gr_runs(sqlite_path: Path) -> list[sqlite3.Row]:
    """Every `gr_run` row including the GENERATED `complete` column.

    `complete` is selected explicitly: `PRAGMA table_info` omits a generated
    column, and `SELECT *` on this table is exactly where a test would
    accidentally stop asserting the gate.
    """
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT run_id, rules_in, rules_merged, not_accounted_for, "
            "coverage_source, coverage_measured_at, gate_excluded, "
            "gate_excluded_reason, complete, system FROM gr_run ORDER BY run_id"
        ).fetchall()
    finally:
        conn.close()


# ======================================================================
# ingest
# ======================================================================


def test_ingest_creates_the_store_and_reports_every_number_it_was_given(
    runner, repo, analysis, tmp_root
):
    """Proves `ingest` is the write path that may create the database.

    Also the baseline for everything below: two rules land, the report names
    the run and the rule breakdown, and the resolved repository root is
    printed -- which is the loudness that stops an ingest keying every row
    against the wrong working tree when `--repo-root` is defaulted.
    """
    src = write_payload(tmp_root, two_rules())
    p = paths_of(repo, analysis)
    assert not p.knowledge_sqlite_path.exists(), "the fixture must start empty"

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 0, result.output
    assert p.knowledge_sqlite_path.exists(), "ingest must create the store"
    counts = table_counts(p.knowledge_sqlite_path)
    assert counts["gr"] == 2
    assert counts["gr_run"] == 1
    assert "2 offered = 2 new" in result.stdout
    assert "rows inserted: 2" in result.stdout
    assert str(p.repo_root) in result.stderr, "the resolved repo root must be loud"


def test_reingesting_the_same_payload_changes_no_count_and_adds_one_run(
    runner, repo, analysis, tmp_root
):
    """The headline acceptance criterion, driven through the command.

    Ingesting the *same saved JSON* twice leaves the requirement count
    unchanged **and** the citation, scenario and edge-case counts unchanged,
    while `gr_run` gains a second row whose `rules_merged` equals the first
    run's `rules_in`. All four counts are named because a flat requirement
    count over a growing child table is the same bug one level down.
    """
    src = write_payload(tmp_root, two_rules())
    p = paths_of(repo, analysis)

    first = invoke(runner, *ingest_args(repo, analysis, src))
    assert first.exit_code == 0, first.output
    before = table_counts(p.knowledge_sqlite_path)
    assert before["gr"] == 2
    assert before["gr_citation"] == 2
    assert before["gr_scenario"] == 2
    assert before["gr_edge_case"] == 4

    second = invoke(runner, *ingest_args(repo, analysis, src))
    assert second.exit_code == 0, second.output
    after = table_counts(p.knowledge_sqlite_path)

    for grain in ("gr", "gr_citation", "gr_scenario", "gr_edge_case"):
        assert after[grain] == before[grain], f"{grain} grew on a re-ingest"
    assert after["gr_run"] == 2

    runs = gr_runs(p.knowledge_sqlite_path)
    assert runs[1]["rules_merged"] == runs[0]["rules_in"] == 2
    assert "2 offered = 0 new + 2 merged" in second.stdout


def test_a_payload_with_no_rules_is_reported_loudly_not_as_a_quiet_success(
    runner, repo, analysis, tmp_root
):
    """Proves an ingest of zero announces itself instead of looking successful.

    This is the worst available shape of failure here: every count is
    correct, the exit code is zero and the store is consistent, so nothing
    else in the system would ever mention it. A field map written from the
    plan's older prose -- reading `rules` where the workflow returns
    `confirmedRules` -- lands exactly here.

    The exit code stays **zero** on purpose: the `gr_run` row *was* written,
    so a non-zero exit would tell the caller nothing was stored, which is
    false. The loud line is the whole defence, and it names the payload's own
    top-level keys so a field-map or wrong-file mistake is diagnosable from
    the output alone.
    """
    src = write_payload(tmp_root, payload())  # `confirmedRules` present but empty
    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 0, result.output
    assert "NO RULES WERE INGESTED" in result.stderr
    assert "confirmedRules" in result.stderr, "the loud line must name the keys"
    assert "coverage" in result.stderr
    assert "0 offered = 0 new" in result.stdout

    p = paths_of(repo, analysis)
    assert table_counts(p.knowledge_sqlite_path)["gr_run"] == 1, (
        "the run is still recorded -- which is why the exit code is zero"
    )


def test_a_payload_missing_its_rule_array_entirely_is_still_loud(
    runner, repo, analysis, tmp_root
):
    """Proves the absent key and the empty list are both reported.

    `_rules_of` returns `[]` for both, so the two are indistinguishable
    downstream -- which means the loud line has to fire on absence too, not
    only on an empty array someone remembered to include.
    """
    body = payload()
    body.pop("confirmedRules")
    src = write_payload(tmp_root, body)

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 0, result.output
    assert "NO RULES WERE INGESTED" in result.stderr


def test_a_rule_array_saved_alone_is_refused_before_any_store_is_created(
    runner, repo, analysis, tmp_root
):
    """Proves the bare-array mistake fails loudly instead of ingesting zero.

    Saving the *rule array* rather than the workflow's whole return value is
    the one input that would reach `ingest_extraction` as a payload with no
    keys at all: zero rules, no coverage, no system. It is refused at the
    door, and refused **before** the knowledge store is constructed, so a
    typo does not leave an empty database behind.
    """
    src = write_payload(tmp_root, [rule()])
    p = paths_of(repo, analysis)

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 1
    assert "not a JSON object" in result.stderr
    assert not p.knowledge_sqlite_path.exists(), (
        "a refused payload must not leave an empty store behind"
    )


def test_a_missing_or_unparseable_from_file_exits_one_and_says_which(
    runner, repo, analysis, tmp_root
):
    """Proves the three read failures are distinguished, not merged into one.

    They call for three different actions -- fix the path, fix the file, save
    the right object -- so one message for all three would be the
    absent-versus-real defect in its diagnostics form.
    """
    missing = invoke(
        runner, *ingest_args(repo, analysis, tmp_root / "nope.json")
    )
    assert missing.exit_code == 1
    assert "no extractor output at" in missing.stderr

    broken = tmp_root / "broken.json"
    broken.write_text('{"confirmedRules": [', encoding="utf-8")
    result = invoke(runner, *ingest_args(repo, analysis, broken))
    assert result.exit_code == 1
    assert "is not valid JSON" in result.stderr
    assert "Nothing was written" in result.stderr


def test_ingest_against_an_unindexed_repository_creates_no_index_sqlite(
    runner, repo, analysis, tmp_root
):
    """Proves the acceptance criterion that no `index.sqlite` is created.

    `SQLiteStore` connects lazily, so *asking* the store whether an index
    exists is what materialises an empty one -- and an empty index database
    beside an unindexed repository is indistinguishable from a real one on
    the next command. The command must therefore take a plain `Path.exists()`
    before constructing anything, name the resolved index path loudly, and
    still exit zero with every citation on its file-level anchor.
    """
    src = write_payload(tmp_root, payload(rule()))
    p = paths_of(repo, analysis)
    assert not p.index_sqlite_path.exists()

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 0, result.output
    assert not p.index_sqlite_path.exists(), "no index.sqlite may be created"
    assert str(p.index_sqlite_path) in result.stdout
    assert "index: NOT present" in result.stdout

    conn = sqlite3.connect(p.knowledge_sqlite_path)
    try:
        resolutions = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT anchor_resolution FROM gr_citation"
            )
        }
    finally:
        conn.close()
    assert resolutions == {"file"}


def test_a_missing_embedder_is_a_degraded_success_that_exits_zero(
    runner, repo, analysis, tmp_root
):
    """`PR-47`: every rule still lands, `reindex-vectors` is named, exit is 0.

    A non-zero exit here would read as "the ingest failed" and invite
    re-running the extraction, which is hours of model time to recover
    something that was never lost. The provider is made unresolvable with an
    unknown `--embedding-provider`, which is `create_embedder`'s `ValueError`
    path and therefore `build_embedder`'s `(None, reason)` return.
    """
    src = write_payload(tmp_root, two_rules())
    p = paths_of(repo, analysis)

    result = invoke(
        runner,
        *ingest_args(repo, analysis, src, "--embedding-provider", "no-such-provider"),
    )

    assert result.exit_code == 0, result.output
    assert table_counts(p.knowledge_sqlite_path)["gr"] == 2, (
        "the requirement count must be what the input offered"
    )
    assert "no embedding provider is available" in result.stderr
    assert "requirements reindex-vectors" in result.stderr
    assert "semantic half is NOT fully populated" in result.stdout


def test_never_measured_coverage_is_reported_as_unmeasured_and_never_as_zero(
    runner, repo, analysis, tmp_root
):
    """Proves NULL coverage does not pass the gate and is not printed as zero.

    `coverage: null` is the shape the workflow really produces, and this is
    the recurring defect of this plan in its most consequential place: a
    stored zero would make the completeness gate pass most confidently in the
    one case it exists to stop. So the column stays NULL, the generated
    `complete` column is 0, and the report says *never measured* in words.
    """
    src = write_payload(tmp_root, payload(rule(), coverage=None))
    p = paths_of(repo, analysis)

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 0, result.output
    assert "coverage: NEVER MEASURED" in result.stdout
    assert "not the same as zero" in result.stdout
    assert "0 chunk(s) not accounted for" not in result.stdout

    run = gr_runs(p.knowledge_sqlite_path)[0]
    assert run["not_accounted_for"] is None
    assert run["complete"] == 0, "an unmeasured run does not pass the gate"
    assert run["coverage_source"] is None


def test_a_skipped_coverage_object_is_treated_as_never_measured_too(
    runner, repo, analysis, tmp_root
):
    """Proves the synthetic `skipped: true` shape lands on the NULL side.

    The workflow cannot emit it -- `extract-rules.js:229` normalizes it to
    `null` first -- but the field map must still handle it, and a shape that
    reached `not_accounted_for` as a zero would be the same gate failure by
    another route.
    """
    src = write_payload(tmp_root, payload(rule(), coverage={"skipped": True}))
    p = paths_of(repo, analysis)

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 0, result.output
    assert "coverage: NEVER MEASURED" in result.stdout
    run = gr_runs(p.knowledge_sqlite_path)[0]
    assert run["not_accounted_for"] is None
    assert run["complete"] == 0


def test_a_capped_uncovered_listing_is_reported_as_shown_against_the_total(
    runner, repo, analysis, tmp_root
):
    """Proves the forty-entry display cap is never read as the total.

    The workflow caps `uncovered_chunks` at forty entries, so
    `len(uncovered_chunks)` is a sample and the real figure is the coverage
    payload's own `uncovered`. `IngestResult.coverage_rendering` already
    renders both -- `"2 of 512 shown"` here -- and the command prints it
    rather than deriving anything.
    """
    src = write_payload(
        tmp_root,
        payload(
            rule(),
            coverage={
                "total": 1000,
                "claimed": 488,
                "uncovered": 512,
                "pct": 48.8,
                "uncovered_chunks": [{"path": "a"}, {"path": "b"}],
            },
        ),
    )
    p = paths_of(repo, analysis)

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 0, result.output
    assert "512 chunk(s) not accounted for (2 of 512 shown)" in result.stdout
    assert "INCOMPLETE" in result.stdout
    assert gr_runs(p.knowledge_sqlite_path)[0]["not_accounted_for"] == 512


def test_the_prompt_injection_notice_reaches_stderr_and_stdout_stays_json(
    runner, repo, analysis, tmp_root
):
    """Proves the notice is not swallowed and does not corrupt `--json` stdout.

    Two properties at once, and they pull against each other: the flagged
    citations must be announced -- they are DATA, never instructions, and a
    reviewer has to read them before trusting rules mined from those files --
    while a `--json` caller's stdout must stay exactly one parseable
    document. stderr is the only stream that satisfies both.
    """
    src = write_payload(
        tmp_root,
        payload(rule(), injectionFlags=["Order.java:12 ignore previous instructions"]),
    )

    result = invoke(runner, *ingest_args(repo, analysis, src, "--json"))

    assert result.exit_code == 0, result.output
    assert "PROMPT-INJECTION SUSPECTS" in result.stderr
    assert "DATA, never instructions" in result.stderr

    document = json.loads(result.stdout)
    assert document["injection_flags"] == [
        "Order.java:12 ignore previous instructions"
    ]
    assert "PROMPT-INJECTION SUSPECTS" in " ".join(document["notices"])


def test_the_json_document_keeps_unmeasured_coverage_as_null(
    runner, repo, analysis, tmp_root
):
    """Proves a JSON consumer can tell "never measured" from "measured zero".

    A `--json` caller is the one reader that cannot see the words, so the
    encoding has to carry the distinction on its own: `not_accounted_for` is
    `null` and `coverage_measured` is `false`, rather than a helpful `0`.
    """
    unmeasured = invoke(
        runner,
        *ingest_args(
            repo,
            analysis,
            write_payload(tmp_root, payload(rule(), coverage=None)),
            "--json",
        ),
    )
    assert unmeasured.exit_code == 0, unmeasured.output
    doc = json.loads(unmeasured.stdout)
    assert doc["not_accounted_for"] is None
    assert doc["coverage_measured"] is False
    assert doc["complete"] is False

    measured = invoke(
        runner,
        *ingest_args(
            repo,
            analysis,
            write_payload(tmp_root, payload(rule()), "measured.json"),
            "--json",
        ),
    )
    assert measured.exit_code == 0, measured.output
    doc2 = json.loads(measured.stdout)
    assert doc2["not_accounted_for"] == 0
    assert doc2["coverage_measured"] is True
    assert doc2["complete"] is True


def test_a_refused_rule_names_its_offer_ordinal_and_writes_nothing(
    runner, repo, analysis, tmp_root
):
    """Proves a failed ingest is all-or-nothing and says so.

    A ragged `decision_table` fails the transaction. The point of the
    message is that the fix is local -- correct that one rule and run the
    same command again -- and that there is no partial state to clean up and
    no resume flag, which is only true if `gr_run` is empty afterwards too.
    """
    ragged = rule(
        name="Ragged table",
        source="Vendor.java:5-9",
        structuredBodyType="decision_table",
        structuredBody={
            "hitPolicy": "UNIQUE",
            "inputs": [
                {"label": "status", "expression": "o.status", "typeRef": "string"},
                {"label": "amount", "expression": "o.amount", "typeRef": "number"},
            ],
            "outputs": [{"label": "action", "typeRef": "string"}],
            "rules": [{"inputEntries": ["Open"], "outputEntries": ["reject"]}],
        },
    )
    src = write_payload(tmp_root, payload(rule(), ragged))
    p = paths_of(repo, analysis)

    result = invoke(runner, *ingest_args(repo, analysis, src))

    assert result.exit_code == 1
    assert "offer_ordinal 1" in result.stderr
    assert "NOTHING WAS WRITTEN" in result.stderr
    assert "no resume flag" in result.stderr

    counts = table_counts(p.knowledge_sqlite_path)
    assert counts["gr"] == 0
    assert counts["gr_run"] == 0
    assert counts["gr_citation"] == 0

    # And the retry is a clean first ingest.
    retry = invoke(
        runner,
        *ingest_args(
            repo, analysis, write_payload(tmp_root, payload(rule()), "ok.json")
        ),
    )
    assert retry.exit_code == 0, retry.output
    assert table_counts(p.knowledge_sqlite_path)["gr_run"] == 1


def test_the_system_flag_reaches_gr_run_and_a_disagreement_is_loud(
    runner, repo, analysis, tmp_root
):
    """Proves `--system` is recorded, and that overriding a payload is visible.

    `ingest_extraction` reads `gr_run.system` from the payload, so the flag
    the plan's invocation passes has to reach it somewhere. It wins over a
    value inside a saved payload -- the analyst typing it knows which system
    they are ingesting into -- and the override is announced, because two
    runs of one repository filed under two system names do not add up in any
    later report.
    """
    src = write_payload(tmp_root, payload(rule()))  # payload says system="demo"
    p = paths_of(repo, analysis)

    result = invoke(
        runner, *ingest_args(repo, analysis, src, "--system", "customer.ple.nng.app")
    )

    assert result.exit_code == 0, result.output
    assert gr_runs(p.knowledge_sqlite_path)[0]["system"] == "customer.ple.nng.app"
    assert "overrides the 'demo'" in result.stderr


def test_the_vector_collection_lands_beside_knowledge_sqlite_not_in_the_index(
    runner, repo, analysis, tmp_root
):
    """Proves `vector_base_dir` is the knowledge directory, never the index one.

    `index --reset` rmtrees the index directory's collections wholesale, so a
    `gr_statements` collection living there would be destroyed by an
    unrelated re-index -- silently, since the SQLite half would still be
    intact and only the semantic half would be gone. The default is correct
    and the command must not override it, which is what this asserts from
    the outside.
    """
    src = write_payload(tmp_root, payload(rule()))
    p = paths_of(repo, analysis)

    result = invoke(runner, *ingest_args(repo, analysis, src))
    assert result.exit_code == 0, result.output

    assert p.knowledge_sqlite_path.parent == p.knowledge_dir
    chroma_dirs = list(p.knowledge_dir.glob("chroma*"))
    assert chroma_dirs, (
        f"no collection under the knowledge directory {p.knowledge_dir}: "
        f"{sorted(x.name for x in p.knowledge_dir.iterdir())}"
    )
    # Containment, not equality: the index lives at <analysis>/index/... and
    # the knowledge store at <analysis>/knowledge, so the two are siblings
    # under the analysis directory and neither contains the other.
    assert p.knowledge_dir not in p.index_dir.parents
    if p.index_dir.exists():
        assert list(p.index_dir.glob("chroma*")) == []


# ======================================================================
# validate
# ======================================================================


def seeded_store(repo: Path, analysis: Path, **overrides) -> tuple[Path, str]:
    """Create a knowledge store holding exactly one `gr` row, and return both.

    Uses `KnowledgeStore` plus the `insert_gr` helper from
    `tests/test_gr_state.py` rather than going through `ingest`, because
    these tests need a *specific* statement/pattern combination and the
    validator's input is the row, not the extraction.
    """
    p = resolve_requirements_paths(repo, None, analysis, print_banner=False)
    store = KnowledgeStore(p.knowledge_sqlite_path)
    try:
        gr_id = insert_gr(store._connect(), **overrides)
    finally:
        store.close()
    return p.knowledge_sqlite_path, gr_id


def validate_args(repo: Path, analysis: Path, *extra: str):
    return [
        "requirements",
        "validate",
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
        *extra,
    ]


def test_validate_changes_nothing_at_all(runner, repo, analysis):
    """Proves `validate` reports violations *without changing anything*.

    The Purpose section's wording is the constraint: it cannot reach the
    validator through `refresh_gr_derived_sql`, which rewrites `gr_fts` and
    replaces `gr_finding` rows. The observable is a byte-identical snapshot
    of every stored finding row across the run -- taken as rows rather than
    as a count, since a replace-with-identical-content would keep the count
    and change the rows.
    """
    sqlite_path, gr_id = seeded_store(
        repo, analysis, statement="Orders are saved to the database."
    )

    def snapshot():
        conn = sqlite3.connect(sqlite_path)
        try:
            return conn.execute(
                "SELECT gr_id, finding_id, severity, span, message, evaluated "
                "FROM gr_finding ORDER BY gr_id, finding_id, span"
            ).fetchall()
        finally:
            conn.close()

    before = snapshot()
    result = invoke(runner, *validate_args(repo, analysis))
    after = snapshot()

    assert result.exit_code == 1, "the seeded statement carries an ERROR"
    assert after == before, "validate wrote to gr_finding"
    assert "nothing was written" in result.stdout


def test_validate_reports_findings_with_stable_identifiers(runner, repo, analysis):
    """Proves every reported finding carries one of the twenty-eight check ids.

    "Reports findings with stable identifiers" is an explicit acceptance
    criterion, and the assertion is written against `CHECK_IDS` rather than
    against a literal list so it cannot drift from the validator.
    """
    seeded_store(repo, analysis, statement="Orders are saved to the database.")

    result = invoke(runner, *validate_args(repo, analysis, "--json"))

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["findings"], "the seeded statement must produce findings"
    assert {f["finding_id"] for f in document["findings"]} <= set(CHECK_IDS)
    assert "V-KW-01" in {f["finding_id"] for f in document["findings"]}
    assert document["checks_run"] == len(CHECK_IDS)
    assert document["wrote_nothing"] is True


def test_validate_exits_zero_on_a_conformant_corpus(runner, repo, analysis):
    """Proves a clean corpus is a zero exit, so the non-zero one means something."""
    seeded_store(repo, analysis, statement="An order must record a vendor number.")

    result = invoke(runner, *validate_args(repo, analysis))

    assert result.exit_code == 0, result.output
    assert "blocking (evaluated ERROR) findings: 0" in result.stdout
    assert "nothing blocks approval" in result.stdout


def test_a_not_evaluated_error_does_not_block_and_is_not_a_pass_either(
    runner, repo, analysis
):
    """Proves the `evaluated` flag decides the exit code, and is still reported.

    A row with a NULL `pattern` produces four ERROR-severity findings that
    could not be *decided*, because no template locates the slots: the three
    `V-SLOT` checks, and -- since amendment A4 gave it the `[Subject]` slot as
    its only site -- `V-VAG-03`. The number is four rather than three only
    because the check set grew; what this test proves is unchanged. A
    command that exited non-zero on the count of ERROR rows would refuse a
    corpus for checks nobody ran; one that dropped them would present
    "undecidable" as "clean". Both counts are printed and only the evaluated
    half sets the exit code.
    """
    seeded_store(
        repo,
        analysis,
        statement="An order must record a vendor number.",
        pattern=None,
    )

    result = invoke(runner, *validate_args(repo, analysis, "--json"))

    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["blocking_findings"] == 0
    assert document["counts_by_severity"]["ERROR"]["not_evaluated"] == 4
    assert document["counts_by_severity"]["ERROR"]["evaluated"] == 0
    # Under `--json` the human report is a diagnostic and moves to stderr so
    # stdout stays exactly one parseable document -- asserted on the stream it
    # actually goes to, not on `result.output`, which interleaves both.
    assert "NOT EVALUATED" in result.stderr
    assert "ERROR: 0 evaluated, 4 not evaluated" in result.stderr


def test_validate_says_whether_identifier_leakage_was_ever_looked_for(
    runner, repo, analysis, tmp_root
):
    """Proves "no leakage found" and "leakage was never looked for" differ.

    With no reachable index `leaked_terms` is empty for every record and
    `V-STY-03` ran on its morphological half alone. That is a supported
    state, not an error -- but it is not the shipped check either, and a
    corpus that presented the two the same way would let a reviewer read an
    unexamined statement as a clean one.
    """
    sqlite_path, _ = seeded_store(
        repo, analysis, statement="An order must record a vendor number."
    )
    p = paths_of(repo, analysis)

    without_index = invoke(runner, *validate_args(repo, analysis))
    assert without_index.exit_code == 0, without_index.output
    assert "NEVER LOOKED FOR" in without_index.stdout
    assert str(p.index_sqlite_path) in without_index.stdout
    assert not p.index_sqlite_path.exists(), "validate must not create an index"

    # Now give it an index -- migrated but with no symbols, which is enough:
    # the fact under test is whether the symbol half was consulted at all.
    from legacylift_search.store import SQLiteStore

    p.index_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    index_store = SQLiteStore(p.index_sqlite_path)
    try:
        index_store.migrate()
    finally:
        index_store.close()

    with_index = invoke(runner, *validate_args(repo, analysis, "--json"))
    assert with_index.exit_code == 0, with_index.output
    assert "NEVER LOOKED FOR" not in with_index.output
    # The report is on stderr here because `--json` owns stdout.
    assert "checked against" in with_index.stderr
    assert json.loads(with_index.stdout)["leaked_terms_available"] is True
    assert sqlite_path.exists()


def test_validate_can_target_one_requirement_and_refuses_an_unknown_one(
    runner, repo, analysis
):
    """Proves `--gr-id` narrows the corpus and an unknown id is an error.

    An unknown `gr_id` exits 1 rather than reporting a clean corpus of zero
    records: "nothing to validate" and "you named something that is not
    there" are different facts, and the second is a typo the analyst needs
    to see.
    """
    _, gr_id = seeded_store(
        repo, analysis, statement="Orders are saved to the database."
    )

    targeted = invoke(
        runner, *validate_args(repo, analysis, "--gr-id", gr_id, "--json")
    )
    assert targeted.exit_code == 1
    document = json.loads(targeted.stdout)
    assert document["requirements_validated"] == 1
    assert {f["gr_id"] for f in document["findings"]} == {gr_id}

    unknown = invoke(runner, *validate_args(repo, analysis, "--gr-id", "GR-nope"))
    assert unknown.exit_code == 1
    assert "no requirement" in unknown.stderr


def test_validate_on_a_missing_store_exits_one_and_creates_nothing(
    runner, repo, analysis
):
    """Proves the read-path probe runs before the constructor.

    `KnowledgeStore.__init__` creates the file *and its parent*, so a
    `validate` that constructed one to find out whether requirements existed
    would answer "no findings" from a database it had just made -- which is
    indistinguishable from a real, clean corpus.
    """
    p = paths_of(repo, analysis)
    assert not p.knowledge_sqlite_path.exists()

    result = invoke(runner, *validate_args(repo, analysis))

    assert result.exit_code == 1
    assert "no requirements store at" in result.stderr
    assert not p.knowledge_sqlite_path.exists()


# ======================================================================
# set-run-coverage and retire-run
# ======================================================================


def one_unmeasured_run(runner, repo, analysis, tmp_root) -> tuple[Path, str]:
    """Ingest a run whose `coverage` is `null` -- the shape the workflow makes."""
    src = write_payload(tmp_root, payload(rule(), coverage=None))
    result = invoke(runner, *ingest_args(repo, analysis, src))
    assert result.exit_code == 0, result.output
    p = paths_of(repo, analysis)
    runs = gr_runs(p.knowledge_sqlite_path)
    assert len(runs) == 1 and runs[0]["complete"] == 0
    return p.knowledge_sqlite_path, runs[0]["run_id"]


def test_set_run_coverage_records_a_remeasurement_and_opens_the_gate(
    runner, repo, analysis, tmp_root
):
    """Proves the first exit from the gate records a measurement that was taken.

    It stamps `coverage_source = 'remeasured'` and `coverage_measured_at`, so
    the audit question -- why did this run stop blocking the export? -- is
    answered with "because somebody measured it, on this date". A re-measured
    zero is a real value and flips the generated `complete` column.
    """
    sqlite_path, run_id = one_unmeasured_run(runner, repo, analysis, tmp_root)

    result = invoke(
        runner,
        "requirements",
        "set-run-coverage",
        run_id,
        "--not-accounted-for",
        "0",
        "--measured-at",
        "2026-09-02T12:00:00+00:00",
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
    )

    assert result.exit_code == 0, result.output
    run = gr_runs(sqlite_path)[0]
    assert run["not_accounted_for"] == 0
    assert run["coverage_source"] == "remeasured"
    assert run["coverage_measured_at"] == "2026-09-02T12:00:00+00:00"
    assert run["complete"] == 1
    assert run["gate_excluded"] == 0, "a measurement is not a retirement"
    assert "NEVER MEASURED (not zero)" in result.stdout, "the before line"
    assert "complete=1" in result.stdout


def test_set_run_coverage_stamps_the_time_it_ran_when_none_is_given(
    runner, repo, analysis, tmp_root
):
    """Proves the stamp is never left blank -- the figure's date is the point.

    `--measured-at` defaults to now rather than to NULL, because
    `set_gr_run_coverage` refuses a blank stamp and a command whose whole
    claim is "this was measured" has no answer to *when* without one.
    """
    sqlite_path, run_id = one_unmeasured_run(runner, repo, analysis, tmp_root)

    result = invoke(
        runner,
        "requirements",
        "set-run-coverage",
        run_id,
        "--not-accounted-for",
        "7",
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
    )

    assert result.exit_code == 0, result.output
    run = gr_runs(sqlite_path)[0]
    assert run["coverage_measured_at"], "a re-measurement must carry its date"
    assert run["not_accounted_for"] == 7
    assert run["complete"] == 0, "seven chunks left over is still incomplete"
    assert "does NOT pass the completeness gate" in result.stdout


def test_set_run_coverage_cannot_record_a_measurement_that_was_not_made(
    runner, repo, analysis, tmp_root
):
    """Proves a missing measurement cannot become a zero.

    `--not-accounted-for` is a required option with no default, so omitting
    it is a usage error rather than a silent zero -- and the run's coverage
    is still NULL afterwards. NULL means never measured, and `complete`
    derives from exactly that distinction.
    """
    sqlite_path, run_id = one_unmeasured_run(runner, repo, analysis, tmp_root)

    result = invoke(
        runner,
        "requirements",
        "set-run-coverage",
        run_id,
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
    )

    assert result.exit_code != 0
    run = gr_runs(sqlite_path)[0]
    assert run["not_accounted_for"] is None, "the absent measurement stayed absent"
    assert run["complete"] == 0


def test_set_run_coverage_refuses_an_unknown_run_and_a_negative_count(
    runner, repo, analysis, tmp_root
):
    """Proves both `ValueError` paths surface as exit 1 with the reason.

    The schema has no CHECK for either, so a silent no-op `UPDATE` on a
    mistyped `run_id` is what this stops -- an analyst would read the zero
    exit as "recorded" and the gate would still be closed.
    """
    sqlite_path, run_id = one_unmeasured_run(runner, repo, analysis, tmp_root)
    common = ["--repo-root", str(repo), "--analysis-dir", str(analysis)]

    unknown = invoke(
        runner,
        "requirements",
        "set-run-coverage",
        "RUN-nope",
        "--not-accounted-for",
        "0",
        *common,
    )
    assert unknown.exit_code == 1
    assert "no run" in unknown.stderr

    negative = invoke(
        runner,
        "requirements",
        "set-run-coverage",
        run_id,
        "--not-accounted-for",
        "-1",
        *common,
    )
    assert negative.exit_code == 1
    assert "must be >= 0" in negative.stderr
    assert gr_runs(sqlite_path)[0]["not_accounted_for"] is None


def test_retire_run_excludes_the_run_and_leaves_complete_unchanged(
    runner, repo, analysis, tmp_root
):
    """Proves the second exit records a judgement without forging a measurement.

    `retire-run` writes `gate_excluded` and `gate_excluded_reason` and leaves
    `not_accounted_for` -- and therefore the GENERATED `complete` column --
    untouched, so the record still says what was actually known about the
    run. Overwriting the coverage figure while retiring would fabricate a
    measurement to justify the judgement, which is the thing the two-command
    split exists to prevent.
    """
    sqlite_path, run_id = one_unmeasured_run(runner, repo, analysis, tmp_root)
    before = gr_runs(sqlite_path)[0]

    result = invoke(
        runner,
        "requirements",
        "retire-run",
        run_id,
        "--reason",
        "superseded by the 2026-09-02 re-extraction",
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
    )

    assert result.exit_code == 0, result.output
    after = gr_runs(sqlite_path)[0]
    assert after["gate_excluded"] == 1
    assert (
        after["gate_excluded_reason"] == "superseded by the 2026-09-02 re-extraction"
    )
    assert after["complete"] == before["complete"], "retire must not move `complete`"
    assert after["not_accounted_for"] == before["not_accounted_for"]
    assert after["coverage_source"] == before["coverage_source"]
    assert "deliberately unchanged" in result.stdout


def test_retire_run_leaves_complete_unchanged_on_a_complete_run_too(
    runner, repo, analysis, tmp_root
):
    """Proves the invariant holds in the direction that could hide a bug.

    Retiring an *unmeasured* run leaves `complete` at 0, which is also what a
    writer that reset the column would produce -- so the same assertion has
    to be made where `complete` is 1 and a reset would be visible.
    """
    src = write_payload(tmp_root, payload(rule()))  # measured, uncovered = 0
    assert invoke(runner, *ingest_args(repo, analysis, src)).exit_code == 0
    sqlite_path = paths_of(repo, analysis).knowledge_sqlite_path
    run_id = gr_runs(sqlite_path)[0]["run_id"]
    assert gr_runs(sqlite_path)[0]["complete"] == 1

    result = invoke(
        runner,
        "requirements",
        "retire-run",
        run_id,
        "--reason",
        "duplicate of a later run",
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
    )

    assert result.exit_code == 0, result.output
    after = gr_runs(sqlite_path)[0]
    assert after["complete"] == 1, "retire must not reset a real measurement"
    assert after["not_accounted_for"] == 0
    assert after["gate_excluded"] == 1


def test_retire_run_requires_a_reason_and_refuses_a_blank_one(
    runner, repo, analysis, tmp_root
):
    """Proves the audit question always has an answer.

    Omitting `--reason` is a usage error; passing a whitespace-only one is
    refused by the writer with a message that names the question, rather than
    by the table's CHECK with a message that names neither the column nor the
    question.
    """
    sqlite_path, run_id = one_unmeasured_run(runner, repo, analysis, tmp_root)
    common = ["--repo-root", str(repo), "--analysis-dir", str(analysis)]

    missing = invoke(runner, "requirements", "retire-run", run_id, *common)
    assert missing.exit_code != 0
    assert gr_runs(sqlite_path)[0]["gate_excluded"] == 0

    blank = invoke(
        runner, "requirements", "retire-run", run_id, "--reason", "   ", *common
    )
    assert blank.exit_code == 1
    assert "non-empty reason" in blank.stderr
    assert gr_runs(sqlite_path)[0]["gate_excluded"] == 0


def test_retire_run_refuses_an_unknown_run(runner, repo, analysis, tmp_root):
    """Proves a mistyped `run_id` is not a silent no-op `UPDATE`."""
    one_unmeasured_run(runner, repo, analysis, tmp_root)

    result = invoke(
        runner,
        "requirements",
        "retire-run",
        "RUN-nope",
        "--reason",
        "superseded",
        "--repo-root",
        str(repo),
        "--analysis-dir",
        str(analysis),
    )

    assert result.exit_code == 1
    assert "no run" in result.stderr


def test_the_two_gate_commands_are_separate_and_write_different_columns(
    runner, repo, analysis, tmp_root
):
    """Proves the `PR-54` split is real in the CLI, not just in the store.

    "How did this run stop blocking the export?" has to be answerable from
    the columns: a re-measurement moves `coverage_source`/
    `coverage_measured_at` and never `gate_excluded`, and a retirement moves
    `gate_excluded`/`gate_excluded_reason` and never the coverage figure. One
    command carrying both flags would make the two indistinguishable after
    the fact, which is exactly the question an audit asks.
    """
    sqlite_path, run_id = one_unmeasured_run(runner, repo, analysis, tmp_root)
    common = ["--repo-root", str(repo), "--analysis-dir", str(analysis)]

    measured = invoke(
        runner,
        "requirements",
        "set-run-coverage",
        run_id,
        "--not-accounted-for",
        "3",
        *common,
    )
    assert measured.exit_code == 0, measured.output
    mid = gr_runs(sqlite_path)[0]
    assert mid["coverage_source"] == "remeasured" and mid["gate_excluded"] == 0

    retired = invoke(
        runner,
        "requirements",
        "retire-run",
        run_id,
        "--reason",
        "superseded",
        *common,
    )
    assert retired.exit_code == 0, retired.output
    end = gr_runs(sqlite_path)[0]
    assert end["gate_excluded"] == 1
    assert end["coverage_source"] == "remeasured", "the measurement survived"
    assert end["not_accounted_for"] == 3
    assert end["complete"] == 0

    # And neither command has the other's flag.
    assert "--reason" not in _help(runner, "set-run-coverage")
    assert "--not-accounted-for" not in _help(runner, "retire-run")


def _help(runner: CliRunner, command: str) -> str:
    result = invoke(runner, "requirements", command, "--help")
    assert result.exit_code == 0, result.output
    return result.output


def test_all_four_commands_expose_the_three_shared_path_options(runner):
    """Proves house rule 3 holds for every command in this module.

    `--repo-root`, `--config` and `--analysis-dir` come from the `_shared`
    `Annotated` aliases, so four independently-written commands cannot
    disagree about a flag's name -- but only if each actually declares them.
    """
    for command in ("ingest", "validate", "set-run-coverage", "retire-run"):
        text = _help(runner, command)
        for flag in ("--repo-root", "--config", "--analysis-dir", "--json"):
            assert flag in text, f"{command} is missing {flag}"
