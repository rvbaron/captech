"""Tests for the vendored github-linguist profile (M0 of the extraction-gap plan).

This is the important half of M0. The profile is a derived snapshot fetched by
hand, so a refresh that silently half-succeeded -- an empty extension map, a
lost vendor split, a branch name where a commit SHA belongs -- would not raise
anywhere; it would quietly empty the gap report's two classification columns and
leave every finding unlabelled. These assertions make that failure loud.

Every volume and resolution below is a property of upstream commit
``d5214e1612c858ba14bf98edeca57e1683276f1d`` (2026-09-01T09:40:55Z), which is
the commit ``scripts/refresh_linguist.py --ref`` was pinned to for the initial
generation. That pinning is what makes this a bad-refresh detector rather than a
tripwire that fires on the next linguist release: a **deliberate** refresh
against a newer ref is *expected* to move these numbers, and updating them here
is part of that commit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from tree_sitter_language_pack import detect_language_from_extension, has_language

from legacylift_search.linguist import (
    DEFAULT_PROFILE_PATH,
    LinguistProfile,
    classify_extension,
    classify_filename,
    load_linguist_profile,
    tree_sitter_grammar_for,
)

PINNED_COMMIT = "d5214e1612c858ba14bf98edeca57e1683276f1d"

PACKAGE_ROOT = Path(__file__).parent.parent / "src" / "legacylift_search"
PROFILE_PATH = PACKAGE_ROOT / "profiles" / "linguist.json"


def _load() -> LinguistProfile:
    return load_linguist_profile(PROFILE_PATH)


def _names(languages: list) -> list[str]:
    return [lang.name for lang in languages]


# ---------------------------------------------------------------------------
# Loading and packaging
# ---------------------------------------------------------------------------


def test_packaged_profile_is_where_the_loader_defaults_to() -> None:
    """The default path is the packaged copy, as with extractors.json."""
    assert DEFAULT_PROFILE_PATH == PROFILE_PATH.resolve()
    assert PROFILE_PATH.exists()


def test_load_linguist_profile_validates() -> None:
    profile = _load()
    assert profile.schema_version == 1
    assert "MIT" in profile.attribution
    assert "GitHub" in profile.attribution


def test_load_linguist_profile_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="linguist.json"):
        load_linguist_profile(tmp_path / "nope.json")


def test_a_profile_missing_a_language_type_key_fails_validation(tmp_path: Path) -> None:
    """A half-succeeded refresh must fail loudly, not default to None.

    ``type`` is nullable for schema tolerance, but still required to be
    *present*; catching a refresh that dropped a key is why this module has a
    test at all.
    """
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    del profile["extensions"][".jsp"][0]["type"]
    broken = tmp_path / "linguist.json"
    broken.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_linguist_profile(broken)


# ---------------------------------------------------------------------------
# Volumes, pinned to the commit
# ---------------------------------------------------------------------------


def test_upstream_commit_is_a_sha_and_not_a_branch_name() -> None:
    """A one-step raw fetch cannot produce a SHA, so this catches that mistake.

    ``raw.githubusercontent.com/.../main/...`` returns no commit identity at
    all; a refresh that skipped the API resolution step would have to put
    something like ``"main"`` here.
    """
    profile = _load()
    assert re.fullmatch(r"[0-9a-f]{40}", profile.upstream_commit)
    assert profile.upstream_commit == PINNED_COMMIT


def test_volumes_at_the_pinned_commit() -> None:
    profile = _load()

    # Upstream language count is carried as a scalar because the pruned maps
    # cannot express it: 6 of the 833 are reachable by neither extension nor
    # filename (REPL transcripts, OpenAPI v2/v3, interpreter-only OpenRC), so
    # 827 distinct names survive pruning. Asserting both numbers separates a
    # changed upstream from a broken inversion.
    assert profile.upstream_language_count == 833
    assert len(profile.extensions) == 1486
    assert len(profile.filenames) == 419

    distinct = {
        lang.name
        for languages in (*profile.extensions.values(), *profile.filenames.values())
        for lang in languages
    }
    assert len(distinct) == 827


def test_vendor_patterns_split_113_filename_55_directory() -> None:
    """The split rule is one line, and getting it wrong moves drop attribution.

    A pattern is directory-shaped when, with any trailing anchor removed, it
    ends in a slash. Only the filename-shaped half is adopted downstream --
    none of vendor.yml's directory patterns decides provenance, because on the
    reference corpus ``WEB-INF/tld/`` is 9/11 vendored, ``xmlcatalog/`` is
    100% vendored and ``com/nng/ple/service/external/`` is 0% vendored while a
    single directory pattern claims all 63 of its files.
    """
    profile = _load()
    filename_patterns = profile.vendor_filename_patterns
    directory_patterns = profile.vendor_directory_patterns

    assert len(filename_patterns) == 113
    assert len(directory_patterns) == 55
    assert len(filename_patterns) + len(directory_patterns) == 168

    # The lists must actually obey the rule they were split by.
    assert all(not p.rstrip("$").endswith("/") for p in filename_patterns)
    assert all(p.rstrip("$").endswith("/") for p in directory_patterns)


def test_every_carried_language_has_a_type() -> None:
    """So the report's type column can never be blank for a language linguist knows."""
    profile = _load()
    untyped = [
        lang.name
        for languages in (*profile.extensions.values(), *profile.filenames.values())
        for lang in languages
        if lang.type is None
    ]
    assert untyped == []


# ---------------------------------------------------------------------------
# Determinism of the generated file
# ---------------------------------------------------------------------------


