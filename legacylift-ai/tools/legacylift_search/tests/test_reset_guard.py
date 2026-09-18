"""Tests for `Indexer._validate_reset_path` — the `index --reset` guard.

Milestone 0 of `docs/exec-plans/active/reqs-to-data-store.md` widens this
guard, which had never had a single test. Its old final clause required the
delete target to be a descendant of `<repo_root>/legacylift-docs/`, which is
exactly the layout that milestone replaces: after the relocation the index
resolves under `<app>/analysis/<system>/` while `--repo-root` still points at
`<app>/legacy/<system>/`, so `relative_to` raised and `--reset` failed on
every relocated repository.

The guard now takes two clauses in place of that one:
  * the target must be under `<repo_root>/legacylift-docs/` **or** under the
    resolved analysis directory (the same two branches as the resolver), and
  * the target must show positive evidence of being an index directory —
    `index.sqlite`, a `chroma/` subdirectory, or empty/absent.

Everything the guard refused before it must still refuse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from legacylift_search.config import Manifest, resolve_index_dir
from legacylift_search.indexer import Indexer


# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------
def _indexer(repo_root: Path, analysis_dir: str | None = None) -> Indexer:
    """Build an Indexer with a default manifest and the given repo root."""
    manifest = Manifest()
    if analysis_dir is not None:
        manifest.index.analysis_dir = analysis_dir
    return Indexer(manifest, repo_root)


def _index_dir(path: Path, *, sqlite: bool = True, chroma: bool = False) -> Path:
    """Create `path` and populate it so it looks like a real index dir."""
    path.mkdir(parents=True, exist_ok=True)
    if sqlite:
        (path / "index.sqlite").write_bytes(b"")
    if chroma:
        (path / "chroma").mkdir(exist_ok=True)
    return path


def _relocated_layout(tmp_path: Path) -> tuple[Path, Path]:
    """The `legacy/` + `analysis/` shape: returns (repo_root, analysis_dir)."""
    repo_root = tmp_path / "legacy" / "sys1"
    repo_root.mkdir(parents=True)
    analysis_dir = tmp_path / "analysis" / "sys1"
    analysis_dir.mkdir(parents=True)
    return repo_root, analysis_dir


# ----------------------------------------------------------------------
# 1. The relocated shape is accepted (the bug this milestone fixes)
# ----------------------------------------------------------------------
def test_relocated_analysis_dir_accepted(tmp_path: Path) -> None:
    """<app>/analysis/<system>/index/code-search is accepted with
    --repo-root still pointing at <app>/legacy/<system>/."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    target = _index_dir(analysis_dir / "index" / "code-search")

    _indexer(repo_root)._validate_reset_path(target)


def test_relocated_shape_raised_before_the_fix(tmp_path: Path) -> None:
    """Regression pin: the relocated target is NOT under
    <repo_root>/legacylift-docs/, which is what the old clause required."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    target = analysis_dir / "index" / "code-search"

    with pytest.raises(ValueError):
        target.resolve().relative_to((repo_root / "legacylift-docs").resolve())


def test_relocated_shape_accepts_chroma_only_index(tmp_path: Path) -> None:
    """chroma/ alone is enough positive evidence (index.sqlite absent)."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    target = _index_dir(
        analysis_dir / "index" / "code-search", sqlite=False, chroma=True
    )

    _indexer(repo_root)._validate_reset_path(target)


# ----------------------------------------------------------------------
# 2. The fallback shape still behaves exactly as it does today
# ----------------------------------------------------------------------
def test_legacylift_docs_fallback_accepted(tmp_path: Path) -> None:
    """The repos/ctcm/ctcm-api shape: no legacy/ parent, so the index lives
    under <repo_root>/legacylift-docs/ and must keep working."""
    repo_root = tmp_path / "ctcm-api"
    repo_root.mkdir()
    target = _index_dir(repo_root / "legacylift-docs" / "index" / "code-search")

    _indexer(repo_root)._validate_reset_path(target)


def test_legacylift_docs_fallback_still_works_in_relocated_layout(
    tmp_path: Path,
) -> None:
    """Both branches are live at once: a repo that has an analysis sibling can
    still reset a legacylift-docs/ index left over from before the move."""
    repo_root, _analysis_dir = _relocated_layout(tmp_path)
    target = _index_dir(repo_root / "legacylift-docs" / "index" / "code-search")

    _indexer(repo_root)._validate_reset_path(target)


