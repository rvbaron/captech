"""M1 acceptance: the assertions the tier table does not show.

Drop attribution, the two identity rescues, gap-by-extension, the
`rejected_by` and `matched_glob` labels, and the POSIX guarantee -- none of
which the probe can check, because it implements no labels. Sibling fixtures
as for `gap-acceptance-walk.py`.
"""
import collections
import json
import sys
from pathlib import Path

from legacylift_search.config import Manifest
from legacylift_search.gaps import walk_repository
from legacylift_search.linguist import load_linguist_profile

HERE = Path(__file__).resolve().parent
MAIN = Path("C:/Users/dnorton/captechdev/legacylift-ai")

CORPORA = {
    "nng": dict(
        repo_root=MAIN / "repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app",
        domains=HERE / "gap-acceptance-domains-nng.json",
        own=["nngco.com"],
    ),
    "ctcm": dict(
        repo_root=MAIN / "repos/ctcm/ctcm-api",
        domains=None,
        own=["ctcm"],
    ),
}


def run(name):
    spec = CORPORA[name]
    manifest = Manifest.model_validate(
        json.loads((HERE / "gap-acceptance-manifest.json").read_text(encoding="utf-8"))
    )
    first_party, vendored = [], []
    if spec["domains"]:
        d = json.loads(spec["domains"].read_text(encoding="utf-8"))
        first_party, vendored = d.get("exclude_globs", []), d.get("vendored_globs", [])

    walk = walk_repository(
        spec["repo_root"],
        manifest,
        profile=load_linguist_profile(),
        first_party_exclude_globs=first_party,
        vendored_globs=vendored,
        own_identities=spec["own"],
    )

    print(f"=== {name} ===")

    rules = collections.Counter(d.rule for d in walk.dropped)
    print("  drop attribution:", dict(rules))
    if name == "nng":
        print("  rescued_by_identity:", sorted(walk.rescued_by_identity))

    gap = [f for f in walk.files if f.tier == "gap"]
    print(f"  gap files: {len(gap)}")
    labels = collections.Counter(f.rejected_by for f in gap)
    print("  gap rejected_by:", dict(labels))

    by_ext = collections.defaultdict(lambda: [0, 0, 0])
    for f in gap:
        row = by_ext[f.extension]
        row[0] += 1
        row[1] += f.size_bytes
        row[2] += f.line_count
    print("  gap by extension (byte-ordered):")
    for ext, (n, b, ln) in sorted(by_ext.items(), key=lambda kv: -kv[1][1])[:8]:
        print(f"    {ext:<12} {n:>4} {round(b / 1024):>6} KB {ln:>7} lines")

    fp = [f for f in walk.files if f.tier == "first_party_excluded"]
    unlabelled = [f.relative_path for f in fp if f.matched_glob is None]
    per_glob = collections.defaultdict(lambda: [0, 0, 0])
    for f in fp:
        row = per_glob[f.matched_glob]
        row[0] += 1
        row[1] += f.size_bytes
        row[2] += f.line_count
    tot_f = sum(r[0] for r in per_glob.values())
    tot_b = sum(r[1] for r in per_glob.values())
    print(f"  first-party: {len(fp)} files, {len(unlabelled)} with no matched_glob, "
          f"per-glob sums to {tot_f} files / {round(tot_b / 1024)} KB")
    dead = [g for g in first_party if g not in per_glob]
    if dead:
        print(f"  first-party globs claiming ZERO files ({len(dead)}): {dead}")

    backslash = [f.relative_path for f in walk.files if "\\" in f.relative_path]
    backslash += [d.relative_path for d in walk.dropped if "\\" in d.relative_path]
    print(f"  paths containing a backslash: {len(backslash)}")
    print()


for corpus in sys.argv[1:] or ["nng", "ctcm"]:
    run(corpus)
