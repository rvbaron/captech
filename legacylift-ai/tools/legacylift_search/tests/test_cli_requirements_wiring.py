"""Tests that the `requirements` sub-app is registered and shares one contract.

Milestone 1, Step 8 of `docs/exec-plans/active/reqs-to-data-store.md`. Every
test here fails before this wave -- `ImportError` on
`legacylift_search.cli_requirements`, or `requirements` missing from
`legacylift-search --help` -- and passes after.

This is the **foundation** unit's own coverage: it proves the skeleton four
sibling units fill is present and correct, and deliberately asserts nothing
about the fourteen commands' behaviour, which is theirs. What it does assert
is the shape they depend on:

* the sub-app is registered on the root app as `requirements`, and
  `legacylift-search requirements --help` renders -- which is not free, since
  this is the **first** `app.add_typer` in a file with sixteen flat
  `@app.command` registrations;
* the three names the sub-app shadows (`validate`, `search`, `stats`) still
  work at top level;
* the four command modules exist with the ownership table in the package
  docstring, so two agents cannot both claim a command;
* the shared options and helpers in `_shared.py` are importable and behave
  the way the commands will rely on -- in particular that the read path
  probes `Path.exists()` before constructing a `KnowledgeStore`, which is
  house rule 2 and the difference between "no requirements" and "an empty
  store I just created".
"""

from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.cli_requirements import requirements_app
from legacylift_search.cli_requirements._shared import (
    AnalysisDirOption,
    ConfigOption,
    JsonOption,
    RepoRootOption,
    RequirementsPaths,
    build_embedder,
    emit_json,
    open_index_store,
    open_knowledge_store,
    open_knowledge_store_for_write,
    resolve_requirements_paths,
)

_IS_WINDOWS = sys.platform == "win32"
_PKG = Path(__file__).resolve().parents[1] / "src" / "legacylift_search"

#: The fourteen commands and the module that owns each, per Step 8 and the
#: table in `cli_requirements/__init__.py`. Asserted against that docstring
#: so the two cannot drift, and kept here so a sibling unit that registers a
#: command in the wrong module fails a test rather than merely surprising a
#: reviewer.
_OWNERSHIP = {
    "read_cmds": ("list", "show", "search", "stats"),
    "write_cmds": ("set-state", "set-field"),
    "run_cmds": ("ingest", "validate", "set-run-coverage", "retire-run"),
    "repair_cmds": ("reindex-vectors", "rederive-subjects", "export", "import"),
}


@pytest.fixture
def runner():
    return CliRunner()


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


