"""Chroma persistent vector store wrapper.

Implements Milestone 9b of the ExecPlan
(`docs/exec-plans/active/semantic-code-search-graph-index.md`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from legacylift_search.embeddings import Embedder
    from legacylift_search.models import CodeChunk


class VectorResult(BaseModel):
    """A single vector query result from Chroma."""

    id: str
    document: str
    metadata: dict
    distance: float


class ChromaVectorStore:
    """Wrapper around Chroma PersistentClient for code chunk storage."""

    def __init__(
        self,
        base_dir: Path,
        collection_name: str,
        embedder: Embedder,
        metadata: dict[str, str],
    ):
        """Initialize ChromaVectorStore.

        Args:
            base_dir: Root directory the collection lives under (Chroma uses
                `base_dir/chroma`). **Renamed from `index_dir` in Milestone 1
                Step 5 of `docs/exec-plans/active/reqs-to-data-store.md`**,
                because two callers now pass two different roots: the code
                index passes the resolved *index* directory, and the
                `gr_statements` collection passes the resolved *knowledge*
                directory, precisely so `index --reset` -- which rmtrees
                `index_dir/chroma` wholesale -- cannot delete requirements
                vectors. **The rename fixes the name and nothing else.**
                `chroma_dir` from the manifest is still read by five other
                sites (`cli.py` twice, `indexer.py` three times) and still NOT
                read here -- this constructor hardcodes `"chroma"` -- so
                a manifest that sets it non-default still has a reset path
                aimed at a directory this store never wrote. That is filed as
                entry 2 of `docs/exec-plans/pending/deferred-small-items.md`
                and a `base_dir` parameter is not evidence it was closed.
            collection_name: Name of the Chroma collection.
            embedder: Embedder instance (provides dimension and name).
            metadata: Additional metadata to store in collection metadata.

        Raises:
            ImportError: If chromadb is not installed.
        """
        try:
            import chromadb
        except ImportError as e:
            raise ImportError(
                "chromadb is required for ChromaVectorStore. "
                "Install it with: pip install chromadb"
            ) from e

        self.base_dir = base_dir
        self.collection_name = collection_name
        self.embedder = embedder
        self.metadata = metadata

        # Create persistent client
        chroma_path = base_dir / "chroma"
        self.client = chromadb.PersistentClient(path=str(chroma_path))

        # Build collection metadata. The hnsw:* keys tune Chroma's HNSW
        # persistence: a higher sync_threshold lets the index buffer more
        # inserts before fsyncing to disk, which is the dominant cost when
        # indexing large repos (e.g. ctcm-api at ~58k chunks).
        collection_metadata = {
            "embedder_name": embedder.name,
            "embedding_dimension": str(embedder.dimension),
            "hnsw:sync_threshold": 100000,
            "hnsw:batch_size": 10000,
            **metadata,
        }

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata=collection_metadata,
        )

    def upsert_chunks(
        self,
        chunks: list[CodeChunk],
        embeddings: list[list[float]],
        domain_by_chunk: dict[str, str] | None = None,
    ) -> None:
        """Upsert code chunks with their embeddings into Chroma.

        Args:
            chunks: List of CodeChunk instances.
            embeddings: Corresponding embedding vectors (same order as chunks).
            domain_by_chunk: Optional `{chunk.id: domain}` map (Milestone 5 of
                `domain-enhancements-plan.md`, issues #26/#29). When present,
                each chunk whose id is in the map gets its authoritative
                capability `domain` merged into its per-chunk metadata dict.
                A chunk id absent from the map (or a ``None`` map) leaves the
                key off — matching pre-Milestone-5 behavior and, per the
                derived-mirror invariant, marking a file that has no
                `file_domains` row at all.

        Raises:
            ValueError: If chunks and embeddings have different lengths.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunk count ({len(chunks)}) must match embedding count "
                f"({len(embeddings)})"
            )

        if not chunks:
            return  # Nothing to upsert

        # Prepare data for Chroma
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]

        # Build metadata, coercing None to empty string. **The coercion is
        # right and the reason once given for it was not**: chromadb 1.5.9
        # does not reject a None value, it *silently drops the key*. Measured
        # 2026-09-01: upserting {"gr_id": "A", "subject": None} and
        # {"gr_id": "B"} yields two rows whose metadata is byte-identical. So
        # a real-but-absent value and a value nobody supplied share an
        # encoding unless the caller coerces, which is why every optional
        # field below is written as `or ""` rather than passed through.
        metadatas = []
        for chunk in chunks:
            meta = {
                "relative_path": chunk.relative_path,
                "language": chunk.language,
                "chunk_kind": chunk.chunk_kind,
                "symbol_id": chunk.symbol_id or "",
                "symbol_path": chunk.symbol_path or "",
                "start_line": str(chunk.start_line),
                "end_line": str(chunk.end_line),
                "text_sha256": chunk.text_sha256,
            }
            if domain_by_chunk is not None:
                domain = domain_by_chunk.get(chunk.id)
                if domain is not None:
                    meta["domain"] = domain
            metadatas.append(meta)

        # Upsert into Chroma
        self.collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def upsert_texts(
        self,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]],
    ) -> None:
        """Upsert plain id/text/metadata triples — the text-shaped writer.

        Milestone 1 Step 5 of `docs/exec-plans/active/reqs-to-data-store.md`.
        A **sibling** of `upsert_chunks`, deliberately not a generalization of
        it: `upsert_chunks` is `CodeChunk`-typed and owns the indexer's eight
        metadata keys, and widening it to serve requirements too would put a
        second caller's field set inside the indexer's hot path for no gain.

        **Every metadata value must already be a string.** chromadb 1.5.9 does
        not reject a `None` value, it *silently drops the key* (measured
        2026-09-01: upserting `{"gr_id": "A", "subject": None}` and
        `{"gr_id": "B"}` yields two rows whose metadata is byte-identical), so
        "this requirement has no derivable subject" and "nobody wrote a
        subject" would share an encoding. This method therefore coerces `None`
        to `''` rather than trusting its callers, and **`''` means absent** in
        any collection written through it — a `where={"subject": ""}` filter
        matches exactly the coerced rows.

        Args:
            ids: Record ids, one per text.
            texts: The documents to store and embed.
            embeddings: Vectors, in the same order as `ids`.
            metadatas: One metadata dict per id.

        Raises:
            ValueError: If the four lists are not all the same length.
        """
        if not (len(ids) == len(texts) == len(embeddings) == len(metadatas)):
            raise ValueError(
                f"upsert_texts needs four equal-length lists; got "
                f"{len(ids)} ids, {len(texts)} texts, "
                f"{len(embeddings)} embeddings, {len(metadatas)} metadatas"
            )
        if not ids:
            return

        coerced = [
            {k: ("" if v is None else str(v)) for k, v in meta.items()}
            for meta in metadatas
        ]
        self.collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=coerced,
        )

    def count(self) -> int:
        """Return the number of records in the collection.

        There was no count wrapper before Milestone 1 Step 5; the shortfall
        check (an under-populated `gr_statements` collection must announce
        itself rather than answering a near-duplicate search with zero
        candidates) needs one.
        """
        return self.collection.count()

    def delete_ids(self, ids: list[str]) -> None:
        """Delete records by id. Best-effort: an absent id is not an error."""
        if not ids:
            return
        # Chroma accepts up to ~5k ids per call; chunk to be safe.
        for i in range(0, len(ids), 1000):
            batch = ids[i : i + 1000]
            try:
                self.collection.delete(ids=batch)
            except Exception:
                # Deletion is best-effort: if the id wasn't there, that's fine.
                pass

    def delete_chunks(self, ids: list[str]) -> None:
        """Delete vectors from the Chroma collection by chunk id.

        Used during incremental reindex when a file is deleted from the
        source tree or when its chunks are rewritten with different ids.
        """
        self.delete_ids(ids)

    def update_domain_metadata(self, chunk_ids: list[str], domain: str) -> None:
        """Stamp a `domain` metadata key onto existing Chroma records.

        Wraps `collection.update(...)`. chromadb 1.5.9 MERGES the supplied
        metadata into each id's existing dict rather than replacing it
        (verified empirically — see the "Surprises & Discoveries" note in
        `docs/exec-plans/pending/domain-enhancements-plan.md`), so passing only
        `{"domain": domain}` preserves the chunk's other seven metadata keys —
        no read-merge-write and no re-embedding.

        Must tolerate chunk ids that are NOT in the collection (issue #15):
        chunks below `chunking.embed_min_tokens` land in SQLite/FTS5 but are
        never embedded, so `SELECT id FROM chunks` can return ids that were
        never upserted into Chroma. Callers should prefer to restrict
        `chunk_ids` to the `vectors_present` set (exact); this method also
        wraps the call defensively — mirroring `delete_chunks` — so a stray
        absent id can never raise.

        Args:
            chunk_ids: Chroma record ids to stamp.
            domain: The domain value to merge into each record's metadata.
        """
        if not chunk_ids:
            return
        # Chroma accepts up to ~5k ids per call; chunk to be safe (mirrors
        # delete_chunks).
        for i in range(0, len(chunk_ids), 1000):
            batch = chunk_ids[i : i + 1000]
            metadatas = [{"domain": domain} for _ in batch]
            try:
                self.collection.update(ids=batch, metadatas=metadatas)
            except Exception:
                # Best-effort: an id absent from the collection (never embedded)
                # must not abort the stamp pass (issue #15).
                pass

    def query(
        self,
        query_embedding: list[float],
        limit: int,
        where: dict | None = None,
    ) -> list[VectorResult]:
        """Query the collection for similar chunks.

        Args:
            query_embedding: Query vector.
            limit: Maximum number of results to return.
            where: Optional Chroma metadata filter, passed straight through to
                ``collection.query(...)``. ``None`` means no filter (today's
                behavior). Milestone 6 of `domain-enhancements-plan.md` passes
                ``{"domain": domain_id}`` here to restrict results to a single
                capability domain (the ``domain`` metadata is a derived mirror
                of the authoritative `file_domains` row).

        Returns:
            List of VectorResult instances, ordered by similarity.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where,
        )

        # Unpack Chroma results (returns lists of lists)
        vector_results = []
        if results["ids"] and results["ids"][0]:
            ids = results["ids"][0]
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            for i in range(len(ids)):
                vector_results.append(
                    VectorResult(
                        id=ids[i],
                        document=documents[i],
                        metadata=metadatas[i],
                        distance=distances[i],
                    )
                )

        return vector_results

    def validate_dimension(self) -> None:
        """Validate that collection dimension matches embedder dimension.

        Raises:
            ValueError: If existing collection has a different dimension.
        """
        collection_meta = self.collection.metadata or {}
        stored_dim_str = collection_meta.get("embedding_dimension")

        if stored_dim_str is not None:
            stored_dim = int(stored_dim_str)
            if stored_dim != self.embedder.dimension:
                raise ValueError(
                    f"Existing Chroma collection uses dimension {stored_dim} but "
                    f"configured embedder uses dimension {self.embedder.dimension}. "
                    "Re-run with --reset or choose a different index directory."
                )

    def close(self) -> None:
        """Release this client's file handles AND Chroma's cached System.

        Both halves are load-bearing, and the second was missing until
        2026-09-14, which made `--reset` behave differently on Windows and
        Linux:

        `chromadb.PersistentClient` does not return a fresh object per call.
        `SharedSystemClient` keeps a process-global `_identifier_to_system` map
        keyed by path, so a later `PersistentClient(path=...)` for the same path
        hands back the CACHED System -- with the SQLite connection it opened the
        first time. Dropping our references and collecting, as this method used
        to do alone, does nothing to that map.

        That is invisible until the directory underneath is replaced, which is
        exactly what `--reset` does. On Linux the `rmtree` succeeds, the cached
        connection is left pointing at an unlinked inode, and the next query
        fails with SQLite error 1032, `SQLITE_READONLY_DBMOVED` -- surfacing as
        the thoroughly misleading "attempt to write a readonly database". On
        Windows the same `rmtree` cannot delete files held open, and because it
        runs with `ignore_errors=True` it fails silently; the directory survives,
        the cached connection stays valid, and the bug is masked. The suite was
        green on Windows and red on the first Linux CI run for this reason.

        Clearing the cache here is the narrow fix: a closed store must leave
        nothing behind that a later open would resurrect.
        """
        import gc

        self.collection = None
        self.client = None

        # Drop Chroma's process-global System cache. Best-effort: the import
        # path is internal to chromadb and pinned only by our version pin, and
        # failing to clear a cache must never turn closing a store into an
        # error. The directory-replacement bug above is the reason to try.
        try:
            from chromadb.api.shared_system_client import SharedSystemClient

            SharedSystemClient.clear_system_cache()
        except Exception:
            pass

        # Force garbage collection to close file handles (Windows needs this
        # before any caller can delete or replace the directory).
        gc.collect()
