# SQL Extractor: Separate Temp Tables / CTEs and Resolve Bracketed FK Targets

> **Status: COMPLETE — Milestones 0-5 done (2026-07-30). M6 deferred by decision, not by omission.**
> Started as a follow-up carried over from the domains-enhancement / NNG DB-unit work
> (`feature/domains-enhancement`, session handoff 2026-07-24). Root causes re-verified against the
> running code on 2026-07-24 (branch `fix/sql-extractor-temp-cte-fk`, `.venv` / Python 3.12.9);
> see the **Surprises & Discoveries** and **Decision Log** entries dated 2026-07-24 — the original
> FK framing was corrected. M2/M3 shipped in `87bc8db6`; M4 (regex `CREATE TABLE` recovery, which
> the original draft deferred) landed 2026-07-30 in `c089abac` and is what makes bracket-heavy T-SQL
> usable. **M5 (`1efd49a9`) turned out to be more than a verification pass**: re-indexing the real
> NNG DB unit exposed two further defects invisible to the hand-written fixtures — bracketed *data
> types* dropped every column, and out-of-line `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY`
> (81 of 81 FKs in that unit) was never scanned. Both are fixed; the map now runs off the index.

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and
`Outcomes & Retrospective` current.


## Purpose / Big Picture

`legacylift-search`'s SQL extractor (tree-sitter-sql on the tree-sitter path + a regex fallback in
`extractors.py`) has weaknesses that surfaced while mapping the NNG DB unit
(`customer.ple.nng.db.ETSPii`), which forced `/modernize-map` onto the sanctioned grep path instead
of the index's structural facts:

1. **Temp tables are conflated with real tables.** On the tree-sitter path, a `CREATE TABLE #Temp`
   / `@table` transient object is still a `create_table` node, so it becomes a table symbol and
   pollutes the durable-schema inventory and lineage graph.
2. **Bracketed / schema-qualified FK edges dangle — but NOT because the FK target is un-normalized.**
   The FK *reference* is already normalized (`[dbo].[Customer]` → `Customer`, `extractors.py:1169-1171`,
   shipped in M24 `6b9ac4b3` on 2026-07-17). The real defect is an **asymmetry**: the `create_table`
   *symbol name* is **not** normalized. `_extract_name` returns the raw name-node text, which
   tree-sitter-sql surfaces **mangled** for bracketed identifiers — a `CREATE TABLE [dbo].[Customer]`
   yields symbol name `dbo].[Customer` (verified 2026-07-24). Meanwhile `GraphBuilder._resolve_callee`
   resolves FK edges by **exact `ref.name` string match** (`graph.py:151`). `Customer` never matches
   `dbo].[Customer`, so the edge is emitted with `callee_symbol_id=None`, confidence 0.30 — dangling
   (reproduced; plain unbracketed names resolve fine). **The fix belongs on the table-symbol-name side
   (or a normalized resolution index), not the FK ref.**
3. **CTEs are a lineage-ref concern, not a table-inventory one.** `WITH cte AS (…)` is not a
   `create_table` node, so it never becomes a durable table symbol via this path (the original plan
   overstated this). A CTE name can only surface as a `table_reference` / `object_reference` *call*
   ref. So "exclude CTEs from the table inventory" is a non-issue; the only real question is whether
   CTE references should be suppressed / labeled in the data-lineage refs.

After this change, the SQL extractor should (a) exclude — or clearly label — temp tables so the
durable-schema inventory is clean, (b) normalize the `create_table` symbol name so bracketed /
schema-qualified FK edges resolve to their tables, and (c) if warranted, label CTE-derived lineage
refs — letting the DB map rely on structural facts instead of grep.

> **Environment note (resolved 2026-07-24).** tree-sitter-sql loads fine in the project `.venv`
> (Python 3.12.9): `get_language("sql")` parses, and all 8 `test_m24_sql.py` tests pass. An earlier
> "does not load" reading was an interpreter mistake — running the global Python 3.14, which has
> **none** of the project deps installed. There is no production loading bug. Always run
> `legacylift_search` via `.venv`. The bugs below (bracketed-name mangling, temp-table capture) are on
> the **tree-sitter path** and are the real, reproduced defects.


## Progress

- [x] Milestone 0: Environment triage — confirmed tree-sitter-sql loads in `.venv` (Py 3.12.9);
      earlier "doesn't load" was a wrong-interpreter artifact. Bugs are on the tree-sitter path.
- [x] Milestone 1: Committed fixture `tests/fixtures/polyglot_repo/database/tsql_bracketed.sql` +
      regression tests (`tests/test_sql_temp_cte_fk.py`) pinning both weaknesses.
