"""Tests for Step 9's export/import half: `gr_export.py`.

Milestone 1, Step 9 (export/import only — the CLI wiring and the
`modernize-extract-rules` producer wiring are other units') of
`docs/exec-plans/active/reqs-to-data-store.md`.

**Nothing writes a `gr` row through ingest yet** (that is Step 6/6a, a
different unit), so these tests insert `gr`, `gr_citation`, `gr_scenario`,
`gr_edge_case`, `gr_run` and `gr_run_hit` rows directly with raw SQL, reusing
`test_gr_state.py`'s `_MINIMAL_GR` and `insert_gr` the way `test_gr_refresh.py`
already does.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from legacylift_search.gr_export import (
    IMPORT_GUARDRAILS,
    REASON_COVERAGE_NEVER_MEASURED,
    IncompleteCorpusError,
    export_jsonl,
    import_records,
)
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import GRRecord
from tests.test_gr_state import _MINIMAL_GR, insert_gr


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        ks = KnowledgeStore(Path(tmpdir) / "knowledge" / "knowledge.sqlite")
        try:
            yield ks
        finally:
            ks.close()


# --------------------------------------------------------------------------
# Raw-SQL fixture helpers (no ingest exists yet to build these rows for us)
# --------------------------------------------------------------------------


def _insert_citation(conn: sqlite3.Connection, gr_id: str, **overrides) -> None:
    row = {
        "gr_id": gr_id,
        "anchor_key": "sym:Foo.bar",
        "anchor_resolution": "symbol",
        "relative_path": "src/foo.py",
        "start_line": 1,
        "end_line": 5,
        "content_hash": "abc123",
        "verified_at": None,
        "provenance": "extracted",
    }
    row.update(overrides)
    conn.execute(
        "INSERT INTO gr_citation (gr_id, anchor_key, anchor_resolution, "
        "relative_path, start_line, end_line, content_hash, verified_at, "
        "provenance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(row.values()),
    )


def _insert_scenario(conn: sqlite3.Connection, gr_id: str, ordinal: int, **overrides) -> None:
    row = {
        "gr_id": gr_id,
        "ordinal": ordinal,
        "given": "an order exists",
        "when": "the vendor number is missing",
        "then": "the order is rejected",
        "and_clause": None,
        "provenance": "extracted",
    }
    row.update(overrides)
    conn.execute(
        'INSERT INTO gr_scenario (gr_id, ordinal, "given", "when", "then", '
        "and_clause, provenance) VALUES (?, ?, ?, ?, ?, ?, ?)",
        tuple(row.values()),
    )


def _insert_edge_case(conn: sqlite3.Connection, gr_id: str, ordinal: int, **overrides) -> None:
    row = {"gr_id": gr_id, "ordinal": ordinal, "text": "vendor number is blank", "provenance": "extracted"}
    row.update(overrides)
    conn.execute(
        "INSERT INTO gr_edge_case (gr_id, ordinal, text, provenance) VALUES (?, ?, ?, ?)",
        tuple(row.values()),
    )


def _insert_run(conn: sqlite3.Connection, run_id: str, **overrides) -> None:
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


def _insert_hit(conn: sqlite3.Connection, gr_id: str, run_id: str, ordinal: int = 0, outcome: str = "new") -> None:
    conn.execute(
        "INSERT INTO gr_run_hit (gr_id, run_id, offer_ordinal, outcome) VALUES (?, ?, ?, ?)",
        (gr_id, run_id, ordinal, outcome),
    )


def _record_line(**overrides) -> dict:
    """A full 42-key `GRRecord` dict plus empty children, the export shape."""
    base = {**_MINIMAL_GR, "rule_class": "behavioral", "pattern": "B-UNCOND"}
    base.update(overrides)
    obj = GRRecord(**base).model_dump()
    obj["citations"] = []
    obj["scenarios"] = []
    obj["edge_cases"] = []
    obj["findings"] = []
    return obj


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        for line in lines:
            fh.write(json.dumps(line, sort_keys=True).encode("utf-8"))
            fh.write(b"\n")


# --------------------------------------------------------------------------
# Export: determinism, shape, line endings
# --------------------------------------------------------------------------


def test_the_second_export_is_byte_identical_over_an_unchanged_store(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn)
    _insert_citation(conn, gr_id)
    _insert_scenario(conn, gr_id, 0)
    _insert_edge_case(conn, gr_id, 0)
    conn.commit()

    out1, out2 = tmp_path / "one.jsonl", tmp_path / "two.jsonl"
    export_jsonl(store, out1)
    export_jsonl(store, out2)
    assert out1.read_bytes() == out2.read_bytes()
    assert out1.read_bytes()  # not vacuously equal because both are empty


def test_lines_end_in_lf_and_keys_are_sorted_within_each_object(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn)
    _insert_citation(conn, gr_id)
    _insert_scenario(conn, gr_id, 0)
    conn.commit()

    out = tmp_path / "out.jsonl"
    export_jsonl(store, out)
    raw = out.read_bytes()
    assert b"\r" not in raw  # \n only, regardless of host

    lines = raw.decode("utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert list(obj.keys()) == sorted(obj.keys())
    assert obj["citations"]
    assert list(obj["citations"][0].keys()) == sorted(obj["citations"][0].keys())
    assert obj["gr_id"] == gr_id


def test_export_nests_citations_scenarios_and_edge_cases_deterministically(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn)
    _insert_citation(conn, gr_id, relative_path="src/b.py", start_line=10, end_line=12)
    _insert_citation(conn, gr_id, relative_path="src/a.py", start_line=1, end_line=2)
    _insert_scenario(conn, gr_id, 1)
    _insert_scenario(conn, gr_id, 0)
    _insert_edge_case(conn, gr_id, 0)
    conn.commit()

    out = tmp_path / "out.jsonl"
    export_jsonl(store, out)
    obj = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    # Citations ordered by (relative_path, start_line, end_line), not insert order.
    assert [c["relative_path"] for c in obj["citations"]] == ["src/a.py", "src/b.py"]
    # Scenarios ordered by ordinal within provenance.
    assert [s["ordinal"] for s in obj["scenarios"]] == [0, 1]
    assert len(obj["edge_cases"]) == 1


# --------------------------------------------------------------------------
# Export: the completeness gate and its one header line
# --------------------------------------------------------------------------


def test_an_incomplete_run_refuses_export_without_the_flag(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn)
    _insert_run(conn, "RUN-never-measured", not_accounted_for=None)
    _insert_hit(conn, gr_id, "RUN-never-measured")
    conn.commit()

    with pytest.raises(IncompleteCorpusError) as exc:
        export_jsonl(store, tmp_path / "refused.jsonl")
    assert "RUN-never-measured" in exc.value.blocking
    assert not (tmp_path / "refused.jsonl").exists()


def test_allow_incomplete_is_deterministic_and_names_both_reasons_in_words(store, tmp_path):
    conn = store._connect()
    gr_id_a = insert_gr(conn)
    gr_id_b = insert_gr(conn, gr_id="GR-01HQ2X0000000000000000002")
    _insert_run(conn, "RUN-unmeasured", not_accounted_for=None)
    _insert_run(conn, "RUN-gappy", not_accounted_for=37)
    _insert_hit(conn, gr_id_a, "RUN-unmeasured")
    _insert_hit(conn, gr_id_b, "RUN-gappy")
    conn.commit()

    out1, out2 = tmp_path / "one.jsonl", tmp_path / "two.jsonl"
    export_jsonl(store, out1, allow_incomplete=True)
    export_jsonl(store, out2, allow_incomplete=True)
    assert out1.read_bytes() == out2.read_bytes()

    first_line = out1.read_text(encoding="utf-8").splitlines()[0]
    header = json.loads(first_line)
    assert set(header.keys()) == {"_incomplete"}
    assert header["_incomplete"]["RUN-unmeasured"] == REASON_COVERAGE_NEVER_MEASURED
    assert header["_incomplete"]["RUN-gappy"] == "37 chunks unaccounted for"

    # And the same store WITHOUT the flag is still refused.
    with pytest.raises(IncompleteCorpusError):
        export_jsonl(store, tmp_path / "refused.jsonl")


def test_a_retired_run_does_not_block_export(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn)
    _insert_run(
        conn,
        "RUN-retired",
        not_accounted_for=None,
        gate_excluded=1,
        gate_excluded_reason="superseded by a later run",
    )
    _insert_hit(conn, gr_id, "RUN-retired")
    conn.commit()

    out = tmp_path / "out.jsonl"
    export_jsonl(store, out)  # must not raise
    assert out.exists()
    line = out.read_text(encoding="utf-8").splitlines()[0]
    assert "_incomplete" not in json.loads(line)


# --------------------------------------------------------------------------
# `gr_run.complete` — the generated column, and the `table_xinfo` trap
# --------------------------------------------------------------------------


def test_complete_is_a_generated_column_read_via_table_xinfo_not_table_info(store):
    conn = store._connect()
    _insert_run(conn, "RUN-null", not_accounted_for=None)
    _insert_run(conn, "RUN-positive", not_accounted_for=5)
    _insert_run(conn, "RUN-zero", not_accounted_for=0)
    conn.commit()

    info_columns = {r[1] for r in conn.execute("PRAGMA table_info('gr_run')")}
    assert "complete" not in info_columns  # PRAGMA table_info OMITS generated columns

    xinfo_columns = {r[1] for r in conn.execute("PRAGMA table_xinfo('gr_run')")}
    assert "complete" in xinfo_columns  # table_xinfo is the one that does not lie

    rows = {
        r[0]: r[1]
        for r in conn.execute("SELECT run_id, complete FROM gr_run").fetchall()
    }
    assert rows["RUN-null"] == 0  # never measured -- NOT complete
    assert rows["RUN-positive"] == 0  # measured, something left over -- NOT complete
    assert rows["RUN-zero"] == 1  # measured AND zero -- the only complete case


# --------------------------------------------------------------------------
# Import: the `_incomplete` header is skipped, never becomes a record
# --------------------------------------------------------------------------


def test_import_skips_a_leading_incomplete_object_without_creating_a_requirement(
    store, tmp_path
):
    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [{"_incomplete": {"RUN-x": REASON_COVERAGE_NEVER_MEASURED}}])

    result = import_records(store, path)
    assert result.rows_read == 0
    assert store.count_gr() == 0


# --------------------------------------------------------------------------
# Import: restores a state the file carried, never invents one
# --------------------------------------------------------------------------


def test_import_restores_the_states_the_file_carried(store, tmp_path):
    path = tmp_path / "in.jsonl"
    _write_jsonl(
        path,
        [
            _record_line(gr_id="GR-01HQ2X0000000000000000010", state="approved"),
            _record_line(gr_id="GR-01HQ2X0000000000000000011", state="rejected"),
        ],
    )

    result = import_records(store, path)
    assert result.rows_read == 2
    # A fresh insert has no prior state to have "changed" from.
    assert result.rows_changed_state == 0
    assert store.get_gr("GR-01HQ2X0000000000000000010").state == "approved"
    assert store.get_gr("GR-01HQ2X0000000000000000011").state == "rejected"


def test_import_never_invents_a_state_beyond_what_the_file_carries(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn, state="draft")
    conn.commit()

    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [_record_line(gr_id=gr_id, state="approved")])

    result = import_records(store, path)
    assert result.rows_changed_state == 1
    assert store.get_gr(gr_id).state == "approved"  # exactly what the file said


# --------------------------------------------------------------------------
# Import: refuses to lower a state by default, allows it under the flag
# --------------------------------------------------------------------------


def test_import_refuses_a_downgrade_by_default(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(
        conn,
        state="approved",
        reviewed_by="dnorton",
        reviewed_at="2026-09-01T00:00:00Z",
        review_note="looks right",
        name="original name",
    )
    conn.commit()

    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [_record_line(gr_id=gr_id, state="draft", name="updated name")])

    result = import_records(store, path)
    assert result.rows_changed_state == 0
    row = store.get_gr(gr_id)
    # The review act is protected...
    assert row.state == "approved"
    assert row.reviewed_by == "dnorton"
    assert row.reviewed_at == "2026-09-01T00:00:00Z"
    assert row.review_note == "looks right"
    # ...but everything else in the record still restores from the file.
    assert row.name == "updated name"


def test_import_performs_a_downgrade_under_allow_downgrade(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn, state="approved", reviewed_by="dnorton")
    conn.commit()

    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [_record_line(gr_id=gr_id, state="draft")])

    result = import_records(store, path, allow_downgrade=True)
    assert result.rows_changed_state == 1
    row = store.get_gr(gr_id)
    assert row.state == "draft"
    assert row.reviewed_by is None  # the file's own (unset) reviewer, restored


def test_approved_to_superseded_is_not_treated_as_a_downgrade(store, tmp_path):
    """`superseded` outranks `approved`, so moving on from an approval is a
    rank increase and restores freely.

    Supersession is not "damage" the way un-approving is -- the successor is
    where the work continues -- so the ordinary case must not need the flag.
    See `test_superseded_to_approved_is_refused_without_the_flag` for the
    direction that must, and `_STATE_RANK` for why the two are not symmetric.
    """
    conn = store._connect()
    gr_id = insert_gr(conn, state="approved")
    successor = insert_gr(conn, gr_id="GR-01HQ2X0000000000000000099")
    conn.commit()

    path = tmp_path / "in.jsonl"
    _write_jsonl(
        path, [_record_line(gr_id=gr_id, state="superseded", superseded_by=successor)]
    )

    result = import_records(store, path)  # allow_downgrade defaults False
    assert result.rows_changed_state == 1
    assert store.get_gr(gr_id).state == "superseded"


def test_superseded_to_approved_is_refused_without_the_flag(store, tmp_path):
    """A stale file may not silently un-supersede a record.

    This is the direction an equal rank got wrong. With `superseded` level
    with `approved`, the comparison is a tie **both** ways, so a checkout
    exported before a supersession would restore `approved` over a record the
    store has since superseded -- reverting a human's judgement and orphaning
    `superseded_by`, with no flag required and nothing reporting it.

    `superseded` is terminal in `ALLOWED_TRANSITIONS` because its successor is
    where the work continues, so leaving it is exactly what
    `--allow-downgrade` exists to make deliberate. Ranking it above `approved`
    refuses this while still letting `approved -> superseded` through.
    """
    conn = store._connect()
    successor = insert_gr(conn, gr_id="GR-01HQ2X0000000000000000099")
    gr_id = insert_gr(conn, state="superseded")
    conn.execute(
        "UPDATE gr SET superseded_by = ? WHERE gr_id = ?", (successor, gr_id)
    )
    conn.commit()

    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [_record_line(gr_id=gr_id, state="approved")])

    result = import_records(store, path)  # allow_downgrade defaults False
    assert result.rows_changed_state == 0
    row = store.get_gr(gr_id)
    assert row.state == "superseded"
    assert row.superseded_by == successor, "the supersession link survived"

    # And it goes through when the analyst says so.
    result = import_records(store, path, allow_downgrade=True)
    assert result.rows_changed_state == 1
    assert store.get_gr(gr_id).state == "approved"


# --------------------------------------------------------------------------
# Import: one `gr_import` row per invocation, with the right counts
# --------------------------------------------------------------------------


def test_one_gr_import_row_per_invocation_with_the_right_counts(store, tmp_path):
    conn = store._connect()
    gr_id = insert_gr(conn, state="draft")
    conn.commit()

    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [_record_line(gr_id=gr_id, state="approved")])
    import_records(store, path)

    _write_jsonl(path, [_record_line(gr_id=gr_id, state="approved")])
    import_records(store, path)  # a no-op state-wise the second time

    rows = conn.execute(
        "SELECT source_path, rows_read, rows_changed_state FROM gr_import "
        "ORDER BY import_id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["rows_read"] == 1 and rows[0]["rows_changed_state"] == 1
    assert rows[1]["rows_read"] == 1 and rows[1]["rows_changed_state"] == 0
    assert all(r["source_path"] == str(path) for r in rows)


# --------------------------------------------------------------------------
# Import: children round-trip, and the refresh pair actually runs
# --------------------------------------------------------------------------


def test_import_restores_citations_scenarios_and_edge_cases(store, tmp_path):
    line = _record_line(gr_id="GR-01HQ2X0000000000000000020")
    line["citations"] = [
        {
            "anchor_key": "sym:Foo.bar",
            "anchor_resolution": "symbol",
            "relative_path": "src/foo.py",
            "start_line": 1,
            "end_line": 5,
            "content_hash": "abc123",
            "verified_at": None,
            "provenance": "extracted",
        }
    ]
    line["scenarios"] = [
        {
            "ordinal": 0,
            "given": "g",
            "when": "w",
            "then": "t",
            "and_clause": None,
            "provenance": "extracted",
        }
    ]
    line["edge_cases"] = [{"ordinal": 0, "text": "edge", "provenance": "extracted"}]

    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [line])
    import_records(store, path)

    conn = store._connect()
    assert (
        conn.execute(
            "SELECT relative_path FROM gr_citation WHERE gr_id = ?", (line["gr_id"],)
        ).fetchone()[0]
        == "src/foo.py"
    )
    assert (
        conn.execute(
            'SELECT "given" FROM gr_scenario WHERE gr_id = ?', (line["gr_id"],)
        ).fetchone()[0]
        == "g"
    )
    assert (
        conn.execute(
            "SELECT text FROM gr_edge_case WHERE gr_id = ?", (line["gr_id"],)
        ).fetchone()[0]
        == "edge"
    )


def test_import_refreshes_fts_so_the_restored_text_is_searchable(store, tmp_path):
    line = _record_line(
        gr_id="GR-01HQ2X0000000000000000030",
        statement="The Widget Service must archive stale tickets.",
        statement_extracted="The Widget Service must archive stale tickets.",
    )
    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [line])
    import_records(store, path)

    hits = store.search_gr_fts("Widget")
    assert line["gr_id"] in [gr_id for gr_id, _ in hits]


def test_import_records_the_source_path_in_gr_import(store, tmp_path):
    path = tmp_path / "in.jsonl"
    _write_jsonl(path, [_record_line(gr_id="GR-01HQ2X0000000000000000040")])
    import_records(store, path)
    conn = store._connect()
    row = conn.execute("SELECT source_path FROM gr_import").fetchone()
    assert row["source_path"] == str(path)


# --------------------------------------------------------------------------
# The guard-rail strings exist and are non-empty (the CLI help text source)
# --------------------------------------------------------------------------


def test_import_guardrails_are_four_nonempty_strings():
    assert len(IMPORT_GUARDRAILS) == 4
    assert all(isinstance(s, str) and s.strip() for s in IMPORT_GUARDRAILS)
