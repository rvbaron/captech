#!/usr/bin/env python3
"""Build the platform-ui dataset from a LegacyLift analysis tree.

THE APPROACH: platform-ui never reads an analysis tree. It reads a COPY.

This script copies the SQLite store and emits the JSON and markdown sidecars
that go with it into ``platform-ui/data/``, and the API serves only from there.
Three reasons, all deliberate:

* **The live store is never opened.** ``knowledge.sqlite`` is copied
  byte-for-byte and read from the copy, so a UI bug, a lock or a stray write can
  never reach Layer 1 -- and on this corpus the source store is the frozen
  379/117 pair that Milestone 1.5 of `active/reqs-to-data-store.md` compares
  against.
* **Only cited line ranges leave the analysis tree.** Snippets are extracted at
  prepare time into ``snippets.json``; whole client files are never copied, so
  the API cannot serve the source tree even by accident.
* **The UI has no dependency on the analysis layout.** It needs a data
  directory, not a workspace, so it runs anywhere that directory is present.

  python platform-ui/tools/prepare_data.py

What it writes, per system, under ``platform-ui/data/<systemId>/``:

  knowledge.sqlite   byte copy of the Layer-1 store, opened read-only
  snippets.json      each citation's line range plus 8 lines of context
  domains.json       copied from the analysis tree
  docs/*.md          ASSESSMENT, PREFLIGHT (current) + BUSINESS_RULES,
                     DATA_OBJECTS (stale, from --stale-docs-root)
  diagrams/*.mmd     architecture, call graph, critical path, data lineage
  TOPOLOGY.html      the map step's own interactive page

plus ``platform-ui/data/projects.json``, the project and system catalog.

``platform-ui/data/`` is gitignored: everything in it derives from a client
codebase and must not reach the remote. Re-run to refresh; it overwrites in
place.

RETARGETING THIS AT ANOTHER ENGAGEMENT: pass ``--analysis-root`` (and
``--stale-docs-root`` if you have pre-store markdown worth showing), and edit the
two constants below -- ``SYSTEMS`` and ``PROJECT`` -- which describe the NNG demo
and nothing else. There is no discovery step; the catalog is declared, not
inferred.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS = REPO_ROOT / "repos" / "nng-app-legacylift-analysis"
# Engagement-specific defaults -- both describe the NNG demo. Override on the
# command line rather than editing them.
#
# BUSINESS_RULES.md and DATA_OBJECTS.md were never re-rendered into the current
# analysis tree; the only copies are in an older checkout that predates the
# requirements store and, on the author's machine, sits outside this repo. They
# are shown with a staleness banner.
# Missing is fine -- the copy is skipped and those pages fall back to an
# honest empty state, so leaving this unset costs two documents, not a
# working dataset.
DEFAULT_STALE_DOCS = (
    Path.home() / "captechdev" / "nng-app-legacylift-analysis" / "analysis"
)

DIAGRAMS = {
    "ARCHITECTURE.mmd": "Architecture",
    "call-graph.mmd": "Call graph",
    "critical-path.mmd": "Critical path",
    "data-lineage.mmd": "Data lineage",
}
DOCS = ("ASSESSMENT.md", "PREFLIGHT.md")
STALE_DOCS = ("BUSINESS_RULES.md", "DATA_OBJECTS.md")
SNIPPET_CONTEXT = 8

EXT_LANG = {
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsp": "xml",
    ".xml": "xml",
    ".sql": "sql",
    ".properties": "properties",
    ".gradle": "groovy",
    ".sh": "bash",
    ".bat": "dos",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".html": "xml",
    ".css": "css",
    ".py": "python",
    ".cs": "csharp",
    ".scpf": "xml",
}


@dataclass
class SystemSpec:
    system_id: str
    label: str
    kind: str


SYSTEMS = [
    SystemSpec("customer.ple.nng.app", "PLE Application", "application"),
    SystemSpec("customer.ple.nng.db.ETSPii", "ETSPii Database", "database"),
]

PROJECT = {
    "projectId": "nng",
    "name": "NNG — Pipeline Location Engine",
    "client": "National Fuel Gas (NNG)",
    "summary": (
        "Legacy Java/J2EE pipeline location engine plus its SQL Server schema. "
        "Analyzed with LegacyLift: preflight, assess, map, tag-domains and "
        "business-rule extraction."
    ),
    "currentStep": "extract-rules",
    "steps": ["preflight", "assess", "tag-domains", "map", "extract-rules", "brief"],
}


def log(msg: str) -> None:
    print(f"  {msg}")


def copy_file(src: Path, dst: Path) -> bool:
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return True


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def read_slice(path: Path, start: int, end: int) -> tuple[int, list[str]] | None:
    """Return (first_line_number, lines) for start..end plus context, or None."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    if not lines:
        return None
    lo = max(1, start - SNIPPET_CONTEXT)
    hi = min(len(lines), end + SNIPPET_CONTEXT)
    if lo > len(lines):
        return None
    return lo, lines[lo - 1 : hi]