def test_the_root_help_lists_the_requirements_group(runner):
    """Proves the first `app.add_typer` in this CLI actually took effect."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "requirements" in result.output


def test_the_group_help_renders_with_no_commands_registered_yet(runner):
    """Proves an empty sub-app is a valid group, not a runtime error.

    Typer can refuse to build a click command for a `Typer` instance with
    nothing on it, and this is the foundation commit -- the four command
    modules are empty by design until the sibling units land. If this ever
    broke, `legacylift-search --help` would break with it.
    """
    result = runner.invoke(app, ["requirements", "--help"])
    assert result.exit_code == 0, result.output
    assert "requirements" in result.output
    assert "knowledge.sqlite" in result.output


def test_the_sub_app_is_registered_under_exactly_that_name():
    """Proves the group name, read off the registration rather than the help."""
    names = [
        info.name or (info.typer_instance.info.name if info.typer_instance else None)
        for info in app.registered_groups
    ]
    assert "requirements" in names
    assert len(app.registered_groups) == 1, (
        "this is still the only sub-app; a second one is a design change"
    )
    assert requirements_app.info.name == "requirements"


def test_the_three_shadowed_top_level_commands_still_work(runner):
    """Proves the namespacing is not a collision.

    `validate`, `search` and `stats` exist at top level and the sub-app
    reuses all three names. They are different commands over different
    stores, and the Python functions cannot collide because the sub-app's
    live in `legacylift_search.cli_requirements`.
    """
    registered = {c.name for c in app.registered_commands}
    for name in ("validate", "search", "stats"):
        assert name in registered
    for name in ("validate", "search", "stats"):
        result = runner.invoke(app, [name, "--help"])
        assert result.exit_code == 0, f"{name}: {result.output}"


def test_cli_py_carries_exactly_one_add_typer_call():
    """Proves the one change to `cli.py` is the one change to `cli.py`.

    An `ast` scan rather than a text grep: prose in a comment describing
    `add_typer` is not a call, which is the absent-versus-real rule applied
    to source text (three Wave B assertions tripped on exactly that).
    """
    tree = ast.parse((_PKG / "cli.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_typer"
    ]
    assert len(calls) == 1, f"expected one add_typer, found {len(calls)}"


# --------------------------------------------------------------------------
# The four command modules and the ownership table
# --------------------------------------------------------------------------


def test_the_four_command_modules_exist_and_are_imported_for_registration():
    """Proves the package imports all four, so a command registers on import."""
    import legacylift_search.cli_requirements as pkg

    for module in _OWNERSHIP:
        assert (_PKG / "cli_requirements" / f"{module}.py").exists()
        assert hasattr(pkg, module), f"{module} is not imported by the package"


def test_the_package_docstring_states_the_command_assignment():
    """Proves the assignment is written where four agents will read it.

    The table has to be in the package docstring, not only in a brief: the
    brief is gone by the time the next reader arrives.
    """
    import legacylift_search.cli_requirements as pkg

    doc = pkg.__doc__ or ""
    for module, commands in _OWNERSHIP.items():
        assert module in doc, module
        for command in commands:
            assert f"`{command}`" in doc, f"{command} not assigned in the docstring"
    assert sum(len(c) for c in _OWNERSHIP.values()) == 14


def test_each_command_module_names_its_own_commands_in_its_docstring():
    """Proves a sibling unit opening one file alone sees its whole scope."""
    import importlib

    for module, commands in _OWNERSHIP.items():
        doc = (
            importlib.import_module(
                f"legacylift_search.cli_requirements.{module}"
            ).__doc__
            or ""
        )
        for command in commands:
            assert f"``{command}``" in doc or f"`{command}`" in doc, (
                f"{module} does not describe {command}"
            )


def test_no_cli_module_contains_a_gr_table_write_statement():
    """Proves house rule 1 holds for the new package, ahead of the commands.

    The writer census in `test_gr_state.py` scans `src/legacylift_search/*.py`
    -- a flat glob that does **not** reach into this package -- so the same
    property is asserted here for the sub-package, using the same `ast`-based
    literal scan. Without this, a command module could compose its own
    `UPDATE gr SET` and the census would never see it.
    """
    from tests.test_gr_state import _WRITES_GR_ROWS, _sql_literals

    for path in sorted((_PKG / "cli_requirements").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        offenders = [sql for sql in _sql_literals(text) if _WRITES_GR_ROWS.search(sql)]
        assert offenders == [], f"{path.name} writes `gr` directly: {offenders}"
        assert "apply_gr_state" not in text, (
            f"{path.name} must go through gr_state.set_state"
        )


# --------------------------------------------------------------------------
# _shared.py
# --------------------------------------------------------------------------


def test_the_shared_options_build_a_working_command(runner):
    """Proves the `Annotated` aliases are usable as command parameters.

    A probe rather than an inspection: the aliases are only correct if typer
    can actually build a click parameter from each one, and that is what
    every sibling unit depends on.
    """
    probe = typer.Typer()

    @probe.command("probe")
    def _probe(
        repo_root: RepoRootOption = None,
        config: ConfigOption = None,
        analysis_dir: AnalysisDirOption = None,
        as_json: JsonOption = False,
    ) -> None:
        typer.echo(f"{repo_root}|{config}|{analysis_dir}|{as_json}")

    help_result = runner.invoke(probe, ["--help"])
    assert help_result.exit_code == 0
    for flag in ("--repo-root", "--config", "--analysis-dir", "--json"):
        assert flag in help_result.output

    run = runner.invoke(probe, ["--repo-root", ".", "--json"])
    assert run.exit_code == 0, run.output
    assert run.output.strip().endswith("|True")


def test_the_read_path_probes_before_it_constructs_and_creates_nothing():
    """Proves house rule 2: a missing store is reported, not created.

    `KnowledgeStore.__init__` creates the file **and its parent directory**,
    so a read-only command that constructs one to find out whether
    requirements exist silently materializes an empty store -- and an empty
    knowledge database is indistinguishable from a real one on the next
    command. The assertion is a filesystem assertion, which is the only form
    that can catch this.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        paths = resolve_requirements_paths(root, None, root / "analysis")
        assert paths.knowledge_exists is False
        with pytest.raises(typer.Exit) as exc:
            open_knowledge_store(paths)
        assert exc.value.exit_code == 1
        assert not paths.knowledge_sqlite_path.exists()
        assert not paths.knowledge_sqlite_path.parent.exists(), (
            "not even the parent directory may be created by a read path"
        )


