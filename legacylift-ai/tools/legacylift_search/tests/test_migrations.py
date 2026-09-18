"""Tests for the schema migration runner and for the shipped migrations.

The *runner* (Milestone 0) is exercised with throwaway fixture migrations
defined in this module, which is the point of having built the mechanism
first: the first real column addition arrived on a tested runner instead of
being the thing that debugged it.

The second half of this file tests that first real migration --
`INDEX_MIGRATIONS` version 2, which puts `anchor_key`, `entity_class` and
`content_hash` on `symbols` (Milestone 1 Step 2) -- and the backfill-only
`kind` shim it uses. The test that matters most there is
`test_backfilled_and_inserted_anchor_keys_are_identical`: if the migration
and the insert path derive a key differently, the two halves of the corpus
silently stop joining and no error is raised anywhere.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from legacylift_search.identity import ENTITY_CLASSES, anchor_key, content_hash
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.migrations import (
    INDEX_MIGRATIONS,
    KNOWLEDGE_MIGRATIONS,
    SHIM_KIND_TO_ENTITY_CLASS,
    Migration,
    _has_column,
    _index_v2_identity,
    highest_version,
    run_migrations,
    shim_entity_class_for_kind,
    stamp_fresh_database,
    symbol_anchor_key,
    was_database_empty,
)
from legacylift_search.models import SourceFile, Symbol, TextRange
from legacylift_search.store import SQLiteStore


# ----------------------------------------------------------------------
# Fixture migrations
# ----------------------------------------------------------------------


def _user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


class _Recorder:
    """Records which fixture migrations ran, in order."""

    def __init__(self) -> None:
        self.calls: list[int] = []


@pytest.fixture
def recorder() -> _Recorder:
    return _Recorder()


@pytest.fixture
def conn(tmp_path: Path):
    """An open connection to a database holding one table with one row."""
    c = sqlite3.connect(str(tmp_path / "fixture.sqlite"))
    c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    c.execute("INSERT INTO widget (id, name) VALUES (1, 'before')")
    c.commit()
    yield c
    c.close()


def _fixture_migrations(recorder: _Recorder) -> tuple[Migration, ...]:
    """Three migrations: a no-op, an idempotent column add, and a data write."""

    def v2_noop(_conn: sqlite3.Connection) -> None:
        recorder.calls.append(2)

    def v3_add_column(c: sqlite3.Connection) -> None:
        recorder.calls.append(3)
        # Idempotent by construction: re-running a partially applied state
        # must not raise "duplicate column name".
        if not _has_column(c, "widget", "colour"):
            c.execute("ALTER TABLE widget ADD COLUMN colour TEXT DEFAULT 'grey'")

    def v4_insert(c: sqlite3.Connection) -> None:
        recorder.calls.append(4)
        c.execute("INSERT INTO widget (id, name) VALUES (2, 'added-by-v4')")

    return (
        Migration(version=2, description="no-op", apply=v2_noop),
        Migration(version=3, description="add widget.colour", apply=v3_add_column),
        Migration(version=4, description="insert a widget row", apply=v4_insert),
    )


# ----------------------------------------------------------------------
# 1. A fresh database ends at the highest known version, nothing executed
# ----------------------------------------------------------------------


def test_fresh_index_database_is_stamped_at_highest_version(tmp_path: Path) -> None:
    """A brand-new index.sqlite ends at max(INDEX_MIGRATIONS version).

    The expected version is COMPUTED from the list, never a hard-coded
    literal. Both lists end at 1 today and INDEX_MIGRATIONS gains version 2
    in the very next step of this plan, so a literal `1` would be a test
    that fails inside this milestone's successor and gets "fixed" by editing
    the constant — at which point it asserts nothing. The property M0
    actually wants (the fresh stamp works; no column addition is re-applied
    to a table migrate() just created with the column) is version-independent.
    """
    store = SQLiteStore(tmp_path / "index.sqlite")
    store.migrate()
    assert _user_version(store.conn) == highest_version(INDEX_MIGRATIONS)


def test_fresh_knowledge_database_is_stamped_at_highest_version(
    tmp_path: Path,
) -> None:
    """Same for knowledge.sqlite — computed maximum, not a literal.

    KNOWLEDGE_MIGRATIONS must carry the baseline too; if it shipped empty
    this would assert 0, which is indistinguishable from unstamped.
    """
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    assert _user_version(store.conn) == highest_version(KNOWLEDGE_MIGRATIONS)
    assert highest_version(KNOWLEDGE_MIGRATIONS) > 0


def test_fresh_database_runs_no_migration_functions(
    tmp_path: Path, recorder: _Recorder
) -> None:
    """On a fresh database the stamp fires and no migration function runs."""
    db = tmp_path / "fresh.sqlite"
    c = sqlite3.connect(str(db))
    migrations = _fixture_migrations(recorder)
    assert was_database_empty(c) is True
    # Stand in for migrate(): create the schema wholesale, already carrying
    # the column that v3 would otherwise add.
    c.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, colour TEXT)")
    c.commit()
    assert stamp_fresh_database(c, migrations) is True
    assert run_migrations(c, migrations) == []
    assert recorder.calls == []
    assert _user_version(c) == highest_version(migrations)
    c.close()


# ----------------------------------------------------------------------
# 2. An older database has the intervening migrations applied in order
# ----------------------------------------------------------------------


def test_older_database_applies_intervening_migrations_in_order(
    conn: sqlite3.Connection, recorder: _Recorder
) -> None:
    migrations = _fixture_migrations(recorder)
    conn.execute("PRAGMA user_version = 2")

    applied = run_migrations(conn, migrations)

    assert applied == [3, 4]
    assert recorder.calls == [3, 4]  # version 2 skipped; ascending order
    assert _user_version(conn) == highest_version(migrations)


# ----------------------------------------------------------------------
# 3. Rows survive a column addition, with the new column defaulted
# ----------------------------------------------------------------------


def test_existing_rows_survive_a_column_addition(
    conn: sqlite3.Connection, recorder: _Recorder
) -> None:
    """The Milestone 0 acceptance criterion: rows + stamped old version ->
    new column present AND rows still there."""
    migrations = _fixture_migrations(recorder)
    conn.execute("PRAGMA user_version = 2")

    run_migrations(conn, migrations)

    assert _has_column(conn, "widget", "colour")
    row = conn.execute("SELECT name, colour FROM widget WHERE id = 1").fetchone()
    assert row is not None
    assert row["name"] == "before"
    assert row["colour"] == "grey"


# ----------------------------------------------------------------------
# 4. Re-running the runner is a no-op
# ----------------------------------------------------------------------


def test_rerunning_the_runner_is_a_noop(
    conn: sqlite3.Connection, recorder: _Recorder
) -> None:
    migrations = _fixture_migrations(recorder)
    run_migrations(conn, migrations)
    first = list(recorder.calls)
    version_after_first = _user_version(conn)

    second = run_migrations(conn, migrations)

    assert second == []
    assert recorder.calls == first
    assert _user_version(conn) == version_after_first


def test_migration_functions_are_individually_idempotent(
    conn: sqlite3.Connection, recorder: _Recorder
) -> None:
    """A partially applied state can be re-run safely.

    The column already exists but user_version still says otherwise; the
    PRAGMA table_info guard inside the fixture migration makes the re-run
    succeed instead of raising "duplicate column name".
    """
    migrations = _fixture_migrations(recorder)
    conn.execute("ALTER TABLE widget ADD COLUMN colour TEXT DEFAULT 'grey'")
    conn.commit()
    conn.execute("PRAGMA user_version = 2")

    assert run_migrations(conn, migrations) == [3, 4]
    assert _user_version(conn) == highest_version(migrations)


# ----------------------------------------------------------------------
# 5. A failing migration stops the run and commits nothing of its own
# ----------------------------------------------------------------------


def test_failing_migration_leaves_version_at_last_good_and_rolls_back(
    conn: sqlite3.Connection, recorder: _Recorder
) -> None:
    def v3_partial_then_fail(c: sqlite3.Connection) -> None:
        recorder.calls.append(3)
        c.execute("INSERT INTO widget (id, name) VALUES (99, 'partial')")
        raise RuntimeError("boom")

    def v2_ok(c: sqlite3.Connection) -> None:
        recorder.calls.append(2)
        c.execute("ALTER TABLE widget ADD COLUMN colour TEXT DEFAULT 'grey'")

    def v4_never(_c: sqlite3.Connection) -> None:  # pragma: no cover
        recorder.calls.append(4)

    migrations = (
        Migration(version=2, description="ok", apply=v2_ok),
        Migration(version=3, description="fails", apply=v3_partial_then_fail),
        Migration(version=4, description="unreached", apply=v4_never),
    )

    with pytest.raises(RuntimeError, match="boom"):
        run_migrations(conn, migrations)

    # Version 2 succeeded and stays committed, so a retry resumes at 3
    # rather than restarting the whole run.
    assert _user_version(conn) == 2
    assert recorder.calls == [2, 3]  # v4 never ran
    assert _has_column(conn, "widget", "colour")
    # v3's partial work is gone.
    assert (
        conn.execute("SELECT count(*) FROM widget WHERE id = 99").fetchone()[0] == 0
    )


# ----------------------------------------------------------------------
# 6. isolation_level is restored
# ----------------------------------------------------------------------


def test_index_store_migrate_restores_isolation_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`conn.isolation_level` is back to its pre-migrate() value afterwards.

    THIS ASSERTION EXISTS TO STOP THE NEXT REFACTOR from "simplifying" the
    save/restore in `run_migrations` away. The runner must set
    isolation_level=None (DDL gets no implicit transaction otherwise), but the
    stores' shared connection relies on the DEFAULT isolation level plus an
    explicit conn.commit() for the atomicity of ~18 multi-row write sites. If
    the connection is left in autocommit, every one of those commit() calls
    becomes a no-op and a half-failed upsert leaves half its rows behind.
    """
    import legacylift_search.store as store_module

    SQLiteStore(tmp_path / "index.sqlite").migrate()
    _reopen_with_a_pending_migration(
        monkeypatch,
        tmp_path / "index.sqlite",
        store_module,
        "INDEX_MIGRATIONS",
        "index_metadata",
        "fixture_col2",
    )

    store = SQLiteStore(tmp_path / "index.sqlite")
    conn = store._connect()
    before = conn.isolation_level

    store.migrate()
    assert _has_column(conn, "index_metadata", "fixture_col2"), (
        "the runner short-circuited -- this assertion would be vacuous"
    )

    assert conn.isolation_level == before
    # And it must actually be the default, not None.
    assert conn.isolation_level == ""


