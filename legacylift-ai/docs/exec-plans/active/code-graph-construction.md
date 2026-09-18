# How legacylift-search Builds the Code Graph

> Reference explanation of how the `legacylift-search` code graph is constructed today,
> from a read of the implementation on 2026-07-13, **updated 2026-08-05** after Milestones
> 22–25 (type-hierarchy edges, annotation/SQL/type-ref extraction, the `symbol_facts` store)
> and domain tagging landed. Companion to the governing plan
> [`semantic-code-search-graph-index.md`](./semantic-code-search-graph-index.md).
> The code is the source of truth; this is orientation.

## 0. The one thing to get right first

**The code graph is NOT built from the chunks.** Chunking and the graph are two independent
consumers of tree-sitter over the same source files. Chunking (Chonkie, `prefer_ast_boundaries`)
produces retrieval payloads for embedding/FTS; the graph comes from a *separate* symbol/reference
extraction pass. They share source files, not parse output.

Pipeline (`indexer.py`, `Indexer` docstring): `discovery → extract → chunk → persist (SQLite)
→ graph → embed → persist (Chroma) → metadata`.

Domain tagging is a **separate later pass** over the built index, not part of this pipeline —
see §5.

## 1. Per-file extraction → nodes, raw (unresolved) edges, and facts

`SymbolExtractor.extract()` (`extractors.py`) parses each file with tree-sitter, then
`_walk_tree` does a depth-first descent emitting **three** things (it returns
`(symbols, refs, facts)`), driven by the per-language JSON profiles in
`profiles/extractors.json`:

- **Symbols** (node candidates) — any node whose type ∈ `definition_node_kinds`. Emits a
  `Symbol` with `id = lang:path:qualified_name:line`, `kind` = the raw tree-sitter node type
  (`class_declaration`, `method_declaration`, …), and a `qualified_name` built from a
  **container stack** tracked during descent.
- **Refs** (edge candidates, still unresolved) — any node whose type ∈ `call_node_kinds`,
  **plus** the relational refs added by M22/M23/M25: inheritance clauses
  (`inheritance_node_kinds` → `extends`/`implements`/`inherits_or_implements`),
  `@JoinColumn`/`@ManyToOne`-style annotations (`foreign_key`/`associates`), and
  field/property/parameter/return types (`has_field_of_type`/`accepts_dto`/`returns_dto`).
  Each emits a `SymbolRef` capturing the target **name as text**, the **enclosing symbol**,
  the **evidence** line, and range.
- **Facts** (M23–25) — `SymbolFact` records for things that have no target symbol, so they
  cannot be edges: annotations/attributes/decorators, SQL column definitions, Java `throws`
  clauses, enum members. See §4.

Both the inheritance and the annotation/fact handlers fire on the **same definition-node
visit** that produced the `Symbol`, so a fact's `subject_symbol_id` reuses that symbol's
exact `.id` verbatim rather than recomputing it.

Parser loading is layered (`_get_parser_for`): the live path is
`tree_sitter_language_pack.get_language(name)` wrapped in a real `tree_sitter.Parser`
(pack **1.8.1** + tree-sitter **0.25.2**); a per-language-package tier exists as fallback but is
currently uninstalled/inert; and if no parser loads (COBOL always; parse failure; empty parse),
a **regex fallback** produces symbols (`kind="fallback_definition"`) and refs
(`kind="fallback_call"`) from the profile's regex patterns — including a third split-emit loop
for the `inheritance` fallback patterns. A hybrid path supplements tree-sitter refs with regex
definitions when a grammar's def-node names diverge (SQL), and SQL foreign keys specifically
come from a **regex supplement** because tree-sitter mis-parses the FK clause to `ERROR`.

At this stage **refs are just names** — no target resolved yet.

## 2. Repo-wide resolution → the graph

The graph step runs *after every file is extracted*, because resolving a ref needs a repo-wide
view. In `indexer.py`:

1. Build `all_symbols_by_name` — a dict keyed by **both plain and qualified name** → list of
   `Symbol`, over the **union of changed + unchanged** files.
