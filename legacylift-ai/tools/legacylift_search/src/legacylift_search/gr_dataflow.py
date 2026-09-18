"""Compute `reads[]`/`writes[]` for a requirement from Layer-0 graph data.

Milestone 1 Step 7 of `docs/exec-plans/active/reqs-to-data-store.md`.

**`gr_dataflow` has no writer in Milestone 1, and it ships empty.** Both
paths into the table are deferred, for two independent reasons, and this
module owns only the first of them plus the reporting rule both reasons
force on `requirements stats`:

1. **The computed path** (this module's `compute_dataflow_entries`) reads
   `uses_table` / `executes_sql` graph edges, `has_column` facts and
   `foreign_key` edges for a requirement's cited symbols and turns them into
   `DataflowEntry` rows with `provenance='computed'`. It is real, tested code
   — but it ships **disabled by default** behind `GR_DATAFLOW_COMPUTED_ENABLED`,
   because Milestone 26 of
   `docs/exec-plans/active/semantic-code-search-graph-index.md` has not
   landed. Until it does, `uses_table` edges emit SQL table *aliases*
   (`o`, `c`, `po`) as datastore names and produce confident self-referencing
   edges such as `Orders -> Orders`. Shipping this block enabled before that
   fix would not be merely incomplete, it would be wrong — which breaks
   `NORMATIVE PRINCIPLE-1`'s promise that the computed path is the
   trustworthy one. See `GR_DATAFLOW_COMPUTED_ENABLED`'s docstring for
   exactly what Milestone 26 fixes.

2. **The `llm_inferred` fallback** — recording what the extractor inferred
   where the graph yields *nothing* for a cited symbol — has no writer at
   all in Milestone 1 and this module deliberately does not add one.
   `RULES_SCHEMA` has no reads/writes field yet; that field is added
   alongside the Milestone 26 work, when the computed path it is a fallback
   *for* actually exists (with no graph output there is no *silence* to
   fall back from). It is **deferred, not deleted**: `DataflowEntry` already
   accepts `provenance='llm_inferred'` and this module's shape below is
   built so that adding the fallback later is additive.

   The obvious place that half will slot in: a second function, sibling to
   `compute_dataflow_entries`, named something like
   `dataflow_entries_from_extractor` (taking the extractor's per-rule
   reads/writes plus the set of symbols the computed path already covered,
   so it fires only on graph *silence* per cited symbol, never on
   *disagreement*) — feeding entries with `provenance='llm_inferred'` and a
   populated `explanation` into the same `DataflowEntry` model this module
   already imports. Nothing here should need to change for that function to
   exist; that is the whole point of keeping `compute_dataflow_entries`
   symbol-scoped and side-effect-free.

`dataflow_status_text` is this module's other export, and it is the one
`requirements stats` (Milestone 1 Wave C) must call for this block instead
of computing a rate itself. An earlier draft of this step said the rate
would be "100% for the whole of Milestone 1, by construction", which was
wrong in exactly the way `PR-29`'s discipline warns about: with zero
entries the rate is zero over zero, so a naive implementation either
prints "100% of nothing" or divides by zero. `dataflow_status_text` makes
that structurally impossible in Milestone 1 rather than merely avoided —
see its docstring.
"""

from __future__ import annotations

from typing import Final

from .knowledge_store import KnowledgeStore
from .models import DataflowEntry
from .store import SQLiteStore

__all__ = [
    "GR_DATAFLOW_COMPUTED_ENABLED",
    "compute_dataflow_entries",
    "dataflow_status_text",
]


GR_DATAFLOW_COMPUTED_ENABLED: Final[bool] = False
"""Gates the *computed* `reads[]`/`writes[]` path. Defaults to **off**.

**The one thing that unblocks flipping this to `True` in production is
Milestone 26 of `docs/exec-plans/active/semantic-code-search-graph-index.md`
("`uses_table` data-lineage correctness — alias binding and self-reference
suppression").** Reproduced there against the running grammar: a nine-line
T-SQL fixture yields 10 `uses_table` edges of which 5 are junk — SQL table
*aliases* (`o`, `c`, `po`) emitted as unresolved (`callee_symbol_id IS NULL`,
confidence 0.30) datastore names, and confident (0.85) self-referencing
edges such as `Orders -> Orders`, where an object's own name inside its own
`CREATE` statement is read back as a usage of itself. Milestone 26's
deliverable is alias binding (resolving `o` to the `Orders` it stands for
inside the same `FROM`/`JOIN`) plus self-reference suppression. Until that
lands, turning this flag on would feed the requirements store confidently
wrong table names rather than merely incomplete ones, which is the one
failure mode `NORMATIVE PRINCIPLE-1` (the computed path is the trustworthy
one) cannot tolerate.

Flipping this to `True` once Milestone 26 has landed is meant to be exactly
a one-line change: `compute_dataflow_entries` already runs the join,
provenance-tags every row `'computed'`, and is exercised by
`tests/test_gr_dataflow.py` with the flag forced on via the `enabled=True`
keyword, against fixtures — never against this module constant.
"""