def test_runner_restores_isolation_level_even_on_failure(
    conn: sqlite3.Connection,
) -> None:
    """The restore is in a `finally`, so a raising migration cannot leak
    autocommit onto the shared connection."""
    before = conn.isolation_level

    def boom(_c: sqlite3.Connection) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        run_migrations(
            conn, (Migration(version=2, description="fails", apply=boom),)
        )

    assert conn.isolation_level == before


def test_knowledge_store_construction_restores_isolation_level(
    tmp_path: Path,
) -> None:
    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    assert store.conn.isolation_level == ""


# ----------------------------------------------------------------------
# Forcing the runner to ACTUALLY run on a store's own connection
# ----------------------------------------------------------------------


def _reopen_with_a_pending_migration(monkeypatch, path, store_module, list_name, table, column):
    """Return a store whose construction really drove `run_migrations`.

    This helper exists because of a trap that made three tests below vacuous
    when they were first written. `run_migrations` returns early when nothing
    is pending -- BEFORE it touches `isolation_level` at all. On a FRESH
    database `stamp_fresh_database` has already written the highest known
    version, so `pending` is empty and the runner is a pure no-op. A test that
    merely constructs a store therefore exercises none of the save/restore
    logic it claims to, and cannot fail for the defect it names.

    So: create the database first (stamped at the current highest version),
    then patch a HIGHER-versioned fixture migration into the list the store
    reads, then reopen. Now the database is not fresh, `pending` is non-empty,
    and the runner genuinely enters its try/finally on the store's shared
    connection. That is also the exact shape of Milestone 1 Step 2, which adds
    INDEX_MIGRATIONS version 2 against existing indexes.
    """
    import legacylift_search.migrations as m

    real = getattr(m, list_name)
    extra = Migration(
        version=highest_version(real) + 1,
        description=f"fixture: add {table}.{column}",
        apply=lambda c: (
            None
            if _has_column(c, table, column)
            else c.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        ),
    )
    patched = tuple(real) + (extra,)
    monkeypatch.setattr(store_module, list_name, patched)
    return patched


