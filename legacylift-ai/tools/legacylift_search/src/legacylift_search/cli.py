"""Typer CLI shell for legacylift-search.

This module is intentionally thin. Each command is a stub during Wave 1;
business logic will be implemented in later milestones in dedicated modules
(see docs/exec-plans/active/semantic-code-search-graph-index.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer

app = typer.Typer(
    name="legacylift-search",
    help="Local semantic, lexical, and graph code search indexer for LegacyLift.",
    no_args_is_help=True,
    add_completion=False,
)

# Milestone 1 Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`: the
# `requirements` command group, and **the first `app.add_typer` in this
# file**. Every other command here is a flat `@app.command` registration, so
# there is no precedent to copy for the sub-app wiring itself.
#
# The sub-app namespaces three names that already exist at top level --
# `validate`, `search` and `stats` -- which is deliberate and is not a
# collision: `legacylift-search stats` and `legacylift-search requirements
# stats` are different commands over different stores. The Python function
# names cannot collide either, because the sub-app's live in
# `legacylift_search.cli_requirements`, not in this module.
#
# The import is at module scope rather than inside a function, unlike almost
# every other import in this file. Those are deferred to keep `--help` fast
# by not importing `rich`, `chromadb` or the extractors; `cli_requirements`
# imports only `typer` at module scope and defers the rest the same way, so
# it costs nothing here -- and a sub-app cannot be registered lazily, since
# the registration is what makes the group appear in `--help` at all.
from legacylift_search.cli_requirements import requirements_app

app.add_typer(requirements_app, name="requirements")


def _not_implemented(command: str) -> None:
    typer.echo(
        f"[legacylift-search] '{command}' is not yet implemented. "
        f"See docs/exec-plans/active/semantic-code-search-graph-index.md."
    )


# managed by Agent A1
@app.command("init-config")
def init_config(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root", help="Target repository root."),
    output: Optional[Path] = typer.Option(None, "--output", help="Manifest output path."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if manifest exists."),
) -> None:
    """Write a default semantic-search.manifest.json (Milestone 2)."""
    from legacylift_search.config import write_default_manifest

    # Determine the manifest output path
    if output:
        manifest_path = output
    elif repo_root:
        manifest_path = repo_root / "semantic-search.manifest.json"
    else:
        manifest_path = Path("semantic-search.manifest.json")

    try:
        write_default_manifest(manifest_path, overwrite=overwrite)
        typer.echo(f"[legacylift-search] Wrote default manifest to {manifest_path}")
    except FileExistsError as e:
        typer.echo(f"[legacylift-search] Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"[legacylift-search] Failed to write manifest: {e}", err=True)
        raise typer.Exit(code=1)


# managed by Agent C2
@app.command("index")
def index(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    reset: bool = typer.Option(False, "--reset"),
    embedding_provider: Optional[str] = typer.Option(None, "--embedding-provider"),
) -> None:
    """Build the SQLite + Chroma index for a repository (Milestone 10)."""
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.config import apply_path_overrides, load_manifest
    from legacylift_search.indexer import Indexer

    console = Console()

    # Resolve repo root
    resolved_repo_root = (repo_root or Path(".")).resolve()
    if not resolved_repo_root.exists():
        console.print(
            f"[red]repo-root does not exist: {resolved_repo_root}[/red]"
        )
        raise typer.Exit(code=1)

    # Resolve config path
    config_path = config or (resolved_repo_root / "semantic-search.manifest.json")

    # Load (or default) manifest
    try:
        if config_path.exists():
            manifest = load_manifest(config_path)
        else:
            from legacylift_search.config import Manifest

            manifest = Manifest()
    except Exception as exc:
        console.print(f"[red]Failed to load manifest: {exc}[/red]")
        raise typer.Exit(code=1)

    # Apply --index-dir / --analysis-dir overrides
    # Both flags go through the ONE precedence point (CR-02/03/04). It
    # .resolve()s each, so a FLAG always means "relative to the current
    # working directory", the way any other CLI path argument does, on every
    # command that offers it -- --index-dir included, which this site used to
    # store verbatim and so read as repo_root-relative here and CWD-relative
    # on `stats`. A relative value in the MANIFEST still resolves against
    # repo_root; that is the documented split.
    apply_path_overrides(manifest, index_dir, analysis_dir)

    try:
        indexer = Indexer(manifest, resolved_repo_root)
        stats = indexer.run(
            reset=reset,
            embedding_provider_override=embedding_provider,
        )
    except Exception as exc:
        console.print(f"[red]Indexing failed: {exc}[/red]")
        raise typer.Exit(code=1)

    table = Table(title="Index Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("files_indexed", str(stats.files_indexed))
    table.add_row("chunk_count", str(stats.chunk_count))
    table.add_row("symbol_count", str(stats.symbol_count))
    table.add_row("ref_count", str(stats.ref_count))
    table.add_row("graph_edge_count", str(stats.graph_edge_count))
    table.add_row("fact_count", str(stats.fact_count))
    table.add_row("embedder", stats.embedder_name)
    table.add_row("embedding_dimension", str(stats.embedding_dimension))
    table.add_row("index_dir", stats.index_dir)
    console.print(table)


# managed by Agent C2
@app.command("backfill-vectors")
def backfill_vectors(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    embedding_provider: Optional[str] = typer.Option(None, "--embedding-provider"),
) -> None:
    """Embed and upsert only the chunks missing from Chroma (resumable).

    Drives the embed/upsert phase off the SQLite `chunks` table filtered
    against the `vectors_present` cache, so it processes only chunks not yet
    in Chroma and is safe to call repeatedly. Use this to complete an
    interrupted `index --reset` run: under the skip-on-unchanged fast path a
    plain rerun feeds nothing to the embedder, whereas backfill-vectors makes
    monotonic forward progress until `vectors_upserted == chunk_count`.
    """
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.config import (
        Manifest,
        apply_path_overrides,
        load_manifest,
    )
    from legacylift_search.indexer import Indexer

    console = Console()

    resolved_repo_root = (repo_root or Path(".")).resolve()
    if not resolved_repo_root.exists():
        console.print(
            f"[red]repo-root does not exist: {resolved_repo_root}[/red]"
        )
        raise typer.Exit(code=1)

    config_path = config or (
        resolved_repo_root / "semantic-search.manifest.json"
    )

    try:
        if config_path.exists():
            manifest = load_manifest(config_path)
        else:
            manifest = Manifest()
    except Exception as exc:
        console.print(f"[red]Failed to load manifest: {exc}[/red]")
        raise typer.Exit(code=1)

    # Both flags go through the ONE precedence point (CR-02/03/04). It
    # .resolve()s each, so a FLAG always means "relative to the current
    # working directory", the way any other CLI path argument does, on every
    # command that offers it -- --index-dir included, which this site used to
    # store verbatim and so read as repo_root-relative here and CWD-relative
    # on `stats`. A relative value in the MANIFEST still resolves against
    # repo_root; that is the documented split.
    apply_path_overrides(manifest, index_dir, analysis_dir)

    try:
        indexer = Indexer(manifest, resolved_repo_root)
        stats = indexer.backfill_vectors(
            embedding_provider_override=embedding_provider,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]Backfill failed: {exc}[/red]")
        raise typer.Exit(code=1)

    table = Table(title="Backfill Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("chunks_missing", str(stats.chunks_missing))
    table.add_row("vectors_backfilled", str(stats.vectors_backfilled))
    table.add_row(
        "vectors_upserted_total", str(stats.vectors_upserted_total)
    )
    table.add_row("chunk_count", str(stats.chunk_count))
    table.add_row("embedder", stats.embedder_name)
    table.add_row("embedding_dimension", str(stats.embedding_dimension))
    table.add_row("index_dir", stats.index_dir)
    console.print(table)

    if stats.vectors_upserted_total >= stats.chunk_count:
        console.print("[green]Vector coverage complete.[/green]")
    else:
        console.print(
            f"[yellow]Vector coverage incomplete: "
            f"{stats.vectors_upserted_total}/{stats.chunk_count}. "
            f"Re-run `legacylift-search backfill-vectors --repo-root "
            f"{resolved_repo_root}` to continue.[/yellow]"
        )


@app.command("backfill-hashes")
def backfill_hashes(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
) -> None:
    """Hash the entity bodies of symbols whose content_hash is still NULL.

    Milestone 1 Step 2. The version-2 migration adds `symbols.content_hash`
    and leaves it NULL, because the body text is not stored in `symbols` and
    on an existing index the file on disk may no longer be the file that was
    indexed. This is the repair command that fills it in -- resumable,
    processes only what is missing, and safe to call repeatedly.

    A plain `index` rerun will NOT do this: the skip-on-unchanged fast path
    never revisits an unchanged file, so those symbols would stay NULL
    forever. For each unhashed row this checks that the file's current
    on-disk sha256 still equals the indexed one; if it does the body is
    hashed, and if it does not the row is left NULL for the next real `index`
    run, which re-extracts the file because a drifted file is a changed file.
    """
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.config import (
        Manifest,
        apply_path_overrides,
        load_manifest,
    )
    from legacylift_search.indexer import Indexer

    console = Console()

    resolved_repo_root = (repo_root or Path(".")).resolve()
    if not resolved_repo_root.exists():
        console.print(
            f"[red]repo-root does not exist: {resolved_repo_root}[/red]"
        )
        raise typer.Exit(code=1)

    config_path = config or (
        resolved_repo_root / "semantic-search.manifest.json"
    )

    try:
        if config_path.exists():
            manifest = load_manifest(config_path)
        else:
            manifest = Manifest()
    except Exception as exc:
        console.print(f"[red]Failed to load manifest: {exc}[/red]")
        raise typer.Exit(code=1)

    # Both flags go through the ONE precedence point (CR-02/03/04), exactly
    # as `index` and `backfill-vectors` do.
    apply_path_overrides(manifest, index_dir, analysis_dir)

    try:
        indexer = Indexer(manifest, resolved_repo_root)
        stats = indexer.backfill_hashes()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[red]Backfill failed: {exc}[/red]")
        raise typer.Exit(code=1)

    table = Table(title="Content-Hash Backfill Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("symbols_missing", str(stats.symbols_missing))
    table.add_row("symbols_hashed", str(stats.symbols_hashed))
    table.add_row("symbols_skipped", str(stats.symbols_skipped))
    table.add_row("files_verified", str(stats.files_verified))
    table.add_row("files_drifted", str(stats.files_drifted))
    table.add_row("files_unreadable", str(stats.files_unreadable))
    table.add_row("symbols_unhashable", str(stats.symbols_unhashable))
    table.add_row("remaining_null", str(stats.remaining_null))
    table.add_row("symbol_count", str(stats.symbol_count))
    table.add_row("index_dir", stats.index_dir)
    console.print(table)

    if stats.remaining_null == 0:
        console.print("[green]Every symbol has a content hash.[/green]")
    else:
        # Not a warning about this command: the skipped rows are exactly the
        # ones whose source changed, and re-indexing is what fixes them.
        console.print(
            f"[yellow]{stats.remaining_null} symbols are still unhashed "
            f"({stats.files_drifted} files drifted since indexing, "
            f"{stats.files_unreadable} unreadable). Run `legacylift-search "
            f"index --repo-root {resolved_repo_root}` to re-extract the "
            f"changed files, which hashes them on the insert path.[/yellow]"
        )


def _print_domain_freshness(
    ks,
    records: list,
    discovered_paths: set,
) -> None:
    """Print the Milestone 7 domains freshness line(s) for `validate`.

    Conceptual model (plan Milestone 7 + the excluded-by-design tier):
    **untagged** = a discovered file with NO `file_domains` row at all — the
    staleness signal. **unassigned** = a discovered file whose row IS the
    reserved `unassigned` domain — an ACCEPTED coverage gap ("your globs
    missed a domain file"), reported as coverage info, never staleness.
    **excluded** = a discovered file whose row IS the reserved `excluded`
    domain — intentionally NOT a business capability (tests, ops SQL,
    generated code). `domains: stale` iff `untagged > 0`; `domains: fresh`
    iff `untagged == 0`, regardless of unassigned/excluded counts.

    Coverage is honest about intent: excluded files are dropped from the
    denominator, so `coverage = classified / (|discovered| - |excluded|)` —
    "of the files that ought to belong to a capability, how many are tagged."
    Only `unassigned` (never `excluded`) triggers the "re-run assess" hint.

    All count buckets are computed over `rows_present` — the raw
    `file_domains` table restricted to the discovered set (issue #42), a
    defensive intersect for the window between reconciles (e.g. a ghost
    row surviving a `--reset`, issue #55). The partition is exact:
    `classified + unassigned + excluded + untagged == |discovered|`.
    """
    from legacylift_search.domain_tagger import resolve_file_domains

    conn = ks._connect()
    rows = {
        row["relative_path"]: (row["domain"], row["source"])
        for row in conn.execute(
            "SELECT relative_path, domain, source FROM file_domains"
        ).fetchall()
    }
    rows_present = {p: v for p, v in rows.items() if p in discovered_paths}

    untagged_paths = sorted(discovered_paths - set(rows_present.keys()))
    _reserved = ("unassigned", "excluded")
    classified = [p for p, (d, _s) in rows_present.items() if d not in _reserved]
    unassigned = [p for p, (d, _s) in rows_present.items() if d == "unassigned"]
    excluded = [p for p, (d, _s) in rows_present.items() if d == "excluded"]
    manual = [p for p, (_d, s) in rows_present.items() if s == "manual"]

    # Excluded-by-design files leave the coverage denominator: coverage now
    # measures only files that OUGHT to be classified (issue: unassigned
    # overloaded "gap" vs "out-of-scope").
    coverage_denom = max(1, len(discovered_paths) - len(excluded))
    coverage_pct = (len(classified) / coverage_denom) * 100

    # Split untagged using the shared resolver against the stored,
    # currently-authored domains/globs AND exclusions (issue #14 ordering is
    # preserved: `records` comes from `list_domains()`): glob-matchable (a
    # real domain — reindex classifies it), excludable (an exclusion —
    # reindex marks it excluded, NOT a gap), need-assess (neither — a true
    # coverage gap that a reindex will not fix).
    exclude_globs = ks.list_exclusions()
    resolved = (
        resolve_file_domains(untagged_paths, records, exclude_globs)
        if untagged_paths
        else {}
    )
    glob_matchable = [p for p in untagged_paths if resolved[p][0] not in _reserved]
    excludable = [p for p in untagged_paths if resolved[p][0] == "excluded"]
    need_assess = [p for p in untagged_paths if resolved[p][0] == "unassigned"]

    assess_row = conn.execute(
        "SELECT assess_run_id FROM domains WHERE assess_run_id IS NOT NULL "
        "ORDER BY assess_run_id DESC LIMIT 1"
    ).fetchone()
    assess_run_id = assess_row["assess_run_id"] if assess_row else None

    excl_seg = f" · {len(excluded)} excluded" if excluded else ""
    if untagged_paths:
        untagged_detail = f"{len(glob_matchable)} glob-matchable"
        if excludable:
            untagged_detail += f", {len(excludable)} excludable"
        untagged_detail += f", {len(need_assess)} need assess"
        line = (
            f"domains: stale · coverage {coverage_pct:.0f}% · "
            f"{len(unassigned)} unassigned{excl_seg} · {len(manual)} manual · "
            f"{len(untagged_paths)} untagged ({untagged_detail})"
        )
    else:
        line = (
            f"domains: fresh · coverage {coverage_pct:.0f}% · "
            f"{len(unassigned)} unassigned{excl_seg} · {len(manual)} manual"
        )
    if assess_run_id:
        line += f" · assess run {assess_run_id}"

    # typer.echo, not console.print: rich's Console mangles non-ASCII
    # separators (the middle dot here) on a legacy Windows console without
    # UTF-8 support, whereas Click's echo() encodes correctly (matches the
    # `domains`/`stats` commands' Milestone 2 convention).
    typer.echo(line)

    # Route the coverage gap to a fix (issue #48). The freshness verb is
    # UNCHANGED by this — the gap lives on coverage, not freshness.
    if unassigned:
        typer.echo(
            f"— {len(unassigned)} file(s) unassigned (coverage gap); re-run "
            f"modernize-assess with domain globs that cover them (or author "
            f"a Shared/Common domain), then re-run tag-domains"
        )
    if manual:
        typer.echo(
            f"— {len(manual)} manual override(s) preserved; not overwritten "
            f"by glob resolution"
        )


# managed by Agent D2
@app.command("validate")
def validate(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
) -> None:
    """Validate an existing index (Milestone 12)."""
    from rich.console import Console

    from legacylift_search.cli_helpers import resolve_paths

    console = Console()
    try:
        manifest, resolved_repo_root, resolved_index_dir = resolve_paths(
            repo_root, config, index_dir, analysis_dir
        )
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    sqlite_path = resolved_index_dir / manifest.index.sqlite_file
    chroma_path = resolved_index_dir / manifest.index.chroma_dir

    if not resolved_index_dir.exists():
        console.print(
            f"[red]missing: index directory does not exist: {resolved_index_dir}. "
            f"Run `legacylift-search index --repo-root <path>` first.[/red]"
        )
        raise typer.Exit(code=1)
    if not sqlite_path.exists():
        console.print(
            f"[red]missing: sqlite file not found: {sqlite_path}. "
            f"Run `legacylift-search index --repo-root <path>` first.[/red]"
        )
        raise typer.Exit(code=1)
    if not chroma_path.exists():
        console.print(
            f"[red]missing: chroma directory not found: {chroma_path}. "
            f"Run `legacylift-search index --repo-root <path>` first.[/red]"
        )
        raise typer.Exit(code=1)

    from legacylift_search.store import SQLiteStore

    console.print(f"OK index directory: {resolved_index_dir}")

    store = SQLiteStore(sqlite_path)
    try:
        required = [
            "schema_version",
            "indexed_at",
            "embedder_name",
            "embedding_dimension",
        ]
        missing = [k for k in required if store.get_metadata(k) is None]
        if missing:
            console.print(
                f"[red]missing: required metadata keys: {', '.join(missing)}.[/red]"
            )
            raise typer.Exit(code=1)

        stats = store.stats()
        if stats.chunk_count < 1:
            console.print("[red]missing: no chunks in index.[/red]")
            raise typer.Exit(code=1)

        console.print(
            f"OK sqlite: {stats.chunk_count} chunks, "
            f"{stats.symbol_count} symbols, "
            f"{stats.edge_count} graph edges"
        )

        # Lexical search smoke check.
        try:
            store.search_lexical("a", 1)
        except Exception as exc:
            console.print(f"[red]lexical search failed: {exc}[/red]")
            raise typer.Exit(code=1)
        conn = store._connect()
        row = conn.execute("SELECT COUNT(*) FROM chunk_fts").fetchone()
        if not row or row[0] < 1:
            console.print("[red]missing: chunk_fts has no rows.[/red]")
            raise typer.Exit(code=1)

        # Open Chroma collection and verify dimension consistency.
        embedder_name = store.get_metadata("embedder_name") or ""
        embedding_dim = int(store.get_metadata("embedding_dimension") or "0")

        from legacylift_search.embeddings import HashEmbedder
        from legacylift_search.vector_store import ChromaVectorStore

        probe = HashEmbedder(dimension=embedding_dim or 64)
        try:
            vs = ChromaVectorStore(
                base_dir=resolved_index_dir,
                collection_name=manifest.index.collection_name,
                embedder=probe,
                metadata={},
            )
        except Exception as exc:
            console.print(f"[red]chroma collection failed to open: {exc}[/red]")
            raise typer.Exit(code=1)

        try:
            stored_meta = vs.collection.metadata or {}
            stored_dim_str = stored_meta.get("embedding_dimension")
            stored_dim = int(stored_dim_str) if stored_dim_str is not None else None
        finally:
            vs.close()

        if stored_dim is not None and embedding_dim and stored_dim != embedding_dim:
            console.print(
                f"[red]embedding dimension mismatch: sqlite={embedding_dim} "
                f"chroma={stored_dim}.[/red]"
            )
            raise typer.Exit(code=1)

        console.print(f"OK chroma collection: {manifest.index.collection_name}")
        console.print(f"OK embedding: {embedder_name} dimension={embedding_dim}")
        console.print("OK lexical search")

        # Vector coverage warning (Milestone 15). When vectors_upserted is
        # less than chunk_count, the Chroma collection is missing vectors
        # for some chunks (e.g. an interrupted upsert phase). Surface this
        # explicitly rather than reporting freshness=fresh silently.
        try:
            vectors_upserted = int(
                store.get_metadata("vectors_upserted") or "0"
            )
        except ValueError:
            vectors_upserted = 0
        if vectors_upserted < stats.chunk_count:
            console.print(
                f"[yellow]WARNING: vector coverage incomplete: "
                f"vectors_upserted={vectors_upserted} < "
                f"chunk_count={stats.chunk_count}. "
                f"Re-run `legacylift-search index --repo-root "
                f"{resolved_repo_root}` to backfill missing vectors."
                f"[/yellow]"
            )

        # Freshness check.
        from legacylift_search.discovery import discover_source_files

        stored_source_sha = store.get_metadata("source_set_sha256")
        try:
            files = discover_source_files(resolved_repo_root, manifest)
        except Exception as exc:
            console.print(f"[red]discovery failed: {exc}[/red]")
            raise typer.Exit(code=1)

        import hashlib as _hashlib

        joined = "".join(
            sorted(f"{f.relative_path}\t{f.sha256}\n" for f in files)
        )
        current_sha = _hashlib.sha256(joined.encode("utf-8")).hexdigest()

        if stored_source_sha is None:
            console.print(
                "[yellow]freshness: stale (no source_set_sha256 stored; "
                "run `legacylift-search index --repo-root <path>` to refresh)"
                "[/yellow]"
            )
        elif current_sha == stored_source_sha:
            console.print("freshness: fresh")
        else:
            console.print(
                f"[yellow]freshness: stale ({len(files)} files in current "
                f"discovery; run `legacylift-search index --repo-root "
                f"{resolved_repo_root}` to refresh)[/yellow]"
            )

        # Domain freshness axis (Milestone 7 of domain-enhancements-plan.md).
        # Existence-probe BEFORE constructing KnowledgeStore (issue #33):
        # construction creates the file (and its parent dir) as a side
        # effect, which would defeat the "missing" check and litter an
        # empty DB into an un-tagged repo.
        from legacylift_search.cli_helpers import print_resolved_path
        from legacylift_search.config import resolve_knowledge_dir

        resolved_knowledge_dir = resolve_knowledge_dir(resolved_repo_root, manifest)
        print_resolved_path("knowledge directory", resolved_knowledge_dir)
        knowledge_sqlite_path = resolved_knowledge_dir / "knowledge.sqlite"
        if not knowledge_sqlite_path.exists():
            typer.echo("domains: missing")
        else:
            from legacylift_search.knowledge_store import KnowledgeStore

            ks = KnowledgeStore(knowledge_sqlite_path)
            try:
                domain_records = ks.list_domains()
                # domains: missing per issues #19/#33 when the table is empty
                # too (never tagged), not only when the file is absent.
                if not domain_records:
                    typer.echo("domains: missing")
                else:
                    discovered_paths = {f.relative_path for f in files}
                    _print_domain_freshness(ks, domain_records, discovered_paths)
            finally:
                ks.close()  # release WAL/SHM handles on Windows (issue #52)

        console.print("Index is valid.")
    finally:
        store.close()


# managed by Agent D1
@app.command("search")
def search(
    query: str = typer.Argument(..., help="Free-text query."),
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    limit: Optional[int] = typer.Option(None, "--limit"),
    embedding_provider: Optional[str] = typer.Option(
        None, "--embedding-provider"
    ),
    domain: Optional[str] = typer.Option(
        None,
        "--domain",
        help=(
            "Restrict results to a single capability domain "
            "(exact domain_id slug or case-insensitive display name; "
            'the reserved "Unassigned" is also accepted). '
            "Requires a knowledge store built by `tag-domains`."
        ),
    ),
) -> None:
    """Hybrid (vector + lexical) ranked search (Milestone 11)."""
    from rich.console import Console

    from legacylift_search.cli_helpers import print_resolved_path
    from legacylift_search.config import (
        Manifest,
        apply_path_overrides,
        load_manifest,
        resolve_index_dir,
    )
    from legacylift_search.embeddings import create_embedder
    from legacylift_search.search import SearchEngine
    from legacylift_search.store import SQLiteStore
    from legacylift_search.vector_store import ChromaVectorStore

    console = Console()

    resolved_repo_root = (repo_root or Path(".")).resolve()
    if not resolved_repo_root.exists():
        console.print(
            f"[red]repo-root does not exist: {resolved_repo_root}[/red]"
        )
        raise typer.Exit(code=1)

    config_path = config or (
        resolved_repo_root / "semantic-search.manifest.json"
    )

    try:
        if config_path.exists():
            manifest = load_manifest(config_path)
        else:
            manifest = Manifest()
    except Exception as exc:
        console.print(f"[red]Failed to load manifest: {exc}[/red]")
        raise typer.Exit(code=1)

    # Both flags go through the ONE precedence point (CR-02/03/04). It
    # .resolve()s each, so a FLAG always means "relative to the current
    # working directory", the way any other CLI path argument does, on every
    # command that offers it -- --index-dir included, which this site used to
    # store verbatim and so read as repo_root-relative here and CWD-relative
    # on `stats`. A relative value in the MANIFEST still resolves against
    # repo_root; that is the documented split.
    apply_path_overrides(manifest, index_dir, analysis_dir)

    resolved_index_dir = resolve_index_dir(resolved_repo_root, manifest)
    print_resolved_path("index directory", resolved_index_dir)
    sqlite_path = resolved_index_dir / manifest.index.sqlite_file
    chroma_path = resolved_index_dir / manifest.index.chroma_dir

    if not sqlite_path.exists() or not chroma_path.exists():
        console.print(
            f"[red]No index found at {resolved_index_dir}. "
            f"Run: legacylift-search index --repo-root <path>[/red]"
        )
        raise typer.Exit(code=1)

    # Domain resolution (Milestone 6). --domain is the only search path that
    # touches the knowledge DB, and it is a read-only consumer, so probe
    # knowledge.sqlite with a plain Path.exists() BEFORE constructing
    # KnowledgeStore (construction would create an empty DB + dir as a side
    # effect — issues #33/#50). When --domain is omitted the knowledge DB is
    # never opened (behavior exactly as today).
    domain_id: Optional[str] = None
    in_domain_paths: Optional[set[str]] = None
    if domain is not None:
        from legacylift_search.config import resolve_knowledge_dir

        resolved_knowledge_dir = resolve_knowledge_dir(resolved_repo_root, manifest)
        print_resolved_path("knowledge directory", resolved_knowledge_dir)
        knowledge_sqlite_path = resolved_knowledge_dir / "knowledge.sqlite"
        if not knowledge_sqlite_path.exists():
            console.print(
                "[red]no knowledge store - run `tag-domains` first[/red]"
            )
            raise typer.Exit(code=1)

        from legacylift_search.knowledge_store import KnowledgeStore

        ks = KnowledgeStore(knowledge_sqlite_path)
        try:
            records = ks.list_domains()
            arg = domain.strip()
            arg_lower = arg.lower()
            # The reserved `unassigned`/`excluded` slugs have no `domains`
            # row (Milestone 2 + the excluded-by-design tier), so special-case
            # them: "Unassigned"/"unassigned" and "Excluded"/"excluded" map
            # straight to the slug so you can scope a search into either.
            if arg_lower in ("unassigned", "excluded"):
                domain_id = arg_lower
            else:
                for rec in records:
                    if arg == rec.domain_id or arg_lower == rec.name.lower():
                        domain_id = rec.domain_id
                        break
            if domain_id is None:
                console.print(
                    f"[red]unknown domain '{domain}'; run "
                    f"`legacylift-search domains` to list[/red]"
                )
                if records:
                    available = ", ".join(
                        f"{r.name} ({r.domain_id})" for r in records
                    )
                    console.print(f"available: {available}")
                raise typer.Exit(code=1)
            # Pass BOTH the resolved id and the in-domain path set into the
            # search call; close the handle now (issue #52) — SearchEngine
            # does not own a KnowledgeStore.
            in_domain_paths = set(ks.files_for_domain(domain_id))
        finally:
            ks.close()

    store = SQLiteStore(sqlite_path)
    vector_store: Optional[ChromaVectorStore] = None
    try:
        embedder = create_embedder(
            manifest.embedding, provider_override=embedding_provider
        )
        vector_store = ChromaVectorStore(
            base_dir=resolved_index_dir,
            collection_name=manifest.index.collection_name,
            embedder=embedder,
            metadata={},
        )
        try:
            vector_store.validate_dimension()
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

        engine = SearchEngine(store, vector_store, embedder, manifest.search)
        results = engine.search(
            query,
            limit=limit,
            domain_id=domain_id,
            in_domain_paths=in_domain_paths,
        )
    finally:
        if vector_store is not None:
            vector_store.close()
        store.close()

    if not results:
        console.print("[yellow]No results.[/yellow]")
        return

    for rank, result in enumerate(results, start=1):
        symbol = result.symbol_path or ""
        header = (
            f"[bold]{rank}.[/bold] score={result.score:.4f} "
            f"{result.relative_path}:{result.start_line}-{result.end_line} "
            f"{result.language} {symbol}"
        ).rstrip()
        console.print(header)
        if result.snippet:
            for line in result.snippet.splitlines():
                console.print(f"   {line}")
        console.print("")


# managed by Agent D2
@app.command("symbols")
def symbols(
    name: str = typer.Option(..., "--name", help="Symbol name to look up."),
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    """Find indexed symbols by name (Milestone 12)."""
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.cli_helpers import open_store_or_exit

    console = Console()
    store = open_store_or_exit(repo_root, config, index_dir, console, analysis_dir)

    try:
        records = store.find_symbols(name, limit)
        if not records:
            console.print(f"No symbols found matching '{name}'.")
            return

        table = Table(title=f"Symbols matching '{name}'")
        table.add_column("id", overflow="fold")
        table.add_column("kind")
        table.add_column("language")
        table.add_column("qualified_name", overflow="fold")
        table.add_column("lines")
        for rec in records:
            table.add_row(
                rec.id,
                rec.kind,
                rec.language,
                rec.qualified_name,
                f"{rec.start_line}-{rec.end_line}",
            )
        console.print(table)
    finally:
        store.close()


# managed by Agent D2
@app.command("callers")
def callers(
    symbol_id: str = typer.Argument(..., help="Symbol ID to find callers for."),
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    depth: int = typer.Option(1, "--depth"),
    edge_kind: Optional[List[str]] = typer.Option(
        None,
        "--edge-kind",
        "--kind",
        help=(
            "Repeatable Milestone 25 filter: only show edges of these kinds "
            "(e.g. --edge-kind calls). Default: all kinds."
        ),
    ),
) -> None:
    """Show incoming graph edges for a symbol (Milestone 12)."""
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.cli_helpers import open_store_or_exit

    console = Console()
    store = open_store_or_exit(repo_root, config, index_dir, console, analysis_dir)

    try:
        edges = store.callers(symbol_id, depth, edge_kind or None)

        # Fall back to unresolved edges by name when no resolved callers exist.
        if not edges:
            sym = store.get_symbol(symbol_id)
            if sym is not None:
                conn = store._connect()
                # Apply the same --edge-kind filter here (second site): without
                # it, filtered queries would still leak type-association edges
                # through the unresolved-by-name fallback path.
                fb_sql = (
                    "SELECT id, caller_symbol_id, callee_symbol_id, callee_name, "
                    "edge_kind, confidence, evidence, source_ref_id, "
                    "relative_path, start_line "
                    "FROM graph_edges "
                    "WHERE callee_symbol_id IS NULL AND callee_name = ?"
                )
                fb_params: list = [sym.name]
                if edge_kind:
                    placeholders = ",".join("?" for _ in edge_kind)
                    fb_sql += f" AND edge_kind IN ({placeholders})"
                    fb_params.extend(edge_kind)
                rows = conn.execute(fb_sql, fb_params).fetchall()
                from legacylift_search.store import GraphEdgeRecord

                edges = [
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

        if not edges:
            console.print(f"no callers found for {symbol_id}")
            return

        table = Table(title=f"Callers of {symbol_id}")
        table.add_column("caller_symbol_id", overflow="fold")
        table.add_column("edge_kind")
        table.add_column("confidence")
        table.add_column("path:line", overflow="fold")
        table.add_column("evidence", overflow="fold")
        for e in edges:
            table.add_row(
                e.caller_symbol_id or "(unknown)",
                e.edge_kind,
                f"{e.confidence:.2f}",
                f"{e.relative_path}:{e.start_line}",
                e.evidence,
            )
        console.print(table)
    finally:
        store.close()


# managed by Agent D2
@app.command("callees")
def callees(
    symbol_id: str = typer.Argument(..., help="Symbol ID to find callees for."),
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    depth: int = typer.Option(1, "--depth"),
    edge_kind: Optional[List[str]] = typer.Option(
        None,
        "--edge-kind",
        "--kind",
        help=(
            "Repeatable Milestone 25 filter: only show edges of these kinds "
            "(e.g. --edge-kind calls). Default: all kinds."
        ),
    ),
) -> None:
    """Show outgoing graph edges for a symbol (Milestone 12)."""
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.cli_helpers import open_store_or_exit

    console = Console()
    store = open_store_or_exit(repo_root, config, index_dir, console, analysis_dir)

    try:
        edges = store.callees(symbol_id, depth, edge_kind or None)
        if not edges:
            console.print(f"no callees found for {symbol_id}")
            return

        table = Table(title=f"Callees of {symbol_id}")
        table.add_column("callee_name", overflow="fold")
        table.add_column("callee_symbol_id", overflow="fold")
        table.add_column("edge_kind")
        table.add_column("confidence")
        table.add_column("path:line", overflow="fold")
        for e in edges:
            table.add_row(
                e.callee_name,
                e.callee_symbol_id or "(unresolved)",
                e.edge_kind,
                f"{e.confidence:.2f}",
                f"{e.relative_path}:{e.start_line}",
            )
        console.print(table)
    finally:
        store.close()


# Milestones 23-25: attribute-facts query command
@app.command("facts")
def facts(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    predicate: Optional[str] = typer.Option(
        None, "--predicate", help="Filter facts by predicate (e.g. http_method)."
    ),
    symbol: Optional[str] = typer.Option(
        None, "--symbol", help="Filter facts by subject symbol id."
    ),
) -> None:
    """Show attribute-facts by predicate or subject symbol (Milestones 23-25)."""
    import json

    from rich.console import Console
    from rich.table import Table

    from legacylift_search.cli_helpers import open_store_or_exit

    console = Console()

    if (predicate is None) == (symbol is None):
        console.print(
            "[red]Provide exactly one of --predicate or --symbol.[/red]"
        )
        raise typer.Exit(code=1)

    store = open_store_or_exit(repo_root, config, index_dir, console, analysis_dir)

    try:
        if predicate is not None:
            records = store.facts_by_predicate(predicate)
            title = f"Facts with predicate '{predicate}'"
        else:
            records = store.facts_for_symbol(symbol)
            title = f"Facts for symbol '{symbol}'"

        if not records:
            console.print("No facts found.")
            return

        table = Table(title=title)
        table.add_column("subject_symbol_id", overflow="fold")
        table.add_column("predicate")
        table.add_column("object", overflow="fold")
        table.add_column("attributes", overflow="fold")
        table.add_column("confidence")
        table.add_column("path:line", overflow="fold")
        for rec in records:
            table.add_row(
                rec.subject_symbol_id,
                rec.predicate,
                rec.object or "",
                json.dumps(rec.attributes) if rec.attributes is not None else "",
                f"{rec.confidence:.2f}",
                f"{rec.relative_path}:{rec.start_line}",
            )
        console.print(table)
    finally:
        store.close()


def _domain_counts_intersected(
    ks,
    records: list,
    resolved_repo_root: Path,
    manifest,
) -> tuple[dict[str, list[str]], set[str]]:
    """Return `{domain_id: [discovered relative paths]}` for every domain in
    `records` plus the reserved "unassigned" bucket, each intersected with
    the discovered file set (issue #55): a `file_domains` ghost row that
    survives a `--reset` (Milestone 5) must not make `domains`/`stats`
    over-count while `validate` (which applies the same guard) reports
    correctly. Calls `discover_source_files` once and reuses the result.
    """
    from legacylift_search.discovery import discover_source_files

    discovered_paths = {
        sf.relative_path for sf in discover_source_files(resolved_repo_root, manifest)
    }
    by_domain: dict[str, list[str]] = {}
    for rec in records:
        by_domain[rec.domain_id] = [
            p for p in ks.files_for_domain(rec.domain_id) if p in discovered_paths
        ]
    by_domain["unassigned"] = [
        p for p in ks.files_for_domain("unassigned") if p in discovered_paths
    ]
    by_domain["excluded"] = [
        p for p in ks.files_for_domain("excluded") if p in discovered_paths
    ]
    return by_domain, discovered_paths


# Milestone 4 of domain-enhancements-plan.md
@app.command("tag-domains")
def tag_domains(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    domains: Path = typer.Option(
        ..., "--domains", help="Path to the domains.json to ingest."
    ),
    config: Optional[Path] = typer.Option(None, "--config"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
) -> None:
    """Ingest domains.json, resolve globs to per-file domains, stamp Chroma.

    Deterministic and idempotent (Milestone 4 of
    `domain-enhancements-plan.md`). Sequence: `index -> assess ->
    tag-domains`. Writes the authored `domains`/`domain_edges` tables and the
    derived `file_domains` rows into the durable knowledge store, then stamps
    each embedded chunk's Chroma `domain` metadata from the authoritative
    row — with no re-embedding.
    """
    from rich.console import Console

    from legacylift_search.config import (
        Manifest,
        apply_path_overrides,
        load_manifest,
    )
    from legacylift_search.domain_tagger import DomainTagger

    console = Console()

    resolved_repo_root = (repo_root or Path(".")).resolve()
    if not resolved_repo_root.exists():
        console.print(f"[red]repo-root does not exist: {resolved_repo_root}[/red]")
        raise typer.Exit(code=1)

    config_path = config or (
        resolved_repo_root / "semantic-search.manifest.json"
    )
    try:
        manifest = load_manifest(config_path) if config_path.exists() else Manifest()
    except Exception as exc:
        console.print(f"[red]Failed to load manifest: {exc}[/red]")
        raise typer.Exit(code=1)

    # Section 6 gap: this command consumes BOTH stores, so without
    # --analysis-dir the step after `index --analysis-dir D:\out` failed with
    # FileNotFoundError on a missing index.sqlite. Routed through the same one
    # precedence point every other command uses.
    apply_path_overrides(manifest, None, analysis_dir)

    if not domains.exists():
        console.print(f"[red]domains file not found: {domains}[/red]")
        raise typer.Exit(code=1)

    # Output uses typer.echo/secho (ASCII-safe) rather than Rich console.print,
    # matching the sibling domain commands; avoids non-ASCII mangling on the
    # legacy Windows console (see the plan's accepted-deviation note).
    try:
        stats = DomainTagger(manifest).tag(resolved_repo_root, domains)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except ValueError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as exc:
        typer.secho(f"tag-domains failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    _excluded = (
        f", {stats.excluded_count} excluded" if stats.excluded_count else ""
    )
    typer.echo(
        f"tagged: {stats.domains_ingested} domain(s), "
        f"{stats.edges_ingested} edge(s); resolved {stats.files_resolved} file(s) "
        f"({stats.glob_count} glob-matched{_excluded}, "
        f"{stats.unassigned_count} unassigned); "
        f"stamped {stats.chunks_stamped} chunk(s)."
    )

    if stats.dropped_domains:
        parts = ", ".join(
            f"{d} ({stats.reclassified_counts.get(d, 0)} file(s) reclassified)"
            for d in stats.dropped_domains
        )
        typer.secho(
            f"dropped {len(stats.dropped_domains)} domain(s) no longer "
            f"in domains.json: {parts}",
            fg=typer.colors.YELLOW,
        )

    if stats.manual_preserved:
        shown = ", ".join(stats.manual_preserved[:5])
        more = (
            f" (+{len(stats.manual_preserved) - 5} more)"
            if len(stats.manual_preserved) > 5
            else ""
        )
        typer.secho(
            f"preserved {len(stats.manual_preserved)} manual domain "
            f"override(s) - not overwritten by glob resolution: {shown}{more}",
            fg=typer.colors.YELLOW,
        )

    if stats.file_rows_reaped:
        typer.echo(
            f"reaped {stats.file_rows_reaped} file_domains row(s) for "
            f"undiscovered paths."
        )


# Milestone 2 of domain-enhancements-plan.md
@app.command("domains")
def domains_cmd(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
) -> None:
    """List capability domains with per-domain file and chunk counts.

    The chunk count needs both databases (`file_domains` in
    `knowledge.sqlite`, `chunks` in `index.sqlite`) — separate files, so a
    single-statement SQL join is impossible. This reads the two tables over
    separate connections and joins in Python (issue #34) rather than
    ATTACHing a WAL `index.sqlite` read-only (unreliable — see the plan).
    """
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.cli_helpers import print_resolved_path, resolve_paths
    from legacylift_search.config import resolve_knowledge_dir

    console = Console()
    try:
        manifest, resolved_repo_root, resolved_index_dir = resolve_paths(
            repo_root, config, None, analysis_dir
        )
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    resolved_knowledge_dir = resolve_knowledge_dir(resolved_repo_root, manifest)
    print_resolved_path("knowledge directory", resolved_knowledge_dir)
    knowledge_sqlite_path = resolved_knowledge_dir / "knowledge.sqlite"

    # Existence-probe BEFORE constructing KnowledgeStore (issue #33):
    # construction creates the file (and its parent dir) as a side effect.
    # Uses typer.echo rather than console.print: rich's Console mangles
    # non-ASCII characters (the em dash here) on a legacy Windows console
    # that lacks UTF-8 support, whereas Click's echo() encodes correctly.
    if not knowledge_sqlite_path.exists():
        typer.echo("no domains - run `tag-domains` to populate the knowledge store.")
        return

    from legacylift_search.knowledge_store import KnowledgeStore
    from legacylift_search.store import SQLiteStore

    ks = KnowledgeStore(knowledge_sqlite_path)
    index_store: SQLiteStore | None = None
    try:
        records = ks.list_domains()
        if not records:
            typer.echo("no domains - run `tag-domains` to populate the knowledge store.")
            return

        try:
            by_domain, _discovered_paths = _domain_counts_intersected(
                ks, records, resolved_repo_root, manifest
            )
        except Exception as exc:
            console.print(f"[red]discovery failed: {exc}[/red]")
            raise typer.Exit(code=1)

        # Chunk counts: separate connection to index.sqlite, joined in
        # Python. Degrade gracefully (issues #19/#33) when it is absent.
        #
        # Opened through SQLiteStore rather than sqlite3.connect: this is a
        # READ PATH on index.sqlite, and CR-01's open-time migration only
        # fires for connections SQLiteStore opens. A raw connect here was
        # harmless while it read nothing but `chunks`, but from version 2
        # onward it would be a read path that never advances the schema --
        # the exact asymmetry CR-01 was raised to remove.
        index_sqlite_path = resolved_index_dir / manifest.index.sqlite_file
        chunk_counts_by_path: dict[str, int] = {}
        index_available = index_sqlite_path.exists()
        if index_available:
            index_store = SQLiteStore(index_sqlite_path)
            for rel_path, count in index_store.connection().execute(
                "SELECT relative_path, COUNT(*) FROM chunks GROUP BY relative_path"
            ):
                chunk_counts_by_path[rel_path] = count

        def _counts(domain_id: str) -> tuple[int, str]:
            paths = by_domain.get(domain_id, [])
            file_count = len(paths)
            if not index_available:
                return file_count, "n/a"
            chunk_count = sum(chunk_counts_by_path.get(p, 0) for p in paths)
            return file_count, str(chunk_count)

        table = Table(title="Capability Domains")
        table.add_column("Domain")
        table.add_column("Files", justify="right")
        table.add_column("Chunks", justify="right")

        for rec in records:
            file_count, chunk_count = _counts(rec.domain_id)
            table.add_row(f"{rec.name} ({rec.domain_id})", str(file_count), chunk_count)

        unassigned_files, unassigned_chunks = _counts("unassigned")
        table.add_row("Unassigned (unassigned)", str(unassigned_files), unassigned_chunks)

        excluded_files, excluded_chunks = _counts("excluded")
        if excluded_files:
            table.add_row(
                "Excluded (excluded)", str(excluded_files), excluded_chunks
            )

        console.print(table)
    finally:
        if index_store is not None:
            index_store.close()
        ks.close()


# Milestone 8 of domain-enhancements-plan.md
@app.command("render-architecture")
def render_architecture(
    repo_root: Optional[Path] = typer.Option(
        None,
        "--repo-root",
        help=(
            "Repo root. Required only when --domains is omitted (the SQLite "
            "source needs it to locate the knowledge store); optional and "
            "unused when --domains is given."
        ),
    ),
    domains_path: Optional[Path] = typer.Option(
        None,
        "--domains",
        help=(
            "Render from this domains.json instead of the knowledge store "
            "(the assess-time path — never touches knowledge.sqlite)."
        ),
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        help="Output file path, or '-' for stdout. Omitted = stdout (default).",
    ),
    config: Optional[Path] = typer.Option(None, "--config"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback. Used only on the SQLite source path "
            "(i.e. when --domains is omitted)."
        ),
    ),
) -> None:
    """Render the domain dependency diagram as deterministic Mermaid.

    Milestone 8: ONE renderer, TWO sources (issue #13). Nodes/edges come
    either from a `domains.json` (`--domains`, parsed via `load_domains_json`
    — the path `modernize-assess` uses, since domains only reach SQLite after
    `tag-domains` runs) or, when `--domains` is omitted, from the tagged
    knowledge store (`list_domains()`/`get_domain_edges()`). Both are
    normalized to the same `DomainRecord`/`DomainEdgeRecord` shape before
    calling `render_architecture_mermaid`, so the two sources produce
    byte-identical output for identical data.
    """
    from rich.console import Console

    console = Console()

    from legacylift_search.domain_tagger import (
        domains_file_to_records,
        load_domains_json,
        render_architecture_mermaid,
    )

    if domains_path is not None:
        try:
            df = load_domains_json(domains_path)
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        domains, edges = domains_file_to_records(df)
    else:
        if repo_root is None:
            console.print(
                "[red]render-architecture requires --domains or "
                "--repo-root[/red]"
            )
            raise typer.Exit(code=1)

        from legacylift_search.cli_helpers import print_resolved_path
        from legacylift_search.config import (
            Manifest,
            apply_path_overrides,
            load_manifest,
            resolve_knowledge_dir,
        )

        resolved_repo_root = repo_root.resolve()
        if not resolved_repo_root.exists():
            console.print(
                f"[red]repo-root does not exist: {resolved_repo_root}[/red]"
            )
            raise typer.Exit(code=1)

        config_path = config or (
            resolved_repo_root / "semantic-search.manifest.json"
        )
        try:
            manifest = (
                load_manifest(config_path) if config_path.exists() else Manifest()
            )
        except Exception as exc:
            console.print(f"[red]Failed to load manifest: {exc}[/red]")
            raise typer.Exit(code=1)

        # Section 6 gap: without --analysis-dir this reported "no knowledge
        # store" after `index --analysis-dir`, because it resolved the
        # knowledge directory from the manifest alone.
        apply_path_overrides(manifest, None, analysis_dir)

        resolved_knowledge_dir = resolve_knowledge_dir(resolved_repo_root, manifest)
        print_resolved_path("knowledge directory", resolved_knowledge_dir)
        knowledge_sqlite_path = resolved_knowledge_dir / "knowledge.sqlite"

        # Existence-probe BEFORE constructing KnowledgeStore (issues #33,
        # #50): construction creates the file (and its parent dir) as a side
        # effect, so a never-tagged repo must not silently get an empty
        # knowledge.sqlite and an empty diagram.
        if not knowledge_sqlite_path.exists():
            console.print(
                "[red]no knowledge store - run `tag-domains` first[/red]"
            )
            raise typer.Exit(code=1)

        from legacylift_search.knowledge_store import KnowledgeStore

        ks = KnowledgeStore(knowledge_sqlite_path)
        try:
            domains = ks.list_domains()
            edges = ks.get_domain_edges()
        finally:
            ks.close()

    mermaid = render_architecture_mermaid(domains, edges)

    if output is None or output == "-":
        typer.echo(mermaid, nl=False)
    else:
        Path(output).write_text(mermaid, encoding="utf-8")
        console.print(f"wrote {output}")


# managed by Agent D2
@app.command("stats")
def stats(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
) -> None:
    """Print index statistics (Milestone 12)."""
    from rich.console import Console
    from rich.table import Table

    from legacylift_search.cli_helpers import open_store_or_exit

    console = Console()
    store = open_store_or_exit(repo_root, config, index_dir, console, analysis_dir)

    try:
        s = store.stats()
        table = Table(title="Index Stats")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("files indexed", str(s.file_count))
        table.add_row("chunks", str(s.chunk_count))
        table.add_row("symbols", str(s.symbol_count))
        table.add_row("refs", str(s.ref_count))
        table.add_row("graph edges", str(s.edge_count))
        table.add_row("facts", str(s.fact_count))
        table.add_row(
            "languages", ", ".join(s.languages) if s.languages else "(none)"
        )
        table.add_row(
            "embedding provider",
            store.get_metadata("embedder_name") or "(unknown)",
        )
        table.add_row(
            "embedding dimension",
            store.get_metadata("embedding_dimension") or "(unknown)",
        )
        table.add_row(
            "indexed_at", store.get_metadata("indexed_at") or "(unknown)"
        )
        console.print(table)

        # Domain summary (Milestone 2 of domain-enhancements-plan.md).
        # Existence-probe BEFORE constructing KnowledgeStore (issue #33):
        # construction creates the file as a side effect.
        from legacylift_search.cli_helpers import print_resolved_path, resolve_paths
        from legacylift_search.config import resolve_knowledge_dir

        # print_banner=False: the index directory was already printed by the
        # open_store_or_exit()->resolve_paths() call above; this second
        # resolve_paths call exists only to get manifest/repo_root back for
        # the knowledge-directory resolution below, and must not print the
        # same resolved index directory a second time in one run.
        domain_manifest, domain_repo_root, _domain_index_dir = resolve_paths(
            repo_root, config, index_dir, analysis_dir, print_banner=False
        )
        resolved_knowledge_dir = resolve_knowledge_dir(domain_repo_root, domain_manifest)
        print_resolved_path("knowledge directory", resolved_knowledge_dir)
        knowledge_sqlite_path = resolved_knowledge_dir / "knowledge.sqlite"
        # typer.echo, not console.print: rich's Console mangles non-ASCII
        # output (the middle-dot separator here) on a legacy Windows
        # console without UTF-8 support, whereas Click's echo() is correct.
        if not knowledge_sqlite_path.exists():
            typer.echo("domains: no domains yet")
        else:
            from legacylift_search.knowledge_store import KnowledgeStore

            ks = KnowledgeStore(knowledge_sqlite_path)
            try:
                records = ks.list_domains()
                if not records:
                    typer.echo("domains: no domains yet")
                else:
                    try:
                        by_domain, _discovered = _domain_counts_intersected(
                            ks, records, domain_repo_root, domain_manifest
                        )
                    except Exception as exc:
                        typer.echo(f"domain discovery failed: {exc}", err=True)
                    else:
                        unassigned_count = len(by_domain.get("unassigned", []))
                        excluded_count = len(by_domain.get("excluded", []))
                        # "files tagged" counts CLASSIFIED files only (a domain
                        # other than the reserved `unassigned`/`excluded`); the
                        # unassigned gap and the excluded-by-design set are
                        # reported separately. This matches the plan's M2
                        # example and `validate`'s coverage arithmetic — the
                        # two commands must not describe the same repo with
                        # different totals.
                        classified_count = sum(
                            len(by_domain.get(rec.domain_id, [])) for rec in records
                        )
                        excl_seg = (
                            f" · {excluded_count} excluded" if excluded_count else ""
                        )
                        typer.echo(
                            f"domains: {len(records)} domains · "
                            f"{classified_count} files tagged · "
                            f"{unassigned_count} unassigned{excl_seg}"
                        )
            finally:
                ks.close()
    finally:
        store.close()


# Layer-0 retrieval (code-modernization-layer0-retrieval.md, M3)
@app.command("coverage")
def coverage(
    repo_root: Optional[Path] = typer.Option(None, "--repo-root"),
    config: Optional[Path] = typer.Option(None, "--config"),
    index_dir: Optional[Path] = typer.Option(None, "--index-dir"),
    analysis_dir: Optional[Path] = typer.Option(
        None,
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
    claimed: Path = typer.Option(
        ...,
        "--claimed",
        help="File of path:start-end citations (JSON array or newline-delimited).",
    ),
    limit: int = typer.Option(
        50, "--limit", help="How many uncovered chunks to list."
    ),
    json_output: bool = typer.Option(
        False, "--json/--no-json", help="Emit JSON instead of a human table."
    ),
) -> None:
    """Report chunk-level coverage of the index against a set of citations.

    Loads `path:start-end` citations from --claimed, marks each indexed chunk
    claimed when a citation in the same file overlaps its line range, and
    reports the claimed fraction plus the highest-value uncovered chunks.
    SQLite-only (no Chroma dependency).
    """
    import json

    from rich.console import Console
    from rich.table import Table

    from legacylift_search.cli_helpers import open_store_or_exit

    console = Console()

    if not claimed.exists():
        console.print(f"[red]claimed file not found: {claimed}[/red]")
        raise typer.Exit(code=1)

    citations = _parse_claimed_citations(claimed.read_text(encoding="utf-8"))

    store = open_store_or_exit(repo_root, config, index_dir, console, analysis_dir)
    try:
        result = store.coverage(citations)
    finally:
        store.close()

    listed = result.uncovered_chunks[: max(limit, 0)]

    # A total mismatch — citations supplied but nothing matched — almost always
    # means the citation paths use a different base or separators than the
    # index's repo-root-relative paths, not that no code was extracted. Surface
    # it loudly so a real 0% (nothing found yet) isn't confused with a broken
    # handoff. In JSON mode the warning goes to stderr so it can't corrupt the
    # payload the caller parses.
    # `parse_citation` returns one triple per line RANGE, not per citation
    # string -- `a.cs:1-2,8-9` is one citation and two triples -- so this count
    # is phrased as ranges rather than citations. See `citations.parse_citation`.
    zero_match_warning = (
        f"warning: {len(citations)} cited line range(s) supplied but 0 chunks "
        f"matched. "
        f"Citation paths likely use a different base/separators than the index's "
        f"repo-root-relative paths (e.g. 'legacy/<system>/...' or absolute vs. "
        f"'src/...'). Coverage is reporting 0% claimed for that reason, not "
        f"because no rules were found."
        if citations and result.claimed == 0 and result.total > 0
        else ""
    )

    if json_output:
        if zero_match_warning:
            Console(stderr=True).print(f"[yellow]{zero_match_warning}[/yellow]")
        payload = {
            "total": result.total,
            "claimed": result.claimed,
            "uncovered": result.uncovered,
            "pct": result.pct,
            "uncovered_chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "path": c.relative_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "symbol": c.symbol,
                }
                for c in listed
            ],
        }
        console.print_json(json.dumps(payload))
        return

    console.print(
        f"coverage: {result.claimed}/{result.total} chunks claimed "
        f"({result.pct:.1f}%); {result.uncovered} uncovered chunks "
        f"({len(listed)} listed below)"
    )
    if listed:
        table = Table(title="Highest-value uncovered chunks")
        table.add_column("chunk_id", overflow="fold")
        table.add_column("path:line", overflow="fold")
        table.add_column("symbol", overflow="fold")
        for c in listed:
            table.add_row(
                c.chunk_id,
                f"{c.relative_path}:{c.start_line}-{c.end_line}",
                c.symbol or "",
            )
        console.print(table)
    if zero_match_warning:
        console.print(f"[yellow]{zero_match_warning}[/yellow]")


def _parse_claimed_citations(raw: str) -> list[tuple[str, int, int]]:
    """Parse `path:start-end` citation strings into (path, start, end) tuples.

    **The parser itself now lives in `citations.parse_citation`** (Milestone 1
    Step 6a), promoted out of here so that this best-effort coverage
    denominator and ingest's anchor resolution cannot disagree about what a
    citation is. This name and signature survive for the coverage caller, and
    `strict=False` keeps its behaviour byte-identical: malformed entries are
    skipped silently, because coverage is a denominator and not a validator.
    Ingest passes `strict=True` instead, where a dropped citation is a
    dropped `anchor_key` and so a silently different `dedupe_key`.
    """
    from legacylift_search.citations import parse_citation

    return parse_citation(raw, strict=False)


# managed by Agent B1
@app.command("dump-ast")
def dump_ast(
    path: Path = typer.Argument(..., help="Source file to parse."),
    max_depth: int = typer.Option(6, "--max-depth"),
    language: Optional[str] = typer.Option(None, "--language"),
) -> None:
    """Dump tree-sitter node kinds and ranges for a file (Milestone 5)."""
    from legacylift_search.extractors import SymbolExtractor, load_profiles

    if not path.exists():
        typer.echo(f"[legacylift-search] file not found: {path}", err=True)
        raise typer.Exit(code=1)

    profile_path = (
        Path(__file__).resolve().parent / "profiles" / "extractors.json"
    )
    try:
        profiles = load_profiles(profile_path)
    except Exception as exc:
        typer.echo(
            f"[legacylift-search] failed to load extractor profiles: {exc}",
            err=True,
        )
        raise typer.Exit(code=1)

    extractor = SymbolExtractor(profiles)
    output = extractor.dump_ast(path, language, max_depth)
    typer.echo(output)


if __name__ == "__main__":  # pragma: no cover
    app()
