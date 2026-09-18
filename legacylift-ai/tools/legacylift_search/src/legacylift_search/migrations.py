"""Versioned, forward-only schema migrations for both SQLite databases.

Milestone 0 (first half) of `docs/exec-plans/active/reqs-to-data-store.md`.

Before this module existed neither `index.sqlite` nor `knowledge.sqlite`
could evolve: `migrate()` in each store uses `CREATE TABLE IF NOT EXISTS`,
so adding a *table* was free, but adding a *column* required deleting the
database (`index --reset`). There was no `PRAGMA user_version` anywhere.

The contract, which the two halves split cleanly:

* `migrate()` brings a **missing or empty** database up to the current
  *baseline* schema. It is what creates a database from nothing and it keeps
  working exactly as it does today.
* `run_migrations()` brings an **existing older** database forward, one
  migration at a time, in ascending version order, each in its own
  transaction.

A brand-new database therefore gets its whole schema from `migrate()` and is
then *stamped* at the highest known version by `stamp_fresh_database()`, so
the runner never re-applies a column addition to a table that was just
created with that column already present. See `was_database_empty()` for the
one subtlety in that: the emptiness snapshot must be taken *before* any
`CREATE TABLE` runs.

Two migration lists are kept, one per database, because the two files
version independently.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from .identity import anchor_key

__all__ = [
    "INDEX_MIGRATIONS",
    "KNOWLEDGE_MIGRATIONS",
    "Migration",
    "SHIM_KIND_TO_ENTITY_CLASS",
    "highest_version",
    "run_migrations",
    "shim_entity_class_for_kind",
    "stamp_fresh_database",
    "symbol_anchor_key",
    "was_database_empty",
]


@dataclass(frozen=True)
class Migration:
    """One forward-only schema change.

    Attributes:
        version: Target `PRAGMA user_version` after this migration applies.
            Versions are unique within a list and applied in ascending order.
        description: Human-readable summary, used in error messages.
        apply: Callable taking an open `sqlite3.Connection`. It must be
            idempotent wherever that is cheap (guard column additions with
            `_has_column`), so a partially applied state can be re-run.
    """

    version: int
    description: str
    apply: Callable[[sqlite3.Connection], None]


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return True if `table` exists and already has `column`.

    Every real migration is expected to call this before an `ALTER TABLE ...
    ADD COLUMN`, so that re-running a partially applied migration is safe.

    `PRAGMA table_info(<table>)` takes no bound parameters (see the comment
    in `_set_user_version`), and returns zero rows for a table that does not
    exist — which is why a missing table reads as "column absent" rather
    than raising.
    """
    # PRAGMA arguments cannot be bound; `table` is an identifier from our own
    # migration code, never from user input. Quote it defensively anyway.
    quoted = table.replace('"', '""')
    rows = conn.execute(f'PRAGMA table_info("{quoted}")').fetchall()
    return any(row[1] == column for row in rows)


def _get_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row is not None else 0


def _set_user_version(conn: sqlite3.Connection, version: int) -> None:
    """Set `PRAGMA user_version` to `version`.

    NOTE ON THE INTERPOLATION, which looks like a SQL-injection defect and is
    not: PRAGMA statements accept no bound parameters at all, so
    `PRAGMA user_version = ?` raises. The value must be interpolated into the
    SQL text. It is an `int` taken from our own `Migration.version` (or from
    `highest_version()` over our own lists) and never from any input, and it
    is coerced with `int()` here as a belt-and-braces guard.
    """
    conn.execute(f"PRAGMA user_version = {int(version)}")


def highest_version(migrations: Sequence[Migration]) -> int:
    """Return the highest version in `migrations`, or 0 if the list is empty.

    Both shipped lists carry a version-1 baseline precisely so that this
    never returns 0 in production: version 0 is indistinguishable from an
    unstamped database, which would make the fresh-database stamp
    unobservable.
    """
    return max((m.version for m in migrations), default=0)


