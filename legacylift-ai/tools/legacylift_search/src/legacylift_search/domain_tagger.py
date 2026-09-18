"""Deterministic domain tagging: ingest `domains.json`, resolve globs to
per-file domain rows, and stamp Chroma metadata.

Milestone 4 of `docs/exec-plans/pending/domain-enhancements-plan.md`.

`tag-domains` is the single reconcile point for every durable domain row —
authored (`domains`/`domain_edges`) and derived (`file_domains`). It is
idempotent: re-running converges to the same logical state. The reconcile
order inside `DomainTagger.tag` (issues #38/#41) is:

    1. INSERT OR REPLACE the authored tables from `domains.json`.
    2. Reap authored `domains`/`domain_edges` rows absent from the ingest,
       printing a notice naming dropped domains + reclassified-file counts.
    3. Resolve every discovered file against the SURVIVING globs and write
       `file_domains` (`source='glob'`; unmatched -> explicit
       `domain='unassigned'` rows), honoring manual-wins for live files.
    4. Reap `file_domains` rows for ANY undiscovered path regardless of
       `source`, INCLUDING `manual` (a deleted file has no live decision to
       protect, issue #42).

Finally it stamps each chunk's Chroma `domain` metadata from the
authoritative `file_domains` row (glob/manual/unassigned alike) with no
re-embedding — chromadb 1.5.9 MERGES the `domain` key into the existing
metadata (verified — see the plan's "Surprises & Discoveries").
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pathspec
from pydantic import BaseModel, ConfigDict, Field, field_validator

from legacylift_search.cli_helpers import print_resolved_path
from legacylift_search.config import (
    Manifest,
    resolve_index_dir,
    resolve_knowledge_dir,
)
from legacylift_search.discovery import discover_source_files
from legacylift_search.knowledge_store import KnowledgeStore
from legacylift_search.models import DomainEdgeRecord, DomainRecord
from legacylift_search.store import SQLiteStore

logger = logging.getLogger(__name__)

RESERVED_UNASSIGNED = "unassigned"

# The excluded-by-design tier: a file matching an authored `exclude_globs`
# pattern (and no domain glob) carries this reserved `file_domains.domain`
# value instead of `unassigned`. Like `unassigned` it is NEVER a `domains`
# row — it is a file_domains value only. Semantics: "intentionally not a
# business capability" (tests, ops/DBA scripts, generated code) — dropped
# from the coverage denominator and never a "re-run assess" gap.
RESERVED_EXCLUDED = "excluded"

# Shared/Core cross-cutting domain detection is by reserved slug, not a
# schema flag (issue #20) — exact kebab-case match against the same slugs
# assess authors.
RESERVED_SHARED_CORE = {"shared", "core"}


class DomainEdgeInput(BaseModel):
    """An inter-domain edge as authored in `domains.json`.

    JSON keys are `"from"`/`"to"`; `from` is a Python keyword, so the fields
    are `from_`/`to_` with aliases and `populate_by_name=True`. `kind` is
    optional in the file and MUST default to `""` (never `None`) to match the
    `domain_edges.kind NOT NULL DEFAULT ''` column (issue #51) — otherwise
    ingest of a `None` kind violates NOT NULL and the two M8 render sources
    diverge on edge labels.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to_: str = Field(alias="to")
    kind: str = ""
    evidence: str | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def _coerce_none_kind(cls, v: object) -> object:
        # A missing key uses the default ""; an explicit null coerces to "".
        return "" if v is None else v


class DomainsFile(BaseModel):
    """A parsed, schema-validated `domains.json` (Milestone 3 schema).

    `load_domains_json` doubles as the Milestone 3 validator. `domains` is a
    list of `DomainRecord` whose declaration order IS the glob precedence
    order — `display_order` is assigned from the array index at ingest, so
    the SQLite `list_domains()` ordering (issue #14) agrees with this order.
    """

    schema_version: int
    assess_run_id: str | None = None
    domains: list[DomainRecord] = []
    edges: list[DomainEdgeInput] = []
    # Excluded-by-design tier (optional). Globs for files that are
    # intentionally NOT a business capability (tests, ops/DBA scripts,
    # generated code). A file matching one of these and NO domain glob is
    # tagged `domain='excluded'` rather than `unassigned`. Domain globs win
    # over exclusions (exclusion only claims otherwise-unassigned files), so
    # a too-broad exclusion can never hide a domain file.
    exclude_globs: list[str] = []
    # Third-party provenance globs (Q27 of the gap-detection decision record):
    # vendored libraries and other not-this-codebase content. Distinct from
    # exclude_globs, which is first-party content excluded by choice.
    # Additive/optional — no schema_version bump, no migration. Read directly
    # by `legacylift_search.gaps.walk_repository`; nothing in the domain-
    # tagging path (this module) consumes it yet.
    vendored_globs: list[str] = []
    # Identity tokens (case-insensitive substrings) that mark a declared
    # <uri>/targetNamespace/PUBLIC identity as first-party (e.g. the client's
    # own domain). Additive/optional, same rationale as vendored_globs.
    own_identities: list[str] = []


def load_domains_json(path: Path) -> DomainsFile:
    """Parse and schema-validate a `domains.json` file.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the JSON is malformed or fails schema validation.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"domains.json not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in domains file {path}: {e}") from e
    try:
        return DomainsFile.model_validate(data)
    except Exception as e:
        raise ValueError(f"Invalid domains.json schema in {path}: {e}") from e


def resolve_file_domains(
    files: list[str],
    domains: list[DomainRecord],
    exclude_globs: list[str] | None = None,
) -> dict[str, tuple[str, float]]:
    """Resolve each file to `(domain_id, confidence)` against ordered globs.

    Precedence is the ORDER of the `domains` argument (first matching domain
    wins). The resolver does NOT re-sort — it trusts the caller order (issue
    #14); both callers pass `domains` in `display_order` (`tag-domains` uses
    the `domains.json` array order, the indexer uses `list_domains()`). Globs
    are matched with `pathspec`'s GitWildMatch engine (NOT `fnmatch`),
    matching how the discovery layer (`discovery.py`) treats path patterns.
    The spec name `"gitignore"` is the non-deprecated spelling of the same
    `GitWildMatchPattern` the plan calls "gitwildmatch".

    If a later domain also matches a file, a warning naming the file and both
    domains is logged (ambiguity is a data-quality signal), but the first
    match still wins.

    Files matching no domain fall through to the excluded-by-design tier:
    if `exclude_globs` is given and the file matches one, it maps to
    `("excluded", 1.0)`; otherwise `("unassigned", 1.0)`. **Domains win over
    exclusions** — exclusion only reclassifies files no domain claimed, so a
    broad exclusion can never hide a domain file.
    """
    specs = [
        (d.domain_id, pathspec.PathSpec.from_lines("gitignore", d.path_globs))
        for d in domains
    ]
    exclude_spec = (
        pathspec.PathSpec.from_lines("gitignore", exclude_globs)
        if exclude_globs
        else None
    )
    result: dict[str, tuple[str, float]] = {}
    for f in files:
        winner: str | None = None
        for domain_id, spec in specs:
            if spec.match_file(f):
                if winner is None:
                    winner = domain_id
                else:
                    logger.warning(
                        "file %s matches multiple domains: %s (wins) and %s "
                        "— ambiguous glob coverage",
                        f,
                        winner,
                        domain_id,
                    )
        if winner is not None:
            result[f] = (winner, 1.0)
        elif exclude_spec is not None and exclude_spec.match_file(f):
            result[f] = (RESERVED_EXCLUDED, 1.0)
        else:
            result[f] = (RESERVED_UNASSIGNED, 1.0)
    return result


def domains_file_to_records(
    df: DomainsFile,
) -> tuple[list[DomainRecord], list[DomainEdgeRecord]]:
    """Adapt a parsed `domains.json` (`DomainsFile`) to the same uniform shape
    `render_architecture_mermaid` receives from the SQLite source (issue #36).

    `DomainsFile.domains` entries are already `DomainRecord`s (the Milestone 3
    schema reuses that model), but the JSON carries no `display_order` — this
    assigns it from the array index, exactly as `DomainTagger.tag` does at
    ingest (issue #14), so `list_domains()` (SQLite) and this adapted list
    (JSON) sort identically for identical input.

    `DomainsFile.edges` entries are `DomainEdgeInput` (JSON keys `from`/`to`,
    Python attrs `from_`/`to_`) — mapped here onto `DomainEdgeRecord`'s
    `from_domain`/`to_domain` field names, and deduplicated on the
    `(from_domain, to_domain, kind)` triple (issue #56) to match
    `domain_edges`'s PRIMARY KEY, which silently collapses a repeated edge at
    ingest time. The JSON `edges` array does not dedup on its own, so without
    this the JSON-source render can emit two arrows where the SQLite-source
    render emits one, breaking the Milestone 8 byte-identity guarantee.
    """
    domains = [
        d.model_copy(update={"display_order": i}) for i, d in enumerate(df.domains)
    ]
    seen: set[tuple[str, str, str]] = set()
    edges: list[DomainEdgeRecord] = []
    for e in df.edges:
        key = (e.from_, e.to_, e.kind)
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            DomainEdgeRecord(
                from_domain=e.from_, to_domain=e.to_, kind=e.kind, evidence=e.evidence
            )
        )
    return domains, edges


def _mermaid_label(text: str) -> str:
    """Escape a label for safe embedding inside a double-quoted Mermaid label."""
    return text.replace("\\", "\\\\").replace('"', "&quot;")


def render_architecture_mermaid(
    domains: list[DomainRecord], edges: list[DomainEdgeRecord]
) -> str:
    """Render a deterministic Mermaid `graph TD` from domain nodes + edges.

    Milestone 8. Takes ONE uniform shape regardless of source — SQLite's
    `DomainRecord`/`DomainEdgeRecord` (from `list_domains()`/
    `get_domain_edges()`), or a `domains.json` adapted via
    `domains_file_to_records` — so identical domain/edge data renders
    byte-identically no matter which source fed it:

    - Excludes the reserved `unassigned` slug (issue #28), belt-and-
      suspenders even though neither source ever actually carries it
      (`list_domains()` never returns it; `domains.json` never lists it).
    - Drops any edge whose `from`/`to` is not among the emitted domain nodes
      (issue #36) — `domain_edges` has no foreign key, and an edge authored
      against an unlisted domain (or the excluded `unassigned` slug, as a
      subcase) would otherwise make Mermaid auto-create a phantom node.
    - Detects a Shared/Core cross-cutting domain by the reserved slug
      `{"shared", "core"}` (exact match, issue #20) and renders it with a
      distinct (stadium) node shape to mark it visually as cross-cutting;
      every other domain renders as an ordinary rectangular node. No
      dependency arrows are invented for it — edges render exactly as given,
      whether or not one touches the cross-cutting node.
    - Sorts nodes by `(display_order, domain_id)` and edges lexically by
      `(from_domain, to_domain, kind)` so the output is stable and does not
      depend on the iteration order of the input lists.
    """
    nodes = sorted(
        (
            d
            for d in domains
            if d.domain_id not in (RESERVED_UNASSIGNED, RESERVED_EXCLUDED)
        ),
        key=lambda d: (d.display_order, d.domain_id),
    )
    node_ids = {d.domain_id for d in nodes}

    valid_edges = sorted(
        (e for e in edges if e.from_domain in node_ids and e.to_domain in node_ids),
        key=lambda e: (e.from_domain, e.to_domain, e.kind),
    )

    lines = ["graph TD"]
    for d in nodes:
        label = _mermaid_label(d.name)
        if d.domain_id in RESERVED_SHARED_CORE:
            lines.append(f'    {d.domain_id}(["{label}"])')
        else:
            lines.append(f'    {d.domain_id}["{label}"]')
    for e in valid_edges:
        if e.kind:
            lines.append(
                f"    {e.from_domain} -->|{_mermaid_label(e.kind)}| {e.to_domain}"
            )
        else:
            lines.append(f"    {e.from_domain} --> {e.to_domain}")
    return "\n".join(lines) + "\n"


@dataclass
class TagStats:
    """Outcome of a `DomainTagger.tag` run, for the CLI to report.

    Carries the manual-override count/paths (issue #3) and the authored-table
    reap result (issue #41): the names of dropped domains and, per dropped
    domain, how many files were reclassified off it.
    """

    domains_ingested: int = 0
    edges_ingested: int = 0
    files_resolved: int = 0
    glob_count: int = 0
    unassigned_count: int = 0
    manual_preserved: list[str] = field(default_factory=list)
    dropped_domains: list[str] = field(default_factory=list)
    reclassified_counts: dict[str, int] = field(default_factory=dict)
    file_rows_reaped: int = 0
    chunks_stamped: int = 0
    excluded_count: int = 0


class DomainTagger:
    """Ingest `domains.json` and reconcile the durable domain rows + Chroma.

    Reused by the indexer's 7-Auto (Milestone 5) via the module-level
    `resolve_file_domains`; the `tag` method is the `tag-domains` command's
    whole implementation.
    """

    def __init__(self, manifest: Manifest) -> None:
        self.manifest = manifest

    def tag(self, repo_root: Path, domains_json: Path) -> TagStats:
        """Run the full ingest -> resolve -> stamp reconcile.

        Args:
            repo_root: resolved repository root (must match the globs'
                repo-relative anchoring — see Milestone 3, issue #40).
            domains_json: path to the `domains.json` to ingest.

        Raises:
            FileNotFoundError: if no code-search index exists (issue #39) or
                `domains.json` is missing.
            ValueError: if `domains.json` fails schema validation.
        """
        repo_root = Path(repo_root).resolve()

        # Missing index (issue #39): the stamp step reads chunk ids from
        # index.sqlite. Fail clearly BEFORE any lookup rather than throwing on
        # the first chunk-id query.
        index_dir = resolve_index_dir(repo_root, self.manifest)
        print_resolved_path("index directory", index_dir)
        index_sqlite = index_dir / self.manifest.index.sqlite_file
        if not index_sqlite.exists():
            raise FileNotFoundError(
                f"no code-search index found at {index_sqlite} — "
                f"run `legacylift-search index` first"
            )

        df = load_domains_json(domains_json)

        knowledge_dir = resolve_knowledge_dir(repo_root, self.manifest)
        print_resolved_path("knowledge directory", knowledge_dir)
        knowledge_sqlite = knowledge_dir / "knowledge.sqlite"
        ks = KnowledgeStore(knowledge_sqlite)
        index_store: SQLiteStore | None = None
        stats = TagStats()
        try:
            conn = ks._connect()

            # Snapshot pre-existing state for the reap report.
            pre_file_counts = ks.domain_file_counts()
            pre_domain_ids = {
                row["domain_id"]
                for row in conn.execute("SELECT domain_id FROM domains").fetchall()
            }

            # (1) INSERT OR REPLACE authored tables from domains.json.
            ingested_domain_ids = [d.domain_id for d in df.domains]
            for order, d in enumerate(df.domains):
                ks.upsert_domain(
                    d.domain_id,
                    d.name,
                    d.description,
                    d.path_globs,
                    df.assess_run_id,
                    order,
                )
            ingested_edge_keys = [
                (e.from_, e.to_, e.kind) for e in df.edges
            ]
            for e in df.edges:
                ks.upsert_domain_edge(e.from_, e.to_, e.kind, e.evidence)
            stats.domains_ingested = len(ingested_domain_ids)
            stats.edges_ingested = len(df.edges)

            # Ingest the excluded-by-design glob set (replace-all, like the
            # authored domains). Persisted so the indexer's incremental 7-Auto
            # honors exclusions on newly-added files with no `tag-domains` run.
            ks.set_exclusions(df.exclude_globs)

            # (2) Reap authored rows absent from the ingest (issue #41).
            dropped = sorted(pre_domain_ids - set(ingested_domain_ids))
            stats.dropped_domains = dropped
            stats.reclassified_counts = {
                d: pre_file_counts.get(d, 0) for d in dropped
            }
            self._reap_authored_domains(conn, ingested_domain_ids)
            self._reap_authored_edges(conn, ingested_edge_keys)
            conn.commit()

            # (3) Resolve every discovered file against the SURVIVING globs
            # and write file_domains, honoring manual-wins for live files.
            discovered = [
                sf.relative_path
                for sf in discover_source_files(repo_root, self.manifest)
            ]
            discovered_set = set(discovered)
            surviving = ks.list_domains()  # display_order-sorted (issue #14)
            resolved = resolve_file_domains(
                discovered, surviving, df.exclude_globs
            )

            manual_rows = {
                row["relative_path"]
                for row in conn.execute(
                    "SELECT relative_path FROM file_domains WHERE source='manual'"
                ).fetchall()
            }
            for rel_path, (domain_id, conf) in resolved.items():
                if rel_path in manual_rows:
                    # manual-wins: never overwrite a live human decision.
                    continue
                ks.upsert_file_domain(
                    rel_path, domain_id, "glob", df.assess_run_id, conf
                )

            stats.files_resolved = len(resolved)
            stats.unassigned_count = sum(
                1
                for p, (d, _c) in resolved.items()
                if p not in manual_rows and d == RESERVED_UNASSIGNED
            )
            stats.excluded_count = sum(
                1
                for p, (d, _c) in resolved.items()
                if p not in manual_rows and d == RESERVED_EXCLUDED
            )
            stats.glob_count = sum(
                1
                for p, (d, _c) in resolved.items()
                if p not in manual_rows
                and d not in (RESERVED_UNASSIGNED, RESERVED_EXCLUDED)
            )
            stats.manual_preserved = sorted(
                p for p in manual_rows if p in discovered_set
            )

            # (4) Reap file_domains rows for ANY undiscovered path,
            # regardless of source, INCLUDING manual (issues #38/#42).
            stats.file_rows_reaped = self._reap_undiscovered_files(
                conn, discovered
            )
            conn.commit()

            # Stamp Chroma from the authoritative file_domains rows.
            #
            # Opened through SQLiteStore rather than sqlite3.connect: this is
            # a READ PATH on index.sqlite, and CR-01's open-time migration
            # only fires for connections SQLiteStore opens. A raw connect was
            # harmless while it read nothing but `chunks`/`vectors_present`,
            # but from INDEX_MIGRATIONS version 2 onward it would be a read
            # path that never advances the schema -- the exact asymmetry
            # CR-01 was raised to remove.
            index_store = SQLiteStore(index_sqlite)
            stats.chunks_stamped = self._stamp_chroma(
                ks,
                index_store.connection(),
                index_dir,
                self.manifest.index.collection_name,
            )
            # _stamp_chroma opens/closes its own ChromaVectorStore.
        finally:
            if index_store is not None:
                index_store.close()
            ks.close()

        return stats

    # ------------------------------------------------------------------
    # Reap helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reap_authored_domains(
        conn: sqlite3.Connection, ingested_ids: list[str]
    ) -> None:
        if ingested_ids:
            placeholders = ",".join("?" for _ in ingested_ids)
            conn.execute(
                f"DELETE FROM domains WHERE domain_id NOT IN ({placeholders})",
                ingested_ids,
            )
        else:
            conn.execute("DELETE FROM domains")

    @staticmethod
    def _reap_authored_edges(
        conn: sqlite3.Connection, ingested_keys: list[tuple[str, str, str]]
    ) -> None:
        if ingested_keys:
            placeholders = ",".join("(?,?,?)" for _ in ingested_keys)
            params: list[str] = []
            for k in ingested_keys:
                params.extend(k)
            conn.execute(
                "DELETE FROM domain_edges WHERE "
                f"(from_domain, to_domain, kind) NOT IN ({placeholders})",
                params,
            )
        else:
            conn.execute("DELETE FROM domain_edges")

    @staticmethod
    def _reap_undiscovered_files(
        conn: sqlite3.Connection, discovered: list[str]
    ) -> int:
        """Delete every file_domains row whose path is no longer discovered,
        regardless of source (including `manual`, issues #38/#42).

        Computes the stale set in Python (bounded by the number of dropped
        rows, usually small) rather than a giant `NOT IN (<all discovered>)`
        clause, which could exceed SQLite's bound-variable limit at scale.
        """
        discovered_set = set(discovered)
        existing = [
            row[0]
            for row in conn.execute(
                "SELECT relative_path FROM file_domains"
            ).fetchall()
        ]
        stale = [p for p in existing if p not in discovered_set]
        for i in range(0, len(stale), 500):
            batch = stale[i : i + 500]
            placeholders = ",".join("?" for _ in batch)
            conn.execute(
                f"DELETE FROM file_domains WHERE relative_path IN ({placeholders})",
                batch,
            )
        return len(stale)

    # ------------------------------------------------------------------
    # Chroma stamping
    # ------------------------------------------------------------------

    @staticmethod
    def _stamp_chroma(
        ks: KnowledgeStore,
        index_conn: sqlite3.Connection,
        index_dir: Path,
        collection_name: str,
    ) -> int:
        """Stamp each chunk's Chroma `domain` metadata from its file's row.

        Stamps from the AUTHORITATIVE `file_domains` row for every file
        (glob/manual/unassigned alike). Restricts to embedded chunks via the
        `vectors_present` cache (issue #15) — below-`embed_min_tokens` chunks
        never reach Chroma, so `SELECT id FROM chunks` can return ids that
        were never upserted. Returns the number of chunk ids stamped.
        """
        from legacylift_search.embeddings import HashEmbedder
        from legacylift_search.vector_store import ChromaVectorStore

        conn = ks._connect()
        file_rows = conn.execute(
            "SELECT relative_path, domain FROM file_domains"
        ).fetchall()
        if not file_rows:
            return 0

        # Which chunk ids are actually embedded (issue #15)?
        present = {
            row[0]
            for row in index_conn.execute(
                "SELECT chunk_id FROM vectors_present"
            ).fetchall()
        }
        # path -> [embedded chunk ids]
        path_to_chunks: dict[str, list[str]] = defaultdict(list)
        for cid, rel_path in index_conn.execute(
            "SELECT id, relative_path FROM chunks"
        ).fetchall():
            if cid in present:
                path_to_chunks[rel_path].append(cid)

        # Aggregate chunk ids by their file's authoritative domain.
        domain_to_chunks: dict[str, list[str]] = defaultdict(list)
        for row in file_rows:
            rel_path = row["relative_path"]
            domain = row["domain"]
            domain_to_chunks[domain].extend(path_to_chunks.get(rel_path, []))

        # Determine the collection's dimension for a probe embedder (metadata
        # updates never embed, so the value only affects a brand-new
        # collection's stored metadata; the collection already exists here).
        dim_row = index_conn.execute(
            "SELECT value FROM index_metadata WHERE key='embedding_dimension'"
        ).fetchone()
        try:
            dim = int(dim_row[0]) if dim_row else 64
        except (ValueError, TypeError):
            dim = 64

        chroma_path = index_dir / "chroma"
        if not chroma_path.exists():
            logger.warning(
                "no Chroma store at %s — skipping domain metadata stamp",
                chroma_path,
            )
            return 0

        stamped = 0
        vector_store = ChromaVectorStore(
            base_dir=index_dir,
            collection_name=collection_name,
            embedder=HashEmbedder(dimension=dim),
            metadata={},
        )
        try:
            for domain, chunk_ids in domain_to_chunks.items():
                if not chunk_ids:
                    continue
                vector_store.update_domain_metadata(chunk_ids, domain)
                stamped += len(chunk_ids)
        finally:
            vector_store.close()
        return stamped


__all__ = [
    "DomainsFile",
    "DomainEdgeInput",
    "load_domains_json",
    "resolve_file_domains",
    "domains_file_to_records",
    "render_architecture_mermaid",
    "DomainTagger",
    "TagStats",
]