# ----------------------------------------------------------------------
# 7. A multi-row write still rolls back as a unit afterwards
# ----------------------------------------------------------------------


def test_multi_row_write_still_rolls_back_after_the_runner_has_executed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression the scoped isolation_level exists to prevent.

    It is invisible to every other test in the suite: if `run_migrations`
    left the store's connection in autocommit, each INSERT below would commit
    on its own and the rollback would recover nothing.
    """
    import legacylift_search.store as store_module

    # First open: creates and stamps the database. The runner short-circuits
    # here, which is precisely why this test used to be vacuous.
    SQLiteStore(tmp_path / "index.sqlite").migrate()

    _reopen_with_a_pending_migration(
        monkeypatch,
        tmp_path / "index.sqlite",
        store_module,
        "INDEX_MIGRATIONS",
        "index_metadata",
        "fixture_col",
    )

    # Second open: the database is at the old version, so the runner really
    # enters its try/finally on THIS connection before the writes below.
    store = SQLiteStore(tmp_path / "index.sqlite")
    store.migrate()
    conn = store.conn
    assert _has_column(conn, "index_metadata", "fixture_col"), (
        "the fixture migration did not run -- this test would be vacuous again"
    )

    conn.execute(
        "INSERT INTO index_metadata (key, value) VALUES ('first', '1')"
    )
    conn.execute(
        "INSERT INTO index_metadata (key, value) VALUES ('second', '2')"
    )
    conn.rollback()

    assert (
        conn.execute(
            "SELECT count(*) FROM index_metadata WHERE key IN ('first','second')"
        ).fetchone()[0]
        == 0
    )


def test_multi_row_write_on_knowledge_store_still_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same regression, on the durable database."""
    import legacylift_search.knowledge_store as ks_module

    KnowledgeStore(tmp_path / "knowledge.sqlite").conn.close()

    _reopen_with_a_pending_migration(
        monkeypatch,
        tmp_path / "knowledge.sqlite",
        ks_module,
        "KNOWLEDGE_MIGRATIONS",
        "domain_exclusions",
        "fixture_col",
    )

    store = KnowledgeStore(tmp_path / "knowledge.sqlite")
    conn = store.conn
    assert _has_column(conn, "domain_exclusions", "fixture_col"), (
        "the fixture migration did not run -- this test would be vacuous again"
    )

    conn.execute("INSERT INTO domain_exclusions (pattern) VALUES ('a/**')")
    conn.execute("INSERT INTO domain_exclusions (pattern) VALUES ('b/**')")
    conn.rollback()

    assert conn.execute("SELECT count(*) FROM domain_exclusions").fetchone()[0] == 0


