"""Shared pytest helpers for the legacylift_search suite.

``sql_grammar`` exists because the SQL extractor's tree-sitter path and its
regex-recovery path are *different* code paths with different outputs: a test
that pins tree-sitter behavior is meaningless without the grammar, and on an
interpreter that has no ``tree_sitter`` at all it used to FAIL rather than skip,
which reads as a real regression instead of a missing dependency (ExecPlan
sql-extractor-temp-cte-fk, Milestone 4, acceptance criterion 3).

Note this is about the *grammar*, not the language key: ``get_language("sql")``
resolves from a static table whether or not a parser can be built.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _no_ansi_in_cli_output():
    """Force Rich to render help and banners without colour, for every test.

    Not cosmetic, and not CI-specific plumbing: without it, roughly a dozen
    CLI assertions pass locally and fail on any machine where Rich detects
    colour support -- which is what GitHub Actions does. Rich renders an option
    name as SEPARATE style spans, so `--repo-root` reaches the test as
    `[1;2;36m-[0m[1;2;36m-repo[0m[1;2;36m-root[0m`
    and a plain `"--repo-root" in result.stdout` is False even though the flag
    is right there on screen. The failure therefore says "ingest is missing
    --repo-root", which is not true and sends the reader after a phantom
    regression in the CLI.

    Forcing colour off is the right fix rather than stripping ANSI at each
    assertion: these tests are about what the help *says*, never how it is
    painted, so the styling is noise they should never have been exposed to.
    `NO_COLOR` is the cross-tool convention; `TERM=dumb` covers the detection
    path that does not consult it. Session-scoped and autouse because a Console
    is constructed per render, and any test that forgets the guard would
    reintroduce the same machine-dependent failure.
    """
    import os

    os.environ["NO_COLOR"] = "1"
    os.environ["TERM"] = "dumb"
    os.environ.pop("FORCE_COLOR", None)
    yield


def sql_grammar_available() -> bool:
    """True if a tree-sitter SQL parser can actually be built in this env."""
    try:
        from legacylift_search.extractors import _get_parser_for
        from legacylift_search.languages import get_language

        parser, _name = _get_parser_for(get_language("sql"))
        return parser is not None
    except Exception:
        return False


requires_sql_grammar = pytest.mark.skipif(
    not sql_grammar_available(),
    reason="tree-sitter-sql grammar unavailable; tree-sitter-path assertions "
    "do not apply (run via the project .venv)",
)
