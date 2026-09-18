"""Tests for config.py manifest loading and writing."""

from pathlib import Path
import json
import tempfile

import pytest

from legacylift_search.config import (
    Manifest,
    ProjectConfig,
    IndexConfig,
    ChunkingConfig,
    EmbeddingConfig,
    SearchConfig,
    load_manifest,
    write_default_manifest,
    resolve_analysis_dir,
    resolve_index_dir,
    resolve_knowledge_dir,
    apply_path_overrides,
    is_default_setting,
)


def test_default_manifest_write_and_load_round_trip():
    """Test that a default manifest can be written and loaded back."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "semantic-search.manifest.json"

        # Write default manifest
        write_default_manifest(manifest_path, overwrite=False)
        assert manifest_path.exists()

        # Load it back
        manifest = load_manifest(manifest_path)

        # Verify key fields match the expected defaults
        assert manifest.schema_version == 1
        assert manifest.project.name == "current-repository"
        assert manifest.project.repo_roots == ["."]
        assert "**/*.cs" in manifest.project.include_globs
        assert "**/*.py" in manifest.project.include_globs
        assert "**/node_modules/**" in manifest.project.exclude_globs
        assert manifest.project.max_file_bytes == 2000000

        assert manifest.index.index_dir == "legacylift-docs/index/code-search"
        assert manifest.index.sqlite_file == "index.sqlite"
        assert manifest.index.chroma_dir == "chroma"
        assert manifest.index.collection_name == "code_chunks"
        assert manifest.index.reset_before_index is False
        assert manifest.index.store_full_chunk_text_in_sqlite is True

        assert manifest.chunking.target_tokens == 800
        assert manifest.chunking.max_tokens == 1400
        assert manifest.chunking.min_tokens == 80
        assert manifest.chunking.overlap_lines == 12
        assert manifest.chunking.prefer_ast_boundaries is True
        assert manifest.chunking.fallback_max_lines == 120

        assert manifest.embedding.provider == "qwen3"
        assert manifest.embedding.model == "Qwen/Qwen3-Embedding-0.6B"
        assert manifest.embedding.dimension == 1024
        assert manifest.embedding.batch_size == 512
        assert manifest.embedding.normalize is True
        assert manifest.embedding.device == "auto"

        assert manifest.search.default_limit == 10
        assert manifest.search.vector_candidates == 40
        assert manifest.search.lexical_candidates == 40
        assert manifest.search.rrf_rank_constant == 60
        assert manifest.search.graph_neighbor_depth == 1
        assert manifest.search.snippet_radius_lines == 8

        # No `languages` block: it was inert config and was removed. A manifest
        # that still carries one must keep loading, ignored.
        assert not hasattr(manifest, "languages")


def test_write_default_manifest_refuses_overwrite_by_default():
    """Test that write_default_manifest refuses to overwrite by default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "semantic-search.manifest.json"

        # Write first time succeeds
        write_default_manifest(manifest_path, overwrite=False)
        assert manifest_path.exists()

        # Write second time without overwrite should fail
        with pytest.raises(FileExistsError, match="already exists"):
            write_default_manifest(manifest_path, overwrite=False)


def test_write_default_manifest_allows_overwrite_when_explicit():
    """Test that write_default_manifest allows overwrite when explicitly requested."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = Path(tmpdir) / "semantic-search.manifest.json"

        # Write first time
        write_default_manifest(manifest_path, overwrite=False)
        original_mtime = manifest_path.stat().st_mtime

        # Write second time with overwrite=True should succeed
        import time
        time.sleep(0.01)  # Ensure mtime differs
        write_default_manifest(manifest_path, overwrite=True)
        new_mtime = manifest_path.stat().st_mtime

        # File should have been rewritten
        assert new_mtime >= original_mtime
        assert manifest_path.exists()


def test_load_manifest_fails_on_missing_file():
    """Test that load_manifest raises FileNotFoundError for missing files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        missing_path = Path(tmpdir) / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="Manifest not found"):
            load_manifest(missing_path)


