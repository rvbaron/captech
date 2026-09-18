# Session Handoff — Domains work (2026-07-24)

> ## ⚠ SUPERSEDED as of 2026-07-30 — every action item in this file is CLOSED.
> Read it as a **historical record + reference**: §1 (environment), §2/§3 (what was run) and §6
> (memory pointers) are still useful. Do **not** action §4.5 or §5 — they were completed in later
> sessions. Status of each, verified against git on 2026-07-30:
>
> | Item | Said | Actually |
> |---|---|---|
> | §4 excluded-by-design tier | "CODE COMPLETE, UNCOMMITTED — commit this" | **Committed** `98f2f9bf` |
> | §5 orphan Chroma vectors | "BUG (unfixed)" | **Fixed** `afc05364` — snapshot ordering, + regression test |
> | §5 assess should emit `exclude_globs` | "NOT done" | **Done** `dec5b809`; ExecPlan closed `8b574061`; merged `51771072` |
> | §5 DB SQL extractor weakness | "Signal for a future improvement" | **Done** `1efd49a9`; see `docs/exec-plans/completed/sql-extractor-temp-cte-fk.md` |
>
> **Branch note:** `feature/domains-enhancement` no longer exists. Everything above *except* the SQL
> extractor work is merged into **`feature/version-next`**. The SQL extractor fix (`1efd49a9`,
> `8787d28a`) is still only on **`fix/sql-extractor-temp-cte-fk`** — that merge is the one genuinely
> open action, and it is not a domains task.

Everything a fresh agent needs to pick up the domains work as it stood on 2026-07-24
(branch was `feature/domains-enhancement`; see banner).
Nothing here lives only in the previous session's head; this file + the memory pointers
below + the on-disk artifacts are the complete state.

---

## TL;DR — state as of 2026-07-24 (see banner for what has changed since)

Three things happened this session, in order:

1. **NNG at-scale domain test — DONE.** Ran the deferred capability-domains validation
   (preflight → assess → tag-domains → map, Stage E deferred) on both NNG units. All milestones
   M1–M8 + #57 PASS. Deliverables + report written. (Fully documented; see §2.)
2. **APP glob-gap fix — DONE.** 122 wrongly-`unassigned` files (mostly non-LES/EDI Hibernate
   `.hbm.xml` mappings) were routed to the right domains by tightening `domains.json` globs. (§3)
3. **New feature: excluded-by-design tier — CODE COMPLETE, TESTS GREEN, UNCOMMITTED.** Splits the
   overloaded `unassigned` bucket into `unassigned` (a real gap) vs `excluded` (intentionally not a
   business capability: tests, ops SQL, generated code). Applied to the NNG app → **coverage
   69% → honest 100%**. (§4) — **committed 2026-07-24 in `98f2f9bf`.**

**~~IMMEDIATE PENDING ACTION~~ — DONE.** The feature was committed in `98f2f9bf`; the in-flight
`pytest` run came back green. Historical detail retained in §4.4/§4.5.

---

## 1. Environment / how to run things

- Working dir for the NNG test: `repos/nng-app-legacylift-analysis` (`legacy/` + `analysis/` siblings).
- `legacylift-search` CLI: `cd tools/legacylift_search && py -3.12 -m legacylift_search.cli <verb> --repo-root "<abs path>"`.
- **There are TWO working interpreters, and mixing them caused a false bug report for weeks
  (clarified 2026-07-30).** Both have the deps; a third does not:
  - `py -3.12` → `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` — full deps **including
    `boto3`**. This is what the CLI recipe above uses, which is why indexing always worked.
  - `tools/legacylift_search/.venv` (3.12.9) — full deps, but was **missing `boto3`** until
    2026-07-30. `pytest` is normally run here, so `test_bedrock_embedder` failed while the CLI
    worked, and the failure got written off as "environmental" across several sessions. It was the
    project's own declared extra: `pip install 'boto3>=1.40'` (`[project.optional-dependencies] aws`).
    Now installed; suite is green with no exceptions.
  - the **global Python 3.14** has *none* of the deps. Running it produced a "tree-sitter-sql
    doesn't load" scare (ExecPlan `sql-extractor-temp-cte-fk` M0). Never use it.
  Rule: whichever you pick, use it for **both** the CLI and `pytest` so the two agree.
