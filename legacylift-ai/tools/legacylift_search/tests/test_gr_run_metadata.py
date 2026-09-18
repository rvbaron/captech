"""Step 10's per-run termination record, end to end.

`docs/exec-plans/active/reqs-to-data-store.md` Step 10 requires four figures
per run in `gr_run` -- `rounds_run`, `round_cap`, `stop_reason` and
`new_rules_in_final_round` -- and requires `requirements stats` to surface
them. Three of the four had no producer at all:
`workflows/extract-rules.js` emitted only `rounds`, so a run that cost hours
of model time recorded NULL for how it ended, and under this plan's
absent-versus-real rule a NULL there correctly and permanently means "never
measured".

This file covers all three sides of that gap:

* **the workflow** now emits `roundCap`, `stopReason` and
  `newRulesInFinalRound`, and `stopReason` is derived from the loop's three
  real termination paths. The workflow is a JavaScript file whose body ends
  in a top-level `return`, so it is neither importable as an ES module nor
  reachable from Python; these tests drive it the way its own runtime does,
  by wrapping the body in an async function and injecting stub `agent`,
  `parallel`, `budget` and `log` globals. That runs the **real loop** against
  scripted agent output rather than inspecting the source text, so a
  derivation that is merely *spelled* correctly still fails.
* **the ingest** stores all four when the payload carries them and leaves all
  four NULL when it does not -- the absent-versus-real pair, read back
  through `KnowledgeStore.list_gr_runs()` rather than raw SQL.
* **`stats`** prints each of the four, prints `unmeasured` and never `0` for
  a NULL, and carries a real JSON `null` under `--json` rather than the
  string `"None"` or a text sentinel.

The one assertion worth naming ahead of the code, because it is this plan's
recurring defect class in its most misleading form:
**`newRulesInFinalRound` is `null`, not `0`, when no round ever ran.** `0`
there means "the final round found nothing new", which is precisely the
`'dry'` signal, so a `0` on the no-round-ran path asserts the opposite of the
truth rather than merely overstating confidence.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.cli_requirements._shared import resolve_requirements_paths
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import GRRun

_IS_WINDOWS = sys.platform == "win32"

#: `tools/legacylift_search/tests/` -> the repository root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

WORKFLOW = (
    _REPO_ROOT
    / ".claude"
    / "skills"
    / "code-modernization"
    / "workflows"
    / "extract-rules.js"
)

#: The three values `gr_run.stop_reason`'s CHECK constraint admits. Every one
#: must have a producer in the workflow, and every workflow termination path
#: must land on one of them -- the set is asserted below to be exactly
#: reachable, in both directions.
STOP_REASONS = ("dry", "round_cap", "budget_exhausted")


# ----------------------------------------------------------------------
# Driving the real workflow loop from Python
# ----------------------------------------------------------------------

#: A node harness that runs the workflow the way its own runtime does.
#:
#: The workflow file cannot be `import`ed: its body ends in a top-level
#: `return`, which is a SyntaxError in an ES module, so the Workflow runtime
#: must wrap the body in a function and inject `args`, `agent`, `parallel`,
#: `budget` and `log`. This harness wraps it identically. `export const meta`
#: is the one statement that cannot live inside a function body, so it loses
#: its `export` keyword and nothing else changes -- in particular no line of
#: the extraction loop or of the return object is rewritten, which is what
#: makes this a probe of the shipped code rather than of a copy of it.
_HARNESS = r"""
import fs from 'node:fs'

const [srcPath, scenarioJson] = process.argv.slice(2)
const scenario = JSON.parse(scenarioJson)

let body = fs.readFileSync(srcPath, 'utf8')
body = body.replace('export const meta =', 'const meta =')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const run = new AsyncFunction('args', 'agent', 'parallel', 'budget', 'log', body)

const logs = []
const log = m => logs.push(String(m))
const parallel = fns => Promise.all(fns.map(f => f()))

// How many DISTINCT rules each round reports. Index 0 is round 1; rounds past
// the end of the list report nothing, which is how a run is driven dry.
const freshPerRound = scenario.freshPerRound || []
// The round number that must NOT run because the budget is gone by then.
// 1 means the loop breaks before any round runs at all.
const budgetDiesBeforeRound = scenario.budgetDiesBeforeRound || 0