# ----------------------------------------------------------------------
# Helpers and list shape
# ----------------------------------------------------------------------


def test_both_lists_ship_the_version_1_baseline() -> None:
    """Neither list may ship empty: version 0 is indistinguishable from
    unstamped, so the fresh-database stamp would be unobservable."""
    for migrations in (INDEX_MIGRATIONS, KNOWLEDGE_MIGRATIONS):
        assert migrations, "a migration list must never be empty"
        assert min(m.version for m in migrations) == 1
        versions = [m.version for m in migrations]
        assert len(set(versions)) == len(versions), "versions must be unique"


def test_has_column_reports_missing_table_as_missing_column(
    conn: sqlite3.Connection,
) -> None:
    assert _has_column(conn, "widget", "name") is True
    assert _has_column(conn, "widget", "colour") is False
    assert _has_column(conn, "no_such_table", "anything") is False


def test_stamp_does_not_touch_an_already_versioned_database(
    conn: sqlite3.Connection, recorder: _Recorder
) -> None:
    conn.execute("PRAGMA user_version = 2")
    assert stamp_fresh_database(conn, _fixture_migrations(recorder)) is False
    assert _user_version(conn) == 2


def test_was_database_empty_is_true_only_before_create_table(
    tmp_path: Path,
) -> None:
    c = sqlite3.connect(str(tmp_path / "empty.sqlite"))
    assert was_database_empty(c) is True
    c.execute("CREATE TABLE t (x INTEGER)")
    assert was_database_empty(c) is False
    c.close()


def test_second_migrate_call_on_existing_index_database_is_a_noop(
    tmp_path: Path,
) -> None:
    """An existing (non-fresh) database is not re-stamped and stays put."""
    path = tmp_path / "index.sqlite"
    first = SQLiteStore(path)
    first.migrate()
    first.conn.close()

    second = SQLiteStore(path)
    second.migrate()

    assert _user_version(second.conn) == highest_version(INDEX_MIGRATIONS)


# ----------------------------------------------------------------------
# CR-01: index.sqlite migrates on EVERY open, not only from `index`
# ----------------------------------------------------------------------
# Before the fix, `SQLiteStore.migrate()` was the sole caller of
# `run_migrations(INDEX_MIGRATIONS)` and it ran from exactly two commands.
# Every read command opened an unmigrated database. Verified in production:
# both NNG index.sqlite files sat at user_version 0 while both
# knowledge.sqlite files were at 1. These tests assert directly on
# `PRAGMA user_version`, which is what that evidence was gathered with.


def _force_version_zero(path: Path) -> None:
    """Make a migrated database look like a pre-Milestone-0 one."""
    c = sqlite3.connect(str(path))
    c.execute("PRAGMA user_version = 0")
    c.commit()
    c.close()


def test_read_only_use_of_an_unversioned_index_database_migrates_it(
    tmp_path: Path,
) -> None:
    """Opening an existing user_version 0 index for a READ brings it to 1.

    This is the exact production state: an index built before Milestone 0
    existed, then opened by `stats`/`symbols`/`search`. It must not stay at 0,
    or Milestone 1 Step 2's version 2 never reaches it.
    """
    path = tmp_path / "index.sqlite"
    SQLiteStore(path).migrate()
    _force_version_zero(path)

    store = SQLiteStore(path)
    try:
        store.stats()  # a pure read, the way every read command opens it
        assert _user_version(store._connect()) == highest_version(INDEX_MIGRATIONS)
    finally:
        store.close()


