"""Tests for the M1 walk (``gaps.walk_repository``) of the extraction-gap plan.

These are written from the specification alone -- `docs/exec-plans/active/
layer0-extraction-gap-detection.md`, sections "M1 -- the walk", "Concrete Steps
> Step 2", "Validation and Acceptance > M1" and "Interfaces and Dependencies" --
and deliberately not from the implementation, so that they are an independent
oracle for it rather than a restatement of it.

The plan pins the walk as three steps per file, in this order, and most of what
is asserted below is the *order*:

1. the manifest ``exclude_globs`` gate, which removes a file from the walk
   entirely -- not counted, not tiered, not reported;
2. third-party provenance in strict precedence (declared identity, then
   ``vendor.yml``'s filename patterns, then ``vendored_globs``), which **drops**
   a file into ``WalkResult.dropped`` rather than tiering it;
3. a six-tier mutually exclusive partition, ``indexed`` > ``credential`` >
   ``referenced_content`` > ``asset`` > ``first_party_excluded`` > ``gap``.

The six tiers plus the drop bucket must reconcile to the tree, which is the one
property a reader of the report checks with their eyes.

Nothing here needs a corpus, a database or the network; every fixture is a
handful of tiny files under ``tmp_path``. The linguist profile is the real
packaged one (M0, shipped), never a stub.
"""

from __future__ import annotations

import builtins
import inspect
import os
import re
from pathlib import Path

import pathspec
import pytest

from legacylift_search.config import Manifest, ProjectConfig
from legacylift_search.gaps import (
    DroppedFile,
    TierTotals,
    WalkedFile,
    WalkResult,
    walk_repository,
)
from legacylift_search.languages import detect_language
from legacylift_search.linguist import load_linguist_profile

# A .tld that declares the client's own domain, and one that declares a
# standards body's. Provenance rule 2.1 reads at most the first 8,000 bytes and
# matches <uri>...</uri>; the identity is authoritative in both directions.
OWN_TLD = "<taglib>\n  <uri>http://www.nngco.com/tags/nngauthz</uri>\n</taglib>\n"
FOREIGN_TLD = "<taglib>\n  <uri>http://java.sun.com/jsp/jstl/core</uri>\n</taglib>\n"

TIERS = (
    "indexed",
    "credential",
    "referenced_content",
    "asset",
    "first_party_excluded",
    "gap",
)


@pytest.fixture(scope="module")
def profile():
    """The real packaged linguist profile -- committed data, never stubbed."""
    return load_linguist_profile()


