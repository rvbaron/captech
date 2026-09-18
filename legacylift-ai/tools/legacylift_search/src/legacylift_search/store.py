"""SQLite store: schema, migrations, upserts, lexical FTS5 search.

Milestone 7 implementation following the DDL and schema exactly as defined in
`docs/exec-plans/active/semantic-code-search-graph-index.md`.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .identity import content_hash
from .migrations import (
    INDEX_MIGRATIONS,
    highest_version,
    run_migrations,
    stamp_fresh_database,
    symbol_anchor_key,
    was_database_empty,
)
from .models import (
    CodeChunk,
    GraphEdge,
    SourceFile,
    Symbol,
    SymbolFact,
    SymbolRef,
)


# ----------------------------------------------------------------------
# Entity body text: the ONE way a `symbols` row's source is recovered
# ----------------------------------------------------------------------
#
# Two callers need it and must agree byte for byte, for the same reason
# `migrations.symbol_anchor_key` has one caller-shared definition: the insert
# path (`upsert_symbols`) and the `backfill-hashes` repair command both feed
# `identity.content_hash`, and a body sliced differently at the two sites
# would produce two different hashes for one unchanged entity -- reported as
# drift, with nothing raising.


@dataclass(frozen=True)
class SourceText:
    """The three views of one file's content that symbol bounds index into.

    All three are derived once per file because deriving any of them per
    symbol would re-encode or re-split the whole file for every symbol in it.

    Attributes:
        text: The file decoded as UTF-8 with `errors="replace"`, which is how
            every extractor reads it (`extract_worker._extract_with`).
        byte_space: `text` re-encoded as UTF-8. **This, not the file's raw
            bytes, is what `symbols.start_byte`/`end_byte` index into**:
            the extractors measure against the re-encoded decoded text
            (`extractors.py:964`, `:1055`), so a file containing invalid
            UTF-8 has a byte space of a different length from its raw bytes,
            and slicing the raw bytes would silently shift every offset.
        lines: `text` split on `"\n"`, so `lines[start_line - 1]` is the
            symbol's first line. Line numbers are 1-based and are counted by
            the extractors as `text[:offset].count("\n") + 1`, over this same
            decoded text, so the two agree by construction.
    """

    text: str
    byte_space: bytes
    lines: tuple[str, ...]


def source_text(raw: bytes) -> SourceText:
    """Build the `SourceText` views from a file's raw bytes."""
    text = raw.decode("utf-8", errors="replace")
    return SourceText(
        text=text,
        byte_space=text.encode("utf-8"),
        lines=tuple(text.split("\n")),
    )


def read_source_text(
    absolute_path: Path, expected_sha256: str | None = None
) -> SourceText | None:
    """Read a file and return its `SourceText`, or `None` if it cannot be used.

    A read failure is not an error here: `content_hash` is nullable and NULL
    means "not yet hashed", so a file that has been deleted or locked since
    indexing simply leaves its symbols unhashed for `backfill-hashes` to
    revisit.

    `CR-09`: pass `expected_sha256` -- the digest of the bytes that produced
    the symbols being written -- and the read is REFUSED when the file on
    disk no longer matches. Without it, a file edited between extraction and
    the write (a full index is a long pooled run) is re-read here, its stored
    bounds usually still fit, and a hash is written for source that never
    produced those rows: a non-NULL value that is silently wrong. That is the
    precise error the migration-time backfill was rejected for and that
    `Indexer.backfill_hashes` guards against; the insert path must guard the
    same way. Returning `None` leaves the hashes NULL, and the next `index`
    run re-extracts the file because a drifted file is a changed file.

    Args:
        absolute_path: The file to read.
        expected_sha256: The indexed digest to verify against, or `None` to
            skip verification (callers with no digest in hand).

    Returns:
        The file's `SourceText`, or `None` if it is unreadable or drifted.
    """
    try:
        raw = absolute_path.read_bytes()
    except OSError:
        return None
    if expected_sha256 is not None:
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            return None
    return source_text(raw)


def symbol_body_text(
    source: SourceText,
    start_byte: int,
    end_byte: int,
    start_line: int,
    end_line: int,
) -> str | None:
    """Recover one symbol's body text from its stored bounds.

    **Byte bounds first, line bounds as the fallback, and the fallback is not
    defensive padding** -- it is the only way a large class of real symbols
    can be hashed at all. `xml_extractor.py:130` emits
    ``end_byte == start_byte`` by construction: the XML element parser knows
    where an element *starts* in bytes and where it starts and ends in
    *lines*, so its byte range is a point and its line range is the span.
    Measured on the NNG app index that is 1,739 of 16,272 symbols -- every
    Hibernate mapping, every Spring bean and every WebFlow state. Dropping
    them would leave the entire framework layer permanently unhashed and
    therefore outside the drift-versus-clone matrix, with the count reported
    as if it were an extractor bug.

    Byte bounds win where they describe a real span because they are exact:
    a tree-sitter symbol's range starts and ends mid-line.

    Args:
        source: The file's views, from `source_text` / `read_source_text`.
        start_byte: `symbols.start_byte`.
        end_byte: `symbols.end_byte`.
        start_line: `symbols.start_line` (1-based).
        end_line: `symbols.end_line` (1-based, inclusive).

    Returns:
        The body text, or `None` when neither pair of bounds can be satisfied
        by this file. `None` means "unhashable", and the caller must then
        leave `content_hash` NULL rather than hash a truncated body: NULL is
        "not yet hashed", and a wrong hash is indistinguishable from real
        drift.
    """
    if 0 <= start_byte < end_byte <= len(source.byte_space):
        return source.byte_space[start_byte:end_byte].decode(
            "utf-8", errors="replace"
        )
    if 1 <= start_line <= end_line <= len(source.lines):
        return "\n".join(source.lines[start_line - 1 : end_line])
    return None


# Store-specific result models (not added to models.py)
class LexicalResult(BaseModel):
    """A single BM25-ranked lexical search result from FTS5."""

    chunk_id: str
    relative_path: str
    language: str
    symbol_path: str | None
    start_line: int
    end_line: int
    rank: float


class CodeChunkRecord(BaseModel):
    """A full chunk record retrieved from the database."""

    id: str
    file_id: int
    file_sha256: str
    relative_path: str
    language: str
    chunk_index: int
    chunk_kind: str
    symbol_id: str | None
    symbol_path: str | None
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    text_sha256: str
    token_count_estimate: int
    text: str | None


class SymbolRecord(BaseModel):
    """A full symbol record retrieved from the database."""

    id: str
    file_id: int
    language: str
    name: str
    qualified_name: str
    kind: str
    container: str | None
    signature: str | None
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int


class GraphEdgeRecord(BaseModel):
    """A full graph edge record retrieved from the database."""

    id: str
    caller_symbol_id: str | None
    callee_symbol_id: str | None
    callee_name: str
    edge_kind: str
    confidence: float
    evidence: str
    source_ref_id: str | None
    relative_path: str
    start_line: int


class SymbolFactRecord(BaseModel):
    """A full symbol-fact record retrieved from the database."""

    id: str
    file_id: int
    subject_symbol_id: str
    predicate: str
    object: str | None
    attributes: dict | None
    evidence: str
    confidence: float
    language: str
    relative_path: str
    start_line: int


class IndexStats(BaseModel):
    """Statistics about the indexed repository."""

    file_count: int
    chunk_count: int
    symbol_count: int
    ref_count: int
    edge_count: int
    fact_count: int
    languages: list[str]


def _norm_path_components(path: str) -> tuple[str, ...]:
    """Normalize a file path to a tuple of POSIX path components for
    base/separator-tolerant matching in ``SQLiteStore.coverage``.

    Handles Windows ``\\`` separators, mixed separators, a Windows drive letter,
    leading ``./`` / ``/`` noise, and ``.``/``..`` segments. Returns the path
    split into its components with empties and ``.`` dropped; ``..`` pops the
    prior component so a citation like ``a/b/../Foo.cs`` normalizes to
    ``("a", "Foo.cs")``. Returns an empty tuple for a blank/rootless path.
    """
    if not path:
        return ()
    raw = path.replace("\\", "/")
    comps: list[str] = []
    for seg in raw.split("/"):
        seg = seg.strip()
        if seg in ("", "."):
            continue
        # Drop a Windows drive letter ("C:") appearing as the first segment.
        if not comps and len(seg) == 2 and seg[1] == ":" and seg[0].isalpha():
            continue
        if seg == "..":
            if comps:
                comps.pop()
            continue
        comps.append(seg)
    return tuple(comps)


