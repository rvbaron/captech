"""Tests for citation parsing and anchor resolution (M1 Step 6a).

`resolve_anchor`'s output is a **hash input**: `sorted(anchor_keys)` is the
tier-1 input to both `dedupe_key` and `dedupe_key_anchor_only`. So these tests
are not about tidiness -- each one pins a value whose divergence would change
what stage one of the merge decides, silently and with no error anywhere.

The acceptance criteria from Step 6a, and the test that carries each:

1. innermost containing symbol wins, not its enclosing class
2. an unindexed / non-code file takes the file-level anchor
3. no resolution anywhere ever returns an empty `primary`
4. the file-level anchor is byte-identical before and after an `index` run
5. an absent path is `unresolved` with a computed, non-empty anchor
6. a range spanning three siblings picks the smallest-span intersector, and a
   fourth unrelated declaration inside that range does not move the primary
7. `store=None` takes the floor and creates no `index.sqlite`
8. a stale index refuses its symbol match in favour of the floor
9. the per-run cache hashes each cited file exactly once
10. `parse_citation` strict mode surfaces what non-strict skips, and the
    `cli.py` caller's behaviour is unchanged
11. a comma-separated multi-range citation yields one triple per range, and
    each range resolves its own symbol anchor (deferred item 11)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from legacylift_search import citations
from legacylift_search.citations import (
    WHOLE_FILE_END_LINE,
    AnchorResolver,
    CitationParseError,
    parse_citation,
    resolve_anchor,
)
from legacylift_search.cli import _parse_claimed_citations
from legacylift_search.config import Manifest
from legacylift_search.identity import file_anchor_key
from legacylift_search.migrations import symbol_anchor_key
from legacylift_search.models import SourceFile, Symbol, TextRange
from legacylift_search.store import SQLiteStore

# ----------------------------------------------------------------------
# Fixtures built by hand, because these tests are about exact line spans
# ----------------------------------------------------------------------

_JAVA = "src/main/java/Station.java"
_INI = "conf/app.ini"


def _write(repo: Path, relative_path: str, lines: int) -> SourceFile:
    """Write a file of `lines` numbered lines and describe it as indexed."""
    absolute = repo / relative_path
    absolute.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"line {n}\n" for n in range(1, lines + 1))
    absolute.write_bytes(body.encode("utf-8"))
    raw = absolute.read_bytes()
    return SourceFile(
        absolute_path=absolute,
        repo_root=repo,
        relative_path=relative_path,
        language="java",
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        mtime_ns=absolute.stat().st_mtime_ns,
    )


def _symbol(
    qualified_name: str,
    entity_class: str,
    start_line: int,
    end_line: int,
    *,
    suffix: str = "",
) -> Symbol:
    """One `Symbol` with an exact line span.

    `entity_class` must be one of `identity.ENTITY_CLASSES`' seven values --
    a plausible-looking word like `operation` is a pydantic validation error,
    which is Step 2 doing its job.
    """
    return Symbol(
        id=f"java:{qualified_name}:{start_line}{suffix}",
        language="java",
        name=qualified_name.rsplit(".", 1)[-1],
        qualified_name=qualified_name,
        kind="method_declaration" if entity_class == "function" else "class_declaration",
        entity_class=entity_class,
        # Byte bounds are a point on purpose: `symbol_body_text` falls back to
        # the line bounds, and nothing here depends on the body.
        range=TextRange(
            start_byte=0, end_byte=0, start_line=start_line, end_line=end_line
        ),
    )


def _seed(
    tmp_path: Path, symbols: list[Symbol], *, lines: int = 60
) -> tuple[Path, Path, SourceFile]:
    """A repo with one indexed Java file plus an unindexed `.ini`, and an index.

    Returns `(repo_root, index_sqlite_path, java_source_file)`.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    java = _write(repo, _JAVA, lines)
    _write(repo, _INI, 5)
    index_path = tmp_path / "index" / "index.sqlite"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(index_path)
    try:
        store.migrate()
        store.upsert_files([java])
        store.upsert_symbols(java, symbols)
    finally:
        store.close()
    return repo, index_path, java