def _write(root: Path, rel: str, content: bytes | str = "x\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        content = content.encode("utf-8")
    path.write_bytes(content)
    return path


def _manifest(
    *,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    max_file_bytes: int = 2_000_000,
) -> Manifest:
    """A real Manifest with the three fields the walk reads made explicit.

    The defaults in ``ProjectConfig`` are deliberately replaced rather than
    extended: a fixture that inherited the 27 default include globs and the 32
    default exclude globs would be asserting the defaults, not the walk.
    """
    return Manifest(
        project=ProjectConfig(
            include_globs=list(include),
            exclude_globs=list(exclude),
            max_file_bytes=max_file_bytes,
        )
    )


def _files(result: WalkResult) -> dict[str, WalkedFile]:
    return {f.relative_path: f for f in result.files}


def _dropped(result: WalkResult) -> dict[str, DroppedFile]:
    return {d.relative_path: d for d in result.dropped}


def _lines(path: Path) -> int:
    """The plan's line convention, stated once: ``sum(1 for _ in open(p,"rb"))``.

    It differs from ``wc -l`` by one on a file with no trailing newline, which
    is why the convention is pinned rather than assumed.
    """
    with open(path, "rb") as handle:
        return sum(1 for _ in handle)


def _tier_files(result: WalkResult, tier: str) -> list[WalkedFile]:
    return [f for f in result.files if f.tier == tier]


# ---------------------------------------------------------------------------
# Step 1 -- the manifest gate
# ---------------------------------------------------------------------------


def test_manifest_exclusion_beats_everything(tmp_path: Path, profile) -> None:
    """An excluded file is not counted, not tiered, and not reported at all.

    The two excluded fixtures would otherwise land in *different* tiers -- one
    in ``indexed`` and one in ``credential``, the tier the plan says may never
    be suppressed -- so a walk that applied the manifest gate after tiering, or
    that recorded exclusions as a drop, fails here rather than silently
    reporting a keystore under a build directory.
    """
    _write(tmp_path, "build/generated/Ignored.java", "class Ignored {}\n")
    _write(tmp_path, "build/keystore.p12", "not-a-real-keystore\n")
    _write(tmp_path, "src/Kept.java", "class Kept {}\n")

    result = walk_repository(
        tmp_path,
        _manifest(include=("**/*.java",), exclude=("**/build/**",)),
        profile=profile,
    )

    assert set(_files(result)) == {"src/Kept.java"}
    assert result.dropped == []
    assert result.rescued_by_identity == []
    assert sum(t.files for t in result.totals.values()) == 1
    assert not any("build/" in f.relative_path for f in result.files)


# ---------------------------------------------------------------------------
# Step 3 -- tier precedence
# ---------------------------------------------------------------------------


def test_credential_outranks_asset(tmp_path: Path, profile) -> None:
    """A keystore with an asset-looking name is credential material.

    ``cacerts.png`` satisfies the credential rule by its stem and the asset rule
    by its extension. The plan is explicit that the credential tier outranks
    every other non-indexed tier "precisely so a keystore can never be hidden by
    an image glob", so only the precedence -- not either rule alone -- makes
    this pass.
    """
    _write(tmp_path, "assets/cacerts.png", "PNG-ish bytes\n")
    _write(tmp_path, "assets/logo.png", "PNG-ish bytes\n")
    _write(tmp_path, "sec/ssTrustStore", "trust\n")
    _write(tmp_path, "sec/app.p12", "p12\n")

    result = walk_repository(tmp_path, _manifest(), profile=profile)
    files = _files(result)

    assert files["assets/cacerts.png"].tier == "credential"
    assert files["sec/ssTrustStore"].tier == "credential"
    assert files["sec/app.p12"].tier == "credential"
    assert files["assets/logo.png"].tier == "asset"


def test_credential_filename_rule_is_case_insensitive(tmp_path: Path, profile) -> None:
    """The one filename comparison in the walk that the plan folds, and says so.

    Linguist filename lookup stays exact (``Jenkinsfile`` is not
    ``jenkinsfile``), but the credential rule is specified "(case-insensitive)",
    because a keystore that hid behind its spelling on disk is the failure the
    tier exists to prevent.
    """
    _write(tmp_path, "sec/CACERTS", "trust\n")
    _write(tmp_path, "sec/sstruststore", "trust\n")

    result = walk_repository(tmp_path, _manifest(), profile=profile)
    files = _files(result)

    assert files["sec/CACERTS"].tier == "credential"
    assert files["sec/sstruststore"].tier == "credential"


def test_referenced_content_is_by_extension_not_by_reference(
    tmp_path: Path, profile
) -> None:
    """A .docx is referenced content whether or not anything references it.

    Membership is by extension deliberately: a zero-reference template is the
    *finding* on the second reference corpus, and it can only be reported as one
    if it stays in the tier instead of falling through to ``gap`` and being
    buried under genuinely unparsed source. The walk knows nothing about
    references at all -- that is M3 -- so an implementation that gated the tier
    on a reference count would empty it here.
    """
    _write(tmp_path, "docs/Template.docx", "docx bytes\n")

    result = walk_repository(tmp_path, _manifest(), profile=profile)

    assert _files(result)["docs/Template.docx"].tier == "referenced_content"
    assert result.totals["referenced_content"].files == 1


def test_first_party_exclusion_beats_indexed(tmp_path: Path, profile) -> None:
    """A file matching include_globs *and* a first-party glob is excluded, not indexed.

    This branch is the whole content of the "applies to both sides of the ratio"
    decision, and is why the ``indexed`` tier is smaller than the ``repo_files``
    table on the reference corpus (1,229 - 358 = 871).
    """
    _write(tmp_path, "tools/Gen.java", "class Gen {}\n")
    _write(tmp_path, "src/Kept.java", "class Kept {}\n")

    result = walk_repository(
        tmp_path,
        _manifest(include=("**/*.java",)),
        profile=profile,
        first_party_exclude_globs=("tools/**",),
    )
    files = _files(result)

    assert files["tools/Gen.java"].tier == "first_party_excluded"
    assert files["tools/Gen.java"].matched_glob == "tools/**"
    assert files["tools/Gen.java"].rejected_by is None
    assert files["src/Kept.java"].tier == "indexed"
    assert result.totals["indexed"].files == 1


# ---------------------------------------------------------------------------
# Step 2 -- third-party provenance
# ---------------------------------------------------------------------------


def test_declared_identity_rescues_a_tld_a_vendored_glob_claims(
    tmp_path: Path, profile
) -> None:
    """Declared identity is authoritative in both directions.

    ``nngauthz.tld`` is 1,630 bytes, binds an access-control tag across the JSP
    layer, and survives only because reading the identity it declares about
    itself overrides an otherwise-correct ``WEB-INF/tld/**`` pattern -- nine of
    the eleven files in that one flat directory really are vendored. Provenance
    is not a property of location, and this is the test that says so.
    """
    _write(tmp_path, "web/WEB-INF/tld/nngauthz.tld", OWN_TLD)
    _write(tmp_path, "web/WEB-INF/tld/jstl-core.tld", FOREIGN_TLD)

    result = walk_repository(
        tmp_path,
        _manifest(),
        profile=profile,
        vendored_globs=("**/WEB-INF/tld/**",),
        own_identities=("nngco.com",),
    )
    files = _files(result)
    dropped = _dropped(result)

    # Rescued: kept in the walk, and named as rescued so the override is visible.
    assert "web/WEB-INF/tld/nngauthz.tld" in files
    assert "web/WEB-INF/tld/nngauthz.tld" not in dropped
    assert result.rescued_by_identity == ["web/WEB-INF/tld/nngauthz.tld"]

    # The sibling declares a standards body, so identity drops it before the
    # vendored glob is ever consulted.
    assert "web/WEB-INF/tld/jstl-core.tld" not in files
    assert dropped["web/WEB-INF/tld/jstl-core.tld"].rule == "declared_identity"
    # The whole declared identity, not a substring of it: asserting the host
    # appears *somewhere* would also pass for a URI that merely embeds it, and
    # `detail` is specified as the identity itself.
    assert (
        dropped["web/WEB-INF/tld/jstl-core.tld"].detail
        == "http://java.sun.com/jsp/jstl/core"
    )


def test_identity_rule_is_skipped_when_no_own_identity_is_configured(
    tmp_path: Path, profile
) -> None:
    """With no token, the rule is skipped entirely -- it does not drop everything.

    Taken literally with an empty token set, "third-party exactly when the
    identity contains none of the tokens" makes every file that declares any
    identity third-party, which would silently delete the very file Q27 exists
    to rescue. The plan resolves it by skipping the rule and failing toward
    *reporting*: an unrecognised third-party schema becomes a noisy gap finding
    rather than an invisible deletion.
    """
    _write(tmp_path, "web/WEB-INF/tld/nngauthz.tld", OWN_TLD)
    _write(tmp_path, "web/WEB-INF/tld/jstl-core.tld", FOREIGN_TLD)

    result = walk_repository(tmp_path, _manifest(), profile=profile)

    assert result.dropped == []
    assert result.rescued_by_identity == []
    assert set(_files(result)) == {
        "web/WEB-INF/tld/nngauthz.tld",
        "web/WEB-INF/tld/jstl-core.tld",
    }

    # And with the rule skipped, provenance falls through to vendored_globs,
    # which then claims *both* -- attributed to the glob, never to identity.
    fell_through = walk_repository(
        tmp_path,
        _manifest(),
        profile=profile,
        vendored_globs=("**/WEB-INF/tld/**",),
    )
    assert fell_through.files == []
    assert {d.rule for d in fell_through.dropped} == {"vendored_globs"}
    assert fell_through.rescued_by_identity == []


def test_vendor_filename_patterns_match_the_path_not_the_basename(
    tmp_path: Path, profile
) -> None:
    """vendor.yml's patterns are filename-*shaped*, not filename-*scoped*.

    ``(^|/)\\.gitattributes$`` must match ``some/deep/dir/.gitattributes``.
    Reading "filename patterns" literally and matching ``Path.name`` compiles,
    runs, and silently changes the drop attribution on both reference corpora,
    so this pins a nested path that a basename match cannot satisfy -- and a
    near-miss sibling that a too-loose ``re.search`` would swallow.
    """
    _write(tmp_path, "src/CTCM.API/.gitignore", "bin/\nobj/\n")
    _write(tmp_path, "src/gitignore-notes.md", "why we ignore things\n")

    result = walk_repository(tmp_path, _manifest(), profile=profile)
    dropped = _dropped(result)

    assert dropped["src/CTCM.API/.gitignore"].rule == "vendor_filename"
    assert "gitignore" in dropped["src/CTCM.API/.gitignore"].detail
    assert set(_files(result)) == {"src/gitignore-notes.md"}


# ---------------------------------------------------------------------------
# The gap labels -- the assertions the probe cannot make
# ---------------------------------------------------------------------------

# An extension the language registry will never claim, because no such format
# exists. Deliberately synthetic: the `rejected_by="language"` gate needs a
# stand-in for "the allow-list names it and the registry does not know it",
# and every REAL candidate for that role is one coverage widening away from
# becoming registered -- which is exactly what happened to this test's
# original `.jsp`. See `test_registry_does_not_claim_the_gate_sentinel`.
_UNREGISTERED_EXT = ".no-such-language"


def test_registry_does_not_claim_the_gate_sentinel() -> None:
    """The sentinel's whole value is that it stays unregistered.

    Asserted in its own test so that a future widening which somehow claimed
    it fails here, naming the cause, instead of failing inside the gate test
    where it reads as a gate regression.
    """
    assert detect_language(Path("x" + _UNREGISTERED_EXT)) is None


def test_include_glob_match_with_no_language_is_a_gap_labelled_language(
    tmp_path: Path, profile
) -> None:
    """Passing the allow-list is not enough; ``detect_language`` gates too.

    Under the default ``include_globs`` this case cannot occur, because every
    default glob maps to an extension ``_EXTENSION_TO_KEY`` already knows. It
    becomes reachable the moment someone widens the allow-list -- which is
    exactly when someone needs to be told that widening it bought nothing.

    The stand-in extension is a **synthetic sentinel**, not a real format.
    This test originally used ``.jsp``, and its own docstring predicted the
    consequence: registering ``.jsp`` (the 2026-09-08 coverage widening) made
    the precondition false and the fixture stopped testing the gate. A format
    nobody will ever write an extractor for cannot be invalidated that way.
    """
    # Precondition, asserted rather than assumed: this is the gate under test.
    assert detect_language(Path("page" + _UNREGISTERED_EXT)) is None
    assert detect_language(Path("Kept.java")) is not None

    _write(tmp_path, "web/page" + _UNREGISTERED_EXT, "<%= 1 %>\n")
    _write(tmp_path, "src/Kept.java", "class Kept {}\n")

    result = walk_repository(
        tmp_path,
        _manifest(include=("**/*" + _UNREGISTERED_EXT, "**/*.java")),
        profile=profile,
    )
    files = _files(result)

    assert files["web/page" + _UNREGISTERED_EXT].tier == "gap"
    assert files["web/page" + _UNREGISTERED_EXT].rejected_by == "language"
    assert files["src/Kept.java"].tier == "indexed"
    assert files["src/Kept.java"].rejected_by is None


def test_include_glob_match_over_the_size_cap_is_a_gap_labelled_size_cap(
    tmp_path: Path, profile
) -> None:
    """The fourth discovery gate, modelled so the label can prescribe the fix.

    "raise the cap or accept it" is a different remedy from "edit the manifest"
    and from "write a parser", which is the entire reason ``rejected_by``
    exists.
    """
    _write(tmp_path, "src/Big.java", "// " + "x" * 500 + "\n")
    _write(tmp_path, "src/Small.java", "class Small {}\n")

    result = walk_repository(
        tmp_path,
        _manifest(include=("**/*.java",), max_file_bytes=100),
        profile=profile,
    )
    files = _files(result)

    assert files["src/Big.java"].size_bytes > 100
    assert files["src/Big.java"].tier == "gap"
    assert files["src/Big.java"].rejected_by == "size_cap"
    assert files["src/Small.java"].tier == "indexed"


# ---------------------------------------------------------------------------
# Reconciliation -- the property a reader checks with their eyes
# ---------------------------------------------------------------------------


def test_six_tiers_plus_drops_reconcile_to_the_tree(tmp_path: Path, profile) -> None:
    """The tiers must not overlap and must not lose anyone.

    A reader who cannot add the columns to the walk total will not trust any of
    them, so this asserts the partition three ways -- files, bytes and lines --
    over a tree that populates every tier and all three drop rules at once.
    """
    excluded = [
        _write(tmp_path, "build/generated/Ignored.java", "class Ignored {}\n"),
        _write(tmp_path, "build/keystore.p12", "p12\n"),
    ]
    surviving = [
        _write(tmp_path, "src/Kept.java", "class Kept {}\n"),  # indexed
        _write(tmp_path, "sec/app.p12", "p12\n"),  # credential
        _write(tmp_path, "docs/Template.docx", "docx\n"),  # referenced_content
        _write(tmp_path, "img/logo.png", "png\n"),  # asset
        _write(tmp_path, "tools/Gen.java", "class Gen {}\n"),  # first_party_excluded
        _write(tmp_path, "web/page.jsp", "<%= 1 %>\n"),  # gap
        # No trailing newline: the case where this convention and wc -l differ.
        _write(tmp_path, "conf/app.properties", "a=1\nb=2"),  # gap
    ]
    dropped_paths = [
        _write(tmp_path, "schemas/foreign.tld", FOREIGN_TLD),  # declared_identity
        _write(tmp_path, ".gitattributes", "* text=auto\n"),  # vendor_filename
        _write(tmp_path, "libs/third.js", "var a = 1;\n"),  # vendored_globs
    ]

    result = walk_repository(
        tmp_path,
        _manifest(include=("**/*.java",), exclude=("**/build/**",)),
        profile=profile,
        first_party_exclude_globs=("tools/**",),
        vendored_globs=("libs/**",),
        own_identities=("nngco.com",),
    )

    tree_files = len(excluded) + len(surviving) + len(dropped_paths)
    assert tree_files == 12

    tiered = sum(t.files for t in result.totals.values())
    assert tiered == len(result.files)
    assert tiered + len(result.dropped) == tree_files - len(excluded)
    assert tiered == len(surviving)

    # Each tier is populated exactly once -- mutually exclusive, in the pinned
    # precedence, with nothing double-counted.
    assert {f.relative_path for f in result.files} == {
        p.relative_to(tmp_path).as_posix() for p in surviving
    }
    assert {t: result.totals[t].files for t in TIERS if t in result.totals} == {
        "indexed": 1,
        "credential": 1,
        "referenced_content": 1,
        "asset": 1,
        "first_party_excluded": 1,
        "gap": 2,
    }
    assert {d.rule for d in result.dropped} == {
        "declared_identity",
        "vendor_filename",
        "vendored_globs",
    }

    # Bytes and lines reconcile on the same partition, on the plan's line
    # convention -- conf/app.properties has no trailing newline and still counts
    # two lines.
    assert sum(t.size_bytes for t in result.totals.values()) == sum(
        p.stat().st_size for p in surviving
    )
    assert sum(t.line_count for t in result.totals.values()) == sum(
        _lines(p) for p in surviving
    )
    assert _files(result)["conf/app.properties"].line_count == 2

    for walked in result.files:
        assert isinstance(walked, WalkedFile)
    for drop in result.dropped:
        assert isinstance(drop, DroppedFile)
    for totals in result.totals.values():
        assert isinstance(totals, TierTotals)


# ---------------------------------------------------------------------------
# The four that fail silently rather than loudly if they are skipped
# ---------------------------------------------------------------------------


def test_every_emitted_path_is_posix(tmp_path: Path, profile) -> None:
    """Does nothing on Linux; is the whole guard on Windows.

    ``Path.relative_to`` yields backslashes there, and one repo-relative POSIX
    string per file is what every gate, join and column in this feature
    consumes: ``**/*.java`` does not match ``a\\foo.java``, ``vendor.yml``'s
    patterns are anchored on ``/``, and M3 joins these strings against
    ``repo_files.relative_path``, which is POSIX in all 5,944 live rows. A
    native-separator walk reconciles to a delta equal to the whole tree on
    Windows and to zero on Linux -- green CI on one platform, silent on the
    other. Two directories deep is the shallowest fixture at which it shows.
    """
    _write(tmp_path, "a/b/c.jsp", "<%= 1 %>\n")
    _write(tmp_path, "a/b/tld/own.tld", OWN_TLD)
    _write(tmp_path, "a/b/tld/foreign.tld", FOREIGN_TLD)
    _write(tmp_path, "a/b/.gitattributes", "* text=auto\n")

    result = walk_repository(
        tmp_path,
        _manifest(),
        profile=profile,
        vendored_globs=("a/b/tld/**",),
        own_identities=("nngco.com",),
    )

    emitted = (
        [f.relative_path for f in result.files]
        + [d.relative_path for d in result.dropped]
        + list(result.rescued_by_identity)
    )
    # All three collections must be non-empty, or this asserts nothing at all.
    assert result.files and result.dropped and result.rescued_by_identity
    for path in emitted:
        assert "\\" not in path, path

    assert "a/b/c.jsp" in {f.relative_path for f in result.files}
    assert "a/b/tld/own.tld" in result.rescued_by_identity
    assert "a/b/tld/foreign.tld" in {d.relative_path for d in result.dropped}


def test_matched_glob_names_the_deciding_pattern_and_sums_back(
    tmp_path: Path, profile
) -> None:
    """"Excluded on purpose, and under which glob" is a table the report promises.

    These globs are gitignore dialect, where the **last** matching pattern
    decides and a ``!`` pattern un-excludes. So ``matched_glob`` is the pattern
    whose match decided the outcome, not the first pattern that matched, and a
    file whose last match is a negation is not in the tier at all. Looping over
    per-pattern specs and taking the first hit compiles, runs, and gets negation
    backwards -- which is why the negated file is a fixture here.
    """
    _write(tmp_path, "docs/other.md", "notes\n")
    _write(tmp_path, "docs/keep.md", "keep me\n")
    _write(tmp_path, "conf/app.properties", "a=1\n")
    _write(tmp_path, "conf/app2.properties", "b=2\n")

    globs = ("docs/**", "!docs/keep.md", "conf/*.properties")
    result = walk_repository(
        tmp_path,
        _manifest(),
        profile=profile,
        first_party_exclude_globs=globs,
    )
    files = _files(result)

    assert files["docs/other.md"].tier == "first_party_excluded"
    assert files["docs/other.md"].matched_glob == "docs/**"
    assert files["conf/app.properties"].matched_glob == "conf/*.properties"
    assert files["conf/app2.properties"].matched_glob == "conf/*.properties"

    # Rescued by the negation: not in the tier, and claimed by no pattern.
    assert files["docs/keep.md"].tier == "gap"
    assert files["docs/keep.md"].matched_glob is None

    excluded = _tier_files(result, "first_party_excluded")
    assert len(excluded) == 3
    assert all(f.matched_glob is not None for f in excluded)
    assert all(f.matched_glob in globs for f in excluded)

    # The per-glob breakdown sums back to the tier totals exactly. (M2/M3 expose
    # this as ``first_party_excluded_by_glob``; at M1 it is derivable from
    # ``matched_glob``, and it is the derivation that has to add up.)
    by_glob: dict[str, list[WalkedFile]] = {}
    for walked in excluded:
        by_glob.setdefault(walked.matched_glob, []).append(walked)

    assert set(by_glob) == {"docs/**", "conf/*.properties"}
    totals = result.totals["first_party_excluded"]
    assert sum(len(v) for v in by_glob.values()) == totals.files
    assert sum(f.size_bytes for v in by_glob.values() for f in v) == totals.size_bytes
    assert sum(f.line_count for v in by_glob.values() for f in v) == totals.line_count


def test_defaults_are_not_mutated_between_calls(tmp_path: Path, profile) -> None:
    """A call that passes nothing must not inherit a previous call's lists.

    The signature takes ``Sequence[str] = ()`` rather than ``list[str] = []``
    for exactly this reason, so the empty defaults are asserted directly as well
    as behaviourally. (``profile`` is keyword-only with no default in the
    specified signature, so "no keyword arguments at all" is read here as "none
    of the three defaulted sequences".)
    """
    tree_a = tmp_path / "a"
    tree_b = tmp_path / "b"
    _write(tree_a, "tools/Gen.java", "class Gen {}\n")
    _write(tree_a, "libs/third.js", "var a = 1;\n")
    _write(tree_b, "tools/Gen.java", "class Gen {}\n")
    _write(tree_b, "libs/third.js", "var a = 1;\n")

    manifest = _manifest(include=("**/*.java",))

    bare_first = walk_repository(tree_a, manifest, profile=profile)
    assert _files(bare_first)["tools/Gen.java"].tier == "indexed"
    assert bare_first.dropped == []

    configured = walk_repository(
        tree_a,
        manifest,
        profile=profile,
        first_party_exclude_globs=("tools/**",),
        vendored_globs=("libs/**",),
        own_identities=("nngco.com",),
    )
    assert _files(configured)["tools/Gen.java"].tier == "first_party_excluded"
    assert [d.relative_path for d in configured.dropped] == ["libs/third.js"]

    # A second call on a different tree, again passing nothing, must be
    # unaffected by either of the calls above.
    bare_second = walk_repository(tree_b, manifest, profile=profile)
    assert _files(bare_second)["tools/Gen.java"].tier == "indexed"
    assert _files(bare_second)["tools/Gen.java"].matched_glob is None
    assert bare_second.dropped == []
    assert bare_second.rescued_by_identity == []
    assert {t: v.files for t, v in bare_second.totals.items() if v.files} == {
        "indexed": 1,
        "gap": 1,
    }

    # And the defaults themselves are still the empty, immutable sequences.
    parameters = inspect.signature(walk_repository).parameters
    for name in ("first_party_exclude_globs", "vendored_globs", "own_identities"):
        default = parameters[name].default
        assert default == (), name
        assert isinstance(default, tuple), name


# ---------------------------------------------------------------------------
# Case handling, pinned by the Decision Log
# ---------------------------------------------------------------------------


def test_extensions_casefold_into_one_row(tmp_path: Path, profile) -> None:
    """``.JSP`` and ``.jsp`` reach the same tier and one gap-by-extension key.

    ``WalkedFile.extension`` stores the casefolded form so that a per-extension
    aggregation cannot split one extension across two rows -- the reason NNG's
    14 ``MANIFEST.MF`` files do not depend on their spelling on disk.

    The two variants sit in different directories deliberately: NTFS is
    case-insensitive, so ``page.jsp`` and ``Page.JSP`` in one directory are one
    file on the platform this runs on.
    """
    _write(tmp_path, "x/lower/page.jsp", "<%= 1 %>\n")
    _write(tmp_path, "x/upper/Page.JSP", "<%= 2 %>\n")

    result = walk_repository(tmp_path, _manifest(), profile=profile)
    files = _files(result)

    assert files["x/lower/page.jsp"].tier == "gap"
    assert files["x/upper/Page.JSP"].tier == "gap"
    assert files["x/lower/page.jsp"].extension == ".jsp"
    assert files["x/upper/Page.JSP"].extension == ".jsp"
    assert {f.extension for f in _tier_files(result, "gap")} == {".jsp"}


def test_globs_stay_case_sensitive_and_label_the_right_gate(
    tmp_path: Path, profile
) -> None:
    """The two gates disagree about case, and the walk must reproduce that.

    ``detect_language`` casefolds, ``pathspec``'s gitignore dialect does not:
    ``**/*.java`` matches ``a/foo.java`` and not ``a/FOO.JAVA``. So an
    upper-case-extension file fails the allow-list even though the language gate
    would have accepted it, and it must be labelled ``include_globs``, never
    ``language``. Casefolding the glob side "for consistency" would reclassify
    exactly these files and reverse the fix the label prescribes.
    """
    # The disagreement itself, asserted against the gate being modelled.
    assert detect_language(Path("Foo.JAVA")) is not None

    # Separate directories, because NTFS would otherwise make these one file.
    _write(tmp_path, "x/upper/Foo.JAVA", "class Foo {}\n")
    _write(tmp_path, "x/lower/Foo.java", "class Foo {}\n")

    result = walk_repository(
        tmp_path, _manifest(include=("**/*.java",)), profile=profile
    )
    files = _files(result)

    assert files["x/lower/Foo.java"].tier == "indexed"
    assert files["x/upper/Foo.JAVA"].tier == "gap"
    assert files["x/upper/Foo.JAVA"].rejected_by == "include_globs"
    assert files["x/upper/Foo.JAVA"].extension == ".java"


# ---------------------------------------------------------------------------
# Provenance -- the vendor.yml half that must NOT be adopted
# ---------------------------------------------------------------------------


def test_vendor_directory_patterns_are_not_adopted(tmp_path: Path, profile) -> None:
    """``vendor.yml`` contributes its filename patterns and none of its directory ones.

    This is the longest bullet in "What must not happen", and it has 63 files
    behind it: ``(^|/)[Ee]xtern(als?)?/`` claims the whole of NNG's
    ``com/nng/ple/service/external/`` -- the client's own external-*systems*
    integration layer, ``ContractsService.java`` included. Provenance is not a
    property of location: ``WEB-INF/tld/`` is 9/11 vendored, ``xmlcatalog/`` is
    100% vendored, and this directory is 0%. M0 split the vendored data into
    ``vendor_filename_patterns`` and ``vendor_directory_patterns`` precisely so
    that "the directory patterns are not adopted" is an auditable property, and
    this is the test that audits it.

    An implementation that iterates both lists deletes 63 first-party files
    while every other test in this module still passes.
    """
    pattern = "(^|/)[Ee]xtern(als?)?/"
    # Not a tautology: the pattern really is in the shipped data, and it really
    # would claim the fixture if the list were consulted.
    assert profile.vendor_directory_patterns, "shipped data has no directory patterns"
    assert pattern in profile.vendor_directory_patterns
    relative = "com/nng/ple/service/external/ContractsService.java"
    assert re.search(pattern, relative) is not None

    _write(tmp_path, relative, "class ContractsService {}\n")
    _write(tmp_path, "com/nng/ple/vendor/Bundled.java", "class Bundled {}\n")
    # A control: provenance really is running in this walk, so an
    # implementation that skipped rule 2 entirely cannot pass by accident.
    _write(tmp_path, "com/nng/ple/.gitattributes", "* text=auto\n")

    result = walk_repository(
        tmp_path, _manifest(include=("**/*.java",)), profile=profile
    )
    files = _files(result)
    dropped = _dropped(result)

    assert set(dropped) == {"com/nng/ple/.gitattributes"}
    assert dropped["com/nng/ple/.gitattributes"].rule == "vendor_filename"

    assert relative in files
    assert files[relative].tier == "indexed"
    # ``(^|/)[Vv]+endor/`` is in the same list, and is the same mistake.
    assert "(^|/)[Vv]+endor/" in profile.vendor_directory_patterns
    assert "com/nng/ple/vendor/Bundled.java" in files
    assert files["com/nng/ple/vendor/Bundled.java"].tier == "indexed"


# ---------------------------------------------------------------------------
# Tier precedence -- credential outranks *indexed*, not merely asset
# ---------------------------------------------------------------------------


def test_credential_outranks_indexed(tmp_path: Path, profile) -> None:
    """A keystore that matches ``include_globs`` is credential material, not indexed.

    "The credential tier outranks every other non-indexed tier" left the
    indexed case contradictory -- a ``**/*.p12`` in the allow-list would tier a
    keystore as ordinary indexed source, and the tier that exists so that a
    keystore can never be hidden would be empty. Settled with the maintainer
    (2026-09-02): credential outranks ``indexed`` too.

    The discriminator is sharp in both wrong directions: with ``indexed``
    checked first, ``sec/app.p12`` lands in ``gap`` with
    ``rejected_by="language"`` (``detect_language`` knows no ``.p12``), so
    neither verdict can be reached by accident.
    """
    assert detect_language(Path("app.p12")) is None

    _write(tmp_path, "sec/app.p12", "p12 bytes\n")
    _write(tmp_path, "sec/trust.jks", "jks bytes\n")
    _write(tmp_path, "src/Kept.java", "class Kept {}\n")

    result = walk_repository(
        tmp_path,
        _manifest(include=("**/*.p12", "**/*.jks", "**/*.java")),
        profile=profile,
    )
    files = _files(result)

    assert files["sec/app.p12"].tier == "credential"
    assert files["sec/app.p12"].rejected_by is None
    assert files["sec/app.p12"].matched_glob is None
    assert files["sec/trust.jks"].tier == "credential"

    # The neighbour that genuinely is source still indexes, so this is a
    # precedence test and not "the allow-list stopped working".
    assert files["src/Kept.java"].tier == "indexed"
    assert result.totals["credential"].files == 2
    assert result.totals["indexed"].files == 1
    assert result.totals["gap"].files == 0


def test_credential_stem_rule_outranks_an_include_glob(tmp_path: Path, profile) -> None:
    """The filename/stem half of the rule beats the allow-list as well.

    ``.xml`` is the sharpest fixture available: it matches the allow-list *and*
    ``detect_language`` returns a language for it, so under an
    ``indexed``-first implementation ``conf/cacerts.xml`` is a clean
    ``indexed`` row with no label to give it away. Only the precedence change
    moves it, and the sibling ``conf/app.xml`` proves the allow-list is
    otherwise intact.
    """
    assert detect_language(Path("cacerts.xml")) is not None

    _write(tmp_path, "conf/cacerts.xml", "<trust/>\n")
    _write(tmp_path, "conf/ssTrustStore.xml", "<trust/>\n")
    _write(tmp_path, "conf/app.xml", "<app/>\n")

    result = walk_repository(
        tmp_path, _manifest(include=("**/*.xml",)), profile=profile
    )
    files = _files(result)

    assert files["conf/cacerts.xml"].tier == "credential"
    assert files["conf/ssTrustStore.xml"].tier == "credential"
    assert files["conf/app.xml"].tier == "indexed"
    assert result.totals["credential"].files == 2


# ---------------------------------------------------------------------------
# Dropped files carry their weight, so the drop bucket can be added up
# ---------------------------------------------------------------------------


def test_dropped_files_carry_bytes_and_lines(tmp_path: Path, profile) -> None:
    """``DroppedFile`` records size and lines, on the walk's line convention.

    The drop bucket is "removed from the walk total and from both sides of
    every ratio" -- but the acceptance criteria print it as a row with a KB and
    a lines column (NNG: 72 files / 762 KB / 20,730 lines), so the walk has to
    have measured it. A shape that records only the path and the rule cannot
    produce that row at all.

    ``.gitattributes`` here has **no trailing newline**, which is the case that
    separates ``sum(1 for _ in open(p, "rb"))`` from ``wc -l``: two lines by
    this convention, one newline byte in the file.
    """
    attrs = _write(tmp_path, "deep/dir/.gitattributes", "* text=auto\n*.java text")
    foreign = _write(tmp_path, "schemas/foreign.tld", FOREIGN_TLD)
    vendored = _write(tmp_path, "libs/third.js", "var a = 1;\nvar b = 2;\nvar c = 3;\n")

    # The distinguishing property of the fixture, asserted rather than assumed.
    assert attrs.read_bytes().count(b"\n") == 1

    result = walk_repository(
        tmp_path,
        _manifest(),
        profile=profile,
        vendored_globs=("libs/**",),
        own_identities=("nngco.com",),
    )
    dropped = _dropped(result)

    assert set(dropped) == {
        "deep/dir/.gitattributes",
        "schemas/foreign.tld",
        "libs/third.js",
    }

    assert dropped["deep/dir/.gitattributes"].line_count == 2  # not wc -l's 1
    assert dropped["libs/third.js"].line_count == 3
    assert dropped["schemas/foreign.tld"].line_count == _lines(foreign)

    # Sizes are the real ones, and they differ from each other, so a constant
    # (0, or "the last file seen") cannot pass.
    for path, rel in (
        (attrs, "deep/dir/.gitattributes"),
        (foreign, "schemas/foreign.tld"),
        (vendored, "libs/third.js"),
    ):
        assert dropped[rel].size_bytes == path.stat().st_size, rel
        assert dropped[rel].size_bytes > 0, rel
    assert len({d.size_bytes for d in result.dropped}) == 3

    # The drop bucket sums independently of the tier totals -- it is a separate
    # row of the same table, and the walk total excludes it.
    assert sum(d.size_bytes for d in result.dropped) == sum(
        p.stat().st_size for p in (attrs, foreign, vendored)
    )
    assert sum(t.size_bytes for t in result.totals.values()) == 0


# ---------------------------------------------------------------------------
# gitignore dialect: last match wins between two *positive* patterns
# ---------------------------------------------------------------------------


def test_matched_glob_is_the_last_positive_match_not_the_first(
    tmp_path: Path, profile
) -> None:
    """``matched_glob`` is "the pattern whose match decided the outcome".

    The negation test above cannot catch a first-hit implementation, because no
    file in it matches two *positive* patterns -- handle ``!`` correctly and
    first-hit and last-hit agree there. Here ``docs/readme.md`` matches both
    ``docs/**`` and the later ``docs/*.md``, so the two strategies disagree and
    the gitignore rule (last match decides) picks the later one. That is what
    ``pathspec``'s ``CheckResult.index`` reports and what a hand-rolled loop
    over per-pattern specs gets backwards.
    """
    globs = ("docs/**", "docs/*.md")

    # Both patterns genuinely claim the file -- the precondition that makes the
    # two strategies disagree. Checked one pattern at a time, so the expected
    # answer is not computed the way the walk computes it.
    both = [
        g
        for g in globs
        if pathspec.PathSpec.from_lines("gitignore", [g]).match_file(
            "docs/readme.md"
        )
    ]
    assert both == list(globs)

    _write(tmp_path, "docs/readme.md", "read me\n")
    _write(tmp_path, "docs/sub/deep.txt", "deep\n")

    result = walk_repository(
        tmp_path, _manifest(), profile=profile, first_party_exclude_globs=globs
    )
    files = _files(result)

    assert files["docs/readme.md"].tier == "first_party_excluded"
    assert files["docs/readme.md"].matched_glob == "docs/*.md"

    # And "always the last pattern in the list" is not the rule either: this
    # one is claimed only by the earlier pattern, so a constant answer fails.
    assert files["docs/sub/deep.txt"].tier == "first_party_excluded"
    assert files["docs/sub/deep.txt"].matched_glob == "docs/**"


# ---------------------------------------------------------------------------
# Declared identity -- the two untested regexes, the byte cap, the extension gate
# ---------------------------------------------------------------------------


def test_target_namespace_identity_drops_a_foreign_xsd(tmp_path: Path, profile) -> None:
    """``targetNamespace="..."`` on a .xsd -- the rule behind all three ctcm-api drops.

    Only ``<uri>...</uri>`` was exercised before this. On the second reference
    corpus every declared-identity drop comes from this form: the three
    ``iaiabc.org`` EDI schemas, which without the rule become gap findings and
    move the headline from 3.15% to 3.85% of bytes. It is authoritative in both
    directions, so the client's own schema beside them must survive.
    """
    _write(
        tmp_path,
        "Edi/Xml/xsd/claim.xsd",
        '<xs:schema targetNamespace="http://www.iaiabc.org/edi/claims"/>\n',
    )
    _write(
        tmp_path,
        "Edi/Xml/xsd/internal.xsd",
        '<xs:schema targetNamespace="http://schemas.ctcm.example/internal"/>\n',
    )

    result = walk_repository(
        tmp_path, _manifest(), profile=profile, own_identities=("ctcm",)
    )
    dropped = _dropped(result)

    assert set(dropped) == {"Edi/Xml/xsd/claim.xsd"}
    assert dropped["Edi/Xml/xsd/claim.xsd"].rule == "declared_identity"
    # The detail is the identity itself, not the file name or the rule name --
    # asserted whole rather than as a substring, so a namespace that merely
    # embeds the standards body's host cannot satisfy it.
    assert (
        dropped["Edi/Xml/xsd/claim.xsd"].detail
        == "http://www.iaiabc.org/edi/claims"
    )

    assert "Edi/Xml/xsd/internal.xsd" in _files(result)


def test_public_identifier_identity_drops_a_foreign_dtd(
    tmp_path: Path, profile
) -> None:
    """``PUBLIC "..."`` on a .dtd -- the third identity form, and the third extension.

    NNG's four ``.dtd`` files are exactly what the "do not let a denylist hide
    what an allow-list would have hidden" bullet counts as lost when the stored
    exclusions are unioned in, so the form that classifies them is worth
    pinning on its own.
    """
    _write(
        tmp_path,
        "dtd/hibernate-mapping.dtd",
        '<!ENTITY % x PUBLIC "-//Hibernate/Hibernate Mapping DTD 3.0//EN" "x.dtd">\n',
    )
    _write(
        tmp_path,
        "dtd/inhouse.dtd",
        '<!ENTITY % y PUBLIC "-//NNGCO.COM//DTD Internal//EN" "y.dtd">\n',
    )

    result = walk_repository(
        tmp_path, _manifest(), profile=profile, own_identities=("nngco.com",)
    )
    dropped = _dropped(result)

    assert set(dropped) == {"dtd/hibernate-mapping.dtd"}
    assert dropped["dtd/hibernate-mapping.dtd"].rule == "declared_identity"
    assert "Hibernate" in dropped["dtd/hibernate-mapping.dtd"].detail

    # Case-insensitive substring on the rescue side too: the own token is lower
    # case and the file shouts it.
    assert "dtd/inhouse.dtd" in _files(result)


def test_identity_is_read_from_at_most_the_first_8000_bytes(
    tmp_path: Path, profile
) -> None:
    """"Read at most the first 8,000 bytes" is a cap, and caps get pinned.

    The two fixtures declare the *same* foreign namespace and differ only in
    where it sits, so the control proves the pattern works and the subject
    proves the read stops. An implementation that reads the whole file drops
    the padded one too; one that reads too little drops neither.
    """
    identity = '<xs:schema targetNamespace="http://www.iaiabc.org/edi/claims"/>\n'
    padding = "<!-- " + ("p" * 9000) + " -->\n"
    padded = (padding + identity).encode("utf-8")
    assert padded.index(b"targetNamespace") > 8000

    _write(tmp_path, "xsd/past-the-cap.xsd", padded)
    _write(tmp_path, "xsd/within-the-cap.xsd", identity)

    result = walk_repository(
        tmp_path, _manifest(), profile=profile, own_identities=("ctcm",)
    )
    files = _files(result)
    dropped = _dropped(result)

    assert set(dropped) == {"xsd/within-the-cap.xsd"}
    assert dropped["xsd/within-the-cap.xsd"].rule == "declared_identity"

    # Not dropped, therefore tiered -- and it is a gap, which is the plan's
    # stated failure direction: unrecognised third-party material becomes a
    # noisy finding rather than an invisible deletion.
    assert files["xsd/past-the-cap.xsd"].tier == "gap"
    assert files["xsd/past-the-cap.xsd"].rejected_by == "include_globs"


def test_identity_rule_is_gated_on_the_three_extensions(
    tmp_path: Path, profile
) -> None:
    """A .java containing ``<uri>`` is never opened as an identity candidate.

    The rule is scoped to ``.tld``, ``.xsd`` and ``.dtd``. Ungated, a JSP
    taglib import or a Javadoc comment quoting a namespace would drop live
    source silently -- the single worst outcome available to this feature,
    since a dropped file leaves both sides of the ratio.
    """
    _write(
        tmp_path,
        "src/UriHolder.java",
        "// see <uri>http://java.sun.com/jsp/jstl/core</uri>\nclass UriHolder {}\n",
    )
    _write(tmp_path, "src/config.xml", '<c targetNamespace="http://java.sun.com/x"/>\n')
    _write(tmp_path, "web/WEB-INF/tld/jstl-core.tld", FOREIGN_TLD)

    result = walk_repository(
        tmp_path,
        _manifest(include=("**/*.java", "**/*.xml")),
        profile=profile,
        own_identities=("nngco.com",),
    )
    files = _files(result)

    # Only the .tld is a candidate; the two indexable files keep their tier.
    assert set(_dropped(result)) == {"web/WEB-INF/tld/jstl-core.tld"}
    assert files["src/UriHolder.java"].tier == "indexed"
    assert files["src/config.xml"].tier == "indexed"


# ---------------------------------------------------------------------------
# The totals dict is a complete partition, empty tiers included
# ---------------------------------------------------------------------------


def test_totals_always_carries_all_six_tiers(tmp_path: Path, profile) -> None:
    """Every tier is a key, zeroed when empty -- the report prints all six rows.

    Both reference tables have rows reading ``0  0 KB  0 lines`` (NNG's
    referenced content; ctcm-api's first-party excluded, asset and credential),
    and "the tiers add up to the total" is only checkable by eye if the rows
    are all there. A ``defaultdict``-shaped or write-on-first-use ``totals``
    passes every other test in this module and silently drops those rows.
    """
    _write(tmp_path, "src/Only.java", "class Only {}\n")

    result = walk_repository(
        tmp_path, _manifest(include=("**/*.java",)), profile=profile
    )

    assert set(result.totals) == set(TIERS)
    assert len(result.totals) == 6
    assert result.totals["indexed"] == TierTotals(
        files=1, size_bytes=len("class Only {}\n"), line_count=1
    )
    for tier in TIERS:
        if tier == "indexed":
            continue
        assert result.totals[tier] == TierTotals(
            files=0, size_bytes=0, line_count=0
        ), tier


# ---------------------------------------------------------------------------
# Read errors -- pinned as measured, because the plan does not specify them
# ---------------------------------------------------------------------------


def test_unreadable_file_is_tiered_with_zero_lines(
    tmp_path: Path, profile, monkeypatch
) -> None:
    """A file that stats but cannot be read is tiered normally, with 0 lines.

    **The plan does not specify this**; it is the behaviour measured on
    2026-09-02 and pinned here so that changing it is a deliberate act rather
    than an accident. The line counter swallows ``OSError`` and returns 0, so
    the file keeps its real ``size_bytes`` and its real tier and contributes
    nothing to the line side of the ratio. The defensible alternative -- a
    label saying "we could not read this" -- would be a better report, and is a
    change rather than a fix.
    """
    _write(tmp_path, "src/Unreadable.java", "class Unreadable {}\nline two\n")
    _write(tmp_path, "src/Readable.java", "class Readable {}\n")
    expected_size = (tmp_path / "src" / "Unreadable.java").stat().st_size

    denied = {"count": 0}
    real_path_open = Path.open
    real_builtin_open = builtins.open

    def _is_target(candidate: object) -> bool:
        try:
            text = os.fspath(candidate)
        except TypeError:
            return False
        return isinstance(text, str) and text.endswith("Unreadable.java")

    def fake_path_open(self, *args, **kwargs):
        if _is_target(self):
            denied["count"] += 1
            raise OSError(13, "Permission denied")
        return real_path_open(self, *args, **kwargs)

    def fake_builtin_open(file, *args, **kwargs):
        if _is_target(file):
            denied["count"] += 1
            raise OSError(13, "Permission denied")
        return real_builtin_open(file, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_path_open)
    monkeypatch.setattr(builtins, "open", fake_builtin_open)

    result = walk_repository(
        tmp_path, _manifest(include=("**/*.java",)), profile=profile
    )

    monkeypatch.undo()
    files = _files(result)

    # The denial actually fired, so this cannot pass vacuously.
    assert denied["count"] >= 1

    assert files["src/Unreadable.java"].tier == "indexed"
    assert files["src/Unreadable.java"].line_count == 0
    assert files["src/Unreadable.java"].size_bytes == expected_size
    assert result.dropped == []

    # The readable sibling is unaffected, so the walk did not simply give up.
    assert files["src/Readable.java"].line_count == 1
    assert result.totals["indexed"] == TierTotals(
        files=2,
        size_bytes=expected_size + files["src/Readable.java"].size_bytes,
        line_count=1,
    )


def test_unstattable_file_leaves_the_walk_entirely(
    tmp_path: Path, profile, monkeypatch
) -> None:
    """A file whose ``stat()`` fails is dropped from the walk -- silently.

    **The plan does not specify this either.** Measured 2026-09-02: the file is
    neither tiered nor recorded in ``dropped``, so it disappears exactly the way
    the drop bucket exists to prevent, and the walk total shrinks with it. It is
    pinned rather than changed because the honest fix (report it) is a report
    change with a schema behind it, and this test is what fails loudly when
    someone makes it.

    The fixture is the realistic shape of the failure -- a file that is present
    when the tree is scanned and gone by the time it is measured, which is a
    live checkout during a build -- so the first ``stat`` succeeds and the
    walk's own call is the one that raises. ``PermissionError`` deliberately
    takes a different route: ``Path.is_file`` re-raises ``EACCES`` rather than
    swallowing it (only ``ENOENT``/``ENOTDIR``/``EBADF``/``ELOOP`` are
    ignored), so an ACL-unreadable file never reaches the walk's ``stat`` at
    all. That used to crash ``walk_repository``; it is now caught beside
    ``is_file`` and the entry is skipped, landing in the same place as this
    test's vanished file. Both are unspecified by the plan, and both are
    recorded in its ``Surprises & Discoveries``.
    """
    _write(tmp_path, "src/Ghost.java", "class Ghost {}\n")
    _write(tmp_path, "src/Present.java", "class Present {}\n")

    refused = {"count": 0, "seen": 0}
    real_stat = Path.stat

    def fake_stat(self, *args, **kwargs):
        if self.name == "Ghost.java":
            refused["seen"] += 1
            if refused["seen"] > 1:
                refused["count"] += 1
                raise FileNotFoundError(2, "No such file or directory")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    result = walk_repository(
        tmp_path, _manifest(include=("**/*.java",)), profile=profile
    )

    monkeypatch.undo()

    assert refused["count"] >= 1
    assert set(_files(result)) == {"src/Present.java"}
    assert result.dropped == []
    assert result.rescued_by_identity == []
    assert sum(t.files for t in result.totals.values()) == 1
