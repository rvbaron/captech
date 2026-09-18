# Domain Capture & Back-Annotation — Interview Notes

> Working notes for the pre-execplan interview on capturing and back-annotating
> `modernize-assess` domains into the legacylift-search Layer-0 index.
> Source design direction: `fact-graph-decision.md` §6a.
> Status: **interview COMPLETE (2026-07-17); execplan AUTHORED.** All 11 branches resolved with Darrell.
> Governing execplan: `docs/exec-plans/completed/domain-enhancements-plan.md`. The
> `semantic-code-search-graph-index.md` Decision Log reference has been repointed to it.
> This file remains the durable record of the decision rationale.

## Grounding facts (verified in code this session)

- `SymbolFact` model + `symbol_facts` table already exist (M23–25 plumbing committed,
  `models.py:50`, `store.py:346`), keyed on `subject_symbol_id`. Rules/data-model facts
  already have a home; domain-tagging them is a join, not new plumbing.
- Chroma `query()` passes no `where` filter today (`vector_store.py:161`); chunk metadata
  has no `domain` key (`vector_store.py:112`). Both are small additions.
- `vectors_present` (`store.py:334`) is the side-table precedent §6a points to for `chunk_domains`.
- `chunks` table has deterministic content-addressed ids and `relative_path` (`store.py:208`).
- assess emits domains as a **markdown table + `ARCHITECTURE.mmd` only** — human-facing,
  file-path granularity, top-down grouped (5–12), with inter-domain edges. No machine-readable
  emission today.
- The index dir `legacylift-docs/index/code-search/` is **gitignored and wiped on `--reset`**
  (Bedrock vectors had to be re-backfilled after M22's reset).

## Decisions

### Q1 — Source of record: SQLite vs JSON  → **RESOLVED: SQLite**
Darrell's strategic intent: eventually move ALL downstream outputs (BUSINESS_RULES.md,
DATA_OBJECTS.md, etc.) to be generated/queried FROM SQLite — store the rules extractor's
output, data objects, and domains in a relational store, so the whole knowledge base can
move to the cloud for shared team use. Given that, SQLite is the store of record for domains
(not a git-committed JSON). JSON, if used at all, is only a transient interchange from assess.

Open consequence to resolve next (Q2): the code-search index SQLite is throwaway (`--reset`
wipes it). A durable relational knowledge store cannot live in a throwaway artifact. Need to
decide the physical home + reset semantics.

### Q2 — Durable store location + `--reset` semantics  → **RESOLVED: 2B (separate durable knowledge DB)**
A durable knowledge DB (e.g. `legacylift-docs/knowledge.sqlite`, NOT gitignored, NOT touched by
`--reset`) holds domains/rules/data-objects/facts. The throwaway `index.sqlite` keeps
chunks/vectors/graph. Join by stable keys (`relative_path`, `chunk_id`, `symbol_id`) via `ATTACH`
or app-level joins. Matches the cloud/shared-team migration story: the knowledge DB is the thing
you ship; the index is a local accelerator.
Consequence: migrate the just-landed `symbol_facts` (M23–25) OUT of `index.sqlite` INTO the
knowledge DB so facts + domains share the durable store from the start.

### Q3 — Assignment granularity  → **RESOLVED: file-granularity**
Source-of-record assignment stored at file granularity: `file_domains(relative_path, domain, …)`,
keyed on `relative_path` (stable across content edits; matches assess's native output; no per-edit
churn). Chunk/symbol/fact domain DERIVED by join (chunk.relative_path → file_domains). A `domain`
copy is denormalized into Chroma metadata only because Chroma can't join at query time. §6a's
`chunk_domains` is therefore a derived denormalization, not the source of record. Symbol-level
override (Shared/Core edge case) is a documented later refinement, not v1.

### Q4 — assess emission + mapping mechanism  → **RESOLVED: hybrid; domains.json is transient**
assess (LLM) emits a transient `domains.json` = `{domain: {name, description, path_globs[]}, edges[]}`.
A deterministic `legacylift-search` ingest step reads it ONCE and writes to the knowledge DB:
  - `domains` catalog table (domain_id, name, description, **path_globs**, assess run_id)
  - `domain_edges` table (inter-domain dependency edges)
  - `file_domains` table (resolver output: explicit relative_path → domain rows)