def test_read_path_applies_a_pending_column_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pending migration reaches the database through a read-only caller.

    Shaped exactly like Milestone 1 Step 2 (a new column on `symbols` against
    an already-built index): create the database at today's highest version,
    patch a higher-versioned migration into the list `store.py` reads, reopen
    for a read, and require both the stamp and the column.
    """
    import legacylift_search.store as store_module

    path = tmp_path / "index.sqlite"
    SQLiteStore(path).migrate()

    patched = _reopen_with_a_pending_migration(
        monkeypatch, path, store_module, "INDEX_MIGRATIONS", "symbols", "anchor_probe"
    )

    store = SQLiteStore(path)
    try:
        store.stats()
        conn = store._connect()
        assert _user_version(conn) == highest_version(patched)
        assert _has_column(conn, "symbols", "anchor_probe")
    finally:
        store.close()


def test_a_database_newer_than_this_build_is_refused_loudly(
    tmp_path: Path,
) -> None:
    """Forward-only migrations mean an older build must refuse, not guess."""
    path = tmp_path / "index.sqlite"
    SQLiteStore(path).migrate()
    c = sqlite3.connect(str(path))
    c.execute("PRAGMA user_version = 9999")
    c.commit()
    c.close()

    store = SQLiteStore(path)
    with pytest.raises(RuntimeError) as excinfo:
        store.stats()
    message = str(excinfo.value)
    assert "9999" in message and "NEWER" in message


def test_a_refused_database_is_refused_on_every_open_not_just_the_first(
    tmp_path: Path,
) -> None:
    """`CR-10`: the connection must not be cached before the guard passes.

    `_connect` used to assign `self.conn` and only then migrate, so a
    database the guard refused stayed cached and marked open. The refusal
    fired once; every later `_connect()` handed back a live connection to
    the very schema that had just been rejected, and reads succeeded against
    it. A guard that holds for exactly one call is not a guard.
    """
    path = tmp_path / "index.sqlite"
    SQLiteStore(path).migrate()
    c = sqlite3.connect(str(path))
    c.execute("PRAGMA user_version = 9999")
    c.commit()
    c.close()

    store = SQLiteStore(path)
    with pytest.raises(RuntimeError):
        store._connect()
    assert store.conn is None, "a refused connection must not be cached"

    # The second call must refuse identically rather than return the cached
    # connection -- this is the assertion that failed before the fix.
    with pytest.raises(RuntimeError) as excinfo:
        store._connect()
    assert "9999" in str(excinfo.value)


def test_connect_enables_foreign_keys_without_going_through_migrate(
    tmp_path: Path,
) -> None:
    """`CR-11`: `foreign_keys` is per-connection, and most connections are
    now opened without `migrate()` ever running (that is what `CR-01`
    changed). With it off, `symbols`' `ON DELETE CASCADE` to `repo_files` is
    unenforced and a symbol row can outlive its file.
    """
    path = tmp_path / "index.sqlite"
    SQLiteStore(path).migrate()

    store = SQLiteStore(path)  # a read-shaped open: no migrate() call
    conn = store._connect()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO symbols
                (id, file_id, language, name, qualified_name, kind,
                 container, signature, start_byte, end_byte,
                 start_line, end_line, anchor_key, entity_class, content_hash)
            VALUES ('orphan', 999999, 'sql', 'X', 'X', 'fallback_definition',
                    NULL, NULL, 0, 1, 1, 1, 'ak1:dead', 'other', NULL)
            """
        )
    store.close()