def _keys(resolution) -> set[str]:
    return {hit.anchor_key for hit in resolution.all}


# ----------------------------------------------------------------------
# 1. innermost, and exactly one
# ----------------------------------------------------------------------


def test_citation_in_a_method_takes_the_method_not_its_class(
    tmp_path: Path,
) -> None:
    """A citation inside an indexed method carries the INNERMOST containing
    symbol's `anchor_key` with `resolution = 'symbol'` -- not its enclosing
    class. Were the class to win, adding an unrelated sibling method to it
    would re-key this rule."""
    repo, index_path, _ = _seed(
        tmp_path,
        [
            _symbol("Station", "type", 1, 20),
            _symbol("Station.updatePhysVol", "function", 5, 10),
        ],
    )
    store = SQLiteStore(index_path)
    try:
        got = resolve_anchor(store, repo, _JAVA, 6, 8)
    finally:
        store.close()

    method_key = symbol_anchor_key("java", "function", "Station.updatePhysVol", _JAVA)
    class_key = symbol_anchor_key("java", "type", "Station", _JAVA)

    assert got.resolution == "symbol"
    assert got.primary == method_key
    assert got.primary != class_key
    # The class is still *recorded* -- the full set answers "which symbols does
    # this requirement touch?" -- it just is not the key input.
    assert _keys(got) == {method_key, class_key}
    assert all(hit.containment == "contains" for hit in got.all)
    assert got.all[0].anchor_key == method_key, "the primary sorts first"


# ----------------------------------------------------------------------
# 2. the file-level floor
# ----------------------------------------------------------------------


def test_unindexed_file_takes_the_file_level_anchor(tmp_path: Path) -> None:
    """A citation in a non-code file the indexer never opened carries the
    file-level anchor with `resolution = 'file'`. `.ini` fails `include_globs`,
    so it is in the tree and not in `repo_files` -- the common case, and the
    one an empty-string fallback would collapse."""
    repo, index_path, _ = _seed(tmp_path, [_symbol("Station", "type", 1, 20)])
    store = SQLiteStore(index_path)
    try:
        got = resolve_anchor(store, repo, _INI, 2, 3)
    finally:
        store.close()

    assert got.resolution == "file"
    assert got.primary == file_anchor_key(_INI)
    assert _keys(got) == {file_anchor_key(_INI)}


def test_lines_between_declarations_take_the_file_level_anchor(
    tmp_path: Path,
) -> None:
    """An indexed file whose symbols do not reach the cited lines still
    resolves -- to `file`, not to nothing. The floor is total."""
    repo, index_path, _ = _seed(tmp_path, [_symbol("Station.go", "function", 5, 10)])
    store = SQLiteStore(index_path)
    try:
        got = resolve_anchor(store, repo, _JAVA, 40, 42)
    finally:
        store.close()

    assert got.resolution == "file"
    assert got.primary == file_anchor_key(_JAVA)


def test_a_bare_path_meaning_the_whole_file_takes_the_file_anchor(
    tmp_path: Path,
) -> None:
    """A citation with no line range means the whole file, which Step 6a
    assigns to the file grain by name. Resolving it against symbols would hand
    a whole-file citation to whichever declaration happened to be smallest."""
    repo, index_path, _ = _seed(
        tmp_path,
        [
            _symbol("Station", "type", 1, 20),
            _symbol("Station.go", "function", 5, 10),
        ],
    )
    (path, start, end), = parse_citation(_JAVA)
    assert (start, end) == (1, WHOLE_FILE_END_LINE)
    store = SQLiteStore(index_path)
    try:
        got = resolve_anchor(store, repo, path, start, end)
    finally:
        store.close()

    assert got.resolution == "file"
    assert got.primary == file_anchor_key(_JAVA)