def test_load_manifest_fails_on_invalid_json():
    """Test that load_manifest raises ValueError for invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_json_path = Path(tmpdir) / "bad.json"
        bad_json_path.write_text("{ not valid json", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_manifest(bad_json_path)


def test_load_manifest_fails_on_invalid_schema():
    """Test that load_manifest raises ValueError for schema violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        invalid_schema_path = Path(tmpdir) / "invalid-schema.json"

        # Valid JSON but wrong schema (missing required nested fields)
        invalid_schema_path.write_text(
            json.dumps({"schema_version": "not-an-int"}),
            encoding="utf-8"
        )

        with pytest.raises(ValueError, match="Invalid manifest schema"):
            load_manifest(invalid_schema_path)


def test_resolve_index_dir_relative():
    """Test that resolve_index_dir correctly resolves relative paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "my-repo"
        repo_root.mkdir()

        manifest = Manifest()
        # Default index_dir is "legacylift-docs/index/code-search"

        resolved = resolve_index_dir(repo_root, manifest)

        expected = (repo_root / "legacylift-docs" / "index" / "code-search").resolve()
        assert resolved == expected


def test_resolve_index_dir_absolute():
    """Test that resolve_index_dir returns absolute paths unchanged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "my-repo"
        repo_root.mkdir()

        absolute_index_dir = Path(tmpdir) / "absolute-index"

        manifest = Manifest()
        manifest.index.index_dir = str(absolute_index_dir)

        resolved = resolve_index_dir(repo_root, manifest)

        assert resolved == absolute_index_dir


def test_resolve_knowledge_dir_relative():
    """Test that resolve_knowledge_dir correctly resolves relative paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "my-repo"
        repo_root.mkdir()

        manifest = Manifest()
        # Default knowledge_dir is "legacylift-docs/knowledge"

        resolved = resolve_knowledge_dir(repo_root, manifest)

        expected = (repo_root / "legacylift-docs" / "knowledge").resolve()
        assert resolved == expected


def test_resolve_knowledge_dir_absolute():
    """Test that resolve_knowledge_dir returns absolute paths unchanged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "my-repo"
        repo_root.mkdir()

        absolute_knowledge_dir = Path(tmpdir) / "absolute-knowledge"

        manifest = Manifest()
        manifest.index.knowledge_dir = str(absolute_knowledge_dir)

        resolved = resolve_knowledge_dir(repo_root, manifest)

        assert resolved == absolute_knowledge_dir


def test_manifest_programmatic_construction():
    """Test that Manifest models can be constructed programmatically."""
    manifest = Manifest(
        schema_version=1,
        project=ProjectConfig(
            name="test-project",
            repo_roots=["./src"],
            max_file_bytes=1000000,
        ),
        embedding=EmbeddingConfig(
            provider="hash",
            dimension=64,
        ),
    )

    assert manifest.project.name == "test-project"
    assert manifest.project.repo_roots == ["./src"]
    assert manifest.embedding.provider == "hash"
    assert manifest.embedding.dimension == 64
    # Check defaults still apply
    assert manifest.chunking.target_tokens == 800


# --- analysis_dir resolution (Milestone 0, second half of
# docs/exec-plans/active/reqs-to-data-store.md) ---------------------------


def test_legacy_analysis_shape_resolves_under_analysis_dir(tmp_path):
    """repo_root under .../legacy/<system> with a sibling analysis/<system>
    that exists resolves index/knowledge underneath it."""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    repo_root = legacy_dir / "sys1"
    repo_root.mkdir()
    analysis_dir = tmp_path / "analysis" / "sys1"
    analysis_dir.mkdir(parents=True)

    manifest = Manifest()

    assert resolve_analysis_dir(repo_root, manifest) == analysis_dir.resolve()
    assert resolve_index_dir(repo_root, manifest) == analysis_dir / "index" / "code-search"
    assert resolve_knowledge_dir(repo_root, manifest) == analysis_dir / "knowledge"


def test_legacy_parent_without_analysis_sibling_falls_back(tmp_path):
    """repo_root.parent.name == 'legacy' but the sibling analysis/<system>
    does not exist -> fall back to <repo_root>/legacylift-docs/..."""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    repo_root = legacy_dir / "sys1"
    repo_root.mkdir()
    # Deliberately do NOT create tmp_path / "analysis" / "sys1"

    manifest = Manifest()

    assert resolve_analysis_dir(repo_root, manifest) is None
    assert resolve_index_dir(repo_root, manifest) == (
        repo_root / "legacylift-docs" / "index" / "code-search"
    ).resolve()
    assert resolve_knowledge_dir(repo_root, manifest) == (
        repo_root / "legacylift-docs" / "knowledge"
    ).resolve()


