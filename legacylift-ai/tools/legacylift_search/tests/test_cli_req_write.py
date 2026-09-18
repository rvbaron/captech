"""Tests for `requirements set-state` and `requirements set-field`.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md` -- the
two human write commands, exercised **through the real registration**
(`CliRunner` against `legacylift_search.cli:app` with
`["requirements", "set-state", ...]`) rather than against the sub-app in
isolation, so a command that failed to register fails these tests.

Every test here is a probe rather than an inspection: this plan's history is
nine review rounds in which a green suite hid a live defect twice, and both
times the passing test asserted something about the code instead of about
what the code did. So the assertions read the `gr` row back, or read the exit
code, or read what the command printed.

Two conventions worth stating once. **The human-readable report goes to
stderr and `--json` goes to stdout**, so a test asserting on wording reads
`result.stderr` and a test asserting on JSON reads `result.stdout`; click
8.4's `CliRunner` keeps the two apart. And the reviewer environment variable
is cleared for every test by an autouse fixture, because an ambient
`LEGACYLIFT_REVIEWER` on a developer's machine would silently satisfy the
"refuses to run without a reviewer" criterion and make that test vacuous.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.cli_requirements.write_cmds import REVIEWER_ENV_VAR
from legacylift_search.gr_fields import HUMAN_WRITABLE_FIELDS
from legacylift_search.knowledge_store import KnowledgeStore
from tests.test_gr_state import insert_gr

#: A statement that satisfies every SPEC-1 check the validator can run
#: against a `behavioral` / `B-UNCOND` rule carrying an `enforcement_level`
#: -- verified by probe, not by reading the checks: it yields zero findings.
GOOD_STATEMENT = "The Order Service must record a vendor number on each order."

#: The same sentence with the modal keyword removed. `V-KW-01` fires as an
#: evaluated `ERROR`, which is exactly what the `-> approved` gate refuses,
#: and the three `V-SLOT` checks come back `evaluated = 0` because the
#: template's keyword is no longer unambiguously present.
KEYWORDLESS_STATEMENT = "The Order Service records a vendor number on each order."

SECOND_ID = "GR-01HQ2X0000000000000000009"


@pytest.fixture(autouse=True)
def _no_ambient_reviewer(monkeypatch):
    """Clear `$LEGACYLIFT_REVIEWER` so the refusal tests are not vacuous."""
    monkeypatch.delenv(REVIEWER_ENV_VAR, raising=False)


@pytest.fixture
def repo(tmp_path):
    """A repository root with no knowledge store yet. `--repo-root` takes it."""
    root = tmp_path / "repo"
    root.mkdir()
    return root


def knowledge_path(repo):
    """Where `resolve_knowledge_dir` puts the store for a bare repo root."""
    return repo / "legacylift-docs" / "knowledge" / "knowledge.sqlite"


def seed(repo, **overrides):
    """Create the store and one `gr` row, returning its `gr_id`.

    Defaults to the approvable shape `tests/test_gr_state.insert_gr` builds
    (`behavioral` / `B-UNCOND`) plus an `enforcement_level`, which is what
    takes the record to *zero* findings rather than one `V-ENF-03` WARN --
    tests about the gate want the finding they introduce to be the only one.
    """
    store = KnowledgeStore(knowledge_path(repo))
    try:
        row = {"enforcement_level": "strict", "statement": GOOD_STATEMENT}
        row.update(overrides)
        return insert_gr(store._connect(), **row)
    finally:
        store.close()


def read(repo, gr_id):
    """Read one `gr` row back through a freshly opened store."""
    store = KnowledgeStore(knowledge_path(repo))
    try:
        return store.get_gr(gr_id)
    finally:
        store.close()


def run(repo, *args, provider="nope"):
    """Invoke a `requirements` subcommand against `repo`.

    `provider="nope"` is the default because an unbuildable provider is the
    fast path *and* the interesting one: `build_embedder` returns
    `(None, reason)`, `refresh_gr_vectors` short-circuits without touching
    Chroma, and the degraded-but-zero-exit contract is what most of these
    tests are about. Tests that need a real embedder pass `provider="hash"`.
    """
    argv = list(args) + ["--repo-root", str(repo)]
    if provider is not None:
        argv += ["--embedding-provider", provider]
    return CliRunner().invoke(app, ["requirements"] + argv)


# ----------------------------------------------------------------------
# set-state: the review act
# ----------------------------------------------------------------------


def test_the_review_act_is_fully_recorded(repo):
    """`--to approved --reviewer X --note ...` populates all three columns.

    The ninth-round acceptance criterion. Proves the command threads
    `--reviewer` into `reviewed_by` and `--note` into `review_note`, and that
    `reviewed_at` is stamped -- the triple that makes the approved corpus
    able to say who approved each record.
    """
    gr_id = seed(repo)
    result = run(
        repo,
        "set-state",
        gr_id,
        "--to",
        "approved",
        "--reviewer",
        "dana@example.com",
        "--note",
        "read the calculation against the DDL",
    )
    assert result.exit_code == 0, result.stderr
    record = read(repo, gr_id)
    assert record.state == "approved"
    assert record.reviewed_by == "dana@example.com"
    assert record.reviewed_at
    assert record.review_note == "read the calculation against the DDL"


def test_a_second_set_state_to_the_same_state_changes_none_of_the_three(repo):
    """The same-state no-op stamps nothing and bumps nothing.

    Second half of the ninth-round criterion, and the value-changing-write
    rule: a re-run must not overwrite `reviewed_by`/`reviewed_at`/
    `review_note` with a different reviewer's name, nor bump `updated_at` --
    which is in the JSONL export, so a bumped one shows an untouched record
    as modified in the next pull request.
    """
    gr_id = seed(repo)
    assert (
        run(
            repo,
            "set-state",
            gr_id,
            "--to",
            "approved",
            "--reviewer",
            "dana@example.com",
            "--note",
            "first pass",
        ).exit_code
        == 0
    )
    first = read(repo, gr_id)

    result = run(
        repo,
        "set-state",
        gr_id,
        "--to",
        "approved",
        "--reviewer",
        "someone-else@example.com",
        "--note",
        "clobber attempt",
    )
    assert result.exit_code == 0, result.stderr
    assert "no-op" in result.stderr

    second = read(repo, gr_id)
    assert second.reviewed_by == first.reviewed_by == "dana@example.com"
    assert second.reviewed_at == first.reviewed_at
    assert second.review_note == first.review_note == "first pass"
    assert second.updated_at == first.updated_at


def test_set_field_refuses_the_three_review_columns_by_store_ownership(repo):
    """`set-field` cannot forge a review: the triple is STORE_OWNED.

    Third half of the ninth-round criterion. The refusal must be *by
    membership* in `STORE_OWNED_FIELDS`, so the message says which set the
    column is in rather than reading like a hand-maintained denial list.
    """
    gr_id = seed(repo)
    for column in ("reviewed_by", "reviewed_at", "review_note"):
        result = run(
            repo, "set-field", gr_id, "--field", column, "--value", "forged"
        )
        assert result.exit_code != 0, column
        assert "STORE_OWNED" in result.stderr, column
        assert "set-state" in result.stderr, column
    record = read(repo, gr_id)
    assert record.reviewed_by is None
    assert record.reviewed_at is None
    assert record.review_note is None


@pytest.mark.parametrize("column", ["state", "dedupe_key", "dedupe_key_anchor_only"])
def test_set_field_refuses_state_and_both_dedupe_keys(repo, column):
    """`set-field` never writes `gr.state` and never edits a dedupe key.

    `state` is `set-state`'s alone because the approval gate lives there, and
    a hand-edited dedupe key would silently re-partition the merge. Both are
    refused by which ownership set they are in, not by a special case.
    """
    gr_id = seed(repo)
    result = run(repo, "set-field", gr_id, "--field", column, "--value", "approved")
    assert result.exit_code != 0
    assert "STORE_OWNED" in result.stderr
    assert read(repo, gr_id).state == "draft"


def test_set_field_refuses_an_extractor_owned_shadow_column(repo):
    """A `_extracted` shadow is refused because it is EXTRACTOR_OWNED.

    The live column is writable and its shadow is not, which is the whole
    mechanism by which a human edit survives re-extraction.
    """
    gr_id = seed(repo)
    result = run(
        repo, "set-field", gr_id, "--field", "statement_extracted", "--value", "x"
    )
    assert result.exit_code != 0
    assert "EXTRACTOR_OWNED" in result.stderr
    assert read(repo, gr_id).statement_extracted == GOOD_STATEMENT


# ----------------------------------------------------------------------
# set-state: the gate
# ----------------------------------------------------------------------


def test_the_gate_names_the_blocking_finding_then_lets_it_through_once_fixed(repo):
    """The gate refuses, names the finding by identifier, and later relents.

    The headline acceptance criterion for `set-state`, end to end and through
    the CLI in both directions: a `set-field` edit to `statement` re-runs the
    validator (which is how the `ERROR` gets there at all), `--to approved`
    then exits non-zero naming `V-KW-01`, and the same command succeeds once
    a second `set-field` resolves it.
    """
    gr_id = seed(repo)
    edit = run(
        repo,
        "set-field",
        gr_id,
        "--field",
        "statement",
        "--value",
        KEYWORDLESS_STATEMENT,
    )
    assert edit.exit_code == 0, edit.stderr
    assert "V-KW-01" in edit.stderr

    refused = run(
        repo, "set-state", gr_id, "--to", "approved", "--reviewer", "dana@example.com"
    )
    assert refused.exit_code != 0
    assert "V-KW-01" in refused.stderr
    assert read(repo, gr_id).state == "draft"
    # A refused approval records nothing at all -- not even the attempt.
    assert read(repo, gr_id).reviewed_by is None

    fixed = run(
        repo, "set-field", gr_id, "--field", "statement", "--value", GOOD_STATEMENT
    )
    assert fixed.exit_code == 0, fixed.stderr

    allowed = run(
        repo, "set-state", gr_id, "--to", "approved", "--reviewer", "dana@example.com"
    )
    assert allowed.exit_code == 0, allowed.stderr
    assert read(repo, gr_id).state == "approved"


def test_a_null_pattern_is_refused_for_approval_and_pointed_at_set_field(repo):
    """The `pattern IS NOT NULL` precondition surfaces as words, not a CHECK.

    A raw `CHECK constraint failed` names no column and no remedy; the
    refusal must name `pattern` and the command that sets one.
    """
    gr_id = seed(repo, rule_class=None, pattern=None)
    result = run(
        repo, "set-state", gr_id, "--to", "approved", "--reviewer", "dana@example.com"
    )
    assert result.exit_code != 0
    assert "pattern" in result.stderr
    assert "set-field" in result.stderr
    assert read(repo, gr_id).state == "draft"


def test_a_blocked_approval_reports_the_findings_in_json_too(repo):
    """`--json` carries the blocking findings, so a caller can act on them.

    The identifier has to be machine-readable as well as printed: a wrapper
    that only got a non-zero exit code cannot tell an approval blocked by a
    finding apart from an illegal transition.
    """
    gr_id = seed(repo)
    run(
        repo,
        "set-field",
        gr_id,
        "--field",
        "statement",
        "--value",
        KEYWORDLESS_STATEMENT,
    )
    result = run(
        repo,
        "set-state",
        gr_id,
        "--to",
        "approved",
        "--reviewer",
        "dana@example.com",
        "--json",
    )
    assert result.exit_code != 0
    payload = json.loads(result.stdout)
    assert payload["refused"] == "approval_blocked"
    assert payload["changed"] is False
    assert [f["finding_id"] for f in payload["blocking_findings"]] == ["V-KW-01"]


# ----------------------------------------------------------------------
# set-state: the reviewer identity
# ----------------------------------------------------------------------


def test_missing_reviewer_refuses_to_run(repo):
    """With no `--reviewer` and no env var, the command refuses.

    The 2026-08-25 review criterion. It must refuse *before* writing, and the
    message must name both places a reviewer could have come from -- an
    identity is the one thing in this schema that cannot be reconstructed
    after the fact, so there is deliberately no placeholder.
    """
    gr_id = seed(repo)
    result = run(repo, "set-state", gr_id, "--to", "approved")
    assert result.exit_code != 0
    assert "--reviewer" in result.stderr
    assert REVIEWER_ENV_VAR in result.stderr
    assert read(repo, gr_id).state == "draft"


def test_a_whitespace_only_reviewer_is_refused(repo):
    """`--reviewer "   "` is absent, not present. It cannot be smuggled past."""
    gr_id = seed(repo)
    result = run(repo, "set-state", gr_id, "--to", "approved", "--reviewer", "   ")
    assert result.exit_code != 0
    assert read(repo, gr_id).reviewed_by is None


def test_the_env_var_supplies_the_reviewer_when_the_flag_is_absent(
    repo, monkeypatch
):
    """`$LEGACYLIFT_REVIEWER` is the one configured default, and it is used.

    The plan requires a *configured* fallback and forbids a placeholder;
    `Manifest` carries no reviewer setting, so this variable is it. Git's
    committer identity is deliberately not consulted -- see the module
    docstring of `write_cmds.py`.
    """
    monkeypatch.setenv(REVIEWER_ENV_VAR, "  ops@example.com  ")
    gr_id = seed(repo)
    result = run(repo, "set-state", gr_id, "--to", "reviewed")
    assert result.exit_code == 0, result.stderr
    assert read(repo, gr_id).reviewed_by == "ops@example.com"


def test_the_flag_wins_over_the_env_var(repo, monkeypatch):
    """An explicit `--reviewer` overrides the configured default."""
    monkeypatch.setenv(REVIEWER_ENV_VAR, "ops@example.com")
    gr_id = seed(repo)
    assert (
        run(
            repo,
            "set-state",
            gr_id,
            "--to",
            "reviewed",
            "--reviewer",
            "dana@example.com",
        ).exit_code
        == 0
    )
    assert read(repo, gr_id).reviewed_by == "dana@example.com"


# ----------------------------------------------------------------------
# set-state: supersession
# ----------------------------------------------------------------------


def test_superseded_without_a_successor_is_refused(repo):
    """`--to superseded` with no `--superseded-by` refuses rather than writes.

    A `superseded` row with a NULL `superseded_by` is a dead end: the state
    is terminal, so the question "what replaced this?" would be permanently
    unanswerable.
    """
    gr_id = seed(repo, state="approved")
    result = run(
        repo,
        "set-state",
        gr_id,
        "--to",
        "superseded",
        "--reviewer",
        "dana@example.com",
    )
    assert result.exit_code != 0
    assert "successor" in result.stderr
    assert read(repo, gr_id).state == "approved"


def test_superseded_sets_superseded_by_and_leaves_derived_from_untouched(repo):
    """The successor lands in `superseded_by`, never in `derived_from`.

    `derived_from` means "the rules this rollup summarizes" and nothing else;
    mixing supersession into it would give the array two meanings with no
    discriminator, and Milestone 2's rollup query would silently collect
    replacement links alongside constituent rules.
    """
    derived = '["GR-01HQ2X0000000000000000111"]'
    gr_id = seed(repo, state="approved", derived_from=derived)
    store = KnowledgeStore(knowledge_path(repo))
    try:
        insert_gr(store._connect(), gr_id=SECOND_ID, statement=GOOD_STATEMENT)
    finally:
        store.close()

    result = run(
        repo,
        "set-state",
        gr_id,
        "--to",
        "superseded",
        "--reviewer",
        "dana@example.com",
        "--superseded-by",
        SECOND_ID,
    )
    assert result.exit_code == 0, result.stderr
    record = read(repo, gr_id)
    assert record.state == "superseded"
    assert record.superseded_by == SECOND_ID
    assert record.derived_from == derived


# ----------------------------------------------------------------------
# set-state: the transition graph, routed rather than re-implemented
# ----------------------------------------------------------------------


def test_an_illegal_transition_exits_non_zero_naming_both_states(repo):
    """`StateTransitionError` reaches the exit code and keeps its wording.

    `superseded` is terminal, so `superseded -> draft` is refused. The CLI's
    job is to route the error, not to own a second copy of the graph, and the
    message it prints has to still name both states for a reader to act on.
    """
    gr_id = seed(repo, state="superseded")
    result = run(
        repo, "set-state", gr_id, "--to", "draft", "--reviewer", "dana@example.com"
    )
    assert result.exit_code != 0
    assert "superseded" in result.stderr
    assert "draft" in result.stderr
    assert read(repo, gr_id).state == "superseded"


def test_an_unknown_state_exits_non_zero_without_writing(repo):
    """A misspelled `--to` is refused by `set_state`, not written."""
    gr_id = seed(repo)
    result = run(
        repo,
        "set-state",
        gr_id,
        "--to",
        "signed-off",
        "--reviewer",
        "dana@example.com",
    )
    assert result.exit_code != 0
    assert "unknown state" in result.stderr
    assert read(repo, gr_id).state == "draft"


def test_an_unknown_requirement_exits_non_zero(repo):
    """A `gr_id` that is not in the store is reported, not created."""
    seed(repo)
    result = run(
        repo,
        "set-state",
        "GR-nope",
        "--to",
        "approved",
        "--reviewer",
        "dana@example.com",
    )
    assert result.exit_code != 0
    assert "GR-nope" in result.stderr


# ----------------------------------------------------------------------
# Both commands: the store probe, JSON routing, and degraded vectors
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ("set-state", "GR-x", "--to", "approved", "--reviewer", "dana@example.com"),
        ("set-field", "GR-x", "--field", "owner", "--value", "dana"),
    ],
)
def test_a_missing_store_exits_non_zero_and_creates_nothing(repo, argv):
    """Neither command may materialize an empty knowledge store.

    House rule 2 as a probe rather than as a source inspection:
    `KnowledgeStore.__init__` creates the file *and its parent directory*, so
    a command that constructed one to find out whether requirements exist
    would leave an empty database that is indistinguishable from a real one
    on the next command. Both of these operate on an existing store, so both
    go through `_shared.open_knowledge_store`.
    """
    result = run(repo, *argv)
    assert result.exit_code != 0
    assert not knowledge_path(repo).exists()


def test_set_state_json_goes_to_stdout_and_the_banner_to_stderr(repo):
    """`--json` output is parseable because the banner is on stderr.

    House rule 4. `resolve_requirements_paths` prints two resolved-path
    banners, and either one on stdout would break every caller parsing it.
    """
    gr_id = seed(repo)
    result = run(
        repo,
        "set-state",
        gr_id,
        "--to",
        "approved",
        "--reviewer",
        "dana@example.com",
        "--note",
        "signed off",
        "--json",
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is True
    assert payload["from_state"] == "draft"
    assert payload["to_state"] == "approved"
    assert payload["reviewed_by"] == "dana@example.com"
    assert payload["review_note"] == "signed off"
    assert "resolved knowledge directory" in result.stderr


def test_set_field_json_goes_to_stdout_and_the_banner_to_stderr(repo):
    """The same routing for `set-field`, including the findings list."""
    gr_id = seed(repo)
    result = run(
        repo,
        "set-field",
        gr_id,
        "--field",
        "statement",
        "--value",
        KEYWORDLESS_STATEMENT,
        "--json",
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is True
    assert payload["validated"] is True
    assert payload["new_value"] == KEYWORDLESS_STATEMENT
    assert [f["finding_id"] for f in payload["blocking_findings"]] == ["V-KW-01"]
    # `evaluated` travels beside `severity` rather than folded into it: the
    # three V-SLOT ERRORs here could not be decided and did not fail.
    unevaluated = [f for f in payload["findings"] if not f["evaluated"]]
    assert unevaluated and all(f["severity"] == "ERROR" for f in unevaluated)
    assert "resolved knowledge directory" in result.stderr


@pytest.mark.parametrize(
    "argv",
    [
        ("set-state", "--to", "approved", "--reviewer", "dana@example.com"),
        ("set-field", "--field", "owner", "--value", "dana"),
    ],
)
def test_an_unreachable_embedding_provider_still_records_and_exits_zero(repo, argv):
    """A missing embedder is a degraded success, named, exiting **zero**.

    An unreachable embedding provider must never be a reason a human's
    recorded judgement or edit fails, and the message must name
    `requirements reindex-vectors` as the one documented recovery -- a
    non-zero exit here reads as "the write failed" and invites re-running an
    extraction to recover something that was never lost.
    """
    gr_id = seed(repo)
    head, *rest = argv
    result = run(repo, head, gr_id, *rest, provider="not-a-provider")
    assert result.exit_code == 0, result.stderr
    assert "reindex-vectors" in result.stderr
    assert "semantic half" in result.stderr


def test_a_working_embedder_reports_no_degradation(repo):
    """With a real embedder the write reports no shortfall at all.

    The complement of the degraded test: without it, "reindex-vectors is
    never mentioned" would be indistinguishable from "the reporting is
    broken". Uses the `hash` provider, which needs no network.
    """
    pytest.importorskip("chromadb")
    gr_id = seed(repo)
    result = run(
        repo,
        "set-field",
        gr_id,
        "--field",
        "owner",
        "--value",
        "dana@example.com",
        provider="hash",
    )
    assert result.exit_code == 0, result.stderr
    assert "reindex-vectors" not in result.stderr
    assert read(repo, gr_id).owner == "dana@example.com"


# ----------------------------------------------------------------------
# set-field: the nine human-writable fields, and the two key inputs
# ----------------------------------------------------------------------

#: The value each human-writable column is set to, plus the starting row
#: shape that makes the write legal. `rule_class` needs a row with no
#: `pattern`, because `definitional` alongside a `B-*` pattern is refused by
#: the table CHECK that partitions the ten patterns by class.
_HUMAN_WRITES = {
    "rule_class": (
        "definitional",
        {"rule_class": None, "pattern": None, "enforcement_level": None},
    ),
    "pattern": ("B-COND", {}),
    "enforcement_level": ("guideline", {}),
    "confidence_intent": ("Medium", {}),
    "disposition": ("captured", {}),
    "modality_confirmed": ("1", {}),
    "rationale": ("the vendor number is the audit key", {}),
    "fit_criterion": ("every order row has a non-null vendor number", {}),
    "owner": ("dana@example.com", {}),
}


def test_the_write_table_covers_every_human_writable_field():
    """The parametrization is derived from the constant, so it cannot drift.

    A hand-listed set of nine would silently stop covering a tenth column the
    moment `HUMAN_WRITABLE_FIELDS` gained one -- the stale-copy defect this
    plan was bitten by six times.
    """
    assert set(_HUMAN_WRITES) == set(HUMAN_WRITABLE_FIELDS)


@pytest.mark.parametrize("field", sorted(_HUMAN_WRITES))
def test_every_human_writable_field_is_settable_through_the_command(repo, field):
    """All nine, `owner` included, reach the column via `set-field`.

    `PR-45`'s criterion needs every one of the nine to be writable before it
    can ask whether they survive re-extraction, and `owner` in particular had
    no writer at all until `PR-81`: Step 3 introduced it as human-owned and
    merge-protected, but `set_state` writes only `reviewed_by`, so the column
    was unreachable and its audit claim unachievable.
    """
    value, overrides = _HUMAN_WRITES[field]
    gr_id = seed(repo, **overrides)
    result = run(repo, "set-field", gr_id, "--field", field, "--value", value)
    assert result.exit_code == 0, result.stderr
    stored = getattr(read(repo, gr_id), field)
    expected = True if field == "modality_confirmed" else value
    assert stored == expected


@pytest.mark.parametrize(
    "field,value,overrides",
    [
        ("pattern", "B-COND", {}),
        ("rule_class", "behavioral", {"rule_class": None, "pattern": None}),
    ],
)
def test_writing_a_key_input_leaves_both_dedupe_keys_byte_identical(
    repo, field, value, overrides
):
    """`rule_class` and `pattern` are key inputs and must not move a key.

    The fifth-round criterion, and the assertion that fails if someone wires
    key recomputation into `set-field`. Keys move only on extractor-owned
    writes: these two are the only human-writable key inputs and so the only
    place that rule is easy to break.
    """
    gr_id = seed(repo, **overrides)
    before = read(repo, gr_id)
    result = run(repo, "set-field", gr_id, "--field", field, "--value", value)
    assert result.exit_code == 0, result.stderr
    after = read(repo, gr_id)
    assert getattr(after, field) == value
    assert after.dedupe_key == before.dedupe_key
    assert after.dedupe_key_anchor_only == before.dedupe_key_anchor_only


# ----------------------------------------------------------------------
# set-field: NULL versus the empty string
# ----------------------------------------------------------------------


def test_null_and_the_empty_string_are_two_different_writes(repo):
    """`--null` writes SQL NULL; `--value ""` writes `''`. Both are reachable.

    The distinction the CLI exists to express: `assumptions = ''` means "the
    agent considered assumptions and had none" while NULL means the field
    never arrived, which is why the shadow equality is `IS` and not `=` and
    why the fill-rate figures report three numbers instead of a rate. A
    command that could only send a string would make NULL unreachable and one
    of those two facts unrepresentable.
    """
    gr_id = seed(repo)
    assert read(repo, gr_id).assumptions is None

    empty = run(repo, "set-field", gr_id, "--field", "assumptions", "--value", "")
    assert empty.exit_code == 0, empty.stderr
    assert read(repo, gr_id).assumptions == ""

    cleared = run(repo, "set-field", gr_id, "--field", "assumptions", "--null")
    assert cleared.exit_code == 0, cleared.stderr
    assert read(repo, gr_id).assumptions is None


def test_value_and_null_together_are_refused(repo):
    """The two flags mean different things, so asking for both is ambiguous."""
    gr_id = seed(repo)
    result = run(
        repo, "set-field", gr_id, "--field", "assumptions", "--value", "x", "--null"
    )
    assert result.exit_code != 0
    assert "mutually exclusive" in result.stderr
    assert read(repo, gr_id).assumptions is None


def test_neither_value_nor_null_is_refused(repo):
    """Omitting both is a usage error, not an implicit clear.

    If a bare `set-field --field assumptions` silently wrote NULL, a
    mistyped command would clear a column instead of failing.
    """
    gr_id = seed(repo, assumptions="considered")
    result = run(repo, "set-field", gr_id, "--field", "assumptions")
    assert result.exit_code != 0
    assert "required" in result.stderr
    assert read(repo, gr_id).assumptions == "considered"


def test_null_on_a_not_null_column_is_refused_naming_the_column(repo):
    """Clearing `statement` is refused by name, not by a CHECK failure."""
    gr_id = seed(repo)
    result = run(repo, "set-field", gr_id, "--field", "statement", "--null")
    assert result.exit_code != 0
    assert "statement" in result.stderr
    assert "NOT NULL" in result.stderr
    assert read(repo, gr_id).statement == GOOD_STATEMENT


def test_the_null_help_text_says_which_flag_writes_which(repo):
    """The help distinguishes the two, because nothing else can.

    A user cannot discover the NULL-versus-`''` distinction from the schema,
    and picking the wrong one silently records the wrong fact. So the help
    text for both flags names the other one and says what each means.
    """
    result = CliRunner().invoke(app, ["requirements", "set-field", "--help"])
    assert result.exit_code == 0
    text = " ".join(result.output.split())
    assert "--null" in text
    assert "empty string" in text
    assert "NULL" in text


# ----------------------------------------------------------------------
# set-field: validation, the no-op, and the findings report
# ----------------------------------------------------------------------


def test_a_value_outside_the_schemas_check_is_refused_naming_the_legal_set(repo):
    """A bad enum value is refused at the command, with the legal values.

    The plan mandates this specifically: a raw `CHECK constraint failed`
    names neither the column nor the legal values, and this command's whole
    audience is a human typing a value at a shell.
    """
    gr_id = seed(repo)
    result = run(repo, "set-field", gr_id, "--field", "disposition", "--value", "maybe")
    assert result.exit_code != 0
    assert "captured" in result.stderr
    assert read(repo, gr_id).disposition is None


def test_a_cross_column_check_is_refused_at_the_command(repo):
    """An `enforcement_level` on a `definitional` rule is refused with a reason.

    One of the two worked examples in the plan, and the case a single-column
    validator would miss: the prospective row is what violates the CHECK, not
    the value on its own.
    """
    gr_id = seed(
        repo, rule_class="definitional", pattern="D-NEC", enforcement_level=None
    )
    result = run(
        repo, "set-field", gr_id, "--field", "enforcement_level", "--value", "strict"
    )
    assert result.exit_code != 0
    assert "definitional" in result.stderr
    assert read(repo, gr_id).enforcement_level is None


def test_a_pattern_disagreeing_with_rule_class_is_refused(repo):
    """The ten patterns are partitioned by class, so `behavioral` + `D-*` fails."""
    gr_id = seed(repo)
    result = run(repo, "set-field", gr_id, "--field", "pattern", "--value", "D-NEC")
    assert result.exit_code != 0
    assert "disagree" in result.stderr
    assert read(repo, gr_id).pattern == "B-UNCOND"


def test_an_unknown_field_prints_the_accepted_list(repo):
    """An unrecognized `--field` is how a user discovers the twelve columns.

    The help text deliberately does not restate the list -- a hand-copied one
    would drift from `gr_fields` -- so the refusal has to carry it.
    """
    gr_id = seed(repo)
    result = run(repo, "set-field", gr_id, "--field", "nonsense", "--value", "x")
    assert result.exit_code != 0
    for column in HUMAN_WRITABLE_FIELDS:
        assert column in result.stderr
    for shadowed in ("statement", "assumptions", "modality"):
        assert shadowed in result.stderr


def test_a_no_op_write_says_so_and_does_not_bump_updated_at(repo):
    """Writing the value the row already holds writes nothing and reports it.

    `updated_at` is in the JSONL export, so a no-op that bumped it would show
    every touched record as modified in the next pull request -- and a report
    that called it a successful write would make the export's byte-identity
    property look broken to whoever checked it next.
    """
    gr_id = seed(repo, owner="dana@example.com")
    before = read(repo, gr_id)
    result = run(
        repo, "set-field", gr_id, "--field", "owner", "--value", "dana@example.com"
    )
    assert result.exit_code == 0, result.stderr
    assert "no-op" in result.stderr
    assert "validator did not re-run" in result.stderr
    assert read(repo, gr_id).updated_at == before.updated_at


def test_the_no_op_path_reports_validated_false_in_json(repo):
    """`validated` says whether the validator ran, apart from what it found.

    "No findings changed" and "the validator did not run" are different
    facts, and a caller that could not tell them apart would read a stale
    findings list as a fresh verdict.
    """
    gr_id = seed(repo, owner="dana@example.com")
    result = run(
        repo,
        "set-field",
        gr_id,
        "--field",
        "owner",
        "--value",
        "dana@example.com",
        "--json",
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is False
    assert payload["validated"] is False


def test_the_findings_are_reported_after_the_write(repo):
    """Editing `statement` re-runs the validator and the command says what fired.

    Setting a `pattern` or editing a `statement` changes the findings, and the
    reason `set-field` reports them is that the edit is the moment a reviewer
    can act on the change. `V-KW-01` must be labelled as blocking approval,
    because that is the consequence the reviewer needs to see.
    """
    gr_id = seed(repo)
    clean = run(repo, "set-field", gr_id, "--field", "owner", "--value", "dana")
    assert clean.exit_code == 0, clean.stderr
    assert "findings: none." in clean.stderr

    broken = run(
        repo,
        "set-field",
        gr_id,
        "--field",
        "statement",
        "--value",
        KEYWORDLESS_STATEMENT,
    )
    assert broken.exit_code == 0, broken.stderr
    assert "V-KW-01" in broken.stderr
    assert "BLOCKING" in broken.stderr
    assert "not evaluated" in broken.stderr
    assert "approval is blocked by V-KW-01" in broken.stderr


def test_setting_a_pattern_turns_a_slot_check_from_undecidable_into_a_verdict(repo):
    """`pattern` is what decides whether the V-SLOT checks can be decided.

    The fifth-round criterion that a rule the extractor left undecided can be
    settled by a human, from the validator's side: on a subject-less
    statement with a NULL `pattern` the three V-SLOT `ERROR`s are stored with
    `evaluated = 0` and their would-be severity intact, and setting
    `rule_class` and then `pattern` through `set-field` turns `V-SLOT-01`
    into a real verdict with a span pointing into the live text. The whole
    effect of that second write is in the re-run validator, which is why the
    command re-runs it rather than leaving findings stale.
    """
    subjectless = "must record a vendor number on each order."
    gr_id = seed(repo, rule_class=None, pattern=None, statement=subjectless)
    first = run(
        repo, "set-field", gr_id, "--field", "owner", "--value", "dana", "--json"
    )
    assert first.exit_code == 0, first.stderr
    undecided = {
        f["finding_id"]: f
        for f in json.loads(first.stdout)["findings"]
        if f["finding_id"].startswith("V-SLOT")
    }
    assert len(undecided) == 3
    assert all(not f["evaluated"] for f in undecided.values())
    assert all(f["severity"] == "ERROR" for f in undecided.values())

    assert (
        run(
            repo, "set-field", gr_id, "--field", "rule_class", "--value", "behavioral"
        ).exit_code
        == 0
    )
    result = run(
        repo, "set-field", gr_id, "--field", "pattern", "--value", "B-UNCOND", "--json"
    )
    assert result.exit_code == 0, result.stderr
    slots = [
        f
        for f in json.loads(result.stdout)["findings"]
        if f["finding_id"].startswith("V-SLOT")
    ]
    assert [f["finding_id"] for f in slots] == ["V-SLOT-01"]
    assert slots[0]["evaluated"] is True
    # A *missing* slot has nothing in the text to point at, so `V-SLOT-01`
    # arrives as a record-level finding whose span is the literal empty
    # string -- never NULL, because `span` is part of `gr_finding`'s
    # `UNIQUE (gr_id, finding_id, span)` and SQLite treats NULLs as distinct.
    # Asserted rather than skipped so that a span appearing here later is a
    # visible change and not a silent one.
    assert slots[0]["span"] == ""


def test_a_bad_boolean_for_modality_confirmed_is_refused(repo):
    """`modality_confirmed` takes a boolean word, and `0` is a real value.

    `0` means "no human has confirmed the modality" -- a fact, not a way of
    clearing the column -- so the refusal of a non-boolean has to name the
    words it does accept.
    """
    gr_id = seed(repo)
    result = run(
        repo, "set-field", gr_id, "--field", "modality_confirmed", "--value", "maybe"
    )
    assert result.exit_code != 0
    assert "boolean" in result.stderr
    assert read(repo, gr_id).modality_confirmed is False


def test_set_field_leaves_state_alone_on_every_accepted_write(repo):
    """No accepted `set-field` write moves the record out of `draft`.

    The gate lives in `set-state`, so `set-field` writing `state` as a side
    effect of anything would be a route around it. Probed across all nine
    human-writable columns rather than argued.
    """
    for n, (field, (value, overrides)) in enumerate(sorted(_HUMAN_WRITES.items())):
        gr_id = seed(repo, gr_id=f"GR-01HQ2X000000000000000000{n:02d}", **overrides)
        assert (
            run(repo, "set-field", gr_id, "--field", field, "--value", value).exit_code
            == 0
        ), field
        assert read(repo, gr_id).state == "draft", field
