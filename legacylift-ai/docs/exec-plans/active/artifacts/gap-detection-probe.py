#!/usr/bin/env python
"""Reproduce the acceptance numbers in `pending/layer0-extraction-gap-detection-decision.md`.

WHY THIS FILE IS COMMITTED
--------------------------
The first version of this probe was ad-hoc and lived in a session scratchpad. The
handoff that followed had to tell its reader "the tier-walk probe is NOT committed"
and describe the recipe in prose, which cost the next session a re-derivation. This
script is the recipe. It is not production code and nothing imports it; it exists so
that §2, §2b and §3.I of the decision record can be re-measured by anyone, and so a
disagreement with those numbers is a bug in one place rather than an argument.

    <venv>/python.exe docs/exec-plans/active/artifacts/gap-detection-probe.py nng
    <venv>/python.exe docs/exec-plans/active/artifacts/gap-detection-probe.py ctcm

Use the venv interpreter directly — the PATH `legacylift-search` shim is broken:
    tools/legacylift_search/.venv/Scripts/python.exe

Needs `vendor.yml` from github-linguist. Pass --vendor <path>, or let it fetch:
    https://raw.githubusercontent.com/github-linguist/linguist/main/lib/linguist/vendor.yml
(MIT (c) GitHub.) `pyyaml` is NOT a runtime dependency of legacylift_search; it is
present in the venv only as a transitive dep, so this script may need `pip install
pyyaml` in a clean environment. That is deliberate — see Q11/Q23, which keep the
runtime free of it.

WHAT IT IMPLEMENTS (record §3.K, Q26 + Q27)
-------------------------------------------
Walk order, once per file:

  1. manifest `exclude_globs` + `**/legacylift-docs/**`  -> dropped, not part of the walk
  2. THIRD-PARTY provenance, in precedence order         -> dropped
       a. declared identity, where the format publishes one, and it is
          AUTHORITATIVE IN BOTH DIRECTIONS: a file naming the client's own
          domain is first-party even when a vendored glob claims it. This is
          what keeps `nngauthz.tld` and `naesb.tld` out of the vendored bucket.
       b. vendor.yml FILENAME patterns only (its 55 directory-shaped patterns
          are NOT adopted: `(^|/)[Ee]xtern(als?)?/` alone claims 63 first-party
          files on NNG)
       c. the assess `vendored_globs` list
  3. tiers, mutually exclusive, in this precedence:
       indexed -> credential -> referenced content -> asset -> first-party excluded -> gap

`first-party excluded` applies to BOTH sides of the ratio (Q27): it can claim a file
that also matches `include_globs`, which is why the `indexed` tier is smaller than
`repo_files`. The script prints that reconciliation, because it is the thing an
implementer gets wrong.

Headline = gap / (gap + indexed), reported in bytes and in lines.
KB = round(bytes / 1024) everywhere, per tier and total alike, so the column sums.
Lines = sum(1 for _ in open(path, 'rb')) — differs from `wc -l` by one on a file
with no trailing newline; what matters is that one method is used on both sides.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "legacylift_search" / "src"))

import pathspec  # noqa: E402
import yaml  # noqa: E402

from legacylift_search.config import ProjectConfig  # noqa: E402

VENDOR_URL = (
    "https://raw.githubusercontent.com/github-linguist/linguist/main/lib/linguist/vendor.yml"
)

# --- tier membership, by extension (Q26) ------------------------------------
CRED_EXT = {".p12", ".jks", ".keystore", ".pfx", ".pem"}
CRED_FN = {"sstruststore", "cacerts"}
REFCONTENT = {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".pdf", ".zip"}
ASSET = {".png", ".jpg", ".jpeg", ".gif", ".psd", ".ico", ".bmp", ".svg",
         ".woff", ".woff2", ".ttf", ".eot"}

# --- declared identity (Q27) ------------------------------------------------
DECLARES = {".tld", ".xsd", ".dtd"}
_URI = re.compile(rb"<uri>\s*([^<\s]+)\s*</uri>", re.I)
_TNS = re.compile(rb'targetNamespace\s*=\s*"([^"]+)"', re.I)
_PUB = re.compile(rb'PUBLIC\s+"([^"]+)"', re.I)

# --- corpora ----------------------------------------------------------------
# NNG's `vendored_globs` / `exclude_globs` below are the Q27 RE-CLASSIFICATION of
# the 45 patterns that `/modernize-assess` wrote into one flat list on 2026-08-04.
# They are recorded here because §3.I's numbers cannot be reproduced without them
# and the live `knowledge.sqlite` still holds the un-split original. When assess is
# re-run with the two-list prompt (shipped 2026-09-01) these should come from
# `domains.json` instead, and this block becomes the expected output.
#
# Dropped from the original list entirely, per the maintainer: `db/**` and
# `ple-persistence/sql/**` — 25 files of Quartz DDL, FarmTap backup/rollback and
# 16 data-cleanup queries that encode real data-quality rules. Business rules
# written in SQL, indexed, and four of check two's eight findings.
NNG_VENDORED = [
    "ple-web/src/main/webapp/content/javascript/lib/**",
    "ple-web/src/main/webapp/content/javascript/prototype.js",
    "ple-web/src/main/webapp/content/javascript/calendar_popup.js",
    "ple-web/src/main/webapp/content/javascript/wz_tooltip.js",
    "ple-web/src/main/webapp/content/javascript/tip_balloon.js",
    "ple-web/src/main/webapp/content/theme/jquery/**",
    "ple-web/src/main/webapp/WEB-INF/lib/**",
    # 9/11 vendored; nngauthz.tld and naesb.tld are rescued by declared identity.
    "ple-web/src/main/webapp/WEB-INF/tld/**",
    "**/*.dtd",   # all 4 are Hibernate's and the W3C's
    "**/*.xsd",   # all 14 are Spring's published schemas
]
NNG_FIRSTPARTY = [
    "*/bin/**", "ple-services-test/**", "ple-web/src/main/webapp/content/images/**",
    "jamon-web/**", "ple-ear/**", "**/.settings/**", "**/.apt_generated/**", ".gradle/**",
    "**/.classpath", "**/.project", "**/.checkstyle", "**/.pmd", "**/.factorypath",
    "**/.acignore", "**/.compatibility", "**/.gitignore", ".gitattributes",
    "**/build.gradle", "**/build.xml", "settings.gradle", "gradlew.bat", "gradle/**",
    "Jenkinsfile", "azure-pipelines.yaml", "**/MANIFEST.MF", "**/*.keep",
    "**/spring.xmlcatalog", "semantic-search.manifest.json", "**/.tern-project",
    "**/.temp-*", "**/*.gph", "**/favicon.ico", "legacylift-docs/**",
]

CORPORA = {
    # ctcm-api has NO knowledge.sqlite, so it has no first-party list. That makes it
    # the control on the both-sides logic (its reconciliation delta must be 0).
    # It does NOT exercise the command's predicted mode, which this comment used to
    # claim: that turns on index.sqlite, not knowledge.sqlite, and ctcm-api's
    # index.sqlite exists at the default resolved path (4,715 repo_files rows,
    # measured 2026-09-02), so a bare `gaps` run against it is observed.
    "nng": dict(
        root=REPO / "repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app",
        db=REPO / "repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.app"
                  "/index/code-search/index.sqlite",
        vendored=NNG_VENDORED, firstparty=NNG_FIRSTPARTY, own=("nngco.com",),
        expect="871 indexed / 276 gap / 482 first-party / 60 asset / 4 credential, "
               "walk 1693, 19.60% bytes, 17.55% lines, check two 5",
    ),
    "ctcm": dict(
        root=REPO / "repos/ctcm/ctcm-api",
        db=REPO / "repos/ctcm/ctcm-api/legacylift-docs/index/code-search/index.sqlite",
        vendored=[], firstparty=[], own=("ctcm",),
        expect="4715 indexed / 186 gap / 0 first-party / 0 asset / 59 referenced content, "
               "walk 4960, 3.15% bytes, 3.14% lines, check two 0",
    ),
}


def count_lines(path: Path) -> int:
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def declared_identity(path: Path) -> str | None:
    """The origin a file states about itself, or None if it states none."""
    try:
        head = path.read_bytes()[:8000]
    except OSError:
        return None
    m = _URI.search(head) or _TNS.search(head) or _PUB.search(head)
    return m.group(1).decode("utf-8", "replace") if m else None


def load_vendor_patterns(path: str | None) -> list[re.Pattern]:
    """vendor.yml's FILENAME/extension patterns only — never its directory ones."""
    if path:
        raw = Path(path).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(VENDOR_URL, timeout=60) as r:
            raw = r.read().decode("utf-8")
    entries = yaml.safe_load(raw)
    return [re.compile(p) for p in entries if not p.rstrip("$").endswith("/")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("corpus", choices=sorted(CORPORA))
    ap.add_argument("--vendor", help="local vendor.yml (else fetched from GitHub)")
    ap.add_argument(
        "--repo",
        help="repository root holding repos/. Defaults to this file's checkout — "
             "pass the MAIN checkout when running from a worktree, since the "
             "corpora are not checked out into worktrees.",
    )
    args = ap.parse_args()
    C = CORPORA[args.corpus]

    if args.repo:
        base = Path(args.repo).resolve()
        C = dict(C,
                 root=base / Path(C["root"]).relative_to(REPO),
                 db=base / Path(C["db"]).relative_to(REPO))

    root = Path(C["root"])
    if not root.exists():
        print(f"corpus not found: {root}", file=sys.stderr)
        print("The corpora live in the MAIN checkout, not in a worktree — "
              "re-run with --repo <main checkout>.", file=sys.stderr)
        return 2

    cfg = ProjectConfig()
    include = pathspec.PathSpec.from_lines("gitignore", cfg.include_globs)
    exclude = pathspec.PathSpec.from_lines(
        "gitignore", cfg.exclude_globs + ["**/legacylift-docs/**"]
    )
    vendor_fn = load_vendor_patterns(args.vendor)
    vendored = (pathspec.PathSpec.from_lines("gitignore", C["vendored"])
                if C["vendored"] else None)
    firstparty = (pathspec.PathSpec.from_lines("gitignore", C["firstparty"])
                  if C["firstparty"] else None)

    tiers: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    gap_by_ext: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    refcontent: list[tuple[str, str]] = []
    rescued: list[str] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if exclude.match_file(rel):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        lines = count_lines(path)
        ext = path.suffix.lower()

        # --- provenance ---
        identity = declared_identity(path) if ext in DECLARES else None
        third_party = False
        if identity is not None:
            ours = any(o in identity.lower() for o in C["own"])
            third_party = not ours
            if ours and vendored is not None and vendored.match_file(rel):
                rescued.append(rel)
        elif any(p.search(rel) for p in vendor_fn):
            third_party = True
        elif vendored is not None and vendored.match_file(rel):
            third_party = True
        if third_party:
            row = tiers["third-party (dropped)"]
            row[0] += 1; row[1] += size; row[2] += lines
            continue

        # --- tiers ---
        name, stem = path.name.lower(), os.path.splitext(path.name.lower())[0]
        excluded_fp = firstparty is not None and firstparty.match_file(rel)
        if include.match_file(rel):
            tier = "first-party excl" if excluded_fp else "indexed"
        elif ext in CRED_EXT or stem in CRED_FN or name in CRED_FN:
            tier = "credential"
        elif ext in REFCONTENT:
            tier = "referenced content"
            refcontent.append((rel, path.name))
        elif ext in ASSET:
            tier = "asset"
        elif excluded_fp:
            tier = "first-party excl"
        else:
            tier = "gap"

        row = tiers[tier]
        row[0] += 1; row[1] += size; row[2] += lines
        if tier == "gap":
            e = gap_by_ext[ext or "(none)"]
            e[0] += 1; e[1] += size; e[2] += lines

    order = ["indexed", "gap", "first-party excl", "referenced content", "asset", "credential"]
    total = [sum(tiers[k][i] for k in order) for i in range(3)]
    gap_b, idx_b = tiers["gap"][1], tiers["indexed"][1]
    gap_l, idx_l = tiers["gap"][2], tiers["indexed"][2]

    print(f"=== {args.corpus} ===")
    print(f"  expected: {C['expect']}\n")
    d = tiers["third-party (dropped)"]
    print(f"  {'third-party DROPPED':<22}{d[0]:>6}{round(d[1]/1024):>8} KB{d[2]:>9} lines")
    for k in order:
        f, b, ln = tiers[k]
        print(f"  {k:<22}{f:>6}{round(b/1024):>8} KB{ln:>9} lines")
    # The displayed total is the SUM OF THE DISPLAYED ROWS, not a separately
    # rounded total — that is the only way the column a reader adds up actually
    # adds up. Rounding each row and the true total independently disagrees by
    # one whenever the fractional parts accumulate past a half (measured: it
    # sums on nng and does not on ctcm). Exact bytes belong in `--json`.
    kb_sum = sum(round(tiers[k][1] / 1024) for k in order)
    print(f"  {'WALK TOTAL':<22}{total[0]:>6}{kb_sum:>8} KB{total[2]:>9} lines")
    print(f"  (displayed KB total is the sum of the rows; exact bytes {total[1]}, "
          f"round(total/1024)={round(total[1]/1024)})")
    print(f"  HEADLINE  {100*gap_b/(gap_b+idx_b):.2f}% of bytes, "
          f"{100*gap_l/(gap_l+idx_l):.2f}% of lines")

    print("\n  gap by extension:")
    for ext, (f, b, ln) in sorted(gap_by_ext.items(), key=lambda kv: -kv[1][1])[:10]:
        print(f"    {ext:<14}{f:>5}{round(b/1024):>7} KB{ln:>8} lines")
    if rescued:
        print("\n  rescued by declared identity (a vendored glob claimed them; "
              "the file says otherwise):")
        for r in sorted(set(rescued)):
            print(f"    {r}")

    db = Path(C["db"])
    if not db.exists():
        print(f"\n  no index at {db} — skipping check two and reference counts")
        return 0

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    n_repo_files = conn.execute("SELECT COUNT(*) FROM repo_files").fetchone()[0]
    delta = n_repo_files - tiers["indexed"][0]
    print(f"\n  reconciliation: repo_files={n_repo_files}, indexed tier={tiers['indexed'][0]}, "
          f"delta={delta}")
    print("    The delta is the first-party exclusion (and any third-party drop that was")
    print("    indexed). The report must STATE this; observed mode must not treat these")
    print("    as walk-vs-index discrepancies.")

    rows = conn.execute(
        "SELECT f.relative_path p FROM repo_files f "
        "LEFT JOIN symbols s ON s.file_id = f.id "
        "GROUP BY f.id HAVING COUNT(s.id) = 0 AND f.size_bytes >= 2048 "
        "ORDER BY f.size_bytes DESC"
    ).fetchall()

    def survives(p: str) -> bool:
        if firstparty is not None and firstparty.match_file(p):
            return False
        if vendored is not None and vendored.match_file(p):
            return False
        return not any(r.search(p) for r in vendor_fn)

    kept = [r["p"] for r in rows if survives(r["p"])]
    print(f"\n  check two (--min-bytes 2048): {len(rows)} raw -> {len(kept)} after exclusion")
    for k in kept:
        print(f"    {k}")

    if refcontent:
        blobs = [r[0] or "" for r in conn.execute("SELECT text FROM chunks")]
        zero = [rel for rel, nm in refcontent if not any(nm in b for b in blobs)]
        print(f"\n  referenced content: {len(refcontent)} files, "
              f"{len(zero)} with ZERO indexed references")
        for z in zero:
            print(f"    zero-ref: {z}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
