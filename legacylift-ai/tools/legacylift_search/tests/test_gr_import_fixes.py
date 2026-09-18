"""Two Step 9 defects in `requirements import`, probed end to end.

Milestone 1, Step 9 of `docs/exec-plans/active/reqs-to-data-store.md`.

**Defect 1 — a refused downgrade had no encoding of its own.** `_import_one`
reverted `state`, `reviewed_by`, `reviewed_at`, `review_note` and
`superseded_by` to their stored values whenever `_is_state_downgrade` fired
without the flag, and nothing counted it. `rows_changed_state == 0` therefore
meant either "the file agreed with the store" or "every state change in the
file was refused" — the tenth instance of this plan's recurring defect class,
inside Step 9's own code. The tests below pin both readings apart, and pin
that a refusal names the record it protected rather than only counting it.

**Defect 2 — `import_records` had no `embedder` parameter.** It called
`refresh_gr_vectors(store, touched)` with no embedder, so `import`'s vector
half degraded *unconditionally* while every other write path in this
milestone threads the CLI-resolved embedder through the Step 5 pair. The
tests below pin the populated case, the degraded-but-zero-exit case, and that
`reindex-vectors` is still the recovery from the second.

Every test here is a probe: it reads the `gr` rows back, the ids in the
`gr_statements` collection, the exit code, or the bytes of the exported file
— never the source. Two conventions inherited from
`tests/test_cli_req_repair.py`, whose helpers this module reuses rather than
respelling: the report goes to stdout and the diagnostics to stderr, and a
bare `--repo-root` resolves the store to
`<repo>/legacylift-docs/knowledge/knowledge.sqlite`.

**The `hash` provider here is built at `manifest.embedding.dimension`, which
defaults to 1024 — not `HashEmbedder`'s own default of 64.** So every
collection this module opens is opened at 1024. A collection seeded at 64
would fail `validate_dimension` against the CLI's embedder on the next
command and the test would then measure a dimension mismatch instead of what
it claims. The repo root is pytest's `tmp_path` rather than a
`TemporaryDirectory`, which is the established pattern for this command group
and sidesteps Chroma's Windows handle-release problem entirely — pytest does
not remove the directory during the run.
"""

from __future__ import annotations

import json

import pytest

from legacylift_search.gr_export import IMPORT_GUARDRAILS, RefusedDowngrade
from tests.test_cli_req_repair import (
    SECOND_ID,
    export_path,
    open_store,
    read_row,
    run,
    seed,
    seed_incomplete,
)

#: The dimension the CLI's `hash` embedder is built at -- `EmbeddingConfig`'s
#: `dimension` default, NOT `HashEmbedder`'s. Asserted below rather than
#: trusted, because the two disagreeing is exactly the trap this module's
#: docstring describes.
HASH_DIMENSION = 1024


@pytest.fixture
def repo(tmp_path):
    """A repository root with no knowledge store yet. `--repo-root` takes it."""
    root = tmp_path / "repo"
    root.mkdir()
    return root


def collection_ids(repo):
    """Every id in `gr_statements`, read through a 1024-dim hash embedder.

    Opened at the dimension the CLI's `hash` provider uses, so this helper
    can never be the thing that creates (or validates against) a 64-dim
    collection. `get(include=[])` reads ids only, so no vector is computed.
    """
    from legacylift_search.embeddings import HashEmbedder
    from legacylift_search.gr_refresh import open_gr_collection

    store = open_store(repo)
    collection = None
    try:
        collection = open_gr_collection(store, HashEmbedder(dimension=HASH_DIMENSION))
        return sorted(collection.collection.get(include=[])["ids"])
    finally:
        if collection is not None:
            collection.close()
        store.close()


def approve(repo, gr_id, reviewer="A. Analyst"):
    """Move `gr_id` to `approved` through the real `set_state` path.

    Through `set_state` rather than a raw UPDATE so the approval under test
    is a real one: it went through the Step 4 gate and wrote the review
    columns the downgrade guard exists to defend.
    """
    from legacylift_search.gr_state import set_state

    store = open_store(repo)
    try:
        set_state(store, gr_id, "approved", reviewer)
    finally:
        store.close()