# Edge kinds that mean "this symbol's code touches a datastore directly".
# `uses_table` is the SQL-table-reference case (tree-sitter FROM/JOIN/UPDATE/
# INTO parsing, `graph.py`'s `_edge_kind_from_ref`); `executes_sql` is the
# COBOL EXEC SQL block case. Both are "data-access edges" in Step 7's text;
# `foreign_key` is handled separately below because it never carries a read/
# write verb to key a direction off of.
_DATA_ACCESS_EDGE_KINDS: Final[frozenset[str]] = frozenset(
    {"uses_table", "executes_sql"}
)

# Verbs whose presence in an edge's `evidence` text means the access is a
# write. Anything else (bare SELECT/FROM/JOIN, or no recognizable verb at
# all) defaults to a read, which is the conservative choice: a plain SELECT
# is read-only far more often than any of these five write verbs appear
# without one of them naming themselves in the evidence slice.
_WRITE_VERBS: Final[tuple[str, ...]] = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "UPSERT",
    "TRUNCATE",
)


def _direction_from_evidence(evidence: str) -> str:
    """Classify one data-access edge's evidence text as `'reads'` or `'writes'`.

    Args:
        evidence: The `graph_edges.evidence` slice of source text the edge
            was extracted from.

    Returns:
        `'writes'` if any of `_WRITE_VERBS` appears (case-insensitively) in
        `evidence`, else `'reads'`.
    """
    upper = evidence.upper()
    if any(verb in upper for verb in _WRITE_VERBS):
        return "writes"
    return "reads"


def _cited_anchor_keys(ks: KnowledgeStore, gr_id: str) -> list[str]:
    """All `anchor_key` values a requirement's citations touch.

    Unions `gr_citation.anchor_key` (the primary anchor of each citation,
    guaranteed non-empty by `GRCitation`'s validator) with
    `gr_citation_anchor.anchor_key` (the full resolved set, primary
    included — see that model's docstring), so a citation spanning three
    sibling methods contributes all three rather than only its primary.

    Runs entirely against `knowledge.sqlite` — no cross-database join here;
    that join happens in `compute_dataflow_entries` once these keys are
    looked up against `index.sqlite`'s `symbols` table.

    Args:
        ks: An already-open `KnowledgeStore`.
        gr_id: The requirement to look up citations for.

    Returns:
        Distinct anchor keys, in no particular order. Empty if the
        requirement has no citations (or does not exist).
    """
    conn = ks._connect()
    rows = conn.execute(
        """
        SELECT anchor_key FROM gr_citation WHERE gr_id = ?
        UNION
        SELECT gca.anchor_key
          FROM gr_citation_anchor gca
          JOIN gr_citation gc ON gc.citation_id = gca.citation_id
         WHERE gc.gr_id = ?
        """,
        (gr_id, gr_id),
    ).fetchall()
    return [row[0] for row in rows]