// The highest round number any extractor prompt has been issued for. The
// budget guard runs at the top of an iteration, BEFORE `round += 1`, so at
// that moment this equals the number of rounds that have completed.
let roundsIssued = 0

const budget = {
  total: 10000000,
  remaining: () =>
    budgetDiesBeforeRound && roundsIssued >= budgetDiesBeforeRound - 1
      ? 1000
      : 5000000,
}

const agent = async (prompt, opts) => {
  const label = (opts && opts.label) || ''
  if (label.startsWith('extract:')) {
    const round = Number(label.slice(label.lastIndexOf(':r') + 2))
    roundsIssued = Math.max(roundsIssued, round)
    // Only the first lens of each round reports; the other two come back
    // empty, so `fresh.length` for the round is exactly freshPerRound[n].
    if (!label.startsWith('extract:calculations:')) return { rules: [] }
    const n = freshPerRound[round - 1] || 0
    const rules = []
    for (let i = 0; i < n; i += 1) {
      rules.push({
        name: `round ${round} rule ${i}`,
        category: 'Validation',
        // P1, not P0: the P0 panel is not what these scenarios exercise.
        priority: 'P1',
        source: 'Order.java:10-20',
        plainEnglish: 'the code rejects something',
        given: 'g',
        when: 'w',
        then: 't',
      })
    }
    return { rules }
  }
  if (label.startsWith('verify:')) return { verdict: 'confirmed', reason: 'ok' }
  if (label.startsWith('p0:')) return { p0Justified: true, faithful: true, reason: 'ok' }
  if (label === 'dto-catalog') return { dataObjects: [] }
  throw new Error(`unstubbed agent label: ${label}`)
}

