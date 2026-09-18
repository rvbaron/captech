# Deferred small items — too small to own an ExecPlan, too real to forget

**Status: STANDING LIST — append-only, not a conforming ExecPlan.** This file is deliberately not a
plan. It is where a change lands when it is (a) concrete and measured, (b) genuinely useful, and
(c) too small or too far off-topic to justify its own file — the kind of item that otherwise gets
buried in the "Surprises & Discoveries" section of an unrelated plan and is never seen again.
`CLAUDE.md` routes here and describes the convention: **check this list before filing a new draft
for a one-file fix, and add to it rather than burying a discovery in an unrelated plan's
*Surprises* section.**

This repository's ExecPlan conventions live in [`docs/exec-plan.md`](../../exec-plan.md). Nothing here
has a Plan of Work or acceptance criteria. Each entry records what the change is, why it was
deferred, the evidence that it is real, and what it would touch — enough that someone can pick one
up cold, and enough that a future design conversation can reject it on the merits rather than
rediscover it. An entry is removed only when it ships, and then only by the change that ships it.

**Entry bar.** An item belongs here only if it is measured, not suspected. If it needs a design
conversation, it needs its own draft in `pending/` instead. If it is a bug with a known fix, it
belongs in a branch, not a list.

**History.** Created 2026-09-01 — `CLAUDE.md` had described this file for some time and it did not
exist. Entries 1–6 and 7–8 were written independently on two branches (the requirements store and
the Layer-0 extraction-gap work) and were combined when those branches merged on 2026-09-03; the
numbering below reflects that merge, so a cross-reference written before it may name a different
number than the one it now carries. The two sibling drafts the original preamble listed as missing,
`pending/durable-loc-counts.md` and `pending/embed-everything-evaluation.md`, **now exist** — they
are real drafts with measurements behind them rather than one-line fixes, so do not fold them in
here.

**Entry 13 was added 2026-09-10** from the four-round NNG extraction; entry 12 was added
2026-09-09. **Entry 14 was added and then promoted the same day** to
[`dto-catalog-bounding.md`](./dto-catalog-bounding.md), once measurement showed it carried five open
design questions — its heading is kept as a pointer. **Entry 11 shipped 2026-09-08** and was removed
by the change that shipped it, as the rule above requires — `parse_citation` now accepts a
comma-separated range list and emits one triple per range, with tests, verified against the 133-rule
NNG round-1 corpus (9 affected rules, 0 remaining mis-parses). **Entries 15 and 16 were added 2026-09-10** from Step 10 Phases 4–5 of the requirements plan — the
vector shortfall guard is silent on the one ingest where the semantic half is guaranteed blind, and
the value-changing-write rule is applied per offer rather than per run, so a re-ingest bumps
`updated_at` on 48 unchanged rows.
**Entry 17 was added 2026-09-10** from Step 10 Phase 6 — the ingest banner's per-reason merge-candidate
tally cannot be reproduced from the store, and the mechanism discards similarity scores the semantic
half computed. **Numbers are not reused**, so this
list holds **fifteen** live entries, numbered **1–10, 12, 13, 15, 16 and 17**, and the next entry written is
**18**; a cross-reference to entry 11 is pointing at shipped work and one to entry 14 at a promoted
draft, neither at a missing entry. **Entry 13 and that draft touch the same file** —
`.claude/skills/code-modernization/workflows/extract-rules.js` — so whoever picks up one should look
at the other, and remember that file needs its CapTech attribution line overwritten per `CLAUDE.md`.

---

## 1. The four domain tables' TEXT primary keys admit NULL

**Measured 2026-09-01**, while adding Step 3's GR tables in
`docs/exec-plans/active/reqs-to-data-store.md`.

In a SQLite rowid table, a `PRIMARY KEY` column that is not `INTEGER PRIMARY KEY` is **not**
implicitly `NOT NULL`, and the unique index behind it treats NULLs as distinct. So a table declared
`x TEXT PRIMARY KEY` accepts a NULL key — and accepts *two* of them. Verified against this
repository's virtual environment (SQLite 3.45.3):

    CREATE TABLE t (a TEXT PRIMARY KEY, b TEXT);
    INSERT INTO t VALUES (NULL,'x');   -- accepted
    INSERT INTO t VALUES (NULL,'y');   -- also accepted

**Ten columns are exposed across the two databases, measured rather than estimated.** Three in
`knowledge.sqlite` (`knowledge_store.py`): `domains.domain_id`, `file_domains.relative_path`,
`domain_exclusions.pattern`. `domain_edges` is already safe — its composite key's three columns are
each declared `NOT NULL` independently. Seven in `index.sqlite` (`store.py`), every one a
`TEXT PRIMARY KEY`: `index_metadata.key` (`:449`), `chunks.id` (`:472`), `symbols.id` (`:506`),
`symbol_refs.id` (`:552`), `graph_edges.id` (`:579`), `vectors_present.chunk_id` (`:615`) and
`symbol_facts.id` (`:627`).

The `index.sqlite` seven matter less than the count suggests, and it is worth saying why so nobody
prices this as a ten-column job: that database is disposable and rebuildable by `index --reset`, so
a malformed row there is a bug to fix rather than data to recover. The three in `knowledge.sqlite`
are the ones on a database this repository calls irreplaceable.

