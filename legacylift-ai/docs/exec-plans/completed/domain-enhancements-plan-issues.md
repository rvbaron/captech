# Review Issues — `domain-enhancements-plan.md`

Review date: 2026-07-17. Reviewer: Claude (Opus 4.8), at Darrell Norton's request.
Cross-checked against `tools/legacylift_search/src/legacylift_search/store.py`,
`vector_store.py`, and `config.py`.

Ordered by severity.

---

## Substantive issues

### 1. Milestone 1 under-specifies the `symbol_facts` relocation — two real problems it doesn't solve

> **RESOLVED (2026-07-17).** The plan was revised so that `symbol_facts` is **not**
> relocated — it stays in `index.sqlite` with both foreign keys and the `upsert_facts`
> orphan-drop guard intact. Only the authored, non-re-derivable domain tables
> (`domains`, `domain_edges`, `file_domains`) go into the durable `knowledge.sqlite`.
> This dissolves the issue entirely without changing `--reset`, because facts are
> re-derivable on reindex and every `--reset` re-embeds Chroma anyway (the dominant
> cost). Relocating `symbol_facts` to a shared store is deferred to the cloud-migration
> follow-on, where the FK-replacement work will be done deliberately. See the plan's
> Decision Log (2026-07-17 revision), the rewritten Milestone 1, and Revision Notes.
> The analysis below is retained as the record of *why*.

The plan says to move `symbol_facts` and "the two foreign keys re-expressed for
cross-database reality" (line 162), but only actually addresses one of the two FKs,
and glosses over the `file_id` column entirely.

- **SQLite cannot declare a cross-database foreign key at all.** A FK must reference
  a table in the *same* database file. So "re-expressed for cross-database reality"
  isn't actionable as written — both FKs (`repo_files(id)` and `symbols(id)`) must be
  *dropped*, not re-expressed, and replaced with application logic. The plan only
  replaces the `file_id`→`repo_files` cascade (with `DELETE ... WHERE relative_path = ?`).
- **The `subject_symbol_id`→`symbols(id)` FK is a load-bearing correctness guard, and
  the plan silently loses it.** In `upsert_facts` (store.py:657), the
  `INSERT OR REPLACE` relies on that FK raising `IntegrityError` to *drop and report
  orphaned facts* whose subject symbol wasn't persisted. Once `symbol_facts` lives in a
  DB with no `symbols` table, that guard vanishes and orphaned facts get silently
  inserted instead of dropped. The plan never mentions replacing this behavior.
- **The `file_id NOT NULL` column becomes meaningless/unstable.** `upsert_facts`
  resolves `file_id` via `_get_file_id()` against `repo_files` in the *same* store
  (store.py:623), and `file_id` is a rowid that is reassigned on every `--reset`
  rebuild of `index.sqlite`. Moving the table without dropping `file_id` stores a
  dangling reference into a foreign DB. The plan's own `SymbolFact` field list
  (line 133) omits `file_id`, so it hasn't reckoned with the fact that the *table* has
  it and `upsert_facts` requires it. The relocation needs to either drop the column or
  re-derive it — this isn't stated.

This is the milestone everything else builds on, so it deserves to be tightened.

### 2. Milestone 7's freshness metric conflates "untagged" and "unassigned" — and is internally contradictory

> **RESOLVED (2026-07-17).** Milestone 7 was rewritten around a single coherent model:
> *untagged* (no `file_domains` row) is the **only** staleness signal; *unassigned* (a
> row pointing at the reserved bucket) is an **accepted gap** and never forces `stale`.
> To make that stick, the semantics of the two writers were pinned down: `tag-domains`
> (the explicit assess-driven pass) writes `unassigned` rows for current non-matches,
> while the indexer's 7-Auto writes only `glob`-match rows and leaves non-matching new
> files **untagged** — so a genuinely new/unclassified file surfaces as `stale` exactly
> as the Purpose promises, and goes quiet once an assess/`tag-domains` pass reviews it.
> `validate` is `stale` iff untagged > 0, `fresh` otherwise, and always prints
> `coverage%` + the `unassigned` count (with untagged split into glob-matchable vs
> need-assess). The contradictory acceptance test was replaced. See the plan's Decision
> Log (second 2026-07-17 revision), the rewritten Milestone 7, and the tightened
> Milestone 4/5 writer semantics. The analysis below is retained as the record of *why*.

The plan defines two distinct states (line 289): *untagged* = a discovered file with
**no** `file_domains` row; *unassigned* = a file with a row pointing at the reserved
`unassigned` domain. But:

- After any `tag-domains` run, **every discovered file gets a row** (unmatched →
  `unassigned`), so "untagged" is 0 by construction. Yet the Milestone 7 acceptance
  (line 291) says `validate` should show `stale` "with the count of the
  intentionally-unmatched `annotations/`+`hierarchy/` files as untagged/unassigned" —
  treating them as untagged when they're actually `unassigned`.
- The freshness rule "fresh when there are zero untagged files and no `unassigned`-only
  gap beyond a small tolerance" is fuzzy and conflicts with the Purpose's stated design,
  where `Unassigned` is a *legitimate, permanent* bucket for code assess deliberately
  excluded. If `unassigned` files count against freshness, `validate` will report
  `stale` forever on any real repo. If they don't, the acceptance test (unmatched dirs →
  stale) fails. These two can't both be true as written.

The concept needs to be pinned down: staleness should key on *newly-discovered files
with no row yet* (genuinely new/untagged), not on the deliberate `unassigned` bucket —
but then the M7 acceptance needs rewriting, because tag-domains leaves nothing untagged.

### 3. Manual corrections don't propagate to Chroma → vector vs. lexical domain filter diverge (M5 ↔ M6)

> **RESOLVED (2026-07-17).** A companion invariant was added: a chunk's Chroma `domain`
> is a **derived mirror of the authoritative `file_domains` row** (glob *or* manual), and
> both stampers maintain it. Concretely: (1) 7-Auto no longer leaves a manual file's
> Chroma metadata untouched — it never overwrites the manual *row*, but when it re-embeds
> that file it stamps Chroma with the *manual* row's domain, not a recomputed glob value;
> (2) `tag-domains` stamps from **every** `file_domains` row including manual, so a re-run
> reconciles Chroma to any hand-edits with no re-embedding — the supported way to make a
> manual correction take effect on the vector side; (3) M6 now notes the two sides stay
> consistent because both derive from `file_domains`. M5 acceptance (b) was strengthened
> to assert Chroma actually reads the manual domain (not merely "not reverted"), plus the
> reconcile path. One dependency remains: the `update_domain_metadata` helper must *merge*
> the `domain` key rather than replace the whole metadata dict — that is open issue #4.
> See the plan's authored-vs-derived invariant, Milestone 4 stamp step, and Milestone 5.
>
> **Visibility follow-up (2026-07-17):** because manual rows are deliberately never
> overwritten, they must never be *invisible* either. `tag-domains` and the indexer both
> emit an explicit notice when `source='manual'` rows exist (count + paths for tag-domains;
> total count on any reindex), and `validate` shows a `N manual` field plus a "manual
> override(s) preserved; not overwritten" note. So an operator always knows overrides are
> present and being honored. The analysis below is retained as the record of *why*.

Milestone 5 says a `manual` row is skipped by the indexer, leaving "both the row and the
Chroma metadata for that file untouched" (line 263). But Milestone 6's vector-side
`--domain` filter reads Chroma's `domain` metadata, while the lexical side reads
`files_for_domain()` from the knowledge DB. When a human sets a `manual` row to a
*different* domain than the glob assigned, the SQLite row changes but Chroma still
carries the old glob `domain`. So:

- lexical search will treat the file as the manual domain,
- vector search (Chroma `where`) will still treat it as the old domain.

M6 filtered results become inconsistent, and there is no path in scope to restamp Chroma
for a manual correction (correction tooling is deferred). M5's acceptance (b) even
sidesteps this — it only asserts Chroma "was not reverted to `core-services`," which is
trivially true because the manual edit never touched Chroma at all. The plan should
either restamp Chroma on manual edits or explicitly acknowledge that manual corrections
don't affect vector-side filtering in v1.

### 4. Chroma metadata `update` may *replace* rather than *merge* — verify before relying on it

> **RESOLVED (2026-07-17) — verified MERGE.** Empirical probe against the pinned
> chromadb 1.5.9: a record carrying the eight `upsert_chunks` metadata keys, updated with
> `collection.update(ids=[id], metadatas=[{"domain": "core-services"}])`, read back with
> **all eight original keys intact plus `domain`**. So `update` merges the supplied keys;
> passing only `{"domain": ...}` is safe and `update_domain_metadata` needs no
> read-merge-write. Recorded in the plan's Surprises & Discoveries; the Milestone 4 stamp
> step and Interfaces note were simplified accordingly. Caveat: this is version-specific —
> it holds for the pinned 1.5.9; a chromadb upgrade should re-run the probe (preserved
> verbatim in the plan's "Artifacts and Notes" section). The probe also surfaced a benign Chroma
> Rust-backend teardown panic on Windows process exit (teardown-only, after results
> return; unrelated to correctness). The analysis below is retained as the record of *why*.

Milestone 4 (line 250) stamps `domain` via
`collection.update(ids=[...], metadatas=[{"domain": domain_id}])`. In several chromadb
versions, `update`/`upsert` **replaces the entire metadata dict** for an id rather than
merging a single key — which would wipe the existing keys (`relative_path`, `language`,
`chunk_kind`, `symbol_id`, etc. set in `upsert_chunks`, vector_store.py:112–121). If
that's the behavior in the pinned chromadb 1.5.9, `update_domain_metadata` must
read-merge-write (fetch current metadata, add `domain`, write back) rather than pass
`{"domain": ...}` alone. This is worth verifying explicitly given the metadata is relied
on elsewhere (e.g. the M6 `where` filter, and search result rendering). Right now the
plan assumes a partial-key merge without confirming it.

---

## Smaller issues

### 5. `display_order` has no source at ingest time

> **RESOLVED (2026-07-17).** M4's resolver now states `display_order` is assigned by the
> ingest step from each domain's position in the `domains.json` array (index 0, 1, 2, …).

Precedence is defined as declaration order via `display_order` (lines 249, 181), but the
`domains.json` schema (Milestone 3, lines 215–229) has **no `display_order` field**. The
plan never says ingest derives it from the JSON array index. Since precedence
(first-matching-domain-wins) is a determinism-critical rule, this needs to be stated:
`display_order = array position in domains.json`.

### 6. Cross-database join in Milestone 2 is described as SQL but can't be

> **RESOLVED (2026-07-17).** M2's `domains` command now spells out that the two tables
> live in separate files and gives two valid mechanisms: `ATTACH DATABASE` (read-only) on
> the knowledge connection, or a Python-side join over two read-only connections.

The `domains` command "join[s] `file_domains` to the index `chunks` table on
`relative_path`" (line 204). Those tables live in two separate `.sqlite` files, so this
requires either `ATTACH DATABASE` or a Python-side join across two connections. The plan
says "open both stores read-only" (implying Python-side), but the "joining" language is
misleading. Milestone 6 correctly acknowledges the cross-DB limitation for FTS5 — M2
should get the same explicit treatment.

### 7. `pathspec` vs `fnmatch` is left as an either/or, but they have different glob semantics

> **RESOLVED (2026-07-17).** M4's resolver now commits to `pathspec` `gitwildmatch` and
> explicitly rules out `fnmatch` (differing `*`/`**`/separator semantics would make
> resolution non-deterministic vs. how assess authors globs).

Milestone 4 (line 249) says match "using `pathspec` … or `fnmatch`." These differ
materially (`**` crossing `/`, `*` behavior, anchoring). For a *deterministic* resolver
whose output must be stable and match how assess authors globs, this can't be an
implementer's coin-flip — pick one and specify the semantics. (pathspec's gitwildmatch
is the natural choice since discovery already uses it.)

### 8. `.gitignore` rule for `.sqlite` won't cover WAL sidecar files

> **RESOLVED (2026-07-17).** Two parts. **Part A (gitignore):** M1 and Context/Orientation
> now specify concrete rules — the durable dir sits *outside* the already-ignored `index/`
> path, so nothing covered it; added `repos/*/legacylift-docs/knowledge/knowledge.sqlite*`
> (+ the `*/*` variant), where the trailing `*` catches the `-wal`/`-shm` siblings.
> **Part B (fixture pollution):** verified the pytest suite already copies the fixture to a
> temp dir (`shutil.copytree`), so tests never pollute; only the plan's Concrete Steps ran
> in place. Rewrote Concrete Steps to `cp -r` the fixture to a scratch `$REPO` outside the
> tree and use `--repo-root "$REPO"` throughout — so no fixture-path ignore is needed and
> `git status` stays clean. The analysis below is retained as the record of *why*.