def was_database_empty(conn: sqlite3.Connection) -> bool:
    """Return True if the database currently holds no tables.

    This is how "the database was just created" is detected, and **when it is
    called matters**: the snapshot must be taken *before* any `CREATE TABLE`
    executes. Called after `migrate()` it always sees tables and would stamp
    nothing, leaving every fresh database at version 0 and re-running every
    future column addition against columns that already exist.

    Callers therefore take the snapshot early and hold it in a local:
      * `SQLiteStore.migrate()` — right after the two PRAGMA statements, held
        until the `run_migrations` call at the end of the same method.
      * `KnowledgeStore.__init__` — *before* the `self.migrate()` call.
    """
    row = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table'"
    ).fetchone()
    return int(row[0]) == 0 if row is not None else True


def stamp_fresh_database(
    conn: sqlite3.Connection, migrations: Sequence[Migration]
) -> bool:
    """Stamp a just-created database at the highest known migration version.

    Call this only when `was_database_empty()` was True *before* `migrate()`
    ran, i.e. the schema now present was created wholesale by `migrate()` and
    already includes everything every migration would add. Stamping it means
    the runner has nothing to do, which is the correct outcome.

    Does nothing (and returns False) if `user_version` is already non-zero —
    an existing database is the runner's business, not the stamp's.

    Returns:
        True if the version was written, False if it was left alone.
    """
    if _get_user_version(conn) != 0:
        return False
    target = highest_version(migrations)
    if target == 0:
        return False
    # A bare PRAGMA write, deliberately outside any transaction: this runs
    # from migrate(), which is already committing DDL of its own.
    _set_user_version(conn, target)
    return True


def run_migrations(
    conn: sqlite3.Connection, migrations: Sequence[Migration]
) -> list[int]:
    """Apply every migration newer than `PRAGMA user_version`, in order.

    Each migration runs inside its own explicit transaction and stamps
    `user_version` as it goes, so a failure leaves the database at the last
    *successfully applied* version and a retry resumes rather than restarts.
    One transaction around the whole run would be simpler but would roll back
    the migrations that had succeeded, destroying exactly that property.

    Two sqlite3 mechanics are handled here and must not be "simplified":

    1. **DDL gets no implicit transaction.** At the default
       `isolation_level`, Python's sqlite3 opens a transaction before
       INSERT/UPDATE/DELETE/REPLACE and *not* before ALTER TABLE or CREATE.
       So an `ALTER TABLE` migration would auto-commit and the promise that a
       failure aborts it would be false. Hence `isolation_level = None` plus
       explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK.

    2. **But that setting is scoped to this run and restored in a `finally`,
       and is never set in `_connect`.** Both stores share one connection at
       the default isolation level and rely on the implicit transaction plus
       an explicit `conn.commit()` for the atomicity of their multi-row
       writes (18 such sites across `store.py` and `knowledge_store.py`).
       Leaving the connection in autocommit turns every one of those
       `commit()` calls into a no-op, so a half-failed `upsert_chunks` would
       leave half its rows behind.

    `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys` cannot run inside a
    transaction; both already run at the top of the stores' `migrate()`
    methods and must stay there, outside anything this function wraps.

    Args:
        conn: Open connection to the database being migrated.
        migrations: That database's migration list.

    Returns:
        The versions actually applied, in the order they were applied.

    Raises:
        Whatever a migration function raises, after rolling that one
        migration back. Earlier migrations in the same run stay committed.
    """
    pending = sorted(
        (m for m in migrations if m.version > _get_user_version(conn)),
        key=lambda m: m.version,
    )
    if not pending:
        return []

    previous_isolation = conn.isolation_level
    applied: list[int] = []
    try:
        # Autocommit mode: sqlite3 issues no BEGIN of its own, so the
        # explicit ones below are the only transaction boundaries and they
        # cover DDL as well as DML.
        conn.isolation_level = None
        for migration in pending:
            conn.execute("BEGIN IMMEDIATE")
            try:
                migration.apply(conn)
                _set_user_version(conn, migration.version)
            except Exception:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
            applied.append(migration.version)
    finally:
        conn.isolation_level = previous_isolation

    return applied


# ----------------------------------------------------------------------
# The migration lists
# ----------------------------------------------------------------------


