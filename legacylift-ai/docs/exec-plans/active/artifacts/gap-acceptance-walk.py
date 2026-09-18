#!/usr/bin/env python
"""Scratch acceptance driver for M1 (`layer0-extraction-gap-detection.md`) of
`legacylift_search.gaps.walk_repository`.

NOT part of the repo, NOT a test — a throwaway script to diff its output,
line for line, against `docs/exec-plans/active/artifacts/gap-detection-probe.py`.

Usage (from the WORKTREE checkout, so PYTHONPATH resolves to the code under
test rather than the main checkout's different branch):

    cd C:/Users/dnorton/captechdev/legacylift-ai/.claude/worktrees/layer0-gap-detection/tools/legacylift_search
    PYTHONPATH="$PWD/src" \
        C:/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/python.exe \
        docs/exec-plans/active/artifacts/gap-acceptance-walk.py nng
    ... same, with "ctcm" ...

Fixtures used (siblings of this script):
    gap-acceptance-manifest.json     -- config.py's 32 default exclude_globs + **/legacylift-docs/**
    gap-acceptance-domains-nng.json  -- NNG's Q27-split vendored_globs / exclude_globs
                                        (first-party) / own_identities

Counting conventions (both load-bearing, both once wrong in this project):
  - Each row's KB is round(bytes / 1024).
  - THE DISPLAYED WALK TOTAL IS THE SUM OF THE DISPLAYED (ROUNDED) ROWS, not a
    separately-rounded true total. On ctcm-api the rows sum to 21918 KB while
    round(true_total_bytes / 1024) gives 21917 -- 21918 is correct.
  - The headline is computed from EXACT bytes/lines, never from the rounded
    KB column.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

CORPORA = {
    "nng": dict(
        repo_root=Path(
            "C:/Users/dnorton/captechdev/legacylift-ai/repos/"
            "nng-app-legacylift-analysis/legacy/customer.ple.nng.app"
        ),
        domains_path=HERE / "gap-acceptance-domains-nng.json",
        own_identities=["nngco.com"],
    ),
    "ctcm": dict(
        repo_root=Path(
            "C:/Users/dnorton/captechdev/legacylift-ai/repos/ctcm/ctcm-api"
        ),
        domains_path=None,  # no authored lists at all for this corpus
        own_identities=["ctcm"],
    ),
}

# The six tiers `walk_repository`'s WalkResult.totals carries, in the display
# order the probe uses, mapped to the probe's display labels.
DISPLAY_ORDER = [
    ("indexed", "indexed"),
    ("gap", "gap"),
    ("first_party_excluded", "first-party excl"),
    ("referenced_content", "referenced content"),
    ("asset", "asset"),
    ("credential", "credential"),
]


def _fmt_row(label: str, files: int, size_bytes: float, lines: int) -> str:
    return f"  {label:<22}{files:>6}{round(size_bytes / 1024):>8} KB{lines:>9} lines"


def _count_lines(path: Path) -> int:
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in CORPORA:
        print(f"usage: {argv[0]} nng|ctcm", file=sys.stderr)
        return 2
    corpus = argv[1]
    C = CORPORA[corpus]

    # --- imports that must succeed before anything else --------------------
    try:
        from legacylift_search.config import load_manifest
        from legacylift_search.linguist import load_linguist_profile
    except ImportError as exc:  # pragma: no cover - environment problem
        print(f"FAILED to import M0/config dependencies: {exc}", file=sys.stderr)
        return 1

    try:
        from legacylift_search.gaps import walk_repository
    except ImportError as exc:
        print(
            "legacylift_search.gaps.walk_repository is not importable yet "
            f"({exc}). This is expected if M1 has not shipped, or is "
            "mid-write, in this worktree. Leaving this driver in place for "
            "the integration agent — not writing a stub gaps.py.",
            file=sys.stderr,
        )
        return 1
    except AttributeError as exc:
        print(
            "legacylift_search.gaps exists but has no walk_repository "
            f"attribute yet ({exc}). Same situation as an ImportError here "
            "— M1 is mid-write. Leaving this driver in place.",
            file=sys.stderr,
        )
        return 1

    repo_root = C["repo_root"]
    if not repo_root.exists():
        print(f"corpus not found: {repo_root}", file=sys.stderr)
        return 2

    manifest_path = HERE / "gap-acceptance-manifest.json"
    manifest = load_manifest(manifest_path)

    first_party_exclude_globs: list[str] = []
    vendored_globs: list[str] = []
    if C["domains_path"] is not None:
        # Read via domain_tagger.load_domains_json -- deliberately NOT
        # editing/reading gaps.py or tests/test_gaps_walk.py, which are
        # off-limits; domain_tagger.py is this task's own deliverable 1.
        from legacylift_search.domain_tagger import load_domains_json

        domains_file = load_domains_json(C["domains_path"])
        first_party_exclude_globs = domains_file.exclude_globs
        vendored_globs = domains_file.vendored_globs

    profile = load_linguist_profile()

    walk = walk_repository(
        repo_root,
        manifest,
        profile=profile,
        first_party_exclude_globs=first_party_exclude_globs,
        vendored_globs=vendored_globs,
        own_identities=C["own_identities"],
    )

    # --- third-party DROPPED: WalkResult.dropped carries no byte/line count,
    # so compute it here the same way the probe does, straight off disk. ----
    dropped_files = 0
    dropped_bytes = 0
    dropped_lines = 0
    for d in walk.dropped:
        p = repo_root / d.relative_path
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        dropped_files += 1
        dropped_bytes += size
        dropped_lines += _count_lines(p)

    print(f"=== {corpus} ===\n")
    print(_fmt_row("third-party DROPPED", dropped_files, dropped_bytes, dropped_lines))

    kb_sum = 0
    files_sum = 0
    lines_sum = 0
    exact_bytes_sum = 0
    for key, label in DISPLAY_ORDER:
        totals = walk.totals[key]
        print(_fmt_row(label, totals.files, totals.size_bytes, totals.line_count))
        kb_sum += round(totals.size_bytes / 1024)
        files_sum += totals.files
        lines_sum += totals.line_count
        exact_bytes_sum += totals.size_bytes

    print(f"  {'WALK TOTAL':<22}{files_sum:>6}{kb_sum:>8} KB{lines_sum:>9} lines")

    indexed = walk.totals["indexed"]
    gap = walk.totals["gap"]
    gap_denom_bytes = gap.size_bytes + indexed.size_bytes
    gap_denom_lines = gap.line_count + indexed.line_count
    headline_bytes_pct = 100 * gap.size_bytes / gap_denom_bytes if gap_denom_bytes else 0.0
    headline_lines_pct = 100 * gap.line_count / gap_denom_lines if gap_denom_lines else 0.0

    print(f"\n  HEADLINE  {headline_bytes_pct:.2f}% of bytes, {headline_lines_pct:.2f}% of lines")

    # --- raw (pre-suppression) headline --------------------------------
    # Per the plan's Decision Log: every file surviving the manifest gate
    # that is NOT in the indexed tier, PLUS the third-party drops, over
    # indexed plus that. Derived from EXACT bytes/lines, never the rounded
    # KB column.
    raw_num_bytes = (exact_bytes_sum - indexed.size_bytes) + dropped_bytes
    raw_denom_bytes = indexed.size_bytes + raw_num_bytes
    raw_num_lines = (lines_sum - indexed.line_count) + dropped_lines
    raw_denom_lines = indexed.line_count + raw_num_lines
    raw_bytes_pct = 100 * raw_num_bytes / raw_denom_bytes if raw_denom_bytes else 0.0
    raw_lines_pct = 100 * raw_num_lines / raw_denom_lines if raw_denom_lines else 0.0

    print(
        f"  RAW HEADLINE (pre-suppression)  {raw_bytes_pct:.2f}% of bytes, "
        f"{raw_lines_pct:.2f}% of lines"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
