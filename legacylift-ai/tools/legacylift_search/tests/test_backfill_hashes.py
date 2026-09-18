"""Tests for the resumable `backfill-hashes` subcommand (M1 Step 2).

`INDEX_MIGRATIONS` version 2 adds `symbols.content_hash` and leaves it NULL,
because the body text it hashes is not stored in `symbols` and, on an
existing database, the file on disk may no longer be the file that produced
those rows. This command is how the column actually gets filled in.

The reason it has to exist at all is the M15 skip-on-unchanged fast path: an
`index` rerun compares each file's `sha256` against `repo_files.sha256` and
re-extracts only the changed ones, so on any existing index the overwhelming
majority of symbols are never revisited and would stay NULL forever --
silently disabling the drift-versus-clone matrix, with nothing raising.
`test_a_plain_reindex_does_not_fill_the_column` pins exactly that, so the
command cannot later be deleted as redundant.

Required behaviours:

1. With `content_hash` cleared, `backfill-hashes` restores it in full.
2. A second run is a no-op.
3. A file that drifted after indexing is **skipped and left NULL**, never
   hashed -- hashing it would attribute a hash to source that never produced
   that symbol, the precise error a migration-time backfill was rejected for.
4. A drifted file's rows are recovered by the next real `index` run, because
   a drifted file is by definition a changed file.
5. The CLI command works end to end.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest
from legacylift_search.indexer import Indexer
from legacylift_search.store import SQLiteStore

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _manifest() -> Manifest:
    m = Manifest()
    m.embedding.provider = "hash"
    m.embedding.dimension = 64
    return m


def _sqlite_path(repo: Path) -> Path:
    return repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"


def _clear_content_hashes(repo: Path) -> int:
    """Put the index in the state the version-2 migration leaves it in.

    The migration adds the column and backfills nothing into it, so an index
    that has just been brought forward looks exactly like this.
    """
    store = SQLiteStore(_sqlite_path(repo))
    try:
        conn = store._connect()
        conn.execute("UPDATE symbols SET content_hash = NULL")
        conn.commit()
        return int(
            conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        )
    finally:
        store.close()


def _hash_state(repo: Path) -> tuple[int, int]:
    """Return `(rows_with_a_hash, rows_still_null)`."""
    store = SQLiteStore(_sqlite_path(repo))
    try:
        conn = store._connect()
        filled = int(
            conn.execute(
                "SELECT COUNT(*) FROM symbols WHERE content_hash IS NOT NULL"
            ).fetchone()[0]
        )
        null = int(
            conn.execute(
                "SELECT COUNT(*) FROM symbols WHERE content_hash IS NULL"
            ).fetchone()[0]
        )
        return filled, null
    finally:
        store.close()


def _one_indexed_file(repo: Path) -> str:
    """Return the relative path of the indexed file holding the most symbols.

    Picked by symbol count rather than by name so the test does not depend on
    which fixture files the extractors happen to parse.
    """
    store = SQLiteStore(_sqlite_path(repo))
    try:
        row = (
            store._connect()
            .execute(
                """
                SELECT f.relative_path, COUNT(*) AS n
                FROM symbols s JOIN repo_files f ON f.id = s.file_id
                GROUP BY f.relative_path ORDER BY n DESC LIMIT 1
                """
            )
            .fetchone()
        )
        assert row is not None, "fixture produced no symbols"
        return row["relative_path"]
    finally:
        store.close()


def _index(repo: Path, manifest: Manifest, reset: bool = False):
    return Indexer(manifest, repo).run(
        reset=reset, embedding_provider_override="hash"
    )


# ----------------------------------------------------------------------


def test_indexing_writes_content_hashes_on_the_insert_path(
    tmp_path: Path,
) -> None:
    """A fresh index needs no backfill at all: the insert path hashes as it
    writes, so the command is a repair tool and not a required second step."""
    repo = _copy_fixture(tmp_path)
    _index(repo, _manifest(), reset=True)

    filled, null = _hash_state(repo)
    assert filled > 0
    assert null == 0


def test_backfill_fills_every_null_hash(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    _index(repo, manifest, reset=True)

    total = _clear_content_hashes(repo)
    assert _hash_state(repo) == (0, total)

    stats = Indexer(manifest, repo).backfill_hashes()

    assert stats.symbols_missing == total
    assert stats.symbols_hashed == total
    assert stats.symbols_skipped == 0
    assert stats.files_drifted == 0
    assert stats.files_unreadable == 0
    assert stats.symbols_unhashable == 0
    assert stats.remaining_null == 0
    assert _hash_state(repo) == (total, 0)


def test_backfill_reproduces_the_hashes_the_insert_path_wrote(
    tmp_path: Path,
) -> None:
    """The two write paths must agree, for the same reason the migration and
    the insert path must agree on `anchor_key`: a body sliced differently at
    the two sites yields two hashes for one unchanged entity, and the
    difference reads as drift."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    _index(repo, manifest, reset=True)

    def _hashes() -> dict[str, str]:
        store = SQLiteStore(_sqlite_path(repo))
        try:
            return dict(
                store._connect()
                .execute("SELECT id, content_hash FROM symbols")
                .fetchall()
            )
        finally:
            store.close()

    from_insert = _hashes()
    _clear_content_hashes(repo)
    Indexer(manifest, repo).backfill_hashes()

    assert _hashes() == from_insert