def test_no_legacy_parent_falls_back_like_ctcm_api(tmp_path):
    """No 'legacy' parent at all (the repos/ctcm/ctcm-api shape) -> falls
    back to <repo_root>/legacylift-docs/..., exactly as it does today."""
    repo_root = tmp_path / "ctcm" / "ctcm-api"
    repo_root.mkdir(parents=True)

    manifest = Manifest()

    assert resolve_analysis_dir(repo_root, manifest) is None
    assert resolve_index_dir(repo_root, manifest) == (
        repo_root / "legacylift-docs" / "index" / "code-search"
    ).resolve()
    assert resolve_knowledge_dir(repo_root, manifest) == (
        repo_root / "legacylift-docs" / "knowledge"
    ).resolve()


def test_analysis_dir_override_wins_when_detection_would_succeed(tmp_path):
    """An explicit analysis_dir override wins over the legacy/analysis
    convention even when that convention's directory exists."""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    repo_root = legacy_dir / "sys1"
    repo_root.mkdir()
    (tmp_path / "analysis" / "sys1").mkdir(parents=True)

    override = tmp_path / "custom-analysis"
    manifest = Manifest()
    manifest.index.analysis_dir = str(override)

    assert resolve_analysis_dir(repo_root, manifest) == override
    assert resolve_index_dir(repo_root, manifest) == override / "index" / "code-search"
    assert resolve_knowledge_dir(repo_root, manifest) == override / "knowledge"


def test_analysis_dir_override_wins_when_detection_would_fail(tmp_path):
    """An explicit analysis_dir override applies even with no legacy/
    parent and no analysis/ sibling at all, and even though the override
    directory does not yet exist."""
    repo_root = tmp_path / "ctcm" / "ctcm-api"
    repo_root.mkdir(parents=True)

    override = tmp_path / "does-not-exist-yet"
    assert not override.exists()

    manifest = Manifest()
    manifest.index.analysis_dir = str(override)

    assert resolve_analysis_dir(repo_root, manifest) == override
    assert resolve_index_dir(repo_root, manifest) == override / "index" / "code-search"
    assert resolve_knowledge_dir(repo_root, manifest) == override / "knowledge"


def test_analysis_dir_override_relative_resolves_against_repo_root(tmp_path):
    """A relative analysis_dir override resolves against repo_root."""
    repo_root = tmp_path / "ctcm" / "ctcm-api"
    repo_root.mkdir(parents=True)

    manifest = Manifest()
    manifest.index.analysis_dir = "../analysis-out"

    expected = (repo_root / "../analysis-out").resolve()
    assert resolve_analysis_dir(repo_root, manifest) == expected


def test_analysis_dir_override_absolute_used_as_is(tmp_path):
    """An absolute analysis_dir override is used as-is."""
    repo_root = tmp_path / "ctcm" / "ctcm-api"
    repo_root.mkdir(parents=True)

    absolute_override = tmp_path / "absolute-analysis"
    manifest = Manifest()
    manifest.index.analysis_dir = str(absolute_override)

    assert resolve_analysis_dir(repo_root, manifest) == absolute_override


def test_absolute_index_dir_wins_over_everything(tmp_path):
    """Branch 1: an absolute index_dir wins even inside the legacy/analysis
    shape and even with an analysis_dir override also set."""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    repo_root = legacy_dir / "sys1"
    repo_root.mkdir()
    (tmp_path / "analysis" / "sys1").mkdir(parents=True)

    absolute_index_dir = tmp_path / "absolute-index"
    manifest = Manifest()
    manifest.index.index_dir = str(absolute_index_dir)
    manifest.index.analysis_dir = str(tmp_path / "custom-analysis")

    assert resolve_index_dir(repo_root, manifest) == absolute_index_dir


def test_nondefault_relative_index_dir_resolves_against_repo_root_regression_guard(
    tmp_path,
):
    """Branch 2: a non-default relative index_dir still resolves against
    repo_root even inside the legacy/analysis shape. This is the regression
    guard for existing manifests that explicitly configured index_dir before
    the analysis_dir convention existed."""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    repo_root = legacy_dir / "sys1"
    repo_root.mkdir()
    (tmp_path / "analysis" / "sys1").mkdir(parents=True)

    manifest = Manifest()
    manifest.index.index_dir = "custom/index/path"

    expected = (repo_root / "custom" / "index" / "path").resolve()
    assert resolve_index_dir(repo_root, manifest) == expected


