"""The extraction-gap walk: what Layer 0 is not looking at.

Implements Milestone 1 of the ExecPlan
(`docs/exec-plans/active/layer0-extraction-gap-detection.md`).

`discover_source_files` gates on an **allow-list** (`include_globs`), so anything
the allow-list does not name is never opened and never lands in the database.
This walk models the same tree with the same manifest exclusions and then
deliberately **drops** the `include_globs` gate, reporting what survives -- a
walk that applied the allow-list and then looked for what the allow-list
rejected would return the empty set by construction.

Nothing here touches a database, so it is unit-testable against small fixture
trees. Two conventions the rest of the feature depends on:

* **Every path is a repo-relative POSIX string**, built once as
  ``path.relative_to(repo_root).as_posix()`` and then used unchanged for glob
  matching, `vendor.yml` regex matching, tier attribution and display. On
  Windows ``**/*.java`` does not match ``a\\foo.java``, and `vendor.yml`'s
  patterns are anchored on ``/``. `Path` objects stay internal to this module;
  nothing in `WalkResult` carries one.
* **Extensions casefold; filenames and globs do not.** `pathspec`'s gitignore
  dialect is case-sensitive, so casefolding the glob side would admit files the
  real allow-list rejects and mislabel them ``rejected_by="language"`` when the
  truth is ``"include_globs"`` -- reversing the fix the label prescribes.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pathspec
from pydantic import BaseModel

from legacylift_search import provenance
from legacylift_search.config import Manifest
from legacylift_search.languages import detect_language
from legacylift_search.linguist import LinguistProfile
from legacylift_search.provenance import ThirdPartyClassifier

Tier = Literal[
    "indexed",
    "credential",
    "referenced_content",
    "asset",
    "first_party_excluded",
    "gap",
]

# The order the report prints the tiers in, and the key order of
# `WalkResult.totals`. It is deliberately NOT the tiering precedence: the
# credential test runs first, ahead of `indexed`, so that a keystore named by
# `include_globs` is still reported as a keystore -- see `walk_repository`.
TIER_ORDER: tuple[Tier, ...] = (
    "indexed",
    "credential",
    "referenced_content",
    "asset",
    "first_party_excluded",
    "gap",
)

# Tier membership by extension. Lowercase literals matched against the
# casefolded extension, per the case rule above.
CREDENTIAL_EXTENSIONS = frozenset({".p12", ".jks", ".keystore", ".pfx", ".pem"})
CREDENTIAL_NAMES = frozenset({"sstruststore", "cacerts"})
REFERENCED_CONTENT_EXTENSIONS = frozenset(
    {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf", ".zip"}
)
ASSET_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".psd",
        ".ico",
        ".bmp",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    }
)

# Formats that publish an origin about themselves. Reading one is a fact
# lookup, not an inference. Re-exported from `provenance`, which now owns the
# three rules so that `discover_source_files` applies the same ones -- see
# that module's header for why a path-shaped rule alone gets NNG's `.tld`
# directory wrong.
IDENTITY_EXTENSIONS = provenance.IDENTITY_EXTENSIONS


class WalkedFile(BaseModel):
    """One file that survived the manifest gate and third-party provenance."""

    relative_path: str
    extension: str  # ".jsp", or "" when the file has none
    size_bytes: int
    line_count: int
    tier: Tier
    rejected_by: Literal["include_globs", "language", "size_cap"] | None
    matched_glob: str | None  # first-party exclusion pattern that claimed it, else None


class DroppedFile(BaseModel):
    """A third-party file, removed from the walk and from both sides of every ratio.

    Recorded rather than discarded because 63 files vanishing without trace is
    the failure mode, and 63 files listed under one named rule is a
    five-second catch.

    Carries its own `size_bytes` and `line_count` because the raw
    (pre-suppression) headline is defined over the drops as well as the tiers,
    and `totals` is keyed on `Tier`, which has no drop member. Recovering them
    later would mean a second pass over the filesystem -- exactly what the
    one-read-per-file convention exists to avoid.
    """

    relative_path: str
    rule: Literal["declared_identity", "vendor_filename", "vendored_globs"]
    detail: str  # the declared identity, or the pattern that matched
    size_bytes: int
    line_count: int


class TierTotals(BaseModel):
    files: int
    size_bytes: int
    line_count: int


class WalkResult(BaseModel):
    files: list[WalkedFile]
    dropped: list[DroppedFile]
    rescued_by_identity: list[str]  # first-party files a vendored glob claimed
    totals: dict[Tier, TierTotals]


def _count_lines(path: Path) -> int:
    """Line count as ``sum(1 for _ in open(path, "rb"))``.

    Differs from ``wc -l`` by one on a file with no trailing newline; what
    matters is that one method is used on both sides of the ratio.
    """
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


# Both now live in `provenance`, aliased here so this module's call sites and
# its tests keep reading the same. `_declared_identity` is used by nothing in
# this file any more -- `ThirdPartyClassifier` applies it -- but it stays
# exported because the walk's tests assert on it directly.
_declared_identity = provenance.declared_identity


_deciding_glob = provenance.deciding_glob


def walk_repository(
    repo_root: Path,
    manifest: Manifest,
    *,
    profile: LinguistProfile,
    first_party_exclude_globs: Sequence[str] = (),
    vendored_globs: Sequence[str] = (),
    own_identities: Sequence[str] = (),
) -> WalkResult:
    """Walk `repo_root`, dropping third-party files and tiering the rest.

    Order of operations per file, exactly:

    1. **Manifest gate.** A file matching `exclude_globs` is not part of the
       walk at all -- not counted, not tiered, not reported.
    2. **Third-party provenance**, in strict precedence order: declared
       identity, then `vendor.yml`'s filename patterns, then `vendored_globs`.
       A third-party file is dropped.
    3. **Tiering**, mutually exclusive, so that the six tiers plus the drop
       bucket reconcile exactly to the tree minus the manifest exclusions. The
       credential test runs first and outranks every other tier including
       `indexed`; below it the precedence is referenced content, asset,
       first-party excluded, gap, with `indexed` taken from the `include_globs`
       match.

    Args:
        repo_root: Absolute path to the repository root.
        manifest: Manifest supplying `include_globs`, `exclude_globs` and
            `max_file_bytes` -- the same three gates `discover_source_files`
            applies.
        profile: The vendored linguist profile, for its adopted `vendor.yml`
            filename patterns. Its directory patterns are never consulted.
        first_party_exclude_globs: "Ours, and we chose not to analyze it."
            Applied to both sides of the ratio as a named tier.
        vendored_globs: "Not this codebase, never was." A drop.
        own_identities: Tokens naming the client's own domain. With none
            supplied the declared-identity rule is skipped entirely, because
            "authoritative in both directions" read against an empty token set
            makes every file that declares any identity third-party.

    Returns:
        A `WalkResult` whose `totals` carry all six tiers, zeroed ones included.
    """
    repo_root = repo_root.resolve()
    project = manifest.project

    include_spec = pathspec.PathSpec.from_lines("gitignore", project.include_globs)
    exclude_spec = pathspec.PathSpec.from_lines("gitignore", project.exclude_globs)

    first_party_patterns = list(first_party_exclude_globs)
    first_party_spec = (
        pathspec.PathSpec.from_lines("gitignore", first_party_patterns)
        if first_party_patterns
        else None
    )
    # The three provenance rules, their precedence, and the vendor.yml
    # filename-SHAPED matching convention all live in `provenance` now, so
    # that `discover_source_files` applies exactly these and the index cannot
    # disagree with the walk about what is third-party.
    third_party = ThirdPartyClassifier(
        profile=profile,
        vendored_globs=vendored_globs,
        own_identities=own_identities,
    )

    files: list[WalkedFile] = []
    dropped: list[DroppedFile] = []
    rescued_by_identity: list[str] = []
    totals: dict[Tier, TierTotals] = {
        tier: TierTotals(files=0, size_bytes=0, line_count=0) for tier in TIER_ORDER
    }

    for path in repo_root.rglob("*"):
        # `is_file` re-raises EACCES -- only ENOENT/ENOTDIR/EBADF/ELOOP are
        # ignored -- so an ACL-unreadable file would crash the walk here, ahead
        # of the guarded `stat()` below. `gaps` never exits nonzero on a
        # completed walk, so an unreachable entry is skipped like any other.
        try:
            if not path.is_file():
                continue
        except OSError:
            continue

        try:
            relative_path = path.relative_to(repo_root).as_posix()
        except ValueError:
            continue

        # 1. Manifest gate.
        if exclude_spec.match_file(relative_path):
            continue

        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue

        extension = path.suffix.lower()

        # Counted here, before provenance, because a dropped file needs its
        # lines too and this is the one pass that reads the file. Every path
        # below this point -- drop or tier -- reads the file's lines exactly
        # once.
        line_count = _count_lines(path)

        # 2. Third-party provenance.
        verdict, rescued = third_party.classify(path, relative_path, extension)
        if verdict is not None:
            dropped.append(
                DroppedFile(
                    relative_path=relative_path,
                    rule=verdict.rule,
                    detail=verdict.detail,
                    size_bytes=size_bytes,
                    line_count=line_count,
                )
            )
            continue
        if rescued:
            rescued_by_identity.append(relative_path)

        # 3. Tiering.
        first_party_glob = _deciding_glob(first_party_spec, first_party_patterns, relative_path)
        rejected_by: Literal["include_globs", "language", "size_cap"] | None = None
        matched_glob: str | None = None

        if (
            extension in CREDENTIAL_EXTENSIONS
            or path.name.lower() in CREDENTIAL_NAMES
            or path.stem.lower() in CREDENTIAL_NAMES
        ):
            # Outranks every other tier, `indexed` included, so that a keystore
            # can never be hidden -- not by an image glob, and not by an
            # allow-list that happens to name its extension, which would bury
            # it part-way down a gap list instead. Contents are never read.
            tier: Tier = "credential"
        elif include_spec.match_file(relative_path):
            if first_party_glob is not None:
                # This branch is why the indexed tier is smaller than repo_files.
                tier = "first_party_excluded"
                matched_glob = first_party_glob
            elif detect_language(path) is None:
                tier = "gap"
                rejected_by = "language"
            elif size_bytes > project.max_file_bytes:
                tier = "gap"
                rejected_by = "size_cap"
            else:
                tier = "indexed"
        elif extension in REFERENCED_CONTENT_EXTENSIONS:
            # Membership is by extension, not by whether a reference was found,
            # so a zero-reference template stays a visible finding.
            tier = "referenced_content"
        elif extension in ASSET_EXTENSIONS:
            tier = "asset"
        elif first_party_glob is not None:
            tier = "first_party_excluded"
            matched_glob = first_party_glob
        else:
            tier = "gap"
            rejected_by = "include_globs"

        files.append(
            WalkedFile(
                relative_path=relative_path,
                extension=extension,
                size_bytes=size_bytes,
                line_count=line_count,
                tier=tier,
                rejected_by=rejected_by,
                matched_glob=matched_glob,
            )
        )

        row = totals[tier]
        row.files += 1
        row.size_bytes += size_bytes
        row.line_count += line_count

    return WalkResult(
        files=files,
        dropped=dropped,
        rescued_by_identity=rescued_by_identity,
        totals=totals,
    )


__all__ = [
    "ASSET_EXTENSIONS",
    "CREDENTIAL_EXTENSIONS",
    "CREDENTIAL_NAMES",
    "IDENTITY_EXTENSIONS",
    "REFERENCED_CONTENT_EXTENSIONS",
    "TIER_ORDER",
    "DroppedFile",
    "Tier",
    "TierTotals",
    "WalkResult",
    "WalkedFile",
    "walk_repository",
]
