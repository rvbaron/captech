"""Tests for Milestone 8 of `domain-enhancements-plan.md`: the
`render-architecture` command and its `render_architecture_mermaid` renderer.

Milestone 8 acceptance has three parts:

(1) SQLite source: `tag-domains` a fixture `domains.json` (2 domains, 1
    edge), then `render-architecture --repo-root $REPO --output -` renders
    Mermaid containing both nodes + the edge; re-running is byte-identical.
(2) `domains.json` source (the assess-time path, run against an index that
    has NEVER been `tag-domains`-ed, i.e. no knowledge.sqlite at all):
    `render-architecture --repo-root $REPO --domains <path> --output -`
    produces the byte-identical SAME Mermaid as (1) — proving the renderer
    is a single, source-independent code path. Two sub-cases prove the
    normalization logic (issue #36): a DUPLICATE edge in the JSON must not
    break byte-identity (issue #56 dedup), and an edge naming a domain that
    is not itself listed must be dropped from both sources alike (phantom
    node guard).
(3) `modernize-assess.md` Step 6 no longer instructs a hand-authored
    `ARCHITECTURE.mmd` and instead shells out to `render-architecture`.

Unit-level tests below also exercise `render_architecture_mermaid` and
`domains_file_to_records` directly: the reserved `unassigned` exclusion, the
phantom-edge drop, the Shared/Core cross-cutting node shape, and
deterministic ordering independent of input order.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from legacylift_search.cli import app
from legacylift_search.config import Manifest, resolve_knowledge_dir
from legacylift_search.domain_tagger import (
    DomainEdgeInput,
    DomainsFile,
    domains_file_to_records,
    render_architecture_mermaid,
)
from legacylift_search.indexer import Indexer
from legacylift_search.models import DomainEdgeRecord, DomainRecord

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"
BASE_DOMAINS_JSON = FIXTURE / "domains.fixture.json"


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------


def _copy_fixture(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)
    return dest


def _build_index(repo: Path) -> None:
    manifest = Manifest()
    manifest.embedding.provider = "hash"
    manifest.embedding.dimension = 64
    Indexer(manifest, repo).run(reset=True, embedding_provider_override="hash")


def _knowledge_path(repo: Path) -> Path:
    return resolve_knowledge_dir(repo, Manifest()) / "knowledge.sqlite"


def _write_domains_json(path: Path, extra_edges: list[dict] | None = None) -> Path:
    """A copy of the base 2-domain/1-edge fixture, optionally with extra
    (already-JSON-shaped) edge dicts appended to the `edges` array."""
    data = json.loads(BASE_DOMAINS_JSON.read_text(encoding="utf-8"))
    if extra_edges:
        data["edges"].extend(extra_edges)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------
# render_architecture_mermaid (unit)
# ---------------------------------------------------------------------


def test_render_basic_nodes_and_edge():
    domains = [
        DomainRecord(
            domain_id="core-services",
            name="Core Services",
            path_globs=["src/**"],
            display_order=0,
        ),
        DomainRecord(
            domain_id="data-layer",
            name="Data Layer",
            path_globs=["database/**"],
            display_order=1,
        ),
    ]
    edges = [
        DomainEdgeRecord(from_domain="core-services", to_domain="data-layer", kind="reads")
    ]
    out = render_architecture_mermaid(domains, edges)
    assert out.startswith("graph TD\n")
    assert 'core-services["Core Services"]' in out
    assert 'data-layer["Data Layer"]' in out
    assert "core-services -->|reads| data-layer" in out


def test_render_excludes_reserved_unassigned():
    """Belt-and-suspenders (issue #28): an `unassigned` domain/edge is
    excluded even though neither real source is ever expected to carry one."""
    domains = [
        DomainRecord(domain_id="a", name="A", path_globs=["src/**"], display_order=0),
        DomainRecord(
            domain_id="unassigned", name="Unassigned", path_globs=[], display_order=1
        ),
    ]
    edges = [DomainEdgeRecord(from_domain="a", to_domain="unassigned", kind="")]
    out = render_architecture_mermaid(domains, edges)
    assert "unassigned" not in out
    assert 'a["A"]' in out
    # The edge touching the excluded node must also be dropped.
    assert "-->" not in out


def test_render_drops_edges_to_unlisted_domain():
    """issue #36: an edge whose endpoint is not among the emitted nodes must
    be dropped, not auto-create a phantom Mermaid node."""
    domains = [
        DomainRecord(domain_id="a", name="A", path_globs=["src/**"], display_order=0),
    ]
    edges = [
        DomainEdgeRecord(from_domain="a", to_domain="ghost", kind="calls"),
        DomainEdgeRecord(from_domain="ghost", to_domain="a", kind="calls"),
    ]
    out = render_architecture_mermaid(domains, edges)
    assert "ghost" not in out
    assert "-->" not in out


def test_render_shared_core_distinct_shape():
    """issue #20: reserved slug {"shared","core"} renders as a cross-cutting
    (stadium-shaped) node; ordinary domains use the plain rectangle shape."""
    domains = [
        DomainRecord(domain_id="a", name="A", path_globs=["src/**"], display_order=0),
        DomainRecord(
            domain_id="shared", name="Shared", path_globs=["lib/**"], display_order=1
        ),
    ]
    out = render_architecture_mermaid(domains, [])
    assert 'a["A"]' in out
    assert 'shared(["Shared"])' in out


def test_render_no_shared_core_nothing_special():
    domains = [
        DomainRecord(domain_id="a", name="A", path_globs=["src/**"], display_order=0),
        DomainRecord(domain_id="b", name="B", path_globs=["lib/**"], display_order=1),
    ]
    out = render_architecture_mermaid(domains, [])
    assert 'a["A"]' in out
    assert 'b["B"]' in out
    assert "((" not in out


def test_render_deterministic_ordering_independent_of_input_order():
    """Sort is by (display_order, domain_id) for nodes and lexical for edges
    (issue #14 analogue) — shuffling the input lists must not change output."""
    domains_a = [
        DomainRecord(domain_id="b", name="B", path_globs=["b/**"], display_order=1),
        DomainRecord(domain_id="a", name="A", path_globs=["a/**"], display_order=0),
    ]
    domains_b = list(reversed(domains_a))
    edges_a = [
        DomainEdgeRecord(from_domain="b", to_domain="a", kind="z"),
        DomainEdgeRecord(from_domain="a", to_domain="b", kind="y"),
    ]
    edges_b = list(reversed(edges_a))
    assert render_architecture_mermaid(domains_a, edges_a) == render_architecture_mermaid(
        domains_b, edges_b
    )


# ---------------------------------------------------------------------
# domains_file_to_records (unit)
# ---------------------------------------------------------------------


def test_domains_file_to_records_assigns_display_order_from_array_index():
    df = DomainsFile.model_validate(
        {
            "schema_version": 1,
            "domains": [
                {"domain_id": "z", "name": "Z", "path_globs": ["z/**"]},
                {"domain_id": "a", "name": "A", "path_globs": ["a/**"]},
            ],
            "edges": [],
        }
    )
    domains, _edges = domains_file_to_records(df)
    assert [d.domain_id for d in domains] == ["z", "a"]
    assert [d.display_order for d in domains] == [0, 1]


def test_domains_file_to_records_dedups_edges_on_from_to_kind():
    df = DomainsFile(
        schema_version=1,
        domains=[
            DomainRecord(domain_id="a", name="A", path_globs=["a/**"]),
            DomainRecord(domain_id="b", name="B", path_globs=["b/**"]),
        ],
        edges=[
            DomainEdgeInput(**{"from": "a", "to": "b", "kind": "calls"}),
            DomainEdgeInput(**{"from": "a", "to": "b", "kind": "calls"}),
            DomainEdgeInput(**{"from": "a", "to": "b", "kind": "reads"}),
        ],
    )
    _domains, edges = domains_file_to_records(df)
    assert len(edges) == 2
    keys = sorted((e.from_domain, e.to_domain, e.kind) for e in edges)
    assert keys == [("a", "b", "calls"), ("a", "b", "reads")]


# ---------------------------------------------------------------------
# CLI acceptance: both sources, byte-identical
# ---------------------------------------------------------------------


def test_render_architecture_sqlite_source_cli(tmp_path: Path):
    """Acceptance (1): tag-domains the fixture, then render from SQLite."""
    repo = _copy_fixture(tmp_path)
    _build_index(repo)
    runner = CliRunner()

    tag_result = runner.invoke(
        app,
        ["tag-domains", "--repo-root", str(repo), "--domains", str(BASE_DOMAINS_JSON)],
    )
    assert tag_result.exit_code == 0, tag_result.output

    result = runner.invoke(
        app, ["render-architecture", "--repo-root", str(repo), "--output", "-"]
    )
    assert result.exit_code == 0, result.output
    assert 'core-services["Core Services"]' in result.output
    assert 'data-layer["Data Layer"]' in result.output
    assert "core-services -->|reads| data-layer" in result.output

    # Re-running is byte-identical.
    result2 = runner.invoke(
        app, ["render-architecture", "--repo-root", str(repo), "--output", "-"]
    )
    assert result2.exit_code == 0, result2.output
    # stdout, not the mixed .output: the resolved-path banner (Milestone 0 of
    # reqs-to-data-store.md) prints the resolved knowledge directory to
    # stderr on every run, and .output mixes stdout+stderr.
    assert result2.stdout == result.stdout


def test_render_architecture_domains_json_source_matches_sqlite(tmp_path: Path):
    """Acceptance (2): the --domains source, run BEFORE any tag-domains
    (empty SQLite — `index` has run, per Milestone 1, so knowledge.sqlite
    exists, but its `domains` table is empty because tag-domains has not),
    must produce byte-identical output to the SQLite source in acceptance
    (1)."""
    import sqlite3

    repo = _copy_fixture(tmp_path)
    _build_index(repo)
    runner = CliRunner()

    # `index` (Milestone 1) already created knowledge.sqlite, but tag-domains
    # has not run yet, so its domains table is empty ("empty SQLite").
    kp = _knowledge_path(repo)
    assert kp.exists()
    conn = sqlite3.connect(str(kp))
    try:
        assert conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0] == 0
    finally:
        conn.close()

    json_result = runner.invoke(
        app,
        [
            "render-architecture",
            "--repo-root",
            str(repo),
            "--domains",
            str(BASE_DOMAINS_JSON),
            "--output",
            "-",
        ],
    )
    assert json_result.exit_code == 0, json_result.output

    # The --domains path never wrote to the knowledge DB (still empty).
    conn = sqlite3.connect(str(kp))
    try:
        assert conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0] == 0
    finally:
        conn.close()

    tag_result = runner.invoke(
        app,
        ["tag-domains", "--repo-root", str(repo), "--domains", str(BASE_DOMAINS_JSON)],
    )
    assert tag_result.exit_code == 0, tag_result.output

    sqlite_result = runner.invoke(
        app, ["render-architecture", "--repo-root", str(repo), "--output", "-"]
    )
    assert sqlite_result.exit_code == 0, sqlite_result.output

    # stdout, not the mixed .output: the --domains source never resolves the
    # knowledge directory (no banner), while the SQLite source does (a
    # stderr-only banner line) — the two sources' STDOUT stays identical,
    # which is the actual invariant this test proves.
    assert json_result.stdout == sqlite_result.stdout