const result = await run(
  // repoRoot is deliberately absent: with no repo root the coverage agent is
  // never spawned, which is the documented index-free path.
  { system: 'demo', maxRounds: scenario.maxRounds },
  agent,
  parallel,
  budget,
  log,
)
process.stdout.write(JSON.stringify({ result, logs }))
"""


@pytest.fixture(scope="module")
def node() -> str:
    """The `node` binary, or a skip.

    This repository has no JavaScript test runner and no `package.json`, and
    adding a JS toolchain for three fields would be a larger change than the
    fields. `node` is present because Claude Code itself runs on it, so the
    probe is available in practice and skips honestly when it is not.
    """
    found = shutil.which("node")
    if not found:  # pragma: no cover - environment-dependent
        pytest.skip("node is not on PATH; the workflow probe needs it")
    return found


@pytest.fixture(scope="module")
def harness(node: str) -> Path:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        path = Path(tmp) / "harness.mjs"
        path.write_text(_HARNESS, encoding="utf-8")
        yield path


def run_workflow(node: str, harness: Path, **scenario) -> dict:
    """Run the real extraction loop under stub agents; return its return value."""
    proc = subprocess.run(
        [node, str(harness), str(WORKFLOW), json.dumps(scenario)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, f"harness failed:\n{proc.stderr}"
    return json.loads(proc.stdout)


# ----------------------------------------------------------------------
# The workflow's return object
# ----------------------------------------------------------------------


def test_the_workflow_emits_all_four_round_fields_by_the_names_ingest_reads(
    node, harness
):
    """Proves the three new fields exist under the spellings `gr_ingest` reads.

    `gr_ingest` reads `_int(payload, "rounds", "roundsRun")`,
    `_int(payload, "roundCap", "maxRounds")`, `_text(payload, "stopReason")`
    and `_int(payload, "newRulesInFinalRound")`. A field emitted under any
    other spelling is silently ignored by the ingest and the column stays
    NULL, which is indistinguishable from the workflow never having emitted
    it -- so the names are the contract, not a detail.
    """
    out = run_workflow(node, harness, maxRounds=2, freshPerRound=[1, 1])
    result = out["result"]
    for key in ("rounds", "roundCap", "stopReason", "newRulesInFinalRound"):
        assert key in result, f"{key} missing from the workflow's return value"


def test_two_dry_rounds_terminate_as_dry_with_zero_new_in_the_final_round(
    node, harness
):
    """Proves the `dryRounds >= 2` guard maps to `'dry'`.

    The design intent: round 1 finds rules, rounds 2 and 3 find nothing, and
    the `while (dryRounds < 2 ...)` guard ends the loop well short of the
    cap. `newRulesInFinalRound` is `0` here and that `0` is REAL -- the last
    round that ran genuinely found nothing new -- which is exactly why the
    no-round-ran case below must not also be `0`.
    """
    out = run_workflow(node, harness, maxRounds=8, freshPerRound=[2])
    result = out["result"]
    assert result["stopReason"] == "dry"
    assert result["rounds"] == 3
    assert result["roundCap"] == 8
    assert result["newRulesInFinalRound"] == 0
    # The cap was never reached, so the "stopped at maxRounds" coverage note
    # must not have been logged -- `dry` and `round_cap` disagreeing with that
    # log line is the mismatch this asserts against.
    assert not [line for line in out["logs"] if "stopped at maxRounds" in line]


def test_hitting_the_round_cap_terminates_as_round_cap_while_still_producing(
    node, harness
):
    """Proves the `round < maxRounds` guard maps to `'round_cap'`.

    Both rounds find new rules, so `dryRounds` is 0 when the cap ends the
    loop: the extractor was still producing when it was cut off, which is the
    fact `'round_cap'` records and `'dry'` would misreport. The file's own
    pre-existing coverage note fires on this path and is asserted alongside,
    so the log and the recorded reason cannot drift apart.
    """
    out = run_workflow(node, harness, maxRounds=2, freshPerRound=[2, 3])
    result = out["result"]
    assert result["stopReason"] == "round_cap"
    assert result["rounds"] == 2
    assert result["roundCap"] == 2
    assert result["newRulesInFinalRound"] == 3
    assert [line for line in out["logs"] if "stopped at maxRounds=2" in line]


def test_the_budget_break_terminates_as_budget_exhausted_and_counts_only_run_rounds(
    node, harness
):
    """Proves the in-loop `budget.remaining() < 60000` break maps to its own value.

    This is the third termination path, and the plan names
    `'budget_exhausted'` without saying what produces it. The break sits
    BEFORE `round += 1`, so the round that never started must not be counted:
    `rounds` is 2 after two rounds ran and a third was abandoned, and
    `newRulesInFinalRound` still describes round 2 -- the last round that
    actually ran -- rather than the one that did not.
    """
    out = run_workflow(
        node,
        harness,
        maxRounds=8,
        freshPerRound=[2, 4],
        budgetDiesBeforeRound=3,
    )
    result = out["result"]
    assert result["stopReason"] == "budget_exhausted"
    assert result["rounds"] == 2
    assert result["roundCap"] == 8
    assert result["newRulesInFinalRound"] == 4
    assert [line for line in out["logs"] if "token budget nearly exhausted" in line]


def test_new_rules_in_final_round_is_null_and_not_zero_when_no_round_ran(
    node, harness
):
    """Proves the recurring defect class was not repeated an eleventh time.

    The budget guard can fire on the very first iteration, before any round
    runs. `0` there would be a lie in the most misleading direction
    available: `0` means "the final round found nothing new", which is the
    `'dry'` signal, so a reader would conclude extraction had run out of
    rules when in fact it never started. `null` is the only honest encoding,
    and `rounds` is `0` for the same reason.
    """
    out = run_workflow(
        node, harness, maxRounds=8, freshPerRound=[3], budgetDiesBeforeRound=1
    )
    result = out["result"]
    assert result["stopReason"] == "budget_exhausted"
    assert result["rounds"] == 0
    assert result["newRulesInFinalRound"] is None
    # Not merely falsy: `0` is falsy too, and `0` is the whole defect.
    assert result["newRulesInFinalRound"] != 0
    assert result["confirmedRules"] == []


def test_every_stop_reason_the_schema_admits_has_a_producer_and_no_path_lacks_one(
    node, harness
):
    """Proves the enum is exactly reachable, in both directions.

    `gr_run.stop_reason` is `CHECK (stop_reason IS NULL OR stop_reason IN
    ('dry','round_cap','budget_exhausted'))`. An unreachable CHECK value is a
    column nobody can interpret, and a termination path with no value is a
    silently unrecorded run -- so this asserts the produced set is exactly
    the admitted set, and that every value `GRRun` will accept is produced.
    """
    produced = {
        run_workflow(node, harness, **scenario)["result"]["stopReason"]
        for scenario in (
            {"maxRounds": 8, "freshPerRound": [2]},
            {"maxRounds": 2, "freshPerRound": [2, 3]},
            {"maxRounds": 8, "freshPerRound": [2], "budgetDiesBeforeRound": 2},
        )
    }
    assert produced == set(STOP_REASONS)
    # And each one survives the model validator that mirrors the DDL CHECK.
    for reason in produced:
        assert GRRun(run_id="RUN-X", stop_reason=reason).stop_reason == reason


# ----------------------------------------------------------------------
# The ingest side: the absent-versus-real pair
# ----------------------------------------------------------------------


@pytest.fixture
def tmp_root():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        yield Path(tmp)


@pytest.fixture
def repo(tmp_root: Path) -> Path:
    root = tmp_root / "repo"
    root.mkdir()
    (root / "Order.java").write_text(
        "\n".join(f"// order line {i}" for i in range(1, 61)), encoding="utf-8"
    )
    return root


def _rule() -> dict:
    return {
        "name": "Vendor number required",
        "category": "Validation",
        "priority": "P1",
        "source": "Order.java:10-20",
        "ruleClass": "behavioral",
        "pattern": "B-UNCOND",
        "statement": "An order must record a vendor number.",
        "modality": "requirement",
        "assumptions": "",
        "given": "an order with no vendor number",
        "when": "it is saved",
        "then": "the save is rejected",
        "confidence": "High",
    }


def test_ingest_stores_all_four_round_fields_and_leaves_all_four_null_when_absent(
    tmp_root: Path, repo: Path
):
    """Proves the absent-versus-real pair on `gr_run`'s four round columns.

    Two ingests into two stores. One payload carries all four (as the
    workflow now emits them) and every column comes back populated,
    `new_rules_in_final_round` included at a real `0`. The other carries none
    and every column comes back NULL -- not `0`, not `''`. The pair is the
    point: if absence and a measured zero shared an encoding, no reader could
    tell a run that ran dry from a run whose workflow never reported how it
    ended. Read back through `KnowledgeStore.list_gr_runs()`, which is the
    surface `stats` uses.
    """
    from legacylift_search.gr_ingest import ingest_extraction

    def ingest(store_dir: str, **extra) -> GRRun:
        store = KnowledgeStore(tmp_root / store_dir / "knowledge.sqlite")
        try:
            payload = {
                "system": "demo",
                "confirmedRules": [_rule()],
                "rejectedRules": [],
                "injectionFlags": [],
            }
            payload.update(extra)
            ingest_extraction(
                store,
                payload,
                repo,
                index_sqlite_path=tmp_root / "index" / "index.sqlite",
                on_notice=lambda _m: None,
            )
            runs = store.list_gr_runs()
            assert len(runs) == 1
            return runs[0]
        finally:
            store.close()

    real = ingest(
        "with",
        rounds=3,
        roundCap=8,
        stopReason="dry",
        newRulesInFinalRound=0,
    )
    assert real.rounds_run == 3
    assert real.round_cap == 8
    assert real.stop_reason == "dry"
    # A measured zero, and it must survive as one.
    assert real.new_rules_in_final_round == 0

    absent = ingest("without")
    assert absent.rounds_run is None
    assert absent.round_cap is None
    assert absent.stop_reason is None
    assert absent.new_rules_in_final_round is None
    # Not falsy-equal: `0` is falsy and `0` is the encoding that must not appear.
    assert absent.new_rules_in_final_round is not False


# ----------------------------------------------------------------------
# `requirements stats`
# ----------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_repo():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        yield root, root / "analysis"


def _open_store(repo_root: Path, analysis_dir: Path) -> KnowledgeStore:
    paths = resolve_requirements_paths(
        repo_root, None, analysis_dir, print_banner=False
    )
    return KnowledgeStore(paths.knowledge_sqlite_path)


def _stats(runner: CliRunner, repo_root: Path, analysis_dir: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "requirements",
            "stats",
            *extra,
            "--repo-root",
            str(repo_root),
            "--analysis-dir",
            str(analysis_dir),
        ],
    )


def _seed_two_runs(repo_root: Path, analysis_dir: Path) -> None:
    """One run with all four figures recorded, one with none of them."""
    store = _open_store(repo_root, analysis_dir)
    try:
        store.insert_gr_run(
            GRRun(
                run_id="RUN-CAPPED",
                system="demo",
                rounds_run=4,
                round_cap=4,
                stop_reason="round_cap",
                new_rules_in_final_round=0,
            )
        )
        store.insert_gr_run(
            GRRun(run_id="RUN-UNREPORTED", system="demo")
        )
        store.commit()
    finally:
        store.close()


def test_stats_prints_all_four_round_fields_per_run(runner, cli_repo):
    """Proves Step 10's four figures reach the text report, per run.

    Step 10 requires them "surfaced in `requirements stats`". A figure stored
    and never displayed is a figure nobody reads, and the point of recording
    how a run ended is that a reader can tell a swept corpus from a truncated
    one.
    """
    root, analysis = cli_repo
    _seed_two_runs(root, analysis)
    result = _stats(runner, root, analysis)
    assert result.exit_code == 0, result.stdout + result.stderr
    text = result.stdout
    assert "stop_reason=round_cap" in text
    assert "rounds_run=4" in text
    assert "round_cap=4" in text
    assert "new_rules_in_final_round=0" in text


def test_stats_prints_unmeasured_not_zero_for_a_null_round_field(runner, cli_repo):
    """Proves a NULL round column prints as `unmeasured`, never `0` or blank.

    `RUN-UNREPORTED` was ingested from a payload carrying none of the four,
    so all four are NULL and the honest rendering is the module's established
    `UNMEASURED` vocabulary -- the same word `not_accounted_for` already
    uses, not a second spelling. `new_rules_in_final_round=0` on this run
    would claim its final round found nothing new, which is the `'dry'`
    signal, about a run whose termination is entirely unrecorded.
    """
    root, analysis = cli_repo
    _seed_two_runs(root, analysis)
    text = _stats(runner, root, analysis).stdout

    unreported = text.split("RUN-UNREPORTED", 1)[1]
    for field in ("stop_reason", "rounds_run", "round_cap", "new_rules_in_final_round"):
        assert f"{field}=unmeasured" in unreported
        assert f"{field}=0" not in unreported
        assert f"{field}= " not in unreported
        assert f"{field}=\n" not in unreported

    # The report must also SAY what unmeasured means here, or the word is a
    # sentinel a reader has to guess at.
    assert "how the loop ended is unrecorded" in text
    # And it must say what each stop_reason implies, because 'round_cap' and
    # 'budget_exhausted' make the corpus a floor rather than a sweep.
    assert "floor, not a sweep" in text


def test_stats_json_carries_a_real_null_for_an_unreported_round_field(
    runner, cli_repo
):
    """Proves `--json` emits `null`, not `"None"` and not a text sentinel.

    `UNMEASURED` is a *text* rendering. Leaking it into JSON, or
    stringifying `None`, would put the absent bucket in the same namespace as
    a real value -- the same collision the module's grouped counts avoid by
    serializing as `{value, count}` lists rather than as objects keyed by the
    value, since JSON has no null key.
    """
    root, analysis = cli_repo
    _seed_two_runs(root, analysis)
    result = _stats(runner, root, analysis, "--json")
    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    runs = {r["run_id"]: r for r in payload["runs"]}

    capped = runs["RUN-CAPPED"]
    assert capped["rounds_run"] == 4
    assert capped["round_cap"] == 4
    assert capped["stop_reason"] == "round_cap"
    assert capped["new_rules_in_final_round"] == 0

    unreported = runs["RUN-UNREPORTED"]
    for field in ("rounds_run", "round_cap", "stop_reason", "new_rules_in_final_round"):
        assert unreported[field] is None, field
        assert unreported[field] != "None"
        assert unreported[field] != "unmeasured"

    # And the banner stayed off stdout, or a parsing caller is broken
    # regardless of what the fields say (house rule 4).
    assert "knowledge" not in result.stdout.splitlines()[0]


def test_stats_reports_no_raw_gr_sql_was_added_to_the_cli_for_this(runner, cli_repo):
    """Proves the four figures are read through `KnowledgeStore`, not new SQL.

    House rule 1: all raw SQL against the `gr` tables lives in
    `knowledge_store.py`. The four columns arrive via
    `KnowledgeStore.list_gr_runs()` and `GRRun`, so `read_cmds.py` must
    mention none of them in a SQL statement. Asserted over the parsed source
    -- `ast`, not a text grep, because prose describing a construct is not
    the construct.
    """
    import ast

    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legacylift_search"
        / "cli_requirements"
        / "read_cmds.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    for text in literals:
        if text in docstrings:
            continue
        lowered = text.lower()
        assert "from gr_run" not in lowered
        assert "select" not in lowered or "gr_run" not in lowered