- Units: `legacy/customer.ple.nng.app` (Java, 1229 files indexed) and `legacy/customer.ple.nng.db.ETSPii` (SQL, 568).
- chromadb pinned **1.5.9**; embeddings = real Bedrock Titan (`AWS_BEARER_TOKEN_BEDROCK` in `.claude/settings.local.json`).
  Creds alone are not enough — `boto3` must be importable in the interpreter running the index, or
  the run dies in `BedrockEmbedder._get_client` in a way that looks like an auth failure.
- **Windows path gotcha (bit me repeatedly):** passing an MSYS `/c/Users/...` path to inline Python fails
  (`unable to open database file` / `FileNotFoundError`). Use `C:/Users/...` form for Python; `/c/...` is fine for bash tools.
- The whole `repos/nng-app-legacylift-analysis/` tree is **gitignored** (root `.gitignore:92`) — client
  source, indexes, `knowledge.sqlite`, and analysis output never commit. Only `tools/legacylift_search`
  code commits.

## 2. NNG domain test (DONE)

- Plan: `docs/exec-plans/completed/domain-enhancements-nng-test-plan.md` (self-contained).
- Deliverables: `repos/nng-app-legacylift-analysis/analysis-domains-enhanced/`
  — `PREFLIGHT.md`, `DOMAIN-ENHANCEMENTS-TEST-REPORT.md`, and per unit `ASSESSMENT.md`, `domains.json`,
  `ARCHITECTURE.mmd`, `topology.json`/`TOPOLOGY.html`/`extract_topology.py`, `call-graph`/`data-lineage`/`critical-path.mmd`.
- The full milestone-by-milestone results (M1 sentinel durability, M2 counts, M3 domains.json, M4
  tag-domains, M5 7-Auto+manual-wins, M6 search --domain, M7 freshness, M8 render, #57 vector-fill,
  Stage D topology pin) are in `DOMAIN-ENHANCEMENTS-TEST-REPORT.md`. Memory: `[[nng-domain-test-plan-status]]`.
- APP credential inventory quarantined (masked) to `analysis/customer.ple.nng.app/SECRETS.local.md`
  (gitignored; deliberately NOT copied into the shareable `analysis-domains-enhanced/` dir).
- **Stage E (extract-rules → BUSINESS_RULES.md/DATA_OBJECTS.md) is DEFERRED** — run only after the
  pending extract-rules changes land; it consumes no domain surface so no milestone depends on it.

## 3. APP glob-gap fix (DONE)

The APP originally showed 505 unassigned (41%). Analysis split it: ~122 were a real glob-authoring
gap (should belong to a domain); ~383 were legitimately-not-a-capability (tests + ops SQL). The 122
(mostly non-LES/EDI `.hbm.xml` under `ple-persistence/JavaSource/config/hbm/{standard,nonstandard,external}/`,
plus Spring converters, config XML, and a few `EmployeeSearch*`/`DunsFileSetupView`/`ContactSearchAndReplaceLite`
classes) were routed to the correct domains by tightening `domains.json` `path_globs`. Result after
that step: 846 matched / 383 unassigned, coverage 69%.

## 4. Excluded-by-design tier (COMMITTED 2026-07-24, `98f2f9bf` — §4.1-§4.3 are still the accurate design reference)

### 4.1 Why
`unassigned` overloaded two meanings: "gap — fix your globs" and "intentionally out of scope
(tests/ops/generated)". Both dragged coverage% down and both fired the "re-run assess" hint. This
tier separates them so coverage becomes honest and the hint only fires on true gaps.

### 4.2 Design (as built)
- `domains.json` gains an optional top-level array **`exclude_globs: [...]`**.
- Precedence: **manual > domain `path_globs` > `exclude_globs` > unassigned.** A domain always wins
  over an exclusion (exclusion only claims otherwise-unassigned files), so a broad exclusion can
  never hide a domain file.