Line 124 says add a gitignore rule "for the `.sqlite` file specifically." But
`KnowledgeStore` opens in WAL mode (per line 160, "copy the pragma setup"), which
produces `knowledge.sqlite-wal` and `knowledge.sqlite-shm` alongside it. The rule should
be `knowledge.sqlite*` (or the whole dir contents), or those sidecars will show up as
untracked. Related: the bundled fixture at `tests/fixtures/polyglot_repo` is **not**
under `repos/*`, so the existing `repos/*/legacylift-docs/index/` ignore rule won't cover
the fixture's generated `legacylift-docs/`, and the Concrete Steps run
`index`/`tag-domains` directly against the fixture tree — this will dirty git status
unless a fixture-scoped ignore is added or tests use a temp copy.

### 9. `domain_edges` PK allows duplicate NULL-`kind` edges

> **RESOLVED (2026-07-17).** Schema changed to `kind TEXT NOT NULL DEFAULT ''`, so the PK
> dedupes edges even when assess omits a `kind`.

Schema (lines 184–190): `PRIMARY KEY (from_domain, to_domain, kind)` with `kind TEXT`
nullable. In SQLite, NULLs are distinct in a multi-column PK, so two edges with the same
from/to and `kind IS NULL` won't be deduped by `INSERT OR REPLACE`. The examples always
supply `kind`, but if assess ever emits an edge without one, idempotence breaks. Either
make `kind` `NOT NULL DEFAULT ''` or note the assumption.

### 10. Pydantic reserved-word field `from`

> **RESOLVED (2026-07-17).** Interfaces section now notes the edge model needs
> `from_: str = Field(alias="from")` with `populate_by_name=True`.

The `domains.json` edges use keys `"from"` / `"to"` (line 227). `from` is a Python
keyword, so the `DomainsFile`/edge Pydantic model (line 425) can't have a field literally
named `from` — it needs `Field(alias="from")` with `from_` (and
`populate_by_name`/`by_alias`). Trivial, but worth a one-line note so the implementer
doesn't trip.

### 11. Editing artifacts / typos left in the prose

> **RESOLVED (2026-07-17).** All four cleaned up: the M1 `get_present_...` garble and the
> Interfaces `delete_facts_for_path` line were removed by the issue-1 rewrite; the M2
> `render_architecture_source()` sentence was rewritten; and `untanged` → `untagged` was
> fixed during the issue-3 work.

- Line 160: "…the facts query used by the `facts` command, `get_present_...` — no; move
  only the fact-specific methods…" — a mid-thought self-correction left inline; garbled.
- Line 202: "Add a new `render_architecture_source()` is deferred to Milestone 8." —
  incoherent sentence (an "add a new X" merged with "X is deferred").
- Line 263: "files remain untanged" → "untagged".
- Interfaces (line 412) introduces `delete_facts_for_path(relative_path)` as the
  KnowledgeStore method name, but Milestone 1's body only calls it "the fact-cleanup
  portion of `clear_reindex_artifacts`" and never names it — minor naming inconsistency
  between the two sections.

---

## What's solid
The authored-vs-derived invariant, the separate-DB rationale, the `manual`-wins
precedence design, the idempotence story, and the milestone dependency ordering are all
coherent and well-justified. The `--reset` durability motivation (Surprises) checks out
exactly against `store.py:345` and the index-dir lifecycle in `config.py`.

The two to treat as blocking before implementation start are **#1** (the M1 relocation
is the foundation and currently loses a correctness guard) and **#2** (the M7 freshness
definition is self-contradictory). #3 and #4 should be resolved before M4/M6 land.

---
---

# Second review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell
Norton's request. This pass reviews the plan *after* issues #1–#11 were resolved and
folded in. Cross-checked against
`tools/legacylift_search/src/legacylift_search/{config,store,vector_store,indexer,discovery,models}.py`
and `.claude/skills/code-modernization/commands/modernize-assess.md`.

The durable-store foundation (M1–M2), the tagging/precedence core (M4), and the
freshness model (M7) are well specified and match the code. The new findings below
cluster in **Milestone 8** (the `render-architecture` command's path + timing story) and
in two cross-stamper consistency details. Ordered by severity.

## Substantive issues

### 12. `render-architecture` default output path is not derivable from `--repo-root` (M8)

> **RESOLVED (2026-07-17).** M8 rewritten: the command **defaults to stdout**, `--output <path>`
> writes a file, and the unreachable `analysis/<system>/ARCHITECTURE.mmd` default is dropped
> (no `--system` flag). assess supplies the `analysis/$1/ARCHITECTURE.mmd` path itself via an
> explicit `--output`, keeping that convention inside the skill that owns it. See the rewritten
> Milestone 8 and its Interfaces note. Analysis below retained as the record of *why*.

Status: **RESOLVED.**

Milestone 8 states the command "default[s] the output to `analysis/<system>/ARCHITECTURE.mmd`."
Verified against `modernize-assess.md:241`: `analysis/$1/` is a **`modernize-assess`
convention** where `$1` is the *system subdirectory name* and the `analysis/` dir is a
sibling/parent-level artifact of the assess run — **not** a path under the repo being
indexed. A `legacylift-search` command invoked as `render-architecture --repo-root <system-dir>`
has no input from which to derive `<system>` or locate `analysis/`; the command signature
in M8 has no `--system` parameter. As written the default is unreachable/wrong.

Consequence: an implementer either hard-codes a path the command can't compute, or the
default silently writes somewhere unexpected. The only workable forms are (a) assess
invokes the command with an explicit `--output analysis/$1/ARCHITECTURE.mmd`, or (b) the
default points somewhere `legacylift-search` actually owns (stdout, or under
`legacylift-docs/`). The plan should drop the `analysis/<system>/` default and pin one of
these.

### 13. The derived diagram cannot be produced during the assess run (M8 sequencing gap)

> **RESOLVED (2026-07-17) — Option B, single code path.** The renderer sources from **either**
> `domains.json` (`--domains`) **or** SQLite (default), through one `render_architecture_mermaid`
> function. assess **shells out** to `render-architecture --domains analysis/$1/domains.json
> --output analysis/$1/ARCHITECTURE.mmd` in Step 6 — so the diagram still exists at the end of
> the assess run (rendered from the just-authored `domains.json`, no SQLite needed), and the LLM
> never hand-authors Mermaid. After `tag-domains`, re-running `render-architecture` without
> `--domains` regenerates it authoritatively from the stored tags (drift-free). Both sources use
> the same `load_domains_json`/`display_order` assignment, so output is source-independent — an
> acceptance test asserts byte-identical output between the two. See the rewritten Milestone 8,
> its Interfaces note, and the updated Concrete Steps. Analysis below retained as the record of *why*.

Status: **RESOLVED.**

Domains land in SQLite only after `tag-domains`, and the plan's own sequencing is
`index → assess → tag-domains`. So at assess time (Step 6) **no domain rows exist yet** —
calling `render-architecture` then would render an empty diagram. M8 has assess *stop*
writing `ARCHITECTURE.mmd` (currently written inline at `modernize-assess.md:241`) but
never says who runs `render-architecture`, or when, or updates assess's Step 7 "Present"
(`modernize-assess.md:244-247`), which today points the user at the generated outputs.

Net effect of M8 as written: after this change, `ARCHITECTURE.mmd` simply does not exist
at the end of an assess run — it can only be produced by a later, unspecified manual step
after `tag-domains`. The plan needs to place `render-architecture` explicitly in the
post-`tag-domains` sequence and reconcile the assess UX (Step 6/Step 7) with that timing.

### 14. `list_domains()` ordering is not pinned to `display_order`, but glob precedence depends on it (M2/M4/M5)

> **RESOLVED (2026-07-17).** M2 now specifies `list_domains()` returns `ORDER BY display_order,
> domain_id`, and M4's resolver contract states precedence is the order of the `domains` argument
> (the resolver trusts caller order and does not re-sort) — so both callers pass `display_order`
> order: `tag-domains` via the `domains.json` array, the indexer via the now-sorted
> `list_domains()`. The Interfaces signature carries the ordering note. See rewritten M2 query-API
> paragraph and M4 resolver bullet. Analysis below retained as the record of *why*.

Status: **RESOLVED.**

Issue #5 (resolved) established `display_order = domains.json array position`, and M4
defines glob precedence as declaration order. `tag-domains` gets that order straight from
the JSON array. But the indexer's 7-Auto (M5) loads domains **from the DB** via
`list_domains()` and calls the *same* `resolve_file_domains`. If `list_domains()` returns
rows in PK (`domain_id`) or physical-insertion order rather than `display_order`, an
ambiguous file (matched by two domains' globs) can resolve to a **different** domain
during reindex than it did during `tag-domains` — a silent divergence between the two
stampers that also violates the authored-vs-derived invariant (glob resolution is
supposed to be a deterministic function of the authored data).

The plan never states the ordering guarantee. Fix: require `list_domains()` to return
ordered by `display_order` (and have `resolve_file_domains` rely on input order, or sort
internally by `display_order`). This is a one-line contract but currently only implied.

### 15. Chroma stamp assumes every chunk id exists as a vector (M4)

> **RESOLVED (2026-07-17).** M4's stamp step now states `SELECT id FROM chunks` can return ids that
> were never embedded (`embed_min_tokens > 0` skips below-threshold chunks at embed time), so
> `update_domain_metadata` must tolerate ids absent from Chroma — preferably by restricting to the
> `vectors_present` cache, or wrapping `collection.update(...)` defensively as `delete_chunks`
> already does (`vector_store.py:143-147`). The Interfaces signature carries the same note. Called
> out as a scale-only path (fixture default `embed_min_tokens=0` embeds everything). See M4 stamp
> bullet. Analysis below retained as the record of *why*.

Status: **RESOLVED.**

The M4 stamp step does `SELECT id FROM chunks WHERE relative_path = ?` then
`collection.update(ids=..., metadatas=[{"domain": ...}])`. But `embed_min_tokens`
(`config.py:129-135`) skips below-threshold chunks at **embed** time — those chunk ids
exist in `index.sqlite`/FTS5 but **not** in Chroma. Calling `collection.update` on an id
absent from the collection can raise/warn depending on chromadb version.

On the fixture the default `embed_min_tokens=0` embeds everything, so this is invisible in
milestone validation but becomes a real failure at scale (any repo run with a non-zero
threshold). Note `delete_chunks` already wraps this exact hazard in try/except
(`vector_store.py:143-147`) precisely because ids may be absent. `update_domain_metadata`
should either restrict to ids present in the `vectors_present` cache or tolerate missing
ids the same way. Worth stating in M4 so it isn't discovered at ctcm scale.

### 16. CapTech attribution: M3 reads as *adding* a comment rather than *overwriting* the existing one (M3)

> **RESOLVED (2026-07-17).** M3 now quotes the `CLAUDE.md` "latest only / overwrite, don't append"
> rule and instructs **replacing** the single existing line at `modernize-assess.md:6` (immediately
> after the frontmatter), not adding a second comment. The replacement line describes the combined
> M3+M8 change set to this file; M8's attribution instruction was reconciled to leave the line as-is
> when it lands same-date as M3 (else replace in place — never append). See rewritten M3 Work
> paragraph and the M8 attribution note. Analysis below retained as the record of *why*.

Status: **RESOLVED.**

`modernize-assess.md:6` already carries a `2026-06-30` attribution comment (the Step-3
discovery-substrate note). `CLAUDE.md` is explicit: "Keep only the **latest**
modification — do not accumulate a history. Overwrite the existing line rather than
appending a new one." M3 (plan lines 248-250) presents a fresh attribution comment and
its sample text drops the existing note's content. Followed literally, M3 either
accumulates two attribution lines (violating `CLAUDE.md`) or discards the prior note's
description without acknowledgement.

Fix: M3 should say *replace* line 6, and decide deliberately whether the merged line
should still mention the Step-3 discovery-substrate change (per `CLAUDE.md`'s "latest
only" rule, dropping it is compliant, but that should be an explicit choice, not an
accident). M8's "refresh the attribution line" wording is already correct for its edit.

## Smaller issues

### 17. `resolve_file_domains(files: list[str], …)` vs. discovery's `list[SourceFile]`

> **RESOLVED (2026-07-17).** M4's "Discovered file set" note now spells out the
> `[sf.relative_path for sf in discover_source_files(...)]` adapter.

Status: **RESOLVED (trivial).** `discover_source_files` returns `list[SourceFile]`
(`discovery.py:35`), not `list[str]`. The interface (plan line 497) and the "reuse the
discovery function" instruction gloss the `[sf.relative_path for sf in ...]` mapping.
`SourceFile.relative_path` exists (`models.py:93`), so this is a one-line adapter — just
worth naming so it isn't missed.

### 18. "Keep the `knowledge/` directory tracked" is not achievable as stated (M1)

> **RESOLVED (2026-07-17).** The "keep the directory tracked" language is gone from both M1 and
> Context/Orientation. New wording: the `knowledge/` dir is **not** committed (git can't track an
> empty dir; its only content is the gitignored DB) and `KnowledgeStore.__init__`
> `mkdir(parents=True, exist_ok=True)`s its parent at runtime, so no `.gitkeep` is needed.

Status: **RESOLVED (minor).** Git cannot track an empty directory. If the only content of
`legacylift-docs/knowledge/` is the gitignored `knowledge.sqlite*`, a fresh clone won't
contain the directory at all. If the intent is for the dir to exist in-repo, it needs a
tracked placeholder (`.gitkeep`); otherwise the phrase is misleading. In practice
`KnowledgeStore.__init__` should `mkdir(parents=True)` its parent (the plan should state
this — it currently only says "copy the pragma setup from `SQLiteStore.__init__`"), which
makes the "tracked directory" language unnecessary. Pick one and say it.

### 19. `domains` / `stats` / `validate` behavior when a sibling DB is absent (M2/M7)

> **RESOLVED (2026-07-17).** M2 now specifies: absent `index.sqlite` → chunk counts `0`/`n/a`
> (don't let `ATTACH` throw); absent/empty `knowledge.sqlite` → `domains`/`stats` print a
> "no domains — run `tag-domains`" line. M7 now reports `domains: missing` when the `domains`
> table is empty **or `knowledge.sqlite` doesn't exist**, without throwing on the absent file.

Status: **RESOLVED (minor).** M2's chunk-count join relies on `ATTACH DATABASE '<index.sqlite>'`;
if `index` has never run, `index.sqlite` doesn't exist and the ATTACH fails. Likewise
`stats`/`validate` assume `knowledge.sqlite` exists. These read paths should degrade
gracefully (zero counts / "not indexed" / "domains: missing") rather than throw an
unhandled exception. Not covered in the plan.

### 20. `render-architecture` Shared/Core detection is unspecified (M8)

> **RESOLVED (2026-07-17).** M8 now pins detection to a reserved slug: a domain whose `domain_id`
> is in `{"shared", "core"}` (exact kebab-slug match) is the cross-cutting node; no match → every
> domain renders ordinarily. Deterministic, no schema flag needed (a `kind` column is noted as a
> future extension).

Status: **RESOLVED (minor).** M8 says a `Shared`/`Core` domain "if present" renders as a
cross-cutting node with no dependency arrows, but never says *how* the renderer
identifies it — by `domain_id`, display name, or an explicit flag. Deterministic
rendering needs a concrete rule (or the special-casing is unimplementable).

### 21. The shared resolver's `unassigned` return has two different caller contracts, stated only implicitly (M4/M5/M7)

> **RESOLVED (2026-07-17).** The Interfaces section now carries an explicit note on
> `resolve_file_domains`: it returns `("unassigned", 1.0)` for non-matches, `tag-domains`
> **persists** that row while the indexer's 7-Auto **drops** it (leaves untagged, driving the M7
> freshness signal) — the single authoritative statement of the split contract.

Status: **RESOLVED (minor).** `resolve_file_domains` returns `("unassigned", 1.0)` for
non-matches; `tag-domains` **persists** that as an `unassigned` row while the indexer
(M5) must **drop** it (leave the file untagged, which is what drives the M7 freshness
signal). This split contract is correct and is described across M4/M5/M7, but never
stated as a single explicit note on the resolver itself. One sentence in the Interfaces
section would stop an indexer-path implementer from accidentally persisting `unassigned`
rows and silently breaking the M7 "stale on new/unclassified file" behavior.

## Assessment

No blocking errors in M1–M2, M4, or M7 — the previously-resolved issues #1–#11 hold up and
the foundation matches the code. The real risks are **#12 and #13** (both Milestone 8 — the
`render-architecture` command's path and timing story is genuinely underspecified and
should be resolved *before* M8 is built), followed by **#14 and #15** (cross-stamper
consistency + at-scale robustness, resolve before M5/M4 land respectively). #16–#21 are
plan-text tightening that can be folded in as the milestones are implemented.