**Why it is deferred rather than fixed here.** Step 3 fixed the two columns it introduced
(`gr.gr_id` and `gr_run.run_id` now carry an explicit `NOT NULL`, with a test), which is the whole
of what that step owns. The pre-existing ten are a different job: `ALTER TABLE` cannot add
`NOT NULL` to an existing column in SQLite, so closing this means a table rebuild inside a
versioned migration — the twelve-step `PRAGMA legacy_alter_table` dance, on the one database this
repository calls irreplaceable. That is a real change with a real risk, not a one-liner.

**Severity is low but not zero.** No current writer can produce a NULL there: every caller reaches
these tables through `upsert_domain`, `upsert_file_domain` or `set_exclusions`, and each takes the
value as a required argument. So this is a missing guard rather than a live bug — which is exactly
why it belongs on this list instead of interrupting a milestone.

**What closing it takes.** One `KNOWLEDGE_MIGRATIONS` entry that rebuilds the three
`knowledge.sqlite` tables with `NOT NULL` on the key column and copies the rows. The seven
`index.sqlite` columns need no migration at all — that database is rebuilt from source, so adding
`NOT NULL` to the DDL in `store.py` is sufficient and the next `index --reset` carries it. It is a natural
companion to the *first* migration that has to rebuild one of those tables for another reason —
doing it then costs almost nothing extra, and doing it alone costs a migration nobody needed.
Note for whoever does: the GR tables added in Step 3 are already correct and must not be included.

---

## 2. `chroma_dir` is honored in five places and `ChromaVectorStore` is not one of them

**Measured 2026-09-01**, while writing the Step 5 orientation block in
`docs/exec-plans/active/reqs-to-data-store.md`.

`ChromaVectorStore.__init__` hardcodes the persistence directory:

    chroma_path = index_dir / "chroma"

while five other sites compute it from the manifest instead:

    chroma_path = index_dir / self.manifest.index.chroma_dir

**Re-counted 2026-09-02 (`grep -n chroma_dir src/legacylift_search/*.py`), because the heading
said two and the Step 5 orientation block said three and both were undercounts.** The five are
`cli.py:498` and `:764` (the `validate` and `backfill-vectors` paths), `indexer.py:383`
(`index --reset`'s rmtree), `indexer.py:1329` (`backfill_vectors`' existence check) and
`indexer.py:321` (the reset guard's `chroma_names` set, which is the one that already tolerates
both spellings). Threading the setting into the constructor therefore touches five readers, not
two.

`IndexConfig.chroma_dir` defaults to `"chroma"` (`config.py:114`), so the two agree today and
every existing manifest is fine. They diverge the moment anyone sets it to anything else: the
store writes to `<index_dir>/chroma`, and the reset path deletes `<index_dir>/<chroma_dir>` — a
directory nothing ever wrote. **The failure is silent in the direction that matters.** `--reset`
reports success, the stale collection survives, and the next index run reuses vectors from before
the reset, which is precisely what the user asked to discard.

**Why it is deferred.** No manifest in this repository overrides `chroma_dir`, so there is no live
defect to fix — only a setting that does not do what its name says. The fix is one line (thread
`chroma_dir` into the constructor, or delete the setting and let the constant win) but it is a
config-surface decision rather than a typo: deleting a documented manifest field and honoring one
that has never been exercised are different acts with different blast radii, and neither belongs
inside a milestone that is about requirements.

**What closing it takes.** Pick one of the two: give `ChromaVectorStore` the subdirectory name as
a parameter and pass `manifest.index.chroma_dir` from all **five** `ChromaVectorStore(...)` call sites (`cli.py:570`, `:835`; `domain_tagger.py:621`; `indexer.py:885`, `:1395`), or remove `chroma_dir`
from `IndexConfig` and have the reset and validate paths use the literal. Note for whoever does:
Milestone 1 Step 5 of the requirements plan **has since renamed** this constructor's first
parameter from `index_dir` to `base_dir` (shipped 2026-09-02), because the GR collection persists
under the *knowledge* directory rather than the index directory. That rename does not touch this,
and both the Step 5 text and the constructor's own docstring say so — do not read a `base_dir`
parameter as evidence this was closed. The constructor still hardcodes `base_dir / "chroma"` while
`index --reset`, `backfill_vectors` and `validate` still compute `index_dir / manifest.index.chroma_dir`.

---

## 3. No collection pins its vector distance metric, and a threshold now depends on it

**Measured 2026-09-02**, while building Step 6's stage-two candidate search in
`docs/exec-plans/active/reqs-to-data-store.md`.

`ChromaVectorStore.__init__` builds `collection_metadata` with `hnsw:sync_threshold` and
`hnsw:batch_size` and **no `hnsw:space`**, so every collection this repository creates — the code
chunks, the domain mirror and now `gr_statements` — takes whichever metric the installed chromadb
defaults to. Verified against the pinned version rather than assumed:

    chromadb 1.5.9
    configuration_json: {'hnsw': {'space': 'l2', 'ef_construction': 100, ...}}
    metadata: {'hnsw:sync_threshold': 100000}

So it is **L2 today**, by default and not by declaration. Two consequences, and only the second is
new:

- Retrieval quality across the existing collections has always depended on an unstated default.
  Nothing observed suggests it is the wrong choice; it is simply not a choice anyone made.
- **A number in the requirements store now means something different if that default moves.**
  Step 6's stage-two semantic half takes `SEMANTIC_DISTANCE_MAX = 0.35`, a *distance*, so moving
  the pin to a release with a different default — or setting a space for an unrelated reason —
  silently rescales it. The same applies to whether the embedder returns normalized vectors, which
  is what decides the range L2 distances actually occupy; that is unmeasured here.