2. Call `GraphBuilder.build_edges` per file (`graph.py`). For each ref:
   - **Caller** = `ref.enclosing_symbol_id`, else the nearest symbol whose line range contains
     the ref (`_resolve_caller`).
   - **Callee** = name lookup in `all_symbols_by_name`, with **confidence encoding ambiguity**
     (`_resolve_callee`, which returns `(id, confidence, callee_kind)`): exactly one match →
     **0.85**; multiple same-language (prefer same file) → **0.70**; cross-language ambiguous →
     unresolved **0.40**; zero matches → unresolved **0.30** but the edge is **kept**, with
     `callee_name` preserved for later refinement (the "preserve unresolved edges" design
     decision).
   - **edge_kind** = `_edge_kind_from_ref` maps the raw `ref.kind`/evidence/language to a
     semantic kind (see below).

**Edge kinds emitted today** (`_edge_kind_from_ref`, `graph.py:207–313`):

| Family | Kinds | Source |
|---|---|---|
| Call/reference | `calls`, `imports`, `references` | original |
| Data access | `uses_table`, `uses_column` | original + SQL |
| Mainframe | `performs`, `executes_sql`, `executes_cics` | COBOL |
| XML frameworks | `maps_to`, `associates`, `instantiates`, `invokes_subflow`, `transitions_to` | Hibernate/Spring/WebFlow |
| **Type hierarchy** | **`inherits`, `implements`** | **M22** |
| **Annotation-relational** | **`foreign_key`, `associates`** | **M23** |
| **Type references** | **`has_field_of_type`, `accepts_dto`, `returns_dto`** | **M25** |

C# `base_list` is inherently ambiguous (a base class and an interface look identical), so
`inherits_or_implements` is reclassified from the *resolved target's* `callee_kind` —
`interface_declaration` → `implements`, any other resolved kind → `inherits`, and unresolved
external bases fall back to the `^I[A-Z]` .NET interface-naming heuristic at confidence 0.30.

**Silent-default hazard:** the function's fallthrough is `return "references"`, so a new ref
kind without an explicit branch still produces an edge — just mislabeled. Edge *totals* rise
exactly as expected while the typed deliverable goes missing. Any new ref kind needs its own
branch, and validation must assert **per-`edge_kind`** counts, never just the total.

So the graph is a **name-resolution graph, not a type-resolved one**: string-name matching
against the symbol table, with the confidence score standing in for the type resolution it
deliberately does not attempt (no overload resolution, no generics, no import-scope tracking).

## 3. Persist + incrementality

Edges are deduped by id and written via `store.upsert_edges` into the `graph_edges` SQLite table.
On reindex the graph is rebuilt over the **union** of changed + unchanged refs — edges for the
rebuild set are deleted then regenerated — because a previously-unresolved edge can now resolve
to a symbol in a changed file, or vice versa. Queried at runtime via `callers`/`callees`
(`store.py`), with an optional repeatable `--edge-kind` filter (M25) so a call-graph query is
not flooded by the type-association and hierarchy kinds.

Note `depth` on `callers`/`callees` is currently a **no-op** — both issue a single
non-recursive `SELECT` and return direct neighbours only.

## 4. Facts — the `symbol_facts` store (M23–25)

Attribute-shaped claims have a *subject* and a *value* but **no target symbol**, so they don't
fit `graph_edges`. They go to a deliberately fact-graph-shaped table
(`symbol_facts`, `store.py:346`): `subject_symbol_id` (NOT NULL FK to `symbols`), `predicate`,
`object`, `attributes` (JSON), `evidence`, `confidence`, `relative_path`, `start_line`,
`language`. Queried via the `facts --predicate <p>` / `facts --symbol <id>` CLI command.

**The 12 predicates emitted today:**

| Group | Predicates | Derived from |
|---|---|---|
| HTTP/API | `http_method`, `exposes_endpoint` | `[HttpGet]`, `@GetMapping`, `@app.get`, Nest `@Get` |
| Security | `requires_auth` | `[Authorize]`, `@PreAuthorize`, `@UseGuards` |
| Validation | `is_required`, `max_length` | `[Required]`, `@NotNull`, `@Size`, `[StringLength]` |
| Persistence mapping | `table_name`, `is_column`, `is_id` | `[Table]`/`@Entity`, `[Column]`, `[Key]`/`@Id` |
| SQL DDL | `has_column` (+ `data_type`/`nullable`/`primary_key`/`unique` attributes) | `column_definition` nodes |
| Behavior | `throws`, `has_enum_value` | Java `throws`, enum members |
| Catch-all | `has_annotation` | any annotation with no mapped intent |