**Update (2026-07-17): all second-pass findings #12–#21 RESOLVED and folded into the plan.**
- #12 — `render-architecture` defaults to stdout; assess passes `--output` explicitly (no `--system`).
- #13 — Option B, single renderer sourced from `domains.json` *or* SQLite; assess shells out to it.
- #14 — `list_domains()` pinned to `ORDER BY display_order, domain_id`; resolver trusts caller order.
- #15 — `update_domain_metadata` must tolerate chunk ids absent from Chroma (`embed_min_tokens`).
- #16 — M3 replaces the single CapTech attribution line (no accumulation); M8 reconciled.
- #17 — `resolve_file_domains` list-adapter (`sf.relative_path`) named in M4.
- #18 — `knowledge/` dir not committed; created at runtime by `KnowledgeStore.__init__`.
- #19 — `domains`/`stats`/`validate` degrade gracefully when a sibling DB is absent.
- #20 — Shared/Core detected by reserved slug `{"shared","core"}`.
- #21 — resolver's dual `unassigned` caller contract stated once in Interfaces.

No open issues remain from the first two review passes.

---
---

# Third review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell
Norton's request. This pass reviews the plan *after* issues #1–#21 were resolved and
folded in, cross-checking every remaining structural claim against the actual indexer,
search, and vector-store code paths (not just the schema/store layer the first two passes
focused on). Cross-checked against
`tools/legacylift_search/src/legacylift_search/{indexer,search,vector_store,config,discovery}.py`.

The foundation (M1–M2), tagging core (M4), freshness model (M7), and render story (M8)
all hold up. The new findings cluster in **Milestone 5** (the plan's mental model of "one
embed/upsert phase" doesn't match the real shared-helper-with-two-callers structure) and
in **Milestone 6** (the lexical post-filter needs a knowledge-store handle the interface
doesn't wire up), plus three smaller spec tightenings. Ordered by severity.

## Substantive issues

### 22. The Chroma upsert is a shared helper with two callers — M5's inline stamp is plumbed for neither, and the backfill path never opens the knowledge store (M1/M5)

> **RESOLVED (2026-07-17).** M5 now names `_embed_and_upsert` (`indexer.py:776`) as the single
> shared Chroma-upsert site (upsert at `:868`) called by **both** `run()` (`:705`) and
> `backfill_vectors()` (`:1009`), and states that threading `domain_by_chunk` means extending
> that helper's signature and supplying the map (or `None`) from both call sites. It also pins
> down the backfill path: `backfill_vectors()` does **not** open a knowledge store, so a
> `--reset` completed via `backfill-vectors` re-creates all vectors with no `domain` metadata —
> M5 now requires `backfill_vectors()` to open the knowledge store and pass the domain map too,
> and the Recovery section documents the `tag-domains` reconcile as the fallback. The
> text-dedup fan-out keying (`domain_by_chunk` keyed by `chunk.id`, covering every fanned
> member) is stated. See the rewritten Milestone 5, the Recovery section, and the Interfaces
> note on `_embed_and_upsert`. Analysis below retained as the record of *why*.

Status: **RESOLVED.**

Milestone 5 says to "stamp its chunks' Chroma metadata inline during the embed/upsert
phase" and thread `domain_by_chunk` into `upsert_chunks`, treating the upsert as one
directly-reachable site. It isn't. The `vector_store.upsert_chunks(...)` call is at
`indexer.py:868`, inside `_embed_and_upsert(self, todo_chunks, embedder, vector_store,
store, _log, phase_label)` (`indexer.py:776`) — which takes no knowledge-store or domain
input. That helper is called from **two** places: `run()` (`indexer.py:705`) and
`backfill_vectors()` (`indexer.py:1009`).

`backfill_vectors()` opens its own `SQLiteStore` (`indexer.py:959`) but **never opens a
knowledge store**. It is the documented resume path for an interrupted `--reset`
(`indexer.py:914-920`), and on a cold `--reset` *every* chunk is missing
(`get_chunks_missing_vectors`), so a reset completed via `backfill-vectors` re-creates all
vectors through this shared helper. Result: even though `knowledge.sqlite` survives the
reset and `file_domains` rows persist, the rebuilt Chroma vectors carry **no `domain`
metadata**, so `search --domain` (M6, vector side) silently returns nothing for those
chunks until a `tag-domains` reconcile runs. The Recovery section previously prescribed a
`tag-domains` reconcile only after a *knowledge*-DB rebuild, not after a backfill-completed
*index* rebuild. Also, the text-dedup fan-out (`indexer.py:859-866`) means the domain map
must be keyed by `chunk.id` and cover every fanned member, not just the representative.

### 23. `SearchEngine` has no `KnowledgeStore` handle, which M6's lexical post-filter requires (M6)

> **RESOLVED (2026-07-17).** M6 now specifies that the CLI resolves the domain and passes the
> in-domain path set (from `KnowledgeStore.files_for_domain(domain_id)`) plus the `domain_id`
> into `SearchEngine`, and that the lexical drop happens in the fusion loop (`search.py:114`,
> where `chunk.relative_path` is in hand) rather than inside `_lexical_ranks` (which only has
> chunk ids). The Interfaces section carries the `SearchEngine.search(...)` / constructor change.
> See the rewritten Milestone 6 and Interfaces. Analysis below retained as the record of *why*.

Status: **RESOLVED.**

`SearchEngine.__init__` is `(store, vector_store, embedder, config)` (`search.py:37-47`).
M6 says the lexical side should "drop any result whose `relative_path` is not in
`KnowledgeStore.files_for_domain(domain_id)`," but nothing wires a knowledge store (or a
precomputed in-domain path set) into `SearchEngine`, and the Interfaces section listed no
`SearchEngine` change. Additionally, `_lexical_ranks` (`search.py:62`) returns only
`chunk_id → rank` — it has no `relative_path` to filter on. The natural filter point is the
main fusion loop at `search.py:114`, where `chunk = self.store.get_chunk(chunk_id)` already
yields `chunk.relative_path`. M6's "drop inside `_lexical_ranks`" phrasing is therefore
both under-wired (no store) and mis-located (no path there).

## Smaller issues

### 24. "byte-identical" is a fragile acceptance criterion for a live WAL SQLite DB (M4)

> **RESOLVED (2026-07-17).** M4 acceptance reworded from "byte-identical" to "logically
> identical — same rows, no row-level diff." (The M8 "byte-identical" claim, which is about
> *Mermaid text*, is left as-is — text comparison is exact and appropriate there.)

Status: **RESOLVED (minor).** M4 acceptance asserts a second `tag-domains` run "leaves the
DB byte-identical." A WAL-mode SQLite file can differ at the byte level between runs (WAL
checkpoint state, free-page layout) even when logical content is unchanged; `INSERT OR
REPLACE` of identical values usually won't move pages, but byte-identity is not a safe
hard criterion for a live DB and risks a false test failure. Row-level logical comparison
is the correct assertion.

### 25. M2 says "open both stores read-only," but the specified `KnowledgeStore` constructor can't (M2)

> **RESOLVED (2026-07-17).** M2 reworded: the knowledge side is opened via the normal
> `KnowledgeStore` constructor (read-write; it `mkdir`s the dir and opens WAL), and only the
> *index* side (`index.sqlite`) is opened/attached **read-only**. The blanket "open both stores
> read-only" instruction is dropped, since the knowledge constructor as specified in M1 has no
> read-only mode. See the rewritten M2 chunk-count paragraph.

Status: **RESOLVED (minor).** M2's chunk-count path says to "open both stores read-only,"
but `KnowledgeStore.__init__` (M1/Interfaces) always `mkdir`s its parent and opens WAL
read-write — there is no read-only mode. Only `index.sqlite` (attached/opened for the join)
needs to be read-only; the knowledge side just uses its normal constructor. The two
sections were inconsistent as written.

### 26. Name collision: two `upsert_chunks` methods (Interfaces)

> **RESOLVED (2026-07-17).** The Interfaces section now notes that `SQLiteStore` also has an
> `upsert_chunks` (called at `indexer.py:475`), distinct from `ChromaVectorStore.upsert_chunks`
> (`:868`), and that the `domain_by_chunk` parameter is added to the **Chroma** one only.

Status: **RESOLVED (awareness).** There are two `upsert_chunks` methods —
`SQLiteStore.upsert_chunks` (`indexer.py:475`) and `ChromaVectorStore.upsert_chunks`
(`indexer.py:868`). The plan correctly scopes the `domain_by_chunk` addition to the Chroma
one, but the collision is worth a one-line note so the edit doesn't land on the SQLite
store by mistake. Not a defect in the plan — an implementation-awareness guard.

## Assessment

No blocking errors. M1–M2, M4, M7, and M8 hold up against the code. The real risk is
**#22** (the M5 inline-stamp model must be reconciled with the shared `_embed_and_upsert`
helper and the store-less backfill path *before* M5 is built), followed by **#23**
(resolve before M6 lands). #24–#26 are plan-text tightenings foldable as the milestones
are implemented.

**Update (2026-07-17): all third-pass findings #22–#26 RESOLVED and folded into the plan.**
- #22 — M5 names `_embed_and_upsert` as the single shared stamp site (both `run()` and `backfill_vectors()`); backfill opens the knowledge store; fan-out keying + Recovery fallback stated.
- #23 — M6 wires the in-domain path set / `domain_id` into `SearchEngine`; lexical drop happens in the fusion loop.
- #24 — M4 acceptance reworded to "logically identical" (row-level), not byte-identical.
- #25 — M2 opens only `index.sqlite` read-only; knowledge side uses its normal constructor.
- #26 — Interfaces notes the `upsert_chunks` name collision; `domain_by_chunk` is on the Chroma method only.