**Why the failure is quiet.** The threshold governs whether stage two *raises a review candidate*,
and stage two never merges anything at any confidence, so a wrong value can never cause a
false-same. What it causes is fewer candidates — and stage two returning none is indistinguishable
from there being no near-duplicates to find. That is the same indistinguishability
`gr_refresh.open_gr_collection` guards against for a reset-destroyed collection, arriving through
a different door, and it is why this is worth writing down rather than leaving to be rediscovered.

**Why it is deferred.** There is no live defect: the default is L2, `0.35` was chosen against L2,
and the pin is fixed at 1.5.9 by a standing constraint of its own. Picking a metric deliberately is
a retrieval-quality decision affecting three collections and wants an evaluation, which is well
outside a milestone about requirements — and `pending/embed-everything-evaluation.md` is already
the declared home for retrieval evaluation work of exactly this shape.

**What closing it takes**, cheapest first:

1. **An assertion, not a change.** `collection.configuration_json['hnsw']['space']` reads the
   effective metric at runtime, so a single check at collection-open time can fail loudly if it is
   ever not what the threshold assumes. This is the one piece worth doing before the metric
   question is settled, and it is a few lines.
2. Declare `hnsw:space` explicitly in `collection_metadata` so the metric is a stated choice.
   Note this is **not** free on existing stores: Chroma fixes a collection's space at creation, so
   changing it means recreating and re-embedding, which for the NNG app is a real cost (see the
   standing note on embedding throughput). Declaring the current value is free; changing it is not.
3. Measure `SEMANTIC_DISTANCE_MAX` and `SEMANTIC_TOP_K` on a real corpus, which the requirements
   plan already records as wanted alongside its Step 10 measurements, and record whether the
   embedder's vectors are normalized while you are there.

---

## 4. `set_state` cannot report a vector half that fails after the embedder builds

**Measured 2026-09-02**, while building Step 8's `requirements set-state` in
`docs/exec-plans/active/reqs-to-data-store.md`.

`gr_state.set_state` is declared `-> None` and drops its `EmbedResult` on the floor. The drop is
**deliberate and the reasoning is written at the call site** (`gr_state.py:198-203`):

    # The `EmbedResult` is deliberately dropped rather than returned: this
    # function's declared return type is `None`, and a degraded vector half is
    # reported by `gr_refresh.describe_vector_shortfall`, which the CLI runs
    # against the whole collection. That is the right place for it -- a
    # per-call return value would say "this one record missed" while the
    # question a reviewer actually has is "is the collection behind."

That argument is sound, and `requirements stats` does run the shortfall check, so **this is a
documented trade-off rather than a live defect.** It is on this list for the residue the trade-off
leaves, which is narrower than "set-state cannot report a degraded embed":

**What `set-state` can and cannot see.** It can report the case where `build_embedder` returned
`(None, reason)` — no provider, absent credentials — because the CLI resolved that itself before
calling. It **cannot** see the case where an embedder builds and the embed call then fails: a
dimension mismatch, or a provider that 500s. `refresh_gr_vectors` catches that, returns an
`EmbedResult` carrying `skipped` and a `reason` naming `reindex-vectors`, and `set_state` discards
it. So a human approving fifty records one at a time gets fifty silent partial successes and learns
about them only on their next `requirements stats`.

**Why that is tolerable.** The state change itself is committed and correct; only the
`gr_statements` metadata is stale, which makes state-filtered *semantic* search wrong until a
`reindex-vectors`. Both `stats` and stage two of the merge call `describe_vector_shortfall`, so the
staleness is detectable and the recovery is one documented command. Nothing is lost.

**Why it is deferred rather than fixed.** Both available fixes are worse than the gap at Milestone
1's scale. Changing the return type touches the declared signature in the plan's
`Interfaces and Dependencies`, which is a contract several call sites hold. Calling
`describe_vector_shortfall` inside `set_state` opens a Chroma collection **per recorded judgement**,
which is a real cost on a corpus being reviewed record by record and puts a retrieval dependency
inside the one function whose whole design principle is that a human's judgement must never fail
because a provider is unreachable.

**What closing it takes.** Most likely: leave `set_state` alone and have the *CLI* run the
shortfall check once at the end of a `set-state` invocation, which is cheap for one record and
keeps the collection question where the existing comment argues it belongs. Revisit when
Milestone 4's review UI lands, since a queue that approves in bulk changes the arithmetic — it
would call the pair once for a batch, at which point returning the `EmbedResult` costs nothing and
the per-call objection disappears.

---

## 5. `describe_vector_shortfall` has no way to say "not measured"

**Measured 2026-09-02**, while building Step 8's `requirements reindex-vectors` and `stats` in
`docs/exec-plans/active/reqs-to-data-store.md`.

The signature is

    def describe_vector_shortfall(gr_count: int, collection_count: int) -> str | None

and both parameters are `int`. Its contract is therefore total over *measured* pairs and has no
representation for the third state that actually occurs: **no collection could be opened at all.**
That happens whenever no embedder is available, because chromadb wants the dimension at collection
creation, and it also happens on a fresh store where nothing has ever been embedded.

**This is the plan's own recurring defect class, in a signature rather than a column** — and it is
notable because the function exists *specifically* to prevent an instance of that class one layer
up. Its docstring says so:

    An under-populated collection answers a near-duplicate query with zero
    candidates, which is indistinguishable from "there are no near duplicates"
    -- the same absent-versus-real defect as storing an unmeasured count as
    zero.