# ----------------------------------------------------------------------
# 3. never empty
# ----------------------------------------------------------------------


def test_no_resolution_ever_returns_an_empty_primary(tmp_path: Path) -> None:
    """**The value that silently collapses stage-one dedupe.** An empty
    `primary` degenerates `dedupe_key_anchor_only` to `'' + rule_class +
    pattern`, identical for every rule in the corpus sharing a class and a
    pattern, and stage one auto-merges them. Every branch of the function is
    exercised here: symbol, file, unresolved, no-store, whole-file, stale."""
    repo, index_path, java = _seed(
        tmp_path,
        [
            _symbol("Station", "type", 1, 20),
            _symbol("Station.go", "function", 5, 10),
        ],
    )
    cases = [
        (_JAVA, 6, 8),  # symbol
        (_JAVA, 40, 42),  # indexed file, no overlap
        (_JAVA, 1, WHOLE_FILE_END_LINE),  # whole file
        (_INI, 1, 2),  # in the tree, not in the index
        ("does/not/exist.cs", 1, 5),  # unresolved
        ("", 1, 5),  # degenerate path
    ]
    store = SQLiteStore(index_path)
    try:
        for relative_path, start, end in cases:
            for candidate_store in (store, None):
                got = resolve_anchor(candidate_store, repo, relative_path, start, end)
                assert got.primary, (relative_path, start, end)
                assert got.all and all(h.anchor_key for h in got.all)
        # And once more against a stale index.
        java.absolute_path.write_text("mutated\n", encoding="utf-8")
        got = resolve_anchor(store, repo, _JAVA, 6, 8)
        assert got.primary
    finally:
        store.close()


# ----------------------------------------------------------------------
# 4. index independence
# ----------------------------------------------------------------------


def test_the_file_level_anchor_is_index_independent(tmp_path: Path) -> None:
    """The same citation must key identically before and after an `index` run.
    This fails the moment anyone resolves `language` from `repo_files` or calls
    `detect_language`: `file_anchor_key` fixes it at the empty string
    (SPEC-3 §S3.1.1) precisely so a tier-1 dedupe-key input cannot become a
    function of index state."""
    from legacylift_search.indexer import Indexer

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "Station.java").write_text(
        "public class Station {\n  void go() {\n    int x = 1;\n  }\n}\n",
        encoding="utf-8",
    )
    (repo / "conf").mkdir()
    (repo / "conf" / "app.ini").write_text(
        "[limits]\nmax_volume = 40\n", encoding="utf-8"
    )

    before = resolve_anchor(None, repo, "conf/app.ini", 2, 2)

    manifest = Manifest()
    manifest.embedding.provider = "hash"
    manifest.embedding.dimension = 64
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")
    index_path = (
        repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    )
    assert index_path.exists(), "the fixture repo must actually have indexed"

    store = SQLiteStore(index_path)
    try:
        after = resolve_anchor(store, repo, "conf/app.ini", 2, 2)
    finally:
        store.close()

    assert before.primary == after.primary
    assert before.resolution == after.resolution == "file"


# ----------------------------------------------------------------------
# 5. unresolved
# ----------------------------------------------------------------------


def test_an_absent_path_is_unresolved_with_a_computed_anchor(
    tmp_path: Path,
) -> None:
    """`unresolved` means one thing: the cited path is not in the working
    tree. It is not a tier beneath the floor -- the anchor is still computed,
    because the key space must stay bounded by path -- and the label is what
    stops the store carrying confident-looking anchors for absent files."""
    repo, index_path, _ = _seed(tmp_path, [_symbol("Station", "type", 1, 20)])
    store = SQLiteStore(index_path)
    try:
        got = resolve_anchor(store, repo, "src/main/java/Gone.java", 3, 9)
    finally:
        store.close()

    assert got.resolution == "unresolved"
    assert got.primary == file_anchor_key("src/main/java/Gone.java")
    assert got.primary != ""
    assert _keys(got) == {got.primary}


