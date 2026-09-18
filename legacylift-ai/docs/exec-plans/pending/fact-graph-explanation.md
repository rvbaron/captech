# The `fact-graph` Skill — What It Collects and How

> A deep explanation of the LegacyLift `fact-graph` skill: the knowledge model it
> produces, the process it follows, and the limitations observed in both its design
> and its real output.
>
> Sources: [`.claude/skills/legacylift-classic/skills/fact-graph/SKILL.md`](../../../.claude/skills/legacylift-classic/skills/fact-graph/SKILL.md),
> the four JSON schemas in [`.claude/skills/legacylift-classic/skills/fact-graph/templates/`](../../../.claude/skills/legacylift-classic/skills/fact-graph/templates/),
> and a real generated graph for `ctcm-api`
> ([`repos/ctcm/ctcm-api/legacylift-docs/context/`](../../../repos/ctcm/ctcm-api/legacylift-docs/context/)).
>
> **Updated 2026-08-05.** Sections 1–7 describe the fact-graph skill itself and remain accurate —
> the skill has not changed. What *has* changed is everything around it: `legacylift-search`
> (Layer 0) now extracts type hierarchy, annotations, SQL columns/FKs, type references, a
> `symbol_facts` store, and capability domains. **[§8](#8-what-layer-0-now-covers-2026-08-05)
> maps each of the four record types below onto its Layer-0 equivalent**, so a reader can tell
> which parts of this document describe unique capability and which describe duplicated work.
> Read §8 before using this document to justify running fact-graph.

---

## 1. Purpose in one paragraph

`fact-graph` statically analyzes a codebase and emits a **structured JSON knowledge
graph** — entities, relations, and facts, each carrying source-code evidence —
organized into **domain-scoped packs**. It is meant to be run *first* on a repository
so that every other LegacyLift documentation skill (`exec-summary-generator`,
`si-documenter`, `data-documenter`, `citation-validator`, etc.) can read pre-computed,
consistent, citable knowledge instead of re-scanning the code. It is explicitly a
**deterministic extraction** tool: "No guessing, no inference, no LLM interpretation.
Every fact must be grounded in verifiable code evidence."

---

## 2. The knowledge model — the four things it collects

The graph has four record types. Each has a JSON Schema in `templates/`.

### 2.1 Entities — *the nodes*

An **entity** is any addressable code element. Required fields: `id`, `type`, `name`,
`file`, `line_range`. Optional: `qualified_name`, `attributes`.

**Entity types** (`entity.schema.json` enum):

| Category | Types |
|---|---|
| Application code | `class`, `interface`, `function`, `method`, `service`, `controller`, `repository`, `model`, `dto`, `enum`, `endpoint`, `middleware`, `component`, `module`, `package`, `config` |
| Database objects | `table`, `view`, `stored_proc`, `sql_function`, `trigger`, `index`, `constraint` |

**Attributes** carry type-specific metadata: `language`, `visibility`, `is_abstract`,
`is_static`, `namespace`, `schema`, `columns`, `primary_key`, `foreign_keys`,
`parameters`, `return_type`, `annotations`, `implements`, `route`, `http_method`, plus
the three classification fields and a `content_hash`.

**Real example** (from `ctcm-api`, `messaging.entities.pack.json`):

```json
{
  "id": "cs:messaging-executeroutingslipconsumer-4c13c95f2e06",
  "name": "ExecuteRoutingSlipConsumer",
  "qualified_name": "CTCM.API.MessagingService.Consumers.ExecuteRoutingSlip.ExecuteRoutingSlipConsumer",
  "type": "class",
  "file": "src/CTCM.API/CTCM.API.MessagingService/Consumers/ExecuteRoutingSlip/ExecuteRoutingSlipConsumer.cs",
  "line_range": [7, 16],
  "visibility": "public",
  "attributes": {
    "domain": "Messaging",
    "technical_layer": "Other",
    "language": "csharp",
    "content_hash": "2535433f0afb",
    "implements": ["IConsumer<RoutingSlip>"]
  }
}
```

### 2.2 Relations — *the edges*

A **relation** is a directed edge between two entities. Required fields (per schema):
`id`, `type`, `source_id`, `target_id`, `file`, `line`.

**Relation types** fall into groups:

| Group | Types |
|---|---|
| Inheritance/implementation | `inherits`, `implements`, `extends` |
| Dependencies | `uses`, `calls`, `invokes`, `references`, `imports`, `depends_on` |
| Structure | `contains`, `owns`, `has_member` |
| Data access | `reads_from`, `writes_to`, `queries` |
| Database | `foreign_key`, `join` |
| Metadata | `triggers`, `decorates`, `annotates`, `routes_to` |
| Uppercase "semantic" set | `EXPOSES_ENDPOINT`, `CALLS`, `WRITES_TABLE`, `READS_TABLE`, `USES_DTO`, `RETURNS_DTO`, `ACCEPTS_DTO`, `REQUIRES_POLICY`, `AUTHENTICATES_VIA`, `PUBLISHES_EVENT`, `CONSUMES_EVENT` |

### 2.3 Facts — *grounded claims with evidence*

A **fact** is a `subject → predicate → object` triple about an entity, backed by an
`evidence` array (≥1 entry, each with `file` + `line_range`, optionally `snippet` and
`snippet_hash`). Required: `id`, `subject_id`, `predicate`, `object`, `evidence`.
Optional: `confidence`, `attributes`.

**Fact predicates** (`fact.schema.json` enum), grouped:

| Group | Predicates |
|---|---|
| Structure | `has_property`, `has_attribute`, `has_method`, `has_field`, `has_column` |
| Validation/constraint | `validates`, `requires`, `ensures`, `max_length`, `min_value`, `max_value`, `pattern_matches`, `is_required`, `is_nullable`, `is_unique`, `is_indexed` |
| Behavior | `throws`, `returns`, `accepts` |
| Integration | `integrates_with`, `authenticates_via`, `authorizes_via` |
| Data operations | `stores_in`, `reads_from`, `writes_to`, `caches_in`, `logs_to`, `publishes_to`, `subscribes_to` |
| Configuration | `triggers_on`, `schedules_at`, `retries_on`, `timeout_after`, `default_value` |
| Workflow/state | `state_transition`, `process_step` |
| HTTP metadata | `http_method`, `accepts_param`, `returns_response`, `requires_auth` |
| Relationship metadata | `has_cardinality` |
| Business logic | `business_rule` |

**Confidence** is meant to be an object `{score: 0.0–1.0, reasoning: "..."}`, scored on
a documented scale: `1.0` = explicit keyword/annotation, `0.9–0.95` = clear pattern,
`0.7–0.85` = inferred from context, `0.5–0.65` = weak heuristic, `<0.5` = excluded.

**Real example** (`messaging.facts.pack.json`):

```json
{
  "id": "fact-210c650cc986",
  "subject_id": "cs:messaging-job-05ffc073f0a5",
  "predicate": "has_property",
  "object": "TrackingNumber",
  "attributes": { "data_type": "Guid", "visibility": "public" },
  "confidence": 1.0,
  "evidence": [{
    "file": "src/CTCM.API/CTCM.API.MessagingService/Models/Job.cs",
    "line_range": [12, 12],
    "snippet": "public Guid TrackingNumber { get; set; }",
    "snippet_hash": "c0519e5f4329"
  }]
}
```

### 2.4 Index — *the master manifest*

`index.json` is the entry point. It contains:

- **`metadata`** — `repository`, `generated_at`, `tool_version`, `analysis_scope`,
  `project_type` (monolith / microservices / monorepo / library / cli_tool / web_app /
  mobile_app), `architecture_pattern` (layered / mvc / mvvm / clean / microservices /
  serverless / event_driven / cqrs).
- **`statistics`** — total `entity_count` / `relation_count` / `fact_count` /
  `files_analyzed`; breakdowns by `entity_types`, `relation_types`, `languages`,
  `fact_predicates`; a `lines_of_code` block; and `packs_metadata`.
- **`packs_metadata`** — per-domain manifest: `packId`, `domain`, file paths for the
  three packs, `entity_count`, and discovery `keywords`.

---

## 3. Domains — how the graph is partitioned

Instead of one giant file, the graph is split into **domain-scoped packs**. A *domain*
is a **business capability** (Orders, Claim, Filing, Billing…), explicitly **not** a
technical layer. Each domain produces exactly three files:

```
packs/{domain}.entities.pack.json
packs/{domain}.relations.pack.json
packs/{domain}.facts.pack.json
```

So total output = `1 (index) + N domains × 3`. The `ctcm-api` graph has 19 domains →
58 files. Each entity also carries a **secondary `technical_layer`** axis (Model,
Service, Persistence, Web, Util, Validation, Exception, Configuration, Other, Unknown),
so the same data can be sliced by business domain *or* by architectural layer.

**Domain classification heuristics** (in priority order):

1. **Database table prefix** (highest confidence): `LES*` → LegalEntity, `POI*` →
   Points, `ORD*` → Orders, etc.
2. **Namespace/package segment**: business keyword in the qualified name.
3. **Folder structure**: domain folder regardless of layer folder.
4. **Fallback**: `Core` for cross-cutting utilities, base classes, framework code.

Validation rules nudge quality: each domain should have ≥5 entities, no domain >70% of
all entities, `Core` <15% of total.

---

## 4. How it works — the 7-phase process

The skill runs a fixed pipeline, writing intermediate results to `temp/` and
checkpointing with `TodoWrite` so it can survive context compaction and resume.

| Phase | What happens |
|---|---|
| **1. Repository Discovery** | Glob all source files (excluding build artifacts, `node_modules`, `legacylift-docs`); categorize by extension; locate config/entry/schema/API files; build a file inventory; run **`cloc`** for LOC metrics (reuses a prior `cloc-report.json` if present, honors `.gitignore` via `--vcs=git`). |
| **1.6 Domain Classification** | Apply the heuristics above to map every file/entity to a `(domain, technical_layer)` pair; write `temp/domain-mapping.json`; validate distribution. |
| **2. Entity Extraction** | Per-language batches (Java, C#, Python, JS/TS, SQL, other) using `grep`/`Glob`/`Read` for declarations; assign deterministic IDs; compute `content_hash`; group by domain. |
| **3. Relation Extraction** | Batches by relation family: inheritance/implementation → containment → dependencies → database (FKs, ORM annotations) → metadata (decorators, routes). |
| **4. Fact Extraction** | Batches by fact family: properties/columns → validation/constraints → integration/config → data ops/workflow/state → HTTP metadata/cardinality/business rules. Each fact gets evidence + confidence + `snippet_hash`. |
| **5. Validation** | Verify file/line validity, evidence snippets exist, relation `source_id`/`target_id` resolve to real entities, fact `subject_id` resolves, and all IDs are unique across collections. |
| **6. JSON Generation** | Group by domain, sort everything by ID (determinism), classify project type/architecture, write `index.json` + all domain packs. |
| **7. Cleanup** | Delete `temp/`; keep only `index.json`, `packs/`, optional `README.md`. |

**Determinism is a core design goal.** IDs are content-based SHA-256 hashes
(`{prefix}:{domain}-{name}-{hash12}` for entities; `rel-{type}-{hash12}` for relations;
`fact-{hash12}` for facts). Arrays are sorted by ID. No timestamps in IDs. The intent is
that the same code yields the same graph on every run.

**Drift detection** is built in via two hash fields: each entity's `content_hash`
(hash of its code block) and each evidence entry's `snippet_hash` (hash of the cited
snippet). `citation-validator` uses these to detect when code has changed since the
graph was generated.

The skill also emphasizes **completeness and persistence**: it is told to extract *all*
entities/relations/facts (no samples), to write large collections in batches of
100–500 with `<!-- BATCH X of Y COMPLETE -->` markers, and never to stop early for
token-budget reasons.

---

## 5. What a real graph looks like (`ctcm-api`)

The `ctcm-api` run (a .NET 10, 18-service microservices backend) produced:

- **6,047 entities**, **3,928 relations**, **38,618 facts**, across **4,846 files**.
- Entity types: `dto` 2,352, `class` 1,594, `endpoint` 753, `interface` 444, `service`
  317, `enum` 308, `controller` 173, `repository` 106.
- **19 domains** — Filing (816), Workflow (605), Claim (581), Entity (537), Document
  (442), Core (436), Edi (427), Reference (345), User (297), Dispute/VocRehab (273
  each), Penalty (246), Calendar (201), Access (184), Compliance (114),
  CoverageInvestigation (109), AppealCase (102), JobPlacement (47), Messaging (12).
  These line up cleanly with the 18 deployed microservices (plus a `Core` bucket for
  the `CTCM.API.Shared` cross-cutting library) — domain classification worked well here.
- `project_type` and `architecture_pattern` both detected as `microservices`.

This demonstrates the skill scales to a large enterprise codebase and that the
business-domain partitioning is meaningful.

---

## 6. Limitations

> **▸ 2026-08-25 — see [§9](#9-measured-2026-08-25--the-schema-vs-output-gap-quantified) for the
> first *count* of the real output: only **5 of ~45 predicates** were ever emitted, and **§6.2
> item 4 is refuted** — `technical_layer` did not largely fail (`Other` is 15.3%, not "nearly
> every C# entity"). `content_hash` **is** present (6,047/6,047, under `attributes`).**

These come in two kinds: **inherent design limits** and **gaps observed between the
documented schema and the actual `ctcm-api` output**.

### 6.1 Inherent / by-design limitations

- **Static, syntactic extraction only.** It is grep/pattern-based ("regex/AST parsing,
  not semantic interpretation"). It cannot follow dynamic dispatch, reflection,
  dependency injection wiring, runtime configuration, or string-built SQL. Relationships
  that only exist at runtime are invisible.
- **Pattern coverage is language- and convention-specific.** The extraction `grep`s and
  the layer/domain heuristics are written around Java/Spring and C#/ASP.NET naming
  conventions (e.g. `.service.`/`.persistence.` package segments, `LES*`/`POI*` table
  prefixes). Codebases that don't follow these conventions degrade silently.
- **No call-graph depth.** "Method call" relations are described as searching for a
  method name as text — prone to false positives (overloads, same-named methods on
  different types) and false negatives, with no type resolution.
- **Heuristic classification can misfire.** Domain, layer, `project_type`, and
  `architecture_pattern` are all rule-based guesses. The validation rules only *warn*;
  they don't correct. A repo with no recognizable prefixes collapses into a large
  `Core` bucket.
- **Determinism depends on disciplined execution.** Because the "engine" is an LLM
  following a long prose spec (not a compiled tool), true run-to-run reproducibility is
  aspirational; batching, ordering, and completeness rely on the model adhering to the
  instructions.
- **Evidence is point-in-time.** Hashes detect drift but the graph itself is a snapshot;
  it must be regenerated to stay accurate.
- **Cost/scale.** A full extraction on a large repo (thousands of files) is a long,
  token-intensive job designed to run across multiple context windows.

### 6.2 Gaps observed in the actual `ctcm-api` output

Comparing the generated graph against its own schemas surfaced several real divergences
— useful to know before consuming the data:

1. **Relations omit required `file` and `line`.** The schema marks both as required, but
   real relation records contain only `id`, `type`, `source_id`, `target_id`,
   `attributes`. **Relations are therefore not individually citable to a source
   location** — a notable loss for citation/validation consumers.
2. **`confidence` is a bare number, not an object.** Output has `"confidence": 1.0`; the
   schema and SKILL.md specify `{score, reasoning}`. The `reasoning` text is absent
   everywhere, so the documented confidence-scoring rationale isn't captured.
3. **Entity field placement differs from schema.** Real entities put `visibility` at the
   top level (not under `attributes`) and use `base_type` rather than the schema's
   `superclass`/`implements` for the parent class.
4. **`technical_layer` largely failed for this codebase** — nearly every C# entity is
   tagged `"Other"`. The layer heuristics key off Java-style lowercase package segments
   (`.service.`, `.persistence.`), which don't match .NET `PascalCase` namespaces, so the
   secondary axis is effectively unusable here.
5. **Only 4 relation types were actually extracted**: `inherits` (1,826), `implements`
   (884), `contains` (1,002), `routes_to` (216). The entire **dependency** family
   (`calls`, `uses`, `imports`, `references`), **data-access** family (`reads_from`,
   `writes_to`, `queries`), and **database** family (`foreign_key`, `join`) are **absent**
   — so the graph captures structure and inheritance but not behavioral call/data flow.
6. **`packs_metadata` is thinner than documented.** Each entry has `entity_count` and
   `keywords` but **no `relation_count` or `fact_count`** (the README example shows
   both), so per-domain relation/fact totals aren't available without opening the packs.
7. **Keywords are low-value.** They're just the alphabetically-first ~20 entity names per
   domain (dominated by "a…" names like `accessservice`, `address`), truncated — not a
   curated, discriminating keyword set, which weakens keyword-based pack discovery.
8. **`fact_predicates` breakdown is missing** from `statistics`, despite being in the
   schema — so there's no top-level view of how the 38,618 facts distribute across
   predicates.
9. **LOC metrics look distorted by a `cloc` quirk.** For C# it reports
   `comment: 237,483` vs `code: 10,993` — almost certainly XML-doc/region
   misclassification. The headline `total_loc` (303,084) is dominated by lines `cloc`
   counted as comments, so "lines of code" here is not a reliable size proxy.

> **Net takeaway for consumers:** treat the `ctcm-api` graph as a strong **entity
> inventory + structural/inheritance map + property/column fact base**, but *not* as a
> reliable source of call graphs, data-flow edges, citable relations, confidence
> reasoning, or accurate LOC. Validate against source where those matter.

---

## 7. Quick reference — output layout

```
{repo}/legacylift-docs/context/
├── index.json                          # master manifest + statistics + packs_metadata
└── packs/
    ├── {domain}.entities.pack.json     # nodes
    ├── {domain}.relations.pack.json    # edges
    ├── {domain}.facts.pack.json        # grounded claims w/ evidence
    └── …  (×N domains)
```

Consumers typically: read `index.json` → pick relevant domains from `packs_metadata`
keywords/counts → load only those packs. That selective-loading design is the main
payoff of the domain-scoped split, and the reason every other LegacyLift skill is told
to run `fact-graph` first.

> **▸ 2026-08-05 — two caveats on that last sentence.** First, selective loading **is not
> actually selective in practice**: every consumer skill globs and loads *all* packs, then
> filters in memory; the `packs_metadata` keywords are never used to drive loading (see
> `fact-graph-decision.md` §2b). Second, "the reason every skill is told to run fact-graph
> first" is now only partly true — the *format* is still fact-graph-only, but most of the
> *content* consumers read is now produced deterministically by Layer 0. See §8.

---

## 8. What Layer 0 now covers (2026-08-05)

`legacylift-search` shipped Milestones 22–25 (2026-07-15/17) and the domain enhancements, which
between them absorb much of what sections 2–5 above describe. This section maps the four record
types onto their Layer-0 equivalents. The comparison and the decision live in
[`./fact-graph-decision.md`](./fact-graph-decision.md) §5a; the Layer-0 mechanics live in
`docs/exec-plans/active/code-graph-construction.md`.

### 8.1 Entities (§2.1)

| Aspect | Layer 0 today |
|---|---|
| The node itself | `symbols` table — measured ~1:1 with fact-graph entities on `ctcm-api` |
| `file`, `line_range`, `qualified_name` | Present (`qualified_name` built from a container stack) |
| **`type`** (`controller`/`dto`/`service`/…) | **Absent** — `symbols.kind` is the raw tree-sitter node type; no semantic mapping exists |
| `route`, `http_method`, `annotations` | **Present as facts** (M23) rather than entity attributes |
| `columns`, `primary_key`, `foreign_keys` | **Present** (M24 `has_column` with `data_type`/`nullable`/`primary_key`/`unique`; `foreign_key` edges) |
| `implements` / `base_type` | **Present as edges** (M22 `inherits`/`implements`) |
| `parameters`, `return_type` | **Present as edges** (M25 `accepts_dto`/`returns_dto`/`has_field_of_type`) |
| `domain` | **Present** — `file_domains` in `knowledge.sqlite`, from assess's `domains.json`, plus Chroma `domain` metadata |
| `technical_layer` | Absent (and per §6.2 item 4 it failed for .NET here anyway) |
| **`content_hash`** | **No entity-level equivalent.** Layer 0 has `repo_files.sha256`, `chunks.text_sha256`, `source_set_sha256`; and symbol IDs embed the start line, so they are not stable across edits |

Database object types (`table`, `view`, `stored_proc`, `sql_function`) are now Layer-0 symbols;
`trigger` and `index` remain on the regex path.

### 8.2 Relations (§2.2)

Layer 0's `graph_edges` covers substantially more than the **4 relation types fact-graph
actually emitted** on `ctcm-api` (§6.2 item 5): `calls`, `imports`, `references`, `uses_table`,
`uses_column`, `performs`, `executes_sql`, `executes_cics`, the Hibernate/Spring/WebFlow XML
kinds, **`inherits`/`implements`** (M22), **`foreign_key`/`associates`** (M23), and
**`has_field_of_type`/`accepts_dto`/`returns_dto`** (M25).

Two Layer-0 advantages worth noting against §6.1's "no call-graph depth" and §6.2 item 1:
every edge carries a **confidence score** (0.85 unique-name → 0.30 unresolved) and unresolved
edges are **kept** with the callee name preserved; and every edge carries `relative_path` +
`start_line`, so **edges are individually citable** — which fact-graph's actual output is not.

Still fact-graph-only: `contains`/`has_member` as explicit edges (Layer 0 keeps containment in
`qualified_name` and the container stack instead), and `has_cardinality`-style relationship
judgments.

### 8.3 Facts (§2.3)

Layer 0 has a fact store — `symbol_facts` (fact-graph-shaped: subject, predicate, object,
attributes, evidence, confidence) plus a `facts --predicate/--symbol` CLI command. It emits
**12 predicates, all read directly off AST nodes at `confidence = 1.0`**:

`http_method`, `exposes_endpoint`, `requires_auth`, `is_required`, `max_length`, `table_name`,
`is_column`, `is_id`, `has_column`, `throws`, `has_enum_value`, `has_annotation` (catch-all).

Annotation-name → intent routing is per-language JSON (`annotation_semantics`), covering ASP.NET
attributes, Spring/JPA annotations, Python decorators, and NestJS/TypeORM decorators.

**What stays fact-graph-only is the interpretive half of the predicate enum** — `business_rule`
above all, plus `validates`, `ensures`, `integrates_with`, `state_transition`, `process_step`,
`has_cardinality`, `default_value`, `publishes_to`/`subscribes_to`, `retries_on`/`timeout_after`/
`schedules_at`. None are AST-derivable. Note also that `has_property`/`has_method`/`has_field`
are Layer-0 *symbols* rather than facts, and Layer 0 is exhaustive there **including generated
code** — the blind spot §6.2 and §5 of the decision doc flag for fact-graph.

`snippet_hash` has no Layer-0 equivalent, but facts store the **full evidence text**, which
serves drift detection at least as well.

### 8.4 Index / manifest (§2.4) — the one wholly unreplaced piece

**Layer 0 has no pack emitter.** None of its 15 CLI commands writes
`legacylift-docs/context/`, so the Phase-0 contract (one `index.json`, three pack shapes per
domain, 8 helper functions, 13 consumer skills) is still served exclusively by this skill. Layer 0
exposes the same information through `stats`, `domains`, `facts`, `symbols`, `callers`/`callees`,
`coverage`, and `render-architecture` — as CLI queries against SQLite, not as a loadable JSON
artifact.

That is the gap to close if fact-graph is refactored onto Layer 0, and it is packaging rather
than data — with two genuine data additions required alongside it: **semantic entity typing**
(8.1) and **stable content-hashed IDs** (8.1, for `citation-validator`).

### 8.5 Domains (§3) — superseded

§3's bottom-up heuristics (table prefix → namespace segment → folder → `Core` fallback) are
superseded. Domains are now authored **top-down** by `modernize-assess` into a machine-readable
`domains.json` (path globs + inter-domain dependency edges + `exclude_globs`), ingested by
`legacylift-search tag-domains` into `knowledge.sqlite` (`domains`, `domain_edges`,
`file_domains`, `domain_exclusions`), and used to scope retrieval via `search --domain`.

Three ways this beats §3 concretely: domains are **grouped and capped** rather than one-per-
namespace-segment (on CTCM: 9 capability domains vs fact-graph's 19 assembly-shaped bins);
**inter-domain edges exist** (39 verified on CTCM vs fact-graph's 0 cross-domain relations); and
an **`excluded`** tier distinguishes "intentionally not a business capability" (tests, ops
scripts, generated code) from `unassigned` (a real gap), so coverage percentages are honest.

### 8.6 What this skill still uniquely provides

> ⚠️ **▸ 2026-08-25 — items 3 and 5 below are CORRECTED BY MEASUREMENT in [§9.4](#94-corrections-to-86-restated-as-measured).**
> Item 3 reduces to a single predicate (1.6% of facts); item 5's "language-agnostic" half is wrong
> — the per-language `grep` blocks are hardcoded in `SKILL.md` (§9.5). **Items 1, 2 and 4 stand**
> (an earlier draft of §9.2 wrongly reported item 4 refuted; `content_hash` is present on
> 6,047/6,047 under `attributes`).

1. The Phase-0 pack format and the 13-consumer contract (8.4).
2. Semantic entity typing — `controller`/`dto`/`service`/`repository` (8.1).
3. Inferred, judgment-bearing facts — `business_rule` and the interpretive predicates (8.3).
4. Position-independent, content-hashed entity identity (8.1).
5. **Zero install and language-agnostic reach.** It is a skill: no venv, tree-sitter, Chroma, or
   boto3; no cold index; runs anywhere Claude Code runs. Layer 0 has 7 language profiles (C#,
   Java, Python, JS, TS, COBOL, SQL) plus XML and degrades to regex or nothing outside them, so
   a VB6 / PL-SQL / Delphi / ABAP repository is a genuine fact-graph-only case.

---

## 9. MEASURED (2026-08-25) — the schema-vs-output gap, quantified

> Everything in §§2–5 and §8.6 above is read off `SKILL.md` and the JSON schemas. **This section
> is the first time the only real run on disk was counted.** It was produced while closing
> question **D7** of `reqs-to-data-store-plan-draft.md`, and it **corrects §8.6 items 3, 4 and 5**
> and adds a tenth entry to §6.2. Where §9 and §§2–8 disagree, **§9 wins — it is measurement, not
> specification.**

**Corpus:** `repos/ctcm/ctcm-api/legacylift-docs/context/` — `index.json` + 57 packs, 30 MB,
generated 2026-06-29, **the only fact-graph output tracked in git** (58 files; everything else
under `repos/` is gitignored). 6,047 entities / 3,928 relations / 38,618 facts.

### 9.1 Predicates: 5 emitted, not ~45

§4.1 advertises **~45 predicates across 10 families**. Counted across all 57 facts packs:

| Predicate | Facts | Share | Who owns it now |
|---|---|---|---|
| `has_property` | 34,488 | 89.3% | Layer-0 **symbols** (exhaustive, **including generated code** — fact-graph's own blind spot) |
| `is_required` | 1,268 | 3.3% | Layer 0 **M23** |
| `accepts_param` | 1,223 | 3.2% | Layer 0 **M25** (`accepts_dto` / `has_field_of_type`) |
| `http_method` | 1,019 | 2.6% | Layer 0 **M23** |
| **`business_rule`** | **620** | **1.6%** | **the GR store** (`reqs-to-data-store-plan-draft.md`) |

**98.4% of the facts layer is already Layer-0's. The entire non-derivable remainder is
`business_rule`, at 1.6%.**

**The interpretive half of the predicate enum emitted ZERO facts.** `validates`, `ensures`,
`integrates_with`, `authenticates_via`, `authorizes_via`, `publishes_to`, `subscribes_to`,
`stores_in`, `reads_from`, `writes_to`, `caches_in`, `logs_to`, `default_value`, `triggers_on`,
`timeout_after`, `state_transition`, `process_step`, `has_cardinality`, `returns_response` —
**0 each.** So §8.3's and `fact-graph-decision.md` §5a.2-item-3's "what stays fact-graph-only is
the interpretive half of the predicate enum" is **true of the schema and false of the output**:
there is nothing there to migrate and nothing to lose.

**Quality caveat on the 620 that do exist.** Sampled fact `fact-449e22ed2ba7`:
`object = "ObjectNotFoundException: transaction associated user"`, `confidence = 0.8`, evidence a
bare `throw new ObjectNotFoundException(...)` at `TransactionPartyManager.cs:727`. That is a
**throw statement, not a business rule** — independent corroboration of §5a.2 item 3's caveat
that `code-mod extract-rules` covers business rules better (adversarially-verified
Given/When/Then Rule Cards).

### 9.2 `content_hash` — PRESENT on all 6,047 entities (**corrected 2026-08-25, same day**)

⚠️ **A first pass of this section claimed `content_hash` was missing on all 6,047 entities. That
was wrong — it reads `attributes.content_hash`, not a top-level field, and the first check only
looked at the top level.** The corrected measurement:

| Measure | Value |
|---|---|
| `attributes.content_hash` present | **6,047 / 6,047 (100%)** |
| Format | 12 lowercase hex (48 bits) |
| Distinct values | **5,888** — 159 repeats, and at 48 bits over 6,047 items the birthday probability of a real collision is ~7x10⁻⁸, so those are **genuine identical spans (clones)**, not hash collisions |
| Equal to the id's trailing hash? | **0 of 6,047** — it is a genuinely separate value, per `calculate_content_hash(file_path, line_range)` (`SKILL.md:996`), i.e. a hash of the entity's **source span** |
| `evidence.snippet_hash` on facts | **38,618 / 38,618 (100%)** |

**So §5 claims 3 and 5 and `fact-graph-decision.md` §5a.1 items 3 and 5 STAND as written.**
fact-graph does carry position-independent identity **and** a real entity-level content hash, and
citation-validator's drift detection has both grains available to it (entity span + fact snippet).
There is **no §6.2 item 10**; the earlier draft of this section invented one.

**What SPEC-3 still improves, narrowed to what is true.** `NORMATIVE SPEC-3` §S3.1/§S3.2 in
`reqs-to-data-store-plan-draft.md` is better than this formula on three counts that are
**independent of whether a content hash exists**: the `anchor_key` inputs are joined with `\x1f`
rather than `:` (fact-graph's `generate_entity_id` at `:942-947` joins
`entity_type:qualified_name:file_path` with `:`, and both `qualified_name` and `file_path` contain
`:`, so `a:b`+`c` and `a`+`b:c` hash alike); it hashes a **coarse** `entity_class` rather than the
volatile raw `entity_type`; and it is **16 hex, not 12** — which matters for SPEC-3's stated
threat model (a collision silently merging two signed-off requirements at ~100k entities), not for
fact-graph's 6,047. And §S3.6 keeps `domain` out of the key, whereas fact-graph puts it in the
**visible id prefix** (`:912`), so a retag churns every id string.

**Net:** identity is **not** a fact-graph weakness, and it is **not** a differentiator either way
— both sides have it; SPEC-3's is better-constructed. Drop it from the comparison.

### 9.3 Entity types and relation types — §6.2 item 5 confirmed, and typing is real

**8 entity types emitted** (`dto` 2,352 · `class` 1,594 · `endpoint` 753 · `interface` 444 ·
`service` 317 · `enum` 308 · `controller` 173 · `repository` 106). Layer 0 has **no** answer for
any of these: `symbols.kind` is the raw tree-sitter node type and no mapping layer exists in the
package. **§8.6 item 2 / §8.1's typing gap is confirmed real and measurable.**

**4 relation types emitted** (`inherits` 1,826 · `contains` 1,002 · `implements` 884 ·
`routes_to` 216) — **§6.2 item 5 confirmed exactly.** Of these, Layer 0 owns
`inherits`/`implements` (M22) and `routes_to` (M23 `exposes_endpoint`); only **`contains`
(1,002)** has no Layer-0 edge equivalent, since containment lives in `qualified_name` + the
container stack.

### 9.4 Corrections to §8.6, restated as measured

| §8.6 item | Measured verdict |
|---|---|
| 1. Phase-0 pack format + 13-consumer contract | ✅ **STANDS.** The one wholly unreplaced piece. Pure packaging — Layer 0 holds every field |
| 2. Semantic entity typing | ✅ **STANDS, and is now quantified** — 8 types over 6,047 entities (§9.3) |
| 3. Inferred, judgment-bearing facts | ⚠️ **REDUCED TO ONE PREDICATE.** `business_rule`, 620 facts, 1.6% — and its sampled quality is a `throw` statement. The other ~18 interpretive predicates emitted **0** |
| 4. Position-independent, **content-hashed** entity identity | ✅ **STANDS** (corrected — an earlier draft of §9.2 wrongly reported this missing). `attributes.content_hash` on **6,047/6,047**, `snippet_hash` on **38,618/38,618**. SPEC-3's keys are better *constructed* (`` delimiter, coarse `entity_class`, 16 hex, domain excluded) but the capability is **not** a differentiator either way |
| 5. Zero install and **language-agnostic** reach | ⚠️ **"Zero install" STANDS; "language-agnostic" DOES NOT** (§9.5) |

### 9.5 "Language-agnostic" is wrong — the language logic is hardcoded in the skill

Corrected 2026-08-25 on the owner's point, then verified. fact-graph does **not** generalize
across languages; its extraction logic is **per-language `grep` blocks embedded in `SKILL.md`**:

- **§2.2 "Extraction Techniques by Language"** (`SKILL.md:653-775`) hardcodes one bash block per
  language — **C#** (`:656-671`: `public\s+class`, `:\s*ControllerBase`,
  `app\.Map(Get|Post|...)`), **Java** (`:680-693`: `@RestController`, `@GetMapping`), **Python**
  (`:701-714`: `^class\s`, `@app\.route`), **TypeScript/JavaScript** (`:719-731`), and SQL. Every
  pattern is a literal regex for that language's syntax and framework idioms.
- **The escape hatch is one sentence with no patterns.** §2.2's *Other Languages (Go, Rust, Ruby,
  PHP, etc.)* block (`:769-772`) reads, in full: *"For other languages, extract entities and save
  to entities-other.json."*
- Language coupling also appears in the file-extension map (`:266-268`), the entry-point list
  (`:279`), and the test-pairing heuristic `{Domain}Test.java` (`:438`).
- §6.1 already conceded the softer half of this ("pattern coverage is language- and
  convention-specific… codebases that don't follow these conventions degrade silently"). §9.5 is
  the harder statement: for an **unlisted** language there is no extraction path at all, only an
  unguided LLM improvisation.
- Counted mentions in `SKILL.md`: Java 52, Python 37, SQL 26, C# 15, TypeScript 8, JavaScript 5 —
  and **VB6, Delphi, ABAP, PL/SQL, COBOL: 0 each.**

**So the honest claim is narrower.** Layer 0 needs a **tree-sitter grammar + extractor profile**
for a new language; fact-graph needs **a hand-authored grep block added to `SKILL.md`**. That is
less work, and it needs no toolchain — but it is *editing the skill*, not running it. **A VB6 /
Delphi / ABAP repo is not a fact-graph capability; it is a fact-graph extension point.** The
durable operational advantage is **zero install** (locked-down client box, no venv / tree-sitter /
Chroma / boto3, no cold index) — not language reach.

### 9.6 §6.2 item 4 REFUTED — `technical_layer` did not largely fail

§6.2 item 4 says *"`technical_layer` largely failed for this codebase — nearly every C# entity is
tagged `Other`… the secondary axis is effectively unusable here."* **Measured, that is wrong:**

| `technical_layer` | Entities | Share |
|---|---|---|
| `Dto` | 2,352 | 38.9% |
| `Model` | 1,398 | 23.1% |
| `Web` | 926 | 15.3% |
| **`Other`** | **925** | **15.3%** |
| `Service` | 332 | 5.5% |
| `Persistence` | 114 | 1.9% |

`Other` is **15.3%, not "nearly every"** — the axis resolved for **84.7%** of entities. Whatever
was observed when §6.2 was written does not hold for this output. **Treat `technical_layer` as a
working secondary axis**, and note it is a *seventh* thing Layer 0 does not produce (§8.1 lists it
as "Absent (and per §6.2 item 4 it failed for .NET here anyway)" — the parenthetical is now void).

### 9.7 The exact pack contract, measured — the specification for residue (a)

Recorded so that filing the pack-emitter shim (`fact-graph-decision.md` §5a.4 residue **(a)**) as a
milestone later needs **no re-derivation**. This is the field-level shape a Layer-0 emitter must
reproduce, counted from the real output rather than from the schema.

**`index.json`** — 4 top-level keys: `metadata`, `statistics`, `packs`, `schema_version`.
- `metadata`: `repository`, `generated_at`, `tool_version`, `analysis_scope`, `project_type`,
  `architecture_pattern`
- `statistics`: `entity_count`, `relation_count`, `fact_count`, `files_analyzed`, `entity_types`,
  `relation_types`, `languages`, `lines_of_code`, **`packs_metadata`**
- ⚠️ **`packs_metadata` is nested under `statistics`, not top-level** (§6.2 item 6 discusses it as
  if top-level). It is a **list of 19** entries, one per domain, each:
  `{packId, domain, files: {entities, relations, facts}, entity_count, keywords[]}` — confirming
  §6.2 item 6 (**no `relation_count`, no `fact_count`**) and item 7 (keywords are the
  alphabetically-first ~20 entity names).
- `packs` is a **stub**: `{"note": "This repository uses domain-scoped packs. See packs_metadata
  for details."}`

**Pack files** — 4 top-level keys each: `schema`, `packId`, `domain`, and one of
`entities` / `relations` / `facts`.

| Record | Fields (count / 6,047 · 3,928 · 38,618) | Layer-0 source |
|---|---|---|
| **entity** | `id`, `name`, `qualified_name`, `type`, `file`, `line_range`, `visibility`, `attributes` — all 100%; plus `namespace` 1,397, `base_types` 926, `base_decl`/`kind`/`bases` 816 each | `symbols` + M22 edges. **`type` needs residue (b)** |
| entity `attributes` | `domain`, `technical_layer`, `language`, **`content_hash`** — all 6,047; then `route` 753, `bases` 938, `http_method` 616, `namespace`/`kind` 427, `controller` 214, `base_type` 415, `implements` 208, `base_types` 188, `http_verb`/`class_route` 137, `controller_route` 102 | `file_domains`; M23 facts; **`content_hash` ← SPEC-3 §S3.2**; `technical_layer` has no Layer-0 equivalent (§9.6) |
| **relation** | `id`, `type`, `source_id`, `target_id` — all 100%; `attributes` 2,022; `source_name`/`target_name` 710 | `graph_edges`. ⚠️ **`file`/`line` present on 0 of 3,928** — §6.2 item 1 confirmed exactly; Layer 0 *does* carry `relative_path`+`start_line` per edge, so the emitter would be **strictly better** here |
| relation `attributes` | `domain` 1,192, `target_name` 1,016, `http_method`/`route` 318, `endpoint` 194, `action` 102 | `graph_edges` + `file_domains` |
| **fact** | `id`, `subject_id`, `predicate`, `object`, `confidence`, `evidence` — all 100%; `attributes` 38,057 | `symbol_facts` (same shape). ⚠️ `confidence` is a bare float, not `{score, reasoning}` — §6.2 item 2 confirmed |
| fact `attributes` | `data_type` 34,937, `visibility` 34,488, `domain` 10,724, `action` 2,066, `param_name` 1,223, `route` 1,007, `kind` 166, `exception` 148 | `symbol_facts.attributes` |
| fact `evidence` | list of `{file, line_range, snippet, snippet_hash}` — **38,618/38,618** | `symbol_facts` evidence text + SPEC-3 §S3.2 span hash |

**The 8 helper functions the shim must keep answerable** (§2b of `fact-graph-decision.md`):
`find_entities_by_type`, `find_entities_by_domain`, `find_entity_by_name`,
`find_facts_by_predicate`, `find_relations_by_type`, `get_entity_by_id`, `get_domains`,
`get_domain_statistics`. Only **`find_entities_by_type`** has no Layer-0 answer today — which is
exactly residue **(b)**.

### 9.8 Residue (b) — what semantic typing has to produce, and the evidence that exists

The 8 `type` values actually emitted, with the Layer-0 signal available to derive each:

| `type` | Entities | Derivable from |
|---|---|---|
| `dto` | 2,352 | M25 `accepts_dto` / `returns_dto` / `has_field_of_type` targets |
| `class` | 1,594 | default for a class-kind symbol with no other signal |
| `endpoint` | 753 | M23 `exposes_endpoint` / `http_method` facts |
| `interface` | 444 | `symbols.kind` directly (tree-sitter node type) |
| `service` | 317 | naming + DI registration; **weakest signal** |
| `enum` | 308 | `symbols.kind` + M23 `has_enum_value` |
| `controller` | 173 | contains a symbol with `exposes_endpoint`; or base type via M22 (`ControllerBase`) |
| `repository` | 106 | M24 `uses_table` / `has_column` reachability, or M22 base type |

**Two of the eight (`interface`, `enum`) are already in `symbols.kind`; four
(`endpoint`, `controller`, `dto`, `repository`) are derivable from shipped M22–M25 facts and
edges; `class` is the default; only `service` needs a heuristic.** That is why §5a.2 calls this
"the smallest remaining derivable gap." ⚠️ Note the mapping is **not** `symbols.kind` renaming —
`kind` is the raw tree-sitter node type, so the pass is a **derivation over facts and edges**, and
per `NORMATIVE PRINCIPLE-1` any LLM-assisted value (realistically only `service`) must be flagged
rather than blended with derived ones.
