"""The refresh pair: what keeps FTS5, the findings and the vectors in step.

Milestone 1, Step 5 of `docs/exec-plans/active/reqs-to-data-store.md`.

A `gr` row's derived artifacts live in three places -- the `gr_fts` row, the
`gr_finding` rows, and a record in the `gr_statements` Chroma collection -- and
**six** write paths change a `gr` row: ingest, the merge, `set-field`,
`set_state`, `import_records` and `rederive-subjects`. Naming "the ingest path"
as the thing that maintains the derived artifacts is the actual bug to avoid:
`set-field` rewrites `statement`, `import_records` restores rows wholesale, and
the merge updates extractor-owned fields -- none of those is ingest. Leave them
out and `requirements search` returns pre-edit text while stage two of the
merge compares incoming rules against stale vectors, so the *reviewed* records
are the ones near-duplicate search stops recognizing.

So every writer calls one obvious thing in one obvious order:

    refresh_gr_derived_sql(store, gr_ids, ...)   # inside the caller's txn
    store.commit()                               # the caller's commit
    refresh_gr_vectors(store, gr_ids, ...)       # after it, may degrade

**It is a pair rather than one function because the two halves sit on opposite
sides of the caller's commit, and no synchronous call can straddle its own
caller's commit.** The SQL half runs inside whatever transaction the caller
already has open -- for ingest, the single transaction covering the run --
using a `SAVEPOINT`, never a nested `BEGIN`, which either fails or silently
commits the outer transaction. The vector half runs after the commit so that a
rolled-back ingest cannot leave vectors behind for rules that never landed;
this repository has already been bitten once by a snapshot taken on the wrong
side of a vector write, which orphaned Chroma entries no SQLite row explained.

**`set_state` is on the caller list and is the one that is easy to leave off**,
because it writes no text: it moves `state`, which changes neither the FTS row
nor the embedded statement. But `state` is `gr_statements` *metadata*, so a
store that skips it answers `search --semantic --state approved` with rules
still tagged `draft`, silently and forever.

Two shapes were rejected and are worth naming, because both look tidier. A
single function returning a deferred handle puts the embedding behind a return
value Python makes trivial to drop, and a dropped handle silently skips
embedding. A single function owning its own transaction would put the validator
run and the FTS write outside ingest's transaction, so a rolled-back ingest
would leave findings and FTS entries for rules that never landed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from .gr_validator import validate_statement
from .knowledge_store import KnowledgeStore
from .models import EmbedResult, GRRecord, RefreshResult

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .embeddings import Embedder
    from .store import SQLiteStore
    from .vector_store import ChromaVectorStore

__all__ = [
    "GR_COLLECTION_NAME",
    "GR_VECTOR_METADATA_KEYS",
    "describe_vector_shortfall",
    "leaked_terms_for",
    "open_gr_collection",
    "open_index_store_if_present",
    "refresh_gr_derived_sql",
    "refresh_gr_vectors",
    "reindex_gr_vectors",
]


#: The dedicated collection requirement statements are embedded into.
#:
#: **Dedicated, not `code_chunks`.** Putting requirements in the code
#: collection would poison code search and force every existing query to carry
#: a type filter.
#:
#: The name is also Chroma-legal, which is not automatic: chromadb 1.5.9
#: validates collection names as 3-512 characters from `[a-zA-Z0-9._-]`
#: starting and ending alphanumeric, and raises `InvalidArgumentError` from
#: `get_or_create_collection` otherwise -- so a one-character test fixture name
#: fails in a way that reads as a configuration problem and is not one.
GR_COLLECTION_NAME: Final[str] = "gr_statements"

#: What a `gr_statements` record carries beside its vector. Every value is a
#: string, and **`''` means absent**: chromadb 1.5.9 does not reject a `None`
#: metadata value, it silently drops the key, so a NULL `subject` and an
#: unwritten `subject` would otherwise be byte-identical in the collection.
#: `upsert_texts` does the coercion; this tuple is what `stats` and the
#: state-filtered semantic search may rely on being present.
GR_VECTOR_METADATA_KEYS: Final[tuple[str, ...]] = (
    "gr_id",
    "kind",
    "state",
    "category",
    "subject",
)


def open_index_store_if_present(index_sqlite_path: Path) -> SQLiteStore | None:
    """Open the Layer-0 index, or return None if there is not one.

    **Probe with a plain `Path.exists()` first, and never construct the store
    to find out.** `SQLiteStore._connect` creates the database file on its
    first query, so asking the store whether an index exists materializes an
    empty `index.sqlite` beside a repository that has never been indexed -- and
    an empty index database is indistinguishable from a real one on the next
    command. `None` is a supported answer here, not an error path: it means
    `V-STY-03` runs on its morphological fallback alone.
    """
    if not index_sqlite_path.exists():
        return None
    from .store import SQLiteStore

    return SQLiteStore(index_sqlite_path)


def leaked_terms_for(
    store: KnowledgeStore,
    index_store: SQLiteStore,
    gr_id: str,
    cache: dict[str, frozenset[str]] | None = None,
) -> frozenset[str]:
    """Symbol names declared in the files this requirement cites. **Public.**

    Promoted out of the private `_leaked_terms_for` for one caller with a
    hard constraint: `requirements validate` "reports rule-notation
    violations without changing anything" (the plan's Purpose section), so it
    cannot reach the validator through `refresh_gr_derived_sql` -- that
    function rewrites `gr_fts` and replaces `gr_finding` rows, which is a
    write. A read-only `validate` therefore needs the `leaked_terms` set on
    its own, and building it by hand at the call site would put a
    cross-database join in the CLI and give `V-STY-03` two different inputs
    depending on which command ran it.

    `cache` is optional here and required on the private form: a single
    `validate` over the whole corpus should thread one dict across every
    requirement (a run's requirements cite the same handful of files
    repeatedly), while a one-off caller should not have to invent one.
    Omitting it means "no reuse", not "no caching" -- a fresh dict is built
    per call.

    `V-STY-03` asks whether a statement leaked an implementation identifier
    into business prose, and the sharpest evidence is a token matching a
    symbol declared in the requirement's *own* cited files. Note what an
    empty return does **not** mean: `frozenset()` from this function means
    the cited files declare no symbols, whereas `validate_statement`
    receiving `frozenset()` because no index exists means the check ran on
    its morphological half alone. The caller keeps those apart --
    `RefreshResult.leaked_terms_available`, and the CLI's own reporting -- and
    this function cannot, which is why it takes a non-optional
    `index_store`.

    The join is done in Python, per `domains_cmd`: `symbols` is in
    `index.sqlite` and `gr_citation` is in `knowledge.sqlite`, and the two
    databases are never `ATTACH`ed.
    """
    return _leaked_terms_for(
        store, index_store, gr_id, {} if cache is None else cache
    )


def _leaked_terms_for(
    store: KnowledgeStore,
    index_store: SQLiteStore,
    gr_id: str,
    cache: dict[str, frozenset[str]],
) -> frozenset[str]:
    """Symbol names declared in the files this requirement cites.

    The private form, kept because `refresh_gr_derived_sql` calls it with a
    cache it owns for the whole batch. `leaked_terms_for` above is the public
    entry point and delegates here; this one is not removed and not renamed,
    so nothing that already calls it has to change.

    `V-STY-03` asks whether a statement leaked an implementation identifier
    into business prose, and the sharpest evidence is a token matching a symbol
    declared in the requirement's *own* cited files.

    The join is done in Python, per `domains_cmd`: `symbols` is in
    `index.sqlite` and `gr_citation` is in `knowledge.sqlite`, and the two
    databases are never `ATTACH`ed. `cache` is keyed on `relative_path`
    because a run's requirements cite the same handful of files repeatedly.
    """
    paths = store.citation_paths_for_gr(gr_id)
    unknown = [p for p in paths if p not in cache]
    if unknown:
        by_path = index_store.get_symbols_for_files(unknown)
        for path in unknown:
            symbols = by_path.get(path) or []
            terms: set[str] = set()
            for symbol in symbols:
                if symbol.name:
                    terms.add(symbol.name)
                if symbol.qualified_name:
                    terms.add(symbol.qualified_name)
            cache[path] = frozenset(terms)
    merged: set[str] = set()
    for path in paths:
        merged |= cache[path]
    return frozenset(merged)


def refresh_gr_derived_sql(
    store: KnowledgeStore,
    gr_ids: list[str],
    index_store: SQLiteStore | None = None,
    repo_root: Path | None = None,
) -> RefreshResult:
    """Rewrite the FTS5 rows and re-run the validator, inside the caller's txn.

    Args:
        store: The knowledge store holding the `gr` tables.
        gr_ids: The requirements to refresh. **A list, not a single id**:
            ingest calls this once for a whole run, and per-record would mean
            several hundred separate validator runs.
        index_store: The Layer-0 index, or **None meaning there is no index**
            -- a supported state under which `V-STY-03` runs on its
            morphological fallback alone and the result says so. Callers
            obtain it through `open_index_store_if_present`.
        repo_root: Declared by this plan's `Interfaces and Dependencies` and
            **read by no code path in Step 5**, stated plainly rather than
            quietly accepted: the two rules that need a repository root are
            Step 6a's citation staleness guard and the span-level
            `content_hash`, both of which run at ingest, inside
            `resolve_anchor`. It is threaded here so the signature does not
            change under the step that starts using it.

    Returns:
        A `RefreshResult`. `leaked_terms_available` is False when
        `index_store` was None -- the difference between "no leaked identifier
        was found" and "leakage was never looked for".

    **Does not commit.** It runs inside whatever transaction the caller already
    has open, bracketed by a `SAVEPOINT` rather than a `BEGIN`: a nested
    `BEGIN` either fails or commits the caller's outer transaction, and the
    second of those is silent. Called with no transaction open, the
    `SAVEPOINT`/`RELEASE` pair starts and commits one of its own -- benign, and
    **not** the contract; do not build on it.
    """
    result = RefreshResult(leaked_terms_available=index_store is not None)
    if not gr_ids:
        return result

    conn = store._connect()
    conn.execute("SAVEPOINT gr_refresh_sql")
    try:
        records: list[GRRecord] = store.list_gr(gr_ids)
        present = {r.gr_id for r in records}
        for gr_id in gr_ids:
            if gr_id not in present:
                # No row: forget its text rather than leaving a searchable
                # ghost. Its `gr_finding` rows are already gone by cascade.
                store.delete_gr_fts(gr_id)
                result.forgotten += 1

        cache: dict[str, frozenset[str]] = {}
        for record in records:
            store.replace_gr_fts(record)
            leaked: frozenset[str] = frozenset()
            if index_store is not None:
                leaked = _leaked_terms_for(store, index_store, record.gr_id, cache)
                result.leaked_term_count += len(leaked)
            findings = validate_statement(record, leaked)
            store.replace_gr_findings(record.gr_id, findings)
            result.refreshed += 1
            result.findings_written += len(findings)
    except Exception:
        conn.execute("ROLLBACK TO gr_refresh_sql")
        conn.execute("RELEASE gr_refresh_sql")
        raise
    conn.execute("RELEASE gr_refresh_sql")
    return result


def open_gr_collection(
    store: KnowledgeStore,
    embedder: Embedder,
    base_dir: Path | None = None,
) -> ChromaVectorStore:
    """Open (creating if needed) the `gr_statements` collection.

    **Under the knowledge directory, not the index directory, and that is not
    a preference.** `index --reset` does `shutil.rmtree(index_dir / chroma)`
    -- every collection in it -- so a `gr_statements` collection created under
    the index directory is destroyed by a routine reindex, and the failure is
    silent in the worst way: stage two of the merge then queries an empty
    collection and returns no candidates, which is indistinguishable from
    finding no near-duplicates. The under-merge safety net would be gone with
    nothing to say so.

    `base_dir` defaults to the directory holding `knowledge.sqlite`, which is
    the resolved knowledge directory -- giving
    `analysis/<system>/knowledge/chroma`, which no reset path can reach.
    """
    from .vector_store import ChromaVectorStore

    root = base_dir if base_dir is not None else store.sqlite_path.parent
    return ChromaVectorStore(
        base_dir=root,
        collection_name=GR_COLLECTION_NAME,
        embedder=embedder,
        metadata={},
    )


def refresh_gr_vectors(
    store: KnowledgeStore,
    gr_ids: list[str],
    embedder: Embedder | None = None,
    base_dir: Path | None = None,
    collection: ChromaVectorStore | None = None,
) -> EmbedResult:
    """Re-embed statements into `gr_statements`. Runs AFTER the caller commits.

    **This half is allowed to degrade and the rules always land.** An embedder
    must be resolvable for the semantic half to work, and for the hosted
    provider that is a network call per statement -- the least reliable thing
    in the pipeline sitting immediately downstream of the most expensive. So
    the SQLite work is committed first and unconditionally; if no embedder is
    configured, or the calls fail, or the collection's dimension does not
    match, the requirements are still in the store and this returns an
    `EmbedResult` whose `reason` names `requirements reindex-vectors` as the
    single recovery. Callers **exit zero** on that: a non-zero exit reads as
    "the ingest failed" and invites re-running the extraction, which is hours
    of model time to recover something that was never lost.

    Args:
        store: The knowledge store -- also where the collection lives.
        gr_ids: The requirements to re-embed. A `gr_id` with no row has its
            record deleted from the collection instead.
        embedder: **None means no embedder is available**, which is a degraded
            success, not an error. Step 8's CLI passes the configured one;
            `set_state` passes whatever its caller had.
        base_dir: Overrides where the collection lives; see
            `open_gr_collection`.
        collection: An already-open collection to write through. When given it
            is left open for the caller to close; when omitted one is opened
            and closed here, which matters on Windows, where Chroma's
            `PersistentClient` holds its own SQLite files open.
    """
    if not gr_ids:
        return EmbedResult()
    if embedder is None:
        return EmbedResult(
            skipped=len(gr_ids),
            reason=(
                "no embedder is available, so the semantic half of the "
                "requirements store was not populated; the requirements "
                "themselves are stored and keyword search works. Run "
                "`legacylift-search requirements reindex-vectors` once an "
                "embedding provider is configured."
            ),
        )

    records = store.list_gr(gr_ids)
    present = {r.gr_id for r in records}
    missing = [g for g in gr_ids if g not in present]

    owned = collection is None
    try:
        if collection is None:
            collection = open_gr_collection(store, embedder, base_dir)
    except Exception as exc:
        return EmbedResult(
            skipped=len(gr_ids),
            reason=(
                f"the {GR_COLLECTION_NAME} collection could not be opened "
                f"({exc}); the requirements are stored and keyword search "
                "works. Run `legacylift-search requirements reindex-vectors` "
                "to populate the semantic half."
            ),
        )

    try:
        try:
            # Only fires on a collection that ALREADY carries an
            # `embedding_dimension` -- `get_or_create_collection` writes it at
            # creation and thereafter ignores it -- so the case this handles is
            # a pre-existing collection under a switched embedding provider.
            # That is the same condition as a missing collection: say so, and
            # point at the rebuild.
            collection.validate_dimension()
        except ValueError as exc:
            return EmbedResult(
                skipped=len(gr_ids),
                reason=(
                    f"the {GR_COLLECTION_NAME} collection was built with a "
                    f"different embedding provider ({exc}); it is unusable "
                    "rather than stale. Delete it and run "
                    "`legacylift-search requirements reindex-vectors`."
                ),
            )

        deleted = 0
        if missing:
            collection.delete_ids(missing)
            deleted = len(missing)

        if not records:
            return EmbedResult(deleted=deleted)

        texts = [r.statement for r in records]
        try:
            embeddings = embedder.embed_documents(texts)
        except Exception as exc:
            return EmbedResult(
                deleted=deleted,
                skipped=len(records),
                reason=(
                    f"embedding failed ({exc}); the requirements are stored "
                    "and keyword search works. Run `legacylift-search "
                    "requirements reindex-vectors` to retry."
                ),
            )

        metadatas = [
            {
                "gr_id": r.gr_id,
                "kind": r.kind,
                "state": r.state,
                "category": r.category,
                "subject": r.subject,
            }
            for r in records
        ]
        try:
            collection.upsert_texts(
                ids=[r.gr_id for r in records],
                texts=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except Exception as exc:
            return EmbedResult(
                deleted=deleted,
                skipped=len(records),
                reason=(
                    f"writing to the {GR_COLLECTION_NAME} collection failed "
                    f"({exc}); the requirements are stored and keyword search "
                    "works. Run `legacylift-search requirements "
                    "reindex-vectors` to retry."
                ),
            )
        return EmbedResult(embedded=len(records), deleted=deleted)
    finally:
        if owned and collection is not None:
            collection.close()


def _collection_ids(collection: ChromaVectorStore) -> list[str]:
    """Every id in the collection, or `[]` if they cannot be enumerated.

    Reaches through to `collection.collection` -- the raw chromadb handle --
    because `ChromaVectorStore` exposes `count()` and `delete_ids()` but no
    id listing, and adding one is a change to a module five other callers
    share. `include=[]` asks chromadb for ids and nothing else, which is what
    keeps this cheap on a large collection.

    An enumeration failure returns `[]` rather than raising: the only use is
    finding **stale** ids to delete, so failing to enumerate degrades
    `reindex_gr_vectors` to "re-embed everything and delete nothing", which
    is a strictly weaker rebuild and not a wrong one. The result says how
    many it deleted, so a zero there is visible.
    """
    try:
        got = collection.collection.get(include=[])
    except Exception:  # pragma: no cover - defensive; chromadb-version drift
        return []
    return list(got.get("ids") or [])


def reindex_gr_vectors(
    store: KnowledgeStore,
    embedder: Embedder | None = None,
    base_dir: Path | None = None,
    collection: ChromaVectorStore | None = None,
) -> EmbedResult:
    """Rebuild `gr_statements` from the `gr` rows. Step 5's one recovery.

    **The single documented recovery for four different failures**, which is
    why it is one command and not four: an `index --reset` that reached the
    collection, a run made with no embedder configured, an embedding call
    that failed mid-run, and a switch of embedding provider (under which the
    existing collection is unusable rather than stale, because its dimension
    no longer matches). Each of those leaves the SQLite half correct and the
    vector half behind, and `describe_vector_shortfall` is what says so.

    It walks `store.all_gr_ids()` and hands the whole list to
    `refresh_gr_vectors`, so it inherits that function's degradation
    behaviour exactly -- a missing embedder, an unopenable collection, a
    failed embed and a dimension mismatch each come back as an `EmbedResult`
    carrying a `reason`, and the caller **exits zero**. It re-embeds every
    row rather than only the missing ones: this is the recovery path, the
    reason a vector is absent is by definition unknown here, and an
    id-by-id diff against the collection would trust the very state that is
    suspect.

    Before that it deletes the ids the collection holds that `gr` does not.
    `refresh_gr_vectors` deletes a `gr_id` with no row only among the ids it
    was *given*, so a requirement deleted while the collection was stale
    would otherwise keep its vector forever -- a searchable ghost of a
    record that no longer exists, which is the same defect
    `replace_gr_fts`'s delete half prevents on the keyword side.

    **Safe to run twice**: the write is an upsert keyed on `gr_id`, the
    delete is over a set difference that is empty the second time, and
    nothing about the operation depends on prior state.

    Returns:
        An `EmbedResult`. `embedded` is how many statements were written,
        `deleted` counts both the stale ids removed here and any absent
        `gr_id` `refresh_gr_vectors` cleaned up, and `skipped` with a
        `reason` is the degraded outcome. On an empty store every count is
        zero and `reason` is None -- **which is a successful rebuild of
        nothing, not a failure**, and the caller should say "0 requirements"
        rather than treating it as an error.
    """
    gr_ids = store.all_gr_ids()

    # The stale-id sweep needs an open collection of its own, and opening one
    # requires an embedder (chromadb wants the dimension at creation). With
    # no embedder there is nothing to sweep with and nothing to embed either,
    # so fall straight through to `refresh_gr_vectors`, whose no-embedder
    # branch is the one that names the recovery.
    stale_deleted = 0
    owned = False
    if embedder is not None:
        if collection is None:
            try:
                collection = open_gr_collection(store, embedder, base_dir)
                owned = True
            except Exception as exc:
                return EmbedResult(
                    skipped=len(gr_ids),
                    reason=(
                        f"the {GR_COLLECTION_NAME} collection could not be "
                        f"opened ({exc}); the requirements are stored and "
                        "keyword search works. Check the embedding provider "
                        "configuration and re-run "
                        "`legacylift-search requirements reindex-vectors`."
                    ),
                )
        known = set(gr_ids)
        stale = [i for i in _collection_ids(collection) if i not in known]
        if stale:
            collection.delete_ids(stale)
            stale_deleted = len(stale)

    try:
        if not gr_ids:
            # Nothing to embed. The sweep above may still have removed
            # orphans, and reporting that is the point of getting here.
            return EmbedResult(deleted=stale_deleted)
        result = refresh_gr_vectors(
            store,
            gr_ids,
            embedder=embedder,
            base_dir=base_dir,
            collection=collection,
        )
    finally:
        if owned and collection is not None:
            collection.close()

    return EmbedResult(
        embedded=result.embedded,
        skipped=result.skipped,
        deleted=result.deleted + stale_deleted,
        reason=result.reason,
    )


def describe_vector_shortfall(gr_count: int, collection_count: int) -> str | None:
    """Words for a `gr_statements` collection that is behind `gr`, else None.

    **Stage two of the merge must call this before searching.** An
    under-populated collection answers a near-duplicate query with zero
    candidates, which is indistinguishable from "there are no near duplicates"
    -- the same absent-versus-real defect as storing an unmeasured count as
    zero. The degraded state has to announce itself at the moment it matters,
    not only in the output of the command that caused it.

    A collection holding *more* records than `gr` is not a shortfall and is
    reported as None: `refresh_gr_vectors` deletes the record of a `gr_id` with
    no row, so a surplus means ids nothing asked about, which no search can
    return as a candidate for a rule that exists.
    """
    if collection_count >= gr_count:
        return None
    behind = gr_count - collection_count
    return (
        f"the {GR_COLLECTION_NAME} collection holds {collection_count} of "
        f"{gr_count} requirements -- {behind} have no vector, so "
        "near-duplicate search cannot see them and a zero-candidate result "
        "here does NOT mean there are no near duplicates. Run "
        "`legacylift-search requirements reindex-vectors` first."
    )