def test_custom_sqlite_file_name_accepted(tmp_path: Path) -> None:
    """A manifest that renames sqlite_file must not get its real index dir
    refused by the positive-evidence clause."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = repo_root / "legacylift-docs" / "index" / "code-search"
    target.mkdir(parents=True)
    (target / "custom.sqlite").write_bytes(b"")

    indexer = _indexer(repo_root)
    indexer.manifest.index.sqlite_file = "custom.sqlite"

    indexer._validate_reset_path(target)


# ----------------------------------------------------------------------
# 3. Positive evidence: an override naming somewhere unrelated is refused
# ----------------------------------------------------------------------
def test_override_naming_source_tree_refused(tmp_path: Path) -> None:
    """An --analysis-dir / index.analysis_dir typo that lands on a directory
    full of source files is refused, even though the prefix check passes."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    override = tmp_path / "srcdump"
    target = override / "index" / "code-search"
    target.mkdir(parents=True)
    (target / "Foo.java").write_text("class Foo {}", encoding="utf-8")
    (target / "Bar.java").write_text("class Bar {}", encoding="utf-8")

    indexer = _indexer(repo_root, analysis_dir=str(override))
    with pytest.raises(ValueError, match="no index in it"):
        indexer._validate_reset_path(target)


def test_non_empty_non_index_dir_refused_under_legacylift_docs(
    tmp_path: Path,
) -> None:
    """The positive-evidence clause is not override-specific: it also bites
    under the legacylift-docs/ ancestor."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = repo_root / "legacylift-docs" / "index" / "code-search"
    target.mkdir(parents=True)
    (target / "notes.md").write_text("hand-written", encoding="utf-8")

    with pytest.raises(ValueError, match="no index in it"):
        _indexer(repo_root)._validate_reset_path(target)


# ----------------------------------------------------------------------
# 4. Empty / absent targets are the legitimate first-run case
# ----------------------------------------------------------------------
def test_empty_dir_under_valid_ancestor_accepted(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = repo_root / "legacylift-docs" / "index" / "code-search"
    target.mkdir(parents=True)

    _indexer(repo_root)._validate_reset_path(target)


def test_missing_dir_under_valid_ancestor_accepted(tmp_path: Path) -> None:
    """`--reset` on a cold repository: the index dir does not exist yet."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    target = analysis_dir / "index" / "code-search"
    assert not target.exists()

    _indexer(repo_root)._validate_reset_path(target)


def test_override_to_nonexistent_dir_accepted(tmp_path: Path) -> None:
    """An override names where things GO, so a not-yet-created target under it
    is accepted — resolve_analysis_dir returns overrides unconditionally."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    override = tmp_path / "elsewhere" / "analysis" / "sys1"

    indexer = _indexer(repo_root, analysis_dir=str(override))
    indexer._validate_reset_path(override / "index" / "code-search")


# ----------------------------------------------------------------------
# 5. The clause-replaced ancestor check still bites
# ----------------------------------------------------------------------
def test_path_outside_both_ancestors_refused(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = _index_dir(tmp_path / "elsewhere" / "code-search")

    with pytest.raises(ValueError, match="outside the known output locations"):
        _indexer(repo_root)._validate_reset_path(target)


def test_wrong_sibling_analysis_dir_refused(tmp_path: Path) -> None:
    """A relocated repo may not reset another system's analysis directory."""
    repo_root, _analysis_dir = _relocated_layout(tmp_path)
    other = tmp_path / "analysis" / "sys2"
    target = _index_dir(other / "index" / "code-search")

    with pytest.raises(ValueError, match="outside the known output locations"):
        _indexer(repo_root)._validate_reset_path(target)


def test_ancestor_refusal_names_both_expected_locations(tmp_path: Path) -> None:
    """The message must tell the user which clause rejected the path and what
    it expected, so they know whether to fix the manifest or the flag."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    target = _index_dir(tmp_path / "elsewhere" / "code-search")

    with pytest.raises(ValueError) as exc:
        _indexer(repo_root)._validate_reset_path(target)

    message = str(exc.value)
    assert str((repo_root / "legacylift-docs").resolve()) in message
    assert str(analysis_dir.resolve()) in message


# ----------------------------------------------------------------------
# 6. Every pre-existing refusal still fires
# ----------------------------------------------------------------------
def test_drive_or_filesystem_root_refused(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    root = Path(tmp_path.anchor)

    with pytest.raises(ValueError, match="drive/filesystem root"):
        _indexer(repo_root)._validate_reset_path(root)


def test_user_home_refused(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(ValueError, match="user home directory"):
        _indexer(repo_root)._validate_reset_path(Path.home())


def test_repo_root_refused(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(ValueError, match="repository root"):
        _indexer(repo_root)._validate_reset_path(repo_root)


def test_non_index_like_directory_name_refused(tmp_path: Path) -> None:
    """A name that is neither in _INDEX_DIR_NAMES nor under
    legacylift-docs/index/ is refused before any ancestor check runs."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = _index_dir(repo_root / "src" / "main")

    with pytest.raises(ValueError, match="not a recognized index directory"):
        _indexer(repo_root)._validate_reset_path(target)


