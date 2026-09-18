# Requirements Extraction: LegacyLift Skills vs. code-modernization Plugin

> **Status: SUPERSEDED (2026-07-07).** This analysis became `docs/exec-plans/completed/code-modernization-layer0-retrieval.md`, whose `Background` section reproduces this document's §6.1 and §7 in full. That plan is complete (all 6 milestones shipped and validated, including a live-session run). This file is retained for historical context only; do not treat it as an active plan.
>
> **Original status:** Pending — analysis draft intended to become an execution plan.
> **Scope:** Compares the LegacyLift documentation skills against Anthropic's `code-modernization` plugin, focusing on (1) whether their analysis artifacts are mergeable and (2) how each approaches gathering, completeness, and accuracy of "requirements."
> **Audience:** LegacyLift maintainers.

---

## 1. Context

LegacyLift's skills and the `code-modernization` plugin both ingest a legacy codebase and extract structured knowledge from it. They were designed independently and converged on several of the same ideas (`file:line` citations, a structured intermediate artifact, business-rule extraction as a first-class output), but they answer fundamentally different questions:

- **LegacyLift** — *"Document what the system does."* Output: enterprise-grade markdown documentation for humans.
- **code-modernization** — *"Mine what the business requires, then prove a rewrite preserves it."* Output: analysis artifacts → human approval gate → transformed/new code with a behavior-equivalence test harness.

This document examines the two at the data-model and process level to determine what is worth adopting from each.

### Source artifacts examined

**LegacyLift:**
- `.claude/skills/fact-graph/templates/{entity,fact,relation,index}.schema.json` — the fact-graph data model
- `.claude/skills/business-documenter/SKILL.md`, `.claude/skills/detailed-req-documenter/SKILL.md` — requirements generation
- `docs/architecture.md` — skill conventions, phases, citation standards

**code-modernization:**
- `commands/modernize-extract-rules.md`, `commands/modernize-brief.md`
- `agents/business-rules-extractor.md`
- `workflows/extract-rules.js` — the loop-until-dry orchestration

---

## 2. Are the analysis artifacts mergeable?

### 2.1 The two data models side by side

| | LegacyLift fact-graph | code-modernization analysis |
|---|---|---|
| **Unit** | Entity / Relation / Fact triple-store (RDF-like) | Rule Card + Data Object + `topology.json` |
| **Format** | Strict JSON Schema (draft-07), validated | Markdown (`BUSINESS_RULES.md`) + loose `topology.json`; the workflow enforces JSON schemas internally but discards them on write |
| **Granularity** | Fine: every class/method/table/column is a node | Coarse: only "rules worth preserving" + DTOs + call graph |
| **Identity** | Deterministic IDs (`cs:orders-orderservice-abc123`) | Filename + `file:line` citation; no stable IDs |
| **Citation** | `evidence[].file + line_range` (structured array) | `source: "path:line-line"` (string) |
| **Confidence** | Numeric `0.0–1.0` + reasoning string | Enum `High/Medium/Low` + SME question |
| **Drift detection** | `content_hash` / `snippet_hash` (SHA-256, 12 char) | None — staleness is mtime comparison only |
| **Domain model** | `domain` / `technical_layer` / `capability` triad per entity | Flat; "domain" is informal grouping in prose |
| **Completeness goal** | Exhaustive map of the code | Selective — "prioritize calculation/validation/eligibility over plumbing" |

### 2.2 How each store is populated

The two stores are built by methods at opposite ends of the extraction spectrum. This difference explains both their strengths and the one place they overlap awkwardly.

