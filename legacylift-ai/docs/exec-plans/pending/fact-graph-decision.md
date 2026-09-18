# fact-graph — Positioning & Rationalization Decision

> **Status:** Pending decision
> **Date:** 2026-07-09 · **Updated:** 2026-08-25 (§5a.5 — the first *measurement* of fact-graph's actual output)
> **Author:** Darrell Norton (with Claude)
> **Question:** Given that LegacyLift now has (a) a `legacylift-search` semantic + graph
> index (Layer 0 retrieval) and (b) a CapTech-enhanced `code-modernization` plugin whose
> discovery skills sit on top of that index, **what is the enduring role of the
> `fact-graph` skill — and should its structural half be refactored onto legacylift-search?**
>
> **Additional info:** a deep, standalone explanation of what fact-graph collects and how,
> including the schema-vs-actual-output gaps observed on `ctcm-api`, lives alongside this
> file in [`./fact-graph-explanation.md`](./fact-graph-explanation.md). Read it for the
> full data model; this document is the comparison and the decision.

> ### ⚠️ Read §5a **and §5a.5** first — the comparison below has moved twice
>
> **Updated 2026-08-05.** Sections 1–4 and the original §5 were written 2026-07-09/13, when
> legacylift-search had no inheritance edges, no annotation awareness, no facts store, and no
> domains. **All four of those gaps have since closed** — Milestone 22 (type-hierarchy edges,
> shipped 2026-07-15), Milestones 23–25 (annotations/attributes, SQL columns/FKs, field &
> signature type refs, plus the `symbol_facts` table, shipped 2026-07-17), and the domain
> enhancements (`domains.json` → `tag-domains` → `file_domains` + Chroma `domain` metadata +
> `search --domain`, which is §6a shipped). Those milestones were *predicted* below as
> "would shrink fact-graph's unique surface"; they landed, so several statements in §2, §2a,
> §4, and §5 are now **stale as written**.
>
> Each affected section carries an inline `▸ 2026-08-05` note. **[§5a](#5a-revisited-2026-08-05--what-is-actually-left)**
> is the 2026-08-05 capability comparison; the original §5 is retained for the audit trail.
>
> **Updated again 2026-08-25 — and this time by counting, not reading.** §§1–5a all scored
> fact-graph against its *schema* and its *SKILL.md*. Nobody had counted its **actual output**.
> **[§5a.5](#5a5-measured-2026-08-25--5a-was-read-off-the-source-this-is-the-count) is now the
> authoritative statement**, and it moves the answer materially:
>
> - fact-graph emitted **5 of ~45 predicates**; **98.4% of its facts layer is already Layer-0's**,
>   and the entire non-derivable remainder is **`business_rule` — 620 facts, 1.6%**.
> - The **~18 interpretive predicates** (`integrates_with`, `state_transition`, `publishes_to`,
>   `validates`, `ensures`, …) emitted **0 facts each**. Credited as fact-graph's core; measured at
>   zero.
> - **Identity is a NON-DIFFERENTIATOR, in both directions.** `attributes.content_hash` is on
>   **6,047/6,047** and `snippet_hash` on **38,618/38,618**, so §5 claims 3 and 5 **stand**;
>   `SPEC-3`'s keys are better *constructed* (`` delimiter, coarse `entity_class`, 16 hex,
>   domain excluded) but the capability exists on both sides.
> - **"Language-agnostic" is wrong** (owner correction, verified): the per-language `grep` blocks
>   are hardcoded in `SKILL.md:653-775` and the *Other Languages* hatch is one pattern-free
>   sentence. **"Zero install" is what survives.**
> - Of the four §5a.4 residue pieces, **(c) is closed by `NORMATIVE SPEC-3`, (d) is homed in the
>   GR store, and (a)+(b) — the pack emitter and semantic typing — are scheduled on NO plan.**
>   ⚠️ The plan usually described as retiring fact-graph does not contain the work to retire it.
> - **§5a.6 adds a third unowned piece, (e):** `anchor_key` gives Layer 0 a stable key but does
>   **not** re-key `symbols.id`, which is still `language:path:qualified_name:start_line`
>   (`extractors.py:1112-1115`) with five surfaces keyed off it. **Open question #6 was
>   over-claimed as "answered" and is re-scoped.** All three pieces are **documented to
>   file-ready detail but deliberately NOT filed** (owner decision 2026-08-25).

---

## 1. The landscape — three overlapping graphs over the same code

LegacyLift now contains **three separate pipelines that each build a graph-shaped
representation of a codebase**, none of which consume each other today:

| Layer | Component | What it is | Trust posture |
|---|---|---|---|
| **0 — Retrieval** | `legacylift-search` | Hybrid vector (Bedrock Titan; Qwen3/hash as fallbacks) + BM25/FTS5 search over code chunks, plus a confidence-scored graph in SQLite covering calls, imports, data access, **type hierarchy (M22)**, and **annotation/type-ref relations (M23/M25)**; a **`symbol_facts` store (M23–25)**; an exact-name symbol table; **capability-domain tagging with domain-scoped search**; and a freshness check. Deterministic, incremental. | Output is **untrusted data** — certifies nothing. |
| **1 — Interpretation** | `fact-graph` | LLM-authored JSON knowledge base: entities + relations + **facts**, domain-scoped packs, in `legacylift-docs/context/`. | Meant as a **source of truth** for doc skills. |
| **1 — Deliverables** | `code-modernization` `assess` / `map` / `extract-rules` | Human-facing artifacts: `ASSESSMENT.md`, interactive `topology.json`/`TOPOLOGY.html`, Given/When/Then Rule Cards. Now use legacylift-search as their discovery floor. | Rule Cards adversarially verified (referee + P0 panel). |

The core tension: **legacylift-search now covers the retrieval and syntactic-graph value
that fact-graph partially duplicates**, and it does so deterministically, with edge
confidence, with preserved unresolved edges, and incrementally — arguably *better* than
fact-graph on those structural axes. So fact-graph's defensible unique value must be found
above retrieval.

---

## 2. What each tool holds — measured on the same 5 files (`ctcm-api`)

We pulled the actual data for 5 files present in **both** the live legacylift-search index
(58k chunks) and the fact-graph packs (6,047 entities / 3,928 relations / 38,618 facts).
Files spanned the spectrum: two small controllers, a large controller, a hand-written DTO
file, and a generated XML/EDI model.

**Findings (concrete, not theoretical):**

- **The structural unit is ~1:1.** legacylift-search *symbols* ≈ fact-graph *entities*
  (PenaltyController 11≈11, DocumentController 45=45). Same code atoms.
- **fact-graph types them semantically; legacylift-search types them syntactically.**
  fact-graph: `controller`/`endpoint`/`dto` + `domain`/`technical_layer` tags +
  `route`/`http_method`. legacylift-search: `class_declaration`/`method_declaration`/
  `property_declaration` only.
- **Chunks are legacylift-search-only** — the embeddable/BM25 retrieval payload (11 → 207
  per file). fact-graph has no chunk concept.
- **The call graph is legacylift-search-only.** Edges: Penalty 70, Filing 36, Document 132
  — call-level, with confidence 0.30–0.85 and resolved/unresolved flags. fact-graph
  "relations" are only `contains`/`inherits`/`routes_to` (no line, no confidence, no
  method-invocation edges).
- **Facts are fact-graph-only.** SPO triples with evidence lines + confidence
  (`http_method`, `accepts_param`, `has_property`, …). legacylift-search has no analog.
- **"Exhaustive" means opposite things.** legacylift-search is exhaustive at chunk/member
  level *everywhere* (even 207 generated XSD fields). fact-graph is exhaustive at
  property-fact level for hand-written DTOs (91 facts on `ClaimServiceDtos.cs`) but
  near-empty for generated code (0 facts on `ProofOfCoverage.cs`).

**Neither is a superset:** legacylift-search has the call graph fact-graph lacks;
fact-graph has the facts and semantic typing legacylift-search lacks.

> **▸ 2026-08-05 — two of these five findings are now stale.** "**Facts are fact-graph-only**"
> is no longer true: M23–25 added a `symbol_facts` table and a `facts` CLI command emitting 12
> deterministic predicates with evidence and confidence (see §5a). "**fact-graph types them
> semantically; legacylift-search syntactically**" still holds for the *entity type*
> (`controller`/`dto`/`service` — legacylift-search has no such mapping) but no longer for
> `route`/`http_method`, which M23 now extracts as facts. The other three findings (1:1
> structural unit, chunks-only-in-Layer-0, opposite meanings of "exhaustive") stand unchanged.

### 2a. Correction (2026-07-13): legacylift-search's graph is *behavioral*, not *type-hierarchical* — ✅ RESOLVED 2026-07-15

> **▸ 2026-08-05 — this entire section is now HISTORY.** It describes the state of the code on
> 2026-07-13 and its recommendation ("extend legacylift-search to extract inheritance edges —
> now specced as Milestone 22") **was implemented and validated on 2026-07-15**. legacylift-search
> now emits `inherits` and `implements` edges: **2,750 hierarchy edges on `ctcm-api`
> (`inherits` 2,112 + `implements` 638)**, the same order of magnitude as the fact-graph baseline
> this section cites (1,826 + 884 ≈ 2,710), with 13.0% unresolved external framework bases held
> at confidence 0.30. A stash-and-rebuild A/B proved zero regression to call/reference edges.
> C# `base_list` ambiguity is resolved from the target symbol's kind, falling back to the
> `^I[A-Z]` .NET interface heuristic when the base is external.
>
> **So the "Option A has a real gap" conclusion at the bottom of this section no longer applies** —
> option (1) was taken. The section is retained because its *reasoning* (why the gap existed
> structurally, and why chunk text is not a substitute for a resolved edge) is still the clearest
> explanation of the distinction between text-retrievable and query-able structure.

> **Trigger question:** "Can agents get the same information (e.g. `inherits`) from
> legacylift-search's vector stores, chunks, and full-text index — or would that be part of
> the graph data? Aside from the canonical ID." Answered by reading the actual v4 code
> (`tools/legacylift_search/src/legacylift_search/{models,store,graph,extractors}.py` +
> `profiles/extractors.json`), not the summaries above. This corrects the framing in §2
> and §5/§6 that treated legacylift-search as strictly superior on *all* structural axes.

**Short answer: no — `inherits`/`implements`/`extends` are NOT recoverable as structured
data from legacylift-search today.** Its graph is deliberately a **call/reference graph**
(the plan calls it a "caller/callee graph"), not a type-hierarchy graph. Inheritance
survives only as **raw text inside chunks** — lexically searchable and semantically
retrievable, but you get the source line back and must re-parse the `: Base` clause
yourself. It is not a queryable, resolved, confidence-scored edge.

What each store actually holds (verified in code):

| Store | Holds | Inheritance? |
|---|---|---|
| `symbols` table | Nodes typed by syntactic `kind` (`class_declaration`, `method_declaration`, …). The `Symbol` model has **no `base_type`/`superclass`/`implements` field.** | **No** — a class is a node; its parent is not recorded. |
| `graph_edges` table | Caller/callee edges w/ confidence + preserved unresolved edges | **No** — see edge kinds below. |
| `chunks` + FTS5 (`store_full_chunk_text_in_sqlite: true`) | Full source text, lexically searchable | **Text only** — `class Foo : BaseController` is findable; parse-it-yourself. |
| Chroma vectors | Qwen3/Bedrock embeddings of chunk text | **Text only** — semantic retrieval of the declaration, same caveat. |

**Why it's absent (structural, not incidental).** `GraphBuilder._edge_kind_from_ref`
(`graph.py`) enumerates every edge kind the graph can emit — `calls`, `performs`,
`executes_sql`, `executes_cics`, `uses_table`, `uses_column`, `maps_to`, `associates`,
`instantiates`, `invokes_subflow`, `transitions_to`, `imports`, `references` — with **no
`inherits`/`implements`/`extends`.** And it *couldn't* emit one: the extractor never creates
a ref from an inheritance clause, because no profile's `call_node_kinds` includes the
base-type node (C# `base_list`, Java `superclass`/`super_interfaces`, TS/JS `class_heritage`,
Python `superclasses`), and the regex fallbacks require a `(` that `class Foo : Bar` lacks.
`grep -E 'inherit|base_list|superclass|extends|implements'` over `extractors.py` → zero hits.

**What legacylift-search's graph HAS that fact-graph lacks** (so §2's "superset" caveat
still holds the other direction): resolved **call** edges (`invocation`/`object_creation`)
with confidence 0.30–0.85 and preserved unresolved edges, `imports`, SQL `uses_table`/
`uses_column`, and framework/XML edges (Hibernate `maps_to`/`associates`, Spring
`instantiates`, WebFlow `transitions_to`) — none of which fact-graph produced on `ctcm-api`.

**Bottom line for the decision.** On `ctcm-api`, ~74% of the fact-graph relations the doc
skills actually consume are inheritance (`inherits` 1,826 + `implements` 884 of the 4
relation types produced). So **Option A ("let Layer 0 own structure") has a real gap** until
type-hierarchy edges exist in legacylift-search — otherwise a refactored fact-graph sourcing
structure from Layer 0 would silently drop the class-hierarchy relations. Two ways to close
it: (1) extend legacylift-search to extract inheritance edges — now specced as **Milestone 22**
in `docs/exec-plans/active/semantic-code-search-graph-index.md` (four-layer change: profiles
→ extractor → graph-builder → tests; unresolved external base types kept at confidence 0.30),
or (2) keep inheritance derivation inside fact-graph's own layer. Prefer (1): it's a small,
well-scoped change legacylift-search arguably should have anyway, and it keeps Option A clean.

**Follow-on (2026-07-13): inheritance is not the only extractable gap — and closing the
others shrinks fact-graph's "unique" surface. ✅ ALL SHIPPED 2026-07-17 — see §5a for the
result.** A `dump-ast` sweep found several more
first-class AST nodes legacylift-search currently ignores but tree-sitter hands over cleanly,
now specced as **Milestones 23–25** in the index plan: **annotations/attributes/decorators**
(routes, HTTP verbs, authz, validation, JPA/EF mapping — legacylift-search has zero annotation
awareness today), **SQL columns/constraints/foreign keys** (data model + FK graph), and
**field-type + signature edges** (associations, typed API surface, DTO-usage). Critically,
these are largely the **facts and relations §5 below calls fact-graph's unique, non-redundant
core** (`has_column`, `is_required`, `http_method`, `foreign_key`, `routes_to`, `uses_dto`).
Extracting them deterministically at Layer 0 requires a new fact-graph-shaped `symbol_facts`
table — i.e. **Layer 0 begins to absorb fact-graph's facts layer**. The more of §5 that Layer 0
can produce deterministically, the more fact-graph's defensible residue narrows to only the
genuinely *inferred* facts that need LLM judgment — which strengthens the Option-A case
(fact-graph as a thin interpreted layer) rather than weakening it. Revisit §5's "enduring
core" list once M23–25 land.

> **▸ 2026-08-05 — M23–25 landed 2026-07-17; this paragraph's prediction held exactly.** All
> three shipped, plus the `symbol_facts` table and `facts` CLI command this paragraph called
> for. Layer 0 now emits `has_column` (with data type / nullability / PK / unique attributes),
> `is_required`, `max_length`, `http_method`, `exposes_endpoint`, `requires_auth`, `table_name`,
> `is_column`, `is_id`, `throws`, `has_enum_value`, and a `has_annotation` catch-all — plus
> `foreign_key`, `associates`, `has_field_of_type`, `accepts_dto`, `returns_dto` edges. That is
> essentially the whole list this paragraph named as fact-graph's "unique, non-redundant core."
> **§5's "enduring core" list is hereby revisited in §5a**, and the residue did narrow to the
> genuinely inferred facts as predicted, so the Option-A case is stronger, not weaker.

### 2b. How the 13 downstream skills consume the graph — the Phase-0 contract

> Recorded 2026-07-13 from a read of the skills under `.claude/skills/`. This is the
> consumer side of the decision: what re-pointing fact-graph onto Layer 0 (Option A) must
> preserve. It is the reference target for open question #1 and the §6a mention of
> "load *all* packs and filter in-memory."

**One shared protocol.** Every consumer follows an identical **Phase 0: Load Fact Graph**
step, defined canonically in `.claude/skills/FACT-GRAPH-INTEGRATION.md` and copy-pasted into
each skill. It runs *before* the skill's own analysis and has three parts:

1. **Load** — check for `legacylift-docs/context/index.json`; if present, read the index
   (`metadata`, `statistics`, `packs_metadata`) then glob-load **every** pack file into three
   flat in-memory arrays (`entities`, `relations`, `facts`).
2. **Query** — a fixed helper API over those arrays, identical in every skill:
   `find_entities_by_type`, `find_entities_by_domain`, `find_entity_by_name`,
   `find_facts_by_predicate`, `find_relations_by_type`, `get_entity_by_id`, `get_domains`,
   `get_domain_statistics`.
3. **Fork** — a hard `if fact_graph_loaded: … else: …` branch; every downstream phase has a
   fallback path that re-derives the same thing with grep/glob/Explore. **No skill hard-depends
   on fact-graph** — it is strictly an optimization.

**The 13 consumers** (from `FACT-GRAPH-INTEGRATION.md`): 7 doc generators (`si-`, `business-`,
`data-`, `exec-summary-`, `database-layer-`, `detailed-req-`, `data-dictionary-`), 2
requirements/use-case (`use-case-generator`, `user-story-generator`), 4 validation/review
(`table-validation`, `gap-analyzer`, `documentation-review`, `citation-validator`).

**Three findings that bear on the decision:**

1. **"Selective loading" is not selective.** The layout is domain-partitioned packs, but every
   skill globs and loads *all* packs then filters in memory with `find_entities_by_domain()` —
   even the domain-scoped ones. The `keywords` in `packs_metadata` are never used to drive
   loading. So the partitioned file layout buys almost nothing at consumption time. (This is
   what §6a's domain-tagging note would actually make useful.)
2. **Consumption is shallow and inventory-oriented.** What's actually read: LOC stats,
   `project_type`/`architecture_pattern`, entity-type counts, and entity lists by type/domain.
   Relations are barely touched; facts are mostly reached via a single `business_rule`
   predicate query. The parts consumers lean on hardest are exactly what Layer 0 already
   produces — the unique-to-fact-graph *facts* layer is the **least-exercised** part of the
   contract.
3. **citation-validator is the one distinct consumer.** It doesn't use fact-graph for content;
   it uses the entity `content_hash` (and evidence `snippet_hash`) for drift detection and to
   skip file reads for entity-anchored citations (~30–40% fewer reads).

**Implication for Option A.** The contract is narrow and uniform: one path
(`index.json`), one dir (`packs/`), a fixed pack schema, 8 helper functions, and every consumer
already has a working non-fact-graph fallback. So it can be re-pointed at a
legacylift-search-backed fact-graph **without a breaking migration**, provided a shim reproduces
`index.json` + the three pack shapes + the `content_hash`/`snippet_hash` fields citation-validator
needs. That directly answers open question #1: yes, stable enough.

> **▸ 2026-08-05 — this is now the *primary* blocker, and it is packaging, not data.** With
> M22–25 shipped, Layer 0 holds the great majority of what these 13 skills read — but
> **legacylift-search has no pack emitter**: its 15 CLI commands (`init-config`, `index`,
> `backfill-vectors`, `validate`, `search`, `symbols`, `callers`, `callees`, `facts`,
> `tag-domains`, `domains`, `render-architecture`, `stats`, `coverage`, `dump-ast`) include
> nothing that writes `legacylift-docs/context/`. So the Phase-0 fast path still resolves to
> fact-graph output for every consumer. Finding 2 above ("consumption is shallow and
> inventory-oriented — the parts consumers lean on hardest are exactly what Layer 0 already
> produces") makes the shim the highest-leverage single piece of Option A. Two concrete gaps
> the shim must fill beyond reformatting: **semantic entity `type`** (`find_entities_by_type('controller')`
> has no Layer-0 answer — see §5a item 2) and **stable content-hashed IDs** for
> citation-validator (§5a item 4).

---

## 3. What fact-graph offers *above* the file/code level

At the higher level, fact-graph provides a **two-axis classification of the whole system**:

1. **System classification** — `project_type: microservices`, `architecture_pattern:
   microservices`, plus repo-wide counts and a `cloc` LOC block.
2. **19 business domains** (the pack partition) with entity counts and keyword vocabularies.
3. **6 technical layers** as a cross-cutting axis (`Dto 2352 · Model 1398 · Web 926 ·
   Other 925 · Service 332 · Persistence 114`).

**The critical limitation:** these are **bins, not a graph**. On `ctcm-api`:

- **Cross-domain relations = 0.** All 3,928 relations are intra-domain. Relation types are
  only `inherits / contains / implements / routes_to`. Despite labeling the system
  "microservices," fact-graph captures **nothing about how the services depend on each
  other**.
- **`capability` sub-level is unpopulated (0).**
- **`fact_predicates` rollup is empty** at the index level despite 38,618 facts existing.

So fact-graph's high level is a **taxonomy/partition**, not an **architecture graph**.

> **▸ 2026-08-05 — items 2 and 3 are now duplicated or superseded; item 1 belongs to assess.**
> Item **2** (the 19-domain partition) is superseded: Layer 0 carries assess-authored capability
> domains natively, *with* the inter-domain edges this section notes are missing — so the
> "bins, not a graph" limitation is resolved on the Layer-0 side (`domain_edges`,
> `render-architecture`). Item **3** (`technical_layer`) is not replicated anywhere, but per
> §6.2 item 4 of the explanation doc it **largely failed on this .NET codebase anyway** (nearly
> every C# entity tagged `Other`), so little is lost. Item **1** (system classification +
> `cloc`) is duplicated by `modernize-assess` (`ASSESSMENT.md`, stack fingerprint, COCOMO) —
> not by Layer 0 — and assess's version does not suffer the `cloc` comment-misclassification
> distortion recorded in §6.2 item 9. Net: **nothing in §3 remains a fact-graph-only
> capability.**

---

## 4. Domain determination — bottom-up vs top-down (the sharpest contrast)

The two tools derive domains in **opposite directions**, which we measured directly by
running code-mod `assess`'s Step-3 domain analysis (`legacy-analyst` agent) against CTCM.

| | fact-graph | code-mod `assess` |
|---|---|---|
| Direction | **Bottom-up** — classify each entity by namespace/prefix heuristic | **Top-down** — LLM reasons about the whole system |
| Grouping | None — every distinct namespace segment is its own domain | Explicitly told to **cluster** subsystems |
| Count control | Guardrails on domain *size*, **not count** | Hard cap **5–12** |
| Inter-domain deps | **Not produced** (0 edges) | **Required** (control flow + shared data) |
| **CTCM result** | **19 domains = 19 service assemblies** (+ a `Core` catch-all) | **9 capability domains + 39 verified edges** |

**Was "one domain per microservice" instructed or assumed? — Neither; it was generalized.**
fact-graph's literal `classify_entity` heuristic is hardcoded to the NNG/PLE codebase
(`LES*`→LegalEntity, `point`→Points…) and matches almost nothing in CTCM. Claude followed
the skill's *stated intent* ("extract the business-domain segment from the namespace") and
applied it to CTCM's `CTCM.API.<X>Service` structure — where the namespace segment
literally *is* the service name. With no grouping step and no count cap, that
deterministically yields 19 domains ≈ 19 assemblies. Nothing says "one domain per service";
it is an emergent consequence of a per-entity, uncapped, namespace-segment rule meeting a
codebase whose packages are named by capability.

**The code-mod / fact-graph mapping (18 business domains → 9):**

| fact-graph (19, = assemblies) | → code-mod (9, = capabilities) |
|---|---|
| Claim | Claims Management |
| Dispute, AppealCase, Calendar | Dispute Adjudication & Scheduling |
| Penalty, Compliance, CoverageInvestigation | Enforcement & Compliance |
| Filing, Edi | Regulatory Filing & EDI |
| VocRehab, JobPlacement | Voc Rehab & Return-to-Work |
| Entity, Reference | Master Data & Reference |
| Document | Document Management |
| Workflow, Messaging | Workflow Orchestration, Calc & Messaging |
| User, Access | Identity & Access Management |
| Core | *(no domain — the `CTCM.API.Shared` cross-cutting library)* |

code-mod's grouping is **evidence-backed** (each merge verified against `AddCtcmService` DI
registrations) and surfaced architecture fact-graph structurally cannot: Workflow is the
hub (11 clients), Dispute↔Calendar and Filing↔Edi are **bidirectional cycles**,
MessagingService is **async-only / invisible to HTTP dependency scans**, and the ~30
calculator controllers inside WorkflowService are a plausible **10th target-state domain**.

For CTCM specifically, fact-graph's 19 aren't *wrong* — the services are cleanly named — but
they are **19 un-grouped, un-connected bins**, whereas code-mod's **9 capability domains
with 39 verified edges** are what you'd take into a modernization-sequencing conversation.

> **▸ 2026-08-05 — the winner of this comparison now lives *inside* Layer 0.** The domain
> enhancements shipped (§6a below, marked SHIPPED): `modernize-assess` emits a machine-readable
> `domains.json` (path globs + inter-domain edges + `exclude_globs`), `legacylift-search
> tag-domains` ingests it into a `knowledge.sqlite` (`domains`, `domain_edges`, `file_domains`,
> `domain_exclusions`) and stamps each chunk's Chroma `domain` metadata with no re-embedding.
> `search --domain` does domain-scoped hybrid retrieval; `domains` and `render-architecture`
> report and draw the result. **So the assess-quality domains this section argues for are now
> the shared substrate's native domain model**, and fact-graph's bottom-up namespace partition
> is not merely inferior — it is redundant. This is the single largest change to the decision
> since 2026-07-13: it removes "but fact-graph owns domain identity" as an argument entirely.

---

## 5. Conclusion (2026-07-09) — fact-graph's enduring, non-redundant core

> **▸ 2026-08-05 — SUPERSEDED BY [§5a](#5a-revisited-2026-08-05--what-is-actually-left).**
> Items 1 and 4 below are no longer accurate, and item 3 needs a caveat. This section is kept
> verbatim as the pre-M22–25 baseline so the delta is auditable. Read §5a for the current answer.

Strip away everything legacylift-search now provides, and fact-graph's defensible unique
value is a tight set:

1. **Facts as a queryable, evidence-grounded type** (SPO triples) — no analog anywhere else.
2. **A persistent, machine-consumable interpreted artifact** other skills query (the Phase-0
   contract) — vs. legacylift-search (retrieval input) and code-mod (terminal deliverables).
3. **Stable, shared entity identity** across all documentation (content-hashed IDs).
4. **A referential-integrity-validated unified model** (code + DB + domain + facts).
5. **Citation-drift hashing** (`content_hash`/`snippet_hash`) feeding `citation-validator`.

**Redundant / now inferior:** fact-graph's structural half (entities + call relations,
domain tagging) duplicates — and underperforms — legacylift-search, which is deterministic,
confidence-scored, keeps unresolved edges, and re-indexes incrementally. fact-graph also has
no adversarial verification (extract-rules does) and produces no inter-domain dependency
graph (map/assess do).

---

## 5a. Revisited (2026-08-05) — what is actually left

> ⚠️ **▸ 2026-08-25 — READ [§5a.5](#5a5-measured-2026-08-25--5a-was-read-off-the-source-this-is-the-count) WITH THIS SECTION.**
> §5a scored claims against the *implementation* and against fact-graph's *schema*; §5a.5 counts
> fact-graph's **actual output** for the first time. It corrects **§5a.1 claims 3 and 5** (no
> both hash grains are real — `attributes.content_hash` 6,047/6,047 and `snippet_hash`
> 38,618/38,618, so identity is a non-differentiator either way), shrinks **§5a.2 item 3** to a single predicate
> (1.6% of facts), refutes the "language-agnostic" half of **§5a.2 item 5**, and re-scores the
> **§5a.4** residue: **(c) is closed by `NORMATIVE SPEC-3`, (d) is homed in the GR store, and
> (a)+(b) are unowned — scheduled on no plan.** Measurement wins over specification.

This is the §5 revisit that §2a's follow-on called for. Checked against the implementation, not
the summaries: `store.py`, `extractors.py`, `graph.py`, `cli.py`, `knowledge_store.py`,
`domain_tagger.py`, `profiles/extractors.json`.

### 5a.1 Scoring the original five claims

| §5 claim | Status | Evidence |
|---|---|---|
| 1. Facts as a queryable, evidence-grounded type — "no analog anywhere else" | **Mostly false** | `symbol_facts` (`store.py:346`) + `facts --predicate/--symbol` (`cli.py:899`); 12 predicates, evidence text, confidence, indexed by predicate and subject |
| 2. A persistent machine-consumable interpreted artifact (the Phase-0 contract) | **Still true** | No pack emitter exists in Layer 0 — see the §2b update |
| 3. Stable, shared entity identity (content-hashed IDs) | **Still true — and Layer 0 is actively worse** | Layer-0 symbol id is `lang:path:qualified_name:line`; the embedded line number means any edit *above* a symbol changes its ID |
| 4. A referential-integrity-validated unified model | **Superseded** | SQL FKs + PK dedupe enforce this structurally and continuously, not as a phase-5 pass; code and SQL symbols share one `symbols` table with `uses_table`/`foreign_key` edges crossing them |
| 5. Citation-drift hashing (`content_hash`/`snippet_hash`) | **Partly** | Layer 0 has `repo_files.sha256`, `chunks.text_sha256` (+ `symbol_id`, so symbol-derived chunks do carry a per-symbol content hash), `source_set_sha256`, and stores full fact evidence text — but no *entity*-keyed hash bound to a stable ID |

### 5a.2 What fact-graph genuinely still has

1. **The Phase-0 delivery format.** 13 skills load `legacylift-docs/context/index.json` +
   domain packs through 8 fixed helpers. Layer 0 has no equivalent emitter, so every consumer's
   fast path still resolves to fact-graph. A packaging gap, not a data gap — but a live one.

2. **Semantic entity typing.** `controller` / `endpoint` / `dto` / `service` / `repository` /
   `model`. Layer 0's `symbols.kind` is the raw tree-sitter node type and **no mapping layer
   exists anywhere in the package**. M23 supplies the *evidence* to derive it (an
   `exposes_endpoint`/`http_method` fact effectively marks an endpoint; `table_name` marks a
   persistent entity) but never assigns the type, so `find_entities_by_type('controller')` has
   no Layer-0 answer. **The smallest remaining derivable gap** — and a prerequisite for the
   Option-A shim.

3. **Inferred facts requiring judgment — the genuinely defensible residue.** Layer 0's predicate
   set is exactly 12, every one read straight off an AST node at `confidence = 1.0`:
   `http_method`, `exposes_endpoint`, `requires_auth`, `is_required`, `max_length`, `table_name`,
   `is_column`, `is_id`, `has_annotation`, `has_column`, `throws`, `has_enum_value`. fact-graph's
   schema additionally covers `business_rule`, `validates`, `ensures`, `integrates_with`,
   `state_transition`, `process_step`, `has_cardinality`, `default_value`, `publishes_to` /
   `subscribes_to`, `retries_on` / `timeout_after` / `schedules_at`. **None of these are
   AST-derivable** — this is exactly the "thin interpreted layer above Layer 0" that Option A
   describes. Caveat: `code-mod extract-rules` covers business rules *better* (adversarially
   verified Given/When/Then Rule Cards) but emits markdown, not queryable triples.

4. **Position-independent identity.** Content-hashed IDs survive edits; Layer-0 symbol IDs do
   not (5a.1 item 3). For `citation-validator`'s cross-document entity anchoring — the one
   distinct consumer per §2b — that is a regression, not a wash.

5. **Two operational advantages the earlier analysis never credited.** fact-graph is a *skill*:
   zero install, no venv / tree-sitter / Chroma / boto3, no ~100-minute cold index, runs on any
   machine where Claude Code runs — which matters on a locked-down client box or a one-off
   engagement. And it is **language-agnostic**, whereas Layer 0 has 7 language profiles (C#,
   Java, Python, JS, TS, COBOL, SQL) plus XML and degrades to regex or nothing outside them. A
   VB6 / PL-SQL / Delphi / ABAP repository is a real fact-graph-only case.

### 5a.3 What has been absorbed since 2026-07-13

Credited to fact-graph in §2/§2a/§4/§5, no longer defensible:

- **Inheritance relations** — §2a's headline gap, ~74% of the relations consumers actually read.
  M22: 2,750 validated hierarchy edges on `ctcm-api` vs fact-graph's ~2,710.
- **Routes / HTTP verbs / authz / validation / JPA-EF mapping** — §2a called these fact-graph's
  "unique, non-redundant core." M23 emits them as facts with evidence.
- **SQL columns, constraints, foreign keys** — M24: `has_column` carrying
  `data_type`/`nullable`/`primary_key`/`unique`, plus regex-supplemented FK edges.
- **DTO / association / signature relations** (`uses_dto`, `accepts_dto`, `returns_dto`) — M25.
- **Domains** — §4's and §6a's whole subject. Now Layer 0's native domain model, sourced from
  assess's top-down, capped, grouped, edge-verified `domains.json`, with an `excluded` tier that
  keeps coverage% honest.
- **Gap / coverage analysis** — the `coverage` command (`cli.py:1426`).

Worth keeping in view: fact-graph's *measured* `ctcm-api` output produced only 4 relation types
and facts dominated by `has_property` / `has_column` / `http_method` — precisely the
deterministic subset Layer 0 now owns. **The real overlap is considerably worse for fact-graph
than its schema implies** (see `fact-graph-explanation.md` §6.2 and §8).

### 5a.4 Consequence for the decision

Option A got materially stronger, and the residue is now sharp enough to spec. A refactored
fact-graph reduces to four things:

| Piece | Nature |
|---|---|
| (a) a pack-emitter shim over `symbol_facts` / `symbols` / `graph_edges` / `file_domains` | deterministic, Layer-0 side |
| (b) a semantic-typing pass over Layer-0 symbols | deterministic, Layer-0 side |
| (c) content-hashed, position-independent entity IDs | deterministic, Layer-0 side |
| (d) LLM-inferred facts Layer 0 cannot derive (`business_rule`, `state_transition`, …) | genuinely needs an LLM |

Only (d) needs a model. (a)–(c) are ordinary work on the Layer-0 side, and (c) is a Layer-0
design issue (line-bearing symbol IDs) that is worth fixing independently of this decision.
The standalone fact-graph skill should be retained as the fallback path for the two operational
cases in 5a.2 item 5 (no-install hosts; languages with no extractor profile).

---

### 5a.5 MEASURED (2026-08-25) — §5a was read off the source; this is the count

> §5a scored the five §5 claims against the *implementation* (`store.py`, `extractors.py`, …) and
> against fact-graph's *schema*. It never counted fact-graph's actual output. Closing question
> **D7** of `reqs-to-data-store-plan-draft.md` did. Full tables:
> [`fact-graph-explanation.md` §9](./fact-graph-explanation.md#9-measured-2026-08-25--the-schema-vs-output-gap-quantified).
> **Where §5a.5 and §5a.1–5a.4 disagree, §5a.5 wins — it is measurement, not specification.**

**Corpus:** the 58 tracked files under `repos/ctcm/ctcm-api/legacylift-docs/context/` (30 MB, run
of 2026-06-29) — the only fact-graph output in git. 6,047 entities / 3,928 relations / 38,618
facts.

⚠️ **Self-correction, same day.** A first pass of this section reported `content_hash` missing on
all 6,047 entities and filed it as a new §6.2 item. **That was wrong** — the field is
`attributes.content_hash`, and the first check only looked at the top level. It is present on
**6,047/6,047**. §5 claims 3 and 5 therefore **stand**, and identity is a non-differentiator
rather than a fact-graph weakness. The rows below are the corrected scoring.

#### Corrections to §5a.1's scoring

| §5 claim | §5a.1 said | Measured verdict |
|---|---|---|
| 1. Facts as a queryable, evidence-grounded type | "Mostly false" | **Confirmed, and understated.** fact-graph emitted **5 predicates, not ~45**: `has_property` 34,488 (89.3%), `is_required` 1,268, `accepts_param` 1,223, `http_method` 1,019, **`business_rule` 620 (1.6%)**. Layer 0 already owns the first four. **98.4% of the facts layer is Layer-0's**; the whole non-derivable remainder is `business_rule` |
| 3. Stable, shared entity identity (content-hashed IDs) | "**Still true — and Layer 0 is actively worse**" | ✅ **STANDS.** ⚠️ *A first pass of §5a.5 wrongly reported this refuted — it read a top-level `content_hash`; the field lives under `attributes`.* Corrected: `attributes.content_hash` on **6,047/6,047**, 12 hex, **5,888 distinct** (the 159 repeats are clones — a real 48-bit collision here has probability ~7x10⁻⁸), and **equal to the id's trailing hash on 0 of 6,047**, i.e. a genuine span hash per `calculate_content_hash` (`SKILL.md:996`) |
| 5. Citation-drift hashing (`content_hash`/`snippet_hash`) | "Partly" | ✅ **STANDS — both grains are real.** `attributes.content_hash` 6,047/6,047 **and** `evidence.snippet_hash` 38,618/38,618. §2b finding 3's citation-validator advantage **does** exist in the data |

**Knock-on: §5a.2 item 3 and §8.3 are true of the schema and false of the output.** The
"interpretive half of the predicate enum" — `validates`, `ensures`, `integrates_with`,
`authenticates_via`, `authorizes_via`, `publishes_to`, `subscribes_to`, `stores_in`, `reads_from`,
`writes_to`, `caches_in`, `logs_to`, `default_value`, `triggers_on`, `timeout_after`,
`state_transition`, `process_step`, `has_cardinality`, `returns_response` — emitted **0 facts
each**. Nothing there to migrate, nothing to lose. And the 620 `business_rule` facts that exist
are shallow: sampled `fact-449e22ed2ba7` is
`object = "ObjectNotFoundException: transaction associated user"` off a bare `throw` at
`TransactionPartyManager.cs:727` — a throw statement, not a business rule. That is the §5a.2-item-3
caveat (extract-rules covers business rules better) confirmed from data.

#### Two claims that got STRONGER

- **§5a.2 item 2 — semantic entity typing.** Quantified: **8 types over 6,047 entities** (`dto`
  2,352 · `class` 1,594 · `endpoint` 753 · `interface` 444 · `service` 317 · `enum` 308 ·
  `controller` 173 · `repository` 106). Layer 0 answers none of them.
- **§6.2 item 5 confirmed exactly** — 4 relation types (`inherits` 1,826 · `contains` 1,002 ·
  `implements` 884 · `routes_to` 216). Layer 0 owns `inherits`/`implements` (M22) and `routes_to`
  (M23); **only `contains` (1,002) has no Layer-0 edge equivalent.**

#### §5a.2 item 5 — "language-agnostic" is WRONG (owner correction, 2026-08-25, then verified)

fact-graph's language handling is **hardcoded per-language `grep` blocks inside `SKILL.md`**, not a
general mechanism. §2.2 "Extraction Techniques by Language" (`SKILL.md:653-775`) has one bash
block each for **C#** (`:656-671`), **Java** (`:680-693`), **Python** (`:701-714`),
**TypeScript/JavaScript** (`:719-731`) and SQL — literal regexes for that language's syntax and
framework idioms. The *Other Languages (Go, Rust, Ruby, PHP, etc.)* escape hatch (`:769-772`) is
**one sentence with no patterns**: *"For other languages, extract entities and save to
entities-other.json."* Language coupling also sits in the extension map (`:266-268`), the
entry-point list (`:279`), and the `{Domain}Test.java` test heuristic (`:438`). Mention counts:
Java 52, Python 37, SQL 26, C# 15, TS 8, JS 5 — **VB6, Delphi, ABAP, PL/SQL, COBOL: 0 each.**

**So the operational advantage is narrower than §5a.2 item 5 and §5 claim set out.** Adding a
language costs Layer 0 a tree-sitter grammar + extractor profile, and costs fact-graph a
hand-authored grep block in `SKILL.md`. Cheaper and toolchain-free — but it is **editing the
skill, not running it**. A VB6 / Delphi / ABAP repo is a fact-graph **extension point, not a
capability**. **What survives is "zero install"** (locked-down client box; no venv, tree-sitter,
Chroma or boto3; no ~100-minute cold index) — that half is unaffected and unfixable by any Layer-0
work.

#### §5a.4 residue, re-scored

| Piece | 2026-08-05 | Status 2026-08-25 |
|---|---|---|
| **(a)** pack-emitter shim | deterministic, Layer-0 side | ⚠️ **STILL WHOLLY OPEN — AND UNOWNED.** Pure packaging; Layer 0 holds every field. **Not a milestone anywhere:** `semantic-code-search-graph-index.md` has M17, M18, M20, M21, M22, M23–25, M26, M27 and **no pack-emitter milestone** |
| **(b)** semantic-typing pass | deterministic, Layer-0 side | ⚠️ **STILL OPEN — AND UNOWNED.** Now quantified (8 types / 6,047 entities). **Also not a milestone anywhere.** §5a.2 calls it "the smallest remaining derivable gap" |
| **(c)** content-hashed, position-independent entity IDs | deterministic, Layer-0 side | ✅ **CLOSED BY SPEC — `NORMATIVE SPEC-3` §S3.1/§S3.2** in `reqs-to-data-store-plan-draft.md`: `anchor_key` as a computed column on `symbols`, `content_hash` at two grains. It is **better-constructed** than fact-graph's formula on four counts — `` delimiter (fact-graph joins with `:`, and both `qualified_name` and `file_path` contain `:`), a coarse `entity_class` rather than the volatile raw `entity_type`, 16 hex not 12, and `domain` excluded from the key rather than sitting in the visible id prefix (`:912`). ⚠️ **But this is a construction improvement, not a capability gap:** fact-graph *does* emit both hashes (see claims 3 and 5 above). **Identity is a non-differentiator in both directions** |
| **(d)** LLM-inferred facts Layer 0 cannot derive | genuinely needs an LLM | ✅ **HOMED — the GR store**, per **Q7** of `reqs-to-data-store-plan-draft.md` (decided *add, don't retire*). Measured scope is far smaller than the schema implied: **one predicate, 620 facts, 1.6%** |

⚠️ **The finding that matters for the roadmap.** Two of the four residue pieces are closed or
homed; the two that remain — **(a) and (b)** — are **deterministic, well-scoped, and scheduled
nowhere**, and [§5a.6](#5a6-the-three-unowned-layer-0-pieces-2026-08-25--documented-so-they-can-be-filed-without-re-derivation)
adds a **third, (e): re-keying `symbols.id` so the PK is not line-bearing** — the open half of what
"fixing the stable IDs" means, which SPEC-3 does **not** do.** The plan generally described as "the one that retires fact-graph"
(`semantic-code-search-graph-index.md`) **does not contain the work required to retire it.** They
exist only as prose in this section. Until they are filed as milestones the way M26/M27 were,
"retire fact-graph" is not an executable statement.

**Corrected end state.** Not "Option A plus a language-agnostic fallback" (open question #5's
framing) but: **Option A, plus fact-graph retained as a zero-install escape hatch whose
per-language grep blocks must be authored per engagement.**

---

### 5a.6 The THREE unowned Layer-0 pieces (2026-08-25) — documented so they can be filed without re-derivation

> **Not filed as milestones.** The owner deliberately deferred filing (decision 2026-08-25) and
> asked only that the information be complete enough to make that call later. This section is that
> record. `reqs-to-data-store-plan-draft.md` **declares a dependency** on all three; it owns none
> of them.

Residue **(c)** and **(d)** are closed (§5a.4). What remains is three deterministic Layer-0 tasks,
none of which appears as a milestone on any plan:

| # | Piece | Specification already written | Blocking what |
|---|---|---|---|
| **(a)** | **Pack-emitter shim** — write `legacylift-docs/context/` from Layer 0 | [`fact-graph-explanation.md` §9.7](./fact-graph-explanation.md) — the **measured** field-level contract: every `index.json` key, all four record shapes with per-field counts, the Layer-0 source per field | **fact-graph retirement.** All 13 Phase-0 consumers resolve their fast path here. M21 cannot conclude "replace" without it, no matter how its tasks score |
| **(b)** | **Semantic-typing pass** over Layer-0 symbols | [`fact-graph-explanation.md` §9.8](./fact-graph-explanation.md) — the 8 `type` values with the shipped M22–M25 signal for each: 2 already in `symbols.kind`, 4 derivable from existing facts/edges, `class` the default, only `service` needing a heuristic | `find_entities_by_type` — the **only** one of the 8 Phase-0 helpers with no Layer-0 answer. Also a prerequisite for (a) |
| **(e) NEW** | **Re-key `symbols.id` so the PK is not line-bearing** | §5a.6.1 below | Nothing today. It is the difference between *having* a stable key and *being* stably keyed |

#### 5a.6.1 Piece (e) — what "fix the stable IDs" actually requires

⚠️ **This corrects an over-claim.** §7 open question #6 was recorded on 2026-08-24/25 as
*"answered — fix it in Layer 0, via `NORMATIVE SPEC-3` §S3.1."* **That is too strong.** SPEC-3 adds
a stable key **beside** the unstable primary key; it does not re-key `symbols`. Both halves matter
and they are different work.

**What SPEC-3 §S3.1 delivers (Milestone 1 of the GR-store plan, additive):** `anchor_key` as a
**computed column** on `symbols` — `sha256(language ␟ entity_class ␟ qualified_name ␟
normalized_relative_path)`, 16 hex, no line numbers, no domain. This is the first
position-independent key Layer 0 has ever had, and it discharges residue **(c)** as §5a.4 framed
it ("content-hashed, position-independent entity IDs — deterministic, Layer-0 side").

**What it does NOT do — `symbols.id` is unchanged and still line-bearing:**

```python
# extractors.py:1112-1115
sym_id = (
    f"{source_file.language}:{source_file.relative_path}:"
    f"{qualified}:{rng.start_line}"
)
```

So an edit *above* a symbol still mints a new id on the next index, and the row is deleted and
re-inserted rather than updated. **Five surfaces key off it** (all in `store.py`):

| Surface | Line | Kind |
|---|---|---|
| `symbols.id` | `:209` | `TEXT PRIMARY KEY` |
| `graph_edges.caller_symbol_id` | `:309` | `FOREIGN KEY … REFERENCES symbols(id) ON DELETE CASCADE` |
| `graph_edges.callee_symbol_id` | `:310` | `FOREIGN KEY … REFERENCES symbols(id) ON DELETE SET NULL` |
| `symbol_facts.subject_symbol_id` | `:359` | `NOT NULL`, `FOREIGN KEY … ON DELETE CASCADE` |
| `chunks.symbol_id` | `:216` | plain column (no FK) |
| `symbol_refs.enclosing_symbol_id` | `:278` | plain column, indexed at `:293` |

**Consequence, stated precisely:** on reindex after an edit, affected symbols get new ids and the
cascade **discards their edges and facts**. That is harmless *today*, because all 12 Layer-0
predicates are deterministic and regenerated from the AST at `confidence = 1.0` — nothing durable
hangs off a symbol row. **It stops being harmless the moment anything judgment-bearing does.**
(Note `chunks.id` is separately unstable — `chunk:{path}:{language}:{chunk_index}:{sha}`,
`chunking.py:143`/`:222`/`:295` — which is a different problem with the same shape.)

**Why the GR store is nonetheless safe without (e).** SPEC-3 §S3.3 makes `anchor_key` **advisory
only, never an FK target**. The durable citation anchor is `(relative_path, start_line, end_line)`;
`gr_id` (a ULID surrogate) is the sole FK target. §S3.3's principle — *"the distinction is not
stable vs unstable, it is recoverable vs unrecoverable"* — is exactly what insulates the GR store
from (e) being open: a stale path+range still points somewhere and `citation-validator` can repair
it, whereas a dead id offers nothing to repair from.

**Scope of (e) if filed:** re-key the PK to `anchor_key` (or add it as a second unique key and
migrate the references), migrate the two FK constraints and the three plain columns, and verify
through an actual **edit-and-reindex cycle**. That last part is not optional — SPEC-3 §S3.7 records
that **none of this identity design has ever been exercised that way**, by fact-graph or by
Layer 0, because fact-graph regenerates its JSON wholesale. (e) wants its own verification, not a
ride-along on Milestone 1.

**Now buildable, which it was not before.** Deferred question **D3** of the GR-store plan (decided
2026-08-25) builds `PRAGMA user_version` + ordered forward-only migrations for **both** DBs as its
**Milestone 0**. Before that there was no `ALTER TABLE` anywhere in `src/`, no `PRAGMA
user_version`, and `SCHEMA_VERSION = "1"` was written (`indexer.py:666`) but never compared — so a
column change meant `index --reset`. **(e) was not merely unowned; it was unimplementable.**

#### 5a.6.2 Why all three belong here rather than in the GR-store plan

Same reasoning that placed **M26** and **M27** on `semantic-code-search-graph-index.md`: these are
**Layer-0 concerns**, and fixing them there benefits every consumer — `table-validation`,
`data-documenter`, `data-dictionary-generator`, `database-layer-documenter`, `/modernize-map`, and
the 13 Phase-0 skills — not just the GR store. The GR-store plan **declares the dependency and
owns none of the repair.**

**None of the three gates GR-store Milestone 1.** (a) and (b) are fact-graph-retirement work;
(e) is insulated by §S3.3's advisory-link design. **Milestone 1 ships unchanged whether or not any
of them is ever filed** — which is precisely why deferring the filing decision costs nothing.

---

## 6. Options for the decision

- **Option A — Refactor fact-graph onto Layer 0 (recommended for evaluation).**
  Have fact-graph *source* its entities and structural edges from the legacylift-search
  index instead of re-deriving them with an LLM, and keep only what is genuinely its own:
  the **Facts layer, stable entity identity, the integrity-validated model, and
  drift-hashing**. Let Layer 0 own structure; fact-graph becomes a thin interpreted-knowledge
  layer above it. This is the same "retrieval vs. judgment" split the code-mod plugin already
  committed to — fact-graph just hasn't been moved onto it yet.

- **Option B — Keep fact-graph standalone, fix the observed output gaps.**
  Retain the current architecture but address the `ctcm-api` divergences documented in the
  additional-info file (missing relation `file`/`line`, bare `confidence`, `technical_layer`
  failing on .NET, only 4 relation types extracted, empty `fact_predicates`, distorted LOC).
  Lower engineering risk; leaves the structural duplication and the 0-cross-domain-edge
  limitation in place.

- **Option C — Deprecate fact-graph's structural output; adopt code-mod domains.**
  Use legacylift-search for structure/retrieval and code-mod `assess`/`map` for
  domains + dependency topology, and reduce fact-graph to a pure facts/citation store
  (or fold its facts into the extract-rules pipeline). Most consolidation, highest churn for
  the 13 downstream doc skills that depend on the Phase-0 contract.

**Recommendation:** evaluate **Option A** first — it preserves the downstream Phase-0
consumer contract while removing the structural redundancy and inheriting Layer 0's
confidence-scored, incrementally-fresh graph. Revisit domain generation separately: adopt a
code-mod-style **top-down, capped, grouped** domain step (with inter-domain edges) rather
than the current bottom-up namespace partition, regardless of which option is chosen.

> **▸ 2026-08-05 — the recommendation stands and is now cheaper; its second half is done.**
> The "revisit domain generation separately" sentence has been **executed** — assess-quality
> domains are Layer 0's native domain model (§4 and §6a updates). And Option A's scope has
> shrunk to the four pieces in §5a.4, of which only the inferred-facts layer needs an LLM.
> Option B (keep standalone, fix the gaps) has weakened correspondingly: several of the
> `ctcm-api` divergences it proposes to fix — missing relation types, the absent dependency /
> data-access / database relation families, the failed `technical_layer` axis — are now moot
> because Layer 0 produces that data deterministically. Option C is unchanged in substance but
> note it would still need §5a.4's (a)–(c) to avoid breaking the 13 consumers.
>
> **One gate to respect before acting:** Milestone 21 in
> `semantic-code-search-graph-index.md` is the "does the index beat fact-graph in the actual
> workflow" evaluation, and it is still open. §5a is a capability comparison read off the
> source; M21 is the task-based, rubric-scored version. Do not treat §5a as a substitute for it —
> but §5a should now inform M21's task set, since the interesting comparisons have moved
> (inheritance, routes, columns, and domains are no longer differentiators).

---

## 6a. Design note (2026-07-13): tag the Layer-0 index with `assess` domains — ✅ SHIPPED

> Captures a design direction explored after the options above. It operationalizes the
> "revisit domain generation separately" line in the §6 recommendation and open question #2,
> and materially de-risks Option A. ~~Not yet committed work.~~
>
> **▸ 2026-08-05 — SHIPPED. This design was built essentially as specified.** What landed:
>
> - **`domains.json` from assess** (point 1) — `/modernize-assess` authors it with path globs,
>   inter-domain edges, *and* `exclude_globs`; `/modernize-map` consumes it. `domains.json` is
>   the single canonical domain set.
> - **Side-table, not a chunk column** (point 2) — a separate **`knowledge.sqlite`** holds
>   `domains` (authored catalog), `domain_edges` (authored dependencies), `file_domains`
>   (one primary domain per file, `source` ∈ `glob`/`manual` with manual-wins), and
>   `domain_exclusions`. It lives *outside* the index dir, so clearing the index does not clear
>   domain tagging. `tag-domains` is the single idempotent reconcile point, with reaping for
>   dropped domains and deleted files.
> - **Chroma `domain` metadata + a `--domain` filter** (the "concrete work" line) — tagging
>   stamps each chunk's `domain` key with **no re-embedding**, and `search --domain` scopes
>   retrieval: the vector arm passes `where={"domain": …}`, the lexical arm filters to in-domain
>   paths and **re-enumerates ranks densely before RRF** so an in-domain hit at global rank 150
>   gets the weight its in-domain position deserves. Plus `domains` and `render-architecture`
>   commands.
> - **Two freshness axes** (point 3) — implemented and reported as a distinct "fresh index,
>   stale domains" state.
> - **Fallback bucket** (point 4) — went further than the note anticipated: **two** reserved
>   `file_domains` values, neither ever a `domains` row. `unassigned` = matched no glob (a real
>   coverage gap); `excluded` = matched an `exclude_globs` pattern (tests, ops/DBA scripts,
>   generated code), **dropped from the coverage denominator**. On the NNG app that moved
>   reported coverage from 69% to an honest 100%.
>
> The note's **known limitation still stands**: domains are assigned at *file* granularity, so a
> chunk whose symbol belongs to a different domain than its file (mostly Shared/Core assemblies)
> is not separately resolvable. Still a later refinement, not a blocker.
>
> **Net effect on this decision:** the de-risking this note promised is now banked. A
> fact-graph refactored onto Layer 0 inherits the *better* domains for free.

**The idea:** back-annotate every legacylift-search chunk with the capability domain it
belongs to, using `modernize-assess`'s domains as the source — so the shared retrieval
substrate carries the *good* (top-down, grouped, edge-verified) domains instead of leaving
domain identity to fact-graph's inferior bottom-up namespace partition (§4).

**Sequencing — a back-annotation pass, not a reorder.** The index already sits *underneath*
assess (`legacy-analyst` queries `search`/`symbols`/`callers` to do its domain sweep — see
`code-modernization-layer0-retrieval.md`). So you cannot run chunk/embed *after* assess
without breaking that discovery dependency. Instead add a third pass:

```
Pass 1  index          chunk + embed + symbols + graph        (no domains yet)
Pass 2  assess         consumes index → capability domains + which files belong to each
Pass 3  tag  (new)     join each chunk → domain, write as metadata   ← no re-embed
```

**Feasible and cheap, because domain is metadata, not content.** Embeddings are computed over
`chunk.text` only (`vector_store.upsert_chunks`), so tagging is a metadata write and *never*
a re-embed. Chunks already carry `relative_path`; assess already returns domains at
**file-path granularity** ("which source files belong to each … cite repo-relative paths"),
so the join is a deterministic path→domain lookup. Adding a `"domain"` key to the Chroma
per-chunk metadata immediately enables `where={"domain": …}` filtered vector search (the
`query()` method needs a small `where` param added — it passes none today).

**Four things to get right:**

1. **Assess must emit domains machine-readably.** Today the domain→files mapping is a
   markdown table + `ARCHITECTURE.mmd` (human-facing). Add a small `domains.json`
   (`domain → path prefixes/globs` + inter-domain edges) to the assess skill so it can serve
   as a join key; parsing the markdown is the fragile alternative.
2. **Store as a side-table, not a chunk column** — `chunk_domains(chunk_id, domain,
   confidence, source_run)`, mirroring the existing `vectors_present` pattern. Domain tags
   are a re-runnable LLM judgment; chunks are content-addressed and rebuilt incrementally.
   Keying on path means most tags survive incremental reindex, and tagging can re-run without
   touching immutable chunk rows.
3. **Two independent freshness axes.** The index is deterministically fresh
   (`source_set_sha256`); domain tags are not — they go stale when files are added or move
   between domains. Record the producing assess run and mark newly-added-but-untagged chunks,
   so "fresh index, stale domains" is a loud, distinct state.
4. **Edge cases need a fallback bucket** — unclassified files, generated code, and
   Shared/Core files that span domains. The side-table makes multi-domain tagging trivial; a
   column would not.

**Payoff:** domain-scoped semantic search and real per-domain coverage denominators; and it
hands the Phase-0 doc-skill consumers assess-quality domains natively (they currently load
*all* packs and filter in-memory by fact-graph's weaker domains — see §2b).
**This is what de-risks Option A:** if Layer 0 carries assess-quality domains, a refactored
fact-graph sourcing structure from Layer 0 inherits the *better* domains for free rather than
re-deriving the worse ones — turning §4's "assess beats fact-graph on domains" from a
criticism into an architectural asset.

**Known limitation:** assess assigns domains at *file* granularity. A chunk whose *symbol*
belongs to a different domain than its file (rare — mostly Shared assemblies) would need
symbol/namespace-level domain mapping, which assess does not produce today. A later
refinement, not a v1 blocker.

**If pursued, the concrete work** (prospective milestone for
`semantic-code-search-graph-index.md`): `domains.json` output from assess + a `chunk_domains`
side-table + Chroma `domain` metadata + a `--domain` filter on `search`.

---

## 7. Open questions for sign-off

*(Status updated 2026-08-05.)*

1. **Is the Phase-0 consumer contract (13 doc skills) stable enough to re-point at a
   legacylift-search-backed fact-graph without a breaking migration?** — **Answered: yes**, per
   §2b (narrow, uniform, every consumer has a fallback). Now reframed as *work*, not a question:
   build the pack-emitter shim, and with it semantic entity typing and stable content-hashed IDs
   (§5a.4 (a)–(c)).
2. **Should domains become a shared notion across all three tools?** — **Answered and shipped:
   yes.** One canonical `domains.json` authored by assess, ingested into Layer 0 by
   `tag-domains`, consumed by map and by domain-scoped search. See the §6a update.
3. Do we want fact-graph facts to inherit extract-rules' adversarial verification (referee /
   P0 panel), or is confidence-scoring sufficient for the doc-generation use case? — **Still
   open, and now better-scoped — and §5a.5 makes it nearly moot:** the judgment-fact layer
   measures **one predicate, 620 facts, 1.6% of output**, and its sampled quality is a `throw`
   statement read as a business rule. Verification for that population is what the GR store's Q5
   review loop and extract-rules' P0 panel already do.** It only applies to the *inferred* facts (§5a.2 item 3); the 12
   deterministic Layer-0 predicates are read off AST nodes at confidence 1.0 and need no panel.
   So the question is narrower than when first written: verification for judgment-facts only.
4. Is the generated-code blind spot (0 facts on XSD/EDI models) acceptable, given
   legacylift-search indexes those members for retrieval anyway? — **Still open**, unchanged.
5. **New (2026-08-05); RE-SCOPED 2026-08-25.** Should the standalone fact-graph skill be retained
   as a fallback? **Yes, but for ONE reason, not two.** ⚠️ §5a.5 refutes the language half: the
   per-language `grep` blocks are hardcoded in `SKILL.md` (`:653-775`) and the *Other Languages*
   escape hatch is one sentence with no patterns (`:769-772`), so an unlisted language is an
   **extension point, not a capability** — reaching VB6 / PL-SQL / Delphi / ABAP means authoring a
   grep block per engagement. **What stands is zero install** (locked-down host; no venv,
   tree-sitter, Chroma or boto3; no cold index). Corrected end state: "Option A **plus a
   zero-install escape hatch whose language blocks are authored per engagement**."
6. **New (2026-08-05); ⚠️ PARTLY ANSWERED — RE-SCOPED 2026-08-25, see [§5a.6.1](#5a61-piece-e--what-fix-the-stable-ids-actually-requires).** The earlier "answered — fix it in Layer 0" was **over-claimed**: SPEC-3 adds a stable key **beside** the unstable PK, it does not re-key `symbols`. **Answered half:** `anchor_key` is a Layer-0 computed column, so stable identity is Layer 0's responsibility, not fact-graph's — residue **(c)** discharged. **Open half (now piece (e)):** `symbols.id` is still `language:path:qualified_name:start_line` (`extractors.py:1112-1115`) and five surfaces key off it, so an edit still churns ids and cascades edges/facts away. Harmless while all 12 predicates are deterministic; not harmless once anything durable hangs off a symbol. **Unowned, and only now implementable** (the GR plan's D3 Milestone 0 supplies the migration mechanism that did not exist). Layer-0 symbol IDs embed
   the start line and are not edit-stable (§5a.1 item 3). **`NORMATIVE SPEC-3` §S3.1 in
   `reqs-to-data-store-plan-draft.md` is the answer**: `anchor_key` becomes a computed column on
   `symbols`, so identity is Layer-0's, not a fact-graph-layer responsibility. This discharges
   §5a.4 residue **(c)**. ⚠️ §5a.5 narrows this: fact-graph's hashes **do** work
   (`attributes.content_hash` 6,047/6,047), so moving identity to Layer 0 is not repairing a broken
   capability — it is putting the key where the symbols live, with a better-constructed formula
   (fact-graph's carries all four defects SPEC-3 §S3.1 enumerates: `:` delimiter, volatile raw
   `entity_type`, 12 hex, `domain` in the visible id).

---

## Related documents

- [`./fact-graph-explanation.md`](./fact-graph-explanation.md) — **additional info**: full
  data model, 7-phase process, schema-vs-actual-output gaps for `ctcm-api`, and (§8) the
  record-type-by-record-type map of what Layer 0 now covers.
- `docs/exec-plans/active/semantic-code-search-graph-index.md` — the legacylift-search index
  plan; M22–25 shipped, **M21 (the value comparison against fact-graph) is still open** and is
  the task-based counterpart to §5a. ⚠️ **§5a.5 carries a correction for M21's task set** (the
  facts layer is no longer a differentiator either) and records that **§5a.4 residue (a) — the
  pack emitter — and (b) — semantic typing — are milestones on no plan, including this one.**
- `docs/exec-plans/pending/reqs-to-data-store-plan-draft.md` — the GR store. **`NORMATIVE SPEC-3`
  closes §5a.4 residue (c)** and §7 open question #6; **Q7 homes residue (d)** there, scoped to
  *adding* the Layer-1 store, not retiring fact-graph. **D7 (decided 2026-08-25): zero
  consumers re-point** — see its Decision Log.
- `docs/exec-plans/active/code-graph-construction.md` — how Layer 0 actually builds symbols,
  edges, facts, and domain tags today. The reference for any §5a claim about Layer-0 capability.
- `docs/exec-plans/completed/code-modernization-layer0-retrieval.md` — the Layer-0
  integration that wired legacylift-search under the code-mod discovery skills.
- `docs/exec-plans/completed/domain-enhancements-plan.md` — the shipped domain work behind the
  §6a update (authoritative for the standing domain design decisions).