def test_second_backfill_is_a_noop(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    _index(repo, manifest, reset=True)
    _clear_content_hashes(repo)

    Indexer(manifest, repo).backfill_hashes()
    second = Indexer(manifest, repo).backfill_hashes()

    assert second.symbols_missing == 0
    assert second.symbols_hashed == 0
    assert second.remaining_null == 0


def test_a_drifted_file_is_skipped_and_left_null(tmp_path: Path) -> None:
    """The rule the command exists to enforce.

    The file's bytes changed after it was indexed, so its stored byte ranges
    no longer describe the source that produced those rows. Hashing it would
    write a hash for source that never produced that symbol. The rows are
    left NULL instead, and reported as skipped rather than as an error.
    """
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    _index(repo, manifest, reset=True)

    target = _one_indexed_file(repo)
    total = _clear_content_hashes(repo)

    store = SQLiteStore(_sqlite_path(repo))
    try:
        drifted_symbol_ids = {
            r["id"]
            for r in store._connect()
            .execute(
                """
                SELECT s.id FROM symbols s
                JOIN repo_files f ON f.id = s.file_id
                WHERE f.relative_path = ?
                """,
                (target,),
            )
            .fetchall()
        }
    finally:
        store.close()
    assert drifted_symbol_ids

    # Drift it: same file, different bytes, no reindex.
    path = repo / target
    path.write_text(
        path.read_text(encoding="utf-8") + "\n// edited after indexing\n",
        encoding="utf-8",
    )

    stats = Indexer(manifest, repo).backfill_hashes()

    assert stats.files_drifted == 1
    assert stats.symbols_skipped == len(drifted_symbol_ids)
    assert stats.symbols_hashed == total - len(drifted_symbol_ids)
    assert stats.remaining_null == len(drifted_symbol_ids)

    store = SQLiteStore(_sqlite_path(repo))
    try:
        still_null = {
            r["id"]
            for r in store._connect()
            .execute("SELECT id FROM symbols WHERE content_hash IS NULL")
            .fetchall()
        }
    finally:
        store.close()
    assert still_null == drifted_symbol_ids


def test_a_drifted_file_is_recovered_by_the_next_index_run(
    tmp_path: Path,
) -> None:
    """Nothing is lost by skipping: a drifted file is a changed file, so the
    skip-on-unchanged fast path re-extracts it and the insert path hashes
    it."""
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    _index(repo, manifest, reset=True)
    _clear_content_hashes(repo)

    target = _one_indexed_file(repo)
    path = repo / target
    path.write_text(
        path.read_text(encoding="utf-8") + "\n// edited after indexing\n",
        encoding="utf-8",
    )

    stats = Indexer(manifest, repo).backfill_hashes()
    assert stats.remaining_null > 0

    _index(repo, manifest)  # incremental: only the drifted file is redone

    store = SQLiteStore(_sqlite_path(repo))
    try:
        remaining = int(
            store._connect()
            .execute(
                """
                SELECT COUNT(*) FROM symbols s
                JOIN repo_files f ON f.id = s.file_id
                WHERE f.relative_path = ? AND s.content_hash IS NULL
                """,
                (target,),
            )
            .fetchone()[0]
        )
    finally:
        store.close()
    assert remaining == 0


def test_a_plain_reindex_does_not_fill_the_column(tmp_path: Path) -> None:
    """The measured reason `backfill-hashes` exists.

    With every file unchanged, the M15 fast path skips them all, so nothing
    is re-extracted and the NULLs survive an `index` run untouched. If this
    ever starts passing with `null == 0`, the fast path changed and this
    command's justification should be re-read before anyone deletes it.
    """
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    _index(repo, manifest, reset=True)
    total = _clear_content_hashes(repo)

    _index(repo, manifest)  # no file changed

    _filled, null = _hash_state(repo)
    assert null == total


def test_backfill_refuses_when_there_is_no_index(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    import pytest

    with pytest.raises(FileNotFoundError):
        Indexer(_manifest(), repo).backfill_hashes()


def test_cli_backfill_hashes_end_to_end(tmp_path: Path) -> None:
    repo = _copy_fixture(tmp_path)
    manifest = _manifest()
    _index(repo, manifest, reset=True)
    total = _clear_content_hashes(repo)

    result = CliRunner().invoke(
        app,
        [
            "backfill-hashes",
            "--repo-root",
            str(repo),
            "--index-dir",
            str(repo / "legacylift-docs" / "index" / "code-search"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Content-Hash Backfill Summary" in result.output
    assert _hash_state(repo) == (total, 0)


# ----------------------------------------------------------------------
# Body recovery: byte bounds first, line bounds where there are none
# ----------------------------------------------------------------------
# `xml_extractor.py:130` emits `end_byte == start_byte` by construction -- it
# knows where an element starts in bytes and where it starts and ends in
# lines. Measured on the NNG app index that shape is 1,739 of 16,272 symbols
# (every Hibernate mapping, every Spring bean, every WebFlow state), so
# treating a zero-length byte range as "unhashable" would leave the whole
# framework layer outside the drift-versus-clone matrix for good.

from legacylift_search.identity import content_hash  # noqa: E402
from legacylift_search.migrations import symbol_anchor_key  # noqa: E402
from legacylift_search.models import SourceFile, Symbol, TextRange  # noqa: E402
from legacylift_search.store import (  # noqa: E402
    source_text,
    symbol_body_text,
)

_TEXT = "alpha\nbravo\ncharlie\ndelta\n"


def test_byte_bounds_are_used_when_they_describe_a_span() -> None:
    src = source_text(_TEXT.encode("utf-8"))
    assert symbol_body_text(src, 6, 11, 1, 4) == "bravo"


def test_zero_length_byte_range_falls_back_to_line_bounds() -> None:
    """The XML-extractor shape: a byte *point* plus a real line span."""
    src = source_text(_TEXT.encode("utf-8"))
    assert symbol_body_text(src, 6, 6, 2, 3) == "bravo\ncharlie"


def test_out_of_range_byte_bounds_fall_back_to_line_bounds() -> None:
    src = source_text(_TEXT.encode("utf-8"))
    assert symbol_body_text(src, 0, 10_000, 1, 1) == "alpha"


def test_unsatisfiable_bounds_are_unhashable() -> None:
    """Neither pair fits, so there is no body -- and NULL is the only honest
    answer, because a wrong hash is indistinguishable from real drift."""
    src = source_text(_TEXT.encode("utf-8"))
    assert symbol_body_text(src, 0, 0, 99, 200) is None


def test_byte_bounds_index_the_decoded_byte_space_not_the_raw_bytes() -> None:
    """Extractors measure offsets against the decoded text re-encoded as
    UTF-8, so a file with invalid UTF-8 has a byte space of a different
    length from its raw bytes. Slicing the raw bytes would shift every
    offset in such a file."""
    raw = b"a\xffb\n"  # \xff is not valid UTF-8; it decodes to U+FFFD
    src = source_text(raw)
    assert len(src.byte_space) != len(raw)
    assert symbol_body_text(src, 0, len(src.byte_space), 1, 2) == src.text


def test_insert_path_hashes_a_symbol_with_no_byte_span(tmp_path: Path) -> None:
    """End to end: an XML-shaped symbol reaches the database with a hash."""
    body = "<hibernate-mapping>\n  <class name='Thing'/>\n</hibernate-mapping>\n"
    absolute = tmp_path / "Thing.hbm.xml"
    # write_bytes, not write_text: on Windows `write_text` translates "\n" to
    # "\r\n", so the file on disk would not match the digest computed below
    # and the CR-09 drift guard in `upsert_symbols` would (correctly) refuse
    # to hash it. Discovery reads raw bytes, so this matches production.
    absolute.write_bytes(body.encode("utf-8"))
    import hashlib

    source_file = SourceFile(
        absolute_path=absolute,
        repo_root=tmp_path,
        relative_path="Thing.hbm.xml",
        language="xml",
        size_bytes=len(body.encode("utf-8")),
        sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        mtime_ns=0,
    )
    symbol = Symbol(
        id="xml:Thing.hbm.xml:Thing:2",
        language="xml",
        name="Thing",
        qualified_name="Thing",
        kind="hibernate_class_mapping",
        entity_class="type",
        # The xml_extractor shape: a byte point, a real line span.
        range=TextRange(start_byte=20, end_byte=20, start_line=2, end_line=2),
    )

    store = SQLiteStore(tmp_path / "index.sqlite")
    try:
        store.migrate()
        store.upsert_files([source_file])
        store.upsert_symbols(source_file, [symbol])
        row = store._connect().execute(
            "SELECT anchor_key, entity_class, content_hash FROM symbols"
        ).fetchone()
    finally:
        store.close()

    assert row["entity_class"] == "type"
    assert row["anchor_key"] == symbol_anchor_key(
        "xml", "type", "Thing", "Thing.hbm.xml"
    )
    assert row["content_hash"] == content_hash("  <class name='Thing'/>")


# ---------------------------------------------------------------------------
# CR-09: the INSERT path must apply the same drift guard this command does
# ---------------------------------------------------------------------------
def test_insert_path_refuses_to_hash_a_file_that_drifted_mid_run(
    tmp_path: Path,
) -> None:
    """`CR-09`. `upsert_symbols` re-reads the file in the writer process,
    long after the extract worker read it -- a cold index is a long pooled
    run with batched commits. If the file is edited inside that window the
    stored bounds usually still *fit* the new file, so a body is recovered
    and hashed, and a non-NULL `content_hash` is written for source that
    never produced those symbols.

    That is exactly the error a migration-time backfill was rejected for and
    that `backfill-hashes` refuses by comparing on-disk `sha256` against
    `repo_files.sha256`. The insert path has the digest in hand and must use
    it: on a mismatch the hash stays NULL, and the next `index` run recovers
    the rows because a drifted file is a changed file.
    """
    import hashlib

    from legacylift_search.identity import content_hash
    from legacylift_search.models import Symbol, TextRange
    from legacylift_search.models import SourceFile

    repo = tmp_path / "repo"
    repo.mkdir()
    path = repo / "A.java"
    indexed = b"class Alpha {\n  int beta() { return 1; }\n}\n"
    path.write_bytes(indexed)

    source_file = SourceFile(
        absolute_path=path,
        repo_root=repo,
        relative_path="A.java",
        language="java",
        size_bytes=len(indexed),
        sha256=hashlib.sha256(indexed).hexdigest(),
        mtime_ns=0,
    )

    store = SQLiteStore(tmp_path / "index.sqlite")
    store.migrate()
    store.upsert_files([source_file])

    symbol = Symbol(
        id="java:A.java:Alpha.beta:2",
        language="java",
        name="beta",
        qualified_name="Alpha.beta",
        kind="method_declaration",
        entity_class="function",
        range=TextRange(start_byte=16, end_byte=40, start_line=2, end_line=2),
    )

    # The file is edited between extraction and the write.
    edited = b"class Alpha {\n  int beta() { return 999; }\n}\n"
    path.write_bytes(edited)

    store.upsert_symbols(source_file, [symbol])

    stored = store._connect().execute(
        "SELECT content_hash FROM symbols WHERE id = ?", (symbol.id,)
    ).fetchone()[0]

    assert stored is None, (
        "a drifted file must leave content_hash NULL; before the fix this "
        f"held {stored!r}, the hash of the EDITED body "
        f"({content_hash(edited.decode()[16:40])})"
    )
    store.close()


def test_insert_path_still_hashes_an_unchanged_file(tmp_path: Path) -> None:
    """The `CR-09` guard must not suppress the normal case."""
    import hashlib

    from legacylift_search.identity import content_hash
    from legacylift_search.models import SourceFile, Symbol, TextRange

    repo = tmp_path / "repo"
    repo.mkdir()
    path = repo / "A.java"
    indexed = b"class Alpha {\n  int beta() { return 1; }\n}\n"
    path.write_bytes(indexed)

    source_file = SourceFile(
        absolute_path=path,
        repo_root=repo,
        relative_path="A.java",
        language="java",
        size_bytes=len(indexed),
        sha256=hashlib.sha256(indexed).hexdigest(),
        mtime_ns=0,
    )
    store = SQLiteStore(tmp_path / "index.sqlite")
    store.migrate()
    store.upsert_files([source_file])
    symbol = Symbol(
        id="java:A.java:Alpha.beta:2",
        language="java",
        name="beta",
        qualified_name="Alpha.beta",
        kind="method_declaration",
        entity_class="function",
        range=TextRange(start_byte=16, end_byte=40, start_line=2, end_line=2),
    )
    store.upsert_symbols(source_file, [symbol])
    stored = store._connect().execute(
        "SELECT content_hash FROM symbols WHERE id = ?", (symbol.id,)
    ).fetchone()[0]
    assert stored == content_hash(indexed.decode()[16:40])
    store.close()