So the guard against "zero candidates versus no candidates" cannot itself express "the count was
never taken versus the count is zero". Passing `collection_count=0` for an unopenable collection
returns the shortfall sentence, which is *accidentally* the right user-facing outcome — every
requirement does lack a vector — but it reports a measurement that was not made, and the two states
call for different fixes: one wants `reindex-vectors`, the other wants an embedding provider
configured.

**Why there is no live defect.** Step 8 handled it at the CLI layer instead: `stats` and
`reindex-vectors` carry `collection_count` as `int | None`, print *unmeasured* rather than
`0 of N`, and `--json` carries a separate `shortfall_measured` boolean so a null shortfall is never
read as *no* shortfall. The behaviour is correct today; what is wrong is that the correctness lives
in two CLI commands rather than in the one function whose job it is, so a third caller will get it
wrong.

**What closing it takes.** Widen the parameter to `collection_count: int | None` and return a
distinct sentence for `None` — one naming the missing embedder rather than `reindex-vectors`, since
reindexing without a provider cannot help. Then move the CLI's two hand-rolled versions onto it and
delete `shortfall_measured` in favour of asking the function. Roughly a dozen lines plus the two
call sites, and worth doing alongside the next change to either command rather than on its own.
Note while there: the sibling entry 3 above wants a runtime assertion on `hnsw:space` at
collection-open time, which is the same neighbourhood and the same shape of fix.

---

## 6. The durable `gr_import` row keeps the ambiguity the in-memory result no longer has

**Measured 2026-09-02**, while closing entry-adjacent defect 1 of Step 8's four in
`docs/exec-plans/active/reqs-to-data-store.md` — see that plan's *Milestone 1 Step 8* retrospective.

`ImportResult` was fixed on 2026-09-02 to carry `refused_downgrades` (one record per refusal, with
`gr_id`, `stored_state`, `incoming_state` and `stored_reviewed_by`) plus a derived count, because
`rows_changed_state == 0` could otherwise mean either *"the file agreed with the store"* or
*"every state change in the file was refused"*. **The `gr_import` table was not, and still stores
only the four columns it always did:**

    import_id  source_path  imported_at  rows_read  rows_changed_state

So the fix holds for the duration of the command's own output and is lost the moment it exits. The
durable marker row — whose entire reason for existing is that `import_records` is the single
declared exception to "`set_state` is the only writer of `gr.state`", so a state change arriving
through it must be traceable rather than appearing to have happened spontaneously — cannot answer
*"did this import protect anything?"* at all. An auditor reading `gr_import` six months later sees
a zero and cannot tell which of the two facts it records.

**Why it is deferred.** Adding a column to `gr_import` is the **first GR *column* addition**, and
Step 3 draws the line there deliberately: the eleven GR tables were created with no
`KNOWLEDGE_MIGRATIONS` entry, because `migrate()` runs from `__init__` on every open so a *table*
addition is free — and it records that "the first GR *column* addition is what needs a migration".
So this is the change that exercises M0's versioned-migration machinery on `knowledge.sqlite` for
the first time, which is a larger and more interesting act than the column deserves on its own.

**Severity is low.** Nothing is corrupted and nothing is silently wrong: the command reports the
refusals accurately to the analyst performing the import, and the store's `gr` rows are correct
either way. What is missing is only the *retrospective* answer, and the JSONL export plus the
analyst's own record cover the common case.

**What closing it takes.** One `KNOWLEDGE_MIGRATIONS` entry adding
`rows_refused_downgrade INTEGER` to `gr_import` — nullable, because every row written before the
migration genuinely never measured it, which is the same absent-versus-real distinction the column
exists to record. Then write it from `import_records`, which already has the number. Consider
carrying the refused `gr_id`s too, as JSON in a text column, since naming what was protected is
what made the in-memory fix worth doing; a bare count in the durable row would reproduce half the
defect. **This is the natural companion to entry 1's table rebuild** — both want the first
`knowledge.sqlite` migration, and doing them together costs one migration instead of two.
---

## 7 — `/modernize-status` could surface the extraction-gap percentage in its verdict