def test_nondefault_relative_knowledge_dir_resolves_against_repo_root_regression_guard(
    tmp_path,
):
    """Branch 2 for knowledge_dir, mirroring the index_dir regression
    guard above."""
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    repo_root = legacy_dir / "sys1"
    repo_root.mkdir()
    (tmp_path / "analysis" / "sys1").mkdir(parents=True)

    manifest = Manifest()
    manifest.index.knowledge_dir = "custom/knowledge/path"

    expected = (repo_root / "custom" / "knowledge" / "path").resolve()
    assert resolve_knowledge_dir(repo_root, manifest) == expected


def test_resolve_analysis_dir_returns_none_on_fallback_shapes(tmp_path):
    """resolve_analysis_dir returns None both when there is no legacy/
    parent and when there is a legacy/ parent but no analysis/ sibling."""
    # No legacy/ parent at all.
    repo_root_a = tmp_path / "ctcm" / "ctcm-api"
    repo_root_a.mkdir(parents=True)
    assert resolve_analysis_dir(repo_root_a, Manifest()) is None

    # legacy/ parent present but sibling analysis/<system> missing.
    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    repo_root_b = legacy_dir / "sys1"
    repo_root_b.mkdir()
    assert resolve_analysis_dir(repo_root_b, Manifest()) is None


# ----------------------------------------------------------------------
# An EXPLICIT analysis_dir override beats a non-default relative setting
#
# Regression guard for a real divergence: branch 2 (a non-default relative
# index_dir resolves against repo_root) used to be evaluated BEFORE the
# analysis-dir override, so `--analysis-dir D:\out` on a manifest carrying
# `"index_dir": ".legacylift"` wrote the index INSIDE the client checkout
# while the knowledge store obeyed the override -- splitting the two stores
# and silently ignoring the flag for the larger half.
# ----------------------------------------------------------------------