def compute_dataflow_entries(
    ks: KnowledgeStore,
    index_store: SQLiteStore | None,
    gr_id: str,
    *,
    enabled: bool | None = None,
) -> list[DataflowEntry]:
    """Compute a requirement's `reads[]`/`writes[]` from Layer-0 graph data.

    **No language model on this path** — every entry returned is
    `provenance='computed'`, derived deterministically from
    `graph_edges` and `symbol_facts` in `index.sqlite`.

    Because `symbol_facts` and `graph_edges` live in `index.sqlite` while the
    GR tables live in `knowledge.sqlite`, and the two databases are never
    `ATTACH`ed, this is a cross-database read joined in Python — the
    `domains_cmd` pattern (`cli.py`): two separate connections, joined on
    plain Python data structures, never a single cross-database SQL
    statement.

    **Contract on `index_store`: this function never checks for the file's
    existence and never constructs a `SQLiteStore` itself.** That check is
    the *caller's* responsibility, exactly as `SQLiteStore._connect`'s own
    docstring implies by creating the database file on first query: a
    caller that wants "no index.sqlite" to mean "no computed entries" must
    call `Path.exists()` on the sqlite path *before* constructing a
    `SQLiteStore`, and pass `None` here when it is absent. Passing `None`
    is a no-op that touches no filesystem path at all — it is not merely
    "safe", it is required for that guarantee to hold.

    The algorithm, once a match against `index.sqlite`'s `symbols` table
    exists for at least one of the requirement's cited anchors:

    * **Data-access edges** (`graph_edges` with `edge_kind` in
      `('uses_table', 'executes_sql')`, `caller_symbol_id` one of the cited
      symbols) become a table-grain entry (`column=''`) per edge. Direction
      comes from `_direction_from_evidence` on the edge's evidence text.
      The datastore name prefers the resolved callee symbol's
      `qualified_name` over the raw `callee_name` — the raw name is exactly
      what Milestone 26 fixes for unresolved SQL table aliases, so preferring
      the resolved name is the one piece of that fix this function can take
      advantage of without waiting on it, while `GR_DATAFLOW_COMPUTED_ENABLED`
      still keeps the whole block off until the rest of that milestone lands.
    * **`foreign_key` edges** (same caller set) become a `'reads'`,
      table-grain entry per edge: a foreign key is a referential dependency
      on the table it points at, never a write, and `graph_edges` carries no
      column-level detail for it (the extractor only ever resolves the
      *referenced table*, never the referencing column — see
      `extractors.py`'s SQL foreign-key regex supplement), so `column` stays
      `''`.
    * **`has_column` facts** (`symbol_facts` with `subject_symbol_id` one of
      the cited symbols) mean the cited symbol *is itself a table*: each
      fact becomes a `'reads'`, column-grain entry naming that symbol's own
      `qualified_name` as the datastore and the fact's `object` as the
      column — documenting the table's own schema as data the citing
      requirement depends on.

    Entries are deduplicated on `(direction, datastore, column)` before
    being returned, matching `gr_dataflow`'s own `UNIQUE` constraint.

    Args:
        ks: An already-open `KnowledgeStore` holding the requirement's
            citations.
        index_store: An already-open `SQLiteStore` over `index.sqlite`, or
            `None` when that database does not exist (see the contract
            above).
        gr_id: The requirement to compute data flow for.
        enabled: Overrides `GR_DATAFLOW_COMPUTED_ENABLED` for this call.
            `None` (the default) reads the module flag, so a production
            call site that never passes this keyword picks up the flag's
            current value automatically — flipping the constant is the
            "one-line change" `GR_DATAFLOW_COMPUTED_ENABLED` promises.
            Tests pass `enabled=True` to force the path on against fixtures
            without touching the module-level default other tests share.

    Returns:
        `DataflowEntry` instances with `gr_id` set to the given `gr_id` and
        `provenance='computed'`. Empty when the flag (module default or
        this call's override) is off, when `index_store` is `None`, when
        the requirement has no citations, or when none of its cited anchors
        resolve to a symbol in `index.sqlite`.
    """
    if enabled is None:
        enabled = GR_DATAFLOW_COMPUTED_ENABLED
    if not enabled:
        return []
    if index_store is None:
        return []

    anchor_keys = _cited_anchor_keys(ks, gr_id)
    if not anchor_keys:
        return []

    conn = index_store.connection()
    placeholders = ",".join("?" * len(anchor_keys))
    symbol_rows = conn.execute(
        f"SELECT id, qualified_name FROM symbols WHERE anchor_key IN ({placeholders})",
        anchor_keys,
    ).fetchall()
    if not symbol_rows:
        return []

    symbol_ids = [row[0] for row in symbol_rows]
    qualified_name_by_id = {row[0]: row[1] for row in symbol_rows}

    entries: list[DataflowEntry] = []
    seen: set[tuple[str, str, str]] = set()

    def _add(direction: str, datastore: str, column: str = "") -> None:
        key = (direction, datastore, column)
        if key in seen:
            return
        seen.add(key)
        entries.append(
            DataflowEntry(
                gr_id=gr_id,
                direction=direction,
                datastore=datastore,
                column=column,
                provenance="computed",
            )
        )

    id_placeholders = ",".join("?" * len(symbol_ids))

    edge_rows = conn.execute(
        f"""
        SELECT callee_symbol_id, callee_name, edge_kind, evidence
          FROM graph_edges
         WHERE caller_symbol_id IN ({id_placeholders})
           AND edge_kind IN ('uses_table', 'executes_sql', 'foreign_key')
        """,
        symbol_ids,
    ).fetchall()

    callee_ids = {row[0] for row in edge_rows if row[0] is not None}
    callee_qualified_name_by_id: dict[str, str] = {}
    if callee_ids:
        callee_placeholders = ",".join("?" * len(callee_ids))
        callee_rows = conn.execute(
            f"SELECT id, qualified_name FROM symbols WHERE id IN ({callee_placeholders})",
            list(callee_ids),
        ).fetchall()
        callee_qualified_name_by_id = {row[0]: row[1] for row in callee_rows}

    for callee_symbol_id, callee_name, edge_kind, evidence in edge_rows:
        datastore = callee_qualified_name_by_id.get(callee_symbol_id, callee_name)
        if edge_kind == "foreign_key":
            _add("reads", datastore, "")
        else:
            _add(_direction_from_evidence(evidence), datastore, "")

    fact_rows = conn.execute(
        f"""
        SELECT subject_symbol_id, object
          FROM symbol_facts
         WHERE subject_symbol_id IN ({id_placeholders})
           AND predicate = 'has_column'
        """,
        symbol_ids,
    ).fetchall()

    for subject_symbol_id, column_name in fact_rows:
        table_name = qualified_name_by_id[subject_symbol_id]
        _add("reads", table_name, column_name or "")

    return entries


