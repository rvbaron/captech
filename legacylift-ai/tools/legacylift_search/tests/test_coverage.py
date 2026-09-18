"""Tests for the chunk-level `coverage` command/store method.

Layer-0 retrieval (code-modernization-layer0-retrieval.md, Milestone 3).

Covers:
- empty claimed list -> 0% claimed, all chunks uncovered;
- a citation overlapping a known chunk marks exactly the overlapping chunk(s);
- line-overlap is inclusive and correct at boundaries;
- the JSON output shape matches the contract M4 consumes;
- --limit bounds the listed uncovered chunks (counts stay exact).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacylift_search.cli import app, _parse_claimed_citations
from legacylift_search.config import Manifest
from legacylift_search.indexer import Indexer
from legacylift_search.store import SQLiteStore, _norm_path_components

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _build_index(repo: Path) -> None:
    manifest = Manifest()
    manifest.embedding.provider = "hash"
    manifest.embedding.dimension = 64
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")


@pytest.fixture
def indexed_repo(tmp_path: Path) -> Path:
    repo = _copy_fixture(tmp_path)
    _build_index(repo)
    return repo


def _open_store(repo: Path) -> SQLiteStore:
    return SQLiteStore(
        repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    )


def _all_chunks(store: SQLiteStore) -> list[dict]:
    conn = store._connect()
    rows = conn.execute(
        "SELECT id, relative_path, start_line, end_line FROM chunks"
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Store-level unit tests
# --------------------------------------------------------------------------


def test_empty_claimed_is_zero_percent(indexed_repo: Path) -> None:
    store = _open_store(indexed_repo)
    try:
        result = store.coverage([])
        assert result.total > 0
        assert result.claimed == 0
        assert result.uncovered == result.total
        assert result.pct == 0.0
        assert len(result.uncovered_chunks) == result.total
    finally:
        store.close()


def test_overlapping_citation_marks_chunk_claimed(indexed_repo: Path) -> None:
    store = _open_store(indexed_repo)
    try:
        chunks = _all_chunks(store)
        target = chunks[0]
        # Cite the exact line range of one known chunk.
        claimed = [
            (target["relative_path"], target["start_line"], target["end_line"])
        ]
        result = store.coverage(claimed)

        # The target chunk must not appear among the uncovered ones.
        uncovered_ids = {c.chunk_id for c in result.uncovered_chunks}
        assert target["id"] not in uncovered_ids

        # Every chunk that overlaps the cited range in the same file is claimed.
        expected_claimed = sum(
            1
            for c in chunks
            if c["relative_path"] == target["relative_path"]
            and c["start_line"] <= target["end_line"]
            and c["end_line"] >= target["start_line"]
        )
        assert result.claimed == expected_claimed
        assert result.claimed >= 1
        assert result.uncovered == result.total - result.claimed
    finally:
        store.close()


def test_overlap_is_inclusive_at_boundaries(indexed_repo: Path) -> None:
    store = _open_store(indexed_repo)
    try:
        chunks = _all_chunks(store)
        target = chunks[0]
        path = target["relative_path"]
        start = target["start_line"]
        end = target["end_line"]

        # A citation ending exactly on the chunk's start line touches it.
        touch_start = store.coverage([(path, start - 5, start)])
        assert target["id"] not in {c.chunk_id for c in touch_start.uncovered_chunks}

        # A citation starting exactly on the chunk's end line touches it.
        touch_end = store.coverage([(path, end, end + 5)])
        assert target["id"] not in {c.chunk_id for c in touch_end.uncovered_chunks}

        # A citation ending one line before the chunk's start does NOT touch it.
        if start >= 2:
            before = store.coverage([(path, start - 5, start - 1)])
            assert target["id"] in {
                c.chunk_id for c in before.uncovered_chunks
            }
    finally:
        store.close()


def test_coverage_tolerates_base_and_separator_mismatch(indexed_repo: Path) -> None:
    """A citation whose path has a different base prefix or Windows separators
    still matches the right chunk — the exact-string trap that would otherwise
    report 0% claimed for a whole run."""
    store = _open_store(indexed_repo)
    try:
        chunks = _all_chunks(store)
        target = chunks[0]
        path = target["relative_path"]  # repo-root-relative POSIX, e.g. src/a.cs
        start, end = target["start_line"], target["end_line"]

        exact = store.coverage([(path, start, end)])
        base_claimed = exact.claimed
        assert base_claimed >= 1

        # Extra leading base segments (the `legacy/<system>/...` shape the
        # extractor produces) must still match.
        prefixed = store.coverage([(f"legacy/ctcm-api/{path}", start, end)])
        assert prefixed.claimed == base_claimed

        # Windows backslash separators must still match.
        win = store.coverage([(path.replace("/", "\\"), start, end)])
        assert win.claimed == base_claimed

        # A leading ./ and an absolute-looking prefix must still match.
        dotted = store.coverage([(f"./{path}", start, end)])
        assert dotted.claimed == base_claimed
    finally:
        store.close()


def test_coverage_basename_collision_needs_path_suffix(indexed_repo: Path) -> None:
    """Sharing a filename is necessary but not sufficient — the path suffix must
    align, so a citation to `other/dir/<name>` does not claim a chunk in a
    different directory that merely shares the filename."""
    store = _open_store(indexed_repo)
    try:
        chunks = _all_chunks(store)
        target = chunks[0]
        filename = target["relative_path"].split("/")[-1]
        # A citation that shares only the filename under a bogus directory must
        # not claim the target chunk (its parent dirs differ).
        bogus = store.coverage(
            [(f"totally/unrelated/{filename}", target["start_line"], target["end_line"])]
        )
        # If the target's own path is just the bare filename this test is moot;
        # the fixture uses nested paths so the suffix differs.
        if "/" in target["relative_path"]:
            assert target["id"] in {c.chunk_id for c in bogus.uncovered_chunks}
    finally:
        store.close()


def test_uncovered_sorted_largest_span_first(indexed_repo: Path) -> None:
    store = _open_store(indexed_repo)
    try:
        result = store.coverage([])
        spans = [c.end_line - c.start_line for c in result.uncovered_chunks]
        assert spans == sorted(spans, reverse=True)
    finally:
        store.close()


# --------------------------------------------------------------------------
# Path normalization
# --------------------------------------------------------------------------


def test_norm_path_components() -> None:
    assert _norm_path_components("src/a/Foo.cs") == ("src", "a", "Foo.cs")
    # Windows separators + drive letter.
    assert _norm_path_components(r"C:\src\a\Foo.cs") == ("src", "a", "Foo.cs")
    # Leading ./ and / noise dropped.
    assert _norm_path_components("./src/Foo.cs") == ("src", "Foo.cs")
    assert _norm_path_components("/src/Foo.cs") == ("src", "Foo.cs")
    # `..` pops the prior component.
    assert _norm_path_components("a/b/../Foo.cs") == ("a", "Foo.cs")
    # Blank / rootless.
    assert _norm_path_components("") == ()
    assert _norm_path_components("   ") == ()


# --------------------------------------------------------------------------
# Citation parsing
# --------------------------------------------------------------------------


def test_parse_claimed_json_and_newline_forms() -> None:
    arr = _parse_claimed_citations('["src/a.cs:10-20", "src/b.cs:5-5"]')
    assert arr == [("src/a.cs", 10, 20), ("src/b.cs", 5, 5)]

    nl = _parse_claimed_citations("src/a.cs:10-20\nsrc/b.cs:5-5\n")
    assert nl == [("src/a.cs", 10, 20), ("src/b.cs", 5, 5)]


def test_parse_claimed_path_without_range_covers_whole_file() -> None:
    parsed = _parse_claimed_citations("src/a.cs")
    assert parsed == [("src/a.cs", 1, 2**31 - 1)]


def test_parse_claimed_single_line() -> None:
    parsed = _parse_claimed_citations("src/a.cs:42")
    assert parsed == [("src/a.cs", 42, 42)]


def test_parse_claimed_strips_leading_list_markers() -> None:
    # A bulleted list (dash / asterisk / bullet) must not fold the marker into
    # the path — the workflow fences citations that may arrive bulleted.
    assert _parse_claimed_citations("- src/a.cs:10-20") == [("src/a.cs", 10, 20)]
    assert _parse_claimed_citations("* src/b.cs:5-5") == [("src/b.cs", 5, 5)]
    assert _parse_claimed_citations("• src/c.cs:7") == [("src/c.cs", 7, 7)]
    # Mixed newline-delimited list with bullets and blank lines.
    assert _parse_claimed_citations("- src/a.cs:10-20\n\n- src/b.cs:5-5\n") == [
        ("src/a.cs", 10, 20),
        ("src/b.cs", 5, 5),
    ]
    # JSON array form with a stray bullet is tolerated too.
    assert _parse_claimed_citations('["- src/a.cs:10-20"]') == [("src/a.cs", 10, 20)]


# --------------------------------------------------------------------------
# CLI smoke tests
# --------------------------------------------------------------------------


def test_cli_coverage_human_table(indexed_repo: Path, tmp_path: Path) -> None:
    store = _open_store(indexed_repo)
    try:
        chunks = _all_chunks(store)
    finally:
        store.close()
    target = chunks[0]
    claimed_file = tmp_path / "claimed.txt"
    claimed_file.write_text(
        f"{target['relative_path']}:{target['start_line']}-{target['end_line']}\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "coverage",
            "--repo-root",
            str(indexed_repo),
            "--claimed",
            str(claimed_file),
            "--limit",
            "5",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "chunks claimed" in result.output


def test_cli_coverage_json_shape(indexed_repo: Path, tmp_path: Path) -> None:
    claimed_file = tmp_path / "claimed.json"
    claimed_file.write_text("[]", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "coverage",
            "--repo-root",
            str(indexed_repo),
            "--claimed",
            str(claimed_file),
            "--json",
            "--limit",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    # stdout, not the mixed .output: the resolved-path banner (Milestone 0 of
    # reqs-to-data-store.md) prints to stderr on every run, and .output mixes
    # stdout+stderr, which would corrupt this JSON parse.
    payload = json.loads(result.stdout)
    assert set(payload.keys()) == {
        "total",
        "claimed",
        "uncovered",
        "pct",
        "uncovered_chunks",
    }
    assert payload["claimed"] == 0
    assert payload["pct"] == 0.0
    # --limit bounds the listed chunks but counts stay exact.
    assert len(payload["uncovered_chunks"]) <= 3
    assert payload["uncovered"] == payload["total"]
    if payload["uncovered_chunks"]:
        chunk = payload["uncovered_chunks"][0]
        assert set(chunk.keys()) == {
            "chunk_id",
            "path",
            "start_line",
            "end_line",
            "symbol",
        }


def test_cli_coverage_warns_on_zero_match(indexed_repo: Path, tmp_path: Path) -> None:
    """Citations supplied but nothing matched (unresolvable base) must warn —
    a broken handoff must not read as a legitimate 0%."""
    claimed_file = tmp_path / "claimed.txt"
    # A path that shares no suffix with any indexed chunk.
    claimed_file.write_text("no/such/Nonexistent12345.xyz:1-9\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "coverage",
            "--repo-root",
            str(indexed_repo),
            "--claimed",
            str(claimed_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "0 chunks matched" in result.output


def test_cli_coverage_limit_bounds_list(indexed_repo: Path, tmp_path: Path) -> None:
    claimed_file = tmp_path / "claimed.json"
    claimed_file.write_text("[]", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "coverage",
            "--repo-root",
            str(indexed_repo),
            "--claimed",
            str(claimed_file),
            "--json",
            "--limit",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    # stdout, not the mixed .output: the resolved-path banner (Milestone 0 of
    # reqs-to-data-store.md) prints to stderr on every run, and .output mixes
    # stdout+stderr, which would corrupt this JSON parse.
    payload = json.loads(result.stdout)
    assert len(payload["uncovered_chunks"]) == 1
    assert payload["total"] > 1


def test_cli_coverage_missing_claimed_file(indexed_repo: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "coverage",
            "--repo-root",
            str(indexed_repo),
            "--claimed",
            str(indexed_repo / "no_such_file.json"),
        ],
    )
    assert result.exit_code == 1, result.output
    assert "not found" in result.output.lower()


def test_cli_coverage_missing_index(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    claimed_file = tmp_path / "claimed.json"
    claimed_file.write_text("[]", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "coverage",
            "--repo-root",
            str(repo),
            "--claimed",
            str(claimed_file),
        ],
    )
    assert result.exit_code == 1, result.output
    assert "missing" in result.output.lower()
