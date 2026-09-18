"""Repository file discovery with deterministic ignore rules.

Implements Milestone 3 of the ExecPlan
(`docs/exec-plans/active/semantic-code-search-graph-index.md`).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import pathspec

from legacylift_search.languages import detect_language
from legacylift_search.models import SourceFile
from legacylift_search.provenance import ThirdPartyClassifier


# Minimal interface for Manifest until Agent A1 completes config.py (Milestone 2).
# Once config.py is merged, replace this Protocol with the real import.
class _ProjectConfig(Protocol):
    """Duck-typed accessor for manifest.project fields needed by discovery."""

    include_globs: list[str]
    exclude_globs: list[str]
    max_file_bytes: int
    domains_file: str | None


class _Manifest(Protocol):
    """Duck-typed accessor for Manifest needed by discovery."""

    project: _ProjectConfig


def build_third_party_classifier(
    repo_root: Path, manifest: _Manifest
) -> ThirdPartyClassifier | None:
    """The classifier `manifest.project.domains_file` asks for, or None.

    Returns None when no `domains_file` is configured, and also when the
    configured file names no `vendored_globs` and no `own_identities` -- a
    classifier with neither can only ever fire `vendor.yml`'s filename
    patterns, and turning those on for every repository is a behavior change
    nobody asked for. Silent about a MISSING file for the same reason
    `resolve_analysis_dir` is: discovery runs in contexts where the
    modernization artifacts have not been authored yet.
    """
    configured = getattr(manifest.project, "domains_file", None)
    if not configured:
        return None

    path = Path(configured)
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists():
        return None

    # Imported here, not at module scope: `domain_tagger` imports this module,
    # so a top-level import would close the cycle.
    from legacylift_search.domain_tagger import load_domains_json
    from legacylift_search.linguist import load_linguist_profile

    domains = load_domains_json(path)
    if not domains.vendored_globs and not domains.own_identities:
        return None

    return ThirdPartyClassifier(
        profile=load_linguist_profile(),
        vendored_globs=domains.vendored_globs,
        own_identities=domains.own_identities,
    )


def discover_source_files(
    repo_root: Path,
    manifest: _Manifest,
    *,
    third_party: ThirdPartyClassifier | None = None,
) -> list[SourceFile]:
    """Discover all source files in the repository matching manifest rules.

    Args:
        repo_root: Absolute path to the repository root.
        manifest: Manifest with project.include_globs, project.exclude_globs,
                  and project.max_file_bytes.
        third_party: Provenance classifier override, for tests and for callers
            that have already built one. **Leave it unset in production code**
            -- when it is None the classifier is resolved from
            `manifest.project.domains_file` via
            `build_third_party_classifier`, which is what keeps all four
            `discover_source_files` call sites (the indexer, two CLI commands
            and the domain tagger) returning the same file set. They must:
            `_reap_file_domains_to_discovered` deletes `file_domains` rows for
            undiscovered paths, so a call site that disagreed would silently
            reap the rows another one had just written.

            When a classifier applies, files it judges third-party are
            skipped, applying the SAME three rules
            (declared identity, `vendor.yml` filename patterns,
            `vendored_globs`) in the same precedence order that
            `gaps.walk_repository` uses to populate its `dropped` bucket. When
            unresolvable, discovery behaves exactly as it always has -- the
            allow-list and exclude-list are the only gates.

            This exists because the 2026-09-08 coverage widening made the two
            sides disagree in a way path globs cannot fix. `**/*.tld` matches
            13 NNG files; 11 are JSTL/Spring/displaytag/joda/tiles descriptors
            the walk drops as third-party, and the two that are the client's
            own (`naesb.tld`, `nngauthz.tld`) sit in the SAME directory as
            nine of them. Only the declared `<uri>` separates them.

    Returns:
        List of SourceFile objects for all discovered files that match
        include globs, do not match exclude globs, are not third-party, have a
        recognized language, and are within the size limit.
    """
    repo_root = repo_root.resolve()

    if third_party is None:
        third_party = build_third_party_classifier(repo_root, manifest)

    # Build include and exclude specs using pathspec (gitignore-style globs).
    include_spec = pathspec.PathSpec.from_lines("gitignore", manifest.project.include_globs)
    exclude_spec = pathspec.PathSpec.from_lines("gitignore", manifest.project.exclude_globs)

    discovered: list[SourceFile] = []

    # Walk the entire repository tree.
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue

        # Compute relative path for glob matching (always use forward slashes for pathspec).
        try:
            relative_path = path.relative_to(repo_root).as_posix()
        except ValueError:
            # Path is not relative to repo_root; skip it.
            continue

        # Check exclude first (more efficient to skip early).
        if exclude_spec.match_file(relative_path):
            continue

        # Check include.
        if not include_spec.match_file(relative_path):
            continue

        # Third-party provenance, in the walk's precedence order. Placed after
        # the allow-list rather than before it (the walk's own order) purely
        # for cost: the identity rule reads the head of every `.tld`/`.xsd`/
        # `.dtd`, and a file the allow-list already rejected is skipped
        # either way, so the resulting file SET is identical.
        if third_party is not None and third_party.is_third_party(
            path, relative_path, path.suffix.lower()
        ):
            continue

        # Detect language.
        lang_spec = detect_language(path)
        if lang_spec is None:
            continue

        # Check file size.
        try:
            size_bytes = path.stat().st_size
        except OSError:
            # File disappeared or is inaccessible; skip it.
            continue

        if size_bytes > manifest.project.max_file_bytes:
            continue

        # Compute SHA-256 hash of file content.
        try:
            with path.open("rb") as f:
                content = f.read()
            file_sha256 = hashlib.sha256(content).hexdigest()
        except OSError:
            # Read error; skip this file.
            continue

        # Get modification time in nanoseconds (st_mtime_ns).
        try:
            mtime_ns = path.stat().st_mtime_ns
        except AttributeError:
            # Fallback for platforms without st_mtime_ns; convert st_mtime to nanoseconds.
            mtime_ns = int(path.stat().st_mtime * 1e9)

        discovered.append(
            SourceFile(
                absolute_path=path,
                repo_root=repo_root,
                relative_path=relative_path,
                language=lang_spec.key,
                size_bytes=size_bytes,
                sha256=file_sha256,
                mtime_ns=mtime_ns,
            )
        )

    return discovered


__all__ = [
    "build_third_party_classifier",
    "discover_source_files",
]