def supersede(repo, gr_id, successor, reviewer="A. Analyst"):
    """Move an approved `gr_id` to `superseded`, through `set_state`."""
    from legacylift_search.gr_state import set_state

    store = open_store(repo)
    try:
        set_state(store, gr_id, "superseded", reviewer, superseded_by=successor)
    finally:
        store.close()


# --------------------------------------------------------------------------
# Defect 1: a refused downgrade is counted and named
# --------------------------------------------------------------------------


def test_a_refused_downgrade_leaves_the_state_alone_and_reports_the_refusal(repo):
    """Proves the tenth instance of the recurring defect class is closed.

    A file carrying `draft` for a record the store has since approved must
    not lower it, and the refusal must be REPORTED -- non-zero, and
    distinguishable from a file that agreed with the store. Before this fix
    the revert was silent and `rows_changed_state == 0` was the only trace,
    which is the encoding a file-agreed-with-the-store import also produces.
    """
    (gr_id,) = seed(repo, rows=1, state="draft")
    run(repo, "export", provider=None)  # the file now carries state='draft'
    approve(repo, gr_id)
    assert read_row(repo, gr_id).state == "approved"

    result = run(repo, "import", "--json", provider="nope")
    assert result.exit_code == 0, result.stderr

    row = read_row(repo, gr_id)
    assert row.state == "approved", "the downgrade was applied"
    assert row.reviewed_by == "A. Analyst", "the review columns were reverted too"

    payload = json.loads(result.stdout)
    assert payload["rows_changed_state"] == 0
    assert payload["rows_refused_downgrade"] == 1
    (refused,) = payload["refused_downgrades"]
    assert refused == {
        "gr_id": gr_id,
        "stored_state": "approved",
        "incoming_state": "draft",
        "stored_reviewed_by": "A. Analyst",
    }
    # The human watching a --json run is told too, and told what to do.
    assert "protected 1 record(s)" in result.stderr
    assert "--allow-downgrade" in result.stderr


def test_a_file_that_agrees_with_the_store_reports_zero_refusals(repo):
    """Proves the two readings of `rows_changed_state == 0` are now distinct.

    This is the other half of the pair. Here the file and the store agree, so
    nothing changed state AND nothing was refused. In
    `test_a_refused_downgrade_...` nothing changed state and one record was
    refused. Same `rows_changed_state`, different facts -- which is the whole
    point of the new figure.
    """
    (gr_id,) = seed(repo, rows=1, state="draft")
    approve(repo, gr_id)
    run(repo, "export", provider=None)  # the file now carries state='approved'

    result = run(repo, "import", "--json", provider="nope")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["rows_changed_state"] == 0
    assert payload["rows_refused_downgrade"] == 0
    assert payload["refused_downgrades"] == []
    assert "protected" not in result.stderr
    assert read_row(repo, gr_id).state == "approved"


def test_allow_downgrade_applies_the_change_and_reports_no_refusals(repo):
    """Proves the flag both works and stops counting refusals.

    With `--allow-downgrade` the guard does not fire, so the state moves and
    `rows_refused_downgrade` is zero -- a refusal counted here would be as
    wrong as one uncounted in the default case.
    """
    (gr_id,) = seed(repo, rows=1, state="draft")
    run(repo, "export", provider=None)
    approve(repo, gr_id)

    result = run(repo, "import", "--allow-downgrade", "--json", provider="nope")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["allow_downgrade"] is True
    assert payload["rows_changed_state"] == 1
    assert payload["rows_refused_downgrade"] == 0
    assert payload["refused_downgrades"] == []
    assert read_row(repo, gr_id).state == "draft"


def test_the_text_report_names_the_protected_record(repo):
    """Proves a reviewer who did not pass `--json` still learns which record.

    "3 approvals were protected" is the single most useful thing `import`
    can say, and a bare count cannot be acted on -- the resolution is either
    to re-export from the machine holding the newer state or to pass the
    flag, and both need the `gr_id`.
    """
    (gr_id,) = seed(repo, rows=1, state="draft")
    run(repo, "export", provider=None)
    approve(repo, gr_id, reviewer="R. Reviewer")

    result = run(repo, "import", provider="nope")
    assert result.exit_code == 0, result.stderr
    flat = " ".join(result.stdout.split())
    assert "1 of 1 shown" in flat
    assert gr_id in flat
    assert "kept approved" in flat
    assert "R. Reviewer" in flat