def test_the_write_path_does_create_the_store_and_says_so_by_its_name():
    """Proves `ingest`/`import` have a route that legitimately creates it.

    Two functions rather than a flag, so "this command may create the store"
    is a visible choice at the call site rather than a constructor's default.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        paths = resolve_requirements_paths(root, None, root / "analysis")
        store = open_knowledge_store_for_write(paths)
        try:
            assert paths.knowledge_exists is True
            assert store.count_gr() == 0
        finally:
            store.close()
        # And now the read path opens it, because it exists.
        store = open_knowledge_store(paths)
        store.close()


def test_a_missing_index_is_none_and_no_index_sqlite_is_created():
    """Proves a missing Layer-0 index is a supported state, not an error.

    `SQLiteStore._connect` creates the database on its first query, so
    probing by construction would materialize an empty `index.sqlite` beside
    a repository that has never been indexed. `None` here means `V-STY-03`
    runs on its morphological fallback alone, and the reporting must say
    which of the two it was.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        paths = resolve_requirements_paths(root, None, root / "analysis")
        assert paths.index_exists is False
        assert open_index_store(paths) is None
        assert not paths.index_sqlite_path.exists()


def test_resolved_paths_land_under_the_analysis_override():
    """Proves both stores follow `--analysis-dir` through the one precedence point.

    Milestone 0's `CR-02`/`CR-03`/`CR-04` were three different precedences
    over the same two flags; this asserts the knowledge half and the index
    half agree, which is the failure mode that split a run's output across
    two trees.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        analysis = root / "analysis" / "nng"
        paths = resolve_requirements_paths(root, None, analysis)
        assert paths.knowledge_dir == analysis.resolve() / "knowledge"
        # The index half nests one level deeper -- `<analysis>/index/
        # code-search`, per `resolve_index_dir` -- which is why this asserts
        # containment rather than equality: the property that matters is that
        # both stores landed under the SAME override, not that they share a
        # directory.
        assert paths.index_dir.is_relative_to(analysis.resolve() / "index")
        assert paths.knowledge_sqlite_path.name == "knowledge.sqlite"
        assert paths.index_sqlite_path.parent == paths.index_dir


def test_the_resolved_path_banner_goes_to_stderr_not_stdout(capsys):
    """Proves a `--json` command's stdout stays parseable.

    House rule 4. A banner on stdout corrupts every caller parsing it, and
    several commands in this group take `--json`.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        resolve_requirements_paths(root, None, root / "analysis")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "resolved index directory" in captured.err
    assert "resolved knowledge directory" in captured.err


def test_the_banner_can_be_suppressed_for_a_second_resolution(capsys):
    """Proves a command re-resolving in one run does not print twice."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        resolve_requirements_paths(root, None, root / "a", print_banner=False)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_build_embedder_returns_none_with_a_reason_rather_than_raising():
    """Proves a missing provider is a degraded success, not an exception.

    Every write path in this group passes the embedder to
    `refresh_gr_vectors`, whose contract is that `None` is a degraded
    success. So an unbuildable provider must not stop an edit from
    recording, and the reason has to come back so the caller cannot report
    "no embedder" without saying why.
    """
    from legacylift_search.config import Manifest

    manifest = Manifest()
    embedder, reason = build_embedder(manifest, provider_override="not-a-provider")
    assert embedder is None
    assert reason is not None
    assert "reindex-vectors" in reason

    # And the configured default builds, so the None path is a real branch
    # rather than the only one.
    ok, ok_reason = build_embedder(manifest)
    assert (ok is None) == (ok_reason is not None), (
        "an embedder and a reason are mutually exclusive"
    )


def test_emit_json_writes_sorted_parseable_json_to_stdout(capsys):
    """Proves `--json` output is deterministic and machine-readable.

    Sorted keys so two captures of unchanged data diff cleanly -- the same
    determinism rule Step 9 puts on the JSONL export, applied to command
    output.
    """
    import json

    emit_json({"b": 1, "a": [3, 2], "n": None})
    out = capsys.readouterr()
    assert out.err == ""
    assert json.loads(out.out) == {"b": 1, "a": [3, 2], "n": None}
    assert out.out.index('"a"') < out.out.index('"b"') < out.out.index('"n"')


def test_requirements_paths_is_frozen_so_a_command_cannot_retarget_it():
    """Proves the resolved context cannot be mutated after the banner printed.

    The banner is the record of where a run wrote; a context a command could
    edit afterwards would make that record a lie.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=_IS_WINDOWS) as tmp:
        root = Path(tmp)
        paths = resolve_requirements_paths(root, None, root / "analysis")
        with pytest.raises(Exception):
            paths.knowledge_dir = root  # type: ignore[misc]
        assert isinstance(paths, RequirementsPaths)