No open issues remain from any of the three review passes; the plan is ready to build.

---
---

# Fourth review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell
Norton's request. This pass reviews the plan *after* issues #1–#26 were resolved and
folded in. It (a) verified **every** code reference the plan cites — line numbers,
signatures, and behaviors — against the live source, and (b) traced the
`modernize-assess` integration end-to-end against the skill's own conventions
(`$1`, `analysis/$1/`, and the repo-root resolution documented in its Step 3).
Cross-checked against
`tools/legacylift_search/src/legacylift_search/{indexer,search,vector_store,store,config,discovery,models}.py`
and `.claude/skills/code-modernization/commands/modernize-assess.md`.

**Line-reference audit — all confirmed accurate.** `store.py:346` (symbol_facts CREATE),
`store.py:657` (orphan-guard IntegrityError), `store.py:452` (SQLiteStore.upsert_chunks),
`vector_store.py:84` (Chroma upsert_chunks, exactly the 8 metadata keys listed),
`vector_store.py:143-147` (defensive delete_chunks), `query()` has no `where` today,
`search.py:37-47` (SearchEngine.__init__ signature), `search.py:62` (_lexical_ranks),
`search.py:114` (get_chunk in fusion loop with relative_path in hand),
`indexer.py` 705/776/868/859-866/906/959/1009/914-920/188-199,
`config.py:265` (resolve_index_dir) + embed_min_tokens, `models.py:93`
(SourceFile.relative_path), `discovery.py:35` (discover_source_files → list[SourceFile],
uses pathspec gitignore/gitwildmatch), `modernize-assess.md:6` (attribution line), and
Steps 3 & 6 with ARCHITECTURE.mmd written in Step 6. No drift. The new findings are all
about the assess-integration story and two small consistency nits, not the core code
paths (which the first three passes had already nailed).

## Substantive issues

### 27. M8's assess shell-out passes the wrong `--repo-root` (contradicts the skill's own Step-3 convention) (M8)

> **RESOLVED (2026-07-17).** `render-architecture`'s `--repo-root` is now **optional**, required
> only when `--domains` is omitted (the SQLite source needs it to open `knowledge.sqlite`); with
> `--domains` given the renderer reads the file directly and `--repo-root` is unused, and the CLI
> errors only if **both** are absent. The assess shell-out (M8 Work) dropped `--repo-root "$1"`
> entirely — it now runs `render-architecture --domains "analysis/$1/domains.json" --output
> "analysis/$1/ARCHITECTURE.mmd"`. See the M8 "Source + timing" bullet, the M8 Work shell-out
> note, and the Interfaces render note. Analysis below retained as the record of *why*.