# ----------------------------------------------------------------------
# 6. the tie-break, and the set staying out of the key
# ----------------------------------------------------------------------


def test_three_siblings_pick_the_smallest_span_intersector(
    tmp_path: Path,
) -> None:
    """A citation spanning three sibling declarations resolves to exactly the
    smallest-span intersector, `all` holds three hits marked `intersects`, and
    -- the assertion that matters -- adding a FOURTH unrelated declaration
    inside that range leaves the primary byte-identical. That is what proves
    the child set stayed out of the key: were `all` hashed, an unrelated
    sibling appearing inside a cited range would re-key a rule whose own cited
    code never changed."""
    siblings = [
        _symbol("Station.first", "function", 10, 19),  # span 9
        _symbol("Station.second", "function", 21, 32),  # span 11
        _symbol("Station.third", "function", 34, 40),  # span 6  <- winner
    ]
    repo, index_path, java = _seed(tmp_path, siblings)
    store = SQLiteStore(index_path)
    try:
        got = resolve_anchor(store, repo, _JAVA, 10, 40)

        expected = symbol_anchor_key("java", "function", "Station.third", _JAVA)
        assert got.resolution == "symbol"
        assert got.primary == expected
        assert len(got.all) == 3
        assert {h.containment for h in got.all} == {"intersects"}
        assert _keys(got) == {
            symbol_anchor_key("java", "function", f"Station.{n}", _JAVA)
            for n in ("first", "second", "third")
        }

        # A fourth, unrelated declaration inside the cited range. Its span (9)
        # is larger than the winner's, so nothing about this rule's own cited
        # code has changed.
        store.upsert_symbols(
            java, siblings + [_symbol("Station.inner", "function", 22, 31)]
        )
        again = resolve_anchor(store, repo, _JAVA, 10, 40)
    finally:
        store.close()

    assert again.primary == got.primary, "the primary must be byte-identical"
    assert len(again.all) == 4, "the full set does grow -- it is just not a key"


def test_the_tie_break_is_start_line_then_qualified_name(tmp_path: Path) -> None:
    """Equal spans break by smallest `start_line`, then by `qualified_name`
    ascending. Written as stated and asserted here because the value is
    hashed: two implementations that break a tie differently produce different
    `dedupe_key`s for the same rule, and the merge stops working with no error
    anywhere."""
    repo, index_path, _ = _seed(
        tmp_path,
        [
            # Same span (4), different start lines -> line 12 wins.
            _symbol("Station.bbb", "function", 12, 16),
            _symbol("Station.ccc", "function", 20, 24),
            # Same span AND same start line as `bbb`, so only the name
            # separates them -- and `Station.aaa` sorts first.
            _symbol("Station.aaa", "function", 12, 16, suffix="-b"),
        ],
    )
    store = SQLiteStore(index_path)
    try:
        got = resolve_anchor(store, repo, _JAVA, 10, 30)
    finally:
        store.close()

    assert got.primary == symbol_anchor_key(
        "java", "function", "Station.aaa", _JAVA
    )


# ----------------------------------------------------------------------
# 7. no index at all
# ----------------------------------------------------------------------


