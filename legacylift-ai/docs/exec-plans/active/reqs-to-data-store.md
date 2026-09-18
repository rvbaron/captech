# Store generated requirements in a queryable data store instead of markdown files

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository's ExecPlan conventions live in `docs/exec-plan.md` (there is no `PLANS.md` at the repository root). This document must be maintained in accordance with `docs/exec-plan.md`.

This plan is split into two files per `docs/exec-plan.md` ("Large plans: split current state from archived detail"). **This file holds everything needed to understand and continue the current state** and is self-contained for that purpose. The companion archive `reqs-to-data-store-additional-info.md`, in this same directory, holds the per-finding record of the nine pre-implementation review rounds — 125 closed findings, one row each. **You do not need the archive to build anything.** Open it for one reason: before proposing a change to how this plan does something, to check whether a review already considered and rejected it. What remains live from those rounds is summarized under `Surprises & Discoveries` below. When a milestone completes, migrate its `Concrete Steps` and its retrospective entry into the archive and update `Progress` and `Outcomes & Retrospective` here to match.

The design interview that produced this plan is checked in at `docs/exec-plans/pending/reqs-to-data-store-plan-draft.md`. That file is the *audit trail* — twenty-five settled decisions, the research behind them, and four sections marked NORMATIVE. **This ExecPlan is self-contained except for three NORMATIVE sections it cannot restate without losing fidelity.** Two of them bind Milestone 1: `SPEC-1` (the notation — §S1.2 for the `rule_class` decision procedure Step 6a depends on, §S1.3 through §S1.9 for the validator, plus §S1.4 and §S1.7 for the schema constraints it implies) and `SPEC-3` (identity and deduplication). The third, `SPEC-2` (baseline comparison), binds **Milestone 1.5 only** — you do not need it to build the store, and you cannot do the comparison without it: §S2.1 for the parser, §S2.4's two constraints on what any write-up may claim, and §S2.6's reproduction recipe including the citation regex. Milestone 1.5 summarizes those constraints but does not replace them, and they are the part that stops a comparison from becoming a post-hoc story. **Where this plan and any of the three disagree, the draft wins and this plan is the defect** — with three deliberate refinements, all recorded in the Decision Log: when `dedupe_key` is recomputed, how a missing `dedupe_key` part is encoded, and how a missing element *inside* the tier-2 discriminator is encoded. **The draft itself has been amended in the fifth and eighth review rounds, and every amendment is load-bearing for what you build:** SPEC-1 gained §S1.12, an amendment log, recording `V-STY-03`'s rescoping (A1), `V-VAG-09`'s seed list (A2) and — from the eighth round — the sites of `V-VAG-04` and `V-SING-01` (A3, which is what makes the slot split in Step 4 buildable at all); SPEC-3 gained §S3.1.1 (the file grain of `anchor_key`) and §S3.1.2 (`entity_class` declared at extraction rather than derived from `kind`, which the eighth round extended with the full classification of the closed half after finding the stated default silently unclassified twenty-nine of fifty-two entries). Read those four subsections — they close defects that made Step 4, Step 1, Step 2 and Step 6a unbuildable as previously written. The draft's fourth NORMATIVE section, `PRINCIPLE-1`, is restated in full under `Plan of Work` and is genuinely not a dependency. Everything else you need is here; read the rest of the draft only when you need to know *why* a decision was made.

## Purpose / Big Picture

Today, when an analyst runs LegacyLift's business-rule extraction over a legacy codebase, the output is a markdown file. That file is the only record. Run the extraction again and the previous file is overwritten: any correction a human made to a rule's wording, any sign-off, any note that a rule was reviewed and rejected — gone. There is also no way to ask a question across the results. "Which rules touch the Orders table?" and "how many rules has anyone actually approved?" are questions nobody can answer without reading thousands of lines of markdown by hand.

After this change, extraction writes into a real database. Each business rule becomes a durable record with a stable identifier, a lifecycle (`draft` → `reviewed` → `approved`, or `rejected`, or `superseded`), and citations back to the exact lines of code it was mined from. Re-running extraction **merges** into that store rather than replacing it, so human review accumulates instead of evaporating. Markdown becomes a report generated *from* the store, not the store itself.

Concretely, when this plan's first two milestones are done, an analyst can run these commands in a legacy repository and see the behavior described:

    legacylift-search requirements list --state approved
    legacylift-search requirements show GR-01HQ2X...
    legacylift-search requirements set-state GR-01HQ2X... --to approved
    legacylift-search requirements validate
    legacylift-search requirements export --format jsonl

The first lists approved requirements. The second shows one requirement with its citations, its structured body, and its computed data-flow block. The third is how a human records a judgement: no automated producer can move a requirement out of `draft`, it requires a named reviewer, and it refuses the move to `approved` while any `ERROR`-severity finding stands. The fourth reports rule-notation violations without changing anything. The fifth writes a git-committable text file so a team can review requirement changes in a pull request. Running extraction twice in a row produces the same count the second time, not double — that is the merge working, and it is the single most important observable outcome in this plan.

Two words appear throughout and mean specific things here. A **GR** ("generated requirement") is one record in the new store: a business rule, or later a user story, that a tool generated from source code and a human may then edit and approve. **Layer 0** means the existing deterministic code index built by `tools/legacylift_search/` — its SQLite database of files, symbols, graph edges and facts, plus a vector database for semantic search. Layer 0 is machine-derived and disposable. The GR store is the opposite: it holds human judgment and must never be casually destroyed.

## Progress

**Next action (2026-09-10): Milestone 1.5 — the SPEC-2 baseline comparison. Step 10 is COMPLETE,
all seven phases.** **To start it cold, open
[`active/SESSION-HANDOFF-milestone1.5-2026-09-10.md`](./SESSION-HANDOFF-milestone1.5-2026-09-10.md)** —
it carries the reading order, the pre-flight measurements that are already taken, the one gate to
decide before ingesting anything into the real store, and the nine traps. **State stays here; that
file records nothing.** Phase 6 ran on 2026-09-10 and `rules_candidate` — Step 6's key-instability
measurement, the last unspent deliverable in Milestone 1 — **is 211 of 435 offers (48.5%)**. Every
Milestone 1 acceptance check that needed a real run is discharged: `A1` (Phase 2), `A2` (Phase 1),
`A3` (Phase 5). Numbers live in `Outcomes & Retrospective` → *Step 10 Phase 3, as measured*, *Step
10 Phase 4*, *Step 10 Phase 5* and *Step 10 Phase 6*; commands in the four matching
`Concrete Steps` sections.

**Milestone 1.5 now has the control it did not have, and it is the reason to start there.** The
plan's mandatory noise floor is BASE-ORIG versus BASE-ENH — two runs of the *old* extractor — and
`PR-79` notes that no comparison could separate a pipeline delta from the prompt change. Phase 6
supplies the missing measurement directly: **two four-round runs of the new extractor over
identical code, at identical settings**, giving 379 requirements / 117 files cited against a second
run of 435 offers that widened the corpus to 656 / 140. **The new extractor's own run-to-run
variance is now a measured quantity rather than an unknown**, and it is large — see *Step 10 Phase
6*. Run the BASE-ORIG-versus-BASE-ENH floor as the plan requires, but read it beside this one.

**The real store still holds only run 1, deliberately.** Phase 6 was ingested into a copy under the
scratchpad, per the 2026-09-10 decision, so Milestone 1.5's frozen pair (379 requirements / **118
distinct citation paths, 117 of them real files**) is still recoverable from the real store and was
not spent. The merged two-run store can be produced whenever Milestone 1.5 wants it, from
`extracted-rules-4round-run2.json`, which is saved.

**Phase 5's headline beyond `A3`: the semantic half of stage two has never run against a populated
collection**, verified by code ordering (`gr_ingest.py:1049` — the vector half runs *after* the
commit, so a first ingest queries an empty collection) and by a control experiment (an ingest with
no embedder at all produced candidate counts identical to Phase 3's: 148, `drift` 85,
`range_overlap` 63). **This cannot have cost a rule** — stage two never merges — it costs a reviewer
18 suggested pairs. Both defaults are nonetheless **defensible and should be left alone**:
`SEMANTIC_TOP_K=5` is not the binding constraint (5 and 10 are identical up to `dist_max` 0.50), and
at `SEMANTIC_DISTANCE_MAX=0.35` the twelve closest pairs in the corpus are *all already queued* by
the deterministic reasons, so the semantic half is **redundant here rather than too tight** — the
opposite of the failure direction its docstring feared. The silent shortfall guard is
`pending/deferred-small-items.md` entry 15.

**The real store is still the output of a *single* extraction run, deliberately, and Milestone 1.5's
frozen data point is intact.** 379 requirements over 118 distinct citation paths — **117 of them real
files**. Phase 6 would have turned this into a two-run merge, so it was ingested into a scratchpad
copy instead. The reason the choice mattered, kept here because it governs any *future* decision to
merge for real: the rule count survives a merge (`gr.first_seen_run_id` marks every row) but
**distinct-files-cited does not** — `gr_citation` carries no `run_id` and a later run's citations
attach to existing requirements indistinguishably. The figures are frozen in Milestone 1.5 →
*The new-run data point, frozen 2026-09-10 before Phase 6*. **Take the comparison you want before
ingesting run 2 for real, not after**; `extracted-rules-4round-run2.json` is saved and the merge can
be performed whenever this milestone wants it.

**A free result from Phase 5 worth knowing before Milestone 1.5: `MEAS-1` is exactly reproducible.**
The `A3` degraded ingest was itself a first ingest into an empty store and reproduced Phase 3 figure
for figure, collapse count included. Given a store copy with the domain tables intact, the number is
deterministic rather than a one-run artifact.

**Phase 4's result in one line, and the one hazard it left behind.** Re-ingesting the same file
twice more gave `0 new + 437 merged + 0 candidate` and `rows inserted: 0` both times, with `gr`,
`gr_citation`, `gr_scenario`, `gr_edge_case`, `gr_citation_anchor`, `gr_finding` and
`gr_merge_candidate` all flat, and a second `gr_run` row whose `rules_merged` equals run 1's
`rules_in`. A field-by-field diff across a third ingest shows **every substantive column is stable**
and only `updated_at` plus the `scenario_id`/`edge_case_id` surrogates churn, on exactly the 48 rows
of `MEAS-1`'s reading B. **The hazard: `stats` now prints `intra_run_collapse=106` on all three
runs, and only `RUN-01M2646H97JAZJPPKHSCZT1RRY` is `MEAS-1`** — the other two merged into a full
store, where the same number means something else. Quote a collapse figure only with its run id.

**The three headline numbers, so nobody re-derives them.** `MEAS-1` = **106 offers on shared rows
/ 48 distinct rows absorbing more than one offer**, which is 58 of 437 mined rules (13.3%) not
getting their own row; **the verdict is true-same, not false-same** — all 48 groups were read back
against the corpus and the shape is one file, one identical line range, a later round renaming a rule
it had already found. `MEAS-2` = **39** decision tables. `MEAS-3` = **3–8 rules per table, median 5,
84.6% at or under six**, so **the replay loop is not blocked by the six-rule threshold** — while
still covering only 39 of 379 requirements (10.3%), so DMN coverage of the corpus remains something
not to promise. `A1` was already discharged; **`A3` is NOT discharged by this ingest** — vectors
came back 379 of 379, so the ingest was never degraded, and `A3` needs Phase 5's deliberate
degradation.

**The one thing Phase 3 found that the design had not anticipated, and it is not a defect.** Beyond
the auto-merges `MEAS-1` counts, the store holds **34 `dedupe_key_anchor_only` clusters with 54
excess rows** — the same rule split across rows. **The safety net was verified rather than assumed:
every internal pair of all 34 is queued as a `drift` merge candidate, 34/34 with none missed**, so
the under-merge residue is fully visible, exactly as `gr_ingest.py`'s asymmetry argument requires.
The mechanism is structural: **18 of the 34 are mixed body/bodyless clusters, and the tiered
discriminator hashes a structured body (tier 1) or a span `content_hash` set (tier 2), so those two
rows can never match the exact key however identical the rule.** Only 88 of 379 rows carry a body.
Recorded as its own draft, `pending/dedupe-key-tier-mismatch.md`, and note it is **no longer a
free change**: the store is populated now, so touching the key is a re-key migration.

**One live decision remains and it is the user's: whether to force-add
`analysis/customer.ple.nng.app/knowledge/requirements.jsonl` into git.** `MEAS-1` is spent, so that
decision is closed. The export ran (Phase 3 tested its gate too — it refuses with exit 1 and needs
`--allow-incomplete`, which writes the `_incomplete` header) and produced a 380-line, 2.5 MB JSONL.
But `.gitignore:108` ignores the whole `repos/nng-app-legacylift-analysis/` tree, so the file the
CLI itself calls "what survives" is untracked, and the 437-rule corpus plus its ingested form still
exist only on one laptop. Committing it means putting client-derived business rules into this
repository; **not committing it means an unreproducible artifact has no backup.** No `git add -f`
was run.

**The round-count decision is settled by having been executed: four rounds ran.** It did not
saturate. New rules per round were **112 / 115 / 92 / 118** — round 4 produced *more* than any
other round, so `round_cap` here is not truncating a tapering tail but a flat one, and `dry` was
never reachable. **The corpus size Milestone 1.5 compares is therefore a budget decision, not a
saturation point**, and anyone tempted to run a fifth round should know the return has not yet begun
to fall off. Chunk coverage after four rounds is **473/15,398 = 3.07%**.

**Four extractor/validator defects were found and fixed on 2026-09-08/09, all before any ingest.**
Two came from a code review of the Phase 2 commits, two from the runs themselves. In order of
severity: NOTATION's transcription of the four `structuredBody` payloads did not match
`gr_body_schemas.py` (38 of 40 bodies in the round-1 corpus would have failed, and ingest is one
transaction, so that run would have stored *nothing*); `V-VAG-03` fired on 20% of the corpus at a
severity that blocks approval with none of the 26 findings being an actual vague pronoun, now
**SPEC-1 amendment A4**; NOTATION never stated that decision-table entries are strings, so 6 of 18
tables were refused for a bare `true`/`false` or `0`; and the extractor writes **two files in one
`source` string**, which `rpartition(":")` turned into one citation with a bogus path carrying the
*second* file's line numbers. **The prior gate, the multi-range citation defect, was fixed on
2026-09-08.** Phases 0 and 1 are done and green, and Phase 2 ran once at
`maxRounds: 1` as a verification round after a defect was found and fixed (below). **Step 10 was
never a coding step and now has been one**: `RULES_SCHEMA` was too large for the safety classifier,
so every mining agent failed at spawn and **no live extraction had been possible since the Step 6a
notation rewrite on 2026-09-02**. See `Surprises & Discoveries` → *What Step 10 Phase 2 discovered*.

**Phases 0 and 1, for the record.** Phase 0 (baseline suite, Bedrock probe) and Phase 1
(`/modernize-preflight`, `index --reset`, `backfill-hashes`, `tag-domains`, and all five
post-rebuild assertions) ran on 2026-09-08 and all passed —
**including `A2`, Milestone 0's one deliberately-open acceptance criterion, which is now
discharged**. The rebuilt index is at `user_version` 2 with `entity_class`, `anchor_key` and
`content_hash` non-NULL on all 16,268 symbols, so Step 2's acceptance check is discharged too.
Numbers, transcripts and the reconciliation against the gap plan's trial figures are in
`Outcomes & Retrospective` → *Milestone 1 Step 10, Phases 0–1* and `Concrete Steps`. Phase 2's
launch-and-save and the `A1` gate are done as well — see the next paragraph, which is current where
this one is history. **Phase 2 is now finished in full (all four rounds); what remains is Phases 3–5**
(the three measurements, the merge acceptance test, `A3`) **and Phase 6**.

**Where Phase 2 stands: finished.** The four-round run (`wf_e242dcb9-f34`, 2026-09-10) is the
corpus of record — **552 agents, 0 errors, 437 rules confirmed, 0 rejected**, saved verbatim to
`analysis/customer.ple.nng.app/knowledge/extracted-rules-4round.json` (1,229 KB). The two earlier
runs are superseded as corpora but **their files are kept and must not be overwritten**:
`extracted-rules-round1.json` (133 rules, the 1-round verification run) and
`extracted-rules-scoped2round-test.json` (186 rules, a scoped test artifact). Numbers and the three
findings are in `Outcomes & Retrospective` → *Step 10 Phase 2, the four-round run*.

**`resumeFromRunId` is dead for this step, and the reason generalizes.** Both prior runs
(`wf_5d70da43-474`, `wf_0b5440c3-7e0`) are unusable as caches because four prompt fixes landed after
them — a cached agent replays only when its `(prompt, opts)` are unchanged, so a prompt fix
invalidates every mining agent in the run. **Resume is worth reaching for only when the script's
post-processing changed and the agent prompts did not.**

**The other gate is closed.** The multi-range citation defect was **fixed on 2026-09-08, before any
ingest** — `parse_citation` now emits one triple per comma-separated range, so the 9 affected rules
resolve two symbol anchors each instead of one `unresolved` file anchor. Verified by re-parsing the
saved round-1 JSON: **0 whole-file triples remain across all 133 rules**, and the 9 rules entry 11
measured are exactly the 9 that now expand. Nothing had been ingested, so this was a code change
rather than a re-key migration — which was the entire argument for doing it first. Entry 11 of
`pending/deferred-small-items.md` is therefore gone; the list's preamble records that it shipped.

**What Step 10 is, and what is left of it.** Every line of Milestone 1's code is shipped: Steps
1–5, 6a, 6, 7, 8 and 9 are all done and their headings say so. What remains is a real run against
the NNG app unit — hours of model time — which is also the only way to discharge **three** other
acceptance checks that no unit test can reach. **One of the three is now closed**: Milestone 0's
deliberately-open criterion (no `legacylift-docs/` anywhere under the checkout after a real index
run) was discharged by Phase 1 on 2026-09-08. **Two remain, and both need Phase 2's extraction**:
Step 6a's live check that the extractor actually emits `ruleClass`/`statement`/`modality` (`A1`),
and `PR-47`'s hand-off half — a degraded ingest followed by `requirements reindex-vectors`
populating the collection with no re-extraction, which spans two command modules and so was not
provable at unit scale (`A3`).

Two corrections to the earlier framing of this block, so neither is re-derived. It called for a
**four-command** pipeline run; the settled 2026-09-08 decision is **`/modernize-preflight` only**,
for the reasons two paragraphs down. And it said `Concrete Steps` "says why none of it may be
shortcut" — that section now carries the deviation and its rationale instead.

Baseline before you start: **1,250 tests, exit 0** — re-confirmed 2026-09-08 at 6m21s (1,207 from
the 2026-09-03 merge until the 2026-09-08 coverage widening; 1,159 until the 2026-09-03 merge of
`feature/layer0-extraction-gap-detection`, which added 48).

**To actually run it, open [`reqs-to-data-store-step10-runbook.md`](./reqs-to-data-store-step10-runbook.md)
in this directory.** It is the execution detail for this one step, written 2026-09-02 so an agent
starting cold can run it without reading this file end to end: the measured on-disk state of the
NNG unit, the two environmental traps that will otherwise cost a cycle (the `PATH`
`legacylift-search` shim is **broken** — use the venv binary; a Workflow launch here needs an
ASCII-normalized copy and an `args` JSON-string shim), seven phases with exact commands and the
exact SQL for each measurement, and a per-phase subagent/model split. **State stays here** — the
runbook records nothing; results come back to `Progress`, `Outcomes & Retrospective` and
`Concrete Steps`.

**Phase 1 invalidated four rows of the runbook's own “Verified state” table, and the runbook says
the plan wins where the two disagree — so read these here rather than there.** `index.sqlite` is no
longer at `user_version` 0 and no longer predates Step 2: it is at **2**, freshly built, with
`anchor_key`/`entity_class`/`content_hash` populated, so the rebuild-not-backfill instruction is
**already carried out** and must not be repeated. `knowledge.sqlite` is no longer GR-table-less:
all eleven plus `gr_fts` exist, at `user_version` 1, with `gr` and `gr_run` empty. `file_domains`
is no longer 1,229 rows / 383 `excluded`: it is **1,504 / 384**, re-tagged against the widened
discovery. The runbook's *(pre-widening)* figures are the before-picture of a move that has now
happened. Its Phases 2 onward are unaffected and remain the execution detail to follow. The **one decision it raised has been settled** (2026-09-08, user's call, and
disclosed where the runbook asks for it in `Concrete Steps`): of the four pipeline commands,
**Phase 1 re-ran `/modernize-preflight` only**, reusing the existing `ASSESSMENT.md`,
`domains.json` and `topology.json`. Re-running `/modernize-assess` would re-author the pinned
canonical `domains.json` nondeterministically — moving every `derived` subject and desynchronizing
the Milestone 1.5 baseline — and it authors neither `vendored_globs` nor `own_identities`, the two
provenance fields `discover_source_files` now reads, so it would silently delete them and put 11
vendor `.tld` descriptors back into the index. **Milestone 1.5 compares against this run.**

**The pre-Step-10 wave is done and Step 10's own prerequisite is closed.** The workflow now emits
`roundCap`, `stopReason` and `newRulesInFinalRound`, so all four `gr_run` termination columns have a
producer — ingest always read them, but three had no source, and a NULL there correctly means
"never measured", so they would have been permanently blank for a run costing hours of model time.
**`stop_reason`'s three-value `CHECK` is now exactly reachable in both directions**, and the third
value's producer — which this plan names nowhere — is the extraction loop's budget `break`.

**Two of Wave C's four defects are fixed and two are deferred**, decided rather than left open:
`ImportResult` now names the records whose approval it protected, and `import_records` can reach an
embedder. `gr_state.set_state`'s dropped `EmbedResult` and `describe_vector_shortfall`'s two-`int`
signature are **`pending/deferred-small-items.md` entries 4 and 5**, with a third — entry 6, the
durable `gr_import` row keeping the ambiguity the in-memory fix removed — opened by the fix itself.
All three want the same thing: the first `knowledge.sqlite` *column* migration, which Step 3
deliberately left as the line where the free-table-addition rule stops. `Outcomes & Retrospective`
→ *Milestone 1 Step 8* carries the evidence for each.

**Two unvalidated defaults Wave B had to invent, because the plan specifies neither, and both
want measuring in the same run as Step 10.** Stage two's semantic half uses top-k 5 and a maximum
distance of 0.35. Neither can ever cause a merge — they only change which pairs a reviewer is
shown — and both are parameters of `ingest_extraction` rather than constants. **They are also
metric-dependent and nothing here pins the metric:** `ChromaVectorStore` sets
`hnsw:sync_threshold` and `hnsw:batch_size` but no `hnsw:space`, so the distance is whatever the
installed chromadb defaults to (L2 on the pinned 1.5.9). The failure direction is the quiet one —
too tight a threshold raises fewer candidates, and stage two returning none is indistinguishable
from there being no near-duplicates to find.

**Three things Wave C settled that Step 10 must not re-derive.** `KnowledgeStore.intra_run_collapse_count`
counts **offers, not collapsed requirements** — two offers landing on one `gr_id` returns 2, not 1,
and its own docstring says so, but "the intra-run collapse count" reads like a count of collapses
and one of Step 10's three measurements is exactly this number. Decide which you are reporting and
label it. The `hash` embedding provider is built at `manifest.embedding.dimension` = **1024**, not
`HashEmbedder`'s own default of 64, so a collection seeded at 64 fails `validate_dimension` and the
test then measures a dimension mismatch instead of what it claims; and `EmbeddingConfig.provider`
defaults to `qwen3` (a model load), so any test or dry run touching the vector half must pin
`hash` explicitly. And **`ingest_extraction` has no `system` parameter** — it reads
`payload["system"]`, so `requirements ingest --system` injects into a shallow copy of the payload,
the flag wins over a value already in a saved file, and a disagreement prints a loud stderr line
naming both.

Every step of Milestone 1 is shipped — Steps 1 through 5, 6a, 6, 7, 8 and 9 — and their headings
say so.

**Superseded, and do not restore either:** the previous Next action pointed at Step 8 with an
870-test baseline, and the one before that at Step 6a with 734. Both are stale.

**What is still outstanding in Milestone 1**, so the tick marks above are not the only place this
is stated: **nothing. Milestone 1 is complete as of 2026-09-10.** Step 10's three mandatory
measurements were taken in Phase 3, its three run-dependent acceptance checks (`A1`, `A2`, `A3`) are
discharged, the merge acceptance test passes on the real store, and Phase 6 spent the last
deliverable — `rules_candidate`. The next work is Milestone 1.5. Two items are *filed rather than
outstanding* and must not be read as Milestone 1 gaps: the exported `requirements.jsonl` is still
untracked because `.gitignore:108` ignores the whole `repos/nng-app-legacylift-analysis/` tree
(committing client-derived requirements is the maintainer's call, and no `git add -f` has been run),
and the small defects the run surfaced live in `pending/deferred-small-items.md` as entries 15, 16
and 17.

**Step 6a's first half was the first work in this plan to leave `tools/legacylift_search/`**, and
what it established is worth carrying into any later skill-file work: all three files that
carried the old Given/When/Then shape had to change together — the command file, the agent
definition and the Rule Card format — because the acceptance check in `Concrete Steps` (open the
saved extractor JSON and confirm a rule object carries `ruleClass`, `statement` and `modality`)
fails if any one of them still describes the old shape. That check is still outstanding: it can
only run against a live extraction, in the same run as Step 10. The `PR-79` Decision Log entry
carries the measurements that made the *previous* design of the step unbuildable, and they are
also what Milestone 1.5 compares against.

**What Step 5 leaves you.** `gr_refresh.refresh_gr_derived_sql` and `refresh_gr_vectors` are the
pair every write path calls, in that order, around the caller's commit; `set_state` is wired and
is the worked example of a call site. Ingest (Step 6) is the next caller and calls each **once for
the whole run**, not per record. Two things Step 6a and Step 6 must not re-derive: the
`gr_statements` collection lives under the *knowledge* directory (`open_gr_collection` resolves it
from `store.sqlite_path.parent` — do not pass an index directory), and the vector half is allowed
to degrade, so ingest reports `EmbedResult.reason` and **exits zero**.

**And read the line-reference correction table under `Surprises & Discoveries` before you follow
any `file.py:NNN` in this plan.** Every one has drifted — Milestone 0 and Steps 1–5 added ~600
lines to `store.py`/`knowledge_store.py` and ~270 to `cli.py`. The constructs all still exist;
only the numbers are wrong.

Keep this line current: it is the one place that states where to start, and a stale one sends the
next agent to the wrong step.

- [x] (2026-08-31) Milestone 0: versioned schema migration mechanism for both SQLite databases (`PRAGMA user_version` + ordered forward-only steps). `migrations.py`, both lists carrying the version-1 no-op baseline, 18 tests.
- [x] (2026-08-31) Milestone 0, second half: all generated output relocated under `analysis/<system>/` per the `code-modernization` layout — path resolution with detection plus override, resolved paths printed, `.gitignore` rules, `index --reset`'s safety guard widened to the new layout, and the existing `repos/` artifacts moved and verified.
  - [x] (2026-09-08) **The one deliberately-open acceptance criterion is discharged** — `A2` in the Step 10 runbook. A real `index --reset` over `legacy/customer.ple.nng.app` (1,504 files, 4,970 vectors re-embedded through Bedrock Titan) left **zero** `legacylift-docs` directories anywhere under that checkout, asserted as a filesystem `rglob`, not as `git status`: that tree is not its own repository and `.gitignore:92` ignores it whole, so the git form reports clean either way. Both commands printed their resolved directories under `analysis/customer.ple.nng.app/`, and `knowledge.sqlite` survived the reset in place. Evidence in `Outcomes & Retrospective` → *Milestone 1 Step 10, Phases 0–1*.
- [x] (2026-09-01) Milestone 0 code review follow-ups — all six defects `CR-01` … `CR-06` fixed, each with a probe that fails before and passes after. See `Outcomes & Retrospective` → *Milestone 0 code review* for each one's evidence and fix.
  - [x] `CR-01` — migrations now run from `SQLiteStore._connect`, so every read path advances the schema. Was: `run_migrations(INDEX_MIGRATIONS)` only runs from `index`/`backfill-vectors`, so version 2 will not reach an existing `index.sqlite` that a read command opens. Both NNG indexes are at `user_version` 0 today.
  - [x] `CR-02`/`CR-03`/`CR-04` — settled once in `apply_path_overrides`, the single entry point for both flags. Was: `resolve_index_dir`, `resolve_knowledge_dir` and `cli_helpers.resolve_paths` implement three different precedences over the same two flags. Settle it once, in one place, and make all three call it.
  - [x] `CR-05`/`CR-06` — fixed, and `CR-06`'s parity now holds in both directions (Wave 3). Was: `index --reset` refuses a directory an interrupted reset left behind, and refuses both configured-`index_dir` branches while its comment claims parity with the resolver.
  - [x] (2026-09-01) Closed the §6 `--analysis-dir` gap — all 14 commands now carry the flag. Was: they are the three commands that consume both stores, so the pipeline breaks after `index --analysis-dir`.
- [x] (2026-09-01) Milestone 1 step 1: `src/legacylift_search/identity.py` — the shared identity module (`anchor_key` at both grains, `content_hash`, `normalize_path`, `new_ulid`).
- [x] (2026-09-01) Milestone 1 step 2: `anchor_key`, `entity_class` and entity-level `content_hash` as columns on the Layer-0 `symbols` table; `entity_class` **declared by every extractor** (profiles JSON, framework extractors, regex fallback), `anchor_key` backfilled by migration, `content_hash` by a new `backfill-hashes` command. Reviewed in the same wave: four further defects `CR-08` … `CR-11` found and fixed — see `Outcomes & Retrospective` → *Milestone 1 Steps 1–2*. 521 tests pass (was 408).
- [x] (2026-09-01) Milestone 1 step 3: all eleven GR tables in `knowledge.sqlite` (`gr`, `gr_citation`, `gr_citation_anchor`, `gr_scenario`, `gr_edge_case`, `gr_finding`, `gr_dataflow`, `gr_merge_candidate`, `gr_run`, `gr_run_hit`, `gr_import`), created by `KnowledgeStore._migrate_gr_tables` from `migrate()` — **no `KNOWLEDGE_MIGRATIONS` entry, deliberately**: adding a *table* is free because `migrate()` runs from `__init__` on every open, so an existing store gains them with no version bump; the first GR *column* addition is what needs a migration. `gr` carries exactly the forty-two columns, asserted. Plus `src/legacylift_search/gr_body_schemas.py` — the four `structured_body` payloads as `pydantic` models, the single `validate_structured_body` entry point, and `canonical_structured_body`, which is the tier-1 `dedupe_key` discriminator and had no named producer before. 588 tests pass (was 521).
- [x] (2026-09-01) Milestone 1 step 4: `src/legacylift_search/gr_validator.py` — all twenty-eight SPEC-1 checks, the shared keyword matcher, and the template-driven `split_slots`; plus `src/legacylift_search/gr_state.py` — `ALLOWED_TRANSITIONS` and `set_state`, carrying the `draft → approved` gate. `GRRecord` and `Finding` added to `models.py`, and four GR methods to `KnowledgeStore` (`get_gr`, `list_gr_findings`, `replace_gr_findings`, `apply_gr_state`). **All 28 identifiers proved reachable by probe, not by inspection**, and ten plausible conformant statements across all ten patterns produce zero blocking `ERROR`s. 706 tests pass (was 588).
- [x] (2026-09-02) Milestone 1 step 5: `gr_fts` (standalone FTS5, `chunk_fts`'s shape, created by `_migrate_gr_tables` with **no** `KNOWLEDGE_MIGRATIONS` entry — a table addition, same reasoning as Step 3), the dedicated `gr_statements` Chroma collection **under the knowledge directory** so `index --reset` cannot reach it, and `src/legacylift_search/gr_refresh.py` — the refresh **pair** (`refresh_gr_derived_sql` inside the caller's transaction via `SAVEPOINT`, `refresh_gr_vectors` after the commit and permitted to degrade), plus `describe_vector_shortfall`, `open_gr_collection` and `open_index_store_if_present`. `ChromaVectorStore` gained `upsert_texts`, `count()` and `delete_ids`, and its first parameter is renamed `index_dir` → `base_dir` across all sixteen construction sites. **Both seams Step 4 left open are closed**: `set_state` calls the full pair, and `refresh_gr_derived_sql` builds `leaked_terms` from the requirement's own cited files. 734 tests pass (was 706).
- [x] (2026-09-02) Milestone 1 Wave 0 (of Step 6a/6/7/8/9): the ten remaining GR Pydantic models in `models.py` — `GRCitation`, `GRCitationAnchor`, `AnchorHit`, `AnchorResolution`, `GRScenario`, `GREdgeCase`, `GRMergeCandidate`, `GRRunHit`, `DataflowEntry`, `GRRun`. Landed as **one file with one owner before any parallel work started**, because it is the shared contract five later units import and a conflict point if delegated. Each table-backed model's field set is verified against `PRAGMA table_xinfo` for its table — eight tables, zero mismatches. `GRRun.complete` is a read-only **property** computing the generated column's expression, not a field, so it cannot be set out of step with `not_accounted_for`; `table_xinfo` rather than `table_info` is required to see that column at all. Validators mirror the DDL `CHECK`s at construction, and three of them guard the recurring absent-versus-real class: a non-empty `anchor_key` on all three anchor-bearing models (the `''` that silently collapses stage-one dedupe corpus-wide), a nullable `GRMergeCandidate.similarity` that is not `0.0`, and `gate_excluded` requiring a non-empty reason. 734 tests, exit 0 — unchanged, as expected for a types-only change.
- [x] (2026-09-02) Milestone 1 step 6a, **both halves**, built as five parallel units after the ten remaining Pydantic models landed first as a single-owner shared contract. 821 tests, exit 0 (was 734).
  - [x] The extractor authors SPEC-1 notation — all three files that carried the old shape changed together. Three corrections the source forced on this plan's own wording: **`gr.modality` is NOT SPEC-1's modal keyword**, it is `CHECK (modality IN ('requirement','expectation'))`, Q3i's KAOS pair, and `gr_validator.py` never reads the column at all — so §S1.3's keyword sets belong in the `statement` description, where the `V-KW-*` checks actually test them; `ruleClass` is required but **nullable**, because §S1.2 step 4 mandates NULL when neither class is determinable and forbids guessing; `pattern` is optional with `null` in its enum and abstention stated as a last resort.
  - [x] `citations.py` — `parse_citation` promoted out of `cli.py` with a strict mode (the old name delegates, so the coverage denominator cannot disagree with ingest), plus `resolve_anchor`: innermost containing symbol, smallest-span intersector, the stated tie-break applied to **both** pools, the total file-level floor, existence-based `unresolved`, and a per-run hash cache held as an instance attribute. Six deviations from the sketch, all improvements and all recorded in the code — the load-bearing one is that a **whole-file citation short-circuits to the file anchor**, without which a bare path intersects every symbol and the *smallest* declaration in the file wins the key.
  - [x] `gr_fields.py` — the four-way partition (14/3/9/16), `SHADOWED_FIELDS` derived from `PRAGMA table_info`, tuple-valued `EXTRACTOR_FIELD_MAP`, and `UNMAPPED_KEYS` **verified empty rather than assumed**: all 22 rule keys are accounted for — 14 through the map, `ruleClass`/`pattern` verbatim outside it, six as child rows.
  - [x] `gr_subject.py` — the one subject derivation both ingest and `rederive-subjects` call, with the two sentinels kept distinct and an absent subject (NULL `pattern`, so no locatable `[Subject]`) stored NULL and counted apart from `llm_named`.
- [x] (2026-09-02) Milestone 1 step 6: merge-with-dedupe ingest — **plus the two dedupe keys themselves, which did not exist.** Step 3 created the columns and specified the formulas and Steps 4–5 read them, but no producer had ever been built, so `gr_keys.py` landed here: both keys, the discriminator tier selection, `sorted(set(...))` taken *inside* the functions so a caller cannot get the two readings of `sorted(anchor_keys)` wrong, and `UNIT_SEPARATOR`/`DIGEST_HEX_CHARS` imported from `identity` rather than redefined. **Verified by probe, not inspection: a requirement whose every citation is unreadable keys differently from one with no citations at all** — tier 2 versus tier 3, exactly what the `ch0:none` sentinel exists to keep apart. `gr_ingest.py` is one transaction over eight tables, one shared `IS`-not-`=` helper for the three shadowed fields, value-changing-write on `updated_at`, and stage two raising candidates that never merge. **All raw `gr` SQL lives in `knowledge_store.py`** — the writer census asserts which modules write the table, so the layering is enforced rather than conventional. Six further decisions and two resolved ambiguities are in the commit message and in the modules' own comments; the two ambiguities are the pattern-free statement fallback's `[Subject]` (the rule's `name`, then `plainEnglish`, then `"This rule"` — never one of `V-SLOT-02`'s four banned literals) and the semantic-candidate thresholds named in the Next action above. 870 tests, exit 0 (was 822).
- [x] (2026-09-02) Milestone 1 step 7: the `reads[]`/`writes[]` data-flow block — table, model, rendering and computed code all built, but **no writer in Milestone 1**: the computed path is flagged off pending M26 of `docs/exec-plans/active/semantic-code-search-graph-index.md`, and the LLM fallback has no extractor source until the field is added alongside that work. `stats` says so in words and reports no rate.
- [x] (2026-09-02) Milestone 1 step 8: the `requirements` CLI command group — all **fourteen** commands (`ingest`, `list`, `show`, `search`, `set-state`, `set-field`, `set-run-coverage`, `retire-run`, `reindex-vectors`, `rederive-subjects`, `validate`, `stats`, `export`, `import`), verified registered under one group by probe. Built as a foundation commit plus four parallel units on disjoint files. **870 → 1,131 tests, exit 0.**
  - [x] Wave C1, single owner, first: the GR query and `gr_run` write API in `knowledge_store.py` (twelve readers, two writers), `gr_setfield.py` and `gr_rederive.py` as callable functions mirroring `gr_state.set_state`, a **public** `gr_refresh.leaked_terms_for` (so `validate` can run the validator without writing `gr_finding` rows) and `reindex_gr_vectors`, the `cli_requirements/` package with `_shared.py`, and the **first `app.add_typer` in `cli.py`**. 965 tests. It also closed a hole in the writer census: `tests/test_gr_state.py` globs `src/legacylift_search/*.py` — flat — so a module in the new sub-package could have composed its own `UPDATE gr SET` invisibly; a package-scoped equivalent now reuses the same `ast` scan.
  - [x] Wave C2, four parallel units: `read_cmds` (`list`/`show`/`search`/`stats`, 44), `write_cmds` (`set-state`/`set-field`, 53), `run_cmds` (`ingest`/`validate`/`set-run-coverage`/`retire-run`, 33), `repair_cmds` (`reindex-vectors`/`rederive-subjects`/`export`/`import`, 36). **Every command wires a shipped function and adds nothing** — a second copy of a rule in the CLI is the sixth review round's stale-copy defect. Four defects in shipped code were found and deliberately left to their owners; see `Outcomes & Retrospective`.
- [x] (2026-09-02) Milestone 1 step 9: `gr_export.py` — deterministic JSONL export (byte-identical second run; the `_incomplete` header under `--allow-incomplete` only, carrying no timestamp) and `import_records`, the one declared second writer of `gr.state`. The `/modernize-extract-rules` wiring shipped alongside Step 6a's first half. **Its `--allow-downgrade` ranking puts `superseded` ABOVE `approved`, not level with it**: level made the comparison a tie in both directions, so a stale export would silently restore `approved` over a record the store had since superseded, reverting a human's judgement and orphaning `superseded_by` with no flag required. Its two CLI commands shipped in Step 8's Wave C2, which also found **two defects in this step's own code, both still open**: `ImportResult` cannot report a refused downgrade, and `import_records` has no `embedder` parameter. See `Outcomes & Retrospective` → *Milestone 1 Step 8*.
- [x] (2026-09-08) Out-of-band, gating Step 10 Phase 3: **`parse_citation` accepts multi-range citations.** `path:24-26,62-70` is a well-formed citation the extractor emits (9 of 133 round-1 rules, 6.8%) and the parser silently made it a whole-file citation whose *path* held the range text, so the rule keyed at tier 2/3 instead of tier 1. Now one triple per range, via a `_parse_range_list` helper running the same `split("-", 1)` body per comma-separated piece; a malformed piece fails the whole entry rather than half-keeping it (strict raises, non-strict falls back to the pre-existing whole-entry-as-path behaviour). **Landed before the first kept ingest on purpose** — afterwards it is a re-key migration over `knowledge.sqlite`. Verified against the saved round-1 corpus: 9 rules expand, **0 whole-file triples remain**. 1,256 tests, exit 0 (was 1,250).
- [x] (2026-09-10) Milestone 1 step 10, **complete — all seven phases**: all three mandatory measurements taken, every acceptance check that needed a real run discharged, and Phase 6's `rules_candidate` spent. `MEAS-1` = **106** offers on shared rows / **48** distinct absorbing rows (58 of 437 mined rules, 13.3%, did not get their own row), verdict **true-same** on a census of all 48 groups; `MEAS-2` = **39** decision tables; `MEAS-3` = 3–8 rules per table, median 5, **84.6% at or under six**, so the replay loop is not blocked by the six-rule threshold. All four `gr_run` metadata columns populated (`round_cap`, 4 rounds, `new_rules_in_final_round` 118). `A1` discharged by Phase 2 (2026-09-10), `A2` by Phase 1 (2026-09-08), **`A3` by Phase 5** (2026-09-10) — degraded ingest exits zero and names `reindex-vectors`, which then populates 379 of 379 with no re-extraction. Phase 4's **merge acceptance test PASSES on the real store**, confirmed by a field-by-field diff across a third ingest rather than by counts alone. Both unvalidated defaults measured and **left unchanged** on the evidence. See `Outcomes & Retrospective` → *Step 10 Phase 3, as measured*, *Step 10 Phase 4* and *Step 10 Phase 5*.
  - [x] (2026-09-10) **Phase 6 is done — `rules_candidate` = 211 of 435 offers (48.5%)**, the key-instability figure, from a second four-round extraction (`wf_fe5c5435-2db`, 595 agents, 0 errors, 16.76M subagent tokens, 3 h 6 m) ingested into a **copy** of the store per the settled decision, so Milestone 1.5's frozen pair was not spent. `rules_new` = 66, `rules_merged` = 158, 3 rejected by the referee panel. `A1` passes 435/435 and 93/93 `structuredBody` payloads validate, so no repair pass. **The predicted first-ever `semantic` merge candidates appeared** — 39 raised, 14 surviving in the store with non-NULL `similarity` 0.742–0.939, all fourteen cross-run pairs. Two findings the run produced that the handoff did not predict, both measured: the ingest banner's per-reason candidate tally **cannot be reproduced from the store** (25 `semantic` inserts are silently rewritten to `range_overlap`, `pending/deferred-small-items.md` entry 17), and the merge's field churn is **not** the predicted cosmetic `updated_at`-only diff — 91 pre-existing rows had every extractor-owned field replaced by run 2's phrasing. See `Outcomes & Retrospective` → *Step 10 Phase 6*.
- [ ] Milestone 1.5: the SPEC-2 baseline comparison against the two NNG corpora (noise floor first, then NEW vs each baseline).
- [ ] Milestone 2: the other four GR producers against the same schema.
- [ ] Milestone 3: the vocabulary layer (`term`, `fact_type`).
- [ ] Milestone 4: the review experience — deferred to `docs/exec-plans/pending/reqs-review-ui.md`. Milestone 1 ships only the minimal `requirements set-field` write path that its own acceptance tests require.

Use timestamps as work completes, for example `- [x] (2026-08-26 14:30Z) Milestone 0 complete.`

## Surprises & Discoveries

Milestone 0 is built; what it surprised us with is recorded in `Outcomes & Retrospective` → *Milestone 0*, and what two code-review passes then found in the shipped code is in *Milestone 0 code review* (`CR-01` … `CR-07`) directly below it. Record further observations here with concise evidence as you go. Two findings from the design phase changed decisions rather than merely surprising us, and so are recorded in the Decision Log rather than here: `symbols.id` embeds a line number and so is not stable across edits, and there was no schema migration mechanism anywhere in `tools/legacylift_search/src/`. A third — that fact-graph emitted 5 of its ~45 advertised predicates on the one real corpus, and that 4 of those 5 are already Layer-0 output — is a measurement owned by `docs/exec-plans/pending/fact-graph-decision.md` §5a.5, not by this plan; it is the evidence behind the two fact-graph decisions below, and this plan does not restate or re-measure it.

### What the second four-round run discovered (2026-09-10, Phase 6)

**The extractor is far less key-stable than the plan's framing implied, and that is the headline
rather than a caveat.** Over identical code at identical settings, only **36.3% of run 2's offers
matched an existing requirement on the exact `dedupe_key`**; 48.5% matched on the anchor-only key
with a discriminator mismatch and 15.2% matched nothing. The two-tier key caught every one of
them — all 211 were inserted *and* queued as review pairs — so the store behaved as designed. What
moved was the extractor's own account of the same code: statement wording, `ruleClass`, `pattern`,
and the `structuredBody` presence that selects the discriminator tier. **Anyone sizing the review
burden of a second extraction should budget for ~half the offers arriving as candidates, not for a
quiet merge.**

**Two runs now agree that four rounds do not saturate, and the agreement is the useful part.**
New rules per round were 130/124/83/101 here against 112/115/92/118 in run 1. Both dip in round 3
and recover in round 4; neither tapers. A single non-saturating run is a budget observation, but two
independent ones over the same corpus make it a property of the extraction loop at this scale.
Coverage after four rounds was 2.9% of chunks here and 3.07% in run 1.

**`pending/dedupe-key-tier-mismatch.md` is now measured on two runs and it is bigger than it looked.**
Run 2's discriminator tiers were 1=93 / 2=342 against run 1's 1=88 / 2=349 — so the tier split is
stable in aggregate while the *per-rule* assignment is not, which is exactly the condition the
filed defect describes: a rule mined once with a `structuredBody` and once without is discriminated
at different tiers and its two rows can never match the exact key. That draft's note that it is
"not a correctness defect" still holds — every affected pair is queued as a candidate — but its
cost is no longer 34 clusters / 54 excess rows. **On a two-run store it is a large fraction of the
211.** The draft is still correct that this is no longer a free change, because altering the key is
now a re-key migration over a populated store.

**A count test cannot see the ingest banner disagree with the store, and here it does.** The
banner's per-reason candidate tally counts *inserts*; the stored `reason` column can be overwritten
afterwards by a second raise of the same pair, uncounted. The totals therefore agree (374 = 374)
while the breakdown does not (`semantic` 39 vs 14, `range_overlap` 152 vs 177). This is the same
shape as the hazard Phase 4 recorded — a field rewrite a count assertion is blind to — and it is
worth stating as a general lesson about this ingest: **the banner is a record of what the run did,
the store is a record of what survived, and Phase 6 is the first run where those differ.** Filed as
`pending/deferred-small-items.md` entry 17.

**The handoff's prediction about export churn was wrong in scope, and the correction matters more
than the prediction did.** It predicted a diff confined to `updated_at`, cosmetic. The measured diff
replaces every extractor-owned text field on 91 rows, flips `category` on 16, `priority` on 13 and
`modality` on 4. **All of it is correct behaviour** — `gr_fields`' partition protected all nine
`HUMAN_WRITABLE_FIELDS` and wrote the three shadows only where the live value still equalled its
shadow — but "cosmetic" would have been a materially misleading thing to write in a plan. The
reason the prediction went wrong is instructive: it was extrapolated from Phase 4, where the same
file was re-ingested and so `merged with no value change` was 331 of 437. A *different* corpus
merging into the same rows changes values by definition, and Phase 6 reported that figure as **0**.

**One prose citation per run appears to be the steady-state rate, and it inflates a file count.**
Each run contributed exactly one rule whose `source` is prose rather than a citation, and in both
cases the whole prose string lands in `gr_citation.relative_path` (445 and 459 characters). It
degrades to `unresolved` and does not abort, as entry 13 records — but it also **counts as a
distinct cited path**, so a naive `COUNT(DISTINCT relative_path)` overstates file coverage by one
per affected run. Filter on length or on `anchor_resolution` before reporting a file count.

### What the four-round run discovered (2026-09-10)

**The headline is a negative result: four rounds do not saturate the extraction loop.** New rules
per round were **112 / 115 / 92 / 118** (437 catalogued, 0 rejected by referees). Round 4 was the
*largest* round, and round 3's dip to 92 did not continue, so there is no decay curve here to read a
stopping point off. `stopReason` is `round_cap` and `dry` was never reachable — `deriveStopReason`
needs two consecutive dry rounds and the `while` guard exits at the cap first. **What this changes:
the round count is a budget parameter, not a convergence one, and any future claim that "the loop
ran dry" needs `stopReason: 'dry'` behind it rather than a flattening count.** Chunk coverage reached
only **473/15,398 = 3.07%** of the index, which is the honest denominator for how much of this estate
four rounds actually touched.

**The four 2026-09-08/09 prompt fixes hold, on their first end-to-end exercise.** Bodies valid on
first emission: **88/88 (100%)**, against 2/40 (5%) before the fixes and 43/49 (88%) on the scoped
run — so `validate_structured_body` rejected nothing and **no `repair-structured-bodies` pass was
needed**. All ten SPEC-1 §S1.4 patterns and both modality values have live output, `implementationNotes`
and `assumptions` are on **100%** of rules, and P0 settled at **45/437 (10.3%)**, holding near the
reference corpus's ~13% rather than reverting to the 33% the deleted `priority` criterion produced.

**A third bad citation shape exists, and it is prose.** One rule of 437 (`Northern Natural Gas
own-party identity`, D-CONST) emitted a **586-character English sentence** as its `source`:
paths prefixed with the session-relative path *to* the codeRoot instead of relative to it,
parenthetical asides (`(isNNG predicate; field bound at :48-49)`), `and` / `; supporting:`
connectives joining several files, and a bare single-line list (`...java:401,419,504,572`) that the
comma-split then tears into a fourth bogus triple beginning `572 and PartyService.java...`. All four
cited files exist under the codeRoot, so this is a **formatting defect, not a hallucinated
citation** — the evidence is real and recoverable by hand. **The lesson is about the previous two
fixes, not this rule:** multi-range and multi-file were both fixed by teaching `parse_citation` a
richer grammar, and this shape shows that road has an end — an agent can always write prose into a
string field, so the durable defense is a per-rule *emission* constraint, not a more forgiving
parser. Filed as **entry 13** of `pending/deferred-small-items.md`. The plan's standing caveat that
"the citation base is an observation about prior corpora, not a guarantee" was correct and should
stay.

**The DTO catalog stalled, and it is NOT the `RULES_SCHEMA` size trap — measuring it was what
established that.** The Data objects agent failed with `1 StructuredOutput validation failure (last
input: {"__unparsedToolInput"...` after twice reporting "the payload was too large", and the
runtime's retry produced the 63-object catalog. But serialized, `DTO_SCHEMA` is **543 bytes**, the
second-smallest of the file's five schemas; `RULES_SCHEMA` was 15,242 and was refused *at spawn*.
**The mechanism is inverted: a tiny but wholly unbounded schema**, whose open `fields` and
`consumedBy` arrays let one response outgrow the tool-input limit — so shrinking the schema is the
wrong fix and bounding the response is the right one. It cost nothing this run
(`dataObjects: (dto && dto.dataObjects) || []` tolerates a null, and the phase runs after
`confirmed` is computed). **The worse finding is beside it:** the prompt passes
`ruleNames.slice(0, 250)`, so **187 of this run's 437 rules were never shown to the DTO agent** and
`consumedBy` silently cannot reference them — a defect already sitting in the returned corpus, newly
reachable because no earlier run exceeded 250 rules. Both are now owned by `pending/dto-catalog-bounding.md` (promoted out of `deferred-small-items.md` entry 14, whose number is retired). **The general
lesson: "payload too large" names a symptom shared by two opposite causes, so measure the schema
before assuming which one you have.**

**The wall clock is not a throughput measurement, and reading it as one was wrong.** The run
reported 19.4 hours; **active compute was ~1.6 hours**. 551 of 552 agents completed inside a
2.2-hour window, then two multi-hour gaps followed (the laptop slept, and the resume delivered
`[Request interrupted by user]` to the one in-flight agent). Measured from agent-transcript mtimes:
**5 gaps over 10 minutes accounting for 17.5 h of the 19.1 h span — 92% idle.** Two things worth
carrying: **an overnight workflow on a laptop needs sleep disabled**, because a resume interrupts
whatever agent was in flight rather than resuming it; and **agent count, not wall clock, is what
scales with the work** — 552 agents for four rounds against 238 for one, comfortably inside the
1000-per-workflow cap and below the 500–700 estimate.

**`journal.jsonl` is a real recovery path for a corpus, and that was worth establishing before it
was needed.** The workflow's per-agent journal carries the 12 extract results (452 raw rule objects
with the full notation shape) plus all 437 verify and 98 P0 verdicts, so a run that never returns is
**not** a lost corpus. Backed up alongside the corpus as
`knowledge/extracted-rules-4round-journal-backup.jsonl` (2.4 MB). This retires the "hours of model
time, exactly one copy" exposure that the runbook and this plan both warn about — for extraction at
least, the return value is no longer the only copy.

### What the Phase 3 rehearsal and the scoped two-round run discovered (2026-09-09)

**The single most valuable thing this day produced: rehearsing Phase 3 against a *copy* of the store
found two blocking defects for the price of minutes, and spent nothing a real Phase 3 needs.** Both
would have surfaced during a four-round run, at the point where they were most expensive. Neither
was visible to the unit suite, which was green throughout.

**1. Ingest would have stored nothing, and the suite could not see it.** NOTATION's prose
description of the four `structuredBody` payloads — the prose that *replaced* the deleted four-way
`oneOf` on 2026-09-08 — did not match `gr_body_schemas.validate_structured_body`, this system's
designated single authority on those payloads. Measured over the 133-rule corpus: **ok 2, bad 38**;
`decision_table` 24/24, `formula` 7/7 and `invariant` 7/7 all failed. The prose named
`inputs[{name}]` where the model requires `label`/`expression`/`typeRef`, `condition` where
`InvariantBody` requires `expression`/`scope`/`notation`, and marked `scale`/`meter` optional where
`FormulaBody` requires both. Because `ingest_extraction` owns one transaction per run, the first bad
rule aborts everything. **The lesson is not "check the prose" but "a duplicated contract needs a
mechanical cross-check":** the prose now exists in two files (`extract-rules.js` NOTATION and
`repair-structured-bodies.js` SHAPES) because a workflow script cannot read a Python module, and a
script that walks `model_fields` and greps both copies is what keeps them honest.

**2. The corpus was recoverable without re-mining it, and that is a reusable pattern.** A
purpose-built `repair-structured-bodies` workflow re-derived all 38 payloads from the code each rule
already cited — 80 agents, 0 errors, **6.2 minutes**, 3.0M subagent tokens, against 67 minutes to
re-mine. 38/38 repaired, 38/38 validate, 0 abandoned, 0 unresolved, 4 needed the corrective pass
after a referee refuted the first attempt. **Re-derivation beat a mechanical transform** because the
missing fields (`typeRef`, `meter`, `notation`) are not in the saved JSON in any form — a transform
would have had to invent them, while an agent reading the cited lines can read the declared types
off the code. The merged corpus is `knowledge/extracted-rules-round1-bodies-repaired.json`; the
original is byte-for-byte untouched, per the runbook's rule about the one irreplaceable artifact.

**3. `V-VAG-03` was blocking a fifth of the corpus on findings that were all false.** 26 evaluated
ERRORs on 129 requirements. Classified exhaustively: **21 were `that` used as a determiner (*that
short name*) or a relative pronoun (*types that do not allow*), and 5 were `it` as an object or
relative-clause pronoun with its antecedent in the same sentence. Not one was a vague pronoun.** The
check's class in §S1.6 is named *vague pronouns*, but it was implemented as a seed-list regex over
the whole statement, matching those words regardless of part of speech. Fixed as **amendment A4** —
the site is the `[Subject]` slot, firing only when the subject *is* the pronoun, which is the
mechanism `V-SLOT-02` already used and the not-evaluated rule A3 already established. Blocking
findings on the corpus went **37 → 11**. **Two things worth not re-deriving:** SPEC-1 does *not*
scope this check — the "as a bare subject" wording lives in NOTATION, the prompt, so the validator
was faithful to the spec and this needed an amendment rather than a bug fix — and the amendment's
declared cost is that a genuinely vague pronoun *outside* `[Subject]` stops being flagged, with the
old pinning example kept as a test of the narrower site.

**4. The scoped two-round run validated all three prompt fixes, quantitatively.** Bodies valid on
first emission went **2/40 (5%) → 43/49 (88%)**. Restoring `priority`'s deleted definition moved P0
from **44/133 (33%) → 17/186 (9.1%)**, past the ~13% of the reference corpus — the miner had been
assigning a field whose criterion was deleted along with the schema descriptions. `modality:
'expectation'` was produced for the first time (2 rules) and `D-CONST` exercised for the first time
(4 rules), so **all ten SPEC-1 patterns and both halves of the modality enum now have live output**.
`suspectedDefect`, also undescribed until the fix, came back on 30 rules.

**5. Two new defects the run found, both now fixed.** Decision-table entries: NOTATION never said
they are strings, and **6 of 18 tables** were refused for a bare `true`/`false` or `0` — the rule
now names all three wrong shapes (number, boolean, null). And **multi-*file* citations**: 30
citations on 29 of 186 rules (16%) wrote two files in one `source` (`A.java:96-118, B.java:44-51`).
**This is subtler than the multi-*range* defect it resembles:** `rpartition(":")` takes the *last*
colon, which belongs to the second file's range, so the path became the whole comma-joined string
and the stored line numbers belonged to a **different file than the stored path named** — zero
whole-file sentinels, strict mode raised on none of the 30, and the first (primary) range was
discarded outright. A third of the cases were the *same* file twice with the path repeated, which is
semantics the system already intended to support. `parse_citation` now splits a citation list, but
**only when every comma-separated piece is well formed**, so the all-or-nothing rule stays at the
entry grain. Regression risk was measured, not assumed: **0** of round 1's 9 comma-bearing citations
are re-interpreted.

**6. `modulePattern` is a prose hint, not a filter — this changes how to estimate a four-round run.**
The scoped run named one package and the agents cited `ple-model` (15 citations), `ple-web` (4) and
`ple-persistence` (5) anyway. It cost **246 agents, 73 minutes, 6.58M subagent tokens** — more
agents than round 1's unscoped 238. **Scoping bounds what agents are told to prioritize, not what
the run costs.** Do not price a four-round run by assuming a narrow `modulePattern` makes it
cheaper.

**7. Two ingest-log numbers disagree, by design but not by intent.** The anchor-resolution breakdown
is tallied pre-dedup and printed directly under the post-dedup citation count, so `file=2,
symbol=140` (sum 142, *seen*) sits beneath `142 seen, 138 inserted` while the stored table holds
2 + 136. Filed as **entry 12** of `pending/deferred-small-items.md` rather than fixed mid-run.

### What Step 10 Phase 2 discovered (2026-09-08)

- **`RULES_SCHEMA` was too large for the safety classifier, so NO live extraction had been possible
  since 2026-09-02.** Every mining agent failed at spawn with `blocked by safety classifier: output
  schema too large to classify safely`. The schema was **15,242 bytes** of JSON. This is the single
  most consequential thing Step 10 has found, and it is exactly the class of defect the step exists
  to find: the notation rewrite shipped with a green unit suite, nine review rounds behind it, and a
  schema no agent would ever accept. **A green suite is not evidence that the pipeline runs** — the
  suite never spawns an agent.
  The failure is silent from inside the workflow. `journal.jsonl` records only
  `{"type":"failed","agentId":""}` with no reason and no transcript; the reason appears **only** in
  the Workflow completion notification's `<failures>` block. A run that is stopped early therefore
  reports nothing at all, which is how the first attempt looked like a mystery. **Read the
  completion notification, not the journal, when a workflow agent fails.**

- **The budget is ~4 KB and it was measured, not guessed.** A synthetic 4,000-byte output schema
  spawns; a 6,000-byte one is blocked. Seven sizes were probed (2K–14K) and the boundary sits in
  (4000, 6000]. For comparison, the schemas that always worked: `VERDICT_SCHEMA` 496,
  `P0_SCHEMA` 340, `DTO_SCHEMA` 543, `COVERAGE_SCHEMA` 699 — so the referee and the P0 panel were
  never at risk, and only the mining call was.
  **Three hypotheses were wrong before the right one, and are recorded so nobody re-tests them**:
  it is not the `business-rules-extractor` agent type (spawns fine with a small schema), not
  `type: ['string','null']` with `null` in an `enum`, and not `oneOf` on a nested object. All three
  were probed directly and all three pass. It is size alone. A fourth non-cause: the mining prompt
  is only ~3 KB and a probe with the real prompt and a small schema succeeded.

- **73% of the schema was prose, so the fix cost nothing machine-checkable.** 11,169 bytes across
  43 `description` fields carried the `ruleClass` decision procedure, the ten sentence templates and
  the hard-rules list. Moving them into the `NOTATION` prompt fragment (1,870 → 10,231 chars) took
  `RULES_SCHEMA` to **2,239 bytes**, a 44% margin under the largest size proven to spawn, while
  **retaining all 22 rule properties, all 13 required fields and all 7 enums**. `structuredBody`
  additionally drops its four-way `oneOf` and is now a permissive object, on the ground that
  `gr_body_schemas.validate_structured_body` is already this plan's designated single authority on
  those four payloads — the branch was duplicate enforcement, and the Python validator can *reject*
  where a JSON Schema branch could only fail to constrain. The four `BODY_*` constants were deleted
  rather than left unreferenced, and their field lists now appear in `NOTATION`.
  **Guidance delivered through the prompt works as well as guidance in the schema**, which is the
  finding that makes the fix safe rather than merely small: the verification round produced
  `implementationNotes` on 133/133 rules and **zero null `ruleClass`**, both of which the schema
  descriptions had been carrying the instructions for.

- **The verification round: 238 agents, 0 errors, 133 rules, 0 referee rejections.** 67 minutes,
  6.98M subagent tokens, `maxRounds: 1`. `behavioral` 97 / `definitional` 36; P0 44, P1 78, P2 11;
  confidence High 103 / Medium 30, 34 carrying an `smeQuestion`; categories Validation 70, Policy
  26, Lifecycle 21, Calculation 16. Nine of the ten SPEC-1 patterns are exercised (only `D-CONST` is
  absent) and **`pattern` is null on no rule at all** — the abstention path the schema description
  used to argue for was never needed. 62 data objects, **0 injection flags**.
  Two facts worth carrying into Milestone 1.5 rather than rediscovering. **Every rule came back
  `modality: 'requirement'` — zero `expectation`**, so a modality split in the corpus is not
  evidence of anything yet. And **40 of 133 rules carry a `structuredBody`** — 24 `decision_table`,
  7 `formula`, 7 `invariant`, 2 `state_transition` — so `MEAS-2` and `MEAS-3` have real data from
  round 1 alone, and the DMN verdict this plan reserves judgement on can actually be reached.

- **The chunk-level coverage metric works, and the widened denominator is what it counts.**
  `Round 1 coverage: 179/15398 chunks claimed (1.2%); 15219 uncovered chunks remain`. Two things had
  to be true for that line to exist: `repoRoot` must be passed (it is not optional here — without it
  `legacyDir` resolves to a `legacy/<system>` path that does not exist from this repository's root),
  and the coverage agent's command must be reachable, which required pointing it at the venv binary
  because the `PATH` shim is broken. Left alone, the agent takes its documented `skipped` branch and
  `not_accounted_for` lands NULL, unrecoverable without re-running extraction. **1.2% after one
  round is the expected shape, not a defect** — it is one round of three lenses against 15,398
  chunks, and the metric exists to target later rounds.

- **The citation base is unpinned in the workflow, and CODE-relative is the form that works.**
  Nothing in `extract-rules.js` tells the mining agents what their "repo-relative" citation is
  relative to, and three consumers disagree: the referee receives a bare `path:line` with no base,
  the coverage agent needs it relative to `repoRoot`, and `requirements ingest --repo-root <CODE>`
  needs it relative to `CODE`. Measured directly against `coverage`: CODE-relative citations claimed
  115 chunks from two files where the session-cwd-relative form claimed 31 — partial suffix
  tolerance, so a wrong base degrades quietly rather than failing. **In the event the agents emitted
  CODE-relative paths unprompted**, and all 44 distinct cited paths exist on disk. That is luck
  worth converting into a guarantee before Milestone 2 adds four more producers.

- **9 of 133 citations (6.8%) are multi-range and `parse_citation` mis-parses them without
  raising.** `LesstatusHistory.java:24-26,62-70` returns
  `('...LesstatusHistory.java:24-26,62-70', 1, 2147483647)` — a whole-file citation whose *path*
  contains the range text — in **both** strict and non-strict mode. The path does not exist, so
  `resolve_anchor` fails its existence check, the row stores `anchor_resolution = 'unresolved'`, and
  the `dedupe_key` falls from tier 1 to tier 2/3. Ingest exits zero. This is the failure mode
  `parse_citation`'s own docstring predicts, arrived at by a cause the docstring did not anticipate:
  it reasons about prose landing in `source`, not about a *valid* citation naming two ranges.
  Recorded as entry 11 of `pending/deferred-small-items.md` with both candidate fixes.

  **Fixed 2026-09-08, before any ingest** (entry 11 shipped and was removed). `parse_citation`
  accepts a comma-separated range list and returns one triple per range on the same path; the
  return contract did not change, and it stays the single parser, so the coverage denominator and
  ingest's anchor set moved together by construction. Re-parsing the saved round-1 JSON leaves
  **0 whole-file triples across 133 rules**. **The load-bearing consequence above has therefore
  lapsed and `requirements stats` was deliberately left alone**: the multi-range cause of
  `unresolved` no longer exists, so the label is back to covering the one pair of faults
  `parse_citation`'s docstring already documents as sharing it by design (prose in `source`, and an
  extraction taken against a different checkout). Splitting the label would now be a change with no
  measured fault behind it — which is the entry bar for `pending/deferred-small-items.md`, so no
  successor entry was filed. **One consequence to expect rather than re-derive:** coverage numbers
  on any corpus with multi-range citations rise, so a pre-fix coverage figure is not comparable
  with a post-fix one.

### What Step 10 Phases 0–1 discovered (2026-09-08)

- **The rebuilt index has FEWER symbols than the index it replaced, while indexing 275 more
  files, and that is correct.** `symbols` went 16,272 (2026-07-23, old globs) → **16,268**, a net
  −4, and the gap plan's own trial table predicts 16,303. Anyone comparing headline numbers will
  read this as a regression. It is not, and the arithmetic closes exactly, so nobody should
  re-derive it: the trial figure of 1,537 files predates both the `ThirdPartyClassifier` and the
  extension-scoped exclusions, and **1,537 − 13 − 20 = 1,504**. The 13 are provenance drops (11
  vendor `.tld` and 2 jQuery `.css`); the 20 are the `first_party_excluded` tier. Several of those
  33 files are `.xml`, which the framework-aware `xml_extractor` *does* produce symbols from — 35
  symbols' worth (16,303 − 16,268). That is what puts the total marginally below July's, and it is
  the right sign: the widening's own symbol contribution is only +21, all `.xml`, so removing
  symbol-bearing `.xml` outweighs it. **Do not attribute the −4 to any single file** — today's
  control run measured 16,282 against July's 16,272, so ~10 symbols of unrelated extractor drift
  already sit between the two, and this run did not separate the two effects.
  `chunks` and the 0-symbol counts move with the same 33 files: 15,534 → 15,398 and 331 → 306.
  Evidence: the rebuild's own summary, plus a per-extension join of `repo_files` against `symbols`
  and `chunks`. Verified directly: `applicationContext-test.xml`, `spring.tld` and
  `gradle-wrapper.properties` are absent from `repo_files`, while `naesb.tld`, `nngauthz.tld` and
  `application-prod1.properties` are present — each one exactly as its tier requires.

- **The gap plan's disagreement census counts glob *matches*, not *drops*, and so reads 2 files
  high.** Its `Surprises` entry gives "13 `vendored_globs` (11 `.tld` + 2 jquery `.css`), 2
  `declared_identity` (the xmlcatalog pair), 20 `first_party_excluded`", which sums to 35 — but
  only **33** files actually leave the index. The two extra are `naesb.tld` and `nngauthz.tld`:
  `ple-web/src/main/webapp/WEB-INF/tld/**` matches all 11 files in that directory, and the
  `own_identities: ["nngco.com"]` rule then **rescues** the client pair, so 9 of the 11 drop, not
  11. Measured: `WEB-INF/tld/` holds 11 `.tld` and `ple-arch-properties/xmlcatalog/` holds 2, of
  the 13 in the tree; `discover_source_files` returns exactly the client 2. This is that plan's
  Q27 rescue working, described from the other side — no defect in the code, only a census line
  that cannot be added up.

- **Opening the knowledge store during `tag-domains` was enough to create all eleven GR tables
  plus `gr_fts`, with no version bump.** `knowledge.sqlite` went from four tables to twenty-one
  while `user_version` stayed at **1**, and `gr`/`gr_run` are empty. Step 3 said a table addition
  is free because `migrate()` runs from `__init__` on every open; this is the first time that has
  been observed on a real store rather than a fixture. The corollary is the one Step 3 already
  states and this run does not weaken: the first GR *column* addition is what will need a
  migration entry.

- **`/modernize-preflight` re-run against a static tree reproduced all five checks to the digit,
  which is what makes the deviation cheap.** 995 Java classes, 534 `com.nng.*` imports, 0 missing
  internal source, the same five `javac` classpath errors, identical tool versions. The only
  number that moved was `scc`'s code-line total, 168,026 → 168,035, and that is the earlier
  report's hand-rolled "Other" grouping rather than a source change. So the argument for reusing
  `ASSESSMENT.md` and `topology.json` is now evidenced rather than assumed: nothing about this
  unit's environment has drifted since 2026-08-03.

- **The `.jsp` layer indexed exactly as the accepted-substrate decision predicted: 178 files, 213
  chunks, 0 symbols.** `.properties` 42 files / 51 chunks / 0 symbols, `.vm` 35/35/0, `.css`
  6/29/0, `.ent` 3/6/0, `.xmi` 2/2/0, `.tld` 2/2/0. All 21 new-file symbols are `.xml`'s. Nothing
  here needs a JSP extractor to proceed and writing one remains deferred entry 9.

### What nine review rounds established, kept here because it is still live

The per-finding record of those rounds — `PR-01` through `PR-125`, all closed — has moved to
the companion archive `reqs-to-data-store-additional-info.md`. Seven things from it are *not* history
and stay here, because they change what you should do next rather than explaining what was already
done. **The last of the seven is the instruction to stop reviewing and start building**, and it is
the one to act on before any of the others.

**One recurring defect class, seven instances, and it will recur again: a value that is absent, capped
or unmeasured must never share an encoding with one that is real.** It appeared as the empty-string
`dedupe_key` part, the NULL `gr_finding.span` and `gr_dataflow.column`, an unmeasured
`not_accounted_for` stored as zero, an unresolved `anchor_key` collapsing to `''`, a coverage list
truncated to forty entries and then counted as a total, a missing element inside the tier-2
discriminator, and — the ninth round's — the reserved `excluded` domain becoming eligible to be a
business subject, which is the one instance where the bad value reads as a *plausible* real one
rather than as an obvious zero or blank. Every time, the failure was silent and the thing it corrupted looked like it was
working. **Two further instances arrived in Wave C** and are recorded under *What Wave C discovered* below; the tenth widens the rule from columns and encodings to **signatures**. **Check any new field against it before adding it**, and note the fourth-round refinement:
it applies to *derived* values too, not only stored columns — a count read off the wrong field of an
entirely correct payload fails exactly the way a NULL stored as zero does.

**An eighth instance was measured on 2026-09-01 and it is the first one found in a dependency
rather than in this plan's own design: chromadb 1.5.9 does not reject a `None` metadata value, it
*silently drops the key*.** Upserting `{"gr_id": "A", "subject": None}` and `{"gr_id": "B"}`
produces two rows whose metadata is byte-identical, so "this requirement has no derivable
subject" and "nobody wrote a subject" are the same fact in the collection. It matters to Step 5,
where `subject` and `category` are both nullable on `gr` and both are collection metadata, and it
is now recorded at `ChromaVectorStore.upsert_chunks`, whose comment asserted the opposite
("Chroma rejects None") and had done since before this plan. The coercion that comment sits above
was always right; its stated reason was not, which is a reminder that **a defensive line and a
correct explanation of it are two separate things to check.** The rule extends accordingly: the
encoding a value takes on the way *out* of this system is as much a place for this defect as a
column.

**One structural theme runs through the fifth round and is worth carrying forward as a check of its
own: a value that is hashed must have a *specified* source, and a mapping that feeds a hash is as
load-bearing as the hash's own formula.** Four rounds verified the `anchor_key` and `dedupe_key`
formulas exhaustively and none of them asked where the *inputs* came from. Three of the fifth
round's five blockers were exactly that — `pattern` derived by a procedure that did not exist
(`PR-79`), `language` at the file grain with no defined value (`PR-82`), and `entity_class` derived
from a `kind` mapping left to the implementer over a domain the client's own code authors
(`PR-83`). **When you add or change anything that feeds a key, ask not "is the formula right" but
"is every input's source written down, total, and immune to churn."**

**One theme belongs to the seventh round and generalizes three findings the fifth and sixth rounds
closed one at a time: a column can be classified, counted and partitioned correctly and still have
no writer.** `PR-81` found `owner`, `rule_class` and `pattern` in that state; `PR-99` found
`implementation_notes` in it one round later, for a different reason — its writer was a re-authoring
step that `PR-79` deleted, leaving the column behind. The four-way partition does not catch this,
correctly, because it asserts *membership* and reachability is a different question. **So the check
is its own: for every column, name the code path that writes it, and if the answer is a step that
another finding removed, the column went stale with it.** The paired assertion is now in
`Validation and Acceptance`. Watch for it wherever this plan deletes a step rather than a field.

**One theme belongs to the eighth round and is the reason seven rounds of consistency-checking did
not find its findings: a rule can be internally consistent, correctly cross-referenced, and still
not executable — and the way to notice is to run it against the specification's own worked
examples rather than against the rest of the plan.** All seven of that round's findings were of
that shape. The keyword-anchored slot split was coherent, cited §S1.4 correctly, and fired two
`ERROR`s on the statement §S1.10 marks conformant. The `entity_class` default rule read as a
disciplined honest-default and silently unclassified twenty-nine of the fifty-two entries whose
classification the plan had just finished making load-bearing. `gr_scenario` was described
completely and given no primary key. The reachability assertion the seventh round added was itself
always false. **So the check is: for every rule this plan states, find the concrete input it
governs and walk it through by hand.** §S1.10's ten examples, `extractors.json`'s fifty-two
entries, and one re-ingest of one saved JSON are the three places that pay for themselves. Two
consequences follow for the do-not-re-verify list below and are worth stating plainly: a
*measurement* being confirmed says nothing about whether the thing measured is *complete* — the
seventh round correctly re-measured `52 entries / 36 distinct kinds` while the classification over
them had a twenty-nine-entry hole — and an assertion added by a review round is not thereby
verified, since `PR-112` closed one that `PR-99`'s own round had introduced.

**One theme belongs to the ninth round and sharpens the eighth's into something you can apply
mechanically: the eighth round asked whether a rule could be built, and the ninth found that the
rules which fail that test cluster at *interfaces* — the point where a rule stated in one place has
to be reached from another.** All six of its blockers were of that shape, and none was a wrong rule.
A column asserted by four call sites and absent from the schema; a `--note` and an import marker
with nowhere to land; a constant typed so the assertion mandated against it cannot pass; a value
whose only stated producer the plan forbids to exist; a check specified as a database lookup inside
a signature holding no database; a header the schema requires and the exporter forbids. **So the
check is: for every value this plan names, walk from where it is written to where it is read, and
confirm the signature, the column and the constant on that path can actually carry it.** The four
questions that found all six were — does this column exist in the forty-two; does this constant's
declared type admit the assertion made against it; can the function that must produce this value
reach what it needs from its own parameters; and do the two rules governing this file agree. Note
what this adds to the eighth round's advice rather than replacing: walking §S1.10's examples by hand
catches a wrong rule, and walking a value from writer to reader catches a rule that is right and
unreachable.

**One theme belongs to the sixth round and is the reason that round existed at all: a rule this plan
states in several places gets corrected in all but one of them, and the surviving copy is an
instruction to build the wrong thing.** All four of the sixth round's blocking findings were that
shape, and all four had their stale copy in `Validation and Acceptance` — the four-way ownership
partition still asserted as three sets, `rederive-subjects` still told to re-template statements it
no longer touches, a duplicated Milestone 0 criterion under the wrong command name, and a field count
of ten where the set holds nine. The fix applied is structural as well as textual: **`Validation and
Acceptance` now states an observable plus a pointer and does not restate a rule it tests.** Hold that
line. When you correct a rule, grep for every place this plan names it before you consider the
correction done — the `Decision Log`, the owning Step, `Progress`, `Concrete Steps` and
`Validation and Acceptance` are five places one rule can live.

**Do not re-verify the following. Five rounds have checked it against the source, the fourth and
fifth independently, and all of it held; the sixth and seventh rounds re-checked the parts their own
findings touched and they held too.** The seventh round additionally re-measured
`profiles/extractors.json` from disk and confirms the `52 entries / 36 distinct kinds` figure, the
per-profile `9/7/3/7/10/8/8` split, `create_table`'s presence and `foreign_key`'s absence; it
confirms the column list partitions exactly with no column in two sets and
none in none; it confirms all fourteen `requirements` commands are named in Step 8; and it confirms
both Milestone 1.5 baseline files are on disk. The eighth round re-confirmed the `52 / 36` figure, the partition and both baseline files a second time, so none of it needs a tenth look. **One figure on this list has since moved and must be read as current rather than as confirmed history:** the ninth round added `reviewed_at` and `review_note`, so `gr` is **forty-two** columns partitioning `14/3/9/16`, not forty partitioning `14/3/9/14`. The partition still holds — it was re-derived, not merely re-counted — but quote the new numbers — but note the distinction that round drew, because it is the one thing on this list that misled: **these are confirmations that a set was counted correctly, never that the plan says something about every member of it.** The `52 / 36` figure was right in the seventh round and the classification over those 52 entries had a twenty-nine-entry hole. Spending another pass here buys nothing: ~~every code line
reference in this plan~~ (**struck 2026-09-01 — every one has drifted; see the correction table
immediately below this list**); the eight `index.sqlite` tables and the four *pre-Step-3* `knowledge.sqlite` tables (that store now holds fifteen — the four domain tables plus Step 3's eleven; read the count as history, not as current); the
twelve Layer-0 fact predicates; SPEC-1's twenty-eight validator checks and their `2/7/3/9/1/3/3`
breakdown (unchanged by amendments A1 and A3, which rescoped one check's test and two checks' sites and altered no count or
severity); the ten-value `pattern` enum and its §S1.4 templates; the six `enforcement_level` values;
the `chromadb==1.5.9` pin; ~~the fifteen flat `@app.command` registrations~~ (**now sixteen** —
Step 2 added `backfill-hashes`) and ~~the absence of any
`add_typer`~~ (**struck 2026-09-02 — Step 8 added the first one, for the `requirements` group**); the `symbols` DDL and its ~~three~~ **four** indexes (`store.py:241-266`, **now
`:505-546`** — Step 2 added the column set and `ix_symbols_anchor_key`); `index --reset`'s wipe
path (`indexer.py:184-200`); `chroma_dir` resolution (`cli.py:350`, `indexer.py:188`);
`ChromaVectorStore`'s embedder-and-dimension contract; `RULES_SCHEMA` and `DTO_SCHEMA` in
`extract-rules.js`; the workflow's return object and the loop's three termination paths;
`_parse_claimed_citations` at `cli.py:1532`; `SQLiteStore.__init__` at `store.py:157`;
`.gitignore:82-83`, `:88-89` and `:92`; every fixture and corpus path named here; and every
Milestone 1.5 figure — 55 P0 `###` cards in lines 25–709, 768 raw pipe rows over four sub-tables
summing to 760, the Summary block's 441/215/101/58 differing from the catalog by exactly those 55
rules, 470 `####` cards in BASE-ENH, and both baseline files present on disk.

### ⚠️ Every code line reference in this plan is now stale (measured 2026-09-01, after Step 4)

**This amends the do-not-re-verify list directly above, and it is the one item on it that has
gone wrong.** That list says "every code line reference in this plan" was confirmed against the
source. It was — but the confirmation predates Milestone 0 and Milestone 1 Steps 1–4, which added
484 lines to `store.py` (1,490 → 1,974), 273 to `cli.py` (1,620 → 1,893) and the whole GR
half of `knowledge_store.py` (1,010 → 1,135). **Nothing moved except line numbers** — every
construct the plan points at still exists and still does what the plan says — so the fix is a
lookup table rather than a re-read. Grep for the construct, do not trust the number.

| The plan says | It is actually at | The construct |
|---|---|---|
| `store.py:157` | `store.py:303` | `SQLiteStore.__init__` |
| `store.py:166-171` | `store.py:312` | `_connect`, which creates the file on first query |
| `store.py:173` | `store.py:430` | `SQLiteStore.migrate()` |
| `store.py:216` | `store.py:471` | `chunks` DDL (`symbol_id` is a plain column) |
| `store.py:231-238` | **`store.py:492-501`** | the `chunk_fts` FTS5 DDL — **Step 5's house pattern** |
| `store.py:241-266` | `store.py:505-546` | `symbols` DDL and its indexes — **four now, not the three the do-not-re-verify list names**: Step 2 added `ix_symbols_anchor_key` alongside `_name`, `_qualified_name` and `_language` |
| `store.py:278` | `store.py:551` | `symbol_refs` DDL |
| `store.py:286` | `store.py:312` | `_connect`, where `CR-01`/`CR-10`/`CR-11` landed |
| `store.py:309`, `:310` | `store.py:578` | `graph_edges` DDL and its two symbol FKs |
| `store.py:359` | `store.py:626` | `symbol_facts` DDL |
| `store.py:400`, `:501-505`, `:1202` | **`store.py:697`, `:798-805`, `:1551`** | the three `chunk_fts` delete-then-insert sites — **Step 5's maintenance idiom** |
| `store.py:1064-1065` | `store.py:1414` | `coverage`'s "returns every uncovered chunk so counts stay exact" |
| `store.py:1810` | `store.py:1858` / `:1884` | `count_symbols_missing_content_hash` / `symbols_missing_content_hash` |
| `cli.py:130` | **`cli.py:167`** | `@app.command("backfill-vectors")` — the model for `reindex-vectors`. Was `:145` after Step 4; Step 8's `add_typer` block moved it again. Every other appearance of `cli.py:130` in this plan (three of them, in Steps 2, 5 and 8) means this line. |
| `cli.py:350` | `config.py:114` + `indexer.py:383` | `chroma_dir` resolution; see the trap below, it is in two places and they disagree |
| `cli.py:1095` | **`cli.py:1317`** | `domains_cmd`, the canonical cross-database join-in-Python pattern |
| `cli.py:1471` | `cli.py:1747` | `listed = result.uncovered_chunks[: max(limit, 0)]` |
| `cli.py:1532` | `cli.py:1808` | `_parse_claimed_citations` |
| `config.py:101-105` | `config.py:101` / `:105` | `index_dir` / `knowledge_dir` manifest defaults (unmoved) |
| `config.py:108` | `config.py:114` | `collection_name` default `code_chunks` |
| `config.py:269-302` | `config.py:383` / `:449` | `resolve_index_dir` / `resolve_knowledge_dir` (plus `resolve_analysis_dir` at `:346` and `apply_path_overrides` at `:302`, both added by Milestone 0) |
| `indexer.py:184-200` | `indexer.py:301-344` | `index --reset`'s guard |
| `indexer.py:188`, `:199-200` | **`indexer.py:383`, `:394-395`** | `chroma_path = index_dir / chroma_dir`, then `shutil.rmtree(chroma_path, ignore_errors=True)` — **the reason Step 5's collection must not live under the index directory** |
| `extractors.py:1112-1115` | `extractors.py:1179` (and `:1734`, `:2705`) | the line-bearing `sym_id` construction — **there are three sites, not one** |
| `knowledge_store.py:127-129` | `domain_tagger.py:60` (`RESERVED_EXCLUDED`), `:157` | where `domain = 'excluded'` is decided |
| fifteen `@app.command` registrations | **sixteen** | Step 2 added `backfill-hashes`. Counted, not estimated: `grep -c "^@app.command" cli.py` is 16 and `grep -c add_typer` is 0, so Step 8's sub-app is still a new pattern with no precedent to copy |
| `ChromaVectorStore(index_dir=...)` | `ChromaVectorStore(base_dir=...)` | Step 5's rename. All **sixteen** construction sites pass it by keyword — five in `src/` (`cli.py` twice, `domain_tagger.py`, `indexer.py` twice) and eleven in `tests/`. The parameter's name is the only thing that changed; see `pending/deferred-small-items.md` entry 2 |
| `store.py:231-238` (`chunk_fts`) | plus `knowledge_store.py`'s `gr_fts` | Step 5 added the second FTS5 table, in the same standalone shape and with the same delete-then-insert maintenance. Its single writer is `KnowledgeStore.replace_gr_fts`, called only from `gr_refresh.refresh_gr_derived_sql` |

**The lesson to carry rather than the table:** a line number is a measurement with a shelf life,
and this plan's own rule — an assertion computed from the thing it describes cannot drift from it
— applies to prose references too. When you cite code from here on, cite the *symbol name* and
let the reader grep; where a line number is genuinely needed, say what it was measured against.

**Four earlier closures are superseded, and reinstating any of their wording would reintroduce the
defect.** (The fourth is the eighth round's: `PR-107` replaces `PR-28`'s *mechanism* — the
keyword-anchored two-part split — while leaving everything else in that entry standing, because the
reasons it gives for rejecting stored slots and a five-slot parser are still why the replacement had
to keep the same shape. Treat any further "which side of the rule keyword a token falls on" wording
as a stale copy.) (A fourth pattern appeared in the sixth round and is different in kind: `PR-87` and `PR-91`
did not supersede anything, they *finished* `PR-79`'s closure, which had corrected a rule in its
owning Step and left a stale copy standing elsewhere. The seventh round found four more of the same
shape — `PR-99` through `PR-101` and `PR-103` are all `PR-79` residue, and `PR-99` is the one worth
knowing about, because `PR-79` deleted a *step* rather than a rule and `implementation_notes` was
that step's output, left in the schema with nothing to fill it. **`PR-79` is now finished; treat any
further "the extractor derives this at ingest" or "the scenario is re-authored" wording as a stale
copy rather than as a rule.**) `PR-22` closed the "a 100% data-flow inference rate reads as a quality signal" concern by
requiring the rate be stated everywhere; `PR-48` replaced that outright, because with no writer at
all there are no entries to take a rate over, so `stats` prints both reasons in words and no
percentage. `PR-01` closed the seven-unsourced-columns finding by capping the extractor extension at
three fields and deriving `pattern` and `statement` mechanically at ingest; `PR-79` replaced that
outright, because the derivation was unbuildable — the extractor now authors the notation and the
cap is gone. `PR-70` made field ownership a three-way partition; `PR-81` replaced it with a four-way
one, because the three shadowed fields are written by *both* parties and cannot sit in a disjoint
three-set scheme. The archive keeps all six rows standing, the earlier ones unedited, so each
sequence is legible.

**Before proposing a change to anything in this plan, check the archive for a row about it.** Many of
the 125 exist specifically to stop a tempting simplification being reintroduced — a shorter key, a
merged column, a dropped branch, a two-set assertion — and each records why the simpler thing fails.
That is the one situation in which reading the archive is not optional.

**Nine rounds is enough. Do not run a tenth review of the same kind — build Milestone 0 instead.**
This is a live instruction rather than history, which is why it is here and not only in the archive,
and it was settled by measuring the review record rather than by anyone's impression of it. The
numbers are in the archive under `What the nine rounds cost and bought, measured`; three of them
carry the decision.

**The reviews stopped exploring the design at round 4.** Rounds 1–3 produced 63 findings of which one
referred to earlier work; rounds 5–9 produced 47 of which 24 did. Since round 5 a little over half of
each round has been rework of ground the earlier rounds opened, and three artifacts account for most
of it — field ownership (`PR-45` → `PR-70` → `PR-81` → `PR-86`/`PR-92` → `PR-99` → `PR-112` →
`PR-119`, seven rounds and still being corrected in the ninth), the slot split, and `entity_class`.
**In every one of those the requirement held still and only its written expression was wrong**, which
is the important half: exactly one finding in 125 changed what the system does (`PR-79`), and no
load-bearing decision has been reopened once. The design is stable. The prose describing it is what
keeps being defective, and prose is not the artifact that fixes that.

**Three rounds running have repaired the previous round's own new assertion** — `PR-70` → `PR-81`,
`PR-99` → `PR-112`, `PR-112` → `PR-119`. Three of the last twenty-seven findings exist only because a
review created them. This is the review process's own failure mode and it follows directly from the
rule R8 added: an assertion added by a review round is not thereby verified. **The fix is to make the
assertions executable, not to write more of them.**

**And the remaining defects have moved to where implementation finds them first.** All six of round
9's blockers were interface-level — a column four call sites assert and the schema lacks, a constant
typed so its own assertion cannot pass, a value whose only stated producer the plan forbids to exist,
a check specified as a database lookup inside a signature holding no database — and every one would
surface in the first hour of writing the step it belongs to, most from a type checker or the first
`pytest` run. The find rate confirms it rather than contradicting it: 25, 18, 20, 15, 7, 13, 8, 7, 12,
with more blockers in the ninth round than the eighth. That is not a plan converging on zero; it is a
plan being read by a simulated implementer, and the real one is cheaper and more accurate.

**So the sequence is Milestone 0, then Step 1, then Step 3's DDL**, and the reason for that order is
not only the Plan of Work's. Milestone 0 has been untouched by five consecutive rounds — longer than
anything else in this document — and depends on none of the three churned artifacts. Step 3's DDL is
the specific thing that ends the churn, because it converts the column list from prose into a table
`PRAGMA table_info` can read: the four-way partition test becomes executable, and the `PR-45` lineage
stops being possible rather than being corrected an eighth time.

**Two things would justify another round, and neither is "read it again".** A *measurement* against
the reference corpora, which is the one kind of finding reading buys and implementation does not —
`PR-79`'s 470-rule statistics, `PR-83`'s collision count and `PR-108`'s 52-entry count were all of
that kind, and `PR-124` is the shape to look for: a defect that ships silently and produces wrong
output rather than failing a build. Or a *specific* suspicion about a step, checked against that
step's own inputs. A general re-read is what has now hit diminishing returns, twice.

### What Waves 0, A and B discovered (2026-09-02)

Seven findings from building Steps 6a, 6, 7 and 9's functions. **None of them came from the test
suite** — every one came from an agent reading the source to build against it, which is the same
lesson the two `CR-` rounds recorded and is now recorded a third time.

**1. The workflow's rule array is `confirmedRules`, not `rules`, and this plan said `rules`.**
Measured against `workflows/extract-rules.js`: the returned object is `{system, rounds,
confirmedRules, rejectedRules, dataObjects, injectionFlags, coverage, stats}`. A field map written
from this plan's prose alone finds no rules at all and **reports a successful ingest of zero** —
green, quiet and empty, which is the worst available shape of failure here. `rounds_run` comes
from `rounds` and `injection_flags` from `injectionFlags`, both camelCase. Ingest now accepts both
spellings so hand-written fixtures keep working. The same reading confirms Step 10's claim that
`round_cap`, `stop_reason` and `new_rules_in_final_round` have **no producer at all** in the
return value.

**2. Neither dedupe key had a producer.** Step 3 created both columns and stated both formulas,
Step 4's gate and Step 5's refresh read them, and Step 6 described merging on them — but nothing
in the shipped code ever computed one. It was invisible because every layer that *reads* a key
existed, so the suite was green with the keys permanently absent. Built in Wave B as `gr_keys.py`.
The lesson generalizes past this plan: **a column with readers, a schema, a `CHECK` and tests can
still have no writer**, and the seventh review round's writer-reachability question is the only
thing that catches it. It caught `owner`, `rule_class` and `pattern` at the column level; nobody
asked it of the keys.

**3. The `gr.state` writer census was evadable, and was already being evaded.** The executable
form of "no producer may write `gr.state` by any other route" was a raw-text regex for
`UPDATE gr SET ... state =`. It missed adjacent string concatenation, `INSERT … ON CONFLICT DO
UPDATE SET` (the merge's own shape), and `REPLACE INTO gr` — and it was already blind to
`gr_export.py`, which writes the column through `f"UPDATE gr SET {set_clause}"` and
`f"INSERT INTO gr ({columns})"`. **A source regex cannot see a runtime-built column list**, and
that is the ordinary way to write a column-mapped update, so every write path Milestone 1 still
had to add would have been invisible too. The census now scans real string literals through `ast`,
skipping docstrings, and flags *any* write against the `gr` table, so every module containing one
must be declared. It paid for itself immediately: Wave B put **all** raw `gr` SQL in
`knowledge_store.py` because the census would otherwise have failed, which turned a layering
convention into an enforced one.

**4. "The six Figure-1 patterns" is seven, and two stale copies outlived the correction.** The
plan already recorded this twice, yet the two places an implementer actually works from — the
`StatementSpans` interface sketch and an eighth-round acceptance criterion — still said six. The
criterion's "six … with `value` populated on the other three" is nine against ten patterns, so a
test written from it fails. `FIGURE1_PATTERNS` has always held seven and asserts `7 + 3 == 10`.
**A correction recorded in two places and not applied in the two that are read is not a
correction**, which is the sixth review round's stale-copy defect recurring after that round
closed.

**5. `gr.modality` is not SPEC-1's modal keyword, and Step 6a's brief conflated them.** The column
is `CHECK (modality IN ('requirement','expectation'))` — Q3i's KAOS pair — and `gr_validator.py`
never reads it: every `V-KW-*` check tests `statement`. So §S1.3's keyword strings belong in the
extractor's `statement` instruction, where the checks actually look, and not in a `modality` enum.
Two fields whose names collide in ordinary English are a place to expect this.

**6. Nothing in this repository pins the vector distance metric.** `ChromaVectorStore` sets
`hnsw:sync_threshold` and `hnsw:batch_size` but **no `hnsw:space`**, so the metric is whatever the
installed chromadb defaults to — L2 on the pinned 1.5.9. It matters because stage two's semantic
candidate threshold is a distance, so moving the pin or setting a space silently changes what the
number means. The failure direction is the quiet one: too tight a threshold raises fewer
candidates, and **stage two returning none is indistinguishable from there being no
near-duplicates to find** — the same indistinguishability `open_gr_collection` guards against for
a reset-destroyed collection, arriving through a different door.

### What Wave C discovered (2026-09-02)

Step 8's two waves are recorded in `Outcomes & Retrospective` → *Milestone 1 Step 8*, including the
four open defects in shipped code and the two acceptance criteria that could not be satisfied as
written. Three findings belong here instead, because they change what a later agent should do rather
than explain what was already built.

**The recurring defect class reached instances nine and ten, and the tenth widens the rule again.**
Nine is `gr_export.ImportResult`, which cannot distinguish "the file agreed with the store" from
"every state change in the file was refused" — inside Step 9's own code, in a plan that has now
found this class ten times. Ten is subtler and is the first instance that is neither a column, a
derived count nor an outbound encoding: **a parameter whose `None` correctly means "absent", which a
reporting layer then had nothing else to print.** `index_sqlite_path=None` is the documented way to
say "no index", so a report rendered from `IngestResult` printed `index: NOT present at None` — and
the resolved path is exactly what the acceptance criterion demands the banner name, because a
mis-resolved path under Milestone 0's layout and a genuinely unindexed repository produce identical
corpora and call for opposite fixes. **So the check now extends to signatures: when a parameter's
`None` means absent, ask what the *reporting* path will print, because the caller's own resolved
value is usually the thing a human needs and the callee cannot know it.**

**An assertion that scans source text must also scan the right *files*, and the census did not.**
`tests/test_gr_state.py`'s `gr.state` writer census globs `src/legacylift_search/*.py` — flat, so it
does not descend into a package. Step 8's `cli_requirements/` sub-package was therefore outside it
from the moment it existed, and any of four command modules could have composed its own
`UPDATE gr SET` invisibly. Wave B's finding 7 established that a census must read literals through
`ast` rather than text; this adds the other half. **A source-scanning assertion has two failure
modes — the wrong matcher and the wrong file set — and four review rounds only ever checked the
first.** A package-scoped scan reusing the census's own helpers now covers it. Expect this wherever
this repository grows its second sub-package.

**The `hash` embedder's dimension comes from the manifest, not from `HashEmbedder`.** It is built at
`manifest.embedding.dimension` = 1024, while `HashEmbedder`'s own default is 64, so a collection
seeded at 64 fails `validate_dimension` against the CLI's embedder — and the test then measures a
dimension mismatch while claiming to measure something else. `EmbeddingConfig.provider` also
defaults to `qwen3`, a real model load, so any test or dry run touching the vector half must pin
`hash` explicitly. Both cost iterations in two separate units of the same wave.

**Five small traps, each of which cost a unit at least one iteration, recorded because none is
guessable from this plan.** They are facts about the shipped code, not defects.

- **`KnowledgeStore.upsert_file_domain` takes five positional arguments**, not the three the
  natural reading suggests: `(relative_path, domain, source, assess_run_id, confidence)`. Two
  separate units reached for the three-argument form. Any test that seeds `file_domains` — which
  is every test of subject derivation — needs all five.
- **`anchor_resolution` is a column on `gr_citation`, not on `gr_citation_anchor`.** The names
  invite the opposite reading: the *anchor* table holds one row per containing or intersecting
  symbol with its `containment`, while how the primary anchor was resolved is a property of the
  citation. Verified in the DDL (`knowledge_store.py:475`, `CHECK (anchor_resolution IN
  ('symbol','file','unresolved'))`).
- **The index and knowledge directories are not siblings.** `resolve_index_dir` puts the index at
  `<analysis>/index/code-search` while the knowledge store is `<analysis>/knowledge`. A test
  asserting the two are siblings, or constructing one from the other by a single `parent`, is
  asserting something false. Assert containment under the analysis directory instead.
- **`gr_export.REASON_COVERAGE_NEVER_MEASURED` contains an em dash** and it reaches CLI output,
  through `IncompleteCorpusError`'s message and the `_incomplete` export header. It is the one
  non-ASCII string that does. Routing it through `typer.echo` rather than `rich` stops rich
  mangling it, but a stdout redirected under a cp1252 locale can still raise `UnicodeEncodeError`.
  The words are mandated by Step 3's two-reasons rule, so this is a note rather than a fix.
- **`gr_citation.provenance` is `('extracted','repaired','human')`** — not `'extractor'`, which is
  what the field map calls the same idea one table over. Recorded once already under Step 5's
  notes; it caught another unit in Wave C, so it is repeated here.

**7. An assertion that greps source *text* trips on prose describing the thing, and it happened
three times in one wave.** The census (finding 3) flagged any file whose docstring merely
contained the phrase, which cost `gr_export.py` its clearest wording — the test made a comment
worse to stay green. Then an assertion that `gr_dataflow.py` performs no division tripped on that
module's own docstring, which names `computed / total` as the thing it avoids. **Both are the
absent-versus-real rule applied to source code**: a description of a construct and the construct
are two different things and must not share an encoding. Both are now `ast` scans. Expect this
wherever a test asserts something about the code rather than about behaviour.

## Decision Log

- Decision: The store is the source of truth; markdown becomes a generated report.
  Rationale: Markdown cannot hold a lifecycle, cannot be queried, and is overwritten on every run, so human review cannot accumulate. Everything else in this plan follows from this.
  Date/Author: 2026-08-19, Darrell Norton with Claude.

- Decision: Model the schema generically with a `kind` discriminator; wire only `/modernize-extract-rules` in Milestone 1, the other four producers in Milestone 2.
  Rationale: Five tools generate requirement-shaped output today with five incompatible identifier schemes. One generic schema avoids five stores, while wiring one producer first keeps Milestone 1 provable.
  Date/Author: 2026-08-19.

- Decision: Nothing is ever migrated from the existing markdown corpora. The store starts empty.
  Rationale: The two existing corpora (470 and 815 rules from a prior engagement) are *reference data* for comparison, never input. Writing a backfill would import unreviewed output as though it were reviewed, destroying the meaning of the lifecycle on day one. Firm commitment, do not re-open, do not build a migration path.
  Date/Author: 2026-08-21.

- Decision: The GR tables live in `knowledge.sqlite`, not `index.sqlite` and not a third database.
  Rationale: `index.sqlite` is derived, gitignored, and deletable by `index --reset`, so a reindex could destroy signed-off human work. `knowledge.sqlite` already survives `--reset` and already holds human/LLM judgment (`file_domains`), so the subject-derivation join is one SQL statement. A third database would add a second cross-database seam for no gain. Note the consequence: the data-flow block's `reads[]`/`writes[]` is a cross-database read either way, because `symbol_facts` lives in `index.sqlite` and the two databases are never `ATTACH`ed.
  Date/Author: 2026-08-24.

- Decision: Full lifecycle from Milestone 1, and re-extraction is a merge with dedupe, never truncate-and-insert.
  Rationale: Two independent arguments. First, durable records with protected human edits are the only thing markdown cannot do, so it is the point of the plan. Second, measurement: on the reference corpus, the only run that reached the web-action and persistence layers (327 files versus 148) got there by merging three scoped runs, and the best single run stopped at its round cap while still finding roughly 28 new rules per round. Truncate-and-insert cannot reach coverage that has already been demonstrated.
  Date/Author: 2026-08-24.

- Decision: Requirements get both SQLite FTS5 full-text search and a *dedicated* vector collection, never mixed into the existing `code_chunks` collection.
  Rationale: FTS5 covers keyword lookup nearly free. A separate vector collection provides semantic dedupe, which the merge needs the moment it exists — "have I seen this rule before?" is a fuzzy question that exact keys cannot answer. Mixing GRs into `code_chunks` would poison code search and force every existing query to carry a filter.
  Date/Author: 2026-08-24.

- Decision: This plan is the home for the fact-graph skill's remaining LLM-inferred-facts role, but it is scoped to **adding** the store, never to **retiring** fact-graph.
  Rationale: Retirement is gated on Milestone 21 of `docs/exec-plans/active/semantic-code-search-graph-index.md`, which is an open evaluation. Building this store is additive and removes nothing, so it may proceed — but any language reading as "fact-graph is replaced by this" would decide that evaluation by fait accompli.
  Date/Author: 2026-08-24.

- Decision: The gitignored database stays authoritative; a committed JSONL export rides alongside; import happens only via an explicit command.
  Rationale: `knowledge.sqlite` is gitignored (`.gitignore:88-89`), so a store of expensive LLM output plus human sign-off would otherwise live on one analyst's laptop. A sorted JSONL export makes requirement changes diffable and reviewable in a pull request, which is where sign-off discussion actually happens. Import must be explicit so a stale checkout cannot silently overwrite approved state. Committing the binary was rejected (merge conflicts, no diff review); accepting local-only was rejected (the accumulated judgment is the differentiator and would be unrecoverable).
  Date/Author: 2026-08-25.

- Decision: This plan builds a real versioned migration mechanism for **both** databases, as Milestone 0, before any GR table exists.
  Rationale: There is no schema `ALTER TABLE` anywhere in `tools/legacylift_search/src/`, no `PRAGMA user_version`, and `SCHEMA_VERSION = "1"` is written at `indexer.py:666` but never compared. Adding a table is free; adding a *column* today requires `index --reset`, which deletes the database. For a durable store that is data loss. Scoping the mechanism to one database would leave the other as the exception that reintroduces the problem.
  Date/Author: 2026-08-25.

- Decision: Zero fact-graph consumers re-point at the GR store in this plan.
  Rationale: All thirteen consumer skills already have working non-fact-graph fallbacks, so re-pointing buys quality rather than capability. Re-pointing the business-rule query specifically would move fact-graph's only non-redundant contribution into the new store while the evaluation that is supposed to decide that is still open. The consequence — two stores holding business rules over the same code for a period — is accepted deliberately, and its exit is that evaluation.
  Date/Author: 2026-08-25.

- Decision: `anchor_key` is **additive**. This plan does not re-key `symbols.id`.
  Rationale: The stable-identity problem has two halves. This plan closes the first by adding a position-independent key as a computed column, which is what downstream design work asked for. The second half — that `symbols.id` itself embeds a start line, and five surfaces key off it — is Layer-0 repair work that benefits every consumer, so it is filed as a declared dependency rather than absorbed here. It does not gate anything in this plan, because citations anchor on path-plus-line-range with `anchor_key` as an advisory soft link. Do not write anywhere that this plan "fixes Layer-0 stable IDs."
  Date/Author: 2026-08-25.

- Decision: `dedupe_key` is recomputed only on extractor-owned writes, never on a human edit.
  Rationale: A deliberate refinement of `NORMATIVE SPEC-3` §S3.3's table cell, which says "recomputed on every write." Two of the key's inputs — `rule_class` and `pattern` — are nullable while a record is `draft`, so a literal reading re-keys the row the moment a reviewer fills them in, and the next extraction run then fails to match it. That is exactly the failure the exclusion of `statement` from the key exists to prevent, arriving through a different door. Recording it here so it reads as a decision rather than as drift from SPEC-3.
  Date/Author: 2026-08-25.

- Decision: every part of the `dedupe_key` hash input is a string, and a missing part is the empty string.
  Rationale: The *second* deliberate refinement of `NORMATIVE SPEC-3`. §S3.3.1's tier-3 discriminator reads `NULL`, but `NULL` is not an encodable value inside a hash input — it is an ambiguity. Two correct implementations that spell a missing discriminator differently produce different keys for the same rule, and the merge then silently stops working with no error raised anywhere. The same reasoning covers a NULL `rule_class` on a `draft` row. Recorded here, alongside the one below and the tier-2 element rule further down, so all three of the plan's departures from SPEC-3 are declared rather than reading as drift. Also declared with it: the sorted anchor list is joined with the same U+001F separator as the four top-level parts, so a two-anchor rule cannot collide with a one-anchor rule whose inputs happen to concatenate to the same bytes.
  Date/Author: 2026-08-25.

- Decision: the human review surface is a *minimal* CLI write path in Milestone 1 and a real review experience in Milestone 4; no review UI is built in Milestone 1.
  Rationale: Milestone 1's acceptance turns on a human edit surviving re-extraction, so *some* write path must exist inside Milestone 1 or the headline test cannot be performed and `stats`' SME fill rates are structurally zero. But a review *experience* — queues, diffs, side-by-side `as_built` versus `statement`, bulk triage — is a separate product with its own plan. So Milestone 1 ships one deliberately unpolished command (`requirements set-field`) sufficient to prove the invariants, and Milestone 4 owns the experience. See `docs/exec-plans/pending/reqs-review-ui.md`.
  Date/Author: 2026-08-25.

- Decision: **SUPERSEDED by `PR-79`, 2026-08-26 — do not implement this entry.** The extractor authors the SPEC-1 notation directly; see the entry below. The original text is left standing unedited, per this plan's convention for a replaced closure, because the *reasoning* it records about prompt surface and Milestone 1.5 is still the reason the replacement had to be argued rather than assumed. Original: the extractor gains exactly three fields (`ruleClass`, `modality`, `assumptions`); everything else missing is derived mechanically at ingest, with no language model in the CLI.
  Rationale: `PR-01`. Those three genuinely require reading the source, and the extraction agents are the only actors that do — `rule_class` in particular has a deterministic procedure in SPEC-1 §S1.2 that operates on the cited code. Inferring them at extraction time is nearly free and is PRINCIPLE-1 applied literally: infer once, at the point of maximum evidence. The alternatives both failed. A larger schema extension would require reworking the extractor's prompts, and Milestone 1.5 exists to measure whether extraction changed, so the more prompt surface this touches the more it confounds its own measurement. An LLM normalization pass at ingest would put a model dependency inside a deterministic Python CLI that has none today, and add a second provenance seam. Accepted consequence: `statement` on a freshly ingested corpus is machine-templated rather than fluent, and `pattern` is sometimes NULL. That is a correct Milestone 1 outcome — the claim is that judgement accumulates durably, not that the first extraction reads well.
  Date/Author: 2026-08-25.

- Decision: nothing the extractor produces is dropped; a verbatim `extractor_payload` backs up whatever the schema does not name, and a test enforces it.
  Rationale: `PR-10`, `PR-09`. Four fields were being read and discarded. Typed homes were added for the ones with decided semantics (`gr_scenario`, `gr_edge_case`, `gr.parameters`, `gr.name`, `gr_run.injection_flags`), but a promotion-only approach fails silently the next time `RULES_SCHEMA` grows. The payload column plus the assertion that *every key of every input object is either mapped or preserved* makes "we capture everything" executable, and lets a later milestone promote a field without re-running extraction — which on a real corpus costs hours of model time. `injectionFlags` is called out separately as needing to be *loud*, because a prompt-injection suspect nobody reads is worse than never having scanned.
  Date/Author: 2026-08-25.

- Decision: `gr_scenario` retains the extractor's Given/When/Then as a subordinate child, rather than discarding it.
  Rationale: `PR-09`. Q3f settled on demote-and-retain, not discard, and three things depend on the retention. G/W/T is required on every rule of every run, so with no table it is the largest single volume of extracted content that ingest drops. The comparison this whole change exists to make — is the new requirement shape better than G/W/T — is far stronger within one run, same rule and both shapes side by side, than across two corpora separated by hundreds of rules of run-to-run noise. And for conditional rules, the bulk of any real corpus, a G/W/T scenario *is* the fit criterion, so discarding it while reporting `fit_criterion` fill rate as 0% throws away the answer and then complains about the question. It is deliberately not a `dedupe_key` input, for the same reason `as_built` is not.
  Date/Author: 2026-08-25.

- Decision: reviewer identity (`owner`, `reviewed_by`) is captured from day one, and `set_state` refuses to run without it.
  Rationale: `PR-09`. Identity is the one field in this schema that cannot be reconstructed retroactively — every other gap can be backfilled by re-running something. An approved corpus that cannot say who approved each record fails the exact audit claim the lifecycle exists to support. Made a required argument rather than an optional one so no caller can omit it by accident, and recorded as a binding requirement on the future review UI in `docs/exec-plans/pending/reqs-review-ui.md`.
  Date/Author: 2026-08-25.

- Decision: drift is expected to break the exact `dedupe_key`, and a second anchor-only key exists so it lands as a candidate rather than as a cold miss.
  Rationale: `PR-12`. Tier 2 of the discriminator is the span-level content hash, so any edit to cited code re-keys the rule. Routing a drifted rule to review is correct on the merits — the rule may no longer describe the code. What is not correct is that it should arrive indistinguishable from a genuinely new rule, because on a repository under active modernization drift is the normal case. `dedupe_key_anchor_only` recovers the recognition without weakening the exact key, and stage two still never auto-merges. Also settled here: a move auto-repair recomputes both keys, because rewriting `gr_citation.anchor_key` changes a tier-1 input.
  Date/Author: 2026-08-25.

- Decision: `not_accounted_for` is run-scoped, not rule-scoped, and the completeness gate blocks `export`.
  Rationale: `PR-15`. The five-value `disposition` set mixed two scopes: four values describe a rule that was found, while `not_accounted_for` describes code that yielded no rule and therefore has no `gr` row to sit on. Left as written, the value would either require a phantom record per gap or simply never be used, making the gate vacuous while the plan claimed it was enforced. Moving it to `gr_run` and naming `export` as what it blocks makes it real, and `export` is the right hard stop because the export is what leaves the machine and reaches a client.
  Date/Author: 2026-08-25.

- Decision: `data objects` are Milestone 3's, not Milestone 1's.
  Rationale: `PR-11`. Step 9 could not render `DATA_OBJECTS.md` from a store with no data objects in it. A bespoke `gr_data_object` table would be superseded within one milestone, because a data object is a cluster of terms and fact types and that is precisely what Milestone 3's vocabulary layer models. So Milestone 1 keeps rendering that one file from the extractor's return value and documents the asymmetry rather than hiding it.
  Date/Author: 2026-08-25.

- Decision: the `NORMATIVE SPEC-2` baseline comparison is its own milestone (1.5), after Milestone 1 and before Milestone 2.
  Rationale: SPEC-2 is a comparison harness, not a store feature: two markdown parsers over corpora with different card shapes, a mandatory noise-floor run of the two baselines against each other, and reporting rules that constrain what may be claimed. Folding it into Milestone 1 would put two parsers and an end-to-end NNG run on the critical path of "does the store work." Dropping it would leave the plan claiming coverage as its measured selling point (Step 6) while never measuring it. A declared milestone keeps both honest.
  Date/Author: 2026-08-25.

- Decision: the `pattern` CHECK is scoped to `state = 'approved'`.
  Rationale: `PR-26`. As first written the constraint and Step 6a could not both hold — ingest defaults `disposition` to `captured` and leaves `pattern` NULL on an ambiguous G/W/T shape, and the unscoped CHECK rejects exactly that row, so a bad extraction raises on `INSERT` instead of landing as a `draft`. Scoping to `approved` keeps everything SPEC-1 §S1.4 actually asks for (no NULL `pattern` in the approved corpus) while preserving the rule that nothing gates `draft`. The approval gate stays the human-facing enforcement; the CHECK is defence in depth behind it.
  Date/Author: 2026-08-25.

- Decision: `gr_citation.anchor_key` is resolved **at ingest**, by a Layer-0 lookup with a file-level floor — not by a later refresh pass, and not by the `citation-validator` skill.
  Rationale: `PR-27`. The design draft names `citation-validator` as the resolution pass, but that skill reads markdown with `Read`/`Edit`/`Glob`/`Grep`, predates `legacylift-search`, and opens neither database — so the mechanism the draft points at cannot do the job. More fundamentally a *refresh* pass is the wrong shape: resolved anchors are the tier-1 input to both dedupe keys, so they must exist before the row is keyed. The lookup itself is placed in Layer 0 rather than in the CLI because `symbols` lives in `index.sqlite`, Step 7 asks the same containment question again, and the rule must have one implementation. The file-level fallback is what makes an unresolvable citation safe: it bounds a collision to one file instead of collapsing the key space corpus-wide.
  Date/Author: 2026-08-25.

- Decision: the five slot-dependent validator checks use a computed slot split, not stored slots and not a five-slot parser.
  Rationale: `PR-28`. (**Amended by `PR-107`:** the *mechanism* below is superseded and must not be reinstated — "which side of the rule keyword a token falls on" is not a sufficient boundary, because §S1.3's restricted keywords are discontinuous and three of the ten patterns put `[Condition]` after the keyword rather than before it. Step 4 now derives the spans from each `pattern`'s own §S1.4 template. **Everything else in this entry stands and is why the replacement had to keep the same shape:** the split still re-derives from live text on every validation, still yields the character offsets `gr_finding.span` wants, and still rejects both stored slots and a five-slot parser for the reasons given. The original text is left standing per this plan's convention for a replaced closure.) See the entry below on the merge criterion for the other decision this review forced. `validate_statement` receives flat text and nothing in the schema stores slots, so the checks were unimplementable as written. Re-reading them shows none needs the `[Action]`/`[Object]` boundary — which S1.4 says is not a real boundary anyway — only which side of the rule keyword a token falls on. Storing slots at template-fill time was rejected because a human edit to `statement` desynchronizes them, silently disabling those checks on precisely the records under review; a full template reverse-parse was rejected because a NULL `pattern` leaves no template and an off-template edit cascades into five findings none of which name the real problem. The split re-derives from live text, yields the character offsets `gr_finding.span` already wants, and adds, removes or re-severities no check, so it is an §S1.6 implementation note rather than a SPEC-1 amendment.
  Date/Author: 2026-08-25.

- Decision: "not measured" is a distinct state from "nothing unaccounted for", everywhere it appears.
  Rationale: `PR-29`. (**Mechanism corrected by `PR-76`**, which is the accurate account and wins over this sentence: the workflow hands ingest `null`, not a zero, because `extract-rules.js:229` normalizes any skipped result before it reaches the return value. The decision below is unaffected — the zero-bearing shape is still what a field map reading a raw agent result would see — and the earlier wording is left standing as the record rather than edited, per the convention this plan already follows for `PR-22`.) The workflow hands ingest a zero when coverage never ran, so storing that zero made the completeness gate pass most confidently in the case it exists to stop. A nullable `not_accounted_for` with `complete = (not_accounted_for IS NOT NULL AND not_accounted_for = 0)` puts unmeasured on the same side of the gate as incomplete without pretending it is the same thing, and the two are reported in different words because they call for different actions. Apply the same discipline to any future field the extractor can hand back as a default: a measured zero and an absent measurement must never share an encoding. This is the same defect as the empty-string `dedupe_key` part and the NULL `span`, in a third place.
  Date/Author: 2026-08-26.

- Decision: the merge acceptance criterion is stated against a fixed extractor-output file; live re-extraction is a separate, softer criterion.
  Rationale: `PR-34`, `PR-35`. Step 6a made `rule_class` extractor-emitted and `pattern` a function of LLM-authored G/W/T, so two of `dedupe_key`'s four parts became nondeterministic *after* SPEC-3 §S3.3.1 had rejected `as_built` for precisely that property. Both keys re-key on such a flip, so the anchor-only fallback does not cover it; stage two's line-range intersection does, which means the rule is recognized but arrives as an extra row plus a candidate pair. The store is behaving correctly and a flat-count assertion across two live extractions would still fail, so the hard test is re-ingesting one saved JSON and the live re-run becomes a measurement — the second-run `rules_candidate` count, which is exactly the extractor's run-to-run classification instability and is worth knowing on its own. Rejected: removing `rule_class` and `pattern` from the key, which walks back into SPEC-3's rejected option A and collides on the dominant real case of several rules in one dense validator.
  Date/Author: 2026-08-26.

- Decision: `gr_dataflow` ships with no writer in Milestone 1; the table is still created, and `stats` reports its emptiness in words rather than as a rate.
  Rationale: `PR-48`. Both writers are unavailable for different reasons — the computed path is gated on M26, and the `llm_inferred` fallback that Q3h assigns to the extractor has no field in `RULES_SCHEMA`. (**Amended by `PR-79`:** the original reason was Step 6a's three-field cap, which no longer exists — the extractor is now rewritten to author the notation. The fallback stays deferred anyway, on the stronger ground that shipping the inferred half while the *computed* path is gated on M26 would invert the provenance principle. The conclusion is unchanged; only its second reason is.) The fallback is deferred rather than deleted, because Q3h is settled and the provenance value keeps its meaning; the field arrives alongside the M26 work. Adding it now was rejected for that reason, and dropping Step 7 wholesale was rejected because it would take the table, the model, the rendering and the computed code with it, and "enabling it later is a one-line change" is only honest if that code exists and is tested with the flag forced on. The table is created in Milestone 1 even though Milestone 0's runner would make adding it later safe, because deferring the table means deferring its tests. The reporting half is the part most likely to be got wrong: a rate over an empty table is zero over zero, and the earlier text calling it "100% by construction" would have shipped either a meaningless percentage or a division by zero into the acceptance criteria. Same discipline as `not_accounted_for`, in a fourth place.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: `requirements ingest` attempts embedding and degrades; it never blocks the rules from landing, and never exits non-zero because the semantic half failed.
  Rationale: `PR-47`. Embedding is the least reliable step in the pipeline — a network call per statement for the hosted provider — and it sits immediately downstream of the most expensive one. Blocking on it would risk losing an extraction run that costs hours of model time to a missing API key. The alternative considered was making embedding lazy: ingest never embeds, and `reindex-vectors` builds the collection before the first merge that needs it. Rejected because it removes the dependency from the hot path only by moving the failure later and quieter — the first re-ingest against a fresh store would have no stage two at all unless someone remembered a step nothing forces. Attempt-and-degrade keeps the common case correct with no ceremony, and makes `reindex-vectors` the single recovery path for every way the collection can fall behind: a reset, a missing embedder, a failed call, a provider switch that trips `validate_dimension`. The accepted cost is a reachable state where every rule is present and keyword-searchable while stage two is degraded, which is why the shortfall check in Step 5 is mandatory rather than optional — that state has to announce itself where it matters, not only in the output of the command that caused it.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: every artifact this toolchain generates moves under `<app>/analysis/<system>/`, following the `code-modernization` plugin's layout; nothing is written inside the pulled client code again.
  Rationale: user's call, 2026-08-26, prompted by `PR-46`. The plugin already separates `legacy/<system>/` (client code, pulled, read-only) from `analysis/<system>/` (everything generated), and `/modernize-assess` and `/modernize-map` write `ASSESSMENT.md`, `domains.json` and `topology.json` there today. `legacylift_search` predates that convention and resolves both its directories relative to `--repo-root`, which points at the code — so on the NNG unit it has written 316 MB of index plus Chroma and 484 KB of knowledge store into a pulled client repository whose own `.gitignore` does not mention `legacylift-docs/`. That is a client-repository hygiene problem before it is a design inconsistency, and this plan was about to add a file *intended to be committed* to the same wrong place. The index moves as well as the knowledge store: leaving it behind would fix the cheap half and leave the actual bulk in the checkout. Resolution detects the convention (`repo_root`'s parent named `legacy`, sibling `analysis/<basename>` present) rather than requiring it, falls back to today's paths otherwise so `repos/ctcm/ctcm-api` is unaffected, takes an explicit override, and prints the resolved paths on every run — a guessing path that cannot be inspected produces a second empty store beside a populated one. Folded into Milestone 0 rather than filed as a dependency because Step 9's export path, Step 5's collection and the backup advice all name locations that are wrong until it lands, and nothing else owns it.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: every field the extractor and a human may both write carries an `_extracted` shadow column; every field only one of them writes carries none.
  Rationale: `PR-45`. The plan had one shadow column and a hand-written protected list, and the two did not cover the same ground: `set-field` accepted eight fields, the merge protected five, and nothing named the four in between, so re-extraction silently reverted a reviewer's `disposition` and an SME's `modality_confirmed` — the exact accumulation this plan exists to deliver, failing invisibly. The fix is a rule rather than a longer list. A shadow column is needed precisely where "who wrote the live value" is unrecoverable, which is where both parties can write: `statement`, `assumptions`, `modality`. Everywhere else the question is already answered — the extractor-forbidden fields are human by definition, and `disposition` and `modality_confirmed` become insert-only so ingest never contends for them. `modality_confirmed` is deliberately kept alongside `modality != modality_extracted` because confirming a value and changing it are different acts and the commoner one leaves no trace otherwise. The symmetry was the user's call: one mechanism applied uniformly beats a per-field judgement that the next reader has to re-derive. And both ownership lists now come from one `EXTRACTOR_OWNED_FIELDS` constant, because two hand-kept lists in two files is what produced the defect.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: a citation resolves to **one** primary anchor, and every other symbol it touches is kept in a `gr_citation_anchor` child table that is never a key input.
  Rationale: `PR-44`. SPEC-3 §S3.3 declares a single `anchor_key` per citation row, but Step 6a's intersection fallback resolved a set, so the two disagreed and a multi-anchor citation had nowhere to live. Three shapes were considered. Concatenating the set into the one column was rejected because the move auto-repair finds citations by `WHERE anchor_key = ?` and a joined string degrades that to a substring match that half-works silently. Hashing the set into a single derived value was rejected because it severs the join back to `symbols` entirely, killing both the repair and the query. So resolution became total — innermost container, else smallest-span intersector with a written tie-break, else the file-level floor — which restores SPEC-3's row shape exactly. The child table then exists on its own merits: "which symbols does this requirement touch?" is a first-class query this store is expected to answer, with Milestone 3's vocabulary layer as its consumer, and a single primary anchor cannot answer it. Keeping it out of both dedupe keys is the load-bearing half: hashing the full set would re-key a rule whose own code never changed as soon as an unrelated sibling declaration appeared inside its cited range, which is Step 6a's "innermost, not all-enclosing" failure one level down. The same retain-but-exclude split `gr_scenario` already makes.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: `gr.statement` is NOT NULL, and a NULL `pattern` gets a pattern-free fallback template rather than an empty statement.
  Rationale: `PR-66`. (**Amended by `PR-79`, and by `PR-103` which finished pointing the copies at it:** the decision below stands in full — `statement` is `NOT NULL` and a NULL `pattern` gets a pattern-free fallback — but its *frequency* premise is dead. The extractor now authors `statement` as a required field, so the fallback is a defensive default rather than the commonest first-ingest path, and a NULL `pattern` is an abstention the extractor made rather than a shape ingest could not decide. Everything the entry says about why the column is `NOT NULL`, and about why defaulting `pattern` was rejected, is unaffected and is why the original text is left standing.) Step 6a fills `statement` from the chosen `pattern`'s §S1.4 template while also leaving `pattern` NULL wherever the G/W/T shape is ambiguous — commonly, on the definitional side, because §S1.4 draws six distinctions there that the extractor is never asked to report. So the plan's own commonest first-ingest case had no defined value in the column four subsystems read: the validator, the FTS5 index, the `gr_statements` embedding, and the `statement = statement_extracted` equality that is the sole definition of "a human edited this". Nullability was the alternative and was rejected on cost: it puts a NULL under all four, and two acquire a trap — the shadow equality has to become `IS` rather than `=`, because SQLite's `=` over two NULLs is NULL rather than true, so the merge would read every statement-less row as human-edited and never update it again. The fallback keeps one code path everywhere. Its load-bearing property is that it emits **text only and never a `pattern` value**, so both dedupe keys, the `approved`-scoped CHECK and the approval gate are untouched and the honest NULL survives. Also rejected, explicitly: defaulting `pattern` to `B-UNCOND` or `D-NEC`, which would write a guessed value into both dedupe keys and into the approved corpus. The manufactured sentence will trip the vagueness and keyword checks, which is the right outcome — the plan already establishes that `validate` exits non-zero on every fresh corpus, and these rows belong at the front of the review queue. Recorded as a §S1.4 implementation note, on the same footing as Step 4's keyword-anchored split against §S1.6: it adds no `pattern` value, changes no check, re-severities nothing.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: `index --reset`'s safety guard is widened as part of Milestone 0's relocation, with two clauses rather than one.
  Rationale: `PR-64`. The guard's final check requires the delete target be a descendant of `<repo_root>/legacylift-docs/` (`indexer.py:151-158`), which is the layout the relocation replaces — so after the move `index --reset` raises on every relocated repository, and no test in the suite would have caught it. Simply dropping the check and trusting the resolved path was rejected: the guard exists to catch a mangled manifest or an `--analysis-dir` override naming somewhere unrelated, and a check that validates the resolved path against itself catches nothing. So the ancestor requirement becomes the same two branches as the path-resolution rule — `legacylift-docs/` or the resolved analysis directory — which makes the guard and the resolver agree by construction rather than by maintenance, and a second clause requires positive evidence that the target really is an index directory (`index.sqlite` or `chroma/` present, or empty), which is what makes an override typo safe under any future layout rather than merely improbable. Fixed here rather than deferred because the relocation is what breaks it, and because so much of this plan reasons about what `--reset` destroys that a `--reset` which merely errors would leave those statements describing a command nobody can run.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: a missing element inside `dedupe_key`'s tier-2 discriminator is encoded as the literal `ch0:none`, not dropped and not `''`.
  Rationale: `PR-67`. The **third** deliberate refinement of `NORMATIVE SPEC-3`, and the same rule as the second applied one level down. §S3.3.1 defines tier 2 as a set of span-level content hashes and tier 3 as none of them, so it never contemplates a set with a hole — which Step 3 produces routinely, because a citation whose range cannot be read inserts with a NULL `content_hash` rather than being dropped. Dropping NULL members was rejected as the same ambiguity the empty-string rule exists to kill: two correct implementations disagree about whether a hole shrinks the set or fills it, mint different keys for one rule, and the merge stops matching with nothing raised. Encoding a hole as `''` was rejected for a subtler reason worth keeping: a requirement whose every citation is unreadable would then join to `''`, byte-identical to tier 3, which means "no citations and no typed body at all" — two different facts sharing an encoding, in the same formula where that mistake has now been made three times. With a sentinel, tier 2 fires whenever there is at least one citation, tier 3 only when there are none, and the tier is recoverable from the key's inputs.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: the lifecycle transition graph is explicit, `draft → approved` is permitted directly, and only `→ approved` is gated.
  Rationale: `PR-68`. Q5 settled the five states and nothing about the moves between them, and SPEC-1 §S1.9 assumes only that `draft` and `approved` exist and that the transition between them is a place a check can run — so "rejects an illegal transition" had no referent and the plan was unbuildable at that line. The graph is written as a literal `ALLOWED_TRANSITIONS` mapping rather than scattered conditionals so the legal set is readable in one place and enumerable by a test. `draft → approved` direct because Milestone 1 has no review queue — `set-field` is the whole write surface — so forcing two calls to record one person's single act would be ceremony the plan avoids everywhere else, and the gate fires either way. `reviewed` stays ungated for the same reason nothing gates `draft`: a gated `reviewed` makes the state a reviewer moves *through* unreachable on exactly the rows that most need review. `superseded` is terminal because a record that could leave it would leave `superseded_by` pointing somewhere with no defined meaning. And a same-state move is a no-op that stamps neither the review timestamp nor `updated_at`, which is Step 6's value-changing-write rule applied to the second writer.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: "not evaluated" is a column on `gr_finding`, never a third `severity` value.
  Rationale: `PR-69`. (**Amended by `PR-103`, the same amendment `PR-66` carries:** the frequency claim in the next sentence is dead — the extractor authors `statement` and emits `pattern`, so a NULL `pattern` is an abstention rather than the commonest shape. The decision is unaffected, because **the column is justified by reachability, not by frequency**: a check nobody could run and a check that ran clean are different facts however rare the first is, and the SPEC-fidelity argument below — which is the load-bearing half — never depended on the rate at all.) Step 4 requires the three `V-SLOT` checks be emitted as not-evaluated where `pattern` is NULL, and with `PR-66`'s fallback in place that is the common case on a fresh corpus, not the edge — so the state needed storage. The obvious home was a third severity, and it is the one option SPEC fidelity forbids: §S1.6 opens "Severity has exactly two values" and closes by requiring a SPEC-1 amendment for any change of severity, and Step 4's entire claim that the keyword-anchored split is *not* an amendment rests on it re-severitying nothing. Trading that away for a reporting concern would be a bad exchange. A boolean beside the severity costs nothing and keeps the closed set closed. Also settled here, because it is the kind of thing a later reader will worry about: the `evaluated = 1` clause added to the approval gate is defence in depth rather than load-bearing, since the only condition producing a not-evaluated row is a NULL `pattern` and the gate already refuses `approved` on that — but the clause is written anyway, because a gate that reads correctly on its own beats one that is correct only in combination with a precondition three paragraphs away.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: field ownership is a three-way exhaustive partition of `gr`'s columns, and `owner` is human-writable.
  Rationale: `PR-70`. `PR-45` replaced two hand-kept lists with one constant, which was right, but its acceptance criterion asserted the two sets were *complements* over `gr`'s columns — and fourteen columns belong to neither party, being assigned by the store or written by `set_state` and `import_records`. So the assertion failed on day one, and the natural way to make it pass is a hand-written exclusion list, which is precisely the mechanism that produced the original defect. Three named sets asserted pairwise disjoint with their union equal to the column list is the version that catches something: a column added by any future milestone fails the test until someone classifies it. Closing this surfaced a second defect that had been invisible behind the two-set framing — **`owner` had no writer anywhere.** Step 3 introduces it as human-owned and present from day one on the argument that identity cannot be reconstructed retroactively; `set_state` writes only `reviewed_by`; no command's accepted set included it. The audit claim it exists to support was therefore unachievable rather than merely unexercised. It belongs to `set-field` rather than to `set_state` because accountability is assigned rather than derived from an act, and it changes independently of any state transition.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: `gr_id` is `"GR-" + ULID` and the ULID generator is fifteen lines in `identity.py`, not a dependency.
  Rationale: `PR-77`. Step 3 called for "a ULID" and specified neither an algorithm nor a library, while `pyproject.toml` pins thirteen packages at exact versions and this plan's own rule forbids adding one without a recorded decision — so the store's primary key, called the single most important schema decision in the plan, was unbuildable. `uuid.uuid7()` would have been the tidy answer and is Python 3.14, while this package targets 3.11 or later. `uuid4` was rejected because Step 9 sorts the export by `gr_id` and Step 3 wants creation order, both of which need lexicographic sortability. So the algorithm is written out where the hash formulas are written out — 48-bit millisecond timestamp, ten `secrets` bytes, 26 characters of Crockford base32 with `I`/`L`/`O`/`U` omitted — and lives beside the keys it is a sibling of. Closing this also settled a format inconsistency the finding surfaced: the Purpose section's CLI examples read `GR-01HQ2X…` while Step 3 specified a bare 26-character ULID. The prefix wins, because a constant prefix costs nothing, preserves sortability, and makes an identifier self-describing in the three places it appears outside the database — the CLI, the JSONL export and `BUSINESS_RULES.md`. Worth recording alongside: unlike every other identifier here, `gr_id` is not a hash and nothing joins on its internal structure, so a divergent implementation is untidy rather than silently destructive — which is why writing the algorithm down is about clarity rather than about the correctness stakes that `dedupe_key` carries.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: re-deriving `subject` after a domain retag is an explicit `requirements rederive-subjects` command, not a side effect of `tag-domains` and not accepted staleness.
  Rationale: `PR-78`. `subject` is derived from `file_domains` at ingest and `statement` embeds it, so a retag left every subject and every templated statement describing the previous domain set with nothing reporting it — and the domain-retag invariant test does not catch it, correctly, because that test asserts the *keys* are byte-identical and subjects are the surface that is supposed to move. The two assertions are complements. Having `tag-domains` do the work implicitly was rejected twice over: it would make a Layer-0 tagging command know about the GR tables and about the shadow-column rule, and it would rewrite requirement text as a side effect of tagging, which is a large hidden consequence for a command that runs *before* extraction in the normal pipeline. Accepting the staleness until Milestone 4 was rejected because of what it does to the one check the Concrete Steps put in front of the implementer: they say to confirm a non-zero `derived` subject count before believing the derivation works, and a rate that can only fall as a corpus ages makes that check quietly useless. The command therefore also reports `llm_named → derived` transitions separately — a file that was `unassigned` at ingest and has since been tagged should stop being model-named, and nothing else makes that happen. (**Amended by `PR-79`:** the original entry closed by saying the command *"re-templates `statement` only where the live value still equals its shadow, which is the same unedited test the merge uses."* That is no longer true and must not be reinstated. The extractor now authors `statement`, so there is no template to re-fill and no mechanical way to substitute a new subject into someone else's sentence; the command touches neither that column nor any key. Step 8 is the accurate account, and the divergence between a stale statement and a refreshed `subject` is what `show` makes visible. Everything above this marker stands.)
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: the two exits from the completeness gate are two commands — `set-run-coverage` and `retire-run`.
  Rationale: `PR-73`. They were one command carrying both jobs, and they are different acts: one records a measurement someone actually took, the other records a human's judgement that a superseded run no longer counts. Collapsed into one name, "how did this run stop blocking the export?" cannot be answered without reading the columns, which is precisely the question an audit asks of a gate. Splitting them costs nothing before either exists and makes each one's required field — a measurement stamp on the first, a reason on the second — belong to the command that needs it.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: `/modernize-extract-rules` is **rewritten to author SPEC-1 notation directly**, and ingest derives only what needs ingest-time context. This replaces `PR-01`'s three-field cap outright.
  Rationale: `PR-79`. The plan said `statement` was "structurally unavailable to the extractor no matter how its schema grows" because a conforming statement names its `[Subject]` and the subject is derived from `file_domains` at ingest — and then specified a deterministic ingest-time deriver that measurement shows cannot work. On the 470-rule reference corpus, 66% of `then` values are passive clauses carrying their own subject, so they cannot follow "must" and trip `V-STY-01` on sight; 51% carry a semicolon and 36% an `and`, tripping `V-SING-01`; 20% of `given` values carry a comma, colliding with Step 4's own comma-delimited `[Condition]` split. `given` and `when` are *required* fields, non-empty on 470 of 470, so the stated rule "a non-empty `given` or `when` means there is a `[Condition]`" makes `B-COND` universal and `B-UNCOND` unreachable. And `[Formula]` and `[Value]`, which `D-COMPUTE`/`D-INFER`/`D-CONST` require, have no source field at all while the derivation bullet actively routes rules to those three patterns. The consequence is not ugly prose: `statement` feeds the `gr_statements` embedding, which *is* stage two of the merge, so the under-merge safety net the whole design rests on would search over noise. The `[Subject]` objection does not survive the data either — `plainEnglish` already names a concrete business subject on 470 of 470 rules ("A station", "A phone", "A contact"), `V-SLOT-02` bans only four literals rather than requiring a particular subject, and a business noun is a better `[Subject]` than a domain name would be; `gr.subject` stays the domain-derived analytic facet it already is. Rejected: keeping the design and merely specifying the splice precisely, which the measurements price; and having the extractor emit *slots* for ingest to assemble, which `PR-28` already rejected because a human edit to `statement` desynchronizes stored slots and silently disables the five slot-dependent checks on precisely the records under review.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: field ownership is a **four-way** exhaustive partition, and its fourth set is derived from the schema rather than declared. This replaces `PR-70`'s three-way partition.
  Rationale: `PR-81`. `PR-70` was right that exhaustiveness is what catches a new column and wrong that three sets can be disjoint. `statement`, `assumptions` and `modality` are written by the extractor *and* by a human — that is not a classification slip, it is `PR-45`'s own rule ("a shadow column is required for exactly those fields the extractor writes **and** a human may edit") defining a fourth cell into existence. Under three disjoint sets the plan contradicted itself three ways: the merge was told to write "exactly `EXTRACTOR_OWNED_FIELDS` and nothing outside it" while Step 6 required it to write three fields listed in `HUMAN_WRITABLE_FIELDS`; "`EXTRACTOR_OWNED_FIELDS` minus the insert-only pair" subtracted two columns that were never in that set; and `owner` sat in none of the three, so the union covered 39 of 40 columns and the assertion failed on day one — which is the exact failure `PR-70` closed one round earlier. Deriving the fourth set as `{c for c in columns if c + "_extracted" in columns}` is strictly better than a fourth declared list, because it cannot drift from the shadow columns it describes. Closing this surfaced a second defect of the same kind: **`rule_class` and `pattern` had no human writer either**, while `V-CLASS-01` blocks approval on a NULL `rule_class` and the gate blocks it on a NULL `pattern` — so a rule the extractor left ambiguous was permanently un-approvable. The Decision Log's own recompute rule proves the intent was otherwise, since it exists because "a reviewer who fills in `rule_class` re-keys the row". They need no shadow column, and the reason is worth keeping: both are inputs to *both* dedupe keys, so any merge that matches an existing row has identical values for them by construction — an exact-key hit implies agreement and an anchor-only hit inserts rather than updates — so **the merge can never change them**, which is exactly the position `disposition` and `modality_confirmed` already occupy.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: `V-STY-03` implements rubric items 2, 3 and 5 only, and this is recorded as a **SPEC-1 amendment** (§S1.12 A1) rather than as an implementation note.
  Rationale: `PR-80`. Unlike Step 4's boundary computation and Step 6a's fallback, this changes a numbered check's *test*, which §S1.6 reserves to an amendment — so the plan's established implementation-note device would have been a dodge. The inconsistency was inside SPEC-1 rather than introduced here: §S1.6's own row said six items while §18b says items 1/4/6 are not leakage, §S1.10 #10 fires the check on "items 2 and 5", and §S1.11 item 3 names "items 2, 3 and 5". Item 6 was additionally unbuildable in the validator's signature, being a relation between two records where `validate_statement` takes one. The user's call was to fix the spec rather than accumulate a fourth note against it, so SPEC-1 gained §S1.12, an amendment log, and the two "SPEC-1 stands unamended" claims in the design history are now pointed at it rather than left false. Recorded there and not fixed the same way: the three SPEC-3 refinements stay as Decision Log entries with SPEC-3 unedited, because departing deliberately from a coherent spec and correcting an incoherent one are different acts.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: the file grain of `anchor_key` passes a **constant empty string** for `language`, and `entity_class` is **declared by each extractor** rather than derived from `symbols.kind`. Both are recorded as SPEC-3 additions (§S3.1.1, §S3.1.2).
  Rationale: `PR-82`, `PR-83`. SPEC-3 §S3.1 specified `anchor_key` for Layer-0 *symbols* only; the `file` grain is this plan's own invention and left `language` undefined — while `detect_language` rejects every unrecognised extension outright and `discover_source_files` then skips the file, so an unindexed or absent path has no language to read. Any lookup would make a tier-1 dedupe-key input a function of whether someone had run `index`. A constant is correct rather than merely convenient: measured across both NNG indexes and `ctcm-api`, zero files carry more than one symbol language and zero symbols disagree with their file's, so at a grain where `entity_class` and `qualified_name` are both fixed, `language` carries no information at all. For `entity_class`, the mapping had the same churn properties as the closed seven-value set that Step 1 freezes so carefully, and was left to the implementer — over a domain that is **not enumerable from our source**, because `xml_extractor.py:208` mints kinds as `f"hibernate_{tag}"` from the client's own Hibernate elements and `:252` from the client's Webflow state elements. Declaration at the extractor is PRINCIPLE-1 again, and its load-bearing property is that a classification change then touches one framework's symbols and rides Step 3's existing re-resolution path, instead of moving everything and needing an `ak2:` bump. Rejected: dropping `entity_class` from the key as `language` was effectively dropped — measured, it genuinely discriminates, separating 19 `(file, qualified_name)` collisions in the NNG app and 2 in ctcm, all of them real (`SecUser.StatusEnum` as both `enum_declaration` and `field_declaration`; `FileDistributedCache.IsConnected` as both `property_declaration` and `method_declaration`). Also rejected: hashing the raw `kind`, which §S3.1 departure 2 already names as fact-graph's backwards design.
  Date/Author: 2026-08-26, Darrell Norton with Claude.

- Decision: the slot split is driven by each `pattern`'s §S1.4 template, and the resulting change to where `V-VAG-04` and `V-SING-01` fire is recorded as **SPEC-1 amendment A3**.
  Rationale: `PR-107`. The keyword-anchored form this replaces was not merely imprecise, it was contradicted by the spec's own worked examples: §S1.10 #3 is a ✅ conformant `D-INFER` carrying `and` in its `[Value]` and a trailing `if [Condition]`, and the old split scored it two `ERROR`s, making a spec-certified statement permanently un-approvable. Three properties of §S1.3 and §S1.4 caused it — discontinuous restricted keywords, trailing conditions on three of the ten patterns, and three patterns that §S1.4 explicitly places outside Figure 1's slot structure. Driving the split from the template is not a heavier mechanism than the one it replaces: `pattern` is already a column and already a parameter, so the split becomes a table lookup rather than a parse. The amendment half is the part that needed a decision rather than a correction, because saying a check has *no site* on three patterns changes where a numbered rule fires, which §S1.6 reserves to an amendment — and A1's precedent settles which way to go, since the user's call there was to fix an incoherent spec rather than accumulate a fourth implementation note against it. Rejected again, for the record: a five-slot parser (§S1.4 forbids it — `[Object]` is absorbed into `[Action]`) and stored slots (`PR-28` — a human edit desynchronizes them and silently disables the five checks on the records under review).
  Date/Author: 2026-08-28, Darrell Norton with Claude.

- Decision: the closed half of the `kind` domain is enumerated in full, `other` is the default for the **open** half only, and `property_declaration` classifies as `field`.
  Rationale: `PR-108`. The rule this replaces — "any `definition_node_kinds` entry not named above is `other`" — read as the same honest-default discipline §S3.1.2 establishes for the open half, and was the opposite thing applied to the closed one. Measured, it silently classified 16 distinct kinds across about 29 of the 52 entries, including every C#, Java and TypeScript type and member kind, and it re-collapsed both collisions the earlier decision cites as the measured reason `entity_class` is a key input at all. An honest default is honest because nothing better is knowable; over an enumerable domain, declining to enumerate is not a default but an unrecorded classification, and it lands in a **hashed** value where two implementations disagreeing is silent and corpus-wide. `property_declaration` is the one entry two implementers would genuinely split on, and it is decided by evidence rather than by taste: a C# property reads as a member but compiles to accessors, so `function` is arguable, and choosing it re-collapses the `FileDistributedCache.IsConnected` collision that is cited as justification for the column. It is state, so it classifies as state. Settled alongside: `definition_node_kinds` becomes `dict[str, str]` rather than gaining a sibling map, because a parallel map can hold a kind the list does not — priced first, and it costs one test fixture, since `set()`, `len()` and `in` behave identically on a dict.
  Date/Author: 2026-08-28, Darrell Norton with Claude.

- Decision: the four `structured_body` payloads are **specified in Milestone 1**, not deferred to Milestone 3 on the `gr_dataflow` no-writer pattern.
  Rationale: `PR-111`, user's call. The column was required to validate on write, the `decision_table` shape was forbidden to be invented, and no source defined any of the four — so the step was unbuildable, and deferring was the cheaper of the two exits. Deferring was rejected because it deletes one of Step 10's three mandatory measurements: the DMN argument is that a decision table is *executable* and can therefore serve as an oracle, and the whole point of measuring rule-counts-per-table is to find out whether that argument survives contact with a real corpus. A measurement that only happens two milestones after the claim is made is not a check on the claim. Specifying is also cheaper than it looks, because the `decision_table` payload is not a design problem: `hitPolicy`, `input`/`inputExpression`, `output` and `rule` with its `inputEntry`/`outputEntry` children are DMN 1.5's own decision-table element, so transcribing them is what "DMN-shaped" was always asking for. The accepted cost is one more field on the extractor prompt surface that Milestone 1.5 must disclose — which Step 6a already discloses in full, so it adds a line rather than a confound.
  Date/Author: 2026-08-28, Darrell Norton with Claude.

- Decision: the review act gets three columns and no history table — `reviewed_by`, `reviewed_at`, `review_note` — and the import marker gets its own table, `gr_import`.
  Rationale: `PR-114`. Four places already asserted observable behavior on a review timestamp that the forty-column list did not contain, and `set_state`'s own signature took a `note` that had nowhere to go — so the plan tested a column it never created. Adding them is not free, because the column count is a checksum on the four-way partition, so the count moves to forty-two and `STORE_OWNED_FIELDS` to sixteen deliberately rather than by omission. **Rejected: a `gr_state_history` table.** A per-transition trail is the right long-run answer and is genuinely wanted, but nothing in Milestone 1 reads one, so it would ship untested and unqueried — the same argument that keeps the review UI in Milestone 4, and it is recorded there. Last-write-wins matches `reviewed_by`, which was already specified that way and which nobody objected to. `gr_import` is separate rather than a column on `gr` for the opposite reason: import is the one declared exception to "`set_state` is the only writer of `gr.state`", so its marker has to exist somewhere, and attributing individual rows to it would be the per-record trail just rejected.
  Date/Author: 2026-08-31, Darrell Norton with Claude.

- Decision: the `llm_named` and `derived_ambiguous` subject is the `[Subject]` span of the requirement's own `statement`, read deterministically at ingest.
  Rationale: `PR-115`. Step 3 sent both fallback branches to "a model-named subject" while Step 6a forbids a language model in the CLI, adds no subject field to `RULES_SCHEMA`, and explicitly declines to unify the extractor's subject with `gr.subject` — so the branch had no producer at all, and the Concrete Steps meanwhile tell the implementer to read the `derived`-versus-`llm_named` split as the gate on believing the derivation works. The four candidate sources were: ask the extractor for a subject field (a new prompt surface Milestone 1.5 would have to disclose, for a field the agent already writes inside `statement`); an LLM pass at ingest (rejected on `PRINCIPLE-1` and on adding a model dependency to a CLI that has none); leave the column NULL always (which makes `subject_provenance`'s two fallback values decorative and the stats check meaningless); and read the span the extractor already authored. The last costs nothing, adds no prompt surface, and makes the provenance label literally true — the noun is the model's. Where `split_slots` finds no `[Subject]`, `subject` is NULL and the provenance still records the branch, per the absent-versus-real rule; `subject` is therefore nullable and `stats` counts the NULLs separately. Accepted consequence: `subject` derivation now depends on Step 4, which the Plan of Work's ordering already satisfies.
  Date/Author: 2026-08-31, Darrell Norton with Claude.

- Decision: `V-STY-03` receives its Layer-0 symbol tokens as a `leaked_terms` parameter; the validator never opens a database.
  Rationale: `PR-116`. Step 4 specifies the check as matching statement tokens against `symbols.name` and `qualified_name` for the cited files — "literally the check rather than a proxy for it" — while `validate_statement(gr: GRRecord)` carries neither the citations nor a `SQLiteStore`, and `symbols` is in the other database. This is the same unbuildable-signature shape as `PR-110`'s `resolve_anchor`, and it is sharper here because §S1.6's own reason for routing rubric item 6 out of this check is that it cannot be expressed in this signature. Rejected: passing a `SQLiteStore` into the validator, which would make a pure function depend on two databases and a working tree and force an index fixture into every `V-*` test. So the caller builds the set — `refresh_gr_derived_sql`, the only place the validator is re-run, which gains an optional `SQLiteStore` and `repo_root` for it and joins in Python like every other cross-database read here. An empty set is supported and means there was no index, under which the check runs on its morphological fallback alone; `stats` reports that, because a silently weaker check reads as a cleaner corpus.
  Date/Author: 2026-08-31, Darrell Norton with Claude.

- Decision: `split_slots` degrades to the NULL-`pattern` path when a non-NULL `pattern`'s keyword is absent from `statement`.
  Rationale: `PR-117`. Every row of Step 4's template table anchors on the keyword, and the step specified only the `pattern IS NULL` degradation — leaving undefined the case §S1.10's own rejected examples are made of: #5 uses `shall`, which is no keyword, and #6 carries one keyword from each class. Both are exactly what `V-KW-01`/`V-KW-02`/`V-KW-03` exist to catch, so the case is common rather than hypothetical. Rejected: raising, which turns a reportable defect into a crashed validation; and guessing a boundary, which produces three `V-SLOT` findings derived from a span that was never found, all naming the wrong problem on a record whose real defect a `V-KW` `ERROR` already states precisely — the cascade `PR-28` rejected. Degrading costs one branch and no new state, since `evaluated = 0` already exists for exactly this.
  Date/Author: 2026-08-31, Darrell Norton with Claude.

- Decision: the export's incompleteness marker is a deterministic `_incomplete` first line written only under `--allow-incomplete`, and Step 9's rule is restated as determinism rather than as "no header line of any kind".
  Rationale: `PR-118`. Step 3 requires the incompleteness be "written into the export itself" and Step 9 forbade any header line, so the two could not both hold and an implementer had to pick one silently. The property Step 9 is actually protecting is byte-identity across two runs over unchanged data, and a marker carrying only the offending `run_id`s and their reason does not threaten it — what threatens it is a timestamp, a counter or a version, which is what the rule's own examples all are. So the rule keeps its teeth in the form that states the property, and the marker is permitted in the one case that needs it. `import` skips the object rather than reading it as a record. Rejected: a sibling `.incomplete` file, which separates the warning from the artifact that reaches the client — the export is what leaves the machine, and a caveat in a second file is a caveat nobody receives.
  Date/Author: 2026-08-31, Darrell Norton with Claude.

- Decision: `file_domains`' two reserved non-domains — `unassigned` and `excluded` — are both barred from becoming a subject, and an all-sentinel requirement is `derived_ambiguous` rather than `llm_named`.
  Rationale: `PR-124`. The subject derivation named only `unassigned`, and `excluded` has existed since 2026-07-24 (`98f2f9bf`): `/modernize-assess` authors `exclude_globs`, `tag-domains` writes `domain = 'excluded'` for a matching file with no real domain (`knowledge_store.py:127-129`), and coverage percentages already drop it from the denominator. Left unhandled, a rule citing an excluded file derives the literal string `excluded` as its business subject — the absent-versus-real defect in its purest form, a reserved sentinel presented as a real value. Both sentinels therefore leave the candidate set and the denominator. **Routing the all-sentinel case to `llm_named` was rejected, and the reason is the one that justified a third provenance value in the first place:** `llm_named` means "the code was never tagged, run `tag-domains`", which is actionable and false of an excluded file — it *was* tagged, deliberately, and re-tagging changes nothing. Putting an unfixable case in the fixable bucket also depresses the `derived` rate the Concrete Steps tell the implementer to read as the gate on believing the derivation works. `derived_ambiguous` already means "the derivation legitimately has no answer here". Settled with it: the all-excluded count is its own figure in `stats`, because it is a finding about the *extraction* — rules mined from code declared out of scope — and both of its readings are actionable.
  Date/Author: 2026-08-31, Darrell Norton with Claude.

- Decision: `gr_merge_candidate` is keyed `UNIQUE (gr_id_existing, gr_id_incoming)`, with `run_id` outside the tuple and no surrogate key.
  Rationale: `PR-125`. The table was specified as a bare column list while every sibling child table carries a key — `PR-109`'s omission one table on — and its stated purpose depends on one: a reviewer's `distinct` judgement is supposed to stick "so the same pair does not resurface on every subsequent run", which needs a lookup the table did not have. The pair is the relationship's identity, so it is the natural key. **`run_id` is deliberately excluded from the tuple**, which is the half that carries the meaning: keying per run would let a later run re-raise a pair already resolved `distinct`, reintroducing through the constraint the exact behaviour the constraint is there to stop. `run_id` keeps the `first_seen` sense `gr.first_seen_run_id` has. A surrogate key was rejected despite three sibling tables having one, because none of their reasons applies: this is a pair with attributes, not ordinal-bearing content (`gr_scenario`, `gr_edge_case`), not itself a parent (`gr_citation`), and not subject to `gr_run_hit`'s count identity, where one run can offer two rules landing on one `gr_id`. Two distinct incoming `gr_id`s are already two distinct rows, so the natural key is total.
  Date/Author: 2026-08-31, Darrell Norton with Claude.

- Decision: The embedder reaches `refresh_gr_vectors` and `set_state` as a keyword-only parameter defaulting to `None`, and `None` means degraded-success rather than error.
  Rationale: Step 5, as built. `Interfaces and Dependencies` declared `refresh_gr_vectors(store, gr_ids)` and `set_state(store, gr_id, to_state, reviewer, note)`, and neither can reach an embedder — but the vector half needs one and `set_state` is one of the pair's six callers, so the two rules could not both hold. **Making the embedder required was rejected outright**, because it inverts this step's own degradation rule at the worst point: `set_state` records the single act the whole lifecycle exists to support, and a required embedder would let an unreachable hosted provider — the least reliable thing in the pipeline — be the reason a human's sign-off fails to record. Defaulting it to `None` keeps the store correct and merely under-populated, and `describe_vector_shortfall` is what makes the under-population announce itself. Settled with it: `refresh_gr_vectors` also takes an optional already-open `collection`, so ingest opens one for a whole run rather than one per record, and `set_state` **drops** the returned `EmbedResult` deliberately — its declared return type is `None`, and the question worth answering is "is the collection behind", which is a property of the collection and not of one call.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `gr.modality` stays the two-value KAOS enum, and `NORMATIVE SPEC-1` §S1.3's modal keyword strings are carried in the extractor's `statement` instruction instead. Step 6a's own wording, which asked `RULES_SCHEMA.modality` to carry those strings, is the defect.
  Rationale: The column is `CHECK (modality IN ('requirement','expectation'))`, which is Q3i's decision, and `gr_validator.py` does not read the column at all — every `V-KW-*` check tests `statement`. Putting SPEC-1's keywords in a `modality` enum would have failed every ingest against a `CHECK` while leaving the checks that actually test for those keywords looking at a field the extractor was never told to shape. The two ideas share an English word and nothing else. Recorded rather than silently fixed because the plan's Step 6a text still reads naturally in the wrong direction.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `RULES_SCHEMA.ruleClass` is required but **nullable**, and `pattern` is optional with `null` in its enum; the prompt calls abstention a last resort and an extraction failure.
  Rationale: `NORMATIVE SPEC-1` §S1.2 step 4 says that where neither class is determinable `rule_class` is NULL and "it must never be guessed", and `V-CLASS-01` exists for precisely that row. A required two-value enum forces the guess the spec forbids. The same reasoning covers `pattern`: a guessed value goes into **both** dedupe keys and into the approved corpus, and destroys the signal the nullability carries. `HUMAN_WRITABLE_FIELDS` is what makes the abstention recoverable — a reviewer can fill either in without re-keying the row.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: The `gr.state` writer census asserts over the **table**, not the column, and reads string literals through `ast` rather than raw text.
  Rationale: See `Surprises & Discoveries` finding 3. A source regex cannot see a runtime-built SET clause or column list, which is the ordinary shape of a column-mapped update and was already in the tree, so the column-level form gave false assurance on the acceptance criterion "`set_state` and `import_records` are the only writers, and a test asserts that set is complete". Asserting over the table converts "invisible" into "must be declared": any module containing a write against `gr` fails the test until it is named. Reading literals through `ast` and skipping docstrings removes the false positive that had already cost one module its clearest docstring. A meta-test asserts all five evasion shapes are caught and that prose is not.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `import_records`' downgrade guard ranks `superseded` **above** `approved`, not level with it.
  Rationale: Level with it makes the comparison a tie in *both* directions, so a file exported before a supersession restores `approved` over a record the store has since superseded — reverting a human's judgement and orphaning `superseded_by`, with no flag required and nothing reporting it. `superseded` is terminal in `ALLOWED_TRANSITIONS` precisely because its successor is where the work continues, so leaving it is exactly the act `--allow-downgrade` exists to make deliberate. Ranking it above gets both directions right at once: `approved → superseded` is an increase and restores freely, which the ordinary case requires, while the reverse is refused. The first form of this guard was reasoned only about the direction the plan's two worked examples name.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `dataflow_status_text` reports a non-zero total as an anomaly with **counts**, and does not raise.
  Rationale: Its first form raised `NotImplementedError`, on the reasoning that Milestone 1 has no writer so a row can only mean a bug. The reasoning is right and the failure mode is wrong for this caller: `requirements stats` is read-only and is where Step 10's three mandatory measurements are read from, so raising out of it for a *data* condition costs the operator the state counts, the SME fill rates, the intra-run collapse rate and the anchor-resolution breakdown in order to describe one empty table. Degrade loudly instead — the same choice ingest makes when no embedder is reachable. The no-rate guarantee this function exists for is unaffected and is now stronger than it was: it is asserted structurally, as the absence of any division in the module, rather than by taking the right branch.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: Stage two's semantic half uses top-k 5 and a maximum distance of 0.35, as **parameters of `ingest_extraction` documented as unvalidated**, not as tuned constants.
  Rationale: The plan specifies no threshold anywhere, and stage two cannot function without one. The safe direction is available because of the asymmetry Step 6 already establishes: no similarity threshold auto-merges anything at any confidence, so the only thing these numbers change is which pairs a reviewer is shown, and getting them wrong can never cause a false-same. They are parameters so tuning needs no code change. **Both are metric-dependent and nothing pins the metric** (`Surprises` finding 6), so they are recorded as wanting measurement on a real corpus in the same run as Step 10 rather than as settled values.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: The pattern-free statement fallback takes its `[Subject]` from the rule's `name`, then `plainEnglish`, then the literal `"This rule"`.
  Rationale: Step 6a specifies the fallback's *keyword* by `rule_class` and its predicate from `then`, but never says what fills the subject slot — and the fallback exists precisely for a rule arriving with an empty `statement`, where nothing else in the payload is guaranteed. The chain prefers the most specific business noun available. `"This rule"` is chosen deliberately over any of `V-SLOT-02`'s four banned literals (`the system`, `the application`, `the software`, `the program`): a manufactured sentence must not trip a notation check for a reason unrelated to the extraction, because that finding would be read as evidence about the extractor. The fallback still produces text only and never a `pattern` value, so both dedupe keys, the `approved`-scoped `CHECK` and the gate are untouched.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: All raw SQL touching the `gr` tables lives in `knowledge_store.py`; `gr_ingest.py` contains none.
  Rationale: A consequence of the census decision above rather than a taste preference, and worth recording because it looks like one. The census asserts exactly which modules contain a write statement against `gr`, so putting the merge's SQL in `gr_ingest.py` fails the suite. The effect is that a layering that was previously conventional — the store owns SQL, the logic modules own logic — is now enforced, and a future writer has to either use the store's API or declare itself. `gr_export.py` is the one other declared writer, for the reasons Step 9 gives.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: **Phase 6's second live extraction is ingested into a COPY of the store, not into the real one.**
  Rationale: Phase 6's deliverable is `rules_candidate`, the extractor's run-to-run key-instability figure, and that number needs only a store that already holds run 1 — which a copy has. Ingesting into the real store would additionally turn it into a two-run merge, and while `gr.first_seen_run_id` keeps run 1's *rule* count recoverable, its **distinct-files-cited figure is not**: `gr_citation` carries no `run_id` and `_write_children` upserts citations on `(gr_id, relative_path, start_line, end_line)`, so a merged run's new citations attach to existing requirements indistinguishably from the originals. Milestone 1.5 requires rule count and distinct-files-cited to be reported *together*, so losing one of the pair would settle that milestone's framing as a side effect of running Phase 6. A copy costs a few hundred MB of scratch and forecloses nothing: the merged store can be produced later by ingesting the same saved corpus for real, once the Milestone 1.5 comparison is chosen with the numbers in hand. Rejected: not ingesting at all, which does not yield `rules_candidate` and so does not perform Phase 6. **The copy must include `knowledge/chroma/`, not only `knowledge.sqlite`** — see the note in the runbook's §9; without it the collection starts empty and the run cannot test whether stage two's semantic half fires, which Phase 5 identified as Phase 6's first opportunity.
  Date/Author: 2026-09-10, Darrell Norton with Claude.

- Decision: On a merge, `gr_citation.verified_at` moves only when that citation's `content_hash` actually changed.
  Rationale: Step 6 says an already-present citation is "left alone apart from a refreshed `content_hash` and `verified_at`", which read literally stamps the column on every ingest. `verified_at` is part of the JSONL export, so stamping it unconditionally makes two headline claims false in a column nobody thinks to check: re-ingesting the same output *changes nothing*, and the second export is *byte-identical*. This is Step 6's own value-changing-write rule applied one level down, to a child table the rule was written about the parent of.
  **Measured 2026-09-10, Phases 4–6 — the decision holds, and so does export determinism; what needed narrowing was this entry's first observable, not its second.** `verified_at` moved on **no** citation across two re-ingests of the same file, and `gr_citation` came back **byte-identical** in a field-by-field diff of all 383 rows, so the mechanism this entry protects works. **Export determinism also holds as stated**: two exports of the same store with no intervening write are byte-identical (2,498,820 bytes both times), which is the claim the acceptance list makes and it passes. What is *not* true is the sentence's other half — that re-ingesting the same output **changes nothing**. It changes two things, neither of them a citation: `updated_at` moves on the 48 requirements that absorbed more than one offer in the run (`MEAS-1`'s reading-B set, rewritten once per offer — see *Step 10 Phase 4*), and the reserved `_incomplete` header gains a name per contributing run, 1 → 3 across three ingests. So an export taken *across* a re-ingest differs, and an export taken *twice over an unchanged store* does not. **Keep both byte-identity criteria in the acceptance list**; just do not read either as a claim that ingest is a no-op.
  Date/Author: 2026-09-02, Darrell Norton with Claude; measured 2026-09-10.

- Decision: A citation whose line range extends past end-of-file stores a NULL span `content_hash` rather than a hash of the clamped range.
  Rationale: "The cited range cannot be read" is one of the two NULL cases Step 3 names, and a range running past EOF is that case. Clamping would hash a range nobody cited into a tier-2 dedupe-key input, so two rules citing different over-long ranges in the same file would key identically — a false-same, which is the failure class this plan calls invisible and fatal. The `WHOLE_FILE_END_LINE` sentinel from `parse_citation` is the one deliberate exception, because there the whole file *is* the citation.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: A rule arriving with a missing or invalid `modality` fails the ingest, naming the rule by `offer_ordinal`. Ingest never defaults the column.
  Rationale: `modality` is `NOT NULL` with a two-value `CHECK`, and it is extractor-proposed and SME-confirmed under `PRINCIPLE-1`. Any default ingest could pick is a guess written into a confirmed-by-a-human-later field, and `modality_confirmed` false would not distinguish "the extractor proposed this" from "ingest invented it". Failing loudly with the ordinal is recoverable in seconds; a silent default is not recoverable at all once a reviewer has confirmed it.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `gr_fields.UNMAPPED_KEYS` is declared and **empty**, and `gr_ingest` declares two further constants — `CHILD_MAPPED_KEYS` and `VERBATIM_KEYS` — to make Step 3's completeness disjunction computable.
  Rationale: Step 3's rule is a three-way disjunction (mapped to a column, or to a child row, or knowingly unpromoted) and only the first branch had a computable referent. Verified rather than assumed: `RULES_SCHEMA`'s rule item carries exactly 22 keys after Step 6a, and all 22 are accounted for — 14 through `EXTRACTOR_FIELD_MAP`, `ruleClass` and `pattern` written verbatim **outside** it (they are `HUMAN_WRITABLE_FIELDS`, so the map cannot carry them, yet ingest is what first puts a value in them), and six as child rows. `UNMAPPED_KEYS` stays declared as the reviewable slot for a future field deliberately left in `extractor_payload` alone. A guard fails the ingest if ingest's read set and `EXTRACTOR_FIELD_MAP` ever disagree, because a map key added and not read would otherwise be declared and silently dropped.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: Both dedupe keys live in a new `gr_keys.py`, take `sorted(set(...))` inside the functions, and import `UNIT_SEPARATOR`/`DIGEST_HEX_CHARS` from `identity.py` rather than redefining them.
  Rationale: A separate module because the future move auto-repair must share one implementation with ingest, and a key computed two ways is the silent-merge-failure class in its purest form. The set-and-sort is taken inside the functions so no caller can get the two readings of "`sorted(anchor_keys)`" wrong — the plan spells that ambiguity out because two implementations reading it differently mint different keys for the same rule. `identity.py` gained public names for its two private constants (aliases kept) for the same reason: two definitions of a hash input is exactly what this unit exists to prevent, and duplicating them in a second module would have been one.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: A whole-file citation short-circuits to the file-level anchor instead of being resolved against symbols.
  Rationale: Step 6a lists "a bare path meaning the whole file" among the file-anchor cases but the resolution rules read as applying to every citation. A whole-file range intersects every symbol in the file, so under the general rule the **smallest declaration in the file** wins the key — a value that changes whenever an unrelated small member is added, on a citation that was never about that member. Found by constructing the case rather than by reading the rule.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `models.py`'s ten new Pydantic models landed first, alone, as a single-owner commit, before any parallel unit started.
  Rationale: Process, recorded because the next multi-unit wave faces the same question. Five of the six units imported the same models, so it is the one file that could not be divided among them and the one place concurrent edits would have conflicted. Everything else in the wave was genuinely disjoint by file, which is what made five agents in one checkout safe. The corollary is in `Concrete Steps`: the *test suite* is shared even when files are not, so a full-suite run taken mid-wave reports failures that are neither yours nor real — take per-file counts during the work and the suite count once, at the end.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: The `requirements` sub-app lives in a new `cli_requirements/` package, and `cli.py` gains only the one `app.add_typer` line. **This deviates from Step 8's own wording**, which says to add the sub-application in `cli.py` and calls Step 8 "the only remaining work in `cli.py`".
  Rationale: `cli.py` was 1,857 lines before this step and fourteen commands would have nearly doubled it. The decisive reason is not size but process: the package gives four parallel units **disjoint file ownership**, which is the property that made Wave A's five agents safe in one checkout, and there is no way to divide one 1,200-line addition to a single file among four agents. `cli_helpers.py` is the existing precedent for CLI code outside `cli.py`. The plan's requirement is satisfied in substance — the group is registered with `app.add_typer`, and it is still the first in the file. One consequence had to be repaired: the `gr.state` writer census globs `src/legacylift_search/*.py`, which is flat and does not descend into a package, so a command module could have composed its own `UPDATE gr SET` invisibly. A package-scoped scan reusing the census's own `ast` helpers now covers it, so the layering is enforced for the new code rather than merely intended.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `set-state --reviewer` falls back to the `LEGACYLIFT_REVIEWER` environment variable and to nothing else. Git `user.email` was considered and **rejected**.
  Rationale: Step 8 requires a reviewer identity "from `--reviewer`, falling back to a configured default" and names no source; `Manifest` carries no identity field at all (`ProjectConfig`/`IndexConfig`/`EmbeddingConfig`/`SearchConfig`/`LanguagesConfig`, none of them), so the env var is the only honest configured source available without changing `config.py`. Git config was the tempting second: `user.email` answers "who authors commits in this checkout", which on a shared workstation or in CI is routinely a service account. Attributing a human's sign-off to a bot is the exact audit failure the reviewer requirement exists to prevent, and it is worse than requiring the flag, because **an identity that might be someone else's is a placeholder wearing a real name** — which is this plan's absent-versus-real rule applied to accountability. The command still refuses to run when neither is present.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `set-field` takes a `--null` flag distinct from `--value ""`, and passing neither is a usage error rather than an implicit clear.
  Rationale: `set_field` accepts `value: str | None` where `None` writes SQL NULL and `""` writes `""`, and in this schema those are different facts: `assumptions = ''` means "the agent considered assumptions and had none" while NULL means the field never arrived — it is the one shadowed field whose nullability is already the reason the shadow equality is `IS` and not `=`. A CLI that can only send a string cannot express the first. Refusing an argument-free invocation is the same rule one level out: a mistyped `set-field --field assumptions` must fail rather than wipe a column.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `requirements stats` prints no fill rate for `modality_confirmed`, and prints the **numerator by name** beside every rate it does report.
  Rationale: `gr_field_fill_counts` deliberately returns `{filled, empty, absent}` rather than a rate, because the numerator differs per column and one rule for twelve columns is wrong for at least two of them. `modality_confirmed` is `NOT NULL DEFAULT 0`, so its fill rate is a guaranteed 100% measuring nothing, and its `0` is a fact rather than an absence. `assumptions`'s numerator is `filled + empty`; every free-text SME column's is `filled` alone. A rate whose numerator is not stated is the derived-value form of this plan's recurring defect — the fourth review round's refinement, that a count read off the wrong field of an entirely correct payload fails exactly the way a NULL stored as zero does.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `--json` emits grouped counts as a **list of `{value, count}` objects**, never as an object keyed by the grouped value.
  Rationale: A JSON object cannot carry a null key, so the obvious encoding forces NULL to become the string `"None"` or a chosen sentinel — re-introducing, at the boundary, exactly the NULL-versus-real collision the `count_gr_by` reader exists to keep apart. The same applies to `RederiveResult.provenance_transitions`, whose keys are tuples and whose obvious encoding turns a NULL old provenance into the literal `"None"`; it is emitted as `{from, to, count}` objects. It is the outbound-encoding form of the recurring rule in `Surprises & Discoveries`: **the encoding a value takes on the way out of this system is as much a place for this defect as a column.**
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `requirements ingest` exits **zero** on a payload that yields zero rules, and is loud about it, naming the payload's own top-level keys.
  Rationale: The `gr_run` row is written either way, so a non-zero exit would tell the caller nothing was stored, which is false. But zero rules is also the signature of Wave A's finding 1 — a field map written against `rules` when the workflow returns `confirmedRules` **reports a successful ingest of zero**, green and quiet and empty. Naming the keys that actually arrived makes a wrong-file or wrong-shape mistake diagnosable from the command's own output, without which the loudest failure in this pipeline is also its most silent.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `requirements validate` never calls `refresh_gr_derived_sql`; it validates through the newly public `gr_refresh.leaked_terms_for` with one shared cache across the corpus.
  Rationale: The Purpose section says this command "reports rule-notation violations **without changing anything**", and the refresh pair's SQL half performs a delete-then-insert of `gr_finding`. Routing `validate` through it would have made the one read-only inspection command a writer — and, worse, one whose writes look like the validator merely being run. A probe asserts the `gr_finding` rows are byte-identical across a validate. The private `_leaked_terms_for` was promoted rather than duplicated, for the same reason `gr_keys.py` imports its hash constants instead of redefining them.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

- Decision: `requirements ingest --system` reaches `gr_run.system` by injecting into a shallow copy of the payload, and the flag wins over a value already in the file.
  Rationale: `ingest_extraction` reads `payload["system"]` and has no `system` parameter, so the flag that `Concrete Steps`' own invocation passes had nowhere else to land. The flag wins because it describes the run being performed now while a saved payload's value describes the run that produced it, and a re-ingest of an archived file is precisely when the two legitimately differ. A disagreement prints a loud stderr line naming both values, so the precedence is visible rather than assumed.
  Date/Author: 2026-09-02, Darrell Norton with Claude.

## Outcomes & Retrospective

Write an entry here at the end of each milestone comparing the result against the Purpose section above: what an analyst can now do that they could not before, what remains, and what surprised you.

### Milestone 0 (2026-08-31)

**What is now possible that was not.** Either SQLite database can gain a column without being deleted first — the property Milestone 1 Step 2 and Step 3 both depend on, and the reason this milestone came first. And nothing this toolchain generates is written inside the analyzed repository any more: 353 MB of index, Chroma and knowledge store moved out of two pulled client checkouts into `analysis/<system>/`, with `repos/ctcm/ctcm-api` left on the `legacylift-docs/` fallback to prove the detection does not require the convention.

**Result.** 408 tests passing, up from the 357 baseline: +18 `test_migrations.py`, +13 `test_config.py` (24 total), +19 `test_reset_guard.py`, +1 `test_cli_smoke.py`. Both NNG units report counts identical to the pre-move transcript, every `.sqlite` verified by SHA-256 before the originals were removed.

**Five things that surprised, all worth carrying forward:**

1. **`index --reset`'s user-home refusal never fired.** Its own `ValueError` was raised *inside* a `try` whose `except Exception: pass` swallowed it. Home was still refused, but by the directory-name clause under a message naming the wrong reason. That guard had zero tests before this milestone; it has 19 now, and this is what the first test run found. A defect can sit in a safety check for as long as nobody asserts on it.
2. **`search` is nondeterministic across processes**, so the plan's own verification oracle was unsound. See the corrected paragraph in Milestone 0's relocation section — measured, not inferred, by interleaved A/B runs against the original and the copy.
3. **ChromaDB rewrites its files on every open, including a read-only query.** So the hygiene problem this milestone fixes was worse than stated: on a fallback-path repository, *searching* dirtied the client's checkout, not just indexing.
4. **The migration runner's first real-world act was visible in production data**: both NNG `knowledge.sqlite` files went `user_version` 0 → 1 on first open, with all four tables' row counts unchanged. The fresh-versus-existing stamp working on a real database, which is exactly what the version-1 no-op baseline exists to make observable.
5. **The resolved-path banner had two defects of its own**, both caught only by looking at real output rather than at tests: rich wrapped every path across two lines at the 80-column pipe width, making the banner ungreppable, and it parsed the literal `[legacylift-search]` prefix as style markup and silently dropped it. A line whose entire purpose is inspectability has to be inspected.

**Two plan defects corrected in passing**, both surviving nine review rounds: the `conn.commit()` site count read "twenty" while its own enumeration listed eighteen, and the class is `Indexer`, not `IndexBuilder`. Both are the shape the ninth round predicted — things a type checker or a grep finds in an hour, not things more prose review would have caught.

**What remains.** The full-`index`-run acceptance (plan §Milestone 0, "the observable form") was not executed: it means re-embedding 15,040 chunks through Bedrock Titan, hours plus spend. It was settled the cheap way instead — `grep -rn "legacylift-docs" src/` confirms no write path constructs that string literally; every remaining hit is help text, a docstring, the two manifest defaults that flow through the resolver, or the reset guard. Run it for real when the next full index of that unit happens anyway, which Milestone 1's end-to-end acceptance requires regardless.

### Milestone 0 code review (2026-09-01) — findings `CR-01` … `CR-07`

Two independent review passes ran against `bb148e41..HEAD` after Milestone 0 shipped: a first
adversarial pass whose four findings were fixed in `751c8b26` and recorded in the session handoff,
and this second pass. **These `CR-` identifiers are a different series from the `PR-` findings in
the archive**: `PR-` are pre-implementation *plan* reviews, `CR-` are code reviews against shipped
code. Every finding below was reproduced with an executable probe; none is inferred from reading.
The full suite was green throughout (408 passing, exit 0), so none of these is a test failure —
which is the point, and `CR-01` is the one to act on first.

**Three of the six defects share one root cause**, and it is the thing to understand before fixing
any of them: `resolve_index_dir`, `resolve_knowledge_dir` and `cli_helpers.resolve_paths` implement
**three different precedences** over the same two flags. The two resolvers agree with each other
only when their inputs happen to agree; `resolve_paths` short-circuits before either. Fixing
`CR-02`, `CR-03` and `CR-04` one at a time will not converge — settle the precedence once, in one
place, and make all three call it.

| ID | Finding | Where | Status |
|---|---|---|---|
| `CR-01` | **`index.sqlite` never migrates on any read path.** `SQLiteStore.migrate()` is the only caller of `run_migrations(INDEX_MIGRATIONS)` and runs from exactly two places, `index` and `backfill-vectors`. Every read command builds `SQLiteStore` without migrating, while `KnowledgeStore.__init__` migrates on *every* open — the two databases have asymmetric triggers. Verified in production data: both NNG `index.sqlite` files sit at `user_version` 0 while both `knowledge.sqlite` files are at 1. | `store.py`; `indexer.py:325`, `:1248` | **Fixed 2026-09-01** — migrations run from `SQLiteStore._connect`; read paths now advance the schema. Probe: a plain `stats` took a 232 MB copy of the NNG-app index 0→2. |
| `CR-02` | **The default-detection comparison is a raw string compare** (`manifest.index.index_dir != default_index_dir`), so a manifest holding the *normalized-identical* default is misread as explicitly configured. `"./legacylift-docs/index/code-search"` and `"legacylift-docs\index\code-search"` (the natural Windows hand-edit) both put the index inside the client checkout while the knowledge store obeys the new layout — the exact two-roots split the adjacent comment says the branch ordering exists to prevent. Compare `Path(x) != Path(default)`. | `config.py:349`, `:398` | **Fixed 2026-09-01** — `is_default_setting` compares as `PurePosixPath` after folding backslashes, so the Windows hand-edit and `./`-prefixed default both read as default. |
| `CR-03` | **`--index-dir` and `--analysis-dir` have opposite precedence depending on the command.** `resolve_paths` returns `index_dir` before consulting the resolver, so the index flag wins; `resolve_index_dir` sets `explicit_analysis_dir` and skips branch 2, so the analysis flag wins. With both given, `index`/`search` write to `<B>/index/code-search` and `stats`/`symbols`/`callers`/`callees`/`facts`/`coverage` read `<cwd>/out`. Written to one place, read from another, one explicit flag silently ignored in each direction. | `cli_helpers.py:95` vs `config.py:349` | **Fixed 2026-09-01** — `apply_path_overrides` is the single entry point for both flags; `resolve_paths` no longer short-circuits. Settled precedence `--index-dir` > `--analysis-dir` > manifest, verified identical across the read and index families. |
| `CR-04` | **`--index-dir` still names two different directories depending on the command** — `<repo_root>/out` from `index`/`backfill-vectors`/`search`, `<cwd>/out` from the seven `resolve_paths` commands. This is the first review's finding 3, which `751c8b26` fixed for `--analysis-dir` by adding `.resolve()` and did not extend to its sibling flag on the same lines. | `cli.py:111`, `:203`, `:651` | **Fixed 2026-09-01** — both flags are `.resolve()`d in `apply_path_overrides`, so each names one directory on every command. |
| `CR-05` | **`--reset` becomes unrecoverable after an interrupted reset.** Reset deletes only `index.sqlite`(+`-wal`/`-shm`) and `chroma/`, never `manifest.snapshot.json` or `index.log`, which `run()` writes into the same directory. Any state where the DB and Chroma are gone but those two remain now hits the new positive-evidence clause: `Refusing to reset non-empty path with no index in it`. Reachable by Ctrl-C during the `rmtree` of a multi-GB `chroma/`, and by the common habit of hand-deleting the DB to force a rebuild. The message then blames `--analysis-dir`/`index_dir` and offers "or to be empty" as the escape — a state `--reset` itself can never produce. Treat a directory holding only known indexer artifacts as empty, or delete them as part of the reset. | `indexer.py:214` | **Fixed 2026-09-01** — "empty" now means "holds nothing but this indexer's own artifacts", honouring the manifest's configured `sqlite_file`/`chroma_dir` names. |
| `CR-06` | **The reset guard's parity comment is false.** It states `allowed_ancestors` are "the SAME two branches that `resolve_index_dir` takes, so the guard and the resolver agree by construction." They cover branches 3 and 4 only, so `--reset` always raises for both configured-`index_dir` branches: `index_dir=".legacylift"` resolves to `<repo>/.legacylift` and is refused, even though `.legacylift` is deliberately in `_INDEX_DIR_NAMES` so the name clause passes. The refusal is pre-existing; Milestone 0 promoted those branches to documented, tested, first-class precedence *and* codified the invariant as true, so the next editor will trust it. | `indexer.py:197` | **Fixed 2026-09-01** — `allowed_ancestors` covers all four resolver branches, and branch 2 is suppressed by an explicit `analysis_dir` exactly as the resolver suppresses it (Wave 3), so parity holds in both directions. |
| `CR-07` | The Milestone 0 retrospective above said "405 tests passing … +18 / +11 / +19" while `CLAUDE.md` said 408. 408 is right (`test_config.py` +13, `test_cli_smoke.py` +1; 357 + 51). | this file | **Closed** — corrected above |

**On §6 of the handoff's "known gaps", one call is worth revisiting and one claim was wrong.**
`tag-domains`, `domains` and `render-architecture` still take no `--analysis-dir`, and the reason
given was that they take no `--index-dir` either, so the asymmetry was matched rather than
widened. But they are the three commands that consume *both* stores, so after
`index --analysis-dir D:\out` the next pipeline step fails: `tag-domains` raises
`FileNotFoundError` on a missing `index.sqlite` and `domains`/`render-architecture` report
"no domains". Recommend closing the gap. The claim that those commands would **create an empty
`knowledge.sqlite` inside the client checkout is false** — all three existence-probe before
constructing `KnowledgeStore` (`cli.py:1238`, `:1404`; `domain_tagger.py:350`), which is issue #33's
fix still holding. The failures are loud, not polluting.

**What the review confirmed correct, so do not re-check it.** No silently weakened requirement in
the plan diff: the two narrowings are disclosed and evidenced (`search` dropped from the relocation
oracle, absolute `index_dir` carved out of "`--analysis-dir` overrides the whole question", tested
by name). The "twenty → eighteen" `conn.commit()` correction is accurate — all 18 cited line
numbers land on a `commit()` and `grep -c` gives 13 + 5. `monkeypatch.setattr(store_module, ...)` in
`_reopen_with_a_pending_migration` does cover every path, since both stores use
`from .migrations import …`. No second vacuous test was found. All 10 `--analysis-dir` additions and
the 5 `open_store_or_exit(..., console, analysis_dir)` sites are consistent, with no transposed
argument. All 13 `SQLiteStore(`/`KnowledgeStore(` construction sites are preceded by a
`print_resolved_path` for the directory they derive from, so **the second-empty-store hazard the
banner exists for is closed** — `CR-02`, `CR-03` and `CR-04` are now visible in the banner rather
than silent, which is the mitigation working as designed. The relocation itself is verified on
disk: no `legacylift-docs/` survives under `repos/nng-app-legacylift-analysis/legacy/`.

### Milestone 1 Steps 1–2 (2026-09-01) — shipped, plus the `CR-08` … `CR-11` code review

Step 1 (`identity.py`) and Step 2 (`anchor_key`, `entity_class`, `content_hash` on `symbols`)
shipped together with all six open Milestone 0 defects and the §6 `--analysis-dir` gap. Four
implementation agents ran, then a review-and-verify wave. **408 → 513 → 521 tests, exit 0.**

Every §3 measurement of the handoff was reproduced independently in the review wave and none
moved: migration v2 on copies of all three real indexes (0→2, counts unchanged,
`ix_symbols_anchor_key` non-unique), **all anchors recomputed through `identity.anchor_key` with
0 mismatches**, `extractors.json` at 52 entries / 36 kinds matching the authoritative table in
Step 2 exactly and the `migrations.SHIM_KIND_TO_ENTITY_CLASS` shim agreeing with it on all 42
kinds, and `other` populated where predicted (ETSPii 265, NNG app 1,471). All three production
`index.sqlite` files are still at `user_version` 0 with 12 columns; every migration test ran on
scratchpad copies.

**The `--analysis-dir` gap is closed**: all 14 commands carry the flag, and the settled precedence
`--index-dir` > `--analysis-dir` > manifest was verified to be identical across the read family
and the index family.

**Four new defects, `CR-08` … `CR-11`, all found by the Wave 3 review and all fixed in the same
wave with a probe that fails before and passes after.** The Milestone 0 lesson held again: the
suite was green at 513 with two of these live.

| # | Finding | Where | Status |
|---|---|---|---|
| `CR-08` | **The regex fallback stored CHARACTER indices in `TextRange.start_byte`/`end_byte`.** `re` matches a `str`, so `m.start()` is a character index, but the field is contracted to be a byte offset into the extractors' byte space. Inert while the bounds only drove chunking; a correctness bug once Step 2 made `store.symbol_body_text` slice `SourceText.byte_space` with them — a character index is always ≤ the byte index, so the bounds guard still passes and a **shifted body is hashed with nothing raising**. Probe: a SQL file with ten `é` before the definition hashed `'-- caf� 
CREATE PROCEDURE d'` instead of `'CREATE PROCEDURE dbo.DoThing'`. Blast radius on the three real corpora is **zero** (394 `fallback_definition` symbols, none preceded by non-ASCII) — a property of those repositories, not of the code. Note the offending line predates this work (`0f4f5d8b`); Step 2 is what made it consequential. | `extractors.py` `_extract_fallback`, 3 `TextRange` sites | **Fixed** — `_byte_offset_table`, skipped entirely for ASCII text. Distinct from the pre-existing `_char_to_byte_offsets`, which maps a *known* offset set in one pass and is the right shape for the SQL segment reconciliation; the fallback discovers its offsets while iterating and needs O(1) random access. |
| `CR-09` | **The insert path skipped the very drift guard `backfill-hashes` exists to apply.** `upsert_symbols` re-reads the file in the writer process, long after the extract worker read it — a cold index is a long pooled run with batched commits. A file edited inside that window still *fits* the stored bounds, so a body was recovered and a **non-NULL `content_hash` written for source that never produced those rows**: the precise error a migration-time backfill was rejected for. `source_file.sha256` was in hand and unused. | `store.py` `upsert_symbols` / `read_source_text` | **Fixed** — `read_source_text` takes an optional `expected_sha256` and refuses on mismatch, leaving the hash NULL for the next `index` run. The fix also exposed a fixture bug: `write_text` translates `
`→`

` on Windows, so `test_insert_path_hashes_a_symbol_with_no_byte_span` had never matched its own digest. |
| `CR-10` | **`_connect` cached the connection before the on-open migration succeeded.** `self.conn` was assigned first, so a database the guard refused stayed cached and marked open: the refusal fired once, and every later `_connect()` handed back a live connection to the schema it had just rejected. Probe: after the newer-schema refusal, the second `_connect()` read 589 symbols. Latent — no caller retries today — but a guard that holds for one call is not a guard. | `store.py:286` | **Fixed** — connect to a local, migrate, close on failure, cache only on success. |
| `CR-11` | **`count_symbols_missing_content_hash` and `symbols_missing_content_hash` disagreed on the `repo_files` join**, so an orphan symbol row is counted in `remaining_null` but never offered for hashing — a "still unhashed" warning no rerun can clear. Narrowed on probe: the FK is `ON DELETE CASCADE`, so the row is unreachable *while `PRAGMA foreign_keys` is on*. That surfaced the larger half — **`_connect()` never set `foreign_keys=ON`; only `migrate()` did** — so after `CR-01` moved migration into `_connect`, most connections ran with the cascade unenforced. | `store.py:1810`, `:286` | **Fixed** — both queries carry the join, and `_connect` sets the pragma. Two queries answering one question must agree by construction, not by relying on a pragma set elsewhere. |

**What the review confirmed correct, so do not re-check it.** The `SourceText.byte_space` choice is
load-bearing rather than defensive: on an invalid-UTF-8 file (raw 67 bytes, byte space 69) raw-byte
slicing yields `'ass Alpha {…'` where the byte space yields `'class Alpha {…'`. The byte/line
fallback in `symbol_body_text` is likewise real — **exactly 1,739 of 16,272 NNG-app symbols carry
`end_byte == start_byte` by construction and all 1,739 hash correctly**, giving 16,272/16,272. The
insert and backfill paths agree byte for byte because both slice through the one shared
`symbol_body_text` over a `SourceText` built the same way. `new_ulid` holds all three unspecified
properties: 32,000 identifiers across 16 threads all distinct, a clock stepped 60 s backwards does
not regress the sequence, and the random-space overflow branch bumps the timestamp. Six processes
racing the on-open migration succeed on both the 589- and the 16,272-symbol index. All 36 literal
`Symbol(...)` test fixtures carry an `entity_class`, and every one matches what the shim would
assign. The `--reset` guard's positive-evidence and name clauses catch cases the ancestor clause
does not.

**One thing left deliberately un-fixed.** No `busy_timeout` is set on either store. It costs
nothing today — the v2 migration is fast enough that six concurrent openers never contend — but a
slower future migration would surface as `CR-01`'s "migration could not be applied" error on a
reader that merely waited too long. Recorded rather than fixed because the right value is a guess
until a migration is slow enough to need one.

### Milestone 1 Step 3 (2026-09-01) — the GR tables, shipped

Eleven tables, `gr` at forty-two columns, plus `gr_body_schemas.py`. **521 → 588 tests, exit 0**
(51 in `tests/test_gr_schema.py`, 16 in `tests/test_gr_body_schemas.py`). Five things worth
carrying forward:

**The step needed no migration entry, and working out why is the useful part.** The instinct on
reading "Milestone 0 built a migration mechanism, now add tables" is to add a
`KNOWLEDGE_MIGRATIONS` version 2. That would be wrong twice over: `migrate()` already brings an
existing `knowledge.sqlite` to the current baseline on every open, and `_baseline`'s own docstring
says so — "every table that exists today is created by the owning store's `migrate()`". So the
mechanism's first *real* customer is still ahead of us, and the first person to add a GR column is
the one who exercises it. Milestone 0 remains untested by production use, which is worth knowing
rather than assuming.

**`gr_run.complete` found a better home than a writer.** The plan defines it as
`not_accounted_for IS NOT NULL AND not_accounted_for = 0` and warns at length that storing a zero
for an unmeasured run is the failure mode. A SQLite generated column removes the writer entirely,
so the definition cannot be got wrong and `gate_excluded`'s "leaves `complete` untouched" is
structural. The cost is one quirk, pinned by a test: **`PRAGMA table_info` omits generated
columns.** Anything enumerating `gr_run`'s columns must use `PRAGMA table_xinfo`.

**The tier-1 dedupe discriminator had no producer, and now does.** Step 3 says the tier-1
discriminator is "the canonical form of the structured body" and never says what canonical means —
a `json.dumps` over the incoming payload would move the key when the extractor reordered its keys,
which is the silent-merge-failure class this plan has found seven times. `canonical_structured_body`
is the one producer: model field order, sorted keys, no optional whitespace, aliases preserved.
This is the ninth round's interface theme showing up exactly where it predicted — at the point
where a value stated in one step has to be reached from another.

**One real defect shipped in the first commit of this step and was caught while writing the handoff
notes, not by the fifty tests.** `gr_id TEXT PRIMARY KEY` **admits NULL**, and admits *two* NULLs,
because in a SQLite rowid table a PRIMARY KEY column that is not `INTEGER PRIMARY KEY` is not
implicitly `NOT NULL` and the unique index treats NULLs as distinct. So the store's immutable
surrogate identity — the single most important schema decision in the plan, by its own words —
could have been absent on a row, twice over. `gr_run.run_id` had it too. Both now carry an explicit
`NOT NULL` with a test that fails without it (`14a818e5` shipped the hole; the follow-up closed
it). Two things to take from it rather than one. The obvious one: **`PRIMARY KEY` is not `NOT NULL`
in SQLite unless the column is `INTEGER PRIMARY KEY`** — check every other `TEXT PRIMARY KEY` you
add. The less obvious one is about *how* it surfaced: it came out of enumerating the NOT NULL
columns for a handoff note and finding the count off by one against the DDL I had just written. The
plan's own eighth-round lesson is that a rule can be internally consistent and still not
executable, and the fix is to walk a concrete input through it by hand; this is the same lesson for
a *schema* — the fifty tests all inserted a well-formed `gr_id`, so none of them ever asked whether
one was required.

**Two `CHECK`s in the plan text are unsatisfiable as literally written, and both were already
flagged as such.** `pattern NOT NULL` and the `state = 'draft' OR rule_class IS NOT NULL` reading
of §S1.7 item 1 each make a legitimate row unstorable — the first a `draft` row from a bad
extraction, the second a *rejected* one. The plan's scoped forms are what shipped, and the second
omission is now recorded at the Step's heading, since the plan never stated it explicitly and an
implementer reading SPEC-1 alone would add it.

### Milestone 1 Step 4 (2026-09-01) — the validator and the gate, shipped

`gr_validator.py` (28 checks, the shared keyword matcher, `split_slots`), `gr_state.py`
(`ALLOWED_TRANSITIONS`, `set_state`, the gate), `GRRecord` and `Finding` in `models.py`, and four
GR methods on `KnowledgeStore`. **588 → 706 tests, exit 0** (83 in `tests/test_gr_validator.py`,
35 in `tests/test_gr_state.py`).

**Five places this plan under-specified, each decided in code and recorded so none reads as
drift.** They are all the ninth round's interface theme — a rule stated in one place that has to
be reached from another — and every one surfaced in the first hour of writing the step, exactly
as that round predicted.

1. **"The six Figure-1 patterns" is seven.** `Interfaces and Dependencies` annotates
   `StatementSpans.action` as "the six Figure-1 patterns only", but §S1.4's two tables carry ten
   patterns of which three are the D5 deviations (`D-COMPUTE`, `D-INFER`, `D-CONST`), so seven
   follow Figure 1. `FIGURE1_PATTERNS` holds seven and a test asserts `7 + 3 == 10`. A literal
   six would have left one pattern in neither set.
2. **`StatementSpans` needed a sixth field, `degraded`, and `subject` had to become nullable.**
   The sketch types `subject` as `tuple[int, int]`, but Step 4's own degradation rule says a
   keyword-absent row has no `[Subject]` span — so the two disagreed. Worse, a caller
   re-deriving "was this degraded?" from `subject is None` would conflate *no template* with *an
   empty subject*, which is precisely what `V-SLOT-01` exists to distinguish, and the
   not-evaluated rule then fires on the wrong rows. The flag carries the state explicitly.
3. **A non-NULL `pattern` degrades when the keyword is present but *ambiguous*, not only when it
   is absent.** Step 4 phrases the rule as "whose keyword cannot be located", which reads as
   absence — but `Validation and Acceptance` requires §S1.10 **#6** (*An order always must have a
   customer*, one keyword from each class, under a non-NULL `pattern`) to emit all three `V-SLOT`
   findings as `evaluated = 0`, and #6's template keyword `must` **is** present. So the
   implemented condition is *exactly one rule-keyword occurrence, and that occurrence is one the
   pattern's template accepts*. Both readings satisfy "one finding, not four"; only this one
   satisfies the stated test.
4. **A NULL `rule_class` leaves `V-KW-01` and `V-KW-02` not evaluated too**, not only the three
   `V-SLOT` checks. Both are written against "its `rule_class`'s set" and there is no set —
   `evaluated = 0` is the honest encoding, and it is the same absent-versus-real rule the column
   was added for. It changes no severity, no count, and no gate outcome (`V-CLASS-01` blocks
   approval on that row regardless), so it is an implementation note rather than an amendment.
5. **`set_state` needed a `superseded_by` parameter the `Interfaces` signature omits.** Step 8
   requires `superseded` to record its successor on the record being superseded, and the
   five-parameter signature has nowhere for it. Added keyword-only, and a move to `superseded`
   without it is refused rather than writing a state whose `superseded_by` points nowhere.

**One deliberate departure from §S1.10's verdict column, and it is the plan's own instruction
that produces it.** §S1.10 #5 (*The system shall validate the order*) lists `V-SLOT-02` — "the
system" — in its verdict. Under Step 4's degradation rule, with a non-NULL `pattern` whose
keyword is absent, all three `V-SLOT` checks are not evaluated, so `V-SLOT-02` does **not** fire
as an `ERROR`; `V-KW-03` does. The ExecPlan's acceptance criterion states this outcome explicitly
and §S1.10's verdict column is illustrative of what is wrong with the sentence rather than a
finding list. Recorded rather than resolved, because reinstating the other reading means
guessing a boundary the statement never marked.

**What the tests are driven from, and why it is not the plan.** §S1.10's ten worked examples plus
one conformant statement per pattern from §S1.4's own template tables. That is the eighth round's
lesson applied rather than restated: the superseded keyword-anchored split was internally
coherent, cited §S1.4 correctly, and fired two `ERROR`s on #3.
`test_spec_s1_10_conformant_examples_produce_no_error` is the single assertion that fails under
it.

**Two measurements taken outside the suite, because a green suite is not evidence.** All
twenty-eight identifiers were proved **reachable** by a probe that constructs a triggering record
per check — a check that can never fire is the seventh round's writer-reachability defect one
level down, and the four-way partition would not catch it. And ten plausible conformant
statements spanning all ten patterns (rental, ordering, claims and billing vocabulary, not
SPEC-1's own examples) produce **zero** blocking `ERROR`s, with every slot span correct by
inspection; the only `WARN` on any of them is `V-ENF-03`, which is review progress by design. The
false-`ERROR` rate is the number that matters here, because a false `ERROR` makes a record
permanently un-approvable — the same failure §S1.6's two mandatory carve-outs exist to prevent.

**Three checks are heuristics and are documented as such at their implementation**, because
§S1.6 leaves them to the implementer and a later reader will otherwise take them for
specification. `V-KW-07` is `may` with no `only` (the plan's own stated heuristic).
`V-SING-01`'s conjoined-action test is "the token after `and` is not a function word **and** the
token after that is a determiner", which correctly separates *recalculate the balance and notify
the customer* from *record the pickup branch and the drop-off branch* — deliberately biased
toward under-firing, since it is an `ERROR`. `V-VAG-09` looks for a digit or a part designator
within the same clause and thirty characters, same bias.

**`gr_finding`'s writer is `KnowledgeStore.replace_gr_findings` and it does not commit** — Step
5's `refresh_gr_derived_sql` runs inside whatever transaction its caller already has open, so a
commit here would break ingest's single-transaction contract before that step is written. The
one seam left open in `set_state` is the refresh pair itself, marked in the source.

**The "only writer of `gr.state`" claim is now executable.** `set_state` holds all the policy and
`KnowledgeStore.apply_gr_state` is a mechanical writer; `test_set_state_is_the_only_writer_of_gr_state`
scans the package source and asserts that no other module writes the column and that nothing but
`gr_state.py` calls the writer. Step 9's `import_records` is the declared exception and will have
to be added to that assertion deliberately, which is the point of writing it as a set rather than
as a prohibition.

### Milestone 1 Step 5 (2026-09-02) — FTS5, the `gr_statements` collection and the refresh pair, shipped

`src/legacylift_search/gr_refresh.py` (the pair, plus `describe_vector_shortfall`,
`open_gr_collection`, `open_index_store_if_present`), `gr_fts` in `_migrate_gr_tables`, six new
`KnowledgeStore` methods, `upsert_texts`/`count`/`delete_ids` on `ChromaVectorStore`,
`RefreshResult` and `EmbedResult` in `models.py`, and the `index_dir` → `base_dir` rename.
**706 → 734 tests, exit 0** (28 in `tests/test_gr_refresh.py`).

**Both seams Step 4 left open are closed.** `set_state` calls the full pair — `refresh_gr_derived_sql`,
`store.commit()`, `refresh_gr_vectors` — and `refresh_gr_derived_sql` builds `leaked_terms` from
the requirement's own cited files, so `V-STY-03` runs its shipped check wherever an index exists.

**One refinement to the declared interfaces, made deliberately and worth knowing before Step 8.**
`Interfaces and Dependencies` declares `refresh_gr_vectors(store, gr_ids)` and
`set_state(store, gr_id, to_state, reviewer, note)`, and neither signature can reach an embedder —
but the vector half needs one, and `set_state` is one of its six callers. So both gained a
keyword-only `embedder: Embedder | None = None` (and `set_state` two more, `index_store` and
`repo_root`, threaded through to the SQL half). **`None` is a supported degraded success, not an
error**: the state change lands in SQLite and `gr_fts`, the record's vector metadata stays behind,
and `requirements reindex-vectors` is the recovery. Making the embedder *required* would have made
an unreachable embedding provider a reason a human's recorded judgement fails, which inverts this
step's own degradation rule. `refresh_gr_vectors` also takes an optional already-open `collection`,
so ingest opens one collection for a whole run rather than one per record.

**`set_state` drops the `EmbedResult` and that is a decision, not an oversight.** Its declared
return type is `None`, and the question a reviewer actually has is "is the collection behind",
not "did this one record miss" — which is what `describe_vector_shortfall` answers, against the
whole collection, at the moment stage two would otherwise return zero candidates.

**The orientation block's five measured mechanics all held**, including the one that matters most:
chromadb 1.5.9 does silently drop a `None` metadata value, so `upsert_texts` coerces to `''` and
`test_a_null_subject_is_stored_as_empty_string_not_dropped` asserts both that the key survives and
that `where={"subject": ""}` matches it — the coerced value has to be *filterable* or `''` is a
hole rather than an encoding of "absent". Two of its figures were undercounts and are corrected
here: the rename touches **sixteen** construction sites, not five, because eleven of them are in
tests; and `chroma_dir` is read by **five** sites, not three (re-counted by grep, and
`pending/deferred-small-items.md` entry 2 is corrected to match — its heading said two).

**`apply_gr_state` commits, which changes where the pair's commit boundary sits in `set_state`
only.** The contract is unchanged — SQL durable before any vector is written — but in this one
caller the state UPDATE has already committed by the time the pair runs, so the SQL half opens and
releases its own savepoint. `refresh_gr_derived_sql` called with no transaction open is
self-committing (measured in the orientation block); that is benign and is **not** the contract,
and ingest's single run-wide transaction is still the shape everything else is built for.
`test_refresh_runs_inside_the_callers_transaction_and_rolls_back_with_it` is the executable form.

**Three of Step 5's five acceptance criteria could only be written at unit level**, and each says
so in its own docstring so the step that supplies the command knows what is still owed: a
`set-field` edit reaching search, ingest-with-no-embedder followed by `reindex-vectors`, and the
stage-two shortfall report all need CLI surfaces that are Step 8's. What *is* proved end to end at
this layer is the contract each of those rests on — `gr_fts` forgets old text on a rewrite, a
state change reaches the vector metadata while a same-state no-op re-embeds nothing (asserted with
a counting embedder), and a short collection produces words naming `reindex-vectors` rather than a
silent zero.

**Three things cost time and will cost it again**, all recorded in `Concrete Steps`: Chroma tests
need `ignore_cleanup_errors` on Windows; `gr_citation.provenance` is `'extracted'`, not
`'extractor'`; and a hand-built `Symbol` needs one of `identity.ENTITY_CLASSES`' seven values, so
a plausible-sounding `operation` is a validation error — which is Step 2 working as designed.

### Milestone 1 Step 6a (2026-09-02) — the extractor notation, anchors, ownership and subjects, shipped

Built as **five parallel units** after `models.py`'s ten remaining models landed alone as the
shared contract. `.claude/skills/code-modernization/` (three files), `citations.py`, `gr_fields.py`,
`gr_subject.py`, plus `gr_dataflow.py` and `gr_export.py` from Steps 7 and 9 in the same wave.
**734 → 822 tests, exit 0.**

**What an analyst can do that they could not before:** nothing yet — this wave has no CLI surface,
which is Step 8's. What *changed* is that the extraction agents now author SPEC-1 notation rather
than Given/When/Then alone, and every input the merge needs to key a rule exists: resolved
anchors, span hashes, the ownership partition and a derived subject.

**Three corrections the source forced on the plan's own text**, each recorded in the Decision Log:
`gr.modality` is the KAOS pair and not SPEC-1's modal keyword; `ruleClass` must be nullable because
§S1.2 forbids guessing it; and "the six Figure-1 patterns" is seven in the two places an
implementer reads.

**What surprised us.** The prose-versus-code assertion trap (`Surprises` finding 7) appeared twice
in this wave alone and cost one module its clearest docstring before anyone noticed the test was
at fault rather than the comment. And the whole-file citation case — a bare path resolving to the
*smallest* declaration in the file — was found by building the input, not by reading the rule that
produced it, which is the third time in this plan that a hashed value's edge case has only shown
up when someone constructed it.

### Milestone 1 Step 6 (2026-09-02) — the merge, and the dedupe keys, shipped

`gr_keys.py` (both keys, the discriminator tier selection), `gr_ingest.py` (the merge), eighteen
new `KnowledgeStore` methods, and two constants promoted to public in `identity.py`.
**822 → 870 tests, exit 0** (11 in `tests/test_gr_keys.py`, 37 in `tests/test_gr_ingest.py`).

**The headline is that neither dedupe key had a producer** (`Surprises` finding 2). Every layer
that reads a key existed — the gate, the refresh, the merge's own description — so the suite was
green with the keys permanently absent. This step therefore delivered both the merge and the thing
the merge merges on.

**What an analyst can do that they could not before:** still nothing directly, for one more step —
but `ingest_extraction` is callable, so re-running extraction now *merges* rather than replacing,
and every number Step 10 must report is computed and carried on `IngestResult` rather than waiting
to be derived by a reporting command.

**What surprised us.** Two properties had to be established by probe rather than by inspection,
and both are ones a reviewer would have signed off on by reading: that a requirement whose every
citation is unreadable keys **differently** from one with no citations at all (tier 2 versus tier
3, which is the whole reason `ch0:none` is a sentinel rather than `''`), and that a hole in the
hash set keys differently from a dropped member. Reading the formula tells you neither; running it
does.

**Two gaps in the plan this step had to fill rather than follow**, both in the Decision Log: the
pattern-free statement fallback's `[Subject]`, which was never specified, and stage two's semantic
threshold, which does not exist anywhere in the plan and which stage two cannot run without. The
second is the one to carry forward — it is an invented number governing the under-merge safety
net, it is metric-dependent, and nothing pins the metric.

**What remains in Milestone 1:** Step 8 (the fourteen `requirements` commands, the only remaining
work in `cli.py`), Step 9's two commands, and Step 10's three measurements — which are not a
coding step but a real pipeline run, and the same run that discharges Step 6a's live acceptance
check and Milestone 0's one deliberately-open criterion.

### Milestone 1 Step 8 (2026-09-02) — all fourteen `requirements` commands, shipped

Two commits: `72464baf` (Wave C1, the foundation, one owner) and `41023c43` (Wave C2, four parallel
units on disjoint files). **870 → 965 → 1,131 tests, exit 0.** All fourteen commands verified
registered under one `requirements` group by probe, not by reading the source.

**What an analyst can now do that they could not before — which is the whole point of this step.**
Every command in the Purpose section's opening list now runs. Requirements can be listed and
filtered, shown with their citations and findings, searched by keyword and by meaning, moved through
the lifecycle by a named human, corrected by hand, exported to a git-committable JSONL file and
imported back. The store stopped being a library and became a tool. Nothing in Milestone 1 is
unbuilt except Step 10's measurements, which are a pipeline run rather than code.

**The design rule that made the wave cheap: every command wires a shipped function and adds
nothing.** `set-state` is `gr_state.set_state`; `set-field` is `gr_setfield.set_field`; `ingest` is
`gr_ingest.ingest_extraction`; the transition graph, the approval gate, the merge, the refresh pair
and the dedupe keys are all reached rather than restated. This was not tidiness — a second copy of
a rule in the CLI is the sixth review round's stale-copy defect, whose whole finding was that a rule
stated in several places gets corrected in all but one of them and the survivor is an instruction to
build the wrong thing. The commands own only presentation, flag handling and exit codes.

**Four defects in shipped code, found by units that could not fix them.** Each was found by an
agent reading a module to build against it — the fourth consecutive wave where that, and not the
test suite, is what found the defects. **Their disposition was decided deliberately and is recorded
here so nobody re-triages it:** the first two are fixed in the pre-Step-10 wave below, because
neither is on Step 10's path but both are cheap and the first is this plan's own recurring class
sitting inside Step 9. The second two are **deferred to `pending/deferred-small-items.md` entries 4
and 5**, because each needs a design decision rather than a patch and neither is exercised by
Step 10.

1. **`gr_export.ImportResult` cannot report a refused downgrade — FIXED 2026-09-02.**
   `_import_one` silently reverted `state`, `reviewed_by`, `reviewed_at`, `review_note` and
   `superseded_by` to their stored values when `_is_state_downgrade` fired without
   `--allow-downgrade`, and nothing counted it. So `rows_changed_state == 0` meant either *"the file
   agreed with the store"* or *"every state change in the file was refused"* — two different facts
   sharing an encoding, and the command could not tell an analyst that three approvals were
   protected. **The recurring absent-versus-real class, the ninth instance, inside Step 9's own
   code.** The fix carries the **records** rather than a count — `refused_downgrades` with each
   `gr_id`, `stored_state`, `incoming_state` and `stored_reviewed_by`, and the count as a *derived
   property* so the two cannot disagree — because the guard defends a named human's judgement and
   both resolutions available to an analyst need the `gr_id`. A count answers "how many" and cannot
   be acted on. `stored_reviewed_by` stays NULL when none was recorded rather than flattening to
   `''`, which would be the same collapse one field down. **The durable half is still open** as
   `deferred-small-items.md` entry 6: `gr_import` stores only `rows_changed_state`, so the database
   keeps the ambiguity the command's own output no longer has — and closing it needs the first GR
   *column* migration, which Step 3 deliberately left as the line where its free-table-addition rule
   stops.
2. **`import_records` has no `embedder` parameter — FIXED 2026-09-02.** It called
   `refresh_gr_vectors(store, touched)` with none (at `gr_export.py:662`, not the `:645` this plan
   first recorded — the usual drift), so `import`'s vector half degraded unconditionally while every
   other write path threaded the CLI-resolved embedder through the Step 5 pair. `import_records` now
   takes `embedder`, `index_store` and `repo_root`, all defaulting to `None`, and `import` takes
   `--embedding-provider`. **The last two close the same defect in the other half of the same call
   pair**, which nobody had noticed: `refresh_gr_derived_sql` was hard-coded `None, None`, so
   `V-STY-03` always ran on its morphological half alone on this path. One symptom found, two
   instances fixed. **The obvious follow-up was then done and came back clean:** all six writers of
   the refresh pair — `gr_ingest`, `gr_export`, `gr_rederive`, `gr_setfield`, `gr_state` and the
   merge — now pass `index_store` and `repo_root` through, verified by grepping every call site
   rather than by assuming, and `gr_export.py` was the only one that had not. Worth recording as a
   *negative* result, because "one caller of a six-caller function got this wrong" is exactly the
   shape that usually means several did.
3. **`gr_state.set_state` returns `None` and deliberately drops its `EmbedResult`**, so `set-state`
   cannot report an embed that fails *after* the embedder builds — a dimension mismatch, or a
   provider that 500s. It can only report the case where no embedder could be built. `set-field` has
   no such gap, because `SetFieldResult.embed` carries it. **Deferred** — `deferred-small-items.md`
   entry 4, which also records that the drop is deliberate and argued at the call site, so the
   residue is narrower than "cannot report a degraded embed": `stats` and stage two both run the
   shortfall check, so the staleness is detectable and one command recovers it.
4. **`describe_vector_shortfall(gr_count, collection_count)` takes two `int`s**, so "no collection
   could be opened at all" has no representation in its contract. It had to be handled at the CLI
   layer, where a null shortfall carries a separate `shortfall_measured` boolean so it is never read
   as *no* shortfall. **Deferred** — `deferred-small-items.md` entry 5. Note what makes it worth
   writing down: this function exists *specifically* to prevent an instance of the
   absent-versus-real class one layer up, and its own docstring says so, yet its signature cannot
   express the same distinction about itself.

**Two acceptance criteria could not be satisfied as written, and both are worth fixing in the plan
rather than in the code.** The `V-SLOT-01` criterion asks for a finding "with a `span` pointing
into" the edited wording, but the shipped validator emits a record-level finding with `span == ''`
for a *missing* `[Subject]` — when the slot is absent there is nothing in the text to point at, and
a span could only exist for a slot that is present but wrong. And the sharpest available `stats`
probe — planting a real value spelled `none` to falsify a `COALESCE(col, 'none')` — is unbuildable,
because **every one of the twelve groupable columns carries a `CHECK`** that forbids it. The
encoding was falsified instead: JSON must carry a real `null`, and the text sentinel must not appear
in JSON. Record both, because the next agent will reach for the same planted row.

**Three traps in the shipped code that cost iterations and will again.** The `hash` embedding
provider is built at `manifest.embedding.dimension` = **1024**, not `HashEmbedder`'s own default of
64 — a collection seeded at 64 fails `validate_dimension` and the test then measures a dimension
mismatch instead of what it claims. `EmbeddingConfig.provider` defaults to `qwen3`, a model load, so
every test touching the vector half must pin `hash` explicitly. And
`KnowledgeStore.intra_run_collapse_count` counts **offers, not collapsed requirements**: two offers
landing on one `gr_id` returns 2, not 1. That last one is carried into `Progress`, because it is one
of Step 10's three mandatory measurements and the name reads like the other reading.

**The absent-versus-real class produced one more instance during the wave, one layer further out
than any previous.** Passing `index_sqlite_path=None` when the index is absent — which is what the
contract asks for — leaves `IngestResult.index_sqlite_path` as `None`, so the ingest report printed
`index: NOT present at None`. The acceptance criterion requires the banner name the **resolved**
path, precisely because a mis-resolved path under Milestone 0's new output layout and a repository
that genuinely was never indexed produce identical corpora and call for opposite fixes. The fix was
to thread the resolved path into the report separately from the result, so `index_present: false`
and *where it looked* are both available. Ten instances now, and the generalization keeps widening:
this one was not a column, not a derived count and not an outbound encoding, but **a parameter whose
`None` correctly means "absent" and which a reporting layer then had nothing else to print.**

**What the parallel shape cost and bought.** Five agents, one checkout, zero conflicts — the
foundation landed alone first, exactly as Wave A's `models.py` did, and the four command units then
owned one module and one test file each. The one thing the foundation had to get right beyond its
own code was the file-ownership table, which lives in `cli_requirements/__init__.py`'s docstring and
is asserted by a test, so the four units could not disagree about who owned what. What it cost is
that `PR-47`'s full sequence — a degraded ingest, then `reindex-vectors` populating the collection
with no re-extraction — spans two units and so is proved only in halves. It needs one cross-unit
test or the Step 10 run.

**What remains in Milestone 1: nothing — this paragraph is history, kept because it names `PR-47`'s
shape.** Step 10's three measurements were *this* sentence's answer and were taken on 2026-09-10;
Phase 4 (merge acceptance), Phase 5 (`A3`) and Phase 6 (`rules_candidate`) followed the same day.
`PR-47`'s full sequence, which this paragraph correctly said was proved only in halves at the time,
was closed by Phase 5: the Phase 3 ingest reached the embedder and so was never degraded, and Phase
5 supplied the degraded half by removing the credential for one command.

### Milestone 1.5 pre-flight, measured 2026-09-10 — every parse target verified, and one plan error corrected

Taken immediately after Phase 6, read-only, against the two baseline files on disk. **Nothing here
is a Milestone 1.5 result** — it is the parser's ground truth, measured so the first session of that
milestone does not spend a pass rediscovering it. The one thing that changed a plan statement is the
path-prefix correction, and it is struck in both places it appeared.

**Both baselines are present.** `analysis-original/customer.ple.nng.app/BUSINESS_RULES.md` (838,585
bytes, 2,118 lines, dated Jun 23) and
`analysis-semantic-search-enhanced/customer.ple.nng.app/BUSINESS_RULES.md` (416,609 bytes, 4,902
lines, Jul 6). Both are under the `.gitignore:92`-ignored tree, so this remains impossible on a
fresh clone.

**Every parse target the plan states verifies exactly.** Nothing needed adjusting:

| plan says | measured | |
|---|---|---|
| P0 `###` cards | **55** | `## P0 — Confirmed critical rules (55, two-judge panel)` at line **24** |
| Catalog starts | line **710** | `## Full rule catalog` |
| Catalog is four sub-tables | **4** | `### Validation (424)` @712, `### Calculation (57)` @1141, `### Lifecycle (185)` @1203, `### Policy (94)` @1393 |
| Sub-table counts sum | 424+57+185+94 = **760** | ✓ |
| `grep -c '^|'` over 710–1491 | **768** | ✓ — 768 − 4 separators − 4 header rows = **760** data rows |
| **Integrity check 1** | 55 + 760 = **815** | ✓ |
| **Integrity check 2** | Summary − catalog per category = 17 + 30 + 7 + 1 = **55** | ✓ — Summary block is one line, **line 18**: `By category: Validation 441, Lifecycle 215, Policy 101, Calculation 58.` |
| BASE-ENH `####` cards | **470** | ✓, and **zero** `###` headings, so one parser suffices |

**The correction: neither baseline's citation paths carry a prefix.** Census over every citation in
both files — 1,038 backticked in BASE-ORIG, 470 markdown-link in BASE-ENH:

    BASE-ENH   470 citations: no prefix (code-root relative) 470
    BASE-ORIG 1038 citations: no prefix (code-root relative) 1038

Zero `repos/`, zero `legacy/`, zero `./`, zero absolute. **This is the same shape as
`gr_citation.relative_path`, so the join key needs no path surgery** — and the plan said twice that
it did. Both statements are struck where they stood.

**The layer census, which corroborates §S2.6's coverage finding from a new direction.** Top-level
segment of every citation:

| | BASE-ORIG | BASE-ENH |
|---|---|---|
| `ple-web` | **500** | 40 |
| `ple-services` | 261 | **349** |
| `ple-persistence` | **216** | 17 |
| `ple-model` | 61 | 61 |
| `ple-web-api` | 0 | 3 |

**This is what "BASE-ORIG's advantage is breadth" looks like at citation level**: it is a `ple-web`
and `ple-persistence` corpus, BASE-ENH is a `ple-services` corpus, and they agree almost exactly on
`ple-model` (61 each). It also makes §S2.4 rule 6's triage advice directly actionable — a BASE-ONLY
finding in `ple-web` or `ple-persistence` is a likely genuine coverage gap — and it predicts where
NEW will look thin, since NEW's own new-file additions in Phase 6 were heavily `ple-web` and
`ple-services`.

#### Two parser hazards, both measured, and the second one is a silent wrong answer

**1. Reuse `citations.parse_citation` — it already handles both baselines.** Run over every capture
with `strict=True`: BASE-ORIG's 1,038 raw captures expand to **1,172 triples with 0 strict
rejections**, and BASE-ENH's 470 to **528 triples, also 0 rejections**. The expansion is real and
required: **109 BASE-ORIG citations carry a comma-separated range list** (e.g.
`WebflowExceptionHandler.java:30-65,95-107`), which is exactly the class `parse_citation` was fixed
for on 2026-09-08 as entry 11. A hand-rolled baseline regex would collapse each of those to one
range and under-match the join. **Do not write a third citation parser.**

**2. But `parse_citation` silently mis-parses the multi-FILE class, and there are 47 of them.** A
BASE-ORIG citation like

    ple-persistence/.../AbstractDao.java:201-234; ple-persistence/.../SecurityRoles.java:8-12

comes back, in **both** strict and lenient mode, as a **single** triple whose path is the entire
string up to the last colon and whose line numbers are the **second** file's:

    ('ple-persistence/.../AbstractDao.java:201-234; ple-persistence/.../SecurityRoles.java', 8, 12)

**This is the same defect class the plan already records as fixed** — "the extractor writes **two
files in one `source` string**, which `rpartition(':')` turned into one citation with a bogus path
carrying the *second* file's line numbers". That fix was made **in the extractor prompt**, so the
extractor stops emitting the shape; it did nothing to the parser, and it can do nothing for a
baseline that has been on disk since June. **47 of BASE-ORIG's 1,038 citations (4.5%) will silently
produce a bogus path and the wrong line range**, which the join will then score as BASE-ONLY. Split
on `;` — and on a comma that separates two *paths* rather than two ranges — **before** calling
`parse_citation`, and assert the split count.

**The distinction that matters when writing that splitter:** a comma inside a citation is a range
list 109 times and a file separator some smaller number of times, so it cannot be split on blindly.
The discriminator is whether the piece after the comma contains a `/` or a `.` extension. This is
also why the count to assert is triples-per-rule, not captures-per-rule.

**One reading worth carrying into the write-up.** 1,038 backtick captures for 815 BASE-ORIG rules is
**not** 1.27 citations per rule — the P0 cards cite in prose as well as in the metadata line, so the
capture set is a superset of the rule-citation set. Attribute captures to rules during the parse
rather than counting them globally, or the distinct-files-cited figure for BASE-ORIG will not
reproduce §S2.3's stated **327**.

### Step 10 Phase 6 (2026-09-10) — `rules_candidate` = **211 of 435**, and the semantic half fires for the first time

**The deliverable.** A second four-round extraction (`wf_fe5c5435-2db`) over identical code, at
identical settings, ingested into a **copy** of the store per the settled decision:

    rules: 435 offered = 66 new + 158 merged + 211 candidate; 3 rejected by the panel
    rows inserted: 277 (new + candidate)     merged with no value change: 0
    merge candidates raised: 374 [drift=183, range_overlap=152, semantic=39]
    intra-run collapse: 114                  citations: 435 seen, 277 inserted
    anchor resolution: file=4, symbol=430, unresolved=1
    subject provenance: derived=434, llm_named=1     discriminator tiers: 1=93, 2=342
    derived SQL: 368 refreshed, 314 findings written, 0 forgotten
    vectors: 368 embedded, 0 skipped, 0 deleted                            exit 0

**`rules_candidate` = 211, which is 48.5% of the offers — the key-instability figure Step 6 asked
for, and it is large.** Only 158 of 435 offers (36.3%) matched an existing requirement on the exact
`dedupe_key`; 211 matched on the anchor-only key but disagreed on the tier-1/tier-2 discriminator,
and 66 matched nothing at all. **Read that as a property of the extractor, not of the store**: an
anchor-only match with a discriminator mismatch is exactly what the two-tier key exists to detect,
and every one of the 211 was inserted *and* queued as a review pair, which is the designed
behaviour. The extractor's `ruleClass`/`pattern` and statement text move enough between two runs
over unchanged code that **fewer than two in five offers key identically**.

**`rules_new` = 66 is not a merge defect, and the softer criterion was applied rather than assumed.**
The runbook's test is whether the same rules also fail to appear in `requirements list --candidates`.
59 of the run-2 rows raised no candidate pair at all, and **22 of those cite files run 1 never
cited once** — `PoigroupAction.java`, `LegalEntityWizardAction.java`, `PartyService.java`,
`SecurityAdvice.java`, `LeskeyAssignerDao.java` and seventeen more. They are new *code coverage*,
not failed merges, which is the expected consequence of a corpus that four rounds never exhausted:
round 4 of this run still produced 101 new rules.

**The cited-file set widened, which is the axis Milestone 1.5 actually requires.** 117 real files →
**140** (+23), against BASE-ENH's 148. Distinct citation *paths* went 118 → 142, but **two of the 142
are prose smuggled into the `relative_path` column** (445 and 459 characters, one per run), so the
real-file figures are 117 and 140. This also refines the frozen data point: its parenthetical "116
if the one prose-citation rule's four unresolvable paths are excluded" is the count of *resolvable
paths*, while **117 is the count of real files** — the two readings differ by one and both are
correct for what they measure.

**The prediction fired: `semantic` merge candidates exist for the first time.** 39 were raised, and
all fourteen that survive in the store carry a non-NULL `similarity` between **0.7422 and 0.9391**.
Every one is a **cross-run pair** — a run-1 `gr_id` against a run-2 `gr_id` — which is what the
semantic half was built for and what neither a first ingest nor a re-ingest could ever produce.
Phase 5's harness predicted "roughly 18 novel pairs at `SEMANTIC_DISTANCE_MAX = 0.35`" and the
observed raise count was 39, so the harness was **conservative by about a factor of two** rather
than wrong in direction. **Zero would have been worth investigating; this is not.** Both defaults
stay unchanged, now on evidence from a run where the half actually executed.

#### Two findings the handoff did not predict, both measured

**1. The ingest banner's per-reason candidate tally cannot be reproduced from the store, and the
disagreement destroys similarity scores.** The banner reported `drift=183, range_overlap=152,
semantic=39`; the store holds `drift=183, range_overlap=177, semantic=14`. The totals agree at 374
and the discrepancy is exactly 25 rows in each direction. The mechanism was confirmed by probe, not
by arithmetic: `record_gr_merge_candidate` treats the *pair* as the primary key, and on a second
raise of an existing unresolved pair it **UPDATEs `reason` and `similarity` and returns `False`**,
so `_raise_candidate` never counts it. 25 pairs were therefore inserted by the semantic half
carrying a real similarity score, then re-raised structurally later in the same run, which
overwrote `reason` to `range_overlap` **and `similarity` to NULL**. The probe raises one pair twice
(`semantic`/0.91, then `range_overlap`/NULL) and shows the row ending as `range_overlap`/NULL with
the insert-only return value `False`. Two consequences worth stating separately: a similarity score
the semantic half computed is **silently discarded** whenever the structural half also finds the
pair, and no query of the store can reproduce a banner a reader might reasonably trust. Filed as
`pending/deferred-small-items.md` entry 17. **Not a correctness defect for merging** — stage two
never merges, and every one of the 374 pairs is queued for review either way — which is why it is a
small item rather than a milestone blocker.

**2. The merge's field churn is not the predicted cosmetic `updated_at` diff — it is a wholesale
text replacement, and it is correct.** The handoff predicted a Phase 6 export diff confined to
`updated_at` on 48 rows, "cosmetic; do not let it look like data loss". Measured, on a field-level
diff of two exports from the copy either side of the ingest: **91 of 379 pre-existing rows changed,
and on all 91 every extractor-owned text field was replaced by run 2's phrasing** — `statement`,
`name`, `as_built`, `implementation_notes`, `assumptions`, `parameters`, `extractor_payload`, plus
the `scenarios` and `edge_cases` child sets. Smaller counts moved too: `category` on 16 rows,
`priority` on 13, `confidence_extraction` on 14, `suspected_defect` on 20, `sme_question` on 22,
`findings` on 14, and **`modality` on 4** (`expectation` → `requirement`).

**This is the designed behaviour and no human work was at risk, which is the part to state
explicitly rather than leave to inference.** `gr_fields`' four-way partition holds: every field that
moved is in `EXTRACTOR_OWNED_FIELDS` (14 columns, merge-written by design) or is one of the three
`SHADOWED_FIELDS`, which the merge writes *only* while the live value still equals its shadow —
i.e. only while no human has edited it. All 379 rows were `draft`/`captured` with every SME column
NULL, so the shadows moved freely and correctly. **None of the nine `HUMAN_WRITABLE_FIELDS`
appears in the diff at all.** The `findings` change is the derived-SQL refresh working: a
`V-VAG-04` ERROR disappeared on 14 rows because run 2's restated statement no longer trips the
check. The four `modality` flips are the clearest illustration of why `modality_confirmed` exists —
it is `False` everywhere here, so a merge is free to reclassify an unconfirmed row, and a reviewer's
confirmation is what would stop it.

**So the honest summary of the churn is "a merge replaces the extractor's account of a requirement
with the newer run's account, and protects everything a human owns" — not "cosmetic".** Reporting
it as `updated_at`-only would have understated a real and intended behaviour by two orders of
magnitude in scope. Entry 16's `updated_at` observation is still true; it was simply never the
whole diff.

#### Run metadata, and what the run cost

    wf_fe5c5435-2db   595 agents, 0 errors, 0 skipped, 0 empty results
    16,755,656 subagent tokens, 5,230 tool calls, 3 h 6 m wall clock
    Round 1: 131 reported, 130 new     Round 3:  85 reported,  83 new
    Round 2: 124 reported, 124 new     Round 4: 113 reported, 101 new (438 catalogued)
    435 confirmed, 3 rejected by referees; stats.p0 = 59 (the log line says 70)
    stopReason=round_cap, rounds=4, newRulesInFinalRound=101
    coverage after four rounds: 440/15,398 chunks = 2.9%

**Four rounds did not saturate this run either, and the per-round shape differs from run 1's** —
130/124/83/101 against run 1's 112/115/92/118. Both runs dip in round 3 and recover in round 4, and
neither shows a decay curve, so the earlier conclusion stands and is now replicated: **the corpus
size is a budget decision, not a saturation point.** The P0 log-versus-`stats` discrepancy
reproduced exactly as run 1's did (log 70, `stats.p0` 59, the log printing before the panel
demotes); **report `stats`.**

**`A1` passes 435/435** — `ruleClass`, `statement` and `modality` present on every rule, zero NULL
`ruleClass`, all ten SPEC-1 §S1.4 patterns represented, `assumptions` and `implementationNotes`
100% filled, and `given`/`when`/`then` still flat alongside the notation. **93 of 93
`structuredBody` payloads validate** against `gr_body_schemas.validate_structured_body` (29 formula,
39 decision table, 18 invariant, 7 state transition), so `repair-structured-bodies` was not needed,
exactly as in run 1. All 435 citation sources parse; **435 triples for 435 rules, against run 1's
441 for 437** — this run emitted no multi-range citations at all.

**One free cross-check.** The A1 harness was verified against the *existing* corpus before the new
one landed, and it re-derived `MEAS-2` = **39 decision tables** independently of Phase 3's SQL. The
same query on run 2 also returns 39, which is a coincidence worth flagging as such rather than
reporting as stability.

### Step 10 Phase 5 (2026-09-10) — `A3` **PASSES**; the two defaults measured, and the semantic half found never to have run

**`A3` — `PR-47`'s hand-off half: PASS, end to end.** Run against a scratch copy at
`<scratch>/a3` (`--analysis-dir`) holding a copy of `index.sqlite` and a copy of `knowledge.sqlite`
with the eleven GR tables emptied and `domains`/`file_domains` (1,504) left intact, so subjects still
resolve `derived`. The degraded ingest was produced by removing the Bedrock credential from the
environment for that one command, which is the real failure rather than a simulated one:

        embedding failed (Bedrock embedding requires the AWS_BEARER_TOKEN_BEDROCK environment
        variable to be set ... It is absent. Set it, or use --embedding-provider hash (or qwen3)
        for a local embedder.); the requirements are stored and keyword search works.
        Run `legacylift-search requirements reindex-vectors` to retry.
        ...
        rows inserted: 379        vectors: 0 embedded, 379 skipped, 0 deleted
        the semantic half is NOT fully populated ... run `requirements reindex-vectors` to
        populate it. Exiting ZERO: nothing was lost and there is no extraction to re-run.
                                                                              exit 0

Then `requirements stats` reported `gr_statements holds 0 of 379` **and** volunteered the sentence
that matters — "a zero-candidate result here does NOT mean there are no near duplicates" — which is
Step 5's mandatory shortfall check doing exactly the job the Decision Log gave it. Then:

        requirements reindex-vectors --repo-root <CODE> --analysis-dir <scratch>/a3
        -> gr_rows 379 | embedded 379 | skipped 0 | deleted 0 | collection_count 379
           No shortfall: all 379 requirement(s) have a vector in gr_statements.     exit 0

**Three things worth keeping from how it passed.** `reindex-vectors` resolved **only the knowledge
directory** — no index, no repo root — so it cannot re-extract by construction, which is the
strongest form of "with no re-extraction" the criterion could ask for. The collection was created at
`<scratch>/a3/knowledge/chroma`, confirming trap 3: it lives under the knowledge directory and is
out of `index --reset`'s reach. And the real store was untouched throughout (`gr` 379, `gr_run` 3).

**A free result: `MEAS-1` is exactly reproducible.** The degraded ingest was a first ingest into an
empty store, and it reproduced Phase 3 **figure for figure** — 272 new / 58 merged / 107 candidate,
379 rows, 148 candidates (`drift` 85, `range_overlap` 63), intra-run collapse **106**, citations
441 seen / 383 inserted, anchors 4 / 433 / 4, subjects 436 / 1, tiers 88 / 349, 287 findings. So the
handoff's fourth unverified item — whether a `MEAS-1` redo is possible — is answered: **yes, given a
store copy with the domain tables intact, and the number is deterministic, not an artifact of one
run.** That was worth knowing before Milestone 1.5 leaned on it.

---

**The two unvalidated defaults, measured on a real corpus for the first time.** A read-only harness
queried the A3 store's populated `gr_statements` collection for the ten nearest neighbours of every
one of the 379 statements, then computed which pairs each `(SEMANTIC_TOP_K, SEMANTIC_DISTANCE_MAX)`
setting would surface. Nearest-neighbour distance across the corpus:

        p0 0.0000   p10 0.1227   p50 0.6268   p90 1.0565   p100 1.6485
        p1 0.0317   p25 0.3892   p75 0.8618   p99 1.3730

| top_k | dist_max | pairs surfaced | of those, **not already queued** |
|---|---|---|---|
| 5 | **0.35** (default) | 74 | **18** (24%) |
| 5 | 0.50 | 125 | 47 (38%) |
| 5 | 0.75 | 335 | 230 (69%) |
| 5 | 1.00 | 766 | 642 (84%) |
| 10 | 0.35 | 74 | 18 |
| 10 | 0.50 | 125 | 47 |
| 10 | 1.00 | 1,060 | 934 |

**`SEMANTIC_TOP_K = 5` is not the binding constraint and does not need changing.** 5 and 10 give
*identical* results at every threshold up to and including 0.50 — the distance cutoff binds first.
Raising `top_k` only matters once `dist_max` exceeds 0.5, where the yield is mostly noise.

**`SEMANTIC_DISTANCE_MAX = 0.35` is defensible, and the evidence is qualitative rather than the
count.** The twelve closest pairs in the corpus are **all already queued** by the deterministic
reasons, and reading them shows why: every one is visibly the same rule paraphrased ("When a trading
partner DUNS number is not exactly nine numeric characters…" against "When the *entered* trading
partner DUNS number is not exactly nine…", distance 0.0212). So the semantic half is **redundant on
this corpus, not too tight** — the opposite of the failure direction the docstring feared. Its
marginal value at the default is the 18 novel pairs; loosening to 0.50 buys 29 more at the cost of
41 additional already-queued duplicates for a reviewer to dismiss. **Recommendation: leave both
defaults alone.**

**The metric is still unpinned, and this is the number that depends on it.** `ChromaVectorStore`
sets no `hnsw:space`, so the distances above are in whatever chromadb 1.5.9 defaults to; the
collection's metadata was not readable through the wrapper. Observed distances span **0.0000 to
1.6485**, which is consistent with more than one metric, so **these thresholds must be re-measured
if the chromadb pin moves.** `pending/deferred-small-items.md` entry 3 already carries the
unpinned-metric item; this is the first measurement that depends on it.

---

**The finding that matters more than either default: the semantic half of stage two has never
actually run against a populated collection.** It is verified two independent ways.

*By code ordering.* `gr_ingest.py:1049` carries the comment "The vector half runs **AFTER** the
commit", so `refresh_gr_vectors` populates the collection only once the per-rule loop is over. During
the loop — which is where `_stage_two` runs its semantic query — the collection holds only vectors
from *previous* runs. **On a first ingest into an empty store it therefore holds nothing at all, for
the entire run.**

*Empirically.* The `A3` degraded ingest ran with **no embedder whatsoever** and produced candidate
counts byte-identical to Phase 3's fully-credentialed run: 148, `drift` 85, `range_overlap` 63. Had
the semantic half contributed a single pair in Phase 3, the two would differ. It contributed none.

And on the re-ingests of Phase 4 the semantic half is unreachable for the opposite reason: every rule
matched stage one's exact `dedupe_key`, so `_stage_two` was never called. **Between the two, no
ingest performed in this milestone has exercised the semantic half against a non-empty collection** —
which is why the harness above, not an ingest, is what measured its thresholds.

**The guard that should have said so is silent in exactly this case.** Ingest calls
`describe_vector_shortfall(store.count_gr(), collection.count())` *before* inserting, and on a first
ingest both arguments are 0 — `describe_vector_shortfall(0, 0)` returns `None`, confirmed directly.
So the run where the semantic half is guaranteed blind is the one run that prints no warning about
it, while `stats` afterwards reports `379 of 379` and "no shortfall" because by then the vectors
exist. **This is precisely the indistinguishability `SEMANTIC_DISTANCE_MAX`'s own docstring warns
about**, occurring in the place the docstring did not look. Filed as
`pending/deferred-small-items.md` entry 15, which separates the small honesty fix (compare against
the incoming rule count, not the pre-insert one) from the design question it should not decide alone
(whether stage two ought to see the current run's own rules at all).

**Nothing here weakens `MEAS-1` or Phase 4.** Stage two never merges, so a blind semantic half can
only mean *fewer candidates shown to a reviewer* — never a lost rule. The 18 novel pairs it would
have surfaced are additions to a 148-pair review queue, not corrections to the corpus.

---

**One more thing the harness turned up, and it is the cleanest possible proof case for
`pending/dedupe-key-tier-mismatch.md`.** Exactly one pair of requirements in the store shares a
**byte-identical `statement`** — and they are two rows, at distance **0.0000**:

        4A85JX  "An Active point status period never carries a termination type."
                body: none          -> tier 2, hashes ch1:2578ba85
        2ST1MQ  same statement
                body: invariant, 185 chars -> tier 1, hashes the body

Same `dedupe_key_anchor_only`, same `rule_class`/`pattern` (`definitional`/`D-IMPOSS`), same single
citation — `PoipointService.java:928-931` — and the **same span `content_hash`, `ch1:2578ba85`**.
Every input to a tier-2 key is identical. They are two rows solely because one carries a structured
body and the other does not, so one hashed the body and the other hashed the content hash. Had both
been discriminated at tier 2 their keys would have been equal and they would have auto-merged.
Queued as `drift`, so the net is visible. **This is the regression case that draft should be written
against.**

### Step 10 Phase 4 (2026-09-10) — the merge acceptance test **PASSES** on the real store

**This is the plan's single most important observable outcome, and it passed against the real
populated store rather than the 2026-09-09 rehearsal copy.** The same saved corpus file was
re-ingested twice more — runs `RUN-01M26551VPR5KSVY7BYFNVDBZJ` and
`RUN-01M2657EP2T11JAQV0EYS9HSKH`, both exit 0 — and each reported the ideal banner:

        rules: 437 offered = 0 new + 437 merged + 0 candidate; 0 rejected by the panel
        rows inserted: 0        merge candidates raised: 0 [(none)]
        citations: 441 seen, 0 inserted
        merged with no value change: 331

**The two stated assertions, both met exactly.**

| assertion | run 1 | run 2 | verdict |
|---|---|---|---|
| `gr` | 379 | **379** | PASS |
| `gr_citation` | 383 | **383** | PASS |
| `gr_scenario` | 379 | **379** | PASS |
| `gr_edge_case` | 794 | **794** | PASS |
| `gr_run` gains a row whose `rules_merged` = run 1's `rules_in` | 437 in | **437 merged** | PASS |

`gr_citation_anchor` (811), `gr_finding` (287) and `gr_merge_candidate` (148) are flat as well,
which the runbook does not require but which is the same bug one level further down. `gr_run_hit`
grew 437 → 874 → 1,311, which is correct and is **Step 3's count identity holding at three runs:
1,311 = 3 × 437**, one hit per offer per run.

**Beyond the stated assertions: a third ingest establishes that run 2 is a content fixed point.** A
full row-level snapshot was taken before and after the third ingest and diffed field by field, which
is stronger than the count assertions because a count cannot see a silent rewrite:

        gr                   379 rows; 48 differ, in `updated_at` ONLY
        gr_citation          383 rows, BYTE-IDENTICAL
        gr_finding           287 rows, BYTE-IDENTICAL
        gr_merge_candidate   148 rows, BYTE-IDENTICAL
        gr_scenario          379 rows; 48 differ, in `scenario_id` ONLY
        gr_edge_case         794 rows; 83 differ, in `edge_case_id` ONLY

**Every substantive column is stable** — `statement`, `structured_body`, both dedupe keys, `state`,
`subject`, `subject_provenance`, `created_at`, `first_seen_run_id`, and every citation, finding and
merge-candidate row. What churns is one timestamp and two surrogate row ids.

**And the churn is fully explained, which is why it is benign.** The 48 `gr` rows whose `updated_at`
moves are **exactly** the 48 rows of `MEAS-1`'s reading B — the set was compared, not eyeballed, and
the two are identical. A row that absorbs more than one offer in a run is written once per offer, so
its last write always moves the timestamp and re-mints its scenario and edge-case rows; the 331 rows
that took a single offer are reported by the banner itself as "merged with no value change" and are
byte-stable. This is why `scenarios rewritten: 106` and `edge-case sets rewritten: 106` appear on a
run that inserted nothing: 437 offers − 331 single-offer rows = **106**, the same number `MEAS-1`
reading A reports. **Ingest is idempotent in content and not in `updated_at`.**

**One consequence worth stating rather than rediscovering: `scenario_id` and `edge_case_id` are not
stable across ingests.** They are monotonically increasing integers re-minted on every rewrite
(543 → 648, 492 → 597, 494 → 599), so each re-ingest burns roughly 106 of each. Row *counts* stay
flat, so nothing leaks, but **any external reference to a scenario or edge-case id will dangle after
a re-ingest** — a review UI (Milestone 4, `pending/reqs-review-ui.md`) must key on `gr_id` plus
content, never on these ids.

**The Decision Log's `verified_at` entry was tested at the same time.** Its mechanism is confirmed:
`verified_at` moved on **no** citation, and all 383 `gr_citation` rows are byte-identical.

**A correction to how that test was first read, because the distinction is the whole point.** An
export taken after the two re-ingests differs from the Phase 3 export — 380 lines and the same
`gr_id` set, but **48 of 379 requirement lines differ in `updated_at`** (the same 48 rows) and the
`_incomplete` header grew from 1 named run to 3, 2,498,688 → 2,498,820 bytes. That was first written
up as "the second export is not byte-identical", which is the wrong conclusion: **two exports of an
unchanged store *are* byte-identical**, verified directly afterwards at 2,498,820 bytes both times
with no intervening write. The difference above is caused by the two ingests in between, not by the
export. So the plan's two byte-identity acceptance criteria stand as written, and the claim that
actually needed narrowing is the Decision Log's other half — that re-ingesting the same output
changes *nothing*. It changes `updated_at` on 48 rows and the header's run list, and nothing else.

**A labelling hazard this created, and it is now live in the store.** `requirements stats` prints
`intra_run_collapse=106` on **all three** runs, because the figure is a property of the corpus and
not of the store's state. **Only run `RUN-01M2646H97JAZJPPKHSCZT1RRY` is `MEAS-1`** — it is the one
that ran against an empty store. Runs 2 and 3 report the same 106 while merging into a full store,
where the number means something else entirely. Anyone quoting a collapse figure from this store
must name the run id.

### Step 10 Phase 3, as measured (2026-09-10) — `MEAS-1` spent, all three numbers taken

**`MEAS-1` is spent and cannot be retaken.** The four-round corpus was ingested into the empty store
on 2026-09-10 as run **`RUN-01M2646H97JAZJPPKHSCZT1RRY`**, exit 0. 437 offers became **379 rows**:
272 new + 58 merged + 107 candidate, **0 rejected by the panel**. The pre-ingest gate passed —
`derived`=378 / `llm_named`=1, so the run is testing what Step 3 built and not a fallback path.

**`MEAS-1`, both readings, labelled.**

| reading | figure | of what |
|---|---|---|
| **A — offers that landed on a shared `gr_id`** (`intra_run_collapse_count`, the number `stats` prints) | **106** | 24.3% of 437 offers |
| **B — distinct requirements that absorbed more than one offer** | **48** | 12.7% of 379 rows |
| **offers that lost their own row** (A − B) | **58** | 13.3% of offers — identical to the run's own `merged=58` |

Fan-in was shallow: 331 rows took exactly one offer, 40 took two, 6 took three, 2 took four. **The
maximum number of mined rules that collapsed onto any one requirement is four.**

**The verdict: these are true-sames, and the corpus is not silently short.** All 48 collapsed groups
were read back against the corpus by `offer_ordinal`. The shape is the same in essentially every
group — one file, one identical line range, the same rule renamed by a later round's agent
(`StatusHistoryService.java:96-106` collapsed offers 38 / 82 / 379 / 405, respectively "Modified
status history must overlap the record it replaces", "A modified status period must overlap the
period it replaces", "…must still overlap…", "An edited status period must overlap…"). Two pairs are
worth a reviewer's eye rather than a claim of certainty:
`LegalEntityStatusHistoryValidator.java:47-71` merged "Legal entity **short name** must be unique"
with "Legal entity **name** must not duplicate another legal entity", which may be two fields; and
`:91-97` merged a not-zero check with a required-when-flag-clear check. **Neither is evidence of the
invisible false-same the design fears** — both are visible in the store, both name the same lines,
and both sit in the review queue below.

**What the collapse figure does not measure, and this is the larger population.** `MEAS-1` counts the
*auto-merge* on the exact `dedupe_key`. The store also holds **34 `dedupe_key_anchor_only` clusters
carrying 54 excess rows** — same anchor, same `rule_class`, same `pattern`, kept apart only by the
tiered discriminator. That is under-merging, which `gr_ingest.py`'s own docstring argues for on the
ground that a false-distinct is visible and a false-same is not. **The safety net was verified rather
than assumed: every internal pair of all 34 clusters is queued as a `drift` merge candidate — 34/34,
0 partial, 0 missed.** 148 candidates in total (85 `drift`, 63 `range_overlap`), every one
`resolution='unresolved'`. So the residue is fully visible to a reviewer, and the asymmetry the
design was built around holds on real data.

**The mechanism behind those splits was not anticipated, and it is structural rather than textual.**
**18 of the 34 clusters are *mixed*: some rows in the cluster carry a `structured_body` and some do
not.** The discriminator is tiered — tier 1 is the canonical form of the structured body, tier 2 the
span-level `content_hash` set (`gr_keys.py:13`) — so a body-carrying row and a bodyless row hash
*different tiers* and **can never match the exact key, however identical the rule**. Only **88 of
379** rows carry a body, and whether the extractor emits one varies round to round, so any rule
re-mined across rounds has a substantial chance of splitting this way. Of the rest, 7 clusters carry
a body on every row and split because the bodies differ textually, and 9 carry none and split
because the span sets differ within one symbol anchor. The clearest instance is
`StatusHistoryService.java:151-167`, where four rows share one `dka1:e3485b145836401a` and one
subject: one has no body, three carry `invariant` bodies of 301 / 267 / 255 characters. **This is not
a defect to fix inside Phase 3** — the drift queue catches all of it — but it means the exact key's
hit rate is bounded by body-emission stability, which nothing measures. Recorded as its own
draft, `pending/dedupe-key-tier-mismatch.md` — the deferred-small-items entry bar sends it there
rather than to the list, because the fix needs a design choice and, now that the store is populated,
a re-key migration.

**`MEAS-2` — rules that collapse into a decision table: 39.** Not the rehearsal's 24, which was
taken against a copy holding a different corpus. Full `structured_body_type` breakdown over the 379
rows: `<null>` 291, `decision_table` **39**, `formula` 23, `invariant` 22, `state_transition` 4.

**`MEAS-3` — distribution of rule counts per candidate table, and the verdict it forces.** Over
those 39 tables, `len(structured_body.rules)` ran **3 to 8**, median **5**, mean **4.90**:

        3 rules:  7 tables      6 rules:  6 tables
        4 rules: 11 tables      7 rules:  3 tables
        5 rules:  9 tables      8 rules:  3 tables

**33 of 39 tables (84.6%) sit at or under six rules; 6 (15.4%) are above, and the largest is 8.** The
threshold Step 10 names is roughly six rules per table, past which the only published code-to-DMN
study reports decision-rule accuracy collapsing. **Most tables in this corpus are under it, so the
replay loop is not blocked on this criterion** — and the maximum of 8 is well inside the study's
19-rule ceiling. This is a green light to *attempt* the loop as a detector of bad extraction, and
still not a promise of DMN coverage: 291 of 379 requirements carry no structured body at all, so the
executable subset is 39 of 379 requirements, **10.3%**.

**Run metadata, all four columns populated — none `unmeasured`.** `stop_reason=round_cap`,
`rounds_run=4`, `round_cap=4`, `new_rules_in_final_round=118`, `not_accounted_for=14925`,
`complete=False`, `coverage_source=extraction`. The corpus is a floor, not a sweep, and the plan's
`Progress` already says why a fifth round was a budget decision rather than a saturation point.

**The rest of what this run was the only chance to record.**

- **Anchor resolution in the store: `symbol` 375, `file` 4, `unresolved` 4**, over 383 inserted
  citations (441 seen). The ingest banner's own breakdown reads 433 / 4 / 4 because it prints
  pre-dedup — `pending/deferred-small-items.md` entry 12, now confirmed on live output rather than
  re-derived.
- **Distinct files cited: 118.**
- **`gr_dataflow` is empty and `stats` says so in words with no rate** — "no data-flow entries:
  computed path disabled pending M26, extractor source not yet added". Step 7's acceptance was that a
  percentage over an empty table is the defect and not the expected value; that is what it printed.
- **Findings: 287 written over 379 rows.** By severity: ERROR 46 evaluated + 24 not evaluated, WARN
  217. By id, `V-ENF-03` dominates at **196 of 287** — `enforcement_level` is unfilled on all 379
  rows, and it is an SME column, so this is the review queue reporting absent human input rather
  than a notation fault. `V-STY-03` fired **4** times against 21,469 symbol names from the cited
  files.
- **SME-field fill rates: 0%.** `enforcement_level`, `confidence_intent`, `rationale`,
  `fit_criterion` and `owner` are absent on all 379 rows; every extractor-owned column
  (`rule_class`, `pattern`, `statement`, `modality`, `assumptions`, `disposition`) is 100%.
- **Vectors: 379 of 379, no shortfall.** Bedrock was reachable throughout, so **this ingest was not
  degraded and therefore does not discharge `A3`** — `A3` needs a deliberately degraded ingest
  followed by `reindex-vectors`, which is Phase 5's job.
- **10 prompt-injection suspects** stored on `gr_run.injection_flags` and echoed to stderr. All ten
  are the same shape: in-source comments asking that a Fortify finding be dismissed, plus one
  unverifiable precondition asserted only in prose. They are data.
- **Discriminator tiers over the 437 offers: tier 1 = 88, tier 2 = 349.** No offer fell to tier 3.

**Two of the handoff's four unverified items are now closed by observation.**

- **The bad citation degrades, it does not block.** Rule 254, `Northern Natural Gas own-party
  identity`, ingested as `GR-01M2648AATD4HMHFAZ16TE9T06` with **4 `unresolved` anchors**, and is the
  only row in the store with zero resolved citations. Ingest did not abort. Its
  `gr_citation.relative_path` holds the whole prose blob verbatim — entry 13's defect, now visible in
  the store rather than only in the corpus, and the `unresolved` path is confirmed to run on a rule
  with no resolvable citation at all.
- **`export` does trip the completeness gate, as predicted.** Without the flag it **refuses and
  exits 1**, naming the run and the reason: "14925 chunks unaccounted for". With `--allow-incomplete`
  it wrote `knowledge/requirements.jsonl` — **380 lines, 2,498,688 bytes**, opening with the reserved
  `_incomplete` header `{"RUN-…": "14925 chunks unaccounted for"}`. **The file on disk no longer
  matches those bytes**: Phase 4 re-exported over it, and the header now names three runs
  (2,498,820 bytes) — see *Step 10 Phase 4*. The export command overwrites in place, so save a copy
  before re-running it. **It is still not committed**: the
  whole `repos/nng-app-legacylift-analysis/` tree is gitignored at `.gitignore:108`, so the durable
  backup exists on disk and outside git, and force-adding 2.5 MB of client-derived requirements is a
  maintainer's decision, not an implementer's.

**One new observation that bears on runbook §8.** Stage two's *semantic* half raised **zero**
candidates. All 148 came from `drift` (85) and `range_overlap` (63), with `similarity` NULL on both —
those two reasons are key- and range-based, not vector-based. The `gr_statements` collection held all
379 statements at the time, so the semantic search ran against a full collection and surfaced nothing
the two deterministic reasons had not already caught. That is either healthy redundancy or
`semantic_distance_max=0.35` being too tight to ever fire, and **this run cannot distinguish the
two** — which is precisely the measurement runbook §8 asks for, and the reason it needs a Python
harness rather than a flag.

### Step 10 Phase 2, the four-round run (2026-09-10) — the corpus of record

**Run `wf_e242dcb9-f34`**, launched from the repository root against the ASCII launch copy with
`{system: "customer.ple.nng.app", repoRoot: "repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app",
maxRounds: 4}`, no `modulePattern`. **552 agents, 0 errors, 0 skipped, 0 empty results**, 15.37M
subagent tokens, 4,932 tool uses. 19.4 h wall clock of which **~1.6 h was active compute** (see
`Surprises & Discoveries`). Agent split: 12 extract (3 lenses x 4 rounds), 4 coverage, 437 verify
(one referee per fresh rule), 98 P0 panel (2 judges x 49), 1 DTO catalog + 1 retry.

Round-by-round, as logged:

    Round 1: 114 reported, 112 new (112 total catalogued)   coverage 128/15398 (0.8%)
    Round 2: 116 reported, 115 new (227 total catalogued)   coverage 284/15398 (1.8%)
    Round 3:  94 reported,  92 new (319 total catalogued)   coverage 414/15398 (2.7%)
    Round 4: 128 reported, 118 new (437 total catalogued)   coverage 473/15398 (3.1%)
    Coverage note: stopped at maxRounds=4 before extraction ran dry
    437 rules confirmed (49 P0); 0 rejected by referees

**Report `stats`, not that last log line** — the same pre/post-panel gap the 2026-09-08 round-1 note
records holds again: the log prints 49 P0 before the panel demotes, and `stats.p0` is **45**, which
is what the returned rules agree with. Returned metadata: `rounds` 4, `roundCap` 4, `stopReason`
`round_cap`, `newRulesInFinalRound` 118, `confirmedRules` 437, `rejectedRules` 0, `dataObjects` 63,
`injectionFlags` 10, `stats` `{confirmed 437, rejected 0, p0 45, needsSme 65}`, `coverage`
`{total 15398, claimed 473, uncovered 14925, pct 3.07, round 4}`.

**Saved verbatim, first, before any gate ran**, to
`analysis/customer.ple.nng.app/knowledge/extracted-rules-4round.json` (1,229 KB) — a **new** file,
with the three earlier corpora asserted byte-unchanged before and after the write, and the saved JSON
re-read and compared structurally to the return value. The tree is gitignored (`.gitignore:92`), so
this file is in no commit and cannot be.

**All ten `injectionFlags` are the same class** and none is an attack: in-source comments of the form
`"This method is used in only Test Cases no real problem fortify fix not needed"`, i.e.
instruction-shaped text asking an automated scanner to dismiss a finding, correctly treated as data.
One is substantive as an *assumption* rather than an injection —
`PoipointLiteService.java:480-481` asserts in prose a precondition ("the points have been filtered
by the database the same way the flags are being passed") that the executable code never checks.

**`A1` — the pre-ingest shape gate: PASS on 437/437, all four checks.** `ruleClass`, `statement` and
`modality` non-empty on every rule; every `pattern` present, non-null and one of §S1.4's ten;
`given`/`when`/`then` retained and **flat** (no `scenario`/`givenWhenThen` nesting), which is what
`gr_fields.EXTRACTOR_FIELD_MAP` expects. `implementationNotes` and `assumptions` are each on
**437/437 (100%)**, so the abstraction instruction took — cross-check that against the `V-STY-03`
finding rate after ingest, per the runbook. Two gate mechanics that cost a re-run in earlier phases
and were honored here: the rules are under **`confirmedRules`**, not `rules`, and a citation's
trailing range may be a comma-separated list.

Distributions, for Milestone 1.5's baseline: `ruleClass` behavioral 245 / definitional 192;
`modality` requirement 428 / expectation 9; `pattern` B-PROHIB 148, D-INFER 82, B-RESTRICT 52,
D-COMPUTE 49, B-COND 30, D-RESTRICT 23, D-NEC 20, B-UNCOND 15, D-CONST 10, D-IMPOSS 8 — **all ten
exercised**; `priority` P1 362, P0 45, P2 30; `confidence` High 372, Medium 63, Low 2;
`suspectedDefect` 37; `smeQuestion` 67.

**`structuredBody` — 88 present of 437, and 88/88 validate.** By type: `decision_table` 39,
`formula` 23, `invariant` 22, `state_transition` 4 — **`state_transition` has live output for the
first time**, so all four body kinds are now exercised. Validated by calling
`gr_body_schemas.validate_structured_body` directly, the same entry point ingest calls, so **no
`repair-structured-bodies` pass was needed** and the one-transaction ingest has nothing to abort on.
No body carries a missing or unknown `structuredBodyType`, and no rule declares a type without a
body.

**Citations — 441 triples from 437 rules, 0 parse errors, 437 resolve.** Re-parsed with
`legacylift_search.citations.parse_citation`: **0 whole-file sentinels** (`WHOLE_FILE_END_LINE`) and
**0 ranges extending past end-of-file**, so both previously-fixed bad shapes stay fixed on a corpus
3.3x the size that found them. Two rules legitimately expand to more than one triple. **4 triples
from 1 rule do not resolve** — the prose-`source` defect recorded in `Surprises & Discoveries` and
filed as entry 13; the affected rule is `Northern Natural Gas own-party identity` and all four files
it names do exist under the codeRoot.

**Not ingested, on purpose.** `MEAS-1` is defined as the intra-run collapse on the *first* ingest
into an empty store, `index --reset` cannot reach the knowledge store, and the store is still `gr` 0
/ `gr_run` 0. That measurement has one clean shot and spending it is a decision for the maintainer,
not a step an implementer takes on initiative.

### Step 10 Phase 3 rehearsal, and the scoped two-round run (2026-09-09)

**Not Phase 3 itself — a rehearsal against a copy, and the difference is recorded on purpose.**
Runbook §6 defines `MEAS-1` as the intra-run collapse on *the first ingest into an empty store*, and
`index --reset` cannot reach the knowledge store (that is why it lives outside the index subtree), so
that measurement has exactly one clean shot. It is **unspent**: the real
`analysis/customer.ple.nng.app/knowledge/knowledge.sqlite` still reports `gr` 0, `gr_run` 0,
`gr_finding` 0, `file_domains` 1504. Everything below ran against a scratch copy of `index/` +
`knowledge/` passed via `--analysis-dir`. **`index/` had to be copied too, not symlinked or
omitted** — 318 MB against 1.8 MB — because a missing index is a *supported degraded success* that
exits zero, and every citation would have silently fallen to the file-level anchor and corrupted the
anchor-resolution breakdown.

**What the rehearsal discharges at full value**, because none of it depends on the store being
pristine: `MEAS-2`, `MEAS-3`, the four `gr_run` metadata columns, the `derived`-subjects gate, the
`V-STY-03` rate, the SME fill rates, the empty data-flow block, and **Phase 4's merge acceptance
test** — which the runbook states against a *fixed input* precisely so that a copy is as valid as
the real store.

**Ingest #1** (`extracted-rules-round1-bodies-repaired.json`, exit 0):
133 offered = 91 new + 4 merged + 38 candidate, 0 rejected; 129 rows inserted; 46 merge candidates
raised (`drift` 9, `range_overlap` 37); citations 142 seen / 138 inserted; **anchor resolution
`file`=2 (both `.xml`), `symbol`=136, `unresolved` 0**; **subject provenance `derived`=133 — the
Phase 3 gate passes**; discriminator tiers 1=40, 2=93; 144 findings written; 129 vectors embedded
through Bedrock.

**Phase 4 — the merge acceptance test: PASS.** Re-ingesting the same file reported
`0 new + 133 merged + 0 candidate`, `142 seen, 0 inserted`. All four counts identical to run 1
(`gr` 129, `gr_citation` 138, `gr_scenario` 129, `gr_edge_case` 280) and `gr_run` gained a second
row with `rules_merged` 133 = run 1's `rules_in` 133. **This is the plan's single most important
observable outcome and it holds.**

**MEAS-1, both readings, labelled as the runbook demands.** Sum-of-offers (what
`intra_run_collapse_count` returns): **8**. Distinct `gr_id`s that absorbed more than one offer:
**4**. So 4 mined rules lost their own row, not 8 — and the store was empty, which is why 4 rules
report as "merged" at all. Small enough to carry no warning about the tier-2 key, and **this is a
rehearsal figure, not the recorded one**.

**MEAS-2: 24** decision tables. **MEAS-3:** `3,3,4,4,4,4,4,4,4,4,5,5,5,6,6,6,6,6,6,7,8,9,12,13` —
median 5, max 13, **19 of 24 (79%) at or under six rules**, 5 above it. **The verdict the plan
reserved: the replay loop is NOT blocked.** The runbook's trigger was "if most candidate tables
exceed about six rules, the replay loop waits", and most do not; the max of 13 sits inside the
published study's own 19-rule ceiling. Per §S2.4 and the runbook's own instruction the loop is still
framed as a *detector of bad extraction*, and no DMN coverage of the corpus is promised — and this
is one round, so the distribution can move.

**Two numeric coincidences, tested rather than assumed.** The 40 tier-1 requirements *are* exactly
the 40 carrying a `structured_body`, and that is causal, not coincidence: `select_discriminator`
(`gr_keys.py:221`) fires tier 1 **iff** a validated canonical body exists. The consequence worth
carrying is that **93 of 129 requirements (72%) are keyed with no body discriminator**. The other —
38 `candidate` outcomes against 38 repaired bodies — **is** coincidence: the overlap is 13/38.

**The findings, before and after amendment A4.** Before: ERROR 37 evaluated / 12 not evaluated,
WARN 95 / 0, of which `V-VAG-03` was **26 evaluated ERRORs** and all 26 were false positives. After
A4: **ERROR 11 evaluated / 16 not evaluated**, WARN 95 / 0 unchanged. The four extra not-evaluated
rows are `V-VAG-03` on the four records where no template locates `[Subject]`, which line up
exactly with the four not-evaluated `V-SLOT-01/02/03` rows. The 11 that remain are real:
`V-SING-01` 4, `V-VAG-04` 3, `V-VAG-09` 2, `V-KW-01` 2. `V-ENF-03`'s 95 WARNs are not a signal —
its own message says "review progress, not a defect".

**The scoped two-round run** (`wf_0b5440c3-7e0`, `maxRounds: 2`, `modulePattern` naming the point
validator package): 246 agents, **0 errors**, 73 minutes, 6.58M subagent tokens, **186 rules
confirmed, 1 rejected**, 73 data objects, 5 injection flags. Saved to
`knowledge/extracted-rules-scoped2round-test.json` — a **test artifact, deliberately not merged into
the corpus**. `stopReason` `round_cap` with `newRulesInFinalRound` 87, so round 2 added 87 rules to
round 1's 99: **the loop had not saturated, which is the strongest evidence yet that four rounds are
worth running.** `stopReason: 'dry'` remains unexercised and cannot be reached inside a cap of 2 —
`deriveStopReason` returns `dry` only at `dryRounds >= 2`, and the `while` guard exits first.

**Suite: 1,263 passed, exit 0** (floor was 1,256; A4 added five tests and the citation-list change
two).

### Milestone 1 Step 10, Phases 0–1 (2026-09-08) — pre-flight and the index rebuild, all green

Runbook phases 0 and 1. **`A2` is discharged and so is Step 2's every-row `entity_class` check.**
The three mandatory measurements are not in this entry: they need Phase 2's live extraction, which
has not run. Total wall clock for both phases, including the suite, was under 25 minutes.

**The pipeline deviation, disclosed as the runbook requires.** Of the four `code-modernization`
commands `Concrete Steps` lists, this run re-ran **`/modernize-preflight` only**. `/modernize-assess`
and `/modernize-map` were deliberately not re-run — see the settled decision in the `Progress`
Next action. **Milestone 1.5 compares against this run**, so this is the baseline, and the
`domains.json` it used is the 2026-08-04 canonical file plus the two provenance fields hand-added
on 2026-09-08.

**Phase 0.** Baseline suite **1,250 passed, exit 0, 6m21s** — exactly the floor, no regression.
The Bedrock probe passed live: `create_embedder` on the unit's manifest yields `BedrockEmbedder`
for `amazon.titan-embed-text-v2:0` in `us-east-2`, and both `embed_documents` and `embed_query`
return 1024-dimensional unit-norm vectors. Runbook step 0b (the ASCII copy of `extract-rules.js`
and the `args` shim) was **not** done — it is Phase 2 preparation and nothing in Phase 1 needs it.

**The pre-rebuild verification that had to happen first.** `repos/nng-app-legacylift-analysis/`
is gitignored whole, so the manifest and `domains.json` edits the coverage widening depends on
exist **on disk only, in no commit**, and a rebuild against un-widened artifacts would have
produced the wrong index with nothing announcing it. All three checks passed before the rebuild
was started: both units' `semantic-search.manifest.json` carry 28 `include_globs` including all
eight widened patterns and a `project.domains_file` pointing at
`../../analysis/<unit>/domains.json`; `analysis/customer.ple.nng.app/domains.json` carries 10
`vendored_globs` and `own_identities: ["nngco.com"]` alongside its 12 domains and 45
`exclude_globs` (`customer.ple.nng.db.ETSPii` carries `own_identities` and zero `vendored_globs`,
which the gap plan records as a deliberate "unmeasured"); and `discover_source_files` returned
**1,504 files with exactly 2 `.tld` — `naesb.tld` and `nngauthz.tld`**, the pinned sanity number.

**`/modernize-preflight`, re-run.** Every one of its five checks lands where 2026-08-03 left it:
`scc` 1,541 files / 168,035 code lines / 15 languages / COCOMO $5,864,960; `scc` 3.7.0, `cloc`
2.06, `lizard` 1.23.0, `glow` 2.1.2, `delta` 0.19.2 all present at identical versions; `javac` and
`java` 17.0.12 work while the repo compile still fails with the same five classpath errors on
`DateRangeable.java` and the Gradle wrapper still holds only `gradle-wrapper.properties`; **0
missing internal Java source** (995 classes, 534 `com.nng.*` imports, 19 private-feed, 0 binary
artifacts, 13 `.tld`, 133 `.hbm.xml`, 33 Web Flow definitions, all six key descriptors present);
no `.git` and no telemetry. So no verdict moved and `/modernize-extract-rules` is still **Ready**.
`PREFLIGHT.md` gained a *Re-verification — 2026-09-08* section recording that, plus the three
things that **did** change since August: the coverage widening, the fact that `domains.json` is
now partly hand-maintained and `/modernize-assess` must not re-author it, and the `.properties`
credential surface now reaching the index and therefore Bedrock.

**Phase 1, the rebuild.** `index --reset` ran in **7m28s**, exit 0, and printed both resolved
directories under `analysis/customer.ple.nng.app/`:

| | rebuilt 2026-09-08 | gap-plan trial (new globs) | real index 2026-07-23 (old globs) |
|---|---:|---:|---:|
| `repo_files` | **1,504** | 1,537 | 1,229 |
| `chunks` | **15,398** | 15,534 | 15,040 |
| `symbols` | **16,268** | 16,303 | 16,272 |
| `symbol_refs` | **74,278** | 74,306 | 74,289 |
| `graph_edges` | **74,541** | 74,569 | 74,552 |
| `symbol_facts` | **6,955** | — | — |
| files with 0 symbols | **306** | 331 | 36 |
| 0 symbols and >= 2048 b | **143** | 164 | 8 |

`backfill-hashes` was the documented no-op (`symbols_missing` 0, `remaining_null` 0,
"Every symbol has a content hash"). `tag-domains` resolved **1,504 files — 1,120 glob-matched, 384
excluded, 0 unassigned**, across all 12 domains and 36 edges, and stamped all 15,398 chunks: the
widening added 275 files and **every one of them landed in a domain or in the `excluded` tier**, so
the 100%-honest-coverage property from the domain-enhancements work survives it.

**All five post-rebuild assertions pass.**

1. `A2` — zero `legacylift-docs` directories under the checkout, by `rglob`, before and after.
2. Printed paths resolve under `analysis/customer.ple.nng.app/`; `index.sqlite` and `chroma/`
   under `index/code-search/`, and `knowledge.sqlite` **survived `--reset` in place**.
3. Counts reconcile exactly — see the *Surprises* entry, which is where the arithmetic lives
   because the headline reads like a regression and is not one.
4. `symbols.entity_class` is **non-NULL on all 16,268 rows**, including XML-extractor and
   regex-fallback rows: `function` 9,047, `field` 5,644, `type` 1,301, `other` 251, `table` 25.
   This is Step 2's acceptance check and a rebuilt index was the only way to reach it.
5. `symbols.anchor_key` and `symbols.content_hash` are non-NULL and non-empty on all 16,268 rows.

**Two things the run confirmed that had only been predicted.** `index.sqlite` moved
`user_version` **0 → 2**, so the rebuilt index carries Step 2's schema with classes its extractors
actually declared rather than the migration shim's guesses. And the **eleven GR tables plus
`gr_fts` were created free on first open**, exactly as Step 3's table-addition rule says: opening
the knowledge store during `tag-domains` was enough, `knowledge.sqlite` is still at
`user_version` **1**, and `gr` and `gr_run` are both empty — so Phase 3's first ingest really is
an ingest into an empty store, which is what `MEAS-1` requires.

**The store is set up for Phase 3's gate.** `file_domains` holds 1,504 rows over 12 real domains
(largest: `reference-data-code-admin` 189, `point-poi-management` 186, `shared-core-platform` 186,
`legal-entity-management` 179) plus 384 `excluded`, so `derived` subjects have a source and the
"if every subject is `llm_named`, stop" gate should pass.

**Embedding, recorded because `pending/embed-everything-evaluation.md` is about this number.**
Of 15,398 chunks, dense vectors were **skipped for 10,428 low-value chunks (67.7%)**; 148
duplicate-text chunks were deduplicated, leaving 4,822 distinct to embed, and 4,970 vectors were
upserted at 65–81 chunks/s. That is the ~70% figure that plan is named after, now measured on the
widened corpus rather than the old one. `chunk_kind` came out `symbol` 14,589 / `fallback` 561 /
`chonkie` 248.

**The accepted exposures are present and were not "fixed".** `application-prod1.properties` is in
`repo_files` and its chunks were embedded through Bedrock — the maintainer decision recorded in
the gap plan's Decision Log, whose deferred gate is `pending/indexer-credential-gate.md`. The
JSP layer is indexed and symbol-dead: 178 `.jsp` files, **0 symbols**, 213 chunks, citations into
them resolving to the path-only file-level anchor floor.

## Context and Orientation

You are working in a repository whose product is a set of Claude Code *skills* — packaged instruction files that an AI agent follows to analyze legacy codebases and write documentation. Alongside those skills is a conventional Python package that builds a searchable index of a codebase. This plan changes the Python package and wires one skill into it.

### The Python package you will edit

Everything you build lives under `tools/legacylift_search/`. It is a normal Python project: source in `tools/legacylift_search/src/legacylift_search/`, tests in `tools/legacylift_search/tests/`, configuration in `tools/legacylift_search/pyproject.toml`. There is a virtual environment at `tools/legacylift_search/.venv/`.

Use the virtual environment's interpreter directly. On this Windows machine that is `tools/legacylift_search/.venv/Scripts/python.exe`. **The `legacylift-search` executable found on the system `PATH` is a broken shim — do not use it.** Use `.venv/Scripts/legacylift-search.exe`, or equivalently `.venv/Scripts/python.exe -m legacylift_search.cli`.

The modules that matter to you:

`src/legacylift_search/store.py` (about 1,490 lines) owns `index.sqlite`, the disposable code index. Its class is `SQLiteStore`. Its `migrate()` method at line 173 creates every table with `CREATE TABLE IF NOT EXISTS`, after setting `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`. Eight tables live here — `index_metadata`, `repo_files`, `chunks`, `symbols`, `symbol_refs`, `graph_edges`, `vectors_present` and `symbol_facts` — plus one FTS5 virtual table, `chunk_fts` (`store.py:231`). Callers invoke `migrate()` explicitly.

`src/legacylift_search/knowledge_store.py` (about 1,010 lines) owns `knowledge.sqlite`, the durable store. Its class is `KnowledgeStore`. It holds **fifteen** tables: the four domain tables `domains`, `domain_edges`, `file_domains` and `domain_exclusions`, plus the eleven GR tables Step 3 added, created by `_migrate_gr_tables` from the same `migrate()`. Read its module docstring before you touch it — it explains the two properties you must preserve. First, unlike `SQLiteStore`, it calls `migrate()` from `__init__`, so merely constructing a `KnowledgeStore` creates and migrates the file. Second, it has no read-only mode, so any read-only caller must check `sqlite_path.exists()` with a plain `Path.exists()` *before* constructing it, or it will silently materialize an empty database as a side effect. Several existing commands do exactly that check; follow the pattern.

`src/legacylift_search/cli.py` (1,893 lines as of Step 4) is a Typer application. Commands are registered with `@app.command("name")` decorators — **sixteen** exist today, including `index`, `search`, `symbols`, `facts`, `tag-domains`, `domains`, `coverage`, `stats` and Step 2's `backfill-hashes`. Look at `domains_cmd` (`cli.py:1317`) for the canonical pattern: it resolves paths with `resolve_paths` from `cli_helpers`, resolves the knowledge directory with `resolve_knowledge_dir` from `config`, checks `Path.exists()` before constructing a `KnowledgeStore`, and joins across the two databases *in Python* rather than with SQL. Its docstring states the reason: the two SQLite files are separate and are never `ATTACH`ed, because attaching a write-ahead-logging database read-only is unreliable. You will hit this same constraint.

`src/legacylift_search/config.py` owns where everything lands. `index_dir` and `knowledge_dir` are manifest settings (`:101-105`) resolved against `--repo-root` by `resolve_index_dir` and `resolve_knowledge_dir` (`:269-302`). Their defaults put both directories *inside the analyzed repository*, which Milestone 0's second half changes — read that section before you write any code that names a path, because most of the locations elsewhere in this plan are stated in terms of the layout it establishes rather than the one on disk today.

`src/legacylift_search/models.py` holds Pydantic models — `Symbol`, `SymbolFact`, `CodeChunk`, `GraphEdge`, `DomainRecord` and others, plus `GRRecord` and `Finding`, which Step 4 added. Add your new record types here, following the existing style. **`GRRecord` mirrors `gr`'s forty-two columns exactly and a test asserts that against `PRAGMA table_info('gr')`**, so a column added to the DDL without being added to the model fails there rather than at the first ingest.

**Three modules this plan itself added, listed here because the orientation above predates them and a new agent otherwise goes looking for them in the wrong step:**

`src/legacylift_search/identity.py` (Step 1, shipped) is the one place any key in this system is computed — `anchor_key`, `file_anchor_key`, `content_hash`, `normalize_path`, `new_ulid`. A second implementation appearing beside it is the failure the module exists to prevent, so read it before you write anything that looks like a hash.

`src/legacylift_search/migrations.py` (Milestone 0, shipped) holds the `Migration` record, the runner, the two per-database lists, and — for Step 2's backfill only — the `SHIM_KIND_TO_ENTITY_CLASS` compatibility shim. `INDEX_MIGRATIONS` is at version 2 and `KNOWLEDGE_MIGRATIONS` at version 1; **the knowledge list has no real migration yet**, because Step 3 added tables rather than columns and `migrate()` covers that case. The first GR column addition is the mechanism's first production customer, so do not assume it has been exercised end to end.

`src/legacylift_search/gr_body_schemas.py` (Step 3, shipped) holds the four `structured_body` payload models, `validate_structured_body` (the single entry point ingest calls) and `canonical_structured_body` (the tier-1 `dedupe_key` discriminator). Step 6a's extractor prompt has to ask for exactly these shapes, so the module and the prompt are one contract in two places.

`src/legacylift_search/gr_validator.py` (Step 4, shipped) is the SPEC-1 notation validator — the twenty-eight checks, the shared keyword matcher `find_keywords`, and `split_slots`, the template-driven slot split that Step 5's `refresh_gr_derived_sql`, Step 6a and Step 3's `subject` derivation all consume. It is a **pure function of one record plus a `leaked_terms` set**; if you find yourself wanting to pass it a store, read the module docstring first — that shape was considered and rejected.

`src/legacylift_search/gr_state.py` (Step 4, shipped) holds `ALLOWED_TRANSITIONS` and `set_state`, which is the **only** writer of `gr.state` (Step 9's `import_records` is the declared exception). The `draft → approved` gate lives inside it, so a second write path is a way around the gate; `tests/test_gr_state.py` asserts the writer set by scanning the package source.

`src/legacylift_search/vector_store.py` wraps ChromaDB, the vector database used for semantic search. `ChromaVectorStore.__init__` takes a `collection_name`, creates a `chromadb.PersistentClient`, and calls `get_or_create_collection`. The default collection name is `code_chunks`, set in `config.py:108`. **The installed ChromaDB version must stay pinned at 1.5.9**; a mismatch causes a native crash.

`src/legacylift_search/extractors.py` builds symbols from parsed source. At lines 1112 through 1115 it constructs the symbol identifier, and you should read those four lines now because they explain a constraint you will work around rather than fix:

        sym_id = (
            f"{source_file.language}:{source_file.relative_path}:"
            f"{qualified}:{rng.start_line}"
        )

That identifier embeds a start line. Any edit *above* a symbol changes the symbol's identifier, so on the next index the row is deleted and re-inserted rather than updated. Five surfaces key off it: `symbols.id` is the primary key (`store.py:243`); `graph_edges.caller_symbol_id` and `graph_edges.callee_symbol_id` are foreign keys (`store.py:309` and `:310`, with `ON DELETE CASCADE` and `ON DELETE SET NULL`); `symbol_facts.subject_symbol_id` is a `NOT NULL` foreign key with `ON DELETE CASCADE` (`store.py:359`); and `chunks.symbol_id` (`store.py:216`) plus `symbol_refs.enclosing_symbol_id` (`store.py:278`) are plain columns. So a reindex after an edit discards the affected symbols' edges and facts. That is harmless today, because all twelve Layer-0 fact predicates are read straight off the syntax tree and regenerated at full confidence — nothing durable hangs off a symbol row. **Repairing that is explicitly out of scope here** (see the Decision Log and the Interfaces and Dependencies section). Your GR citations must therefore not depend on symbol identifiers being stable, and the schema below is designed so they do not.

### The skill you will wire in

**Orientation first, because extraction is one step of four and this plan changes the step rather than the sequence.** The `code-modernization` plugin analyzes a legacy application through four slash commands run in order: `/modernize-preflight` checks the environment and the completeness of the pulled source; `/modernize-assess` inventories the system and **authors `analysis/<system>/domains.json`**, the domain set this plan's `subject` derivation depends on; `/modernize-map` builds call graphs and data lineage; and `/modernize-extract-rules` mines business rules. A "slash command" here is a markdown instruction file an agent follows — there is no compiled command behind it. You will change only the fourth, and a real run of this plan means running all four against a repository from the top.

`/modernize-extract-rules` is defined in `.claude/skills/code-modernization/commands/modernize-extract-rules.md`, backed by a workflow script at `.claude/skills/code-modernization/workflows/extract-rules.js` and an agent definition at `.claude/skills/code-modernization/agents/business-rules-extractor.md`. **All three carry the rule shape and Step 6a changes all three**; the workflow's `RULES_SCHEMA` alone is not enough, because the agent definition and the command file's Rule Card format both describe Given/When/Then independently. The workflow runs multiple AI agents that mine business rules from source code, verify each rule's citation against the cited lines, and run a confirmation panel over the highest-priority rules. It returns a JavaScript object; the *calling session* — the agent running the slash command — renders `analysis/<system>/BUSINESS_RULES.md` and `analysis/<system>/DATA_OBJECTS.md` from that object. Agents never write those files themselves, because the source code they read is untrusted input.

The important fact for you: **a substantial structured schema for each rule already exists and is thrown away.** `extract-rules.js` defines `RULES_SCHEMA` starting at line 72. Each rule carries `name`, `category` (one of `Calculation`, `Validation`, `Lifecycle`, `Policy`), `priority` (`P0`, `P1`, `P2`), `source` (a repository-relative `path:line-line` citation), `plainEnglish`, `given`, `when`, `then`, an optional `and`, optional `parameters`, optional `edgeCases`, optional `suspectedDefect`, a `confidence` of `High`/`Medium`/`Low`, and an optional `smeQuestion`. The workflow's return value at the end of the file exposes `confirmedRules`, `rejectedRules`, `dataObjects`, `injectionFlags`, `coverage`, and a `stats` block. Your ingest path consumes that return value.

**Do not conclude from that list that nothing needs deriving, and do not conclude that the extractor stays as it is.** **Eight** of the `gr` columns have no source anywhere in the schema above — `rule_class`, `pattern`, `statement`, `modality`, `structured_body`, `structured_body_type`, `assumptions` and `implementation_notes`. **Step 6a's answer is to rewrite the extractor so it emits them**, because the extraction agents are the only actors in the system that read the code, and every one of those eight is a judgement about the code. An earlier version of this plan capped the schema extension at three fields and derived `pattern` and `statement` mechanically at ingest from the Given/When/Then; that was measured against the real corpus and does not work (`PR-79`, Decision Log). Read Step 6a before writing any ingest code *or* touching the extractor.

**The old Given/When/Then is retained, unchanged and still required.** It stops being the requirement and becomes a subordinate `gr_scenario` child, which is the settled `Q3f` demote-and-retain shape — and it doubles as the within-run comparison of the old shape against the new, same rule and both shapes side by side, which is a far stronger comparison than one across two corpora separated by run-to-run noise.

**Nothing is migrated from the old corpora.** The 470-rule and 815-rule outputs are the products of the *old* extractor and are reference data for Milestone 1.5 only. After the extractor is rewritten, a completely new analysis is run from the top of the `code-modernization` pipeline — preflight, assess, map, extract-rules — and the store is populated from that. Do not attempt to read an old-format rule into the new schema.

### Terms this plan uses

A **business rule** here is a statement about what the business requires, such as "when a purchase order is open, the Order Service must recalculate the quantity due within the same transaction." A **citation** is a repository-relative file path plus a start and end line, identifying the source lines a rule was mined from. **Drift** means the cited code changed after the rule was written, so the rule may no longer describe it. A **clone** means two different places in the codebase contain byte-identical code. **Provenance** means the record of how a value was produced — computed deterministically, or inferred by a language model.

**Behavioral** versus **definitional** is a distinction you must implement and it is not decoration. A behavioral rule can be violated at run time ("the Order Service must record a vendor number"). A definitional rule cannot be violated, because it defines what something *is* ("a closed purchase order never carries an open balance"). They take different modal verbs and different sentence templates, and a validator check exists specifically to catch a statement using the wrong class's verb.

## Plan of Work

The work divides into six milestones, only the first four of which this plan specifies. Milestone 0 builds the migration mechanism, because without it no durable table can ever gain a column. Milestone 1 builds the store, the validator, the identity module, the search surfaces, the merge, and the command-line interface, and wires the rule extractor into it end to end. Milestone 1.5 measures the result against the two existing NNG corpora. Milestone 2 adds the four other producers against the same schema. Milestone 3 adds a vocabulary layer once there is a review loop to populate it, and takes ownership of data objects. Milestone 4 — the review experience — is declared here and specified elsewhere, in `docs/exec-plans/pending/reqs-review-ui.md`.

Within Milestone 1 the order matters. The identity module comes first because the schema's keys depend on it. The tables come next. The validator and the search surfaces can then be built in either order. Step 6a — which is both the extractor rewrite and the ingest field map — must precede the merge, because `dedupe_key` takes `rule_class` and `pattern` as inputs and both now arrive from the extractor, so nothing can be keyed until the extractor emits them. The merge itself needs the tables *and* the vector collection, because its second stage searches for near-duplicates. The command-line interface comes last, exposing what the layers below already do.

**One sequencing consequence is easy to miss and expensive to get wrong.** Step 6a changes `/modernize-extract-rules`, so every extraction run taken *before* that change produces the old Given/When/Then shape with no `ruleClass`, `pattern` or `statement` — and such a file cannot be ingested, because `statement` is `NOT NULL` and `rule_class` feeds both dedupe keys. There is no conversion path and none should be written (the Decision Log's no-migration commitment covers this too). So do not run extraction for real until Step 6a is done. Use small hand-written JSON fixtures in the new shape for every test before that point; they are cheaper, deterministic, and they are what the merge acceptance test wants anyway.

One governing principle applies to every field you add, and it is named in the design draft as PRINCIPLE-1. State it plainly: **deterministic first; a language model only when the deterministic path yields nothing; never blend the two in one field; never let an inferred value into a computed total; and always report the inference rate.** In practice this means every field that a model might fill carries a `provenance` marker, and any aggregate you compute either excludes inferred values or reports them separately. Apply it by default to fields this plan does not enumerate, and record any deviation in the Decision Log.

## Milestone 0: a versioned schema migration mechanism, and the output layout

This milestone does two independent pieces of groundwork, both of which have to be right before a durable store exists: schema evolution, and *where the files live*. They are unrelated in mechanism and are described separately below.

At the end of the first half, both SQLite databases carry a schema version number, and adding a column to either one is a supported, tested operation that does not destroy data. Nothing user-visible changes yet; the proof is a test that creates a database at version 1, runs the migration runner, and observes both the new column and the preserved rows.

At the end of the second half, nothing this toolchain generates is written inside the analyzed repository any more. Everything lands under `analysis/<system>/`, the same place `/modernize-assess` and `/modernize-map` already write, and the pulled client code is untouched.

Today neither database can evolve. Grep for `ALTER TABLE` under `tools/legacylift_search/src/` and every hit is in `extractors.py` (lines 449, 454, 966, 1742, 1810) — comments, docstrings and one log message belonging to `_SQL_FK_RE`, the regular expression that *parses* `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY` out of a client's SQL schema files. Not one of them is a statement that alters our own schema; there is no such statement anywhere. There is no `PRAGMA user_version` anywhere. `SCHEMA_VERSION = "1"` at `indexer.py:38` is written into the `index_metadata` table at `indexer.py:666` and reported at `:686` and `:1194`, but it is never compared against anything. So it is a label, not a mechanism. Adding a *table* is free today, because `migrate()` uses `CREATE TABLE IF NOT EXISTS`. Adding a *column* requires deleting the database with `index --reset`.

Create `src/legacylift_search/migrations.py`. It defines a migration as a small named unit: a target version number, a human-readable description, and a function taking an open `sqlite3.Connection`. Migrations are **forward-only** and ordered by version. The runner reads `PRAGMA user_version`, applies every migration whose version is greater, in ascending order, each inside a transaction, and sets `PRAGMA user_version` to the applied version as it goes. A failure aborts that migration's transaction and stops the run, leaving the version at the last successfully applied step so a retry resumes rather than restarts.

Keep two separate migration lists, one per database, because the two files version independently. Export something like `INDEX_MIGRATIONS` and `KNOWLEDGE_MIGRATIONS`, plus a single `run_migrations(conn, migrations)` function used by both.

Four mechanics of Python's `sqlite3` will silently break the paragraph above if you write the obvious code, and all four have to be handled explicitly:

- **DDL does not get an implicit transaction.** At the default `isolation_level`, Python's `sqlite3` opens a transaction before `INSERT`/`UPDATE`/`DELETE`/`REPLACE` and **not** before `ALTER TABLE` or `CREATE`. So an `ALTER TABLE` migration auto-commits, and the promise that "a failure aborts that migration's transaction" is simply false — a half-applied migration would be permanent. The runner therefore needs `isolation_level=None` and explicit `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK` around each migration.
- **But do not leave that setting on the store's shared connection, and do not set it in `_connect`.** This is the trap inside the previous bullet, and it breaks code far away from anything you are editing. Both stores open one connection at default `isolation_level` and rely on the implicit transaction plus an explicit `conn.commit()` for the atomicity of multi-row writes — **eighteen** such sites exist (`store.py:382, 402, 464, 540, 579, 617, 686, 715, 1181, 1242, 1266, 1421, 1498`; `knowledge_store.py:157, 194, 217, 258, 364`; line numbers as of Milestone 0's own edits, which shifted them; the count was stated as "twenty" here for nine review rounds while this bullet's own enumeration listed eighteen). Switch that connection to autocommit and **every one of those `commit()` calls becomes a no-op**: each `INSERT` commits on its own, so a `upsert_chunks` or `upsert_symbols` that fails partway leaves half its rows behind instead of rolling back. No existing test would catch it, and the symptom would surface later as a mysteriously half-indexed repository. So scope the change to the run: save `conn.isolation_level`, set it to `None`, run the migrations, and restore it in a `finally`. Add a test that asserts `isolation_level` is back to its original value after `migrate()` returns — that assertion is what stops the next refactor from "simplifying" the save/restore away. (Opening a second, private connection for the runner also works and is the alternative if the save/restore reads as too subtle; it costs a second WAL reader and a locking consideration the single-connection form does not have.)
- **`PRAGMA user_version = ?` does not accept a bound parameter.** PRAGMA statements take no parameters, so the version must be interpolated into the SQL string. It is an `int` taken from your own migration list, never from input, so this is safe — but write that reason in a comment, because it looks like an injection defect to every reviewer who reads it.
- **`PRAGMA journal_mode=WAL` cannot run inside a transaction**, and neither can a change to `PRAGMA foreign_keys`. Both already run at the top of `migrate()`; keep them there, outside anything the runner wraps.
- **Wrap each migration individually, not the whole run.** One transaction around the entire run is simpler, but a failure then rolls back every migration that had succeeded, and the "resume from the last good version" property this milestone exists to provide disappears.

**Both lists ship with exactly one entry — a no-op "baseline" at version 1.** The no-op is deliberate and is worth the mild oddity of an empty migration function. With a list empty, the highest known version is 0, so the fresh-database stamp described below writes 0, which is indistinguishable from an unstamped database — meaning M0's central mechanism cannot be observed working on that database, and its tests would have to lean entirely on fixture migrations. A real version 1 makes the stamp observable, makes the fresh-versus-existing distinction testable in production shape, and costs two lines. Milestone 1 Step 2's column addition to `index.sqlite` then becomes `INDEX_MIGRATIONS` version 2.

**`KNOWLEDGE_MIGRATIONS` needs that baseline just as much as `INDEX_MIGRATIONS` does — do not ship one and not the other.** Milestone 1 Step 3 adds the GR tables through `migrate()`'s `CREATE TABLE IF NOT EXISTS`, so `knowledge.sqlite` gains no *migration* in this plan and it is tempting to leave its list empty. Do not: every `knowledge.sqlite` in existence, fresh or not, then sits at version 0 forever, and the first real column addition to a GR table — Milestone 2 or 3, or any schema correction after review starts — is applied to freshly created databases that already have that column from the baseline `migrate()`. The per-migration `PRAGMA table_info` guard makes that survivable rather than fatal, but relying on it means the version number is decorative on the one database that holds irreplaceable human judgment. With the baseline in place both files behave identically: an existing database gets the no-op and is stamped 1, a fresh one is created by `migrate()` and stamped 1, and both end at the same version with the same schema.

Beyond that baseline there is nothing to migrate yet — every table that exists today is created by `migrate()`. So this milestone's tests still exercise the *runner* with throwaway fixture migrations defined in the test module. That is the point of building the mechanism first: the first real column addition arrives on a tested runner instead of being the thing that debugs it.

The interaction with the existing `CREATE TABLE IF NOT EXISTS` style needs care, and getting it wrong is the main risk in this milestone. Both `migrate()` methods must keep running exactly as they do — they are what creates a database from nothing. The migration runner is *additional*, and it runs immediately after `migrate()`. So the contract is: `migrate()` brings a missing or empty database up to the current *baseline* schema, and the migration runner brings an *existing older* database forward. A brand-new database therefore gets the baseline from `migrate()` and must then be stamped at the current version so the runner does not try to re-apply column additions to tables that were just created with those columns present. Implement that stamp explicitly: after `migrate()` on a database whose `user_version` is 0 and which has just been created, set `user_version` to the highest known migration version. Detect "just created" by querying `SELECT count(*) FROM sqlite_master WHERE type='table'` and finding zero — and note **when** that query has to run, because the obvious wiring gets it wrong. The snapshot must be taken *before* any `CREATE TABLE` executes:

- In `SQLiteStore.migrate()`, take it in the first few lines of the method, right after the two `PRAGMA` statements, and hold it in a local until the runner call at the end of the same method.
- In `KnowledgeStore.__init__`, take it *before* the `self.migrate()` call, not after.

A check taken after `migrate()` always sees tables and would stamp nothing, leaving every fresh database at version 0 and re-running every column addition against columns that already exist.

Every migration function must itself be idempotent where cheaply possible — check for the column before adding it, using `PRAGMA table_info(<table>)` — so that a partially applied state can be re-run safely.

Wire the runner into both stores. In `KnowledgeStore.__init__`, call the runner right after the existing `self.migrate()`. In `SQLiteStore`, call it at the end of `migrate()` itself, since callers invoke `migrate()` explicitly and there is no other common entry point.

Add `tests/test_migrations.py`. It must contain at least: a test that a fresh database ends at the highest known version with no migration functions executed; a test that a database stamped at an earlier version has the intervening migrations applied in order; a test that rows present before a column addition are still present with the new column defaulted afterward; a test that re-running the runner is a no-op; and a test that a deliberately failing migration leaves `user_version` at the last good value and does not commit its partial work.

### The output layout: everything generated moves under `analysis/<system>/`

The second half of this milestone. It is here rather than in Milestone 1 because Step 9's export path, Step 5's vector collection and the backup advice in `Idempotence and Recovery` all name locations, and every one of them is wrong until this lands.

**What is wrong today.** The `code-modernization` plugin, which owns `/modernize-extract-rules` and everything upstream of it, uses a two-directory convention per application: `<app>/legacy/<system>/` holds the client's code, pulled from their repository and never written to, and `<app>/analysis/<system>/` holds everything the tooling generates — `ASSESSMENT.md`, `domains.json`, `topology.json`, `BUSINESS_RULES.md` and the rest. `legacylift_search` predates that convention and does not follow it. Its two path settings, `index_dir` defaulting to `legacylift-docs/index/code-search` and `knowledge_dir` defaulting to `legacylift-docs/knowledge` (`config.py:101-105`), are resolved relative to `--repo-root` — which points at the *code* — so the index and the knowledge store are written **inside the client checkout**. On the NNG unit that is 316 MB of `index.sqlite` plus Chroma and 484 KB of knowledge store sitting in a pulled repository whose own `.gitignore` says nothing about `legacylift-docs/`, so it shows in the client's `git status` and is one `git add -A` away from entering their history. This plan then proposed to add `requirements.jsonl` — a file that is *meant* to be committed — to the same wrong place.

**The target layout**, which is simply the plugin's convention applied without exception:

        <app>/legacy/<system>/                 pulled code; nothing is ever written here
        <app>/analysis/<system>/               everything generated
            ASSESSMENT.md, domains.json, BUSINESS_RULES.md, ...
            index/code-search/                 index.sqlite and its chroma/ subdirectory
            knowledge/                         knowledge.sqlite, the gr_statements collection, requirements.jsonl

Everything moves, not just the durable half. Leaving the 316 MB index behind would solve the part that is cheap and leave the part that is the actual pollution.

**How the paths resolve, and why not by derivation alone.** Keep `--repo-root` meaning the code, and keep `resolve_index_dir` and `resolve_knowledge_dir` (`config.py:269-302`) as the single entry points — this is a changed default plus an override, not a new mechanism. The rule: if `repo_root`'s parent directory is named `legacy` and a sibling `../../analysis/<basename of repo_root>` exists, resolve both directories underneath that; otherwise fall back to today's `repo_root/legacylift-docs/`. Add a manifest setting named `analysis_dir`, alongside `index_dir` and `knowledge_dir` at `config.py:101-105`, plus a matching `--analysis-dir` flag that overrides the whole question, for a layout that matches neither shape. Name the key here rather than at implementation time: a manifest setting is user-facing and permanent.

**The full precedence, written down because the two-branch rule above is not the whole story and an implementer will hit the gap immediately.** `index_dir` and `knowledge_dir` are existing settings that some manifest may already carry, so each resolver runs four branches in this order: an **absolute** setting is used as-is; otherwise a setting that **differs from the packaged default** is treated as explicitly configured and resolves against `repo_root` exactly as it always has — *unless* an explicit `analysis_dir` is set, in which case the override wins, because "overrides the whole question" has to mean it; otherwise the detected analysis directory; otherwise today's `legacylift-docs/` fallback. The third clause of that second branch is the one worth stating: without it, a manifest carrying a non-default relative `index_dir` would keep writing the index **inside the client checkout** while the knowledge store obeyed the override, splitting the two stores across two roots and silently ignoring the flag for the larger half — the exact pollution this section exists to end. Both halves have tests.

**And be consistent about what a relative path is relative to**, because the flag and the manifest key are not the same thing. A relative `--analysis-dir` on the command line resolves against the **current working directory**, the way any other CLI path argument does, on every command that offers it; a relative `analysis_dir` in the **manifest** resolves against `repo_root`, like its two siblings. The flag was briefly inconsistent between the commands that go through `resolve_paths` and the three that set the manifest field directly, which made the same `--analysis-dir out` name two different directories depending on which command was typed.

Then the part that makes a wrong guess survivable: **every command prints the index and knowledge paths it resolved, on every run.** A path convention that guesses must be inspectable, or the failure mode is a second empty store created silently beside a populated one — which is the same class of defect as `KnowledgeStore` materializing an empty database when a caller forgets the `Path.exists()` check, and it is far more confusing because both databases are real. **Print them to stderr, not stdout**, following the house precedent at `cli.py:1490`, where the `coverage` command routes its warning through `Console(stderr=True)` so that `--json` output stays parseable. Several `requirements` commands take `--json` (Step 8), and a resolved-path banner on stdout would corrupt every one of them for any caller parsing the output.

Note that `repos/ctcm/ctcm-api` has no `legacy/` parent, so it takes the fallback and behaves exactly as it does today. That is deliberate: the detection must not require every analyzed repository to adopt the convention.

**Relocate the existing artifacts once, and verify before deleting anything.** For each affected unit under `repos/`, move `legacy/<system>/legacylift-docs/index` and `.../knowledge` to `analysis/<system>/`. The databases store repository-relative paths, so a move is expected to be sufficient and a rebuild unnecessary — but *expected* is not *verified*, so run `stats` and `domains` against the relocated store and compare the counts against a transcript taken before the move. Only then remove the original. If the counts differ, rebuilding the NNG index is hours of work plus embedding cost, which is exactly why the verification comes first rather than after.

**Do not use `search` as part of that oracle, and note why, because the earlier wording did.** Measured during Milestone 0's own relocation: `search` on `customer.ple.nng.app` is *nondeterministic across processes*. Interleaved A/B runs — eight against the unmoved original and eight against the copy — returned the same roughly even split between two different rank-1 hits from **both** locations, so a single-run comparison has close to a coin-flip chance of a spurious mismatch. The fusion in `search.py:250-257` sorts on `(-score, best_rank, relative_path)`, a total order, so the variation is upstream in the vector half: Chroma returns a different neighbour set per process. The scores are pure RRF rank weights, so an identical score column across two runs proves nothing about whether the hits matched. A spurious mismatch here is precisely the signal that triggers "rebuild the index, hours plus embedding cost", which is the one outcome this verification exists to avoid. `stats` and `domains` are exact and are the whole oracle.

**One further thing that relocation measurement established, worth keeping because it is the strongest evidence for this section's premise:** ChromaDB rewrites `chroma.sqlite3` and `data_level0.bin` on every open, including a read-only query. So on any repository still taking the `legacylift-docs/` fallback, merely *searching* it dirties files inside the client's checkout — not just indexing. The hygiene argument above is broader than it first appears.

**Widen `index --reset`'s safety guard in the same change, or the relocation breaks that command outright.** `Indexer._validate_reset_path` (`indexer.py:115-227` after Milestone 0; `96-158` before it — and the class is `Indexer`, not the `IndexBuilder` this paragraph called it for nine review rounds) refuses to delete anything that is not plausibly an index directory: not a drive or filesystem root, not the user's home, not the repository root, a recognized directory name (`_INDEX_DIR_NAMES` at `:41-45`, which contains `code-search`), and finally a **descendant of `<repo_root>/legacylift-docs/`** (`:151-158`). That last check encodes the very layout this section replaces. After the move the index resolves to `<app>/analysis/<system>/index/code-search` while `--repo-root` still points at `<app>/legacy/<system>/`, so `relative_to` raises and **`index --reset` fails with a `ValueError` on every relocated repository.** Nothing in the test suite catches it, because no test anywhere exercises this guard. Notice how much of this plan reasons about what `--reset` destroys — the Decision Log's choice to put the GR tables in `knowledge.sqlite`, Step 5's placement of the `gr_statements` collection, and the whole of `Idempotence and Recovery` — so a `--reset` that merely errors out would leave every one of those statements describing a command nobody can run.

Fix it with two clauses rather than one, because each covers a case the other does not:

- **Replace the single `legacylift-docs` ancestor requirement with the two shapes this section establishes**: the target must be a descendant of `<repo_root>/legacylift-docs/` **or** of the resolved analysis directory. Those are the same two branches as the path-resolution rule above, so the guard and the resolver agree by construction rather than by maintenance. Do not instead delete the check and trust the path the resolver returned — the guard's real job is to catch a mangled manifest or an `--analysis-dir` override naming somewhere unrelated, and a check that validates the resolved path against itself catches nothing.
- **Add positive evidence that the target really is an index directory**: it contains `index.sqlite` or a `chroma/` subdirectory, or it is empty. That is what makes an override typo safe rather than merely improbable, and unlike a path-prefix rule it holds under any future layout.

Keep every existing check; this is one clause replaced and one added, not a new safety model. And write the tests, since this guard has never had any: `--reset` succeeds against the relocated NNG unit and against `repos/ctcm/ctcm-api` on the fallback path, and is refused for an override naming a directory that is neither an index directory nor empty.

**Update `.gitignore` in the same change.** The four existing artifact rules (`.gitignore:82-83` for the index, `:88-89` for the knowledge database) name `legacylift-docs` paths that will no longer be written. Add rules for the new locations — the whole of `repos/*/analysis/*/index/`, and `knowledge/knowledge.sqlite*` plus `knowledge/chroma/` under `repos/*/analysis/*/` — and note the one thing that must **not** be ignored: `analysis/<system>/knowledge/requirements.jsonl` is meant to be tracked, so ignore the database and the vector directory by name, never the `knowledge/` directory wholesale. Keep the old rules as well for as long as any repository still takes the fallback path. `repos/nng-app-legacylift-analysis/` is ignored in its entirety (`.gitignore:92`) and is unaffected either way.

Acceptance for this half: pointing the CLI at `repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app` resolves its index and knowledge paths under `analysis/customer.ple.nng.app/`, prints both, and reports the same counts it reported before the move; pointing it at `repos/ctcm/ctcm-api` still resolves to `legacylift-docs/`; **`index --reset` works on both shapes rather than raising**, and is refused for an override that names neither an index directory nor an empty one.

**The observable form of "nothing is written inside the client's code" is a filesystem assertion, not a git one:** after a full `index` run against that unit, **no `legacylift-docs/` directory exists anywhere under `legacy/customer.ple.nng.app/`**. State it that way and do not reinstate the earlier wording, which asked for `git status` in the analyzed repository to be clean. That criterion cannot fail and so proves nothing here: the checkout in this working tree is not a client repository — `git rev-parse --show-toplevel` inside it returns *this* repository's root — and `.gitignore:92` ignores the whole of `repos/nng-app-legacylift-analysis/`, so `git status` reports clean before and after regardless of what the code does. The client-repository hygiene argument in the Decision Log is about real pulled checkouts, which have their own `.git` and their own `.gitignore`; this tree does not contain one, so the property has to be verified by looking at the filesystem instead of at git.

## Milestone 1: the requirements store, end to end

At the end of this milestone an analyst can run `/modernize-extract-rules` against a legacy repository, then use `legacylift-search requirements` commands to list, inspect, validate, search, approve and export the resulting requirements — and running the extraction a second time merges rather than duplicates. That last property is the acceptance test that matters most.

### Step 1: the shared identity module

**✅ SHIPPED 2026-09-01 (`05f8eaf8`), reviewed and corrected in `9dd8d283`.** What follows is
the specification the shipped module holds to, not work outstanding — read `identity.py` and
`tests/test_identity.py` first, and change this text only if you change the code. See
`Outcomes & Retrospective` → *Milestone 1 Steps 1–2*.

Create `src/legacylift_search/identity.py`. Every consumer of these keys must call this one module; if the index, the exporter and the GR store each compute their own, they cannot join and the identity is not shared, which defeats the purpose. Export five functions:

    def normalize_path(path: str) -> str: ...
    def anchor_key(language: str, entity_class: str, qualified_name: str, relative_path: str) -> str: ...
    def file_anchor_key(relative_path: str) -> str: ...
    def content_hash(body_text: str) -> str: ...
    def new_ulid(prefix: str) -> str: ...

`new_ulid` is the surrogate-identifier generator that mints `gr_id` and `gr_run.run_id`; its exact algorithm is specified in Step 3, where the identifier format is settled. It lives here rather than in the knowledge store because it is identity, and because a second implementation appearing beside it is the failure this module exists to prevent.

**There is no `entity_class_of(kind)` function, and writing one is the defect this step exists to prevent.** An earlier version of this plan had one, and it was unbuildable: it required a total mapping from `symbols.kind` onto the closed class set, over a domain that is **not enumerable from this repository's source**. `xml_extractor.py:208` mints a kind as `f"hibernate_{tag}"` from the client's own Hibernate mapping element and `:252` as the client's Spring Webflow state element, so the code under analysis authors kinds no table can contain. Per `NORMATIVE SPEC-3` §S3.1.2, **`entity_class` is declared by whichever extractor emits the symbol** and lands in a stored `symbols.entity_class` column — Step 2 builds that. The only mapping that survives is a small compatibility shim used by Step 2's backfill for rows written before extractors declared a class, defaulting to `other` and deletable once every index has been rebuilt.

`normalize_path` converts backslashes to forward slashes and strips a leading `./`. It **must not** change case: this repository runs on Windows and analyzes code authored on Linux, so without normalization the same file hashes differently per host, but case-folding is wrong on case-sensitive filesystems.

`entity_class` is a **closed, coarse** set of exactly seven values: `type`, `function`, `field`, `table`, `column`, `file`, `other`. Write them in the module docstring. `file` is in the list because the citation fallback computes a file-level anchor and needs a class for it; `column` is in it although **nothing emits a column symbol today**, and both are named now rather than added later, because a value appended later is not a free extension.

The reason the class must be coarse is subtle and important: it goes *into a hash*, so a value that changes when the extractor improves would churn identity. The fine-grained `kind` stays a plain column where churn is harmless. **The same reasoning binds the set itself, which is why it is closed rather than suggested: adding, removing or renaming a value re-keys every `anchor_key` derived from it.** A change to this list is therefore a new key version — bump the `ak1:` prefix and recompute every anchor in both databases — and never an edit in place.

**And it binds the *assignment* just as hard, which is the half an earlier draft missed.** A mapping that feeds a hash is as load-bearing as the hash's formula. Because assignment is declared per extractor (§S3.1.2), the discipline is: **an unclassified kind is `other`, and promoting a kind out of `other` later is an `ak2:` event.** Say that where the declarations live. That is what makes the open half of the domain safe — an unrecognised framework's symbols land in `other` honestly, rather than being guessed into a class that a later improvement would move.

`file_anchor_key(relative_path)` is the file grain, specified in `NORMATIVE SPEC-3` §S3.1.1: it returns `anchor_key("", "file", "", relative_path)`. **The empty `language` is a constant for the whole class, not an absence encoding**, and it must not be "fixed" into a lookup. Two reasons, the second load-bearing. It carries no information — with `entity_class` fixed at `file` and `qualified_name` at `''`, the only varying input is the path, which determines the extension, which determines the language; measured across both NNG indexes and `ctcm-api`, zero files carry more than one symbol language and zero symbols disagree with their file's. And any lookup would make a tier-1 dedupe-key input a function of index state: `repo_files.language` exists only for files the indexer accepted, `detect_language` rejects every unrecognised extension outright, and an `unresolved` citation names a path that is not in the tree at all — so the same citation would key differently before and after an `index` run. A constant cannot churn.

One accepted consequence of the `other` bucket, stated so it is not later mistaken for a defect: two symbols of genuinely different kinds that both fall to `other`, sharing a qualified name in one file, collapse to a single anchor. The span-level `content_hash` in tier 2 of `dedupe_key` separates the rules that cite them, so the damage is bounded. Do not fix it by widening the set — that is the re-keying operation described above. **Note that this consequence carries more weight than it reads like**, because `fallback_definition` — the regex fallback path, which is the single largest kind in the ETSPii index — is `other` by construction, so `other` is well populated on any repository whose files did not parse.

Add `tests/test_identity.py` coverage for the file grain alongside the symbol grain: `file_anchor_key` is stable for the same path across separator styles, differs from a symbol anchor on the same path, and is computed identically whether or not the path exists on disk.

`anchor_key` answers "which code entity does this cite?" and is computed as:

    anchor_key = "ak1:" + sha256(
        language + US + entity_class + US + qualified_name + US + normalize_path(relative_path)
    ).hexdigest()[:16]

where `US` is the single character U+001F, the ASCII unit separator. Four properties of that formula are deliberate and must not be "improved":

The delimiter must be a character that cannot occur in the inputs. Joining with `:` is broken, because both `qualified_name` and `relative_path` contain colons, dots and slashes — so `a:b` plus `c` and `a` plus `b:c` would hash identically. No validated identifier or path component contains U+001F.

The hash takes the coarse `entity_class`, never the fine `kind`, for the churn reason given above.

Paths are separator-normalized but not case-folded, as above.

The digest is truncated to **16** hexadecimal characters (64 bits), not 12. At 48 bits and 100,000 entities the chance of a collision is roughly one in 55,000, and in this store a collision would silently merge two signed-off requirements. Sixty-four bits puts it near three in ten billion.

The `ak1:` prefix is mandatory so the formula can evolve unambiguously later.

`content_hash` answers "did the cited code change, and is it a clone?" and is computed as `"ch1:" + sha256(normalized_body).hexdigest()[:16]`. Normalization converts line endings to `\n`, strips trailing whitespace on each line, and drops leading and trailing blank lines. **Comments are kept** — a rule may be cited *to* a comment, so a comment change is real drift. Do not add a second, coarser near-clone hash now.

One function, but **two grains, and both are required** (`NORMATIVE SPEC-3` section S3.2). The *entity-level* hash lives on the Layer-0 `symbols` row and answers "did this entity's code change, and is it a clone of another entity" — Step 2 adds it. The *span-level* hash lives on each GR citation row, covers exactly the cited lines, and is the tier-2 input to `dedupe_key` — Step 3 adds it. The drift matrix below needs the entity grain; the merge needs the span grain. Neither substitutes for the other.

Note what each key deliberately excludes. `anchor_key` includes the path and excludes line numbers, body text, and domain. `content_hash` includes body text and excludes path, name, language, line numbers, and domain. Because one includes the path and excludes the body while the other does the reverse, the pair is jointly informative on every reindex: same anchor and same content means unchanged; same anchor and different content means **drift**, so re-verify the requirement; different anchor and same content means a **clone or a move**; different in both means unrelated. A move is distinguishable from a clone and therefore auto-repairable — if an `anchor_key` disappears in the same reindex in which a new `anchor_key` bearing the same `content_hash` appears, that is a rename or move and the citation can be repaired automatically. A clone has no vanished predecessor.

**No key defined here takes a domain as input.** That is a hard invariant with a test attached, and Step 3 explains why.

Add `tests/test_identity.py` covering: the delimiter collision case (construct two different input tuples that would collide under a `:` join and assert they differ under U+001F); path normalization across separator styles with case preserved; digest length and prefix; and stability of `content_hash` under line-ending and trailing-whitespace changes but not under a comment change.

### Step 2: `anchor_key` and entity-level `content_hash` on the Layer-0 symbols table

**✅ SHIPPED 2026-09-01 (`05f8eaf8`), with four review defects `CR-08` … `CR-11` fixed in
`9dd8d283`.** What follows is the specification the shipped code holds to, not work outstanding.
Two things it does that this text does not say, both load-bearing: `store.symbol_body_text` falls
back to LINE bounds when the byte bounds are degenerate (`xml_extractor.py` emits
`end_byte == start_byte` by construction — 1,739 of 16,272 NNG-app symbols), and the regex
fallback must emit real BYTE offsets, which it did not (`CR-08`). See
`Outcomes & Retrospective` → *Milestone 1 Steps 1–2*.

Add **three** columns to `symbols` in `store.py`'s `migrate()` baseline — `anchor_key TEXT`, `entity_class TEXT` and `content_hash TEXT` — with an index on `anchor_key`. Populate all three on insert wherever symbols are written. This is the **first substantive migration authored in this plan**, and it is **version 2** of `INDEX_MIGRATIONS` — version 1 is Milestone 0's no-op baseline, which exists so the fresh-database stamp is observable. Milestone 0's own tests use throwaway fixture migrations, not this one.

**Fix `CR-01` before you write this migration, or it will not reach the databases it is for.** Milestone 0's code review established that `SQLiteStore.migrate()` — the only caller of `run_migrations(INDEX_MIGRATIONS)` — runs from exactly two places, `indexer.py:325` (`index`) and `:1248` (`backfill-vectors`). Every read command (`stats`, `search`, `symbols`, `callers`, `callees`, `facts`, `coverage`, `validate`) constructs `SQLiteStore` without migrating, so version 2 will not be applied to an existing index until someone re-indexes it — hours plus Bedrock spend for the NNG unit — while every read in the meantime opens a version-1 schema against code expecting version 2 and fails on `no such column: anchor_key`. Both NNG `index.sqlite` files are at `user_version` 0 right now, so this is the state Step 2 will actually meet. `KnowledgeStore.__init__` already migrates on every open, which is the shape to copy; note that doing the same for `SQLiteStore` means a read command may now write to `index.sqlite`, so decide deliberately whether the runner belongs in `_connect`, in a new explicit call on every CLI entry point, or behind a read-only version check that refuses rather than migrates.

**`entity_class` is declared, not derived, and that makes this step larger than "purely additive on the write path".** Per `NORMATIVE SPEC-3` §S3.1.2 there is no `entity_class_of(kind)` to call — the classification lives at the point of emission, in three kinds of place:

- **`src/legacylift_search/profiles/extractors.json`** — one class per entry in each profile's `definition_node_kinds`. There are **52 such entries across seven language profiles today, spanning 36 distinct kinds** (`csharp` 9, `java` 7, `python` 3, `javascript` 7, `typescript` 10, `cobol` 8, `sql` 8; `xml` has no tree-sitter profile). The per-profile numbers sum to 52 rather than 36 because most kinds appear in several profiles, and §S3.1.2 requires a class **per entry, per language** — so you write 52 declarations, not 36, and the test below iterates entries rather than distinct kinds. This is the closed half of the domain and it gets a test: **assert that every value in every profile's `definition_node_kinds`, read from the JSON at test time, has an explicit class declared.** That is the assertion that fails the build when someone tunes extraction by adding a node kind to a data file — which is otherwise a silent re-key with no code review anywhere near it. **Change the field from `list[str]` to `dict[str, str]`, kind → class, rather than adding a parallel map** — one source cannot drift from itself, and a sibling `entity_classes` object can hold a kind the list does not. Measured, the migration is nearly free: `set()`, `len()` and `in` all behave identically on a dict, so the one production reader (`extractors.py:1062`, `set(profile.definition_node_kinds)`) and four of the five test assertions need no edit at all, and only the inline fixture at `tests/test_extractors.py:89` changes. A reader that genuinely wants the kind list takes `.keys()`.
- **Framework extractors** (`xml_extractor.py` and its successors) — declared at the symbol-construction site. The extractor already knows a Hibernate `<property>` is a `field`; it should say so rather than emit `hibernate_property` and leave something downstream to infer it from the string.
- **The regex fallback** — `other` by construction. `fallback_definition` means the kind is genuinely unknown.

Budget for roughly nine symbol-construction sites across `extractors.py` and `xml_extractor.py`, plus the `Symbol` model. The judgement calls worth settling once and writing into §S3.1.2 rather than rediscovering per site: COBOL `paragraph`/`section_header`/`procedure_division` → `function`, `data_description_entry` → `field`, and `program_id_paragraph`/`file_description_entry`/`linkage_section`/`working_storage_section` → `other`; SQL `create_table`/`create_view`/`view_definition`/`table_definition`/`create_temp_table` → `table`, `create_procedure`/`create_function`/`create_trigger_statement` → `function`, `create_index_statement` → `other`; JS/TS `variable_declaration`/`lexical_declaration`/`variable_declarator` → `field`; Python `decorated_definition` → `other`, being a wrapper whose real definition is emitted separately; `spring_bean` and `hibernate_class_mapping` → `type`; the `hibernate_{tag}` children → `field`; every Webflow state, `webflow_flow` and `xml_document` → `other`.

**Two corrections to that list, because an earlier version of it had both a hole and a phantom, and this list is meant to be authoritative.** First, **`create_table` is in the `sql` profile's `definition_node_kinds`** and is the dominant SQL symbol kind; it needs a class like any other entry, and omitting it would fail the very test the first bullet above mandates. Second, **do not classify `foreign_key`.** It is a `SymbolRef` kind rather than a symbol kind — `extractors.py:1618` and `:1722` emit it into `symbol_refs`, which this step gives no `entity_class` column — so hunting for its symbol-construction site is a dead end. `NORMATIVE SPEC-3` §S3.1.2 lists it among the hand-written kinds alongside `fallback_definition` and `create_temp_table`; only the latter two are symbols. §S3.1.2 carried the same error and now records the correction beside its own classification table. Nothing else in the plan turns on it, because the mandated non-NULL assertion in `Validation and Acceptance` covers the hand-written kinds that the `extractors.json` test cannot reach.

**Three of those COBOL calls are new and the reasoning is worth keeping, because two of them are the only genuinely ambiguous entries in the closed half.** `data_description_entry` is a level-numbered data item (`05 CUST-NAME PIC X(30).`), so it is the COBOL analogue of `field_declaration` and of the JS `variable_declarator` this same list already sends to `field`. `linkage_section` and `working_storage_section` are **lexical containers whose contents are separately emitted** as `data_description_entry` symbols — which is the identical situation this list already resolves for Python `decorated_definition`, and it resolves the same way. `type` would be wrong for them: they are not declared types, and there is exactly one of each per program, so neither carries a discriminating name. They cannot collide with each other under `:488`'s accepted `other` consequence, since their qualified names differ.

**The list above settles the calls two implementers would answer differently. It is not the whole closed half, and an earlier version of this step closed with "any `definition_node_kinds` entry not named above is `other`" — which was a defect, not a default.** Measured against `extractors.json` on disk, the unnamed remainder is **16 distinct kinds spanning about 29 of the 52 entries**: every mainstream C#, Java, TypeScript, JavaScript and Python type and member kind. Sending all of them to `other` would contradict this plan's own measured reason for putting `entity_class` in the hash at all — the Decision Log cites `SecUser.StatusEnum` colliding as `enum_declaration` and `field_declaration`, and `FileDistributedCache.IsConnected` as `property_declaration` and `method_declaration`, and under a blanket `other` both pairs re-collapse along with the other 19 NNG and 2 ctcm collisions the measurement counted. **So the closed half is enumerated in full:**

| kind | class | | kind | class |
|---|---|---|---|---|
| `class_declaration` | `type` | | `method_declaration` | `function` |
| `class_definition` | `type` | | `method_definition` | `function` |
| `interface_declaration` | `type` | | `constructor_declaration` | `function` |
| `struct_declaration` | `type` | | `abstract_method_signature` | `function` |
| `enum_declaration` | `type` | | `function_declaration` | `function` |
| `record_declaration` | `type` | | `function_definition` | `function` |
| `type_alias_declaration` | `type` | | `generator_function_declaration` | `function` |
| `field_declaration` | `field` | | `property_declaration` | **`field`** |

**`property_declaration` is the one genuinely ambiguous entry in that table and the measurement decides it, not taste.** A C# property reads like a field and is implemented as accessor methods, so `function` is arguable — but the Decision Log's own collision evidence is `FileDistributedCache.IsConnected` appearing as both `property_declaration` and `method_declaration`, and mapping the first to `function` re-collapses exactly the collision that is cited as justification for the column. It is state, and it classifies as state.

**Then the default, narrowed to what it is actually for: `other` is the default for the *open* half — a framework extractor's unrecognised kind, and the regex fallback — and never for a `definition_node_kinds` entry.** Every entry in that data file carries a declared class. The mandated test keeps its intent and gains precision: it fails the build when someone adds a *new* node kind, which is the hole worth catching, instead of passing over twenty-nine existing ones classified by omission. The `ak2:` cost of promoting a kind out of `other` is then paid only for the open half, where it is genuinely unavoidable.

The three columns backfill differently, and the differences are not cosmetic:

- `entity_class` cannot be recovered from an existing row at all, because the extractor that would have declared it did not run. The migration adds the column and backfills it with the **compatibility shim** from Step 1 — a small `kind` → class table defaulting to `other`, used here and nowhere else. Note the shim's honest limitation: for a `hibernate_{tag}` kind it can only guess, so it maps what it recognises and defaults the rest to `other`, which is the correct conservative answer given that promoting out of `other` later is an `ak2:` event. **The shim is deletable once every index in use has been rebuilt**, and under this plan's workflow — a completely new analysis from `preflight` onward — that may be immediately. Confirm rather than assume before deleting it.
- `anchor_key` is computed from stored columns only, so the migration backfills it in place for every existing row, using the backfilled `entity_class` above. **Note where the path comes from: `symbols` does not have one.** Its columns are `id`, `file_id`, `language`, `name`, `qualified_name`, `kind`, `container`, `signature`, and the byte and line bounds (`store.py:241-256`); `relative_path` lives on `repo_files` and is reached by joining on `file_id`, as Step 6a's containment query also has to do. This is the first real migration anyone writes in this codebase and its shape will be copied, so get the join into it rather than leaving the next author to discover the column is missing. Apply `normalize_path` to the joined path exactly as the insert path does — if the migration and the insert normalize differently, backfilled rows and newly written rows carry different keys for the same entity and nothing anywhere raises.
- `content_hash` needs the symbol's body text, which `symbols` does not store. On an existing database the file on disk may no longer match what was indexed, so a migration-time backfill would write hashes for source that was never the source of those rows. The migration therefore adds the column and leaves it NULL. Treat NULL as "not yet hashed", never as "unchanged".

**Do not expect "the next `index` run" to populate it.** Indexing has a skip-on-unchanged fast path: `indexer.py:293-301` partitions discovered files into changed and unchanged by comparing each file's `sha256` against the stored `repo_files.sha256`, and only changed files are re-extracted (`:332`). So on any existing index the overwhelming majority of symbols are never revisited and their `content_hash` stays NULL forever — which silently disables the Step 1 drift-versus-clone matrix and the move auto-repair that depends on it, with no error anywhere to tell you.

Add a **`backfill-hashes` command** instead, modelled on the existing `backfill-vectors` at `cli.py:130` — the same shape of resumable, processes-only-what-is-missing repair command, so this follows house precedent rather than inventing a convention. It walks `symbols WHERE content_hash IS NULL`, and for each one it **first checks that the file's current on-disk `sha256` still equals the stored `repo_files.sha256`**. If it matches, the bytes on disk are provably the bytes that produced that row, so read the body, hash it, and store it. If it does not match, **skip the row and leave it NULL** — the file has drifted since indexing, and hashing it would write a hash for source that never produced that symbol, which is the precise error the migration-time backfill was rejected for. Report both counts. Those skipped rows are picked up correctly by the next real `index` run, because a drifted file is by definition a changed file.

The blunt alternative, if you would rather not add a command: have the migration clear the change-detection state so the next `index` treats every file as changed. That is correct and needs no new code, but it pays for a full re-extract of the repository. Prefer the backfill command.

Why the entity grain belongs here at all: without it the drift-versus-clone matrix in Step 1 cannot be evaluated, and the move auto-repair it promises is impossible — you cannot notice that an `anchor_key` vanished in the same reindex in which a new `anchor_key` carrying the same `content_hash` appeared if `symbols` never carried a `content_hash`.

This is **additive to the schema and to Layer-0 behavior** — `symbols.id` is unchanged and remains line-bearing, for the reasons in Context and Orientation. Do not attempt to re-key it, and do not describe this step as fixing Layer-0 identity: it gives Layer 0 a stable key, it does not make Layer 0 stably keyed. Note that "additive" is a claim about the *schema*, not about the diff: `entity_class` touches every extractor, which is the cost of putting classification where the evidence is.

`anchor_key` is not unique — two symbols can share one if a file legitimately declares the same qualified name twice — so do not add a `UNIQUE` constraint. Treat it as a lookup key that may return several rows.

### Step 3: the GR tables

**✅ SHIPPED 2026-09-01.** What follows is the specification the shipped schema holds to, not work
outstanding — read `KnowledgeStore._migrate_gr_tables` and `tests/test_gr_schema.py` (51 tests)
before changing anything here, because nearly every `CHECK`, `UNIQUE` and nullability in that DDL
closes a defect this step names, and several of them look tightenable when they are not. Six
things the shipped code decided that this text left open, all recorded so they do not read as
drift:

- **No `KNOWLEDGE_MIGRATIONS` entry.** Milestone 0's contract already covers a new *table*:
  `migrate()` uses `CREATE TABLE IF NOT EXISTS` and `KnowledgeStore.__init__` runs it on every
  open, so an existing `knowledge.sqlite` gains all eleven tables the next time anything touches
  it. A version-2 no-op would add a stamp and no behaviour. The first GR *column* addition is what
  needs an entry — that is the half Milestone 0 exists for.
- **`gr_run.complete` is a SQLite generated column**, `CASE WHEN not_accounted_for IS NOT NULL AND
  not_accounted_for = 0 THEN 1 ELSE 0 END`, so no writer can contradict the definition and
  `gate_excluded` provably leaves it alone. **It brings one quirk worth knowing before you write a
  test against that table: `PRAGMA table_info` omits generated columns** — use `PRAGMA table_xinfo`
  or `complete` reads as missing.
- **`enforcement_level`, `confidence_extraction` and `confidence_intent` carry `CHECK`s** for the
  six SBVR-derived values and for `RULES_SCHEMA`'s `High`/`Medium`/`Low` respectively. The two
  confidence columns share one scale by construction, which is what makes "each has its own
  confidence" a comparison rather than two unrelated fields.
- **`gr_citation.anchor_key` and `gr_citation_anchor.anchor_key` carry `CHECK (anchor_key <> '')`.**
  The acceptance criterion "no citation anywhere carries an empty `anchor_key`" is structural rather
  than asserted, since the file-level anchor is the floor and a real value therefore always exists.
- **`gr_run.gate_excluded = 1` requires a non-empty `gate_excluded_reason`**, by `CHECK`. A retired
  run with no reason answers none of "why did this stop blocking?".
- **There is deliberately no `state = 'draft' OR rule_class IS NOT NULL` CHECK**, though SPEC-1
  §S1.7 item 1 reads that way. It would make `set-state --to rejected` impossible on exactly the
  rows that most deserve rejecting — a bad extraction with a NULL `rule_class`. This step already
  settles it: a NULL `rule_class` blocks *approval* and is not accommodated further.

`canonical_structured_body` in `gr_body_schemas.py` is the one thing shipped here that this step
named without locating: the tier-1 `dedupe_key` discriminator is "the canonical form of the
structured body", and that form now has exactly one producer — model field order, sorted keys, no
optional whitespace, aliases so `from` stays `from`. Step 6 must call it rather than reaching for
`json.dumps` over the incoming payload, which would move the key with formatting.

What is **not** here, so it is not looked for: the `gr_fts` FTS5 table (Step 5), the Pydantic
record models (added by the steps that write them, per Interfaces and Dependencies), and the four
ownership constants (Step 6 declares them; what this step delivers is a column list
`PRAGMA table_info` can read, which is what makes their partition test executable at all).

**Five mechanics of the shipped schema that the first writer against it will otherwise discover the
hard way.** None is a design decision — they are properties of the DDL that any `INSERT` has to
respect, and each one has cost a session somewhere:

- **Four column names are SQLite keywords and must be quoted in every statement**, not only in the
  DDL: `gr_scenario."given"`, `."when"`, `."then"` and `gr_dataflow."column"`. An unquoted `when`
  is a syntax error rather than a wrong result, so this one fails loudly — but it fails at the
  first ingest, in the middle of the longest multi-table write in the system.
- **Nothing references `gr_run` by foreign key** — not `gr.first_seen_run_id`, not
  `gr_run_hit.run_id`, not `gr_merge_candidate.run_id`. That is deliberate and it exists to keep
  ingest's insert order free: Step 6 derives `gr_run`'s five counts from `gr_run_hit`, so the run
  row cannot be written until the hits are, and an FK would invert that. The cost is that a typo'd
  `run_id` will not be caught by the database; the count identity is what catches it instead.
- **Thirteen `gr` columns are NOT NULL**, so the insert cannot be built up in passes: `gr_id`,
  `kind`, `state` (defaulted `draft`), `statement`, `statement_extracted`, `modality`,
  `modality_extracted`, `modality_confirmed` (defaulted `0`), `dedupe_key`,
  `dedupe_key_anchor_only`, `extractor_payload`, `created_at`, `updated_at`. Both dedupe keys are
  among them, which means **the keys must be computed before the row is written**, not stamped
  afterwards — worth knowing because their tier-2 input is the citations' `content_hash` set, and
  the citations are inserted *after* the `gr` row they hang off. Compute, then insert both.
- **`KnowledgeStore` sets `row_factory = sqlite3.Row`**, so `cursor.fetchone() == (1, 'x')` is
  always false, however right the query is. Compare element by element or convert. This is a
  test-writing trap rather than a production one, and it looks like a schema bug for about ten
  minutes.
- **`gr_finding` and `gr_dataflow` have no surrogate key and no `ON CONFLICT` clause**, by design:
  both are refreshed by delete-then-insert over the whole `(gr_id)` or `(gr_id, direction)` scope
  inside the caller's transaction. An upsert against either satisfies the `UNIQUE` constraint and
  still strands the stale rows, which is the failure the delete half exists to prevent.

Add these tables to `KnowledgeStore.migrate()`, in `knowledge.sqlite`. They must be in the durable database precisely because they hold human judgment that must survive `index --reset`.

The central table is `gr`. Its primary key is `gr_id`, an immutable surrogate identifier assigned once at creation. **It must not be derived from content.** A human edits a requirement's wording during review; if identity were content-derived, approving that edit would mint a new requirement and destroy the sign-off. This is the single most important schema decision in the plan.

**The format is `"GR-" + ULID`, twenty-nine characters, and the ULID is generated by a function in `identity.py` rather than by a library.** A ULID is a lexicographically sortable identifier: encode a timestamp in the high bits and randomness in the low bits, and sorting the strings sorts by creation time. That property is not decoration here — Step 9 sorts the export by `gr_id`, and a reviewer listing requirements wants creation order without a join to a timestamp column.

**`new_ulid` is already built, tested and shipped — Step 1 wrote it (2026-09-01), so this paragraph is now the contract it must keep rather than an instruction to write it.** Read `identity.new_ulid` before touching anything here; if you find yourself writing a second generator, stop, because that is the exact duplication `identity.py` exists to prevent. The specified algorithm, which the shipped function implements: take the current Unix time in **milliseconds** as a 48-bit big-endian integer, append **10 cryptographically random bytes** (`secrets.token_bytes(10)`), and encode the resulting 16 bytes as **26 characters of Crockford base32** — alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ`, which omits `I`, `L`, `O` and `U` so a human transcribing an identifier cannot confuse them. Then prefix `GR-`. A constant prefix preserves sortability, and it makes an identifier self-describing wherever it appears outside the database, which is most places that matter: the CLI examples in this plan's Purpose section, the JSONL export, and `BUSINESS_RULES.md`.

No dependency is added for this. `pyproject.toml` pins thirteen packages at exact versions and the plan's own rule in `Interfaces and Dependencies` is to add none without recording the decision; a fifteen-line function does not justify one. Note the one way this differs from every other identifier in this plan: `gr_id` is **not** a hash, nothing joins on its internal structure, and no key input depends on how it was built — so unlike `dedupe_key`, two implementations that differ in detail are merely untidy rather than silently destructive. It still belongs in one function, for the same reason everything else does.

`gr_run.run_id` uses the same generator with a `RUN-` prefix, so runs sort chronologically and a run identifier is never mistaken for a requirement identifier in a log line or an error message.

`tests/test_identity.py` already covers all four required properties — 29 characters with the
expected prefix, every character after the prefix in the Crockford alphabet, identifiers minted in
sequence sorting in generation order (1,000 in a tight loop, which is what exercises the
within-a-millisecond case), and ten thousand all distinct — plus two more: `GR-` and `RUN-` never
collide, and two calls with the same prefix differ, so approving a human's edit can never mint a
new requirement.

**One behaviour the implementation has that this plan never specified, recorded so it is not
mistaken for drift and not "simplified" away.** `new_ulid` is **monotonic within a millisecond**:
under a lock, the random component is incremented rather than redrawn when the clock has not
advanced, which is the standard ULID monotonic factory. Plain per-call randomness would satisfy
"sorts in generation order" only about half the time for two calls inside the same millisecond, and
Step 9's export sorts by `gr_id`. A clock that steps backwards is treated the same way, so the
sequence never regresses. Verified outside the suite: 32,000 identifiers across 16 threads all
distinct, a clock stepped 60 s backwards does not regress the sequence, and the random-space
overflow branch bumps the timestamp. Only the thread and clock cases are unpinned by a test; add
one if you touch the function.

`gr` carries exactly the following **forty-two** columns. The count is load-bearing rather than incidental, because Step 6's four-way ownership partition is asserted against it and a column added without being classified is what the exhaustiveness test exists to catch. They are: `gr_id` primary key; `kind` (`business_rule` now, `story` reserved for Milestone 2); `name`; `state` (`draft`, `reviewed`, `approved`, `rejected`, `superseded`); `subject`; `subject_provenance` (`derived`, `derived_ambiguous` or `llm_named`); `statement`; `statement_extracted`; `as_built`; `rule_class` (`behavioral` or `definitional`, nullable only while `draft`); `pattern` (nullable, see below); `modality` (`requirement` or `expectation`); `modality_extracted`; `modality_confirmed` (boolean); `enforcement_level`; `category` (`Calculation`, `Validation`, `Lifecycle`, `Policy`); `priority` (`P0`, `P1`, `P2` — the extractor's own enum, `extract-rules.js:84`); `confidence_extraction`; `confidence_intent`; `disposition`; `structured_body` (JSON text); `structured_body_type`; `implementation_notes`; `parameters`; `rationale`; `fit_criterion`; `assumptions`; `assumptions_extracted`; `sme_question`; `suspected_defect`; `derived_from` (JSON array of `gr_id`, for Milestone 2 rollups — the rules a story summarizes, and **nothing else**); `superseded_by` (a single `gr_id`, nullable); `dedupe_key`; `dedupe_key_anchor_only`; `owner`; `reviewed_by`; `reviewed_at`; `review_note`; `extractor_payload` (JSON text); `first_seen_run_id`; and created/updated timestamps.

Name that last column `first_seen_run_id`, not `run_id`. It is a convenience index on the common case and **not** the answer to "which runs saw this rule" — `gr_run_hit` is, for the reasons given there — and a column called `run_id` sitting on `gr` invites exactly the misreading that table exists to prevent.

`name` is the extractor's plain-English rule name (`extract-rules.js:82`, a required field there). It exists because every table the CLI prints needs something short and human-readable: without it `requirements list` can show only an opaque `gr_id` or a full-sentence `statement`. It is extractor-owned and carries no notation constraints.

`implementation_notes` and `parameters` are both extractor-owned and both exist to stop abstraction from being lossy. `implementation_notes` holds the implementation-specific detail the extractor deliberately left *out* of `statement` — the legacy method names, exception types and symbols that a conforming SPEC-1 sentence in business vocabulary cannot carry. **Note where that act now happens, because Q3f's original wording no longer describes it.** Q3f settled the residue's home while the plan still had ingest re-author the extractor's scenario implementation-independent; `PR-79` deleted that step, so the abstraction is performed *inside* the extractor at the moment it authors `statement`, and `implementation_notes` is where it parks what it discarded. The extractor is therefore its writer (Step 6a) — it is the only actor that knows what it abstracted away, which is `PRINCIPLE-1` again. It also gives `V-STY-03` a destination: that check WARNs on program symbols appearing in `statement`, and this is the column where those symbols legitimately belong. `parameters` carries the extractor's constants, rates and thresholds verbatim (`extract-rules.js:95`); it is the raw form, and a `formula` structured body is the typed form, so the two coexist rather than one replacing the other.

`owner` and `reviewed_by` capture **who**, and they are here from day one because identity is unrecoverable retroactively. `owner` is who is accountable for the requirement (29148 cl. 5.2.8 *Owner* — "approves changes … reports the status"); `reviewed_by` is who last recorded a judgement through `set_state`. An approved corpus that cannot answer "who approved this" fails the exact audit claim the lifecycle exists to make, and no later milestone can backfill it. Consequences to implement: `set_state` takes a **required** reviewer identity (see Interfaces and Dependencies), the CLI resolves it from `--reviewer` or a configured default and **refuses to transition without one**, and any future review UI is required to pass it — that requirement is recorded in `docs/exec-plans/pending/reqs-review-ui.md`. Both fields are human-owned and protected by the merge.

**`reviewed_at` and `review_note` are the other two halves of that same act, and they are columns rather than prose because four places in this plan already assert observable behavior on them.** `reviewed_at` is the review timestamp `set_state` stamps on a state-changing move — Step 6 forbids the merge to touch it, Step 8 says a same-state no-op must not stamp it, and `Validation and Acceptance` asserts it changes on an approval. `review_note` is where `set-state --note` lands; without it that flag has no destination and the `note` parameter in `set_state`'s signature writes nowhere. Both are `STORE_OWNED_FIELDS`, on the same footing as `reviewed_by`: written by `set_state` alone, refused by `set-field`, never written by the merge. They are **last-write-wins and not a history** — one row records the most recent judgement, exactly as `reviewed_by` does. A per-transition audit trail is a real want and is Milestone 4's, recorded in `docs/exec-plans/pending/reqs-review-ui.md`; do not add a `gr_state_history` table here on the strength of this paragraph, because nothing in Milestone 1 reads one and it would ship untested.

`extractor_payload` is the **lossless backstop**, and it is what makes "nothing the extractor produced is silently dropped" a testable claim rather than an intention. Store the incoming rule object verbatim as JSON. Its value is not query-time access — the promoted columns and child tables cover that — it is that a later milestone can promote a field the schema does not yet name **without re-running extraction**, which on a real corpus costs hours of model time. Write the test that gives it teeth, and note carefully what it must *not* say. The tempting assertion is "every key is either mapped to a column or child row **or present in `extractor_payload``" — and that assertion can never fail, because `extractor_payload` is the verbatim object, so the second branch is true of every key unconditionally. It would pass on a `RULES_SCHEMA` that grew ten new fields ingest ignored entirely, which is the exact drift it was written to catch. So assert the stronger thing: **every key of every ingested rule object is mapped to a named column or a child-table row, unless it appears in an explicit `UNMAPPED_KEYS` constant declared next to the field map.** A new key in `RULES_SCHEMA` then fails the test until someone either maps it or adds it to that list deliberately, with the list itself being the reviewable record of what is knowingly unpromoted. `extractor_payload` stays exactly as valuable — it is what lets a later milestone promote one of those keys without re-running extraction, which on a real corpus costs hours of model time — it just is not the thing that satisfies the test.

Several of those need explanation.

`statement` and `as_built` are two fields on purpose. `as_built` is descriptive and cited — what the code does. `statement` is normative — what the business requires. Each has its own confidence, hence two confidence columns: `confidence_extraction` answers "is the citation faithful?" and `confidence_intent` answers "is this the business's intent?" Conflating them into one field is exactly the defect this plan fixes; a single "Medium" carrying both is uninformative. **`statement` is `NOT NULL`, and so is `statement_extracted`.** Step 6a is where the value comes from, including the pattern-free fallback that covers the case where `pattern` is NULL and there is therefore no §S1.4 template — read that step before writing this column's DDL. The nullability is not a free choice: four subsystems read `statement` unconditionally, and a NULL would force the shadow-equality test in Step 6 to become `statement IS statement_extracted`, because SQLite's `=` over two NULLs yields NULL rather than true — under which the merge reads every statement-less row as human-edited and stops updating it forever.

`statement_extracted` exists so that Step 6's protection of human edits is **computable**. Step 6 must not overwrite a `statement` a human has edited, which requires knowing what the extractor last produced — a fact that is unrecoverable if only the live value is stored. So the ingest path writes the extractor's text to **both** `statement` and `statement_extracted` on insert, and on a merge it writes the incoming text to `statement_extracted` always, and to `statement` **only when the two currently agree**. `statement != statement_extracted` is therefore the exact, cheap definition of "a human has edited this," and it is the predicate Step 6 tests and `stats` counts. Never expose `statement_extracted` as an editable field, and never let the human review path write it — it is extractor-owned by construction.

**Three fields need this treatment, not one, and the rule that decides which is mechanical.** A shadow column is required for exactly those fields the extractor writes *and* a human may edit, because only there is "who wrote the live value" unrecoverable. That set is `statement`, `assumptions` and `modality`, so the schema carries `statement_extracted`, `assumptions_extracted` and `modality_extracted`, all three behaving identically: written on insert alongside the live value, written always on a merge, and copied into the live value on a merge **only when the live value and the shadow currently agree**. The other human-editable fields need no shadow because they sit on one side or the other of that line — `rationale`, `fit_criterion`, `enforcement_level` and `confidence_intent` are extractor-*forbidden*, so any non-NULL value in them is human by definition, while `disposition` and `modality_confirmed` are written by ingest **on insert only** and never on a merge, so a human's value is never in contention. Apply the same test to any field a later milestone adds: if both parties can write it, it gets a shadow column, and if that feels like too many shadow columns the answer is to narrow who may write the field, not to skip the column.

**`modality` and `modality_extracted` are both `NOT NULL`, for the same reason `statement` is.** Say so in the DDL rather than leaving it to be inferred. `modality` is a required extractor field (Step 6a), so there is always a value to write; and it is shadowed, so a NULL would force `modality IS modality_extracted` in the merge's edited-test — SQLite's `=` over two NULLs yields NULL rather than true, and the merge would then read every modality-less row as human-edited and never update it again. That is the identical trap `statement`'s nullability discussion above describes, and the three shadowed columns must not differ on it: `assumptions` and `assumptions_extracted` are the exception and are **nullable**, because `assumptions` is genuinely absent on many rules, so its edited-test must be written as `IS NOT DISTINCT FROM` — spelled in SQLite as `IS` — rather than as `=`. Write that once, in the shared helper the three fields share, not three times.

Note that `modality_confirmed` is a different signal from `modality != modality_extracted` and both are kept. The shadow equality says an SME *changed* the modality; `modality_confirmed` says an SME *looked at it and agreed*, which is the more common and more valuable act and leaves the value untouched. Collapsing them would make a confirmed-as-correct rule indistinguishable from one nobody has read.

`subject` is who the statement is about, and it is **derived** from the `file_domains` table for the citing file, not invented. Because the GR tables and `file_domains` are in the same database, that is a single SQL join. When the citing file's domain is `unassigned`, fall back to a model-named subject and set `subject_provenance` to `llm_named` so the two are never blended. Never use any of the four placeholder subjects `V-SLOT-02` rejects — `the system`, `the application`, `the software`, `the program`. All four are `ERROR`s, not just the first, so a fallback that reaches for "the application" to avoid "the system" has gained nothing.

**`file_domains.domain` carries two reserved non-domains, not one, and neither may become a subject.** Alongside `unassigned` there is `excluded`, the excluded-by-design tier: `/modernize-assess` authors `exclude_globs` in `domains.json`, and `tag-domains` writes `domain = 'excluded'` with `source = 'glob'` for a file matching one and no real domain (`knowledge_store.py:127-129`). It is a deliberate declaration that the file is out of scope, and it is distinct from `unassigned`, which means nobody has classified the file yet. **Take the majority over citations carrying a *real* domain only: both sentinels are excluded from the candidate set and from the denominator.** Writing either string into `gr.subject` would put a reserved sentinel where a business noun belongs, which is the absent-versus-real rule in a new place — a requirement whose subject reads *excluded* looks like a rule about a thing called "excluded".

**A requirement all of whose citations land on sentinel domains takes the fallback with `subject_provenance = 'derived_ambiguous'`, not `llm_named`, and the distinction is the same one that justified a third provenance value in the first place.** `llm_named` means the code was never tagged and running `tag-domains` fixes it. That is false of an `excluded` file: it *was* tagged, deliberately, as out of scope, and re-running the tagger changes nothing — so routing it to `llm_named` would put an unfixable case into the bucket whose whole meaning is "fixable by tagging", and quietly depress the one rate the Concrete Steps tell you to read. `derived_ambiguous` already means "the derivation legitimately has no answer for this rule", which is exactly the situation. An all-`unassigned` requirement still takes `llm_named`, unchanged.

**Report the all-excluded count in `requirements stats` as its own figure rather than only inside `derived_ambiguous`.** It is not a subject-derivation statistic, it is a finding about the extraction: rules are being mined from code the analyst declared out of scope, so either the rule does not belong in the corpus or the `exclude_globs` are wrong. Both are actionable and neither is visible if the count is folded away.

**Say where the model-named subject comes from, because there is no language model in the CLI and an earlier version of this plan left the branch with no producer at all.** It is the `[Subject]` span of the requirement's own `statement`, read with `split_slots` (Step 4). That is a *deterministic* read at ingest of text a model already authored, which is why the provenance value is honest: the noun is the extraction agent's, not the derivation's. Three properties make this the right source rather than a convenient one. The extractor already names a concrete business subject on essentially every rule — measured, `plainEnglish` did so on 470 of 470 (Step 6a) — so the branch is populated rather than nominally available. It needs no new `RULES_SCHEMA` field, no prompt change and no second inference pass, all three of which `PRINCIPLE-1` and Step 6a rule out. And it is not the coupling Step 6a forbids: that paragraph forbids handing the extraction agents `domains.json` so they can author `gr.subject` themselves, which is a change to what the agent is asked; reading a span out of a sentence the agent already wrote is not.

**When `split_slots` cannot locate a `[Subject]` — `pattern` is NULL, or the template's keyword is absent from the statement (Step 4) — `subject` is NULL and the provenance still records which branch was taken.** NULL means "not recoverable here", which is this plan's own absent-versus-real rule; do not substitute a placeholder, and in particular do not reach for any of `V-SLOT-02`'s four literals. `subject` is therefore **nullable**, and `requirements stats` counts the NULLs as their own figure beside the three provenance values rather than folding them into `llm_named`. Note the one ordering consequence: `subject` derivation now depends on `split_slots`, so Step 4 must be built before ingest can fill this column — which the Plan of Work already requires for other reasons, since Step 4 and Step 5 both precede Step 6a.

`gr_citation` is explicitly one-to-many, so "the citing file" is not always one file and the rule has to be written down. The rule: take the domain holding a **strict majority** of the requirement's citations. If no domain holds a majority, do not derive a subject at all — fall back to the model-named subject above and set `subject_provenance` to `derived_ambiguous`. **State it as majority and nothing else.** An earlier version of this paragraph said "take the modal domain, breaking ties by the first citation in `(relative_path, start_line)` order" and then imposed the majority test in the next sentence, which makes the tie-break unreachable — a tie can never be a majority — so an implementer had two rules and no way to tell which governed. Majority is the one that carries the meaning, because it is what makes `derived_ambiguous` mean "this rule genuinely straddles domains" rather than "the counts were close." The reason for a third provenance value rather than reusing `llm_named` is that the two cases are different failures and only one of them is fixable: `llm_named` means the code was never tagged, and running `tag-domains` fixes it; `derived_ambiguous` means the rule genuinely straddles domains, which is a signal about the *rule* and often means it should be split. Blending them makes the `derived` rate in `requirements stats` dishonest, and that rate is the number the Concrete Steps section tells you to check before believing the derivation works at all.

The derived path has a precondition worth stating because it is easy to miss: `file_domains` is populated by `tag-domains`, which ingests the `analysis/<system>/domains.json` that `/modernize-assess` authors. In the real pipeline that has already happened by the time rules are extracted. In a repository that was indexed but never assessed there are no rows at all, so **every** subject silently takes the `llm_named` fallback and the derived path is never exercised. Assert on the row count before concluding the derivation works.

`rationale`, `fit_criterion` and `enforcement_level` are **SME-only: the extractor is forbidden to fill them.** They are not derivable from code — a rationale is why the business wants the rule, which is absent from the implementation. Report their fill rate as *review progress*, never as a defect count. `confidence_intent` belongs to that same forbidden set — it answers "is this the business's intent?", which no extractor can know, and it has no source in `RULES_SCHEMA` — so state it as forbidden rather than leaving it unlisted and merely unsourced. By contrast `assumptions` **is** extractor-permitted, because assumptions are often visible in the cited code, and that is exactly why it carries a shadow column: it is one of the three fields both parties may write.

`enforcement_level` must be NULL whenever `rule_class` is `definitional`, enforced by a `CHECK`. Phrase the constraint against `definitional`, as `NORMATIVE SPEC-1` section S1.7 item 3 does, and not as "only when behavioral" — the two differ for a `draft` row whose `rule_class` is still NULL, and the SPEC form is the one that lets such a row exist. A definitional rule cannot be "suggested but not enforced" because it cannot be violated at all. Its six permitted values, in decreasing severity, are `strict`, `deferred`, `pre-authorized`, `post-justified`, `override`, `guideline`. The lowest, `guideline`, is the warn-but-do-not-block tier. Note for any client-facing deliverable: these six values come from an *example* set given in the SBVR standard and derived from BMM, so cite them that way and not as a normative enumeration.

`pattern` is the notation template that `statement` follows, and it is a closed **ten-value** enum. Take the ten values and their exact sentence templates from `NORMATIVE SPEC-1` section S1.4, and the constraints from section S1.7 item 2 — do not invent a set, because `V-KW-02` and `V-SLOT-03` test against this enum and `dedupe_key` hashes it.

**`pattern` is nullable, and that is a deliberate departure from a literal reading of SPEC-1.** §S1.4 calls it "NOT NULL … on every GR **whose `disposition` makes it a rule**," which is a conditional constraint, not a blanket one — and `V-KW-06` explicitly routes an advice statement to a non-rule disposition and says not to store it "as a GR with a `pattern`." A flat `NOT NULL` would make those rows unstorable. It would also collide head-on with the rule that **nothing gates `draft`**: a bad extraction must land, and `pattern` is one of the fields the extractor cannot always supply (Step 6a). So:

- Express SPEC-1's actual constraint, **scoped to the state in which a GR is a settled rule**: `CHECK (state <> 'approved' OR pattern IS NOT NULL OR disposition IN ('not_applicable','unreachable','delegated'))`. The `state <> 'approved'` term is not a weakening and must not be removed as one — without it this constraint and Step 6a are mutually unsatisfiable. Step 6a defaults `disposition` to `captured` for every confirmed rule *and* leaves `pattern` NULL wherever the G/W/T shape is ambiguous, so the unscoped form rejects that row: the `INSERT` raises, the rule never lands at all, and **nothing gates `draft`** — the principle stated in the sentence directly above — becomes false in the one place it matters most, on a bad extraction. Scoped to `approved`, the constraint still refuses to let a NULL `pattern` into the approved corpus, which is the whole of what §S1.4 asks for.
- Keep the partition tie, written to tolerate both NULLs deliberately rather than relying on SQLite evaluating comparisons against NULL to unknown: `CHECK (rule_class IS NULL OR pattern IS NULL OR (rule_class = 'behavioral' AND pattern LIKE 'B-%') OR (rule_class = 'definitional' AND pattern LIKE 'D-%'))`.
- Enforce presence **in the approval gate**, not as a validator check: `set_state` refuses the move to `approved` while `pattern IS NULL`, and says so as a schema precondition. The gate is what a human sees; the `approved`-scoped CHECK above is defence in depth behind it, so a caller that somehow bypasses `set_state` still cannot write an approved row with a NULL `pattern`. The gate must fire *first*, because a raw SQLite `CHECK constraint failed` message names no finding and tells a reviewer nothing. This matters procedurally — SPEC-1 says no check may be added without amending it, and a precondition inside the gate is not a check, so this stays SPEC-faithful. In practice the gate rarely fires on `pattern` alone, because a NULL `pattern` travels with a NULL `rule_class` and `V-CLASS-01` already blocks that as an `ERROR`.

A NULL `rule_class` is an extraction failure rather than an expected state, so it blocks approval instead of being accommodated further.

`disposition` answers "was every rule carried forward?" — a different question from chunk coverage, which answers "did we look at all the code?" Keep both. It converts an unfalsifiable claim ("we found 470 rules") into an auditable one ("67 rules, 46 captured, 21 not applicable, 0 unaccounted"). Since no benchmark or ground truth exists for extraction quality, auditable *completeness* is the only honest claim available; do not claim accuracy anywhere.

**`gr.disposition` takes only four values — `captured`, `not_applicable`, `unreachable`, `delegated` — and `not_accounted_for` moves to `gr_run`.** The five-value set in the design draft mixes two scopes. The first four describe a rule the extractor actually found, so they belong on the rule. `not_accounted_for` describes *code the extractor could not account for*, which is by definition not a rule and has no `gr` row to sit on; putting it there forces a phantom record for every gap, or else the value is simply never used and the gate that depends on it is vacuous. So `gr_run` carries `not_accounted_for` as a count taken from the coverage step.

**Take that count from the coverage payload's `uncovered` integer, never from the length of `uncovered_chunks`.** The two disagree by design, and the design is documented rather than accidental. `SQLiteStore.coverage` returns *every* uncovered chunk and says so in its own docstring — "callers that need a shortened list must truncate `uncovered_chunks` itself (e.g. by slicing the result); this method returns every uncovered chunk so counts stay exact" (`store.py:1064-1065`) — and the `coverage` command performs exactly that truncation at `cli.py:1471`, `listed = result.uncovered_chunks[: max(limit, 0)]`, while the workflow invokes it with `--limit 40` (`extract-rules.js:212-213`). So the list a run hands ingest is capped at forty entries while the integer sitting beside it in the same payload is exact. Count the list and any corpus with more than forty unaccounted chunks reports exactly forty — and, worse for something billed as a gate, a run sitting at the cap becomes indistinguishable from one genuinely near-complete. `uncovered_chunks` is a display sample; derive no number from its length.

Then say so where the two disagree, rather than picking one silently: when `len(uncovered_chunks) < uncovered`, `requirements ingest` reports the list as *40 of 512 shown* at the moment it reads the payload, so the sample is never mistaken for the set. Note that `requirements stats` needs no such caveat and must not invent one — it reads the stored `not_accounted_for`, which is the exact figure, and the truncated list is never persisted. Those three lines at ingest are what stop the cap being reintroduced the next time this payload changes shape, and they are the same discipline as Step 5's collection-shortfall check. Note that this is the absent-versus-real rule applied to a *derived* value rather than a stored column: a count read off the wrong field of a perfectly correct payload fails exactly the way a NULL stored as zero does.

**`not_accounted_for` is NULLABLE, and NULL means "never measured" — it is not zero.** This is the difference between a gate and the appearance of one. The workflow returns `coverage: lastCoverage`, which is **`null`** whenever `repoRoot` was omitted, no index existed, or the coverage command failed. Be precise about the shape, because the tempting summary is wrong: the agent's contract does specify a failure payload of `{"skipped": true, …, "uncovered": 0, "uncovered_chunks": []}` (`extract-rules.js:215`), but the helper that calls it normalizes any falsy-or-skipped result to `null` before returning (`extract-rules.js:229`), so that zero-bearing object is consumed there and **never reaches the return value**. What ingest actually sees is either `null` or a real measurement.

That distinction matters for what you write and what you can test. The defect the nullable column exists to prevent is real either way — store a zero for an unmeasured run and the arithmetic says the run is complete, `gr_run.complete` goes to 1, and `export` waves through a corpus whose coverage nobody ever looked at, the gate passing most confidently in the one case it should stop. But the path that delivers the zero is the field map reading a raw agent result rather than the workflow's return value, which is exactly the kind of re-pointing a later milestone does. So keep both branches: write NULL when `coverage` is `null` **or** carries `skipped: true`. The second branch is belt-and-braces rather than a live case, and it is worth two lines for the same reason `PR-51` kept a value with only one real case — a defensive branch whose reachability is documented is better than one silently removed. Its test needs a synthetic fixture, because the workflow cannot produce that shape. Define completeness as `complete = (not_accounted_for IS NOT NULL AND not_accounted_for = 0)`, so unmeasured falls to the same side as incomplete without pretending to be it.

**The completeness gate is enforced, not advisory, and here is exactly what it blocks.** Any run whose `complete` is 0 — whether because `not_accounted_for > 0` or because it is NULL — is printed by `requirements stats` as not complete rather than silently summed into the totals, and `requirements export` **refuses** unless `--allow-incomplete` is passed, in which case the incompleteness is written into the export itself.

**Scope that refusal to the runs that actually contributed rows to this export, computed through `gr_run_hit` — not to every run in the store.** The export emits requirements, not runs, and after a few merges a requirement is typically carried by several runs of differing completeness, so "refuses it" needs a referent or three different implementations are equally defensible. A run whose rules were all superseded, or which falls outside the export's own selection, has no bearing on what leaves the machine and must not block it. The opposite reading — gate on the most recent run only — is worse and is the one to rule out explicitly: a single clean run would launder a corpus built mostly from unmeasured ones.

**Give the gate two exits that do not require re-running extraction, because otherwise it will be routed around.** The first ingest against a new repository is the one most likely to have run without `repoRoot`, so its `not_accounted_for` is NULL, and coverage cannot be recovered afterwards — the extraction that would have measured it is over. Under a naive gate that run blocks every export for the life of the store, and since the JSONL export is the only durable backup of a gitignored database (Step 9), a permanent refusal does not protect anyone: it teaches the analyst to pass `--allow-incomplete` by reflex, and a flag passed by reflex is not a gate. So:

- **Re-measure, honestly.** `legacylift-search coverage` already answers the same question from the index, independently of any extraction. A `requirements set-run-coverage` records a fresh measurement against a run — stamped with when it was taken and that it was taken this way, never silently backdated — which clears a NULL on its merits rather than by assertion.
- **Retire a run.** A superseded exploratory run can be marked excluded from the gate on `gr_run`, with a required reason, so its rules remain in the corpus while it stops blocking. This is a human judgement and is logged as one.

`--allow-incomplete` then keeps its proper meaning: the deliberate act of exporting a corpus known to be incomplete, with that fact written into the file rather than argued about later. Export is the right place for the hard stop because the export is what leaves the machine and reaches a client — an incomplete corpus presented as complete is the specific failure this gate exists to prevent. **`stats` and the export note must distinguish the two reasons in words**, because they call for different actions: "37 chunks unaccounted for" is a coverage result to go and close, while "coverage not measured — completeness unknown" means re-run extraction with `repoRoot` set against a repository that has an index. Collapsing them into one "incomplete" label loses the only actionable part.

Ingest defaults `disposition` to `captured` for every confirmed rule **on insert, and never touches it again on a merge**, so a reviewer's `not_applicable` survives re-extraction; a human sets the other three with `set-field`. Be honest about what that means for Milestone 1: with everything defaulted to `captured`, the *distribution* of dispositions is not yet evidence of anything, and only the `gr_run` gate carries real information. The distribution becomes meaningful once review starts, which is Milestone 4's territory.

`structured_body` is one JSON column discriminated by `structured_body_type`, which takes `decision_table`, `state_transition`, `formula`, or `invariant`, and is zero-or-one per requirement. Validate the JSON against a per-type schema on write; keep the four schemas together in one module, `src/legacylift_search/gr_body_schemas.py`, one per `structured_body_type`, expressed with the `pydantic` already in the dependency set rather than adding a JSON-Schema validator. Treat automatic invariant inference as out of scope; the `invariant` type is for hand- or model-authored invariants.

**The four payloads are specified here rather than left to the implementer, because the extractor prompt in Step 6a has to ask for them and a payload shape invented at implementation time cannot be asked for in advance:**

        decision_table   {hitPolicy: "UNIQUE"|"FIRST"|"PRIORITY"|"ANY"|"COLLECT",
                          inputs:  [{label, expression, typeRef}],
                          outputs: [{label, typeRef}],
                          rules:   [{inputEntries: [str], outputEntries: [str], annotation?}]}
        state_transition {states: [str], initial: str|null,
                          transitions: [{from, to, trigger, guard?}]}
        formula          {scale, meter, expression, variables: [{name, meaning, unit?}]}
        invariant        {expression, scope, notation: "prose"|"ocl"|"sql"}

**`decision_table` is a transcription of DMN 1.5's `<decisionTable>` element, not a format this plan invented** — `hitPolicy`, `input`/`inputExpression`, `output`, and `rule` with its `inputEntry`/`outputEntry` children are that element's own field set, so a body conforming to this schema serializes to DMN 1.5 XML mechanically. That is what "DMN-shaped" means and it is why an ad-hoc table format is forbidden: the executability argument in Step 10 depends on the payload being convertible without a second design step. Note the consequence for that step: **`len(rules)` is exactly the per-table rule count Step 10 must measure**, so the mandatory measurement becomes one query rather than a bespoke count. `formula` is Planguage's `Scale` and `Meter` plus the expression itself, per Q3c. Each `inputEntries` list must be the same length as `inputs`, and each `outputEntries` list the same length as `outputs`; enforce that in the model rather than leaving a ragged table to fail later at conversion time.

**The workflow's top-level result keys are not the names this plan uses, and the field map has to
follow the workflow.** Measured against `workflows/extract-rules.js` on 2026-09-02: the returned
object is `{system, rounds, confirmedRules, rejectedRules, dataObjects, injectionFlags, coverage,
stats}`. So the rule array is **`confirmedRules`, not `rules`**, `rounds_run` comes from `rounds`,
and `injection_flags` from `injectionFlags`. Ingest accepts both `confirmedRules` and `rules` so a
hand-written fixture keeps working, but **`confirmedRules` is the real one** — a field map written
from this plan's prose alone finds no rules at all and reports a successful ingest of zero. This
also confirms what Step 10 says about `round_cap`, `stop_reason` and `new_rules_in_final_round`:
they genuinely have no producer in the return value and must be added to the workflow before they
can be stored.

`dedupe_key` answers "have I extracted this rule before?" and is **never** a foreign-key target. Compute it as:

    dedupe_key = "dk1:" + sha256(
        US.join(sorted(anchor_keys)) + US + rule_class + US + pattern + US + discriminator
    ).hexdigest()[:16]

where `US` is the same U+001F separator `anchor_key` uses. It joins the sorted anchor list as well as the four top-level parts, so a two-anchor rule cannot collide with a one-anchor rule whose inputs happen to concatenate to the same bytes.

**`anchor_keys` means one anchor per citation — the `gr_citation.anchor_key` primary — deduplicated and sorted across all of the requirement's citations.** It is requirement-level, not citation-level, and it is *not* the contents of `gr_citation_anchor`. This is `NORMATIVE SPEC-3` §S3.3.1 read against the `gr_citation` row §S3.3 declares, and it is written down here because "`sorted(anchor_keys)`" has two plausible readings and two implementations that read it differently mint different keys for the same rule — the silent-merge-failure class the empty-string rule below exists to prevent. `discriminator` is, in order of preference: the canonical form of the structured body if one exists (tier 1); otherwise the sorted span-level `content_hash` set from the citations, joined with `US` (tier 2); otherwise the empty string (tier 3).

**Tier 2 needs one rule SPEC-3 does not state, because §S3.3.1 contemplates a set of hashes and a set of none, never a set with a hole in it.** Step 3 requires a citation whose line range cannot be read to insert with a NULL `content_hash` rather than being dropped, so a requirement can hold two citations of which one has a hash and one does not. **Each citation contributes either its `content_hash` or, when that is NULL, the literal string `ch0:none`.** Then deduplicate, sort, and join with `US` as before. Two properties are the reason for a sentinel rather than the obvious alternatives:

- **A missing element must be encodable, not absent.** Dropping NULL members and joining what is left is the tempting reading of "set", and it is the same defect as spelling a missing top-level part `None` — two correct implementations disagree about whether a hole shrinks the set or fills it, mint different keys for the same rule, and the merge silently stops matching with nothing raised anywhere. This is the third place in `dedupe_key` alone where that rule applies.
- **The sentinel is what keeps the three tiers distinguishable.** Encode a hole as `''` and a requirement whose every citation is unreadable produces the joined string `''` — byte-identical to tier 3, which means "this rule has no citations and no typed body at all." Those are different facts about a rule and must not share an encoding. With `ch0:none`, tier 2 fires whenever the requirement has at least one citation and tier 3 fires only when it has none, so the tier a key came from is recoverable from the key's inputs.

Note that tier 3 is close to unreachable for rules from this extractor — `source` is a required field of `RULES_SCHEMA` and Step 3 forbids dropping a citation — so it exists for Milestone 2's other producers and for citations a human adds during review. Do not delete it as dead code on the strength of a Milestone 1 corpus.

**Every part of the input is a string, and a missing part is the empty string — never the literal `None` or `NULL`.** The formula is hashed, so an unencodable part is not a nullable column, it is an ambiguity: two correct implementations that spell a missing discriminator differently produce different keys for the same rule and the merge silently stops working.

**The key is recomputed on extractor-owned writes only, never on a human edit.** This is a deliberate refinement of `NORMATIVE SPEC-3` section S3.3, whose table says "recomputed on every write" — see the Decision Log. `rule_class` and `pattern` are both inputs and both nullable while a record is `draft`, so under a literal reading a reviewer who fills in `rule_class` re-keys the row, and the next extraction run no longer matches it. That is the same failure the exclusion of `statement` below exists to prevent, arriving through a different door. Store the key as a column; do not derive it on read.

**Drift changes this key, and that is intended — but store a second, drift-resistant key beside it.** Tier 2 of the discriminator is the span-level `content_hash` set, so *any* edit to the cited code re-keys the rule: run N+1 produces a different `dedupe_key` for what is recognisably the same rule, misses on stage one, and falls to stage two. That behavior is correct on the merits — when the cited code changes, the rule may no longer describe it, and routing it to review is what should happen. It is not correct that it should arrive at stage two as a *cold* miss, indistinguishable from a genuinely new rule, because on a repository under active modernization drift is the normal case rather than the edge case.

So compute and store `dedupe_key_anchor_only` alongside it, over the tier-1 parts only:

    dedupe_key_anchor_only = "dka1:" + sha256(
        US.join(sorted(anchor_keys)) + US + rule_class + US + pattern
    ).hexdigest()[:16]

Stage one tries `dedupe_key`. On a miss it tries `dedupe_key_anchor_only`, and a hit there becomes a **high-confidence review candidate** carrying the reason `drift` — not an auto-merge, because no similarity signal auto-merges anything at any confidence, and this one is no exception. Same string rules as the full key: every part is a string, a missing part is the empty string.

One related mechanic to get right: when the move auto-repair from Step 1 rewrites a `gr_citation.anchor_key`, it changes a tier-1 input to both keys. **Recompute both as part of the repair** — a repair is a tooling-owned write, which the Decision Log's recompute rule permits — and stamp `gr_citation.provenance = 'repaired'` so the change is traceable to the repair rather than looking spontaneous.

Two exclusions from that key are not obvious and must not be reversed. **`statement` is excluded because a human edits it.** Dedupe compares extraction output to extraction output; a key containing human-edited text stops matching what the extractor produces next run, so the *reviewed* rules become exactly the ones that duplicate — the more human work invested, the more likely it duplicates. That is backwards and fatal. **`subject` is excluded because it is domain-derived**, so including it would put domain-retag churn back into the hash; and it is also redundant, since `anchor_key` already contains the path and `file_domains` maps path to domain.

`gr_citation` is a child table, so one requirement may cite many places and each citation carries its own drift state: `citation_id` (a surrogate integer primary key), `gr_id`, `anchor_key`, `anchor_resolution`, `relative_path`, `start_line`, `end_line`, `content_hash`, `verified_at`, `provenance`. The surrogate key exists because `gr_citation` is itself a parent — `gr_citation_anchor` below hangs off it — and the natural key is a four-column tuple that no child should have to carry. **`anchor_key` is populated at ingest, not by a later pass — Step 6a specifies the resolution rule and `anchor_resolution` records which tier of it fired. Read that before writing this table**, because both dedupe keys take the resolved anchors as their tier-1 input and an unresolved anchor that silently becomes the empty string collapses stage one into a corpus-wide auto-merge. Its `provenance` takes `extracted` (the extractor supplied this citation), `repaired` (the move auto-repair from Step 1 rewrote its `anchor_key`), or `human` (added during review) — three values, because "who put this citation here" is a different question from every other provenance field in the schema and the drift story needs to distinguish a repaired anchor from an original one. Put a `UNIQUE` constraint on `(gr_id, relative_path, start_line, end_line)` — that tuple *is* the citation's identity, and it is what Step 6's "add any new citations" tests against, so without the constraint a re-ingest quietly accumulates duplicate citation rows under a correctly-deduplicated requirement.

`gr_citation_anchor` is where the *rest* of a citation's resolved anchors live: `citation_id`, `anchor_key`, `containment`, `is_primary`, with `(citation_id, anchor_key)` as the primary key and `ON DELETE CASCADE` from `gr_citation`. `containment` takes `contains` or `intersects`, so a consumer can tell an enclosing symbol from a partially-overlapped one. A citation whose line range spans three sibling methods produces three rows here and **one** `gr_citation.anchor_key` — the primary, chosen by the deterministic rule in Step 6a.

The reason for two homes rather than one is that the two jobs pull in opposite directions, and collapsing them breaks whichever one loses. `gr_citation.anchor_key` must stay a single atomic value because the move auto-repair from Step 1 finds citations by `WHERE anchor_key = ?`; concatenating a list into that column degrades the lookup to a substring match over 16-hex-char keys, which half-works silently. And `gr_citation_anchor` must exist because "which symbols does this requirement touch?" is a first-class query this store is expected to answer — Milestone 3's vocabulary layer is its consumer — and a single primary anchor cannot answer it.

**`gr_citation_anchor` is not an input to either dedupe key, and must never become one.** The keys hash the primary anchors only. Hashing the full set instead would re-key a rule whose own cited code never changed, the moment an unrelated sibling declaration is added inside its cited range — which is the identical failure Step 6a's "innermost, not all-enclosing" rule exists to prevent, arriving one level down. This is the same split `gr_scenario` already makes: retain everything the resolution produced, keep it out of the hash. Two indexes serve the two directions and both are required — `gr_citation(anchor_key)` for the repair's lookup, and `gr_citation_anchor(anchor_key)` for the reverse query, "which requirements touch this symbol."

The child table is **derived and rebuildable** at any time from the durable `(relative_path, start_line, end_line)` triple, so a re-resolution pass after a reindex is safe and expected. But a re-resolution that changes the *primary* changes both dedupe keys, so it must go through the same path the move auto-repair does — recompute both keys, stamp `gr_citation.provenance = 'repaired'` — and never quietly rewrite the column. Note also that `anchor_key` is not unique in `symbols` (Step 2), so the join from either table back to Layer 0 returns rows rather than a row; that is the advisory-link contract, not a defect to fix with a `UNIQUE`.

`content_hash` here is the **span-level** grain from Step 1, and the ingest path is what computes it: read the cited line range out of the working tree, normalize it, hash it. It cannot come from the extractor, which returns a `path:line-line` string and no source text. When the file or the range cannot be read — the citation points past the end of the file, or the path does not exist — insert the citation with `content_hash` NULL and let the validator and `requirements show` report it. Do not guess, and do not drop the citation. The absent-path case additionally carries `anchor_resolution = 'unresolved'` (Step 6a), so the two columns together distinguish "this file is there but the range is not" from "this file is not there at all" — different diagnoses calling for different fixes, and the second is usually an extraction taken against a different checkout. The **durable anchor is the triple of path, start line and end line**; `anchor_key` here is an *advisory soft link*, refreshed by a resolution pass. The reasoning is worth internalizing, because it is why Step 2 could stay additive: a path plus a line range always still points *somewhere*, so it is wrong in a way that is detectable and repairable by re-reading the source — which is what the existing `citation-validator` skill does. An identifier either matches or is gone, offering nothing to repair from. The distinction is not stable versus unstable, it is **recoverable versus unrecoverable**.

`gr_finding` stores validator output as `gr_id`, `finding_id`, `severity`, `span`, and `message` — the human-readable text naming what failed, which `requirements validate` prints and which `set-state` quotes when it refuses an approval. `span` is the character offset range **within `statement`** that the finding points at, stored as `"start-end"`, and it is what lets a reviewer see *which words* tripped a check rather than only that one did. Most checks have one (`V-VAG-*` and `V-KW-*` all match a substring); some are record-level and have none (`V-CLASS-01`, `V-ENF-03`). **Store `''` for a record-level finding, never NULL** — `span` is part of the `UNIQUE` tuple, and SQLite treats NULLs as distinct, so a NULL span would let the same finding insert repeatedly. `(gr_id, finding_id, span)` is `UNIQUE`, and re-validating a requirement **deletes that requirement's findings and re-inserts them inside one transaction** rather than upserting row by row, so a finding that no longer fires actually disappears instead of being stranded forever.

**`gr_finding` carries one more column — `evaluated INTEGER NOT NULL DEFAULT 1` — and it is deliberately not a third severity value.** Step 4 requires that where `pattern` is NULL the three `V-SLOT` checks be emitted as *not evaluated* rather than as passing, and that state has to live somewhere: a check nobody could run and a check that ran clean are different facts, and the first is a real case on any fresh corpus rather than a hypothetical. **The column is justified by reachability, not by frequency** — do not reinstate the earlier wording calling a NULL `pattern` "the common case", which was true while ingest derived `pattern` and stopped being true when `PR-79` made the extractor emit it. Putting it on `severity` was rejected on SPEC fidelity, not taste. §S1.6 opens "**Severity has exactly two values**" and closes "no rule may be added, removed, or have its severity changed without amending SPEC-1" — and Step 4's whole claim that the keyword-anchored split is *not* an amendment rests on it re-severitying nothing. A third severity value would break that argument for a reporting concern. A separate boolean does not: `severity` keeps the severity the check *would* have carried, `evaluated = 0` says it could not be decided, and the closed two-value set is untouched. Store `''` for such a row's `span`, per the rule above, and put the reason in `message` ("not evaluated: `pattern` is NULL, so no template locates `[Subject]`").

With that, the approval gate is a single `NOT EXISTS (SELECT 1 FROM gr_finding WHERE gr_id = ? AND severity = 'ERROR' AND evaluated = 1)`. **That extra clause is defence in depth rather than load-bearing, and it is worth knowing why: a not-evaluated row can never decide an approval anyway.** The only condition that produces one is a NULL `pattern`, and the gate already refuses `approved` while `pattern IS NULL` as a schema precondition — so by the time a record is approvable every check is decidable. Write the clause regardless, because a gate that reads correctly on its own is worth more than one that is correct only in combination with a precondition three paragraphs away. Report the not-evaluated count in `requirements stats` as its own figure: it is how much of the corpus has checks nobody could run, which is a review-progress signal and not a defect count.

`gr_dataflow` stores the data-flow entries as `gr_id`, `direction` (`reads` or `writes`), `datastore`, `column`, `provenance` (`computed` or `llm_inferred`), and `explanation`, with `(gr_id, direction, datastore, column)` `UNIQUE`. **It is created in Milestone 1 and stays empty through it — neither of its two writers exists yet (Step 7).** Build the table and its constraints properly anyway; the tests for the two mechanics below run against the computed code with its flag forced on.

That `UNIQUE` does **not** work as written unless you do two things, and getting it wrong reintroduces exactly the stacking it exists to prevent. First, **store `''` rather than NULL for a table-level entry with no column.** SQLite treats NULLs as distinct in a `UNIQUE` index, so a NULL `column` lets the identical entry insert on every recompute, without error, forever. Second, **make recompute a delete-then-insert for the whole `(gr_id, direction)` pair inside one transaction**, not a row-by-row upsert. The constraint alone stops duplicates but cannot make a *stale* entry disappear — a column the requirement no longer reads would sit there permanently. This is the same idiom `gr_finding` uses below for the same reason, so the codebase carries one pattern rather than two.

`gr_scenario` is the home for the extractor's Given/When/Then, as a **0..n child** — `scenario_id` (a surrogate integer primary key), `gr_id`, `ordinal`, `given`, `when`, `then`, `and_clause`, `provenance`, with `UNIQUE (gr_id, provenance, ordinal)`. Its `provenance` takes `extracted` or `human`, the two values `gr_citation`'s own takes minus `repaired`: nothing repairs a scenario, because unlike an anchor it is not derived from anything the store can recompute. Milestone 1 writes only `extracted`; `human` is reserved for a scenario added during review and is what stops Milestone 4 from having to add a value to a stored enum.

**That uniqueness tuple is not decoration, and `provenance` is inside it for a reason.** Without a constraint here a re-ingest silently accumulates a second full set of scenarios under a correctly-deduplicated requirement — the exact bug `gr_citation`'s `UNIQUE` prevents one table over, and a worse one, because `given`/`when`/`then` are *required* on every rule of every run and so this is the largest child table in the store. The headline merge test asserts requirement count and citation count, so it would pass while this doubled underneath it. `provenance` is in the tuple so that a human scenario added during review can take an ordinal without colliding with an extracted one, and so the merge rule below can address the extracted set alone.

This is the settled Q3f shape: G/W/T is *demoted*, not discarded. It stops being the requirement — the normative record is `statement` plus `pattern` — and becomes a subordinate scenario. **Store it verbatim**, and do not read Q3f's "re-authored implementation-independent" as an instruction to rewrite it here: Step 6a keeps the extractor's G/W/T *required and unchanged*, and the implementation-independent re-authoring Q3f asked for is now what the extractor performs when it authors `statement`, with the residue landing in `gr.implementation_notes` (see that column above). Rewriting the scenario as well would destroy the within-run old-shape-versus-new comparison that retaining it exists to provide.

Retaining it is not sentimentality about the old format; three things depend on it. `given`, `when` and `then` are **required** fields of `RULES_SCHEMA`, present on every rule of every run, so with no table they are the largest single volume of extracted content that ingest silently drops. The whole point of this change is to find out whether the new requirement shape is *better than* G/W/T, and that comparison is far stronger made within one run — same rule, both shapes, side by side — than across two corpora separated by hundreds of rules of run-to-run noise. And for conditional rules, which the design research says are the bulk of any real corpus, a G/W/T scenario **is** the fit criterion; discarding it while reporting `fit_criterion` fill rate as 0% review progress throws away the answer and then complains about the question. Note that `gr_scenario` is *not* a `dedupe_key` input — it is extractor prose and would re-key on every paraphrase, which is the same defect that keeps `as_built` out of the key.

`gr_edge_case` is `edge_case_id` (a surrogate integer primary key), `gr_id`, `ordinal`, `text` and `provenance`, with `UNIQUE (gr_id, provenance, ordinal)` — the extractor's `edgeCases` array, which has no other home and is exactly the material a reviewer needs when deciding whether a rule is completely stated. It carries the same shape as `gr_scenario` deliberately, `provenance` included even though Milestone 1 writes only `extracted`: the two tables have identical lifecycles, they are refreshed by the same merge rule below, and a Milestone 4 that lets a reviewer add an edge case should not have to migrate a table to do it.

**Both child sets are refreshed on a merge, and the rule is the same one `gr_finding` and `gr_dataflow` already use.** Compare the incoming set against the stored `provenance = 'extracted'` rows for that `gr_id`; if they are identical, do nothing at all; otherwise delete that subset and insert the incoming one, inside the ingest transaction. Three properties of that phrasing are load-bearing. Scoping the delete to `extracted` is what preserves a reviewer's own scenarios and edge cases, which a blanket delete would destroy. Delete-then-insert rather than upsert is what makes a scenario the extractor no longer emits actually disappear instead of being stranded, the same reason those two tables use it. And skipping the write entirely when the sets match is Step 6's value-changing-write rule applied one level down: it keeps the surrogate keys stable across an idempotent re-ingest, which matters because Step 9's export must be byte-identical on a second run. **Serialize these children by their content and never by `scenario_id` or `edge_case_id`** — a surrogate key is store bookkeeping, and putting one in the export would make byte-identity depend on insertion order.

`gr_merge_candidate` gives stage two of the merge a persistent home, without which its output is counted and then thrown away: `gr_id_existing`, `gr_id_incoming`, `run_id`, `similarity`, `reason` (`semantic`, `range_overlap`, or `drift`), `resolution` (`merged`, `distinct`, `unresolved`), and `resolved_at`. The incoming rule is still inserted as an ordinary `draft` row — the under-merge bias is the whole design and must not be softened here — and this row records only the *suspected relationship* between two records. `resolution` is what makes it usable: a reviewer's judgement that two records are genuinely `distinct` sticks, so the same pair does not resurface on every subsequent run. Two rejected alternatives, for the record: a `candidate` value on `state` conflates the lifecycle with dedupe and mismodels a relationship between two records as a property of one; recomputing candidates on demand gives a `distinct` judgement nowhere to live.

**Put `UNIQUE (gr_id_existing, gr_id_incoming)` on it, and give it no surrogate key.** That pair *is* the relationship's identity, and without the constraint the sentence above is an intention rather than a mechanism: "has a reviewer already judged this pair?" has no lookup, so a re-raised pair appends a second row instead of finding the first, and `list --candidates` grows a duplicate for every run that re-surfaces one. This is `PR-109`'s omission — a child table specified as a bare column list while every sibling carries a key — one table further on.

**`run_id` is deliberately *outside* that tuple, and that is the load-bearing half.** Including it would key the pair per run, so run N+2 could re-raise a pair a reviewer marked `distinct` in run N — which is precisely the behavior `resolution` exists to prevent, reintroduced by the constraint meant to enforce it. `run_id` keeps its own meaning as the run that *first* raised the pair, exactly the relationship `gr.first_seen_run_id` has to `gr_run_hit`. On a later run that would re-raise an existing pair, leave the row alone unless `resolution` is `unresolved`, in which case refreshing `similarity` and `reason` is fine; never overwrite a resolved one.

**A surrogate key would be wrong here even though three sibling tables have one, and the reason is worth stating so the shape is not copied blindly.** `gr_scenario` and `gr_edge_case` take one because they are ordinal-bearing content; `gr_citation` takes one because it is itself a parent; `gr_run_hit` takes one because a natural key on `(gr_id, run_id)` would break the run-count identity, one run being able to offer two rules that land on one `gr_id`. None of those applies to a pair with attributes: two distinct incoming `gr_id`s are already two distinct rows, so the natural key is total.

`gr_run_hit` is `hit_id` (a surrogate integer primary key), `gr_id`, `run_id`, `offer_ordinal`, `outcome` (`new`, `merged`, or `candidate`), and it is the answer to "which runs saw this rule."

**The surrogate key is load-bearing, and a natural key on `(gr_id, run_id)` would break the count identity below.** One row here means *one offered rule*, not one requirement — and a single run can offer two rules that land on the same `gr_id`. The extractor's own in-run dedupe keys on `path::lowercased-name` (`extract-rules.js:256`), so two rules mined from the same lines under different names survive it and can then collide on `dedupe_key`, the first inserting as `new` and the second merging as `merged`. Two rules that both merge produce two rows that are identical in every natural column. Under a natural key one of them is refused or silently absorbed, `rules_in` under-counts, and the identity assertion fails for a reason that is not a defect in the merge. So: `hit_id` as the primary key, **no uniqueness on `(gr_id, run_id)`**, and `offer_ordinal` recording the rule's index within that run's input array so a hit traces back to the specific offered object rather than to a requirement that may have absorbed several. `rules_in` is then `COUNT(*)` for the run and the three outcome counts are a `GROUP BY` over it, and the identity holds by construction rather than by assertion.

Say plainly beside the `rules_new` comment below that **a `gr` row may carry several hits in one run**, and that this is the correct representation of two offered rules collapsing into one requirement rather than a duplicate to clean up. That collapse is itself worth counting, and `offer_ordinal` is what makes it countable: the number of offered rules that landed on a `gr_id` some other rule in the same run also landed on is one `GROUP BY` away. A single column on `gr` cannot answer it: a rule found in runs 1 and 3 keeps one value, first or last is arbitrary, and the middle is gone. `gr.first_seen_run_id` stays as the cheap indexed common case, a convenience and not the source of truth.

**Derive `gr_run`'s five counts from this table rather than storing them independently** — then `rules_in = rules_new + rules_merged + rules_candidate` is a `GROUP BY` over real rows, which is *checkable*, instead of a stored number that is merely asserted. That only holds if every offered rule produces **exactly one** `gr_run_hit` row per run, so define the three outcomes precisely:

- `new` — neither key matched; a row was inserted.
- `merged` — an exact `dedupe_key` match; the existing row was updated.
- `candidate` — the rule matched `dedupe_key_anchor_only`, or stage two surfaced it. **A row was also inserted here**, and a `gr_merge_candidate` pair recorded beside it.

Say plainly in a comment that **`rules_new` is therefore not the number of rows inserted** — `rules_new + rules_candidate` is. Someone reading `rules_new` as the insertion count and finding the table larger than it will go hunting for a bug that is not there.

This also settles an ambiguity in the identity: rejected rules never become `gr` rows at all, so `rules_rejected` stays a plain scalar on `gr_run` and is explicitly **outside** the identity. State that in a comment or someone will try to make the four numbers sum.

Coverage is per-run in `gr_run` but the *claim* this plan makes about coverage is cumulative, so compute both and never substitute one for the other. `gr_run.final_round_chunk_coverage_pct` is one run's number, and note what the extractor actually hands you: `extract-rules.js` returns `coverage: lastCoverage`, the **final round's** chunk coverage, not the run's union — so store it under a name that says so and do not present it as whole-run coverage. The cumulative figure that carries the argument for merging is **distinct files cited across all runs**, which is a single `COUNT(DISTINCT relative_path)` over `gr_citation` and needs no new column. Report it in `requirements stats`; Milestone 1.5 needs exactly that number, because the 327-versus-148-files result is what makes the case that merge accumulates coverage. Cumulative *chunk* coverage is not derivable from what the extractor returns, so do not claim it.

`gr_run` stores per-extraction-run metadata: `run_id`, `system`, `started_at`, `finished_at`, `rounds_run`, `round_cap`, `stop_reason`, `new_rules_in_final_round`, `final_round_chunk_coverage_pct`, `not_accounted_for`, `coverage_source` (`extraction` or `remeasured`, with `coverage_measured_at`, so a cleared NULL is never mistaken for a figure the run itself produced), `gate_excluded` and `gate_excluded_reason` (the retire-a-run exit above; a reason is required, and `complete` is left untouched so the record still says what was actually known), `complete`, `injection_flags` (JSON), and five named counts — `rules_in` (**confirmed** rules the extractor offered, which is what `gr_run_hit` counts; rejected rules never become `gr` rows, so anyone reconciling this against the workflow's `stats.confirmed + stats.rejected` will find a gap that is not a defect), `rules_new` (rows inserted), `rules_merged` (rows matched by an exact `dedupe_key`), `rules_candidate` (stage-two review candidates surfaced), and `rules_rejected` (the extractor's own `rejectedRules`). `rules_in` must equal `rules_new` plus `rules_merged` plus `rules_candidate` — derive all four from `gr_run_hit` per above, and assert the identity, because it is what makes the merge auditable rather than merely plausible. `rules_rejected` sits outside that identity.

**The four round fields are required, and three of them have no source in what the workflow returns today — so this is a return-value change, not just a field map.** They are how you tell "we stopped because we were done" from "we stopped while still finding rules," which is the difference between a corpus you can reason about and a truncated one. The workflow already computes every value and then discards it: `round` is returned as `rounds`, but `maxRounds` is a local clamped to `[1, 8]` (`extract-rules.js:28`), the cap condition `round >= maxRounds && dryRounds < 2` exists only to write a log line (`:380-381`), and each round's new-rule count is logged and dropped (`:321`). Add them to the object the workflow returns.

Two things to get right while doing it. First, `rounds` → `rounds_run` is a **rename**, so write the mapping down rather than assuming the names match. Second, **`cap_reached` as a boolean is the wrong shape, because there are three termination paths, not two.** Alongside running dry and hitting `maxRounds` there is a token-budget break at `:268-269` that exits the loop early, and a boolean folds that into whichever branch it happens to resemble. Store `stop_reason` as a closed enum — `dry`, `round_cap`, `budget_exhausted` — and store `round_cap` beside `rounds_run`, because "we stopped at the cap" means nothing without knowing what the cap was, and the clamp silently turns a requested 20 into 8.

Note that none of this touches an agent prompt: these fields are added to the workflow's final `return` object, not to `RULES_SCHEMA`. Step 6a *does* change `RULES_SCHEMA` and the prompts that carry it, and Milestone 1.5's write-up must disclose that (see that milestone's third constraint) — but a return-value addition has no prompt surface at all and is constrained by nothing here. An earlier version of this plan capped the extractor extension at three fields to protect that measurement; `PR-79` removed the cap, so do not read one into this paragraph.

`injection_flags` holds the workflow's `injectionFlags` — `file:line` locations where an agent found instruction-shaped text inside the analyzed source. **Surface it loudly**: print a distinct, unmissable line in `requirements stats` whenever it is non-empty, and never fold the count into a general statistics table. A prompt-injection suspect that nobody sees is worse than never having scanned for one, because the scan's existence creates the impression it was acted on. This is the one field in the schema whose value is entirely in being *read*.

`gr_import` is the home for Step 9's import marker, which that step requires and which otherwise has nowhere to live: `import_id` (a surrogate integer primary key), `source_path`, `imported_at`, `rows_read`, `rows_changed_state`. One row per `requirements import` invocation, appended and never updated. It is the smallest table in the store and it earns its place for one reason Step 9 states plainly — import is the single declared exception to "`set_state` is the only writer of `gr.state`", so a state change that arrives through it must be traceable to a specific import rather than appearing to have happened spontaneously. **It is deliberately not part of the JSONL export** (Step 9 exports requirements, and an import marker is local provenance about *this* machine), and it is deliberately not joined to `gr`: attributing each individual row to the import that last touched it would be a per-record audit trail, which is the thing the `reviewed_at` paragraph above defers to Milestone 4.

Finally, the invariant that ties this together. **Because no key takes a domain as input, re-tagging domains is a single `UPDATE ... SET domain = ?` on one row: nothing re-keys, no row is orphaned, no citation breaks.** Write that as a test: re-run `tag-domains` with a changed `domains.json` and assert that every `anchor_key`, `content_hash` and `dedupe_key` in the store is byte-identical before and after. `tests/fixtures/polyglot_repo/domains.fixture.json` already exists and is the file to mutate for the unit-level version of this test; the end-to-end version needs a repository that actually has a domain set, which is discussed under Concrete Steps. That test is the executable form of the invariant and it is required.

Be aware that none of this identity design has ever been exercised through an edit-and-reindex cycle, by this tool or by the fact-graph skill it partly replaces, because fact-graph regenerates its output wholesale. The drift matrix in Step 1 and the retag test here are therefore load-bearing verification, not documentation.

### Step 4: the notation validator and the approval gate

**✅ SHIPPED 2026-09-01.** What follows is the specification the shipped validator holds to, not
work outstanding — read `gr_validator.py`, `gr_state.py`, `tests/test_gr_validator.py` (83 tests)
and `tests/test_gr_state.py` (35) before changing anything here. **Five places where this text
under-specified and the code had to decide are recorded in `Outcomes & Retrospective` →
*Milestone 1 Step 4*; read those five before you conclude the code has drifted from this step.**
The one that matters most for a reader of this section: the interface sketch's "the six Figure-1
patterns" is **seven** — §S1.4 carries ten patterns of which three are the D5 deviations.

Create `src/legacylift_search/gr_validator.py`. It validates the `statement` field **only**. `as_built` is deliberately exempt: it records what the code does in whatever words fit, and forcing it into a normative template would destroy the distinction that having two fields exists to create.

Severity has exactly two values. `ERROR` blocks the `draft → approved` transition and nothing else. `WARN` is recorded on the record and never blocks. **Nothing gates `draft` itself** — a bad extraction must still land, because the data is the point and extraction quality cannot be assumed. No check may be added, removed, or have its severity changed without amending the specification; the finding identifiers are stable and must be emitted with every finding.

The full set of checks — **twenty-eight** of them, with exact tests, severities and stable identifiers — is specified in `docs/exec-plans/pending/reqs-to-data-store-plan-draft.md`, section `NORMATIVE SPEC-1`, subsections S1.3 through S1.9. The count breaks down as `V-CLASS` 2, `V-KW` 7, `V-SLOT` 3, `V-VAG` 9, `V-SING` 1, `V-STY` 3, `V-ENF` 3; if your implementation emits a different number of distinct identifiers, one is missing or invented. **Implement that section literally. Do not paraphrase it, re-derive it, or improve it.** It is too long to restate here without losing fidelity, and it is already exact.

SPEC-1 is also the source for two things Step 3 depends on and this plan does not restate: the ten-value `pattern` enum with its sentence templates (section S1.4) and the schema constraints the notation implies (section S1.7). Read those two subsections before writing the `gr` DDL, not after. Read §S1.2 as well — Step 6a depends on its `rule_class` decision procedure, and it sits outside the §S1.3–S1.9 range this plan's preamble names. **And read §S1.12, the amendment log**, which is outside that range too and records the **three** places §S1.3–S1.9 has been corrected: A1 and A2 in the fifth review round, and A3 in the eighth, which is the one that decides where `V-VAG-04` and `V-SING-01` fire.

**`V-STY-03` is the one check whose implementation you cannot read straight off §S1.6, so here is what to build.** SPEC-1 amendment A1 rescoped it to **items 2, 3 and 5** of the Baxter & Hendryx rubric — program symbols used as business terms, implementation technology as vocabulary, and an unabstracted variable where a named business term belongs. Items 1, 4 and 6 are not this check and §S1.6 now says where each went; item 6 in particular is a relation *between two records* and cannot be expressed in `validate_statement(gr)` at all.

Items 2 and 5 both reduce to "a code-shaped token appears in `statement`", and Layer 0 already knows which tokens those are: **match tokens in `statement` against `symbols.name` and `qualified_name` for the requirement's cited files.** That is literally the check rather than a proxy for it, and it needs no vocabulary layer. Back it with a morphological fallback for symbols the parser missed — `ALL-CAPS-WITH-HYPHENS`, `snake_case`, internal-capital `camelCase`, any token containing `_`. Item 3 takes a seed list on the same convention as the nine `V-VAG` classes, seeded from what a real corpus produces: `*Exception`, dotted lowercase message keys such as `station.physical.volume.overlap`, and framework vocabulary. Honour A1's carve-out: item 5 does not apply to the `[Value]` slot of `D-CONST` or `D-INFER`, because §S1.10 #3 is a conformant `D-INFER` containing *category 87* and *1000.00* and a naive magic-number test fires on it.

**But that lookup is a cross-database read and the validator's signature cannot make it, so pass the tokens in rather than passing a store in.** `symbols` lives in `index.sqlite` while the GR tables live in `knowledge.sqlite`, and `validate_statement(gr: GRRecord)` carries neither the requirement's citations nor any handle to Layer 0 — which is the identical objection §S1.6 uses to route rubric item 6 out of this check entirely, so it cannot be waved through for items 2 and 5. Handing the validator a `SQLiteStore` was rejected: it would make a pure, cheaply-testable function depend on two databases and a working tree, and every `V-*` test would then need an index fixture. So `validate_statement` takes a second parameter, `leaked_terms: frozenset[str]`, defaulting to empty, and the **caller** builds it — `refresh_gr_derived_sql`, which is the single place the validator is ever re-run (Step 5), and which therefore gains an optional `SQLiteStore` for exactly this. It resolves the requirement's `gr_citation.relative_path` values, reads `symbols.name` and `qualified_name` for those files, and joins in Python per `domains_cmd` at `cli.py:1095` like every other cross-database read in this plan.

An **empty `leaked_terms` is a supported state, not an error**, and it is the same state as the `resolve_anchor` store being `None`: there is no index, or none was resolved. `V-STY-03` then runs on its morphological fallback alone, which is a real check rather than a stub — `ALL-CAPS-WITH-HYPHENS`, `snake_case`, internal-capital `camelCase` and any token containing `_` catch most of what §S1.10 #10 is about. Report it honestly all the same: `requirements stats` says when the symbol half of `V-STY-03` was unavailable, for the same reason the `anchor_resolution` breakdown is reported — a rate taken with the index missing is not comparable to one taken with it present, and a silently weaker check reads as a cleaner corpus.

Because it is a `WARN` it never blocks, so imprecision here is cheap — the same trade §S1.6 already makes explicitly for `V-KW-07`. **Its rate is worth reporting in `requirements stats` for a reason beyond hygiene:** with the extractor now authoring `statement` and instructed to use business vocabulary (Step 6a), this rate measures whether that instruction worked, and it is the direct input to sizing Milestone 3's vocabulary layer. `V-KW-07`'s own heuristic, which §S1.6 leaves to the implementation, is `may` with no `only` in the same clause.

**§S1.12 carries a second amendment, A2, and it is not about `V-STY-03`.** It gives `V-VAG-09` a seed list the check previously lacked entirely — "a reference" was never defined, so before A2 that check could not be written at all. Read it before implementing it. The do-not-re-verify list under `Surprises & Discoveries` names A1 alone because A1 is the amendment that changed a check's *test*; A2 supplies a missing one rather than changing one, and like A1 it alters no count and no severity. **A third amendment, A3, was added in the eighth round** and belongs to the slot split below rather than to any single check's text: it records that `V-VAG-04` and `V-SING-01` have no site on `D-COMPUTE`, `D-CONST` or `D-INFER`. Like A1 and A2 it alters no count and no severity.

**How the validator gets at 29148 slots: a template-driven split keyed on `pattern`, and nothing more.**

Five of the twenty-eight checks are written against Figure 1's slots — `V-SLOT-01` and `V-SLOT-02` need `[Subject]`, `V-SLOT-03` needs `[Condition]`, `V-VAG-04` permits `or` inside `[Condition]` while making it an `ERROR` inside `[Action]` or `[Object]`, and `V-SING-01` bans an `and` that joins two actions inside `[Action]`. Nothing in the plan stores slots and `validate_statement` receives only flat text, so an implementer reaching for the obvious answer will write a five-slot parser. **Do not.** S1.4 says plainly that the slots are not independently nullable and that `[Object]` is *absorbed into* `[Action]` in the short construct, so the `[Action]`/`[Object]` boundary is not a real boundary and a parser that invents one will mis-parse the commonest sentence shape.

**Do not write the keyword-anchored two-part split an earlier version of this plan specified either — it is wrong for half the enum, and its failure mode is an `ERROR` on text SPEC-1 itself marks conformant.** That design said: locate the rule keyword, treat everything after it as `[Action][Object][ConstraintOfAction]`, and split everything before it into `[Condition]` and `[Subject]`. Three properties of §S1.3 and §S1.4 defeat it. **The restricted keywords are discontinuous** — `may ... only`, `may ... only if`, `can ... only`, `can ... only if` — so "the keyword's position" has two candidate answers and the `[Action][Object]` region sits *between* them rather than after them. **In `B-RESTRICT`, `D-RESTRICT` and `D-INFER` the `[Condition]` trails the keyword** (`... only if [Condition]`, `... considered [Value] if [Condition]`), so a pre-keyword search for it finds nothing and `V-SLOT-03` fires on every conformant instance. And **§S1.4 states outright that `D-COMPUTE`, `D-INFER` and `D-CONST` do not follow Figure 1's slot structure**: their post-keyword region is `[Formula]` or `[Value]`, so there is no `[Action]` there for `V-VAG-04` or `V-SING-01` to bind to. The measured consequence is that §S1.10 #3 — *An inventory item is to be considered category 87 if its purchase cost is more than 1000.00 **and** less than 5000.00*, which SPEC-1 marks ✅ conformant — trips `V-SING-01` on its `and` and `V-SLOT-03` on its unfound condition. Two `ERROR`s on a conformant example means the record can never be approved, which is the identical failure §S1.6's `V-VAG-08` carve-out exists to prevent, arriving through a different door.

**`pattern` is a stored column and it is passed to the splitter, so read the boundaries off the template it names.** §S1.4 gives an exact template per pattern, so the split is a table lookup rather than a parse:

| `pattern` | `[Subject]` | `[Action]` or `[Value]` | `[Condition]` |
|---|---|---|---|
| `B-COND`, `B-PROHIB` | first comma → keyword | after keyword — `[Action]` | start → first comma |
| `B-UNCOND` | start → keyword | after keyword — `[Action]` | — |
| `D-NEC`, `D-IMPOSS` | start → keyword | after keyword — `[Action]` | — |
| `B-RESTRICT`, `D-RESTRICT` | start → `may`/`can` | between `may`/`can` and `only` — `[Action]` | after `only if` |
| `D-INFER` | start → keyword | keyword → ` if ` — `[Value]` | after ` if ` |
| `D-COMPUTE`, `D-CONST` | start → keyword | after keyword — `[Value]` | — |

`[Object]` and `[ConstraintOfAction]` are never separated from `[Action]`, for the reason in the paragraph above: the `[Action]` column is that whole undivided region. Then the five checks wire onto it directly:

- `V-SLOT-01` fires when `[Subject]` is empty or whitespace, and `V-SLOT-02` matches the four literals — `the system`, `the application`, `the software`, `the program` — against it. Both are decidable on all ten patterns.
- `V-SLOT-03` fires when `pattern` is one of `B-COND`, `B-PROHIB`, `B-RESTRICT`, `D-RESTRICT` or `D-INFER` and no `[Condition]` span was found. The three trailing-condition forms are now found, which is the half the two-part split got wrong.
- `V-VAG-04`'s `or` prohibition and `V-SING-01`'s conjoined-action test bind to `[Action]` **only**. `or` inside `[Condition]` stays permitted, which is §S1.6's mandatory carve-out. Neither check has a site on `D-COMPUTE`, `D-CONST` or `D-INFER`, whose post-keyword region is a `[Value]` or `[Formula]` — see the amendment note below, because that is the one part of this that is not merely an implementation detail.

**Write the keyword matcher once, because four consumers must agree on what an occurrence is.** `V-KW-01`, `V-KW-04`, `V-KW-06` and this split all ask the same question and two implementations of it will disagree. The four restricted keywords match as a **pair** — the modal (`may` or `can`) plus the first following `only` in the same sentence — and count as **one** occurrence for `V-KW-04`'s at-most-one test. `V-KW-06`'s advice test is that same matcher's negative case, a `may` with no following `only`, which is why the two cannot be written separately. Get this wrong and *A branch manager may grant a spot discount only if the rental is open* carries two keywords instead of one, and `V-KW-04` fires an `ERROR` on a conformant `B-RESTRICT`.

Three properties make this the right shape rather than a shortcut. It **re-derives from the live `statement` on every validation**, so a reviewer's edit is validated as edited rather than against a stale snapshot — which is what a stored-slots design cannot do, and the edited records are exactly the ones review cares about. It produces **character offsets naturally**, which is what `gr_finding.span` already stores. And it **degrades honestly**: where `pattern` is NULL there is no template, so the three `V-SLOT` checks cannot be decided — emit them as not-evaluated rather than as passing, since a silent pass on the rows where the extractor could not decide a `pattern` would make those checks look verified when they were never run. That state is stored as `gr_finding.evaluated = 0` beside the severity the check would have carried, **never as a third `severity` value** — §S1.6 fixes severity at two values and forbids re-severitying without amending SPEC-1, which is the same rule that makes this split an implementation note rather than an amendment. See Step 3 for the column and for why the approval gate is unaffected by it. `V-VAG-04` and `V-SING-01` still run, because they need only the keyword.

**One more case needs a stated answer, because the table above cannot supply one and §S1.10's own rejected examples are full of it: `pattern` is non-NULL but the template's keyword is not in `statement`.** Every row of that table anchors on the keyword, so with no keyword there is no boundary to read. This is not a rare shape — it is what `V-KW-01`, `V-KW-02` and `V-KW-03` exist to catch, and two of the spec's ten worked examples are exactly it: #5 *The system shall validate the order* uses `shall`, which is no keyword at all, and #6 *An order always must have a customer* carries one keyword from each class. **The rule: a non-NULL `pattern` whose keyword cannot be located degrades to the same path as a NULL `pattern`** — `[Condition]` found structurally per the paragraph below, no `[Subject]`, `[Action]` or `[Value]` span, and the three `V-SLOT` checks emitted not-evaluated with `evaluated = 0`. The reason to degrade rather than guess is the cascade `PR-28` rejected: the statement does not follow the template it claims, a `V-KW` `ERROR` already says so precisely, and three more findings derived from a boundary that was never found would name the wrong problem three times over on a record whose real defect is already reported. Write it as one branch in `split_slots`, not as a per-check guard, and give it its own test driven from §S1.10 #5 and #6.

**But compute the `[Condition]` span on a NULL-`pattern` row anyway — and on a keyword-absent row, which takes the same path — structurally rather than from a template.** The two delimiters §S1.4 uses are syntactic and need no pattern to find: a leading comma clause, or a trailing `only if` / ` if ` clause. Take whichever is present. Only `V-SLOT-03` is genuinely undecidable without a template — because deciding it means knowing whether the pattern *required* a condition — so it alone is what the not-evaluated rule above is really about, and the other two `V-SLOT` checks join it for consistency rather than necessity. Skip this and `V-VAG-04`'s carve-out is silently lost on exactly the rows nobody has classified yet, so a conformant `or` inside a condition becomes an `ERROR` on the least-reviewed part of the corpus.

**Two thirds of this is an implementation note; one third is a SPEC-1 amendment, and the split between them is deliberate.** Computing the boundaries from §S1.4's own templates adds no check, removes none and re-severities none — it defines *how* a boundary the checks already assume is located, so it is an implementation note against §S1.6, the same footing as Step 6a's pattern-free fallback against §S1.4. Record it there so the next reader does not re-derive it. What is **not** a note is the statement that `V-VAG-04` and `V-SING-01` have no site on `D-COMPUTE`, `D-CONST` and `D-INFER`: that changes where a numbered check fires, which §S1.6 reserves to an amendment. It is recorded as **§S1.12 amendment A3**, and its justification is A1's exactly — the amendment adopts the reading SPEC-1's own cross-references already take, since §S1.4 says those three patterns do not follow Figure 1's slot structure and §S1.10 #3 marks a statement conformant that the other reading rejects. Read A3 before implementing either check. Write the split as one function with its own tests, not inline in five checks.

Four things in it are traps that an implementer working from intuition will get wrong, so they are called out here as well.

`V-KW-05` makes `should` un-approvable until a human intervenes, and that is intended rather than a bug to route around. It is an `ERROR` when a statement uses `should` and `enforcement_level` is NULL or is `strict`/`deferred` — and `enforcement_level` is extractor-*forbidden* (below), so every `should` rule the extractor produces carries a blocking finding until an SME sets an enforcement level with `set-field`. That is the design: `should` is only a legitimate rule keyword when the rule's enforcement level says so, and only a human can say so. Do not "fix" it by defaulting `enforcement_level`, and do not have the extractor emit `should`-shaped statements to avoid it.

The modal keywords are **disjoint by rule class**, and they are literal strings matched case-insensitively as whole words with no synonyms or inflections. **Match the longest candidate first**: `must not` and `should not` must be tested before `must` and `should`, or every prohibition is read as its positive and the split table's "after keyword" boundary lands four characters early, putting a stray `not` at the head of `[Action]`. The shared matcher below is where that ordering lives, so it is settled once. Behavioral rules use `must`, `should`, `must not`, `should not`, and `may ... only`. Definitional rules use `always`, `never`, `not always`, and `can ... only`. A statement using the other class's keyword is an `ERROR` — that is the headline check the disjointness buys. Three special-purpose definitional keywords exist for computation, derivation and constants: `is to be computed as`, `is to be considered`, and `is to be fixed at`. The phrase `is by definition` is **not** a keyword; it was asserted during design, refuted, and the refutation confirmed against the standard.

Two carve-outs are mandatory and the validator is unusable without them. First, the vagueness check that bans totality terms including `always` and `never` **must not apply** to the rule-keyword occurrence of `always` or `never` in a definitional statement — without this, the validator rejects every well-formed definitional rule. Second, the check that bans passive construction **must exempt** the three special-purpose definitional keywords, which are required passives — without this, every computation rule fails.

The absence of a constraint-of-action slot is **deliberately unchecked, and no check may be written for it.** The source standard's examples are performance-shaped, whereas mined business rules are conditional and usually have no such constraint. This sentence exists to stop a future implementer adding that check.

There are six documented deviations from ISO/IEC/IEEE 29148, listed in subsection S1.8 of the draft. Any deliverable claiming alignment with that standard must reproduce that table; a deviation not listed there is a defect rather than a decision.

The gate itself: `draft → approved` requires zero `ERROR` findings. Implement it as a guard inside the single state-transition function that `requirements set-state` calls — one code path, so no future caller can route around it — and have the refusal name the blocking findings by identifier and `message`. `requirements validate` reports the same findings without transitioning anything; it is the read-only view of the gate, not the gate.

### Step 5: full-text and vector search over requirements — SHIPPED 2026-09-02

**This step is built.** What it produced, what it corrected in the orientation block below, and
the three of its five acceptance criteria that could only be written at unit level are recorded in
`Outcomes & Retrospective` → *Milestone 1 Step 5*. Everything below is kept as written, because
Step 6 and Step 8 are its callers and the reasoning — why a pair, why under the knowledge
directory, why delete-then-insert — is what stops them re-deriving it wrongly.

> **Orientation, written 2026-09-01 at the end of Step 4 and measured rather than recalled.**
> Everything below this block is the original specification and is unchanged. Everything *in* it
> is what a fresh agent would otherwise spend a session discovering — the state Step 4 left, the
> six pieces of code that do not exist yet, and five mechanics that are not readable off the
> source. **Read this block first; the line numbers the specification cites have all drifted, and
> the correction table under `Surprises & Discoveries` is the lookup.**
>
> #### What Step 4 left, and the two seams it left open
>
> `gr_validator.validate_statement(gr: GRRecord, leaked_terms: frozenset[str]) -> list[Finding]`
> and `gr_validator.can_approve(findings) -> bool` are built and tested (83 tests), as is
> `split_slots`. `gr_state.set_state` is built (35 tests) and holds the approval gate.
> `KnowledgeStore` gained `get_gr`, `list_gr_findings`, `replace_gr_findings` and
> `apply_gr_state`. The two seams:
>
> 1. **`set_state` does not call the refresh pair.** There is a comment in it marking exactly
>    where `refresh_gr_derived_sql` (inside the transaction) and `refresh_gr_vectors` (after the
>    commit) go. Wiring those two lines is the smallest possible first commit of this step, and
>    `tests/test_gr_state.py::test_set_state_is_the_only_writer_of_gr_state` will keep you honest
>    about not adding a third write path while you are in there.
> 2. **Nothing builds `leaked_terms`, so `V-STY-03` currently runs on its morphological fallback
>    everywhere.** That is a supported state, not a defect — but it is not the shipped check, and
>    `stats` is required to say so. `refresh_gr_derived_sql` is the function that has to build it.
>
> #### The `leaked_terms` recipe, since no code does this today
>
> `refresh_gr_derived_sql` gains the optional `SQLiteStore` and `repo_root`. For each `gr_id`:
> read `SELECT DISTINCT relative_path FROM gr_citation WHERE gr_id = ?` — **there is no reader
> for that yet; add one to `KnowledgeStore` rather than inlining SQL in the new module** — then
> call `SQLiteStore.get_symbols_for_files(paths) -> dict[str, list[Symbol]]`, which already
> exists and already returns `entity_class`, and take the union of every `Symbol.name` and
> `Symbol.qualified_name`. Join in Python, per `domains_cmd`: the two databases are never
> `ATTACH`ed. **The store is optional and `None` means there is no index** — check
> `index_sqlite_path.exists()` with a plain `Path.exists()` *before* constructing a
> `SQLiteStore`, because `_connect` creates the file on its first query and an empty
> `index.sqlite` beside an unindexed repository is indistinguishable from a real one.
>
> #### Six things that do not exist and that this step must add
>
> | Add | Where | Note |
> |---|---|---|
> | `gr_fts` virtual table | `KnowledgeStore._migrate_gr_tables` | A *table* addition, so it needs **no** `KNOWLEDGE_MIGRATIONS` entry — same reasoning Step 3 records. `CREATE VIRTUAL TABLE IF NOT EXISTS` is idempotent. |
> | `ChromaVectorStore.upsert_texts` | `vector_store.py` | Sibling of `upsert_chunks`, not a generalization of it. |
> | `ChromaVectorStore.count()` | `vector_store.py` | **There is no count wrapper today.** The shortfall check needs one; `self.collection.count()` is the call. |
> | `RefreshResult`, `EmbedResult` | `models.py` | Named in `Interfaces and Dependencies` and defined nowhere. At minimum each needs to carry what `stats` and the ingest banner must report: for the SQL half, rows refreshed and findings written; for the vector half, embedded, skipped and the reason. |
> | `refresh_gr_derived_sql` / `refresh_gr_vectors` | a new module | Suggested `gr_refresh.py`, beside `gr_validator.py` and `gr_state.py`. |
> | the `base_dir` rename | `vector_store.py` | Mechanical, but touches **five** construction sites, all of which pass the parameter by keyword: `cli.py:570`, `cli.py:835`, `domain_tagger.py:621`, `indexer.py:885`, `indexer.py:1395`. Read the trap below before doing it. **Corrected as built: sixteen sites, not five** — the count omitted the eleven in `tests/`, which is the kind of undercount that reads as "nearly done" until the suite fails. |
>
> #### Five mechanics measured on this machine, none readable off the source
>
> **1. `SAVEPOINT` works on a `KnowledgeStore` connection, and its no-transaction case commits.**
> The connection runs in legacy implicit-transaction mode (`isolation_level == ''`). Verified:
> inside a caller's open transaction, `SAVEPOINT` / `ROLLBACK TO` / `RELEASE` nests correctly and
> the outer transaction survives a rollback to the savepoint. **With no caller transaction open,
> `SAVEPOINT` starts one and `RELEASE` commits it** — so `refresh_gr_derived_sql` called outside
> a transaction is self-committing. That is benign but must not be mistaken for the contract; the
> contract is still "runs inside whatever transaction the caller already has open", and a nested
> `BEGIN` (which would commit the outer transaction silently) is still forbidden.
>
> **2. FTS5 is compiled into this interpreter's SQLite** (3.45.3, Python 3.12.9). Verified by
> creating, inserting into and `MATCH`ing a scratch virtual table. No build check is needed.
>
> **3. chromadb 1.5.9 *silently drops* a `None` metadata value — it does not reject it.** The
> comment in `upsert_chunks` said the opposite ("Chroma rejects None") and had done since before
> this plan; it is corrected in place as of Step 4, so do not be surprised to find it agreeing
> with this paragraph. Measured: upserting `{"gr_id": "A", "subject": None}` and `{"gr_id": "B"}`
> produces two rows whose metadata is byte-identical. **This is the plan's recurring
> absent-versus-real defect sitting in the vector store**, and it bites Step 5 specifically
> because `subject` and `category` are both nullable on `gr`. So `upsert_texts` must coerce
> `None` to `''` explicitly — the coercion is right, the existing reason for it is not — and the
> step must state that `''` means *absent* in this collection. A `where={"subject": ""}` filter
> then matches the coerced rows and nothing else, which was also verified.
>
> **4. Chroma validates collection names: 3–512 characters from `[a-zA-Z0-9._-]`, starting and
> ending alphanumeric.** `gr_statements` passes. A short test-fixture name like `"c"` raises
> `chromadb.errors.InvalidArgumentError` from `get_or_create_collection`, which reads as a
> configuration failure and is not one.
>
> **5. `validate_dimension()` only raises when the collection already carries an
> `embedding_dimension` in its metadata**, which `get_or_create_collection` writes on creation
> and thereafter ignores. So a fresh collection never fails it, and the failure mode this step
> must handle is a *pre-existing* collection under a switched provider.
>
> #### One trap in the code the step renames
>
> **`chroma_dir` is honored in three places and `ChromaVectorStore` is not one of them.**
> (**Re-counted as built, 2026-09-02: five places, not three** — `cli.py:498` and `:764`,
> `indexer.py:321`, `:383` and `:1329`. Nothing else in this paragraph changes, and
> `pending/deferred-small-items.md` entry 2, whose heading said *two*, is corrected to match.) The
> constructor hardcodes `chroma_path = index_dir / "chroma"`, while `index --reset`
> (`indexer.py:383`), `backfill_vectors`' existence check (`indexer.py:1329`) and the `validate`
> command all compute `index_dir / manifest.index.chroma_dir` (default `"chroma"`). They agree
> only at the default. **Renaming the parameter to `base_dir` does not fix that and must not be
> taken to have fixed it** — a manifest setting `chroma_dir` to anything else already has a reset
> path pointing at a directory the store never wrote, and `--reset` would report success while
> the stale collection survived. Out of scope here: it is **already filed as entry 2 of
> `pending/deferred-small-items.md`**, which also warns the next reader not to read a `base_dir`
> parameter as evidence it was closed.
>
> #### How to test with no ingest
>
> **Nothing writes a `gr` row yet** — ingest is Step 6 — so Step 5's tests insert rows directly.
> Copy the `_MINIMAL_GR` dict and `insert_gr` helper from `tests/test_gr_state.py`; between them
> they cover the eleven NOT NULL columns in one place. For the embedder, use
> `HashEmbedder(dimension=64)`: it is deterministic, needs no network, exposes the `.name` and
> `.dimension` the `ChromaVectorStore` constructor reads, and is what the existing vector tests
> use. **Do not reach for the real providers in tests** — `create_embedder(config,
> provider_override)` dispatches `hash` / `qwen3` / `api`, the last of which is Bedrock and needs
> the declared `aws` extra plus a live credential.
>
> **Call `close()` on both stores in every fixture, or Windows temp-directory teardown fails.**
> `KnowledgeStore.close()` releases the WAL and SHM handles; `ChromaVectorStore.close()` drops
> the client and collection references and forces a `gc.collect()`, because Chroma's
> `PersistentClient` holds its own SQLite files open. `tests/test_gr_state.py`'s `store` fixture
> is the shape to copy — `try: yield / finally: close()`. This is not a Step 5 quirk, but Step 5
> is the first step whose tests hold *both* stores at once.
>
> #### Acceptance criteria that are already written for this step
>
> Scattered through `Validation and Acceptance` rather than collected, so they are listed here by
> their observable: `gr_fts` forgets old text on a `set-field` edit (the delete-half assertion); a
> `set-field` edit reaches search; a state change reaches the vector metadata *and* a same-state
> no-op re-embeds nothing; ingest with no embedder available still stores every rule, exits zero,
> names `reindex-vectors`, and a later `reindex-vectors` populates the collection with no
> re-extraction; and stage two reports the shortfall rather than returning zero candidates while
> the collection is behind. Three of those five need Step 6 or Step 8 to be performable end to
> end — write the unit-level form now and leave the end-to-end form to the step that supplies the
> command.

Add an FTS5 virtual table over the requirement text fields in `knowledge.sqlite`, and follow the house pattern exactly rather than choosing an FTS5 flavour — `store.py` already establishes one and the two paths need to look the same:

        CREATE VIRTUAL TABLE IF NOT EXISTS gr_fts USING fts5(
          gr_id UNINDEXED,
          name,
          statement,
          as_built,
          rationale
        )

That mirrors `chunk_fts` at `store.py:231-238`, which is a **standalone** FTS5 table — not external-content, not contentless — with its row key marked `UNINDEXED` so it is stored and returnable but not searched. Maintenance follows the same idiom: every write path does an explicit `DELETE FROM gr_fts WHERE gr_id = ?` followed by an `INSERT`, exactly as the chunk paths do at `store.py:400`, `:501-505` and `:1202`. `refresh_gr_derived_sql` is the only caller (see below), so that delete-then-insert lives in one place.

Three choices in there are deliberate. **Standalone rather than external-content** because external-content FTS5 needs triggers or exact rowid discipline to stay in step with `gr`, and this step has already rejected triggers on the grounds that Chroma cannot be trigger-driven — a half-trigger-driven refresh would be the worst of both. **Standalone rather than contentless** (`content=''`) because contentless cannot return the matched text, so `requirements search` could not show a snippet, which is most of what makes keyword search useful to a reviewer. And **delete-then-insert rather than upsert** for the same reason `gr_finding` and `gr_dataflow` use it: it is the one form that makes stale content actually disappear, so the codebase carries a single pattern rather than three.

The column set is the substantive decision. `as_built` is in because a reviewer hunting a code-level phrase wants the descriptive field, not only the normative one, and `rationale` because it is the field a reviewer writes and will then want to find again. `assumptions` and `implementation_notes` are deliberately out for now; adding them later is free, since the table is rebuilt wholesale from `gr` by `refresh_gr_derived_sql` and carries no durable state of its own.

**Keep it and the vector collection in sync through one explicit function, called from every write path — not from triggers, and not from "the ingest path".** SQLite triggers could maintain FTS5 but can reach nothing outside the database, so Chroma would need a second mechanism regardless, and two mechanisms is how a store ends up half-synced. And naming the ingest path alone is the actual bug to avoid: `set-field` rewrites `statement`, `import_records` restores rows wholesale, and the merge in Step 6 updates extractor-owned fields — none of those is ingest. Leave them out and `requirements search` silently returns pre-edit text while stage two of the merge compares incoming rules against stale vectors, so the reviewed records are the ones the near-duplicate search stops recognizing. Define it as **one named pair, called in order** — `refresh_gr_derived_sql(gr_ids)`, which rewrites the FTS5 rows and re-runs the validator, and `refresh_gr_vectors(gr_ids)`, which re-embeds the statements into `gr_statements` — and call both, in that order, from **every one of the six** write paths that touch a `gr` row: ingest, the merge, `set-field`, `set_state`, `import_records`, and `rederive-subjects` where it recomputes `subject`. **`set_state` is on that list and it is the one that is easy to leave off**, because it writes no text: it moves `state`, which changes neither the FTS row nor the embedded statement. But `state` is `gr_statements` *metadata* (below), so a store that skips it answers `search --semantic --state approved` with rules still tagged `draft`, silently and forever. Call the full pair there anyway rather than the vector half alone — on one row the SQL half is one delete-and-insert plus one validator run, and the property this whole mechanism buys is that every writer calls one obvious thing in one obvious order. A single call site that calls half the pair on a per-site judgement about which halves matter is the reasoning that produced this defect. Skip both on a same-state no-op, per the value-changing-write rule in Step 8. **A single function cannot do this job**, and an earlier version of this plan specified one: its two halves sit on opposite sides of the caller's commit, and no synchronous call can straddle its own caller's commit. A pair keeps the property the single function was reaching for — a fifth writer added later has one obvious thing to call — while putting the commit boundary in front of the reader at every call site instead of burying it in a return type. Both take a list rather than a single id. See Interfaces and Dependencies for the signatures, for why that ordering is load-bearing, and for the two tidier-looking shapes that were rejected.

Add a **dedicated** Chroma collection for requirement statements, named `gr_statements`. Construct it through the existing `ChromaVectorStore` with that collection name. **Do not put requirements into the `code_chunks` collection**, which would poison code search and force every existing query to carry a type filter. Embed the `statement` text, with the `gr_id`, `kind`, `state`, `category` and `subject` as metadata so filtered queries work.

**Persist it under the knowledge directory, not the index directory, and know why that is not a preference.** `ChromaVectorStore.__init__` takes an `index_dir` and appends `chroma` to it, and `index --reset` deletes that whole subtree — `shutil.rmtree(chroma_path, ignore_errors=True)` at `indexer.py:199-200`, every collection in it. A `gr_statements` collection created with the default index directory is therefore destroyed by a routine reindex, and the failure is silent in the worst way: stage two of the merge queries an empty collection and returns no candidates, which is indistinguishable from finding no near-duplicates. The under-merge safety net that the whole false-same-versus-false-distinct argument rests on would be gone with nothing to say so. So pass the resolved *knowledge* directory, giving `analysis/<system>/knowledge/chroma`, which no reset path can reach. Rename `ChromaVectorStore`'s parameter from `index_dir` to `base_dir` while you are there — with two callers passing two different roots, the old name is actively misleading, and the change is mechanical.

Two more consequences to handle rather than discover. **The collection is rebuildable and must have a command that rebuilds it**: relocation does not cover a changed embedding provider (`validate_dimension()` will refuse the collection outright), a partial ingest, or a manually deleted directory. Add `requirements reindex-vectors`, modelled on `backfill-vectors` at `cli.py:130` exactly as Step 2's `backfill-hashes` is — it walks the `gr` rows, re-embeds each `statement`, and is the documented recovery. And **stage two must notice when the collection is short**: compare its count against the `gr` row count and report a shortfall in words before searching, rather than returning zero candidates as though the search had run. This is the same discipline as `not_accounted_for` being NULL rather than 0 — an unsearched collection and a collection with no matches must never present the same way.

**The existing `ChromaVectorStore` cannot store a requirement as it stands, so budget for three small changes rather than discovering them.** Its writer is `upsert_chunks(chunks: list[CodeChunk], embeddings)` — chunk-*typed*, not text — so add a sibling `upsert_texts(ids, texts, embeddings, metadatas)` rather than generalizing the chunk method, leaving the indexer's path untouched. Its constructor requires an `Embedder`, which is what makes embedding a runtime dependency of every GR write path and not merely of search. And `validate_dimension()` compares the collection's stored dimension against the current embedder's, so switching embedding providers — the hosted Titan path and a local model are both in use in this repository — does not leave the collection stale, it leaves it *unusable*. Treat that as the same condition as a missing collection: say so, and point at the rebuild.

**Embedding is attempted at ingest and degrades rather than blocking — the rules always land.** An embedder must be resolvable for the semantic half to work, and for the hosted provider that is a network call per statement, so it is the least reliable thing in the pipeline sitting immediately downstream of the most expensive. The rule, which is why the refresh is a pair rather than one function and applies to all four of its callers: commit the SQLite work first and unconditionally, then attempt the embedding as a separate resumable phase. If no embedder is configured, or the calls fail, or the dimension does not match, the requirements are still in the store, `requirements ingest` prints plainly that the semantic half is not populated and names `requirements reindex-vectors` as the fix, and it **exits zero** — a non-zero exit here would read as "the ingest failed" and invite a re-run of the extraction, which is hours of model time to recover something that was never lost. This is the same graceful-degradation choice Step 9 makes one layer out, for the same reason, and it makes `reindex-vectors` the single recovery path for every way the collection can fall behind rather than one path per cause.

The cost of that choice, stated so it is not mistaken for a defect: a store can sit in a state where every rule is present and searchable by keyword while stage two of the merge is degraded. That is why the shortfall check above is mandatory rather than nice — the degraded state must announce itself at the moment it matters, not only in the output of the command that caused it.

This is Milestone 1 scope rather than a later nicety for one concrete reason: the merge in Step 6 deliberately under-merges, and its second stage is a semantic near-duplicate search. Without this collection that stage has no backstop.

### Step 6a: rewriting the extractor to author SPEC-1 notation, and the ingest field map

This step has two halves and the first one is a change to `/modernize-extract-rules`, not to the CLI. **Eight** `gr` columns have no source in today's `RULES_SCHEMA` — the eight listed in `Context and Orientation` — and the answer is that the extractor emits them. The second half is the field map that turns an extractor rule object into a `gr` row. Build both before Step 6, because `dedupe_key` takes `rule_class` and `pattern` as inputs.

**Read the Decision Log entry for `PR-79` before you start.** An earlier version of this step capped the extractor extension at three fields and derived `pattern` and `statement` deterministically at ingest from the Given/When/Then. That is measurably unbuildable and the measurements are worth carrying, because they are also what Milestone 1.5 is comparing against. On the 470-rule reference corpus: 66% of `then` values are passive clauses carrying their own subject, so none can follow "must" and all trip `V-STY-01`; 51% carry a semicolon and 36% an `and`, tripping `V-SING-01`; 20% of `given` values carry a comma, colliding with Step 4's own comma-delimited `[Condition]` boundary. `given` and `when` are *required* fields and were non-empty on 470 of 470, so "a non-empty `given` or `when` means there is a `[Condition]`" would have made `B-COND` universal and `B-UNCOND` unreachable. `[Formula]` and `[Value]`, which `D-COMPUTE`/`D-INFER`/`D-CONST` require, have no source field at all. And the damage would not have been confined to readability: `statement` feeds the `gr_statements` embedding, which *is* stage two of the merge, so the under-merge safety net would have searched over noise.

**What maps directly.** `name` ← `name`. `category` ← `category`. `priority` ← `priority`. `suspected_defect` ← `suspectedDefect`. `sme_question` ← `smeQuestion`. `parameters` ← `parameters`. `confidence_extraction` ← `confidence`. `gr_scenario` rows ← `given` / `when` / `then` / `and`. `gr_edge_case` rows ← `edgeCases`. `gr_citation` rows ← `source`, with the span-level `content_hash` computed at ingest by reading the cited lines. And `as_built` ← `plainEnglish`, which is the right map rather than a convenient one: `plainEnglish` is specified in the workflow as "one sentence a business analyst would recognize" describing what the code does, and that is precisely `as_built`'s definition.

**Declare the direct map as a constant, `EXTRACTOR_FIELD_MAP: dict[str, tuple[str, ...]]` — incoming rule-object key to the `gr` columns it writes — beside `UNMAPPED_KEYS` in the same module.** Two assertions in `Validation and Acceptance` are stated against it and neither has a computable referent without it: that it covers exactly `EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS`, and that every classified column has some writer. A prose description of "what ingest writes" cannot serve, because ingest also writes the store-assigned columns below and the two insert-only defaults, so an assertion phrased that way is false on day one.

**The value is a tuple rather than a bare column name, and that is forced rather than stylistic.** `EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS` is seventeen columns, but only fourteen incoming keys reach them: the three `_extracted` shadows have no incoming key of their own, because `statement`, `assumptions` and `modality` each write **two** columns — the live one and its shadow (Step 3). Under a `dict[str, str]` the mandated assertion `set().union(*EXTRACTOR_FIELD_MAP.values()) == EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS` could never pass, at most fourteen values against seventeen columns, and the likely reaction — quietly dropping the shadows from the right-hand side — removes exactly the columns whose writer is easiest to forget. So `"statement": ("statement", "statement_extracted")`, and the same for the other two; every other key carries a one-element tuple. The conditional half of the write (a shadowed live column moves only where it currently equals its shadow) is the merge's business, not the map's — the map records *which columns this key can write*, and the union of its values is what the assertion computes over.

**What the store assigns.** `gr_id` (a fresh ULID), `state` (always `draft`), `dedupe_key` and `dedupe_key_anchor_only`, `extractor_payload` (the verbatim object), `gr_run_hit`, and the timestamps. **Separately from those, ingest writes two insert-only defaults that belong to the human — `disposition` (`captured`) and `modality_confirmed` (false).** Keep them named apart as `INSERT_ONLY_DEFAULTS`: they sit in `HUMAN_WRITABLE_FIELDS`, ingest touches them only on insert and never on a merge (Step 6), and folding them in with the store-assigned columns is what makes the ownership assertion above come out wrong.

**Anchor resolution — where `gr_citation.anchor_key` comes from, and why it cannot wait.**

Step 3 calls `gr_citation.anchor_key` an advisory soft link "refreshed by a resolution pass." That describes a *repair*, and a repair is not enough: `sorted(anchor_keys)` is the tier-1 input to **both** `dedupe_key` and `dedupe_key_anchor_only`, so the anchors must exist at the moment the row is keyed, which is here. A later pass arrives after stage one has already decided what merged. Get this wrong and the failure is silent and severe — if unresolved anchors collapse to the empty string, `dedupe_key_anchor_only` degenerates to `'' ␟ rule_class ␟ pattern`, which is identical for every rule in the corpus sharing a class and a pattern, and stage one auto-merges them. That is the false-same failure Step 6 calls invisible and fatal, arriving on the very first ingest.

Note that the design draft names the existing `citation-validator` skill as the resolution pass. It is not: that skill validates line numbers inside markdown documents with `Read`/`Edit`/`Glob`/`Grep`, belongs to the pre-`legacylift-search` generation of the product, and never opens either SQLite database. Do not wire it in.

Split the work. The **lookup** is a Layer-0 concern — `symbols` lives in `index.sqlite`, "which entity covers these lines" is a question Step 7's data-flow block asks again, and the containment rule must have exactly one implementation. Put it in the identity/citation module with its own tests, and have `SQLiteStore` expose the query. The **call site** is ingest. Because the GR tables are in `knowledge.sqlite` and the two databases are never `ATTACH`ed, this is another cross-database read joined in Python; follow `domains_cmd` at `cli.py:1095`.

The rules, all of which need to be explicit because each has a silent failure behind it:

- **Parse the citation with the existing parser.** `_parse_claimed_citations` at `cli.py:1532` already handles the extractor's exact `path:line-line` shape and is proven against what the coverage step really emits — leading list markers, colons inside paths, a bare path meaning the whole file. Promote it out of `cli.py` into the shared module rather than writing a second parser that disagrees with the first. It needs one change: its documented behavior of skipping malformed entries silently is right for a best-effort coverage denominator and **wrong here**, where Step 3 says do not drop the citation. Give it a strict mode that surfaces the malformed entry instead.
- **Resolve to the innermost containing symbol, and resolve to exactly one.** Of the symbols in that file whose `start_line`/`end_line` span contains the citation's range, take the one with the smallest span. Innermost, not all-enclosing: a citation inside a method must not also pick up its class, or adding an unrelated sibling method to that class would re-key the rule. If no symbol *contains* the range, fall to the symbols the range *intersects* and pick the one with the smallest span, breaking ties by smallest `start_line` and then by `qualified_name` ascending. **Write that tie-break into the code as stated and do not vary it**: this value is hashed, so two implementations that break a tie differently produce different `dedupe_key`s for the same rule and the merge stops working with no error anywhere. The single winner is `gr_citation.anchor_key`; every symbol the range contains or intersects — winner included — is also recorded as a `gr_citation_anchor` row with its `containment`, because the full set is what answers "which symbols does this requirement touch?" and only the primary is a key input (Step 3).
- **Fall back to a file-level anchor, never to the empty string.** When no symbol matches — a file type the indexer does not parse, lines between declarations, a bare path meaning the whole file — call `file_anchor_key(relative_path)` from Step 1, which is `NORMATIVE SPEC-3` §S3.1.1's grain: `anchor_key("", "file", "", normalize_path(relative_path))`. This is what bounds the damage: a file-level anchor still discriminates by path, so the worst case is two rules of the same class and pattern in the same file, and tier 2's span-level `content_hash` separates those. A global empty string discriminates nothing. **Do not resolve `language` from `repo_files` here, and do not call `detect_language`** — the constant is specified in §S3.1.1 and Step 1, and either lookup would make a tier-1 dedupe-key input a function of whether the repository had been indexed, so the same citation would key differently before and after an `index` run. Note also that the earlier wording of this bullet named "SQL or configuration" as reaching the fallback; `.sql` is an indexed extension and does not, while most configuration formats are not indexed at all and do.
- **`unresolved` means one specific thing: the cited path does not exist in the working tree.** It is not a third failure tier beneath the file-level floor — the floor is total, and every case in the bullet above reaches it. Reserve this value for the citation whose `relative_path` is simply not there, which is the one case where a file-level anchor is *computable but describes nothing*: the hash is over strings and does not care whether the file exists, so without this label the store would carry confident-looking anchors for files that are absent, and they would feed both dedupe keys indistinguishably from real ones. So compute the file-level anchor anyway — the key space must stay bounded by path — and set `anchor_resolution = 'unresolved'` to say what it is. This is the citation-level companion to Step 3's rule that such a row inserts with a NULL `content_hash` rather than being dropped; the two together are what make a stale citation visible instead of merely wrong. Report the rate in `requirements stats` as what it actually measures — citations pointing at paths that are not in the tree — because that is a real and actionable signal about an extraction taken against a different checkout, and a value nothing can ever produce would make the same field read as permanently healthy.
- **Guard against a stale index the same way Step 2 does.** Before trusting a symbol match, check that the file's on-disk `sha256` still equals the stored `repo_files.sha256`. If it does not, the symbol ranges describe source that is no longer there, so prefer the file-level anchor over a confidently wrong symbol anchor. This is why `resolve_anchor` takes a `repo_root` (see Interfaces and Dependencies): the check reads the working tree, and `SQLiteStore` knows only where the database is. **Hash each file once per ingest and cache it for the run** — the guard is a per-*file* question while citations are per-rule, and a dense corpus cites the same file many times, so the naive form re-hashes large source files hundreds of times in a single ingest.
- **Record which happened.** Add `anchor_resolution` to `gr_citation`, taking `symbol`, `file`, or `unresolved`, and report the rate in `requirements stats`. Without it, a run against a repository with no index at all produces a full corpus of file-level anchors that looks exactly like a healthy one. That case in particular must be **loud** at ingest — the same treatment `injection_flags` gets — because the merge is degraded for every subsequent run against that store, not just the current one. **Break the `file` rate down by file extension as well as reporting it overall.** A high `file` rate concentrated in one extension is not noise, it is "Layer 0 has no extractor for this technology" — which is how Hibernate mappings and Spring Webflow states came to be supported at all, discovered by hand on one engagement. This is the late half of a signal whose early half is filed as `docs/exec-plans/pending/layer0-extraction-gap-detection.md`; that plan makes it available right after `index` instead of after an extraction run costing hours of model time. **Nothing here depends on that plan** — this breakdown is one `GROUP BY` and stands alone.
- **Add the index the containment query needs.** `symbols` is indexed on `name`, `qualified_name` and `language` today (`store.py:258-266`) and on nothing positional, and it carries `file_id` rather than `relative_path`, so this query joins through `repo_files`. Add `CREATE INDEX IF NOT EXISTS ix_symbols_file_span ON symbols(file_id, start_line, end_line)` alongside Step 2's `anchor_key` index, in the same migration.
- **Handle "there is no index at all" explicitly, because the obvious code creates one by accident.** Acceptance requires that ingesting against an unindexed repository is reported loudly and produces a corpus that is entirely `file`, and neither half happens for free. `SQLiteStore.__init__` (`store.py:157-164`) only records the path — `_connect()` opens the file lazily and **SQLite creates it on that first query** — so constructing a store against a missing `index.sqlite` materializes an empty database and then fails on `no such table: symbols`. That is the identical side effect this plan already guards against for `KnowledgeStore`, and the guard is the same: **ingest checks `index_sqlite_path.exists()` with a plain `Path.exists()` before constructing `SQLiteStore`**, and passes `None` when it is absent. `resolve_anchor` therefore takes `SQLiteStore | None`, and a `None` store means every citation takes the file-level floor with `anchor_resolution = 'file'` — which is correct rather than degraded, since the floor is total and index-independent by construction (Step 1). Print the loud banner **at that check**, naming the resolved index path, so a mis-resolved path under Milestone 0's new layout is distinguishable from a repository that genuinely was never indexed. Those two produce identical corpora and call for opposite fixes.

The `provenance` value `repaired` from Step 3 keeps its meaning on top of this: resolution at ingest stamps `extracted`, and only the move auto-repair rewriting an anchor later stamps `repaired`.

**What stays deliberately empty.** `rationale`, `fit_criterion`, `enforcement_level`, `confidence_intent`, `owner`. All SME-only; the extractor is forbidden to fill them and their emptiness is the review-progress signal.

**What is derived at ingest, deterministically and with no model.** `subject` and `subject_provenance`, from `file_domains` per the majority-domain rule in Step 3 — a SQL join on the derived branch, and on the two fallback branches the `[Subject]` span of the rule's own `statement`, read with `split_slots`. Both branches are specified in Step 3; read that paragraph before writing this, because the fallback's source is the part an earlier version of this plan left unstated.

That leaves the gap. Close it by rewriting the extractor, and split the work by **who holds the evidence** — which is `NORMATIVE PRINCIPLE-1` applied literally: infer once, at the point of maximum evidence, and mark it.

**The extractor emits the notation.** Extend `RULES_SCHEMA` with `ruleClass`, `pattern`, `statement`, `modality` and `assumptions`, plus `implementationNotes` and `structuredBody` / `structuredBodyType` as optional. Every one of these is a judgement about the code, and the extraction agents are the only actors in the system that read it. **`structuredBody`'s four payload shapes are specified in Step 3 and must be reproduced in `RULES_SCHEMA` verbatim** — an agent cannot emit a shape the schema does not describe, and `gr_body_schemas.py` validates against the same shapes on write, so a divergence between the two fails the ingest transaction on every rule that carries a body.

**`implementationNotes` is on that list for a reason that is easy to miss, so state it in the prompt rather than leaving the field to be filled by accident.** A conforming SPEC-1 statement is written in business vocabulary, so authoring one is an act of abstraction: the agent reads `StationDAO.updatePhysVol()` throwing `VolumeOverlapException` and writes *A station must not record a physical volume that overlaps an existing one*. What it dropped in that step — method names, exception types, table and column identifiers, framework vocabulary — is exactly what `implementation_notes` is for, and the agent is the only actor that ever holds it. Ask for it explicitly: *what implementation detail did you leave out of `statement`?* Without the instruction the field arrives empty on a schema that permits it, which is indistinguishable from an extractor that had nothing to leave out. Note the reinforcing loop with Step 4: `V-STY-03` WARNs precisely when that abstraction did *not* happen and a program symbol survived into `statement`, so a high `V-STY-03` rate beside an empty `implementation_notes` says the instruction did not take. `rule_class` has a deterministic procedure in `NORMATIVE SPEC-1` §S1.2 — does the cited code have a violation-response path, or is it an assignment with no failure path — and that procedure reads the source. `pattern` and `statement` are §S1.4's closed enum and its sentence templates, applied by an agent that has the file open.

**The Given/When/Then stays, required and unchanged.** It is demoted to a `gr_scenario` child, which is the settled Q3f shape, and it now carries a second job: the within-run comparison of the old shape against the new, same rule and both shapes side by side. That is a far stronger comparison than one across two corpora separated by hundreds of rules of run-to-run noise, and it costs nothing because the fields are already required.

**On the `[Subject]` objection, because it is the reason an earlier draft went the other way.** A conforming statement names its `[Subject]`, and `gr.subject` is derived from `file_domains` at ingest, which the agents cannot see. That does not block anything. `V-SLOT-02` bans four literals — `the system`, `the application`, `the software`, `the program` — and requires nothing further of the subject; `plainEnglish` on the old corpus already named a concrete business subject on 470 of 470 rules ("A station", "A phone", "A contact"), and a business noun is a *better* `[Subject]` than a domain name like "Point Management" would be. So the statement's subject is the extractor's business noun, and `gr.subject` remains the domain-derived analytic facet it already is. The two coexist and the derived branch of `gr.subject` is not taken from the statement. **They do meet in exactly one place, and it is not this coupling:** where the domain derivation yields nothing — every citation on a sentinel domain (`unassigned` or `excluded`), or no real domain holding a majority — Step 3's fallback reads the `[Subject]` span out of the statement the extractor already wrote. That is a deterministic read at ingest, not a request to the agent, and it is what gives `llm_named` and `derived_ambiguous` a producer. What remains forbidden here is the other direction: handing the extraction agents the `domains.json` entry for each file they open — the pipeline authors it two steps earlier, in `assess` — so that they author `gr.subject` themselves, at the cost of coupling the extractor to domain tagging. Do not do that in Milestone 1.

**Three files carry the old shape and all three must change together**, or the schema and the prompts will disagree. The plan previously named only the first:

| File | What carries the Given/When/Then shape |
|---|---|
| `workflows/extract-rules.js` | `RULES_SCHEMA`'s required fields and their `description` strings — which is where most of the field-shape instruction actually sits, since the miner prompt itself is generic |
| `agents/business-rules-extractor.md` | its `description` frontmatter, and the section "Encode it as Given/When/Then with concrete values" (`:33-37`) |
| `commands/modernize-extract-rules.md` | the "Rule Card format" section (`:116-141`) — and note `:36` currently instructs *"**not** change the Rule Card format, the citation referee, or the P0 two-judge"*, which this step explicitly overrides for the Rule Card format only |

**All three are Apache-2.0**, so each needs the attribution line the repository requires — `Modified by CapTech on <date>: [brief description].` immediately after the frontmatter, overwriting any existing line rather than appending. Step 9 previously required this on the command file alone.

**Still do not touch the referee or the P0-panel prompts.** They judge citations and priority, not notation, and changing them would move extraction quality on an axis Milestone 1.5 measures for reasons unrelated to this work.

**What this costs Milestone 1.5, stated rather than hidden.** The earlier three-field cap existed to protect that measurement: "every prompt change to `extract-rules.js` risks moving extraction quality, and Milestone 1.5 is trying to measure exactly that." That argument is now spent — the extractor is deliberately rewritten, so a new run differs from both baselines in prompt *and* in pipeline. This does not invalidate Milestone 1.5: `SPEC-2` §S2.4 already forbids accuracy claims, both baselines are unvalidated model output, and the mandatory BASE-ORIG-versus-BASE-ENH noise floor remains the control. What it requires is that the write-up **say the prompt changed**, in the same breath as every headline number.

**One consequence of the earlier cap is now reversed.** Q3h assigns the data-flow block's `llm_inferred` entries to the extractor, and a per-rule reads/writes field was excluded as a fourth field the cap forbade. With the cap gone, that argument no longer stands on its own — but `gr_dataflow` still has no writer in Milestone 1, because the *computed* path is gated on M26 and shipping only the inferred half would invert the provenance principle. Step 7 is unchanged; only its second stated reason is. Add the extractor field alongside M26's work, as Step 7 already says.

**Ingest derives only what needs ingest-time context, with no language model in the CLI.** `legacylift_search` has no LLM dependency today and this plan does not add one; a second inference pass over every rule would be both a cost and a new provenance seam. That leaves `subject`/`subject_provenance`, both dedupe keys, the citation anchors and span hashes, the insert-only defaults, and the timestamps. Specifically, on the two fields an earlier draft derived and no longer does:

- `pattern` and `rule_class` arrive from the extractor and ingest **stores them verbatim**. Do not re-derive, do not second-guess, and above all do not fill a NULL. `pattern` remains nullable (Step 3) for the case where the agent could not decide, and the approval gate catches it. Note what changed and what did not: these two are still nondeterministic across runs, so the key-instability analysis later in Step 6 is unaffected — a run that classifies the same code `definitional` where the last run said `behavioral` still re-keys both keys and lands as a candidate.
- `statement` likewise arrives from the extractor and is written to **both** `statement` and `statement_extracted` on insert. Ingest performs no templating. The review loop is what makes wording good — that is what those two columns and the whole lifecycle exist for.
- **`statement` is `NOT NULL`, and a pattern-free fallback exists as a defensive default only.** It is no longer the common first-ingest path, because `statement` is now a required extractor field; it covers a schema-conforming rule that nonetheless arrives with an empty statement. Keep it, because the NOT NULL is load-bearing: four things downstream read the column — the validator (Step 4), the FTS5 index and the `gr_statements` embedding (Step 5), and the `statement = statement_extracted` equality that is the *sole* definition of "a human edited this" (Step 3) — and two of them acquire a NULL trap without it. The shadow equality would have to become `statement IS statement_extracted`, because SQLite's `=` over two NULLs yields NULL rather than true, and until someone noticed, the merge would read every statement-less row as human-edited and never update it again. The fallback is:

    - `<Subject> must <then>` when `rule_class` is `behavioral`.
    - `<Subject> always <then>` when `rule_class` is `definitional`.
    - `<Subject> must <then>` when `rule_class` is NULL as well. `V-CLASS-01` already blocks such a row from approval, so nothing turns on the choice of keyword there.

  Two properties of that fallback are load-bearing. It **produces text only and never a `pattern` value** — `pattern` stays NULL, so both dedupe keys, the `approved`-scoped `CHECK` and the approval gate are entirely unaffected, and the honest NULL that records "the shape was undecided" survives. And Step 4's rule still applies unchanged on top of it: with `pattern` NULL the three `V-SLOT` checks remain undecidable and must be emitted as not-evaluated, since a statement now exists but the template that would locate its slots does not. Do **not** close this gap by defaulting `pattern` to `B-UNCOND` or `D-NEC`, at ingest or in the extractor: that writes a guessed value into both dedupe keys and into the approved corpus, and destroys the signal the nullability exists to carry. Record the fallback as an implementation note against §S1.4 — it adds no `pattern` value, changes no check and re-severities nothing, so unlike amendment A1 it is not a SPEC-1 amendment.
- `implementation_notes` ← `implementationNotes`, stored as it arrives. It is extractor-owned and takes no shadow column: it is not in `HUMAN_WRITABLE_FIELDS`, so `set-field` refuses it by membership and the two parties never contend for it. Should a later milestone want a reviewer to edit it — parking leakage they stripped from a `statement` during review — that is `PR-45`'s rule firing, and the change is a move to `SHADOWED_FIELDS` plus an `implementation_notes_extracted` column, not a quiet widening of `set-field`.
- `structured_body` ← `structuredBody` and `structured_body_type` ← `structuredBodyType`, stored as they arrive, with the body validated against the schema its type selects (`gr_body_schemas.py`, Step 3) **on write**. A body that fails its schema fails the ingest transaction, and the error names the offending rule by `offer_ordinal` per Step 6. The pair is all-or-nothing: a `structured_body` arriving without a `structured_body_type` is a rejected row, never a defaulted one, because the type is what selects the schema and a guessed type validates against the wrong one.
- `assumptions` behaves exactly as `statement` and `modality` do, because it is the third shadowed field (Step 3): the incoming value is written to **both** `assumptions` and `assumptions_extracted` on insert, and on a merge to the shadow always and to the live column only where the two currently agree. It is spelled out here because the rule is spelled out for the other two, and a rule stated for two of three members of a set reads as not applying to the third.
- `modality_confirmed` is `false` on every **newly inserted** row without exception. The extractor proposes `modality`; only a human confirms it. On a *merge* ingest must leave it alone — writing `false` there would erase an SME's confirmation on every re-extraction, which is precisely the accumulation this plan exists to protect. The proposed value goes to `modality_extracted` always and to `modality` only when the two currently agree, exactly as `statement` behaves (Step 3).

Be honest in the plan's own terms about what a first run produces. The extractor now authors conforming sentences, so `statement` is real prose rather than a template fill — but it is *unreviewed* prose from a language model, `pattern` is sometimes NULL, and a corpus in that state is a *correct* Milestone 1 outcome rather than a degraded one. The claim this milestone makes is that judgement accumulates durably, not that the first extraction is right.

**One consequence to state before someone treats it as a build failure.** `requirements validate` exits non-zero when any `ERROR` stands, and it **will exit non-zero on every freshly ingested corpus, which is the expected value for the whole of Milestone 1** — exactly as `V-KW-05`'s blocking of every `should` rule is in Step 4. Three sources guarantee that independently of how good the extractor gets: `V-KW-05` blocks every `should` statement until an SME sets an `enforcement_level`, which is extractor-*forbidden*; `V-STY-03` fires on program symbols in the statement, which is what mining from code produces; and any rule whose `rule_class` the agent could not decide trips `V-CLASS-01`. Say so in the command's help text. Do not wire that exit code into CI as a health check, do not soften the checks to make it green, and do not have the extractor sanitize its output to dodge them — the findings are the review queue, and a corpus with no findings on first ingest would mean the validator was not doing anything.

### Step 6: merge with dedupe

Ingest is a merge, never truncate-and-insert. Implement two stages with deliberately asymmetric behavior.

Stage one is an exact `dedupe_key` match, and it merges automatically. Stage two runs when there is no exact match: search the `gr_statements` collection semantically, and separately find citations whose line ranges *intersect* an existing requirement's citations on the same file. Surface the results as **review candidates**. **Stage two never merges on its own. No similarity threshold auto-merges anything, at any confidence.**

The asymmetry is intentional and the reason must be preserved in a comment. The two failure modes are not symmetric. A false-distinct — a duplicate row — is visible, and a reviewer merges it, so it is recoverable. A false-same — an over-merge — is invisible: a real rule silently never enters the corpus, and coverage is this plan's measured selling point (measured in Milestone 1.5). So the exact key is biased toward under-merging and stage two recovers the residue without ever acting alone. Note also that exact range equality is right for a *key* while range intersection is right for a *candidate search*; they are different jobs and both are needed.

**One false-same case is reachable on the very first ingest, inside a single run, and you should know its exact bound before trusting a corpus.** Everything else in this plan discusses dedupe across runs, but two rules offered in *one* run can collide too. If they cite the same line range they share their anchors, and the tier-2 discriminator is the span-level `content_hash` of exactly those lines — identical for both. Tier 1 does not apply unless a typed body exists. So the entire discrimination between them is `rule_class` and `pattern`: **two classes against ten patterns, narrowing to two against one on whatever subset of the corpus the extractor left `pattern` NULL**, since NULL encodes as the empty string. Do not reinstate the earlier wording that called that subset the common case — it was written while ingest derived `pattern` from the Given/When/Then, and `PR-79` replaced that with an extractor that emits it, so the abstention subset is now small and unmeasured rather than dominant. **Which cuts both ways and is the reason the measurement below is mandatory rather than optional:** the space is wider than that wording implied, so the residue is probably smaller — but nobody has measured either the abstention rate or the collapse rate on a real corpus, and a bound argued down from a rate nobody has taken is not a bound. Stage one matches, merges automatically, and stage two never runs because there was no miss — so a real rule never enters the corpus and nothing anywhere reports it. The extractor's own in-run dedupe does not prevent this: it keys on `path::lowercased-name` (`extract-rules.js:256`), which collapses same-*name* rules, not same-*lines* rules.

This is **SPEC-3's known and accepted residue, not a new gap** — §S3.3.1 names it when rejecting option B, "still collides on the dominant real case: two different `B-COND` rules in one dense validator", and chose the tiered key to address it. What the tiering cannot address is two rules citing byte-identical lines, because every tier below the class-and-pattern pair is then the same by construction. Do not attempt to fix it by adding a within-run sequence number or offer index to the discriminator: that makes the key run-dependent, so the same rule keys differently on the next run and cross-run merging — the entire point of the store — stops working. The rejected direction is worth naming because it is the first thing that comes to mind.

**So measure it before deciding anything.** `gr_run_hit.offer_ordinal` makes it one query: the number of offered rules in a run that landed on a `gr_id` another rule in the same run also landed on. On a first ingest into an empty store that figure *is* the intra-run collapse rate, uncontaminated by cross-run merging. Report it in `requirements stats` and record it as a mandatory measurement (Step 10). If it comes back small, the residue is what SPEC-3 assumed it was. If it comes back large on a real corpus, the key needs strengthening before anyone trusts a coverage claim from this store — and knowing that is worth more than a mitigation designed against a rate nobody has measured.

Merging must protect human work, and the test for "a human edited this" is exact rather than heuristic. When an incoming extracted rule matches an existing record:

- For each of the three shadowed fields — `statement`, `assumptions`, `modality` — write the incoming value to its `_extracted` shadow **always**, and to the live column **only if the live column equals its shadow on the stored row**. That equality is precisely the statement "no human has touched this," per Step 3. **Write it as SQLite's `IS`, not `=`, and put it in one shared helper the three fields call.** `statement` and `modality` are `NOT NULL` so the two operators agree on them, but `assumptions` is nullable — and `=` over two NULLs yields NULL rather than true, so an unedited rule with no assumptions reads as human-edited and the merge stops updating it, permanently and silently. One helper means the trap is disarmed once instead of being got right in two fields out of three. Where they differ, leave the live value alone; the human's version stands and the new extractor value is still captured in the shadow, so a reviewer can see what the extractor would now say.
- **Never write** `rationale`, `fit_criterion`, `enforcement_level`, `confidence_intent`, `state`, `reviewed_by`, `owner`, `reviewed_at`, `review_note`, `disposition`, or `modality_confirmed`. The first four are extractor-forbidden, so any non-NULL value in them is human by definition. The last two are insert-only defaults (Step 3, Step 6a): writing them on a merge would reset a reviewer's triage and erase an SME's modality confirmation on every re-extraction.
- Update the remaining extractor-owned fields, add any new citations, **refresh the `gr_scenario` and `gr_edge_case` extracted sets per the rule in Step 3**, and re-run the validator. Do not leave the two child sets out of this list: they are not fields, so the ownership partition says nothing about them, and an implementer working from the partition alone will write a merge that inserts a second full set of scenarios on every run.

**Derive every ownership list from constants rather than maintaining them by hand.** Written as hand-kept lists in two files they *will* drift — that is what produced this finding, where `set-field` accepted eight fields while the merge protected five and the four-field gap between them was silent.

**Declare FOUR sets, not three, and the fourth is derived from the schema rather than written out.** The partition is over *which of the two contended write paths may touch a column* — the merge, and `set-field` — and that question has four answers, not three. An earlier version of this plan declared three and asserted them pairwise disjoint, which cannot hold: `statement`, `assumptions` and `modality` are written by the extractor **and** by a human. That is not a classification slip; it is `PR-45`'s own rule — a shadow column is required for exactly those fields both parties write — defining a fourth cell into existence.

| Set | The merge | `set-field` | Count |
|---|---|---|---|
| `EXTRACTOR_OWNED_FIELDS` | writes | refuses | 14 |
| `SHADOWED_FIELDS` | writes **only if the live column equals its shadow** | accepts | 3 |
| `HUMAN_WRITABLE_FIELDS` | never | accepts | 9 |
| `STORE_OWNED_FIELDS` | never | refuses | 16 |

**Derive `SHADOWED_FIELDS` rather than declaring it:** `{c for c in columns if c + "_extracted" in columns}`, read from `PRAGMA table_info`. It then cannot drift from the shadow columns it describes, which is strictly better than the fourth hand-kept list this mechanism exists to eliminate. The three `_extracted` shadows themselves sit in `EXTRACTOR_OWNED_FIELDS`, since the extractor is their only writer, and `set-field` refuses them by that membership rather than by a special case.

**Write the membership out rather than leaving it to be classified**, because classification is where two implementers differ and the four counts above are the only checksum on a forty-two-column partition:

| Set | Columns |
|---|---|
| `EXTRACTOR_OWNED_FIELDS` (14) | `name`, `as_built`, `category`, `priority`, `confidence_extraction`, `structured_body`, `structured_body_type`, `implementation_notes`, `parameters`, `sme_question`, `suspected_defect`, `statement_extracted`, `assumptions_extracted`, `modality_extracted` |
| `SHADOWED_FIELDS` (3, derived) | `statement`, `assumptions`, `modality` |
| `HUMAN_WRITABLE_FIELDS` (9) | `rule_class`, `pattern`, `enforcement_level`, `confidence_intent`, `disposition`, `modality_confirmed`, `rationale`, `fit_criterion`, `owner` |
| `STORE_OWNED_FIELDS` (16) | `gr_id`, `kind`, `state`, `subject`, `subject_provenance`, `derived_from`, `superseded_by`, `dedupe_key`, `dedupe_key_anchor_only`, `reviewed_by`, `reviewed_at`, `review_note`, `extractor_payload`, `first_seen_run_id`, `created_at`, `updated_at` |

Those forty-two are exactly Step 3's column list. A later milestone that adds a column adds it to one of these four and to its count; the exhaustiveness test is what forces that to happen deliberately rather than by omission.

**Membership is not reachability, so record the writer for the two `STORE_OWNED_FIELDS` columns nothing obvious writes**, since that is the question the seventh round's `implementation_notes` finding says to ask of every column: `superseded_by` is written by `set_state` on the `→ superseded` transition, and **`derived_from` has no writer in Milestone 1 at all** — it is reserved for Milestone 2's rollups and its emptiness is correct rather than a dead end. Naming them here stops a later reader rediscovering the question and stops the reachability assertion in `Validation and Acceptance` being written over all forty-two columns, which it is not: it covers the three non-store sets.

Everything else follows and stops needing maintenance. The merge writes `EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS`, the second conditionally — **there is no "minus the insert-only pair"**, because `disposition` and `modality_confirmed` are human-writable and the merge never touches them. `set-field` accepts `HUMAN_WRITABLE_FIELDS ∪ SHADOWED_FIELDS`.

**Assert the property that actually catches something: the four sets are pairwise disjoint and their union is exactly the column list of `gr`.** That is an exhaustive partition, so a column added by any future milestone fails the test until someone classifies it deliberately. A complement assertion over two sets fails immediately on the fourteen store-owned columns, and the implementer's likely reaction — quietly exempting them with a hand-written exclusion list — reintroduces the mechanism that produced this defect in the first place. A three-set version fails on day one too, for a subtler reason: it leaves the shadowed three in whichever set breaks the other rule.

**`HUMAN_WRITABLE_FIELDS` is nine columns, and three of them are there because otherwise nothing in the system could write them:** `rule_class`, `pattern`, `enforcement_level`, `confidence_intent`, `disposition`, `modality_confirmed`, `rationale`, `fit_criterion`, `owner`.

- **`owner`** was introduced in Step 3 as human-owned and present from day one, and appeared in no command's accepted set, so the audit claim it exists to support was unachievable rather than merely unexercised.
- **`rule_class` and `pattern`** are the same defect one level up, and worse: `V-CLASS-01` is an `ERROR` on a NULL `rule_class` and the gate refuses `approved` while `pattern IS NULL`, so a rule the extractor left undecided was **permanently un-approvable with no command able to fix it**. The Decision Log's recompute rule proves the intent was otherwise — it exists precisely because "a reviewer who fills in `rule_class` re-keys the row."

**Neither needs a shadow column, and the reason is worth keeping because it is not obvious.** Both are inputs to *both* dedupe keys, so any merge that matches an existing row has identical values for them by construction: an exact-key hit implies they agree, and an anchor-only hit inserts a new row rather than updating one. **The merge can never change them.** They therefore sit exactly where `disposition` and `modality_confirmed` already sit — written by ingest on insert, never contended on a merge — and need no new mechanism. Two rules follow: `set-field` must **not** recompute either dedupe key when writing them, per the Decision Log's rule that keys move only on extractor-owned writes; and it enforces the `approved`-scoped `CHECK` and the `rule_class`/`pattern` prefix `CHECK` at the command, which Step 8 already requires generally.

**State the partition's scope, or the ownership test and the import path will read as contradicting each other.** It governs exactly two write paths, the merge and `set-field`, and within them it governs *field-mapped* writes only. `set_state` and `import_records` are outside it — import restores whole records and must write extractor-owned columns.

**Four columns are store bookkeeping and are outside it as well**, written by the store on both paths despite sitting in `STORE_OWNED_FIELDS`: `updated_at`, `dedupe_key`, `dedupe_key_anchor_only` and `extractor_payload`. Without this clause the table above reads as forbidding the merge to bump `updated_at` or to recompute a key, which Step 6's value-changing-write rule and the Decision Log's recompute rule both require it to do — a contradiction an implementer hits the moment they write the merge. The partition test is unaffected either way, because it asserts *membership*, not write behaviour. Settle the one open case while you are here: **the merge refreshes `extractor_payload`**, and it participates in the value-changing-write comparison below, so re-ingesting the same file still changes nothing while a genuinely new `RULES_SCHEMA` field does reach the lossless backstop that column exists to be. A payload frozen at first insert would defeat the one thing it is for — promoting a field in a later milestone without re-running extraction.

Do not implement the edited-test as a fuzzy comparison, a timestamp comparison, or a "looks edited" heuristic. It is one equality over two columns, per field, and that is the whole mechanism.

**A write that changes no value must not bump `updated_at`.** Compare the incoming extractor-owned fields against the stored row and skip the `UPDATE` entirely when they are identical. This is not a micro-optimization, though it does save most of the work on a re-ingest: two headline claims in this plan are false without it. `Idempotence and Recovery` says re-ingesting the same extractor output *changes nothing*, and Step 9 says the second export is *byte-identical* while explicitly including the per-record timestamps on the grounds that they "change only when the record does". Stamp `updated_at` unconditionally and both become untrue in the one column nobody thinks to check — and the export diff that is supposed to make a single reviewed wording change visible in a pull request instead shows all several hundred records as modified, which is the same as showing nothing.

Do not read this as contradicting `gr_run_hit`. A run that merges an identical rule still records its hit with outcome `merged`: **being seen by a run and being changed by it are different facts**, and the hit table is what records the first. What this rule buys is that `updated_at` comes to mean exactly "when a value in this record last changed", which makes `ORDER BY updated_at` a real recent-activity view for a reviewer rather than a list of everything the last ingest touched.

**Know what the exact key is and is not stable against, because Step 6a changed the answer after SPEC-3 was written.** SPEC-3 §S3.3.1 chose this key over the alternative that included `as_built` on the grounds that `as_built` is "free LLM prose: re-extracting unchanged code yields a paraphrase, so the key changes every run regardless of SME activity." Two of this key's four parts are now in that same family. **Both `rule_class` and `pattern` arrive from the extractor** as the new `ruleClass` and `pattern` fields (Step 6a) — per-run judgements an agent makes while reading the code, not values derived from anything stable. So a run that classifies the same code `definitional` where the previous run said `behavioral`, or that picks `B-COND` where the previous run picked `B-UNCOND`, re-keys the rule. (Do not read this as licence to derive `pattern` at ingest from the shape of the Given/When/Then: an earlier version of this plan did exactly that, `PR-79` measured it unbuildable, and Step 6a now says ingest stores both values verbatim and re-derives neither.) Note that it re-keys **both** keys, since `rule_class` and `pattern` are inputs to `dedupe_key_anchor_only` too, so the anchor-only fallback does not catch this one.

What does catch it is already here: the citations are unchanged, so stage two's line-range intersection finds the existing requirement exactly and the rule lands as a `drift`-adjacent candidate rather than as an unrecognized new rule. That is the correct outcome and no new machinery is needed — but it means **an extra row and a candidate pair, not a merge.** Two consequences to honour rather than paper over. The second-run `rules_candidate` count over an unchanged working tree is a direct measurement of key instability under extractor nondeterminism, so record it in `Outcomes & Retrospective` alongside Step 10's two numbers. And the merge acceptance test has to be stated against a fixed input, which is what the next paragraph and the Validation section now do.

**One ingest is one transaction over the SQLite work — not one transaction per rule.** This is the longest multi-table write in the system, touching `gr`, `gr_citation`, `gr_citation_anchor`, `gr_scenario`, `gr_edge_case`, `gr_merge_candidate`, `gr_run` and `gr_run_hit`, and it has several ordinary ways to fail partway: a `CHECK` rejection, an unreadable citation, a `structured_body` that fails its schema, a crash. Committing per rule means a failure at rule 300 of 470 leaves a `gr_run` describing a run that half-happened and 300 `gr_run_hit` rows whose counts satisfy the identity while describing a corpus nobody intended. Re-running is then not a clean retry: the rules themselves merge correctly, but a *second* `gr_run` and a second set of hits are appended, so `rules_in` double-counts the first 300 and "which runs saw this rule" acquires a run that never really happened. A few thousand rules is a small write for SQLite, so wrapping the whole ingest costs almost nothing — and it is what makes `gr_run` unable to exist without the rules it counts, which is the difference between a count identity that is trustworthy and one that is merely arithmetically consistent.

Two consequences to implement rather than infer. A failed ingest leaves **no** `gr_run` row at all, so a retry is a first ingest and needs no cleanup, no resume flag and no deduplication of run metadata — say so, because the instinct on seeing a half-finished job is to write recovery code for it. And the error must name the offending rule by its `offer_ordinal` (Step 3) and by the field that failed: "ingest failed" over a 470-rule file tells the analyst nothing and sends them back to an extraction that cost hours. The embedding phase sits **outside** this transaction by design (Step 5) — the rules commit as one unit, and the vectors follow as the resumable phase that is allowed to degrade. Per-rule commits with a resume marker were considered and rejected: they would save re-doing a file read and some hashing, seconds of work, at the cost of a partial-state design that every later reader has to reason about.

"Add any new citations" means insert on the `gr_citation` uniqueness tuple from Step 3, `(gr_id, relative_path, start_line, end_line)`: a citation already present is left alone apart from a refreshed `content_hash` and `verified_at`, and one that is new is inserted. Without that rule the requirement count stays flat across two ingests — the headline acceptance test — while the citation count doubles underneath it, which is the same bug hiding one level down.

### Step 7: the data-flow block, built and shipped with no writer

**Read this first: `gr_dataflow` has no writer in Milestone 1, and that is the whole shape of this step.** Both paths into the table are deferred, for two independent reasons, and the table ships empty. (`PR-79` changed the second reason but not the conclusion — see below.) Say so in the `stats` output rather than reporting a rate over it — see the end of this step, which is the part most likely to be got wrong.



Compute `reads[]` and `writes[]` for each requirement from Layer 0, using the data-access edges, `uses_table` edges, the `has_column` facts and the `foreign_key` edges for the requirement's cited symbols. **No language model on the computed path.** Because `symbol_facts` lives in `index.sqlite` while the GR tables live in `knowledge.sqlite`, and the two are never `ATTACH`ed, this is a cross-database read joined in Python — follow `domains_cmd` in `cli.py:1095` for the pattern.

The design's second path is the flagged LLM fallback: where the graph yields **nothing** for a cited symbol, record what the extractor inferred, marked `llm_inferred`, with an `explanation`. The fallback fires on graph *silence*, never on graph *disagreement*, and inferred entries must never join a computed total.

**That fallback also has no writer in Milestone 1.** Q3h assigns those entries to the *extractor* — its provenance table reads "filled by: extractor" — but `RULES_SCHEMA` has no reads/writes field, and Step 6a does not add one. Nothing in the workflow's return value carries per-rule data flow: `dataObjects` is a separate top-level result with its own schema, keyed per object rather than per rule, and Milestone 3 owns it. **Note what changed here and what did not** (`PR-79`). The original reason was that Step 6a capped the extractor extension at three fields, and that cap is gone — Step 6a now rewrites the extractor to author the whole SPEC-1 notation, so "a fourth field is out of budget" is no longer an argument for anything. The conclusion survives on stronger ground: the *computed* path is gated on M26, and shipping the `llm_inferred` half alone would mean the only data flow in the store is model-inferred, which inverts PRINCIPLE-1's promise that the computed path is the trustworthy one and the fallback fires on graph *silence*. With no graph output at all there is no silence to fall back from. So the field is added alongside the M26 work, when the computed path it is a fallback *for* actually exists. It is **deferred, not deleted** — Q3h is settled and the `llm_inferred` provenance value keeps its meaning.

With both paths deferred, `gr_dataflow` is **empty throughout Milestone 1**, and the reporting rule follows from that rather than from the flag:

**`requirements stats` must not report an inference rate while the table is empty.** An earlier draft of this step said the rate would be "100% for the whole of Milestone 1, by construction," which was wrong in a way worth naming: with no entries at all the rate is zero over zero, so the implementation either prints 100% of nothing or divides by zero. Print words instead — *no data-flow entries: computed path disabled pending M26, extractor source not yet added* — naming both reasons, because they are cleared by different work. This is the `PR-29` discipline applied a fourth time: an absent measurement and a measured value must never share an encoding, and a percentage over an empty set is the purest form of that mistake.

Everything else in this step still ships. Create the table, the `DataflowEntry` model, the `show` rendering and the computed code behind its flag, and test that code with the flag forced on against fixtures — that is what keeps "enabling it later is a one-line change" an honest claim rather than an aspiration, and it is why the table is created now even though Milestone 0's migration runner would make adding it later perfectly safe.

**Ship this step with the computed path disabled behind a flag that defaults to off.** Milestone 26 of `docs/exec-plans/active/semantic-code-search-graph-index.md` is a hard prerequisite: until it lands, `uses_table` edges emit SQL table *aliases* (`o`, `c`, `po`) as datastore names and produce confident self-referencing edges such as `Orders → Orders`. Shipping the computed block before that fix would not be merely incomplete, it would be **wrong**, which breaks the provenance principle's core promise that the computed path is trustworthy. Either that milestone lands first, or this block ships disabled — never with known-bad values. Write the flag, the code and the tests now so that enabling it later is a one-line change, and state in the flag's docstring exactly which milestone unblocks it.

### Step 8: the `requirements` command group — SHIPPED 2026-09-02

Add a Typer sub-application registered as `requirements` with `app.add_typer`. **SHIPPED 2026-09-02** — see `Outcomes & Retrospective` → *Milestone 1 Step 8*. (When written, this said "all fifteen existing commands are flat `@app.command` registrations and there is no `add_typer` call in `cli.py` today": it was **sixteen**, and there is now one `add_typer`. The sub-app lives in a `cli_requirements/` package rather than in `cli.py` — a deliberate deviation recorded in the Decision Log.) Follow the existing commands for everything inside it — path resolution, `--json` output, `rich` tables, the read-only existence check below.

Provide `ingest` (read a JSON file of extractor output and merge it), `list` (with `--state`, `--category`, `--kind`, `--subject`, `--disposition` filters and a `--json` flag), `show` (one requirement with citations, findings, structured body and data flow), `search` (FTS5 keyword and, with a flag, semantic), `set-state` (below), `set-field` (below), `set-run-coverage` (record an independently re-measured coverage figure against a run, stamped with when it was taken and that it was re-measured rather than produced by the run), `retire-run` (mark a superseded run excluded from the completeness gate, with a required `--reason`), `reindex-vectors` (rebuild the `gr_statements` collection from the `gr` rows — Step 5's single documented recovery for a reset, a missing embedder, a failed call or a provider switch), `rederive-subjects` (recompute `subject` after a domain retag — see below), `validate` (run the validator and report findings, exiting non-zero if any `ERROR` exists), `stats` (counts by state, category and disposition, plus fill rates for the SME-only fields reported as progress, plus the data-flow block's status — which in Milestone 1 is the words Step 7 specifies, never a rate, because the table is empty — plus the intra-run collapse count per run from Step 6, plus the count of requirements whose citations all land on an `excluded` domain — Step 3's own figure, not folded into `derived_ambiguous`), `export` and `import`.

**`set-run-coverage` and `retire-run` are two commands, not one, and the split is deliberate.** They are `PR-54`'s two exits from the completeness gate and they are different acts with different audit meaning: one records a measurement that was actually taken, the other records a human's judgement that a run no longer counts. A single command carrying both would make "how did this run stop blocking the export?" unanswerable without reading the columns, which is exactly the question an audit asks. `retire-run` writes `gate_excluded` and `gate_excluded_reason` and leaves `complete` untouched, so the record still says what was actually known.

`set-field GR-… --field <name> --value <text>` is the **minimal, deliberately unpolished** human write path, and its scope is fixed by what Milestone 1 must prove rather than by what a reviewer would want. It exists because two of this milestone's acceptance criteria are otherwise unperformable: a human edit to `statement` must survive re-extraction, and `stats` must report SME-field fill rates as review progress — and with no way to write those fields, the first test cannot be set up and the second is structurally zero forever.

Constrain it tightly. It accepts exactly `HUMAN_WRITABLE_FIELDS ∪ SHADOWED_FIELDS` (Step 6) — the nine human-writable columns `rule_class`, `pattern`, `enforcement_level`, `confidence_intent`, `disposition`, `modality_confirmed`, `rationale`, `fit_criterion` and `owner`, plus the three shadowed ones `statement`, `assumptions` and `modality`, for twelve. It **refuses everything in `EXTRACTOR_OWNED_FIELDS` and everything in `STORE_OWNED_FIELDS` by membership** rather than by a hand-written denial list, so the three `_extracted` shadow columns and both dedupe keys are refused because of which set they are in and not because someone remembered them. Those four sets are an exhaustive partition of `gr`'s columns by construction rather than by maintenance, which is what stops the gap this rule closes from reopening.

**Three of those twelve are there because otherwise nothing in the system could write them at all**, and each was a live dead-end in an earlier version of this plan. `owner`: Step 3 introduces it as human-owned, merge-protected and present from day one on the argument that identity cannot be reconstructed retroactively, but `set_state` writes only `reviewed_by`, so the column was unreachable and its audit claim unachievable rather than merely unexercised. It is `set-field`'s because accountability is assigned, not derived from an act. `rule_class` and `pattern`: `V-CLASS-01` blocks approval on a NULL `rule_class` and the gate blocks it on a NULL `pattern`, and the extractor is permitted to leave either undecided — so without a writer here, such a rule could never be approved by anyone. **Writing these two must not recompute either dedupe key**, per the Decision Log rule that keys move only on extractor-owned writes; they are the only human-writable key inputs and the only place that rule is easy to break.

It validates against the same `CHECK` constraints the schema enforces, so `enforcement_level` on a `definitional` rule, or a `pattern` whose prefix disagrees with `rule_class`, is refused at the command rather than at the database. It re-runs the validator after the write, because editing a `statement` — or setting the `pattern` that decides whether the three `V-SLOT` checks are evaluable — changes its findings. It does not write `gr.state`; that is `set-state`'s job and the gate lives there. Do not grow this command into a review tool; that is Milestone 4.

**Do not build a review UI in this milestone.** The review experience — work queues, `as_built`-versus-`statement` diffs, bulk triage, reviewer assignment — is a separate deliverable with its own plan at `docs/exec-plans/pending/reqs-review-ui.md`. Milestone 1's job is to make review *possible and durable*; making it *pleasant* is Milestone 4's.

`list` also takes `--candidates`, which reports the `gr_merge_candidate` pairs from Step 3 whose `resolution` is `unresolved`. Without it, stage two of the merge is counted and never seen, and the whole under-merge safety argument collapses into a number nobody looks at.

`set-state GR-… --to <state>` is how a human records a judgement, and it is the **only** way a requirement leaves `draft` (Step 9's `import_records` is the one declared exception, for the reasons given there). Nothing automated calls it: `ingest` writes `draft` and never anything else, so an extractor can never approve its own output. It takes an optional `--note`, which lands in `gr.review_note`; it stamps `gr.reviewed_at`; it enforces the Step 4 gate on the `approved` transition plus the `pattern IS NOT NULL` precondition from Step 3; and it rejects an unknown or illegal transition rather than silently writing the column. `reviewed_by`, `reviewed_at` and `review_note` are written together by this one call and are last-write-wins, not a history (Step 3).

**"Illegal transition" needs a referent, so here is the whole graph.** Q5 settled the five states and said nothing about which moves between them are permitted, and SPEC-1 §S1.9 deliberately assumes only "that `draft` and `approved` exist and that the transition between them is a place a check can run" — so this is a decision this plan makes rather than one it inherits. Write it as a literal `ALLOWED_TRANSITIONS` mapping inside `set_state`, not as scattered `if` statements, so the legal set is readable in one place and a test can enumerate it:

        draft      -> reviewed, approved, rejected
        reviewed   -> approved, rejected, draft
        approved   -> superseded, rejected
        rejected   -> draft
        superseded -> (terminal)

Four things about that graph are decisions rather than mechanics. **`draft → approved` is permitted directly**, without passing through `reviewed`. Milestone 1 has no review queue — `set-field` is the entire write surface and Milestone 4 owns the experience — so requiring two calls to record one person's single act of reading and signing off would be ceremony, and the gate fires either way. **`reviewed` means "a human has read this and has not signed it off"**, which is a real and useful state precisely because it is the one a queue sorts on; it is optional in Milestone 1 and expected to carry weight in Milestone 4. **Only `→ approved` is gated.** Nothing gates `draft`, per Step 4, and nothing gates `reviewed` either — a gated `reviewed` would make the state a reviewer moves *through* unreachable on exactly the rows that most need review, which inverts the point. **`rejected → draft` reopens** a rule someone rejected in error, and `superseded` is terminal because its successor is where the work continues; a record that could leave `superseded` would leave `superseded_by` pointing somewhere with no defined meaning.

A move to the state a record already holds is a no-op rather than an error, and must not stamp `reviewed_at` or `review_note` or bump `updated_at` — the same value-changing-write rule Step 6 applies to the merge, for the same reason. **On a move that does change the state, finish by calling the Step 5 refresh pair** — `refresh_gr_derived_sql` inside the transaction, `refresh_gr_vectors` after the commit — for the one `gr_id`. `state` is `gr_statements` metadata, so without it an approved requirement keeps a vector tagged `draft` and every state-filtered semantic search is wrong in a way nothing reports. Skip both on the no-op.

**`set-state` requires a reviewer identity and refuses to run without one.** Take it from `--reviewer`, falling back to a configured default, and write it to `gr.reviewed_by`. Do not make it optional and do not default it to a placeholder: an approved corpus that cannot say who approved each record fails the exact audit claim the lifecycle exists to support, and identity is the one thing in this schema that cannot be reconstructed after the fact. The same requirement binds any future review UI, which is recorded in `docs/exec-plans/pending/reqs-review-ui.md`. `rejected` and `superseded` go through the same command; `superseded` additionally requires the `gr_id` of the successor, and it is recorded in **`superseded_by` on the record being superseded** — one row, whose `state` and `superseded_by` are written together by the same call, so there is no second record to keep in step. Do **not** put it in `derived_from`. That column means "the rules this rollup summarizes" and nothing else (Step 3): mixing supersession into it gives the array two meanings with no discriminator, so Milestone 2's rollup query silently collects replacement links alongside constituent rules. Keeping them apart also makes the question a reviewer actually asks — *what replaced this?* — a single-column lookup rather than a scan of every array in the table, and leaves the inverse available as `WHERE superseded_by = ?`.

**`rederive-subjects` exists because nothing else re-derives a subject after the domain set changes, and the staleness is silent.** `subject` and `subject_provenance` are computed from `file_domains` at ingest (Step 3) — so re-running `tag-domains` with a changed `domains.json` leaves every subject describing the *previous* domain set, with nothing anywhere reporting it. That silently corrupts the `derived` rate in `requirements stats`, which is the one check the Concrete Steps put in front of an implementer. The domain-retag invariant test does not catch this and must not be changed to: it asserts that every `anchor_key`, `content_hash` and `dedupe_key` is byte-identical across a retag, which is correct and is the whole point of no key taking a domain as input. Subjects are the surface that is *supposed* to move. The two assertions are complements, not duplicates.

The command recomputes `subject` and `subject_provenance` for every row from current `file_domains`, applying the same majority-domain rule, the same statement-`[Subject]` fallback and the same three-value provenance as ingest — one implementation, called from two places. It reads `statement` on the fallback branch and still never writes it, which is the distinction the next sentences draw. It applies Step 3's two-sentinel rule too, so a file that has since been added to `exclude_globs` moves from `derived` to `derived_ambiguous` rather than silently keeping a subject the domain set no longer yields. **It does not touch `statement`.** An earlier version of this plan had it re-template the statement wherever the live value still equalled its shadow, which was correct while ingest built statements from a §S1.4 template — but Step 6a no longer does that: `statement` is authored by the extractor, so there is no template to re-fill and no mechanical way to substitute a new subject into someone else's sentence. The staleness this leaves is smaller and honest: a requirement's *text* may name a subject the domain set no longer derives, while the refreshed `subject` column says what the derivation now yields, and the divergence between them is visible in `show`. Finish by calling `refresh_gr_derived_sql` and then, after the commit, `refresh_gr_vectors` for the touched rows, because `subject` is `gr_statements` metadata and a changed subject must reach the collection.

Two things it must do beyond the obvious. It **must not touch any key, and must not touch `statement`** — a test asserts both dedupe keys, every citation anchor and every `statement` are byte-identical before and after, which is the same invariant as the retag test one layer up. And it should report the `llm_named → derived` transitions separately, because that is the case the finding behind this command exposed: a file that was `unassigned` at ingest and has since been tagged should stop being model-named, and without this command it never does. Report the reverse direction as its own figure as well — `derived → derived_ambiguous`, which is what a newly-excluded file produces — because that one means the corpus now holds rules mined from code the analyst has since declared out of scope, and it is the same signal Step 3 asks `stats` to surface. Since the Concrete Steps tell you to check the `derived` rate before believing the derivation works at all, a rate that can only fall as a corpus ages would quietly undermine the one check the plan puts in front of you.

This is the fourth resumable repair command in the CLI, after `backfill-vectors` (`cli.py:130`), Step 2's `backfill-hashes` and Step 5's `reindex-vectors`. They share a shape worth naming, because a fifth will be added: each recomputes a derived value from a durable source, processes only what is stale or missing, reports what it changed and what it skipped, and is safe to run twice.

Every read-only command must check `knowledge_sqlite_path.exists()` with a plain `Path.exists()` before constructing a `KnowledgeStore`, or it will silently create an empty database.

### Step 9: JSONL export and the extractor wiring — SHIPPED 2026-09-02

`requirements export --format jsonl` writes one JSON object per requirement, sorted by `gr_id`, to `<analysis-dir>/knowledge/requirements.jsonl` — that is, `analysis/<system>/knowledge/requirements.jsonl` under the layout Milestone 0 establishes. It is deliberately the sibling of `knowledge.sqlite`, so the relationship between the authoritative store and its diffable mirror is obvious from the directory listing, and it now also sits two levels from `BUSINESS_RULES.md`, which is where a reviewer already looks for rule output. The database stays authoritative; the JSONL is a deterministic export, the same relationship markdown now has. Because the export must be diffable in a pull request, sort keys within each object as well as sorting the lines, and write `\n` line endings regardless of host.

**Nothing that changes between two runs over unchanged data may appear in the file** — no export timestamp, no run counter, no tool version, no anything else that varies. That is what makes "the second export is byte-identical" a real acceptance criterion rather than a near-miss, and it is the one thing that is trivial to violate by adding a helpful provenance header.

**State that as a determinism rule and not as "no header line of any kind", because the plan requires exactly one header line and the absolute form forbids it.** Step 3's completeness gate says `export` refuses an incomplete corpus unless `--allow-incomplete` is passed, "in which case the incompleteness is written into the export itself" — which is the point of the flag, since the export is what reaches a client and an incomplete corpus presented as complete is the failure the gate exists to prevent. So: **under `--allow-incomplete` only, the file opens with a single JSON object carrying the reserved key `_incomplete`**, listing the offending `run_id`s and, per run, which of the two reasons applies in the words Step 3 mandates — chunks unaccounted for, or coverage never measured. It carries **no timestamp, no counter and no tool version**, so two exports over an unchanged store are still byte-identical and the acceptance criterion is untouched. Without the flag there is no first line and the file is requirements only. `import` skips a leading `_incomplete` object rather than treating it as a record. The rule that actually protects the property is determinism, not the absence of a header; keep it stated that way, and add nothing to this line that a second run could change. Per-record timestamps (`created_at`, `updated_at`) are fine and must be included: they are properties of the record, so they change only when the record does, which is exactly what a diff should show. That last clause is a *requirement on the merge*, not an assumption about it — see Step 6: a write that changes no value must not bump `updated_at`, or this criterion fails on the second export after any re-ingest and the diff shows every record as modified. If an export needs to record when it ran, that belongs in the import marker described below, not in the exported file.

Be precise about whose git tree that is, because Milestone 0's relocation changed the answer. The export lands in the **analysis** tree, `<app>/analysis/<system>/knowledge/`, not inside the client's code checkout — that separation is the point of the layout change, and it means the file belongs to whatever repository tracks the analysis outputs rather than to the client's own repository and review process. When that analysis tree is under `repos/` here, the ignore rules Milestone 0 writes name `knowledge/knowledge.sqlite*` and `knowledge/chroma/` specifically and never the `knowledge/` directory, so the sibling `requirements.jsonl` is tracked in this repository — which is the intent, not an oversight to be "fixed" by widening the rule to the directory.

**Demonstrate that on `repos/ctcm/ctcm-api`, not on the NNG unit, and know why the choice is forced.** The arrangement this whole decision rests on — the authoritative database ignored, its diffable export tracked — is already true at `ctcm-api` and is verifiable there today: `git check-ignore` reports `legacylift-docs/knowledge/knowledge.sqlite` as ignored by `.gitignore:89` and reports `legacylift-docs/knowledge/requirements.jsonl` as **not** ignored. So the acceptance criterion belongs there: after an `export`, `git status` shows `requirements.jsonl` as an untracked or modified file while `knowledge.sqlite` does not appear at all. On the NNG unit that criterion is unrunnable, because `.gitignore:92` ignores that entire tree — which is a property of how the NNG comparison corpus is kept locally, not a defect in this design, and not a reason to widen any rule. Without a criterion somewhere, the byte-identity test is the only thing standing behind the export and it proves determinism rather than reviewability, which are different claims.

`requirements import --from-jsonl` reads it back. **Import happens only when explicitly invoked — never on open, never implicitly**, so that a stale checkout cannot overwrite approved state or human-authored fields behind the analyst's back. Say that in the command's help text.

Import is the **one declared exception** to "`set_state` is the only writer of `gr.state`," and the exception has to be written down or the next reader will treat it as a bug. The rule elsewhere in this plan exists to stop *automation* approving its own output: no extractor, no workflow, no future producer may move a record out of `draft`. Import is not automation approving anything — it is restoring judgements a human already recorded, in this same store, through `set_state`, and which the JSONL merely transported. Routing it through `set_state` would be worse than useless: `set_state` re-runs the Step 4 gate, so a requirement legitimately approved on a machine whose working tree matched the citations would be *refused* on a checkout where the cited code has since drifted and the validator now fires an `ERROR`. That would make approvals un-restorable exactly when the store is most needed.

So implement import as a distinct writer with its own guard rails, and state all four in the help text:

- Import **never** writes a state a `gr_id` did not already carry in the file. It restores; it does not decide.
- Import writes through a single dedicated function, `import_records`, which is the only other function in the codebase permitted to write `gr.state`. Both it and `set_state` are the complete, enumerable set — assert that in a test that greps for writes to the column.
- Every import is recorded: append one `gr_import` row (Step 3) carrying the source path, the timestamp, the row count and how many rows changed state, so a surprising state change is traceable to a specific import rather than appearing to have happened spontaneously. That table is where the marker lives; it is not written into the exported file, and it is not joined to `gr` (see Step 3 for why a per-record attribution is Milestone 4's).
- Import **refuses by default** to lower a state — to move a record from `approved` back to `draft`, or from `approved` to `rejected` — and requires an explicit `--allow-downgrade` to do it. A stale checkout's most likely damage is un-approving work, and that is the case the flag makes deliberate.

Update the Milestone 1 acceptance wording accordingly: what must hold is that *no automated producer* can move a record out of `draft`, not that literally one function writes the column.

Export the GR tables only. Exporting `file_domains` is a real gap but it belongs to domain-tagging scope, not here; note it and move on.

Then wire the producer. Modify `.claude/skills/code-modernization/commands/modernize-extract-rules.md` so that after the workflow returns, the calling session writes the workflow's return value to a JSON file and invokes `requirements ingest` on it, then renders `BUSINESS_RULES.md` *from the store* rather than from the return value. **The notation rewrite itself is Step 6a's, not this step's, and it touches all three files that carry the Given/When/Then shape** — the workflow's `RULES_SCHEMA`, the `business-rules-extractor` agent definition, and this command file's Rule Card format. Do that work there; this step only adds the ingest call and repoints the rendering.

**`DATA_OBJECTS.md` keeps being rendered from the return value, and that is not an oversight to fix here.** The workflow returns `dataObjects` alongside the rules, and this schema has no table for them — so "render the markdown from the store" is achievable for one of the two files and impossible for the other. Do not add a bespoke `gr_data_object` table to close the gap: a data object is a cluster of terms and fact types, which is exactly what Milestone 3's vocabulary layer (`term`, `fact_type`) is chartered to model, and a one-off table in Milestone 1 would be superseded by it within one milestone. So in Milestone 1: rules come from the store, data objects come from the return value, and the command file says so plainly rather than leaving a reader to discover the asymmetry. Milestone 3 takes ownership of data objects when it builds the vocabulary layer.

Two mechanics that the command file has to spell out, because the slash command runs inside the analyzed repository while the CLI lives in this one. First, how it is invoked: shell out to `legacylift-search requirements ingest …` with `py -3.12 -m legacylift_search.cli requirements ingest …` as the documented fallback. That is the pattern the same workflow already uses for its coverage step (`extract-rules.js:212-213`), so follow it rather than inventing a second convention. Second, what happens when the CLI is absent or the ingest fails: the session still renders `BUSINESS_RULES.md` and `DATA_OBJECTS.md` from the workflow's return value and says plainly in its output that the store was not updated. The rule extraction is expensive and must never be lost because a tool on the far side of it was missing — the same graceful-degradation choice the coverage step already makes. Because you are modifying a file under `.claude/skills/code-modernization/`, the repository's contribution rules require an Apache-2.0 attribution line: add or update `Modified by CapTech on <the date you do the work>: [brief description].` immediately after the YAML frontmatter, keeping only the latest such line. That file already carries a `2026-07-01` line — **overwrite it**, do not append beside it, and use the current date rather than any date written in this plan.

### Step 10: the three mandatory measurements

**This section says what the three numbers are and what they mean. To run the step, use
[`reqs-to-data-store-step10-runbook.md`](./reqs-to-data-store-step10-runbook.md)**, which carries
the measured on-disk state, the exact commands and SQL, the environmental traps, and the
subagent/model split. This section stays authoritative on the *meaning* of the numbers and the
verdicts they force; where the two disagree, this one wins.

Milestone 1 must produce three numbers, recorded in `Outcomes & Retrospective`. The third is stated first because it is the one that can invalidate the other two.

**The intra-run collapse rate on the first ingest into an empty store**: how many offered rules landed on a `gr_id` that another rule in the same run also landed on, counted with `gr_run_hit.offer_ordinal` (Step 3). This is the direct measurement of the first-ingest false-same case in Step 6 — two rules citing identical lines, discriminated only by `rule_class` and `pattern` — and it is the one number in this milestone that says whether the corpus is missing rules it never knew it dropped. A false-same is invisible by construction, so this figure is the only evidence available about it. Take it on the NNG unit, not on a fixture, because the case it detects is dense real code. If it is large, say so plainly and treat every coverage claim from the store as provisional until the key is strengthened; do not proceed to Milestone 1.5's comparison as though the corpus were complete.

Then the two that were always here, both of which are now one query each because Step 3 fixes the `decision_table` payload: **how many rules collapse into a decision table** is the count of `gr` rows with `structured_body_type = 'decision_table'`, and **the distribution of rule counts per candidate table** is the distribution of `len(structured_body.rules)` over those rows — `rules` being DMN's own list of decision rules, so the number means what the study below means by it. These are not idle statistics: the argument for DMN-shaped decision tables is that such a table is *executable*, so the legacy system can serve as an oracle for the decision-logic subset. But the only published code-to-DMN study reports zero-percent decision-rule accuracy on three of its eight logic cases, collapsing past roughly six rules per table, on hand-picked single-file Java of at most nineteen rules. **So if most candidate tables in your corpus exceed about six rules, the replay loop waits.** Treat the loop as a *detector of bad extraction* rather than a validation of good extraction — that framing makes it more valuable, not less, because it is the only place in the design where extraction error is measurable rather than assumed. Do not promise DMN coverage of a corpus.

Also record `rounds_run`, `round_cap`, `stop_reason` and `new_rules_in_final_round` per run in `gr_run`, and surface them in `requirements stats`. **The prerequisite this sentence used to carry is discharged (2026-09-02):** it said "three of the four need adding to the workflow's return value first", and they have been — `extract-rules.js` now emits `roundCap`, `stopReason` and `newRulesInFinalRound` in the camelCase spellings `gr_ingest` already read, and `stats` surfaces all four with NULL rendered as *unmeasured* rather than as zero. `stopReason` is derived from **three** termination paths, not the two the `while` guards suggest: two consecutive dry rounds, the `maxRounds` cap, and the in-loop `break` when the token budget nears exhaustion — which is the producer of `budget_exhausted`, a value this plan named without ever saying what wrote it. `dry` is tested before `round_cap` because both guards can fail on the same iteration. So this paragraph is now a reporting instruction only, and the numbers it asks for will be present in the run rather than NULL.

## Milestone 1.5: the SPEC-2 baseline comparison

At the end of this milestone there is a number that says whether the new pipeline covers more or less of a real codebase than the two runs that came before it, and a written statement of what that number may and may not be used to claim. Nothing in the store changes.

This milestone implements `NORMATIVE SPEC-2` in the design draft. **Implement that section literally, as with SPEC-1** — its interpretation rules are the point, not decoration, and they constrain what any deliverable is allowed to say. The shape of the work:

Parse the two baselines. They are markdown, they have no identifiers, and **they are not the same shape**.

> **CORRECTED 2026-09-10, measured — the citation paths carry NO prefix, and the sentence this
> replaces said they did.** All 470 BASE-ENH and all 1,038 BASE-ORIG backticked citations are
> **code-root relative** (`ple-services/JavaSource/...`, `ple-web/src/main/java/...`) — zero carry a
> `repos/`, `legacy/`, `./` or absolute prefix. That is **the same shape as
> `gr_citation.relative_path`**, so the join needs **no** prefix reconciliation at all. This
> previously read "Both paths are relative to `repos/nng-app-legacylift-analysis/`", and the frozen
> data point below carried a matching warning to strip a `legacy/customer.ple.nng.app/` prefix; both
> were wrong, and following either would have produced zero overlap — which this milestone's own
> rules say "will look like a result". The top-level segment census is in `Outcomes &
> Retrospective` → *Milestone 1.5 pre-flight, measured 2026-09-10*.

`analysis-original/customer.ple.nng.app/BUSINESS_RULES.md` holds its 815 rules in two places and so needs two parsers: **55** rules as `###` cards under `## P0 — Confirmed critical rules` (file lines 25–709), and **760** rules as markdown table rows under `## Full rule catalog` (lines 710–1491). `55 + 760 = 815` is the integrity check that the parse is right, and the two halves are disjoint — the catalog does not repeat the P0 cards.

Two measured details the parser needs and SPEC-2 §S2.1 glosses over. The catalog is **four** per-category sub-tables, not one: `### Validation (424)`, `### Calculation (57)`, `### Lifecycle (185)`, `### Policy (94)`, which sum to 760. So a row counter must skip four header-plus-separator pairs, which is exactly why a raw `grep -c '^|'` over that range returns **768** rather than 760 — SPEC-2 quotes the grep, this plan quotes the row count, and both are correct. Second, those per-category numbers are the *catalog* counts, not the corpus counts: the Summary block's by-category totals are Validation 441 / Lifecycle 215 / Policy 101 / Calculation 58, and each difference is the P0 rules of that category, which sum back to 55. Use that as a second integrity check.

`analysis-semantic-search-enhanced/customer.ple.nng.app/BUSINESS_RULES.md` holds 470 rules as `####` cards and needs one parser. Citations there render as `[📄](path:start-end)`; in BASE-ORIG they are a backticked path on the card's metadata line, or a table column. The reproduction recipe including the citation regex is in SPEC-2 section S2.6.

**These corpora are not in git.** `.gitignore:92` ignores `repos/nng-app-legacylift-analysis/` in its entirety — client code plus the original code-modernization outputs, kept local and never committed. So a cold-start agent on a fresh clone cannot run this milestone at all, and nothing in the repository will say why. Confirm both files are present on disk before planning any of this work, and if they are not, stop and ask rather than reconstructing a baseline.

Join on code location, not text: `(normalized_path, start_line, end_line)`, matching when line ranges **intersect** within the same file, and report both a strict count (identical ranges) and a tolerant count (intersecting) with the tolerant one as the headline and the strict one as the floor.

**Run the noise floor first.** Compare BASE-ORIG against BASE-ENH before comparing anything new against either. Two runs of a similar pipeline over identical code produced sets differing by hundreds of rules, and that difference is the bar: a new-vs-baseline delta smaller than the baseline-vs-baseline delta is within noise and may not be reported as a result. Doing this second, after seeing the new numbers, is how the exercise turns into a post-hoc story.

Report rule count **and distinct-files-cited** together, always. BASE-ORIG cites 327 distinct files against BASE-ENH's 148 while carrying fewer rich cards, so a run that raises rule count while narrowing file coverage has regressed and raw counts hide that completely. Every headline number must state which of the three reference points it used — 229 (unenhanced single run), 470 (best single run), 815 (three-run merge) — and whether the match was strict or tolerant. **Never compare a single new run against 815**, which is a merge of three scoped runs.

Two constraints on the write-up, taken from SPEC-2 section S2.4. Neither baseline is ground truth; both are unvalidated model output over the same code, so this measures change and agreement, never accuracy. And a higher rule count is not a better result — 815 versus 470 over the same system, and the smaller set was judged the better run.

**A third constraint, added by `PR-79`: say that the extractor's prompts changed.** Both baselines are the output of the *old* extractor, which emitted Given/When/Then and no notation. Step 6a rewrites `RULES_SCHEMA`, the agent definition and the Rule Card format so the extractor authors SPEC-1 statements — so a new run differs from both baselines in prompt **and** in pipeline, and no comparison here can separate the two. This does not invalidate the exercise: §S2.4 already forbids accuracy claims, the join is on code location rather than text, and the mandatory BASE-ORIG-versus-BASE-ENH noise floor remains the control for run-to-run variation. What it forbids is a sentence attributing a delta to the semantic index, or to merging, without naming the prompt change alongside it. An earlier version of this plan capped the extractor extension at three fields specifically to protect this measurement; that cap is gone, and the honest replacement is disclosure rather than a cap nobody could implement.

**Two measurements from the old corpus are worth recording here before they are lost**, because they are the baseline for whether the notation rewrite worked and they cannot be taken again once the extractor changes. On BASE-ENH's 470 rules: `plainEnglish` carried a behavioral rule keyword on 30% and a definitional one on 6%, with 65% carrying none and `shall`/`will` appearing zero times; 66% of `then` values were passive constructions, 51% carried a semicolon and 36% an `and`. Those are the rates the rewritten extractor should move, and the `V-STY-03`, `V-SING-01` and `V-KW-*` finding rates on the new corpus are the same measurement taken from the other side.

This milestone needs the NNG app unit ingested into a GR store, which means it depends on Milestone 1 being wired end to end, not merely on the schema existing.

### The new-run data point, frozen 2026-09-10 before Phase 6 — read this before running Phase 6

**These are the numbers this milestone compares, taken while the store is still the output of a
single extraction run.** They are recorded here rather than left in the store because **Phase 6
destroys one of them irrecoverably** — see the asymmetry below. Every figure is from
`knowledge.sqlite` after Phases 3–5, and the store at that moment held 379 rows all carrying
`first_seen_run_id = RUN-01M2646H97JAZJPPKHSCZT1RRY`.

| | value |
|---|---|
| requirements | **379** (from 437 offers: 272 new + 58 merged + 107 candidate) |
| **distinct files cited** | **118** — 116 if the one prose-citation rule's four unresolvable paths are excluded |
| citations | 383 (379 resolvable, 4 `unresolved`, all on one rule) |
| citations per requirement | 1 to 4 |
| by category | Validation 168, Calculation 74, Policy 69, Lifecycle 68 |
| by rule class | behavioral 196, definitional 183 |
| provenance | one run, four rounds, `stop_reason=round_cap` — a floor, not a sweep |

**Against the three reference points this section names**, and stating which was used as §S2.4
requires: BASE-ORIG is **815 rules / 327 files** (a merge of three scoped runs), BASE-ENH is
**470 / 148** (the best single run), and the unenhanced single run is **229**. The honest comparison
for this data point is **against BASE-ENH's 470/148**, single run against single run; comparing 379
against 815 is the thing this section explicitly forbids.

**Note what the pair of numbers says before anyone reports the rule count alone.** 379 rules over 118
files is lower than BASE-ENH on **both** axes. This section's own rule is that a run raising rule
count while narrowing file coverage has regressed; here neither rose, which is a different result and
must not be dressed up as one. Run the mandatory BASE-ORIG-versus-BASE-ENH noise floor before
attaching any meaning to a 470→379 delta, and remember `PR-79`: the extractor's prompts changed too,
so the delta cannot be attributed to the pipeline.

**The recoverability asymmetry, which is the reason for freezing this.**

- **Rule count survives Phase 6.** `gr.first_seen_run_id` marks every row with the run that created
  it, so `WHERE first_seen_run_id = 'RUN-01M2646H97JAZJPPKHSCZT1RRY'` recovers the single-run rule
  set exactly, however many later runs merge into the store.
- **Distinct-files-cited does not.** `gr_citation` has **no `run_id` column**, and
  `_write_children` upserts citations on `(gr_id, relative_path, start_line, end_line)` — so a later
  run that merges into an existing requirement and cites a *different* line range simply **adds a
  citation row to that requirement**, indistinguishable from the original. After Phase 6 there is no
  query that recovers which files the first run cited. **118 is available now and never again.**

Runs 2 and 3 (Phase 4's re-ingests) added nothing — 383 citations before and after — so the figures
above are unaffected by them.

**This data point SURVIVED Phase 6 and is still recoverable from the real store**, because Phase 6
was ingested into a scratchpad copy per the 2026-09-10 decision. The real store still reports `gr`
379, `gr_run` 3, `gr_merge_candidate` 148 and 118 distinct citation paths — re-verified after Phase
6 ran. **The asymmetry above was therefore never exercised**; it remains the reason not to ingest a
second run for real until this milestone's comparison is chosen.

**One refinement Phase 6 measured, since it re-derived these figures independently.** The
parenthetical above — "116 if the one prose-citation rule's four unresolvable paths are excluded" —
is the count of **resolvable paths**. The count of **real files** is **117**: of the 118 distinct
`relative_path` values, exactly one is a 445-character prose string that the extractor put in a
`source` field (entry 13's class), and it counts as a distinct path while naming no file. Both
readings are correct for what they measure and they differ by one, so **say which one a reported
number is.** The pair to compare against BASE-ENH's 470/148 is **379 / 117**. Filter on path length
or on `anchor_resolution` before reporting any file count from this table.

**~~One join detail measured at the same time, because it will otherwise cost a cycle.~~ WRONG —
struck 2026-09-10 after measuring both baselines directly. Do not act on the struck version.**
It claimed the baselines' paths carry a `repos/nng-app-legacylift-analysis/` prefix and that the
join must reconcile `legacy/customer.ple.nng.app/` before matching. **Measured: neither baseline
carries any prefix.** All 1,508 citations across the two files (1,038 + 470) are code-root relative,
**identical in shape to `gr_citation.relative_path`** — e.g. both sides say
`ple-services/JavaSource/com/nng/ple/service/point/validator/PointFarmTapValidator.java`. **The join
needs no path surgery.** Stripping or adding a prefix on the strength of the struck paragraph is the
one thing that would produce zero overlap and look like a result. The census and the two real parser
hazards are in `Outcomes & Retrospective` → *Milestone 1.5 pre-flight, measured 2026-09-10*.

## Milestone 2: the other four producers

Four more skills generate requirement-shaped output today, each with its own identifier scheme and no connection to the others: `.claude/skills/legacylift-classic/skills/detailed-req-documenter/`, `.claude/skills/legacylift-classic/skills/business-documenter/`, `.claude/skills/legacylift-classic/skills/use-case-generator/`, and `.claude/skills/legacylift-classic/skills/user-story-generator/` (these four moved into the `legacylift-classic` plugin on 2026-09-11; they are invoked as `legacylift-classic:<name>`, not by the bare name). Point each at the same schema and the same `requirements ingest` path. No schema change should be needed beyond using the `story` value of `kind` and the `derived_from` column, both of which Milestone 1 already creates. `derived_from` holds only the rules a story summarizes — supersession lives in `superseded_by` (Step 3) — so the rollup query is the whole column with no filtering.

A user story is a rollup requirement referencing the rules it summarizes through `derived_from`. Do not put actor fields on every individual rule; per-rule actors would be fabricated.

**"No schema change" is true and, on its own, misleading — this milestone has a blocker that is not in the schema.** The validator runs on `statement`, and all twenty-eight SPEC-1 checks assume a *rule*. A user story — "as a claims adjuster, I want to see open items, so that I can prioritize" — carries no rule keyword, so `V-KW-01` fires an `ERROR`; its `rule_class` is neither `behavioral` nor `definitional`, so `V-CLASS-01` fires another. Step 4's gate is zero `ERROR` findings, so **under Milestone 1's rules no story is ever approvable**, and the discovery would otherwise land after four producers had been wired up.

The resolution is that **`kind` selects which checks run**, and defining the story set is this milestone's work — it is deliberately not specified here, because nothing has yet been learned from a real story corpus, but the question is named so Milestone 2 starts from it rather than rediscovering it. This is not a SPEC-1 amendment: the twenty-eight checks are unchanged and continue to apply in full to `kind = 'business_rule'`, and what is new is a second `kind` that needs its own answer. Q3e settled the rollup *shape* and left notation open; this is that gap.

One constraint on whatever emerges: **the gate mechanism does not change.** `set_state` still refuses to approve anything carrying an `ERROR`, and a story does not get a weaker gate because its notation is different — a story with no checks at all would be approvable by default, which is the one outcome to rule out now.

## Milestone 3: the vocabulary layer

Add `term` and `fact_type` tables that requirements reference, populated from Layer-0 symbols and columns plus analyst naming. Four independent sources in the design research agree that rules are built *on* a vocabulary and that the vocabulary must be recovered first. It is sequenced last here for a practical reason: the review loop from Milestone 1 is what populates it, so it cannot usefully exist before that loop does.

**This milestone also takes ownership of data objects.** Milestone 1 deliberately leaves `DATA_OBJECTS.md` rendered from the extractor's return value rather than from the store, because a data object is a cluster of terms and fact types and belongs in this layer rather than in a bespoke table (see Step 9). So part of this milestone is modelling the workflow's `dataObjects` output as `term` and `fact_type` rows, and moving `DATA_OBJECTS.md` onto the store the way `BUSINESS_RULES.md` already is. Until then the asymmetry stands and is documented, not hidden.

## Milestone 4: the review experience (deferred)

Not planned here. Milestone 1 deliberately ships the smallest write path its own tests need (`requirements set-field`, Step 8) and nothing more. The review experience is a separate deliverable — see `docs/exec-plans/pending/reqs-review-ui.md`, which carries what is already known about it: the store's shape, the fields a reviewer must touch, the fields that must stay read-only, and the two invariants any UI has to preserve (a live column differing from its `_extracted` shadow is the only definition of "edited", for each of the three shadowed fields, and the approval gate lives in `set_state`, never in the client).

Sequencing note: Milestone 4 is not a prerequisite for Milestones 1.5, 2 or 3. It is a prerequisite for *the store being used at scale by humans*, which is a different claim and should not be conflated with the milestones that prove the store works.

## Concrete Steps

All commands assume the working directory `tools/legacylift_search` unless stated otherwise. Use the virtual environment's interpreter, not anything on `PATH`.

Establish the baseline before changing anything:

        cd tools/legacylift_search
        .venv/Scripts/python.exe -m pytest -q

Expect **1,250 passed, 0 failed** (verified 2026-09-08, exit code 0; it was 357 before Milestone 0, 408 after it, 521 after Milestone 1 Steps 1–2, 588 after Step 3, 706 after Step 4, 734 after Step 5, 822 after Step 6a's five-unit wave, 870 after Step 6, 965 after Step 8's Wave C1 foundation, 1,131 after its four parallel command units, 1,159 after the pre-Step-10 fix wave, **1,207** after `feature/layer0-extraction-gap-detection`, and **1,250** after the 2026-09-08 Layer-0 coverage widening
merged in on 2026-09-03 — that last step added no requirements tests at all, only the gap-detection
plan's 48: M0's 18 linguist tests, M1's 28 walk tests and 2 `DomainsFile` tests).
**Below 1,250 is a regression you caused, not an environmental failure — bisect before continuing.** Note the 822: this section briefly recorded 821, which was a count taken before the last test of that wave was added — a reminder to take the number after the work, not during it. Update this number whenever you add tests, because it is the only baseline anyone checks against. The suite takes **13–20 minutes** at this size, so run it in the background if your tooling allows.

Two quirks of running it here, both of which have wasted a session before. **`pytest -q` in this project prints no summary line, only progress dots** — to get a count use `--collect-only -q`, which prints `tests/file.py: N` per file; note that `grep -c "::"` over that output matches nothing and exits 1, which reads as a failure and is not one. And if `tests/test_bedrock_embedder.py` fails, that *is* environmental: it needs the declared `aws` extra (boto3), installed with `.venv/Scripts/python.exe -m pip install -e ".[aws]"`. That extra is required to index any repository configured with the hosted embedding provider, though not for this plan's own tests.

For Milestone 0, after creating `src/legacylift_search/migrations.py` and wiring both stores:

        .venv/Scripts/python.exe -m pytest tests/test_migrations.py -v

Expect every test named in the Milestone 0 narrative to pass. Then confirm no regression:

        .venv/Scripts/python.exe -m pytest -q

Expect the current baseline plus your new tests, all passing. If the total is below the baseline recorded above, you have caused a regression — bisect before continuing.

For each subsequent step, add its tests, run that file alone first, then run the full suite. Commit at every step — the plan explicitly favors frequent commits, and the branch is `feature/reqs-to-data-store`.

Step 3, as actually run (2026-09-01, `14a818e5` plus the `gr_id NOT NULL` follow-up):

        .venv/Scripts/python.exe -m pytest tests/test_gr_schema.py tests/test_gr_body_schemas.py -q
        .venv/Scripts/python.exe -m pytest -q

51 + 16 new tests, then 588 total, exit 0 both times. Two things about *counting* the suite that
cost time here and will cost it again. `pytest -q` in this project prints only progress dots, so
the count has to come from `--collect-only -q`, which prints `tests/file.py: N` per file and no
total — sum it: `... --collect-only -q | awk -F': ' '/^tests\//{s+=$2} END{print s}'`. And a
`pytest -q` run that has *already been backgrounded* through `| tail` shows nothing at all until it
exits, which reads as a hung command and is not one.

There is no CLI surface to exercise for Step 3 and there will not be one until Step 8, so the
schema's own guarantees are the only observable. Verify one by hand if you want the shape of it:

        .venv/Scripts/python.exe -c "import tempfile,pathlib; from legacylift_search.knowledge_store import KnowledgeStore; ks=KnowledgeStore(pathlib.Path(tempfile.mkdtemp())/'k.sqlite'); print(len([r for r in ks._connect().execute(\"PRAGMA table_info('gr')\")])); ks.close()"

`42`. Note `PRAGMA table_info` over `gr_run` is the one place that lies to you — it omits the
generated `complete` column; use `PRAGMA table_xinfo`.

Step 4, as actually run (2026-09-01):

        .venv/Scripts/python.exe -m pytest tests/test_gr_validator.py tests/test_gr_state.py -q
        .venv/Scripts/python.exe -m pytest -q

83 + 35 new tests, then 706 total, exit 0 both times. There is still no CLI surface — Step 8 is
where `requirements validate` and `requirements set-state` appear — so these two one-liners are
the shape of it by hand:

        .venv/Scripts/python.exe -c "from legacylift_search.gr_validator import CHECK_IDS; print(len(CHECK_IDS))"
        .venv/Scripts/python.exe -c "from legacylift_search.gr_validator import split_slots; s='A branch manager may grant a spot discount only if the rental is open.'; sp=split_slots(s,'behavioral','B-RESTRICT'); print(repr(s[sp.action[0]:sp.action[1]]), repr(s[sp.condition[0]:sp.condition[1]]))"

`28`, then `'grant a spot discount' 'the rental is open'` — the discontinuous keyword and the
trailing condition, which are the two shapes the superseded two-part split got wrong.

**The reachability probe is the one thing the suite cannot show you and it is worth re-running
whenever a check changes.** It constructs a triggering record for each of the twenty-eight
identifiers and reports any that no input can fire — the seventh round's writer-reachability
defect one level down, which the membership assertions do not catch, because a check can be
correctly named, correctly severitied and still unfireable. The Step 4 run reported
`unreachable: []` and zero blocking `ERROR`s across ten conformant statements outside SPEC-1's
own examples; the script is small enough to rewrite from that description and was not kept.

Step 5, as actually run (2026-09-02):

        .venv/Scripts/python.exe -m pytest tests/test_gr_refresh.py -q
        .venv/Scripts/python.exe -m pytest -q

28 new tests, then 734 total, exit 0 both times. There is still no CLI surface — `requirements
search`, `reindex-vectors` and `set-field` are all Step 8's — so these two one-liners are the
shape of it by hand:

        .venv/Scripts/python.exe -c "import tempfile,pathlib; from legacylift_search.knowledge_store import KnowledgeStore; ks=KnowledgeStore(pathlib.Path(tempfile.mkdtemp())/'k.sqlite'); print([r[1] for r in ks._connect().execute(\"PRAGMA table_info('gr_fts')\")]); ks.close()"
        .venv/Scripts/python.exe -c "from legacylift_search.gr_refresh import describe_vector_shortfall as d; print(d(10,4)); print(d(10,10))"

`['gr_id', 'name', 'statement', 'as_built', 'rationale']`, then the shortfall sentence naming
`reindex-vectors` followed by `None` — the two states stage two has to be able to tell apart.

**Three things about running Step 5's own tests that will cost time again.** Chroma tests need
`tempfile.TemporaryDirectory(ignore_cleanup_errors=IS_WINDOWS)`, which is already the house
pattern in `tests/test_vector_store.py`: `close()` drops the client and forces a `gc.collect()`
and Windows still holds the handle often enough to fail teardown, and a leaked teardown error
reads as a test failure. `gr_citation.provenance` is `('extracted','repaired','human')` — not
`'extractor'`, which is what the field map calls the same idea one table over. And a `Symbol`
built by hand needs an `entity_class` from `identity.ENTITY_CLASSES`' seven values; a plausible
word like `operation` is a `pydantic` validation error, which is Step 2 doing its job.

Step 6a plus Steps 7 and 9's functions, as actually run (2026-09-02) — five parallel units, so
the per-file counts are listed rather than a single delta:

        .venv/Scripts/python.exe -m pytest tests/test_citations.py -q      # 22
        .venv/Scripts/python.exe -m pytest tests/test_gr_fields.py -q      # 16
        .venv/Scripts/python.exe -m pytest tests/test_gr_subject.py -q     # 17
        .venv/Scripts/python.exe -m pytest tests/test_gr_export.py -q      # 20
        .venv/Scripts/python.exe -m pytest tests/test_gr_dataflow.py -q    # 13
        .venv/Scripts/python.exe -m pytest -q                              # 821, exit 0

**Two things about running a wave in parallel that cost time here and will again.** Five agents
editing one checkout is safe only while their file ownership is disjoint — it was, by
construction — but the *test suite* is shared, so a full-suite run taken while another unit is
mid-edit reports failures that are neither yours nor real. One of them was a genuine transient in
`test_gr_state.py`, observed and then gone. Take the per-file count during the work and the
full-suite count once, at the end. And `models.py` had to land **first, alone**, as a single-owner
commit: five units imported the same ten new Pydantic models, and it is the one file that could
not be divided among them.

There is still no CLI surface for any of this — `requirements ingest` and the other thirteen
commands are all Step 8's — so these two one-liners are the shape of Step 6a by hand:

        .venv/Scripts/python.exe -c "from legacylift_search.citations import parse_citation as p; print(p('- src/Foo.java:10-20')); print(p('C:/x/Foo.java:10-20'))"
        .venv/Scripts/python.exe -c "from legacylift_search.gr_fields import EXTRACTOR_FIELD_MAP as m, EXTRACTOR_OWNED_FIELDS as e; print(len(m), len(set().union(*m.values())), len(e))"

`[('src/Foo.java', 10, 20)]` then `[('C:/x/Foo.java', 10, 20)]` — the stripped list marker and
the colon inside a path, which are the two shapes a second parser gets wrong. Then `14 17 14` —
fourteen incoming keys reaching seventeen columns, which is why the map's values are tuples.

**Before following the sequence below, read [`reqs-to-data-store-step10-runbook.md`](./reqs-to-data-store-step10-runbook.md).** This block is the *design* of the end-to-end run and was written before the unit's current state was measured; the runbook is that measurement (2026-09-02) plus the exact commands. Three things it corrects or supplies that this block does not know: the NNG unit's `index.sqlite` is at `user_version` 0 and predates Step 2, so it must be **rebuilt** — which is the same action as Milestone 0's open criterion; `/modernize-preflight`, `/modernize-assess` and `/modernize-map` have **already run** against this unit and their outputs are current, which turns "do not shortcut it" below into a decision the user must make rather than a rule to follow blindly; and the `PATH` `legacylift-search` shim is **broken**, so every command must use the venv binary or the ingest step silently takes its graceful-degradation branch and leaves the store empty.

For the end-to-end acceptance run the repository needs **two** things, and this is where it is easy to go wrong: an index, and a domain set. `subject` is derived from `file_domains`, which `tag-domains` populates from the `analysis/<system>/domains.json` that `/modernize-assess` authors. In the normal pipeline that has already happened by extraction time, but the obvious candidate repository here has not been through it: `repos/ctcm/ctcm-api` has `legacylift-docs/index/` and **no** `domains.json` and no `knowledge.sqlite` anywhere under `repos/ctcm/`. It also has no `legacy/` parent directory, so under Milestone 0's layout rule it keeps resolving to `legacylift-docs/` — check the paths the command prints rather than assuming which shape you are in. Ingesting there proves the merge but exercises only the `llm_named` fallback, and it cannot run the domain-retag invariant test at all, because there is no `domains.json` to change.

So pick deliberately:

- **Fast iteration** — `tests/fixtures/polyglot_repo`, which already ships `domains.fixture.json`. This is the right target for the retag invariant test at unit scale.
- **Realistic end to end** — the NNG app unit, `repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app`, which already has both a `domains.json` and a `knowledge.sqlite` with `file_domains` rows. This is also the unit Milestone 1.5 measures, so ingesting it serves both milestones.
- **`repos/ctcm/ctcm-api`** — only after running `/modernize-assess` and `tag-domains` against it first. Otherwise treat any subject-derivation result from it as untested.

**Run the whole `code-modernization` pipeline, in this order, and do not shortcut it.** Extraction is the fourth step of a four-step sequence, and each earlier step produces something a later one needs — `/modernize-assess` authors the `analysis/<system>/domains.json` that `tag-domains` ingests and that `subject` derivation depends on, and `/modernize-map` is what has usually already run by the time rules are extracted in a real engagement. These are Claude Code slash commands, run from a session whose working directory is the analysis root (the directory holding `legacy/` and `analysis/`), not from `tools/legacylift_search`:

        /modernize-preflight <system>
        /modernize-assess <system>
        /modernize-map <system>
        /modernize-extract-rules <system>

`<system>` is the directory name under `legacy/` — for the reference unit, `customer.ple.nng.app`. The extraction step is what writes the JSON that `requirements ingest` consumes; Step 9 specifies the command file change that makes it do so, and it also renders `BUSINESS_RULES.md` from the store afterwards.

**Keep the extractor's output JSON.** The merge acceptance test re-ingests *the same file*, so save it somewhere stable rather than letting it be a temporary. It is also hours of model time, and it is the input every later test in this plan replays.

**Before ingesting anything, confirm the extractor actually emits the new shape.** Open the saved JSON and check that a rule object carries `ruleClass`, `statement` and `modality`, that `pattern` is either absent or one of §S1.4's ten values, that `assumptions` and `implementationNotes` are present on at least some rules, and that `given`/`when`/`then` are *still there* alongside them. **Check `implementationNotes` across the file rather than on one rule**: it is optional per rule and legitimately absent where the extractor abstracted nothing away, but empty on *every* rule of a real corpus means the prompt instruction did not take (Step 6a) — cross-check that reading against the `V-STY-03` rate after ingest, since the two measure the same abstraction from opposite sides. If the notation fields are missing, Step 6a's rewrite did not take effect in the run — most likely because the agent definition or the Rule Card format still describes the old shape, since all three files must change together. Ingesting anyway will fail on `statement NOT NULL`, which is the correct behavior and not a bug to route around.

Then, from `tools/legacylift_search`, build the index, ingest the domain set, and inspect:

        .venv/Scripts/legacylift-search.exe index --repo-root <repo>
        .venv/Scripts/legacylift-search.exe backfill-hashes --repo-root <repo>
        .venv/Scripts/legacylift-search.exe tag-domains --repo-root <repo> --domains <analysis/<system>/domains.json>
        .venv/Scripts/legacylift-search.exe requirements ingest --repo-root <repo> --system <name> --from <extractor-output.json>
        .venv/Scripts/legacylift-search.exe requirements stats --repo-root <repo>
        .venv/Scripts/legacylift-search.exe requirements list --repo-root <repo> --state draft
        .venv/Scripts/legacylift-search.exe requirements list --repo-root <repo> --candidates

Every `requirements` command takes `--repo-root`, like every other command in this CLI — the flag is not optional on `ingest` in particular, which needs the repository for three separate things: locating `knowledge.sqlite`, reading the cited line ranges to compute each citation's span-level `content_hash`, and reaching `index.sqlite` for the anchor resolution in Step 6a. An `ingest` that cannot find the repository cannot key a single row correctly.

`backfill-hashes` is only needed on an index that predates Step 2; a freshly built index populates `content_hash` at extraction time. Running it anyway is a no-op, so include it in the sequence rather than trying to remember which case you are in.

**Rebuild the index rather than backfilling it, if you have the choice.** Step 2 adds `entity_class` as a declared-at-extraction column, and its migration can only backfill existing rows through a compatibility shim that guesses for framework kinds it does not recognise and defaults the rest to `other` — and promoting a kind out of `other` later is an `ak2:` event. A rebuilt index carries classes its extractors actually declared. Under this plan's intended workflow the question does not arise, because a new analysis starts at `/modernize-preflight` and indexes from scratch; the shim exists for indexes already on disk.

Confirm before going further that `stats` reports a non-zero count of `derived` subjects. If every subject is `llm_named`, `tag-domains` did not run or matched nothing, and the run is not testing what Step 3 built. Note that Milestone 0's relocation **inverts** a piece of folklore from earlier work here. It used to be true that clearing the analysis directory left domain tagging intact, because `knowledge.sqlite` lived under the code checkout and the analysis directory held only markdown. Now `knowledge.sqlite` lives *inside* `analysis/<system>/`, so deleting that directory destroys the domain tagging **and every approved requirement with it**. What survives is narrower and precise: `index --reset` still cannot touch the knowledge store, because reset only removes the index subtree. Do not carry the old rule of thumb forward.

Then run the same ingest a second time — **the same output JSON file, not a second extraction run** — and compare `requirements stats`. The requirement counts must be identical **and so must the citation, scenario and edge-case counts**: a flat requirement count over any growing child table is the same bug one level down. That is the merge acceptance test and it is the headline proof of this milestone, and it is stated against a fixed input on purpose (see Step 6 and Validation and Acceptance).

Only then run extraction itself a second time, and expect a different shape of result: mostly `merged`, some `candidate`, a few `new`. Record `rules_new`, `rules_merged` and `rules_candidate` from that run. The `rules_candidate` figure is the key-instability measurement Step 6 asks for — it is how much the extractor's `ruleClass` and `pattern` moved between two runs over identical code — and it belongs in `Outcomes & Retrospective`. A non-zero `rules_new` here is not a merge defect; treat it as one only if the same rules also fail to appear in `requirements list --candidates`.

### Step 10 Phases 0–1, as actually run (2026-09-08)

**The deviation, stated where the runbook asks for it.** Of the four commands above, this run
re-ran **`/modernize-preflight` only**. `/modernize-assess` and `/modernize-map` were deliberately
skipped: their outputs are current, and re-running `assess` re-authors the pinned canonical
`domains.json` nondeterministically (moving every `derived` subject, desynchronizing the Milestone
1.5 baseline) while authoring neither `vendored_globs` nor `own_identities` — the two provenance
fields `discover_source_files` now reads — so it would delete them and put 11 vendor `.tld`
descriptors back into the index. **Milestone 1.5 compares against this run.** The settled decision
is in the `Progress` Next action; the widening it turns on is
`active/layer0-extraction-gap-detection.md`.

Phase 0, from `tools/legacylift_search`:

        .venv/Scripts/python.exe -m pytest

`1250 passed in 381.74s (0:06:21)`, exit 0. Note the bare `-m pytest`: `pyproject` already sets
`addopts = "-q"`, so passing `-q` again gives `-qq` and suppresses the summary line that makes the
count readable.

The Bedrock probe, same directory, with `AWS_BEARER_TOKEN_BEDROCK` and `AWS_REGION` exported from
`.claude/settings.local.json`:

        .venv/Scripts/python.exe -c "from pathlib import Path; from legacylift_search.config import load_manifest; from legacylift_search.embeddings import create_embedder; m=load_manifest(Path(CODE)/'semantic-search.manifest.json'); e=create_embedder(m.embedding); print(type(e).__name__, len(e.embed_documents(['x'])[0]))"

`BedrockEmbedder 1024`. The method is **`embed_documents`/`embed_query`**, not `embed` — there is
no `embed`, and reaching for it costs a cycle.

The pre-rebuild verification, which must happen before the rebuild because
`repos/nng-app-legacylift-analysis/` is gitignored and the widening's manifest and `domains.json`
edits are therefore on disk only:

        .venv/Scripts/python.exe -c "... load_manifest(...); print(len(discover_source_files(CODE, m)))"

`1504`, with `Counter` over the suffixes giving `.tld: 2` — `naesb.tld` and `nngauthz.tld`. Two
API facts worth writing down: `SourceFile` exposes `relative_path`/`absolute_path`, **not** `path`,
and `ProjectConfig.domains_file` is what resolves the classifier, so a manifest missing it
silently indexes the vendor copies.

Phase 1 proper, all from `tools/legacylift_search`, with `CODE` =
`repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app` and `DOMAINS` =
`repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.app/domains.json`:

        .venv/Scripts/legacylift-search.exe index --reset --repo-root <CODE>
        .venv/Scripts/legacylift-search.exe backfill-hashes --repo-root <CODE>
        .venv/Scripts/legacylift-search.exe tag-domains --repo-root <CODE> --domains <DOMAINS>

Transcripts, trimmed:

        [legacylift-search] resolved index directory: ...\analysis\customer.ple.nng.app\index\code-search
        [legacylift-search] resolved knowledge directory: ...\analysis\customer.ple.nng.app\knowledge
        Discovered 1504 source files
        Created 74541 graph edges (full union)
        Skipped dense vectors for 10428 low-value chunks
        Deduplicated 148 duplicate-text chunks (4822 distinct to embed)
        Upserted 4970 new vectors into Chroma collection code_chunks
        files_indexed 1504 | chunk_count 15398 | symbol_count 16268 | ref_count 74278
        graph_edge_count 74541 | fact_count 6955 | embedder api:bedrock:amazon.titan-embed-text-v2:0
        -- 7m28s, exit 0

        Hashed 0 symbols, skipped 0 (0 still unhashed) ... Every symbol has a content hash.
        -- exit 0, the documented no-op on a freshly built index

        tagged: 12 domain(s), 36 edge(s); resolved 1504 file(s)
          (1120 glob-matched, 384 excluded, 0 unassigned); stamped 15398 chunk(s).
        -- exit 0

Then the five assertions. `A2` is a filesystem `rglob` for `legacylift-docs` under `<CODE>` — **not**
`git status`, which reports clean either way because that tree is not its own repository and
`.gitignore:92` ignores it whole. The other four are SQL over the rebuilt `index.sqlite`:

        SELECT COUNT(*) FROM symbols WHERE entity_class IS NULL;                  -- 0
        SELECT COUNT(*) FROM symbols WHERE anchor_key  IS NULL OR anchor_key  = ''; -- 0
        SELECT COUNT(*) FROM symbols WHERE content_hash IS NULL OR content_hash = ''; -- 0
        PRAGMA user_version;                                                      -- 2 (was 0)

Two schema-name traps in the verification queries themselves: `repo_files` has no `path` column —
it is **`relative_path`** — and `file_domains` has no `domain_id` column, it is **`domain`**. Both
cost a re-run.

**Next: Phase 2.** Launch `/modernize-extract-rules customer.ple.nng.app` from a session whose
working directory is `repos/nng-app-legacylift-analysis`, in the **main session** (the return value
is hours of model time with one copy), and save it verbatim to
`analysis/customer.ple.nng.app/knowledge/extracted-rules.json` **before anything else**. Runbook
step 0b — the ASCII-normalized copy of `extract-rules.js` plus the `args` JSON-string shim — has
not been prepared yet and is Phase 2's first task.

### Step 10 Phase 2, as actually run — the 1-round verification run (2026-09-08)

**Phase 2 needed a code fix first.** `RULES_SCHEMA` was 15,242 bytes and every mining agent was
refused before it started. The fix is in `.claude/skills/code-modernization/workflows/extract-rules.js`
(CapTech attribution line overwritten per `CLAUDE.md`, not appended): guidance moved from 43
`description` fields into `NOTATION`, `structuredBody` made permissive, the four `BODY_*` constants
deleted. `RULES_SCHEMA` is now 2,239 bytes. Rationale and the measured threshold are in
`Surprises & Discoveries` → *What Step 10 Phase 2 discovered*.

**Launching a workflow here needs four transforms of the committed file, and three of them have
each cost a launch.** Build the launch copy in the scratchpad — never edit the committed file for
this — and assert each one:

1. **LF line endings.** The approval guard's "control characters" message means `\r`. Python's
   `Path.write_text` translates `\n` to `\r\n` on Windows, which put 798 CR bytes in the copy and
   got two launches rejected. Write with `open(p, "w", encoding="ascii", newline="\n")` and assert
   `not [b for b in p.read_bytes() if b < 0x20 and b != 0x0A]`.
2. **ASCII only.** 69 em-dashes; replace with `--`.
3. **The `args` shim.** `args` arrives as a JSON *string*:
   `const A = (typeof args === 'string' ? JSON.parse(args) : (args || {}))`, then repoint **every**
   read — including `args && typeof args.repoRoot === 'string'`, which otherwise works by accident
   because a JSON string is truthy.
4. **The coverage command.** Point it at
   `tools/legacylift_search/.venv/Scripts/legacylift-search.exe`; the `PATH` shim is broken and the
   documented `py -3.12` fallback is not installed either.

Then syntax-check before spending an approval, because the harness reports only
`Script parse error (line:col)`:

        # strip `export` from meta, wrap, and check
        node --check <(printf 'async function __wrap(args, agent, parallel, pipeline, phase, log) {\n%s\n}\n' "$(cat copy.js)")

A backtick in any text injected into an agent prompt terminates the enclosing template literal —
that is what the parse error was the one time it fired.

The launch, from the repository root:

        Workflow({
          scriptPath: "<scratchpad>/extract-rules-ascii.js",
          args: {system: "customer.ple.nng.app",
                 repoRoot: "repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app",
                 maxRounds: 1}
        })

**`repoRoot` is not optional here.** It sets `legacyDir`, and without it the mining agents are
pointed at `legacy/customer.ple.nng.app`, which does not exist relative to this repository's root
(the agents' working directory is the session's, verified in a transcript). Pass it
**session-relative**, as the command file documents (`repos/ctcm/ctcm-api` is its own example).

Round 1, trimmed:

        Round 1: 135 reported, 133 new (133 total catalogued)
        Round 1 coverage: 179/15398 chunks claimed (1.2%); 15219 uncovered chunks remain
        Coverage note: stopped at maxRounds=1 before extraction ran dry
        133 rules confirmed (50 P0); 0 rejected by referees
        -- 238 agents, 0 errors, 67 min, 6.98M subagent tokens

Note the P0 count differs between the log line (50) and the returned `stats.p0` (44), and the
returned rules agree with `stats`: the log prints the count **before** the P0 panel, which demoted
six. Report `stats`, not the log line.

**Save the return value verbatim before anything else** — this is step 1 of the calling-session work
and it is the only copy:

        analysis/customer.ple.nng.app/knowledge/extracted-rules-round1.json   (513 KB)

It is named `-round1` deliberately, so a later full run cannot overwrite the one corpus that exists.
`repos/nng-app-legacylift-analysis/` is gitignored, so **this file is in no commit and cannot be** —
the same "hours of model time, one copy" exposure the runbook warns about. Step 9's JSONL export is
the durable backup and it only helps once the rules are ingested.

**Then `A1`, on the saved file.** All four runbook checks pass on 133/133 rules, and Given/When/Then
arrives **flat** (`given`/`when`/`then`), which is what `gr_fields.EXTRACTOR_FIELD_MAP` expects. Two
gate mechanics that cost a re-run: the rules are under **`confirmedRules`**, not `rules`, and a
citation's trailing range may be a **comma-separated list**, so a `:\d+-\d+$` strip is not enough —
which is how the multi-range defect was found rather than assumed.

**That round was a verification round, and Phase 2 is now finished by the four-round run below.**
**The multi-range citation defect is settled** — fixed 2026-09-08 before any ingest, so the ~7%
mis-keying this section used to warn about no longer applies and no re-extraction is implied: the
parser change affects how the saved round-1 JSON is *read*, not what it says.

### Step 10 Phase 2, as actually run — the four-round run (2026-09-10)

**The four transforms above are still all four required, and the launch copy built to them worked on
the first approval.** The build script asserted each one mechanically rather than by inspection, and
that is what it caught: 45 em-dashes replaced with 0 non-ASCII remaining; 0 bytes `< 0x20` other
than `0x0A` and 0 CR; the `args` shim inserted with **5** reads repointed (the four live reads plus a
comment, and a positive assertion that no `args.` or `args &&` read remains anywhere else); the
coverage command pointed at the venv exe. Then `node --check` on the `export`-stripped, wrapped copy.

**Two of the four transforms bit inside the transform script itself, which is the argument for
asserting rather than eyeballing.** The replacement prose written *for* transform (d) contained a
literal `py -3.12` and a **backtick** — the backtick is precisely the failure the section above
warns about, since that text is injected into an agent prompt inside a template literal. Both were
caught by the script's own residual-string assertions before an approval was spent. **When you write
replacement text for a transform, the assertions must run against the text you are inserting, not
only the text you are removing.**

The launch, from the repository root:

        Workflow({
          scriptPath: "<scratchpad>/extract-rules-ascii.js",
          args: {system: "customer.ple.nng.app",
                 repoRoot: "repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app",
                 maxRounds: 4}
        })

**No `modulePattern`** — this is the full system, and per the 2026-09-09 finding a `modulePattern`
would not have made it cheaper anyway. **No `resumeFromRunId`**: four prompt fixes landed after both
prior runs, so every mining agent's prompt had changed and nothing would have replayed from cache.

Result, trimmed — the full record is in `Outcomes & Retrospective` → *Step 10 Phase 2, the four-round
run*:

        Round 1: 114 reported, 112 new     Round 3:  94 reported,  92 new
        Round 2: 116 reported, 115 new     Round 4: 128 reported, 118 new (437 total)
        437 rules confirmed (49 P0 in the log; stats.p0 = 45); 0 rejected by referees
        -- 552 agents, 0 errors, 15.37M subagent tokens, ~1.6 h active compute

Saved verbatim, before any gate, to
`analysis/customer.ple.nng.app/knowledge/extracted-rules-4round.json` (1,229 KB) — a NEW file, with
the three earlier corpora asserted byte-unchanged. `A1` passes 437/437; **88/88 `structuredBody`
payloads validate**, so no repair pass; 437 of 441 citation triples resolve, the 4 exceptions being
one rule with a prose `source` (entry 13). **Not ingested** — `MEAS-1` has one clean shot and the
store is still `gr` 0 / `gr_run` 0.

Two practical notes for whoever runs the next multi-hour workflow here. **Disable sleep first**: the
laptop slept mid-run and the resume delivered `[Request interrupted by user]` to the one agent then
in flight rather than resuming it (the retry recovered, but only because that phase tolerates a null
result). And **`journal.jsonl` in the run's transcript directory is a genuine recovery path** — it
carries one `{"type":"result"}` line per completed agent with its full return value, including the
raw rule cards, so a run that never returns is not a lost corpus.

### Step 10 Phase 3, as actually run (2026-09-10)

Nothing was delegated and no skill was invoked. Phase 3 is CLI commands and SQL, and the runbook's
own §11 puts the launch-and-record work in the main session. The four pre-ingest checks were
re-verified first rather than taken from the handoff: `gr` 0, `gr_run` 0, `file_domains` 1,504,
`domains` 12, `user_version` 1, and the eleven GR tables plus `gr_fts` already present from a prior
read-only open (Step 3's create-on-open rule, working as designed).

All commands from `<CLI>` = `tools/legacylift_search`, using the venv exe because the `PATH` shim is
broken:

        .venv/Scripts/legacylift-search.exe requirements ingest \
          --repo-root <CODE> --system customer.ple.nng.app \
          --from <OUT>/knowledge/extracted-rules-4round.json
        .venv/Scripts/legacylift-search.exe requirements stats --repo-root <CODE>

Ingest banner, trimmed — the full reading is in `Outcomes & Retrospective` → *Step 10 Phase 3, as
measured*:

        ingested extracted-rules-4round.json as run RUN-01M2646H97JAZJPPKHSCZT1RRY
          rules: 437 offered = 272 new + 58 merged + 107 candidate; 0 rejected by the panel
          rows inserted: 379          merge candidates raised: 148 [drift=85, range_overlap=63]
          intra-run collapse: 106     citations: 441 seen, 383 inserted
          anchor resolution: file=4, symbol=433, unresolved=4     (pre-dedup; entry 12)
          subject provenance: derived=436, llm_named=1            (pre-dedup; store reads 378/1)
          discriminator tiers: 1=88, 2=349
          coverage: 14925 chunk(s) not accounted for -- run is INCOMPLETE
          derived SQL: 379 refreshed, 287 findings written, 0 forgotten
          vectors: 379 embedded, 0 skipped, 0 deleted             exit 0

The three measurements were taken with read-only SQLite against `<KNOWLEDGE>`, not from the banner,
because reading A of `MEAS-1` is the only one the banner carries and both readings are required. The
two `MEAS-1` queries are the runbook's verbatim. The census that produced the true-same verdict
joined `gr_run_hit.offer_ordinal` back to `confirmedRules[ordinal]` in the corpus JSON and printed
the surviving row's name beside every offered name — **that join is the whole basis of the verdict,
and it works only because the corpus file still exists**, which is the argument for never
overwriting one.

The split population was then measured three ways, each narrowing the last: grouping `gr` rows by
their full citation span-set (38 span-sets carrying 85 rows); grouping by `dedupe_key_anchor_only`
(34 clusters, 54 excess rows, against 379 distinct `dedupe_key` values over 379 rows); and finally
asking whether every internal pair of those 34 clusters appears in `gr_merge_candidate`
(34/34, 0 partial, 0 missed). The tier explanation came from reading `gr_keys.py:13` and
`gr_ingest.py`'s docstring rather than inferring it, then confirming on the four-row
`StatusHistoryService.java:151-167` cluster that one row has no `structured_body` and three do.

Then the export, which was the last unverified item and the only thing here that writes:

        .venv/Scripts/legacylift-search.exe requirements export --repo-root <CODE>
        -> export refused: 1 run(s) ... incomplete or unmeasured -- RUN-...: 14925 chunks
           unaccounted for. Pass --allow-incomplete ...                        exit 1

        .venv/Scripts/legacylift-search.exe requirements export --repo-root <CODE> --allow-incomplete
        -> <OUT>/knowledge/requirements.jsonl   380 lines, 2,498,688 bytes     exit 0

**It was not committed and no `git add -f` was run.** `git check-ignore -v` reports
`.gitignore:108` ignoring the whole `repos/nng-app-legacylift-analysis/` tree, so the export's own
closing advice ("this file is what survives -- commit it") cannot be followed without force-adding
client-derived content into this repository. That is left as the open decision in `Progress`.

**No code changed in Phase 3, so the suite was not re-run.** The baseline stands where the plan puts
it. Phases 4, 5 and 6 are untouched.

### Step 10 Phase 4, as actually run (2026-09-10)

Run in the main session, not delegated — the runbook assigns Phase 4 to a Sonnet 5 subagent, and
that was overridden for one reason worth recording: the acceptance test compares against run 1's
counts, and run 1's counts had just been measured in this session, so handing them to a subagent
would have meant re-deriving the baseline the test is stated against.

A count snapshot was taken **before** the second ingest — this is the whole test, and it cannot be
reconstructed afterwards:

        gr 379 | gr_citation 383 | gr_citation_anchor 811 | gr_scenario 379
        gr_edge_case 794 | gr_finding 287 | gr_merge_candidate 148 | gr_run 1 | gr_run_hit 437

Then the same command as Phase 3, against **the same saved file** — not a second extraction:

        .venv/Scripts/legacylift-search.exe requirements ingest \
          --repo-root <CODE> --system customer.ple.nng.app \
          --from <OUT>/knowledge/extracted-rules-4round.json

        -> ingested ... as run RUN-01M26551VPR5KSVY7BYFNVDBZJ
           rules: 437 offered = 0 new + 437 merged + 0 candidate; 0 rejected
           rows inserted: 0    merge candidates raised: 0 [(none)]
           citations: 441 seen, 0 inserted     merged with no value change: 331
           scenarios rewritten: 106; edge-case sets rewritten: 106        exit 0

All four required counts were flat and `gr_run` gained a row with `rules_merged=437`, so the
assertion set passed at that point. **A third ingest was then run deliberately**
(`RUN-01M2657EP2T11JAQV0EYS9HSKH`), with a full row-level snapshot of six tables either side of it,
because the stated assertions are counts and a count cannot see a silent field rewrite — and the
second ingest's banner had said 106 scenario sets were rewritten while inserting nothing, which is
the shape of a change a count test would miss. The diff was field-by-field over every column of
`gr`, `gr_citation`, `gr_scenario`, `gr_edge_case`, `gr_finding` and `gr_merge_candidate`; the result
and its explanation are in `Outcomes & Retrospective` → *Step 10 Phase 4*.

The last step was to confirm the 48 churning `gr` rows are exactly `MEAS-1`'s reading-B set, by
intersecting the moved-`updated_at` ids against
`SELECT gr_id FROM gr_run_hit WHERE run_id=<run 1> GROUP BY gr_id HAVING COUNT(*)>1`. **Set equality,
not overlap.** That is what turns the churn from an unexplained diff into a described behaviour.

Finally, the export was re-run and compared against the copy taken in Phase 3
(`cp` first — the command overwrites `knowledge/requirements.jsonl` in place, so the earlier file is
gone unless it is saved):

        cp <OUT>/knowledge/requirements.jsonl <scratch>/export1.jsonl
        .venv/Scripts/legacylift-search.exe requirements export --repo-root <CODE> --allow-incomplete
        -> 380 lines, 2,498,820 bytes (was 2,498,688)              exit 0

The comparison was parsed rather than `cmp`-ed, because a byte diff on a 2.5 MB JSONL says only
"differs": each line was loaded as JSON and diffed by field, which is what showed the difference is
confined to `updated_at` on 48 lines plus the header's run list.

**Cost note.** Each re-ingest re-embedded all 379 statements (`vectors: 379 embedded, 0 skipped`),
so the acceptance test is not free against Bedrock even though it changes nothing. Three ingests of
this corpus were run in total. **No code changed, so the suite was not re-run.**

### Step 10 Phase 5, as actually run (2026-09-10)

Run in the main session rather than the runbook's Sonnet 5 subagent. The three traps were the
reason: they are stated in the runbook precisely because each has cost a cycle, and two of the three
turned out not to apply to the route taken — which is a judgment about the runbook, not an execution
detail to hand off.

**Building the `A3` store.** Only `index.sqlite` (226 MB) and `manifest.snapshot.json` were copied,
**not** the whole 318 MB `index/` directory the 2026-09-09 rehearsal copied, because ingest reads
the index solely for anchor resolution. `index: present at <scratch>/a3/...` in the banner confirms
that was enough, and the anchor breakdown came back 4 / 433 / 4 — identical to the real run, which is
the check that proves the index was actually read rather than silently skipped.

`knowledge.sqlite` was copied whole and then emptied of GR rows, keeping `domains` (12) and
`file_domains` (1,504):

        DELETE FROM gr_run_hit, gr_citation_anchor, gr_citation, gr_scenario, gr_edge_case,
                    gr_finding, gr_merge_candidate, gr_dataflow, gr_import, gr_run, gr
        -- child tables first, then VACUUM
        -> gr 0, gr_run 0, gr_citation 0, file_domains 1504, domains 12

Keeping the domain tables is what makes this a valid `MEAS-1` reproduction rather than only an `A3`
fixture: without them every subject would be `llm_named` and the `derived` gate would fail.

**Traps 1 and 2 did not apply, and that is worth recording.** Both concern the `hash` and `qwen3`
providers. The degraded state here was produced with the **real** provider (`api`, Titan
`amazon.titan-embed-text-v2:0`, dim 1024) and its credential removed for one command:

        env -u AWS_BEARER_TOKEN_BEDROCK -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
            -u AWS_SESSION_TOKEN -u AWS_PROFILE \
          .venv/Scripts/legacylift-search.exe requirements ingest \
            --repo-root <CODE> --analysis-dir <scratch>/a3 \
            --system customer.ple.nng.app --from <OUT>/knowledge/extracted-rules-4round.json

That is a truer `A3` than swapping in a local embedder, because the failure it exercises is the one
`PR-47` was written about — a missing API key after hours of extraction — and it sidesteps the
dimension trap entirely rather than having to dodge it. **No manifest was edited and no
`--embedding-provider` flag was passed.** Trap 3 was confirmed rather than avoided: the collection
appeared at `<scratch>/a3/knowledge/chroma`.

**The threshold harness.** `SEMANTIC_TOP_K` and `SEMANTIC_DISTANCE_MAX` are kwargs with no CLI flag,
but re-running ingest at several values would have been both expensive and wrong — stage two only
ever *surfaces* pairs, so the candidate set is a pure function of the neighbour distances. The
harness therefore queries the populated collection once for the ten nearest neighbours of all 379
statements and computes every setting from that one pass:

        PYTHONPATH=$PWD/src .venv/Scripts/python.exe <scratch>/thresholds.py <CODE> <scratch>/a3

using `resolve_requirements_paths` / `build_embedder` / `open_gr_collection` so the harness resolves
paths and providers exactly as the CLI does rather than reimplementing them. Read-only, and against
the A3 copy so the real store's collection was never queried or written. Distances were saved to
`<scratch>/a3/neighbours.json`.

**How the never-ran finding was established** — two independent routes, because a claim that a code
path has never executed is easy to get wrong from reading alone. First the ordering, read at
`gr_ingest.py:1049` (`# The vector half runs AFTER the commit`) with `_stage_two`'s semantic branch
at `gr_ingest.py:1371`. Then the control experiment, which is the stronger half and was free: the
`A3` ingest had **no embedder at all**, so if the semantic half had contributed anything to Phase 3's
148 candidates the two runs would disagree. They agree exactly, `drift` 85 and `range_overlap` 63.
Finally `describe_vector_shortfall(0, 0)` was called directly and returns `None`, which is why no
warning was printed.

**No code changed in Phase 5, so the suite was not re-run.** The A3 scratch store is disposable and
lives only in the session scratchpad; nothing under `analysis/` was modified.

Update this section as work proceeds, recording the exact commands you ran and short transcripts of their output.

### Step 10 Phase 6, as actually run — the second four-round extraction (2026-09-10)

Run in the main session throughout, and the runbook's §11 split was **deliberately overridden for
the recording step**: §11 assigns Phase 7's plan-document updates to an Opus 5 subagent, but every
measurement Phase 6 produced was taken in this session, and handing them to a subagent would have
meant re-deriving the numbers the write-up is stated against. That is the same reason Phases 3, 4
and 5 were each kept in the main session, and it is now the third consecutive phase where the
delegation table lost to that argument. **The launch and the saving of the return value were never
delegable** — §11 already says so.

**`maxRounds` was a budget decision and it was put to the user, not assumed.** Four rounds was
chosen so run 2 is like-for-like with run 1, which is what makes the corpus reusable as Milestone
1.5's missing new-extractor control; a 1- or 2-round run would have yielded `rules_candidate` over a
sample not comparable to run 1's 437.

**The launch copy: all four transforms again required, and asserted against the inserted text.**
Built in the scratchpad from the committed file, which was never edited (`git status` clean
throughout). The build script asserts each transform mechanically:

    (b) ASCII      45 em-dashes replaced, 0 non-ASCII remaining
    (c) args shim  inserted, 5 reads repointed; 0 `args.`/`args &&` reads remain,
                   6 bare `args` accounted for one at a time -- 3 in the shim itself
                   (typeof/JSON.parse/|| {}) and 3 inert (meta prose, a section
                   comment, an error message)
    (d) coverage   pointed at the venv exe; 0 `py -3.12`, 0 bare-PATH invocations
    (a) LF         0 CR bytes, 0 control bytes other than 0x0A (44,715 bytes)

Then `node --check` on the `export`-stripped, wrapped copy. **The launch was approved on the first
attempt.**

**Two of this session's own assertions fired, which is the whole argument for asserting.** Both
were in the bare-`args` census: the count was written as 2, then 3, and the real answer is 4 lines
carrying 6 occurrences — the shim line contains three `args` reads of its own. Nothing reached an
approval dialog wrong, and the enumerating form that replaced the count is stronger than what it
replaced, because a new executable read can no longer hide inside a total. **Write the assertion so
it names what it expects, not how many.**

The launch, from the repository root:

        Workflow({
          scriptPath: "<scratchpad>/extract-rules-ascii-p6.js",
          args: {system: "customer.ple.nng.app",
                 repoRoot: "repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app",
                 maxRounds: 4}
        })

No `modulePattern`, and no `resumeFromRunId` — the same reasoning as run 1, plus the stronger form
here: replaying run 1's agents from cache would have reproduced run 1's corpus, which is the exact
opposite of what a key-instability measurement needs.

**The sleep trap was checked rather than assumed away.** `powercfg /query SCHEME_CURRENT SUB_SLEEP
STANDBYIDLE` reported AC index `0x00000000` (never) and DC `0x0000012c` (5 minutes), and
`Win32_Battery.BatteryStatus` was 2 (on AC), so no power setting was changed. **A machine on battery
here still sleeps after five minutes**, which is the condition that cost run 1 a mid-flight agent.

**Saving the return value, before any gate.** The workflow's return value arrives wrapped —
`{summary, agentCount, logs, result, workflowProgress, totalTokens, totalToolCalls}` — and it is
`result` that carries the eleven corpus keys. That was verified by key-set equality against run 1's
saved corpus rather than by assumption, because `workflowProgress` **is** truncated (its per-agent
summaries carry `…`) and a naive save of the wrapper would have preserved the truncation while
looking complete. The one `…` inside `result` itself was located and read: it is prose inside a
`smeQuestion`, mid-sentence, not a truncation marker.

Three new files, none overwriting anything — the save script refuses an existing path:

        analysis/customer.ple.nng.app/knowledge/extracted-rules-4round-run2.json                 (1,347,567 B)
        analysis/customer.ple.nng.app/knowledge/extracted-rules-4round-run2-runlog.json            (922,036 B)
        analysis/customer.ple.nng.app/knowledge/extracted-rules-4round-run2-journal-backup.jsonl (2,720,420 B)

The saved corpus was asserted to round-trip equal to the returned object, and **all five prior
corpora plus run 1's journal backup were re-hashed against a pre-run SHA-256 snapshot and confirmed
byte-unchanged.** `<OUT>/knowledge/` now holds **six** corpora; the trap is unchanged.

**The store copy, and the one difference from Phase 5's recipe.** Built under the scratchpad and
addressed with `--analysis-dir`:

        <scratch>/p6/index/code-search/index.sqlite            <- copy (227 MB)
        <scratch>/p6/index/code-search/manifest.snapshot.json
        <scratch>/p6/knowledge/knowledge.sqlite                <- copy AS IS, gr tables NOT emptied
        <scratch>/p6/knowledge/chroma/                          <- copied TOO (the load-bearing part)

The runbook's gate was run before ingesting and passed: `requirements stats --analysis-dir
<scratch>/p6` reported `requirements: 379` and **`gr_statements holds 379 of 379`, no shortfall**,
with the index resolved under the copy. Without that the semantic-half observation would have been
void, and it is the one assertion that distinguishes this run from a first ingest.

A pre-ingest baseline was then taken with read-only SQLite, because several of Phase 6's figures are
deltas and cannot be reconstructed afterwards. It reproduced **every** frozen Milestone 1.5 figure
independently — 379 rows, 118 citation paths / 116 resolvable, 383 citations (375 symbol, 4 file, 4
unresolved), 148 candidates with `similarity` NULL on all of them, `first_seen_run_id` uniform, and
the category and rule-class splits. A pre-ingest export was taken from the copy as well (380 lines,
2,498,820 bytes — **identical in size to the real store's**, which is the check that the copy is
faithful rather than merely present).

The commands, all from `<CLI>` = `tools/legacylift_search` with the venv exe:

        # A1 and the body/citation gates, on the saved corpus
        PYTHONPATH=src .venv/Scripts/python.exe <scratch>/a1-gate.py <OUT>/knowledge/extracted-rules-4round-run2.json

        # the ingest -- into the COPY
        .venv/Scripts/legacylift-search.exe requirements ingest \
          --repo-root <CODE> --analysis-dir <scratch>/p6 \
          --system customer.ple.nng.app \
          --from <OUT>/knowledge/extracted-rules-4round-run2.json
        -> ingested ... as run RUN-01M26QXCVQAJ8PK8P9MQNWVWHB                    exit 0

        # the candidate listing, for the softer criterion
        .venv/Scripts/legacylift-search.exe requirements list --candidates \
          --analysis-dir <scratch>/p6 --repo-root <CODE>

        # the export diff (item 4)
        .venv/Scripts/legacylift-search.exe requirements export \
          --repo-root <CODE> --analysis-dir <scratch>/p6 --allow-incomplete

**The A1 harness was validated against the *existing* corpus before the new one arrived**, which is
the cheapest possible way to gate a gate: it reproduced 437/437, 88/88 bodies valid, 441 triples and
`MEAS-2` = 39 exactly. A harness that cannot reproduce a known answer is not evidence about a new
one.

**Reconciling the banner against the store, which is where the two findings came from.** Four
independent readings were taken and made to agree rather than reported separately: `gr_run_hit`
joined to `gr.first_seen_run_id` (435 offers on 368 distinct requirements — 91 pre-existing
absorbing 151 offers, 277 run-2 rows absorbing 284); the `updated_at` fingerprint either side of the
ingest (**moved on exactly those same 91 rows — set equality, not overlap**, the same check Phase 4
used); the per-reason candidate census (which is where the banner's 25-row disagreement surfaced);
and a field-level diff of the two exports, parsed per line rather than `cmp`-ed, because a byte diff
on a 4.5 MB JSONL says only "differs".

**The 25-row disagreement was then settled by probe rather than by arithmetic**, because "the
structural half overwrote the semantic half's row" is a claim about a code path and the arithmetic
alone (39−14 = 25 = 177−152) is consistent with several stories. The probe raises one pair twice
against a throwaway store — `semantic`/0.91 then `range_overlap`/NULL — and shows the row ending as
`range_overlap` with `similarity` NULL, the call returning `False`, and `run_id` correctly keeping
its first-raiser meaning. FK enforcement is disabled for that connection with a comment saying why:
the two `gr_id`s are stand-ins and the probe is about the upsert, not referential integrity.

**Nothing was written to the real store.** Every command above carries `--analysis-dir
<scratch>/p6`, and the real store still reports `gr_run` 3 with `gr` 379. **No code changed in Phase
6**, so the suite was not re-run and the 1,256-test baseline stands where the plan puts it.

## Validation and Acceptance

Phrase every acceptance as observable behavior.

**And phrase it as an observable plus a pointer, never as a restatement of the rule it tests.** Where a criterion depends on a rule this plan states elsewhere — the ownership partition, the transition graph, the dedupe formulas, the notation checks — name the Step that owns it instead of repeating its content here. Every stale-copy defect found in the sixth review round was the same shape and all of them were in this section: a rule was corrected in its owning Step and its copy here was not, so an implementer working from this list would have written a test the plan itself guaranteed would fail. The Steps and the `Decision Log` keep their redundancy deliberately, because a cold-start agent must be able to act on one section without reading the rest; this section is a test list that nobody reads cold, so redundancy buys nothing here and costs a copy to keep in step.

Milestone 0's first half is accepted when `tests/test_migrations.py` passes and, specifically, when a test demonstrates that a database containing rows, stamped at an older version, gains a new column *and still has its rows* after the runner executes. Before the change, adding a column to `knowledge.sqlite` required deleting the file; after it, it does not.

Its second half is accepted when a full `index` run against `repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app` leaves **no `legacylift-docs/` directory anywhere under that checkout** — a filesystem assertion, which is the observable form of "nothing is written inside the client's code" — while the index and knowledge paths the command printed resolve under `analysis/customer.ple.nng.app/` and report the same counts as the transcript taken before the artifacts were moved. **This criterion previously read "leaves `git status` in that checkout clean" and must not be restored to it** (`PR-74`, and again `PR-84`): that checkout is not its own repository, `git rev-parse --show-toplevel` there returns this repository's root, and `.gitignore:92` ignores the whole tree — so the git form reports clean before and after regardless of what the code does. Milestone 0's own section says this; the two disagreed until the fifth review round. `repos/ctcm/ctcm-api`, which has no `legacy/` parent, must still resolve to `legacylift-docs/` and behave exactly as it does today; a test covers both shapes plus the explicit override.

Milestone 1 is accepted when all of the following hold. Running `/modernize-extract-rules` against a legacy repository produces requirements in `knowledge.sqlite` that `requirements list` displays.

**The merge criterion is stated against a fixed input, deliberately.** Ingesting *the same saved extractor-output JSON* a second time leaves the requirement count unchanged **and the citation, scenario and edge-case counts unchanged**, while `gr_run` gains a second row whose `rules_merged` equals the first run's `rules_in`. All four counts are named because a flat requirement count over any growing child table is the same bug one level down, and `gr_scenario` is the largest of them. That is the headline proof and it is a hard pass/fail. Re-running the *extraction* end to end is a second, separate criterion and a softer one, because the extractor is a language model and its output is not reproducible: what must hold there is that the second run's `rules_new` is a small minority and that every rule the first run found arrives as `merged` or as a `candidate` rather than as `new` — a rule recognized only as a candidate is the extractor having flipped `ruleClass` or reshaped its `given`, per Step 6, not a merge failure. Record both numbers. Stating this the other way round — asserting a flat count across two live extractions — would make the milestone's central test fail for a reason that has nothing to do with the store.

Editing a requirement's `statement` by hand and then re-running extraction leaves the edited text intact. `requirements validate` reports findings with stable identifiers, and `requirements set-state <gr_id> --to approved` on a requirement carrying an `ERROR` finding fails with a non-zero exit and a message naming the blocking finding by identifier; the same command succeeds once the finding is resolved, and the record's `state`, `reviewed_by` and `reviewed_at` change while `--note` lands in `review_note`. **No automated producer can move a record out of `draft`** — `set_state` and Step 9's `import_records` are the only writers of the column, and a test asserts that set is complete. `requirements export --format jsonl` produces a file whose second run is byte-identical, so it is genuinely diffable. Re-running `tag-domains` with a changed `domains.json` leaves every `anchor_key`, `content_hash` and `dedupe_key` byte-identical — the domain-retag invariant test, run at unit scale against `tests/fixtures/polyglot_repo/domains.fixture.json` and at least once end to end against a repository whose `file_domains` is actually populated. `requirements stats` reports the SME-field fill rates as progress, reports the data-flow block as having no entries and names both reasons in words rather than printing any rate (per Step 7 — a percentage over an empty table is the defect, not the expected value), reports a non-zero count of `derived` subjects, reports **cumulative distinct-files-cited across all runs**, and satisfies the `gr_run` count identity from Step 3. And the full test suite passes with the new tests included.

Five acceptance criteria come from the 2026-08-25 plan review and are easy to skip because they were not in the original text. **Nothing the extractor produced is dropped**: the completeness test from Step 3 passes, asserting that every key of every ingested rule object is either mapped to a column or child row, or preserved in `extractor_payload` — and specifically that `gr_scenario` holds the Given/When/Then of every rule. **`set-state` refuses to run without a reviewer**, and `gr.reviewed_by` carries that identity afterwards. **`requirements list --candidates` shows the stage-two pairs**, so the under-merge safety net is observable rather than merely counted. **A drifted citation produces a candidate, not a cold miss**: edit a cited line range, re-ingest, and confirm the rule matches on `dedupe_key_anchor_only` and lands in `gr_merge_candidate` with `reason = 'drift'` rather than inserting as new. And **`backfill-hashes` populates `symbols.content_hash` on an existing index** while skipping files whose on-disk `sha256` no longer matches `repo_files`, reporting both counts.

Three more come from the second review. **Citation anchors resolve at ingest**: a citation landing inside an indexed method carries the `anchor_key` of the innermost containing symbol with `anchor_resolution = 'symbol'`, one landing in an unindexed or non-code file carries the file-level anchor with `anchor_resolution = 'file'`, and **no citation anywhere in the store carries an empty `anchor_key`** — assert that as its own test, because the empty string is the value that silently collapses stage-one dedupe. Ingesting against a repository with no index at all is reported loudly, produces a corpus that is entirely `file`, exits zero, **and creates no `index.sqlite`** — assert the absence of that file afterwards, because the lazy-connect behaviour of `SQLiteStore` makes accidentally creating one the default outcome and an empty index database beside an unindexed repository is indistinguishable from a real one on the next command. A citation naming a path that is not in the working tree carries `anchor_resolution = 'unresolved'` together with a NULL `content_hash` and a computed file-level anchor — the one case that value has, so a permanent zero there would mean the label was never wired up rather than that the corpus is clean. **A `draft` row with a NULL `pattern` and `disposition = 'captured'` inserts successfully** and is refused by `set-state --to approved`, proving the CHECK and the ingest defaults no longer contradict each other. **The five slot-dependent checks fire on live text**: edit an approved-shape `statement` with `set-field` so it loses its subject, re-validate, and confirm `V-SLOT-01` fires against the edited wording with a `span` pointing into it — the case a stored-slots design would have missed.

Four more, from items `PR-29` through `PR-35`. **An unmeasured run does not pass the completeness gate**: ingest a run whose `coverage` is `null` — the shape the workflow really produces — and, from a synthetic fixture, one whose `coverage` carries `skipped: true`, which the workflow cannot emit because `extract-rules.js:229` normalizes it to `null` first but which the field map must still handle. Confirm `not_accounted_for` is NULL and `complete` is 0 in both, that `export` refuses both, and that `stats` says *unknown* rather than *complete* — this is the test that would have caught the gate passing on an unmeasured corpus. **The migration runner leaves the connection as it found it**: assert `conn.isolation_level` equals its pre-`migrate()` value afterwards, and assert that on a fresh database of either kind `PRAGMA user_version` equals `max(m.version for m in <that database's list>)` with **no** migration function having executed. **Write the assertion against the computed maximum, never against a literal.** Both lists end at 1 today and `INDEX_MIGRATIONS` ends at 2 the moment Step 2 lands, so a hard-coded `1` is a test that fails inside this same milestone's successor and gets "fixed" by editing the constant — at which point it asserts nothing. The property Milestone 0 actually wants is that the fresh-database stamp works and no column addition is re-applied to a table `migrate()` just created with the column, and that property is version-independent. Same reasoning as deriving `SHADOWED_FIELDS` from `PRAGMA table_info` rather than declaring it: an assertion computed from the thing it describes cannot drift from it. **A `set-field` edit reaches search**: edit a `statement`, then find the record by a word only in the new text via `requirements search`, and confirm it is no longer found by a word only in the old — the assertion that fails if the refresh pair is wired to ingest alone. **The mapping test fails on an unmapped key**: add a key to a fixture rule object that is neither mapped nor in `UNMAPPED_KEYS` and confirm the completeness test fails, which is the only way to know that test is not vacuous.

One more, from `PR-47`. **Ingest with no embedder available still stores every rule.** Run `requirements ingest` with the embedding provider unreachable or unconfigured; confirm the requirement count is what the input JSON offered, that the command says the semantic half is unpopulated and names `reindex-vectors`, that it **exits zero**, and that a subsequent `reindex-vectors` populates the collection so stage two starts working — with no re-extraction anywhere in that sequence. Then confirm stage two reports the shortfall rather than returning zero candidates while the collection is behind.

One more, from `PR-45`. **Every human-written field survives re-extraction, not just `statement`.** Set all **nine** human-writable fields with `set-field` — `HUMAN_WRITABLE_FIELDS` in full, `owner` included, since it had no writer at all until `PR-81` — re-ingest the same JSON, and confirm each one is unchanged: the three shadowed fields keep the human value while their `_extracted` shadows take the incoming one, and `disposition`, `modality_confirmed`, `confidence_intent`, `rationale`, `fit_criterion`, `enforcement_level`, `rule_class` and `pattern` are untouched. Note that the last two are untouched **by construction rather than by protection** — both feed both dedupe keys, so an exact-key hit implies the incoming values already agree and an anchor-only hit inserts rather than updates (Step 6) — so do not assert them the way the other seven are asserted; a test that passes only because the merge protected them is testing the wrong mechanism. The structural assertion that belongs with this criterion is the **four**-way partition, stated once in the fifth round's group below. Do not restate it here.

One more, from `PR-44`. **A citation spanning several symbols resolves to one primary anchor and records all of them.** Ingest a citation whose line range covers three sibling declarations; confirm `gr_citation.anchor_key` holds exactly the smallest-span intersector under the stated tie-break, that `gr_citation_anchor` holds three rows with the right `containment` values, and — the assertion that matters — that adding a fourth unrelated declaration inside that range and re-ingesting leaves `dedupe_key` and `dedupe_key_anchor_only` byte-identical. That last part is what proves the child table stayed out of the keys, and it fails loudly the moment someone "improves" the key to hash the full set.

Three more, from the fourth review. **`index --reset` still works after the relocation**: it succeeds against the relocated NNG unit and against `repos/ctcm/ctcm-api` on the fallback path, and is refused for an `--analysis-dir` override naming a directory that is neither an index directory nor empty. These are the first tests this guard has ever had, which is why the regression would otherwise have shipped invisibly. **`not_accounted_for` survives a corpus with more than forty unaccounted chunks**: ingest a run whose coverage payload carries `uncovered: 512` alongside a forty-entry `uncovered_chunks`, confirm `gr_run.not_accounted_for` is 512 and not 40, and confirm ingest renders the list as *40 of 512 shown* — the assertion that fails the moment anyone derives the count from the list's length. **A rule the extractor left `pattern` NULL still gets a statement**: ingest a rule that carries an empty `statement` and a NULL `pattern`, confirm `statement` and `statement_extracted` are both non-empty and carry the pattern-free fallback wording, confirm `pattern` is still NULL and both dedupe keys are unchanged by the fallback, and confirm the record is findable through `requirements search` — because a NULL statement silently empties the FTS5 row and the embedding, and the shadow equality in Step 6 then reads the row as human-edited forever.

Six more, from the fourth review's second group. **A partially-hashable citation set keys deterministically**: ingest a rule with two citations of which one names an unreadable range, and confirm its `dedupe_key` matches the key computed from the same inputs with the missing hash spelled `ch0:none` — then confirm that a rule whose citations are *all* unreadable does **not** produce the same key as a rule with no citations at all, which is the tier-2-versus-tier-3 collapse the sentinel exists to prevent. **The transition graph is enforced and enumerable**: every move in `ALLOWED_TRANSITIONS` succeeds from a fixture in the right starting state, every move outside it is refused with a message naming both states, `draft → approved` succeeds directly on a clean record, and a move to the state a record already holds changes neither `reviewed_at`, `review_note` nor `updated_at`. **A not-evaluated check is stored and does not block**: ingest a rule with a NULL `pattern`, confirm the three `V-SLOT` findings exist with `evaluated = 0` and their would-be severity intact, confirm `severity` still takes only two distinct values across the whole table, and confirm `stats` reports the not-evaluated count as its own figure rather than folding it into the `ERROR` count. **Field ownership is an exhaustive partition** — see the **four**-way form in the fifth round's group below, which is the only statement of this criterion. `PR-81` replaced the three-set version originally written here, which fails on day one because fourteen columns belong to the store rather than to either party. Do not write a test from this line. **`owner` round-trips**: `set-field --field owner` writes it, re-ingesting the same JSON leaves it untouched, and it appears in `show`. **`gr_fts` forgets old text**: edit a `statement` with `set-field` and confirm the record is findable by a word only in the new text and **not** by a word only in the old, which is the assertion that fails if the delete half of the delete-then-insert is missing — the specific way a standalone FTS5 table goes wrong.

Four more, from the fourth review's third group. **Identifiers are well-formed and ordered**: a generated `gr_id` is 29 characters beginning `GR-`, every character after the prefix is in the Crockford alphabet, two generated in sequence sort in generation order, ten thousand in a loop are all distinct, and a `run_id` carries the `RUN-` prefix instead. **The export is tracked while the database is not** — run this on `repos/ctcm/ctcm-api`, not on the NNG unit: after `requirements export`, `git status` shows `legacylift-docs/knowledge/requirements.jsonl` as untracked or modified and does **not** show `knowledge.sqlite`. That is the D2 arrangement itself, and byte-identity does not test it. **`rederive-subjects` moves subjects without moving keys**: ingest against a repository with domains, change `domains.json` so a cited file's domain differs, re-run `tag-domains` and then `rederive-subjects`, and confirm the affected `subject` values changed, that **every** `statement` is byte-identical before and after — edited or not, because per Step 8 the command does not touch that column at all — that `llm_named → derived` transitions are reported, and — the assertion that matters — that every `dedupe_key`, `dedupe_key_anchor_only` and citation `anchor_key` is byte-identical before and after. **`retire-run` and `set-run-coverage` are distinguishable after the fact**: retire a run and confirm `gate_excluded_reason` is populated while `complete` is untouched, then re-measure a different run and confirm `coverage_source` reads `remeasured` with `coverage_measured_at` set — so the audit question "why did this stop blocking?" has one answer per run.

Milestone 0's acceptance gains one criterion from `PR-30`: a test that a multi-row write still rolls back as a unit after the migration runner has executed on that connection. That is the regression the scoped `isolation_level` exists to prevent, and it is invisible to every other test in the suite.

Seven more come from the fifth review round. **The extractor emits SPEC-1 notation, and the store keeps it verbatim**: run `/modernize-extract-rules` against a repository and confirm every confirmed rule carries a non-empty `statement`, a `ruleClass` in the two-value set, and a `pattern` that is either NULL or one of §S1.4's ten; then confirm `gr.statement` equals the emitted text byte-for-byte, that ingest performed no templating, and that `gr_scenario` still holds the Given/When/Then of every rule. Confirm separately that a rule arriving with an empty `statement` gets the pattern-free fallback with `pattern` still NULL and both dedupe keys unaffected. **`V-STY-03` fires on items 2/3/5 and not on 1/4/6**: a statement containing a token matching a `symbols.name` from its own cited file produces a `V-STY-03` WARN with a span pointing at that token; a conformant `D-INFER` carrying a literal `[Value]` — §S1.10 #3's *category 87* — produces **no** `V-STY-03`, which is the carve-out amendment A1 added; and the validator still emits exactly twenty-eight distinct identifiers with `severity` taking exactly two values. **Field ownership is a four-way exhaustive partition**: assert the four constants are pairwise disjoint and that their union equals `gr`'s column list read from `PRAGMA table_info`, that `SHADOWED_FIELDS` is derived from the schema rather than declared, and that adding a column to the table in a fixture fails the test until it is classified. **`rule_class`, `pattern` and `owner` round-trip through `set-field`**: each writes, each survives re-ingesting the same JSON untouched, each appears in `show` — and writing `rule_class` or `pattern` leaves both dedupe keys **byte-identical**, which is the assertion that fails if someone wires key recomputation to `set-field`. **A rule the extractor left undecided can be approved by a human**: ingest a rule with NULL `rule_class` and NULL `pattern`, confirm `set-state --to approved` refuses it naming `V-CLASS-01`, set both with `set-field`, re-validate, and confirm approval now succeeds — the end-to-end proof that the un-approvable dead-end is closed. **The file-level anchor is index-independent**: compute the anchor for a citation naming an unparsed file type, then build an index over that repository and compute it again, and confirm it is byte-identical — the assertion that fails the moment anyone resolves `language` from `repo_files` or `detect_language`. Confirm in the same test that a citation naming a path absent from the tree carries `anchor_resolution = 'unresolved'` with a computed, non-empty anchor. **`entity_class` is declared everywhere it must be**: assert that every value in every profile's `definition_node_kinds`, read from `extractors.json` at test time, has an explicit class declared; add a node kind to a fixture profile and confirm the test fails until it is classified; and confirm `symbols.entity_class` is non-NULL for every row after an index run, including rows from the XML extractor and from the regex fallback.

Four more come from the seventh review round, all of them writer-reachability or metadata-freshness observables. **Every non-store column has a writer**, asserted over the constants Step 6a declares rather than over a prose description of what ingest does. Assert that `set().union(*EXTRACTOR_FIELD_MAP.values())` equals `EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS` — the union over the tuples, per Step 6a, since the three shadowed keys each write two columns and a `dict[str, str]` makes this assertion unsatisfiable; that `INSERT_ONLY_DEFAULTS` is a subset of `HUMAN_WRITABLE_FIELDS`; that `HUMAN_WRITABLE_FIELDS ∪ SHADOWED_FIELDS` is exactly the set `set-field` accepts; and then the reachability property those three exist to establish — **every column in `EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS ∪ HUMAN_WRITABLE_FIELDS` is written by at least one of the extractor field map, the insert-only defaults, `set-field` or `set_state`**, so a column that is classified but that nothing can write fails the test. Add the meta-test that proves the first assertion is testing the map rather than everything ingest touches: adding `disposition` to `EXTRACTOR_FIELD_MAP` must fail it. This is a different assertion from the four-way partition, which tests membership rather than reachability, and both are required. **`implementation_notes` round-trips**: ingest a rule carrying `implementationNotes`, confirm the column holds it verbatim, confirm `set-field` refuses the field by membership, and confirm re-ingesting the same JSON leaves it unchanged. **A state change reaches the vector metadata**: approve a requirement with `set-state`, then run `requirements search --semantic` filtered to `approved` and confirm the record is returned — and confirm a same-state no-op re-embeds nothing (Step 8). This is the assertion that fails if `set_state` is left off the refresh pair's caller list. **An unedited rule with no assumptions is not read as human-edited**: ingest a rule whose `assumptions` is absent, re-ingest the same JSON with a changed `assumptions`, and confirm the live column takes the new value — which fails if the shadow equality was written as `=` rather than `IS` (Step 6).

Seven more come from the eighth review round, which asked what an agent would be *unable to build* rather than what was inconsistent. **The slot split handles all ten patterns, including the three whose condition trails the keyword**: `split_slots` returns a `[Condition]` span for a conformant `B-RESTRICT` and `D-RESTRICT` (`... only if ...`) and `D-INFER` (`... if ...`), a `[Subject]` span for all ten, and `action` populated on exactly the **seven** Figure-1 patterns with `value` populated on the other three and never both (seven plus three is ten; "six" here was the last stale copy of the arithmetic this plan already corrects twice above, and a test written from it would have failed). Drive the test from SPEC-1 §S1.10's worked examples: **every statement §S1.10 marks ✅ produces zero `ERROR` findings**, and #3 in particular — the `D-INFER` carrying `and` in its `[Value]` and a trailing condition — produces no `V-SING-01` and no `V-SLOT-03`. That single assertion is the one that fails under the superseded two-part split. **A discontinuous keyword counts once**: *A branch manager may grant a spot discount only if the rental is open* passes `V-KW-04`, is not routed to `V-KW-06` as advice, and splits with `[Action]` between `may` and `only`. **`entity_class` is declared for every closed-half entry**: assert that every key of every profile's `definition_node_kinds` maps to one of the seven values with **no entry falling to `other` by omission**, and specifically that `enum_declaration` and `field_declaration` differ, and that `property_declaration` and `method_declaration` differ — the two collisions the Decision Log cites as the reason the column is a key input, which a blanket `other` default re-collapses. **The child sets do not double on a merge**: re-ingest the same JSON and confirm `gr_scenario` and `gr_edge_case` counts are unchanged, that a row inserted with `provenance = 'human'` survives the merge untouched, and that a scenario absent from the second input has actually disappeared. **Ingest against an unindexed repository creates no index**: run `requirements ingest` where `index.sqlite` does not exist, confirm the loud banner names the resolved index path, every citation carries `anchor_resolution = 'file'`, the exit code is zero, and **no `index.sqlite` was created** — the assertion that fails if anyone drops the `Path.exists()` guard or makes `resolve_anchor`'s store non-optional. **A structured body round-trips and a ragged one is refused**: ingest a `decision_table` whose `inputEntries` length matches `inputs`, confirm it stores and that `len(rules)` is what `stats` reports as the table's rule count; then ingest one with a short `inputEntries` and confirm the ingest transaction fails naming the rule by `offer_ordinal`. **The ownership assertion is computed, not literal**: assert `set().union(*EXTRACTOR_FIELD_MAP.values()) == EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS`, and confirm the test fails if `disposition` is added to `EXTRACTOR_FIELD_MAP` — proving it is testing the field map rather than everything ingest happens to write.

Six more come from the ninth review round, which re-ran the eighth's "could an agent build this" question over the steps the eighth round did not reach. **The review act is fully recorded**: `set-state --to approved --reviewer X --note "…"` leaves `reviewed_by`, `reviewed_at` and `review_note` all populated on the row; a second `set-state` to the same state changes none of the three; and `set-field` refuses all three by membership in `STORE_OWNED_FIELDS`. **The ownership assertion is satisfiable**: `set().union(*EXTRACTOR_FIELD_MAP.values())` equals `EXTRACTOR_OWNED_FIELDS ∪ SHADOWED_FIELDS`, all seventeen columns, which requires the map's values to be tuples — assert the three shadowed keys each carry a two-element tuple, since a `dict[str, str]` makes this criterion unpassable and the tempting repair is to drop the shadows from the right-hand side. **The subject fallback is populated, not merely available**: ingest against a repository whose `file_domains` leaves a cited file `unassigned`, and confirm `subject` carries the `[Subject]` span of that rule's own `statement` with `subject_provenance = 'llm_named'`; then ingest a rule whose `pattern` is NULL and confirm `subject` is NULL with the provenance still recorded, and that `stats` counts those NULLs separately rather than inside `llm_named`. **`V-STY-03` works with and without an index**: with a `leaked_terms` set built from the cited files it fires on a token matching a `symbols.name` and reports a span into it; with `leaked_terms` empty it still fires on a `snake_case` token through the morphological fallback, and `stats` says the symbol half was unavailable. **A statement that does not match its own `pattern` produces one finding, not four**: validate §S1.10 #5 (`shall`, no keyword) and #6 (`always must`) with a non-NULL `pattern` set, and confirm the `V-KW` `ERROR` fires while all three `V-SLOT` findings carry `evaluated = 0` — the assertion that fails if `split_slots` guesses a boundary rather than degrading. **`--allow-incomplete` is deterministic**: export an incomplete corpus twice with the flag and confirm the two files are byte-identical and both open with an `_incomplete` object naming the offending `run_id`s and their reason in words; export the same store without the flag and confirm it is refused; and confirm `import` round-trips a file carrying that first line without creating a requirement from it.

Two more close the ninth round's open decisions. **Neither reserved domain becomes a subject**: tag one cited file `excluded` and another `unassigned`, ingest, and confirm no `gr.subject` anywhere holds the literal string `excluded` or `unassigned`; confirm a requirement whose citations are all `excluded` carries `subject_provenance = 'derived_ambiguous'` while one whose citations are all `unassigned` carries `llm_named` — the assertion that fails if the two sentinels are collapsed; confirm a requirement with one `excluded` citation and two in a real domain still derives from that domain, proving the sentinel left the denominator and not just the candidate set; and confirm `stats` reports the all-excluded count as its own figure. **A merge candidate pair is raised once**: surface the same pair on two consecutive runs and confirm `gr_merge_candidate` holds one row, that `list --candidates` shows it once, and — the assertion that matters — that marking it `distinct` and then running a third time leaves the resolution intact rather than re-raising it, which is what fails if `run_id` is inside the uniqueness tuple.

For each new test, state in its docstring what it proves and note that it fails before the change and passes after.

## Idempotence and Recovery

Every step in this plan is designed to be safely repeatable. `migrate()` uses `CREATE TABLE IF NOT EXISTS` throughout, and the migration runner is version-guarded, so running either twice is a no-op. Each migration function checks `PRAGMA table_info` before adding a column, so a partially applied state can be re-run. Ingest is a merge keyed on `dedupe_key`, so re-ingesting the same extractor output changes nothing — literally nothing, including the timestamps, because Step 6 requires a value-changing write before `updated_at` moves.

The one genuinely destructive operation in this repository is `index --reset`, which deletes `index.sqlite`. It does **not** delete `knowledge.sqlite`, which is exactly why the GR tables live there. Even so, before any experiment that might corrupt requirements, copy the file:

        .venv/Scripts/python.exe -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(\"VACUUM INTO ?\", (sys.argv[2],)); c.close()" <app>/analysis/<system>/knowledge/knowledge.sqlite <somewhere-outside-the-tree>/knowledge-backup.sqlite

**Use `VACUUM INTO`, not `cp`.** Both databases run in write-ahead-logging mode (`PRAGMA journal_mode=WAL`, set at the top of each `migrate()`), which means committed transactions can be sitting in the `-wal` sibling rather than in the main file — the NNG knowledge store on disk carries live `knowledge.sqlite-wal` and `-shm` files right now. So copying only the file the plan names silently drops whatever has not been checkpointed, which for the one database this plan calls irreplaceable is the wrong failure to leave lying around. `VACUUM INTO` writes a single consistent, fully-checkpointed database, needs no writer to stand down, and leaves you one file to keep track of instead of three. It requires SQLite 3.27 or later; the interpreter in this virtual environment reports **3.45.3** (Python 3.12.9), so it is available. **Corrected 2026-09-01, and the correction is the useful part: 3.50.4 is what the `python` on `PATH` reports (Python 3.14.3), not the virtual environment's interpreter** — the two disagree, and this plan requires the venv's. Measure with `.venv/Scripts/python.exe -c "import sqlite3; print(sqlite3.sqlite_version)"` rather than with whatever `python` resolves to. The version floor matters twice now: `VACUUM INTO` needs 3.27, and Step 3's `gr_run.complete` generated column needs 3.31.

Copying all three files together is also correct if nothing is writing, and is fine if you prefer it — but it is the option that fails silently when someone copies just the one, which is the mistake being corrected. Milestone 0's relocation is unaffected either way, because moving the containing directory carries the siblings with it; this rule is only about ad-hoc backups.

Note that `knowledge.sqlite` is gitignored, so a copy inside the repository is not protected by git. The committed JSONL export from Step 9 is the durable backup once that step exists; until then, copy the file.

If a migration fails halfway, `PRAGMA user_version` remains at the last successfully applied version and the failed migration's transaction is rolled back, so fixing the migration function and re-running the runner resumes correctly.

A failed `requirements ingest` is simpler still: the whole SQLite half is one transaction (Step 6), so a failure leaves no `gr` rows, no citations and **no `gr_run` row** — fix the offending rule, which the error names by its `offer_ordinal`, and run the same command again. There is no partial state to clean up and no resume flag to pass. Only the embedding phase can be left behind, and `requirements reindex-vectors` is its recovery.

Leave no stray databases or fixtures behind. Tests must use temporary directories.

## Artifacts and Notes

Record here the transcripts that prove each acceptance criterion, kept short. The two most valuable to capture are the before-and-after `requirements stats` output across two identical ingests (proving the merge) and the domain-retag invariant test output (proving that no key takes a domain as input).

Two environment notes carried from prior work in this repository, both of which will cost you time if you rediscover them. The `legacylift-search` on the system `PATH` is a broken shim; use the virtual environment's binary. And the second one has been **inverted by Milestone 0 and must be re-learned rather than remembered**: it used to be that clearing the analysis directory did not clear domain tagging, because `knowledge.sqlite` sat under the code checkout. After the relocation it sits in `analysis/<system>/knowledge/`, so clearing that directory destroys domain tagging and every approved requirement. `index --reset` is still safe, because it removes only the index subtree. Anyone carrying the old note forward will delete the store and expect it to survive.

## Interfaces and Dependencies

In `src/legacylift_search/identity.py` — **built in Step 1 and shipped; this is the signature contract to hold, not work outstanding** — these five:

        def normalize_path(path: str) -> str: ...
        def anchor_key(language: str, entity_class: str, qualified_name: str, relative_path: str) -> str: ...
        def file_anchor_key(relative_path: str) -> str: ...
        def content_hash(body_text: str) -> str: ...
        def new_ulid(prefix: str) -> str: ...

`new_ulid` mints `gr_id` (prefix `GR-`) and `gr_run.run_id` (prefix `RUN-`); Step 3 states the algorithm it already implements — 48-bit millisecond timestamp, ten random bytes, 26 characters of Crockford base32 — and states why no dependency is added for it.

**There is deliberately no `entity_class_of(kind)`.** `entity_class` is declared by each extractor and stored on `symbols` (`NORMATIVE SPEC-3` §S3.1.2, Step 2). The only surviving mapping is a private compatibility shim inside Step 2's backfill migration, defaulting to `other`, which is deletable once every index has been rebuilt. `file_anchor_key` takes no `language` argument on purpose — §S3.1.1 fixes it at the empty string, and a signature that accepted one would invite a lookup that makes a dedupe-key input depend on whether the repository has been indexed.

In `src/legacylift_search/migrations.py`, define a migration record type with `version: int`, `description: str`, and `apply: Callable[[sqlite3.Connection], None]`, plus:

        INDEX_MIGRATIONS: list[Migration]
        KNOWLEDGE_MIGRATIONS: list[Migration]
        def run_migrations(conn: sqlite3.Connection, migrations: Sequence[Migration]) -> list[int]: ...

As built it returns the versions actually applied, in order — an empty list when nothing was
pending — rather than the single `int` this line first declared. Strictly more informative, and
no caller uses the return value either way. The lists are tuples, so the parameter is a
`Sequence`.

**The runner's *trigger* is not symmetric between the two databases, and finding `CR-01` is open
against that.** `KnowledgeStore.__init__` calls `run_migrations` on every open, so `knowledge.sqlite`
migrates whenever anything touches it. `index.sqlite` migrates only from `SQLiteStore.migrate()`,
which only `index` and `backfill-vectors` call — so no read command advances it. Whoever fixes
`CR-01` changes this contract, and Step 2 is the first caller that depends on the answer.

Also in the identity/citation layer, define the anchor resolution Step 6a specifies, plus the strict-mode citation parser promoted out of `cli.py:1532`:

        def parse_citation(raw: str, strict: bool = False) -> list[tuple[str, int, int]]: ...
        def resolve_anchor(store: SQLiteStore | None, repo_root: Path, relative_path: str, start_line: int, end_line: int) -> AnchorResolution: ...

`store` is **optional and `None` means there is no index**, which is a supported ingest and an acceptance criterion, not an error path: every citation then takes the file-level floor with `anchor_resolution = 'file'`. Its caller reaches that state by checking `index_sqlite_path.exists()` with a plain `Path.exists()` *before* constructing the store — the same rule this plan already states for `KnowledgeStore`, and for the same reason, since `SQLiteStore._connect` creates the database file on its first query (`store.py:166-171`). A non-optional parameter here forces the caller to construct a store against a missing path, which silently materializes an empty `index.sqlite` beside a repository that has never been indexed and then fails on `no such table: symbols`.

`repo_root` is not optional and is not decoration. Two of the rules in Step 6a are filesystem questions — the staleness guard, which compares the file's on-disk `sha256` against the stored `repo_files.sha256`, and the absent-path test that produces `unresolved` — and `SQLiteStore` holds only a path to the database (`store.py:157`), so without a root the function cannot read the file it has to hash and both rules quietly become no-ops. A dropped staleness guard is the failure it was written to prevent: a confidently wrong symbol anchor taken from a stale index, feeding both dedupe keys. Ingest already has the root, since `--repo-root` is required there for exactly these reads, so this is a parameter to thread rather than a capability to acquire.

`resolve_anchor` returns an `AnchorResolution` carrying three things: `primary: str`, the single anchor that lands in `gr_citation.anchor_key` and is the only key input; `all: list[AnchorHit]`, one entry per containing or intersecting symbol with its `anchor_key` and `containment`, which becomes the `gr_citation_anchor` rows; and `resolution: str`, the `anchor_resolution` value (`symbol`, `file`, `unresolved`) that produced the primary. `primary` is never the empty string — the file-level fallback is the floor — and when it is a file-level anchor, `all` holds that one entry. `unresolved` does not mean an absent anchor: it is the file-level anchor of a path that is not in the working tree, labelled so (Step 6a).

What keeps FTS5, the vector collection and the findings in step with the `gr` rows — Step 5's answer to the six-writer desync — is a **pair** of functions, each taking a **list** rather than a single id:

        def refresh_gr_derived_sql(store: KnowledgeStore, gr_ids: list[str],
                                   index_store: SQLiteStore | None = None,
                                   repo_root: Path | None = None) -> RefreshResult: ...
        def refresh_gr_vectors(store: KnowledgeStore, gr_ids: list[str],
                               embedder: Embedder | None = None,
                               base_dir: Path | None = None,
                               collection: ChromaVectorStore | None = None) -> EmbedResult: ...

**As built (Step 5), `refresh_gr_vectors` carries three optional parameters this line first
omitted, and the first of them is load-bearing rather than convenience.** The vector half needs an
embedder and this signature could not reach one; `embedder=None` is a **supported degraded
success** meaning none is available, under which the rules stay stored, `gr_fts` stays current and
`EmbedResult.reason` names `requirements reindex-vectors`. Making it required would have made an
unreachable provider a reason a human's recorded judgement fails. `base_dir` overrides where the
collection lives and defaults to `store.sqlite_path.parent`, which *is* the resolved knowledge
directory — so no caller has to re-derive the one placement rule this step exists to protect.
`collection` lets ingest open one collection for a whole run instead of one per call; when it is
omitted the function opens and closes its own, which matters on Windows. `refresh_gr_derived_sql`'s
`repo_root` is threaded and read by no Step 5 code path — its two consumers (the citation staleness
guard and the span-level `content_hash`) both live in `resolve_anchor`, at ingest.

Ingest calls each once for the whole run; `set-field` and `set_state` call each with one element. **All six writers call the pair** — ingest, the merge, `set-field`, `set_state`, `import_records` and `rederive-subjects` — and `set_state` is in that set because `state` is `gr_statements` metadata even though it changes no text (Step 5). Per-record would mean several hundred separate validator runs and several hundred single-item embed calls on a real ingest, which pulls directly against the batched, resumable embedding phase Step 5 specifies.

**It is a pair rather than one function because the two halves have different transactional natures, and no single synchronous call can straddle its own caller's commit.** `refresh_gr_derived_sql` — rewriting the FTS5 row, and the delete-then-insert of that requirement's `gr_finding` rows — runs *inside whatever transaction the caller already has open*, which for ingest is the single transaction covering the run (Step 6). Use a `SAVEPOINT` rather than `BEGIN`: a nested `BEGIN` either fails or commits the outer transaction early, and the second of those is silent. `refresh_gr_vectors` runs **after the caller commits**, batched, and is the half permitted to degrade. Call them in that order at every call site: the ordering is the whole point, and a single function is what hid it.

Two tidier-looking shapes were rejected and are worth naming. **A single function returning a deferred handle** for the caller to fire after committing puts the embedding behind a return value that Python makes trivial to drop, and a dropped handle silently skips embedding — which is precisely the degradation-that-does-not-announce-itself that Step 5's shortfall check exists to catch. **A single function owning its own transaction**, called outside ingest's, would put the validator run and the FTS write outside the run's transaction, so a rolled-back ingest leaves `gr_finding` rows and FTS entries for rules that never landed: the mirror, one database over, of the orphan-vector bug described next.

That ordering is not a preference. Embedding after the commit means a rolled-back ingest cannot leave vectors behind for rules that never landed — and this repository has already been bitten once by exactly this class of bug, where a snapshot taken on the wrong side of a vector write produced orphaned Chroma entries that no SQLite row explained. Write the order down so it is not reversed for tidiness.

In `src/legacylift_search/gr_validator.py`, define:

        def validate_statement(gr: GRRecord, leaked_terms: frozenset[str] = frozenset()) -> list[Finding]: ...
        def can_approve(findings: list[Finding]) -> bool: ...

`leaked_terms` is the set of `symbols.name` and `qualified_name` values for the requirement's cited files, and it is a **parameter rather than a store handle on purpose** (Step 4): `symbols` lives in the other database, and giving the validator a `SQLiteStore` would make every `V-*` test need an index fixture to exercise a function that is otherwise pure. Empty is a supported value meaning "no index was available", under which `V-STY-03` runs on its morphological fallback alone and `stats` says so. `refresh_gr_derived_sql` is the only caller that re-runs the validator, which is why it and not `validate_statement` carries the optional `SQLiteStore` and `repo_root` — both `None` where there is no index, exactly as `resolve_anchor`'s store is.

plus the template-driven slot split the five slot-dependent checks share, returning character offsets into `statement` so `gr_finding.span` falls out of it:

        def split_slots(statement: str, rule_class: str | None, pattern: str | None) -> StatementSpans: ...

        class StatementSpans:
            subject:   tuple[int, int]
            keyword:   tuple[int, int] | tuple[tuple[int, int], tuple[int, int]]
            condition: tuple[int, int] | None
            action:    tuple[int, int] | None   # the SEVEN Figure-1 patterns only
            value:     tuple[int, int] | None   # D-COMPUTE, D-CONST, D-INFER only

**The name changed from `split_on_keyword` and so did the shape, and both changes are load-bearing** (Step 4). The keyword is not always a single span — the four restricted keywords are discontinuous, so `keyword` carries a pair for them — and `action` and `value` are mutually exclusive rather than two names for one region, because §S1.4 says `D-COMPUTE`, `D-CONST` and `D-INFER` do not follow Figure 1's slot structure. A checker that reads `action` on one of those three gets `None` and must not fire, which is §S1.12 amendment A3. `condition` is populated for the trailing `only if` / ` if ` forms as well as the leading comma form; a splitter that looks for it only before the keyword fires `V-SLOT-03` as an `ERROR` on every conformant `B-RESTRICT`, `D-RESTRICT` and `D-INFER`. **A non-NULL `pattern` whose keyword is absent from `statement` returns the same shape as a NULL `pattern`** — `condition` structural, `subject`/`action`/`value` all `None` — per Step 4; that is the shape §S1.10 #5 and #6 produce, and a splitter that raises or guesses on it turns a single `V-KW` `ERROR` into four.

The state transition is one function, and no *producer* may write `gr.state` by any other route — not the CLI, not the extractor wiring, not any future producer — so the Step 4 gate cannot be routed around:

        def set_state(store: KnowledgeStore, gr_id: str, to_state: str, reviewer: str, note: str | None = None,
                      *, superseded_by: str | None = None, embedder: Embedder | None = None,
                      index_store: SQLiteStore | None = None, repo_root: Path | None = None) -> None: ...

`reviewer` is **required and positional-ish on purpose** — no default, so no caller can omit it by accident. It lands in `gr.reviewed_by`. The four keyword-only parameters after it all default to `None` and none of them may become required: `superseded_by` is checked only for the one transition that needs it, and `embedder`/`index_store`/`repo_root` are passed straight through to the refresh pair, where `None` means "degraded, and it says so" rather than "error". A `set_state` that could fail because an embedding provider was unreachable would put the least reliable thing in the pipeline in front of the one act this whole lifecycle exists to record.

`import_records` from Step 9 is the single declared exception, for the reasons given there. These two functions are the complete set of writers of `gr.state`; nothing else may touch the column, and a test asserts it.

        def import_records(store: KnowledgeStore, jsonl_path: Path, allow_downgrade: bool = False) -> ImportResult: ...

In `src/legacylift_search/vector_store.py`, add a text-shaped writer beside the existing chunk-shaped one, and rename the constructor's first parameter now that two callers pass two different roots (Milestone 0):

        def upsert_texts(self, ids: list[str], texts: list[str], embeddings: list[list[float]], metadatas: list[dict[str, str]]) -> None: ...
        def count(self) -> int: ...
        def delete_ids(self, ids: list[str]) -> None: ...

`count()` is what the shortfall check compares against `KnowledgeStore.count_gr()`; there was no
count wrapper before Step 5. `delete_ids` is `delete_chunks` under a name that is not chunk-shaped
— `delete_chunks` now delegates to it, so existing callers are untouched — and it is how a
requirement deleted from `gr` loses its vector rather than leaving a record no row explains. The
rename of the constructor's first parameter touched **sixteen** call sites, not the five the
Step 5 orientation block counted: eleven of them are in tests, and all sixteen pass it by keyword.

In `src/legacylift_search/gr_body_schemas.py`, define one schema per `structured_body_type` (`decision_table`, `state_transition`, `formula`, `invariant`) plus the single entry point the ingest path calls to validate a body against the schema its type selects. **Step 3 gives the four payload shapes in full** — take them from there rather than designing them, since the extractor prompt in Step 6a asks for the same shapes and the two must agree exactly.

`GRRunHit` carries `hit_id` and `offer_ordinal` as well as the three columns the prose first named; see Step 3 for why a natural key there would break the run-count identity.

Add `GRRecord`, `GRCitation`, `GRCitationAnchor`, `AnchorHit`, `AnchorResolution`, `GRScenario`, `GREdgeCase`, `GRMergeCandidate`, `GRRunHit`, `Finding`, `DataflowEntry` and `GRRun` to `src/legacylift_search/models.py` as Pydantic models, following the existing style there. Step 2 also needs `anchor_key`, `entity_class` and `content_hash` added to the **existing** `Symbol` model in that file — the three columns cannot be populated on insert if the model carrying symbols into `upsert_symbols` has no field for them, and that is easy to miss while reading a list of new types. `entity_class` in particular is required rather than optional, because every extractor must declare it and a default would silently reintroduce the guessing this design removes.

Step 2 also touches `src/legacylift_search/profiles/extractors.json`, which is a **data file with a `schema_version`**: `definition_node_kinds` changes from `list[str]` to `dict[str, str]`, mapping each kind to its `entity_class`, so bump `schema_version` from 1 to 2 and change `ProfileEntry.definition_node_kinds`' annotation in `extractors.py:119`. The rest is nearly free — `set()`, `len()` and `in` behave identically on a dict, so `extractors.py:1062` and four of the five assertions in `tests/test_extractors.py` are unchanged, and only the inline fixture at `:89` needs the new shape. Step 2 gives the full 52-entry classification.

Extend `KnowledgeStore` in `src/legacylift_search/knowledge_store.py` with the GR read and write API. Keep the existing conventions: idempotent `CREATE TABLE IF NOT EXISTS` in `migrate()`, `migrate()` called from `__init__`, and no read-only mode.

Use only libraries already present: `sqlite3` from the standard library, `pydantic` for models, `typer` for commands, `rich` for tabular output, and `chromadb` **pinned at 1.5.9** for the vector collection. Do not add a dependency without recording the decision.

Three external dependencies on other plans must be declared and must **not** be absorbed into this one.

`docs/exec-plans/active/semantic-code-search-graph-index.md` Milestone 26 (SQL table-alias binding and self-reference suppression) is a **hard** gate on Step 7's computed data-flow block, for the reason given in that step. Milestone 27 (unresolved-dispatch visibility) is soft for correctness but hard for the honesty claim: without it, an unresolved edge is indistinguishable from an absent one at the point of consumption, so the coverage story cannot be stated truthfully even though the fallback still functions. Milestone 21 (the evaluation of the index against the fact-graph skill) is soft, and this plan's additive scoping exists precisely to keep it honest.

`docs/exec-plans/pending/layer0-extraction-gap-detection.md` is **declared and not depended on.** It is the early half of the framework-coverage signal Step 6a's `anchor_resolution` breakdown reports late: Layer 0 skips every file whose extension `detect_language` does not recognise, so 364 `.jsp` files totalling 1.25 MB in the reference unit are invisible to the index and to every coverage percentage derived from it. Nothing in this plan is blocked by it — the file-level anchor already handles an unparsed citation target correctly, and the `anchor_resolution` rate already makes the gap visible once rules exist. Know it is there so you read this plan's coverage figures as percentages of what Layer 0 agreed to look at.

Three pieces of Layer-0 work are documented but deliberately **unowned**, and this plan depends on none of them: a pack-emitter shim that would write the fact-graph delivery format from Layer 0; a semantic-typing pass that would give Layer 0 an answer for entity types such as `controller` and `dto`; and re-keying `symbols.id` so the primary key is not line-bearing. Their specifications, at file-ready detail, are in `docs/exec-plans/pending/fact-graph-decision.md` section 5a.6 and `docs/exec-plans/pending/fact-graph-explanation.md` sections 9.7 and 9.8. **None gates Milestone 1.** Declare them; do not build them here.

Already-shipped Layer-0 work that this plan builds on, named so you do not go looking for it: Milestone 24 supplies the `has_column` facts and `foreign_key` edges that Step 7's column-level precision needs, and Milestones 22 through 25 plus domain tagging are what make the derived subject in Step 3 possible at all.

## Revision Notes

`docs/exec-plan.md` asks that each revision of a plan carry a note here saying what changed and
why. This plan has been revised nine times since it was authored, and in each case the change was
the same in kind: a review read it against the source code and the NORMATIVE specifications, found
defects, and the plan text above was corrected in place so that it now reads as though the defect
was never there. **The record of what changed lives in the review tables in the companion
archive `reqs-to-data-store-additional-info.md`, one row per finding, and those tables are this
section's detail rather than a summary of it.** Read them when you want to know why a paragraph is
worded the way it is, or before proposing a change that a review already considered and rejected —
several rows exist precisely to stop a tempting simplification being reintroduced. What is still
live from those rounds — the recurring defect class, the do-not-re-verify list, and the one
superseded closure — is kept in this file under `Surprises & Discoveries`.

The three rounds, in order: `PR-01` … `PR-25` on 2026-08-25, largely schema and source-of-value
defects; `PR-26` … `PR-43` on 2026-08-25/26, which found three structural contradictions and seven
silent failures the first pass had left standing; and `PR-44` onward from 2026-08-26, closed one at
a time as each was settled with the plan's owner rather than in a batch. One earlier closure has
been superseded — `PR-48` replaces `PR-22` — and it is called out where it happened.

Two changes in the third round did not originate as review findings and are recorded in the
`Decision Log` instead, because they are decisions rather than corrections: moving all generated
output under `analysis/<system>/` to follow the `code-modernization` plugin's layout, and applying
the shadow-column mechanism uniformly to every field the extractor and a human may both write.

A fourth round followed on 2026-08-26, `PR-64` … `PR-77`. It differs from the first three in two
ways worth knowing. It began by re-verifying every claim the earlier rounds had marked verified,
independently and against the source, and all of it held — which is why its table says not to
re-check any of it a fifth time. And it is the first round to land **partially closed**: three
blocking findings are corrected in the text above, and eleven remain open with their shape recorded
in the table rather than in a conversation, each tagged with the milestone it binds. An open row is
deliberate. A defect whose shape is written down is worth more than a table that looks clean, and
the alternative — closing eleven findings in one pass to keep the record tidy — is how the second
round's silent failures got past the first.

The fourth round was settled in three groups rather than in one pass, and **all fifteen of its
findings are closed**. The first group was the three blocking findings, `PR-64` … `PR-66`. The second
was the six silent-failure and unbuildable-specification findings, `PR-67` … `PR-72`, whose closure
surfaced `PR-78`. The third was the remainder, `PR-73` … `PR-78`. Each group was presented as options
with the source evidence that constrained them, and in three cases the research changed the answer
before anything was written: `PR-69` could not use a third severity value because SPEC-1 §S1.6
forbids it, `PR-67` needed a sentinel rather than an empty string because an empty string collapses
tier 2 into tier 3, and `PR-71` had a house FTS5 pattern to copy rather than a flavour to choose.

A **fifth round** followed on 2026-08-26, `PR-79` … `PR-85`, and it differs from all four before it
in what it went looking for. The earlier rounds verified the `anchor_key` and `dedupe_key` formulas
exhaustively; none asked where the formulas' *inputs* came from. Three of this round's five blockers
were exactly that — `pattern` derived by a procedure that did not exist, `language` at the file
grain with no defined value, and `entity_class` derived from a mapping left to the implementer over
a domain the analyzed code authors. It is also the first round to take measurements against the
reference corpora rather than only against the source, and the measurements changed three answers:
the ingest-time statement deriver was shown unbuildable on real extractor output, `entity_class` was
shown to genuinely discriminate where `language` was shown not to, and the `.jsp` finding that
prompted `pending/layer0-extraction-gap-detection.md` came out of the same pass.

**It is the first round to amend a NORMATIVE section.** `SPEC-1` gained §S1.12, an amendment log,
recording `V-STY-03`'s rescoping and `V-VAG-09`'s seed list; `SPEC-3` gained §S3.1.1 (the file grain
of `anchor_key`) and §S3.1.2 (`entity_class` declared at extraction). The design draft's two claims
that "SPEC-1 stands in full and unamended" are now pointed at §S1.12 rather than left false. The
three SPEC-3 *refinements* remain Decision Log entries with SPEC-3 unedited, and §S1.12 records why
the two are treated differently.

Two of the fifth round's closures supersede earlier ones, and both are called out where they
happened: `PR-79` replaces `PR-01`, and `PR-81` replaces `PR-70`. Both earlier rows stand unedited
in the archive, as `PR-22` does.

A **sixth round** followed on 2026-08-27, `PR-86` … `PR-98`, and it went looking for one thing: places
where the fifth round changed a rule and a copy of that rule elsewhere in the plan was not changed
with it. It found four, and all four had their surviving stale copy in `Validation and Acceptance` —
the ownership partition asserted as three sets where Step 6 now declares four; `rederive-subjects`
told to re-template statements that Step 8 says it does not touch; a Milestone 0 criterion duplicated
under the wrong command name; and "all ten human-writable fields" over a set of nine. Two further
findings were defects the earlier rounds had simply not reached: `refresh_gr_derived` was specified as
one synchronous function whose two halves sit on opposite sides of its own caller's commit, which no
single call can do, and Step 2's SQL classification list — the list that exists precisely so those
judgements are not rediscovered per site — omitted `create_table` while classifying `foreign_key`,
which is a `SymbolRef` kind and never reaches the `symbols` table at all.

The sixth round is also the first to change the plan's *structure* rather than only its text.
`Validation and Acceptance` now states an observable plus a pointer to the Step that owns the rule,
and does not restate the rule itself. The redundancy elsewhere is deliberate and stays — a cold-start
agent must be able to act on one section — but that section is a test list nobody reads cold, so the
redundancy bought nothing there and cost a copy to keep in step. Two closures also finished work the
fifth round had left half-done rather than superseding it: `PR-87` and `PR-91` are `PR-79`'s stale
copies, not replacements for it.

A **seventh round** followed on 2026-08-27, `PR-99` … `PR-106`, and it re-ran the sixth round's
stale-copy sweep with one addition: it also asked, for every column, *which code path writes this*.
That question found what six rounds of formula- and partition-checking had not — `implementation_notes`
is correctly classified, correctly counted inside the `14/3/9/14` partition, and written by nothing,
because the ingest-time scenario re-authoring that was its writer was deleted by `PR-79` and the
column was left standing. Three further findings were the same deletion's stale copies (`pattern`
still described as derived from the Given/When/Then shape in Step 6, and the frequency claim
"a NULL `pattern` is the common case" surviving in four places after the extractor rewrite made it
uncommon). Two were reachability defects of a second kind: `set_state` mutates `state`, which is
`gr_statements` metadata, and was on neither of the two lists naming the refresh pair's callers; and
Step 2's authoritative `entity_class` list — the list `PR-90` had already repaired once — still
omitted three COBOL kinds, two of them the only genuinely ambiguous entries in the closed half.
The round also caught one latent defect nobody had looked for: the shadowed-field edited-test is
specified as an equality, and `assumptions` is the one nullable member of that set, so `=` over two
NULLs would have made every assumption-less rule read as human-edited forever.

**Milestone 0 was re-read against all eight findings and only one touches it** — `PR-104`, an
acceptance criterion asserting a literal schema version that Step 2 invalidates — so the plan's
stated next action is unchanged.

An **eighth round** followed on 2026-08-28, `PR-107` … `PR-113`, and it asked a question none of the
seven before it had: not "is this rule stated consistently everywhere" but **"could an agent
actually build this"** — walking each rule through the concrete input it governs rather than
through the rest of the plan. Three of the seven were hard blockers and each had survived every
earlier pass by being internally coherent. Step 4's keyword-anchored slot split assumed a
contiguous keyword and a leading `[Condition]`, and §S1.3's restricted keywords are discontinuous
while three of the ten patterns put the condition *after* the keyword — so the split fired two
`ERROR`s on §S1.10 #3, a statement SPEC-1 marks conformant, making it permanently un-approvable.
Step 2's `entity_class` list closed with "any entry not named above is `other`", which measured
against `extractors.json` sends **16 distinct kinds across about 29 of the 52 entries** — every
mainstream C#, Java and TypeScript type and member kind — to `other`, re-collapsing the exact
collisions the Decision Log cites as the reason `entity_class` is a key input. And `gr_scenario`
and `gr_edge_case` were specified as bare column lists with no primary key and no merge rule, so
re-ingest would double the largest child table in the store while the headline merge test, which
counts requirements and citations only, passed.

Two more were unbuildable interfaces rather than wrong rules: `resolve_anchor` took a non-optional
`SQLiteStore` while an explicit acceptance criterion requires ingest to work with no index at all,
and `SQLiteStore` creates its database file lazily, so the required behaviour could not be reached
without silently materializing an empty `index.sqlite`; and `gr_body_schemas.py` was required to
validate four payloads on write, and forbidden to invent the DMN one, while neither this plan nor
the draft's Q3c defined any of the four. One was the seventh round's own new assertion, which was
always false. One was a stale count.

**Milestone 0 is untouched by all seven**, so the stated next action is unchanged again — but
unlike the seventh round, this one changes what must be settled before the first substantive
Milestone 1 code: `PR-108` binds Step 2 and `PR-109` binds Step 3, both of which precede the
validator that `PR-107` binds.

The eighth round is the second to amend a NORMATIVE section. SPEC-1 gained **A3** in §S1.12, and
§S3.1.2 gained the full classification of the closed half of the `kind` domain plus the correction
that `foreign_key` is a `SymbolRef` kind rather than a symbol kind — an error `PR-90` had already
fixed in the plan while leaving the spec carrying it.

Nine of the fourth round's closures are decisions rather than corrections and are in the
`Decision Log` accordingly: `gr.statement` becoming NOT NULL with a pattern-free fallback; widening
`index --reset`'s safety guard as part of Milestone 0's relocation; the `ch0:none` sentinel inside
the tier-2 discriminator, which is this plan's third declared refinement of SPEC-3; the explicit
lifecycle transition graph, including the choice to permit `draft → approved` directly; storing
"not evaluated" as a column rather than as a third severity value, which SPEC-1 §S1.6 forbids; and
making field ownership an exhaustive partition — three-way as closed, superseded by `PR-81`'s
four-way, see the `Decision Log` — whose closure is what revealed that `owner`
had no writer at all; the `GR-`-prefixed ULID with its algorithm written out and no dependency added;
`rederive-subjects` as an explicit command rather than a side effect of `tag-domains`; and splitting
the completeness gate's two exits into `set-run-coverage` and `retire-run`.

A **ninth round** followed on 2026-08-31, `PR-114` … `PR-125`, and it re-ran the eighth round's
question — *could an agent actually build this* — over the steps the eighth round did not reach.
Its shape is the eighth's repeated one level out: every one of its six blockers was a rule that
read correctly and had no buildable referent at the point of use. Three were columns or homes that
did not exist for values the plan already asserts observable behavior on — the review timestamp and
`--note` that `set_state` stamps and writes, and Step 9's import marker. One was an assertion the
eighth round itself had introduced and typed in a way that makes it unsatisfiable: `EXTRACTOR_FIELD_MAP`
as `dict[str, str]` can hold at most fourteen values while the set it must equal is seventeen
columns, because the three shadowed keys each write a live column *and* its shadow. One was a branch
with no producer — `gr.subject`'s `llm_named` and `derived_ambiguous` fallbacks were sent to "a
model-named subject" in a CLI that this plan forbids to contain a model. One was `V-STY-03`
specified as a Layer-0 lookup inside a signature that carries neither citations nor a store, which
is the same defect `PR-110` closed for `resolve_anchor` and which §S1.6's own reason for dropping
rubric item 6 states in as many words. One was a contradiction: Step 3 requires incompleteness be
written into the export while Step 9 forbade any header line.

**Milestone 0 is untouched by all twelve findings**, so the plan's stated next action is unchanged for
the third round running. What this round does change ahead of Milestone 1 is the `gr` schema itself:
the column count moves from forty to **forty-two** and the ownership partition from `14/3/9/14` to
**`14/3/9/16`**, and `gr_import` joins the table list — all of which bind Step 3, which precedes
every other Milestone 1 step. Quote the new figures; the old ones are on the do-not-re-verify list
in their superseded form and are called out there.

The round closed in two passes. The first settled the six blockers and the four stale copies. The
second settled two findings raised as decisions rather than corrections, because each had a
defensible alternative the plan's owner had to choose between: **`PR-124`**, that `file_domains`
carries *two* reserved non-domains and the derivation named only one, so a rule citing an
`excluded` file would have taken the literal string `excluded` as its business subject; and
**`PR-125`**, that `gr_merge_candidate` had no key at all, so the `distinct` judgement it exists to
make stick had no lookup to stick to. Both are `PR-109`'s shape — a table or a rule specified
completely and given no identity — reached by the same walk-the-value check the rest of the round
used.

Six of this round's closures are decisions rather than corrections and sit in the `Decision Log`:
the three review columns with no history table, the statement-`[Subject]` source for the fallback
subject, `leaked_terms` as a parameter rather than a store handle, the deterministic `_incomplete`
export line, the two-sentinel subject rule, and `gr_merge_candidate`'s natural key with `run_id`
deliberately outside it. The remaining four were plain stale copies — a coverage column named two
ways, a writer count stated as five over a list of six, a modal-domain tie-break the majority rule
makes unreachable, and an unstated longest-match rule that would have read every `must not` as a
`must`.