- Excluded files get a `file_domains` row `domain='excluded'`, `source='glob'` — a reserved VALUE,
  never a `domains`-table row (same invariant as `unassigned`, issues #28/#30).
- Coverage is now `classified / (discovered − excluded)`. `validate`/`stats`/`domains` report
  `excluded` separately. Only `unassigned` triggers the "re-run assess" hint.
- Persisted in a new `domain_exclusions` table so the indexer's **incremental 7-Auto** auto-tags a
  new exclude-matching file (e.g. a new test) as `excluded` — it does NOT linger untagged→`stale`.

### 4.3 Behavior proof on NNG APP
`exclude_globs = ["ple-services-test/**","ple-persistence/sql/**","db/**"]` (the 358 tests + 25 ops
SQL). After re-tag: `validate` → **`fresh · coverage 100% · 0 unassigned · 383 excluded · 0 manual`**;
`stats` → `10 domains · 846 files tagged · 0 unassigned · 383 excluded`. The updated `domains.json`
(with `exclude_globs`) is already synced into `analysis-domains-enhanced/customer.ple.nng.app/`.
(DB unit already reached 100% via real domains — its Staging/Replication phase-domains are the same
idea expressed as domains rather than exclusions; left as-is.)

### 4.4 Files changed (all under `tools/legacylift_search/`; committed in `98f2f9bf`)
- `src/legacylift_search/knowledge_store.py` — `domain_exclusions(pattern)` table in `migrate()`;
  `set_exclusions()` / `list_exclusions()`.
- `src/legacylift_search/domain_tagger.py` — `RESERVED_EXCLUDED="excluded"`; `DomainsFile.exclude_globs`;
  `resolve_file_domains(..., exclude_globs=None)` (domain-wins precedence); `tag()` calls
  `ks.set_exclusions()` + passes globs; `TagStats.excluded_count`; render filter drops the slug.
- `src/legacylift_search/indexer.py` — `_build_domain_by_chunk` reads `list_exclusions()`, passes to
  resolver, and persists an `excluded` row for a new exclude-matching file.
- `src/legacylift_search/cli.py` — tag result line; `domains` "Excluded" trailer; `stats` `· E excluded`;
  `validate` freshness (excluded bucket, coverage denominator, `excludable` untagged sub-count);
  `search --domain excluded` special-case.
- `tests/test_domain_tagger.py` — resolve precedence + backward-compat, KnowledgeStore roundtrip,
  tag writes excluded rows, CLI reporting.
- `tests/test_indexer_domains.py` — incremental 7-Auto auto-excludes a new file.

### 4.5 ~~To commit (pending user's request)~~ — DONE, `98f2f9bf`
Historical record of what was run. Was on branch `feature/domains-enhancement` (since merged into
`feature/version-next` and deleted). Verify the full suite is green first
(`cd tools/legacylift_search && py -3.12 -m pytest -q`), then:
```
git add tools/legacylift_search/src/legacylift_search/{knowledge_store,domain_tagger,indexer,cli}.py \
        tools/legacylift_search/tests/test_domain_tagger.py \
        tools/legacylift_search/tests/test_indexer_domains.py
git commit   # message below
```
Suggested message:
> Add excluded-by-design domain tier (exclude_globs) to legacylift-search
>
> Splits the overloaded `unassigned` bucket into `unassigned` (a real
> glob-coverage gap) vs `excluded` (intentionally not a business capability:
> tests, ops SQL, generated code). `domains.json` gains optional top-level
> `exclude_globs`; matches become reserved `file_domains.domain='excluded'`
> rows (domain globs win over exclusions). Coverage% drops excluded from the
> denominator; only `unassigned` triggers the re-run-assess hint. Persisted in
> a new `domain_exclusions` table so incremental 7-Auto honors it. Verified on
> the NNG app: coverage 69% -> honest 100% (383 tests/ops-SQL excluded).

## 5. Open findings / follow-ups — ALL THREE NOW CLOSED (verified 2026-07-30)

- ~~**BUG (unfixed): incremental-reindex orphan Chroma vectors.**~~ **FIXED `afc05364`.** Root cause
  was *not* "ids unknown" as assumed here: the stale-id snapshot ran *after* the `upsert_files`
  cascade had already deleted the rows, so there was nothing left to purge. Fixed by moving the
  snapshot earlier in `indexer.py`, plus a regression test. Memory:
  `[[legacylift-incremental-reindex-orphan-vectors]]`.
- ~~**DB SQL extractor weakness:** conflates temp tables/CTEs and doesn't resolve bracketed FK
  targets; the DB map used the sanctioned grep fallback.~~ **FIXED**, ExecPlan
  `docs/exec-plans/completed/sql-extractor-temp-cte-fk.md` (M0-M5, `87bc8db6` → `c089abac` →
  `1efd49a9`). On the DB unit: `create_table` 122 (102 name-mangled) → 143 with 0 mangled; temp
  tables 0 → 68 classified as `create_temp_table`; `has_column` 961 (with junk columns) → 1576, and
  all 143 durable tables now carry columns (0 did after the first pass); FK edges 38-all-dangling →
  81/81 resolved at 0.85. `/modernize-map` re-run on 2026-07-30 seeds edges from the index graph —
  **the grep fallback is retired**. Two framing corrections worth knowing: the real defect was never
  the FK *target* (already normalized) but the un-normalized `create_table` *symbol name*; and the
  hardest part was not CTEs but the shape real SQL Server schemas arrive in (bracketed data types +
  out-of-line `ALTER TABLE` FK constraints), which no hand-written fixture had.
  Memory: `[[sql-extractor-ssms-shape]]`.
- ~~**assess skill should emit `exclude_globs`.**~~ **DONE `dec5b809`** (`/modernize-assess` now
  authors `exclude_globs`; `/modernize-map` buckets `dom:excluded`); brace-expansion lesson taught
  with it; ExecPlan closed `8b574061`, merged `51771072`.
- **STILL STANDING (not a task): `domains.json` is the source of truth** for the NNG app's domain set
  (the scratchpad generator scripts that produced it are session-ephemeral and gone). To adjust
  globs/exclusions, edit `analysis/customer.ple.nng.app/domains.json` directly and re-run
  `tag-domains`. See `[[domain-set-canonical-flow]]`.

### 5b. What IS open (2026-07-30)

- **Merge `fix/sql-extractor-temp-cte-fk` into `feature/version-next`.** `1efd49a9` + `8787d28a` are
  the only commits above not yet on that branch.
- **Stage E (extract-rules) remains deferred** — unchanged from §2, and still gated on the pending
  extract-rules changes rather than on anything here.
- **Two acknowledged SQL-extractor limits**, recorded in the DB map's `observations` rather than
  fixed, because neither affects the table inventory, the FK graph, or the resolved-lineage subset
  the map consumes: the index carries **no read/write direction** for table usage (the map takes the
  pair set from the index and consults source only to label a confirmed pair), and **7911 of 10039
  `object_reference` refs don't bind** to a symbol — query aliases, built-in functions and
  `@variables`, since the extractor emits one ref per identifier-shaped token. Tightening that tail
  is a separate, lower-value piece of work. (This measurement is also why the ExecPlan's optional
  "CTE lineage-ref labeling" milestone was deferred on evidence: the tail is not CTEs.)

## 6. Memory pointers (persisted across sessions)

- `[[nng-domain-test-plan-status]]` — the NNG test: DONE, all milestones, findings (finding #2, the
  SQL extractor / grep fallback, now marked resolved).
- `[[domain-excluded-by-design-tier]]` — this feature: design, files, NNG proof; now committed.
- `[[legacylift-incremental-reindex-orphan-vectors]]` — the orphan-vector bug, now resolved.
- `[[domain-search-vector-recall-57]]` — #57 vector-fill, re-confirmed at NNG scale.
- `[[domain-set-canonical-flow]]`, `[[domain-enhancements-plan-review]]` — standing design.
- `[[sql-extractor-ssms-shape]]` (added 2026-07-30) — why hand-written SQL fixtures hid two total
  extractor failures; verify parser work against a real corpus file.
- `[[legacylift-venv-aws-extra]]` (added 2026-07-30) — the `boto3`/`.venv` gap behind the
  long-standing "environmental" `test_bedrock_embedder` failure; see also §1 above.