| | LegacyLift fact-graph | code-modernization extract-rules |
|---|---|---|
| **Method** | Deterministic, pattern-driven `grep` — *"No guessing, no inference, no LLM interpretation. Every fact must be grounded in verifiable code evidence"* (`fact-graph/SKILL.md`) | Semantic agent sweep — three "lens" agents read raw code and reason about intent |
| **Iteration unit** | File patterns, batched by language (Java, C#, Python, TS/JS, SQL) and by record type | `(lens × round)` — agents re-sweep the whole system each round |
| **Pipeline** | Fixed 7 phases: Discovery → Domain Classification → Entities → Relations → Facts → Validation → Serialization | Loop: extract → verify → P0 panel → data objects |
| **Coverage model** | "Scan all files" — exhaustive *by construction*; every matched file contributes | Probabilistic — loops until two consecutive rounds find nothing new; *declares the gap* if it stops at `maxRounds` first |
| **Verification of a claim** | Structural only — file paths resolve, line ranges in bounds, IDs unique, references valid | Adversarial — a separate referee agent re-reads the cited lines; `confirmed` / `refuted` / `wrong-citation` |
| **Confidence** | Self-assigned numeric score (1.0 explicit keyword → <0.5 excluded) with reasoning string | Self-assigned `High/Medium/Low`, then *independently re-judged* for P0 rules |

**The fact-graph's populate method, in brief** (`fact-graph/SKILL.md`, 7 phases):

1. **Discovery** — Glob source files (excluding build artifacts / `legacylift-docs`); run `cloc` for LOC metrics.
2. **Domain Classification** — the conceptual core. A deterministic `classify_entity()` assigns each entity a **business domain** (from DB table prefixes like `LES*`/`POI*`, namespace segments, or folders; fallback `Core`) and a **technical layer** (from `.service.`/`.persistence.` segments, `Dao`/`Controller` suffixes). Sanity-checked (warn if `Core` > 15%, or one domain > 70%).
3. **Entity Extraction** — `grep` patterns *per language*, batched with TodoWrite checkpoints. Each entity gets a deterministic ID (`{prefix}:{domain}-{name}-{sha256[:12]}`) and a `content_hash`.
4. **Relation Extraction** — 5 batches: inheritance, containment, dependencies, database (FKs/ORM), metadata (decorators/routes).
5. **Fact Extraction** — 5 batches producing claims, each with a confidence score and `snippet_hash`. `business_rule` / `state_transition` facts come from grep patterns like `if.*amount.*>` or `@PostMapping`.
6. **Validation** — every path exists, every line range in bounds, every reference resolves, no duplicate IDs.
7. **Serialization** — group by domain, sort by ID (determinism), write `index.json` + domain packs; clean up `temp/`.

**Where the two methods collide:** the fact-graph's `business_rule` extraction is the **weakest part of an otherwise rigorous deterministic pipeline** — it is grep-for-`if`-statements with a self-assigned confidence score and **no independent verification**. Everywhere else, determinism is a strength (you cannot hallucinate a `CREATE TABLE`); but business rules are exactly where pattern-matching breaks down and semantic judgment is unavoidable. This is precisely the gap code-modernization's referee + P0-panel fills.

**Implication for the work items in §5:** items #1–#5 are *not* a wholesale replacement of the fact-graph's method. They harden the **one fact type** (`business_rule`) where grep-determinism is insufficient — adding the semantic extraction, independent verification, and criticality axis that the rest of the deterministic pipeline neither needs nor benefits from.

### 2.3 Verdict: one direction is clean, the other is lossy

**fact-graph → code-modernization (clean, high value).** The fact-graph is a strict *superset* of what `extract-rules` discovers, and its schema already contains the exact predicates code-modernization mines by hand:

- `predicate: "business_rule"`, `"validates"`, `"state_transition"`, `"is_required"`, `"min_value"`, `"max_value"`, `"pattern_matches"` → these *are* the Rule Card categories (Calculation / Validation / Lifecycle / Policy).
- fact-graph `evidence[].file + line_range` → maps directly to Rule Card `source: path:line-line`.
- fact-graph entities of `type: dto/model` with `attributes.columns/parameters` → the `DATA_OBJECTS.md` catalog, essentially for free.
- The `relations` (`calls`, `routes_to`, `EXPOSES_ENDPOINT`) → the call graph that `topology.json` rebuilds independently.

A fact-graph could feed code-modernization's pipeline and **skip `assess` / `map` / `extract-rules` discovery almost entirely** — exactly the redundancy code-modernization's `analysis/` artifacts were invented to avoid. The data is the same data; LegacyLift just captured it more rigorously.

**code-modernization → fact-graph (lossy, needs a parser).** Going the other way is harder because the Rule Cards are *markdown prose*, and they carry concepts the fact schema has no slot for:

- **Priority (P0/P1/P2)** — no equivalent. fact-graph has numeric confidence but no business-criticality axis. This is code-modernization's single most valuable field and it would be *dropped* on import.
- **Given/When/Then specification** — fact-graph's `object` is a scalar (string/number/bool/null). A three-part behavioral spec doesn't fit; it would have to be stuffed into a stringified blob or the schema extended.
- **`suspectedDefect`** and **`smeQuestion`** — no slot. These are judgment artifacts, not code facts.
- **`injectionSuspects`** — no slot (fact-graph has no threat model).

### 2.4 Concrete merge path

They are **mergeable through the fact-graph as the canonical store**, with two schema extensions:

1. Add `priority` and a structured `specification` object (given/when/then) to `fact.schema.json` for `predicate: business_rule` facts.
2. Add optional `sme_question` and `suspected_defect` to the fact `attributes`.

Then: run `fact-graph` once → derive code-modernization's `BUSINESS_RULES.md` / `DATA_OBJECTS.md` / `topology.json` as *views* over the fact-graph rather than as independently-extracted artifacts. The `content_hash` / `snippet_hash` fields (which code-modernization lacks entirely) would give the modernization pipeline **drift detection it currently does by mtime** — a real upgrade for code-mod.

**The blocker is not data shape — it's provenance trust.** code-modernization treats its inputs as untrusted and *re-derives every rule from cited code* before use. It would not blindly trust an imported fact-graph; it would still run its referee pass over the imported facts. So the merge saves *discovery* effort but not *verification* effort — by design.

---

## 3. Requirements: gathering, completeness, accuracy

Both systems extract "requirements" from code, but they answer three different questions: *how do you find them, how do you know you found them all, and how do you know they're right?*

### 3.1 How requirements are GATHERED

| | LegacyLift (`business-documenter` / `detailed-req-documenter`) | code-modernization (`extract-rules`) |
|---|---|---|
| **Mental model** | "Document what the system does" — requirements *derived* from endpoints, services, validators, state machines | "Mine what the business requires" — explicitly *separate* business intent from incidental implementation |
| **Output unit** | `FR-XXX-001` functional requirements + `BR-XXX` business rules, in prose tables, grouped by domain | Rule Cards: Given/When/Then with concrete values, priority, parameters, edge cases |
| **What's in scope** | Everything: tech stack, architecture, data, integrations, *and* business rules | Deliberately narrow: calculations, validations, eligibility, state transitions, policies — **explicitly excludes** "anything that exists only because of the technology" |
| **Derivation source** | Endpoints→use cases, service methods→FRs, validation facts→rules, state_transition facts→workflows (literal mappings in SKILL.md) | Three "lenses" (calculations / validations & eligibility / state & lifecycle) read raw code directly |
| **Concrete values** | Not required — prose describes the rule | **Mandatory**: "Given balance $1,250.00 and APR 18.5% → interest $19.27" with the exact formula and rounding |
| **Audience** | Business analysts, 60–70 min read documents | Engineers building the replacement + a steering committee approving it |

**Deepest difference:** LegacyLift treats a requirement as a *description*; code-modernization treats it as an *executable test*. LegacyLift's `FR-XXX` says "the system validates the email field." code-modernization's Rule Card says "Given X, When Y, Then Z, with these parameters and these edge cases" — a spec you can compile into a characterization test. This follows from their downstream consumers: LegacyLift's output is read by humans; code-modernization's P0 rules become the literal regression suite that proves a rewrite didn't drift.

### 3.2 How COMPLETENESS is ensured

This is the starkest contrast, and code-modernization is materially stronger.

**LegacyLift — structural coverage:**
- The fact-graph gives an exhaustive entity inventory, and the skill iterates over it (`for domain in get_domains()`, `find_facts_by_predicate('business_rule')`). If the fact-graph is complete, the documentation is complete *by construction* — every endpoint becomes a use case, every validation fact becomes a rule.
- Completeness is asserted, not measured: success criteria are checkbox-style ("ALL use cases", "ALL business rules", "No section lacks citations").
- **Risk:** completeness is only as good as the single fact-graph pass. There is no "did we miss anything" loop. If the fact-graph missed a rule, every downstream doc misses it silently. `gap-analyzer` exists to catch this, but it's a separate, operator-triggered, post-hoc step.

**code-modernization — loop-until-dry with coverage tracking** (`extract-rules.js` lines 184–279):
- Three lens-scoped extractors run **in rounds**; each round reports `coveredAreas` (files actually read). Later rounds are explicitly told: *"target areas NOT in the already-catalogued list — open files no prior pass cited."*
- The loop continues until **two consecutive rounds find nothing new** (`dryRounds < 2`). This directly attacks the "tail" problem — the long thin distribution of rare rules a single pass misses.
- Tracks a `seen` set across rounds (deduped by source+name) so re-discovery doesn't masquerade as progress.
- **Admits its own limits:** if it hits `maxRounds` before going dry, it *logs the gap* — "stopped at maxRounds before extraction ran dry — large estates may hold more rules." LegacyLift never tells you what it didn't cover.

**Verdict:** code-modernization's iterative, self-terminating, gap-declaring loop is a more rigorous completeness mechanism than LegacyLift's single-pass structural coverage. LegacyLift's *advantage* is breadth — it documents the whole system, not just the rules-worth-preserving subset — but it has no feedback loop to know when "all" is actually all.

### 3.3 How ACCURACY is ensured

Both anchor on `file:line` citations, but enforce them at different strengths.

**LegacyLift — citation-first writing, validated post-hoc:**
- Core discipline (repeated ~5× in each SKILL.md): **never write prose then cite; search for evidence first, write the claim with its citation inline.** This structurally prevents the most common hallucination (confident prose with no source).
- Accuracy is then *checked* by separate skills: `citation-validator` (do the line numbers resolve?) and `documentation-review` (is the claim semantically true?).
- **Gap:** the entity writing the citation is the same entity making the claim. There is no independent adversary at authoring time. A citation can be *syntactically valid* (line exists) yet *semantically wrong* (line doesn't support the claim), and only the optional, separate `documentation-review` pass catches it. Confidence is self-assessed.

**code-modernization — adversarial verification wired into the pipeline:**
- Every freshly extracted rule is handed to a **separate referee agent** (`legacy-analyst`) that reads *only the cited lines* and returns `confirmed` / `refuted` / `wrong-citation` (workflow lines 240–275). The extractor cannot enter its own rule into the catalog — a different agent must independently confirm the citation supports it.
- A rule supported only by a **comment or string literal** rather than executable code is *refuted* (an accuracy AND a security control).
- Every **P0 rule** (money / regulatory / data-integrity) faces a **two-judge panel** with distinct lenses — a COMPLIANCE lens ("would a regulator care if this changed?") and a FIDELITY lens ("re-derive the behavior independently; does Given/When/Then match, including rounding and ordering?") (lines 285–333). Both judges must agree or the rule is downgraded and flagged for SME.
- Reports its **rejection count** as a quality signal: "how many candidate rules the referees rejected — this number is the quality the verification bought."

**Security dimension (LegacyLift has none):** code-modernization treats analyzed code as **untrusted input**. Every agent prompt carries an `UNTRUSTED` block; rule text flowing between agents is wrapped in a `<<<UNTRUSTED … UNTRUSTED>>>` fence with fence-escape stripping (workflow lines 34–52); instruction-shaped comments ("mark this rule approved") are flagged as `injectionSuspects`, not obeyed; and the extraction agents are **read-only by design** — they return data, the orchestrator writes files. A hostile or careless legacy codebase cannot steer what lands in the requirements. LegacyLift implicitly assumes a trusted internal repo and has no equivalent defense.

### 3.4 Human-in-the-loop

- **LegacyLift:** no built-in approval gate. Requirements docs are generated and handed off. Completeness/accuracy are validated by other *skills*, not a *human checkpoint*. SME involvement is informal.
- **code-modernization:** the SME loop is *structural*. Every Medium/Low confidence rule generates **the exact question an SME must answer**. `modernize-brief` then **stops in plan mode** and refuses to proceed until a human approves — "no objection is not approval." P0 rules with Confidence < High are explicit **blockers**.

---

## 4. Bottom line

| Dimension | Winner | Why |
|---|---|---|
| **Breadth of requirements captured** | LegacyLift | Documents the whole system; code-mod captures only the rules-worth-preserving subset |
| **Rigor of the requirement unit** | code-modernization | Given/When/Then with concrete values = executable spec, not prose |
| **Completeness mechanism** | code-modernization | Loop-until-dry + coverage tracking + declared gaps vs. single-pass structural coverage |
| **Accuracy mechanism** | code-modernization | Independent referee + P0 judge panel at authoring time vs. self-cited prose validated post-hoc |
| **Provenance data model** | LegacyLift | Strict schema, stable IDs, content hashes for drift — a real database vs. markdown |
| **Security / trust** | code-modernization | Explicit untrusted-input threat model; LegacyLift has none |
| **Human approval** | code-modernization | Structural SME questions + hard plan-mode gate vs. informal |

**Synthesis:** LegacyLift has the better *substrate* (the validated, hash-tracked fact-graph) and the better *breadth*; code-modernization has the better *verification discipline* (adversarial referee, P0 panel, loop-until-dry, untrusted-input handling).

---

## 5. Candidate work items (for the eventual exec-plan)

These are additive to the LegacyLift schema and workflow as they exist today.

1. **Add a criticality axis to business-rule facts.** Extend `fact.schema.json` with a `priority` field (P0/P1/P2) on `predicate: business_rule` facts. P0 = moves money, enforces regulation, or guards data integrity.
2. **Add a structured behavioral specification.** Add an optional `specification` object (given/when/then + parameters + edge cases) so business rules become executable-test-shaped, not prose-shaped.
3. **Add an independent referee pass at authoring time.** Rather than relying on the optional post-hoc `documentation-review`, have a separate agent confirm each cited claim against *only* the cited lines before it enters the doc — mirroring code-modernization's referee.
4. **Add a loop-until-dry extraction round.** Replace single-pass structural coverage with rounds that track covered areas and terminate when two consecutive rounds find nothing new — and that *declare the gap* if stopped early.
5. **Add a P0/criticality judge panel.** For the highest-criticality rules, a two-lens (compliance + fidelity) confirmation before they anchor any downstream deliverable.
6. **Add drift fields to the merge target** (if integrating with code-modernization): expose `content_hash` / `snippet_hash` so the modernization pipeline gains drift detection it currently lacks.
7. **Consider an untrusted-input posture** for client code analysis: fence inter-agent text, flag instruction-shaped comments, keep extraction agents read-only.
8. **Optional: SME-question + suspected-defect capture.** Add `sme_question` and `suspected_defect` to fact `attributes` so judgment artifacts have a home in the canonical store.

---

## 6. Impact of the v4 retrieval layer (`semantic-code-search-graph-index`)

The analysis in §1–§5 predates the v4 semantic code search index (`docs/exec-plans/active/semantic-code-search-graph-index.md`). Assuming that index is implemented as specified, it changes this picture — but at a **different layer** than either approach, and that distinction governs everything below.

The index is a *retrieval substrate*, not an *extraction method*. It provides hybrid search (Chroma vector + SQLite FTS5 lexical, fused with RRF), a confidence-scored caller/callee graph, and chunk-level provenance (file/line/symbol/language + `source_set_sha256` and per-chunk `text_sha256` drift detection). It deliberately carries **no** `business_rule`, `priority`, or Given/When/Then concept — it makes `if (amount > limit)` *findable by meaning*; it does not tell you it is a P0 money rule. "Semantic search" is not "semantic rule mining," and conflating the two is the trap to avoid.

### 6.1 The three-layer stack it introduces

Today both approaches use **grep as their discovery primitive** with a one-shot sweep per run (fact-graph deterministically; code-mod's lens agents semantically, looping until dry). The index sits *underneath* both as a standing, queryable store, producing this stack:

| Layer | Artifact | Question it answers |
|---|---|---|
| **0 — Retrieval** | semantic-code-search index | "Find me the relevant code" |
| **1 — Extraction** | fact-graph facts / code-mod Rule Cards | "What does this code mean / require" |
| **2 — Deliverables** | docs, Rule Cards, `topology.json` | "Present it to humans / tests" |

### 6.2 Effect on fact-graph

- **Deterministic structural extraction (tables, classes, columns) is unchanged and should stay grep-based.** You cannot hallucinate a `CREATE TABLE`; semantic search adds only noise there.
- **The one weak spot — `business_rule` extraction (grep-for-`if` + self-assigned confidence, flagged in §2.2) — is exactly where a meaning-based discovery primitive helps.** Retrieval lets you find candidate rule sites by intent ("where is eligibility reclaimed") instead of by `if.*amount.*>`. But it improves *finding*, not *judging*.
- **The index's graph extractor is a v4 superset of fact-graph's `relations`, and better on two axes fact-graph lacks:** it carries a **confidence score** and **preserves unresolved edges** — which is code-mod's philosophy, not fact-graph's (whose relations must resolve). v4 independently reinvents and improves the relation layer.
- **Drift detection comes natively.** `source_set_sha256` + per-chunk `text_sha256` is the `content_hash`/`snippet_hash` idea computed for free at the retrieval layer.

### 6.3 Effect on code-modernization extract-rules

The index adds most here, and on the two dimensions §3 said code-mod *already wins*:

- **GATHERING:** the three lens agents stop blind-sweeping; "find calculations / eligibility / state transitions" becomes a ranked semantic query returning chunks with file/line/symbol pre-attached.
- **COMPLETENESS (the sharp one):** code-mod's loop-until-dry tracks `coveredAreas` at the *file* level. A chunk inventory gives a far more precise denominator — which *chunks* are claimed by a rule vs. not — so "re-sweep what's uncovered" becomes a precise retrieval (regions of low similarity to any extracted rule) instead of a hopeful re-read. The self-terminating loop gains a real coverage metric.
- **`topology.json` for free:** code-mod rebuilds the call graph independently; the index already has it (with confidence + unresolved edges).
- **VERIFICATION is untouched.** The referee pass and P0 two-judge panel are layer-1 correctness controls. Retrieval can return *wrong* chunks — it certifies nothing. The only marginal help is mechanical (fetching "cited lines + neighbors" faster). The untrusted-input posture is likewise unaffected: the index is derived from the same untrusted code, so chunks must still be fenced.

### 6.4 What this changes about §2–§5

1. **The "merge through fact-graph as the canonical store" path (§2.4) is reframed.** v4 explicitly refuses to consume v3 fact-graph artifacts, so the natural architecture is no longer "merge code-mod *into* fact-graph." It is the three-layer stack: **one retrieval index → verified extraction (fact-graph's breadth + code-mod's referee/P0/loop-until-dry) → deliverables.** The two approaches' best parts merge *on top of* the new layer, not into each other.
2. **The "better substrate" verdict (§4) splits in two.** semantic-code-search is the better *retrieval* substrate; a fact-graph-style store remains the better *knowledge* substrate (extracted, queryable facts). The index feeds the facts DB; it does not replace it.
3. **The §5 work items mostly survive intact, because they are layer-1 concerns the index does not touch:**
   - #1 criticality axis, #2 behavioral spec, #3 referee pass, #5 P0 judge panel, #7 untrusted posture, #8 SME/defect capture — **unaffected.** Still needed, still layer-1.
   - **#4 (loop-until-dry + coverage tracking)** — gets a materially better implementation via the chunk-level coverage metric in §6.3.
   - **#6 (drift fields)** — now provided natively at layer 0; source drift from the index rather than bolting hashes onto a merge target.

### 6.5 Bottom line

The retrieval layer **does not change what a requirement is or how you verify one** — code-mod's verification discipline and the §5 hardening items stand. It changes the **discovery floor under both pipelines**: it replaces grep with hybrid retrieval, makes code-mod's completeness loop measurable instead of heuristic, hands over the call graph and drift hashes for free, and — because it is v4 and will not touch v3 — nudges the eventual architecture toward a clean *retrieval → verified-extraction → deliverable* stack rather than the fact-graph-as-canonical-store merge of §2.4.

The caveat worth stating plainly: the biggest single win identified in §2.2 (hardening `business_rule` extraction with semantic judgment + adversarial verification) is **not** delivered by this index. The index helps you *find* the rule sites; it does nothing for the judgment. That work remains ahead, at layer 1.

---

## 7. How code-modernization could use the index *instead of* fact-graph

§6 framed the index's impact abstractly. This section answers the maintainer's direct
question: **what would the `code-modernization` plugin concretely do with the
semantic-code-search index, in place of fact-graph?**

### 7.1 The premise corrected: code-mod never used fact-graph

The phrase "instead of fact-graph" assumes code-modernization consumes fact-graph today.
It does not. A search of the installed plugin
(`~/.claude/plugins/.../code-modernization/`) finds **zero references** to `fact-graph`,
`legacylift-docs`, or any fact-graph artifact. code-mod's discovery agents
(`legacy-analyst`, `business-rules-extractor`) are each equipped with exactly
**`Read, Glob, Grep, Bash`** and are instructed to "Read before you grep" — i.e. **grep
*is* their discovery substrate.** §2.4's "merge through fact-graph as the canonical
store" was a *proposal* LegacyLift could build, never something code-mod does.

So the real question is sharper and more favorable: code-mod has **no structured index
at all** — not fact-graph, not anything. The opportunity is to give its grep-driven
agents a retrieval substrate they currently lack. And critically, **the integration
surface already exists**: `legacylift-search` is a CLI, and every code-mod discovery
agent already has `Bash`. An agent can call `legacylift-search search "..."` the same way
it calls `grep` — no plugin code change, no new tool grant, no fact-graph dependency.

### 7.2 The swap, command by command

The index exposes five query commands relevant to discovery. Each maps onto a grep/read
idiom the code-mod agents use today:

| code-mod agent does today (grep) | `legacylift-search` equivalent | What changes |
|---|---|---|
| `grep -rn "eligib\|enroll" --include=*.cs` then read hits | `search "where is provider eligibility reclaimed" --limit 20` | Finds conceptually-related code with **no shared keyword** — the thing grep structurally cannot do |
| Trace a call by grepping the method name across the tree | `callers <symbol-id>` / `callees <symbol-id>` | Pre-built caller/callee edges **with confidence scores + preserved unresolved edges** — no false-positive overload noise |
| `grep -rn "class .*Manager"` to inventory a layer | `symbols --name ClaimManager` (exact-then-contains) | Symbol table lookup with file/line/qualified-name already attached |
| Manually estimate "have we read everything?" | `stats` + per-chunk coverage (see §7.4) | A real denominator instead of a guess |

Every result already carries `file:line:symbol:language` + a snippet — exactly the
citation shape both agents are *required* to produce ("Every claim gets a
`path/to/file:line` reference"). The index hands them the citation pre-formed.

### 7.3 Where it helps each command

- **`/modernize-map` (legacy-analyst → structural/dependency map):** the call-graph
  edges and `symbols` inventory are *most* of what this command rebuilds by hand. The
  index's graph is a strict superset of fact-graph's `relations` and — per §6.2 — better
  on the two axes that matter for legacy code: confidence scores and **preserved
  unresolved edges** (fact-graph discards relations whose targets don't resolve; code-mod
  explicitly *wants* unresolved calls kept, and so does the index). This is the cleanest
  fit of all.
- **`/modernize-extract-rules` (business-rules-extractor):** the three "lens" agents
  (calculations / validations & eligibility / state & lifecycle) stop blind-sweeping the
  tree. "Find calculations" becomes a ranked semantic query. This is exactly the §2.2
  weak-spot reframed: the index does not *judge* whether `if (amount > limit)` is a P0
  money rule — but it does surface the candidate site by intent, which is strictly better
  than `grep "if.*amount.*>"`.
- **`/modernize-assess`, `/modernize-brief` (portfolio/topology):** `topology.json` is the
  call graph code-mod rebuilds independently; the index already has it.

### 7.4 The one place it materially upgrades code-mod's *own* strength

§3.2 found code-mod's completeness loop (`extract-rules.js`, loop-until-dry) already
*beats* fact-graph. The index makes code-mod's strength stronger: its `coveredAreas`
tracking is **file-level** ("which files has some pass cited"). A chunk inventory gives a
**chunk-level denominator** — which *regions* are claimed by an extracted rule vs. not —
so "re-sweep what's uncovered" becomes a precise retrieval (chunks with low similarity to
any extracted rule) instead of a hopeful re-read of whole files. The self-terminating
loop gains a measurable coverage metric. fact-graph offers nothing here; the index offers
a real upgrade to the part code-mod already does best.

### 7.5 What the swap does NOT buy (the honest limits)

- **Verification is untouched.** The referee pass and P0 two-judge panel (§3.3) are
  layer-1 correctness controls. Retrieval can return *wrong* chunks; it certifies nothing.
  The only mechanical help is fetching "cited lines + neighbors" faster.
- **The untrusted-input posture is unchanged.** The index is derived from the same
  untrusted code, so chunks it returns must still be fenced and treated as data. An
  injection-shaped comment is just as present in a retrieved chunk as in a grep hit.
- **No `business_rule` / `priority` / Given-When-Then concept exists in the index.** It
  makes rule sites *findable*; the Rule Card, its criticality, and its executable spec are
  all still produced by code-mod's agents at layer 1.
- **It is a different language/runtime.** code-mod is a Claude-plugin (markdown agents +
  JS workflows); the index is a Python CLI. Integration is "an agent shells out to
  `legacylift-search`," which works precisely because the agents have `Bash` — but it does
  couple a code-mod run to a built index existing for that repo (with `validate` reporting
  `fresh|stale|missing` first).

### 7.6 Bottom line for the maintainer's question

code-mod should use the index **as the discovery substrate under its grep-driven agents**,
not as a fact store to import. Because the agents already have `Bash` and the index is a
CLI emitting `file:line` citations, the integration is "teach the discovery agents to
prefer `legacylift-search search/callers/callees/symbols` over raw `grep`, falling back to
`grep` when the index is `missing`/`stale`." That swap (a) gives code-mod meaning-based
discovery and a pre-built confidence-scored call graph it has *never* had, (b) upgrades its
already-best-in-class completeness loop with a chunk-level coverage denominator, and (c)
leaves its verification, P0 panel, and untrusted-input discipline exactly as they are —
which is correct, because those are layer-1 concerns the retrieval layer does not touch.

This supersedes §2.4's "merge through fact-graph as canonical store" for the
code-mod-facing case: the cleaner architecture is **index (layer 0) → code-mod's
verified extraction (layer 1) → Rule Cards / topology (layer 2)**, with fact-graph not in
the code-mod path at all. fact-graph remains valuable on the *LegacyLift* side as the
evidence-backed fact store feeding the documentation skills — the two are complementary,
which is precisely what the active plan's Milestone 21 is set up to confirm.

---

*Draft analysis — to be developed into an execution plan.*
