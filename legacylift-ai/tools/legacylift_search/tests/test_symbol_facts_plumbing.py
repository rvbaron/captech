"""Tests for the Milestones 23-25 Shared plumbing prerequisite.

Covers the two parts that are fully testable in isolation with a synthetic
fact (per the ExecPlan): the end-to-end round-trip of a hand-built
``SymbolFact`` through the pipeline (worker ``ExtractResult`` field -> store
schema -> ``symbol_facts`` row -> query helpers/stats -> ``facts`` CLI) and the
crash-guard/orphan-guard on a dangling ``subject_symbol_id`` FK.

The two cascade-cleanup tests (changed-file / deleted-file) are deliberately
NOT written here: they require re-extraction to emit a *content-driven* fact,
which a synthetic fact injected outside the extractor cannot exercise. The plan
defers them to M23 (the first real content-driven handler).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest
from legacylift_search.extract_worker import ExtractResult
from legacylift_search.indexer import Indexer
from legacylift_search.models import (
    SourceFile,
    Symbol,
    SymbolFact,
    TextRange,
)
from legacylift_search.store import SQLiteStore


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    s = SQLiteStore(tmp_path / "test.sqlite")
    s.migrate()
    yield s
    s.close()


def _make_source_file() -> SourceFile:
    repo_root = Path("/fake/repo")
    return SourceFile(
        absolute_path=repo_root / "src/Controller.cs",
        repo_root=repo_root,
        relative_path="src/Controller.cs",
        language="csharp",
        size_bytes=512,
        sha256="abc123",
        mtime_ns=1234567890,
    )


def _make_symbol() -> Symbol:
    return Symbol(
        id="csharp:src/Controller.cs:GetWidgets:10",
        language="csharp",
        name="GetWidgets",
        qualified_name="WidgetController.GetWidgets",
        kind="method",
        entity_class="other",
        range=TextRange(start_byte=100, end_byte=400, start_line=10, end_line=20),
    )


def _make_fact(subject_id: str, *, predicate: str = "http_method",
               object_: str | None = "GET", start_line: int = 10) -> SymbolFact:
    return SymbolFact(
        id=f"fact:{subject_id}:{predicate}:{object_ or ''}:{start_line}",
        subject_symbol_id=subject_id,
        predicate=predicate,
        object=object_,
        attributes={"route": "/widgets"},
        evidence='[HttpGet("/widgets")]',
        confidence=1.0,
        relative_path="src/Controller.cs",
        start_line=start_line,
        language="csharp",
    )


def test_extract_result_carries_facts_across_pickle() -> None:
    """The worker boundary field must survive model (de)serialization so facts
    cross the ProcessPoolExecutor pickle boundary."""
    sf = _make_source_file()
    sym = _make_symbol()
    fact = _make_fact(sym.id)

    res = ExtractResult(source_file=sf, symbols=[sym], facts=[fact])
    round_tripped = ExtractResult.model_validate_json(res.model_dump_json())

    assert len(round_tripped.facts) == 1
    assert round_tripped.facts[0].id == fact.id
    assert round_tripped.facts[0].subject_symbol_id == sym.id
    assert round_tripped.facts[0].attributes == {"route": "/widgets"}


def test_fact_roundtrip_through_store(store: SQLiteStore) -> None:
    """A hand-built fact whose subject matches a persisted symbol lands in
    symbol_facts and surfaces via both query helpers and stats()."""
    sf = _make_source_file()
    sym = _make_symbol()
    fact = _make_fact(sym.id)

    store.upsert_files([sf])
    store.upsert_symbols(sf, [sym])
    orphaned = store.upsert_facts(sf, [fact])

    assert orphaned == []

    by_pred = store.facts_by_predicate("http_method")
    assert len(by_pred) == 1
    assert by_pred[0].id == fact.id
    assert by_pred[0].subject_symbol_id == sym.id
    assert by_pred[0].object == "GET"
    # attributes serialized via json.dumps round-trips back to a dict.
    assert by_pred[0].attributes == {"route": "/widgets"}
    assert by_pred[0].confidence == 1.0

    by_sym = store.facts_for_symbol(sym.id)
    assert len(by_sym) == 1
    assert by_sym[0].id == fact.id

    assert store.stats().fact_count == 1


def test_fact_upsert_idempotent(store: SQLiteStore) -> None:
    """Re-upserting the same fact id is idempotent (INSERT OR REPLACE)."""
    sf = _make_source_file()
    sym = _make_symbol()
    fact = _make_fact(sym.id)

    store.upsert_files([sf])
    store.upsert_symbols(sf, [sym])
    store.upsert_facts(sf, [fact])
    store.upsert_facts(sf, [fact])

    assert store.stats().fact_count == 1


def test_null_object_and_attributes(store: SQLiteStore) -> None:
    """A bare fact (object None, attributes None) round-trips as NULLs."""
    sf = _make_source_file()
    sym = _make_symbol()
    fact = SymbolFact(
        id=f"fact:{sym.id}:requires_auth::10",
        subject_symbol_id=sym.id,
        predicate="requires_auth",
        object=None,
        attributes=None,
        evidence="[Authorize]",
        confidence=1.0,
        relative_path="src/Controller.cs",
        start_line=10,
        language="csharp",
    )

    store.upsert_files([sf])
    store.upsert_symbols(sf, [sym])
    store.upsert_facts(sf, [fact])

    recs = store.facts_by_predicate("requires_auth")
    assert len(recs) == 1
    assert recs[0].object is None
    assert recs[0].attributes is None


def test_orphan_guard_drops_and_reports_bad_subject(store: SQLiteStore) -> None:
    """A fact with a dangling subject_symbol_id FK must NOT abort the run: it
    is dropped and returned, while valid facts in the same batch are written."""
    sf = _make_source_file()
    sym = _make_symbol()
    good = _make_fact(sym.id, predicate="http_method", object_="GET")
    orphan = _make_fact(
        "csharp:src/Controller.cs:DoesNotExist:99",
        predicate="requires_auth",
        object_=None,
        start_line=99,
    )

    store.upsert_files([sf])
    store.upsert_symbols(sf, [sym])

    # Must not raise despite the dangling FK.
    orphaned = store.upsert_facts(sf, [good, orphan])

    assert len(orphaned) == 1
    assert orphaned[0].subject_symbol_id == "csharp:src/Controller.cs:DoesNotExist:99"
    assert orphaned[0].predicate == "requires_auth"

    # The valid fact in the same batch is still written.
    assert store.stats().fact_count == 1
    assert len(store.facts_by_predicate("http_method")) == 1
    assert store.facts_by_predicate("requires_auth") == []


def test_upsert_facts_missing_file_id_silent_return(store: SQLiteStore) -> None:
    """Mirrors upsert_refs: a missing repo_files row silently no-ops (the
    file_id FK's by-design silent-drop failure mode), not raise."""
    sf = _make_source_file()  # never upsert_files'd
    sym = _make_symbol()
    fact = _make_fact(sym.id)

    orphaned = store.upsert_facts(sf, [fact])

    assert orphaned == []
    assert store.stats().fact_count == 0


# --------------------------------------------------------------------------
# facts CLI smoke test (mirrors test_cli_commands.py style)
# --------------------------------------------------------------------------
def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _open_store(repo: Path) -> SQLiteStore:
    return SQLiteStore(
        repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    )


@pytest.fixture
def indexed_repo_with_fact(tmp_path: Path) -> tuple[Path, str]:
    """Index the polyglot fixture, then inject one synthetic fact anchored on a
    real indexed symbol (no handler emits facts yet, so we inject directly)."""
    repo = _copy_fixture(tmp_path)
    manifest = Manifest()
    manifest.embedding.provider = "hash"
    manifest.embedding.dimension = 64
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    store = _open_store(repo)
    try:
        conn = store._connect()
        row = conn.execute(
            """
            SELECT s.id AS id, rf.repo_root AS repo_root,
                   rf.relative_path AS relative_path, rf.language AS language,
                   rf.sha256 AS sha256, rf.size_bytes AS size_bytes,
                   rf.mtime_ns AS mtime_ns
            FROM symbols s
            JOIN repo_files rf ON rf.id = s.file_id
            LIMIT 1
            """
        ).fetchone()
        assert row is not None, "fixture produced no symbols"
        subject_id = row["id"]
        sf_row = row
        sf = SourceFile(
            absolute_path=Path(sf_row["repo_root"]) / sf_row["relative_path"],
            repo_root=Path(sf_row["repo_root"]),
            relative_path=sf_row["relative_path"],
            language=sf_row["language"],
            size_bytes=sf_row["size_bytes"],
            sha256=sf_row["sha256"],
            mtime_ns=sf_row["mtime_ns"],
        )
        fact = SymbolFact(
            id=f"fact:{subject_id}:http_method:GET:1",
            subject_symbol_id=subject_id,
            predicate="http_method",
            object="GET",
            attributes={"route": "/things"},
            evidence='[HttpGet("/things")]',
            confidence=1.0,
            relative_path=sf.relative_path,
            start_line=1,
            language=sf.language,
        )
        store.upsert_facts(sf, [fact])
    finally:
        store.close()

    return repo, subject_id


def test_facts_cli_by_predicate(indexed_repo_with_fact: tuple[Path, str]) -> None:
    repo, subject_id = indexed_repo_with_fact
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["facts", "--predicate", "http_method", "--repo-root", str(repo)],
    )
    assert result.exit_code == 0, result.output
    assert "http_method" in result.output


def test_facts_cli_by_symbol(indexed_repo_with_fact: tuple[Path, str]) -> None:
    repo, subject_id = indexed_repo_with_fact
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["facts", "--symbol", subject_id, "--repo-root", str(repo)],
    )
    assert result.exit_code == 0, result.output
    assert "http_method" in result.output


def test_facts_cli_requires_exactly_one_filter(
    indexed_repo_with_fact: tuple[Path, str],
) -> None:
    repo, _ = indexed_repo_with_fact
    runner = CliRunner()
    # Neither filter.
    result = runner.invoke(app, ["facts", "--repo-root", str(repo)])
    assert result.exit_code == 1, result.output
    # Both filters.
    result = runner.invoke(
        app,
        [
            "facts",
            "--predicate", "http_method",
            "--symbol", "x",
            "--repo-root", str(repo),
        ],
    )
    assert result.exit_code == 1, result.output


def test_facts_cli_no_match(indexed_repo_with_fact: tuple[Path, str]) -> None:
    repo, _ = indexed_repo_with_fact
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["facts", "--predicate", "no_such_predicate", "--repo-root", str(repo)],
    )
    assert result.exit_code == 0, result.output
    assert "No facts found" in result.output