def test_render_architecture_domains_json_omitting_repo_root(tmp_path: Path):
    """issue #27: --repo-root is optional/unused when --domains is given."""
    repo = _copy_fixture(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["render-architecture", "--domains", str(BASE_DOMAINS_JSON), "--output", "-"],
    )
    assert result.exit_code == 0, result.output
    assert 'core-services["Core Services"]' in result.output


def test_render_architecture_both_absent_errors():
    runner = CliRunner()
    result = runner.invoke(app, ["render-architecture", "--output", "-"])
    assert result.exit_code == 1, result.output


def test_render_architecture_missing_knowledge_store_errors(tmp_path: Path):
    """issue #33/#50: a repo where `index` has never even been run (so the
    knowledge dir was never created at all) must error, not silently
    materialize an empty knowledge.sqlite and render an empty diagram."""
    repo = _copy_fixture(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app, ["render-architecture", "--repo-root", str(repo), "--output", "-"]
    )
    assert result.exit_code == 1, result.output
    assert "run `tag-domains` first" in result.output
    assert not _knowledge_path(repo).exists()


def test_render_architecture_duplicate_edge_stays_byte_identical(tmp_path: Path):
    """issue #56: a duplicated edge in domains.json must not break
    byte-identity — ingest collapses the duplicate on the (from,to,kind)
    PRIMARY KEY, and the --domains renderer must dedup the same way."""
    repo = _copy_fixture(tmp_path)
    _build_index(repo)
    runner = CliRunner()

    dup_json = _write_domains_json(
        tmp_path / "dup_domains.json",
        extra_edges=[
            {"from": "core-services", "to": "data-layer", "kind": "reads"},
        ],
    )

    json_result = runner.invoke(
        app,
        [
            "render-architecture",
            "--repo-root",
            str(repo),
            "--domains",
            str(dup_json),
            "--output",
            "-",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    # Only ONE arrow, despite the duplicate edge in the source JSON.
    assert json_result.output.count("core-services -->|reads| data-layer") == 1

    tag_result = runner.invoke(
        app, ["tag-domains", "--repo-root", str(repo), "--domains", str(dup_json)]
    )
    assert tag_result.exit_code == 0, tag_result.output

    sqlite_result = runner.invoke(
        app, ["render-architecture", "--repo-root", str(repo), "--output", "-"]
    )
    assert sqlite_result.exit_code == 0, sqlite_result.output

    # stdout, not the mixed .output: see the byte-identity comment above.
    assert json_result.stdout == sqlite_result.stdout


def test_render_architecture_phantom_edge_dropped_both_sources(tmp_path: Path):
    """issue #36: an edge naming a domain absent from the domains list must
    be dropped from the diagram on BOTH sources, staying byte-identical."""
    repo = _copy_fixture(tmp_path)
    _build_index(repo)
    runner = CliRunner()

    phantom_json = _write_domains_json(
        tmp_path / "phantom_domains.json",
        extra_edges=[
            {"from": "data-layer", "to": "ghost-domain", "kind": "notifies"},
        ],
    )

    json_result = runner.invoke(
        app,
        [
            "render-architecture",
            "--repo-root",
            str(repo),
            "--domains",
            str(phantom_json),
            "--output",
            "-",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    assert "ghost-domain" not in json_result.output
    assert "notifies" not in json_result.output

    tag_result = runner.invoke(
        app, ["tag-domains", "--repo-root", str(repo), "--domains", str(phantom_json)]
    )
    assert tag_result.exit_code == 0, tag_result.output

    sqlite_result = runner.invoke(
        app, ["render-architecture", "--repo-root", str(repo), "--output", "-"]
    )
    assert sqlite_result.exit_code == 0, sqlite_result.output
    assert "ghost-domain" not in sqlite_result.output

    # stdout, not the mixed .output: see the byte-identity comment above.
    assert json_result.stdout == sqlite_result.stdout


def test_render_architecture_output_file(tmp_path: Path):
    repo = _copy_fixture(tmp_path)
    _build_index(repo)
    runner = CliRunner()
    out_path = tmp_path / "ARCHITECTURE.mmd"

    result = runner.invoke(
        app,
        [
            "render-architecture",
            "--repo-root",
            str(repo),
            "--domains",
            str(BASE_DOMAINS_JSON),
            "--output",
            str(out_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("graph TD\n")
    assert 'core-services["Core Services"]' in text


# ---------------------------------------------------------------------
# assess skill no longer hand-authors ARCHITECTURE.mmd (acceptance 3)
# ---------------------------------------------------------------------


def test_modernize_assess_shells_out_to_render_architecture():
    skill_path = (
        Path(__file__).resolve().parents[3]
        / ".claude"
        / "skills"
        / "code-modernization"
        / "commands"
        / "modernize-assess.md"
    )
    text = skill_path.read_text(encoding="utf-8")
    assert "Mermaid domain\ndependency diagram from the legacy-analyst" not in text
    assert "render-architecture --domains" in text
    assert "--output \"analysis/$1/ARCHITECTURE.mmd\"" in text