def test_generated_file_is_written_deterministically() -> None:
    """Sorted keys, LF endings, one trailing newline.

    Without these a re-run at the same ref produces a different file, and the
    breakage stays invisible until the next refresh diff is unreadable. A CRLF
    default on Windows alone is enough to cause it.
    """
    raw_bytes = PROFILE_PATH.read_bytes()
    assert b"\r" not in raw_bytes
    assert raw_bytes.endswith(b"\n")
    assert not raw_bytes.endswith(b"\n\n")

    top_level = json.loads(raw_bytes.decode("utf-8"))
    assert list(top_level) == sorted(top_level)


# ---------------------------------------------------------------------------
# Extension resolutions
# ---------------------------------------------------------------------------


def test_extension_resolutions() -> None:
    profile = _load()

    jsp = classify_extension(profile, ".jsp")
    assert _names(jsp) == ["Java Server Pages"]
    assert jsp[0].type == "programming"

    for ext in (".xsd", ".xml"):
        resolved = classify_extension(profile, ext)
        assert _names(resolved) == ["XML"]
        assert resolved[0].type == "data"

    css = classify_extension(profile, ".css")
    assert _names(css) == ["CSS"]
    assert css[0].type == "markup"

    properties = classify_extension(profile, ".properties")
    assert _names(properties) == ["INI", "Java Properties"]
    assert [lang.type for lang in properties] == ["data", "data"]

    gradle = classify_extension(profile, ".gradle")
    assert _names(gradle) == ["Gradle"]
    assert gradle[0].type == "data"

    htm = classify_extension(profile, ".htm")
    assert _names(htm) == ["HTML"]
    assert htm[0].type == "markup"

    assert _names(classify_extension(profile, ".txt")) == [
        "Adblock Filter List",
        "Text",
        "Vim Help File",
    ]


def test_extension_absences() -> None:
    """The absences matter as much as the presences.

    These are the extensions the gap report exists to talk about: ``.tld``
    carries access-control tag bindings, ``.vm`` carries Velocity templates,
    and linguist knows nothing about either. A refresh that emptied the map
    would make every one of these look "absent" too, which is why the volume
    assertions above run alongside these.
    """
    profile = _load()
    for ext in (".tld", ".dtd", ".ent", ".vm", ".mf", ".png", ".docx"):
        assert classify_extension(profile, ext) == [], ext


def test_extension_lookup_casefolds_in_both_directions() -> None:
    """NNG's 14 ``MANIFEST.MF`` files are why this is asserted, not assumed.

    ``languages.py:105`` stores ``ext.lower()`` and ``languages.py:117`` looks
    up ``path.suffix.lower()``, so an extension comparison that did not fold
    would report a language verdict the indexer never reached. ``.MF`` must
    reach the same "absent" answer as ``.mf``, and ``.JSP`` the same answer as
    ``.jsp``.
    """
    profile = _load()
    assert classify_extension(profile, ".JSP") == classify_extension(profile, ".jsp")
    assert _names(classify_extension(profile, ".JSP")) == ["Java Server Pages"]
    assert classify_extension(profile, ".MF") == []
    assert classify_extension(profile, ".mf") == []


def test_empty_extension_resolves_to_nothing() -> None:
    """A file with no extension is a real case in the walk, not a guard clause."""
    assert classify_extension(_load(), "") == []


# ---------------------------------------------------------------------------
# Filename resolutions
# ---------------------------------------------------------------------------


def test_filename_resolutions() -> None:
    profile = _load()

    jenkinsfile = classify_filename(profile, "Jenkinsfile")
    assert _names(jenkinsfile) == ["Groovy"]
    assert jenkinsfile[0].type == "programming"

    for name in (".project", ".classpath"):
        resolved = classify_filename(profile, name)
        assert _names(resolved) == ["XML"], name
        assert resolved[0].type == "data"

    gitignore = classify_filename(profile, ".gitignore")
    assert _names(gitignore) == ["Ignore List"]
    assert gitignore[0].type == "data"

    assert classify_filename(profile, ".keep") == []


def test_filename_lookup_is_case_sensitive() -> None:
    """Linguist's own semantics, and git's: ``jenkinsfile`` is not Groovy."""
    profile = _load()
    assert classify_filename(profile, "jenkinsfile") == []
    assert classify_filename(profile, "Jenkinsfile") != []


# ---------------------------------------------------------------------------
# The tree-sitter side
# ---------------------------------------------------------------------------


def test_leading_dot_trap_in_the_upstream_api() -> None:
    """Asserted against the library directly, because it fails silently.

    ``detect_language_from_extension`` wants the extension without its dot. A
    call site that passes the dotted form gets ``None`` for everything and no
    error at all, which empties the grammar column outright.
    """
    assert detect_language_from_extension("dtd") == "dtd"
    assert detect_language_from_extension(".dtd") is None


def test_tree_sitter_grammar_for_handles_the_dot_in_one_place() -> None:
    """The wrapper takes the dotted form, so no call site can repeat the trap."""
    assert tree_sitter_grammar_for(".dtd") == "dtd"
    assert tree_sitter_grammar_for(".DTD") == "dtd"
    assert tree_sitter_grammar_for("") is None


def test_has_language_takes_a_language_name_not_an_extension() -> None:
    """And the two columns are complementary rather than redundant.

    ``.dtd`` is unknown to linguist and *has* a grammar; ``.jsp`` is known to
    linguist and has *none*. Neither column subsumes the other, and the pair is
    the triage: "add a glob" versus "write an extractor".
    """
    assert has_language("css") is True
    assert has_language("jsp") is False
    assert has_language("dtd") is True

    profile = _load()
    assert classify_extension(profile, ".dtd") == []
    assert tree_sitter_grammar_for(".dtd") is not None
    assert _names(classify_extension(profile, ".jsp")) == ["Java Server Pages"]
    assert tree_sitter_grammar_for(".jsp") is None