- [x] Milestone 2: Temp tables (`#`/`##`, `@`, `TEMP`/`TEMPORARY`) are classified as a distinct
      `create_temp_table` kind (via `_sql_is_temp_table`), so they drop out of the `create_table`
      durable inventory while staying present/identifiable. (Chose relabel-kind over a flag: Symbol has
      no attributes field and nothing downstream keys on the kind string except tests.)
- [x] Milestone 3: `create_table` (and all SQL definition + call-ref) names run through the shared
      `_normalize_sql_identifier` helper (de-mangles tree-sitter's `dbo].[Customer`, strips
      `[]`/quotes/backticks, drops schema qualifier). The FK-ref path now reuses the same helper, so
      both sides of graph resolution stay in lockstep. Bracketed/qualified FK edges resolve
      cross-table; `uses_table` lineage refs benefit identically.
- [x] Milestone 4 (2026-07-30 — grew from "defensive regex hardening" into the durable fix for
      bracketed T-SQL, because the grammar turned out to emit WRONG data, not just sparse data):
      - **Regex `CREATE TABLE` segmentation** (`_sql_table_segments`, `_sql_mask_noncode`,
        `_sql_columns_from_body`) now decides the SQL table inventory. The grammar keeps a table only
        when its node maps 1:1 to a single statement AND that statement has no `[` brackets;
        otherwise `_reconcile_sql_tables` discards the grammar's symbol/facts/FK-refs and re-emits
        them from regex (`create_table` / `create_temp_table`, `has_column` at confidence 0.9,
        `foreign_key` refs). Non-FK refs inside a replaced node are re-anchored, so lineage survives.
      - Comment / string-literal masking means a commented-out or dynamic-SQL (`EXEC('CREATE TABLE
        …')`) statement cannot become a phantom table, and a retired `-- FOREIGN KEY …` cannot become
        a live edge (that masking was applied to the M24 tree-sitter FK scan too).
      - **Fallback path**: the same segmenter runs when no grammar is available, so that path now
        yields real tables + columns + resolving FK edges instead of a bare `fallback_definition`
        each; the SQL profile's definition/call regexes accept `[`/`"`/backtick/`#`/`@` leading
        characters and are case-insensitive; SQL fallback names are normalized; and the generic
        patterns are matched against the masked copy (prose in a comment — "a bracketed CREATE TABLE
        that also contains NOT NULL" — used to yield a symbol named `that`).
      - **Temp names keep their marker** (`#Orders`, not `Orders`) on BOTH paths, so a staging table
        can no longer collide with its durable namesake in the graph's name index.
      - `test_m24_sql.py` now skips (not fails) without the grammar via `tests/conftest.py`
        (`requires_sql_grammar`).
      - New: `tests/test_sql_table_recovery.py` (22 tests) + fixture
        `tests/fixtures/polyglot_repo/database/tsql_bracketed_multi.sql`.
- [x] Milestone 5 (2026-07-30, `1efd49a9`): NNG DB unit re-indexed with `index --reset` and
      `/modernize-map` re-run. **The re-run was not a formality — it found two more defects** that
      only appear in DDL shaped the way SQL Server actually scripts a schema (see Surprises):
      - **Bracketed data types dropped the column.** `_SQL_COLUMN_HEAD_RE` required a bare-word
        type; SSMS brackets every type (`[PLACE_FIPS] [varchar] (5) NOT NULL`). All 143 durable
        tables indexed with **zero** columns. Type is now a full possibly-qualified identifier,
        normalized like a name (`[varchar] (5)` -> `varchar(5)`, `[dbo].[PhoneNumber]` -> `PhoneNumber`).
      - **Out-of-line FKs were never scanned.** Both existing FK scans are scoped to a `CREATE TABLE`
        body, but a script-folder export declares constraints in trailing `ALTER TABLE ... ADD
        CONSTRAINT ... FOREIGN KEY` batches — 81 of 81 FKs in this unit. New
        `_sql_alter_table_fk_refs` runs on both paths, anchors the ref on the `FOREIGN KEY` clause at
        the same absolute offset the in-table scans use (so a clause seen by both dedupes rather than
        double-counting), and attributes it to the ALTERED table so the edge reads child -> parent.
      - Full `legacylift_search` suite now green with **no** exceptions: the long-standing
        `test_bedrock_embedder` failure was only the project's own declared `aws` extra (`boto3`)
        missing from `.venv`; installing it makes all 20 pass. `test_discovery.py` updated to 18
        fixtures.
      - `/modernize-map` re-run: `extract_topology.py` rewritten to seed edges from the index graph,
        grep path retired. See **Outcomes** for the before/after and for two false claims in the
        prior (grep-built) map that the index contradicted.
- [ ] Milestone 6 (optional): CTE lineage-ref labeling — not needed for the table inventory (a CTE is
      not a `create_table`, confirmed by test). **Deferred by decision.** M5 measured the actual
      unresolved-ref tail on real data: 7911 of 10039 `object_reference` refs don't bind, and
      spot-checking shows they are query aliases, built-in functions and `@variables` — not CTEs. The
      map already filters to resolved refs, so labeling CTEs specifically would not move the needle.


## Surprises & Discoveries

- **(2026-07-24) FK target normalization already exists.** `extractors.py:1169-1171` does
  `_unquote(...).split(".")[-1].strip('[]"')`, shipped in M24 (`6b9ac4b3`, 2026-07-17) — a week
  before this plan's original draft. The dangling-edge symptom is an **asymmetry**: the FK ref is
  normalized (`Customer`) but the `create_table` symbol name is not. Resolution in
  `GraphBuilder._resolve_callee` (`graph.py:151`) is exact-string `ref.name` vs `Symbol.name`, so the
  two forms never meet.
- **(2026-07-24) Bracketed table names come out MANGLED, not merely qualified.** Reproduced in `.venv`:
  `CREATE TABLE [dbo].[Customer]` → `create_table` symbol name `dbo].[Customer` (not `[dbo].[Customer]`
  nor `dbo.Customer`). The resulting FK edge has `callee_symbol_id=None` / confidence 0.30 (dangling),
  while a plain `REFERENCES providers(...)` resolves cleanly. So Milestone 3 must **de-mangle** the
  bracket artifacts, not just strip a clean `[]` pair.
- **(2026-07-24) Temp tables ARE captured as durable tables.** Reproduced: `CREATE TABLE #TempStaging`
  → `create_table` symbol name `TempStaging` (the `#` is dropped by name extraction), sitting in the
  inventory next to real tables. Milestone 2 is valid and on the tree-sitter path.
- **(2026-07-24) CTEs never become table symbols.** `WITH … AS` is not a `create_table` node
  (reproduced: no `create_table` symbol for the CTE), so "CTEs conflated with real tables" was wrong
  for the table inventory. Downgraded to an optional lineage-ref concern (Milestone 6).
- **(2026-07-24) The "tree-sitter-sql doesn't load" scare was a wrong-interpreter artifact.** Global
  Python 3.14 has none of the project deps (`tree_sitter` absent → full regex fallback → all 8 M24
  tests fail). In the project `.venv` (Py 3.12.9) the grammar loads and M24 passes. No production
  loading bug. NOTE for Milestone 4: the fallback definition regex `[A-Za-z_][A-Za-z0-9_\.\[\]"]*`
  (SQL profile `fallback_patterns`) still rejects a leading `[` or `#`, so if the grammar is ever
  genuinely absent, bracketed/temp tables get no symbol — worth hardening defensively.
- tree-sitter-sql mis-parses the FK clause (it can come back as an `ERROR` node), which is why FKs
  are recovered by regex (`_SQL_FK_RE`, `extractors.py:31`) rather than from the AST. Any FK
  target-resolution fix builds on that regex, not the grammar. (Unchanged from original.)
- **(2026-07-24, KEY LIMITATION) Bracketed DDL + `NOT NULL` makes tree-sitter-sql MERGE adjacent
  tables.** Two single-line bracketed `CREATE TABLE`s parse as two `create_table` nodes — until a
  `NOT NULL` appears, at which point the ERROR-recovery collapses the second table into the first
  node (verified by bisection: the merge appears exactly when `NOT NULL` is added). Because `NOT NULL`
  is ubiquitous in real schemas, **normalization alone cannot make heavily-bracketed T-SQL yield a
  reliable table inventory or FK graph** — the grammar doesn't even segment the tables. The committed
  regression fixture therefore uses plain table names for the cross-table FK case (bracketed only on
  the `REFERENCES` target) and a single bracketed table for definition-side normalization. The durable
  fix for bracketed multi-table T-SQL is regex-based `CREATE TABLE` recovery (Milestone 4 territory),
  analogous to the existing `_SQL_FK_RE` supplement — larger than this change and deferred. This is
  why the NNG DB map may still fall back to grep for the most bracket-heavy units.


- **(2026-07-30, WORSE THAN DOCUMENTED) The merge does not just LOSE the swallowed table — it emits a
  confidently WRONG edge.** Reproduced on three bracketed tables (Customer / Orders / OrderLine, all
  with `NOT NULL`): the grammar produced 2 `create_table` nodes for 3 tables; `Orders` had no symbol;
  its columns (plus a junk `has_column` named `GO`) were attributed to `Customer`; the
  Orders→Customer FK resolved against `Customer`'s own symbol as a **0.85-confidence
  `Customer`→`Customer` self edge**; and the OrderLine→Orders FK dangled at 0.30. A dangling edge is
  visibly missing data; a self edge is a false fact that a reader would believe. That reframed
  Milestone 4 from "defensive hardening, lower priority" into the milestone that actually makes the
  DB map trustworthy.
- **(2026-07-30) Bracketed columns whose names collide with grammar keywords VANISH.** Worse and more
  common than the merge. `CREATE TABLE [dbo].[C] ([Name] NVARCHAR(100) NOT NULL, …)` parses `[Name]`
  as `keyword_name` inside an `ERROR` node, so there is no `column_definition` and the column is
  silently absent from `has_column` — no error, no warning, just a short table. The grammar's
  keyword list covers Name/Date/Value/Status/Type/Key/Number/Level, i.e. much of a real schema. This
  is why recovery had to take over bracketed tables even when the grammar *did* segment them 1:1.
- **(2026-07-30) The closing bracket also poisoned column types.** `[Qty] DECIMAL(9,3)` reaches the
  extractor as `identifier(Qty)`, `ERROR(])`, `decimal(DECIMAL(9,3))` — and `_sql_column_type` took
  the first non-punctuation child, so every bracketed column's `data_type` was `']'`. Fixed by
  skipping bracket-artifact `ERROR` children (with a regex re-derivation as backstop).