def test_fresh_database_creation_is_unaffected_by_the_open_time_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The open-time runner must SKIP a table-less database.

    Running migrations before `migrate()` creates the tables would try to
    ALTER tables that do not exist. A fresh database still takes the
    create-then-stamp path.
    """
    import legacylift_search.store as store_module

    path = tmp_path / "index.sqlite"
    patched = _reopen_with_a_pending_migration(
        monkeypatch,
        path,
        store_module,
        "INDEX_MIGRATIONS",
        "symbols",
        "anchor_probe",
    )
    store = SQLiteStore(path)
    try:
        store.migrate()  # creates from nothing; must not raise
        conn = store._connect()
        assert _user_version(conn) == highest_version(patched)
    finally:
        store.close()


# ----------------------------------------------------------------------
# The backfill compatibility shim (Milestone 1 Step 2)
# ----------------------------------------------------------------------
# Lives here, beside its single caller. It is deliberately NOT in
# `identity.py`: nothing reaching for a key formula should find a `kind`
# lookup next to it, because "there is no `entity_class_of(kind)`" is the
# rule this table is the one narrow exception to.


def test_shim_defaults_unknown_kinds_to_other() -> None:
    """The open half of the `kind` domain is authored by the analyzed
    repository, so it lands in `other` honestly rather than being guessed."""
    assert shim_entity_class_for_kind("hibernate_bag") == "other"
    assert shim_entity_class_for_kind("webflow_view_state") == "other"
    assert shim_entity_class_for_kind("") == "other"
    assert shim_entity_class_for_kind("something_a_client_invented") == "other"


def test_shim_maps_the_enumerable_closed_half() -> None:
    expected = {
        "class_declaration": "type",
        "interface_declaration": "type",
        "enum_declaration": "type",
        "spring_bean": "type",
        "hibernate_class_mapping": "type",
        "method_declaration": "function",
        "function_definition": "function",
        "paragraph": "function",
        "create_procedure": "function",
        "field_declaration": "field",
        "property_declaration": "field",
        "variable_declarator": "field",
        "data_description_entry": "field",
        "create_table": "table",
        "create_temp_table": "table",
        "decorated_definition": "other",
        "working_storage_section": "other",
        "fallback_definition": "other",
    }
    for kind, entity_class in expected.items():
        assert shim_entity_class_for_kind(kind) == entity_class, kind


def test_shim_values_are_all_in_the_closed_set() -> None:
    assert set(SHIM_KIND_TO_ENTITY_CLASS.values()) <= ENTITY_CLASSES


def test_shim_omits_foreign_key_which_is_not_a_symbol_kind() -> None:
    """`foreign_key` is emitted into `symbol_refs`, which has no
    `entity_class` column at all. It must not appear here."""
    assert "foreign_key" not in SHIM_KIND_TO_ENTITY_CLASS


def test_shim_output_is_always_a_usable_anchor_class() -> None:
    for kind in list(SHIM_KIND_TO_ENTITY_CLASS) + ["unknown_client_kind"]:
        entity_class = shim_entity_class_for_kind(kind)
        # Must not raise: every shim result is a legal `anchor_key` input.
        anchor_key("java", entity_class, "com.acme.Thing", "src/Thing.java")


# ----------------------------------------------------------------------
# INDEX_MIGRATIONS version 2: the three identity columns on `symbols`
# ----------------------------------------------------------------------

_V2_COLUMNS = ("anchor_key", "entity_class", "content_hash")


def _source_file(tmp_path: Path, relative_path: str, body: str) -> SourceFile:
    """Write `body` to disk and return the matching `SourceFile`.

    The file must really exist: `upsert_symbols` reads it to compute
    `content_hash`, so a fixture pointing at nothing would exercise only the
    unreadable branch.
    """
    absolute = tmp_path / Path(relative_path.replace("\\", "/"))
    absolute.parent.mkdir(parents=True, exist_ok=True)
    raw = body.encode("utf-8")
    absolute.write_bytes(raw)
    return SourceFile(
        absolute_path=absolute,
        repo_root=tmp_path,
        relative_path=relative_path,
        language="java",
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        mtime_ns=0,
    )


_BODY = "class Thing {\n    void go() {}\n}\n"


def _symbol(symbol_id: str, qualified_name: str, kind: str, entity_class: str) -> Symbol:
    return Symbol(
        id=symbol_id,
        language="java",
        name=qualified_name.rsplit(".", 1)[-1],
        qualified_name=qualified_name,
        kind=kind,
        entity_class=entity_class,
        range=TextRange(
            start_byte=0, end_byte=len(_BODY.encode("utf-8")), start_line=1, end_line=3
        ),
    )


def _strip_v2_columns(path: Path) -> None:
    """Turn a current-schema index back into a genuine pre-version-2 one.

    Rather than hand-building a legacy `CREATE TABLE`, this takes the real
    schema and removes exactly what version 2 adds, so the fixture cannot
    drift away from the shape the migration will actually meet in production.
    The rows and their values survive; only the three columns, the anchor
    index and the version stamp go.
    """
    c = sqlite3.connect(str(path))
    # The index goes first: SQLite refuses to drop a column an index still
    # references.
    c.execute("DROP INDEX IF EXISTS ix_symbols_anchor_key")
    for column in _V2_COLUMNS:
        c.execute(f"ALTER TABLE symbols DROP COLUMN {column}")
    c.execute("PRAGMA user_version = 1")
    c.commit()
    c.close()


def _seeded_index(tmp_path: Path, symbols: list[Symbol]) -> tuple[Path, SourceFile]:
    """A migrated index holding one file and `symbols`, written normally."""
    path = tmp_path / "index.sqlite"
    source_file = _source_file(tmp_path, "src\\main\\Thing.java", _BODY)
    store = SQLiteStore(path)
    try:
        store.migrate()
        store.upsert_files([source_file])
        store.upsert_symbols(source_file, symbols)
    finally:
        store.close()
    return path, source_file


def test_fresh_index_has_the_three_identity_columns(tmp_path: Path) -> None:
    """`migrate()`'s baseline creates them directly, so the guarded ALTERs in
    version 2 find nothing to do on a database created from nothing."""
    store = SQLiteStore(tmp_path / "index.sqlite")
    try:
        store.migrate()
        conn = store._connect()
        for column in _V2_COLUMNS:
            assert _has_column(conn, "symbols", column), column
        assert _user_version(conn) >= 2
    finally:
        store.close()


def test_anchor_key_index_exists_and_is_not_unique(tmp_path: Path) -> None:
    """Two symbols legitimately share an anchor when one file declares the
    same qualified name twice, so a UNIQUE constraint would reject valid
    input. The index is a lookup index and nothing more."""
    path, source_file = _seeded_index(
        tmp_path,
        [
            _symbol("java:Thing.java:Thing.go:1", "Thing.go", "method_declaration", "function"),
            _symbol("java:Thing.java:Thing.go:9", "Thing.go", "method_declaration", "function"),
        ],
    )
    store = SQLiteStore(path)
    try:
        conn = store._connect()
        rows = conn.execute(
            "SELECT name, \"unique\" FROM pragma_index_list('symbols') "
            "WHERE name = 'ix_symbols_anchor_key'"
        ).fetchall()
        assert len(rows) == 1, "ix_symbols_anchor_key is missing"
        assert rows[0][1] == 0, "anchor_key must NOT be unique"
        keys = [
            r[0] for r in conn.execute("SELECT anchor_key FROM symbols").fetchall()
        ]
        assert len(keys) == 2 and keys[0] == keys[1]
    finally:
        store.close()


def test_version_2_migration_backfills_an_existing_index(tmp_path: Path) -> None:
    """The production case: an index built before version 2, opened again.

    Asserts every property the plan names for a real index -- the version
    advances, no row is gained or lost, `anchor_key` is non-NULL everywhere,
    `entity_class` comes from the shim, and `content_hash` stays NULL because
    the migration must never hash source it cannot prove.
    """
    path, _ = _seeded_index(
        tmp_path,
        [
            _symbol("java:Thing.java:Thing:1", "Thing", "class_declaration", "type"),
            _symbol("java:Thing.java:Thing.go:2", "Thing.go", "method_declaration", "function"),
            _symbol("java:Thing.java:Thing.x:3", "Thing.x", "hibernate_bag", "field"),
        ],
    )
    _strip_v2_columns(path)

    before = sqlite3.connect(str(path))
    row_count_before = before.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    before.close()

    store = SQLiteStore(path)
    try:
        conn = store._connect()  # migrates on open (CR-01)
        assert _user_version(conn) == highest_version(INDEX_MIGRATIONS) >= 2
        rows = conn.execute(
            "SELECT kind, anchor_key, entity_class, content_hash FROM symbols"
        ).fetchall()
        assert len(rows) == row_count_before == 3
        assert all(r["anchor_key"] is not None for r in rows)
        assert all(r["content_hash"] is None for r in rows), (
            "the migration must leave content_hash NULL: it cannot prove the "
            "file on disk is the file that produced these rows"
        )
        by_kind = {r["kind"]: r["entity_class"] for r in rows}
        assert by_kind["class_declaration"] == "type"
        assert by_kind["method_declaration"] == "function"
        # The open half falls to `other`: the shim cannot know the client's
        # own Hibernate vocabulary, and guessing would be an `ak2:` debt.
        assert by_kind["hibernate_bag"] == "other"
    finally:
        store.close()


def test_backfilled_and_inserted_anchor_keys_are_identical(tmp_path: Path) -> None:
    """THE normalization-trap test.

    If the migration and the insert path normalize the path differently, the
    same code entity carries two different keys and **nothing anywhere
    raises** -- the join just returns nothing. Both must go through
    `symbol_anchor_key`, so the same logical row keyed by each route must
    come out byte-identical.

    The fixture path uses backslashes deliberately: separator normalization
    is the one transform `identity.anchor_key` applies internally, so a call
    site that "helpfully" normalized first would show up here.
    """
    symbols = [
        _symbol("java:Thing.java:Thing:1", "Thing", "class_declaration", "type"),
        _symbol("java:Thing.java:Thing.go:2", "Thing.go", "method_declaration", "function"),
    ]

    inserted_path, _ = _seeded_index(tmp_path / "inserted", symbols)
    backfilled_path, _ = _seeded_index(tmp_path / "backfilled", symbols)
    _strip_v2_columns(backfilled_path)

    def _keys(path: Path) -> dict[str, str]:
        store = SQLiteStore(path)
        try:
            return {
                r["id"]: r["anchor_key"]
                for r in store._connect()
                .execute("SELECT id, anchor_key FROM symbols")
                .fetchall()
            }
        finally:
            store.close()

    inserted = _keys(inserted_path)
    backfilled = _keys(backfilled_path)

    assert inserted == backfilled
    assert all(v is not None and v.startswith("ak1:") for v in inserted.values())
    # And the value is the shared derivation's, not an accident of both
    # routes being wrong in the same way.
    assert inserted["java:Thing.java:Thing:1"] == symbol_anchor_key(
        "java", "type", "Thing", "src/main/Thing.java"
    )


def test_insert_path_writes_a_content_hash_of_the_entity_body(
    tmp_path: Path,
) -> None:
    """`content_hash` is NULL only where it cannot be proved. On the insert
    path the file was just read, so it is populated -- and it is the hash of
    the entity's own byte range, not of the file."""
    path, _ = _seeded_index(
        tmp_path,
        [_symbol("java:Thing.java:Thing:1", "Thing", "class_declaration", "type")],
    )
    store = SQLiteStore(path)
    try:
        stored = store._connect().execute(
            "SELECT content_hash FROM symbols"
        ).fetchone()[0]
    finally:
        store.close()
    assert stored == content_hash(_BODY)