def dataflow_status_text(*, total: int, computed: int, llm_inferred: int) -> str:
    """The words `requirements stats` prints for the data-flow block.

    Exists so Wave C's `stats` command has exactly one thing to call for
    this block and structurally **cannot** compute `computed / total` (or
    any other ratio) itself for an empty table — the `PR-29` discipline
    applied to reporting, a fourth time: an absent measurement and a
    measured value must never share an encoding, and a percentage over an
    empty set is that mistake's purest form.

    Args:
        total: `COUNT(*) FROM gr_dataflow` for the requirement (or corpus)
            being reported on.
        computed: Of those, how many carry `provenance='computed'`.
        llm_inferred: Of those, how many carry `provenance='llm_inferred'`.

    Returns:
        In Milestone 1, always the fixed sentence naming both deferred
        reasons — because `total` is always `0`: neither writer exists yet
        (see this module's docstring). `computed` and `llm_inferred` are
        accepted now, unused, so this function's signature does not need to
        change the day a later milestone adds a real writer; that milestone
        is the one that earns the right to turn a non-zero `total` into a
        reported figure, and — deliberately — it is not implemented here.

    A non-zero `total` cannot happen in Milestone 1 — neither writer exists
    — so it is reported as the anomaly it is, with **counts and never a
    rate**. This function contains no division at any total, which is what
    makes the no-rate guarantee structural rather than a matter of taking the
    right branch.

    It deliberately does **not** raise on that state, though an earlier form
    did. `requirements stats` is a read-only reporting command and is where
    Step 10's three mandatory measurements are read from; raising out of it
    for a *data* condition would cost the operator every other figure in the
    report — the state counts, the SME fill rates, the intra-run collapse
    rate, the anchor-resolution breakdown — to describe one empty table.
    That is the same degrade-loudly-rather-than-fail choice ingest makes when
    no embedder is reachable, and the anomaly is still impossible to miss.
    """
    if total == 0:
        return (
            "no data-flow entries: computed path disabled pending M26, "
            "extractor source not yet added"
        )
    return (
        f"UNEXPECTED: {total} data-flow entries present "
        f"({computed} computed, {llm_inferred} model-inferred), but this "
        "milestone has no writer for them — the computed path is gated "
        "behind GR_DATAFLOW_COMPUTED_ENABLED pending M26 and the "
        "llm_inferred fallback has no extractor source. Investigate how they "
        "were written; no rate is reported for them, because the reporting "
        "rule for a non-empty table belongs to the milestone that adds a "
        "writer."
    )