def test_no_store_takes_the_floor_and_creates_no_index(tmp_path: Path) -> None:
    """`store=None` is a supported ingest, not an error path: every citation
    takes the file-level floor with `resolution = 'file'`, which is correct
    rather than degraded because the floor is index-independent. And it must
    create nothing -- `SQLiteStore._connect` materializes the database file on
    its first query, so a non-optional parameter here would leave an empty
    `index.sqlite` beside a repository that was never indexed and then fail on
    `no such table: symbols`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write(repo, _JAVA, 30)
    _write(repo, _INI, 4)
    index_path = repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"

    for relative_path, start, end in ((_JAVA, 6, 8), (_INI, 1, 2), (_JAVA, 1, 30)):
        got = resolve_anchor(None, repo, relative_path, start, end)
        assert got.resolution == "file"
        assert got.primary == file_anchor_key(relative_path)

    assert not index_path.exists()
    assert list(repo.rglob("*.sqlite")) == []


# ----------------------------------------------------------------------
# 8. the staleness guard
# ----------------------------------------------------------------------


def test_a_stale_index_refuses_its_symbol_match(tmp_path: Path) -> None:
    """When the file's on-disk `sha256` no longer equals the stored
    `repo_files.sha256`, the symbol ranges describe source that is no longer
    there -- so the file-level anchor is preferred over a confidently wrong
    symbol anchor that would feed both dedupe keys."""
    repo, index_path, java = _seed(
        tmp_path, [_symbol("Station.updatePhysVol", "function", 5, 10)]
    )
    store = SQLiteStore(index_path)
    try:
        fresh = resolve_anchor(store, repo, _JAVA, 6, 8)
        assert fresh.resolution == "symbol"

        java.absolute_path.write_text(
            "// the file has moved on since it was indexed\n", encoding="utf-8"
        )
        stale = resolve_anchor(store, repo, _JAVA, 6, 8)
    finally:
        store.close()

    assert stale.resolution == "file"
    assert stale.primary == file_anchor_key(_JAVA)
    assert stale.primary != fresh.primary


# ----------------------------------------------------------------------
# 9. the per-run hash cache
# ----------------------------------------------------------------------


def test_each_cited_file_is_hashed_once_per_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The staleness guard is a per-FILE question while citations are
    per-rule, and a dense corpus cites the same file hundreds of times. With
    the run's cache in hand each file is visited exactly once, however many
    citations name it."""
    repo, index_path, _ = _seed(
        tmp_path, [_symbol("Station.updatePhysVol", "function", 5, 10)]
    )

    calls: list[str] = []
    real = citations._read_file_state

    def spy(absolute_path: Path):
        calls.append(str(absolute_path))
        return real(absolute_path)

    monkeypatch.setattr(citations, "_read_file_state", spy)

    store = SQLiteStore(index_path)
    try:
        resolver = AnchorResolver(store=store, repo_root=repo)
        for start in range(5, 11):
            resolver.resolve(_JAVA, start, start)
        assert len(calls) == 1, calls

        # A second file is a second visit, and only one.
        resolver.resolve(_INI, 1, 2)
        resolver.resolve(_INI, 3, 4)
        assert len(calls) == 2, calls
        assert len(resolver.hash_cache) == 2

        # Without a cache every call visits the tree -- which is the naive
        # form this exists to replace, so it is pinned rather than assumed.
        calls.clear()
        for start in range(5, 11):
            resolve_anchor(store, repo, _JAVA, start, start)
        assert len(calls) == 6
    finally:
        store.close()


def test_the_cache_is_not_module_state(tmp_path: Path) -> None:
    """Two resolvers over the same paths must not share a cache: a cache that
    outlived its run would answer the staleness guard from a previous run's
    hashes, which is the stale-index failure moved from the database into
    memory."""
    repo, index_path, java = _seed(
        tmp_path, [_symbol("Station.updatePhysVol", "function", 5, 10)]
    )
    store = SQLiteStore(index_path)
    try:
        first = AnchorResolver(store=store, repo_root=repo)
        assert first.resolve(_JAVA, 6, 8).resolution == "symbol"

        java.absolute_path.write_text("mutated\n", encoding="utf-8")
        second = AnchorResolver(store=store, repo_root=repo)
        assert second.resolve(_JAVA, 6, 8).resolution == "file"
        assert second.hash_cache is not first.hash_cache
    finally:
        store.close()


# ----------------------------------------------------------------------
# 10. the parser, and its strict mode
# ----------------------------------------------------------------------


