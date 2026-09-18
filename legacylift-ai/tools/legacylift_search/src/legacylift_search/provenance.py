"""Third-party provenance: did this file arrive with the codebase, or with a library?

Extracted from `gaps.py` so that the extraction-gap walk and
`discover_source_files` answer "is this third-party?" with **one**
implementation rather than two that drift.

The split this module exists to preserve was measured on NNG's 13 `.tld`
files: `ple-web/src/main/webapp/WEB-INF/tld/**` is a `vendored_globs` entry,
which claims all eleven files in that directory -- but two of them,
`naesb.tld` and `nngauthz.tld`, declare `<uri>http://www.nngco.com/...</uri>`
and are the client's own tag libraries. A path-shaped rule cannot tell them
apart from the JSTL, Spring, displaytag, joda and tiles descriptors sitting
beside them; the declared identity can, and it is authoritative in **both**
directions -- it rescues a first-party file from a vendored glob, and it drops
a vendor file no glob happened to name (the two `xmlcatalog/spring*.tld`).

Precedence is strict and is the reason this is a class rather than three
functions: declared identity, then `vendor.yml`'s filename patterns, then
`vendored_globs`. The first rule to fire decides, and identity short-circuits
the other two.

Conventions inherited from `gaps.py` and depended on by both callers:

* **`relative_path` is a repo-relative POSIX string.** `vendor.yml`'s patterns
  are filename-SHAPED, not filename-SCOPED -- they are matched with
  `re.search` against the whole relative path, so a pattern anchored on
  `(^|/)` claims a match at any depth. Matching `Path.name` instead compiles,
  runs, and silently changes the attribution.
* **`extension` is casefolded; globs are not.** `pathspec`'s gitignore dialect
  is case-sensitive.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pathspec
from pydantic import BaseModel

from legacylift_search.linguist import LinguistProfile

# Extensions whose files state their own origin in their first bytes. Read
# only for these: the head read is the one filesystem cost this module adds,
# and outside these three formats there is nothing to find.
IDENTITY_EXTENSIONS = frozenset({".tld", ".xsd", ".dtd"})
_IDENTITY_HEAD_BYTES = 8000
_IDENTITY_PATTERNS = (
    re.compile(rb"<uri>\s*([^<\s]+)\s*</uri>", re.I),
    re.compile(rb'targetNamespace\s*=\s*"([^"]+)"', re.I),
    re.compile(rb'PUBLIC\s+"([^"]+)"', re.I),
)

ProvenanceRule = Literal["declared_identity", "vendor_filename", "vendored_globs"]


class ProvenanceVerdict(BaseModel):
    """Why a file was judged third-party."""

    rule: ProvenanceRule
    detail: str  # the declared identity, or the pattern that matched


def declared_identity(path: Path) -> str | None:
    """The origin the file states about itself, or None if it states none."""
    try:
        with path.open("rb") as handle:
            head = handle.read(_IDENTITY_HEAD_BYTES)
    except OSError:
        return None

    for pattern in _IDENTITY_PATTERNS:
        match = pattern.search(head)
        if match is not None:
            return match.group(1).decode("utf-8", "replace")
    return None


def deciding_glob(
    spec: pathspec.PathSpec | None, patterns: Sequence[str], rel: str
) -> str | None:
    """The pattern whose match decided that `rel` is included, or None.

    Gitignore dialect: the **last** matching pattern decides and a
    `!`-prefixed pattern *un*-excludes, so a file whose last match is a
    negation is not claimed at all. `check_file` reports both the decision and
    the deciding pattern's position; `match_file` returns a bool and cannot
    name the pattern, and looping over per-pattern specs taking the first hit
    compiles, runs, and gets negation backwards.
    """
    if spec is None:
        return None
    result = spec.check_file(rel)
    if not result.include:
        return None
    if result.index is None:
        return None
    # `index` addresses the compiled pattern list, which drops blank lines but
    # keeps comments, so read the pattern text back off the compiled object.
    compiled = spec.patterns[result.index]
    text = getattr(compiled, "pattern", None)
    if isinstance(text, str):
        return text
    return patterns[result.index] if result.index < len(patterns) else None


class ThirdPartyClassifier:
    """Applies the three provenance rules in their settled precedence order.

    Construct once per walk or per index run; the compiled specs and regexes
    are the expensive part and are built here rather than per file.
    """

    def __init__(
        self,
        *,
        profile: LinguistProfile,
        vendored_globs: Sequence[str] = (),
        own_identities: Sequence[str] = (),
    ) -> None:
        self._vendored_patterns = list(vendored_globs)
        self._vendored_spec = (
            pathspec.PathSpec.from_lines("gitignore", self._vendored_patterns)
            if self._vendored_patterns
            else None
        )
        self._vendor_filename_patterns = [
            (raw, re.compile(raw)) for raw in profile.vendor_filename_patterns
        ]
        # With no tokens the declared-identity rule is skipped entirely:
        # "authoritative in both directions" read against an empty token set
        # makes every file that declares any identity third-party.
        self._own_tokens = [token.lower() for token in own_identities if token]

    def classify(
        self, path: Path, relative_path: str, extension: str
    ) -> tuple[ProvenanceVerdict | None, bool]:
        """Judge one file.

        Args:
            path: The file, for the identity head read.
            relative_path: Repo-relative POSIX string.
            extension: Casefolded suffix, `""` when the file has none.

        Returns:
            `(verdict, rescued)`. `verdict` is None when the file is
            first-party. `rescued` is True only when a declared first-party
            identity overrode a `vendored_globs` match -- the walk reports
            those by name, and a caller that does not care can ignore it.
        """
        identity = (
            declared_identity(path)
            if self._own_tokens and extension in IDENTITY_EXTENSIONS
            else None
        )
        if identity is not None:
            # Authoritative in both directions, and it short-circuits the
            # remaining rules: a file naming the client's own domain is
            # first-party even when a vendored glob claims it.
            lowered = identity.lower()
            if not any(token in lowered for token in self._own_tokens):
                return ProvenanceVerdict(rule="declared_identity", detail=identity), False
            rescued = self._vendored_spec is not None and self._vendored_spec.match_file(
                relative_path
            )
            return None, rescued

        vendor_hit = next(
            (
                raw
                for raw, compiled in self._vendor_filename_patterns
                if compiled.search(relative_path)
            ),
            None,
        )
        if vendor_hit is not None:
            return ProvenanceVerdict(rule="vendor_filename", detail=vendor_hit), False

        vendored_hit = deciding_glob(
            self._vendored_spec, self._vendored_patterns, relative_path
        )
        if vendored_hit is not None:
            return ProvenanceVerdict(rule="vendored_globs", detail=vendored_hit), False

        return None, False

    def is_third_party(self, path: Path, relative_path: str, extension: str) -> bool:
        """`classify` reduced to the one bit `discover_source_files` needs."""
        verdict, _ = self.classify(path, relative_path, extension)
        return verdict is not None


__all__ = [
    "IDENTITY_EXTENSIONS",
    "ProvenanceRule",
    "ProvenanceVerdict",
    "ThirdPartyClassifier",
    "declared_identity",
    "deciding_glob",
]