The plan's M8 assess shell-out was `legacylift-search render-architecture --repo-root "$1"
--domains "analysis/$1/domains.json" --output "analysis/$1/ARCHITECTURE.mmd"`. But
`modernize-assess.md` Step 3 (lines 143-145) already establishes the convention: the
`legacylift-search` `<repo-root>` is *"the on-disk directory `$1` resolves to — e.g.
`repos/ctcm/ctcm-api` — **not** a literal `legacy/$1` path."* A bare `"$1"` is the
system-*name*, which is neither `legacy/$1` nor the resolved repo dir — so the invocation
is inconsistent with the skill's own documented convention and would pass an unresolvable
repo-root. Two things to fix: (a) the `--domains` render path never needs the knowledge DB,
so `--repo-root` should be optional there (and the shell-out should omit it), and (b) the
plan never stated whether `--repo-root` is required when `--domains` is supplied — if it is
required and validated, the assess-time render (empty/absent knowledge DB) could fail on a
bad repo-root even though it renders purely from JSON. Making `--repo-root` optional-unless-
SQLite-source resolves both cleanly.

### 28. The reserved `unassigned` bucket can break M8's "byte-identical across both sources" guarantee (M2/M8)

> **RESOLVED (2026-07-17).** Two-part fix. **M2:** `unassigned` is pinned as a reserved
> `file_domains.domain` *value* with **no** `domains`-table row — the `domains`/`stats` commands
> synthesize its display line from the `file_domains` count — so `list_domains()` never returns it
> and it cannot enter glob precedence, `ORDER BY display_order`, or the render node set by
> construction. **M8:** `render_architecture_mermaid` additionally filters out any domain whose
> `domain_id == "unassigned"` (and any edge touching it) as belt-and-suspenders. Together these
> guarantee the SQLite-source and `domains.json`-source renders are byte-identical (M8 acceptance
> step 2). `search --domain "Unassigned"` name resolution special-cases the reserved slug (M6). See
> the rewritten M2 sentinel paragraph, the M6 name-resolution note, and the M8 unassigned-exclusion
> bullet. Analysis below retained as the record of *why*.

M8 acceptance step 2 requires the SQLite-sourced and `domains.json`-sourced renders to be
identical. But `domains.json` never contains an `unassigned` entry (that sentinel is minted
only at ingest), while M2's original wording ("the ingest/resolver inserts it lazily") was
ambiguous about whether a **row lands in the `domains` table**. If it did, the SQLite render
(driven by `list_domains()`) would emit an `Unassigned` node while the `--domains` render
would not → not byte-identical. The plan had to pin down that `unassigned` is *not* a
catalog row (cleanest — dissolves the divergence, and also removes it from precedence and
ordering), with an explicit render-side exclusion as a defensive backup.

## Smaller issues

### 29. Issue-#26's note mislabels method *definitions* as `indexer.py` call-site line numbers (Interfaces)

> **RESOLVED (2026-07-17).** The Interfaces NB now states the `:475`/`:868` numbers are CALL
> SITES in `indexer.py`, and gives the definition locations: `SQLiteStore.upsert_chunks` defined
> `store.py:452` (called `indexer.py:475`); `ChromaVectorStore.upsert_chunks` defined
> `vector_store.py:84` (called `indexer.py:868`). `domain_by_chunk` still lands on the Chroma one.

Issue #26's note read *"TWO upsert_chunks methods — SQLiteStore.upsert_chunks
(indexer.py:475) and this one (ChromaVectorStore, indexer.py:868)."* Both numbers are
**call sites in `indexer.py`**, not definitions (the definitions are `store.py:452` and
`vector_store.py:84`, verified). The substantive scoping (add `domain_by_chunk` to the
Chroma method) was always correct and the surrounding Interfaces header already says "In
vector_store.py" — so this is a cosmetic label fix, but one that would otherwise send an
implementer to a call site expecting a `def`.

### 30. `unassigned` ordering vs. the "final unassigned line" (M2)

> **RESOLVED (2026-07-17).** Folded into the #28 fix: because `unassigned` has no `domains`-table
> row, it never participates in `ORDER BY display_order, domain_id`, and the `domains` command
> prints it as a synthesized trailing line from the `file_domains` count. No `display_order`
> sentinel is needed and there is no ordering conflict.

`list_domains()` is pinned to `ORDER BY display_order, domain_id` (issue #14), but a
lazily-inserted `unassigned` catalog row would need a defined `display_order` or it could
sort *first*, contradicting M2's "a final `unassigned` line." No correctness impact
(`unassigned` has empty globs, so it never affects precedence), purely presentational — and
it dissolves entirely once `unassigned` is not a catalog row (#28).

### 31. Stdout convention stated two ways (M8)

> **RESOLVED (2026-07-17).** M8 Work now pins it: omitting `--output` writes to stdout, `--output
> -` is an explicit synonym for stdout, and `--output <path>` writes that file. The acceptance
> tests' `--output -` usage is consistent with this.

M8 said "defaults to stdout; `--output <path>` writes a file," but Concrete Steps and the
acceptance tests use `--output -`. Harmless, but the two forms should be reconciled so an
implementer knows both omit-for-stdout and `-`-means-stdout are supported.

## Assessment

No blocking errors, and every cited code reference verified accurate against the live
source. The two worth resolving before M8 is built are **#27** (the assess shell-out
repo-root) and **#28** (the `unassigned`/byte-identical guarantee) — both are M8-scoped, so
M1–M7 were already clean and buildable. #29–#31 are plan-text tightenings.

**Update (2026-07-17): all fourth-pass findings #27–#31 RESOLVED and folded into the plan.**
- #27 — `render-architecture --repo-root` is optional when `--domains` is given; assess shell-out drops `--repo-root "$1"`.
- #28 — `unassigned` is a `file_domains` value with no catalog row; `render_architecture_mermaid` excludes the slug; two sources stay byte-identical.
- #29 — Interfaces NB relabels `:475`/`:868` as call sites and gives the `store.py:452` / `vector_store.py:84` definitions.
- #30 — `unassigned` never enters `ORDER BY display_order`; `domains` prints it as a synthesized trailer.
- #31 — stdout on omitted `--output`, `--output -` an explicit synonym, `--output <path>` writes a file.

No open issues remain from any of the four review passes; the plan is ready to build.

---
---

# Fifth review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell
Norton's request. This pass re-verified **every** cited code reference against the live
source using four parallel source-reading agents (`store.py`, `vector_store.py`,
`search.py`, `discovery.py`, `indexer.py`, `config.py`, `models.py`,
`modernize-assess.md`), and specifically hunted for Windows-host and cross-database gaps
the prior four passes might have missed. Nine issues found (#32–#40), **all now resolved
and folded into the plan.**

**Windows path-separator check — SAFE, no action.** The biggest latent risk investigated
was OS-native backslash paths breaking `pathspec` glob matching. It does not occur:
`discovery.py:63` computes `relative_path = path.relative_to(repo_root).as_posix()` (with
the comment "always use forward slashes for pathspec"), and `store.py:133` applies a
defensive `path.replace("\\", "/")`. So `relative_path` is forward-slash canonical
everywhere and glob resolution matches assess-authored globs correctly on Windows. Noted
as a strength.

## Substantive issues

### 32. The plan cites `SQLiteStore._migrate` and "pragma setup in `__init__`" — both wrong (M1)

> **RESOLVED (2026-07-17).** Corrected throughout: the method is public `migrate()`
> (`store.py:173`), the WAL/foreign-key pragmas are in `migrate()` (`store.py:180-181`) not
> `__init__`, and `SQLiteStore` does **not** migrate on construction (the indexer calls
> `store.migrate()` explicitly, `indexer.py:960`). M1 now pins `KnowledgeStore` to a public
> `migrate()` that it **calls from `__init__`** — a deliberate divergence from `SQLiteStore`
> so that constructing the store creates+migrates the durable file (which the indexer's M1
> open relies on). Fixed in Surprises & Discoveries, Context "Key classes", M1 goal + Work,
> M2 schema header, and the Interfaces `KnowledgeStore` block.

The plan repeatedly cited `SQLiteStore._migrate` (Surprises, Context, M1) and instructed
`KnowledgeStore.__init__` to "copy the pragma setup from `SQLiteStore.__init__`." Verified
against source: there is no `_migrate` — the method is public `migrate()` at `store.py:173`;
the pragmas (`PRAGMA journal_mode=WAL` / `PRAGMA foreign_keys=ON`) are at `store.py:180-181`
inside `migrate()`; and `__init__` (`store.py:157-164`) only sets `self.conn = None` and
defers to a lazy `_connect()`, migrating nothing. An implementer literally "mirroring
`SQLiteStore`" would have built a store that never migrates on construction, contradicting
M1's own indexer-open step and acceptance. The 4th-pass claim "all cited references
confirmed accurate" did not hold here.

### 33. `KnowledgeStore` construction creates the file, defeating every "missing" branch and adding a surprising side effect (M1/M2/M7)

> **RESOLVED (2026-07-17).** M1 now states the construction side effect explicitly and
> requires read-only consumers (`domains`/`stats`/`validate`) to `Path.exists()`-probe
> `knowledge.sqlite` **before** constructing a `KnowledgeStore`. M2's graceful-degradation
> note and M7's "missing" branch were updated to probe-before-construct, and M7's impossible
> "open the knowledge DB read-only" wording (no read-only mode — #25) was dropped. The
> Interfaces `KnowledgeStore` note carries the same warning.

M1 has `KnowledgeStore.__init__` `mkdir` its parent and open the connection — which
*creates* `knowledge.sqlite`. But M2 (issue #19) wants `domains`/`stats` to print
"no domains" *when the file doesn't exist*, and M7 wants `domains: missing` *when
`knowledge.sqlite` does not exist*. You cannot detect absence by opening it — opening
creates it. So those branches were unreachable, and worse, running a pure read command
(`validate`, `domains`) on a never-tagged/never-indexed repo would silently materialize an
empty `knowledge.sqlite` + `knowledge/` dir as a side effect of a read. M7 additionally
still said "open the knowledge DB read-only," directly contradicting issue #25's finding
that `KnowledgeStore` has no read-only mode (M2 had been corrected, M7 had not).

### 34. `domains` chunk-count via read-only `ATTACH` on a WAL database is unreliable (M2)

> **RESOLVED (2026-07-17).** M2 now prefers the Python two-connection join and warns that a
> read-only ATTACH (`file:...?mode=ro`) of a WAL `index.sqlite` fails while a live
> `-wal`/`-shm` exists; if attaching, attach read-write (no `mode=ro`) and never write
> through it.

M2 offered `ATTACH DATABASE '<index.sqlite>' AS idx` (read-only) as a primary option.
SQLite **cannot open a WAL-mode database read-only** while a live `-wal`/`-shm` exists (a
read-only connection can't create/attach the shared-memory index), and a normal `index` run
frequently leaves the WAL un-checkpointed — so `mode=ro` ATTACH intermittently fails with
"unable to open database file." The plan's own alternative (Python two-connection join)
sidesteps this and is now the recommended path.

### 35. Milestone 3 rests on globs the skill doesn't emit, points at the wrong step, and mislabels the diagram as top-level-LLM "hand-authored" (M3)

> **RESOLVED (2026-07-17).** M3 Work rewritten into two explicit edits: (1) extend the
> **first `legacy-analyst` prompt in Step 3** to return per-domain path globs (it currently
> returns a markdown table + Mermaid citing repo-relative *file paths*, `modernize-assess.md:161-163`,
> not globs); (2) serialize `analysis/$1/domains.json` in **Step 6** (synthesis, after "Wait
> for all three", `:179`). The "hand-authored by an LLM" framing is corrected — Step 6 copies
> out the *legacy-analyst subagent's* diagram (`:241-242`), so `domains.json` edges derive from
> that same output. M8's Goal/Work wording updated to match. Repo-relative anchoring folded in
> (see #40).

Verified: Step 3 (`modernize-assess.md:140`) is "Parallel deep analysis" spawning three
subagents; only the first `legacy-analyst` builds the domain map, returning "a markdown
table + a Mermaid `graph TD`" with "repo-relative **file paths**" — not the path *globs*
`domains.json` requires. The plan's "add an instruction in Step 3 and Step 6" never said
which step captures globs vs serializes, and the serialization logically belongs in Step 6
(the only place with all subagents' output in hand). Separately, the plan called the current
`ARCHITECTURE.mmd` "hand-authored by an LLM"; it is authored by the legacy-analyst subagent
and copied out by Step 6 — a distinction that matters because `domains.json` edges must come
from that same subagent output.

## Smaller issues

### 36. M8's single renderer has an unspecified two-source type unification and no phantom-node guard (M8)

> **RESOLVED (2026-07-17).** M8 "Source + timing" now specifies that the CLI adapts the
> `--domains` source to the same shape as the SQLite source before calling
> `render_architecture_mermaid` (assign `display_order := array index`; map edge `from`/`to`
> to the record field names), and that the renderer drops any edge whose endpoint is not among
> the emitted nodes (`domain_edges` has no FK) — which also subsumes the `unassigned` exclusion
> (#28). The Interfaces render note carries the same contract.

`render_architecture_mermaid(domains, edges)` is fed from two shapes: SQLite `DomainRecord`
(has `display_order`) + `DomainEdgeRecord` (`from_domain`/`to_domain`), vs. JSON
`DomainsFile` domains (no `display_order` field) + edges (`from`/`to`). For byte-identical
output (M8 acceptance step 2) the JSON path must assign `display_order = array index` and
normalize edge field names — neither was stated, and the Interfaces block left the parameter
types unpinned. Also, with no FK on `domain_edges`, an edge to an unlisted domain makes
Mermaid auto-create a phantom node, breaking both the diagram and byte-identity.

### 37. Concrete Steps are bash/heredoc on a PowerShell-primary host (Concrete Steps)

> **RESOLVED (2026-07-17).** Added a shell note giving PowerShell equivalents (`$env:TEMP`,
> `Remove-Item`, `Copy-Item`, `$env:REPO`), and replaced the Milestone-2 `py -3.12 - <<'PY'`
> heredoc (which does not run in PowerShell at all) with a checked-in `seed_domains.py` run as
> `py -3.12 seed_domains.py "$REPO"` so both shells behave identically.

The snippets used `$REPO`, `rm -rf`, `cp -r`, and a `<<'PY'` heredoc-to-stdin. The plan
hedged "adjust for your shell/OS," but the heredoc is the one form that simply cannot be
adapted inline in PowerShell — the primary shell here.

### 38. No reaping of `file_domains` rows for deleted files → count drift (M2/M4)

> **RESOLVED (2026-07-17).** M4 now reaps `file_domains` rows whose `relative_path` left the
> discovered set, but only where `source IN ('glob','unassigned')` — **never** `manual`. M2's
> count note and the plan acknowledge that displayed counts read from `file_domains` can drift
> above the discovered set until the next `tag-domains` run; `validate` coverage keys on the
> discovered set and is unaffected.
>
> **AMENDED (2026-07-17, sixth pass — issue #42).** The "**never** delete a `manual` row"
> carve-out in this resolution was **reversed**: the reap is now **source-agnostic** and
> deletes any `file_domains` row for an undiscovered path, `manual` included. Rationale:
> `manual` protects a *live* human decision from 7-Auto glob re-resolution; a deleted file
> has no live decision to protect, and preserving its row was the direct cause of the #42
> coverage-inflation bug. Manual-wins is unchanged for files that still exist. See issue #42
> and the M4 `file_domains` reap paragraph.

`domain_file_counts()` and the `domains`/`stats` file counts read from `file_domains`
regardless of whether the file still exists on disk, so per-domain counts drift upward after
deletions. Reaping non-manual rows for undiscovered paths in `tag-domains` (the single
reconcile point) keeps the counts honest while preserving manual overrides.

### 39. `search --domain` no-match behavior and `tag-domains` missing-index handling (M4/M6)

> **RESOLVED (2026-07-17).** M6 now resolves either an exact `domain_id` or a
> **case-insensitive** display name, and **errors** (listing available domains) on an unknown
> domain rather than returning an empty result set indistinguishable from a valid-but-empty
> domain. M4 now errors clearly ("run `legacylift-search index` first") when `index.sqlite` is
> absent, instead of throwing on the first chunk-id lookup.

Minor robustness gaps: a typo'd `--domain` silently returned zero results; and `tag-domains`
run out of the `index → assess → tag-domains` order (no index) would throw a raw traceback
on the chunk-id lookup rather than a clear message.

### 40. `path_globs` / `--repo-root` anchoring across the assess `legacy/$1` vs resolved-repo-root convention (M3/M4)

> **RESOLVED (2026-07-17).** M3 states `path_globs` are repo-relative to the *resolved*
> repo-root (the on-disk dir `$1` resolves to, e.g. `repos/ctcm/ctcm-api`, per
> `modernize-assess.md:143-145`) — not the literal `legacy/$1` the skill body uses — and that
> `tag-domains` must be invoked with `--repo-root` pointing at that same directory or the globs
> won't match the discovered file set.

Carried over from the skill's own internal tension (body uses `legacy/$1`; Step 3's repo-root
note uses `repos/ctcm/ctcm-api`). Harmless once stated, but if `domains.json` globs and the
`tag-domains` `--repo-root` are anchored to different roots, resolution silently sends every
file to `unassigned`.

## Assessment

The core code paths (M1–M2 foundation, M4 tagging, M5 stamping, M6 search, M7 freshness, M8
render) hold up. The three worth treating as blocking before the relevant milestones are
**#32** and **#33** (both M1-foundational — a wrong class-mirroring model and a
construction-side-effect that breaks the "missing" checks) and **#35** (M3 depends on skill
output that doesn't exist yet). #34/#36 bite during M2/M8; #37–#40 are tightenings.

**Update (2026-07-17): all fifth-pass findings #32–#40 RESOLVED and folded into the plan.**
- #32 — `migrate()` (public) not `_migrate`; pragmas in `migrate()` not `__init__`; `KnowledgeStore` migrates from `__init__` by design.
- #33 — read-only consumers `Path.exists()`-probe before constructing; M7 "read-only" wording dropped.
- #34 — `domains` chunk count prefers Python two-connection join; read-only ATTACH on WAL is unreliable.
- #35 — M3 extends the Step-3 legacy-analyst prompt for globs, serializes in Step 6; "hand-authored" framing corrected.
- #36 — M8 unifies both render sources to one shape and drops phantom-endpoint edges.
- #37 — Concrete Steps get PowerShell equivalents; the heredoc replaced with a script file.
- #38 — `tag-domains` reaps non-manual `file_domains` rows for deleted files.
- #39 — `search --domain` errors on unknown domain; `tag-domains` errors clearly with no index.
- #40 — `path_globs` and `tag-domains --repo-root` anchored to the resolved repo-root.

No open issues remain from any of the five review passes; the plan is ready to build.

---
---

# Sixth review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell
Norton's request. This pass reviews the plan *after* issues #1–#40 were resolved and
folded in, deliberately hunting past the code-reference layer the prior five passes
exhausted and into the **reconcile/lifecycle model** — what happens to the authored and
derived rows across *repeated* assess runs, incremental reindexes, and deletions, rather
than on a single clean pass. Cross-checked against `indexer.py` (deleted-file handling at
`:265-272`, `delete_file_artifacts`/`clear_reindex_artifacts` operate only on
`index.sqlite`) and `config.py:135` (`embed_min_tokens` default 0).

Seven issues found (#41–#47), **all currently OPEN.** They share a single root cause the
first five passes never probed: the reconcile/reaping model was designed for one derived
table (`file_domains`) on a single clean run and never generalized to (a) the authored
tables across re-tag, (b) the count/coverage math under preserved-but-orphaned rows, (c)
a coherent `source` vocabulary, or (d) the far-more-frequent incremental `index` path.
Ordered by severity.

## Substantive issues

### 41. The `domains` / `domain_edges` tables are never reaped — stale domains from a prior assess run leak into precedence, rendering, and byte-identity (M4/M5/M8)

> **RESOLVED (2026-07-17) — delete + warn.** M4 now reconciles the authored tables after the
> `INSERT OR REPLACE`: `DELETE FROM domains WHERE domain_id NOT IN (<ingested>)` and the
> analogous `domain_edges` reap, so a domain absent from the current `domains.json` is fully
> removed (safe wholesale — authored tables carry no `manual` rows). When the reap drops a
> domain, `tag-domains` prints a notice naming it and the count of files reclassified off it
> (carried on `TagStats`). A four-step reconcile order was pinned so it composes with the #38
> `file_domains` reap: ingest authored → reap authored (#41) → resolve+write `file_domains`
> against surviving globs → reap `file_domains` (#38). See the rewritten M4 reap paragraphs,
> the Idempotence section, and the `TagStats` note in Interfaces. Analysis below retained as
> the record of *why*.

`tag-domains` reaps `file_domains` (issue #38) but writes the authored tables with only
`INSERT OR REPLACE` (plan lines 286, 488). `INSERT OR REPLACE` touches only rows present
in the *new* `domains.json`; a domain that existed in a previous assess run but is
**absent from the new one** (merged, renamed, re-scoped) is orphaned in the `domains`
table permanently. Consequences, none addressed by any milestone:

- **Glob-precedence corruption (M4/M5).** `list_domains()` still returns the orphan, so
  `resolve_file_domains` walks its globs and can assign live files to a domain no longer
  in the assessment. Because precedence is "first match in `display_order` wins" and the
  orphan keeps its old (possibly low) `display_order`, it can *outrank* current domains.
- **`render-architecture` phantom node/edges (M8).** The SQLite source renders the orphan
  node and its edges. The issue-#36 phantom-*edge* guard does not help — it only drops
  edges whose endpoints aren't nodes, and the orphan *is* still a node.
- **Breaks the M8 "byte-identical across both sources" guarantee (plan lines 366, 384,
  460).** After a re-tag that removes a domain, the SQLite render includes the orphan; the
  `--domains` render (fresh JSON) does not → not byte-identical, contradicting M8
  acceptance step 2 (the same guarantee issues #28/#36 worked hard to establish).
- **Counts and "most-recent `assess_run_id`" (M7, plan line 348)** read a mixture of
  `assess_run_id`s from different runs.

Fix direction: `tag-domains` must reconcile the authored tables too — delete
`domains`/`domain_edges` rows absent from the ingested `domains.json`. Unlike `manual`
`file_domains` rows, these are purely authored and safe to reap wholesale. This is the
authored-table analogue of the issue-#38 reap that was only ever applied to the derived
table.

### 42. Milestone 7 `coverage` / `classified` / `unassigned` are counted over the whole `file_domains` table, not intersected with the discovered set — coverage can exceed 100% and contradict `stale` (M7)

> **RESOLVED (2026-07-17) — two-part.** **(a) Root cause removed:** the reap rule was made
> **source-agnostic** — `tag-domains` (and, per #45, the indexer) now delete *any*
> `file_domains` row for an undiscovered path, **including `manual`** (reversing #38's
> "never delete manual"; see the #38 addendum). The `manual` tag protects a *live* human
> decision from glob re-resolution, so a deleted file's row is pure liability. After a
> reconcile `file_domains ⊆ discovered` holds. **(b) Defensive intersect:** M7's count
> buckets are now computed over `rows_present = rows ∩ discovered`, so even in the window
> between reconciles (e.g. an external raw-SQLite edit) `classified + unassigned + untagged
> == |discovered|` and `coverage ∈ [0,100%]`. Together these make "stale · coverage 200%"
> impossible. See the rewritten M7 count bullets and the M4 `file_domains` reap paragraph.
> Analysis below retained as the record of *why*.

M7 (plan lines 344-346) keys `untagged` correctly on the discovered set ("discovered
files with no row"), but defines the other three over **all** `file_domains` rows:

- `classified` = "rows whose `domain != 'unassigned'`"  — not `rows ∩ discovered`
- `unassigned` = "rows whose `domain == 'unassigned'`"  — likewise
- `coverage = classified / max(1, |discovered|)`

But `manual` rows for deleted files are **deliberately never reaped** (plan line 288:
"never delete a `source='manual'` row … preserved"), and the indexer never reaps
`file_domains` at all (see #45). So the numerator routinely contains rows for files not in
`discovered`, while the denominator is `|discovered|`.

Concrete failure: `discovered = {a}`, `a` untagged; two leftover `manual` rows `x→A`,
`y→B` for since-deleted files. Then `classified = 2`, `coverage = 200%`, while
`untagged = 1` → `stale`. `validate` reports **"stale · coverage 200%"** — impossible to
act on. This directly falsifies the plan's own reassurance at line 288 ("`validate`
coverage keys on the discovered set and is unaffected"): true only of the *denominator*,
not the numerator.

Fix direction: compute `classified`/`unassigned` over `rows` restricted to
`relative_path ∈ discovered` — the same intersection already applied to `untagged`.

### 43. The `source` column's allowed values are self-contradictory: schema says `'glob' | 'manual'`, but the reap predicate uses `source IN ('glob','unassigned')` (M2/M4)

> **RESOLVED (2026-07-17) — source='glob' + CHECK.** Two parts. **(a)** The reap-predicate
> half dissolved when #42 made the reap source-agnostic (it no longer references `source`).
> **(b)** The representation is pinned: an unmatched-file row carries `domain='unassigned'`,
> **`source='glob'`** — "unassigned" is a domain *value*, never a `source` value; the row is
> glob-*sourced* because the glob resolver produced it. `source` stays a strict two-value
> enum, hardened with `CHECK (source IN ('glob','manual'))` in the `file_domains` schema so a
> stray value can't drift in, and M7's `manual = source=='manual'` partition is now
> unambiguous. See the updated `file_domains` schema block and the M4 resolver bullet.
> Analysis below retained as the record of *why*.

Schema comment (plan line 213): `source TEXT NOT NULL, -- 'glob' | 'manual'`. M7 partitions
on it (`manual = source=='manual'`). But the M4 reap (plan line 288) is "only where
`source IN ('glob','unassigned')`" — referencing a **third `source` value `'unassigned'`
the schema never defines.** Meanwhile the reserved bucket is described elsewhere as a
`domain` *value* (line 212: "domain_id, or the reserved `unassigned`") written with
`source='glob'`.

So it is genuinely undefined whether an unmatched-file row is
`(domain='unassigned', source='glob')` or `(domain='unassigned', source='unassigned')`.
Not cosmetic:

- If unassigned rows carry `source='glob'`, the reap's `IN (…, 'unassigned')` branch is
  dead and misleading.
- If they carry `source='unassigned'`, the schema comment is wrong and any future
  `CHECK(source IN ('glob','manual'))` hardening (a natural addition) would reject valid
  inserts.

Fix direction: pick one representation and state it once (schema + reap + M7 must agree).
The reap almost certainly *means* "reap non-`manual` rows for undiscovered files" — key it
on `source <> 'manual'` (or on `domain`), not on a `source` value the schema disallows.

### 44. `search --domain "Unassigned"` silently degrades on the vector side after any incremental reindex (M5/M6)

> **RESOLVED (2026-07-17) — Option A (mirror the row).** M5's Chroma stamp rule was unified:
> **if a `file_domains` row exists, the indexer mirrors that row's `domain` verbatim** (glob,
> manual, *or* `unassigned`); else it uses the freshly glob-resolved domain for a matching new
> file (writing its `glob` row); else omits the key (untagged new file). This makes the
> derived-mirror invariant true for *all* row values (the Context invariant was updated from
> "glob or manual" to all three), fixes the case where a re-embedded `unassigned` file lost its
> Chroma `domain` key on the full-record upsert, and subsumes manual-wins on the vector side.
> Mirroring an existing `unassigned` row is **not** the indexer manufacturing one — only
> `tag-domains` creates `unassigned` rows; the indexer keeps Chroma faithful to what exists.
> Conceptual clarification folded in (see #48): `unassigned` is a gap *sentinel*, not a real
> domain; the ideal steady state is zero unassigned (cross-cutting code goes in an
> assess-authored Shared/Common domain), and the gap is surfaced as `coverage < 100%` on a
> separate axis from fresh/stale. See the rewritten M5 stamp paragraph and the Context
> derived-mirror invariant. Analysis below retained as the record of *why*.

M6 explicitly supports `--domain "Unassigned"` (plan lines 318-320) with a Chroma
`where={"domain":"unassigned"}` vector filter; `tag-domains` stamps `domain="unassigned"`
onto those chunks. But M5's stamp rule (plan line 305) writes the Chroma domain as "the
existing row's domain when `source='manual'`, otherwise the glob-resolved domain,
**otherwise omitted (no match)**."

An `unassigned` file matches no glob and isn't `manual`, so on any incremental **re-embed**
of that file the indexer takes the "omitted" branch — and because the Chroma write is an
`upsert` (full-record replace), the previously-stamped `domain="unassigned"` key is
**dropped**. Now `file_domains` still says `unassigned` (lexical side via
`files_for_domain` returns the file) but Chroma has no `domain` key (vector side misses
it). The two search halves diverge, and the derived-mirror invariant (plan line 163,
scoped to "glob *or* manual") silently *excludes* the `unassigned` case M6 depends on.

Fix direction: either stamp `domain="unassigned"` when an existing `unassigned` row is
present (make the mirror cover all three cases), or document that `--domain "Unassigned"`
vector recall is valid only immediately after a `tag-domains` run and gate/warn.

### 45. The indexer never reaps `file_domains`, so counts/coverage drift on every incremental run, not just at re-tag (M4/M5)

> **RESOLVED (2026-07-17).** M5 now has the indexer reap: when its already-computed
> `deleted_paths` (`indexer.py:265-272`) is non-empty, it `DELETE`s the matching
> `file_domains` rows — source-agnostic, including `manual` (same rule as #38/#42) — so the
> indexer becomes a second reconcile point for row *deletion*. It remains **not** a reconcile
> point for the authored `domains`/`domain_edges` tables (only `tag-domains` writes/reaps
> those). Guarded to no-op when the knowledge DB has no `domains` yet. This closes the
> incremental-run drift; M7's defensive intersect (#42) covers any residual window. See the
> new "Reap `file_domains` for deleted files on reindex" paragraph in M5.

Only `tag-domains` reaps (#38). Confirmed against `indexer.py:265-272`: the incremental
pipeline deletes chunks/symbols for deleted files from `index.sqlite` via
`delete_file_artifacts`/`clear_reindex_artifacts` and has **no** `KnowledgeStore` reap. So
a routine `index` after deleting or **renaming** files (a rename = new path + deleted old
path) leaves orphan `glob` rows in `file_domains`. Between `tag-domains` runs — most of the
time on a real repo — the per-domain file counts (`domains`/`stats`) and, via #42,
`coverage` drift upward. The plan calls `tag-domains` "the single reconcile point," but
nothing keeps the derived rows consistent under the far-more-frequent `index` path.

Fix direction: have the indexer drop non-`manual` `file_domains` rows for the
`deleted_paths` it already computes (`indexer.py:266`), or explicitly scope the #42
intersection fix so displayed numbers stay honest regardless of orphan rows. (These two
fixes are complementary; #42's intersection is the cheaper, sufficient one for correctness
of the *displayed* numbers.)

## Smaller issues

### 46. Lexical recall is starved under `--domain` (M6)

> **RESOLVED (2026-07-17).** M6 now over-fetches lexical candidates when a `--domain` filter is
> active: `_lexical_ranks` requests `limit × k` (k≈5, capped) FTS5 rows so ~`limit` survive the
> in-domain drop, restoring the lexical arm's contribution (the vector arm was already fine —
> Chroma's `where` pre-filters before `limit`). Unfiltered search is unchanged. Recall
> improvement, not a correctness fix; the acceptance term should appear in only a few in-domain
> files so the starvation is actually exercised. See the new "Over-fetch the lexical side" note
> in M6.
>
> **Mechanics superseded by #49 (seventh pass).** The `limit × k`/"top-`limit`" framing above is
> factually wrong about `search.py`: neither arm is sized to `limit` — both fetch
> `config.vector_candidates`/`config.lexical_candidates` (default 40) and fuse-then-truncate to
> `effective_limit`, and `_lexical_ranks` takes no `limit` argument. The starvation is real and
> the *remedy* (over-fetch the lexical pool under `--domain`) is unchanged, but it is now expressed
> as scaling `lexical_candidates`, not `limit`. See #49 and the corrected M6 note.

M6 (plan line 320) drops out-of-domain lexical hits **inside the fusion loop**, after
`_lexical_ranks` has already returned only its top-`limit` *global* hits. For a small
domain, nearly all of those are out-of-domain and get dropped, so the lexical arm
contributes little and results collapse toward vector-only. The vector arm is fine (Chroma
`where` pre-filters before `limit`). Acceptable for v1, but it should be called out — and
the M6 acceptance (plan line 322) uses a term "that appears in both src and database
files," which won't expose the starvation.

Fix direction: note the limitation explicitly, or over-fetch lexical candidates
(`limit × k`) before the in-domain drop so the lexical arm still contributes `~limit`
in-domain hits.

### 47. Milestone 1 Concrete Steps instruct writing the sentinel row via the M2-only seed script (Concrete Steps)

> **RESOLVED (2026-07-17).** The M1 verification now uses a self-contained throwaway `_sentinel`
> table (raw `sqlite3` `CREATE TABLE`/`INSERT` via a `py -3.12 -c` one-liner that runs in both
> shells), independent of the M2 schema, and reads it back after `--reset` to prove durability.
> The M2-only `seed_domains.py` is no longer referenced for the M1 check. See the updated
> Milestone 1 verification block in Concrete Steps.

Concrete Steps (plan line 408) says, for the M1 durability check, "write a sentinel row
directly (see the Milestone 2 snippet below)." That snippet (`seed_domains.py`, plan lines
414-424) calls `upsert_domain`/`upsert_file_domain` against the `domains`/`file_domains`
tables, which do not exist until Milestone 2 — in M1, `migrate()` is only a scaffold (plan
line 174). The M1 prose hedges ("a throwaway table, or a `domains` row once Milestone 2
lands"), but Concrete Steps points specifically at the M2 script, so following the steps
literally during M1 fails.

Fix direction: give M1 its own throwaway-table sentinel snippet (a `CREATE TABLE
_sentinel` + insert via raw SQL), independent of the M2 schema.

### 48. A coverage gap (`unassigned` files) is reported but never routed to a fix (M3/M7)

> **RESOLVED (2026-07-17).** Raised by Darrell Norton during the #44 walk-through: a file in
> `unassigned` is a gap/error condition, so the plan should *drive it to resolution*, not just
> print a number. Two-part fix. **(a) Prevent upstream:** M3's Step-3 legacy-analyst prompt now
> carries a coverage-completeness instruction — aim for total glob coverage, put cross-cutting
> code in an explicit Shared/Common domain, and treat any uncovered file as a coverage gap to
> minimize deliberately (not a dumping ground). **(b) Route to a fix downstream:** M7's
> `validate` now appends an actionable remedy when `unassigned > 0`, naming the process
> (`re-run modernize-assess … then tag-domains`) and pointing at `search --domain "Unassigned"`
> / the `domains` listing to enumerate the offending files. The conceptual model was pinned:
> `unassigned` is a gap *sentinel*, not a real domain; ideal steady state is zero unassigned;
> the gap lives on the always-visible `coverage%` axis, deliberately separate from the
> `fresh`/`stale` verb (per #2). A mandatory catch-all `**` glob was explicitly rejected —
> it would hide the gap the sentinel exists to surface. See the M3 coverage-completeness
> instruction and the M7 "Route the coverage gap to a fix" paragraph.

Emerged from the #44 discussion, not the initial sixth-pass sweep. Recorded here for a
complete audit trail.

## Assessment

No new code-reference drift — the fifth pass's line audit still holds. The two to treat as
**blocking** before a "ready to build" sign-off are **#41** (authored-table reap; also
breaks M8 byte-identity) and **#42** (coverage math can report "stale · 200%"), with
**#43** (the `source` vocabulary contradiction) close behind because it must be settled
before either reap predicate can be written correctly. #44/#45 should be resolved before
M5/M6 land; #46/#47 are tightenings.

**Update (2026-07-17): all sixth-pass findings #41–#48 RESOLVED and folded into the plan**
(walk-through with Darrell Norton).
- #41 — `tag-domains` reaps authored `domains`/`domain_edges` rows absent from the new `domains.json` (delete + warn); four-step reconcile order pinned.
- #42 — reap made source-agnostic (dissolves the root cause) + M7 counts intersect with the discovered set; "stale · coverage 200%" now impossible.
- #43 — `unassigned` is a `domain` value with `source='glob'`; `source` hardened to `CHECK (source IN ('glob','manual'))`.
- #44 — indexer mirrors the existing `file_domains` row's domain for **all** values (glob/manual/unassigned); derived-mirror invariant now total.
- #45 — indexer reaps `file_domains` for its `deleted_paths` (source-agnostic); second reconcile point for row deletion.
- #46 — M6 over-fetches lexical candidates (`limit × k`) under `--domain` to avoid recall starvation.
- #47 — M1 verification uses a self-contained `_sentinel` table, not the M2-only seed script.
- #48 — coverage gap now prevented upstream (assess coverage-completeness instruction) and routed to a fix downstream (`validate` remediation line + triage search).

Key design decisions from this pass, for the record:
- The `manual` tag protects a **live** human decision from glob re-resolution only — it is **not** immortal. Deleted files' rows (any source) are reaped. (Reverses the original #38 carve-out.)
- `unassigned` is a **gap sentinel, not a domain**. Ideal steady state is zero unassigned (cross-cutting code → an assess-authored Shared/Common domain). The gap is surfaced on the always-visible `coverage%` axis, deliberately separate from the `fresh`/`stale` verb, and is now actionable rather than a dead-end number. A mandatory catch-all `**` glob was rejected — it would hide the gap.

No open issues remain from any of the six review passes; the plan is ready to build.

---

# Seventh review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell Norton's
request. This pass reviews the plan *after* issues #1–#48 were resolved and folded in. The
prior six passes had exhausted the citation layer (line numbers, signatures, method names all
re-verified through the fifth pass) and the reconcile/lifecycle model (sixth pass). This pass
read the live source **end-to-end for the plan's *behavioral* claims** — does the code actually
behave the way the prose says it does? — cross-checking `search.py`, `config.py`,
`vector_store.py`, `discovery.py`, `store.py`, and `indexer.py`. Every citation still holds;
what broke were five *behavioral* assumptions, two of them substantive.

Five issues found (#49–#53), **all resolved and folded in.** Ordered by severity.

## Substantive issues

### 49. Milestone 6's issue-#46 over-fetch text is built on a false model of `search.py` (M6)

> **RESOLVED (2026-07-17).** The M6 "Over-fetch the lexical side" note was rewritten to describe
> the search internals as they actually are, and the mitigation re-expressed against the real
> knob. Supersedes the mechanics (not the intent) of #46. See the corrected M6 note and #46's
> superseded-mechanics banner.

The sixth pass's #46 resolution claims (plan M6): "The vector arm … always returns up to
`limit` in-domain hits. … `_lexical_ranks` (`search.py:62`) returns the top-`limit` global FTS5
hits … request `limit × k` FTS5 rows from `_lexical_ranks` … Unfiltered search requests exactly
`limit` as today." **Every one of those four statements is false against the code:**

- `_vector_ranks` (`search.py:51-60`) calls `self.vector_store.query(embedding, limit=self.config.vector_candidates)` — it fetches `vector_candidates` (**default 40**, `config.py:170`), not `limit`.
- `_lexical_ranks` (`search.py:62-74`) calls `self.store.search_lexical(sanitized, limit=self.config.lexical_candidates)` — it fetches `lexical_candidates` (**default 40**, `config.py:171`), not `limit`, and it **takes no `limit` parameter at all** (signature is `_lexical_ranks(self, query)`).
- The fusion loop fuses both candidate pools and only then truncates to `effective_limit` (default 10) at `search.py:139-140`. So **unfiltered search already over-fetches 40 per arm** — it does not "request exactly `limit`."
- Therefore "request `limit × k` FTS5 rows from `_lexical_ranks`" is not implementable as written: there is no `limit` to multiply, and the real pool size is a config value.

The starvation concern itself is real (a small domain's in-domain lexical hits are a small
fraction of the global top-40, and the drop happens post-fetch in the fusion loop at
`search.py:114`), and the remedy direction (over-fetch the lexical pool under `--domain`) is
unchanged. But the *mechanism* and every *number* were wrong. An implementer following the M6
text literally would try to thread a `limit` into a method that has none and would size the
over-fetch off the wrong quantity.

Fix (folded in): the M6 note now (a) states the real candidate-pool sizing (`vector_candidates`
/`lexical_candidates`, default 40, fuse-then-truncate to `effective_limit`), (b) notes
`_lexical_ranks` needs a new optional count override (it has none today), and (c) expresses the
over-fetch as `lexical_candidates × k` rather than `limit × k`.

### 50. `search --domain` and `render-architecture` violate the plan's own #33 existence-probe rule (M6/M8)

> **RESOLVED (2026-07-17).** Both commands now `Path.exists()`-probe `knowledge.sqlite` before
> constructing `KnowledgeStore` and error with "run `tag-domains` first"; the #33 consumer list
> in M1 and the Interfaces comment were extended to include them. See the M6 Work paragraph, the
> M8 `--repo-root`/existence-probe design point, and the updated M1 (#33) text.

Issue #33 (fifth pass) established the rule: **any read-only `KnowledgeStore` consumer must
`Path.exists()`-probe before constructing**, because construction `mkdir`s `knowledge/` and
creates+migrates `knowledge.sqlite` as a side effect. The plan applied this to exactly three
commands — "the `domains`, `stats`, and `validate` commands … must probe `sqlite_path.exists()`
… *before* constructing" (plan M1). But **two later read-only consumers were omitted**:

- **M6 `search --domain`** (plan M6 Work): "the CLI opens the knowledge DB, resolves the name to
  a `domain_id`." No probe. On a never-tagged repo, `search --domain X` constructs
  `KnowledgeStore` (materializing an empty DB + dir — the exact side effect #33 exists to
  prevent), then fails with a confusing "unknown domain" against an empty catalog.
- **M8 `render-architecture`** SQLite source (plan M8): "the renderer must open
  `knowledge.sqlite`." No probe. `render-architecture --repo-root R` (no `--domains`) on a
  never-tagged repo materializes an empty DB and emits an empty `graph TD`.

This is the plan being internally inconsistent with an invariant it had already established. Fix
(folded in): both commands probe first and emit an actionable "no knowledge store — run
`tag-domains` first" error; `search` opens the knowledge DB only when `--domain` is given.

## Smaller issues

### 51. The `DomainsFile` edge model's `kind` default is unspecified — NOT NULL insert + M8 byte-identity (M8/Interfaces)

> **RESOLVED (2026-07-17).** The Interfaces note and the M8 normalization bullet now require the
> edge model to default a missing `kind` to `""`, matching `domain_edges.kind`'s
> `NOT NULL DEFAULT ''`. See the M8 "both sources normalized" bullet and the `DomainsFile` NB in
> Interfaces.

M2's schema declares `domain_edges.kind TEXT NOT NULL DEFAULT ''` (plan M2). M8 guarantees the
SQLite and `--domains` render paths are byte-identical and uses `kind` as the edge label. But
the plan pinned the `from`/`to` alias handling for the edge model without pinning `kind`'s
default. If an assess-authored edge omits `kind`: (a) ingesting a `None` `kind` into the
`NOT NULL` column fails, and (b) if defaulted to `None` rather than `""`, the JSON-source render
and SQLite-source render produce different edge labels, breaking byte-identity. Fix (folded in):
the edge model coerces a missing `kind` to `""`.

### 52. `KnowledgeStore` has no `close()`, unlike `SQLiteStore` — Windows file-handle hygiene (Interfaces/M2)

> **RESOLVED (2026-07-17).** `KnowledgeStore` gains a `close()` in the Interfaces (mirroring
> `SQLiteStore.close`, `store.py:1478`), and M2's two-connection-join note now says to close both
> the raw `sqlite3` connection to `index.sqlite` and the `KnowledgeStore`. See Interfaces and the
> M2 `domains` chunk-count paragraph.

`SQLiteStore.close()` (`store.py:1478`) exists specifically for Windows file-handle release, and
`ChromaVectorStore.close()` (`vector_store.py:204`) does the same. The new `KnowledgeStore` had
no `close()` in the Interfaces, yet the new CLI read commands and the `domains`/`stats`
two-connection Python join (which also opens a raw `sqlite3` connection to `index.sqlite`) will
leave `-wal`/`-shm` handles open on Windows. Not corrupting (knowledge.sqlite is never
`--reset`-deleted, so no unlink races), but inconsistent with the codebase's established Windows
pattern. Fix (folded in): add `close()` and require CLI consumers to close what they open.

### 53. Milestone 5 acceptance (c) wording "glob rows are re-derived" contradicts the #44 uniform rule (M5)

> **RESOLVED (2026-07-17).** M5 acceptance (c) reworded to "existing `glob` rows persist —
> mirrored verbatim per issue #44, not recomputed — while a brand-new glob-matching file gets a
> fresh `glob` row." See M5 acceptance.

Under the issue-#44 uniform rule (plan M5 Work): "if a `file_domains` row already exists for the
file, mirror that row's `domain` verbatim." So on `--reset`, an *existing* `glob` row is mirrored
into Chroma, not re-derived. M5 acceptance (c) said "glob rows are re-derived," describing a code
path the plan elsewhere rules out. End state is identical (glob rows present, Chroma stamped), but
the acceptance text should match the mechanism. Fix (folded in): reworded to "mirrored verbatim,
not recomputed."

## Assessment

Two substantive (#49 the search-internals mismodel; #50 the existence-probe omission), three
tightenings. Both substantive issues are the same *class* of defect the first six passes did not
target: the citations were all correct, but two of them were attached to prose that described
behavior the cited code does not have (#49) or omitted an invariant the plan had itself
established for sibling commands (#50). #49 is the one that would have bitten an M6 implementer
immediately. Every code citation the plan makes was re-verified against the live source in this
pass and remains accurate.

**Update (2026-07-17): all seventh-pass findings #49–#53 RESOLVED and folded into the plan.**
- #49 — M6 over-fetch note rewritten against the real `*_candidates` pools; #46's mechanics banner-superseded.
- #50 — `search --domain` and `render-architecture` added to the #33 existence-probe list; both error "run `tag-domains` first" instead of littering an empty DB.
- #51 — edge model defaults missing `kind` to `""` (NOT NULL + byte-identity).
- #52 — `KnowledgeStore.close()` added; CLI read commands + two-connection join close their handles.
- #53 — M5 acceptance (c) reworded to match the #44 mirror rule.

No open issues remain from any of the seven review passes; the plan is ready to build.

---

# Eighth review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell Norton's
request. This pass reviews the plan *after* issues #1–#53 were resolved and folded in. The
seventh pass established that the citations are all accurate and began testing the plan's
*behavioral* claims; this pass carried that further, tracing the **runtime semantics of the
recent passes' own fixes** — not whether the cited code exists, but whether each fix actually
does what it claims once the surrounding code runs. Cross-checked against `search.py`,
`config.py`, and `indexer.py`.

Three issues found (#54–#56), **all resolved and folded in.** Ordered by severity.

## Substantive issues

### 54. The #46/#49 over-fetch fix is largely inert — in-domain lexical hits keep global ranks and are crushed in RRF (M6)

> **RESOLVED (2026-07-17).** The M6 "Over-fetch the lexical side" note now requires the lexical
> arm to be **filtered to in-domain and re-ranked densely (1..N) *before* RRF** when `--domain` is
> active — supersedes #23's fusion-loop drop for the filtered path. See the corrected M6 note and
> the `SearchEngine.search` Interfaces comment.

The seventh pass (#49) correctly rebuilt the *description* of the search internals and re-expressed
the over-fetch against the real `lexical_candidates` pool. But the *fix it landed on* — enlarge the
pool, keep the fusion-loop drop of #23 — does not restore lexical contribution, because of how RRF
scores interact with the drop:

- RRF scores each hit `1.0 / (k + rank)` with `k = rrf_rank_constant` (**default 60**,
  `config.py:172`), summed across arms (`search.py:108-112`).
- `_lexical_ranks` assigns `rank = i + 1` = the hit's position in the **global** FTS5 result list
  (`search.py:74`). The in-domain drop happens later, in the fusion loop (`search.py:114`, per #23),
  **after** those ranks are frozen.
- Under `--domain`, Chroma's `where` pre-filters the vector arm *before* `n_results`, so its
  in-domain hits are re-densified to ranks 1..N. The lexical arm is **not** re-densified — its
  surviving in-domain hits keep their global positions.

So an in-domain lexical hit sitting at global position 150 contributes `1/(60+150) ≈ 0.0048`, versus
the `1/(60+2) ≈ 0.016` it would earn at its true in-domain position — a ~3.4× suppression. Enlarging
the pool to `lexical_candidates × k` (the #46/#49 remedy) pulls *more* in-domain rows into the pool
but pushes their global ranks *deeper*, making the suppression worse, not better. In the exact
scenario #46 targets — a small domain, a term common globally — the in-domain lexical hits land deep
in the global list, earn negligible RRF weight, and almost never crack `effective_limit` (10). Net
result: `--domain` search returns results but stays effectively **vector-only**, which is the
failure #46 set out to cure. The seventh pass fixed the prose and left the fix inert.

Fix (folded in): when `--domain` is active, filter the lexical results to in-domain and
**re-enumerate the survivors 1..N before RRF**, so the lexical arm's fusion weight matches the
already-dense vector arm. This needs `relative_path` at the lexical stage (a `store.get_chunk`
lookup, as the fusion loop already does at `search.py:114`), and it **supersedes #23's
"drop in the fusion loop"** for the filtered path. Unfiltered search is unchanged.

### 55. The #45 `file_domains` reap keys on `deleted_paths`, which is empty on `--reset` — ghost rows survive and `domains`/`stats` then contradict `validate` (M5/M2)

> **RESOLVED (2026-07-17).** M5's reap now keys on the **discovered set** (`relative_path NOT IN
> current_paths`) rather than `deleted_paths`, so it fires on `--reset` too; and
> `domain_file_counts()` (and thus `domains`/`stats`) applies the same #42 discovered-set intersect
> `validate` uses. See the M5 reap paragraph and the `domain_file_counts` Interfaces NB.

Issue #45 (sixth pass) had the indexer reap `file_domains` "when `deleted_paths` is non-empty."
But `deleted_paths = [p for p in existing_shas.keys() if p not in current_paths]`
(`indexer.py:266`), and on a `--reset` run `existing_shas` is **empty** — the DB was wiped, so
"every file is processed from scratch" (`indexer.py:259-268`). So `deleted_paths` is always empty on
`--reset`, and the #45 reap **never fires there**. A file that was tagged, then deleted from disk,
then `index --reset`-ed (no intervening `tag-domains`) keeps its ghost `file_domains` row, and the
plan's `file_domains ⊆ discovered` invariant breaks after a reset.

This is not cosmetic. The `domains`/`stats` commands read raw `domain_file_counts()` (plan M2) with
**no** discovered-set intersect, while `validate` intersects (#42, sixth pass). So in this window
`domains` over-counts the ghost's domain while `validate` reports correct coverage — two commands
**contradicting each other on the same repo state**, with no error to signal it. #42 hardened
`validate` against exactly this drift but left the sibling read commands exposed.

Fix (folded in), both facets: (1) the indexer reaps `file_domains WHERE relative_path NOT IN
<discovered current_paths>` (a superset of the `deleted_paths` reap that also catches reset-window
ghosts and stray externally-inserted rows), still `manual`-inclusive and still guarded on "knowledge
DB has domains"; `discover_source_files` is already computed in `run()` (`indexer.py:247`), so the
set is free. (2) `domain_file_counts()` applies the #42 intersect too, so a read command can never
disagree with `validate`.

## Smaller issues

### 56. M8 byte-identity breaks if `domains.json` carries a duplicate edge (M8)

> **RESOLVED (2026-07-17).** The M8 normalization bullet now requires the `--domains` adapter to
> **deduplicate the edge list on `(from, to, kind)`** — the same triple as `domain_edges`'s PRIMARY
> KEY — before rendering. See the M8 "both sources normalized" bullet.

M8 guarantees the SQLite-source and `--domains`-source renders are byte-identical for identical
data. `domain_edges` has PRIMARY KEY `(from_domain, to_domain, kind)` (plan M2), so ingest silently
collapses a repeated edge to one row via `INSERT OR REPLACE`. The `--domains` render source, by
contrast, iterates the JSON `edges` **array** verbatim (the #36/#51 adapter only maps field names,
defaults `kind`, and sorts — it does not dedup). If assess ever emits the same `A→B/kind` edge twice
— nothing forbids it, since the edges mirror an LLM-authored Mermaid diagram — the SQLite render
emits one arrow and the JSON render emits two, and the byte-identity guarantee fails. It fails
**invisibly**: the hand-authored fixture has no duplicates, so the M8 acceptance test passes while a
real assess run could break it.

Fix (folded in): dedup the JSON edge list on `(from, to, kind)` — the same triple the PK uses — in
the adapter, so both sources always agree.

## Assessment

One substantive quality/correctness gap (#54 — the over-fetch fix that doesn't fix), one
substantive cross-command consistency gap (#55 — `--reset` ghost rows), and one hard-to-detect
byte-identity gap (#56). All three are the same *class* the seventh pass began surfacing: the
citations are correct and the prose is now accurate, but a fix landed in an earlier pass does not
achieve its stated effect once the surrounding code runs (#54), or an invariant hardened in one
command was not carried to its siblings (#55), or a guarantee holds only for the fixture that tests
it (#56). Every code citation the plan makes was re-verified against the live source in this pass
and remains accurate.

**Update (2026-07-17): all eighth-pass findings #54–#56 RESOLVED and folded into the plan.**
- #54 — M6 lexical arm re-ranked densely before RRF under `--domain`; supersedes #23 for the filtered path.
- #55 — indexer reaps `file_domains` against the discovered set (fires on `--reset`); `domain_file_counts()` intersects with discovered like `validate`.
- #56 — `--domains` edge adapter dedups on `(from, to, kind)` to match the PK, preserving M8 byte-identity.

No open issues remain from any of the eight review passes; the plan is ready to build.

## Reviewer's notes — cleared non-issues, unverified areas, and an implementation caution (pass 8)

Recorded so a future reviewer or implementer does not re-spend effort here, and knows exactly what pass 8 did and did not cover.

**Deliberately cleared — do NOT re-flag as issues:**

- *Below-`embed_min_tokens` files with no Chroma vectors are consistent under `--domain` search.* When `chunking.embed_min_tokens > 0`, a file whose chunks are all below threshold has `file_domains`/lexical/symbol recall but **no** dense vectors. Its `manual`/`glob` domain therefore never reaches Chroma (and #15's `vectors_present` restriction on `update_domain_metadata` correctly skips it). This is **not** a bug: such a file can only ever contribute on the *lexical* side, which filters by the `file_domains` in-domain path set (M6/#54), so it is still found under `--domain`. The vector arm never had it to lose.
- *The Chroma↔`file_domains` eventual-consistency window is acknowledged, not a defect.* A stale Chroma `domain` key (e.g. a `manual` edit not yet re-embedded and not yet reconciled by `tag-domains`) can cause a vector hit to be dropped in the fusion loop against the authoritative `file_domains` path set. This is recall loss, never a wrong-domain result, and the plan documents the `tag-domains` reconcile as the fix. Correct as designed.
- *`render_architecture_mermaid` excluding the reserved `unassigned` slug is belt-and-suspenders, not dead code.* Per M2, `unassigned` has no `domains` row, so `list_domains()`/`domains.json` never carry it anyway; the explicit filter (#28) guards a hypothetical future materialized row. Intentional.

**Not re-verified in pass 8 (relied on earlier passes' citations — spot-check before implementing the relevant milestone):**

- `vector_store.py` was **not** re-read this pass. The `update_domain_metadata`/`collection.update` merge behavior rests on the 1.5.9 probe (plan Artifacts and Notes) and the `delete_chunks` defensive pattern at `vector_store.py:143-147` (cited in M4/#15). Re-confirm when implementing M4.
- `discovery.py`'s `.as_posix()` `relative_path` normalization (fifth pass, underpins Windows `pathspec` gitwildmatch correctness) was **not** re-read this pass.
- **No code was run** in any review pass — all eight are static review. The baseline `py -3.12 -m pytest -q` count in Concrete Steps has never been captured; do that first when starting M1.
- At-scale `repos/ctcm/ctcm-api` validation remains a manual, unconstrained-host follow-up (the fixture is the only in-harness validation).

**Implementation caution for #54 (the M6 lexical re-rank):** the fix requires `relative_path` at the lexical stage to filter-then-re-rank, which means a `store.get_chunk` (or a batched equivalent) per lexical candidate *before* RRF — the fusion loop already pays this cost at `search.py:114`, but doing it earlier for the enlarged `lexical_candidates × k` pool multiplies the lookups. Prefer a batched path→membership check or a single `get_chunk` pass whose results are reused by the fusion loop, rather than looking each chunk up twice. This only fires when `--domain` is active; the unfiltered path must stay exactly as today (no re-ranking, no extra lookups).

# Ninth review pass — 2026-07-17

Review date: 2026-07-17 (post-revision). Reviewer: Claude (Opus 4.8), at Darrell Norton's
request. This pass reviews the plan *after* issues #1–#56 were resolved and folded in. It
re-traced the recently-added Milestone 6 recall machinery (#46/#49/#54) against the live
`search.py`/`config.py`/`vector_store.py` runtime, and asked a question the prior passes did not:
for each fix, **would the milestone's own acceptance test go red if the fix were omitted?** All
cited line numbers and config defaults (`vector_candidates`/`lexical_candidates`=40,
`rrf_rank_constant`=60, `_lexical_ranks` taking no limit, `deleted_paths` empty on `--reset`,
`current_paths` = full discovered set) were re-verified against the live source and remain accurate.

Two issues found (#57–#58) plus two wording tightenings, **all resolved and folded in.** Ordered by severity.

## Substantive issues

### 58. M6's acceptance cannot catch a missing or broken #54 — the plan's most-argued fix is untested

> **RESOLVED (2026-07-17).** M6 acceptance is now split into (1) a filtering-correctness part and
> (2) a load-bearing lexical-recall part. Part 2 asserts that a term appearing *lexically* in a
> `database/**` file (not semantically close to the query) but in *many* `src/**` files still
> surfaces its in-domain lexical match in the returned top-N under `--domain "Data Layer"`. See the
> revised M6 Acceptance.

The three original M6 acceptance terms only assert that `--domain` results are *in-domain*. But the
#23 fusion-loop drop guarantees in-domain-ness **on its own**: a `--domain` search that has silently
degraded to vector-only (the exact failure #46/#54 target) still returns only `database/**` rows and
still satisfies every original term. So the entire #46/#49/#54 apparatus — over-fetch plus dense
pre-RRF re-rank — could be omitted or implemented wrong and the milestone would go green. Line 338
gestured at the right test ("choose a term that appears in only a few in-domain files") but never
operationalized it into a checkable assertion. Fix: a hard recall assertion that fails iff the dense
re-rank is absent (deep-global-rank in-domain hit must reach the top-N).

### 57. The vector-arm over-fetch asymmetry rests on an unverified, version-specific Chroma behavior

> **RESOLVED (2026-07-17).** The M6 "Over-fetch the lexical side" note now carries an explicit
> "Unverified assumption" paragraph: "all in-domain" is guaranteed but "fills `n_results`" is a
> known HNSW-filter soft spot, unverified for chromadb 1.5.9. It adds a probe instruction (query a
> large filtered collection, confirm it fills `n_results`) and a fallback (scale `vector_candidates`
> under `--domain`) to be run before the first at-scale ctcm search.

M6 enlarges only the lexical candidate pool, justified by "Chroma's `where` pre-filters *before*
`n_results`, so its `vector_candidates` hits are all in-domain." The "all in-domain" half is always
true (a `where` query never returns an out-of-domain row). The unstated "so the vector pool is full"
half is **not** verified: HNSW-plus-metadata-filter can return fewer than `n_results` even when more
in-domain matches exist, because the approximate graph walk may not reach enough filter-passing
neighbors in a large collection. On the fixture this never bites; at ctcm scale the vector arm could
under-fill with no over-fetch analogue, silently narrowing `--domain` vector recall. This is exactly
the class of version-specific behavior the `update`-merge probe pinned down (Artifacts and Notes),
and deserves the same treatment.

## Smaller tightenings (folded in, no separate issue number)

- **#54 "supersedes #23" wording clarified.** "Supersedes #23's drop in the fusion loop" read as
  self-contradictory alongside "the fusion-loop drop remains correct for the vector side." Reworded
  to "augments #23": the lexical filter *moves* to a pre-RRF pass; the fusion-loop drop **stays** as
  the vector-side safety net. Prevents an implementer from deleting the drop entirely.
- **M2 `domains`/`stats` intersect requirement repeated inline.** The #55 discovered-set intersect
  lived only in Interfaces + M5; M2's own Work text now states it, since it is a requirement *of
  those commands*, so an implementer building M2 first does not miss it.

## Assessment

Both substantive findings are the same *class* the seventh and eighth passes surfaced: citations and
prose are accurate, but a fix's *stated effect* is not guaranteed once the surrounding code (or the
test that guards it) runs — #58 is a fix with no failing test, #57 is a fix whose asymmetry rests on
an unprobed runtime assumption. Neither is a code-reference error. No open issues remain from any of
the nine review passes; no milestone has been implemented yet; the plan is ready to build.