def test_index_like_name_alternatives_still_accepted(tmp_path: Path) -> None:
    """The other _INDEX_DIR_NAMES entries keep passing the name check."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for name in (".legacylift", "legacylift-index", "code-search-v2"):
        target = _index_dir(repo_root / "legacylift-docs" / name)
        _indexer(repo_root)._validate_reset_path(target)


# ----------------------------------------------------------------------
# CR-05: an interrupted reset must not make --reset unrecoverable
# ----------------------------------------------------------------------
# --reset deletes index.sqlite (+ -wal/-shm) and chroma/, but run() also
# writes manifest.snapshot.json and index.log into the same directory and
# nothing ever deletes those. So the state left by Ctrl-C during the rmtree of
# a multi-gigabyte chroma/ -- or by hand-deleting the database to force a
# rebuild -- used to hit the positive-evidence refusal, and the message
# offered "or to be empty" as the escape: a state --reset itself can never
# produce.


def _interrupted_reset_leftovers(index_dir: Path, *, extra: list[str] = []) -> Path:
    """The directory as an interrupted --reset leaves it: no DB, no chroma."""
    index_dir.mkdir(parents=True, exist_ok=True)
    (index_dir / "manifest.snapshot.json").write_text("{}", encoding="utf-8")
    (index_dir / "index.log").write_text("=== indexing started ===\n", encoding="utf-8")
    for name in extra:
        (index_dir / name).write_text("", encoding="utf-8")
    return index_dir


def test_interrupted_reset_leftovers_are_treated_as_empty(tmp_path: Path) -> None:
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    index_dir = _interrupted_reset_leftovers(
        analysis_dir / "index" / "code-search"
    )
    _indexer(repo_root)._validate_reset_path(index_dir)


def test_interrupted_reset_leftovers_with_orphan_wal_treated_as_empty(
    tmp_path: Path,
) -> None:
    """Ctrl-C between the DB unlink and the -wal unlink leaves these behind."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    index_dir = _interrupted_reset_leftovers(
        analysis_dir / "index" / "code-search",
        extra=["index.sqlite-wal", "index.sqlite-shm"],
    )
    _indexer(repo_root)._validate_reset_path(index_dir)