class SQLiteStore:
    """SQLite persistence for code chunks, symbols, refs, and graph edges.

    Uses stdlib sqlite3 with FTS5 for lexical search, foreign keys enabled,
    and WAL mode for concurrent read/write safety.
    """

    def __init__(self, sqlite_path: Path) -> None:
        """Initialize a connection to the SQLite database at sqlite_path.

        Args:
            sqlite_path: Path to the SQLite file (will be created if missing).
        """
        self.sqlite_path = sqlite_path
        self.conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        """Open or return the existing connection, migrating on first open.

        `CR-10`: the connection is cached only AFTER the on-open migration
        succeeds. Assigning `self.conn` first left a refused database --
        newer than this build, read-only, locked -- cached and marked open,
        so the guard raised once and every later `_connect()` handed back a
        live connection to the schema it had just refused. A guard that holds
        for one call is not a guard.

        `PRAGMA foreign_keys` is enabled here rather than only in `migrate()`
        (`CR-11`). It is a per-CONNECTION pragma, and since `CR-01` moved
        migration into this method most connections never call `migrate()` --
        so `symbols`' `ON DELETE CASCADE` to `repo_files` was going
        unenforced on every one of them, which is how a symbol row can
        outlive its file and become invisible to every joined query.
        """
        if self.conn is None:
            conn = sqlite3.connect(str(self.sqlite_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                self._migrate_existing_on_open(conn)
            except BaseException:
                conn.close()
                raise
            self.conn = conn
        return self.conn

    def _migrate_existing_on_open(self, conn: sqlite3.Connection) -> None:
        """Bring an EXISTING `index.sqlite` forward on every open.

        ------------------------------------------------------------------
        CR-01, and the design call behind it. READ THIS BEFORE MOVING IT.
        ------------------------------------------------------------------
        Before this existed, `SQLiteStore.migrate()` was the only caller of
        `run_migrations(INDEX_MIGRATIONS)` and it ran from exactly two places
        -- `index` and `backfill-vectors`. Every read command (`stats`,
        `search`, `symbols`, `callers`, `callees`, `facts`, `coverage`,
        `validate`) built a `SQLiteStore` and never migrated, while
        `KnowledgeStore.__init__` migrated on every open. The two databases
        had asymmetric triggers, and in production both NNG `index.sqlite`
        files sat at `user_version` 0 while both `knowledge.sqlite` files
        were at 1. The consequence is not cosmetic: the next schema version
        would not reach an existing index until someone re-indexed it (hours
        plus embedding spend), and every read in the meantime would open an
        older schema against code expecting the newer one and die on
        `no such column: ...`.

        Three placements were considered:

          (a) here, in `_connect` -- migrate on open, as `KnowledgeStore`
              already does;
          (b) a new explicit call on each CLI entry point;
          (c) a read-only version check that REFUSES rather than migrates.

        **(a) was chosen**, with (c)'s loudness kept as the failure mode.
        (b) is the defect it is meant to fix: it is a rule the next author
        must remember at eight-and-growing call sites, and forgetting it is
        silent -- which is exactly how this bug arrived. (c) is honest but
        offers the user no remedy: the only command that migrates would be
        `index`, so "refuse" reads as "re-index a multi-gigabyte repository
        to gain a nullable column". The migrations themselves are cheap,
        forward-only, individually transactional and idempotent, so applying
        one on open is the cheaper and safer of the two.

        The cost accepted, stated plainly: **a read command may now write to
        `index.sqlite`** -- but only when the database is genuinely behind,
        and only the ALTERs the running build already requires. WAL mode
        means concurrent readers are not blocked; the write lock is taken by
        `BEGIN IMMEDIATE` inside `run_migrations` and held only for the
        migration itself.

        Two guards keep the remaining cases loud rather than silent:

          * A database NEWER than this build is refused outright. Migrations
            are forward-only, so an older build cannot know what a newer
            schema means, and reading it would produce wrong answers rather
            than an error.
          * A migration that cannot be applied -- a read-only file or
            filesystem, someone else's index, a locked database -- is
            reported as what it is, naming both versions, instead of
            surfacing later as a cryptic `no such column`.

        A FRESH (table-less) database is deliberately skipped here: it gets
        its whole schema from `migrate()`, which then stamps it at the
        highest known version. Running migrations first would try to ALTER
        tables that do not exist yet. This is the same fresh-versus-existing
        split `migrations.was_database_empty` documents.
        """
        if was_database_empty(conn):
            return

        current = int(conn.execute("PRAGMA user_version").fetchone()[0])
        target = highest_version(INDEX_MIGRATIONS)
        if current > target:
            raise RuntimeError(
                f"index database at {self.sqlite_path} is at schema version "
                f"{current}, which is NEWER than this build understands "
                f"(version {target}). Migrations are forward-only. Upgrade "
                f"legacylift-search, or point --index-dir/--analysis-dir at "
                f"an index built by this version."
            )
        if current == target:
            return

        try:
            run_migrations(conn, INDEX_MIGRATIONS)
        except sqlite3.Error as exc:
            raise RuntimeError(
                f"index database at {self.sqlite_path} is at schema version "
                f"{current} and this build needs version {target}, but the "
                f"migration could not be applied: {exc}. The index is "
                f"probably read-only or in use by another process; a "
                f"writable copy can be migrated by running "
                f"`legacylift-search index`."
            ) from exc

    def migrate(self) -> None:
        """Create all tables, indexes, and FTS5 virtual table if they don't exist.

        Sets PRAGMA journal_mode=WAL and PRAGMA foreign_keys=ON.
        Uses the exact DDL from the spec verbatim.
        """
        conn = self._connect()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Milestone 0: snapshot emptiness BEFORE any CREATE TABLE below runs.
        # Taken after migrate() it would always see tables and stamp nothing,
        # leaving every fresh database at version 0. Held in this local until
        # the run_migrations call at the end of this method.
        was_empty = was_database_empty(conn)

        # index_metadata
        conn.execute("""
            CREATE TABLE IF NOT EXISTS index_metadata (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # repo_files
        conn.execute("""
            CREATE TABLE IF NOT EXISTS repo_files (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              repo_root TEXT NOT NULL,
              relative_path TEXT NOT NULL UNIQUE,
              language TEXT NOT NULL,
              sha256 TEXT NOT NULL,
              size_bytes INTEGER NOT NULL,
              mtime_ns INTEGER NOT NULL,
              indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # chunks
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
              id TEXT PRIMARY KEY,
              file_id INTEGER NOT NULL,
              file_sha256 TEXT NOT NULL,
              relative_path TEXT NOT NULL,
              language TEXT NOT NULL,
              chunk_index INTEGER NOT NULL,
              chunk_kind TEXT NOT NULL,
              symbol_id TEXT,
              symbol_path TEXT,
              start_byte INTEGER NOT NULL,
              end_byte INTEGER NOT NULL,
              start_line INTEGER NOT NULL,
              end_line INTEGER NOT NULL,
              text_sha256 TEXT NOT NULL,
              token_count_estimate INTEGER NOT NULL,
              text TEXT,
              FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE
            )
        """)

        # chunk_fts (FTS5 virtual table)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
              chunk_id UNINDEXED,
              relative_path,
              language,
              symbol_path,
              text
            )
        """)

        # symbols
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
              id TEXT PRIMARY KEY,
              file_id INTEGER NOT NULL,
              language TEXT NOT NULL,
              name TEXT NOT NULL,
              qualified_name TEXT NOT NULL,
              kind TEXT NOT NULL,
              container TEXT,
              signature TEXT,
              start_byte INTEGER NOT NULL,
              end_byte INTEGER NOT NULL,
              start_line INTEGER NOT NULL,
              end_line INTEGER NOT NULL,
              -- Milestone 1 Step 2 (INDEX_MIGRATIONS version 2). A database
              -- created here already has all three, so the migration's
              -- guarded ALTERs find nothing to do and the fresh-database
              -- stamp is correct. An EXISTING database gets them from
              -- `_index_v2_identity` instead. Nullable on purpose:
              -- `content_hash` is NULL until `backfill-hashes` (or the next
              -- real `index` of a changed file) proves what the bytes were.
              anchor_key TEXT,
              entity_class TEXT,
              content_hash TEXT,
              FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE
            )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbols_name ON symbols(name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbols_qualified_name ON symbols(qualified_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbols_language ON symbols(language)"
        )
        # Deliberately NOT UNIQUE: two symbols legitimately share an anchor
        # when one file declares the same qualified name twice, so this is a
        # lookup key that may return several rows.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbols_anchor_key "
            "ON symbols(anchor_key)"
        )
        # Milestone 1 Step 6a: the only POSITIONAL index on `symbols`. The
        # citation containment query (`symbols_overlapping_lines`) asks
        # "which symbols in this file touch these lines?", which the three
        # name-shaped indexes above cannot serve, so without this every
        # citation of an indexed file scans the table -- once per rule, on a
        # corpus of hundreds. Carried by INDEX_MIGRATIONS version 2 as well,
        # for databases that already exist.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbols_file_span "
            "ON symbols(file_id, start_line, end_line)"
        )

        # symbol_refs
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_refs (
              id TEXT PRIMARY KEY,
              file_id INTEGER NOT NULL,
              chunk_id TEXT,
              language TEXT NOT NULL,
              name TEXT NOT NULL,
              kind TEXT NOT NULL,
              enclosing_symbol_id TEXT,
              start_byte INTEGER NOT NULL,
              end_byte INTEGER NOT NULL,
              start_line INTEGER NOT NULL,
              end_line INTEGER NOT NULL,
              evidence TEXT NOT NULL,
              FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE,
              FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE SET NULL
            )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbol_refs_name ON symbol_refs(name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbol_refs_enclosing ON symbol_refs(enclosing_symbol_id)"
        )

        # graph_edges
        conn.execute("""
            CREATE TABLE IF NOT EXISTS graph_edges (
              id TEXT PRIMARY KEY,
              caller_symbol_id TEXT,
              callee_symbol_id TEXT,
              callee_name TEXT NOT NULL,
              edge_kind TEXT NOT NULL,
              confidence REAL NOT NULL,
              evidence TEXT NOT NULL,
              source_ref_id TEXT,
              relative_path TEXT NOT NULL,
              start_line INTEGER NOT NULL,
              FOREIGN KEY(caller_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE,
              FOREIGN KEY(callee_symbol_id) REFERENCES symbols(id) ON DELETE SET NULL,
              FOREIGN KEY(source_ref_id) REFERENCES symbol_refs(id) ON DELETE SET NULL
            )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_graph_edges_caller ON graph_edges(caller_symbol_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_graph_edges_callee ON graph_edges(callee_symbol_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_graph_edges_callee_name ON graph_edges(callee_name)"
        )

        # vectors_present: a fast local cache that records which (chunk_id,
        # text_sha256) pairs have already been upserted into Chroma. This
        # avoids a per-chunk Chroma round trip during idempotent reindex.
        # Milestone 15 chose SQLite tracking over `collection.get(ids=...)`
        # because: (1) it's a single local query rather than O(N) Chroma RPCs,
        # (2) we already commit to SQLite per file so the cost is amortized,
        # (3) text_sha256 lets us detect chunk-text changes even when the
        # chunk_id is stable.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vectors_present (
              chunk_id TEXT PRIMARY KEY,
              text_sha256 TEXT NOT NULL,
              upserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # symbol_facts (Milestones 23-25): attribute-facts anchored on a
        # definition symbol. The file_id cascade cleans changed/deleted-file
        # facts (via the upsert_files REPLACE and delete_file_artifacts); the
        # subject_symbol_id cascade removes facts when their symbol is dropped.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_facts (
              id TEXT PRIMARY KEY,
              file_id INTEGER NOT NULL,
              subject_symbol_id TEXT NOT NULL,
              predicate TEXT NOT NULL,
              object TEXT,
              attributes TEXT,
              evidence TEXT NOT NULL,
              confidence REAL NOT NULL,
              language TEXT NOT NULL,
              relative_path TEXT NOT NULL,
              start_line INTEGER NOT NULL,
              FOREIGN KEY(file_id) REFERENCES repo_files(id) ON DELETE CASCADE,
              FOREIGN KEY(subject_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
            )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbol_facts_predicate ON symbol_facts(predicate)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_symbol_facts_subject ON symbol_facts(subject_symbol_id)"
        )

        conn.commit()

        # Milestone 0: versioned schema migrations. A database this method
        # just created from nothing already has every column any migration
        # would add, so it is stamped at the highest known version and the
        # runner then has nothing to do. An existing older database is
        # brought forward by the runner instead. Both PRAGMAs above stay
        # where they are: neither can run inside a transaction.
        #
        # CR-01: an existing database was ALREADY brought forward by
        # `_migrate_existing_on_open` during the `_connect()` above, so this
        # run_migrations call is a no-op on that path. It is kept because
        # this is still the only place a FRESH database gets stamped, and
        # because a migration list that grows during one process's lifetime
        # (tests do this) must still be applied here.
        if was_empty:
            stamp_fresh_database(conn, INDEX_MIGRATIONS)
        run_migrations(conn, INDEX_MIGRATIONS)

    def commit(self) -> None:
        """Commit the current transaction, if a connection is open.

        Milestone 19: the indexer batches many upserts into a single
        transaction and calls this explicitly, so the per-method commits are
        suppressed via ``commit=False``.
        """
        if self.conn is not None:
            self.conn.commit()

    def clear_reindex_artifacts(self, relative_path: str) -> None:
        """Drop a changed file's existing chunks/FTS rows and symbols/refs
        ahead of re-extraction, WITHOUT committing.

        Milestone 19: factored out of the indexer's per-file loop so the
        delete + re-upsert for a changed file can share one batched
        transaction with the writer. The repo_files row is left intact (it is
        re-upserted separately by ``upsert_files`` for changed files).
        """
        conn = self._connect()
        old_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM chunks WHERE relative_path = ?",
                (relative_path,),
            ).fetchall()
        ]
        for cid in old_ids:
            conn.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (cid,))
        conn.execute(
            "DELETE FROM chunks WHERE relative_path = ?",
            (relative_path,),
        )
        file_id_row = conn.execute(
            "SELECT id FROM repo_files WHERE relative_path = ?",
            (relative_path,),
        ).fetchone()
        if file_id_row is not None:
            fid = file_id_row["id"]
            conn.execute("DELETE FROM symbol_refs WHERE file_id = ?", (fid,))
            # Delete facts before symbols so cleanup does not depend on the
            # subject_symbol_id cascade firing first (belt-and-suspenders; in
            # the changed-file path the upsert_files REPLACE at indexer.py:302
            # has already cascade-purged these via file_id).
            conn.execute("DELETE FROM symbol_facts WHERE file_id = ?", (fid,))
            conn.execute("DELETE FROM symbols WHERE file_id = ?", (fid,))

    def upsert_files(self, files: list[SourceFile], commit: bool = True) -> None:
        """Upsert source files into repo_files table.

        Uses INSERT OR REPLACE to handle duplicates by relative_path.
        """
        conn = self._connect()
        for file in files:
            conn.execute(
                """
                INSERT OR REPLACE INTO repo_files
                    (repo_root, relative_path, language, sha256, size_bytes, mtime_ns, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    str(file.repo_root),
                    file.relative_path,
                    file.language,
                    file.sha256,
                    file.size_bytes,
                    file.mtime_ns,
                ),
            )
        if commit:
            conn.commit()

    def _get_file_id(self, relative_path: str) -> int | None:
        """Resolve file_id by relative_path. Returns None if not found."""
        conn = self._connect()
        row = conn.execute(
            "SELECT id FROM repo_files WHERE relative_path = ?", (relative_path,)
        ).fetchone()
        return row["id"] if row else None

    def upsert_chunks(
        self, chunks: list[CodeChunk], commit: bool = True
    ) -> None:
        """Upsert code chunks into chunks table and chunk_fts.

        For each chunk:
        1. Resolve file_id from relative_path.
        2. INSERT OR REPLACE into chunks.
        3. Delete existing FTS row for this chunk_id.
        4. Insert new FTS row.
        """
        conn = self._connect()
        for chunk in chunks:
            file_id = self._get_file_id(chunk.relative_path)
            if file_id is None:
                # Skip chunks for files not yet in repo_files
                continue

            conn.execute(
                """
                INSERT OR REPLACE INTO chunks
                    (id, file_id, file_sha256, relative_path, language,
                     chunk_index, chunk_kind, symbol_id, symbol_path,
                     start_byte, end_byte, start_line, end_line,
                     text_sha256, token_count_estimate, text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    file_id,
                    chunk.file_sha256,
                    chunk.relative_path,
                    chunk.language,
                    chunk.chunk_index,
                    chunk.chunk_kind,
                    chunk.symbol_id,
                    chunk.symbol_path,
                    chunk.start_byte,
                    chunk.end_byte,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.text_sha256,
                    chunk.token_count_estimate,
                    chunk.text,
                ),
            )

            # Delete existing FTS row and insert fresh
            conn.execute(
                "DELETE FROM chunk_fts WHERE chunk_id = ?", (chunk.id,)
            )
            conn.execute(
                """
                INSERT INTO chunk_fts (chunk_id, relative_path, language, symbol_path, text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    chunk.id,
                    chunk.relative_path,
                    chunk.language,
                    chunk.symbol_path,
                    chunk.text,
                ),
            )

        if commit:
            conn.commit()

    def upsert_symbols(
        self, source_file: SourceFile, symbols: list[Symbol], commit: bool = True
    ) -> None:
        """Upsert symbols for a given source file.

        Resolves file_id from source_file.relative_path.

        Milestone 1 Step 2 writes the three identity columns here, which is
        the only place symbols are written:

        * `entity_class` comes off the `Symbol`, where the **extractor
          declared it** (`NORMATIVE SPEC-3` S3.1.2). It is never derived from
          `kind` here; the one `kind` lookup in this codebase is the
          backfill-only shim in `migrations.py`.
        * `anchor_key` is derived by `migrations.symbol_anchor_key`, the same
          function the version-2 backfill calls -- see its docstring for why
          one shared function rather than two lookalike expressions.
        * `content_hash` needs the entity's body text, so the file is read
          once per call and sliced per symbol by `symbol_body_text`. If the
          read fails, **the file has drifted since it was extracted**
          (`CR-09`), or neither the byte nor the line bounds fit the file,
          the hash is left NULL: **NULL means "not yet hashed", never
          "unchanged"**, and `backfill-hashes` revisits it.

        The re-read is deliberate and its cost is bounded. On the `index`
        path the extract worker has already read this file in another
        process, and the body text does not come back across the process
        boundary (returning it would put every file's full source into the
        IPC payload). One warm re-read of a file that was opened moments ago
        is far cheaper than that, and it keeps every writer of `symbols` --
        not just the indexer -- correct by construction.

        **The re-read is verified against `source_file.sha256`** (`CR-09`),
        because "moments ago" is not "atomically": a full index is a long
        pooled run, and a file edited inside that window would otherwise be
        hashed as though it were the source these symbols came from.
        """
        conn = self._connect()
        file_id = self._get_file_id(source_file.relative_path)
        if file_id is None:
            return

        source = read_source_text(source_file.absolute_path, source_file.sha256)

        for symbol in symbols:
            body = (
                None
                if source is None
                else symbol_body_text(
                    source,
                    symbol.range.start_byte,
                    symbol.range.end_byte,
                    symbol.range.start_line,
                    symbol.range.end_line,
                )
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO symbols
                    (id, file_id, language, name, qualified_name, kind, container, signature,
                     start_byte, end_byte, start_line, end_line,
                     anchor_key, entity_class, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol.id,
                    file_id,
                    symbol.language,
                    symbol.name,
                    symbol.qualified_name,
                    symbol.kind,
                    symbol.container,
                    symbol.signature,
                    symbol.range.start_byte,
                    symbol.range.end_byte,
                    symbol.range.start_line,
                    symbol.range.end_line,
                    symbol_anchor_key(
                        symbol.language,
                        symbol.entity_class,
                        symbol.qualified_name,
                        source_file.relative_path,
                    ),
                    symbol.entity_class,
                    None if body is None else content_hash(body),
                ),
            )

        if commit:
            conn.commit()

    def upsert_refs(
        self, source_file: SourceFile, refs: list[SymbolRef], commit: bool = True
    ) -> None:
        """Upsert symbol references for a given source file.

        Resolves file_id from source_file.relative_path.
        """
        conn = self._connect()
        file_id = self._get_file_id(source_file.relative_path)
        if file_id is None:
            return

        for ref in refs:
            conn.execute(
                """
                INSERT OR REPLACE INTO symbol_refs
                    (id, file_id, chunk_id, language, name, kind,
                     enclosing_symbol_id, start_byte, end_byte, start_line, end_line, evidence)
                VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ref.id,
                    file_id,
                    ref.language,
                    ref.name,
                    ref.kind,
                    ref.enclosing_symbol_id,
                    ref.range.start_byte,
                    ref.range.end_byte,
                    ref.range.start_line,
                    ref.range.end_line,
                    ref.evidence,
                ),
            )

        if commit:
            conn.commit()

    def upsert_facts(
        self,
        source_file: SourceFile,
        facts: list[SymbolFact],
        commit: bool = True,
    ) -> list[SymbolFact]:
        """Upsert symbol facts for a given source file.

        Mirrors ``upsert_refs``: resolves file_id from
        ``source_file.relative_path`` and silently returns when that lookup is
        None (the ``file_id`` FK's by-design silent-drop failure mode — see the
        Shared plumbing prerequisite). ``attributes`` is serialized via
        ``json.dumps`` (None -> NULL); ``object`` may be NULL.

        Crash-guard: ``subject_symbol_id`` is a NOT NULL FK checked IMMEDIATE,
        so a fact whose subject is not among the persisted symbols would raise
        ``sqlite3.IntegrityError`` in the sole writer and abort the run. Each
        INSERT is wrapped in try/except so an orphaned fact is dropped (not
        raised); the orphaned facts are returned so the caller can log them.
        Valid facts in the same batch are still written (the failed INSERT is a
        per-statement error inside the still-open transaction).

        Returns the list of facts that were dropped as orphans (empty when all
        facts were written).
        """
        conn = self._connect()
        file_id = self._get_file_id(source_file.relative_path)
        if file_id is None:
            return []

        orphaned: list[SymbolFact] = []
        for fact in facts:
            attributes = (
                json.dumps(fact.attributes)
                if fact.attributes is not None
                else None
            )
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO symbol_facts
                        (id, file_id, subject_symbol_id, predicate, object,
                         attributes, evidence, confidence, language,
                         relative_path, start_line)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact.id,
                        file_id,
                        fact.subject_symbol_id,
                        fact.predicate,
                        fact.object,
                        attributes,
                        fact.evidence,
                        fact.confidence,
                        fact.language,
                        fact.relative_path,
                        fact.start_line,
                    ),
                )
            except sqlite3.IntegrityError:
                # Dangling subject_symbol_id FK: drop-and-report rather than
                # abort the sole writer. Caller emits the FACT_ORPHAN log line.
                orphaned.append(fact)
                continue

        if commit:
            conn.commit()

        return orphaned

    def upsert_edges(self, edges: list[GraphEdge]) -> None:
        """Upsert graph edges (caller/callee relationships)."""
        conn = self._connect()
        for edge in edges:
            conn.execute(
                """
                INSERT OR REPLACE INTO graph_edges
                    (id, caller_symbol_id, callee_symbol_id, callee_name,
                     edge_kind, confidence, evidence, source_ref_id,
                     relative_path, start_line)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.caller_symbol_id,
                    edge.callee_symbol_id,
                    edge.callee_name,
                    edge.edge_kind,
                    edge.confidence,
                    edge.evidence,
                    edge.source_ref_id,
                    edge.relative_path,
                    edge.start_line,
                ),
            )
        conn.commit()

    def search_lexical(self, query: str, limit: int) -> list[LexicalResult]:
        """Perform lexical search using FTS5 MATCH with BM25 ranking.

        Sanitizes query to avoid FTS5 syntax errors by extracting alphanumeric
        tokens and joining with spaces.

        Args:
            query: User search query (may contain FTS5 special chars).
            limit: Maximum number of results to return.

        Returns:
            List of LexicalResult sorted by BM25 rank (best first).
        """
        # Sanitize query: extract alphanumeric tokens and join with space
        tokens = re.findall(r"\w+", query)
        sanitized = " ".join(tokens)
        if not sanitized:
            return []

        conn = self._connect()
        rows = conn.execute(
            """
            SELECT chunk_id, relative_path, language, symbol_path, rank
            FROM chunk_fts
            WHERE chunk_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (sanitized, limit),
        ).fetchall()

        results: list[LexicalResult] = []
        for row in rows:
            chunk_id = row["chunk_id"]
            # Retrieve start_line and end_line from chunks table
            chunk_row = conn.execute(
                "SELECT start_line, end_line FROM chunks WHERE id = ?",
                (chunk_id,),
            ).fetchone()
            if chunk_row is None:
                continue

            results.append(
                LexicalResult(
                    chunk_id=chunk_id,
                    relative_path=row["relative_path"],
                    language=row["language"],
                    symbol_path=row["symbol_path"],
                    start_line=chunk_row["start_line"],
                    end_line=chunk_row["end_line"],
                    rank=row["rank"],
                )
            )

        return results

    def get_chunk(self, chunk_id: str) -> CodeChunkRecord | None:
        """Retrieve a chunk by ID."""
        conn = self._connect()
        row = conn.execute(
            """
            SELECT id, file_id, file_sha256, relative_path, language,
                   chunk_index, chunk_kind, symbol_id, symbol_path,
                   start_byte, end_byte, start_line, end_line,
                   text_sha256, token_count_estimate, text
            FROM chunks WHERE id = ?
            """,
            (chunk_id,),
        ).fetchone()

        if row is None:
            return None

        return CodeChunkRecord(
            id=row["id"],
            file_id=row["file_id"],
            file_sha256=row["file_sha256"],
            relative_path=row["relative_path"],
            language=row["language"],
            chunk_index=row["chunk_index"],
            chunk_kind=row["chunk_kind"],
            symbol_id=row["symbol_id"],
            symbol_path=row["symbol_path"],
            start_byte=row["start_byte"],
            end_byte=row["end_byte"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            text_sha256=row["text_sha256"],
            token_count_estimate=row["token_count_estimate"],
            text=row["text"],
        )

    def get_symbol(self, symbol_id: str) -> SymbolRecord | None:
        """Retrieve a symbol by ID."""
        conn = self._connect()
        row = conn.execute(
            """
            SELECT id, file_id, language, name, qualified_name, kind,
                   container, signature, start_byte, end_byte, start_line, end_line
            FROM symbols WHERE id = ?
            """,
            (symbol_id,),
        ).fetchone()

        if row is None:
            return None

        return SymbolRecord(
            id=row["id"],
            file_id=row["file_id"],
            language=row["language"],
            name=row["name"],
            qualified_name=row["qualified_name"],
            kind=row["kind"],
            container=row["container"],
            signature=row["signature"],
            start_byte=row["start_byte"],
            end_byte=row["end_byte"],
            start_line=row["start_line"],
            end_line=row["end_line"],
        )

    def find_symbols(self, name: str, limit: int) -> list[SymbolRecord]:
        """Find symbols by name (exact then case-insensitive contains).

        Args:
            name: Symbol name to search.
            limit: Maximum results to return.

        Returns:
            List of SymbolRecord, exact matches first.
        """
        conn = self._connect()
        # Try exact match first
        rows = conn.execute(
            """
            SELECT id, file_id, language, name, qualified_name, kind,
                   container, signature, start_byte, end_byte, start_line, end_line
            FROM symbols WHERE name = ?
            LIMIT ?
            """,
            (name, limit),
        ).fetchall()

        # If no exact matches, try case-insensitive contains
        if not rows:
            rows = conn.execute(
                """
                SELECT id, file_id, language, name, qualified_name, kind,
                       container, signature, start_byte, end_byte, start_line, end_line
                FROM symbols WHERE name LIKE ?
                LIMIT ?
                """,
                (f"%{name}%", limit),
            ).fetchall()

        return [
            SymbolRecord(
                id=row["id"],
                file_id=row["file_id"],
                language=row["language"],
                name=row["name"],
                qualified_name=row["qualified_name"],
                kind=row["kind"],
                container=row["container"],
                signature=row["signature"],
                start_byte=row["start_byte"],
                end_byte=row["end_byte"],
                start_line=row["start_line"],
                end_line=row["end_line"],
            )
            for row in rows
        ]

    def callers(
        self,
        symbol_id: str,
        depth: int,
        edge_kinds: list[str] | None = None,
    ) -> list[GraphEdgeRecord]:
        """Find incoming edges (callers) to a given symbol.

        Args:
            symbol_id: The callee symbol ID.
            depth: Traversal depth (currently ignored; returns direct callers only).
            edge_kinds: Optional Milestone 25 filter. When None (default) all
                edge kinds are returned (unchanged behavior); when supplied,
                only edges whose ``edge_kind`` is in the list are returned. This
                keeps type-association edges (has_field_of_type / accepts_dto /
                returns_dto / associates) out of a call-graph query that asks
                for e.g. ``--edge-kind calls``.

        Returns:
            List of GraphEdgeRecord where callee_symbol_id matches.
        """
        conn = self._connect()
        sql = (
            "SELECT id, caller_symbol_id, callee_symbol_id, callee_name, "
            "edge_kind, confidence, evidence, source_ref_id, "
            "relative_path, start_line "
            "FROM graph_edges WHERE callee_symbol_id = ?"
        )
        params: list = [symbol_id]
        if edge_kinds:
            placeholders = ",".join("?" for _ in edge_kinds)
            sql += f" AND edge_kind IN ({placeholders})"
            params.extend(edge_kinds)
        rows = conn.execute(sql, params).fetchall()

        return [
            GraphEdgeRecord(
                id=row["id"],
                caller_symbol_id=row["caller_symbol_id"],
                callee_symbol_id=row["callee_symbol_id"],
                callee_name=row["callee_name"],
                edge_kind=row["edge_kind"],
                confidence=row["confidence"],
                evidence=row["evidence"],
                source_ref_id=row["source_ref_id"],
                relative_path=row["relative_path"],
                start_line=row["start_line"],
            )
            for row in rows
        ]

    def callees(
        self,
        symbol_id: str,
        depth: int,
        edge_kinds: list[str] | None = None,
    ) -> list[GraphEdgeRecord]:
        """Find outgoing edges (callees) from a given symbol.

        Args:
            symbol_id: The caller symbol ID.
            depth: Traversal depth (currently ignored; returns direct callees only).
            edge_kinds: Optional Milestone 25 filter; None (default) returns all
                edge kinds (unchanged behavior), otherwise only edges whose
                ``edge_kind`` is in the list. See ``callers``.

        Returns:
            List of GraphEdgeRecord where caller_symbol_id matches.
        """
        conn = self._connect()
        sql = (
            "SELECT id, caller_symbol_id, callee_symbol_id, callee_name, "
            "edge_kind, confidence, evidence, source_ref_id, "
            "relative_path, start_line "
            "FROM graph_edges WHERE caller_symbol_id = ?"
        )
        params: list = [symbol_id]
        if edge_kinds:
            placeholders = ",".join("?" for _ in edge_kinds)
            sql += f" AND edge_kind IN ({placeholders})"
            params.extend(edge_kinds)
        rows = conn.execute(sql, params).fetchall()

        return [
            GraphEdgeRecord(
                id=row["id"],
                caller_symbol_id=row["caller_symbol_id"],
                callee_symbol_id=row["callee_symbol_id"],
                callee_name=row["callee_name"],
                edge_kind=row["edge_kind"],
                confidence=row["confidence"],
                evidence=row["evidence"],
                source_ref_id=row["source_ref_id"],
                relative_path=row["relative_path"],
                start_line=row["start_line"],
            )
            for row in rows
        ]

    def _fact_row_to_record(self, row: sqlite3.Row) -> SymbolFactRecord:
        """Build a SymbolFactRecord from a symbol_facts row, deserializing the
        JSON ``attributes`` column back into a dict (NULL -> None)."""
        attributes = row["attributes"]
        return SymbolFactRecord(
            id=row["id"],
            file_id=row["file_id"],
            subject_symbol_id=row["subject_symbol_id"],
            predicate=row["predicate"],
            object=row["object"],
            attributes=json.loads(attributes) if attributes is not None else None,
            evidence=row["evidence"],
            confidence=row["confidence"],
            language=row["language"],
            relative_path=row["relative_path"],
            start_line=row["start_line"],
        )

    def facts_by_predicate(self, predicate: str) -> list[SymbolFactRecord]:
        """Return all symbol facts with the given predicate."""
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT id, file_id, subject_symbol_id, predicate, object,
                   attributes, evidence, confidence, language,
                   relative_path, start_line
            FROM symbol_facts WHERE predicate = ?
            """,
            (predicate,),
        ).fetchall()
        return [self._fact_row_to_record(row) for row in rows]

    def facts_for_symbol(self, subject_symbol_id: str) -> list[SymbolFactRecord]:
        """Return all symbol facts anchored on the given subject symbol."""
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT id, file_id, subject_symbol_id, predicate, object,
                   attributes, evidence, confidence, language,
                   relative_path, start_line
            FROM symbol_facts WHERE subject_symbol_id = ?
            """,
            (subject_symbol_id,),
        ).fetchall()
        return [self._fact_row_to_record(row) for row in rows]

    def stats(self) -> IndexStats:
        """Return statistics about the indexed repository."""
        conn = self._connect()

        file_count = conn.execute("SELECT COUNT(*) FROM repo_files").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        symbol_count = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        ref_count = conn.execute("SELECT COUNT(*) FROM symbol_refs").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        fact_count = conn.execute("SELECT COUNT(*) FROM symbol_facts").fetchone()[0]

        lang_rows = conn.execute(
            "SELECT DISTINCT language FROM repo_files ORDER BY language"
        ).fetchall()
        languages = [row["language"] for row in lang_rows]

        return IndexStats(
            file_count=file_count,
            chunk_count=chunk_count,
            symbol_count=symbol_count,
            ref_count=ref_count,
            edge_count=edge_count,
            fact_count=fact_count,
            languages=languages,
        )

    def coverage(
        self, claimed: list[tuple[str, int, int]]
    ) -> "CoverageResult":
        """Compute chunk-level coverage of the indexed chunk inventory against
        a set of ``(relative_path, start_line, end_line)`` citations.

        A chunk is *claimed* when some citation cites the same file and the
        citation's line range overlaps the chunk's line range (inclusive on
        both ends); otherwise the chunk is *uncovered*. Returns total/claimed/
        uncovered counts, the claimed percentage, and the uncovered chunks
        ordered by largest line span first (a proxy for "most code per chunk")
        so the caller can target the biggest blind spots next.

        Path matching is tolerant of base/separator differences. Index chunks
        store repo-root-relative POSIX paths (``src/CTCM.API/Foo.cs``), but a
        citation may arrive with a different base prefix (``legacy/<system>/…``
        or an absolute path) or Windows ``\\`` separators. Both sides are
        normalized to POSIX components and matched when the shorter component
        tuple is a *path-suffix* of the longer (anchored on the filename), so a
        citation that carries extra leading segments — or fewer — still matches
        the right chunk instead of silently reporting 0% claimed.

        Pure SQLite read — no Chroma dependency, so it works even where the
        vector path is unavailable. The caller bounds the size of
        ``uncovered_chunks`` itself (e.g. by slicing the result); this method
        returns every uncovered chunk so counts stay exact.
        """
        from .models import CoverageResult, UncoveredChunk

        # Bucket citation ranges by filename (last path component). A chunk can
        # only match a citation that shares its filename, so this both bounds
        # the suffix check (O(chunks × citations-sharing-a-filename)) and drives
        # the actual path-suffix comparison. Each entry keeps the citation's
        # normalized components alongside its line range.
        cite_by_base: dict[str, list[tuple[tuple[str, ...], tuple[int, int]]]] = {}
        for rel_path, start, end in claimed:
            comps = _norm_path_components(rel_path)
            if not comps:
                continue
            lo, hi = (start, end) if start <= end else (end, start)
            cite_by_base.setdefault(comps[-1], []).append((comps, (lo, hi)))

        conn = self._connect()
        rows = conn.execute(
            """
            SELECT id, relative_path, start_line, end_line, symbol_path
            FROM chunks
            """
        ).fetchall()

        total = len(rows)
        claimed_count = 0
        uncovered: list[UncoveredChunk] = []

        for row in rows:
            chunk_comps = _norm_path_components(row["relative_path"])
            chunk_start = row["start_line"]
            chunk_end = row["end_line"]
            is_claimed = False
            candidates = (
                cite_by_base.get(chunk_comps[-1], []) if chunk_comps else []
            )
            for cite_comps, (lo, hi) in candidates:
                # The shorter tuple must be a path-suffix of the longer (both
                # already share a filename), then the line ranges must touch —
                # inclusive overlap: ranges touch if neither is fully
                # before/after the other.
                n = min(len(chunk_comps), len(cite_comps))
                if (
                    chunk_comps[-n:] == cite_comps[-n:]
                    and lo <= chunk_end
                    and hi >= chunk_start
                ):
                    is_claimed = True
                    break
            if is_claimed:
                claimed_count += 1
            else:
                uncovered.append(
                    UncoveredChunk(
                        chunk_id=row["id"],
                        relative_path=row["relative_path"],
                        start_line=chunk_start,
                        end_line=chunk_end,
                        symbol=row["symbol_path"],
                    )
                )

        # Largest line span first; stable tie-break on path/start so output is
        # deterministic across runs.
        uncovered.sort(
            key=lambda c: (
                -(c.end_line - c.start_line),
                c.relative_path,
                c.start_line,
            )
        )

        uncovered_count = total - claimed_count
        pct = (claimed_count / total * 100.0) if total else 0.0

        return CoverageResult(
            total=total,
            claimed=claimed_count,
            uncovered=uncovered_count,
            pct=pct,
            uncovered_chunks=uncovered,
        )

    def set_metadata(self, key: str, value: str) -> None:
        """Set or update a metadata key-value pair."""
        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO index_metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (key, value),
        )
        conn.commit()

    def get_metadata(self, key: str) -> str | None:
        """Retrieve a metadata value by key."""
        conn = self._connect()
        row = conn.execute(
            "SELECT value FROM index_metadata WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # ------------------------------------------------------------------
    # Milestone 15: skip-on-unchanged helpers
    # ------------------------------------------------------------------
    def get_existing_file_shas(self) -> dict[str, tuple[int, str]]:
        """Return mapping of relative_path -> (file_id, sha256) for all rows
        currently in repo_files. Used by the incremental indexer to decide
        which files can be skipped because their content hasn't changed.
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, relative_path, sha256 FROM repo_files"
        ).fetchall()
        return {row["relative_path"]: (row["id"], row["sha256"]) for row in rows}

    def delete_file_artifacts(self, relative_path: str) -> list[str]:
        """Delete all artifacts (chunks, symbols, refs, graph_edges,
        vectors_present rows, repo_files row) for the given relative_path.

        Returns the list of chunk_ids that were deleted so the caller can
        also remove them from Chroma. FK ON DELETE CASCADE handles chunks/
        symbols/symbol_refs when the repo_files row is removed; graph_edges
        cascade from symbols. We also drop graph_edges anchored to the file
        path itself (those with caller_symbol_id NULL but path matching) and
        the vectors_present cache entries.
        """
        conn = self._connect()
        chunk_rows = conn.execute(
            "SELECT id FROM chunks WHERE relative_path = ?",
            (relative_path,),
        ).fetchall()
        chunk_ids = [r["id"] for r in chunk_rows]

        for cid in chunk_ids:
            conn.execute("DELETE FROM chunk_fts WHERE chunk_id = ?", (cid,))
            conn.execute(
                "DELETE FROM vectors_present WHERE chunk_id = ?", (cid,)
            )

        # Remove edges that are anchored to this file by relative_path even
        # if they have no resolved caller symbol (these wouldn't cascade).
        conn.execute(
            "DELETE FROM graph_edges WHERE relative_path = ?",
            (relative_path,),
        )

        # Drop the file row; FK CASCADE removes chunks/symbols/symbol_refs.
        # Graph edges cascade via caller_symbol_id from symbols.
        conn.execute(
            "DELETE FROM repo_files WHERE relative_path = ?",
            (relative_path,),
        )
        conn.commit()
        return chunk_ids

    def delete_graph_edges_for_files(
        self, relative_paths: list[str]
    ) -> None:
        """Delete graph edges anchored at any of the supplied file paths.

        Used during a partial reindex: every file's edges are rebuilt from
        the union of unchanged + changed refs, so we wipe the slate first.
        Unchanged files keep their symbols/refs/chunks; only their edges
        are recomputed.
        """
        if not relative_paths:
            return
        conn = self._connect()
        # SQLite parameter limit: chunk into batches of 500 to be safe.
        for i in range(0, len(relative_paths), 500):
            batch = relative_paths[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"DELETE FROM graph_edges WHERE relative_path IN ({placeholders})",
                batch,
            )
        conn.commit()

    def get_symbols_for_files(
        self, relative_paths: list[str]
    ) -> dict[str, list[Symbol]]:
        """Return symbols stored in SQLite, grouped by relative_path.

        Used to reload unchanged-file symbols when rebuilding the graph
        during a partial reindex.
        """
        from .models import TextRange

        result: dict[str, list[Symbol]] = {p: [] for p in relative_paths}
        if not relative_paths:
            return result
        conn = self._connect()
        for i in range(0, len(relative_paths), 500):
            batch = relative_paths[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            rows = conn.execute(
                f"""
                SELECT s.id, s.language, s.name, s.qualified_name, s.kind,
                       s.container, s.signature, s.start_byte, s.end_byte,
                       s.start_line, s.end_line, s.entity_class,
                       f.relative_path
                FROM symbols s
                JOIN repo_files f ON f.id = s.file_id
                WHERE f.relative_path IN ({placeholders})
                """,
                batch,
            ).fetchall()
            for row in rows:
                sym = Symbol(
                    id=row["id"],
                    language=row["language"],
                    name=row["name"],
                    qualified_name=row["qualified_name"],
                    kind=row["kind"],
                    container=row["container"],
                    signature=row["signature"],
                    range=TextRange(
                        start_byte=row["start_byte"],
                        end_byte=row["end_byte"],
                        start_line=row["start_line"],
                        end_line=row["end_line"],
                    ),
                    # Read from the column rather than defaulted: this is the
                    # reload path for UNCHANGED files during a partial
                    # reindex, so a default here would quietly re-class every
                    # unchanged symbol as `other` on every incremental run.
                    # `or "other"` covers only the one row shape the version-2
                    # backfill cannot reach -- a symbol whose `file_id` names
                    # no `repo_files` row -- which this JOIN excludes anyway.
                    entity_class=row["entity_class"] or "other",
                )
                result.setdefault(row["relative_path"], []).append(sym)
        return result

    def get_refs_for_files(
        self, relative_paths: list[str]
    ) -> dict[str, list[SymbolRef]]:
        """Return symbol_refs stored in SQLite, grouped by relative_path."""
        from .models import TextRange

        result: dict[str, list[SymbolRef]] = {p: [] for p in relative_paths}
        if not relative_paths:
            return result
        conn = self._connect()
        for i in range(0, len(relative_paths), 500):
            batch = relative_paths[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            rows = conn.execute(
                f"""
                SELECT r.id, r.language, r.name, r.kind, r.enclosing_symbol_id,
                       r.start_byte, r.end_byte, r.start_line, r.end_line,
                       r.evidence, f.relative_path
                FROM symbol_refs r
                JOIN repo_files f ON f.id = r.file_id
                WHERE f.relative_path IN ({placeholders})
                """,
                batch,
            ).fetchall()
            for row in rows:
                ref = SymbolRef(
                    id=row["id"],
                    language=row["language"],
                    name=row["name"],
                    kind=row["kind"],
                    enclosing_symbol_id=row["enclosing_symbol_id"],
                    evidence=row["evidence"],
                    range=TextRange(
                        start_byte=row["start_byte"],
                        end_byte=row["end_byte"],
                        start_line=row["start_line"],
                        end_line=row["end_line"],
                    ),
                )
                result.setdefault(row["relative_path"], []).append(ref)
        return result

    def get_source_file_for_path(
        self, relative_path: str, repo_root: Path
    ) -> SourceFile | None:
        """Reconstruct a SourceFile from an existing repo_files row.

        Used by the indexer to provide GraphBuilder a SourceFile-like view of
        an unchanged file without rereading bytes from disk.
        """
        conn = self._connect()
        row = conn.execute(
            """
            SELECT relative_path, language, sha256, size_bytes, mtime_ns
            FROM repo_files WHERE relative_path = ?
            """,
            (relative_path,),
        ).fetchone()
        if row is None:
            return None
        return SourceFile(
            absolute_path=repo_root / row["relative_path"],
            repo_root=repo_root,
            relative_path=row["relative_path"],
            language=row["language"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
            mtime_ns=row["mtime_ns"],
        )

    def get_present_vector_chunk_ids(
        self, chunk_ids: list[str]
    ) -> dict[str, str]:
        """Return mapping of chunk_id -> text_sha256 for chunks already
        recorded as present in Chroma (per the vectors_present cache).
        """
        result: dict[str, str] = {}
        if not chunk_ids:
            return result
        conn = self._connect()
        for i in range(0, len(chunk_ids), 500):
            batch = chunk_ids[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            rows = conn.execute(
                f"SELECT chunk_id, text_sha256 FROM vectors_present "
                f"WHERE chunk_id IN ({placeholders})",
                batch,
            ).fetchall()
            for row in rows:
                result[row["chunk_id"]] = row["text_sha256"]
        return result

    def mark_vectors_present(
        self, items: list[tuple[str, str]]
    ) -> None:
        """Record (chunk_id, text_sha256) pairs as present in Chroma."""
        if not items:
            return
        conn = self._connect()
        conn.executemany(
            """
            INSERT OR REPLACE INTO vectors_present (chunk_id, text_sha256, upserted_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            items,
        )
        conn.commit()

    def get_chunks_missing_vectors(self) -> list[CodeChunk]:
        """Return CodeChunk objects for every chunk that is NOT yet covered by
        the vectors_present cache (or whose text has changed since it was
        cached). Reconstructed from the chunks table so the backfill-vectors
        command can drive the embed/upsert phase off SQLite rather than the
        in-memory list of chunks produced during a fresh index run.

        Chunks with NULL stored text are excluded: they cannot be embedded
        without their source text (only possible when
        store_full_chunk_text_in_sqlite is disabled), so they are not
        backfillable here.

        The LEFT JOIN keys on (chunk_id, text_sha256) so a chunk whose text
        changed (same id, different sha) is treated as missing and re-embedded.
        """
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT c.id, c.file_sha256, c.relative_path, c.language,
                   c.chunk_index, c.chunk_kind, c.symbol_id, c.symbol_path,
                   c.start_byte, c.end_byte, c.start_line, c.end_line,
                   c.text, c.text_sha256, c.token_count_estimate
            FROM chunks c
            LEFT JOIN vectors_present vp
              ON vp.chunk_id = c.id AND vp.text_sha256 = c.text_sha256
            WHERE vp.chunk_id IS NULL AND c.text IS NOT NULL
            ORDER BY c.relative_path, c.chunk_index
            """
        ).fetchall()

        chunks: list[CodeChunk] = []
        for row in rows:
            chunks.append(
                CodeChunk(
                    id=row["id"],
                    file_sha256=row["file_sha256"],
                    relative_path=row["relative_path"],
                    language=row["language"],
                    chunk_index=row["chunk_index"],
                    chunk_kind=row["chunk_kind"],
                    symbol_id=row["symbol_id"],
                    symbol_path=row["symbol_path"],
                    start_byte=row["start_byte"],
                    end_byte=row["end_byte"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    text=row["text"],
                    text_sha256=row["text_sha256"],
                    token_count_estimate=row["token_count_estimate"],
                )
            )
        return chunks

    def get_present_vector_count(self) -> int:
        """Return the total number of chunks recorded as present in Chroma
        (per the vectors_present cache). Used by the indexer to seed the
        running upsert counter once, instead of COUNT(*)-ing every batch.
        """
        conn = self._connect()
        return conn.execute(
            "SELECT COUNT(*) FROM vectors_present"
        ).fetchone()[0]

    def delete_vectors_present(self, chunk_ids: list[str]) -> None:
        """Drop vectors_present cache rows for the supplied chunk_ids."""
        if not chunk_ids:
            return
        conn = self._connect()
        for i in range(0, len(chunk_ids), 500):
            batch = chunk_ids[i : i + 500]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"DELETE FROM vectors_present WHERE chunk_id IN ({placeholders})",
                batch,
            )
        conn.commit()

    def connection(self) -> sqlite3.Connection:
        """Return the open, **migrated** connection for ad-hoc SQL.

        Two callers read `index.sqlite` with plain SQL rather than through
        this class's methods -- `DomainTagger.tag` (Chroma domain stamping)
        and the `domains` command (per-path chunk counts). Before Step 2 they
        used a raw `sqlite3.connect`, which was harmless while they only read
        `chunks` and `vectors_present`, but it made them read paths that
        never migrate: `_migrate_existing_on_open` is what CR-01 added, and it
        only fires for connections opened by this class. Routing them here
        keeps the CR-01 guarantee -- *every* read path advances the schema --
        true by construction rather than by remembering.

        Prefer a real method on this class for anything reusable; this exists
        so that "I need raw SQL" never means "I need my own connection".
        """
        return self._connect()

    # ------------------------------------------------------------------
    # content_hash backfill support (Milestone 1 Step 2)
    # ------------------------------------------------------------------

    def count_symbols_missing_content_hash(self) -> int:
        """Return how many unhashed `symbols` rows `backfill-hashes` can reach.

        `CR-11`: this MUST carry the same `JOIN repo_files` as
        `symbols_missing_content_hash`, or the two disagree about what
        "missing" means. A symbol row whose `file_id` matches no `repo_files`
        row is counted by a bare `COUNT(*)` but never returned for hashing,
        so `remaining_null` exceeds `symbols_missing - symbols_hashed` and
        the CLI prints a "still unhashed" warning that no number of reruns
        can ever clear. The FK's `ON DELETE CASCADE` makes such a row
        unreachable while `PRAGMA foreign_keys` is on -- which `_connect` now
        guarantees -- but the two queries answering one question must agree
        by construction, not by relying on a pragma set somewhere else.
        """
        conn = self._connect()
        return int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM symbols s
                JOIN repo_files f ON f.id = s.file_id
                WHERE s.content_hash IS NULL
                """
            ).fetchone()[0]
        )

    def symbols_missing_content_hash(
        self,
    ) -> list[tuple[str, str, str, int, int, int, int]]:
        """Return every unhashed symbol, with what is needed to hash it.

        Ordered by `relative_path` so a caller can group by file and read
        (and checksum) each file exactly once.

        Returns:
            `(relative_path, file_sha256, symbol_id, start_byte, end_byte,
            start_line, end_line)` per row. Both pairs of bounds are returned
            because `symbol_body_text` needs both -- see its docstring for
            why the line pair is load-bearing rather than a fallback of last
            resort. `file_sha256` is `repo_files.sha256`, the digest of the
            bytes that were actually indexed; the caller must compare it
            against the file's current on-disk digest before hashing
            anything, because a mismatch means the file drifted after
            indexing and hashing it would attribute a hash to source that
            never produced that symbol.
        """
        conn = self._connect()
        return [
            (
                row[0],
                row[1],
                row[2],
                int(row[3]),
                int(row[4]),
                int(row[5]),
                int(row[6]),
            )
            for row in conn.execute(
                """
                SELECT f.relative_path, f.sha256, s.id,
                       s.start_byte, s.end_byte, s.start_line, s.end_line
                FROM symbols s
                JOIN repo_files f ON f.id = s.file_id
                WHERE s.content_hash IS NULL
                ORDER BY f.relative_path
                """
            ).fetchall()
        ]

    def set_symbol_content_hashes(
        self, hashes: list[tuple[str, str]], commit: bool = True
    ) -> int:
        """Store computed `content_hash` values.

        Args:
            hashes: `(symbol_id, content_hash)` pairs. Rows the caller could
                not verify must simply be absent -- never passed as NULL,
                which is already the column's "not yet hashed" state.
            commit: Commit when done.

        Returns:
            The number of pairs written.
        """
        if not hashes:
            return 0
        conn = self._connect()
        conn.executemany(
            "UPDATE symbols SET content_hash = ? WHERE id = ?",
            [
                (hash_value, symbol_id)
                for symbol_id, hash_value in hashes
            ],
        )
        if commit:
            conn.commit()
        return len(hashes)

    def symbols_overlapping_lines(
        self, relative_path: str, start_line: int, end_line: int
    ) -> tuple[str | None, list[tuple[str, str, str, str, int, int]]]:
        """Return the symbols in one file whose spans touch a line range.

        The containment query behind `citations.resolve_anchor` (Milestone 1
        Step 6a). "Touch" means *intersect*, which is the superset that
        includes containment -- `citations` decides which is which, because
        the choice of a single primary anchor is a hashed decision and must
        have exactly one implementation.

        `symbols` carries `file_id` and no path, so this joins through
        `repo_files`; the join is a LEFT JOIN with the range predicate in the
        `ON` clause so that a file present in the index but overlapped by
        nothing still yields its `sha256`. That digest is the whole reason
        the file row is fetched: the caller compares it against the file's
        current on-disk digest before trusting any span here, because a
        drifted file's stored spans describe source that is no longer there.

        `ix_symbols_file_span ON symbols(file_id, start_line, end_line)`
        serves this query; without it `symbols` has no positional index at
        all and this is a scan per citation.

        Args:
            relative_path: A repository-relative path, **already normalized**
                by `identity.normalize_path` -- `repo_files.relative_path` is
                stored in posix form (`discovery.py` uses `as_posix()`), and
                normalizing here as well as at the call site is how two
                paths drift.
            start_line: The citation's first line (1-based).
            end_line: The citation's last line, inclusive.

        Returns:
            `(file_sha256, rows)`. `file_sha256` is `repo_files.sha256`, or
            `None` when the file is not in the index at all -- which the
            caller must distinguish from "indexed but nothing overlaps",
            since only the second says anything about the index being
            current. Each row is `(symbol_id, language, entity_class,
            qualified_name, start_line, end_line)`: the four columns
            `migrations.symbol_anchor_key` needs plus the span the tie-break
            sorts on. `entity_class` may be NULL on a row the version-2
            backfill could not reach.
        """
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT f.sha256 AS file_sha256, s.id AS symbol_id, s.language,
                   s.entity_class, s.qualified_name,
                   s.start_line, s.end_line
            FROM repo_files f
            LEFT JOIN symbols s
                   ON s.file_id = f.id
                  AND s.start_line <= ?
                  AND s.end_line >= ?
            WHERE f.relative_path = ?
            """,
            (end_line, start_line, relative_path),
        ).fetchall()
        if not rows:
            return None, []
        file_sha256 = rows[0]["file_sha256"]
        symbols = [
            (
                row["symbol_id"],
                row["language"],
                row["entity_class"],
                row["qualified_name"],
                int(row["start_line"]),
                int(row["end_line"]),
            )
            for row in rows
            if row["symbol_id"] is not None
        ]
        return file_sha256, symbols

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None


__all__ = [
    "SQLiteStore",
    "SourceText",
    "read_source_text",
    "source_text",
    "symbol_body_text",
    "LexicalResult",
    "CodeChunkRecord",
    "SymbolRecord",
    "GraphEdgeRecord",
    "SymbolFactRecord",
    "IndexStats",
]