def test_explicit_analysis_dir_override_beats_nondefault_relative_index_dir(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "legacy" / "sys1"
    repo_root.mkdir(parents=True)
    override = tmp_path / "elsewhere"

    manifest = Manifest()
    manifest.index.index_dir = ".legacylift"
    manifest.index.knowledge_dir = "custom-knowledge"
    manifest.index.analysis_dir = str(override)

    assert resolve_index_dir(repo_root, manifest) == override / "index" / "code-search"
    assert resolve_knowledge_dir(repo_root, manifest) == override / "knowledge"
    # And nothing lands inside the checkout.
    assert repo_root not in resolve_index_dir(repo_root, manifest).parents


def test_nondefault_relative_setting_still_wins_without_an_override(
    tmp_path: Path,
) -> None:
    """The other half of the same rule: with NO override, an explicitly
    configured relative setting keeps meaning exactly what it always meant.
    This is the existing-manifest regression guard, and the fix above must
    not have cost it."""
    repo_root = tmp_path / "legacy" / "sys1"
    repo_root.mkdir(parents=True)
    (tmp_path / "analysis" / "sys1").mkdir(parents=True)

    manifest = Manifest()
    manifest.index.index_dir = ".legacylift"

    assert resolve_index_dir(repo_root, manifest) == (repo_root / ".legacylift").resolve()
    # knowledge_dir is left at its default, so it DOES follow the detection.
    assert (
        resolve_knowledge_dir(repo_root, manifest)
        == (tmp_path / "analysis" / "sys1" / "knowledge")
    )


# ----------------------------------------------------------------------
# CR-02: the default is detected as a PATH, not as a string
# ----------------------------------------------------------------------
# The two resolvers decided "has the user explicitly configured this?" with a
# raw string compare against the packaged default, so a manifest holding the
# default in disguise -- a leading "./", or the natural Windows hand-edit with
# backslashes -- read as explicit configuration, took branch 2, and put the
# index back inside the client checkout while the knowledge store obeyed the
# relocated layout. That is the two-roots split the branch ordering exists to
# prevent, and it is silent.


def _relocated(tmp_path: Path) -> tuple[Path, Path]:
    """The legacy/+analysis convention: returns (repo_root, analysis_dir)."""
    repo_root = tmp_path / "legacy" / "sys1"
    repo_root.mkdir(parents=True)
    analysis_dir = tmp_path / "analysis" / "sys1"
    analysis_dir.mkdir(parents=True)
    return repo_root, analysis_dir


@pytest.mark.parametrize(
    "written",
    [
        "./legacylift-docs/index/code-search",
        "legacylift-docs\\index\\code-search",
        "legacylift-docs//index/code-search",
    ],
    ids=["dot-slash", "windows-backslashes", "double-slash"],
)
def test_normalized_default_index_dir_is_not_read_as_explicit(
    tmp_path: Path, written: str
) -> None:
    repo_root, analysis_dir = _relocated(tmp_path)
    manifest = Manifest()
    manifest.index.index_dir = written

    resolved = resolve_index_dir(repo_root, manifest)

    assert resolved == analysis_dir / "index" / "code-search"
    # And the two stores must not split across two roots.
    assert resolve_knowledge_dir(repo_root, manifest) == analysis_dir / "knowledge"


@pytest.mark.parametrize(
    "written",
    [
        "./legacylift-docs/knowledge",
        "legacylift-docs\\knowledge",
    ],
    ids=["dot-slash", "windows-backslashes"],
)
def test_normalized_default_knowledge_dir_is_not_read_as_explicit(
    tmp_path: Path, written: str
) -> None:
    repo_root, analysis_dir = _relocated(tmp_path)
    manifest = Manifest()
    manifest.index.knowledge_dir = written

    assert resolve_knowledge_dir(repo_root, manifest) == analysis_dir / "knowledge"


def test_is_default_setting_distinguishes_disguise_from_configuration() -> None:
    default = IndexConfig.model_fields["index_dir"].default
    assert is_default_setting("./" + default, default)
    assert is_default_setting(default.replace("/", "\\"), default)
    assert not is_default_setting(".legacylift", default)
    assert not is_default_setting("legacylift-docs/index", default)


def test_a_genuinely_different_relative_index_dir_is_still_explicit(
    tmp_path: Path,
) -> None:
    """The CR-02 fix must not swallow real configuration."""
    repo_root, _analysis_dir = _relocated(tmp_path)
    manifest = Manifest()
    manifest.index.index_dir = "./.legacylift"

    assert resolve_index_dir(repo_root, manifest) == (repo_root / ".legacylift")


# ----------------------------------------------------------------------
# CR-03 / CR-04: ONE precedence for the two flags
# ----------------------------------------------------------------------


def test_apply_path_overrides_makes_index_dir_flag_cwd_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-04: the FLAG is CWD-relative, like every other CLI path argument.

    `index`/`backfill-vectors`/`search` used to store it verbatim, so the same
    `--index-dir out` meant <repo_root>/out there and <cwd>/out on the seven
    `resolve_paths` commands.
    """
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(cwd)

    manifest = apply_path_overrides(Manifest(), Path("out"), None)

    assert resolve_index_dir(repo_root, manifest) == cwd / "out"


def test_apply_path_overrides_makes_analysis_dir_flag_cwd_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(cwd)

    manifest = apply_path_overrides(Manifest(), None, Path("B"))

    assert resolve_index_dir(repo_root, manifest) == cwd / "B" / "index" / "code-search"
    assert resolve_knowledge_dir(repo_root, manifest) == cwd / "B" / "knowledge"


def test_index_dir_flag_beats_analysis_dir_flag_for_the_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-03: with both flags given there is now ONE answer.

    `--index-dir` wins for the index directory (it resolves absolute and so
    lands on branch 1, the documented carve-out), while `--analysis-dir` still
    governs the knowledge store, which `--index-dir` says nothing about.
    """
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(cwd)

    manifest = apply_path_overrides(Manifest(), Path("out"), Path("B"))

    assert resolve_index_dir(repo_root, manifest) == cwd / "out"
    assert resolve_knowledge_dir(repo_root, manifest) == cwd / "B" / "knowledge"


def test_apply_path_overrides_leaves_the_manifest_alone_when_no_flags_given(
    tmp_path: Path,
) -> None:
    repo_root, analysis_dir = _relocated(tmp_path)
    manifest = apply_path_overrides(Manifest(), None, None)

    assert manifest.index.analysis_dir is None
    assert (
        resolve_index_dir(repo_root, manifest)
        == analysis_dir / "index" / "code-search"
    )