def test_one_entry_may_carry_several_whole_citations() -> None:
    """The extractor writes two files in one `source`, and both must survive.

    Measured on the first scoped two-round run: 30 citations on 29 of 186
    rules. Unsplit, `rpartition(":")` takes the *last* colon, so the path
    becomes the whole comma-joined string and the line numbers belong to the
    second file -- the first range is discarded and the citation resolves
    `unresolved` while ingest exits zero.
    """
    assert parse_citation("src/a.cs:96-118, src/b.cs:44-51") == [
        ("src/a.cs", 96, 118),
        ("src/b.cs", 44, 51),
    ]
    # A third of the measured cases were the same file twice with the path
    # repeated, rather than the `path:a-b,c-d` form already supported.
    assert parse_citation("src/a.cs:105-127, src/a.cs:264-305") == [
        ("src/a.cs", 105, 127),
        ("src/a.cs", 264, 305),
    ]
    assert parse_citation("a.cs:1-2, b.cs:5-9, c.cs:7") == [
        ("a.cs", 1, 2),
        ("b.cs", 5, 9),
        ("c.cs", 7, 7),
    ]
    # The two shapes compose: a citation in a list may name several ranges.
    assert parse_citation("a.cs:1-2,8-9, b.cs:5-9") == [
        ("a.cs", 1, 2),
        ("a.cs", 8, 9),
        ("b.cs", 5, 9),
    ]
    # Strict mode agrees, since nothing here is malformed.
    for raw in (
        "src/a.cs:96-118, src/b.cs:44-51",
        "a.cs:1-2,8-9, b.cs:5-9",
    ):
        assert parse_citation(raw, strict=True) == parse_citation(raw)


def test_a_malformed_piece_leaves_the_whole_entry_as_it_was() -> None:
    """All-or-nothing at the ENTRY grain, not the citation grain.

    `_split_citations` recognizes a list only when every piece is well
    formed. One piece that is neither a whole `path:range` nor a bare-range
    continuation means the entry keeps exactly the shape it had before the
    splitter existed -- because half a citation keys a rule on a subset of its
    evidence and looks healthy.
    """
    # Second piece is a path with no range: not a citation list.
    assert parse_citation("a.cs:1-2, b.cs") == [
        ("a.cs:1-2, b.cs", 1, WHOLE_FILE_END_LINE)
    ]
    # First piece carries no range: not a citation list either.
    assert parse_citation("a.cs, b.cs:5-9") == [("a.cs, b.cs", 5, 9)]
    # Prose after a good citation stays the pre-existing whole-file fallback.
    assert parse_citation("a.cs:1-2, and also see b") == [
        ("a.cs:1-2, and also see b", 1, WHOLE_FILE_END_LINE)
    ]


def test_parse_citation_handles_the_shapes_the_extractor_emits() -> None:
    """The promoted parser is the SAME parser: the extractor's `path:line-line`
    shape, a JSON array, newline-delimited text, leading list markers, colons
    inside paths, and a bare path meaning the whole file."""
    assert parse_citation('["src/a.cs:10-20", "src/b.cs:5-5"]') == [
        ("src/a.cs", 10, 20),
        ("src/b.cs", 5, 5),
    ]
    assert parse_citation("src/a.cs:10-20\nsrc/b.cs:5-5\n") == [
        ("src/a.cs", 10, 20),
        ("src/b.cs", 5, 5),
    ]
    assert parse_citation("- src/a.cs:10-20") == [("src/a.cs", 10, 20)]
    assert parse_citation("• src/c.cs:7") == [("src/c.cs", 7, 7)]
    assert parse_citation("src/a.cs") == [("src/a.cs", 1, WHOLE_FILE_END_LINE)]
    assert parse_citation("C:\\repo\\a.cs:10-20") == [("C:\\repo\\a.cs", 10, 20)]


