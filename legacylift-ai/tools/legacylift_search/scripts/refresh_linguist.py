"""Regenerate ``profiles/linguist.json`` from upstream github-linguist data.

This is a development script run **by hand**, never on a schedule and never at
run time. It is the only place in this tool that imports ``pyyaml``, which is
deliberately absent from ``pyproject.toml``'s runtime dependencies; install it
into the venv separately if it is missing.

The fetch is two-step on purpose. ``raw.githubusercontent.com`` returns no
commit identity, so a ``.../main/...`` GET cannot populate the
``upstream_commit`` field the profile carries. The ref is therefore resolved to
a commit SHA through the API first, and both YAML downloads are pinned to that
SHA -- which is what makes ``--ref <that sha>`` regenerate a byte-identical
file later.

Usage:

    python scripts/refresh_linguist.py \\
        --ref d5214e1612c858ba14bf98edeca57e1683276f1d \\
        --out src/legacylift_search/profiles/linguist.json

Only the *filename-shaped* half of ``vendor.yml`` is adopted downstream. The
directory patterns are still carried in the JSON, but in a separate list, so
that "the directory patterns are not adopted" is an auditable property of the
data rather than a comment in code -- three directories on the reference corpus
have three different truths about vendoring, so a directory pattern cannot
decide provenance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = 1

ATTRIBUTION = (
    "Derived from github/linguist languages.yml and vendor.yml. "
    "MIT (c) GitHub, Inc."
)

REPO = "github-linguist/linguist"
COMMIT_API = "https://api.github.com/repos/{repo}/commits/{ref}"
RAW_URL = "https://raw.githubusercontent.com/{repo}/{sha}/lib/linguist/{name}"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _get(url: str, accept: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": "legacylift-refresh-linguist"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def resolve_commit(ref: str) -> str:
    """Resolve a branch, tag or SHA to the 40-hex commit SHA it names."""
    payload = json.loads(
        _get(COMMIT_API.format(repo=REPO, ref=ref), "application/vnd.github+json")
    )
    sha = payload["sha"]
    if not _SHA_RE.match(sha):
        raise ValueError(
            f"{ref} resolved to something that is not a commit SHA: {sha!r}"
        )
    return sha


def fetch_yaml(sha: str, name: str) -> Any:
    return yaml.safe_load(
        _get(RAW_URL.format(repo=REPO, sha=sha, name=name), "text/plain")
    )


def build_language_maps(
    languages: dict[str, dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    """Invert languages.yml into extension->languages and filename->languages.

    Extension keys are casefolded, because the gate this data exists to explain
    casefolds too (``languages.py:105`` stores ``ext.lower()``). Filename keys
    are exact -- that is linguist's own semantics and git's, and ``Jenkinsfile``
    is not ``jenkinsfile``.
    """
    by_extension: dict[str, list[dict[str, Any]]] = {}
    by_filename: dict[str, list[dict[str, Any]]] = {}

    for name in sorted(languages):
        spec = languages[name]
        entry = {
            "name": name,
            "type": spec.get("type"),
            "group": spec.get("group"),
        }
        for ext in spec.get("extensions") or ():
            by_extension.setdefault(str(ext).lower(), []).append(entry)
        for filename in spec.get("filenames") or ():
            by_filename.setdefault(str(filename), []).append(entry)

    return by_extension, by_filename


def split_vendor_patterns(patterns: list[str]) -> tuple[list[str], list[str]]:
    """Partition vendor.yml regexes into filename-shaped and directory-shaped.

    The whole rule is one line: a pattern is directory-shaped when, with any
    trailing anchor removed, it ends in a slash. Only the filename-shaped half
    is adopted downstream.
    """
    filename_shaped: list[str] = []
    directory_shaped: list[str] = []
    for pattern in patterns:
        if pattern.rstrip("$").endswith("/"):
            directory_shaped.append(pattern)
        else:
            filename_shaped.append(pattern)
    return filename_shaped, directory_shaped


def write_profile(out_path: Path, profile: dict[str, Any]) -> None:
    """Write the profile byte-reproducibly.

    ``sort_keys`` plus an explicit LF newline is what makes two runs on two
    machines produce the same bytes; the Windows default of CRLF alone would
    break it, and the breakage stays invisible until the next refresh diff.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(profile, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate profiles/linguist.json from upstream linguist."
    )
    parser.add_argument(
        "--ref",
        default="main",
        help=(
            "Branch, tag or 40-hex SHA to fetch. The default is for a "
            "deliberate refresh; pass an explicit SHA to reproduce a snapshot."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "src"
        / "legacylift_search"
        / "profiles"
        / "linguist.json",
        help="Destination JSON path.",
    )
    args = parser.parse_args(argv)

    sha = resolve_commit(args.ref)
    print(f"[refresh-linguist] {args.ref} -> {sha}", file=sys.stderr)

    languages = fetch_yaml(sha, "languages.yml")
    vendor = fetch_yaml(sha, "vendor.yml")

    by_extension, by_filename = build_language_maps(languages)
    filename_patterns, directory_patterns = split_vendor_patterns(vendor)

    # The pruned maps cannot carry every upstream language: 6 of the pinned
    # snapshot's 833 are reachable by neither extension nor filename (REPL
    # transcripts, OpenAPI, interpreter-only OpenRC), so the maps hold 827
    # distinct names. Recording the source count keeps the upstream volume
    # assertable from the vendored file, which is what makes the M0 test a
    # bad-refresh detector for the fetch as well as for the inversion.
    profile = {
        "schema_version": SCHEMA_VERSION,
        "attribution": ATTRIBUTION,
        "upstream_commit": sha,
        "fetched_at": date.today().isoformat(),
        "upstream_language_count": len(languages),
        "extensions": by_extension,
        "filenames": by_filename,
        "vendor_filename_patterns": filename_patterns,
        "vendor_directory_patterns": directory_patterns,
    }

    write_profile(args.out, profile)

    print(
        f"[refresh-linguist] {len(languages)} languages, "
        f"{len(by_extension)} extension keys, {len(by_filename)} filename keys, "
        f"{len(vendor)} vendor regexes "
        f"({len(filename_patterns)} filename / {len(directory_patterns)} directory) "
        f"-> {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
