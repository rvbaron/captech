"""Hybrid (vector + lexical) search with reciprocal rank fusion.

Implements Milestone 11 of the ExecPlan
(`docs/exec-plans/active/semantic-code-search-graph-index.md`).

The :class:`SearchEngine` combines a Chroma vector search with a SQLite
FTS5 lexical search, fuses the two ranked lists using Reciprocal Rank
Fusion, and returns :class:`legacylift_search.models.SearchResult`
records suitable for CLI rendering.
"""

from __future__ import annotations

import re

from .config import SearchConfig
from .embeddings import Embedder
from .models import SearchResult
from .store import SQLiteStore
from .vector_store import ChromaVectorStore


def sanitize_fts_query(query: str) -> str:
    """Tokenize a free-text query into FTS5-safe terms.

    Extracts alphanumeric/underscore tokens and joins them with spaces so
    the resulting string is safe to bind to ``MATCH``. Returns an empty
    string when the query contains no usable tokens.
    """
    tokens = re.findall(r"\w+", query)
    return " ".join(tokens)


class SearchEngine:
    """Hybrid vector + lexical search with RRF fusion."""

    # Under `--domain`, the lexical candidate pool is enlarged so that after
    # dropping out-of-domain hits roughly ``lexical_candidates`` in-domain rows
    # still survive to fuse (issue #46/#49). ``k`` is a multiplier on
    # ``config.lexical_candidates``, capped by a sane ceiling.
    LEXICAL_DOMAIN_POOL_FACTOR = 5
    LEXICAL_DOMAIN_POOL_CEILING = 500

    def __init__(
        self,
        store: SQLiteStore,
        vector_store: ChromaVectorStore,
        embedder: Embedder,
        config: SearchConfig,
    ) -> None:
        self.store = store
        self.vector_store = vector_store
        self.embedder = embedder
        self.config = config

    # ---- internals ---------------------------------------------------

    def _vector_ranks(
        self, query: str, where: dict | None = None
    ) -> dict[str, int]:
        """Run vector search and return chunk_id -> 1-based rank.

        When ``where`` is set (``--domain`` active) it is a Chroma metadata
        filter (``{"domain": domain_id}``). The candidate pool stays at
        ``config.vector_candidates`` and is NOT over-fetched under
        ``--domain`` (issue #57).

        #57 VERIFIED (2026-07-21, chromadb 1.5.9): leaving the vector pool at
        ``vector_candidates`` under ``--domain`` rests on Chroma applying
        ``where`` as a true pre-filter that FILLS ``n_results`` from the
        in-domain set. "All in-domain" is guaranteed (a filtered query never
        returns an out-of-domain row); "full pool" was the open question and
        is now confirmed by direct probe. A filtered ``collection.query`` on
        collections of 20k and 58k (ctcm-scale) random vectors returned a full
        ``n_results``, all in-domain, across selectivity down to 0.5%
        in-domain (100/290 in-domain rows, filter discarding 99.5% of the
        collection) — no under-fill. So no over-fetch / pool scaling is needed
        here; the vector arm's in-domain recall matches the unfiltered arm.
        RE-RUN this probe if the chromadb pin moves off 1.5.9 (the fill
        behavior is version-specific, like the `update`-merge behavior). The
        probe script is preserved verbatim in the
        `domain-search-vector-recall-57` note.
        """
        try:
            embedding = self.embedder.embed_query(query)
        except Exception:
            return {}
        results = self.vector_store.query(
            embedding, limit=self.config.vector_candidates, where=where
        )
        return {result.id: i + 1 for i, result in enumerate(results)}

    def _lexical_ranks(
        self,
        query: str,
        limit: int | None = None,
        in_domain_paths: set[str] | None = None,
    ) -> dict[str, int]:
        """Run FTS5 lexical search and return chunk_id -> 1-based rank.

        The query is sanitized to alphanumeric tokens before being passed
        to the store, which itself binds the value as a parameter.

        ``limit`` overrides the candidate pool size (default
        ``config.lexical_candidates``); the enlarged pool is only requested
        under ``--domain`` (issue #46/#49).

        When ``in_domain_paths`` is set (``--domain`` active), the survivors
        are FILTERED to in-domain and RE-ENUMERATED densely 1..N *before* they
        reach RRF (issue #54). Keeping the survivors on their GLOBAL FTS5 ranks
        would suppress their RRF weight (``1/(60+global_rank)``) and nullify
        the over-fetch — enlarging the pool only pushes global ranks deeper.
        Dense re-ranking gives an in-domain hit at global position 150 the
        ``1/(60+2)``-class weight its in-domain position deserves, matching the
        (already-dense) vector arm.

        Efficiency (issue #54 caution): this needs each candidate's
        ``relative_path``, but ``LexicalResult`` already carries it (selected
        from the FTS row) — so NO extra ``get_chunk`` / round-trip is done here
        and none is double-fetched in the fusion loop. When ``in_domain_paths``
        is None (unfiltered), behavior is byte-identical to before: global
        ranks, no filter.
        """
        sanitized = sanitize_fts_query(query)
        if not sanitized:
            return {}
        pool = limit if limit is not None else self.config.lexical_candidates
        results = self.store.search_lexical(sanitized, limit=pool)
        if in_domain_paths is None:
            # Unfiltered: global 1-based ranks, unchanged.
            return {
                result.chunk_id: i + 1 for i, result in enumerate(results)
            }
        # #54 dense pre-RRF re-rank: keep only in-domain survivors in their
        # global FTS order, enumerating them 1..N.
        ranks: dict[str, int] = {}
        dense = 0
        for result in results:
            if result.relative_path in in_domain_paths:
                dense += 1
                ranks[result.chunk_id] = dense
        return ranks

    def _make_snippet(self, text: str | None) -> str:
        """Build a snippet from chunk text, trimmed by ``snippet_radius_lines``."""
        if not text:
            return ""
        max_lines = max(1, self.config.snippet_radius_lines * 2)
        lines = text.splitlines()
        if len(lines) <= max_lines:
            return text.rstrip("\n")
        return "\n".join(lines[:max_lines])

    # ---- public API --------------------------------------------------

    def search(
        self,
        query: str,
        limit: int | None = None,
        domain_id: str | None = None,
        in_domain_paths: set[str] | None = None,
    ) -> list[SearchResult]:
        """Run a hybrid search and return ranked SearchResult entries.

        When ``domain_id`` is set the search is scoped to a single capability
        domain (Milestone 6 of `domain-enhancements-plan.md`). ``SearchEngine``
        does NOT own a ``KnowledgeStore`` — the CLI resolves the name to a
        ``domain_id`` and passes both it and ``in_domain_paths`` (the set of
        in-domain ``relative_path``s from ``files_for_domain``) in.

        Under ``--domain``:
          * the vector arm passes ``where={"domain": domain_id}`` to Chroma;
          * the lexical arm enlarges its pool and re-ranks the in-domain
            survivors densely BEFORE RRF (issue #46/#49/#54);
          * the fusion loop still drops any hit whose ``relative_path`` is not
            in ``in_domain_paths`` (the #23 vector-side safety net — a no-op on
            the already-in-domain lexical hits, but it discards any vector hit
            that slips through Chroma's ``where``).

        When ``domain_id`` is None, behavior is exactly as before: no filter,
        no re-rank, global ranks for both arms, and the fusion-loop drop is a
        no-op (``in_domain_paths`` is None).
        """
        effective_limit = (
            limit if limit is not None else self.config.default_limit
        )
        k = self.config.rrf_rank_constant

        filtered = domain_id is not None

        vector_ranks = self._vector_ranks(
            query, where={"domain": domain_id} if filtered else None
        )
        if filtered:
            pool = min(
                self.config.lexical_candidates
                * self.LEXICAL_DOMAIN_POOL_FACTOR,
                self.LEXICAL_DOMAIN_POOL_CEILING,
            )
            lexical_ranks = self._lexical_ranks(
                query, limit=pool, in_domain_paths=in_domain_paths
            )
        else:
            lexical_ranks = self._lexical_ranks(query)

        chunk_ids = set(vector_ranks) | set(lexical_ranks)
        if not chunk_ids:
            return []

        scored: list[tuple[float, int, str, SearchResult]] = []
        for chunk_id in chunk_ids:
            vrank = vector_ranks.get(chunk_id)
            lrank = lexical_ranks.get(chunk_id)
            score = 0.0
            if vrank is not None:
                score += 1.0 / (k + vrank)
            if lrank is not None:
                score += 1.0 / (k + lrank)

            chunk = self.store.get_chunk(chunk_id)
            if chunk is None:
                # Result references a chunk no longer present; skip.
                continue

            # #23 fusion-loop drop (vector-side safety net). Under --domain,
            # discard any hit whose file is not in-domain — catches vector
            # hits that slipped through Chroma's `where`. Lexical hits are
            # already in-domain (pre-RRF filter), so this is a no-op on them.
            # Unfiltered: in_domain_paths is None => never applied.
            if (
                in_domain_paths is not None
                and chunk.relative_path not in in_domain_paths
            ):
                continue

            snippet = self._make_snippet(chunk.text)
            result = SearchResult(
                chunk_id=chunk_id,
                score=score,
                vector_rank=vrank,
                lexical_rank=lrank,
                relative_path=chunk.relative_path,
                language=chunk.language,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                symbol_path=chunk.symbol_path,
                snippet=snippet,
            )

            # Tie-break: best (smallest) available rank, then path.
            available = [r for r in (vrank, lrank) if r is not None]
            best_rank = min(available) if available else 10**9

            scored.append((score, best_rank, chunk.relative_path, result))

        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [item[3] for item in scored[:effective_limit]]


__all__ = ["SearchEngine", "sanitize_fts_query"]