**Raised:** 2026-09-01, during the design interview for
[`layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md).

**What.** That plan settled (its Q8c / Q21) that the gap figure travels by having
`/modernize-assess` shell out to `legacylift-search gaps --json` and quote the headline inline in
`ASSESSMENT.md` — no new artifact, no new staleness edge. A consequence worth recording is that
`/modernize-status` is then unaffected **in both directions**: it needs no edit, and it also gains no
behavior. It will never print the gap percentage, never validate it, never flag it stale. The only
sense in which status "covers" the number is that `ASSESSMENT.md` was already an inventoried
artifact and the figure is now text inside it — exactly the status the scc LOC table in the same
document already has.

The optional change is to teach status's §4 verdict to say something like *"mapped 100%, but 25% of
source bytes were never indexed"* alongside its "Where you are" line.

**Why deferred.** §4's job is the single most useful next command, and a coverage caveat competes
with that. The number is already in front of a human at the point where coverage claims are actually
made. This is a preference about emphasis, not a correctness fix.

**Would touch.** `.claude/skills/code-modernization/commands/modernize-status.md` §4. That file now
carries a CapTech attribution line (added 2026-09-01 for the §2 index-staleness rule), so this change
means *overwriting* that line, not adding one — `CLAUDE.md` keeps only the latest modification.

---

## 8 — Spring Webflow state kinds are the only unprefixed symbol kinds Layer 0 emits

**Raised:** 2026-09-01, same conversation.

**What.** `xml_extractor.py` namespaces every symbol kind it mints except one. Hibernate kinds are
prefixed — `hibernate_class_mapping` (`:188`) and `f"hibernate_{tag}"` (`:208`) — and the Webflow
*flow root* is prefixed too, as `webflow_flow` (`:245`). But the Webflow **state** kinds at
`:251-253` are minted as `el.tag.replace("-", "_")` with no prefix, so they enter the global `kind`
namespace as bare `view_state`, `action_state`, `decision_state`, `end_state`, `subflow_state`.

Measured on the NNG app index (2026-09-01) — 174 real symbols carry an unprefixed kind:

        view_state        97        hibernate_property        1007
        subflow_state     44        spring_bean                160
        decision_state    18        hibernate_class_mapping    147
        end_state         15        webflow_flow                33
        action_state       0        (all namespaced)

They sit in the same column, and the same namespace, as tree-sitter-derived kinds like
`method_declaration`, `class_declaration` and `create_table`.

**Severity — read this before acting.** This is a **collision** risk, not an injection risk.
`state_tags` (`:235-241`) is a closed set of five hard-coded Spring Webflow element names, so no
client-authored element name can reach the `kind` column through this path. The unbounded mint is
`f"hibernate_{tag}"` at `:208`, which takes whatever element name appears under a Hibernate class
mapping — and that one *is* correctly namespaced. So the inconsistency is exactly backwards from
where the risk is: the bounded mint is unprefixed and the unbounded mint is prefixed.

What remains is that `view_state` / `decision_state` / `end_state` are generic enough to collide with
a tree-sitter node kind or a future extractor's vocabulary, and a consumer filtering
`kind LIKE 'webflow_%'` will silently miss 174 symbols while `kind LIKE 'hibernate_%'` works
correctly. That asymmetry is a trap for anyone writing a framework-detection query — it was hit once
already while deriving the stack prior for `layer0-extraction-gap-detection.md` (its Q7).

**Why deferred.** Renaming a `kind` value is a data migration, not an edit: existing indexes carry
the old values, and `symbol_facts` and any stored query referencing them would need to move together.
The requirements plan's `PR-83` reached the same conclusion from the other direction and solved the
identity problem by having extractors declare an explicit `entity_class` rather than deriving meaning
from the kind string — that is very likely the right shape here too, and it argues for doing this
*with* that work rather than as a standalone rename.

**Would touch.** `xml_extractor.py:251-253`, every index in `repos/` (migration or reindex), and any
consumer matching on those five kind values. Check
[`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) `PR-83` and the companion archive
before proposing a fix — the reviews may already have settled the shape.

---

## 9 — A JSP extractor would re-key every rule that cites a JSP