def _baseline(conn: sqlite3.Connection) -> None:
    """No-op baseline.

    Deliberately empty. Every table that exists today is created by the
    owning store's `migrate()`, so there is nothing for version 1 to do —
    but the *entry* is not optional. With an empty list `highest_version()`
    is 0, the fresh-database stamp writes nothing, and a stamped database is
    indistinguishable from an unstamped one, so M0's central mechanism could
    not be observed working. A real version 1 makes the stamp observable and
    the fresh-versus-existing distinction testable in production shape.

    Both lists carry it. Shipping it for `INDEX_MIGRATIONS` only would leave
    every `knowledge.sqlite` at version 0 forever, so the first real column
    addition to a durable table — the one database holding irreplaceable
    human judgment — would be applied to freshly created databases that
    already have that column.
    """


# ----------------------------------------------------------------------
# Shared derivation for the version-2 identity columns
# ----------------------------------------------------------------------
#
# WHY THIS LIVES HERE AND NOT IN THE STORE. The version-2 backfill below and
# `SQLiteStore.upsert_symbols` must produce byte-identical `anchor_key`
# values for the same entity. If they normalize differently, backfilled rows
# and newly written rows carry different keys for the same code entity and
# **nothing anywhere raises** -- the join simply returns nothing. The only
# structural defence is that both call ONE function, so the shared
# derivation is factored here, where the migration can reach it without a
# migration having to import the application's store (`store.py` already
# imports this module; the reverse would be a cycle).


def symbol_anchor_key(
    language: str,
    entity_class: str,
    qualified_name: str,
    relative_path: str,
) -> str:
    """Derive `symbols.anchor_key` from the four values a `symbols` row holds.

    **This is the ONE derivation.** Its two callers are
    `SQLiteStore.upsert_symbols` (the insert path) and `_index_v2_identity`
    (the migration backfill), and `tests/test_migrations.py` asserts that a
    row written by the first and the same row backfilled by the second land
    on an identical key. Do not inline `identity.anchor_key` at either site:
    two lookalike expressions is exactly the failure this exists to prevent.

    Note what is deliberately NOT done here: the path is **not** normalized
    before the call. `identity.anchor_key` normalizes it internally, so
    normalizing again at a call site is precisely how the two paths drift.

    The arguments map onto columns as follows, and both callers must take
    them from these sources:

    ==================  ================================================
    argument            column
    ==================  ================================================
    `language`          `symbols.language`
    `entity_class`      `symbols.entity_class` (declared by the extractor;
                        backfilled by `shim_entity_class_for_kind`)
    `qualified_name`    `symbols.qualified_name`
    `relative_path`     `repo_files.relative_path`, joined on `file_id` --
                        `symbols` has no path column of its own
    ==================  ================================================

    Args:
        language: The Layer-0 language key, e.g. `csharp`.
        entity_class: One of `identity.ENTITY_CLASSES`.
        qualified_name: The symbol's qualified name.
        relative_path: The repository-relative path of the symbol's file, in
            any separator style.

    Returns:
        The `ak1:`-prefixed anchor key.
    """
    return anchor_key(language, entity_class, qualified_name, relative_path)


# ----------------------------------------------------------------------
# Compatibility shim -- temporary, backfill-only
# ----------------------------------------------------------------------

