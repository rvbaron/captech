"""Indexing orchestration that ties discovery, extraction, chunking,
SQLite, embeddings, and Chroma together.

Implements Milestone 10 of the ExecPlan
(`docs/exec-plans/active/semantic-code-search-graph-index.md`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .chunking import CodeChunker
from .config import (
    IndexConfig,
    Manifest,
    is_default_setting,
    resolve_analysis_dir,
    resolve_index_dir,
    resolve_knowledge_dir,
)
# Same layering as domain_tagger.py, which imports this banner helper for
# the same Milestone 0 requirement; cli_helpers pulls in only config +
# typer at runtime, so there is no import cycle.
from .cli_helpers import print_resolved_path
from .credential_notice import (
    log_lines as credential_log_lines,
    render_notice as render_credential_notice,
    scan_discovered_files as scan_for_credentials,
)
from .discovery import discover_source_files
from .embed_filter import dedupe_by_text_sha, partition_for_embedding
from .embeddings import create_embedder
from .extract_worker import _extract_with, _init_worker, extract_one
from .extractors import SymbolExtractor, load_profiles
from .graph import GraphBuilder
from .knowledge_store import KnowledgeStore
from .identity import content_hash
from .models import CodeChunk, GraphEdge, Symbol
from .store import SQLiteStore, source_text, symbol_body_text
from .vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"

# Index-like directory names that --reset is allowed to wipe.
_INDEX_DIR_NAMES = {
    "code-search",
    ".legacylift",
    "legacylift-index",
}


def _is_within(candidate: Path, ancestor: Path) -> bool:
    """True when `candidate` is `ancestor` or lives underneath it.

    Both paths are expected to be already resolved. `relative_to` raises
    `ValueError` rather than returning a flag, and it also raises when the
    two live on different Windows drives, so both cases collapse to False.
    """
    try:
        candidate.relative_to(ancestor)
    except ValueError:
        return False
    return True


class IndexStats(BaseModel):
    """Statistics summary returned from an indexing run."""

    files_indexed: int
    chunk_count: int
    symbol_count: int
    ref_count: int
    graph_edge_count: int
    fact_count: int = 0
    embedder_name: str
    embedding_dimension: int
    index_dir: str
    # Milestone 15: incremental indexing stats. files_indexed counts all
    # files present in the index after the run (changed + unchanged);
    # files_processed counts only those that were re-extracted/re-chunked
    # this run. files_skipped == files_indexed - files_processed for
    # non-reset runs; equals 0 on a cold --reset run.
    files_processed: int = 0
    files_skipped: int = 0
    files_deleted: int = 0
    vectors_upserted: int = 0
    vectors_skipped: int = 0


class BackfillStats(BaseModel):
    """Statistics summary returned from a backfill-vectors run."""

    chunks_missing: int
    vectors_backfilled: int
    vectors_upserted_total: int
    chunk_count: int
    embedder_name: str
    embedding_dimension: int
    index_dir: str


class HashBackfillStats(BaseModel):
    """Statistics summary returned from a `backfill-hashes` run.

    The two counts that matter are `symbols_hashed` and `symbols_skipped`,
    and they are reported separately on purpose: a skip is not a failure, it
    is the command declining to attribute a hash to source that has changed
    since it was indexed.

    Attributes:
        symbols_missing: Rows with a NULL `content_hash` when the run began.
        symbols_hashed: Rows hashed and written -- their file's on-disk
            `sha256` still matched `repo_files.sha256`.
        symbols_skipped: Rows deliberately left NULL. `files_drifted` and
            `files_unreadable` say which of the two reasons applied.
        files_verified: Files whose on-disk digest matched.
        files_drifted: Files whose bytes changed after indexing. Their
            symbols are left for the next real `index` run, which will
            re-extract them because a drifted file is a changed file.
        files_unreadable: Files that could not be read at all -- deleted,
            locked, or permission-denied since indexing.
        symbols_unhashable: Rows inside a verified file where neither the
            byte bounds nor the line bounds fit the file. Included in
            `symbols_skipped`; a non-zero value points at an extractor bug,
            not at drift.
        remaining_null: Rows still NULL after the run. Equal to
            `symbols_missing - symbols_hashed`, and reported so a caller can
            see progress is monotonic across repeated runs.
        symbol_count: Total rows in `symbols`.
        index_dir: The resolved index directory.
    """

    symbols_missing: int
    symbols_hashed: int
    symbols_skipped: int
    files_verified: int
    files_drifted: int
    files_unreadable: int
    symbols_unhashable: int
    remaining_null: int
    symbol_count: int
    index_dir: str


class Indexer:
    """End-to-end indexer that orchestrates discovery → extract → chunk →
    persist (SQLite) → graph → embed → persist (Chroma) → metadata.
    """

    def __init__(self, manifest: Manifest, repo_root: Path) -> None:
        self.manifest = manifest
        self.repo_root = repo_root.resolve()

    # ------------------------------------------------------------------
    # Path-safety check for --reset
    # ------------------------------------------------------------------
    def _validate_reset_path(self, index_dir: Path) -> None:
        """Refuse to wipe paths that are clearly not index dirs.

        Per spec (Idempotence and Recovery), in this order:
        - Refuse drive root.
        - Refuse user home.
        - Refuse repo root.
        - Require index-like directory name.
        - Require descendant of <repo_root>/legacylift-docs/ OR of the
          resolved analysis directory.
        - Require positive evidence that the target really is an index
          directory: index.sqlite present, chroma/ present, or empty.
        """
        resolved = index_dir.resolve()

        # Refuse drive root or filesystem root
        if resolved == resolved.anchor and resolved.parent == resolved:
            raise ValueError(
                f"Refusing to reset drive/filesystem root: {resolved}"
            )
        # Path with no parent (root) — anchor check
        if str(resolved) == resolved.anchor or resolved == Path(resolved.anchor):
            raise ValueError(
                f"Refusing to reset drive/filesystem root: {resolved}"
            )

        # Refuse user home. The try only guards Path.home(), which raises when
        # the platform cannot determine a home directory; it must NOT wrap the
        # raise below. It used to, so `except Exception: pass` swallowed this
        # clause's own refusal and the check never fired — home was in practice
        # only caught later, by the index-like-name clause, under a message
        # that named the wrong reason.
        try:
            home: Path | None = Path.home().resolve()
        except Exception:
            home = None
        if home is not None and resolved == home:
            raise ValueError(
                f"Refusing to reset user home directory: {resolved}"
            )

        # Refuse repo root
        if resolved == self.repo_root:
            raise ValueError(
                f"Refusing to reset repository root: {resolved}"
            )

        # Require index-like directory name
        if resolved.name not in _INDEX_DIR_NAMES and not resolved.name.startswith(
            "code-search"
        ):
            # Also accept a path whose parent chain ends in legacylift-docs/index
            parts = resolved.parts
            if not (
                "legacylift-docs" in parts
                and "index" in parts
            ):
                raise ValueError(
                    f"Refusing to reset path that is not a recognized index "
                    f"directory: {resolved}. Expected name like 'code-search' "
                    f"or path under 'legacylift-docs/index/'."
                )

        # Require descendant of one of the places resolve_index_dir can put
        # an index. CR-06: this list used to carry only the last two of the
        # resolver's four branches, under a comment claiming it carried "the
        # SAME two branches ... so the guard and the resolver agree by
        # construction". That was false, and the falsehood had teeth:
        # index_dir=".legacylift" resolves to <repo>/.legacylift and was
        # refused here, even though ".legacylift" is deliberately in
        # _INDEX_DIR_NAMES so the name clause above passes it. Milestone 0
        # promoted the two configured-index_dir branches to documented,
        # tested, first-class precedence, so the guard now covers all four:
        #
        #   branch 4  <repo_root>/legacylift-docs/          (the fallback)
        #   branch 3  the resolved analysis directory       (convention, or
        #             an explicit analysis_dir override)
        #   branch 1  an ABSOLUTE configured index_dir
        #   branch 2  a non-default RELATIVE configured index_dir, which by
        #             construction lands under repo_root
        #
        # Be precise about what each entry buys, because branches 1 and 2 are
        # weaker than 3 and 4 and pretending otherwise is how the old comment
        # went wrong. For 3 and 4 the ancestor is a real containment check
        # against somewhere the caller did not name, so a mangled manifest or
        # an --analysis-dir pointing somewhere unrelated is still caught. For
        # branch 1 the "ancestor" IS the configured path, so this clause is a
        # formality there and the protection comes entirely from the other
        # clauses: the root, home and repo-root refusals, the index-like-name
        # requirement, and the positive-evidence check below. That is the
        # price of the guard agreeing with the resolver, and it is the right
        # price -- a guard that refuses paths the resolver itself hands it is
        # a bug, not safety.
        allowed_ancestors = [(self.repo_root / "legacylift-docs").resolve()]
        analysis_dir = resolve_analysis_dir(self.repo_root, self.manifest)
        if analysis_dir is not None:
            allowed_ancestors.append(analysis_dir.resolve())

        # Mirrors `resolve_index_dir`'s `explicit_analysis_dir`: an analysis
        # directory found by CONVENTION does not suppress branch 2, only one
        # named outright does.
        analysis_dir_is_explicit = self.manifest.index.analysis_dir is not None

        configured_index_dir = Path(self.manifest.index.index_dir)
        default_index_dir = IndexConfig.model_fields["index_dir"].default
        if configured_index_dir.is_absolute():
            allowed_ancestors.append(configured_index_dir.resolve())
        elif not is_default_setting(
            self.manifest.index.index_dir, default_index_dir
        ) and analysis_dir_is_explicit is False:
            # Branch 2 is admitted on exactly the condition `resolve_index_dir`
            # admits it: an EXPLICIT analysis_dir suppresses it there, so
            # admitting it here unconditionally made the guard WIDER than the
            # resolver -- accepting, for deletion, a directory the resolver can
            # never hand back. That is the same class of mismatch CR-06 fixed
            # in the other direction, and the parity claim above is only true
            # with this condition present.
            allowed_ancestors.append(
                (self.repo_root / configured_index_dir).resolve()
            )

        if not any(
            _is_within(resolved, ancestor) for ancestor in allowed_ancestors
        ):
            expected = " or ".join(str(a) for a in allowed_ancestors)
            raise ValueError(
                f"Refusing to reset path outside the known output locations: "
                f"{resolved}. Expected a path under {expected}. "
                f"Repo root is {self.repo_root}. Check --repo-root, "
                f"--analysis-dir and the manifest's index.index_dir / "
                f"index.analysis_dir settings."
            )

        # Require positive evidence that this really is an index directory.
        # A path-prefix rule only makes a typo improbable; this makes it safe,
        # and it holds under any future layout. An index directory either holds
        # an index (index.sqlite / chroma/) or does not exist yet / is empty,
        # which is the legitimate first-run case.
        #
        # CR-05: "empty" here means "holds nothing but this indexer's own
        # artifacts", not "holds no directory entries at all". --reset deletes
        # index.sqlite (+ -wal/-shm) and chroma/, but run() also writes
        # manifest.snapshot.json and index.log into the same directory and
        # nothing ever deletes those. So every state in which the database and
        # Chroma are gone while those two remain -- Ctrl-C during the rmtree
        # of a multi-gigabyte chroma/, or the common habit of hand-deleting
        # the database to force a rebuild -- used to hit the refusal below,
        # making --reset unrecoverable by the one flag whose job is recovery.
        # Worse, the message blamed --analysis-dir/index_dir and offered "or
        # to be empty" as the escape: a state --reset itself can never
        # produce, since it never removes those two files.
        #
        # Honour the manifest's configured artifact names as well as the
        # packaged defaults, so a manifest that renames sqlite_file or
        # chroma_dir does not get its real index dir refused.
        sqlite_names = {"index.sqlite", self.manifest.index.sqlite_file}
        chroma_names = {"chroma", self.manifest.index.chroma_dir}
        known_artifacts = set(sqlite_names) | set(chroma_names) | {
            "manifest.snapshot.json",
            "index.log",
        }
        for name in list(sqlite_names):
            known_artifacts.update({name + "-wal", name + "-shm"})

        if resolved.is_dir():
            foreign = sorted(
                entry.name
                for entry in resolved.iterdir()
                if entry.name not in known_artifacts
            )
            has_sqlite = any((resolved / n).exists() for n in sqlite_names)
            has_chroma = any((resolved / n).is_dir() for n in chroma_names)
            if foreign and not (has_sqlite or has_chroma):
                listed = ", ".join(foreign[:5])
                more = "" if len(foreign) <= 5 else f" (+{len(foreign) - 5} more)"
                raise ValueError(
                    f"Refusing to reset non-empty path with no index in it: "
                    f"{resolved}. Expected it to contain "
                    f"{'/'.join(sorted(sqlite_names))} or a "
                    f"{'/'.join(sorted(chroma_names))}/ subdirectory, or to "
                    f"hold nothing but this indexer's own artifacts. It "
                    f"holds: {listed}{more}. This usually means an "
                    f"--analysis-dir or index_dir setting points at the wrong "
                    f"directory."
                )

    # ------------------------------------------------------------------
    # Manifest digest
    # ------------------------------------------------------------------
    def _manifest_sha256(self) -> str:
        canonical = json.dumps(
            self.manifest.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------
    def run(
        self,
        reset: bool = False,
        embedding_provider_override: str | None = None,
    ) -> IndexStats:
        # 1. Resolve index dir
        index_dir = resolve_index_dir(self.repo_root, self.manifest)
        # Milestone 0's printed-paths requirement. `index` is the command that
        # most needs it: it is what writes hundreds of MB, so a mis-detected
        # analysis directory here is the expensive failure the banner exists
        # to make visible. Routed to stderr by print_resolved_path.
        print_resolved_path("index directory", index_dir)

        # 3. Reset if requested
        do_reset = reset or self.manifest.index.reset_before_index
        if do_reset:
            self._validate_reset_path(index_dir)
            sqlite_path = index_dir / self.manifest.index.sqlite_file
            chroma_path = index_dir / self.manifest.index.chroma_dir
            if sqlite_path.exists():
                sqlite_path.unlink()
            # Also remove WAL/SHM siblings if present
            for suffix in ("-wal", "-shm"):
                side = sqlite_path.with_name(sqlite_path.name + suffix)
                if side.exists():
                    try:
                        side.unlink()
                    except OSError:
                        pass
            if chroma_path.exists():
                # Drop Chroma's process-global System cache BEFORE removing the
                # directory. `PersistentClient` is cached by path, so without
                # this a client opened earlier in the same process survives the
                # rmtree holding a connection to the old, now-unlinked database,
                # and the next query fails with SQLite 1032
                # (SQLITE_READONLY_DBMOVED) reported as "attempt to write a
                # readonly database". `ChromaVectorStore.close` clears it too;
                # this covers the path where a store was never closed, which is
                # the destructive operation's job to survive rather than assume.
                try:
                    from chromadb.api.shared_system_client import (
                        SharedSystemClient,
                    )

                    SharedSystemClient.clear_system_cache()
                except Exception:
                    pass
                shutil.rmtree(chroma_path, ignore_errors=True)

        # 2. Create index dir
        index_dir.mkdir(parents=True, exist_ok=True)

        # 4. Snapshot manifest
        snapshot_path = index_dir / "manifest.snapshot.json"
        with snapshot_path.open("w", encoding="utf-8") as f:
            json.dump(
                self.manifest.model_dump(mode="json"),
                f,
                indent=2,
                ensure_ascii=False,
            )
            f.write("\n")

        # Open log file. Write-through (append + flush per line) so a run
        # killed mid-phase — e.g. a long Qwen embedding pass that exceeds the
        # harness wall-clock cap — still leaves a complete trail on disk.
        # Previously log lines were buffered in memory and flushed only at
        # end-of-run, so interrupted runs produced an empty index.log, which
        # is exactly when the log is most needed for progress assessment.
        log_path = index_dir / "index.log"
        try:
            _log_file = log_path.open("a", encoding="utf-8")
        except OSError:
            _log_file = None

        def _log(msg: str) -> None:
            if _log_file is None:
                return
            try:
                _log_file.write(msg + "\n")
                _log_file.flush()
            except OSError:
                pass

        _log(f"=== indexing started at {datetime.now(timezone.utc).isoformat()} ===")
        _log(f"repo_root={self.repo_root}")
        _log(f"index_dir={index_dir}")

        # 5. Open SQLite, run migrations
        sqlite_path = index_dir / self.manifest.index.sqlite_file
        store = SQLiteStore(sqlite_path)
        store.migrate()

        # Open the durable knowledge store (Milestone 1 of
        # domain-enhancements-plan.md). Construction alone creates the
        # knowledge/ directory and migrates knowledge.sqlite; unlike
        # index.sqlite, this file lives outside index_dir and is never
        # touched by --reset. Nothing is written to it yet — domain writes
        # arrive in Milestones 4-5.
        knowledge_dir = resolve_knowledge_dir(self.repo_root, self.manifest)
        print_resolved_path("knowledge directory", knowledge_dir)
        knowledge_store = KnowledgeStore(knowledge_dir / "knowledge.sqlite")

        # 6. Discover source files
        _log(f"{datetime.now(timezone.utc).isoformat()} [discovery] start")
        files = discover_source_files(self.repo_root, self.manifest)
        _log(f"Discovered {len(files)} source files")
        print(f"Discovered {len(files)} source files")
        _log(f"{datetime.now(timezone.utc).isoformat()} [discovery] end")

        # Say so when this run is about to store -- and, on a hosted embedder,
        # transmit -- credential-shaped values. A NOTICE, not a gate: nothing is
        # excluded or redacted here, because file-level exclusion is the wrong
        # default and the chunk-level gate is still being designed
        # (`docs/exec-plans/pending/indexer-credential-gate.md`). Placed after
        # discovery so it reports on exactly the set that is about to be
        # indexed, and before any of it is stored, so a reader can Ctrl-C.
        credential_notice = scan_for_credentials(
            files, provider=self.manifest.embedding.provider
        )
        if credential_notice:
            # Console gets key names; the log deliberately does not.
            print(render_credential_notice(credential_notice))
            for line in credential_log_lines(credential_notice):
                _log(line)

        # ----------------------------------------------------------------
        # Milestone 15: skip-on-unchanged fast path.
        # Compare each file's current sha256 against the existing repo_files
        # row. Files whose content hasn't changed are skipped end-to-end:
        # no extract, no chunk, no symbol/ref upsert, no Chroma upsert. Their
        # existing artifacts in SQLite remain valid and are reused for the
        # cross-file graph rebuild below.
        # On --reset runs, this map is empty (DB was wiped) so every file is
        # processed from scratch.
        # ----------------------------------------------------------------
        existing_shas = store.get_existing_file_shas()
        current_paths = {f.relative_path for f in files}

        # Detect deleted files: present in repo_files but no longer on disk.
        deleted_paths = [
            p for p in existing_shas.keys() if p not in current_paths
        ]
        deleted_chunk_ids: list[str] = []
        for p in deleted_paths:
            chunk_ids = store.delete_file_artifacts(p)
            deleted_chunk_ids.extend(chunk_ids)
        if deleted_paths:
            _log(
                f"Removed {len(deleted_paths)} deleted files "
                f"({len(deleted_chunk_ids)} orphan chunks dropped from SQLite)"
            )
            print(
                f"Removed {len(deleted_paths)} deleted files "
                f"({len(deleted_chunk_ids)} orphan chunks dropped from SQLite)"
            )

        # Partition discovery into changed vs unchanged.
        changed_files: list = []
        unchanged_paths: list[str] = []
        for f in files:
            existing = existing_shas.get(f.relative_path)
            if existing is not None and existing[1] == f.sha256:
                unchanged_paths.append(f.relative_path)
            else:
                changed_files.append(f)

        # Snapshot each changed file's existing chunk ids BEFORE anything can
        # delete them. This MUST happen before `upsert_files(changed_files)`
        # below: that call uses INSERT OR REPLACE keyed on the UNIQUE
        # relative_path, which drops the file's old repo_files row and — via
        # ON DELETE CASCADE — its old `chunks` rows. Reading the snapshot after
        # that cascade returns nothing, so the file's prior chunk ids are lost
        # and their (now stale) Chroma vectors are never deleted → orphans that
        # only `--reset` could clear. Capturing here preserves the old ids so
        # `truly_stale_chunk_ids` (computed post-extraction) can drive the
        # Chroma delete-by-id.
        stale_chunk_ids: list[str] = []
        for cf in changed_files:
            conn = store._connect()
            rows = conn.execute(
                "SELECT id FROM chunks WHERE relative_path = ?",
                (cf.relative_path,),
            ).fetchall()
            stale_chunk_ids.extend(r["id"] for r in rows)

        # Persist files first so chunk/symbol/ref upserts can resolve file_id.
        # CRITICAL: only upsert changed files. The repo_files table uses
        # `INSERT OR REPLACE` keyed on relative_path (UNIQUE), and the
        # chunks/symbols/symbol_refs tables have `ON DELETE CASCADE` from
        # repo_files. Re-upserting an unchanged file would replace the row,
        # cascade-delete its chunks/symbols/refs, and defeat the entire
        # skip-on-unchanged optimization. We only re-upsert changed files
        # (whose artifacts we explicitly rebuild) and unchanged files keep
        # their existing repo_files row — and therefore their existing
        # chunks/symbols/refs — intact.
        store.upsert_files(changed_files)

        # Load extractor profiles. The path + manifest.chunking are the
        # picklable inputs each worker process needs to rebuild its own
        # SymbolExtractor + CodeChunker (Milestone 19).
        profiles_path = (
            Path(__file__).resolve().parent / "profiles" / "extractors.json"
        )
        profiles = load_profiles(profiles_path)

        all_chunks: list = []  # list[CodeChunk] — chunks produced this run
        # Tuples used only for graph rebuild over the union (changed +
        # unchanged) of refs.
        all_refs_by_file: list[tuple] = []
        files_with_zero_chunks = 0
        symbol_count_processed = 0
        ref_count_processed = 0
        fact_count_processed = 0
        files_processed = 0

        # `stale_chunk_ids` (the changed files' prior chunk ids) was
        # snapshotted above, before `upsert_files` cascade-cleared the rows.
        # After extraction we diff it against the freshly-written ids to find
        # the truly-stale ones and delete their vectors from Chroma.
        _log(f"{datetime.now(timezone.utc).isoformat()} [extract+chunk] start")
        _log(
            f"skip-on-unchanged: {len(unchanged_paths)} unchanged, "
            f"{len(changed_files)} changed, "
            f"{len(deleted_paths)} deleted"
        )
        print(
            f"skip-on-unchanged: {len(unchanged_paths)} unchanged, "
            f"{len(changed_files)} changed, "
            f"{len(deleted_paths)} deleted"
        )

        new_chunk_ids_by_file: dict[str, set[str]] = {}

        # --------------------------------------------------------------
        # Milestone 19 (C1): run the CPU-bound read → extract → chunk work
        # in a process pool. The main process stays the sole SQLite writer
        # (C2): it persists results in a deterministic order (sorted by
        # relative_path, not pool-arrival order) and commits in batches of
        # `commit_batch_files` instead of once per upsert.
        # --------------------------------------------------------------
        configured_workers = self.manifest.index.extract_workers
        if configured_workers <= 0:
            resolved_workers = os.cpu_count() or 1
        else:
            resolved_workers = configured_workers
        # Never spin up more workers than there are files to process.
        resolved_workers = max(1, min(resolved_workers, len(changed_files) or 1))

        # Sort the inputs up front. ProcessPoolExecutor.map preserves input
        # order, so consuming its results in iteration order already yields a
        # deterministic, relative_path-sorted write order — identical to the
        # serial path — while letting the writer drain results as workers
        # produce them (extraction and SQLite writing overlap, rather than
        # extracting everything into a list first and writing afterward).
        changed_files = sorted(changed_files, key=lambda f: f.relative_path)

        commit_batch = max(1, self.manifest.index.commit_batch_files)
        pending_in_batch = 0

        # `pool` is held open across the writer loop so results stream in;
        # the ExitStack closes it (and the serial path needs no cleanup).
        with ExitStack() as _extract_stack:
            if not changed_files:
                results_iter: "object" = iter(())
            elif resolved_workers == 1:
                # Forced-serial, in-process fallback. Also the equivalence
                # oracle the M19 tests compare the parallel path against.
                extractor = SymbolExtractor(profiles)
                chunker = CodeChunker(self.manifest.chunking)
                results_iter = (
                    _extract_with(sf, extractor, chunker) for sf in changed_files
                )
            else:
                _log(
                    f"[extract+chunk] using {resolved_workers} worker processes"
                )
                print(
                    f"[extract+chunk] using {resolved_workers} worker processes"
                )
                chunking_json = self.manifest.chunking.model_dump_json()
                pool = _extract_stack.enter_context(
                    ProcessPoolExecutor(
                        max_workers=resolved_workers,
                        initializer=_init_worker,
                        initargs=(str(profiles_path), chunking_json),
                    )
                )
                # chunksize batches task dispatch to amortize IPC; map
                # preserves input (sorted) order, so writes stay deterministic.
                results_iter = pool.map(
                    extract_one, changed_files, chunksize=8
                )

            for res in results_iter:
                source_file = res.source_file

                # Read failure: leave the file's pre-existing artifacts intact
                # (matches the original serial loop, which `continue`d before
                # any delete when the read raised).
                if res.read_error is not None:
                    _log(
                        f"READ_ERROR {source_file.relative_path}: "
                        f"{res.read_error}"
                    )
                    continue

                # The read succeeded, so clear this changed file's stale
                # chunks/FTS/symbols/refs before writing the fresh set. This is
                # part of the batched transaction (no commit here).
                store.clear_reindex_artifacts(source_file.relative_path)
                pending_in_batch += 1

                if res.extract_error is not None:
                    # Cleared but nothing re-added — mirrors the original loop's
                    # extract-error `continue` (after the per-file delete).
                    _log(
                        f"EXTRACT_ERROR {source_file.relative_path}: "
                        f"{res.extract_error}"
                    )
                    if pending_in_batch >= commit_batch:
                        store.commit()
                        pending_in_batch = 0
                    continue

                for note in res.parse_notes:
                    _log(f"PARSE_NOTE {source_file.relative_path}: {note}")
                if res.chunk_error is not None:
                    _log(
                        f"CHUNK_ERROR {source_file.relative_path}: "
                        f"{res.chunk_error}"
                    )

                chunks = res.chunks
                if not chunks:
                    files_with_zero_chunks += 1

                # Persist into the open batched transaction (commit=False).
                # Facts are upserted AFTER upsert_symbols (same iteration) so
                # the subject_symbol_id FK target already exists, and AFTER
                # upsert_files (indexer.py:302) so the REPLACE cascade has
                # already purged the file's old facts. upsert_facts returns any
                # facts dropped by the crash-guard (dangling subject FK) so we
                # can log them without aborting the run.
                store.upsert_symbols(source_file, res.symbols, commit=False)
                store.upsert_refs(source_file, res.refs, commit=False)
                orphaned_facts = store.upsert_facts(
                    source_file, res.facts, commit=False
                )
                for of in orphaned_facts:
                    _log(
                        f"FACT_ORPHAN {source_file.relative_path}: "
                        f"{of.predicate} subject={of.subject_symbol_id}"
                    )
                store.upsert_chunks(chunks, commit=False)

                all_chunks.extend(chunks)
                all_refs_by_file.append((source_file, res.symbols, res.refs))
                new_chunk_ids_by_file[source_file.relative_path] = {
                    c.id for c in chunks
                }
                symbol_count_processed += len(res.symbols)
                ref_count_processed += len(res.refs)
                fact_count_processed += len(res.facts) - len(orphaned_facts)
                files_processed += 1

                if pending_in_batch >= commit_batch:
                    store.commit()
                    pending_in_batch = 0

            # Flush the final partial batch.
            if pending_in_batch:
                store.commit()

        # Compute chunk_ids that existed before but were not regenerated
        # (i.e. truly stale ids that need deletion from Chroma).
        truly_stale_chunk_ids: list[str] = []
        new_ids_set: set[str] = set()
        for ids in new_chunk_ids_by_file.values():
            new_ids_set.update(ids)
        for old_id in stale_chunk_ids:
            if old_id not in new_ids_set:
                truly_stale_chunk_ids.append(old_id)

        # Combine with deleted-file chunks.
        all_stale_chunk_ids = truly_stale_chunk_ids + deleted_chunk_ids
        # Drop stale rows from vectors_present so they get re-upserted if
        # they ever come back.
        store.delete_vectors_present(all_stale_chunk_ids)

        _log(f"Processed {files_processed} changed files")
        _log(f"Skipped {len(unchanged_paths)} unchanged files")
        _log(f"Created {len(all_chunks)} chunks (this run)")
        _log(f"Extracted {symbol_count_processed} symbols (this run)")
        _log(f"Extracted {ref_count_processed} references (this run)")
        _log(f"Extracted {fact_count_processed} facts (this run)")
        print(f"Processed {files_processed} changed files")
        print(f"Skipped {len(unchanged_paths)} unchanged files")
        _log(f"{datetime.now(timezone.utc).isoformat()} [extract+chunk] end")

        # 12. Build cross-file graph edges over the UNION of changed-file
        # refs and unchanged-file refs. A previously-unresolved edge in an
        # unchanged file may now resolve to a symbol in a changed file, or
        # vice versa, so we cannot simply leave unchanged-file edges alone.
        _log(f"{datetime.now(timezone.utc).isoformat()} [graph-edge-build] start")

        # Reload symbols and refs for unchanged files from SQLite. For
        # changed files, use the in-memory results we just extracted.
        unchanged_symbols_by_path = store.get_symbols_for_files(unchanged_paths)
        unchanged_refs_by_path = store.get_refs_for_files(unchanged_paths)

        # Build the union list (source_file, symbols, refs) for graph build.
        union_inputs: list[tuple] = list(all_refs_by_file)
        for path in unchanged_paths:
            sf = store.get_source_file_for_path(path, self.repo_root)
            if sf is None:
                continue
            union_inputs.append(
                (
                    sf,
                    unchanged_symbols_by_path.get(path, []),
                    unchanged_refs_by_path.get(path, []),
                )
            )

        # Build name index keyed by both plain name and qualified name from
        # the union of all symbols (changed + unchanged).
        all_symbols_by_name: dict[str, list[Symbol]] = {}
        seen_symbol_ids: set[str] = set()
        for _sf, syms, _refs in union_inputs:
            for sym in syms:
                if sym.id in seen_symbol_ids:
                    continue
                seen_symbol_ids.add(sym.id)
                all_symbols_by_name.setdefault(sym.name, []).append(sym)
                if sym.qualified_name and sym.qualified_name != sym.name:
                    all_symbols_by_name.setdefault(
                        sym.qualified_name, []
                    ).append(sym)

        # Drop existing edges for ALL files we're about to rebuild edges
        # for (changed + unchanged). This is safe because we then write a
        # complete, fresh edge set across the same path universe. Files
        # outside this universe (none, since we cover all current files)
        # are untouched.
        rebuild_paths = [sf.relative_path for sf, _, _ in union_inputs]
        store.delete_graph_edges_for_files(rebuild_paths)

        graph_builder = GraphBuilder()
        all_edges: list[GraphEdge] = []
        for source_file, syms, refs in union_inputs:
            try:
                edges = graph_builder.build_edges(
                    source_file, syms, refs, all_symbols_by_name
                )
            except Exception as exc:
                _log(f"GRAPH_ERROR {source_file.relative_path}: {exc!r}")
                continue
            all_edges.extend(edges)

        # Dedupe by id (regex variants can produce duplicates)
        seen_edge_ids: set[str] = set()
        deduped_edges: list[GraphEdge] = []
        for e in all_edges:
            if e.id in seen_edge_ids:
                continue
            seen_edge_ids.add(e.id)
            deduped_edges.append(e)
        all_edges = deduped_edges

        store.upsert_edges(all_edges)
        _log(f"Created {len(all_edges)} graph edges (full union)")
        print(f"Created {len(all_edges)} graph edges (full union)")
        _log(f"{datetime.now(timezone.utc).isoformat()} [graph-edge-build] end")

        # Aggregate counts across the full index (changed + unchanged) for
        # IndexStats and metadata reporting. The store knows the truth.
        full_stats = store.stats()
        symbol_count_total = full_stats.symbol_count
        ref_count_total = full_stats.ref_count
        fact_count_total = full_stats.fact_count
        chunk_count_total = full_stats.chunk_count
        files_indexed_total = full_stats.file_count

        # ----------------------------------------------------------------
        # Domain 7-Auto self-resolution (Milestone 5 of
        # domain-enhancements-plan.md). If the durable knowledge DB has NO
        # domains yet (never tagged), do nothing domain-related. Otherwise:
        #  - reap file_domains rows for undiscovered paths (issue #55 — keyed
        #    on the discovered set, so --reset ghost rows are caught too);
        #  - emit the standing manual-override notice (total manual rows);
        #  - build the authoritative {chunk.id: domain} map for this batch,
        #    mirroring existing rows verbatim and writing fresh glob rows for
        #    new glob-matching files (issue #44). The map is stamped into
        #    Chroma inline via _embed_and_upsert below.
        # ----------------------------------------------------------------
        domain_by_chunk: dict[str, str] | None = None
        if self._knowledge_has_domains(knowledge_store):
            self._reap_file_domains_to_discovered(
                knowledge_store, current_paths, _log
            )
            self._emit_manual_notice(knowledge_store, _log)
            domain_by_chunk = self._build_domain_by_chunk(
                knowledge_store,
                all_chunks,
                write_new_glob_rows=True,
                log=_log,
            )

        # 13. Embed chunks and upsert to Chroma
        embedder = create_embedder(
            self.manifest.embedding,
            provider_override=embedding_provider_override,
        )

        embedder_name_meta = embedder.name
        if embedder.name == "qwen3":
            embedder_name_meta = f"qwen3:{self.manifest.embedding.model}"

        # 14a. Persist metadata BEFORE the Chroma upsert phase. This way an
        # interrupted index leaves SQLite reporting freshness=fresh against
        # the discovered source set; validate can then report
        # vectors_upserted < chunk_count rather than freshness=missing.
        # source_set_sha256: SHA-256 of sorted "<rel>\t<sha>\n" for all files.
        _log(f"{datetime.now(timezone.utc).isoformat()} [metadata-write] start")
        joined = "".join(
            sorted(f"{f.relative_path}\t{f.sha256}\n" for f in files)
        )
        source_set_sha = hashlib.sha256(joined.encode("utf-8")).hexdigest()

        store.set_metadata("schema_version", SCHEMA_VERSION)
        store.set_metadata(
            "indexed_at", datetime.now(timezone.utc).isoformat()
        )
        store.set_metadata("repo_root", str(self.repo_root))
        store.set_metadata("manifest_sha256", self._manifest_sha256())
        store.set_metadata("embedder_name", embedder_name_meta)
        store.set_metadata("embedding_dimension", str(embedder.dimension))
        store.set_metadata("chunk_count", str(chunk_count_total))
        store.set_metadata("symbol_count", str(symbol_count_total))
        store.set_metadata("graph_edge_count", str(len(all_edges)))
        store.set_metadata("source_set_sha256", source_set_sha)
        # Seed vectors_upserted from the existing vectors_present cache so
        # idempotent reruns don't reset the high-water mark to 0.
        existing_present = store.get_present_vector_count()
        store.set_metadata("vectors_upserted", str(existing_present))
        _log(f"{datetime.now(timezone.utc).isoformat()} [metadata-write] end")

        # Build base collection metadata for ChromaVectorStore
        base_meta = {
            "schema_version": SCHEMA_VERSION,
            "repo_root": str(self.repo_root),
        }
        vector_store = ChromaVectorStore(
            base_dir=index_dir,
            collection_name=self.manifest.index.collection_name,
            embedder=embedder,
            metadata=base_meta,
        )

        # Validate dimension before doing anything else.
        try:
            vector_store.validate_dimension()
        except ValueError as exc:
            # Surface the spec-mandated error message verbatim.
            store.close()
            vector_store.close()
            knowledge_store.close()
            raise ValueError(str(exc)) from exc

        vectors_upserted = 0
        vectors_skipped = 0
        _log(f"{datetime.now(timezone.utc).isoformat()} [chroma-upsert] start")

        # Drop stale vectors (deleted files + chunks that no longer exist
        # for changed files). Best-effort; Chroma's delete is idempotent.
        if all_stale_chunk_ids:
            try:
                vector_store.delete_chunks(all_stale_chunk_ids)
                _log(
                    f"Deleted {len(all_stale_chunk_ids)} stale vectors "
                    f"from Chroma"
                )
            except Exception as exc:
                _log(f"CHROMA_DELETE_WARN: {exc!r}")

        if all_chunks:
            # Filter out chunks already represented in Chroma (per the
            # vectors_present cache) — this is the Milestone 15 skip-on-
            # unchanged path for the vector store.
            chunk_ids_this_run = [c.id for c in all_chunks]
            present_map = store.get_present_vector_chunk_ids(chunk_ids_this_run)
            todo_chunks = []
            for c in all_chunks:
                cached = present_map.get(c.id)
                if cached is not None and cached == c.text_sha256:
                    vectors_skipped += 1
                    continue
                todo_chunks.append(c)

            if vectors_skipped:
                _log(
                    f"Skipped {vectors_skipped} vectors already present in Chroma"
                )
                print(
                    f"Skipped {vectors_skipped} vectors already present in Chroma"
                )

            # Shared embed phase applies spike #1 (low-value filter) and
            # spike #2 (text dedup) and emits throttled progress.
            vectors_upserted, _filtered = self._embed_and_upsert(
                todo_chunks,
                embedder,
                vector_store,
                store,
                _log,
                phase_label="[chroma-upsert]",
                domain_by_chunk=domain_by_chunk,
            )
            _log(
                f"Upserted {vectors_upserted} new vectors into Chroma collection "
                f"{self.manifest.index.collection_name}"
            )
            print(
                f"Upserted {vectors_upserted} new vectors into Chroma collection "
                f"{self.manifest.index.collection_name}"
            )

        # Final reconcile: vectors_upserted := count(vectors_present).
        final_present = store.get_present_vector_count()
        store.set_metadata("vectors_upserted", str(final_present))

        _log(f"{datetime.now(timezone.utc).isoformat()} [chroma-upsert] end")
        _log(f"Wrote index to {index_dir}")
        print(f"Wrote index to {index_dir}")
        _log(f"{datetime.now(timezone.utc).isoformat()} [indexing] end")

        # Close Chroma cleanly on Windows.
        vector_store.close()
        store.close()
        knowledge_store.close()

        # Log is write-through (flushed per line above); just close the handle.
        if _log_file is not None:
            try:
                _log_file.close()
            except OSError:
                pass

        # 15. 25% zero-chunks failure threshold — only meaningful when we
        # actually processed files this run. An idempotent rerun that
        # processed zero files is fine (and the threshold would div-zero).
        if changed_files and (
            files_with_zero_chunks / len(changed_files)
        ) > 0.25:
            raise RuntimeError(
                f"Indexing produced zero chunks for "
                f"{files_with_zero_chunks}/{len(changed_files)} processed files "
                f"({files_with_zero_chunks / len(changed_files):.1%}); "
                f"this exceeds the 25% threshold. "
                f"See {log_path} for parser errors."
            )

        return IndexStats(
            files_indexed=files_indexed_total,
            chunk_count=chunk_count_total,
            symbol_count=symbol_count_total,
            ref_count=ref_count_total,
            graph_edge_count=len(all_edges),
            fact_count=fact_count_total,
            embedder_name=embedder_name_meta,
            embedding_dimension=embedder.dimension,
            index_dir=str(index_dir),
            files_processed=files_processed,
            files_skipped=len(unchanged_paths),
            files_deleted=len(deleted_paths),
            vectors_upserted=vectors_upserted,
            vectors_skipped=vectors_skipped,
        )

    # ------------------------------------------------------------------
    # Domain 7-Auto self-resolution (Milestone 5 of
    # domain-enhancements-plan.md)
    # ------------------------------------------------------------------
    @staticmethod
    def _knowledge_has_domains(knowledge_store: KnowledgeStore) -> bool:
        """True iff the knowledge DB has at least one authored `domains` row.

        When false, the indexer does nothing domain-related (no globs to
        resolve against, no rows to reap) — files stay untagged until the
        first `tag-domains` run.
        """
        conn = knowledge_store._connect()
        return (
            conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0] > 0
        )

    @staticmethod
    def _reap_file_domains_to_discovered(
        knowledge_store: KnowledgeStore,
        current_paths: set[str],
        log,
    ) -> int:
        """Reap `file_domains` rows whose path is no longer discovered (#55).

        Keyed on the DISCOVERED set — a superset of the incremental
        `deleted_paths` reap — so it also catches `--reset`-window ghost rows
        (`deleted_paths` is empty on `--reset` because `existing_shas` is
        wiped) and any externally-inserted stray row. Source-agnostic:
        deletes `manual` rows too, since a deleted file has no live decision
        to protect (same rule as the `tag-domains` reap, issues #38/#42).
        The caller guards this to run only when the knowledge DB has domains.
        """
        conn = knowledge_store._connect()
        existing = [
            row[0]
            for row in conn.execute(
                "SELECT relative_path FROM file_domains"
            ).fetchall()
        ]
        stale = [p for p in existing if p not in current_paths]
        for i in range(0, len(stale), 500):
            batch = stale[i : i + 500]
            placeholders = ",".join("?" for _ in batch)
            conn.execute(
                f"DELETE FROM file_domains WHERE relative_path IN ({placeholders})",
                batch,
            )
        if stale:
            conn.commit()
            log(
                f"Reaped {len(stale)} file_domains row(s) for undiscovered "
                f"paths (source-agnostic, includes manual)"
            )
        return len(stale)

    @staticmethod
    def _emit_manual_notice(knowledge_store: KnowledgeStore, log) -> int:
        """Emit the standing manual-override notice on any reindex.

        Counts the TOTAL `source='manual'` rows in the DB (not just the
        changed batch), so awareness that hand-set overrides exist is standing
        even on an incremental run that touches none of them.
        """
        conn = knowledge_store._connect()
        n = conn.execute(
            "SELECT COUNT(*) FROM file_domains WHERE source='manual'"
        ).fetchone()[0]
        if n:
            msg = (
                f"preserved {n} manual domain override(s) — not overwritten "
                f"by glob resolution"
            )
            log(msg)
            print(msg)
        return n

    def _build_domain_by_chunk(
        self,
        knowledge_store: KnowledgeStore,
        chunks: list[CodeChunk],
        *,
        write_new_glob_rows: bool,
        log,
    ) -> dict[str, str]:
        """Compute the authoritative `{chunk.id: domain}` map (issue #44).

        Uniform per-file rule, applied to every file appearing in ``chunks``:
        - if a `file_domains` row already exists, MIRROR its `domain` verbatim
          (`manual` / glob-matched / the reserved `unassigned` alike — never
          recomputed, issue #53); this subsumes manual-wins on the vector side;
        - else, when ``write_new_glob_rows`` (the `run()` path), glob-resolve
          against the stored, display_order-sorted domains: if it matches a
          domain, persist a `source='glob'` row and use that domain; if it
          matches nothing, OMIT the key (the file stays untagged — no row —
          driving the Milestone 7 freshness signal; the indexer never
          manufactures `unassigned` rows);
        - else (``backfill_vectors()`` — a resume path with no new files), a
          file with no row is left unmapped (mirror-only).

        Keyed by `chunk.id`, so every fanned dedup member is covered.
        """
        from .domain_tagger import RESERVED_UNASSIGNED, resolve_file_domains

        domains = knowledge_store.list_domains()  # display_order-sorted (#14)
        exclude_globs = knowledge_store.list_exclusions()
        assess_run_id = domains[0].assess_run_id if domains else None

        conn = knowledge_store._connect()
        existing_rows = {
            row["relative_path"]: row["domain"]
            for row in conn.execute(
                "SELECT relative_path, domain FROM file_domains"
            ).fetchall()
        }

        paths = sorted({c.relative_path for c in chunks})
        path_domain: dict[str, str] = {}
        to_resolve: list[str] = []
        for p in paths:
            existing = existing_rows.get(p)
            if existing is not None:
                path_domain[p] = existing  # mirror verbatim
            else:
                to_resolve.append(p)

        if to_resolve and write_new_glob_rows:
            resolved = resolve_file_domains(to_resolve, domains, exclude_globs)
            for p in to_resolve:
                domain_id, conf = resolved[p]
                if domain_id != RESERVED_UNASSIGNED:
                    # New file matching a domain glob OR an exclusion:
                    # persist a `source='glob'` row (domain = the matched
                    # domain_id, or the reserved 'excluded' value) and use it.
                    # A known-excluded new file (e.g. a test) is thus NOT left
                    # untagged, so it does not flip the repo to `stale`.
                    knowledge_store.upsert_file_domain(
                        p, domain_id, "glob", assess_run_id, conf
                    )
                    path_domain[p] = domain_id
                # else (unassigned): leave untagged (no row, omit the Chroma
                # domain key) — the Milestone 7 freshness/staleness signal.

        domain_by_chunk: dict[str, str] = {}
        for c in chunks:
            d = path_domain.get(c.relative_path)
            if d is not None:
                domain_by_chunk[c.id] = d
        return domain_by_chunk

    # ------------------------------------------------------------------
    # Shared embed/upsert phase (spike #1 filter + spike #2 dedup)
    # ------------------------------------------------------------------
    def _embed_and_upsert(
        self,
        chunks: list[CodeChunk],
        embedder,
        vector_store: ChromaVectorStore,
        store: SQLiteStore,
        log,
        phase_label: str,
        domain_by_chunk: dict[str, str] | None = None,
    ) -> tuple[int, int]:
        """Embed and upsert ``chunks`` into Chroma, applying:

        - spike #1: skip dense vectors for sub-``embed_min_tokens`` chunks that
          carry no business logic (they stay in SQLite/FTS5 for lexical recall);
          such chunks are still marked present so coverage stays exact and
          backfill terminates.
        - spike #2: embed each distinct ``text_sha256`` once and fan the vector
          out to every chunk sharing that text.

        ``domain_by_chunk`` (Milestone 5 of ``domain-enhancements-plan.md``,
        issue #22) is the authoritative ``{chunk.id: domain}`` map, forwarded
        verbatim to ``ChromaVectorStore.upsert_chunks`` so every re-embedded
        chunk carries its file's capability domain. It is keyed by ``chunk.id``
        and covers every fanned member of the text-dedup fan-out below (correct
        by construction — domain is per-file and each member carries its own
        ``relative_path``), so both callers (``run()`` and
        ``backfill_vectors()``) stamp the same value onto every member.

        Returns ``(vectors_upserted, vectors_filtered)`` where
        ``vectors_upserted`` counts chunk ids written to Chroma this call and
        ``vectors_filtered`` counts low-value chunks skipped per spike #1.
        """
        if not chunks:
            return 0, 0

        embed_min_tokens = self.manifest.chunking.embed_min_tokens

        # Spike #1: partition into chunks that warrant a vector vs. low-value.
        to_embed, filtered = partition_for_embedding(chunks, embed_min_tokens)
        vectors_filtered = len(filtered)
        if vectors_filtered:
            # Mark filtered chunks present (resolved w.r.t. the vector store)
            # so they don't keep tripping the coverage warning or backfill.
            store.mark_vectors_present(
                [(c.id, c.text_sha256) for c in filtered]
            )
            log(
                f"Skipped dense vectors for {vectors_filtered} low-value "
                f"chunks (< embed_min_tokens={embed_min_tokens}, no business "
                f"logic); they remain searchable via FTS5"
            )
            print(
                f"Skipped dense vectors for {vectors_filtered} low-value chunks"
            )

        # Spike #2: collapse identical text so it is embedded once.
        representatives, members_by_sha = dedupe_by_text_sha(to_embed)
        dup_saved = len(to_embed) - len(representatives)
        if dup_saved:
            log(
                f"Deduplicated {dup_saved} chunks with identical text "
                f"({len(representatives)} distinct texts to embed)"
            )
            print(
                f"Deduplicated {dup_saved} duplicate-text chunks "
                f"({len(representatives)} distinct to embed)"
            )

        batch_size = max(1, self.manifest.embedding.batch_size)
        total_todo = len(representatives)
        total_batches = (total_todo + batch_size - 1) // batch_size
        running_total = store.get_present_vector_count()
        phase_start = time.monotonic()
        last_emit = phase_start
        progress_interval_s = 30.0
        vectors_upserted = 0

        log(
            f"Embedding {total_todo} distinct chunks in {total_batches} "
            f"batches of {batch_size}"
        )
        print(
            f"Embedding {total_todo} distinct chunks in {total_batches} "
            f"batches of {batch_size}"
        )

        for batch_num, i in enumerate(
            range(0, total_todo, batch_size), start=1
        ):
            reps = representatives[i:i + batch_size]
            texts = [c.text for c in reps]
            vectors = embedder.embed_documents(texts)

            # Fan each representative's vector out to every chunk sharing its
            # text, so every chunk still gets a vector in Chroma.
            fan_chunks: list[CodeChunk] = []
            fan_vectors: list[list[float]] = []
            for rep, vec in zip(reps, vectors):
                for member in members_by_sha[rep.text_sha256]:
                    fan_chunks.append(member)
                    fan_vectors.append(vec)

            vector_store.upsert_chunks(
                fan_chunks, fan_vectors, domain_by_chunk=domain_by_chunk
            )
            store.mark_vectors_present(
                [(c.id, c.text_sha256) for c in fan_chunks]
            )
            vectors_upserted += len(fan_chunks)
            running_total += len(fan_chunks)
            store.set_metadata("vectors_upserted", str(running_total))

            now = time.monotonic()
            is_last = batch_num == total_batches
            if is_last or (now - last_emit) >= progress_interval_s:
                elapsed = now - phase_start
                rate = vectors_upserted / elapsed if elapsed > 0 else 0.0
                # ETA is based on distinct texts remaining (the embed cost).
                reps_done = min(i + batch_size, total_todo)
                reps_remaining = total_todo - reps_done
                rep_rate = reps_done / elapsed if elapsed > 0 else 0.0
                eta_s = reps_remaining / rep_rate if rep_rate > 0 else 0.0
                pct = (reps_done / total_todo * 100) if total_todo else 100.0
                msg = (
                    f"{datetime.now(timezone.utc).isoformat()} "
                    f"{phase_label} progress "
                    f"batch {batch_num}/{total_batches} "
                    f"embedded {reps_done}/{total_todo} distinct "
                    f"({pct:.1f}%) "
                    f"upserted {vectors_upserted} chunks "
                    f"rate={rate:.1f} chunks/s "
                    f"eta={eta_s / 60:.1f}m"
                )
                log(msg)
                print(msg)
                last_emit = now

        return vectors_upserted, vectors_filtered

    # ------------------------------------------------------------------
    # Resumable vector backfill
    # ------------------------------------------------------------------
    def backfill_vectors(
        self,
        embedding_provider_override: str | None = None,
    ) -> BackfillStats:
        """Embed and upsert into Chroma only the chunks missing from the
        ``vectors_present`` cache, driving off the SQLite ``chunks`` table
        rather than an in-memory chunk list.

        This is the resumable completion path for an interrupted ``--reset``
        run: under the M15 skip-on-unchanged fast path, a plain rerun sees
        every file unchanged and feeds nothing to the embedder, so vectors
        can never be restored. ``backfill-vectors`` instead processes exactly
        the chunks that Chroma is missing, is safe to call repeatedly, and
        makes monotonic forward progress under a wall-clock cap. A final call
        drives ``vectors_upserted`` to ``chunk_count``.

        Requires an existing index (SQLite + Chroma + metadata). Does NOT
        rediscover, re-extract, re-chunk, or rebuild the graph.
        """
        index_dir = resolve_index_dir(self.repo_root, self.manifest)
        print_resolved_path("index directory", index_dir)
        sqlite_path = index_dir / self.manifest.index.sqlite_file
        chroma_path = index_dir / self.manifest.index.chroma_dir

        if not sqlite_path.exists() or not chroma_path.exists():
            raise FileNotFoundError(
                f"No index found at {index_dir}. "
                f"Run `legacylift-search index --repo-root {self.repo_root}` "
                f"first, then backfill-vectors to complete the vector phase."
            )

        # Open log file (write-through, append) — same convention as run().
        log_path = index_dir / "index.log"
        try:
            _log_file = log_path.open("a", encoding="utf-8")
        except OSError:
            _log_file = None

        def _log(msg: str) -> None:
            if _log_file is None:
                return
            try:
                _log_file.write(msg + "\n")
                _log_file.flush()
            except OSError:
                pass

        _log(
            f"=== backfill-vectors started at "
            f"{datetime.now(timezone.utc).isoformat()} ==="
        )
        _log(f"repo_root={self.repo_root}")
        _log(f"index_dir={index_dir}")

        store = SQLiteStore(sqlite_path)
        store.migrate()

        # Open the durable knowledge store for domain stamping parity with
        # run() (Milestone 5, issue #22). backfill-vectors is the resume path
        # for an interrupted --reset: on a cold reset every chunk is missing,
        # so a reset COMPLETED via backfill re-creates all vectors through the
        # shared _embed_and_upsert helper. Without opening the knowledge store
        # here and passing the domain map, the rebuilt Chroma vectors would
        # carry no `domain` metadata even though knowledge.sqlite still holds
        # the tags, silently breaking --domain vector search (Milestone 6).
        knowledge_dir = resolve_knowledge_dir(self.repo_root, self.manifest)
        print_resolved_path("knowledge directory", knowledge_dir)
        knowledge_store = KnowledgeStore(knowledge_dir / "knowledge.sqlite")

        # Resolve embedder. Prefer the embedder recorded in metadata so a
        # backfill uses the same provider the index was built with; an
        # explicit override still wins.
        embedder = create_embedder(
            self.manifest.embedding,
            provider_override=embedding_provider_override,
        )
        embedder_name_meta = embedder.name
        if embedder.name == "qwen3":
            embedder_name_meta = f"qwen3:{self.manifest.embedding.model}"

        full_stats = store.stats()
        chunk_count_total = full_stats.chunk_count

        # Open Chroma and validate dimension before doing any work.
        base_meta = {
            "schema_version": SCHEMA_VERSION,
            "repo_root": str(self.repo_root),
        }
        vector_store = ChromaVectorStore(
            base_dir=index_dir,
            collection_name=self.manifest.index.collection_name,
            embedder=embedder,
            metadata=base_meta,
        )
        try:
            vector_store.validate_dimension()
        except ValueError as exc:
            store.close()
            vector_store.close()
            knowledge_store.close()
            if _log_file is not None:
                _log(f"DIMENSION_MISMATCH: {exc}")
                _log_file.close()
            raise ValueError(str(exc)) from exc

        _log(
            f"{datetime.now(timezone.utc).isoformat()} [backfill] start"
        )

        todo_chunks = store.get_chunks_missing_vectors()
        chunks_missing = len(todo_chunks)
        _log(f"Found {chunks_missing} chunks missing vectors")
        print(f"Found {chunks_missing} chunks missing vectors")

        # Build the domain map for parity with run() (issue #22). backfill has
        # no "new" files — it only re-embeds chunks the surviving index already
        # knows — so this MIRRORS existing file_domains rows verbatim
        # (write_new_glob_rows=False, per issue #44/#53: mirrored, NOT
        # recomputed) rather than resolving fresh globs.
        domain_by_chunk: dict[str, str] | None = None
        if self._knowledge_has_domains(knowledge_store):
            self._emit_manual_notice(knowledge_store, _log)
            domain_by_chunk = self._build_domain_by_chunk(
                knowledge_store,
                todo_chunks,
                write_new_glob_rows=False,
                log=_log,
            )

        # Shared embed phase applies spike #1 (low-value filter) and spike #2
        # (text dedup). Filtered chunks are marked present, so a subsequent
        # backfill won't keep re-seeing them and this call still converges.
        vectors_backfilled, _filtered = self._embed_and_upsert(
            todo_chunks,
            embedder,
            vector_store,
            store,
            _log,
            phase_label="[backfill]",
            domain_by_chunk=domain_by_chunk,
        )

        # Final reconcile: vectors_upserted := count(vectors_present).
        final_present = store.get_present_vector_count()
        store.set_metadata("vectors_upserted", str(final_present))

        _log(
            f"Backfilled {vectors_backfilled} vectors "
            f"(coverage {final_present}/{chunk_count_total})"
        )
        print(
            f"Backfilled {vectors_backfilled} vectors "
            f"(coverage {final_present}/{chunk_count_total})"
        )
        _log(f"{datetime.now(timezone.utc).isoformat()} [backfill] end")

        vector_store.close()
        store.close()
        knowledge_store.close()
        if _log_file is not None:
            try:
                _log_file.close()
            except OSError:
                pass

        return BackfillStats(
            chunks_missing=chunks_missing,
            vectors_backfilled=vectors_backfilled,
            vectors_upserted_total=final_present,
            chunk_count=chunk_count_total,
            embedder_name=embedder_name_meta,
            embedding_dimension=embedder.dimension,
            index_dir=str(index_dir),
        )

    def backfill_hashes(self) -> HashBackfillStats:
        """Fill in `symbols.content_hash` for rows the migration left NULL.

        Milestone 1 Step 2. `INDEX_MIGRATIONS` version 2 adds `content_hash`
        and leaves it NULL, because the body text it hashes is not stored in
        `symbols` and, on an existing database, the file on disk may no
        longer be the file that produced those rows. This command is how the
        column actually gets populated.

        **It exists because the next `index` run will not do it.** The M15
        skip-on-unchanged fast path partitions discovered files by comparing
        each file's `sha256` against `repo_files.sha256` and re-extracts only
        the changed ones, so on any existing index the overwhelming majority
        of symbols are never revisited and their `content_hash` would stay
        NULL forever -- silently disabling the Step 1 drift-versus-clone
        matrix and the move auto-repair that depends on it, with no error
        anywhere to say so.

        The rule for each row, and the reason it is not merely defensive:

        * **The file's current on-disk `sha256` equals `repo_files.sha256`.**
          The bytes on disk are then *provably* the bytes that produced this
          row, so the body is read, hashed, and stored.
        * **It does not.** The row is **skipped and left NULL**. Hashing it
          would write a hash for source that never produced that symbol --
          the precise error for which a migration-time backfill was rejected.
          Nothing is lost: a drifted file is by definition a changed file, so
          the next real `index` run re-extracts it and writes the hash on the
          insert path.

        Modelled on `backfill_vectors`: resumable, processes only what is
        missing, safe to call repeatedly, and monotonic -- each run can only
        reduce `remaining_null`. Unlike `backfill_vectors` it needs no
        embedder and no Chroma, so it costs nothing but IO.

        Returns:
            `HashBackfillStats` with both counts.

        Raises:
            FileNotFoundError: If there is no `index.sqlite` to repair.
        """
        index_dir = resolve_index_dir(self.repo_root, self.manifest)
        print_resolved_path("index directory", index_dir)
        sqlite_path = index_dir / self.manifest.index.sqlite_file

        if not sqlite_path.exists():
            raise FileNotFoundError(
                f"No index found at {index_dir}. "
                f"Run `legacylift-search index --repo-root {self.repo_root}` "
                f"first; backfill-hashes only repairs an existing index."
            )

        log_path = index_dir / "index.log"
        try:
            _log_file = log_path.open("a", encoding="utf-8")
        except OSError:
            _log_file = None

        def _log(msg: str) -> None:
            if _log_file is None:
                return
            try:
                _log_file.write(msg + "\n")
                _log_file.flush()
            except OSError:
                pass

        _log(
            f"=== backfill-hashes started at "
            f"{datetime.now(timezone.utc).isoformat()} ==="
        )
        _log(f"repo_root={self.repo_root}")
        _log(f"index_dir={index_dir}")

        # Opening the store migrates it (CR-01), which is what adds the
        # column this command fills -- so `backfill-hashes` works on an index
        # that has never seen version 2.
        store = SQLiteStore(sqlite_path)
        try:
            rows = store.symbols_missing_content_hash()
            symbol_count = int(
                store.connection()
                .execute("SELECT COUNT(*) FROM symbols")
                .fetchone()[0]
            )

            symbols_missing = len(rows)
            files_verified = 0
            files_drifted = 0
            files_unreadable = 0
            symbols_unhashable = 0
            hashes: list[tuple[str, str]] = []

            # `rows` is ordered by relative_path, so each file is read and
            # digested exactly once no matter how many symbols it holds.
            current_path: str | None = None
            current_source = None

            for (
                relative_path,
                indexed_sha,
                symbol_id,
                start_byte,
                end_byte,
                start_line,
                end_line,
            ) in rows:
                if relative_path != current_path:
                    current_path = relative_path
                    current_source = None
                    absolute = self.repo_root / relative_path
                    try:
                        raw = absolute.read_bytes()
                    except OSError as exc:
                        files_unreadable += 1
                        _log(f"UNREADABLE {relative_path}: {exc}")
                        continue
                    if hashlib.sha256(raw).hexdigest() != indexed_sha:
                        files_drifted += 1
                        _log(
                            f"DRIFTED {relative_path}: on-disk sha256 differs "
                            f"from the indexed one; symbols left unhashed for "
                            f"the next `index` run"
                        )
                        continue
                    files_verified += 1
                    # Byte offsets are measured in the extractors' byte space,
                    # not the raw bytes -- see `store.SourceText`.
                    current_source = source_text(raw)

                if current_source is None:
                    # This file was skipped above; every one of its remaining
                    # symbols is skipped with it.
                    continue

                body = symbol_body_text(
                    current_source, start_byte, end_byte, start_line, end_line
                )
                if body is None:
                    symbols_unhashable += 1
                    _log(
                        f"UNHASHABLE {relative_path}: symbol {symbol_id} "
                        f"has neither byte bounds [{start_byte},{end_byte}) "
                        f"nor line bounds [{start_line},{end_line}] that fit "
                        f"the file"
                    )
                    continue
                hashes.append((symbol_id, content_hash(body)))

            symbols_hashed = store.set_symbol_content_hashes(hashes)
            remaining_null = store.count_symbols_missing_content_hash()
        finally:
            store.close()

        symbols_skipped = symbols_missing - symbols_hashed

        _log(
            f"backfill-hashes: {symbols_hashed} hashed, "
            f"{symbols_skipped} skipped "
            f"({files_drifted} drifted files, {files_unreadable} unreadable, "
            f"{symbols_unhashable} unhashable rows); "
            f"{remaining_null} still NULL"
        )
        print(
            f"Hashed {symbols_hashed} symbols, skipped {symbols_skipped} "
            f"({remaining_null} still unhashed)"
        )
        if _log_file is not None:
            try:
                _log_file.close()
            except OSError:
                pass

        return HashBackfillStats(
            symbols_missing=symbols_missing,
            symbols_hashed=symbols_hashed,
            symbols_skipped=symbols_skipped,
            files_verified=files_verified,
            files_drifted=files_drifted,
            files_unreadable=files_unreadable,
            symbols_unhashable=symbols_unhashable,
            remaining_null=remaining_null,
            symbol_count=symbol_count,
            index_dir=str(index_dir),
        )


__all__ = ["Indexer", "IndexStats", "BackfillStats", "HashBackfillStats"]
