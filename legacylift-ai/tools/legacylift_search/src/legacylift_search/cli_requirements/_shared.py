"""What all fourteen `requirements` commands share.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`.

Four things live here because getting any of them wrong is silent:

1. **The three common options.** `--repo-root`, `--config` and
   `--analysis-dir` on every command, as `Annotated` aliases so the four
   command modules cannot disagree about a flag's name or help text. Path
   resolution goes through `cli_helpers.resolve_paths` and
   `config.resolve_knowledge_dir`; `--index-dir`/`--analysis-dir` precedence
   is settled once in `config.apply_path_overrides` and is never
   re-implemented here.
2. **The existence probe.** `KnowledgeStore.__init__` creates the database
   *and its parent directory* as a side effect, so a read-only command that
   constructs one to find out whether requirements exist silently
   materializes an empty store beside a populated one -- and an empty
   knowledge database is indistinguishable from a real one on the next
   command. Every read path here probes `Path.exists()` first, which is
   `cli.py`'s `domains_cmd` pattern.
3. **The resolved-path banner goes to stderr**, via
   `cli_helpers.print_resolved_path`. Several of these subcommands take
   `--json`, and a banner on stdout corrupts every caller parsing stdout.
4. **The embedder is optional.** `build_embedder` returns `None` rather than
   raising when no provider is reachable, because every write path in this
   group treats a missing embedder as a degraded success: the requirements
   land, `EmbedResult.reason` names `requirements reindex-vectors`, and the
   command **exits zero**. A non-zero exit there reads as "the ingest
   failed" and invites re-running an extraction, which is hours of model time
   to recover something that was never lost.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Optional

import typer

if TYPE_CHECKING:  # pragma: no cover - typing only
    from legacylift_search.config import Manifest
    from legacylift_search.embeddings import Embedder
    from legacylift_search.knowledge_store import KnowledgeStore
    from legacylift_search.store import SQLiteStore

__all__ = [
    "AnalysisDirOption",
    "ConfigOption",
    "EmbeddingProviderOption",
    "JsonOption",
    "LimitOption",
    "RepoRootOption",
    "RequirementsPaths",
    "build_embedder",
    "emit_json",
    "open_index_store",
    "open_knowledge_store",
    "open_knowledge_store_for_write",
    "resolve_requirements_paths",
]


#: The filename of the durable knowledge database inside the resolved
#: knowledge directory. Hard-coded, exactly as `cli.py`'s `domains_cmd` and
#: `search --domain` hard-code it: `Manifest` carries `knowledge_dir` but no
#: knowledge *filename* setting, so there is no configuration to read and
#: inventing one here would put a fourth spelling of this path in the tree.
KNOWLEDGE_SQLITE_NAME = "knowledge.sqlite"


# ----------------------------------------------------------------------
# The shared options
# ----------------------------------------------------------------------
#
# Declared as `Annotated` aliases rather than shared `typer.Option(...)`
# default objects. Both work in typer 0.26, but an alias is a *type*, so two
# commands using it cannot end up sharing one mutable `OptionInfo` instance,
# and a command author writes `repo_root: RepoRootOption = None` -- the
# default is visible at the call site, which is where a reader looks for it.

RepoRootOption = Annotated[
    Optional[Path],
    typer.Option("--repo-root", help="Target repository root (default: cwd)."),
]

ConfigOption = Annotated[
    Optional[Path],
    typer.Option(
        "--config",
        help="Path to semantic-search.manifest.json (default: <repo-root>/).",
    ),
]

AnalysisDirOption = Annotated[
    Optional[Path],
    typer.Option(
        "--analysis-dir",
        help=(
            "Override where generated output (index/ and knowledge/) is "
            "written, in place of the legacy/+analysis/ convention or the "
            "legacylift-docs/ fallback."
        ),
    ),
]

JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help=(
            "Emit machine-readable JSON on stdout. The resolved-path banner "
            "goes to stderr, so stdout stays parseable."
        ),
    ),
]

EmbeddingProviderOption = Annotated[
    Optional[str],
    typer.Option(
        "--embedding-provider",
        help=(
            "Override the manifest's embedding provider. A provider that "
            "cannot be built is a degraded success, not an error: the "
            "requirements are stored and `requirements reindex-vectors` "
            "populates the semantic half later."
        ),
    ),
]

LimitOption = Annotated[
    Optional[int],
    typer.Option("--limit", help="Maximum rows to return (default: all)."),
]


@dataclass(frozen=True)
class RequirementsPaths:
    """Everything a `requirements` command needs resolved, resolved once.

    ``knowledge_sqlite_path`` and ``index_sqlite_path`` are *paths*, not open
    stores, and neither is guaranteed to exist -- the existence questions are
    `knowledge_exists` and `index_exists`, both plain `Path.exists()` calls
    taken at construction. Handing a command the paths plus the answers,
    rather than an opened store, is what keeps the probe from being
    accidentally skipped: there is no way to get a `KnowledgeStore` out of
    this object without going through a helper that checks.
    """

    manifest: Manifest
    repo_root: Path
    index_dir: Path
    knowledge_dir: Path
    knowledge_sqlite_path: Path
    index_sqlite_path: Path

    @property
    def knowledge_exists(self) -> bool:
        """Does the knowledge database exist? A plain `Path.exists()`."""
        return self.knowledge_sqlite_path.exists()

    @property
    def index_exists(self) -> bool:
        """Does `index.sqlite` exist? `None` from `open_index_store` when not.

        A missing index is a **supported** state for this whole command
        group, not an error path: `V-STY-03` then runs on its morphological
        fallback alone, and the reporting has to say which of the two it was
        -- "no leaked identifier was found" and "leakage was never looked
        for" are different facts.
        """
        return self.index_sqlite_path.exists()


def resolve_requirements_paths(
    repo_root: Optional[Path],
    config: Optional[Path],
    analysis_dir: Optional[Path],
    *,
    print_banner: bool = True,
) -> RequirementsPaths:
    """Resolve the manifest and both store directories, printing the banner.

    Goes through `cli_helpers.resolve_paths` (which applies the one
    `--index-dir`/`--analysis-dir` precedence point and prints the resolved
    *index* directory) and then `config.resolve_knowledge_dir`, printing the
    resolved *knowledge* directory too -- both to stderr.

    Both banners are printed because these commands routinely read one store
    and write the other, and Milestone 0's path resolution *guesses* (a
    directory-convention detection, not a required layout), so a wrong guess
    must be visible rather than silently creating a second empty store beside
    a populated one.

    Raises:
        Exception: whatever `resolve_paths` raises -- a missing `--repo-root`,
            an unreadable manifest. Callers turn it into `typer.Exit(1)` with
            the message, rather than a traceback.
    """
    from legacylift_search.cli_helpers import print_resolved_path, resolve_paths
    from legacylift_search.config import resolve_knowledge_dir

    manifest, resolved_repo_root, resolved_index_dir = resolve_paths(
        repo_root, config, None, analysis_dir, print_banner=print_banner
    )
    knowledge_dir = resolve_knowledge_dir(resolved_repo_root, manifest)
    if print_banner:
        print_resolved_path("knowledge directory", knowledge_dir)
    return RequirementsPaths(
        manifest=manifest,
        repo_root=resolved_repo_root,
        index_dir=resolved_index_dir,
        knowledge_dir=knowledge_dir,
        knowledge_sqlite_path=knowledge_dir / KNOWLEDGE_SQLITE_NAME,
        index_sqlite_path=resolved_index_dir / manifest.index.sqlite_file,
    )


def open_knowledge_store(paths: RequirementsPaths) -> KnowledgeStore:
    """Open the knowledge store, or exit 1 if there is not one. **Read paths.**

    This is house rule 2 in executable form: the `Path.exists()` probe
    happens **before** the constructor runs, because construction creates the
    file and its parent directory, and an empty store answers every
    subsequent read with "no requirements" indistinguishably from a store
    that was never built.

    Exits with code 1 and a message naming the path it looked at and the
    command that would populate it. Uses `typer.echo`, not `rich`'s
    `Console.print`: rich mangles non-ASCII on a legacy Windows console, and
    this message must survive being read.
    """
    if not paths.knowledge_exists:
        typer.echo(
            f"no requirements store at {paths.knowledge_sqlite_path}. Run "
            "`legacylift-search requirements ingest` (or `/modernize-extract-"
            "rules`) first.",
            err=True,
        )
        raise typer.Exit(code=1)
    from legacylift_search.knowledge_store import KnowledgeStore

    return KnowledgeStore(paths.knowledge_sqlite_path)


def open_knowledge_store_for_write(paths: RequirementsPaths) -> KnowledgeStore:
    """Open the knowledge store, **creating** it if absent. Write paths only.

    `requirements ingest` and `requirements import` are the two commands that
    legitimately create the database: they are how requirements first arrive.
    Every other command in this group calls `open_knowledge_store` instead,
    and the two functions exist separately so that "this command may create
    the store" is a visible choice at the call site rather than the default
    behaviour of a constructor.
    """
    from legacylift_search.knowledge_store import KnowledgeStore

    return KnowledgeStore(paths.knowledge_sqlite_path)


def open_index_store(paths: RequirementsPaths) -> SQLiteStore | None:
    """Open the Layer-0 index if it exists, else `None`. Never creates one.

    Delegates to `gr_refresh.open_index_store_if_present`, which owns the
    same reasoning for the same reason: `SQLiteStore._connect` creates the
    database on its first query, so asking the store whether an index exists
    materializes an empty `index.sqlite` beside a repository that has never
    been indexed.
    """
    from legacylift_search.gr_refresh import open_index_store_if_present

    return open_index_store_if_present(paths.index_sqlite_path)


def build_embedder(
    manifest: Manifest, provider_override: Optional[str] = None
) -> tuple[Embedder | None, str | None]:
    """Build the configured embedder, or return `(None, reason)`.

    **Returning `None` is the supported outcome, not the error path.** Every
    write path in this group passes the embedder straight to
    `refresh_gr_vectors`, whose contract is that `None` is a degraded
    success: the SQLite half is committed unconditionally and the semantic
    half is populated later by `requirements reindex-vectors`. So a provider
    that cannot be constructed -- no credentials, no network, an unknown
    provider name -- must not stop a human's edit or an ingest from
    recording.

    Returns:
        `(embedder, None)` on success, or `(None, reason)` where `reason` is
        a sentence the caller should print. The reason is returned rather
        than logged so the caller decides where it goes -- stderr for a
        `--json` command, the normal output otherwise -- and so a caller
        cannot report "no embedder" without saying why.
    """
    from legacylift_search.embeddings import create_embedder

    try:
        return (
            create_embedder(
                manifest.embedding, provider_override=provider_override
            ),
            None,
        )
    except Exception as exc:
        return (
            None,
            (
                f"no embedding provider is available ({exc}); the semantic "
                "half will not be populated. The requirements themselves are "
                "unaffected and keyword search works. Run `legacylift-search "
                "requirements reindex-vectors` once a provider is configured."
            ),
        )


def emit_json(payload: Any) -> None:
    """Write `payload` to stdout as JSON, one document, sorted keys.

    Sorted keys and a trailing newline so two runs over unchanged data
    produce byte-identical output and a diff of two captures is readable --
    the same determinism rule Step 9 puts on the JSONL export, applied to
    command output.

    `ensure_ascii=False` because a `statement` may legitimately carry
    non-ASCII text and escaping it makes the output unreadable for the human
    who redirected it to a file. Note this is *stdout of a `--json` command*,
    not a `rich` console line -- house rule 6's ASCII preference is about
    banners and tables on a legacy Windows console, and JSON on stdout is
    read by a parser.
    """
    typer.echo(_json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2))