SHIM_KIND_TO_ENTITY_CLASS: Final[dict[str, str]] = {
    # type
    "class_declaration": "type",
    "class_definition": "type",
    "interface_declaration": "type",
    "struct_declaration": "type",
    "enum_declaration": "type",
    "record_declaration": "type",
    "type_alias_declaration": "type",
    "spring_bean": "type",
    "hibernate_class_mapping": "type",
    # function
    "method_declaration": "function",
    "method_definition": "function",
    "constructor_declaration": "function",
    "abstract_method_signature": "function",
    "function_declaration": "function",
    "function_definition": "function",
    "generator_function_declaration": "function",
    "paragraph": "function",
    "section_header": "function",
    "procedure_division": "function",
    "create_procedure": "function",
    "create_function": "function",
    "create_trigger_statement": "function",
    # field -- `property_declaration` is the one genuinely ambiguous entry and
    # is decided by measurement, not taste: it is state, so it is a field.
    # Mapping it to `function` re-collapses the `FileDistributedCache`
    # `IsConnected` collision that justifies the column existing at all.
    "field_declaration": "field",
    "property_declaration": "field",
    "variable_declaration": "field",
    "lexical_declaration": "field",
    "variable_declarator": "field",
    "data_description_entry": "field",
    # table
    "create_table": "table",
    "create_view": "table",
    "view_definition": "table",
    "table_definition": "table",
    "create_temp_table": "table",
    # other -- lexical containers whose contents are emitted separately, plus
    # the regex fallback, whose kind is genuinely unknown.
    "decorated_definition": "other",
    "create_index_statement": "other",
    "program_id_paragraph": "other",
    "file_description_entry": "other",
    "linkage_section": "other",
    "working_storage_section": "other",
    "webflow_flow": "other",
    "xml_document": "other",
    "fallback_definition": "other",
}
"""**COMPATIBILITY SHIM -- do not build on this.** Backfill use only.

This is the single narrow exception to "there is no `entity_class_of(kind)`"
(`NORMATIVE SPEC-3` S3.1.2). It exists for exactly one caller,
`_index_v2_identity` below, which must put *some* `entity_class` on `symbols`
rows written before extractors declared one -- the extractor that would have
declared it did not run, so the value cannot be recovered from the row.

**It is deletable once every index in use has been rebuilt**, and under this
plan's workflow -- a completely new analysis from `preflight` onward -- that
may be immediately. **Confirm rather than assume before deleting it**: every
`index.sqlite` anyone still reads must have been *created* after version 2
shipped, i.e. its three identity columns came from `SQLiteStore.migrate()`
rather than from this migration. It must not acquire a second caller; new
code declares the class at the point of emission, which is the point of
maximum evidence.

It carries the closed half of the `kind` domain, per S3.1.2's classification
table. Note deliberately absent: **`foreign_key`**, which is a `SymbolRef`
kind emitted into `symbol_refs` (`extractors.py:1618`, `:1722`) and is not a
symbol kind at all.

**Its known inaccuracy, which is why it is a shim and not a mapping.** The
open half of the `kind` domain is authored by the *client's* files -- the
``f"hibernate_{tag}"`` children (declared `field` at their emission site) and
every Spring Webflow state element (declared `other`) -- and cannot be
enumerated here. Those fall to the `other` default, so a backfilled row may
carry `other` where a rebuilt index would carry `field`. That is accepted for
backfilled rows and is exactly why a rebuild supersedes this table.

**Promoting a kind out of `other` in this table is an `ak2:` event** once
anything downstream has hashed the result -- as is adding, removing or
renaming any value of `identity.ENTITY_CLASSES`. Neither is an edit in place.
"""


def shim_entity_class_for_kind(kind: str) -> str:
    """Look up a backfill `entity_class` for a legacy `symbols.kind`.

    **COMPATIBILITY SHIM -- backfill only.** See
    `SHIM_KIND_TO_ENTITY_CLASS` for the full limitation.

    Args:
        kind: A `symbols.kind` value, possibly authored by the analyzed
            repository's own framework vocabulary.

    Returns:
        The declared class if `kind` is in the enumerable closed half,
        otherwise `"other"` -- the honest default for a kind whose class is
        genuinely unknown here.
    """
    return SHIM_KIND_TO_ENTITY_CLASS.get(kind, "other")


_V2_UPDATE_BATCH: Final[int] = 2000
"""Rows per `executemany` in the version-2 backfill.

The `SELECT` is read wholesale (58,614 symbols on the largest index measured
here -- five small columns, a few MB), but the writes are chunked so a much
larger index does not build one enormous parameter list.
"""