Intent routing is per-language via each profile's `annotation_semantics` map (name → intent),
so adding a framework is a JSON edit, not code. **All facts carry `confidence = 1.0`** — they
are read directly off AST nodes, not inferred. Fact `id` is
`fact:<subject_symbol_id>:<predicate>:<object>:<start_line>`; the `object` is load-bearing
because several predicates are multi-valued on one line (`throws A, B`, single-line enums).

Facts are written during the extract phase only and never participate in the graph rebuild;
M15 incremental correctness comes from the `file_id` FK cascading off the `upsert_files`
`INSERT OR REPLACE`.

## 5. Domain tagging — a third pass over the built index

Capability domains are **not** derived by this tool. They are authored by
`modernize-assess` into a `domains.json` and ingested by a separate `tag-domains` pass, so the
index carries top-down, grouped, edge-verified domains rather than a bottom-up namespace guess:

```
Pass 1  index         chunk + embed + symbols + graph + facts   (no domains yet)
Pass 2  assess        consumes the index -> domains.json (globs + inter-domain edges)
Pass 3  tag-domains   join file -> domain, stamp Chroma metadata   <- no re-embed
```

Domain rows live in a **separate `knowledge.sqlite`** (outside the index dir, so clearing
`analysis/` does *not* clear domain tagging): `domains` (authored catalog), `domain_edges`
(authored inter-domain dependencies), `file_domains` (one primary domain per file), and
`domain_exclusions` (authored "not a business capability" globs). `tag-domains` is the single
idempotent reconcile point for all of them.

Two reserved `file_domains.domain` values are never `domains` rows: **`unassigned`** (matched
no glob — a real coverage gap) and **`excluded`** (matched an `exclude_globs` pattern — tests,
ops scripts, generated code; dropped from the coverage denominator so coverage% is honest).

Tagging is a **metadata write, never a re-embed** — embeddings are computed over `chunk.text`
only. It stamps each chunk's Chroma `domain` key, which enables `where={"domain": …}` filtered
vector search behind `search --domain`. The lexical arm filters to in-domain paths and
**re-enumerates ranks densely before RRF**, so an in-domain hit at global rank 150 gets the
weight its in-domain position deserves. Surfaced by the `domains` and `render-architecture`
commands.

**Two independent freshness axes:** the index is deterministically fresh
(`source_set_sha256`); domain tags are not — they go stale when files are added or move
between domains, so "fresh index, stale domains" is a distinct reported state.

## 6. Caveats to keep in mind

- **Confidence is about name-ambiguity, not correctness.** A 0.85 edge means "one symbol had
  this name," not "this call provably targets that symbol." Unresolved (0.30) edges are
  external/framework targets kept as leads, not errors.
- **Symbol IDs embed the start line** (`lang:path:qualified_name:line`), so any edit *above* a
  symbol changes its ID. IDs are stable within a snapshot, **not** across edits — they are not
  a durable cross-document entity identity.
- **Symbol `kind` is syntactic, never semantic.** It is the raw tree-sitter node type; nothing
  in the package maps `class_declaration` → `controller`/`service`/`dto`. M23 facts give you
  the *evidence* to derive that (an `exposes_endpoint` fact effectively marks an endpoint) but
  the typing itself is not assigned.
- **Facts are deterministic-only by design.** Every predicate above is read off an AST node.
  Anything needing interpretation — a business rule, a state transition, a cardinality
  judgment — is out of scope for this layer and stays with an LLM-driven skill.
- **Language coverage is 7 profiles + XML** (C#, Java, Python, JS, TS, COBOL, SQL). Outside
  those, extraction degrades to regex or produces nothing.
- **`depth` is not implemented** on `callers`/`callees` (direct neighbours only), and if it
  ever becomes a recursive traversal the `--edge-kind` predicate must be applied at *every*
  hop or filtered queries will re-pollute one hop deep.

## Related documents

- [`semantic-code-search-graph-index.md`](./semantic-code-search-graph-index.md) — the governing
  plan; M22–25 (shipped) extended extraction to the first-class nodes the profiles used to ignore.
- [`../pending/fact-graph-decision.md`](../pending/fact-graph-decision.md) §2a/§5 — how this
  layer's coverage compares to fact-graph's, and what is left that only fact-graph does.