@pytest.mark.parametrize(
    "raw",
    [
        '["src/a.cs:10-20",',  # opens like JSON, is not JSON
        '["src/a.cs:10-20" "src/b.cs:1-2"]',  # a missing comma, so not JSON
        "- ",  # nothing but a list marker
        "*",  # ditto
        "src/a.cs:1-2-3",  # a range that is not a start-end pair
        "src/a.cs:--",  # ditto
        "src/a.cs:10-20,",  # a trailing comma leaves an empty piece
        "src/a.cs:10-20,1-2-3",  # one bad piece fails the whole entry
        "src/a.cs:,",  # nothing but separators
    ],
)
def test_strict_mode_surfaces_what_non_strict_skips(raw: str) -> None:
    """Skipping a malformed entry silently is right for coverage's best-effort
    denominator and **wrong at ingest**, where a dropped citation is a dropped
    `anchor_key` and therefore a silently different `dedupe_key`. Strict mode
    raises instead of dropping; non-strict never raises."""
    with pytest.raises(CitationParseError):
        parse_citation(raw, strict=True)

    parse_citation(raw)  # must not raise
    parse_citation(raw, strict=False)


def test_the_cli_coverage_caller_is_unchanged() -> None:
    """`cli._parse_claimed_citations` keeps its name, signature and behaviour
    -- it now delegates with `strict=False`, so the coverage denominator sees
    byte-identical results and its existing caller is untouched."""
    for raw in (
        '["src/a.cs:10-20", "src/b.cs:5-5"]',
        "src/a.cs:10-20\nsrc/b.cs:5-5\n",
        "- src/a.cs:10-20\n\n- src/b.cs:5-5\n",
        '["- src/a.cs:10-20"]',
        "src/a.cs",
        "src/a.cs:42",
        '["src/a.cs:10-20",',
        "- ",
        "src/a.cs:1-2-3",
    ):
        assert _parse_claimed_citations(raw) == parse_citation(raw, strict=False)

    # And the documented shapes, spelled out.
    assert _parse_claimed_citations("src/a.cs") == [
        ("src/a.cs", 1, 2**31 - 1)
    ]
    assert _parse_claimed_citations('["src/a.cs:10-20",') == []


def test_a_colonless_entry_is_a_whole_file_citation_not_an_error():
    """Prose in the `source` field parses as a whole-file citation on a
    missing path, and is surfaced by `unresolved` rather than by a raise.

    This pins a deliberate limitation rather than a desired behaviour. An
    entry with no colon cannot be told apart from "a bare path meaning the
    whole file", a shape Step 6a requires this parser to accept, and no
    whitespace or extension rule separates them reliably (a repo-relative
    path may contain spaces and may have no extension). Since strict mode
    raises and one ingest is one transaction, a false raise would reject a
    whole extraction -- worse than accepting the entry and labelling it.

    So the fault surfaces one layer out, as `anchor_resolution =
    'unresolved'`, which it shares with the case that label was written for
    (an extraction taken against a different checkout). The docstring on
    `parse_citation` records why they are allowed to share it and what
    `requirements stats` must therefore say about the rate. If someone later
    tightens strict mode, this test should fail and be deleted deliberately.
    """
    parsed = parse_citation("not a citation at all", strict=True)
    assert parsed == [("not a citation at all", 1, WHOLE_FILE_END_LINE)]

    # And the same input in lenient mode, so the two modes are known to agree
    # here -- the coverage denominator counts it the same way.
    assert parse_citation("not a citation at all") == parsed


# ----------------------------------------------------------------------
# 11. multi-range citations (deferred item 11)
# ----------------------------------------------------------------------