`domains.json` is a disposable build artifact after ingest (gitignore/delete OK). Cloud migration
ships `knowledge.sqlite` ONLY — no JSON file to account for.
Flow: assess → domains.json (transient) → ingest (parse + resolve globs vs discovered files) → knowledge.sqlite.
LLM authors compact rules; deterministic resolver produces exhaustive assignments; new files
auto-classify against existing globs on reindex without a full assess re-run.

### Q5 — Cardinality + catch-all  → **RESOLVED: single primary domain per file + reserved `Unassigned`**
v1: each file has exactly one domain (clean scalar Chroma `where` filter, clean coverage math,
matches assess output). `file_domains` stays a TABLE (not a column) so 1:many is a non-breaking
future extension (deferred symbol-level Shared/Core override). Reserved `Unassigned` domain catches
glob-unmatched files — satisfies "all code rolls up", makes gaps loud/countable, doubles as the
freshness signal for new code. `Shared`/`Core` = a normal assess-authored domain (rendered as
cross-cutting in ARCHITECTURE.mmd, not special-cased). Generated code not special-cased in v1.

### Q6 — Tagging-pass ownership + sequencing  → **RESOLVED**
Three passes: index → assess → tag. Pass 3 = a NEW deterministic `legacylift-search tag-domains`
subcommand doing (1) ingest (domains.json → domains/domain_edges/file_domains in knowledge DB, glob
resolution) and (2) stamp (denormalize file-domain into existing Chroma metadata via
`collection.update`, NO re-embed). Idempotent. assess gets ONE minimal additive change: emit
domains.json alongside markdown/ARCHITECTURE.mmd — REQUIRES CapTech attribution line (Apache-2.0
skill per CLAUDE.md). legacy-analyst already knows domains+files, so it's a formatting addition.

### Q7 — Freshness (two axes) + self-maintenance  → **RESOLVED: 7-Auto**
Second freshness axis for domains. Detection: store assess `run_id` on `domains` catalog; `validate`
compares discovered file set vs `file_domains` coverage and prints a DISTINCT line
(`domains: fresh|stale · coverage % · N untagged · assess run <id>`) so "fresh index, stale domains"
is loud. Maintenance = 7-Auto: on reindex the indexer self-resolves new/changed paths against the
STORED globs (shared deterministic resolver), writes derived `file_domains` rows + stamps Chroma
inline → "add file to existing package" is zero-touch. Invariant: authored data (globs/edges/
descriptions) is assess→ingest-only; derived data (file_domains rows, Chroma domain metadata) may be
produced deterministically by EITHER the indexer or tag-domains. Staleness narrows to brand-new
domains / semantic re-grouping (needs assess re-run), which validate flags.

### Q8 — Consumer scope + bridge  → **RESOLVED: Minimal scope; query API IN, bridge DEFERRED**
This feature = (a) capture assess-quality domains into knowledge.sqlite (durable, queryable, fresh),
(b) switch the consumers THIS feature owns — ARCHITECTURE.mmd regen + domain-scoped search — onto
SQLite domains.
Two layers were being conflated:
  1. SQLite domain QUERY API (raw funcs over knowledge.sqlite: list domains, files-by-domain,
     domain edges, per-domain stats) → **IN SCOPE** — ARCHITECTURE.mmd render, `--domain` search
     filter, and stats all need it; already proven by those consumers.
  2. Form-2 BRIDGE (thin alias layer re-exposing that API under fact-graph's exact helper names
     `get_domains()`/`find_entities_by_domain()`/`get_domain_statistics()` for a one-line import
     swap per skill) → **DEFERRED**. In Minimal scope NO skill is re-pointed, so nothing calls the
     bridge; building it now = adapting to the fact-graph contract we intend to retire, with no
     consumer to validate against (YAGNI). Write it in the follow-on WHEN the first skill is
     re-pointed, so it's validated against a real consumer.
Form 1 (regenerate fact-graph JSON packs) rejected — perpetuates the JSON pipeline the SQLite vision
wants to retire. Re-pointing all 13 skills' Phase-0 = gated follow-on (open fact-graph Option A).

