"""Shared helpers for CLI command bodies (Milestone 12).

Centralizes the `--repo-root` / `--config` / `--index-dir` resolution
pattern used by symbols/callers/callees/stats/validate.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

from legacylift_search.config import (
    Manifest,
    apply_path_overrides,
    load_manifest,
    resolve_index_dir,
)

if TYPE_CHECKING:
    from rich.console import Console

    from legacylift_search.store import SQLiteStore


def print_resolved_path(kind: str, path: Path) -> None:
    """Print the one-line resolved-path banner for `kind` (`"index directory"`
    or `"knowledge directory"`) to stderr, never stdout.

    This is the printed-paths requirement from the reqs-to-data-store plan's
    Milestone 0 (`docs/exec-plans/active/reqs-to-data-store.md`): the
    analysis-dir path resolution *guesses* (a directory-convention detection,
    not a required layout), so every run must be inspectable, or a wrong
    guess silently creates a second empty store beside a populated one.

    Always routed through a fresh `Console(stderr=True)` — the house
    precedent at `cli.py`'s `coverage` command, which stderr-routes its
    zero-match warning for the same reason: several `requirements`
    subcommands (Milestone 1) take `--json`, and a banner on stdout would
    corrupt every one of them for a caller parsing stdout.
    """
    from rich.console import Console

    # soft_wrap keeps the path on ONE line. Without it rich wraps at the
    # console width -- 80 columns when stderr is a pipe -- which splits every
    # real path across two lines and makes the banner ungreppable. The whole
    # point of this line is that a wrong guess is easy to spot, so it has to
    # survive being piped into grep.
    # The prefix is escaped: rich parses square brackets as style markup, so an
    # unescaped "[legacylift-search]" is read as an unknown tag and silently
    # DROPPED from the output, leaving a bare leading space. Escape it with
    # rich.markup.escape rather than removing the brackets, so the banner still
    # announces which tool printed it.
    from rich.markup import escape

    Console(stderr=True, soft_wrap=True).print(
        f"[dim]{escape('[legacylift-search]')} resolved {kind}: {path}[/dim]"
    )


def resolve_paths(
    repo_root: Optional[Path],
    config: Optional[Path],
    index_dir: Optional[Path],
    analysis_dir: Optional[Path] = None,
    *,
    print_banner: bool = True,
) -> tuple[Manifest, Path, Path]:
    """Resolve manifest, repo_root, and index_dir per the CLI conventions.

    Mirrors the resolution pattern used by the `index` command body.

    Both `index_dir` and `analysis_dir` are folded into the manifest by
    `config.apply_path_overrides`, which is the single place their precedence
    is settled for every command in the CLI (see its docstring). Both are
    CWD-relative; `--index-dir` wins outright when both are given, because it
    resolves absolute and lands on branch 1 of `resolve_index_dir`.

    `print_banner` controls whether the resolved index directory is printed
    to stderr here (see `print_resolved_path`). Pass `False` when a caller
    already printed it via an earlier `resolve_paths`/`open_store_or_exit`
    call in the same command and only needs the manifest/repo_root back
    (e.g. `stats` re-resolving to reach the knowledge directory) — this
    avoids printing the same resolved index directory twice in one run.
    """
    resolved_repo_root = (repo_root or Path(".")).resolve()
    if not resolved_repo_root.exists():
        raise FileNotFoundError(f"repo-root does not exist: {resolved_repo_root}")

    config_path = config or (resolved_repo_root / "semantic-search.manifest.json")

    if config_path.exists():
        manifest = load_manifest(config_path)
    else:
        manifest = Manifest()

    # CR-03: this used to return `index_dir.resolve()` directly, short-
    # circuiting the resolver, so --index-dir beat --analysis-dir here while
    # --analysis-dir beat --index-dir inside `resolve_index_dir` -- the same
    # two flags with opposite precedence depending on which command you typed.
    # Both flags now go through the ONE precedence point, `apply_path_
    # overrides`, and the resolver is always consulted. The outcome for
    # --index-dir alone is unchanged (it resolves absolute, so branch 1 of
    # `resolve_index_dir` returns it verbatim); what changes is that every
    # command now agrees about what happens when both flags are given.
    apply_path_overrides(manifest, index_dir, analysis_dir)
    resolved_index = resolve_index_dir(resolved_repo_root, manifest)

    if print_banner:
        print_resolved_path("index directory", resolved_index)

    return manifest, resolved_repo_root, resolved_index


def open_store_or_exit(
    repo_root: Optional[Path],
    config: Optional[Path],
    index_dir: Optional[Path],
    console: "Console",
    analysis_dir: Optional[Path] = None,
) -> "SQLiteStore":
    """Resolve paths, verify SQLite exists, and return an open SQLiteStore.

    Exits the CLI with code 1 and a clear message if the index is missing.
    The resolved index directory is printed (via `resolve_paths`) before the
    existence check, so a missing-index exit still tells the caller where it
    looked.
    """
    from legacylift_search.store import SQLiteStore

    try:
        manifest, _resolved_repo_root, resolved_index = resolve_paths(
            repo_root, config, index_dir, analysis_dir
        )
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    sqlite_path = resolved_index / manifest.index.sqlite_file
    if not sqlite_path.exists():
        console.print(
            f"[red]missing: index not found at {sqlite_path}. "
            f"Run `legacylift-search index --repo-root <path>` first.[/red]"
        )
        raise typer.Exit(code=1)

    return SQLiteStore(sqlite_path)


__all__ = ["resolve_paths", "open_store_or_exit", "print_resolved_path"]