def test_no_refusal_is_stated_rather_than_left_as_silence(repo):
    """Proves a measured zero is printed, not implied by an absent line.

    Silence after a guard is indistinguishable from a guard that never ran --
    the same absent-versus-real defect one layer out.
    """
    seed(repo, rows=1, state="draft")
    run(repo, "export", provider=None)
    result = run(repo, "import", provider="nope")
    assert result.exit_code == 0, result.stderr
    assert "No state downgrade was refused" in " ".join(result.stdout.split())


def test_superseded_outranks_approved_so_a_stale_export_cannot_restore_it(repo):
    """Proves the ranking the fix must not weaken.

    `superseded` sits ABOVE `approved`, not level with it. Level made the
    comparison a tie in both directions, so a stale export carrying
    `approved` would silently restore over a record the store had since
    superseded -- reverting a human's judgement and orphaning
    `superseded_by`, with no flag required. Probed through the CLI and read
    back off `gr`, not off `_STATE_RANK`.
    """
    first, second = seed(repo, rows=2, state="draft")
    approve(repo, first)
    run(repo, "export", provider=None)  # the file now carries approved
    supersede(repo, first, second)
    assert read_row(repo, first).state == "superseded"

    refused = run(repo, "import", "--json", provider="nope")
    assert refused.exit_code == 0, refused.stderr
    payload = json.loads(refused.stdout)
    assert payload["rows_refused_downgrade"] == 1
    assert payload["refused_downgrades"][0]["stored_state"] == "superseded"
    assert payload["refused_downgrades"][0]["incoming_state"] == "approved"

    row = read_row(repo, first)
    assert row.state == "superseded"
    assert row.superseded_by == second, "the supersession link survived"

    # And the ordinary direction is not obstructed: with the flag it applies.
    allowed = run(repo, "import", "--allow-downgrade", "--json", provider="nope")
    assert allowed.exit_code == 0, allowed.stderr
    assert json.loads(allowed.stdout)["rows_refused_downgrade"] == 0
    assert read_row(repo, first).state == "approved"


def test_approved_to_superseded_restores_freely_without_the_flag(repo):
    """Proves the rank increase is NOT treated as a downgrade.

    The other direction of the same asymmetry: moving on from an approval is
    the ordinary case and must not need a flag. If this ever needed
    `--allow-downgrade`, the ranking would have been flattened back to a tie.
    """
    first, second = seed(repo, rows=2, state="draft")
    approve(repo, first)
    supersede(repo, first, second)
    run(repo, "export", provider=None)  # the file now carries superseded

    store = open_store(repo)
    try:
        # Put the store back to `approved` so the file is the newer fact.
        from legacylift_search.gr_export import import_records

        conn = store._connect()
        conn.execute(
            "UPDATE gr SET state = 'approved', superseded_by = NULL "
            "WHERE gr_id = ?",
            (first,),
        )
        store.commit()
        result = import_records(store, export_path(repo))
    finally:
        store.close()

    assert result.rows_refused_downgrade == 0
    assert result.refused_downgrades == ()
    assert result.rows_changed_state == 1
    assert read_row(repo, first).state == "superseded"
    assert read_row(repo, first).superseded_by == second


def test_the_guardrail_text_states_that_a_refusal_is_named(repo):
    """Proves what `import` now guarantees reached the four guard rails.

    `IMPORT_GUARDRAILS` is the one source of truth the CLI help text
    repeats, so a new guarantee that is not in it is a guarantee no reviewer
    reading `--help` learns about. (`tests/test_cli_req_repair.py` holds the
    equality assertion between the tuple and its verbatim CLI copy; this
    only pins the content.)
    """
    joined = " ".join(IMPORT_GUARDRAILS)
    assert "COUNTED AND NAMED" in joined
    result = run(repo, "import", "--help", provider=None)
    assert result.exit_code == 0, result.stderr
    assert "COUNTED AND NAMED" in " ".join(result.stdout.split())