### Q9 — ARCHITECTURE.mmd derived + scope split  → **RESOLVED**
ARCHITECTURE.mmd becomes a DERIVED artifact: assess stops hand-authoring it, emits nodes+edges as
DATA in domains.json; a deterministic `legacylift-search` renderer produces ARCHITECTURE.mmd from
`domains` + `domain_edges` (subgraph per domain; `Shared` shown cross-cutting). ASSESSMENT.md stays
assess-authored. Producers confirmed: ARCHITECTURE.mmd→assess; DATA_OBJECTS.md+BUSINESS_RULES.md→
extract-rules; critical-path.mmd+data-lineage.mmd→map.
IN scope (owned outputs): domain-scoped search (`--domain`), ARCHITECTURE.mmd render, per-domain
coverage/stats. OUT of scope: see Future Work.

## FUTURE WORK (deferred — noted per Darrell 2026-07-17)
- Re-point all 13 doc skills' Phase-0 to SQLite domains (gated on fact-graph Option A decision).
- SQLite-source DATA_OBJECTS.md + BUSINESS_RULES.md (from extract-rules); seam = symbol_facts already
  in knowledge DB. Part of the broader "generate every downstream output from SQLite" vision.
- Domain OVERLAY on critical-path.mmd + data-lineage.mmd (from map).
- Symbol-level domain override table (Shared/Core files whose symbol domain != file domain) — the
  §6a "not a v1 blocker" refinement; enabled by keeping file_domains a table (Q3/Q5).
- Multi-domain (1:many) file assignments (Q5 — table already supports it).
- Generated-code (XSD/EDI) special-case domain handling (Q5).
- Move the whole knowledge.sqlite to a shared/cloud relational store for team use (Q1 vision).

### Q10 — Provenance / confidence / human correction  → **RESOLVED: bake into v1 schema**
`file_domains(relative_path, domain, source, assess_run_id, confidence)`.
- `source` ∈ {'glob','manual'}; `assess_run_id` = producing assess run; `confidence` default 1.0.
- Confidence in v1 is effectively binary (glob match is match/no-match); the real judgment lives in the
  catalog (globs). Keep the column for forward-compat (future LLM/symbol-level classifier); don't
  compute gradients now.
- HUMAN CORRECTION TRAP: 7-Auto re-resolves paths against globs every reindex → would clobber manual
  fixes. Precedence rule baked in NOW: `source='manual'` rows are authoritative, NEVER overwritten by
  glob auto-resolution or tag-domains re-runs; only `source='glob'` rows refresh. This is why the
  `source` column must be v1, not a later add.
- Correction TOOLING/UX (CLI verb, or feeding corrections back into globs to generalize) = future work.
  v1 only guarantees a hand-edited `manual` row sticks.

### Q11 — Execplan shape + M23–25 coordination  → **RESOLVED**
- M23–25 is DONE (facts already written to index.sqlite). So coordination collapses to: the new
  feature's FIRST milestone (F) relocates `symbol_facts` OUT of index.sqlite INTO knowledge.sqlite.
- Home = **NEW execplan** (`docs/exec-plans/active/…`), distinct architectural component (durable
  knowledge store) with its own lifecycle/consumers/future-work; cites M22–25 as prerequisites and
  links `fact-graph-decision.md` §6a. Not appended to the ~1,100-line index plan.
- semantic-code-search-graph-index.md references THIS notes doc now; repoint to the final execplan
  once it's authored.

## Work list (for the eventual execplan)
- **F. Knowledge-DB foundation** — new `knowledge.sqlite` + store layer + cross-DB ATTACH/join;
  relocate `symbol_facts` from index.sqlite into it.
- **D. Domain schema** — `domains`(domain_id,name,description,path_globs,assess_run_id) +
  `domain_edges` + `file_domains`(relative_path,domain,source,assess_run_id,confidence; manual-wins).
- **A. assess change** — emit transient `domains.json` (nodes+globs+edges+descriptions) + attribution line.
- **T. `tag-domains` command** — ingest domains.json → domains/domain_edges/file_domains (glob resolve)
  + stamp Chroma metadata (collection.update, no re-embed); idempotent.
- **X. Indexer 7-Auto** — consult knowledge DB, self-resolve new/changed paths vs stored globs, write
  derived file_domains + stamp Chroma inline; enforce manual-wins precedence.
- **S. `--domain` search filter** — thread `where={"domain":…}` into Chroma query + CLI flag.
- **V. Freshness** — `validate` second axis (domain coverage line + assess run_id).
- **R. ARCHITECTURE.mmd renderer** — deterministic from domains+domain_edges; assess stops authoring it.
- **Q. SQLite domain query API + per-domain stats** — raw funcs (list domains, files-by-domain, edges,
  stats); powers R/S/V and (future) the Form-2 bridge.
