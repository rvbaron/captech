"""Pins for the two lists the 2026-09-08 coverage widening made load-bearing.

`ProjectConfig.include_globs` and the language registry's extension set are
now the inputs to a *measured number*: the extraction-gap walk reports NNG's
first-party byte gap as 0.00%, and `/modernize-extract-rules` measures its own
round-over-round coverage as a fraction of indexed chunks. Silently narrowing
either list would move both numbers with nothing to announce it -- and the
failure is invisible in the worst way, because an extraction run over a
too-small index still reports itself complete.

No test pinned either list before this file; several were expected to and none
existed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from legacylift_search.chunking import _CHONKIE_SKIP_LANGUAGES
from legacylift_search.config import ProjectConfig
from legacylift_search.languages import detect_language

# The eight patterns the widening added, and the reason each is here.
COVERAGE_WIDENING_GLOBS = (
    "**/*.xml",
    "**/*.jsp",
    "**/*.properties",
    "**/*.css",
    "**/*.vm",
    "**/*.ent",
    "**/*.tld",
    "**/*.xmi",
)

# The seven path-shaped XML patterns `**/*.xml` subsumed. They must NOT come
# back: re-adding them is harmless to behavior but signals that someone
# reverted the widening and reconstructed the old list from memory.
SUBSUMED_XML_GLOBS = (
    "**/*.hbm.xml",
    "**/*-flow.xml",
    "**/flows/**/*.xml",
    "**/*.beans.xml",
    "**/applicationContext*.xml",
    "**/spring/**/*.xml",
    "**/config/**/*.xml",
)


def _default_includes() -> list[str]:
    return list(ProjectConfig().include_globs)


@pytest.mark.parametrize("glob", COVERAGE_WIDENING_GLOBS)
def test_widening_glob_is_still_in_the_default_allow_list(glob: str) -> None:
    """Each one closes a measured slice of NNG's 276-file / 805 KB gap."""
    assert glob in _default_includes()


@pytest.mark.parametrize("glob", SUBSUMED_XML_GLOBS)
def test_subsumed_xml_glob_did_not_come_back(glob: str) -> None:
    assert glob not in _default_includes()


def test_default_allow_list_has_no_duplicates() -> None:
    """A duplicate is dead weight and a sign of a botched merge of this list."""
    globs = _default_includes()
    assert len(globs) == len(set(globs))


def test_default_allow_list_size_is_pinned() -> None:
    """20 language patterns + the 8 widening patterns.

    Pinned as a count as well as by membership so that ADDING a pattern also
    trips a test -- a new extension needs a registry entry, a Chonkie
    decision, and a re-measured gap number, none of which the membership
    tests above would notice.
    """
    assert len(_default_includes()) == 28


@pytest.mark.parametrize(
    "extension,expected_key",
    [
        (".jsp", "jsp"),
        (".properties", "properties"),
        (".css", "css"),
        (".vm", "velocity"),
        (".ent", "xml_entity"),
        (".tld", "tld"),
        (".xmi", "xmi"),
        (".xml", "xml"),
    ],
)
def test_widening_extension_resolves_to_its_language(
    extension: str, expected_key: str
) -> None:
    """`detect_language` is the gate after the allow-list.

    A glob without a registry entry buys nothing -- the file matches, then
    `discover_source_files` drops it for having no language, and the walk
    labels it `rejected_by="language"`. The two lists have to move together.
    """
    spec = detect_language(Path("sample" + extension))
    assert spec is not None, f"{extension} is allow-listed but has no language"
    assert spec.key == expected_key


@pytest.mark.parametrize(
    "extension,expected_key",
    [
        (".jsp", "jsp"),
        (".css", "css"),
        (".tld", "tld"),
        (".vm", "velocity"),
        (".xml", "xml"),
    ],
)
def test_languages_that_hang_chonkie_are_excluded_from_it(
    extension: str, expected_key: str
) -> None:
    """The trap that cost a measurement run, pinned so it cannot return.

    Chonkie has no code grammar for these, so it falls back to
    `language="auto"` detection, which does not terminate. Measured on real
    NNG files 2026-09-08: a 13.9 KB `.jsp` ran >600s before being killed,
    `.tld` and `.css` >60s, and `.vm` took 13.80s to chunk 144 bytes -- the
    same pathology, merely not yet unbounded. `chunking.py` already carried a
    hardcoded `!= "xml"` guard whose comment says exactly this; the widening
    turned that one-off into `_CHONKIE_SKIP_LANGUAGES`.

    A registry entry alone is NOT sufficient for these extensions, which is
    why this assertion is keyed off the extension a user would add rather
    than off the frozenset's contents.
    """
    spec = detect_language(Path("sample" + extension))
    assert spec is not None
    assert spec.key == expected_key
    assert spec.key in _CHONKIE_SKIP_LANGUAGES


def test_cobol_still_reaches_chonkie() -> None:
    """The negative case, because the guard is easy to over-broaden.

    `cobol` deliberately keeps its existing `"auto"` mapping; behavior for all
    eight pre-existing languages is byte-identical across the widening.
    """
    assert "cobol" not in _CHONKIE_SKIP_LANGUAGES