def test_version_2_migration_is_idempotent(tmp_path: Path) -> None:
    """Re-running a partially applied version 2 must not raise `duplicate
    column name`, and must not disturb rows it already backfilled."""
    path, _ = _seeded_index(
        tmp_path,
        [_symbol("java:Thing.java:Thing:1", "Thing", "class_declaration", "type")],
    )
    _strip_v2_columns(path)

    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    try:
        _index_v2_identity(c)
        first = c.execute("SELECT id, anchor_key, entity_class FROM symbols").fetchall()
        _index_v2_identity(c)
        second = c.execute("SELECT id, anchor_key, entity_class FROM symbols").fetchall()
    finally:
        c.close()
    assert [tuple(r) for r in first] == [tuple(r) for r in second]
    assert first[0]["anchor_key"] is not None


def test_migration_leaves_symbols_with_no_repo_file_row_null(
    tmp_path: Path,
) -> None:
    """A symbol whose `file_id` names no `repo_files` row has no path, and a
    path is a required `anchor_key` input. The join skips it and it stays
    NULL -- "not yet derived" -- rather than being keyed off an invented
    path. The FK's ON DELETE CASCADE means this cannot arise normally; the
    test pins the behaviour for a corrupt database rather than endorsing it.
    """
    path, _ = _seeded_index(
        tmp_path,
        [_symbol("java:Thing.java:Thing:1", "Thing", "class_declaration", "type")],
    )
    _strip_v2_columns(path)
    c = sqlite3.connect(str(path))
    c.execute(
        """
        INSERT INTO symbols (id, file_id, language, name, qualified_name, kind,
                             start_byte, end_byte, start_line, end_line)
        VALUES ('orphan', 9999, 'java', 'Ghost', 'Ghost', 'class_declaration',
                0, 1, 1, 1)
        """
    )
    c.commit()
    c.close()

    store = SQLiteStore(path)
    try:
        rows = dict(
            store._connect()
            .execute("SELECT id, anchor_key FROM symbols")
            .fetchall()
        )
    finally:
        store.close()
    assert rows["orphan"] is None
    assert rows["java:Thing.java:Thing:1"] is not None