def build_snippets(db: sqlite3.Connection, legacy_root: Path) -> dict:
    """Pre-extract only the cited line ranges. Whole client files never leave
    the analysis tree -- see the 'Cited slices only' decision."""
    if not table_exists(db, "gr_citation"):
        return {}
    out: dict[str, dict] = {}
    missing = 0
    for row in db.execute(
        "SELECT citation_id, relative_path, start_line, end_line FROM gr_citation"
    ):
        cid, rel, start, end = row
        src = legacy_root / rel
        got = read_slice(src, start, end)
        if got is None:
            missing += 1
            out[str(cid)] = {
                "citationId": cid,
                "relativePath": rel,
                "startLine": start,
                "endLine": end,
                "available": False,
            }
            continue
        first, lines = got
        out[str(cid)] = {
            "citationId": cid,
            "relativePath": rel,
            "startLine": start,
            "endLine": end,
            "firstLine": first,
            "language": EXT_LANG.get(Path(rel).suffix.lower(), "plaintext"),
            "lines": lines,
            "available": True,
        }
    if missing:
        log(f"! {missing} citation(s) had no readable source file")
    return out


def prepare_system(
    spec: SystemSpec,
    analysis_root: Path,
    legacy_root: Path,
    out_root: Path,
    stale_docs_root: Path | None,
) -> dict:
    src_dir = analysis_root / "analysis" / spec.system_id
    out_dir = out_root / spec.system_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{spec.system_id}]")

    manifest: dict = {
        "systemId": spec.system_id,
        "label": spec.label,
        "kind": spec.kind,
        "hasRequirements": False,
        "requirementCount": 0,
        "docs": [],
        "diagrams": [],
        "topology": False,
        "domains": False,
        "snippetCount": 0,
    }

    for name in DOCS:
        if copy_file(src_dir / name, out_dir / "docs" / name):
            manifest["docs"].append({"name": name, "stale": False})
            log(f"doc  {name}")

    if stale_docs_root is not None:
        for name in STALE_DOCS:
            src = stale_docs_root / spec.system_id / name
            if copy_file(src, out_dir / "docs" / name):
                manifest["docs"].append({"name": name, "stale": True})
                log(f"doc  {name} (stale pre-store copy)")

    for name, label in DIAGRAMS.items():
        if copy_file(src_dir / name, out_dir / "diagrams" / name):
            manifest["diagrams"].append({"name": name, "label": label})
            log(f"mmd  {name}")

    if copy_file(src_dir / "TOPOLOGY.html", out_dir / "TOPOLOGY.html"):
        manifest["topology"] = True
        log("html TOPOLOGY.html")

    if copy_file(src_dir / "domains.json", out_dir / "domains.json"):
        manifest["domains"] = True
        log("json domains.json")

    store_src = src_dir / "knowledge" / "knowledge.sqlite"
    if store_src.is_file():
        store_dst = out_dir / "knowledge.sqlite"
        copy_file(store_src, store_dst)
        size_mb = store_dst.stat().st_size / 1e6
        log(f"db   knowledge.sqlite ({size_mb:.1f} MB)")
        db = sqlite3.connect(f"file:{store_dst}?mode=ro", uri=True)
        try:
            if table_exists(db, "gr"):
                manifest["hasRequirements"] = True
                manifest["requirementCount"] = db.execute(
                    "SELECT count(*) FROM gr"
                ).fetchone()[0]
                snippets = build_snippets(db, legacy_root / spec.system_id)
                manifest["snippetCount"] = sum(
                    1 for s in snippets.values() if s.get("available")
                )
                (out_dir / "snippets.json").write_text(
                    json.dumps(snippets), encoding="utf-8"
                )
                log(
                    f"json snippets.json ({manifest['snippetCount']}"
                    f"/{len(snippets)} citations resolved)"
                )
            else:
                log("-    no gr tables in this store (domains only)")
        finally:
            db.close()
    else:
        log("!    no knowledge.sqlite")

    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--analysis-root",
        type=Path,
        default=DEFAULT_ANALYSIS,
        help="workspace holding analysis/ and legacy/ (default: the NNG tree under repos/)",
    )
    ap.add_argument(
        "--stale-docs-root",
        type=Path,
        default=DEFAULT_STALE_DOCS,
        help=(
            "an older analysis/ directory to take BUSINESS_RULES.md and "
            "DATA_OBJECTS.md from, shown banner-flagged as stale; skipped when "
            "it does not exist"
        ),
    )
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "platform-ui" / "data")
    args = ap.parse_args()

    analysis_root: Path = args.analysis_root
    legacy_root = analysis_root / "legacy"
    if not (analysis_root / "analysis").is_dir():
        print(f"error: no analysis/ under {analysis_root}", file=sys.stderr)
        return 1

    out_root: Path = args.out
    out_root.mkdir(parents=True, exist_ok=True)

    stale_docs_root: Path | None = args.stale_docs_root
    if stale_docs_root is not None and not stale_docs_root.is_dir():
        print(f"note: no stale-doc source at {stale_docs_root}; skipping those two documents")
        stale_docs_root = None

    systems = [
        prepare_system(s, analysis_root, legacy_root, out_root, stale_docs_root)
        for s in SYSTEMS
    ]
    project = dict(PROJECT, systems=systems)
    (out_root / "projects.json").write_text(
        json.dumps({"projects": [project]}, indent=2), encoding="utf-8"
    )
    print(f"\nwrote {out_root / 'projects.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