def test_refused_downgrade_is_immutable_and_carries_a_missing_reviewer_as_none():
    """Proves `stored_reviewed_by` keeps "no reviewer recorded" as NULL.

    Flattening it to an empty string would be the same absent-versus-real
    collapse the rest of this fix is about, one field down.
    """
    refused = RefusedDowngrade(
        gr_id="GR-x", stored_state="approved", incoming_state="draft",
        stored_reviewed_by=None,
    )
    assert refused.stored_reviewed_by is None
    with pytest.raises(Exception):
        refused.gr_id = "GR-y"  # frozen dataclass


# --------------------------------------------------------------------------
# Defect 2: the embedder is threaded, and None is still a degraded success
# --------------------------------------------------------------------------


def test_the_cli_hash_provider_is_built_at_1024_not_64(repo):
    """Proves the dimension this module's collections are opened at.

    `EmbeddingConfig.dimension` defaults to 1024 and `create_embedder`
    honours it for the `hash` provider, while `HashEmbedder`'s own default is
    64. A helper that opened the collection at 64 would create it at 64, and
    the next command's 1024-dim embedder would then fail
    `validate_dimension` -- so a test claiming to measure a degraded vector
    half would in fact be measuring a provider mismatch.
    """
    from legacylift_search.cli_requirements._shared import (
        build_embedder,
        resolve_requirements_paths,
    )

    paths = resolve_requirements_paths(repo, None, None, print_banner=False)
    embedder, reason = build_embedder(paths.manifest, "hash")
    assert reason is None
    assert embedder.dimension == HASH_DIMENSION


def test_import_with_an_embedder_populates_the_collection(repo):
    """Proves the vector half no longer degrades unconditionally.

    Before the fix `import_records` took no embedder and called
    `refresh_gr_vectors(store, touched)`, so nothing an import restored ever
    reached `gr_statements` whatever the provider configuration said. The
    collection lives under the KNOWLEDGE directory, which is what
    `refresh_gr_vectors`' default `base_dir` resolves to.
    """
    ids = seed(repo, rows=2)
    run(repo, "export", provider=None)

    result = run(repo, "import", "--json", provider="hash")
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["vectors_populated"] is True
    assert payload["embed"]["embedded"] == 2
    assert payload["embed"]["degraded"] is False
    assert payload["embed"]["reason"] is None
    assert collection_ids(repo) == sorted(ids)
    assert (repo / "legacylift-docs" / "knowledge" / "chroma").is_dir()


def test_import_without_an_embedder_exits_zero_and_reindex_is_the_recovery(repo):
    """Proves `embedder=None` is a supported degraded success, not data loss.

    The rows land, the command exits ZERO, the report says the semantic half
    is behind and names `requirements reindex-vectors`, and a subsequent
    `reindex-vectors` populates the collection. A non-zero exit here would
    read as "the import failed" and invite re-running an extraction, which is
    hours of model time to recover something that was never lost.
    """
    ids = seed(repo, rows=2)
    run(repo, "export", provider=None)

    degraded = run(repo, "import", "--json", provider="nope")
    assert degraded.exit_code == 0, degraded.stderr
    payload = json.loads(degraded.stdout)
    assert payload["rows_read"] == 2
    assert payload["vectors_populated"] is False
    assert payload["embed"]["degraded"] is True
    assert payload["embed"]["skipped"] == 2
    assert "reindex-vectors" in payload["embed"]["reason"]
    assert "reindex-vectors" in degraded.stderr
    assert "no embedding provider is available" in degraded.stderr

    # SQLite is complete regardless -- that is the whole contract.
    store = open_store(repo)
    try:
        assert sorted(store.all_gr_ids()) == sorted(ids)
        assert len(store.search_gr_fts("vendor", 10)) == 2, "gr_fts is current"
    finally:
        store.close()

    # And the named recovery actually recovers.
    repaired = run(repo, "reindex-vectors", provider="hash")
    assert repaired.exit_code == 0, repaired.stderr
    assert collection_ids(repo) == sorted(ids)


def test_import_records_embedder_defaults_to_none_so_no_caller_breaks(repo):
    """Proves the new parameter did not become mandatory.

    A two-positional-argument call is still valid and still degrades
    gracefully -- which is what keeps every already-shipped caller working
    and is why the default is `None` rather than a required argument.
    """
    from legacylift_search.gr_export import import_records

    seed(repo, rows=1)
    run(repo, "export", provider=None)

    store = open_store(repo)
    try:
        result = import_records(store, export_path(repo))
    finally:
        store.close()

    assert result.rows_read == 1
    assert result.embed_result.degraded is True
    assert "reindex-vectors" in result.embed_result.reason