# ----------------------------------------------------------------------
# CR-01, part two: the read paths that bypassed SQLiteStore entirely
# ----------------------------------------------------------------------
# CR-01's open-time migration only fires for connections `SQLiteStore` opens.
# Two callers read `index.sqlite` with a raw `sqlite3.connect` -- the
# `domains` command (per-path chunk counts) and `DomainTagger.tag` (Chroma
# domain stamping). That was harmless while they read nothing but `chunks`
# and `vectors_present`, but from version 2 onward they are read paths that
# never advance the schema, which is the asymmetry CR-01 was raised to
# remove. Both now go through `SQLiteStore.connection()`.


def test_no_module_opens_the_index_with_a_raw_sqlite3_connect() -> None:
    """Structural guard: `sqlite3.connect` belongs to the two store classes.

    A functional test can only cover the call sites that exist today; this
    one fails when a *new* one is added, which is the failure mode that
    produced CR-01 in the first place. If a third store is ever added,
    widen the allow-list deliberately -- do not delete the test.
    """
    import legacylift_search

    package_dir = Path(legacylift_search.__file__).resolve().parent
    allowed = {"store.py", "knowledge_store.py"}
    offenders = sorted(
        module.name
        for module in package_dir.glob("*.py")
        if module.name not in allowed
        and "sqlite3.connect(" in module.read_text(encoding="utf-8")
    )
    assert offenders == [], (
        f"{offenders} open a SQLite database directly. Index reads must go "
        f"through SQLiteStore (see CR-01) so the schema migrates on open."
    )


def test_domains_command_migrates_the_index_it_reads(tmp_path: Path) -> None:
    """The `domains` command is a read path, so it must advance the schema.

    Uses the real polyglot fixture and the real CLI, then asserts on
    `PRAGMA user_version` -- the same evidence CR-01 was diagnosed with.
    """
    import shutil

    from typer.testing import CliRunner

    from legacylift_search.cli import app
    from legacylift_search.config import Manifest, resolve_knowledge_dir
    from legacylift_search.indexer import Indexer
    from legacylift_search.knowledge_store import KnowledgeStore

    fixture = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"
    repo = tmp_path / "repo"
    shutil.copytree(fixture, repo)

    manifest = Manifest()
    manifest.embedding.provider = "hash"
    manifest.embedding.dimension = 64
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")

    index_path = repo / "legacylift-docs" / "index" / "code-search" / "index.sqlite"
    assert index_path.exists()

    # A domain row is needed or the command returns before touching the index.
    ks = KnowledgeStore(resolve_knowledge_dir(repo, manifest) / "knowledge.sqlite")
    try:
        ks.upsert_domain("core", "Core", "", ["src/**"], "manual-test", 0)
        ks.upsert_file_domain("src/eligibility.py", "core", "manual", "manual-test", 1.0)
    finally:
        ks.close()

    _force_version_zero(index_path)

    result = CliRunner().invoke(app, ["domains", "--repo-root", str(repo)])
    assert result.exit_code == 0, result.output

    check = sqlite3.connect(str(index_path))
    try:
        assert _user_version(check) == highest_version(INDEX_MIGRATIONS)
    finally:
        check.close()