def _index_v2_identity(conn: sqlite3.Connection) -> None:
    """Add `anchor_key`, `entity_class` and `content_hash` to `symbols`.

    Milestone 1, Step 2 of `docs/exec-plans/active/reqs-to-data-store.md`.
    **This is the first substantive migration in this codebase and its shape
    is meant to be copied**, so it is written out longhand: guard every
    `ADD COLUMN` with `_has_column` so a partially applied run resumes,
    create the index with `IF NOT EXISTS`, and do the data backfill inside
    the same transaction as the DDL (`run_migrations` opens it).

    The three columns backfill differently, and the differences are the
    substance of the step rather than an implementation detail:

    * **`entity_class`** cannot be recovered from an existing row -- the
      extractor that would have declared it did not run -- so it is
      backfilled from `SHIM_KIND_TO_ENTITY_CLASS`, defaulting to `other`.
    * **`anchor_key`** is computed from stored columns only, so it is
      backfilled in place for every row, using the `entity_class` just
      derived. **The path is not on `symbols`**: `relative_path` lives on
      `repo_files` and is reached by joining on `file_id`. It is derived
      through `symbol_anchor_key`, the same function the insert path calls
      -- see that function for why sharing it is load-bearing.
    * **`content_hash`** needs the symbol's body text, which `symbols` does
      not store, and on an existing database the file on disk may no longer
      be the file that was indexed. A backfill here would write hashes for
      source that was never the source of these rows, so **the column is
      added and left NULL**. NULL means "not yet hashed" and never
      "unchanged". `legacylift-search backfill-hashes` fills it in, checking
      each file's on-disk `sha256` against `repo_files.sha256` first; do not
      expect the next `index` run to do it, because the skip-on-unchanged
      fast path never revisits an unchanged file.

    `anchor_key` is **not unique** -- two symbols share one when a file
    legitimately declares the same qualified name twice -- so the index on it
    is a plain lookup index with no `UNIQUE` constraint.

    A row whose `file_id` matches no `repo_files` row is skipped by the join
    and keeps a NULL `anchor_key`. That cannot happen under the table's
    `ON DELETE CASCADE` foreign key, and inventing a path for such a row
    would be worse than leaving it NULL: NULL is already this schema's
    "not yet derived".
    """
    for column in ("anchor_key", "entity_class", "content_hash"):
        if not _has_column(conn, "symbols", column):
            # `column` is a literal from the tuple above, never input.
            conn.execute(f"ALTER TABLE symbols ADD COLUMN {column} TEXT")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_symbols_anchor_key "
        "ON symbols(anchor_key)"
    )
    # Step 6a's containment index rides in this migration rather than a
    # version of its own, as Step 6a's own bullet directs: "alongside Step 2's
    # `anchor_key` index, in the same migration". Version 2 is unreleased --
    # it is being added in this same milestone -- so no database in existence
    # is already stamped past it, and a separate version would buy nothing but
    # a second no-op ALTER-less step. `symbols` has no positional index
    # otherwise, so the citation containment query would scan once per
    # citation.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_symbols_file_span "
        "ON symbols(file_id, start_line, end_line)"
    )

    rows = conn.execute(
        """
        SELECT s.id, s.language, s.qualified_name, s.kind, f.relative_path
        FROM symbols s
        JOIN repo_files f ON f.id = s.file_id
        WHERE s.anchor_key IS NULL OR s.entity_class IS NULL
        """
    ).fetchall()

    updates: list[tuple[str, str, str]] = []
    for symbol_id, language, qualified_name, kind, relative_path in rows:
        entity_class = shim_entity_class_for_kind(kind)
        updates.append(
            (
                entity_class,
                symbol_anchor_key(
                    language, entity_class, qualified_name, relative_path
                ),
                symbol_id,
            )
        )

    for start in range(0, len(updates), _V2_UPDATE_BATCH):
        conn.executemany(
            "UPDATE symbols SET entity_class = ?, anchor_key = ? WHERE id = ?",
            updates[start : start + _V2_UPDATE_BATCH],
        )


INDEX_MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="baseline: schema as created by SQLiteStore.migrate()",
        apply=_baseline,
    ),
    Migration(
        version=2,
        description=(
            "symbols: add anchor_key, entity_class and content_hash "
            "(+ ix_symbols_anchor_key, ix_symbols_file_span); backfill the "
            "first two, leave content_hash NULL for `backfill-hashes`"
        ),
        apply=_index_v2_identity,
    ),
)
"""Migrations for `index.sqlite` (the disposable code-search index)."""


KNOWLEDGE_MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="baseline: schema as created by KnowledgeStore.migrate()",
        apply=_baseline,
    ),
)
"""Migrations for `knowledge.sqlite` (the durable knowledge store)."""