- **(2026-07-30, PROCESS) Set iteration broke serial/parallel index equality.** Building the
  recovered-table list by iterating a set of symbol ids made emitted symbol order depend on
  per-process string hashing, so `test_indexer_parallel`'s byte-for-byte serial-vs-parallel
  comparison failed while each test passed alone. Everything in `_reconcile_sql_tables` is now
  derived in segment (source) order; sets are used only for membership. Worth remembering for any
  future extractor change: that test is the only thing that catches this class of bug.
- **(2026-07-30) Phantom tables are the price of regex segmentation, and comments/dynamic SQL are
  full of DDL.** The fixture's own commented-out `CREATE TABLE` and an `EXEC('CREATE TABLE …')` both
  became tables on the first pass. Masking comments and string literals to same-length spaces (so
  offsets and line numbers stay exact) removes the whole class, and the same mask fixed a
  pre-existing fallback-path bug where prose in a comment produced a symbol named `that`.

- **(2026-07-30, M5 — THE HAND-WRITTEN FIXTURES WERE THE WRONG SHAPE.** M1-M4's fixtures were
  authored by hand and used bare-word types (`NVARCHAR(100)`) with inline FK constraints. Real SQL
  Server schemas arrive as an SSMS script-folder export, which does neither. Both differences were
  silent, total failures on the real unit:
  - `[PLACE_FIPS] [varchar] (5) NOT NULL` — the type is **bracketed**, and `_SQL_COLUMN_HEAD_RE`'s
    type group was `([A-Za-z_][\w]*)`. The entry matched nothing, so the column was skipped. All
    143 durable NNG tables indexed with **0** columns (`has_column` went 961 -> 345 after M4 —
    the drop was the signal). A UDT column (`[phone] [dbo].[PhoneNumber]`) fails the same way.
  - Constraints are declared **out of line**: `ALTER TABLE [dbo].[X] ADD CONSTRAINT [FK_…] FOREIGN
    KEY (…) REFERENCES [dbo].[Y] (…)`, in its own `GO` batch. Every FK scan was scoped to a
    `CREATE TABLE` body, so all 81 NNG FKs were invisible and the unit had **0** FK edges.
  Lesson: a fixture that reproduces the *parser* bug is not the same as a fixture that reproduces
  the *input*. Take a real file from the target corpus before declaring a milestone green.

- **(2026-07-30, M5) The baseline's 38 FK edges were a side effect of the merge bug.** Pre-fix the
  unit had 38 `foreign_key` refs, all dangling. Those existed only because a merged `create_table`
  node had swallowed the following `ALTER TABLE` statements into its own text, so the in-body FK
  regex happened to see them (attributed to the wrong table). Fixing segmentation correctly removed
  them — so M4 alone took the unit from 38-wrong to 0, and the out-of-line scan was **required**
  before M5 could pass. A metric going from "wrong" to "absent" can look like a regression; check
  which of the two it is before reverting.

- **(2026-07-30, M5) The index contradicted two claims in the previous, grep-built map.** Worth
  recording because it is the concrete payoff: (a) the prior `TOPOLOGY.md` flow asserted
  `up_bt_getGeneralLegalEntityInformation` reads `LESContact` and `LESAddress`; the proc in fact
  touches exactly `etspii.dbo.LESLegalEntity` and `etspii.dbo.LESStatusHistory` — a hand-written flow
  a grep graph had no facts to contradict. (b) 44 tables were listed as dead ends that are published
  to subscribers through the replication article list (`@source_object`), i.e. external contracts.
  Both are corrected in the re-run.

- **(2026-07-30, M5) The `test_bedrock_embedder` failure was never environmental-and-unfixable.**
  Three prior sessions recorded it as a known `botocore`-missing failure to be lived with. It is the
  project's own declared optional dependency (`[project.optional-dependencies] aws = ["boto3>=1.40"]`)
  simply not installed in `.venv`, while this repo's manifest sets `provider: "api"`. `pip install
  'boto3>=1.40'` makes all 20 pass — and is also required to re-index this unit with its configured
  Titan embedder. The suite has no known failures now.


## Decision Log

- **(2026-07-30) Regex segmentation is authoritative for the SQL table inventory; the grammar is
  authoritative only for clean, unbracketed statements.** Considered the narrower rule "grammar wins
  whenever it segmented 1:1" and rejected it: 1:1 segmentation says nothing about whether the
  *columns* inside survived, and vanished keyword-named columns are silent. Selection rule as
  implemented: replace the grammar's table if its node spans >1 statement, or the statement contains
  a `[`; keep it otherwise. Recovered `has_column` facts carry confidence 0.9 (regex-derived) versus
  1.0 for AST-derived ones, so provenance is visible; raw DDL stays on `signature`/`evidence`.
  Date/Author: 2026-07-30

- **(2026-07-30) Temp markers stay in the symbol name.** `CREATE TABLE #Orders` yields the name
  `#Orders`, not `Orders`. Dropping the marker (the grammar's behavior, which M2 inherited) would put
  a staging table and its durable namesake under the same key in `GraphBuilder`'s name index —
  `#Orders`/`Orders` pairs are idiomatic T-SQL — turning every reference to either into an ambiguous
  0.70 resolution. This changed the M1 test expectation from `StagingRows` to `#StagingRows`.
  Date/Author: 2026-07-30

- **(2026-07-24) Corrected FK root cause.** Milestone 3 was originally "normalize the FK target."
  That is already done. Rewritten to "normalize the `create_table` **symbol name**" so the two sides
  of the exact-string resolution match. At minimum strip `[]`/quotes and drop the schema qualifier
  (`[dbo].[Customer]` → `Customer`), matching the form the FK ref already emits. Keep the raw/qualified
  name available (e.g. as `qualified_name` or an attribute) so the schema qualifier isn't lost.
  Date/Author: 2026-07-24 / re-verify

- **(2026-07-24) Milestone 0 resolved — fix targets the tree-sitter path.** tree-sitter-sql loads in
  `.venv`; the bracketed-name mangling and temp-table capture were both reproduced on the tree-sitter
  path. The fallback-regex gap (Milestone 4) is demoted to defensive hardening. Run all
  `legacylift_search` work via `.venv`, never the global interpreter. Date/Author: 2026-07-24

- Open question: **drop vs. label** transient (temp) objects. Option A — omit temp tables from the
  table inventory entirely (cleanest for the durable data model / lineage). Option B — keep them but
  stamp a `transient`/`kind` flag so consumers can filter. Decide before Milestone 2.
  Date/Author: 2026-07-24 / draft

- Open question: temp-table detection scope. Dialect heuristics: `#` / `##` (T-SQL local/global temp),
  `@table` (table variables), `CREATE TEMP[ORARY] TABLE` (Postgres/SQLite). Confirm which dialects the
  NNG unit actually uses before over-generalizing.


## Context and Orientation

Key file: `tools/legacylift_search/src/legacylift_search/extractors.py`.

- `_SQL_FK_RE` (line 31): `FOREIGN KEY (cols) REFERENCES <target>(cols)`. The target is captured
  **and normalized** already (lines 1169-1171). Comment at lines 27–30 explains the regex-over-AST
  rationale (grammar returns `ERROR` for FKs).
- `_extract_sql_table_facts` (line 1106): emits `has_column` facts (tree-sitter columns) and one
  `foreign_key` ref per FK (regex). **Only runs when `source_file.language == "sql"` and
  `node.type == "create_table"`** — i.e. only on the tree-sitter path.
- `_extract_name` (line 787): returns raw node text for the definition name — this is where the
  `create_table` symbol name is set un-normalized. **Milestone 3 changes here (or in the SQL branch
  that consumes it).**
- `_unquote` (line 348): strips a single pair of surrounding quotes. Extend/reuse for bracket +
  schema-qualifier stripping rather than adding a parallel path.
- SQL profile: `src/legacylift_search/profiles/extractors.json` (`"sql"` block). As of M4 the
  `fallback_patterns` regexes are `(?i)` and accept `[`/`"`/backtick/`#`/`@` leading characters
  (they previously required `[A-Za-z_]`, so a bracketed or temp object got no symbol at all).
- Resolution: `graph.py` `_resolve_callee` (line 128, exact `ref.name` match, line 151) and
  `_edge_kind_from_ref` (line 186, `foreign_key` at line 235).
- M4 recovery machinery, all in `extractors.py` under the "Regex CREATE TABLE recovery" banner:
  `_sql_mask_noncode` (comment/string blanking that preserves offsets — read this first, everything
  else scans its output), `_sql_table_segments` -> `_SqlTableSegment`, `_sql_split_top_level`,
  `_sql_columns_from_body`, `SymbolExtractor._sql_recovered_table_artifacts` (emits the same shapes as
  the AST path), and `SymbolExtractor._reconcile_sql_tables` (the grammar-vs-regex selection rule).
  `tests/test_sql_table_recovery.py` is the readable spec for all of it.
- M5 additions: `_SQL_ALTER_TABLE_FK_RE` (named groups `child` / `fk` / `parent`) +
  `SymbolExtractor._sql_alter_table_fk_refs` for out-of-line FK constraints — called from `extract()`
  after `_reconcile_sql_tables` and from `_extract_fallback`. **There are now THREE FK scans**
  (M24 AST-node body, M4 segment body, M5 out-of-line); all three anchor the ref on the `FOREIGN KEY`
  clause at an absolute file offset so the same clause seen twice yields one ref id and dedupes.
  Keep that invariant if you add a fourth.
- `_SQL_COLUMN_HEAD_RE`'s **type** group is a full qualified identifier, not a bare word. That is
  load-bearing for every SSMS-scripted schema; narrowing it silently drops all columns.

Real-corpus reference: `repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.db.ETSPii`
(568 SQL files, 143 bracketed tables, 69 temp tables, 81 out-of-line FKs) is the file shape that
matters. `ScriptsFolder/Tables/dbo.FIPSCity.Table.sql` is a good 15-line sample of all of it. The
committed miniature is `tests/fixtures/polyglot_repo/database/tsql_ssms_scripted.sql`.

Downstream consumers: the knowledge graph / `graph.py`, and `/modernize-map`'s data-lineage +
call-graph rendering, which is what fell back to grep on the NNG DB unit.

Memory: `[[nng-domain-test-plan-status]]` (records the grep fallback and this weakness as a signal).


## Plan of Work

**Step 0 — parser triage (DONE).** Confirmed tree-sitter-sql loads in `.venv` (Py 3.12.9) and M24
passes; the "doesn't load" reading was a global-interpreter artifact. Fix targets the tree-sitter path.

**Step 1 — fixtures.** Add committed SQL fixtures: a `CREATE TABLE [dbo].[Orders]` with
`REFERENCES [dbo].[Customer]([Id])`, and a `#temp` / `@table` temp table. Assert current (wrong)
behavior to pin the baseline — the bracketed FK edge is dangling (`callee_symbol_id is None`), the
temp table appears as a `create_table` symbol.

**Step 2 — temp tables (tree-sitter path).** In `_extract_sql_table_facts` / the create_table branch,
detect temp-table names and either skip emitting the table symbol or stamp a transient/kind flag per
the Decision Log outcome.

**Step 3 — create_table name normalization (tree-sitter path).** Normalize the `create_table` symbol
`name` (strip `[]`/quotes, drop schema qualifier) so it matches the already-normalized FK ref name and
`_resolve_callee` links the edge. Preserve the qualified form (`qualified_name` / attribute).

**Step 4 — regex CREATE TABLE recovery + fallback path (DONE 2026-07-30).** Broadened well past the
original "defensive regex" scope once the grammar was found to emit wrong data:

- `_sql_table_segments` / `_sql_mask_noncode` / `_sql_split_top_level` / `_sql_columns_from_body`
  segment `CREATE TABLE` statements over a comment- and string-masked copy of the text (same length
  and line breaks, so offsets stay exact); offsets are carried in char AND byte units because
  tree-sitter ranges are byte-based.
- `_reconcile_sql_tables` (called from `extract()` for SQL) replaces the grammar's table when its node
  spans >1 statement or the statement contains `[`, re-emitting symbol + `has_column` + `foreign_key`
  from regex and re-anchoring the node's other refs.
- `_sql_column_type` skips bracket-artifact `ERROR` children (was returning `']'`); `_sql_column_name`
  normalizes; `_sql_temp_marker` restores the `#`/`@` prefix the grammar drops.
- `_extract_fallback` runs the same segmenter for SQL, matches the profile patterns against the masked
  copy, and normalizes SQL names; the SQL profile's definition/call regexes now accept
  `[`/`"`/backtick/`#`/`@` leads and are case-insensitive.
- FK scans on BOTH paths run over the masked text, so a commented-out constraint is not an edge.
- `tests/conftest.py::requires_sql_grammar` makes grammar-dependent tests skip, not fail.

**Step 5 — regression + NNG re-run (DONE 2026-07-30, `1efd49a9`).** Fixtures green. NNG DB unit
re-indexed (`index --reset`), `tag-domains` re-run, `/modernize-map` re-run off the index graph. The
re-run itself exposed two further defects that the hand-written fixtures could not, both fixed here:

- `_SQL_COLUMN_HEAD_RE`'s type group accepted only a bare word, so a bracketed type
  (`[PLACE_FIPS] [varchar] (5)` — what SSMS always emits) matched nothing and the column was
  dropped. Type is now `{_SQL_QUALIFIED_IDENT}`, normalized via `_normalize_sql_identifier`.
- `_sql_alter_table_fk_refs` + `_SQL_ALTER_TABLE_FK_RE` recover out-of-line
  `ALTER TABLE … ADD CONSTRAINT … FOREIGN KEY`, wired into the tree-sitter path (after
  `_reconcile_sql_tables`, so the altered table's symbol is the final one) and into
  `_extract_fallback`. Also install the project's declared `aws` extra (`pip install 'boto3>=1.40'`)
  — required both by `test_bedrock_embedder` and to re-index with the manifest's Titan embedder.


## Validation and Acceptance

1. **MET.** Temp tables are classified `create_temp_table` (not `create_table`), on both the
   tree-sitter and the recovery/fallback paths, and keep their `#`/`##`/`@` marker.
2. **MET.** A bracketed / schema-qualified FK target resolves to its `create_table` symbol, asserted
   through `GraphBuilder.build_edges` — including the harder multi-table case the original plan
   deferred: on `tsql_bracketed_multi.sql` the grammar alone yields 3 nodes for 4 tables and a
   `Customer -> Customer` self edge; after recovery the edge set is exactly
   `{Orders -> Customer, OrderLine -> Orders}` at 0.85.
3. **MET.** `test_m24_sql.py` skips without the grammar (`tests/conftest.py`); `test_sql_temp_cte_fk.py`
   (M1-M3) and `test_sql_table_recovery.py` (M4-M5, 31 tests) cover temp tables, bracketed FKs, the
   merge, vanished/mangled columns, phantom-table guards, non-ASCII byte offsets, ordering
   determinism, the no-grammar path, and — added in M5 — bracketed/UDT data types, out-of-line
   `ALTER TABLE` FK resolution, child->parent attribution, `PRIMARY KEY` not mistaken for a FK,
   commented-out constraints, ref dedupe, and a constraints-only script with no local table symbol.
   Full `legacylift_search` suite green with **no exceptions** (see Surprises: the long-standing
   `test_bedrock_embedder` failure was an uninstalled declared extra, not an environmental fact).
4. **MET (Milestone 5, 2026-07-30).** NNG DB unit (`customer.ple.nng.db.ETSPii`, 568 SQL files)
   re-indexed with `index --reset`; `tag-domains` re-run (8 domains, 568 files, 0 unassigned, 2675
   chunks stamped); `validate` reports `freshness: fresh`. `/modernize-map` re-run **off the index
   graph — the grep path is retired**, and the extractor's own summary asserts the acceptance
   criteria: `143 create_table, 68 create_temp_table, 0 bracket-mangled name(s)` and
   `vs filename walk: 143 Tables/*.sql -> drift=0`. Cost: index 91s end-to-end including Titan
   embeddings (1099 chunks); for reference a synthetic 200-table / 2600-column bracketed T-SQL file
   (106 KiB) extracts fully and correctly in ~1.9s, ~0.5s of which is recovery.


## Idempotence and Recovery

Changes are to the extractor's parsing/normalization logic and its tests — deterministic and safe to
re-run. Re-indexing (`index --reset`) rebuilds facts from source. No schema migration; if
normalization proves too aggressive, the raw FK-target text retained as evidence (and the preserved
qualified table name) allows a revert of the matching heuristic without data loss.

**M4 note for the NNG re-run: use `index --reset`, not an incremental reindex.** Symbol *names* moved
for temp tables (`StagingRows` -> `#StagingRows`) and previously-swallowed tables gained symbols, so
symbol ids for SQL files differ from what an existing index holds. Incremental reindex keys on file
hashes, and these files are unchanged — nothing would be re-extracted.


## Outcomes & Retrospective

**Milestone 4 (2026-07-30).** Bracket-heavy T-SQL now yields a trustworthy inventory. On the committed
`tsql_bracketed_multi.sql`: 3 grammar nodes -> 4 tables, all columns present (the grammar dropped
`[Name]` entirely), all data types real (they were `']'`), FK edges exactly
`{Orders -> Customer, OrderLine -> Orders}` at 0.85 where before there was one bogus self edge and one
dangling ref. The no-grammar fallback path went from a bare `fallback_definition` per statement to the
same full inventory with resolving FKs.

What made this bigger than the plan predicted: the original draft framed Milestone 4 as optional
defensive regex hardening, on the assumption that the tree-sitter path was sound and only a
deps-less environment needed help. Re-testing showed the tree-sitter path itself produces *false*
facts on bracketed DDL — a confident self edge and silently missing columns — which is the failure
mode you cannot detect downstream. The lesson worth carrying: when a parser is documented as
"mis-parsing" a construct, check whether it emits wrong output rather than no output before deciding
the priority. Two mechanical notes for the next extractor change: `test_indexer_parallel`'s
serial-vs-parallel byte-for-byte comparison is the only guard against set-iteration order leaking into
output, and `test_discovery.py`'s hard-coded fixture count/name set must be updated whenever a fixture
is added (M1 left it stale and the "suite green" claim in this plan was wrong as a result).

**Milestone 5 (2026-07-30, `1efd49a9`).** The NNG DB unit now indexes correctly and the DB map is
built from structural facts. Measured on `customer.ple.nng.db.ETSPii` (568 SQL files), before ->
after, with source ground truth for comparison:

| Fact | Pre-fix index (2026-07-23) | After M2-M5 | Ground truth |
|---|---|---|---|
| `create_table` symbols | 122, of which **102 name-mangled** (`dbo].[X`) | **143**, 0 mangled | 143 bracketed `CREATE TABLE` |
| `create_temp_table` | 0 (temp tables indistinguishable) | **68** | 69 `CREATE TABLE #x` |
| `has_column` facts | 961, incl. junk columns named `IDENTITY` (72) and `'N'` | **1576** (1477 regex @0.9 + 99 AST @1.0) | 1231 durable columns, recount matches **exactly**, 0 junk |
| Durable tables with 0 columns | — | **0 of 143** | — |
| `foreign_key` refs | 38 | **81** | 81 `FOREIGN KEY` constraints |
| FK edges resolved | **0** (38/38 dangling @0.30) | **81/81 @0.85**, 0 dangling, 0 self edges | — |

The map (`analysis/customer.ple.nng.db.ETSPii/`) was re-run with `extract_topology.py` rewritten to
seed edges from `index.sqlite` instead of SQL-body regex. Its header used to read *"Edges are REBUILT
FROM SOURCE (SQL body regex), NOT from the index graph: the index's SQL parser conflates temp
tables/CTEs with real tables… This is the sanctioned grep-fallback path"* — that paragraph and the
observation quoting it are gone. Two false claims in the prior grep-built map were corrected (see
Surprises): a fabricated flow step, and 44 tables wrongly listed as dead ends that are in fact
published replication contracts. Dead-end candidates went 77 -> 24 as a result (the 9 Quartz
scheduler tables are also now suppressed — they are written by the Java tier, never by in-database
SQL). 940 edges, 81 of them FK, all endpoints assert-checked to exist as leaves.

Two honest limitations recorded in the map's `observations` rather than papered over: the index does
**not** carry read/write direction (the pair set is the index's; source text is consulted only to
label a confirmed pair), and 7911 of 10039 `object_reference` refs don't bind to a symbol — query
aliases, built-in functions and `@variables`, since the extractor emits one ref per
identifier-shaped token. Tightening that tail is a separate, lower-value piece of work; it does not
affect the table inventory, the FK graph, or the resolved-lineage subset the map uses. The
`ALTER TABLE` fix is also the general lesson for M6-style follow-ups: **check the shape of a real
file from the target corpus before deciding a milestone is verification-only.**