def test_leftovers_under_the_legacylift_docs_fallback_are_treated_as_empty(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    index_dir = _interrupted_reset_leftovers(
        repo_root / "legacylift-docs" / "index" / "code-search"
    )
    _indexer(repo_root)._validate_reset_path(index_dir)


def test_renamed_artifact_leftovers_are_treated_as_empty(tmp_path: Path) -> None:
    """A manifest that renames sqlite_file/chroma_dir is honoured here too."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    index_dir = analysis_dir / "index" / "code-search"
    index_dir.mkdir(parents=True)
    (index_dir / "custom.db-wal").write_text("", encoding="utf-8")
    (index_dir / "index.log").write_text("", encoding="utf-8")

    manifest = Manifest()
    manifest.index.sqlite_file = "custom.db"
    manifest.index.chroma_dir = "vectors"
    Indexer(manifest, repo_root)._validate_reset_path(index_dir)


def test_a_foreign_file_beside_the_leftovers_is_still_refused(
    tmp_path: Path,
) -> None:
    """The relaxation must stay narrow: anything not ours still refuses,
    and the message now names what it found."""
    repo_root, analysis_dir = _relocated_layout(tmp_path)
    index_dir = _interrupted_reset_leftovers(
        analysis_dir / "index" / "code-search", extra=["Program.cs"]
    )
    with pytest.raises(ValueError) as excinfo:
        _indexer(repo_root)._validate_reset_path(index_dir)
    message = str(excinfo.value)
    assert "no index in it" in message
    assert "Program.cs" in message


# ----------------------------------------------------------------------
# CR-06: the guard must agree with the resolver, not claim to
# ----------------------------------------------------------------------
# The parity comment said allowed_ancestors were "the SAME two branches that
# resolve_index_dir takes". They were branches 3 and 4 only, so --reset always
# raised for both configured-index_dir branches -- including
# index_dir=".legacylift", whose name is deliberately in _INDEX_DIR_NAMES so
# the name clause passes it.


def test_configured_relative_index_dir_is_accepted(tmp_path: Path) -> None:
    """Branch 2 of the resolver: a non-default RELATIVE index_dir."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manifest = Manifest()
    manifest.index.index_dir = ".legacylift"

    resolved = resolve_index_dir(repo_root, manifest)
    _index_dir(resolved)

    Indexer(manifest, repo_root)._validate_reset_path(resolved)


def test_configured_absolute_index_dir_is_accepted(tmp_path: Path) -> None:
    """Branch 1 of the resolver: an ABSOLUTE index_dir, outside the repo."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    elsewhere = tmp_path / "elsewhere" / "code-search"
    manifest = Manifest()
    manifest.index.index_dir = str(elsewhere)

    resolved = resolve_index_dir(repo_root, manifest)
    _index_dir(resolved)

    Indexer(manifest, repo_root)._validate_reset_path(resolved)


def test_configured_index_dir_does_not_widen_the_guard_elsewhere(
    tmp_path: Path,
) -> None:
    """Branches 1/2 admit the configured path, not everything."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    manifest = Manifest()
    manifest.index.index_dir = ".legacylift"

    unrelated = _index_dir(tmp_path / "somewhere-else" / "code-search")
    with pytest.raises(ValueError, match="outside the known output locations"):
        Indexer(manifest, repo_root)._validate_reset_path(unrelated)


def test_a_default_index_dir_in_disguise_does_not_add_an_ancestor(
    tmp_path: Path,
) -> None:
    """CR-02 and CR-06 interact: a manifest holding the normalized default is
    NOT explicit configuration, so it must not smuggle in a new ancestor."""
    repo_root, _analysis_dir = _relocated_layout(tmp_path)
    manifest = Manifest()
    manifest.index.index_dir = "./legacylift-docs/index/code-search"

    unrelated = _index_dir(tmp_path / "somewhere-else" / "code-search")
    with pytest.raises(ValueError, match="outside the known output locations"):
        Indexer(manifest, repo_root)._validate_reset_path(unrelated)


def test_the_configured_branches_still_obey_the_other_clauses(
    tmp_path: Path,
) -> None:
    """Widening allowed_ancestors must not disarm the name clause: an
    absolute index_dir with a non-index-like name is still refused."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bad = tmp_path / "Documents"
    manifest = Manifest()
    manifest.index.index_dir = str(bad)
    _index_dir(bad)

    with pytest.raises(ValueError, match="not a recognized index"):
        Indexer(manifest, repo_root)._validate_reset_path(bad)


# ----------------------------------------------------------------------
# The guard must not be WIDER than the resolver either
# ----------------------------------------------------------------------
def test_branch_two_is_suppressed_by_an_explicit_analysis_dir(
    tmp_path: Path,
) -> None:
    """`CR-06`, the other direction.

    `resolve_index_dir` admits branch 2 -- a non-default RELATIVE
    `index_dir` setting resolved against `repo_root` -- only when no
    explicit `analysis_dir` is given; an explicit one "overrides the whole
    question". The guard used to append that ancestor unconditionally, so it
    accepted, for deletion, a directory the resolver can never hand back.
    The comment above `allowed_ancestors` claims parity with the resolver,
    and parity has to hold in both directions or it is just a comment.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    analysis_dir = tmp_path / "analysis-out"
    analysis_dir.mkdir()

    manifest = Manifest()
    manifest.index.index_dir = "custom-out/code-search"
    manifest.index.analysis_dir = str(analysis_dir)

    # The resolver goes to the analysis directory, never to custom-out/.
    resolved = resolve_index_dir(repo_root, manifest)
    assert analysis_dir in resolved.parents

    stale = _index_dir(repo_root / "custom-out" / "code-search")
    indexer = Indexer(manifest, repo_root)
    with pytest.raises(ValueError, match="outside the known output locations"):
        indexer._validate_reset_path(stale)


def test_branch_two_still_wins_when_no_analysis_dir_is_given(
    tmp_path: Path,
) -> None:
    """The anti-over-widening guard above must not break branch 2 itself:
    with no `analysis_dir` override, a non-default relative `index_dir` is
    still what the resolver returns and still what `--reset` accepts."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    manifest = Manifest()
    manifest.index.index_dir = "custom-out/code-search"

    resolved = resolve_index_dir(repo_root, manifest)
    assert resolved == (repo_root / "custom-out" / "code-search").resolve()

    target = _index_dir(repo_root / "custom-out" / "code-search")
    Indexer(manifest, repo_root)._validate_reset_path(target)
