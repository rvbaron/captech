"""Tests for the durable knowledge store (Milestone 1 of
`domain-enhancements-plan.md`).

Verifies:
- Constructing a KnowledgeStore creates the parent directory and the
  SQLite file (migration runs from __init__, unlike SQLiteStore).
- The WAL/foreign-key pragmas are set.
- A row written to the store survives closing and reopening (durability
  proxy for the `--reset` durability check exercised end-to-end in
  Concrete Steps).
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from legacylift_search.knowledge_store import KnowledgeStore


def test_construction_creates_parent_dir_and_file():
    """Merely constructing a KnowledgeStore creates+migrates the file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        assert not sqlite_path.parent.exists()

        ks = KnowledgeStore(sqlite_path)
        try:
            assert sqlite_path.parent.exists()
            assert sqlite_path.exists()
        finally:
            ks.close()


def test_pragmas_set():
    """WAL and foreign_keys pragmas are set on construction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            conn = ks._connect()
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert journal_mode.lower() == "wal"
            assert foreign_keys == 1
        finally:
            ks.close()


def test_written_row_survives_close_and_reopen():
    """A row written to the store survives closing and reopening the file.

    This is the unit-level proxy for the Milestone 1 durability acceptance
    check ("write a sentinel row, run index --reset, confirm it survives")
    exercised end-to-end against the fixture in Concrete Steps.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"

        ks = KnowledgeStore(sqlite_path)
        conn = ks._connect()
        conn.execute("CREATE TABLE IF NOT EXISTS _sentinel(id INTEGER)")
        conn.execute("INSERT INTO _sentinel VALUES (1)")
        conn.commit()
        ks.close()

        # Reopen (construction migrates again, idempotently) and confirm the
        # row is still there.
        ks2 = KnowledgeStore(sqlite_path)
        try:
            count = ks2._connect().execute(
                "SELECT count(*) FROM _sentinel"
            ).fetchone()[0]
            assert count == 1
        finally:
            ks2.close()


def test_upsert_file_domain_manual_wins_guard():
    """A non-manual write against a `manual` row is a no-op (defense-in-depth).

    Manual-wins is enforced at the write primitive, not only at the callers:
    a glob/unassigned write can never clobber a human `manual` correction, but
    a `manual` write still replaces any existing row (correction tooling path).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        try:
            # Human hand-edits a manual assignment.
            ks.upsert_file_domain("src/a.py", "claims", "manual", None, 1.0)

            # A later glob resolution tries to reassign the same path.
            ks.upsert_file_domain("src/a.py", "billing", "glob", "run-1", 1.0)
            row = ks._connect().execute(
                "SELECT domain, source FROM file_domains WHERE relative_path = ?",
                ("src/a.py",),
            ).fetchone()
            assert (row["domain"], row["source"]) == ("claims", "manual")

            # An unassigned (source='glob') write is likewise refused.
            ks.upsert_file_domain("src/a.py", "unassigned", "glob", None, 1.0)
            row = ks._connect().execute(
                "SELECT domain, source FROM file_domains WHERE relative_path = ?",
                ("src/a.py",),
            ).fetchone()
            assert (row["domain"], row["source"]) == ("claims", "manual")

            # A new manual write DOES replace the prior manual row.
            ks.upsert_file_domain("src/a.py", "regulatory", "manual", None, 1.0)
            row = ks._connect().execute(
                "SELECT domain, source FROM file_domains WHERE relative_path = ?",
                ("src/a.py",),
            ).fetchone()
            assert (row["domain"], row["source"]) == ("regulatory", "manual")

            # A glob write to a fresh path is unaffected by the guard.
            ks.upsert_file_domain("src/b.py", "billing", "glob", "run-1", 1.0)
            row = ks._connect().execute(
                "SELECT domain, source FROM file_domains WHERE relative_path = ?",
                ("src/b.py",),
            ).fetchone()
            assert (row["domain"], row["source"]) == ("billing", "glob")
        finally:
            ks.close()


def test_close_releases_connection():
    """close() sets conn back to None, mirroring SQLiteStore.close."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "knowledge" / "knowledge.sqlite"
        ks = KnowledgeStore(sqlite_path)
        assert ks.conn is not None
        ks.close()
        assert ks.conn is None