def test_a_multi_range_citation_yields_one_triple_per_range() -> None:
    """`path:24-26,62-70` is a well-formed citation naming TWO ranges in one
    file, and the extractor emits it: 9 of 133 confirmed rules did so on the
    first real NNG extraction. It parses to one triple per range, sharing a
    path.

    Before this, the comma failed the trailing-range character test, so the
    whole entry -- range text included -- became the *path* of a single
    whole-file citation. That path does not exist in the tree, so every
    affected rule resolved `unresolved` and fell out of tier 1 of its
    `dedupe_key`, silently and with a zero exit.
    """
    real = "ple-model/JavaSource/com/nng/ple/model/LesstatusHistory.java"
    assert parse_citation(f"{real}:24-26,62-70") == [
        (real, 24, 26),
        (real, 62, 70),
    ]

    # Both modes agree: the coverage denominator and ingest see the same two
    # spans, which is the whole reason there is one parser.
    assert parse_citation(f"{real}:24-26,62-70", strict=True) == parse_citation(
        f"{real}:24-26,62-70"
    )

    # Three ranges, bare line numbers, and a single-range control that must
    # keep parsing exactly as it always did.
    assert parse_citation("src/a.cs:5,10-12,20") == [
        ("src/a.cs", 5, 5),
        ("src/a.cs", 10, 12),
        ("src/a.cs", 20, 20),
    ]
    assert parse_citation("src/a.cs:10-20") == [("src/a.cs", 10, 20)]

    # A JSON array of two entries, one of them multi-range, is 3 triples --
    # the list length is not the number of citations.
    assert parse_citation('["src/a.cs:1-2,8-9", "src/b.cs:5-5"]') == [
        ("src/a.cs", 1, 2),
        ("src/a.cs", 8, 9),
        ("src/b.cs", 5, 5),
    ]


def test_each_range_of_a_multi_range_citation_resolves_its_own_anchor(
    tmp_path: Path,
) -> None:
    """The parse change is only worth making because of what it does to the
    KEY: each range resolves to its own innermost symbol, so an affected rule
    gains a second tier-1 anchor instead of a single `unresolved` file anchor.

    That is why deferred item 11 argues for landing this before the first kept
    ingest -- afterwards it is a re-key migration over `knowledge.sqlite`
    rather than a code change.
    """
    repo, index_path, _ = _seed(
        tmp_path,
        [
            _symbol("Station", "type", 1, 60),
            _symbol("Station.first", "function", 10, 20),
            _symbol("Station.second", "function", 30, 40),
        ],
    )
    parsed = parse_citation(f"{_JAVA}:12-14,32-34", strict=True)
    assert len(parsed) == 2

    store = SQLiteStore(index_path)
    try:
        resolver = AnchorResolver(store=store, repo_root=repo)
        primaries = [resolver.resolve(*triple).primary for triple in parsed]
        resolutions = [resolver.resolve(*triple).resolution for triple in parsed]
    finally:
        store.close()

    assert resolutions == ["symbol", "symbol"]
    assert primaries == [
        symbol_anchor_key("java", "function", "Station.first", _JAVA),
        symbol_anchor_key("java", "function", "Station.second", _JAVA),
    ]
    # Two distinct anchors, and neither is the floor the old behaviour gave.
    assert len(set(primaries)) == 2
    assert file_anchor_key(_JAVA) not in primaries


def test_a_malformed_piece_fails_the_whole_multi_range_entry() -> None:
    """One unparseable piece does not silently keep the pieces that parsed.

    Half a citation is worse than none: it would produce a rule keyed on a
    subset of its evidence, which looks healthy. Strict mode raises (ingest);
    non-strict falls back to the pre-existing whole-entry-as-path behaviour,
    which `resolve_anchor` then labels `unresolved`.
    """
    with pytest.raises(CitationParseError):
        parse_citation("src/a.cs:10-20,1-2-3", strict=True)

    assert parse_citation("src/a.cs:10-20,1-2-3") == [
        ("src/a.cs:10-20,1-2-3", 1, WHOLE_FILE_END_LINE)
    ]

    # A piece that is not numeric at all never reaches the range parser: the
    # trailing-range character test rejects it first, so the entry keeps its
    # old whole-file shape in BOTH modes and strict mode does not raise. That
    # is the same deliberate limitation
    # `test_a_colonless_entry_is_a_whole_file_citation_not_an_error` pins,
    # widened by exactly one character.
    assert parse_citation("src/a.cs:10-20,oops", strict=True) == [
        ("src/a.cs:10-20,oops", 1, WHOLE_FILE_END_LINE)
    ]