def test_the_refresh_pair_runs_once_for_the_whole_import(repo):
    """Proves the pair is called per import, not per record.

    Step 5's rule: `refresh_gr_derived_sql` inside the caller's transaction
    and `refresh_gr_vectors` after it commits, ONCE for a whole run. Counted
    by patching both halves rather than by reading the source.
    """
    import legacylift_search.gr_export as gr_export

    seed(repo, rows=3)
    run(repo, "export", provider=None)

    calls = {"sql": 0, "vectors": 0, "gr_ids": None}
    real_sql = gr_export.refresh_gr_derived_sql
    real_vectors = gr_export.refresh_gr_vectors

    def counting_sql(store, gr_ids, *args, **kwargs):
        calls["sql"] += 1
        calls["gr_ids"] = list(gr_ids)
        return real_sql(store, gr_ids, *args, **kwargs)

    def counting_vectors(store, gr_ids, *args, **kwargs):
        calls["vectors"] += 1
        return real_vectors(store, gr_ids, *args, **kwargs)

    gr_export.refresh_gr_derived_sql = counting_sql
    gr_export.refresh_gr_vectors = counting_vectors
    store = open_store(repo)
    try:
        gr_export.import_records(store, export_path(repo))
    finally:
        store.close()
        gr_export.refresh_gr_derived_sql = real_sql
        gr_export.refresh_gr_vectors = real_vectors

    assert calls["sql"] == 1
    assert calls["vectors"] == 1
    assert len(calls["gr_ids"]) == 3


# --------------------------------------------------------------------------
# The two Step 9 properties the fix must not have broken
# --------------------------------------------------------------------------


def test_the_incomplete_header_is_still_skipped_without_creating_a_record(repo):
    """Proves the reserved header line is not mistaken for a requirement.

    Detected by the absence of a `gr_id` key rather than by position, so the
    row count must be the requirement count and nothing else.
    """
    ids = seed_incomplete(repo, rows=2)
    run(repo, "export", "--allow-incomplete", provider=None)
    first_line = json.loads(export_path(repo).read_bytes().splitlines()[0])
    assert "_incomplete" in first_line

    result = run(repo, "import", "--json", provider="nope")
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


def test_two_exports_over_an_unchanged_store_are_byte_identical(repo):
    """Proves the determinism acceptance criterion still holds.

    Nothing that varies between runs may reach the file. Checked with the
    flag as well as without, because the `_incomplete` header is the one
    line that could have grown a timestamp, counter or tool version.
    """
    seed_incomplete(repo, rows=2)

    assert run(repo, "export", "--allow-incomplete", provider=None).exit_code == 0
    first = export_path(repo).read_bytes()
    assert run(repo, "export", "--allow-incomplete", provider=None).exit_code == 0
    assert export_path(repo).read_bytes() == first
    assert b"_incomplete" in first.splitlines()[0]

    # And an export/import/export round trip is a fixed point, so the fix did
    # not start bumping `updated_at` on a write that changed no value.
    assert run(repo, "import", provider="nope").exit_code == 0
    assert run(repo, "export", "--allow-incomplete", provider=None).exit_code == 0
    assert export_path(repo).read_bytes() == first


def test_the_export_path_is_unchanged_by_the_import_fix(repo):
    """Proves `export_jsonl` gained nothing: no new key, no header change.

    A guard against the easy mistake of recording the refusal count in the
    export instead of in the result -- it would vary between runs and break
    byte-identity.
    """
    (gr_id,) = seed(repo, rows=1, state="draft")
    approve(repo, gr_id)
    run(repo, "export", provider=None)
    lines = export_path(repo).read_bytes().splitlines()
    assert len(lines) == 1, "no header without --allow-incomplete"
    obj = json.loads(lines[0])
    assert obj["gr_id"] == gr_id
    assert "refused_downgrades" not in obj
    assert "rows_refused_downgrade" not in obj
    assert SECOND_ID not in obj.values()
