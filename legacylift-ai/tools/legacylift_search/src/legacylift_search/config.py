"""Manifest models, loading, and default config writing.

Implements Milestone 2 of the ExecPlan
(`docs/exec-plans/active/semantic-code-search-graph-index.md`).
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """Project-level configuration."""

    name: str = Field(default="current-repository")
    repo_roots: list[str] = Field(default=["."])
    include_globs: list[str] = Field(
        default=[
            "**/*.cs",
            "**/*.java",
            "**/*.py",
            "**/*.js",
            "**/*.jsx",
            "**/*.mjs",
            "**/*.cjs",
            "**/*.ts",
            "**/*.tsx",
            "**/*.cbl",
            "**/*.cob",
            "**/*.cpy",
            "**/*.copy",
            "**/*.pco",
            "**/*.sql",
            "**/*.ddl",
            "**/*.dml",
            "**/*.psql",
            "**/*.pgsql",
            "**/*.tsql",
            # The 2026-09-08 coverage widening. Measured on NNG: the previous
            # allow-list left 276 files / 805 KB / 19.60% of first-party bytes
            # unindexed, 178 of them `.jsp` -- and because
            # `/modernize-extract-rules` measures its own coverage as a
            # fraction of INDEXED chunks, an extraction run over that index
            # would have certified itself complete while never having been
            # shown the JSP layer. These eight patterns take the gap to 0.00%
            # for +4.4% index wall clock.
            #
            # `**/*.xml` supersedes the seven path-shaped XML patterns that
            # used to sit here (`**/*.hbm.xml`, `**/*-flow.xml`,
            # `**/flows/**/*.xml`, `**/*.beans.xml`,
            # `**/applicationContext*.xml`, `**/spring/**/*.xml`,
            # `**/config/**/*.xml`); they were kept through the measurement
            # trial only to keep that diff mechanical. The framework-aware
            # `xml_extractor` still gives the Hibernate/Spring/WebFlow
            # dialects their symbols -- the extractor keys off content, never
            # off which glob admitted the file.
            #
            # Only `.xml` yields symbols; the other seven are symbol-dead
            # (`extractors.json` has no profile for them, which is the gate --
            # NOT grammar availability) and contribute retrieval coverage
            # only, as fallback text chunks reachable by FTS5 and vector
            # search. That is what the extraction lenses actually consume.
            "**/*.xml",
            "**/*.jsp",
            "**/*.properties",
            "**/*.css",
            "**/*.vm",
            "**/*.ent",
            "**/*.tld",
            "**/*.xmi",
        ]
    )
    exclude_globs: list[str] = Field(
        default=[
            "**/.git/**",
            "**/.svn/**",
            "**/.hg/**",
            "**/node_modules/**",
            "**/bin/**",
            "**/obj/**",
            "**/target/**",
            "**/dist/**",
            "**/build/**",
            "**/.venv/**",
            "**/venv/**",
            "**/__pycache__/**",
            "**/.pytest_cache/**",
            "**/.mypy_cache/**",
            "**/legacylift-docs/index/**",
            "**/.legacylift/**",
            # Eclipse/IDE and build-tool XML that is noise, never architecture.
            "**/.settings/**",
            "**/build.xml",
            "**/ivy.xml",
            "**/pom.xml",
            "**/*.min.js",
            "**/*.bundle.js",
            "**/*.map",
            "**/*.lock",
            "**/package-lock.json",
            "**/yarn.lock",
            "**/pnpm-lock.yaml",
            # Vendored JS libraries: not the application's own logic, and the
            # large ones (jQuery, prototype, dataTables, jquery-ui) are slow to
            # AST-chunk. Excluding keeps the index focused and the build fast.
            "**/content/javascript/lib/**",
            "**/js/lib/**",
            "**/vendor/**",
            "**/jquery*.js",
            "**/prototype.js",
        ]
    )
    max_file_bytes: int = Field(default=2000000)
    # Path to the `domains.json` supplying third-party provenance
    # (`vendored_globs`, `own_identities`) to `discover_source_files`.
    # Relative paths resolve against `--repo-root`. `None` (the default)
    # disables provenance filtering entirely, which is exactly today's
    # behavior -- discovery must not start requiring a domains.json.
    #
    # It names a FILE rather than inlining the two lists because
    # `gaps.walk_repository` already reads them from `domains.json` and
    # `/modernize-assess` already authors them there. Duplicating them into
    # the manifest would create the second source of truth whose drift this
    # setting exists to prevent -- the index and the gap report must never
    # disagree about which files are the vendor's.
    domains_file: str | None = Field(default=None)


class IndexConfig(BaseModel):
    """Index storage configuration."""

    index_dir: str = Field(default="legacylift-docs/index/code-search")
    # Durable knowledge-store directory (Milestone 1 of
    # domain-enhancements-plan.md). Unlike index_dir, this directory sits
    # outside the gitignored index/ path and is never touched by --reset.
    knowledge_dir: str = Field(default="legacylift-docs/knowledge")
    # Overrides the analysis-directory detection entirely (see
    # resolve_analysis_dir). When set, both index_dir and knowledge_dir
    # resolve underneath this directory instead of via the legacy/analysis
    # sibling-directory convention or the legacylift-docs/ fallback. Absolute
    # paths are used as-is; relative paths resolve against --repo-root.
    analysis_dir: str | None = Field(default=None)
    sqlite_file: str = Field(default="index.sqlite")
    chroma_dir: str = Field(default="chroma")
    collection_name: str = Field(default="code_chunks")
    reset_before_index: bool = Field(default=False)
    store_full_chunk_text_in_sqlite: bool = Field(default=True)
    # Milestone 19: parallelize the cold-index extract+chunk phase. The pure
    # read → extract → chunk work runs in a ProcessPoolExecutor (CPU-bound
    # under the GIL); the main process stays the sole SQLite writer.
    #   0 -> os.cpu_count() worker processes (auto).
    #   1 -> forced-serial in-process fallback (also the equivalence oracle).
    #   N -> N worker processes.
    extract_workers: int = Field(default=0)
    # Number of files whose extracted artifacts are persisted per SQLite
    # transaction. Larger batches amortize commit overhead; smaller batches
    # bound the work lost if the process is killed mid-phase.
    commit_batch_files: int = Field(default=50)


class ChunkingConfig(BaseModel):
    """Chunking strategy configuration."""

    target_tokens: int = Field(default=800)
    max_tokens: int = Field(default=1400)
    min_tokens: int = Field(default=80)
    overlap_lines: int = Field(default=12)
    prefer_ast_boundaries: bool = Field(default=True)
    fallback_max_lines: int = Field(default=120)
    # Chunks whose token estimate is below this are skipped at EMBED time
    # (they still land in SQLite + FTS5, so lexical/symbol lookup keeps full
    # recall — only the dense vector is skipped). A below-threshold chunk is
    # kept anyway if it carries a business-logic signal (validation
    # attributes/annotations, control flow, comparisons, SQL constraints), so
    # data-validation logic is never dropped. Default 0 disables the filter.
    embed_min_tokens: int = Field(default=0)


class EmbeddingConfig(BaseModel):
    """Embedding provider configuration.

    `provider="api"` selects the hosted Amazon Bedrock embedder (Milestone 20).
    For that provider, `model` is a Bedrock model id (e.g.
    `amazon.titan-embed-text-v2:0`) and `region` is the Bedrock region.
    Credentials are read from the `AWS_BEARER_TOKEN_BEDROCK` env var by the AWS
    SDK — they are never stored in the manifest.
    """

    provider: Literal["qwen3", "hash", "api"] = Field(default="qwen3")
    model: str = Field(default="Qwen/Qwen3-Embedding-0.6B")
    dimension: int = Field(default=1024)
    batch_size: int = Field(default=512)
    normalize: bool = Field(default=True)
    device: str = Field(default="auto")
    # Bedrock region for provider="api". Note: do NOT inherit AWS_REGION from
    # the environment (Claude Code sets it to us-east-1 for its own model
    # access); Bedrock embedding uses us-east-2 explicitly.
    region: str = Field(default="us-east-2")
    # Max in-flight Bedrock InvokeModel requests per embed_documents batch.
    # Titan embeds one text per request, so the embed phase is network-bound;
    # issuing requests concurrently is the main throughput lever (~16 was the
    # sweet spot in testing; higher values invite throttling). Only used by
    # provider="api".
    max_concurrency: int = Field(default=16)


class SearchConfig(BaseModel):
    """Search ranking configuration."""

    default_limit: int = Field(default=10)
    vector_candidates: int = Field(default=40)
    lexical_candidates: int = Field(default=40)
    rrf_rank_constant: int = Field(default=60)
    # DEAD KNOB, AND A TRAP FOR WHOEVER REVIVES IT. Nothing on the search
    # path has ever read this: hybrid search does not expand along the graph,
    # and `docs/exec-plans/pending/search-graph-expansion.md` is where that
    # capability is designed (its M1 is a measurement that may well conclude
    # "delete the knob"). The default is `1`, an intent declared before the
    # feature existed -- so adding a reader WITHOUT first changing this to 0
    # turns expansion on for every corpus at once, not just the manifests
    # that set it explicitly, and expansion's failure mode is invisible
    # precision dilution through high-fan-in symbols. `tests/test_config.py`
    # pins the current default and must move with it.
    graph_neighbor_depth: int = Field(default=1)
    snippet_radius_lines: int = Field(default=8)


class Manifest(BaseModel):
    """Complete manifest configuration."""

    schema_version: int = Field(default=1)
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    # No `languages` block. There was one until 2026-09-14 -- `enabled` and
    # `profile_file` -- and nothing ever read either: the extractor profiles are
    # loaded from the package directory (`indexer.py`, `cli.py`:
    # `Path(__file__).parent / "profiles" / "extractors.json"`), and which
    # languages are live is decided by profile presence in that file, not by a
    # list here. It was removed rather than wired up, because a config key that
    # silently does nothing is worse than no key. Pydantic ignores unknown keys,
    # so a manifest still carrying `languages` loads unchanged -- and is still
    # ignored, exactly as before.


def load_manifest(path: Path) -> Manifest:
    """Load and validate manifest from JSON file.

    Args:
        path: Path to the manifest file.

    Returns:
        Validated Manifest instance.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
        ValueError: If the manifest is invalid or contains missing fields.
    """
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in manifest {path}: {e}") from e

    try:
        return Manifest.model_validate(data)
    except Exception as e:
        raise ValueError(f"Invalid manifest schema in {path}: {e}") from e


def write_default_manifest(path: Path, overwrite: bool = False) -> None:
    """Write a default manifest to the specified path.

    Args:
        path: Path where the manifest should be written.
        overwrite: If False (default), refuse to overwrite existing files.

    Raises:
        FileExistsError: If the file exists and overwrite is False.
    """
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Manifest already exists: {path}. Use --overwrite to replace it."
        )

    manifest = Manifest()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        # Use model_dump to get JSON-serializable dict, then pretty-print
        json.dump(
            manifest.model_dump(mode="json"),
            f,
            indent=2,
            ensure_ascii=False,
        )
        f.write("\n")  # Add trailing newline


def _as_configured_path(value: str) -> PurePosixPath:
    r"""Normalize a manifest path *setting* for comparison against a default.

    `CR-02`: the two resolvers used to decide "has the user explicitly
    configured this?" with a raw string compare against the packaged default.
    A manifest holding a normalized-identical default — `"./legacylift-docs/
    index/code-search"`, or the natural Windows hand-edit
    `"legacylift-docs\index\code-search"` — therefore read as explicitly
    configured, took branch 2, and kept writing the index inside the client
    checkout while the knowledge store obeyed the relocated layout. That is
    the exact two-roots split the branch ordering exists to prevent.

    Backslashes are folded to `/` before parsing so the Windows hand-edit
    compares equal on POSIX too (a bare `Path()` compare would not: on POSIX
    a backslash is an ordinary filename character). `PurePosixPath` then drops
    `.` segments and duplicate separators. Case is preserved deliberately —
    these settings name real directories and this code must behave the same
    on both platforms.
    """
    return PurePosixPath(value.replace("\\", "/"))


def is_default_setting(value: str, default: str) -> bool:
    """True when a manifest path setting is the packaged default in disguise."""
    return _as_configured_path(value) == _as_configured_path(default)


def apply_path_overrides(
    manifest: Manifest,
    index_dir: Optional[Path] = None,
    analysis_dir: Optional[Path] = None,
) -> Manifest:
    """Fold the `--index-dir` / `--analysis-dir` CLI flags into `manifest`.

    **This is the single place either flag enters the system, and it settles
    their precedence once for every command.** It exists because `CR-02`,
    `CR-03` and `CR-04` were one root cause: `resolve_index_dir`,
    `resolve_knowledge_dir` and `cli_helpers.resolve_paths` each implemented a
    different precedence over these same two flags, so `--index-dir` won on
    `stats`, `--analysis-dir` won on `index`, and the two families wrote and
    read different directories from identical arguments.

    The settled precedence, highest first:

      1. `--index-dir`, resolved against the **current working directory**.
         Because the result is absolute it lands on branch 1 of
         `resolve_index_dir`, which is the documented carve-out from
         "`--analysis-dir` overrides the whole question". It names the index
         directory only; it says nothing about the knowledge store.
      2. `--analysis-dir`, likewise CWD-relative, which governs both stores
         (index *and* knowledge) via `resolve_analysis_dir`.
      3. The manifest, resolved by `resolve_index_dir` /
         `resolve_knowledge_dir` — where a *relative* setting still resolves
         against `repo_root`. That is the documented split: a FLAG is
         CWD-relative like any other CLI path argument, a SETTING is
         repo-root-relative.

    Both flags are `.resolve()`d here (`CR-04`): before this, `index`,
    `backfill-vectors` and `search` stored `--index-dir` verbatim, so a
    relative value meant `<repo_root>/out` there and `<cwd>/out` on the seven
    `resolve_paths` commands — one flag naming two directories.

    Mutates and returns `manifest` for call-site convenience.
    """
    if analysis_dir is not None:
        manifest.index.analysis_dir = str(analysis_dir.resolve())
    if index_dir is not None:
        manifest.index.index_dir = str(index_dir.resolve())
    return manifest


def resolve_analysis_dir(repo_root: Path, manifest: Manifest) -> Path | None:
    """Resolve the `<app>/analysis/<system>/` directory, if any applies.

    Precedence:
      1. `manifest.index.analysis_dir`, if set, names the analysis directory
         outright (absolute as-is, relative resolved against `repo_root`).
         An override names where things GO, so it is returned whether or not
         it currently exists.
      2. Otherwise, if `repo_root`'s parent is named `legacy` and the sibling
         `<repo_root>/../../analysis/<repo_root.name>` EXISTS, that directory
         is the analysis directory. The existence check is deliberate:
         detection must not require every analyzed repository to adopt the
         `legacy/`+`analysis/` convention.
      3. Otherwise `None` — neither an override nor the convention applies.

    Args:
        repo_root: Repository root directory (the client's code).
        manifest: Loaded manifest configuration.

    Returns:
        Absolute path to the analysis directory, or `None`.
    """
    analysis_dir = manifest.index.analysis_dir
    if analysis_dir is not None:
        path = Path(analysis_dir)
        if path.is_absolute():
            return path
        return (repo_root / path).resolve()

    if repo_root.parent.name == "legacy":
        candidate = repo_root.parent.parent / "analysis" / repo_root.name
        if candidate.exists():
            return candidate.resolve()

    return None


def resolve_index_dir(repo_root: Path, manifest: Manifest) -> Path:
    """Resolve the absolute index directory path.

    Branches, in order:
      1. `manifest.index.index_dir` is absolute -> used as-is. This is also
         where an explicit `--index-dir` FLAG lands, because
         `apply_path_overrides` resolves it to an absolute path first; that
         is what makes the flag win outright, on every command.
      2. It differs from the packaged default (compared as a PATH, not as a
         string -- see `is_default_setting`, `CR-02`) -> the user has
         explicitly configured it, so it resolves against `repo_root` exactly
         as it always has. This is what keeps existing manifests safe: an
         explicitly-configured relative `index_dir` keeps today's meaning
         even inside a `legacy/`+`analysis/` layout. An explicit
         `analysis_dir` suppresses this branch (see the comment on it below).
      3. Otherwise, if `resolve_analysis_dir` finds an analysis directory
         (override or convention) -> `<analysis_dir>/index/code-search`.
      4. Otherwise -> `repo_root/legacylift-docs/index/code-search`, today's
         behavior, unchanged.

    The CLI flags do not reach here directly: every command folds them into
    the manifest through `apply_path_overrides`, which is the one place their
    precedence is decided (`CR-03`/`CR-04`).

    Args:
        repo_root: Repository root directory.
        manifest: Loaded manifest configuration.

    Returns:
        Absolute path to the index directory.
    """
    index_dir = Path(manifest.index.index_dir)
    if index_dir.is_absolute():
        return index_dir

    default_index_dir = IndexConfig.model_fields["index_dir"].default
    # An EXPLICIT analysis_dir wins over branch 2, but NOT over branch 1
    # above. The plan's wording is that --analysis-dir "overrides the whole
    # question", and branch 2 running first would break that: a manifest with
    # a non-default relative index_dir would keep writing inside the client
    # checkout -- the exact pollution this layout change exists to end --
    # while the knowledge store obeyed the override, silently splitting the
    # two stores across two roots. Branch 2 still wins when no override is
    # given, which is the regression guard for existing manifests that this
    # ordering preserves. An ABSOLUTE index_dir (branch 1) is the documented
    # carve-out and is also how an explicit --index-dir flag beats an
    # explicit --analysis-dir flag on every command alike.
    explicit_analysis_dir = manifest.index.analysis_dir is not None

    # CR-02: compared as PATHS, not as strings. A raw string compare read
    # "./legacylift-docs/index/code-search" and the Windows hand-edit
    # "legacylift-docs\index\code-search" as explicit configuration, so a
    # manifest holding the default in disguise took this branch and put the
    # index back inside the client checkout while the knowledge store obeyed
    # the relocated layout. See `is_default_setting`.
    if not is_default_setting(manifest.index.index_dir, default_index_dir):
        if not explicit_analysis_dir:
            return (repo_root / index_dir).resolve()

    analysis_dir = resolve_analysis_dir(repo_root, manifest)
    if analysis_dir is not None:
        return analysis_dir / "index" / "code-search"

    return (repo_root / index_dir).resolve()


def resolve_knowledge_dir(repo_root: Path, manifest: Manifest) -> Path:
    """Resolve the absolute durable knowledge-store directory path.

    Analogous to `resolve_index_dir`, but for the durable knowledge store
    (Milestone 1 of `domain-enhancements-plan.md`), which lives outside the
    gitignored index directory and is never deleted by `--reset`.

    Branches, in order:
      1. `manifest.index.knowledge_dir` is absolute -> used as-is.
      2. It differs from the packaged default -> the user has explicitly
         configured it, so it resolves against `repo_root` exactly as it
         always has (the regression guard for existing manifests).
      3. Otherwise, if `resolve_analysis_dir` finds an analysis directory
         (override or convention) -> `<analysis_dir>/knowledge`.
      4. Otherwise -> `repo_root/legacylift-docs/knowledge`, today's
         behavior, unchanged.

    Args:
        repo_root: Repository root directory.
        manifest: Loaded manifest configuration.

    Returns:
        Absolute path to the knowledge-store directory.
    """
    knowledge_dir = Path(manifest.index.knowledge_dir)
    if knowledge_dir.is_absolute():
        return knowledge_dir

    default_knowledge_dir = IndexConfig.model_fields["knowledge_dir"].default
    # An EXPLICIT analysis_dir wins over branch 2, but NOT over branch 1
    # above -- the same ordering `resolve_index_dir` documents at length.
    # Note the asymmetry that is deliberate: --index-dir names the INDEX
    # directory only, so it never reaches this resolver; --analysis-dir
    # governs both stores. Branch 2 still wins when no override is given,
    # which is the regression guard for existing manifests.
    explicit_analysis_dir = manifest.index.analysis_dir is not None

    # CR-02: compared as PATHS, not as strings -- see the twin comment in
    # `resolve_index_dir` and `is_default_setting`.
    if not is_default_setting(manifest.index.knowledge_dir, default_knowledge_dir):
        if not explicit_analysis_dir:
            return (repo_root / knowledge_dir).resolve()

    analysis_dir = resolve_analysis_dir(repo_root, manifest)
    if analysis_dir is not None:
        return analysis_dir / "knowledge"

    return (repo_root / knowledge_dir).resolve()