**Measured 2026-09-08**, during the Layer-0 coverage widening
([`active/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md),
*The 2026-09-08 coverage widening*).

The widening put NNG's 178 first-party `.jsp` files into the index for the first time. They are
**symbol-dead**: `extractors.json` has no `jsp` profile, so `SymbolExtractor.extract` returns an
empty `ExtractedFile` before it ever reaches a parser, and all 241 of their chunks are
`chunk_kind='fallback'`. Retrieval works — FTS5 and vector search reach them, which is what
`/modernize-extract-rules` actually consumes — but the graph does not see them.

The consequence is a *latent* one, and it only fires if someone writes a JSP extractor. Citations
into a symbol-less file resolve to the **file-level anchor floor**, whose `anchor_key` is path-only
and index-independent by design (`active/reqs-to-data-store.md` Decision Log, the `PR-82`/`PR-83`
entry — "a constant cannot churn"). The moment a JSP extractor lands, those same citations resolve
to *symbol* anchors instead. That changes `dedupe_key` tier 1, so every stored rule citing a JSP
re-keys, and rules that were previously distinct may collapse or previously-collapsed rules may
split.

**Why deferred.** Writing the extractor is a milestone, not a small item — and the churn is deferred
either way: not indexing JSP at all would simply mean the rules do not exist yet. Widening first at
least means there *are* rules to re-key, which is strictly the better position. The re-keying itself
is a migration over `knowledge.sqlite`, not an edit.

**Would touch.** A new `jsp` profile in `extractors.json` (or a bespoke extractor beside
`xml_extractor.py`, which is how `.xml` is handled — see `SymbolExtractor.has_extractor` for why
those are two different mechanisms), plus a `dedupe_key` re-key migration over every
`knowledge.sqlite` holding rules cited into JSP. Do it *with* the `entity_class` work `PR-83`
settled, not as a standalone change.

---

## 10 — `/modernize-assess` does not author `vendored_globs` or `own_identities`

**Measured 2026-09-08**, wiring third-party provenance into `discover_source_files`.

`DomainsFile` carries four optional lists. `/modernize-assess` authors `domains` and — since the
`excluded`-tier work — `exclude_globs`. It authors **neither** `vendored_globs` nor
`own_identities`, and both live NNG `domains.json` files had to be hand-edited to add them.

That matters more than it did before this date, because those two fields are now read by
`discover_source_files` (via `ProjectConfig.domains_file`) and not only by `gaps.walk_repository`.
On NNG they are what keeps 11 vendor `.tld` descriptors out of the index while retaining the
client's own `naesb.tld` and `nngauthz.tld`, which sit in the same directory and are separable only
by their declared `<uri>`. **A re-run of `/modernize-assess` silently deletes both fields**, and the
next index quietly re-admits the vendor files with nothing to announce it.

**Evidence.** Before the hand-edit, both `analysis/customer.ple.nng.app/domains.json` and
`analysis/customer.ple.nng.db.ETSPii/domains.json` had `vendored_globs: []` (absent) and no
`own_identities`, while `active/artifacts/gap-acceptance-domains-nng.json` — hand-authored for the
walk — carried 10 and `["nngco.com"]` respectively.

**Why deferred.** Authoring `vendored_globs` well needs the same judgment `exclude_globs` needed:
the skill has to look at the tree and decide what is vendored. `own_identities` is easier and could
ship alone — the client's domain is usually derivable from the package namespace or the POM
`groupId`. Splitting them may be the right call.

**Would touch.** `.claude/skills/code-modernization/commands/modernize-assess.md` (which already
carries a CapTech attribution line — per `CLAUDE.md`, **overwrite** it rather than accumulating
history). A cheaper interim guard, worth considering on its own: have `/modernize-assess` *preserve*
any `vendored_globs`/`own_identities` already present rather than authoring them, which turns a
silent deletion into a no-op.

---

## 12. `requirements ingest` prints its anchor-resolution breakdown pre-dedup

**Measured 2026-09-09**, on the Step 10 Phase 3 rehearsal (first real ingest of the round-1 corpus,
against a copy of the store). The log emits these two lines, four apart:

    citations: 142 seen, 138 inserted
    anchor resolution: file=2, symbol=140

The breakdown sums to **142** — *seen* — while `gr_citation` holds **138** rows, and SQL over the
stored table gives `file=2, symbol=136`. The four dropped citations were all symbol-resolved
duplicates collapsed by `_prepare`'s `seen_tuples`, which exists because `gr_citation`'s uniqueness
tuple is `(gr_id, path, start, end)`.

**Why it matters more than a cosmetic mismatch.** Nothing is stored wrongly — this is a reporting
defect only. But the breakdown sits directly beneath the post-dedup count and reads as describing
the stored rows, and it is the one line in the whole ingest report that would reveal an
anchor-resolution problem. A reviewer comparing the log against `requirements stats` finds two
numbers that disagree with no stated reason, and the natural conclusion — that citations are being
lost between resolution and insert — is wrong.

**Why deferred.** It is a one-file fix with no design question attached, and it was found in the
middle of a measurement run whose numbers it does not affect. Fixing it mid-run would have meant
re-running the ingest to re-verify the log.

**Would touch.** `tools/legacylift_search/src/legacylift_search/gr_ingest.py` — tally the breakdown
from the citations actually appended after the `seen_tuples` collapse rather than from every
resolution performed. One test in `tests/test_cli_req_run.py` asserting the two lines agree on a
corpus with a duplicate citation, which is the case that separates them.

---

## 13 — The extractor can emit prose into `source`, and no parser grammar can fix that

**Measured 2026-09-10**, on the four-round NNG extraction (437 confirmed rules). One rule,
`Northern Natural Gas own-party identity` (D-CONST, Medium confidence), emitted a **586-character
English sentence** where a citation belongs:

    repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app/ple-services/JavaSource/com/nng/ple/service/point/validator/PointPartyValidator.java:389-392 (isNNG predicate; field bound at :48-49) and repos/.../PoipartyService.java:94-105 (transporter+NNG party supplies the point's primary flow direction); supporting: PoipointLiteService.java:401,419,504,572 and PartyService.java:96-107; parameter declarations remain at ple-services/JavaSource/config/application.properties:133-139

Four distinct problems compound in that one string: paths prefixed with the **session-relative path
to the codeRoot** instead of relative to it; **parenthetical asides** inside the citation; **`and` /
`; supporting:` prose connectives** joining several files; and a **bare single-line list**
(`...java:401,419,504,572`) which the comma-split then tears apart, so the fourth triple begins
`572 and PartyService.java...`. `parse_citation` raises nothing — it returns 4 triples, all
unresolvable. **1 rule of 437 (0.23%); 437 of 441 triples across the corpus resolve.**

**All four files it names exist under the codeRoot**, so this is a formatting defect and not a
hallucinated citation. The evidence is real and a human can recover it in a minute.

**Why it is not "fix the parser again".** The two prior citation defects (multi-range, entry 11;
multi-file, fixed 2026-09-09) were both fixed by teaching `parse_citation` a richer grammar. This
one shows that road has an end: a model can always write prose into a string field, and each grammar
extension makes the parser more willing to accept garbage — the multi-file fix is already why this
string yields four confident-looking triples instead of one obvious failure. The durable defense is
an **emission constraint plus a resolve check**, not a more forgiving parser.

**Why deferred.** It needs a small design choice (reject at ingest with a per-rule error, or
normalize-and-warn, or constrain the schema field) and it affects 1 rule in 437, on a corpus that is
not yet ingested. It is not blocking: ingest resolves what it can and records `unresolved` anchors.

**Would touch.** `.claude/skills/code-modernization/workflows/extract-rules.js` — the NOTATION
fragment, to state that `source` is a citation and not a sentence (no parentheticals, no
connectives, paths relative to the repo root under analysis), which is the same "teach the prompt
what the validator enforces" move that took bodies from 5% to 100% valid. Optionally
`tools/legacylift_search/src/legacylift_search/gr_ingest.py`, to fail a rule whose every citation is
unresolvable rather than storing it with no anchor. A test pinning this exact string is the natural
regression case.

---

## 14 — PROMOTED to its own draft, number retired

**Entry 14 became [`dto-catalog-bounding.md`](./dto-catalog-bounding.md) on 2026-09-10.** Measuring
it moved it past this list's entry bar: the fix turned out to need a design choice about what a
bounded catalog *is* (five open questions), and the original diagnosis here was wrong in a way that
would have sent an implementer to the wrong fix — `DTO_SCHEMA` is 543 bytes, the second-smallest
schema in its file, so this is **not** the `RULES_SCHEMA` size defect it first looked like.

Kept as a heading rather than deleted, because **numbers are never reused** and a cross-reference
written before 2026-09-10 may still name entry 14. The draft carries both defects it recorded (the
unbounded response, and the silent 250-rule input truncation that left 187 of 437 rules unable to
appear in `consumedBy`) and is the definitive record of them.

---

## 15 — On a first ingest the vector shortfall guard compares 0 against 0 and stays silent

**Measured 2026-09-10**, during Step 10 Phase 5 of
[`../active/reqs-to-data-store.md`](../active/reqs-to-data-store.md), whose
`Outcomes & Retrospective` → *Step 10 Phase 5* holds the full evidence.

`ingest_extraction` opens the `gr_statements` collection and then announces a shortfall before the
per-rule loop:

    shortfall = describe_vector_shortfall(store.count_gr(), collection.count())

On a **first** ingest into an empty store both arguments are `0`, and
`describe_vector_shortfall(0, 0)` returns `None` — confirmed by calling it directly. So no warning
is printed. But the vector half runs **after** the commit (`gr_ingest.py:1049`, "The vector half runs
AFTER the commit"), while `_stage_two`'s semantic query runs *inside* the loop — so for that entire
run the semantic half queries an empty collection and returns nothing. **The one run where the
semantic half is guaranteed blind is the one run that says nothing about it**, and `stats` afterwards
reports "379 of 379 … no shortfall" because by then the vectors exist.

**The evidence that it really is blind, not merely suspected.** A deliberately degraded ingest with
**no embedder at all** produced candidate counts identical to the fully-credentialed first ingest of
the same corpus: 148 pairs, `drift` 85, `range_overlap` 63. Had the semantic half surfaced a single
pair, they would differ. Separately, a read-only harness over the populated collection shows the
default settings *would* surface 74 pairs, **18 of them not already queued** — so the loss is real
but small, and it is a loss of reviewer suggestions, never of a rule: stage two cannot merge.

**Why this is the small half of a bigger question.** The honesty fix is contained: compare the
collection count against the number of rules **about to be ingested**, not against `count_gr()`
before the insert, so a first ingest says "the semantic half will see 0 of 437 rules this run".
That is a one-file change with a test, no schema and no migration — which is what puts it on this
list. **It must not be allowed to drift into deciding the design question underneath it**, namely
whether stage two ought to see the current run's own rules at all. Doing so means either embedding
inside the transaction (which `PR-47` deliberately refused, because embedding is the least reliable
step and must be allowed to degrade) or a second pass after the commit. That question belongs in a
draft, not here; do not fold it into this entry.

**Would touch.** `tools/legacylift_search/src/legacylift_search/gr_ingest.py` — the `shortfall`
call site around line 961, and the module docstring's account of the degraded state.
`gr_refresh.describe_vector_shortfall` itself needs no change; the defect is what ingest passes it.
A test asserting that a first ingest into an empty store emits the notice is the natural regression
case, and `pending/deferred-small-items.md` entry 5 ("`describe_vector_shortfall` has no way to say
'not measured'") is adjacent enough that whoever opens one should read the other.

---

## 16 — The value-changing-write rule is applied per *offer*, so a re-ingest bumps `updated_at` on rows that did not change

**Measured 2026-09-10**, Step 10 Phase 4 of
[`../active/reqs-to-data-store.md`](../active/reqs-to-data-store.md). Full evidence in that plan's
`Outcomes & Retrospective` → *Step 10 Phase 4*.

Step 6 states the rule plainly (plan, Step 6): *"A write that changes no value must not bump
`updated_at`… two headline claims in this plan are false without it."* Step 9 relies on it: the
export includes `created_at`/`updated_at` deliberately, "on the grounds that they change only when
the record does".

**The comparison is made per offer against the row as it currently stands, not against the row as it
stood at the start of the run.** So for a requirement that absorbs more than one offer in a single
run — the `MEAS-1` collapse population — every offer after the first legitimately differs from what
the previous offer just wrote, writes, and bumps the timestamp. Replay the same file and the
sequence replays identically: the row ends at the same values it started with, but its `updated_at`
has moved.

**Measured on the real corpus.** Re-ingesting the identical 437-rule file into the 379-row store:

| | |
|---|---|
| rows reported "merged with no value change" | 331 |
| rows whose `updated_at` moved | **48** |
| those 48 rows | **exactly** `MEAS-1`'s reading-B set (compared as sets) |
| substantive columns changed on them | **none** — `statement`, `structured_body`, both dedupe keys, `state`, `subject`, `created_at` all byte-identical |
| `gr_scenario` / `gr_edge_case` | 48 / 83 rows re-minted `scenario_id` / `edge_case_id`, content identical |

So a JSONL export taken across a re-ingest shows **48 records as modified when nothing about them
changed**. That is the failure mode Step 6's own paragraph describes — "the export diff that is
supposed to make a single reviewed wording change visible in a pull request instead shows all
several hundred records as modified" — occurring at 48 records rather than several hundred, which is
why it went unnoticed.

**What is *not* broken, so nobody widens this.** Export determinism itself holds: two exports over an
unchanged store are byte-identical (verified, 2,498,820 bytes both times). `verified_at` never
moves, and all 383 `gr_citation` rows are byte-stable. Both byte-identity acceptance criteria stand.
This entry is only about `gr.updated_at` and the two child surrogate ids.

**The fix shape.** Compare the row's **final** state for the run against the state it held when the
run began, and bump `updated_at` only if those differ — for example by memoizing each touched
`gr_id`'s original extractor-owned values on first touch within the run and doing the timestamp
decision in a post-loop pass, still inside the one transaction. The one sub-question to settle
before writing it: whether the intermediate writes should be suppressed too, or only the timestamp
decision deferred. Suppressing them changes which offer's values survive on a collapsed row, which
is `MEAS-1`-relevant behaviour and should not be altered casually — so the conservative reading is
**defer the timestamp decision only**.

**Would touch.** `tools/legacylift_search/src/legacylift_search/gr_ingest.py` — `_apply`'s
value-changing-write comparison and the per-run bookkeeping around it; possibly
`_write_children`'s scenario/edge-case refresh if the surrogate churn is fixed at the same time
(Step 3's rule already says the two child sets skip the write entirely when the incoming set
matches, so the same per-offer-versus-per-run distinction applies there). No schema change and no
migration. The regression case is a fixture where two offers collapse onto one requirement: ingest
twice and assert `updated_at` is byte-identical across the second run.

## 17 — The ingest banner's per-reason candidate tally cannot be reproduced from the store, and the mechanism throws away similarity scores

**Filed 2026-09-10** from Step 10 Phase 6 of
[`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) — the second live extraction, the
first ingest in which stage two's semantic half has ever executed against a populated collection.

**What happens.** `requirements ingest` reports merge candidates by reason:

    merge candidates raised: 374 [drift=183, range_overlap=152, semantic=39]

The store, queried immediately afterwards for the same run, holds:

    drift=183   range_overlap=177   semantic=14

The totals agree at 374 and the breakdown disagrees by exactly 25 rows in each direction.

**Why.** `KnowledgeStore.record_gr_merge_candidate` treats the **pair** as the primary key, with
`run_id` deliberately outside it, and its documented contract is that a later raise of an existing
`unresolved` pair may refresh `similarity` and `reason`. It returns `True` only on an INSERT.
`gr_ingest._raise_candidate` increments `result.candidate_reasons[reason]` **only when that returns
`True`**. So a pair the semantic half inserts, and the structural half then re-raises later in the
same run, is counted once as `semantic` and stored as `range_overlap` — and the UPDATE overwrites
`similarity` with the structural raise's `None`.

**The evidence.** Confirmed by probe, not by arithmetic, because the arithmetic alone is consistent
with several stories. Two raises of one pair against a throwaway store:

    raise 1 (semantic,      sim=0.91): returned True    stored reason='semantic'      similarity=0.91
    raise 2 (range_overlap, sim=None): returned False   stored reason='range_overlap' similarity=None

`run_id` correctly keeps its first-raiser meaning. On the real Phase 6 corpus this is 25 of the 39
semantic pairs: **the 14 that survive carry similarities between 0.7422 and 0.9391, and the 25 that
did not are indistinguishable from structural finds.**

**Why it is small, and why it is not nothing.** Stage two never merges, so no rule was lost or
wrongly combined, and all 374 pairs are queued for review either way — this cannot cost a
requirement. What it costs is (a) a reviewer's ordering signal: 25 pairs that a similarity score
would have ranked now sort with the unscored structural finds, and (b) the credibility of a banner
line, which is the only place the per-reason split is ever shown and which no query can reproduce.
It also means **any future measurement of how much the semantic half contributes will read low**
unless it counts raises rather than rows — and the semantic half's contribution was an open question
in this plan for two milestones.

**The fix shape, and the one decision it needs.** Two independent halves:

1. *The tally.* Count raises rather than inserts — have `_raise_candidate` increment
   `candidate_reasons` regardless of the return value, or have `record_gr_merge_candidate` report
   which of insert/refresh/left-alone happened (a three-valued return, which entry 4's
   `EmbedResult`-shaped problem also wants) so the banner can say "374 raised, 349 rows" honestly.
2. *The score.* Do not let a refresh replace a non-NULL `similarity` with NULL. The narrow form is
   `similarity = COALESCE(?, similarity)`; the question it raises is whether `reason` should then
   also be sticky, or whether a pair found *both* ways is best described by a compound reason. **A
   `reason` value like `semantic+range_overlap` is not in the column's `CHECK`**, so anything beyond
   COALESCE is a schema change and belongs in a design conversation rather than here.

The conservative change is (1) plus the COALESCE half of (2): both are behaviour-preserving for
merging, neither needs a migration, and together they make the banner and the store agree.

**Would touch.** `tools/legacylift_search/src/legacylift_search/gr_ingest.py`
(`_raise_candidate`, and `IngestResult.candidate_reasons`' meaning) and
`knowledge_store.py` (`record_gr_merge_candidate`'s UPDATE and its return contract, whose docstring
would need to say what the new value means). No schema change under the conservative reading. The
regression case is two raises of one pair with the semantic one first: assert the stored
`similarity` survives, and assert the banner's reason total equals the number of raises rather than
the number of rows.

**Related.** Entry 15 is the other place a stage-two signal is silently absent rather than reported.
Entry 4 wants the same three-valued-return treatment for `set_state`'s dropped `EmbedResult`. Unlike
the four entries that want the first `knowledge.sqlite` column migration, **this one needs no
migration**, so it does not have to wait for them.
