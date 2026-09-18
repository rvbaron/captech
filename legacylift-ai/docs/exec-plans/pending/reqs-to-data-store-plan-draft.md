# Store Generated Requirements in Data Store

> **Status:** PRE-EXECPLAN DRAFT — **round 1 is COMPLETE: all twenty numbered questions are
> ✅ **THE EXECPLAN IS AUTHORED: `docs/exec-plans/active/reqs-to-data-store.md` (2026-08-25).**
> This file is now the **AUDIT TRAIL ONLY** — the reasoning behind every decision. It is **not**
> the implementation instruction; the ExecPlan is, and it is self-contained. Come back here for
> *why*, and for the four **NORMATIVE** sections the ExecPlan cites verbatim (SPEC-1's ~30
> validator checks in particular).
> settled**, and **ROUND 2 IS CLOSED — the interview is COMPLETE.** All four promoted deferred
> questions are decided: **D1 → `NORMATIVE SPEC-3`; D2, D3 and D7 answered 2026-08-25, all three
> at the standing recommendation (a)**. Recomputing the tree after D7 promotes nothing (D5 is a
> task; D6 is gated on milestone-1's renderer). ✅ **The frontier is genuinely EMPTY.**
> **Next action: the shared-understanding confirmation, then author the ExecPlan.**
> **Started:** 2026-08-19 · **Last updated:** 2026-08-25 (**D2, D3, D7 settled; frontier 3 → 0; interview complete**)
> **Prior updates:** 2026-08-24 (Q3 branch closed in full, frontier 16 → 4; `NORMATIVE PRINCIPLE-1` named; M26/M27 drafted on the semantic-index plan) · 2026-08-21 second pass (SBVR v1.0 Annex F + cl. 12.1.3/12.1.4, Baxter & Hendryx and DeCoMi all read; open actions 2–6 closed; **Q3l added**; **Q3b-notation** and **Q3-backfill** settled; `NORMATIVE SPEC-1` and `SPEC-2` written)
> **Resuming?** **Do not re-run this interview and do not re-author the ExecPlan.** There are no
> open questions; the shared-understanding confirmation was given by the owner on 2026-08-25 and
> the ExecPlan was authored the same day. Both numbered answer sheets and the *Open Frontier*
> chapter are **ARCHIVES**. To *implement*, read `docs/exec-plans/active/reqs-to-data-store.md`.
> To understand *why* something is the way it is, use the *Section map* below.
> **Owner:** Darrell Norton · **Interviewer:** Claude (Opus 5)
> **Do not implement from this file.** It captures decisions and facts so that an
> ExecPlan can be authored once round 2 closes. This file is the input to
> `docs/exec-plan.md`-conformant ExecPlan authoring.

---

# START HERE (cold-start resume; rewritten 2026-08-24 after round 1 CLOSED)

**State in one line:** research is **complete**; **all twenty numbered questions AND all four
promoted deferred questions (D1, D2, D3, D7) are settled**; the frontier is **EMPTY**, the
shared-understanding confirmation is **given**, and the **ExecPlan is written** at
`docs/exec-plans/active/reqs-to-data-store.md`. **Nothing here is open. This file is the audit
trail; the ExecPlan is the instruction.**

## What to do first, in order

1. **Do NOT re-present the numbered questions.** Q3a–Q3l closed 2026-08-24 and **Q4–Q7 closed
   2026-08-24 in the same session** (all four taken at the standing recommendation). Both the
   Q3 sheet and the Q4–Q7 sheet in this file are historical **ARCHIVES**.
2. **ASK NOTHING, AND AUTHOR NOTHING — the frontier is empty and the ExecPlan exists.**
   Implement from `docs/exec-plans/active/reqs-to-data-store.md`, which is self-contained.
   Historical note on how it got here: All four deferred questions are closed: D1 →
   `NORMATIVE SPEC-3`; **D2** → committed JSONL export beside the gitignored, authoritative DB,
   read back only via explicit `import --from-jsonl`, GR tables only; **D3** → this plan builds
   `PRAGMA user_version` + ordered forward-only migrations for both DBs as **Milestone 0**;
   **D7** → **zero consumers re-point**, and SPEC-3 §S3.1's "must ride the pack-emitter shim" is
   **re-scoped to a future obligation** (see the ⚠️ below). Go straight to the
   **shared-understanding confirmation**, then the ExecPlan.
3. **Then** the shared-understanding confirmation with the user, **then** the ExecPlan. Do not
   skip the confirmation — it was the explicit instruction governing this interview.
4. **Read `NORMATIVE PRINCIPLE-1` before proposing any field.** It is the one named principle
   governing the whole design — *deterministic first; LLM only on silence; never blended; never
   in a computed total; report the inference rate.* Named 2026-08-24 after being applied four
   times without a name (Q3a, Q3d, Q3h, Q3i). **It applies to fields not yet designed.** Apply it
   by default; record any deviation.
5. **Do not re-ask what is settled** — the **Decision Log (SETTLED)** holds twenty entries:
   Q1, Q2, **Q3-backfill**, **Q3b-notation**, **all twelve of Q3a–Q3l**, and **Q4, Q5, Q6, Q7**.
6. **Four sections are NORMATIVE and implementable as they stand.** Implement them literally;
   do not paraphrase, re-derive or "improve" them:
   - **`NORMATIVE PRINCIPLE-1`** — provenance discipline (general, applies everywhere)
   - **`NORMATIVE SPEC-1`** — the requirement notation. **All three of its §S1.11 blockers were
     closed 2026-08-24**, so it is now fully implementable with no open dependencies.
   - **`NORMATIVE SPEC-2`** — baseline comparison against the two NNG corpora
   - **`NORMATIVE SPEC-3`** — identity and deduplication (closes **D1**). Four keys, each
     answering one question; **no key takes a domain, a line number, or human-editable text as
     input**. `anchor_key` **lives in Layer 0** and discharges `fact-graph-decision.md` residue
     **(c)** + open question **#6**. `dedupe_key` is the tiered composite; **dedupe is two-stage
     and stage 2 never auto-merges**
7. **Do not launch research subagents.** All research is done and every source is read. About ten
   agents died on `You've hit your individual spend limit` during the 2026-08-19 session, and the
   completed ones consumed 200k–490k tokens each. Everything that matters is in the *Facts
   Established* sections; remaining primary sources are **on disk** (see *Source artifacts*).
8. **Read the corrections list before recommending anything** — several early recommendations
   were revised or refuted, and two were corrected **by measurement** (see
   *Corrections made during this session*).
9. **When you author the ExecPlan it must declare the dependency on
   `semantic-code-search-graph-index.md`** — see the ⚠️ *Dependency* section below (M26 is a hard
   gate on the computed `reads[]`/`writes[]` of Q3h). **It must also declare, and NOT absorb, the
   three unowned Layer-0 pieces** — (a) pack emitter, (b) semantic typing, **(e) re-keying
   `symbols.id`** — see the section after it. **None gates Milestone 1.**
10. ⚠️ **Do not write that this plan "fixes Layer-0 stable IDs."** SPEC-3's `anchor_key` is a
   **computed column beside** the still-line-bearing `symbols.id`. It gives Layer 0 a stable key;
   it does not make Layer 0 stably keyed. Decided 2026-08-25 (option 3): additive here, re-key
   filed as unowned Layer-0 piece **(e)**.

## The twenty-five settled decisions, in one table

Full reasoning for each is in the **Decision Log (SETTLED)**. This table exists so a resumer can
see the shape of the design without reading 5,700 lines.

| # | Decision | One-line summary |
|---|---|---|
| **Q1** | Store is the source of truth | markdown becomes a deterministic render/export, not the system of record |
| **Q2** | Scope of generators | model the schema generically (`kind` discriminator); wire `/modernize-extract-rules` in milestone 1, the other four producers in milestone 2 |
| **Q3-backfill** | No migration, ever | the 470/815 NNG rules are **reference data, never input**; the store starts empty (`SPEC-2`) |
| **Q3b-notation** | 29148 + SBVR compose | 29148 skeleton, SBVR modal verbs selected by `rule_class`, deviations D1–D6 (`SPEC-1`) |
| **Q3a** | Split observed from intended | `as_built` (cited, descriptive) + `statement` (normative), each with its own confidence |
| **Q3b-strictness** | Validator is enforced | `ERROR` blocks `draft`→`approved` and **nothing else**; nothing gates `draft` |
| **Q3c** | Typed bodies | one `structured_body` JSON column; **DMN-shaped** decision tables; **four** types |
| **Q3d** | Subject | derived from `file_domains`; LLM-named fallback only on `unassigned`, **flagged** |
| **Q3e** | User stories | a story is a rollup GR `kind` with `derived_from[]`; schema in M1, producer in M2 |
| **Q3f** | Scenario shape | the new shape **replaces** the extractor's G/W/T; scenarios become a subordinate 0..n child + `implementation_notes` + the `V-STY-03` lint |
| **Q3g** | Disposition | **both** denominators; `disposition` enum with an enforced `not_accounted_for = 0` |
| **Q3h** | Data-flow block | `reads[]`/`writes[]` **computed** from Layer-0; per-entry `provenance`; LLM fallback only on graph silence |
| **Q3i** | Modality + rule class | two enums; `modality` **extractor-proposed, SME-confirmed**; `enforcement_level` behavioral-only |
| **Q3j** | SME-only fields | `rationale`/`fit_criterion`/`enforcement_level` **extractor-forbidden**; `assumptions` permitted; fill rate = **progress, not defects** |
| **Q3k** | `category` shape | advisory tier lives on `enforcement_level`, **not** `category`; `Lifecycle` **kept**, justified by Q3c's `state_transition` body |
| **Q3l** | Vocabulary layer | `term` + `fact_type` tables adopted, sequenced as a **later** milestone (GR tables → Q5 review loop → vocabulary) |
| **Q4** | Physical store | **new tables in `knowledge.sqlite`** — durable, survives `--reset`; Q3h's reads/writes is a cross-DB read either way |
| **Q5** | Lifecycle | **full lifecycle**; re-extraction is a **merge with dedupe**, never truncate-and-insert; merge is also how **coverage** accumulates |
| **Q6** | Embedding | **FTS5 + a dedicated Chroma collection for GRs**; never mixed into `code_chunks` |
| **Q7** | fact-graph | **yes, this is the vehicle** for residue **(d)** — but scoped to **adding** the Layer-1 store, **not retiring** fact-graph (M21 stays honest) |
| **D1** | Identity | four keys, none taking a domain, line number or human text as input → `NORMATIVE SPEC-3` |
| **D2** | Durability vs git | gitignored DB stays authoritative; **committed JSONL export** beside it; import only when asked explicitly |
| **D3** | Migration | this plan **builds** `PRAGMA user_version` + forward-only migrations for **both** DBs, **before** the GR tables |
| **D7** | fact-graph consumers | **zero re-point.** `anchor_key` is invisible to fact-graph (it reads no Layer-0 table), so SPEC-3 breaks nothing today; two-store duplication accepted out loud, exit = **M21** |
| **(e)-scope** | Stable IDs | `anchor_key` is **additive**; `symbols.id` stays line-bearing. Re-key filed as **unowned Layer-0 piece (e)**, dependency declared, not owned |

## Milestone sequencing implied by the settled set

0. **Milestone 0 (NEW, from D3)** — a real versioned migration mechanism: `PRAGMA user_version`
   + ordered forward-only steps, applied to **both** `index.sqlite` and `knowledge.sqlite`.
   Sequenced **before** the GR tables, because a durable store cannot evolve columns without it
   and `index --reset` is data loss for `knowledge.sqlite`. **Scope this plan owns.**
1. **Milestone 1** — GR tables **in `knowledge.sqlite`** (Q4) + `/modernize-extract-rules` wired
   end-to-end; SPEC-1 validator; `disposition`; computed `reads[]`/`writes[]` (**gated on M26**,
   see Dependency below); **lifecycle states, stable ids and merge-with-dedupe from day one**
   (Q5); **FTS5 + the dedicated GR Chroma collection** (Q6, because Q5's merge needs semantic
   dedupe the moment it exists); **SPEC-3's four keys, the shared `identity.py`, `anchor_key` as a
   Layer-0 column, and the §S3.6 domain-retag regression test**. Schema-only cost for
   `kind = story` and `derived_from[]`. **Plus D2's committed JSONL export** (sorted by `gr_id`,
   written on change; `import --from-jsonl` explicit-only) — GR tables only, not `file_domains`.
   **Two measurements this milestone MUST produce** (Q3c): how many rules collapse into a table,
   and the **rule-count distribution per candidate table**. If most candidates exceed ~6 rules,
   the DMN replay loop **waits**. **Run metadata to record** (Q5): `rounds_run`, `cap_reached`,
   `new_rules_in_final_round`.
2. **Milestone 2** — the other four GR producers (`detailed-req-documenter`,
   `business-documenter`, `use-case-generator`, `user-story-generator`) against the same schema.
3. **Later** — the Q3l vocabulary layer, once Q5's review loop can populate it.

**Q5 is settled as "full lifecycle," and it is the load-bearing one for sequencing** —
re-extraction is a **merge**, not truncate-and-insert, and that shapes identity and dedupe from
milestone 1 onward.

**If the user asks for something other than round 2 or the ExecPlan,** the *Section map* below routes to
the right section — this file is ~5,700 lines and is not meant to be read front to back.

---

# ARCHIVE — the Q4–Q7 answer sheet (ALL FOUR ANSWERED 2026-08-24; do not present)

⚠️ **This sheet is historical.** All four were answered **at the standing recommendation** and
are recorded in the **Decision Log (SETTLED)**, which is the authority. It is kept only because
the option spaces and entanglements are useful context when implementing.

| # | Question | Options | Answered | Entanglements that were named when asking |
|---|---|---|---|---|
| **Q4** | Which physical store, and how many? | (a) new tables in `index.sqlite`; (b) a durable store outside the index dir — new `requirements.sqlite` **or** new tables in `knowledge.sqlite`; (c) Chroma as primary; (d) hosted Postgres/Aurora | **(b) — new tables in `knowledge.sqlite`** | `index.sqlite` is derived, gitignored and `--reset`-able, so a reindex could destroy signed-off SME work. `knowledge.sqlite` already survives `--reset` and already holds Layer-1 judgment (`file_domains`). **Q3d's subject join is one SQL statement** if GRs live there. ⚠️ But `symbol_facts` (M24 `has_column`) lives in `index.sqlite`, so **Q3h's reads/writes is a cross-DB read either way** — the two DBs are **never `ATTACH`ed** (`cli.py:1102-1106`). (c) has no relational integrity and cannot express GR→chunk→symbol joins — it is a Q6 addition, never primary. (d) is deferred to `hosted-data-store.md` |
| **Q5** | Do GRs have a lifecycle, or are they regenerated each run? | durable records with `draft → reviewed → approved/rejected/superseded`, stable ids, protected analyst edits — vs. whatever the last extraction produced | **full lifecycle** | **The load-bearing question for sequencing.** Implies re-extraction is a **merge with dedupe**, not truncate-and-insert. **Merge is also how COVERAGE accumulates** (§S2.6): the only run that reached the web-action and persistence layers (327 vs 148 files) did so by merging three scoped runs, and the best single run stopped at its round cap still finding ~28 new rules/round — so truncate-and-insert **cannot reach coverage already demonstrated**. Record `rounds_run`, `cap_reached`, `new_rules_in_final_round` as run metadata. **Differentiator:** AWS Transform has no requirement-level lifecycle and no HITL gate on requirements. **Three settled decisions already lean on Q5:** SPEC-1's `draft`/`approved` gate, Q3g's reviewer-identity-from-day-one argument, and Q3l's populator |
| **Q6** | Do requirements get embedded for semantic retrieval? | (a) relational + SQLite FTS5 only; (b) FTS5 + a **dedicated** Chroma collection for GRs; (c) GRs in the existing `code_chunks` collection with a type discriminator | **(b)** | FTS5 covers keyword lookup for free. A separate GR collection gives **semantic dedupe**, which Q5's merge needs the moment it exists — "have I seen this rule before?" is a fuzzy-match question exact ids cannot answer. (c) poisons code search and forces every existing query to carry a filter |
| **Q7** | Is this plan the vehicle for the pending fact-graph decision? | (a) explicitly yes — this implements the Layer-1 judgment store and fact-graph's residue **(d)** is satisfied here; (b) explicitly no, accept two Layer-1 stores; (c) defer until M21 | **(a), scoped to adding** | `fact-graph-decision.md` concludes that after M22–25 fact-graph's residue is four pieces, of which only **(d) LLM-inferred facts Layer 0 cannot derive** genuinely needs a model — and a GR store is exactly a home for (d). ⚠️ **Caveat to state in the plan:** that doc gates Option A on **M21**, still open. Building the GR store does not require M21 (it is additive and removes nothing), so proceed — but **scope this plan to *adding* the Layer-1 store, not *retiring* fact-graph**, so M21 stays an honest evaluation rather than a fait accompli |

---

# ARCHIVE — the Q3 answer sheet (ALL TWELVE ANSWERED 2026-08-24; do not present)

⚠️ **This sheet is historical.** Every question in it is answered and recorded in the
**Decision Log (SETTLED)**, which is the authority. It is kept only because the option spaces,
the standing recommendations and the evidence summaries are useful context when implementing.
**Do not re-ask any of it.** The old title was "STEP 1 — Q3 ANSWER SHEET (present this to the
user verbatim)"; that instruction is void.

**This block is the first action of a resumed session.** It is deliberately complete enough to
present without reading the rest of this file. Each question gives the options, the standing
recommendation, and what changed since the questions were first asked. ⚠️ **ALL TWELVE were
answered on 2026-08-24 — the rows are kept below purely as context. Do not present this sheet
again. **Q4–Q7 were also answered on 2026-08-24, so there is nothing left to present at all** —
the next action is the shared-understanding confirmation, then the ExecPlan.

**One framing sentence to open with:** forward requirements engineering writes normative
statements before code exists ("the system shall"); reverse engineering reads code that exists
and produces descriptive statements ("the code does"). The current Rule Card conflates them, and
one `Confidence: Medium` field carries both "is the citation faithful" and "is this the business's
intent" — which is why "Medium" is uninformative across 470 rules. Most of Q3 follows from
separating those.

**Load-bearing constraint behind several answers:** intent is information-theoretically absent
from code (Leveson TSE 1994 on TCAS II), and there is no oracle for extraction quality — no
benchmark, no ground truth, ~29% precision in the one honest published measurement (Chaparro,
WCRE 2012). So the plan cannot claim accuracy. It can claim *auditable completeness* (Q3g) and
*accumulated human judgment* (Q5).

| # | Question | Options | Recommended | Status |
|---|---|---|---|---|
| **Q3a** | Split observed behavior from intended requirement? | (a) two fields on one GR — `as_built` (cited, descriptive) + `statement` (normative), each with its own confidence; (b) one blended field as today; (c) two record types, Observation and Requirement, linked m:n | **(a)** | ✅ **ANSWERED 2026-08-24 — (a) approved.** Do not re-ask; see Decision Log |
| **Q3b** | Is the notation enforced or advisory? | (a) enforced — blocks `approved`; (b) advisory, warn only; (c) stylistic, no validator | **(a)** | ✅ **ANSWERED 2026-08-24 — (a) approved, fully settled.** SPEC-1 stands unamended; `ERROR` blocks `draft`→`approved` and nothing else. Historical context follows. **NARROWED — half of this question was SETTLED 2026-08-21.** *What* the notation is has been decided and fully specified in **NORMATIVE SPEC-1** (29148 skeleton + SBVR modal verbs selected by `rule_class`, deviations D1–D6). All that remains is **how hard it bites**: (a) blocks the `approved` transition, (b) records findings without blocking, (c) no validator. SPEC-1 assumes (a) and degrades cleanly to (b) — every `ERROR` becomes a `WARN` and the §S1.9 gate disappears |
| **Q3c** | Typed bodies for decision tables / state machines / formulas? | (a) three typed child tables now; (b) one generic `structured_body` JSON column, validated per category; (c) flat cards only, defer | **(b)** — but DMN-shaped for the decision-table type, and **four** body types not three (`decision_table`, `state_transition`, `formula`, `invariant`) | ✅ **ANSWERED 2026-08-24 — (b) approved with both amendments.** The 0%-F1 warning below is now **normative**: the replay loop is a **detector of bad extraction**, and it **waits** if most candidate tables exceed ~6 rules. Historical context follows. **RESTATED TWICE.** Biggest change in the branch |
| **Q3d** | Who is the subject of "shall"? | (a) the Layer-0 domain of the citing file; (b) the system/system-dir name; (c) the component the LLM names; (d) literal "the system" | **(a)**, falling back to (c) when the file is `unassigned`, **never (d)** | ✅ **ANSWERED 2026-08-24 — (a) approved, with the (c) fallback explicitly FLAGGED** as LLM-named rather than blended with derived subjects. **Closes §S1.11 item 2: `file_domains` is the naming authority, so `V-SLOT-01`/`V-SLOT-02` are now implementable.** Cost still depends on Q4 |
| **Q3e** | Do user stories exist, and at what level? | (a) no story layer; (b) story as a rollup GR kind over N rules where actor evidence exists, with `derived_from`; (c) `as-a/I-want/so-that` on every GR | **(b)**, deferred to the Q2 future milestone | ✅ **ANSWERED 2026-08-24 — (b) approved.** Milestone 1 pays only the schema cost (`story` in the `kind` enum + nullable `derived_from[]`); the producer is milestone 2. (c) rejected — per-rule actors will be fabricated |
| **Q3f** | What shape do G/W/T scenarios take in the new schema? (**retitled 2026-08-24** — it was never a migration question; nothing is migrated) | (a) keep verbatim; (b) re-author implementation-independent + `implementation_notes`; (c) keep verbatim + a leakage lint | **(b) *plus* (c)'s lint**, and the lint now has a **named six-item rubric** to implement (Baxter & Hendryx slide 5, §18) rather than one we invent | ✅ **ANSWERED 2026-08-24 — (b) + the lint approved.** Scope confirmed by the user: the new shape **replaces** the extractor's G/W/T; scenarios become a subordinate 0..n child. `V-STY-03` stays **WARN** — TCAS II says the cleanup cannot be completed, only recorded |
| **Q3g** | Adopt a disposition model with a zero-invariant? | (a) both — keep chunk coverage as the extraction denominator, add a `disposition` enum with an enforced `not_accounted_for = 0`; (b) chunk coverage only; (c) free-text disposition | **(a)** — still the single most valuable thing to steal from AWS | ✅ **ANSWERED 2026-08-24 — (a) approved.** Both denominators; `not_accounted_for = 0` is an **enforced** gate before a run counts as complete. It is an auditable *completeness* claim in a field where no *accuracy* claim is possible |
| **Q3h** | Attach a deterministic data-flow block? | (a) compute reads/writes from Layer-0 edges, no LLM; (b) have the extractor state them as prose; (c) omit | **(a)** | ✅ **ANSWERED 2026-08-24 — (a) approved, with a FLAGGED LLM fallback.** Per-entry `provenance` (`computed` \| `llm_inferred`) + an `explanation` on inferred entries only; the fallback fires on **graph silence, not disagreement**, and inferred entries never join a computed total. **M24 `has_column` is already implemented**, so the substrate exists |
| **Q3i** | Modality: requirement vs expectation, and definitional vs behavioral? | (a) two enums — `modality` (requirement\|expectation) + `rule_class` (definitional\|behavioral), with `enforcement_level` valid only on behavioral; (b) `rule_class` only; (c) neither, leave conflated as today | **(a)** | ✅ **ANSWERED 2026-08-24 — (a) approved.** `modality` is **extractor-proposed, SME-confirmed** (flagged until confirmed, per PRINCIPLE-1). `rule_class` and `enforcement_level` were already fully specified in SPEC-1, so only `modality` was genuinely open. **VERIFIED 2026-08-21 from SBVR v1.0 itself** (§17a-ter). The `enforcement_level`-only-on-behavioral constraint is not our reasoning — it is the spec's fact type (`operative business rule has level of enforcement`) plus cl. 12.6.12's "(only)". SBVR's own synonym for `operative` is **`behavioral business rule`** |
| **Q3j** | Ship SME-only fields the extractor must leave empty? | (a) carry `rationale` + `fit_criterion` as first-class, extractor-forbidden, and report fill rate as review progress; (b) carry them but let the extractor guess; (c) omit until an SME workflow exists | **(a)** — treat the empty field as a feature | ✅ **ANSWERED 2026-08-24 — (a) approved.** `rationale` + `fit_criterion` (+ `enforcement_level`) **extractor-forbidden**; **`assumptions` extractor-PERMITTED** because it is often visible in the cited code and 29148 cl. 5.2.7 makes it a normative **`shall`**. Fill rate is reported as **progress, never as a defect count** |
| **Q3k** | Does `category` change shape? | (a) put the warn-don't-block tier on **`enforcement_level`** (SBVR's six-value scale, whose lowest value is literally `guideline`) **and** justify or drop `Lifecycle`; (b) add a `guideline` value to `category` instead; (c) leave the enum as `Calculation \| Validation \| Lifecycle \| Policy` | **(a)** | ✅ **ANSWERED 2026-08-24 — (a) approved.** Advisory tier stays on `enforcement_level` (already in SPEC-1 §S1.5); `category` does **not** gain a `guideline` value. **`Lifecycle` is KEPT**, justified as the category whose rules carry Q3c's `state_transition` body; correlation between the two is a **WARN**, never ERROR. Only `V-CLASS-02` is affected. **RESTATED 2026-08-21 (second pass).** The tier is real and the defect is real, but it does **not** belong in `category` — SBVR cl. 12.1.3 puts it on the enforcement scale. See below |
| **Q3l** | Does the store get a **vocabulary layer** — `term` and `fact_type` records — or only rules? | (a) yes, two lightweight tables (`term`, `fact_type`) that GRs reference, populated from Layer-0 symbols/columns + analyst naming; (b) a free-text `glossary` field on each GR; (c) no vocabulary layer, rules cite code symbols directly (today's shape) | **(a)**, but as a **later milestone** — land the GR tables first, add vocabulary once Q5's review loop exists to populate it | ✅ **ANSWERED 2026-08-24 — (a) approved as a later milestone.** Sequencing: GR tables → Q5 review loop → vocabulary. **Closes the last SPEC-1 blocker (§S1.11 item 3)**; `V-STY-03` still stays a WARN. **NEW 2026-08-21 (second pass).** Four independent sources now say rules are built *on* a vocabulary and that the vocabulary must be recovered first: Von Halle 2001 (terms/facts are peers of rules, §17a-bis), SBVR 2008, KDM 2012 (`TermUnit`/`FactUnit`/`RuleUnit`), and Baxter & Hendryx 2005 ("first get the business vocabulary, then build rules using vocabulary", §18). Our design has **no** such layer |

## Why Q3k exists (new, and it is a live defect not just a taxonomy debate)

Von Halle's verified taxonomy (§17a-bis) has **`guideline`** — a rule that "does not force the
circumstance to be true or not true, but merely warns about it, **allowing the human to make the
decision**." **Our `category` enum has no warn-don't-block tier**, so any advisory rule in the
corpus is currently being classified as `Validation` and silently promoted to mandatory. That is
a correctness problem in output we have already shipped, not a future design question.

**Where the tier belongs changed on the second pass (2026-08-21).** SBVR v1.0 cl. 12.1.3, read
directly (§17a-ter), carries a six-value `level of enforcement` scale — `strict`, `deferred`,
`pre-authorized`, `post-justified`, `override`, **`guideline` ("suggested, but not enforced")**.
So the warn-don't-block tier is a position on an **enforcement scale**, not a rule *category*,
and Von Halle's `guideline` and SBVR's `guideline` are the same idea at the same name. Recording
it as a `category` value would make it mutually exclusive with `Calculation`/`Validation`, which
is wrong — an advisory *calculation* is perfectly coherent. Two knock-ons: the tier is orthogonal
to Q3k's other half (the `Lifecycle` question stays a `category` question), and it lands on the
field Q3i already restricts to behavioral rules, which is exactly right — a definitional rule
cannot be "suggested but not enforced" because it cannot be violated at all.
⚠️ Keep §17a's caveat when writing this up: the six values appear under an `Example:` caption and
trace to **BMM**, so cite them as *an example set given by SBVR*, not as a normative SBVR enum.
That caveat is now **confirmed from the standard**, not inherited second-hand.

In the other direction, her four ways a rule guides a business event (present information /
constrain information / initiate external action / create new information) contain **no state or
lifecycle class** — so `Lifecycle` has no counterpart in her taxonomy and cannot borrow its
authority. It needs its own justification or should fold into action-enabler.

⚠️ Note 29148's own `Type` value set (Functional/Performance, Interface, Process, Quality,
Usability, Human Factors) is systems-engineering-shaped and does **not** fit business rules. The
value set must come from **Von Halle** or **Withall** (§11), not the standard.

## The one warning to deliver with Q3c

Q3c's headline argument was that a DMN table is *executable*, so the legacy system becomes the
oracle for the decision-logic subset (extract to DMN XML → Drools `ANALYZE_DECISION_TABLE` →
`COMPUTE_DECISION_TABLE_MCDC` + `MCDC2TCKGenerator` → replay against legacy and diff). **That
argument was restated on 2026-08-21 after reading the only code→DMN paper in existence**
(van de Hoef et al., §17e-bis): it reports **0% decision-rule F1 on three of its eight logic
cases**, collapsing past ~6 rules per table, on hand-picked single-file Java of at most 19 rules.

The Drools half of the chain is unaffected — but the assumption that an extracted table is good
enough to analyse does not hold. **The loop is the detector of bad extraction, not a validation
of good extraction**, which given those numbers makes it more valuable rather than less: it is
the only place in the design where extraction error is *measurable* rather than assumed. Design
for rejecting most tables at first, and **do not promise DMN coverage of the corpus.**

## After Q3 — the rest of the frontier — ✅ **ALSO CLOSED 2026-08-24**

**Q4–Q7 were asked in the round immediately following the Q3 branch and all four were answered
at the standing recommendation.** Full reasoning is in the Decision Log; the *Open Frontier*
chapter is now background only. The two entanglements named when asking, and how they resolved:

- **Q4 (which physical store, how many)** — answered **`knowledge.sqlite`**, so Q3d's subject
  join **is** the cheap one-file SQL statement. Q4 also inherited ReqIF's SpecObject /
  SpecHierarchy split (a GR record existing independently of the documents it appears in). ⚠️
  Q3h's `reads[]`/`writes[]` remains a **cross-DB Python-side join** regardless, because
  `symbol_facts` lives in `index.sqlite`.
- **Q7 (is this the vehicle for the fact-graph decision)** — answered **yes for residue (d)**,
  but **scoped to *adding* the Layer-1 store, not retiring fact-graph**, because **M21** of
  `docs/exec-plans/active/semantic-code-search-graph-index.md` is still open.

**Numbered-question total: ZERO open.** Twenty decisions settled. ⚠️ **But the frontier is not
empty — Q4 and Q7 promoted four deferred questions (D1, D2, D3, D7) into round 2.** See
*Deferred Questions*. **Then** the user confirms shared understanding, **then** the ExecPlan is
authored — that was the explicit instruction governing this interview.

---

## Session log (what happened when, so a resumer can trust the dates)

| Date | What happened |
|---|---|
| **2026-08-19** | Design interview opened. Q1 and Q2 settled. Q3 branched into Q3a–Q3h. Notation survey run (§§1–20); ~ten research agents died on spend limits, two reports lost. Session ended mid-interview. |
| **2026-08-20** | START HERE block audited and extended (code surfaces, section map, gating dependency). **Q3 restated** with the survey folded in: Q3b and Q3c rewritten, **Q3i and Q3j added**, consolidated candidate field list authored. Frontier 12 → 14. |
| **2026-08-24 (fifth pass — D1 closed, SPEC-3 written)** | User drilled into the chunk/symbol id problem, then asked for an approach giving **stable, shared identity that survives domain retagging**, keeping `file_path` in the hash (so two identical methods in different files stay distinct) while still being able to tell whether two things are **exactly the same**. Result: **`NORMATIVE SPEC-3 — Identity and Deduplication`**, closing **D1**. Verified in code first: chunk id `chunking.py:142-145` (+`:221-224`, `:294-297`) with `idx = enumerate(symbols)` at `:116` so inserting a symbol **renumbers every later chunk in the file**; symbol id `extractors.py:1112-1115` where `start_line` means **any line shift above a symbol changes its id with zero content change**; reindex **physically deletes and reinserts** (`store.py:392-417`) with `PRAGMA foreign_keys=ON` (`:181`), so a hard FK yields either silent row deletion (CASCADE) or a silently nulled trace (SET NULL). Found the house precedent: `graph_edges` already treats symbol ids as a **cache not identity** (`store.py:309-311`, durable `callee_name` beside an advisory id). Credited fact-graph for already separating identity / `line_range` / `content_hash` (`SKILL.md:912-932, 818, 996-1020, 1271-1274`). **Decisions taken this pass:** `anchor_key` **lives in Layer 0** (user's call) — discharges `fact-graph-decision.md` residue **(c)** and open question **#6**, rides the pack-emitter shim; **`dedupe_key` = option E, tiered composite**; **stage 2 of dedupe NEVER auto-merges** (user's call). **Four defects found in the existing formulas and fixed normatively:** `:` delimiter is ambiguous because `qualified_name`/`relative_path` contain it; fact-graph hashes the **fine** `entity_type` while coarsening only the display prefix (**backwards**); no path-separator normalization despite Windows-host/Linux-repo analysis; 12 hex chars is ~1-in-55k at 100k entities. **Two non-obvious exclusions recorded:** `statement` is out of `dedupe_key` because it is SME-mutable (so **reviewed rules would be the ones that duplicate**), and `subject` is out because it is domain-derived **and** functionally determined by the anchor — all churn, zero discrimination. Also recorded: the drift-vs-clone **2x2**, which makes **moves auto-repairable** and so removes the cost of keeping `file_path` in identity; and §S3.6's **executable invariant** — re-run `tag-domains` with a changed `domains.json` and assert every key is byte-identical. Frontier: round 2 now **D2, D3, D7**. |
| **2026-08-25 (eighth pass — CONFIRMATION GIVEN, EXECPLAN AUTHORED)** | **The owner confirmed the shared-understanding summary; the ExecPlan was authored to `docs/exec-plans/active/reqs-to-data-store.md` (438 lines) against `docs/exec-plan.md`.** Note there is **no `PLANS.md`** at the repo root — `docs/exec-plan.md` is the convention file, and the ExecPlan references it. Structure: **Milestone 0** (versioned migrations, `PRAGMA user_version` + forward-only steps, **both** DBs, before any GR table), **Milestone 1 in ten steps** (identity module -> `anchor_key` on `symbols` -> five GR tables -> SPEC-1 validator + gate -> FTS5 + the dedicated `gr_statements` Chroma collection -> two-stage merge -> data-flow block **shipped disabled** behind an M26 flag -> the `requirements` CLI group -> JSONL export/import + `/modernize-extract-rules` wiring -> the two mandatory measurements), **Milestone 2** (four remaining producers), **Milestone 3** (vocabulary layer). **Baseline measured, not assumed: 357 tests collected AND 357 passed, exit 0** — which also **corrects the standing `legacylift-venv-aws-extra` note for this machine**, since `test_bedrock_embedder.py` passed, so boto3 is present. Written self-contained per `docs/exec-plan.md`: every term defined in plain language, the `KnowledgeStore` `Path.exists()`-before-construct trap and the cross-DB Python-join constraint (`cli.py:1095`) both explained inline, the broken PATH shim called out, and the four PRINCIPLE-1/SPEC traps restated in the milestone text (keyword disjointness, the two mandatory validator carve-outs, and the explicit "no check may be written for `[ConstraintOfAction]` absence"). **SPEC-1's ~30 validator checks are cited to this file rather than restated** — the one deliberate exception to self-containment, because paraphrasing them would lose fidelity. Acceptance is behavioral throughout; the headline test is **ingest twice, count unchanged**. Also required: the Apache-2.0 attribution line when editing `.claude/skills/code-modernization/commands/modernize-extract-rules.md`. **This file is now demoted to AUDIT TRAIL** — header, resume banner and START HERE all re-pointed at the ExecPlan. **Next action: implement Milestone 0.** |
| **2026-08-25 (seventh pass — the stable-ID scope call)** | **Owner asked the sharp question: “is `anchor_key` in Milestone 1 the stable-IDs fix?” Answer: NO — it is an additive parallel key, and saying otherwise was an over-claim that had already propagated into `fact-graph-decision.md` §7 open question #6.** Verified in code: `symbols.id` is still `f"{language}:{relative_path}:{qualified}:{start_line}"` (`extractors.py:1112-1115`) and **five surfaces key off it** — the PK (`store.py:209`), `graph_edges.caller_symbol_id`/`callee_symbol_id` FKs (`:309`/`:310`, CASCADE / SET NULL), `symbol_facts.subject_symbol_id` (`:359`, NOT NULL CASCADE), and plain columns `chunks.symbol_id` (`:216`) + `symbol_refs.enclosing_symbol_id` (`:278`) — so an edit above a symbol still mints a new id and **cascades its edges and facts away**. Harmless today (all 12 predicates are deterministic and regenerated); not harmless once anything durable hangs off a symbol row. `chunks.id` is separately unstable (`chunking.py:143`/`:222`/`:295`). **Why the GR store is safe regardless:** §S3.3 makes `anchor_key` **advisory only, never an FK target** — `(relative_path, start_line, end_line)` is the durable anchor, `gr_id` the sole FK target, per §S3.3's *“recoverable vs unrecoverable, not stable vs unstable”*. **Owner chose option 3:** ship `anchor_key` additively in Milestone 1 and file the re-key as **unowned Layer-0 piece (e)** — this plan **declares the dependency and owns none of the repair**, the same placement logic as M26/M27 (Layer-0 defects benefit every consumer). Noted that **(e) is implementable only because of this plan's own Milestone 0** (D3's `PRAGMA user_version` + forward-only migrations; before it there was no `ALTER TABLE` in `src/` at all), so (e) was previously not just unowned but **unimplementable** — recorded as a downstream benefit of Milestone 0. Also recorded that **(e) needs its own edit-and-reindex verification** per §S3.7 (this identity design has never been exercised that way by either tool) and must not ride Milestone 1's tests. Written into **`fact-graph-decision.md` §5a.6** (new — consolidating all **three** unowned pieces (a), (b), (e), with §5a.6.1 giving (e)'s surface-by-surface scope and §5a.6.2 the placement rationale), **open question #6 re-scoped to half-answered**, the **M21** block, **SPEC-3 §S3.1** (explicit “ADDITIVE; `symbols.id` is NOT re-keyed”), a new **dependency section** in this file, and START HERE items 9–10. **Next action unchanged: shared-understanding confirmation, then the ExecPlan.** |
| **2026-08-25 (sixth pass — D7 closed; INTERVIEW COMPLETE)** | **D7 answered (a) — zero re-point — closing round 2 and emptying the frontier for real (3 → 0).** Before answering, the owner's framing ("fact-graph is the old way; the semantic-index plan is intended to retire it — with stable IDs fixed, is anything left?") was treated as a **fact question** and answered by **counting the only fact-graph run tracked in git** (58 files / 30 MB, `repos/ctcm/ctcm-api/legacylift-docs/context/`, 6,047 entities / 3,928 relations / 38,618 facts) rather than by reading its schema — the same discipline that produced the §S2.6 correction. **Five measured findings, all recorded in the corrections table:** (1) fact-graph emitted **5 of ~45 predicates** — `has_property` 89.3%, `is_required`, `accepts_param`, `http_method`, and **`business_rule` at 620 facts / 1.6%**; **98.4% of its facts layer is already Layer-0's**; (2) the **~18 interpretive predicates** (`integrates_with`, `state_transition`, `publishes_to`, `validates`, `ensures`, …) emitted **0 facts each** — true of the schema, false of the output, so the GR store loses nothing by not modelling them; (3) the 620 `business_rule` facts are shallow (sampled: a bare `throw` read as a rule), corroborating that extract-rules covers rules better; (4) **identity is a non-differentiator in both directions** — an intermediate claim that fact-graph emits no entity `content_hash` was **my error, corrected the same day** (it is `attributes.content_hash`, present 6,047/6,047, and `snippet_hash` is 38,618/38,618), so §5 claims 3/5 stand and SPEC-3 wins only on *construction* (`` delimiter, coarse `entity_class`, 16 hex, domain excluded) while still closing residue **(c)** on the Layer-0 side; **§6.2 item 4 was also refuted** — `technical_layer` resolved for 84.7% of entities, not "nearly every one is `Other`"; (5) **semantic entity typing is real and quantified** (8 types) and **`contains` (1,002 edges)** has no Layer-0 equivalent. ⚠️ **Owner correction accepted and verified:** fact-graph is **not language-agnostic** — its per-language `grep` blocks are hardcoded in `SKILL.md:653-775` and the *Other Languages* hatch is one pattern-free sentence, so an unlisted language is an **extension point, not a capability**; **"zero install" is the half that survives**. ⚠️ **Roadmap finding:** of §5a.4's four residue pieces, **(c) is closed by SPEC-3, (d) is homed by Q7, and (a) the pack emitter + (b) semantic typing are milestones on NO plan** — so the semantic-index plan does not contain the work required to retire fact-graph; **filing (a)+(b) is an unratified open action.** **SPEC-3 §S3.1 and §S3.6 were RE-SCOPED** (they over-claimed a present pack-shim dependency; fact-graph reads no Layer-0 table, so `anchor_key` ships additively in M1 and breaks nothing). All findings written into **`fact-graph-explanation.md` §9** (new, with §6.2 item 10 and §8.6 corrections), **`fact-graph-decision.md` §5a.5** (new, plus header, §5a banner, open questions #3/#5/#6, Related documents), and the **M21 checklist item** of `semantic-code-search-graph-index.md` (measured-input block correcting its task set). Two follow-on measurements were then taken so that residue **(a)** and **(b)** can be *filed as milestones later without re-derivation* (the owner deferred filing them): **§9.7** records the **measured field-level pack contract** (every `index.json` key, all four record shapes with per-field counts, the Layer-0 source per field, and the finding that relation `file`/`line` are absent on 3,928/3,928 while Layer 0 carries them per edge) and **§9.8** records the **eight `type` values with the shipped M22–M25 signal for each** (two already in `symbols.kind`, four derivable from existing facts/edges, `class` the default, only `service` needing a heuristic). **Next action: the shared-understanding confirmation, then the ExecPlan.** |
| **2026-08-25 (fifth pass — D2 and D3 closed)** | **Round 2 opened; D2 and D3 both answered at the standing recommendation (a), frontier 3 → 1.** Before presenting, the two Q4 consequences were **re-verified in the environment** rather than asserted from the prior pass: `.gitignore:88-89` does ignore `knowledge.sqlite*`, and `src/` has no schema `ALTER TABLE` (the five hits in `extractors.py` are SQL-*parser* regexes reading client DDL), no `PRAGMA user_version`, and `SCHEMA_VERSION = "1"` written at `indexer.py:666` but never compared. The user then asked a **fact** question — what do the *existing* pre-GR stores commit to git — which per the *Interview method* was looked up, not answered from memory: **exactly one store is tracked, and it is text not binary** — 58 files / **30 MB** of fact-graph packs under `repos/ctcm/ctcm-api/legacylift-docs/context/`; `index/` (`.gitignore:83-84`), `knowledge/` (`:88-89`) and the whole NNG analysis repo (`:92`) are ignored, and **zero** `BUSINESS_RULES.md` / `DATA_OBJECTS.md` / `domains.json` are tracked anywhere. Three consequences recorded on **D2**: (i) "binary ignored, text serialization tracked" is **already this repo's pattern** for the only knowledge store it commits, and those packs do carry Layer-1 judgment; (ii) the precedent is also a **size warning** — 30 MB regenerated wholesale each run, so the GR export is deliberately **not** pack-shaped and relies on Q5's incremental merge; (iii) the loss exposure D2 predicts is **already live in `file_domains`**, committed nowhere. **D2 = (a)**: gitignored DB stays authoritative, committed JSONL sorted by `gr_id` beside it, read back **only** via explicit `import --from-jsonl`, **GR tables only** (a `file_domains` export is recorded as a known gap belonging to domain-tagging scope, deliberately not built here). **D3 = (a)**: this plan **builds** `PRAGMA user_version` + ordered forward-only migrations for **both** DBs as **Milestone 0, before the GR tables land** — scope this plan owns and pays for, unlike M26/M27; it also retires SPEC-3 §S3.1's "the repo currently has no such mechanism" caveat. Header, START HERE (now **twenty-three** decisions + a new Milestone 0), Deferred Questions and Interview method all updated. **Next action: D7, the last open question, then the shared-understanding confirmation, then the ExecPlan.** |
| **2026-08-24 (fourth pass — numbered questions closed)** | **Q4–Q7 presented and all four answered at the standing recommendation, emptying the frontier (4 → 0) and closing the interview.** **Q4 (b) — GR tables in `knowledge.sqlite`**: durable, survives `--reset`, already the Layer-1 store holding `file_domains`, so Q3d's subject join is one SQL statement; a third `requirements.sqlite` was rejected as a second cross-DB seam for nothing; ⚠️ recorded that Q3h's `reads[]`/`writes[]` stays a **cross-DB Python-side join under every option** because `symbol_facts` lives in `index.sqlite` and the two DBs are never `ATTACH`ed (`cli.py:1102-1106`). **Q5 — full lifecycle from milestone 1**: durable records, stable ids, `draft`→`reviewed`→`approved`/`rejected`/`superseded`, human text protected from the next LLM pass, and **re-extraction is a merge with dedupe on the §S2.2 join key, never truncate-and-insert** — justified twice over, once as the only thing markdown cannot do and once by §S2.6's measurement that merging scoped runs is how **coverage** was reached (327 vs 148 files) while the best single run capped out still finding ~28 new rules/round; `rounds_run` / `cap_reached` / `new_rules_in_final_round` required as run metadata. **Q6 (b) — FTS5 plus a dedicated GR Chroma collection**, milestone-1 scope because Q5's merge needs semantic dedupe immediately; `code_chunks` reuse rejected (poisons code search, taxes every existing query). **Q7 (a), scoped to ADDING** — this plan is the home for fact-graph residue **(d)**, but the ExecPlan must **add** the Layer-1 store and **not retire** fact-graph, keeping **M21** an honest evaluation. Header, START HERE (now a **twenty**-decision table), milestone-1 scope, session log and section map all updated; the Q4–Q7 sheet demoted to **ARCHIVE** and the **Open Frontier marked EMPTY / background only**. **Next action is the shared-understanding confirmation, then ExecPlan authoring.** ⚠️ **Correction made in the same pass:** the claim "frontier empty" was wrong — recomputing the tree shows Q4 unblocked **D1, D2, D3** and Q7 unblocked **D7**, so **round 2 is open** and the file was re-stated accordingly. **D2 and D3 are consequences of the Q4 answer that the ExecPlan cannot be written around** (`knowledge.sqlite` is gitignored; there is no `ALTER TABLE`/migration mechanism in `src/`). |
| **2026-08-24 (third pass — handoff hardening)** | File restructured so a **new agent can pick it up cold**: START HERE rewritten for the post-Q3 state (adds a sixteen-decision summary table and the implied milestone sequencing), the Q3 answer sheet demoted to a marked **ARCHIVE** and replaced by a self-contained **Q4–Q7 answer sheet**, the Open Frontier's Q3 block marked **CLOSED / background only** with "Decision Log wins" precedence, Decision Log entries reordered Q3a→Q3l, and the section map re-pointed (PRINCIPLE-1, the dependency table, the settled-set table). Header status changed from "paused mid-interview" to "Q3 closed, Q4–Q7 remain". |
| **2026-08-24 (second pass)** | Interview resumed; answer sheet presented. **User approved Q3l (a)** as a later milestone (GR tables → Q5 review loop → vocabulary), **closing the last SPEC-1 blocker (§S1.11 item 3) and the entire Q3 branch**. Earlier: **Q3j (a)** with the forbidden set drawn tightly — `rationale`/`fit_criterion`/`enforcement_level` extractor-forbidden, **`assumptions` extractor-permitted** (often visible in code; 29148 cl. 5.2.7 `shall`), fill rate reported as progress not defects. Earlier: **Q3k (a)** — advisory tier stays on `enforcement_level` (closing the live defect where advisory rules were silently promoted to mandatory `Validation`), and **`Lifecycle` kept**, justified as the category carrying Q3c's `state_transition` body. Earlier: **Q3i (a)** with `modality` **extractor-proposed and SME-confirmed** — the third application of PRINCIPLE-1's flagged-fallback pattern in one session. Also this pass: **M26/M27 drafted** on the semantic-index plan and a **⚠️ DEPENDENCY section** added here (M26 hard, M27 soft-for-correctness/hard-for-honesty, M21 soft). Earlier: **Q3h (a)** and **added the flagged-LLM-fallback amendment**: where Layer 0 is silent, capture the extractor's inference with a per-entry `provenance` marker and an `explanation`, never blended into a computed total. Corrected in the same pass: **M24 `has_column` is already implemented** (done 2026-07-17, `6b9ac4b3`), so Q3h's substrate exists today. Earlier: **Q3g (a)** — both denominators, `not_accounted_for = 0` enforced, with the "never print an LLM-judged number beside a computed one" rule recorded as normative. Earlier in the same pass: **Q3f (b) + the lint**, and clarified the scope: the new requirement shape **replaces** the extractor's G/W/T, which is no longer the requirement. Q3f retitled accordingly (the old title read as a migration question and contradicted SPEC-2). Earlier in the same pass: **Q3e (b)** — story as a rollup GR `kind`, schema cost in milestone 1, producer deferred to the Q2 milestone-2 set. Earlier in the same pass: **Q3d (a)** with the (c) fallback flagged as LLM-named, which **closes §S1.11 item 2** and makes `V-SLOT-01`/`V-SLOT-02` implementable. Earlier in the same pass: **Q3c (b)** with both amendments (DMN-shaped decision-table payload; four body types), and the 0%-F1 inverted framing recorded as **normative**: the replay loop detects bad extraction, and waits if most candidate tables exceed ~6 rules. Earlier in the same pass: **Q3a (a)** — `as_built` + `statement` with split `confidence_extraction` / `confidence_intent` — and **Q3b (a)** — validator enforced, `ERROR` gates `draft`→`approved` only, nothing gates `draft`. **SPEC-1 now stands in full and unamended.** Recorded that a `statement` is normative in form but not forward-looking in provenance until the `approved` transition. Frontier 16 → 4; **Q3 branch closed in full**. |
| **2026-08-24** | User asked for evidence behind the claim that the original NNG run's cards are "richer in places". **Measured both corpora directly — the claim was false and is now corrected** (§S2.6): BASE-ENH carries `Parameters:` on 379/470 cards vs BASE-ORIG's 49, because only 55 of BASE-ORIG's 815 rules are rich cards and 760 are table rows. BASE-ORIG's real advantage is **coverage** (327 files vs 148), bought by scoped re-runs. §S2.4(6)'s triage advice was inverted and fixed. **New consequence: Q5's merge semantics are now required for coverage, not just for human judgment.** |
| **2026-08-21 (third pass)** | User approved the 29148/SBVR resolution and directed that everything be defined concretely enough for an LLM to act on → **`NORMATIVE SPEC-1`** written and **Q3b-notation** marked settled. User then committed firmly to **no migration of the existing 470/815 NNG rules**, which they become the comparison baseline instead → **`NORMATIVE SPEC-2`** written, **Q3-backfill** settled, deferred question 4 closed. |
| **2026-08-21 (second pass)** | User closed out the open-action list. **SBVR v1.0 supplied and Annex F + cl. 12.1.3/12.1.4 read (§17a-ter)** — recovers the RuleSpeak keyword table and corrects the Annex H/F confusion. **Baxter & Hendryx read in full (§18)** — SBVR-based not KDM-based, and it supplies the Q3f lint rubric. **DeCoMi downloaded from OSF and inspected (§17e-ter)** — two defects found in the published prototype that bear on its 0% F1 headline. Ross (1997) closed by the user as covered by Von Halle. **Q3l added.** Frontier 15 → 16. |
| **2026-08-21** | **Four primary sources supplied by the user and read directly**, closing the biggest provenance gaps: Von Halle ch. 2 (§17a-bis), ISO/IEC/IEEE 29148:2018 incl. Figure 1 (§7-bis), Femmer Requirements Smells (§7-ter), and van de Hoef code→DMN (§17e-bis). One correction **reversed**, one **omission closed** (29148 cl. 5.2.8), one recommendation **materially restated** (Q3c's oracle argument), **Q3k added**. Frontier 14 → 15. |

## Open actions carried forward (not questions — tasks)

1. **OPEN — owned by the user.** Acquire a CapTech-licensed 29148. The copy on disk is a third
   party's institutional download (watermarked "Brigham Young University - Idaho", IEEE Xplore,
   May 2020). Fine for verifying facts here; **not a basis for quoting in a client deliverable.**
   ~US$288, or an IEEE Xplore seat if CapTech has one. *(The user has explicitly kept this one;
   do not close it and do not re-ask.)*
2. **DONE 2026-08-21 — DeCoMi obtained and inspected (§17e-ter).** It is **not a document**: it
   is the prototype's source, prompt set, ten cases with gold-standard DMN, and every experiment
   log, published as an OSF dataset. Downloaded via the OSF API to
   `reqs-to-data-store-sources/DeCoMi.zip` (5.4 MB, 1,088 entries) + `Explanation.docx`. Two
   defects found in the published code that bear directly on its 0% F1 headline — see §17e-ter.
3. **DONE 2026-08-21 — `semdesigns_brex.pdf` read in full (§18).** It is a **30-slide 2005
   conference deck**, not a paper, and it is **SBVR-based, not KDM-based** (KDM appears once, as
   an intermediate model in the tool architecture). It supplies the best available "even perfect
   static analysis cannot do this" citation and a six-item defect rubric for machine-extracted
   rules. Text extracted to `semdesigns_brex.txt`.
4. **CLOSED 2026-08-21 by the user — will not be obtained.** Ross (1997) was wanted for the
   clause-level taxonomy one level below Von Halle's seven. The user found enough excerpts to
   conclude **the Von Halle content already covers it**. Do not re-open this lead; §17a-bis is
   the authority for the taxonomy, and §17a-ter (SBVR Annex F) now covers the RuleSpeak
   sentence forms that were the other reason to want Ross.
5. **DONE 2026-08-21 — and the premise of this action was wrong twice (§17a-ter).** The user, an
   OMG member, supplied `SBVR-1.0.pdf`. **(i) Nothing here was member-restricted** — the
   RuleSpeak material is in the *public* v1.0 spec. **(ii) The annex is F, not H** — Annex H is
   "Use of UML Notation in a Business Context to Represent Vocabularies and Rules"; Annex F *is*
   "The RuleSpeak® Business Rule Notation", so it is not a "content substitute", it is the
   source. The F.1.1 modal-operations table is recovered verbatim in §17a-ter.
6. **DONE.** Eyeball 29148 Figure 1's page image — the user supplied the figure text
   2026-08-21; two structural corrections were recorded (§7).

7. **OPEN — NEW 2026-08-24. Two Layer-0 defects that Q3h depends on had NO owning milestone
   anywhere.** Confirmed by searching every plan in `docs/exec-plans/active/` and
   `docs/exec-plans/pending/`: neither appeared as a milestone, a step, or a task — they existed
   **only as caveats in this draft**. Q3h is decided and depends on both.

   ✅ **DRAFTED the same day as Milestones 26 and 27** on
   `docs/exec-plans/active/semantic-code-search-graph-index.md` — Progress entries plus full
   `Concrete Steps` for each. **Both premises were corrected by reproducing the behavior against
   the running grammar, not by repeating the caveat:**

   **(a) M26 — `uses_table` alias binding and self-reference suppression.** A nine-line T-SQL
   probe (two `CREATE TABLE`s + a procedure with `FROM dbo.Orders o INNER JOIN dbo.Customers c`)
   yields **10 `uses_table` edges of which 5 are junk**. Aliases *are* emitted, but land
   **unresolved at confidence 0.30** while genuine tables resolve at **0.85** — so they are
   distinguishable today, which makes the fix cheaper than assumed. ⚠️ **But a confidence filter
   is the WRONG fix**: a real table with no indexed DDL (cross-database, synonym, linked server)
   is *also* unresolved at 0.30, so filtering silently discards genuine lineage. The fix is to
   **bind the alias to its table** in-statement. **A second, worse defect was found in the
   process: confident self-edges at 0.85** — `Orders → Orders`, `Customers → Customers`,
   `GetOpenOrders → GetOpenOrders`. An object's own name in its own `CREATE` becomes a usage of
   itself. The regex-recovery path already guards this
   (`test_sql_table_recovery.py::test_lineage_refs_survive_the_repair`); **the clean tree-sitter
   path does not**, which is why it survived. **This is wrong data at high confidence, not
   missing data** — the worse of the two failure modes, and the one that most directly breaks
   `NORMATIVE PRINCIPLE-1`'s promise that the computed path is trustworthy.

   **(b) M27 — unresolved-dispatch visibility.** Split into two deliverables because the premise
   was wrong: the graph **does** keep unresolved edges with `callee_name` preserved. **(a)
   Visibility, to do regardless** — an `unresolved_edges` breakdown in `stats` by `edge_kind` and
   confidence band, plus a filter, so a consumer can report a **floor rather than a total**. At
   the point of consumption an unresolved edge is today indistinguishable from an absent one, so
   every downstream count under-reports *silently*, and PRINCIPLE-1 clause 5 is unhonourable
   without it. **(b) Framework-config resolution — measure first, then decide.**
   `/modernize-map` already does this, but whether it belongs in Layer 0 is a real question
   (configuration-shaped, framework-specific, unlike the rest of the deterministic AST work).
   Scope it only after (a) quantifies how much of the unresolved population is *addressable*
   framework dispatch versus genuinely external targets that no config pass would ever resolve.

   **What remains open on this action:** the **placement decision is now made in draft form**
   (both filed on the semantic-index plan, so every consumer benefits — `table-validation`,
   `data-documenter`, `/modernize-map` — rather than coupling a Layer-1 feature to a Layer-0
   repair). **The user has not yet ratified that placement**, and this plan's ExecPlan must
   declare a **dependency on M26** in particular: until it lands, Q3h's computed block is *wrong*
   rather than merely incomplete.

**Remaining open actions: two — #1** (the user's, the 29148 licence) **and #7** (ratify the M26/M27
placement, and wire the M26 dependency into this plan's ExecPlan). Nothing in this file is blocked
on an **unread source**; #7 is blocked on a **decision**, not on research.

## Where the change lands (three code surfaces — none touched yet)

**Nothing has been implemented.** No code changed, no store schema written, and — per the
settled *Q3-backfill* decision — **no migration will ever be written**. This draft is the only
artifact.

**Git state (verified 2026-08-24):** branch **`feature/reqs-to-data-store`**; this draft **is
tracked** (first committed as `2a761e74`); `reqs-to-data-store-sources/` is **git-ignored** at
`.gitignore:98` and stays local by decision — see *Source artifacts*.

| Surface | What it does today | Detail section |
|---|---|---|
| `.claude/skills/code-modernization/` (10 `commands/` + 5 `workflows/`) | Writes `analysis/<system>/BUSINESS_RULES.md` + `DATA_OBJECTS.md`. A full JSON schema already exists at `workflows/extract-rules.js:72-169` and is **discarded on write** — this is the primary surface and the cheapest place to start. | *how requirements are stored today* |
| `.claude/skills/{detailed-req-documenter,business-documenter,use-case-generator,user-story-generator}/` | The four LegacyLift GR producers. Pure markdown→markdown, own ID schemes (`FR-`/`BR-`/`UC-`/`US-`), and **entirely disconnected** from the code-mod plugin. | *how requirements are stored today* |
| `tools/legacylift_search/` (`src/legacylift_search/store.py`) | Layer 0 — `index.sqlite` (9 tables) + Chroma. The store a GR must tie back into. Caution: every id format is line- or hash-bearing, i.e. **not edit-stable**. | *legacylift-search persistence (Layer 0)* |

## ⚠️ DEPENDENCY ON `semantic-code-search-graph-index.md` (three milestones, two of them new)

Coupled plans are listed in full at the bottom under *Related plans*, but **one plan gates work
here**: `docs/exec-plans/active/semantic-code-search-graph-index.md`. **The ExecPlan authored from
this file must declare these dependencies explicitly.**

| Milestone | Status | What it gates here | Hard or soft |
|---|---|---|---|
| **M26** — `uses_table` alias binding + self-reference suppression | **open; drafted 2026-08-24** (open action #7) | **Q3h's computed `reads[]`/`writes[]` block.** Until M26 lands, that block is **WRONG, not merely incomplete** — it emits alias names (`o`, `c`, `po`) as datastores and confident 0.85 self-edges (`Orders → Orders`). | **HARD.** Shipping Q3h's computed block before M26 breaks `NORMATIVE PRINCIPLE-1`'s core promise that the computed path is trustworthy. Either M26 lands first, or the block ships **disabled** — never with known-junk values. |
| **M27** — unresolved-dispatch visibility | **open; drafted 2026-08-24** (open action #7) | **PRINCIPLE-1 clause 5** ("report the inference rate") for Q3h. Part (a) is what lets the block report a **floor rather than a total**; without it an unresolved edge is indistinguishable from an absent one at the point of consumption, so the under-report is silent. | **SOFT for correctness, HARD for the honesty claim.** Q3h's `llm_inferred` fallback still functions without M27, but the coverage story cannot be stated truthfully. |
| **M21** — does the index beat `fact-graph`? | **open** (unchanged) | **Q7** — whether this plan is the vehicle for the fact-graph decision. | **SOFT.** Q7's recommendation is to proceed additively and *not* retire fact-graph, precisely so M21 stays an honest evaluation rather than a fait accompli. |

**Already-shipped dependencies (no gate, but name them):** **M24** (`has_column` facts +
`foreign_key` edges, shipped 2026-07-17, `6b9ac4b3`) is the substrate for Q3h's column-level
precision — at-scale validation on `ctcm-db` is still deferred. **M22–25** and domain tagging are
what make Q3d's derived `[Subject]` possible at all.

## ⚠️ THREE UNOWNED LAYER-0 PIECES THIS PLAN DEPENDS ON BUT DOES NOT OWN (2026-08-25)

Distinct from the M26/M27/M21 table above: those are **filed milestones**. These three are
**documented to file-ready detail but deliberately NOT filed** (owner decision 2026-08-25 —
"no need to file a+b as milestones yet, just make sure all info is documented to allow for that
decision later"). Consolidated in **`fact-graph-decision.md` §5a.6**. **The ExecPlan must declare
the dependency and must NOT absorb the repair** — same placement logic as M26/M27: they are Layer-0
defects, and fixing them there benefits every consumer.

| Piece | What | Spec written | Gates Milestone 1? |
|---|---|---|---|
| **(a)** | Pack-emitter shim — write `legacylift-docs/context/` from Layer 0 | `fact-graph-explanation.md` §9.7 — measured field-level contract | **No.** Gates fact-graph *retirement* and **M21's ability to conclude "replace"** |
| **(b)** | Semantic-typing pass over Layer-0 symbols | `fact-graph-explanation.md` §9.8 — 8 `type` values with the M22–M25 signal for each | **No.** Gates `find_entities_by_type`, the only Phase-0 helper Layer 0 cannot answer |
| **(e)** | **Re-key `symbols.id` so the PK is not line-bearing** | `fact-graph-decision.md` §5a.6.1 — surface-by-surface scope | **No** — §S3.3's advisory-link design insulates the GR store |

**(e) is the one to understand before writing the ExecPlan**, because it is easy to over-state what
Milestone 1 delivers. **`anchor_key` gives Layer 0 a stable key; it does not make Layer 0 stably
keyed.** SPEC-3 §S3.1 now says this explicitly. Two consequences to carry into the ExecPlan:

1. **Do not claim the ExecPlan "fixes Layer-0 stable IDs."** It adds a position-independent key and
   discharges `fact-graph-decision.md` residue **(c)**; the primary key stays line-bearing.
   ⚠️ `fact-graph-decision.md` §7 open question **#6** was recorded as fully answered and has been
   **re-scoped to half-answered** as a result.
2. **(e) became implementable only via this plan's own Milestone 0.** D3 builds `PRAGMA
   user_version` + forward-only migrations for both DBs; before it there was no `ALTER TABLE` in
   `src/` at all, so (e) was not merely unowned — it was unimplementable. **Worth stating as a
   downstream benefit of Milestone 0.**

⚠️ **And whatever else (e) rides on, it needs an edit-and-reindex verification of its own** —
SPEC-3 §S3.7 records that this identity design has **never** been exercised that way, by fact-graph
(which regenerates wholesale) or by Layer 0. Do not let it ride along on Milestone 1's tests.

**Placement note (open action #7, awaiting user ratification):** M26 and M27 are filed on the
semantic-index plan rather than absorbed into this one, because they are **Layer-0 defects** and
fixing them there benefits every consumer (`table-validation`, `data-documenter`,
`data-dictionary-generator`, `database-layer-documenter`, `/modernize-map`). This plan declares a
dependency; it does not own the repair.

## Section map (~5,800 lines — read the row you need, not the file)

| What you need | Section |
|---|---|
| **The question set to present first** | **ROUND 2 — D2, D3, D7**, in **Deferred Questions** (promotion table at the top of that section). Both numbered sheets at the top of the file (**Q4–Q7** and **Q3**) are **ARCHIVES** — all twenty are answered. After round 2: confirm shared understanding, then author the ExecPlan |
| **The one general design principle, applying to fields not yet designed** | **NORMATIVE PRINCIPLE-1 — Provenance Discipline**. Deterministic first; LLM only on silence; never blended; never in a computed total; report the inference rate |
| **What this plan depends on in another ExecPlan** | **⚠️ DEPENDENCY ON `semantic-code-search-graph-index.md`** — M26 (hard: Q3h's computed block is *wrong* without it), M27 (soft for correctness, hard for the honesty claim), M21 (soft, Q7 only) |
| **The full shape of the settled design in one table** | **START HERE**, "The twenty settled decisions" + "Milestone sequencing implied by the settled set" |
| **Measured comparison of the two NNG baselines, and why they differ** | **§S2.6** — field-presence counts, paired card examples, coverage-by-layer, and the two documented causes |
| The reasoning behind Q4–Q7 (all answered) | **Open Frontier** — now **EMPTY / background only**; every question in it, Q3 and Q4–Q7 alike, is decided. The **Decision Log** is the authority |
| What happened on which date, and outstanding non-question tasks | **Session log** + **Open actions carried forward** |
| The consolidated GR candidate field list (provenance + who fills each field) | **Q3**, "Candidate field list" — the concrete thing to react to |
| What is already settled and must not be relitigated | **Decision Log (SETTLED)** — **twenty entries**: Q1, Q2, **Q3-backfill**, **Q3b-notation**, **all twelve of Q3a–Q3l**, and **Q4, Q5, Q6, Q7** |
| **The notation, defined normatively for an implementer** | **NORMATIVE SPEC-1 — Requirement Notation**, near the end of the file. Keyword strings, `pattern` enum, `rule_class` procedure, ~25 numbered validator rules, deviation register D1–D6. **All three §S1.11 blockers closed 2026-08-24 — fully implementable, no open dependencies** |
| **How identity, citations and dedupe work** | **NORMATIVE SPEC-3 — Identity and Deduplication**. The four keys (`gr_id` / `dedupe_key` / `anchor_key` / `content_hash`), the drift-vs-clone 2x2, why `statement` and `subject` are excluded from `dedupe_key`, the two-stage merge, and the domain-retag invariant test |
| **How the new output is judged against the old NNG runs** | **NORMATIVE SPEC-2 — Baseline Comparison**. Baseline paths and shapes, the join key, the four buckets, and the interpretation rules that constrain what may be claimed |
| Current rule-card template, machine schemas, complete consumer list, and how real output (815 rules) diverges from the template | **Facts Established — how requirements are stored today** |
| Layer-0 tables, id formats, 15 CLI subcommands, what Chroma holds | **Facts Established — legacylift-search persistence (Layer 0)** |
| Notation survey — KDM, contracts, goal models, Planguage, 29148, Volere, ReqIF, Rupp, Withall, SCR | **Facts Established — requirements notations beyond EARS and GWT**, §§1–13 |
| Why the plan must not claim accuracy (no oracle, ~29% precision) | §15 |
| SBVR modality, DMN hit policies, and the decision-table extraction void | §17 — incl. **§17e-bis**, the only code→DMN paper, read in full, and why it restates Q3c |
| What the field actually produces ("code snippets or graph slices") and the 26-year-old gap | §19 |
| My design conclusions, for the user to accept or reject | §20 |
| Questions identified but deliberately not yet asked | **Deferred Questions** — ⚠️ **now the live frontier**: **D2, D3, D7** open; **D1 closed → SPEC-3**; D5/D6 still deferred; D4 closed |
| Traps to check before running anything in this repo | **Environment notes / gotchas** |
| AWS Transform / Kiro findings, EARS reference facts, the EARS+GWT evidence | **Facts Established (2026-08-19 exploration)** |
| Which sources are VERIFIED vs second-hand, and what is safe to quote in a client deliverable | **§7-bis** (29148), **§7-ter** (Femmer), **§17a-bis** (Von Halle) — all three read directly 2026-08-21 |

## Interview method (for whoever resumes)

This is a **design-tree interview**. Decisions are asked in rounds; each round asks every
question whose prerequisites are already settled (the "frontier"), numbered, each with a
recommended answer. The user answers; the tree is recomputed; the next round is asked.
**Facts are never asked of the user** — they are looked up in the environment or researched.
(Example: when D2 was presented, "what is committed today?" was answered by inspecting
`.gitignore` and `git ls-files`, not by asking.) The interview is complete when the frontier is
empty. ⚠️ **It is not yet: closing Q4 and Q7 on 2026-08-24 promoted D1, D2, D3 and D7. D1, D2 and
D3 are now closed — `D7` alone remains.** Recompute the tree after every round; D7 closing may
promote D5/D6.

Question format used throughout:

    ❓ **Q<n>** - **<title>**: <body, options>

    ➡️ <recommended answer>

## Corrections made during this session — do not reintroduce these

| Claim originally made | Status |
|---|---|
| SPEC-3 §S3.1/§S3.6 "must ride the pack-emitter shim so the 13 Phase-0 consumers see one migration" | **OVER-CLAIMED — re-scoped 2026-08-25 by D7.** `.claude/skills/fact-graph/SKILL.md` has **zero** references to `legacylift-search`, `index.sqlite` or `symbols`; it mints its own ids (`:912`, `:942-947`). Adding `anchor_key` to `symbols` is **invisible to fact-graph and all 13 consumers**, and no Layer-0 pack emitter exists. `anchor_key` ships additively in Milestone 1; the pack-format re-keying is a *future* obligation of residue **(a)**. |
| fact-graph's "interpretive half of the predicate enum" (`integrates_with`, `state_transition`, `publishes_to`, `validates`, `ensures`, …) is a real capability the GR store must cover or lose | **REFUTED BY MEASUREMENT 2026-08-25.** Counted over the only tracked run (`ctcm-api`, 38,618 facts): those ~18 predicates emitted **0 facts each**. fact-graph emitted **5 of ~45** predicates; `has_property` alone is 89.3%, and the only non-AST-derivable one is `business_rule` at **620 facts / 1.6%**. True of the schema, false of the output. See `fact-graph-explanation.md` §9. |
| fact-graph emits no entity `content_hash` (claimed by me 2026-08-25, first pass) | **WRONG — MY ERROR, corrected the same day.** The field is `attributes.content_hash`, not top-level, and the first check only looked at the top level. It is present on **6,047/6,047** (12 hex, 5,888 distinct; the 159 repeats are clones, not collisions), and differs from the id's trailing hash on all 6,047. **So `fact-graph-decision.md` §5 claims 3/5 and §5a.1 items 3/5 STAND**, and **identity is a non-differentiator in both directions.** SPEC-3's keys remain better *constructed* — `` delimiter (fact-graph joins with `:`, which occurs inside both `qualified_name` and `file_path`), coarse `entity_class` over the volatile raw `entity_type`, 16 hex over 12, `domain` excluded rather than in the visible id prefix — but that is construction quality, not a capability gap. **Do not cite "fact-graph has no content hash" anywhere.** |
| fact-graph's `technical_layer` axis "largely failed… nearly every C# entity is tagged `Other`" (`fact-graph-explanation.md` §6.2 item 4) | **REFUTED BY MEASUREMENT 2026-08-25.** `Other` is **925 of 6,047 = 15.3%**; the axis resolved for **84.7%** (`Dto` 2,352 · `Model` 1,398 · `Web` 926 · `Service` 332 · `Persistence` 114). It is a **working** secondary axis, and a seventh thing Layer 0 does not produce. See `fact-graph-explanation.md` §9.6. |
| fact-graph is **language-agnostic**, so a VB6 / PL-SQL / Delphi / ABAP repo is a genuine fact-graph-only case | **WRONG — owner correction 2026-08-25, then verified.** Its extraction logic is **hardcoded per-language `grep` blocks in `SKILL.md`** (§2.2, `:653-775`: C#, Java, Python, TS/JS, SQL); the *Other Languages* hatch (`:769-772`) is one sentence with **no patterns**. Mentions: Java 52, Python 37, SQL 26, C# 15 — **VB6/Delphi/ABAP/PL-SQL/COBOL: 0**. An unlisted language is an **extension point, not a capability**. **"Zero install" is the half that survives.** |
| SCR/Parnas tables are the strongest prior art for tabular *business* requirements | **REFUTED.** Reverse-documentation precedent is real and citable; tabular *transferability* is not. Heninger's own limitation, plus zero business-IS applications in 45 years, plus the McMaster group switching to dependency analysis for enterprise legacy. See §13. |
| ISO/IEC/IEEE 29148 is "not a competing syntax", only quality characteristics | **HALF WRONG, and more so than first recorded.** It prescribes a sentence construct (cl. 5.2.4, Fig. 1), a normative banned-term list (cl. 5.2.7), a *Conforming* characteristic requiring template conformance (cl. 5.2.5), **and an attribute list (cl. 5.2.8)**. Verified against the standard 2026-08-21. See §7 and §7-bis. |
| A ReqIF exporter lets clients load output straight into DOORS/Jama/Polarion; "costs one exporter" | **TOO OPTIMISTIC.** Structural core travels; XHTML, tables, cross-document links and tool extensions lose data. Spec itself instructs agreeing capabilities *before* exchange. See §9. |
| EARS + G/W/T pairing is "weakly supported" by published guidance | **WEAKER THAN THAT.** No authoritative source pairs them; the EARS canon is verifiably silent on BDD. Kiro and AWS both use EARS *instead of* G/W/T. Our composite is defensible by reasoning, not citation. See "On pairing EARS with Given/When/Then". |
| Von Halle's taxonomy includes "mandatory constraint" | **CORRECT after all — verified from the book 2026-08-21.** `constraint` is the parent ("a mandatory restriction or suggested restriction"); **`mandatory constraint` is the leaf** used in Tables 2.2/2.3. The earlier "UNVERIFIED" flag was over-cautious; both terms are real at different levels. See §17a-bis. |
| DMN gives mechanical gap/overlap checking | **TRUE OF TOOLS, FALSE OF THE STANDARD.** The spec supplies predicates and one `SHALL`, deleted its only completeness construct in 1.1, and leaves the algorithm to vendors. Drools/KIE is the real implementation. See §17b. |
| DMN has a 1.7 beta | **NO.** Current formal is 1.5, `formal/24-01-01`, Aug 2024. There is no 1.7 document. |
| Rupp/SOPHIST has a shall/should/will decision tree | **UNVERIFIED — do not assert.** SOPHIST presents the three as parallel definitions. Their real discriminator is the FALLS/SOBALD/SOLANGE condition split. See §10. |
| Chikofsky & Cross 1990 says documentation is typically absent | **DO NOT ATTRIBUTE.** The paper contains no such statement. |
| The original NNG run's cards are "richer in places" and carry `Parameters:` content the enhanced run dropped | **REFUTED BY MEASUREMENT 2026-08-24.** Both halves are false. `Parameters:` appears on **379 of 470** enhanced cards vs **49** in the original, because only 55 of the original's 815 rules are rich cards — the other 760 are table rows with no parameters, edge cases or confidence at all. Card for card the enhanced run wins; the original's only advantage is **file coverage** (327 vs 148), and that was bought by scoped re-runs, not better extraction. See §S2.6. **This briefly produced inverted triage advice in §S2.4(6); do not reintroduce it.** |
| SBVR Annex H is member-restricted and holds the RuleSpeak sentence forms; Annex F is a "content substitute" | **WRONG TWICE.** Annex H is *Use of UML Notation in a Business Context*. **Annex F IS the RuleSpeak annex**, and it is in the public v1.0 spec — nothing was restricted. Verified 2026-08-21. See §17a-ter. |
| Baxter & Hendryx is "the KDM/SBVR angle nobody else took" | **HALF WRONG — it is SBVR, not KDM.** KDM appears once, as an intermediate model in the tool-chain diagram (slide 18). The "standard" of the title is SBVR, and Hendryx co-submitted it. See §18. |
| van de Hoef's 0% decision-rule F1 is the ceiling for LLM code→DMN | **NOT ESTABLISHED — it is a floor from a defective harness.** Reading the published prototype shows the decision-table call discards the five-turn elicitation chain that precedes it, and the completeness answer it asks for is computed and never read. The strongest version of their own method was never run. The *practical* conclusion for us is unchanged — measure on our own corpus — but do not cite 0% as an inherent limit. See §17e-ter. |
| 29148 has no attribute list | **OMISSION, now closed.** The draft had no cl. 5.2.8. It is a **requirements attribute list** (Identification, Version Number, Owner, Stakeholder Priority, Risk, Rationale, Difficulty, Type) overlapping most of Q3's candidate field list. See §7-bis. |

## Source artifacts (on disk, untracked)

`docs/exec-plans/pending/reqs-to-data-store-sources/` — primary sources downloaded and read
during this session, kept so they need not be re-fetched (DTIC returns HTTP 403 to automated
fetches; the session WebSearch budget was exhausted at 200/200):

| File | What it is | Read? |
|---|---|---|
| `normantas_slr.pdf` / `.txt` | Normantas & Vasilecas 2013 SLR, 24 papers — the "code snippets or graph slices" finding (§19) | **read** |
| `semdesigns_brex.pdf` / `semdesigns_brex.txt` | Baxter & Hendryx (Semantic Designs + Hendryx & Associates), "A Standards-Based Approach to Extracting Business Rules", 2005 — a **30-slide deck**, not a paper | **read in full 2026-08-21 (§18).** The KDM implication in the title was wrong: it is **SBVR**-based |
| `cosentino_wcre2013.pdf` / `cosentino.txt` | Cosentino et al., WCRE 2013 COBOL business-rule extraction | not read in full |
| `hatano2016.pdf` / `.txt` | Hatano et al. 2016, conditional-statement extraction | not read in full |
| `DTIC_ADA273362.txt`, `DTIC_ADA272179.txt` | NIST/NASA formal-methods survey, vols 1-2 — Darlington/CICS/TBACS/SACEM figures (§19) | key passages read |
| `Von-Halle-Business_Rules_Extracted_and_Restructured.docx` / `Von-Halle-ch2.txt` | **Added 2026-08-21 by the user from a print copy.** *Business Rules Applied* (Wiley, 2001) ch. 2 — the seven-classification taxonomy, Table 2.2/2.3 templates, Figure 2.3 expression forms | **read in full (§17a-bis)** |
| `ISO-29148-Requirements-Engineering.pdf` / `ISO-29148.txt` | **Added 2026-08-21.** ISO/IEC/IEEE 29148:2018(E), 2nd ed. 2018-11 — the actual standard | **read: cl. 5.2.4–5.2.8 verified (§7-bis)**. ⚠️ watermarked "Brigham Young University - Idaho" IEEE Xplore copy — **not a CapTech licence; do not quote in a deliverable** |
| `RapidQualityAssurancewithRequirementsSmells.pdf` / `femmer_smells.txt` | **Added 2026-08-21.** Femmer et al., Requirements Smells — arXiv:1611.08847v1 preprint of the JSS 2017 paper | **read: 59%/82% verified (§7-ter)**. Openly licensed, safe to quote |
| `Applying LLMs for Automated Extraction of Business Logic.pdf` / `vandehoef_dmn.txt` | **Added 2026-08-21.** van de Hoef et al., the only code→DMN paper in existence (SSRN 6299556) | **read in full (§17e-bis)**. Was the top unread item in this file; it is now closed |
| `SBVR-1.0.pdf` / `SBVR-1.0.txt` | **Added 2026-08-21 by the user (OMG member).** OMG *Semantics of Business Vocabulary and Business Rules* v1.0 — the actual specification | **read: Annex F.1.1, cl. 12.1.3, cl. 12.1.4 verified (§17a-ter)**. OMG specs are freely redistributable under the OMG licence, so this one is safe to quote |
| `DeCoMi.zip` / `Explanation.docx` | **Added 2026-08-21**, downloaded from OSF (van de Hoef, 2025) via the API. The DeCoMi prototype: `back-end/` (4 pipeline steps + Flask API), `front-end/`, `data/case1–10` (Java + gold-standard `.dmn` + DRD/decision-logic JSON + rendered PNGs), `experiment/` (945 files of GPT-4.1 and Gemini 2.5 Pro queries and results) | **inspected 2026-08-21 (§17e-ter)**: all four prompt files read; `experiment/` logs not read. Openly licensed research artifact |

**DECIDED 2026-08-21: this directory is git-ignored and stays local.** The rule is
`docs/exec-plans/pending/reqs-to-data-store-sources/` in `.gitignore:98`. Reason: it holds a
**licensed standard** (ISO/IEC/IEEE 29148:2018, and a third party's watermarked copy at that)
and an **excerpt from a copyrighted book** (Von Halle) — neither is redistributable. The draft
that cites them *is* tracked, so a fresh clone gets the findings and citations but not the
source files. **Do not re-raise this question, and do not `git add -f` anything in there.**
If you need a source a clone does not have, re-acquire it from the publisher.

⚠️ Consequence for a resumer on a fresh clone: every "read from the primary source" claim in
this file (§7-bis, §7-ter, §17a-bis, §17e-bis) is **verified but not re-verifiable locally**
until you obtain the source yourself. The verbatim quotes were transcribed while the files were
in hand; trust them for planning, re-acquire before printing any of them in a deliverable.

## Known research gaps (deliberate, recorded rather than hidden)

1. **The business-rule-extraction literature's detailed survey was lost.** Its agent
   delivered a main report twice that never reached the session, and its transcript was
   deleted before it could be re-requested. Lost: the detailed Sneed lineage, the
   slicing-to-rule-extraction chain, per-paper notation breakdowns, the commercial-tool
   claims (Micro Focus/OpenText EA, IBM ADDI, CAST, EvolveWare, Semantic Designs, Blu Age,
   Heirloom), and the fuller LLM-era treatment. **The most important part was recovered
   independently** by reading `normantas_slr.pdf` directly (§19). To close the rest, read
   the on-disk PDFs — do not re-delegate.
2. **SBVR section A detail arrived truncated.** What survives (§17a) covers the
   definitional-vs-behavioral distinction, the alethic/deontic mapping, and the
   enforcement-level caveat — enough to decide on. The verbatim RuleSpeak sentence forms and
   SBVR modality keyword table were lost.
3. **Unverified items are flagged inline** with ⚠️ throughout the Facts sections. Anything
   destined for a client deliverable needs re-verification against a purchased or
   library copy.
4. **CLOSED 2026-08-21 — three of the biggest gaps.** Von Halle ch. 2 (§17a-bis), the 29148
   standard itself (§7-bis) and the Femmer smells paper (§7-ter) are now on disk and were read
   directly. Every quote this plan leans on from those three is verified. Figure 1 was
   closed separately on 2026-08-21 when the user supplied the figure text (§7 — it corrected
   two structural details). **One caveat survives:** the 29148 copy is a third party's
   institutional download, so acquiring a CapTech-licensed copy is still an open action before
   any client deliverable quotes it.

## Deliverable-shaping conclusions worth carrying forward

Three findings are strong enough to shape what the plan *claims*, independent of how the open
questions resolve:

- **The gap is 26 years old and acknowledged three times** — GUIDE/Business Rules Group
  (2000, objective unmet), Normantas SLR (2013, "not acceptable solution"), and this survey
  (2026, one unrefereed preprint for code→DMN, nothing for decision tables). Best available
  answer to "why do this at all", and every link is citable.
- **There is no oracle for extraction quality** — no benchmark, no ground truth, and ~29%
  precision in the one honest published measurement (Chaparro et al., WCRE 2012). So the
  plan must not claim accuracy; it should claim *auditable completeness* (Q3g) and *accumulated
  human judgment* (Q5). See §15.
- **Intent is information-theoretically absent from code** (Leveson et al., TSE 1994, on
  TCAS II). `rationale` is therefore a field the SME fills, not one the extractor populates —
  which reframes it as the field that *structures the SME conversation*. See §13.

---

## Goal

Change the storage mechanism from the code-modernization plugin's current approach of
storing generated requirements in MD files to storing them in a data store.

## Requirements for implementation

- A Generated Requirement (GR) (to disambiguate from the feature implementation
  requirements) must tie back to any/all code chunks in SQLite/ChromaDB.
- The previous requirement also means a GR is associated with one (possibly but not
  often more than 1) domain.
- **The ExecPlan must declare a dependency on `docs/exec-plans/active/semantic-code-search-graph-index.md`
  — specifically M26 (hard), M27 (soft), and M21 (soft for Q7).** See the ⚠️ *Dependency* section
  near the top of this file for what each one gates. **M26 is the load-bearing one:** Q3h's
  computed `reads[]`/`writes[]` block must not ship enabled before it, because it would emit
  known-junk table names and break `NORMATIVE PRINCIPLE-1`.

## Original Open Questions (from the pre-interview draft)

1. What data store? SQLite, Chroma DB? What are the pros/cons of each?
   → Now **Q4** in the interview. Recommendation given; awaiting answer.
2. What form for requirements? Code-mod uses Given/When/Then. AWS Transform creates a
   User Story with requirements defined using EARS (Easy Approach to Requirements
   Syntax). → Now **Q3** and its sub-branches **Q3a–Q3l**; **restated 2026-08-20**, extended
   2026-08-21, after the
   survey of notations beyond EARS and GWT completed. Still open.
3. Does AWS Transform do anything interesting with extraction and/or requirements
   generation that we do not?
   → **ANSWERED by research.** See "Answer to draft open question 3" below.
4. Are we incorporating everything (all the information, etc.) that is available via
   legacylift-search? → **NOT YET ASKED.** Deferred to a later round; the Layer-0
   surface is now fully mapped (see the persistence facts below), so this becomes a
   concrete per-table/per-edge-kind checklist question.

---

# NORMATIVE PRINCIPLE-1 — Provenance Discipline (NAMED 2026-08-24)

> **Status: NORMATIVE, and general.** Identified by the user on 2026-08-24 after it had already
> been applied **three times independently** without being named. It is **not** a property of the
> questions that produced it — it governs **every field, every metric and every rendered
> artifact** in this store, including ones not yet designed. **Apply it by default; deviating from
> it requires a recorded justification.**

## P1.0 Statement

**For any value that could come from either a deterministic source or a language model:**

1. **Prefer the deterministic source.** If Layer 0, a schema, a config file or a computation can
   produce the value, that is the value. The LLM does not get a vote.
2. **Permit the LLM only where the deterministic source is SILENT** — never where it merely
   disagrees, and never as a supplement to a non-empty deterministic result.
3. **Never blend the two in one undiscriminated field.** Every value carries a **provenance
   discriminator** naming which path produced it.
4. **Never let an inferred value enter a computed total.** Counts, coverage figures, percentages
   and completeness claims default to deterministic entries only; inferred entries are available,
   but **labelled**, and never silently folded in.
5. **Report the inference rate.** The proportion of values that fell back to the LLM is itself a
   quality signal — usually it means a deterministic source is blind somewhere. Surface it
   rather than papering over it.

## P1.1 Why — the three sources this rests on

- **§15, the oracle problem.** There is no benchmark, no ground truth and ~29% precision in
  the one honest published measurement. **Only deterministic numbers are self-reportable.** Any
  claim built on LLM judgment is unfalsifiable, so mixing the two contaminates the half that was
  defensible.
- **SparseAlign's circular evaluation loop.** Organizations "risk a circular evaluation loop,
  where unverified LaaJs are used to assess model outputs." AgentModernize's 92.3%/90.2% is the
  worked example of getting this wrong — its oracle was seeded by an LLM reading the very code
  the pipeline was scored on.
- **TCAS II (§13).** Intent is information-theoretically absent from code. Where the record
  cannot know something, **the schema's job is to have somewhere to put that absence**, not to
  have it filled in plausibly.

## P1.2 Where it is already applied (all three predate the naming)

| Decision | Deterministic source | Fallback, and how it is marked |
|---|---|---|
| **Q3a** | `as_built`, cited to code, `confidence_extraction` | `statement` + `confidence_intent`, **SME-only**; `rationale` / `fit_criterion` **extractor-forbidden and empty by design** |
| **Q3d** | `[Subject]` from `file_domains` | LLM-named component, **only** when the file is `unassigned`, **flagged** as LLM-named |
| **Q3h** | `reads[]` / `writes[]` from Layer-0 edges, `uses_table`, M24 `has_column` | per-entry `provenance` = `llm_inferred` + an `explanation`, **only** where the graph is silent; excluded from computed totals |
| **Q3g** | chunk coverage + `disposition`, both computed | — (no LLM path at all; this is the pure case the others degrade toward) |

## P1.3 How to apply it to a field that does not exist yet

Ask, in order: **(1)** Can a deterministic source produce this? If yes, that is the only path.
**(2)** If not, is the right answer *emptiness* rather than a guess — i.e. is this an SME field
(Q3j) rather than an inference field? **(3)** Only if a guess is genuinely better than a blank:
add the provenance discriminator, an explanation slot, exclusion from totals, and a reported rate.

**Three is the last resort, not the default.** Q3j's whole argument is that an empty field is a
feature: 29148 cl. 5.2.7 makes documenting assumptions a normative `shall`, and a blank
`rationale` is an honest review-progress signal where a fabricated one is a lie with a citation.

---

# Decision Log (SETTLED)

## Q1 — Store is the source of truth: **DECIDED (a)**

The data store is the **source of truth**. Markdown (`BUSINESS_RULES.md`,
`DATA_OBJECTS.md`) becomes a deterministic **render/export** from the store, not the
system of record. The .md deliverable does not go away — it stops being the database.

Supporting fact: `workflows/extract-rules.js:72-114` already defines and validates a
full `RULES_SCHEMA` (14 fields/rule) plus `DTO_SCHEMA`, and the calling session
**discards the structured form** after rendering markdown. Persisting it is not a
rewrite; it is keeping what the pipeline already produces.

## Q2 — Scope of generators: **DECIDED (b as model, a as first milestone)**

Model the GR schema generically — a business rule, a user story, and a use case are all
GR records distinguished by a `kind` discriminator — but wire only
`/modernize-extract-rules` end-to-end in the first milestone. The remaining GR
producers (`detailed-req-documenter`, `business-documenter`, `use-case-generator`,
`user-story-generator`) come in a **future milestone** of this same plan, against the
already-generic schema.

Explicitly out of scope: `ASSESSMENT.md`, `topology.json`, `PREFLIGHT.md`,
`SECURITY_FINDINGS.md`, `DELTA_CATALOG.md` — these are not requirements.

---

## Q3-backfill — no migration, ever: **DECIDED 2026-08-21 (firm commitment)**

**The existing NNG rule corpora will NOT be migrated into the store. Not by translation, not as
legacy records, not partially.** The store starts empty. Every record in it is born under
`NORMATIVE SPEC-1` from a fresh extraction run.

**Instead, the two existing corpora become the comparison baseline** for the new feature's
output. Full method: `NORMATIVE SPEC-2 — Baseline Comparison`, near the end of this file.

**This was the user's decision on 2026-08-21, made as a firm commitment.** Do not re-open it, do
not propose a partial import, and do not write a migration path "just in case" — an unused
migration path is a liability that invites someone to run it.

**What it closes and simplifies:**

- **Deferred question 4 (backfilling the existing corpus) is CLOSED.** It was the only question
  gated on reconciling the old card shapes.
- **No legacy tier, no statement-less records, no `rule_class = NULL` population.** SPEC-1's
  §S1.11(1) problem disappears: nothing arrives that cannot satisfy the validator, so the
  `approved` gate is meaningful from the first record rather than from some future cleanup.
- **No id-reconciliation problem.** `grep -c "RULE-"` is **0 in both** existing files, so there
  were never stable ids to migrate; that is now moot rather than a hazard.
- **The first milestone shrinks.** No importer, no shape-translation logic, no dual-format
  renderer, no "which is authoritative" conflict rule between imported and generated records.
- **Q5's merge semantics stay in scope but start clean** — merge-with-dedupe applies to
  re-extraction runs against a store the new pipeline itself populated, not to reconciling two
  foreign formats.

## Q3b-notation — how 29148 and SBVR compose: **DECIDED 2026-08-21**

**Not a frontier question — settled, and specified.** Q3b's recommendation was "implement
29148". §17a-ter then found that 29148 cl. 5.2.4 and SBVR Annex F.1.1 **disagree on four of five
modal keywords**, because 29148 is a system-requirements standard with no concept of a
definitional rule and ours are business rules.

**Decided:** keep 29148 for the slot skeleton, the mandatory subject, the nine vagueness classes,
*Singular*, *Conforming* and the cl. 5.2.8 attributes; take the **modal verb from SBVR, selected
by `rule_class`**; and record the departures as an explicit deviation register. This is
legitimate rather than a fudge because cl. 5.2.5 *Conforming* requires conformance to "**an**
approved standard template", not to Figure 1.

➡️ **The full definition is `NORMATIVE SPEC-1 — Requirement Notation`, near the end of this
file.** It is normative: exact keyword strings, the ten-value `pattern` enum, the `rule_class`
decision procedure, ~25 numbered validator rules with fixed severities, the six-value
`enforcement_level` enum, and deviations D1–D6. **Implement it literally; do not paraphrase it.**

**What remains open in Q3b:** only whether the validator **blocks** (recommended), **warns**, or
does not exist. SPEC-1 is written for the blocking case and degrades cleanly to warn-only.

---

## Q3a — Split observed behavior from intended requirement: **DECIDED (a) 2026-08-24**

Every GR carries **two** statement fields, not one blended field:

- **`as_built`** — descriptive, cited, "the code does X". Gannod & Cheng's "as-built
  specification". **Exempt from SPEC-1 validation** (§S1.7 item 5) — forcing it into a normative
  template would destroy the distinction this decision exists to create.
- **`statement`** — normative, "the <subject> must/always X", conforming to a SPEC-1 `pattern`.

Each carries **its own confidence**: `confidence_extraction` ("is the citation faithful" —
extractor/referee) and `confidence_intent` ("is this the business's intent" — **SME only**). The
existing `suspectedDefect` becomes the flag that the two halves diverge, and gains meaning it did
not have while one `Confidence: Medium` field carried both questions across 470 rules.

Option (c) — separate Observation and Requirement record types linked m:n — was rejected: it
doubles the review surface and join complexity for a distinction that is 1:1 in the overwhelming
majority of cases.

**Evidence:** five independent precedents (Leveson TSE 1994 / TCAS II, Chaparro WCRE 2012,
Feathers 2004 p.188, KAOS DomPre-vs-ReqPre, Gannod & Cheng) plus two measured error rates
(Chaparro's 36% "implementation rules"; van de Hoef's LLMs "had difficulty separating the source
code from the decision made in the source code"). This is the best-evidenced item in the plan.

**Consequence recorded during the decision (2026-08-24):** `statement` is normative in *form* but
not forward-looking in *provenance* — it is reconstructed from `as_built` by an extractor that
cannot see intent. The "must" is asserted, not authorized. It becomes a genuine forward-looking
requirement on the target system only at the `approved` transition, once an SME has set
`confidence_intent` and filled `rationale`/`fit_criterion`. **Therefore an unapproved `statement`
must never be rendered in a client-facing deliverable without its status** — doing so is exactly
Feathers' failure mode, silently promoting a latent defect to a requirement.

## Q3b-strictness — the validator is enforced: **DECIDED (a) 2026-08-24**

**Q3b is now fully settled.** Its notation half was settled 2026-08-21 (`NORMATIVE SPEC-1`); this
closes the remaining half.

**Decided: (a) enforced.** SPEC-1's `ERROR` findings **block the `draft` -> `approved`
transition and nothing else** (§S1.9). `WARN` findings never block. **Nothing gates `draft`** — a
bad extraction must still land, because the data is the point and §15 says extraction quality
cannot be assumed. SPEC-1 stands exactly as written; no `ERROR` is downgraded to `WARN`.

**Why the false-positive evidence does not defeat this.** Femmer reports 59% precision / 82%
recall (and from the superseded 2011 edition), and SCR's own authors warn that "requiring
determinism can lead to overspecification". Both numbers come from tools that blocked at
*authoring* time. Gating `approved` instead means a false positive costs an analyst one dismissal
at review time and **never loses data** — a materially different risk profile. The upside is
SCR's: 17 coverage + 57 disjointness errors found in 245 seconds on the A-7E document *after* two
expert teams had reviewed it.

**Consequences:**
1. `pattern` is `NOT NULL` on every GR that is a rule, and cl. 5.2.5 *Conforming* is satisfied.
2. Findings are stored per GR as `(rule_id, finding_id, severity, span)`; the gate is one
   `NOT EXISTS (... severity='ERROR')`.
3. Findings are also written to 29148 cl. 5.2.8's **`risk`** attribute — an SDO-sourced home for
   the flag, not an ad-hoc error field.
4. **Two SPEC-1 rules remain unimplementable until other frontier questions land:**
   `V-SLOT-01`/`V-SLOT-02` need **Q3d**'s subject naming authority (until then they detect
   absence but not correctness), and `V-STY-03` cannot be fully resolved until **Q3l** supplies a
   vocabulary layer. Both are known and recorded in §S1.11 — they are not blockers on the
   decision.
5. Severities are frozen: no validator rule may be added, removed, or resevered without amending
   SPEC-1.

---

## Q3c — Typed bodies: **DECIDED (b) 2026-08-24, with both amendments**

**Decided: (b) — one generic `structured_body` JSON column, schema-validated per type**, with
the two amendments the restatement attached:

1. The **`decision_table`** payload is **DMN-shaped** (serializable to DMN 1.5 XML), not ad hoc.
   Executability is the entire point of the type; an aesthetic table shape forfeits it.
2. **Four** body types, not three: `decision_table`, `state_transition`, `formula` (Planguage
   `Scale` + `Meter` + `Goal`/`Fail`), `invariant`.

`structured_body` is **0..1 per GR**, discriminated by type. (a) is rejected for now — the
codebase cannot currently `ALTER TABLE`, so a JSON column evolves where typed child tables could
not. Promoting to (a) later remains open and is decided by the measurement below.

**Complementarity with SPEC-1 (§S1.11 item 5):** a `D-COMPUTE` statement and a `formula`
structured body are **complementary, not alternatives**. Keep both the sentence form and the
composed table.

**The equivalence loop — recorded with its inverted framing, which is normative for any claim
made from it.** The chain (DMN XML → Drools/KIE `ANALYZE_DECISION_TABLE` →
`COMPUTE_DECISION_TABLE_MCDC` + `MCDC2TCKGenerator` → replay `inputNode` values against the
legacy system and diff `resultNode/expected`) is the only place in this plan where extraction
error is **measurable** rather than assumed. But van de Hoef et al. reports **0% decision-rule F1
on three of eight logic cases**, collapsing past ~6 rules per table, on hand-picked single-file
Java of at most 19 rules.

Therefore, **normative for this feature**:
- The loop is the **detector of bad extraction**, not a validation of good extraction.
- **Design for rejecting most tables at first.** A `decision_table` body carries its own fidelity
  verdict; **failing replay is an ordinary recorded outcome** (→ Q3g `disposition`, Q3a
  `confidence_extraction`), never an exception or an error state.
- **Do not promise DMN coverage of the corpus.** The claim is "for the decision-logic subset we
  can *measure* fidelity", never "we can extract decision logic reliably."
- **Sequencing gate:** the first milestone must measure the **rule-count distribution per
  candidate table** alongside the collapse-into-a-table count. **If most candidates exceed ~6
  rules, the replay loop waits** — the paper predicts extraction failure at that size.

**Three cautions carried into implementation:**
1. ⚠️ Mechanical gap/overlap checking is a property of **Drools/KIE, not of the DMN
   standard** — the spec deleted its only explicit completeness construct in v1.1 and leaves
   the algorithm to vendors. State it that way in any deliverable. The DMN TCK is still on 1.4
   (do not cite it as 1.5 conformance); Trisotech does syntax-only V&V, not gap/overlap analysis.
2. ⚠️ **Do not model this on SCR/Parnas tables** — refuted for business rules on five
   sourced grounds (§13).
3. ⚠️ **Nursimulu & Probert:** the same table is produced whether or not the One-and-only-one
   / Inclusive / Exclusive constraints are present, so **the table alone cannot detect a
   constraint omission.** Keep the constraint set (or cause-effect graph) as a reviewable artifact
   in its own right, not just the table.

**Adopt DMN's vocabulary verbatim** — `contracted` / `expanded` / `limited-entry` — and the
three-valued cell (Elmendorf's 3^n enumeration base = Myers' blank = DMN's `-`).

**Measurement that must land in the first milestone regardless:** how many of the 470/815 NNG
rules actually collapse into a table. It decides whether (a) is ever worth promoting to, and it
sizes the equivalence-testing opportunity.

**`invariant` caveat:** its inference precedent (Daikon; Clousot's ~64% of warning-bearing
`mscorlib.dll` methods, from shipped binaries) requires a runnable build with an exercising
workload or at minimum bytecode — which this pipeline usually lacks — and Daikon overfits to
the test suite. Treat automatic invariant inference as out of scope until a runnable target
exists; the *type* is still worth having for hand- and LLM-authored invariants.

---

## Q3d — Subject of the normative statement: **DECIDED (a) 2026-08-24, with the (c) fallback flagged**

**Decided: (a) — `[Subject]` is derived from the Layer-0 domain of the citing file**
(`file_domains`, whose `domains.json` names are business-capability-shaped: "Legal Entity",
"Nomination"), **falling back to (c) — an LLM-named component — only when the file is
`unassigned`. Never (d).**

**The fallback is flagged, not blended.** A subject produced by the (c) fallback is recorded with
an explicit provenance marker (LLM-named, not derived) so that review can tell stable subjects
from invented ones, and so the flag rate is reportable as a quality signal alongside the existing
domain-coverage metrics. **Do not silently mix derived and LLM-named subjects in one column with
no discriminator.**

**Interaction with the `excluded` tier:** `excluded` is a distinct `file_domains` value from
`unassigned` (added 2026-07-24). Only `unassigned` triggers the (c) fallback. A rule cited to an
`excluded` file is a signal that the extraction scope is wrong, not a subject-naming problem.

**Why (a):**
- The subject becomes a **derived, consistent** value rather than an LLM invention — the same
  rule extracted twice gets the same subject. That is 29148's *Unambiguous* characteristic bought
  cheaply.
- It groups requirements by business capability in the render for free.
- It satisfies the draft's second implementation requirement (every GR associated with a domain)
  against a surface that is already canonical (§domain-set canonical flow: `domains.json` is
  the one canonical domain set).

**Why not the others:** (b) the system-dir name (`customer.ple.nng.app`) is accurate but useless
as a requirement subject. (d) is **banned by SPEC-1 `V-SLOT-02`**, which errors on the literals
`the system`, `the application`, `the software`, `the program`. (c) survives only as the fallback
because it reintroduces exactly the instability (a) exists to remove.

**Three independent templates require a named subject**, so this is not an EARS quirk: 29148
Figure 1's `[Subject]` slot, 29148 cl. 5.2.4's prose ("a requirement **shall state the subject**
of the requirement"), and SOPHIST FunctionalMASTeR's `<subject matter>`. None permits "the system"
as a placeholder.

**✅ This unblocks SPEC-1.** §S1.11 item 2 recorded `V-SLOT-01`/`V-SLOT-02` as
unimplementable pending a **naming authority** for the subject — they could detect *absence*
but not *correctness*. **`file_domains` is now that authority**, and both rules become fully
checkable: `V-SLOT-01` on absence, `V-SLOT-02` on the banned literals, plus the new provenance
flag distinguishing derived from LLM-named. **§S1.11 item 2 is hereby closed.**

**Cost settled by Q4 (`knowledge.sqlite`) — this is now the cheap path.** `file_domains` lives in `knowledge.sqlite`, and the two DBs
are **never `ATTACH`ed** — `cli.py:1102-1106` documents that joins are done in Python because
attaching a WAL `index.sqlite` read-only proved unreliable. So GRs in `knowledge.sqlite` (Q4's
decision) make this join one SQL statement in one file, which is what Q4 chose; GRs in
`index.sqlite` would have made it a Python-side join. The decision held either way; only the cost
moved, and it moved in this decision's favour.

**Forward pointer:** if domain vocabulary is ever first-classed, **KDM's `TermUnit`** ("aligned
with SBVR term or name concepts... some 'noun concept'") is where the subject belongs. That is
**Q3l**'s territory and is not decided here.

---

## Q3e — User stories: **DECIDED (b) 2026-08-24, deferred to the Q2 future milestone**

**Decided: (b) — a user story is a GR `kind`, authored as a rollup** over N rules where
citable actor evidence exists (controller, auth role, UI entry point), linked to its constituent
rules by **`derived_from[]`**.

**Milestone split, inherited from Q2 (b as model, a as first milestone):**
- **Milestone 1 pays only the schema cost** — the `story` value in the `kind` enum and the
  nullable `derived_from[]` link. Nothing else. Because Q2 already settled that the schema is
  generic from day one, **no migration is needed when stories arrive.**
- **The story *producer* is milestone 2** — `user-story-generator`, alongside
  `detailed-req-documenter`, `business-documenter` and `use-case-generator`, all against the
  already-generic schema.

**Why (b) and not (c):** a story is a **different altitude** than a mined rule and needs citable
actor evidence. **(c) — `as-a/I-want/so-that` on every GR — is rejected: per-rule actors
will be fabricated**, because mined code usually does not say who the user is, and (c) would have
to ship in milestone 1. AWS Transform independently validates the altitude choice: its user story
is the **section heading** over a group of numbered requirements, **not a per-requirement field**.

**What the rollup buys:** the traceability matrix `US → UC → FR → RULE → code` that
`user-story-generator`'s template already draws but **cannot substantiate** today.

**Carried into milestone 2 when it is built:**
- **iStar 2.0's Role/Agent split** — "the abstract actor a story is written for" vs "the
  concrete system component" — with its `is-a` / `participates-in` actor links, is worth
  borrowing as a distinction. ⚠️ **Do not adopt i* as the notation:** iStar 2.0 explicitly
  excludes any methodology or completion criterion ("when can a model be considered final?"), has
  no formal semantics, and has had no successor in 10 years. Only **piStar** is still maintained;
  OpenOME, jUCMNav and TAOM4E are dead.
- **Where actor evidence actually lives in code is enumerable:** Withall's **Access Control**
  domain (User Registration, User Authentication, Specific Authorization, Configurable
  Authorization, Approval) is the published list of shapes to look for. Use it as the search
  target rather than inventing one.
- **29148 NOTE 2** concedes that "requirements in agile may use alternative formulations such as
  user stories without explicitly using the term 'shall'", so a story layer **does not breach the
  standard** — but it also **gets no template from it**. SPEC-1's `pattern` enum therefore does
  not apply to `kind = story`; a story is not validated as a normative sentence.
- ⚠️ **Sobering precedent for the story/goal-recovery ambition generally:** Yu et al., RE'05,
  "Reverse engineering goal models from legacy code" is a validated four-step pipeline
  (SquirrelMail, Columba) with **74 citations in 21 years**, only ~10 continuing the thread, and
  `title.search:goal-oriented reverse engineering` returns **count: 0** in OpenAlex. Validated,
  published, and essentially abandoned — treat it as an **opportunity, not a mature practice**,
  and do not plan milestone 2 as if a proven pipeline exists to copy.

---

## Q3f — Scenario shape: **DECIDED (b) + (c)'s lint, 2026-08-24**

**Scope first, as stated by the user 2026-08-24: the new requirement shape REPLACES the current
extractor's G/W/T.** G/W/T stops being *the requirement*. The normative record is SPEC-1's
`statement`, with Q3a's `as_built` beside it; **scenarios drop to a subordinate 0..n child.**
This was never a migration question — nothing is ever migrated (§Q3-backfill / SPEC-2), and
the old title ("What happens to the existing G/W/T text?") has been corrected because it read as
one. What "existing" meant was the **extractor's own current output shape**:
`extract-rules.js:80` makes `given`/`when`/`then` **required** fields in `RULES_SCHEMA`, and the
referee schema at `extract-rules.js:139` asks whether the G/W/T is faithful to the cited code.
**Both change.**

**Decided: (b) re-author implementation-independent, PLUS (c)'s leakage lint. Not (b) alone.**

1. **`scenarios[]`** — 0..n child, re-authored implementation-independent. G/W/T remains the
   scenario grammar; it is no longer the requirement.
2. **`implementation_notes`** — where legacy method names, exception types and symbols go
   instead. They are genuinely valuable: they are **how you find the code again** and **how a
   characterization test asserts current behavior**. They belong in an **evidence** field, never
   in acceptance criteria a rewrite is judged against.
3. **`V-STY-03`** — the leakage lint, already in SPEC-1 as a **WARN**, implementing the
   **Baxter & Hendryx six-item rubric** (§18b) rather than an invented list: (1) nonsensical /
   loop-mechanics rule, (2) program symbols used as business terms, (3) implementation technology
   as vocabulary, (4) over-specification, (5) unabstracted variable instead of a named business
   term, (6) cloned business terms implying independence where rules are coupled.

**Cost: a prompt change, not new analysis.** The extractor already has both halves in hand at
extraction time. AWS Transform does the opposite and its requirements are the worse for it.

**Standards mapping:** this is 29148's ***Appropriate*** characteristic — "avoiding unnecessary
constraints on the architecture or design while allowing implementation independence to the extent
possible." ⚠️ **Edition drift:** *Implementation Free* was a **2011** characteristic, **absorbed
into *Appropriate* in 2018**. Any checklist citing "implementation free" as a 29148 characteristic
is keyed to the superseded edition — do not cite it that way in a deliverable.

**Why this is not a tidiness issue:** the formal-methods tradition names the defect
**"implementation bias"** (§19), and **Chaparro measured it at 36%** of recovered rules —
the single largest error class in the one honest published measurement.

**⚠️ Why the lint is a supplement and not an alternative — and why it stays a WARN.** TCAS II:
"we had difficulty abstracting away from the design... to **specify the problem without trying to
solve it**. With practice we became better at omitting design information, but **the struggle
never entirely abated**." **The cleanup cannot be completed, only recorded.** A lint that blocked
on leakage would therefore block forever on some fraction of a real corpus; `V-STY-03` stays
`WARN` and is **not** promoted to `ERROR`.

**One consequence beyond the lint, carried forward:** mined specs are **inherently more complex
than greenfield ones** — Leveson: "our resulting model is more complicated than necessary... we
first built a nice, simple model and found that we had to **complicate it for no better reason
than that it had to match some errors or poor decisions in the pseudocode**." That is the argument
for `suspectedDefect`, and for making the **preserve-vs-fix decision a recorded, first-class
transition** rather than an invisible judgment call inside an extraction prompt. Where that
transition lives is **Q5**'s lifecycle question and is not decided here.

**Where G/W/T is still the right shape:** for **conditional** business rules — the bulk of the
corpus — **a G/W/T scenario *is* the fit criterion** (§12). For **quantitative** GRs it is
the wrong shape, and **Q3c's `formula` body** (§Scale + Meter) takes over. Scenarios survive
as a child; they stop being the headline.

---

## Q3g — Disposition model with a zero-invariant: **DECIDED (a) 2026-08-24**

**Decided: (a) — adopt BOTH denominators.** They measure different things and neither
substitutes for the other:

| Denominator | Question it answers | Source |
|---|---|---|
| **chunk coverage** (`legacylift-search coverage --claimed` → `{total, claimed, uncovered, pct, uncovered_chunks}`) | "did we **look at** all the code?" | already shipped; drives extract-rules' loop-until-dry at `workflows/extract-rules.js:207-231` |
| **`disposition`** enum on the GR (or on the GR→citation link) | "was **every rule carried forward**?" | AWS `traceability.yaml` |

**Values:** `captured | not_applicable | unreachable | delegated | not_accounted_for`, with an
**enforced `not_accounted_for = 0` gate before a run counts as complete.**

⚠️ **Two of the five values may want renaming for a non-mainframe context** (`delegated`,
`unreachable`). Rename at implementation time if the corpus argues for it; keep the semantics.

**Composition with already-shipped work:** `unreachable` composes cleanly with the
`exclude_globs` / **`excluded`** domain tier (added 2026-07-24) — dead code leaves the
denominator **honestly** rather than silently. Do not conflate `excluded` (out of scope by
design) with `unreachable` (in scope, but not live).

**Why this is a positioning decision, not bookkeeping.** It converts "we found 470 rules"
(unfalsifiable) into "67 rules, 46 captured, 21 not applicable, **0 unaccounted**" — auditable
by a client.

- **§15's central consequence:** disposition + `not_accounted_for = 0` is disproportionately
  valuable **precisely because the field has no benchmark**. It is an *auditable completeness*
  claim in a domain where nobody can make an *accuracy* claim. Against ~29% precision as the one
  honest published number, **it is the strongest defensible quality story available.**
- **Only deterministic numbers are self-reportable.** SparseAlign names the failure mode:
  organizations "risk a **circular evaluation loop, where unverified LaaJs are used to assess
  model outputs**." AgentModernize's 92.3%/90.2% is the worked example — its oracle was
  "drafted by the primary annotator with LLM assistance (GPT-4o enumerated candidate rules from
  the legacy code)", i.e. **seeded by an LLM reading the very code the pipeline is scored on**.
  **Coverage and disposition are computed, not judged** — which is exactly why they are the
  numbers we can print. **Normative: never print an LLM-judged quality number beside them.**
- **The measured failure mode is omission, which is what this catches.** van de Hoef et al.
  (§17e-bis) found that GPT-4.1 and Gemini 2.5 Pro **did not hallucinate rules to fill gaps**
  — they "would rather **omit** decision rules... than to devise a decision rule itself to
  create a complete decision table." So a completeness invariant is aimed at the right risk, and
  **hallucination defences matter less than coverage defences.**
- **The invariant framing is sound rather than novel:** SCR's checkable obligations (Coverage,
  Disjointness) are the same idea one layer down, and found 74 real defects **post-expert-review**
  in 245 seconds.

**Consequence for Q5 (recorded here because the reason lives here).** §15's third consequence:
approved, SME-signed-off GRs with code citations **are the ground-truth artifact the field
lacks**. Architecture recovery had to write a whole ICSE paper (Garcia et al., ICSE 2013) whose
**contribution was the oracle**; this store accumulates one as a byproduct. That argues for
capturing **reviewer identity, decision, and timestamp on every lifecycle transition from day
one** — the mechanism is **Q5**, but the justification is Q3g's.

**Interaction with Q3c, already recorded there:** a `decision_table` that fails the DMN replay is
an **ordinary recorded outcome**, routed through `disposition` and Q3a's `confidence_extraction`
— never an exception. Q3g is the field that makes that routing legible.

---

## Q3h — Deterministic data-flow block: **DECIDED (a) 2026-08-24, with a FLAGGED LLM fallback**

**Decided: (a) — `reads[]` / `writes[]` are COMPUTED from Layer-0 for the GR's cited symbols**
(data-access edges, `uses_table`, M24 `has_column` facts, `foreign_key` edges). **No LLM on the
computed path.**

**User amendment 2026-08-24 — the fallback.** Where the graph yields **nothing** for a cited
symbol, do **not** silently emit an empty block. Capture what the extractor infers, **clearly
marked as LLM-inferred rather than computed**, with room for its reasoning.

### The provenance rule (normative)

**Every entry in `reads[]` / `writes[]` carries a per-entry `provenance` discriminator:**

| `provenance` | Meaning | Filled by |
|---|---|---|
| `computed` | derived from Layer-0 edges/facts for a cited symbol | pipeline, no LLM |
| `llm_inferred` | the graph had no edge; the extractor's reading of the code | extractor |

Plus a free-text **`explanation`** on `llm_inferred` entries only — why the extractor believes
this read/write exists, and ideally what it read to conclude it. `computed` entries need no
explanation; their justification is the edge itself.

**This is deliberately the same shape as Q3d's flagged subject fallback** (derived from
`file_domains`, LLM-named only on `unassigned`, flagged either way). Two questions, one pattern:
**prefer the deterministic source, permit the LLM only where the deterministic source is silent,
and never blend the two in one undiscriminated column.**

### Constraints the fallback must respect

1. ⚠️ **Q3g's rule still binds: never print an LLM-judged number beside a computed one.** Any
   count, coverage figure or "requirements touching table X" answer **defaults to `computed`
   entries only**. `llm_inferred` entries are available on request and must be **labelled in the
   output**, never folded into the deterministic total.
2. **The fallback fires on graph silence, not on graph disagreement.** If Layer 0 has edges for
   the cited symbol, those are the answer — the extractor does not get to overrule them or add
   to them. `llm_inferred` is for the empty case only.
3. **`llm_inferred` entries are a review signal.** A high `llm_inferred` rate means the graph is
   blind somewhere (most likely unresolved dispatch), which is information worth surfacing rather
   than papering over. Report the ratio.

### Why (a) for the computed path

- **It is the one place in this record where the survey's negative results do not apply.**
  Reads/writes are computed from a graph: no oracle problem, no confidence field, no SME
  question. §15's "only deterministic numbers are self-reportable" makes this one of the few
  things we can assert flatly. Same argument that settled Q3g — which is exactly why the
  LLM-inferred half must be fenced off from it.
- **Strictly better than AWS, not equal.** Their `Data flows: Reads / Writes` block is
  LLM-generated in the same pass as the prose; ours is computed and therefore checkable.
- **It enables a query nobody else has:** "which requirements touch table AGREEMENT?" —
  precisely what a data-migration workstream asks, and unanswerable from markdown.
- **It fills a named gap in the only code→DMN paper in existence.** van de Hoef et al.'s stated
  limitation, verbatim: "each decision table was extracted separately, i.e., **dependencies
  between decisions were not included, as the LLMs did not receive the context of other
  decisions**." We have those dependencies deterministically. **Supplying inter-decision
  dependency context from the graph rather than hoping an LLM infers it is a concrete
  differentiator over the published state of the art** (§17e-bis), and it is the same
  mechanism this question already recommends.
- **Standards shape:** KDM's `implementation` property applied to data rather than code — the
  same "extent"/"handle" mechanism underpinning the whole citation design (§1).
- **Corroboration:** when the McMaster group attacked legacy *enterprise* code they reached for
  dependency and change-impact analysis — the graph, not tables (§13). A vote of confidence
  in Layer 0 being the right substrate.

### ⚠️ Implementation reality — what this actually costs

1. **T-SQL `uses_table` reports aliases as datastores.** Without a normalization step this block
   emits junk table names (`o`, `po`, `v` instead of `PURCHASE_ORDER`). **This is the main cost of
   (a) and is a real task, not a footnote.**
2. **Dispatch is unresolved, not absent** — restated precisely 2026-08-24 against
   `code-graph-construction.md` §2. `_resolve_callee` grades every ref: **0.85** one match,
   **0.70** ambiguous same-language, **0.40** cross-language ambiguous, **0.30** zero matches —
   and **the zero-match edge is KEPT, with `callee_name` preserved** ("preserve unresolved
   edges"). So the edge exists but **has no callee symbol id**, and a reads/writes computation
   cannot traverse it. Framework-mediated calls (MVC actions, DI-resolved services) are the main
   population.
   `/modernize-map` resolves those from framework config; this block needs the same treatment or
   it under-reports reads/writes for exactly the web-action layer. **This is the primary trigger
   for the `llm_inferred` fallback**, and it is why the fallback exists rather than being an
   afterthought.
3. **The computed block is a deterministic LOWER BOUND, and must be reported as a floor, not a
   total** — the same discipline as Q5's `cap_reached` caveat. Under-reporting is safer than
   fabricating; the `llm_inferred` entries are how the gap becomes visible instead of invisible.

### M24 status — corrected 2026-08-24

**M24 `has_column` is already IMPLEMENTED**, not a future dependency: `semantic-code-search-graph-index.md`
Milestones 23–25, marked done 2026-07-17 (commit `6b9ac4b3`), CI-validated on the polyglot
fixture. It emits `has_column` facts into **`symbol_facts`** (object = column name; attributes =
data type, nullability, PK/unique) and `foreign_key` **edges** into `graph_edges` via a **regex
supplement** (tree-sitter-sql mis-parses the FK clause to `ERROR`).

⚠️ Three caveats:
- **At-scale validation is still deferred** — CI coverage is the polyglot fixture; the
  `ctcm-db` cold `--reset` run was deferred past the harness wall-clock cap. Consistent with the
  recorded SQL-extractor lesson that hand-written fixtures miss the shape real schemas arrive in
  (bracketed data types, out-of-line `ALTER TABLE` FKs).
- **`create_trigger` / `create_index` remain on the regex path** — they mis-parse to `ERROR`;
  M24 corrected `definition_node_kinds` to `create_table`/`create_view`/`create_function`/`create_procedure`
  only.
- **`symbol_facts` lives in `index.sqlite`** (derived, gitignored, `--reset`-able — the
  deliberate Layer-0 design). **Bearing on Q4:** if GRs live in `knowledge.sqlite`, computing this
  block is a cross-DB read, and the two DBs are **never `ATTACH`ed** (`cli.py:1102-1106`). Same
  Python-side join constraint Q3d already hit — reusable, but name it once rather than
  discovering it twice.

---

## Q3i — Modality and rule class: **DECIDED (a) 2026-08-24, `modality` extractor-proposed / SME-confirmed**

**Decided: (a) — two enums.** Note most of this question was **already settled inside SPEC-1**;
approving it re-opens nothing there.

| Field | Values | Status |
|---|---|---|
| `rule_class` | `definitional` \| `behavioral` | **already fully specified** — SPEC-1 §S1.2's decision procedure, §S1.3's disjoint keyword sets, `V-CLASS-01/02` |
| `enforcement_level` | six values, **behavioral only** | **already fully specified** — SPEC-1 §S1.5, `V-ENF-01/02/03` |
| **`modality`** | `requirement` \| `expectation` | **the only genuinely new field this question adds** |

### What `modality` carries that `rule_class` does not

KAOS's distinction between an agent the software controls and one it does not:

- **`requirement`** — satisfied by the **software agent**. *"The Order Service must reject the
  order."* Implementable, testable, ownable.
- **`expectation`** — satisfied by an **environment agent**, therefore **not implementable, only
  assumed**. *"The vendor master file must be loaded before the nightly run."* Nothing in the
  code can enforce it; the system depends on it being true.

**Why this earns a column in a modernization context specifically: an `expectation` is a
MIGRATION RISK, not a work item.** It cannot be built — only re-verified against the new
environment. Conflating the two hands a rewrite team a backlog containing items nobody can
complete, and hides the environmental assumptions that most often break on a lift. This
distinction is entirely invisible in today's output.

### Provenance — extractor-proposed, SME-confirmed (user decision 2026-08-24)

The candidate field list had `modality` as "extractor + SME", which was the **only shared-provenance
entry in the whole schema** and sat awkwardly against `NORMATIVE PRINCIPLE-1`. Resolved:

- The **extractor proposes** `modality`. It is frequently inferable from the citation — a rule
  whose cited code checks for file arrival, polls an external system, or trusts an inbound feed
  is an `expectation`; a rule whose cited code performs the action itself is a `requirement`.
- The value is **flagged as proposed until an SME confirms it**, exactly as Q3d flags an
  LLM-named subject and Q3h flags an `llm_inferred` read/write. **Same PRINCIPLE-1 pattern, third
  application in this branch.**
- **Rationale for not letting it stand unconfirmed:** an expectation misfiled as a requirement
  produces a task nobody can complete; a requirement misfiled as an expectation silently drops
  work from the rewrite. Both failures are expensive and neither is visible without the flag.
- Confirmation rate is review progress (Q3j's framing), not a defect count.

### The verified constraint (unchanged, already implemented)

`enforcement_level` attaches to **behavioral rules only**. **This is SBVR's own constraint, not
our inference** — the fact type is literally `operative business rule has level of enforcement`
(cl. 12.1.3), and cl. 12.6.12's caption reads "...applies to an operative business rule
**(only)**." SBVR's own synonym for `operative` is **`behavioral business rule`**. Verified from
the standard 2026-08-21 (§17a-ter) and already enforced as `V-ENF-01`.

A definitional rule cannot carry an enforcement level because it **cannot be violated at all** —
which is the same reason `guideline` (Q3k's warn-don't-block tier) lands on `enforcement_level`
rather than on `category`.

---

## Q3j — SME-only fields: **DECIDED (a) 2026-08-24, with the forbidden set drawn tightly**

**Decided: (a) — carry them as first-class, extractor-forbidden, and report fill rate as review
progress. The empty field is a feature.**

### The provenance split (normative)

| Field | Filled by | Extractor may write it? |
|---|---|---|
| `rationale` | **SME only** | ❌ **FORBIDDEN** |
| `fit_criterion` | **SME-negotiated** | ❌ **FORBIDDEN** |
| `enforcement_level` | **SME only** (already SPEC-1 §S1.5) | ❌ **FORBIDDEN** |
| `assumptions` | **extractor-permitted**, SME-refined | ✅ permitted |
| `risks` | extractor (validator findings land here) + SME | ✅ permitted |
| `issues` | SME | ❌ forbidden |

**Why `assumptions` is permitted while `rationale` is not** (user decision 2026-08-24): an
assumption is frequently **visible in the cited code** — "assumes the inbound feed has already
arrived", "assumes the vendor table is non-empty" — so a deterministic-ish source exists, and
29148 cl. 5.2.7 makes documenting them a normative **`shall`**. A rationale is *why the business
wants this*, which is precisely what TCAS II proved is **information-theoretically absent from
code**. **Keeping the forbidden set tight and defensible beats a sprawling one** that invites
exceptions later.

Note `assumptions` also composes with **Q3i's `expectation` modality**: an expectation *is* an
assumption about an environment agent, so a rule with `modality = expectation` should generally
carry a populated `assumptions` field. Worth an informational check, WARN at most.

### This is PRINCIPLE-1 §P1.3 clause 2 in its purest form

The general rule asks: when no deterministic source exists, is the right answer **emptiness**
rather than a guess? **Q3j is the case where it plainly is.** A fabricated `rationale` is a lie
with a code citation attached — the most convincing possible form of a fabrication. A blank one
is an honest signal that review has not happened yet.

### Standards backing — stronger than "good practice"

- **29148 cl. 5.2.7 — a normative `shall`:** "All assumptions made regarding a requirement
  **shall** be documented." Not optional, and the reason `assumptions` is first-class.
- **29148 cl. 5.2.8:** `rationale` is among the attributes that "should be captured", alongside
  `risk`, `owner` and version number.
- **Volere:** `fit_criterion` is one of the Robertsons' own load-bearing three — "**non-subjectively**
  test whether the solution fits."
- **§12 — three traditions converge on "fit criterion" independently** (Volere, Planguage's
  `Scale`/`Meter`, 29148's *Verifiable*), which is unusual enough to be worth citing as
  corroboration rather than coincidence.

### Why (b) is actively harmful, not merely weak

Letting the extractor guess `rationale` produces plausible business-intent prose sitting beside a
real code citation. The citation lends it authority it has not earned. **This is the same failure
Q3a exists to prevent** — one field carrying both "the code does this" and "the business wants
this" — and the same failure Feathers warns about: presenting recorded behavior as intent
"silently promotes every latent defect to a requirement."

### What (a) buys operationally

**Fill rate is a review-progress metric that is COMPUTED, not judged** — so it is printable under
Q3g's rule and does not contaminate the deterministic numbers. *"340 of 470 rules carry an
SME-supplied rationale"* is exactly the auditable, falsifiable shape this design keeps reaching
for, and it is the natural companion to `not_accounted_for = 0`.

**Reporting rule:** report fill rate **as progress, never as a defect count**. An empty
`rationale` on a freshly extracted rule is the expected state, not a finding. Do not add a
validator rule that fires on emptiness — SPEC-1 deliberately has none, and `V-ENF-03` (behavioral
rule with no `enforcement_level`) is already framed as a review-progress WARN rather than a
defect, which is the precedent to follow.

---

## Q3k — `category` shape: **DECIDED (a) 2026-08-24, `Lifecycle` kept and justified**

**Decided: (a).** Two separable halves, both resolved.

### Half 1 — the warn-don't-block tier lands on `enforcement_level`, NOT on `category`

**This closes a live defect in shipped output.** Von Halle's verified taxonomy (§17a-bis) has
**`guideline`** — a rule that "does not force the circumstance to be true or not true, but merely
warns about it, **allowing the human to make the decision**." Our `category` enum has **no
warn-don't-block tier**, so **every advisory rule in the corpus is currently classified as
`Validation` and silently promoted to mandatory.** That is wrong data in documentation already
delivered, not a future taxonomy question.

**Why it does not belong in `category`:** SBVR cl. 12.1.3 puts it on a six-value **level of
enforcement** scale whose lowest value is literally `guideline` ("suggested, but not enforced").
It is a position on an *enforcement scale*, not a rule *category*. Encoding it as a `category`
value would make it **mutually exclusive with `Calculation`/`Validation`** — plainly wrong, since
**an advisory calculation is perfectly coherent**. It also lands on the field Q3i restricts to
behavioral rules, which is exactly right: a definitional rule cannot be "suggested but not
enforced" because it **cannot be violated at all**.

✅ **Already implemented — no new work.** SPEC-1 §S1.5 carries the six-value `enforcement_level`
enum including `guideline`, with `V-ENF-01/02/03`. Approving (a) confirms the tier stays there and
that **`category` does NOT grow a `guideline` value**.

⚠️ **Attribution constraint, restated because it is easy to lose:** the six values appear in SBVR
under an `Example:` caption ("An example set of levels of enforcement, **based on [BMM]**") and
SBVR §6 declares examples informative. Cite them as **an example set given by SBVR, derived from
BMM** — never as a normative SBVR enum.

### Half 2 — `Lifecycle` is KEPT, and here is its basis

`Lifecycle` had no counterpart in Von Halle's taxonomy: her four ways a rule guides a business
event — present information / constrain information / initiate external action / create new
information — contain **no state or lifecycle class**, so `Lifecycle` could not borrow her
authority. It needed its own justification or had to fold into action-enabler.

**Decided: keep it, justified by Q3c's `state_transition` body type.** State-machine-shaped rules
are real and common in legacy enterprise code, and Q3c has already given them a first-class
structured body. **`Lifecycle` is the category whose rules carry a `state_transition` body.** That
makes the category enum and the body-type list line up instead of drifting, and it is a cleaner
answer than folding lifecycle rules into action-enabler and losing the distinction.

**Consequence to implement:** `category = 'Lifecycle'` and `structured_body.type =
'state_transition'` should **correlate** — a `Lifecycle` rule with no state transition, or a
`state_transition` body under some other category, is worth an informational check in the spirit
of `V-CLASS-02` (which already warns on `Calculation`+`behavioral` / `Validation`+`definitional`).
**WARN, never ERROR** — the correlation is a strong signal, not a law.

⚠️ **Where the value set may NOT come from:** 29148's own `Type` value set (Functional/Performance,
Interface, Process, Quality, Usability, Human Factors) is **systems-engineering-shaped and does
not fit business rules.** If `category` is ever revisited, borrow from **Von Halle** or **Withall**
(§11 — his 37 patterns across 8 domains: `Calculation Formula`, `ID`, `Data Longevity`,
`Data Archiving`, `Transaction`, `Chronicle`, `Approval`, `Fee/Tax` are close to what a legacy
enterprise system actually yields), **not from the standard.**

### Net effect on SPEC-1

**Only `V-CLASS-02` is affected** (§S1.11 item 4 anticipated exactly this). `category` keeps its
four values — `Calculation | Validation | Lifecycle | Policy` — with `Lifecycle` now carrying a
recorded basis, and the advisory tier lives on `enforcement_level` where SPEC-1 already put it.
**No change to the notation, the pattern enum, or any other validator rule.**

---

## Q3l — Vocabulary layer: **DECIDED (a) 2026-08-24, as a LATER milestone**

**Decided: (a) — two lightweight tables, `term` and `fact_type`, that GRs reference.** Populated
from Layer-0 candidates (symbols, M24 `has_column` facts, table names) plus **analyst naming**.
**Sequenced as a later milestone**: land the GR tables first, add vocabulary once **Q5**'s review
loop exists to populate it.

### Why a vocabulary layer at all — four independent sources, one message

Rules are built **on** a vocabulary, and the vocabulary must be recovered **first**:

| Source | Contribution |
|---|---|
| **Von Halle 2001** (§17a-bis) | terms and facts are **peers of rules**, not subordinate to them |
| **SBVR 2008** | the entire specification is vocabulary-then-rules |
| **KDM 2012 (ISO/IEC 19506)** | `TermUnit` / `FactUnit` / `RuleUnit` are three **coequal** first-class units |
| **Baxter & Hendryx 2005** (§18) | verbatim: "first get the business vocabulary, **then** build rules using vocabulary" |

**Our design has no such layer today** — rules cite code symbols directly, so `PUR-ORD-QTY` *is*
the term.

### ✅ This closes the LAST SPEC-1 blocker (§S1.11 item 3)

`V-STY-03`'s Baxter & Hendryx rubric items **2, 3 and 5** — program symbols used as business
terms, implementation technology as vocabulary, unabstracted variable instead of a named business
term — are **literally unfixable while a code symbol is the only available referent**. SPEC-1's
own worked example §S1.10 #10 says so: *"When PUR-ORD-QTY is greater than zero, the Order Service
must set WS-QTY-DUE"* lands as a WARN and "resolving it properly needs Q3l's vocabulary layer."

**With (a) decided, the resolution path exists** — but only once the layer is populated, which is
why `V-STY-03` **stays a WARN** (Q3f, on TCAS II grounds) and does not become blocking even after
the vocabulary milestone ships.

### Why (a) and not (b)

A free-text `glossary` field per GR yields **the same term spelled five ways across five rules** —
that is the defect restated, not a fix. The value of a vocabulary layer is that it is **shared and
referenced**: renaming `PUR-ORD-QTY` to "purchase order quantity" **once** fixes every rule that
uses it. (c) is today's shape and is what the four sources above argue against.

### Why LATER, and what "later" depends on

The layer needs a **populator**. Layer 0 supplies the *candidates* deterministically (symbols, M24
`has_column`, table names), but **the business-meaningful name is analyst judgment** — textbook
`NORMATIVE PRINCIPLE-1` §P1.3: deterministic candidate, human naming, never an LLM inventing
business vocabulary. There is nobody to supply that judgment until **Q5**'s review loop exists.
**Building the tables before the workflow yields empty tables and a `V-STY-03` that still cannot
fire correctly.**

**Sequencing (record in the ExecPlan):** GR tables → Q5 lifecycle/review loop → vocabulary layer.
The vocabulary milestone is a **peer of Q2's milestone-2 producer set**, not a prerequisite for
either.

### ⚠️ KDM attribution caveat — keep it, do not overclaim

Adopting `TermUnit` / `FactUnit` as **vocabulary** costs nothing and converts "we invented a rule
schema" into "we implemented the half ADM explicitly left to a *difficult value-added knowledge
discovery process*." **But: KDM defines the container and NEVER the extraction, ADM is dormant,
and there is NO requirements metamodel anywhere in ADM.** Cite it for the vocabulary shape only.

**Forward pointer from Q3d:** when the layer lands, **`KDM TermUnit` is where the `[Subject]`
belongs** ("aligned with SBVR term or name concepts... some 'noun concept'"). Until then the
subject stays derived from `file_domains` per Q3d.

## Q4 — Which physical store, and how many: **DECIDED (b) 2026-08-24 — new tables in `knowledge.sqlite`**

**Decided: (b), and within (b) the `knowledge.sqlite` variant** — GR tables live in the existing
durable `knowledge.sqlite`, **not** in `index.sqlite`, **not** in a new third `requirements.sqlite`,
**not** in Chroma, and **not** in a hosted RDBMS.

### Why not `index.sqlite` — the disposability argument

`index.sqlite` is **derived, gitignored and `--reset`-able**. GRs are the opposite: expensive LLM
output plus **signed-off SME judgment** (Q5). Putting reviewed requirements in a directory whose
documented recovery procedure is "delete it and reindex" makes a routine reindex a
**data-loss event**. This is the Layer-0/Layer-1 trust boundary that `fact-graph-decision.md` is
built on: Layer 0 is untrusted, deterministic, disposable; Layer 1 is judgment and must survive.

### Why `knowledge.sqlite` and not a new `requirements.sqlite`

`knowledge.sqlite` **already is** the Layer-1 store: it already survives `--reset`, and it already
holds Layer-1 judgment in `file_domains`. Two consequences:

1. **Q3d's subject join becomes one SQL statement in one file.** The subject is derived from
   `file_domains`; co-locating GRs with `file_domains` makes that a plain join.
2. **A third database adds a second cross-DB seam for nothing.** `requirements.sqlite` would put
   the Q3d join *and* the Q3h join across process boundaries.

### ⚠️ The cross-DB read that (b) does NOT remove — state it in the ExecPlan

`symbol_facts` (M24 `has_column`) lives in **`index.sqlite`**, and the two DBs are **never
`ATTACH`ed** — `cli.py:1102-1106` documents that joins are done **in Python** because attaching a
WAL `index.sqlite` read-only proved unreliable. So **Q3h's computed `reads[]`/`writes[]` is a
cross-DB, Python-side join under every option**, including this one. (b) does not fix that; it
just refuses to pay a second seam for Q3d. The ExecPlan must budget the Python-side join
explicitly rather than assuming a single-file SQL query. **See `NORMATIVE SPEC-3` §S3.3 for how
the join is keyed** — `anchor_key` is the shared, stable join column that makes the cross-DB read
tractable, and it is the reason SPEC-3 puts `anchor_key` in Layer 0 rather than in the GR store.

### Why Chroma is never primary, and where hosted went

Chroma has **no relational integrity** and **cannot express GR→chunk→symbol joins**. It is an
**addition** for vector recall, decided under **Q6**, never the record of truth. Hosted
Postgres/Aurora is **deferred entirely** to `hosted-data-store.md`; nothing in this plan is
allowed to presuppose it.

---

## Q5 — Lifecycle: **DECIDED 2026-08-24 — full lifecycle, from milestone 1**

**Decided: GRs are durable records with state** — `draft` → `reviewed` →
`approved`/`rejected`/`superseded` — with **stable ids that survive re-extraction**, analyst edits
and notes, and **protection of human-edited text from the next LLM pass**. **Re-extraction is a
merge with dedupe, never truncate-and-insert.** This is milestone-1 scope, not a later addition.

### Why — the two independent justifications

**1. It is the only thing markdown fundamentally cannot do.** A store of "whatever the last
extraction produced" buys queries and little else. A store that **accumulates human judgment
across runs** is what lets a client say *"we reviewed and signed off on 340 of 470 rules."*

**2. Merge is how COVERAGE accumulates — not just judgment.** Measured in §S2.6 against the two
NNG baselines:
- the only run that reached the **web-action and persistence layers** (**327 files vs 148**) did so
  by **merging three scoped runs**;
- the best **single** run stopped at its **round cap** while still finding **~28 new rules per
  round**.

So **truncate-and-insert cannot reach coverage that has already been demonstrated.** The store
must support **scoped runs that merge into one corpus**, deduped on the **§S2.2 join key**.

### Required run metadata (so no coverage claim can be read without its floor caveat)

Record per run: **`rounds_run`**, **`cap_reached`**, **`new_rules_in_final_round`**. A corpus whose
final round was still producing ~28 new rules is a **floor**, not a total, and the metadata is what
makes that legible.

### Why this is the load-bearing decision for sequencing

Identity and dedupe are **milestone-1 schema concerns** because of it. **Three already-settled
decisions depend on it:**

| Settled decision | What it needs from Q5 |
|---|---|
| **SPEC-1 / Q3b-strictness** | the `draft` → `approved` gate is meaningless without states |
| **Q3g** | reviewer identity from day one; `disposition` is a review verdict |
| **Q3l** | the vocabulary layer has **no populator** until the review loop exists |

### Differentiator (keep this in the ExecPlan's motivation)

**AWS Transform has no lifecycle state on requirements and no HITL gate on them.** Job-level
approvals exist; **requirement-level approval does not.** Requirements are immutable generated
documents and re-running **restarts the step** — the docs state *"You are not prompted for any
additional inputs before this process starts."* Refinement is punted to the IDE.

---

## Q6 — Embedding for semantic retrieval: **DECIDED (b) 2026-08-24**

**Decided: (b) — SQLite FTS5 for keyword lookup PLUS a dedicated Chroma collection for GRs**,
separate from `code_chunks`.

### Why FTS5 at all

It is **free**: SQLite ships it, GR text is already relational, and exact-term lookup
("find every rule mentioning `PUR-ORD-QTY`") needs no vectors.

### Why a vector collection is required, not optional

**Q5's merge needs semantic dedupe the moment it exists.** *"Have I seen this rule before?"* is a
**fuzzy-match** question — two extraction runs will phrase the same rule differently, and **exact
ids cannot answer it**. Because Q5 is milestone-1 scope, the GR collection is milestone-1 scope
too.

### Why NOT (c) — reusing `code_chunks`

Mixing requirement prose into the code-chunk collection **poisons code search** and **forces every
existing query to carry a type filter**. That is a permanent tax on the retrieval path in exchange
for saving one collection.

### Cross-reference

This is the *only* sanctioned use of Chroma in this design — **Q4** already established Chroma is
never the primary record.

---

## Q7 — Vehicle for the pending fact-graph decision: **DECIDED (a) 2026-08-24, scoped to ADDING**

**Decided: (a) — yes, explicitly.** This plan implements the **Layer-1 judgment store**, and
`fact-graph-decision.md`'s residue **(d)** is satisfied here. **With one hard scoping caveat that
must appear in the ExecPlan.**

### Why (a)

`docs/exec-plans/pending/fact-graph-decision.md` concludes that after **M22–25** fact-graph's
residue is four pieces, of which **only (d) — LLM-inferred facts Layer 0 cannot derive
(`business_rule`, `state_transition`, …) — genuinely needs a model.** A GR store is **precisely** a
home for (d): Q3c's four `structured_body` types include `state_transition`, and the whole store is
LLM-inferred-then-SME-confirmed content that Layer 0 cannot produce.

### ⚠️ The caveat — scope this plan to ADDING, never to RETIRING

`fact-graph-decision.md` gates its Option A on **M21** (the "does the index beat fact-graph"
evaluation), still open in `docs/exec-plans/active/semantic-code-search-graph-index.md`.

- **Building the GR store does not require M21** — it is **additive and removes nothing**, so
  proceed now.
- **But the ExecPlan must be scoped to *adding* the Layer-1 store, not *retiring* fact-graph.**
  Retirement stays M21's call.

That distinction is what keeps **M21 an honest evaluation** rather than a formality decided by
fait accompli. Any ExecPlan language that reads as "fact-graph is replaced by this" is a
violation of this decision.

---

## D2 — Durability vs git: **DECIDED (a) 2026-08-25 — committed JSONL export, DB authoritative**

**Decided: (a).** `knowledge.sqlite` stays gitignored (`.gitignore:88-89`) and remains the
**system of record**. Alongside it, a **committed text serialization** (JSONL, one GR per line,
sorted by `gr_id`) is a **deterministic export**. Same relationship Q1 gives markdown: a render,
not a source of truth.

**Direction of authority is one-way and explicit.** The DB writes the JSONL. The JSONL is read
back **only** via an explicit `import --from-jsonl` command, never silently and never on open.
Rationale: a stale checkout must not be able to overwrite `approved` state or SME-authored
`rationale`/`fit_criterion` (Q3j) behind the analyst's back.

### Why (a) — and the precedent already exists in this repo

Verified 2026-08-25 by lookup, not asked of the user:

| Pre-GR store | Path | Git status |
|---|---|---|
| **fact-graph context packs** | `repos/ctcm/ctcm-api/legacylift-docs/context/` — `index.json` + 57 `packs/*.pack.json` | ✅ **TRACKED** — 58 files, **30 MB**, the only committed store of any kind |
| Layer-0 index (`index.sqlite` + Chroma) | `repos/*/legacylift-docs/index/` | ❌ ignored — `.gitignore:83-84`, "derived, churn on every reindex" |
| Layer-1 knowledge (`knowledge.sqlite`, holds `file_domains`) | `repos/*/legacylift-docs/knowledge/` | ❌ ignored — `.gitignore:88-89` |
| code-mod `analysis/` outputs (`BUSINESS_RULES.md`, `DATA_OBJECTS.md`, `domains.json`) | inside `repos/nng-app-legacylift-analysis/` | ❌ ignored — `.gitignore:92`. **Zero** tracked `BUSINESS_RULES.md`, `DATA_OBJECTS.md` or `domains.json` anywhere in the repo |

Three things this establishes:

1. **"Binary ignored, text serialization tracked" is already this repo's pattern** for the one
   knowledge store it commits — and those packs carry Layer-1 judgment (`"domain": "Access"` at
   pack level and per-entity in `attributes`). (a) is not a new invention.
2. **The precedent is also a size warning.** 30 MB of JSON for one repo, regenerated
   **wholesale** every run, so git history carries the full churn. The GR export is deliberately
   **not** pack-shaped: hundreds of records rather than 6,047 entities + 38,618 facts, and Q5's
   merge semantics mean it changes **incrementally**. State this contrast in the ExecPlan.
3. **The failure mode D2 predicts is already live in `file_domains`** — LLM+human domain tagging,
   survives `--reset`, committed nowhere. Same loss exposure, cheaper asset, already happening.

### Scoping decision taken with it

**The JSONL export covers the GR tables only.** Exporting `file_domains` is a real gap
(finding 3 above) but it is Layer-1 domain-tagging scope with its own home; folding it in widens
this ExecPlan for something it does not own. Record it as a known gap, do not build it here.

**Rejected:** (b) un-gitignore and commit the binary — merge-conflict generator, forfeits diff
review, which is where SME judgment actually gets discussed. (c) accept local-only and defer to
`hosted-data-store.md` — makes Q5's accumulated judgment unrecoverable when a laptop dies, and
Q5's accumulated judgment is the design's stated differentiator.

---

## D3 — Migration mechanism: **DECIDED (a) 2026-08-25 — build a real versioned mechanism, both DBs, own milestone**

**Decided: (a).** This plan **builds** a real versioned migration mechanism — `PRAGMA
user_version` plus ordered, forward-only migration steps — and applies it to **both**
`index.sqlite` and `knowledge.sqlite`. It is **its own milestone, sequenced BEFORE the GR
tables land.**

### The verified starting position (re-confirmed 2026-08-25)

- **No schema `ALTER TABLE` anywhere in `src/`.** The only hits in
  `tools/legacylift_search/src/` are SQL-*parser* regexes in `extractors.py` (`:449`, `:454`,
  `:966`, `:1742`, `:1810`) that read `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY` out of
  client DDL. Nothing in the codebase alters its own schema.
- **No `PRAGMA user_version`** anywhere.
- **`SCHEMA_VERSION = "1"`** is set at `indexer.py:38` and *written* at `indexer.py:666` (plus
  reported at `:686` and `:1194`) — **never compared**. It is a label, not a mechanism.
- Adding a **table** is free (idempotent `CREATE TABLE IF NOT EXISTS` in `migrate()`); adding a
  **column** is unsupported and today requires `index --reset`, which deletes the DB.

### Why (a), and why both DBs

D3's own post-Q4 nuance is the argument: `knowledge.sqlite` survives `--reset`, so its
*destruction* path is narrower — **but that cuts both ways.** The store that survives resets is
exactly the one that **will** need column evolution, and there is no mechanism to do it. Q3l
already schedules a later milestone that adds tables (`term`, `fact_type`), and Q5's lifecycle
guarantees the GR columns will move.

**Both DBs, not just `knowledge.sqlite`,** because scoping it to one leaves `index.sqlite` as the
exception that reintroduces the problem, and the marginal cost over doing one is small.

**Consequence accepted:** this is scope **this plan owns and pays for** — unlike M26/M27, which it
merely declares a dependency on. It also retires the `ak1:`/`ch1:` prefix caveat in SPEC-3 §S3.1
("The repo currently has no such mechanism"): after this milestone, it does.

**Rejected:** (b) scope to `knowledge.sqlite` only — leaves the known-broken path in place.
(c) additive-only discipline with no mechanism — not a real answer for a store whose own roadmap
(Q3l) extends its schema.

---

## D7 — Which fact-graph Phase-0 consumers re-point: **DECIDED (a) 2026-08-25 — ZERO re-point**

**Decided: (a) — no consumer re-points in this plan.** All 13 Phase-0 consumers keep reading
fact-graph packs. The GR store is **purely additive**, exactly as **Q7** scoped it.

### The question as filed bundled three separable things

D7 read "which of the 13 consumers re-point at the GR store." Reading the consumer contract
(`fact-graph-decision.md` §2b) against SPEC-3 shows three independent threads:

| Thread | What it actually is | Owner |
|---|---|---|
| 1. Consumers reading GRs from the store instead of the `business_rule` predicate query | a genuine content overlap | **this plan** |
| 2. SPEC-3 re-keying the pack format (§S3.1 `anchor_key`, §S3.6 domain out of the id) | a Layer-0 identity change | **not a present blocker — see below** |
| 3. The pack-emitter shim itself (residue **(a)**) | does not exist; Option A's primary blocker | **nobody — unowned** |

### Thread 2 collapses on a verified fact

`.claude/skills/fact-graph/SKILL.md` contains **zero** references to `legacylift-search`,
`index.sqlite`, or `symbols`. fact-graph is a standalone LLM-driven skill that mints its own ids
from its own Python snippet (`{prefix}:{domain}-{normalized_name}-{hash}`, `SKILL.md:912`,
formula at `:942-947`). **So adding `anchor_key` as a computed column on `symbols` is invisible to
fact-graph and to all 13 consumers.**

⚠️ **Correction to SPEC-3 §S3.1.** Its sentence "it re-keys `symbols` **and** the fact-graph pack
format, so it must ride the pack-emitter shim" is only true **once a Layer-0-backed pack emitter
exists** — and §2b's 2026-08-05 note records that none of legacylift-search's 15 CLI commands
writes `legacylift-docs/context/`. As written it reads as a gate on this plan's milestone-1
identity work. It is not. **`anchor_key` ships additively in Milestone 1 and breaks nothing.**

### Why zero re-point on thread 1

The measurement taken while closing D7 (recorded in `fact-graph-decision.md` §5a.5 and
`fact-graph-explanation.md` §9) makes the overlap look *more* attractive, not less — fact-graph's
620 `business_rule` facts are 1.6% of its output and one sample is a bare `throw` statement read as
a rule, versus adversarially-verified Rule Cards in the GR store. **Re-pointing would be a quality
win.** It is still the wrong move here:

1. **Q7's scoping forbids it.** Re-pointing the `business_rule` query moves fact-graph's *only*
   non-redundant contribution (residue **(d)**) to the new store while **M21** is still supposed to
   be evaluating whether the index beats fact-graph. That is deciding M21 by fait accompli — the
   precise failure Q7 was scoped to prevent.
2. **It buys quality, not capability.** §2b part 3: every consumer has a working
   non-fact-graph fallback; **no skill hard-depends on fact-graph.** Nothing is unblocked by
   re-pointing.
3. **The real blocker is not consumer readiness.** §2b answered "is the contract stable enough to
   re-point?" with **yes** back on 2026-07-13. What is missing is **residue (a) + (b)** — the pack
   emitter and the semantic-typing pass — and §5a.5 establishes both are **scheduled on no plan**.

### ⚠️ The consequence being accepted out loud

Q7 option (b) was "explicitly accept two Layer-1 stores." **(a) accepts that too — it just
doesn't say so.** For the duration, fact-graph packs and the GR store both hold business rules
over the same code, at very different quality. That is a real cost and it is **accepted
deliberately**, on the grounds that M21's integrity is worth more than removing a duplication of
620 shallow facts. **State it in the ExecPlan as a known, time-boxed duplication whose exit is
M21 — not as an oversight.**

### Two things D7 must record for downstream plans

1. **SPEC-3 §S3.1's "must ride the pack-emitter shim" is re-scoped** to a *future* obligation
   contingent on the shim existing, not a present dependency of this plan.
2. **`citation-validator` and the `business_rule` query are the two identified re-point
   candidates** — recorded as **M21 inputs**, i.e. evidence *for* the evaluation, never a decision
   taken ahead of it. ⚠️ **Correction to an earlier draft of this entry:** it claimed
   fact-graph emits no entity `content_hash`. It does — `attributes.content_hash`, 6,047/6,047 —
   so citation-validator's drift detection **does** work today and the case for re-pointing it is
   *weaker*, not stronger: there is no broken capability to rescue. Both hash grains are real
   (`snippet_hash` 38,618/38,618).

**Rejected:** (b) re-point only requirement-shaped consumers — the trap; it decides M21 piecemeal
while claiming not to. (c) re-point all 13 — impossible anyway, since Layer 0 has no pack emitter
and no semantic entity typing, so 11 of the 13 would lose their fast path entirely.

---

# Open Frontier — ✅ **EMPTY. CLOSED IN FULL 2026-08-24. BACKGROUND ONLY.**

⚠️ **Nothing here is open.** The last four questions — **Q4, Q5, Q6, Q7** — were answered
2026-08-24, all four at the standing recommendation, and are recorded in the
**Decision Log (SETTLED)**, which is the authority. This chapter is retained **only** because the
option spaces and the evidence behind each recommendation are useful when implementing.
**Do not re-ask anything in it.** All research was already complete when the frontier closed.

⚠️ **THE ENTIRE Q3 BRANCH IS CLOSED (2026-08-24) AND MUST NOT BE RE-ASKED.** All twelve
sub-questions plus the two earlier Q3 decisions are in the **Decision Log (SETTLED)**, which is
the authority:

| Settled | Decision in one line |
|---|---|
| **Q3-backfill** | nothing is ever migrated → `NORMATIVE SPEC-2` |
| **Q3b-notation** | how 29148 and SBVR compose → `NORMATIVE SPEC-1` |
| **Q3a** | `as_built` + `statement`, each with its own confidence |
| **Q3b-strictness** | validator enforced; `ERROR` gates `approved` only |
| **Q3c** | generic `structured_body` JSON, DMN-shaped, four types |
| **Q3d** | subject derived from `file_domains`; LLM-named fallback flagged |
| **Q3e** | story is a rollup GR `kind`; producer deferred to milestone 2 |
| **Q3f** | the new shape replaces the extractor's G/W/T; scenarios subordinate; `implementation_notes`; `V-STY-03` stays WARN |
| **Q3g** | both denominators; `not_accounted_for = 0` enforced |
| **Q3h** | computed `reads[]`/`writes[]`; flagged LLM-inferred fallback on graph silence |
| **Q3i** | two enums; `modality` extractor-proposed, SME-confirmed |
| **Q3j** | `rationale`/`fit_criterion` extractor-forbidden; `assumptions` permitted |
| **Q3k** | advisory tier on `enforcement_level`, not `category`; `Lifecycle` kept |
| **Q3l** | `term`/`fact_type` vocabulary layer, sequenced as a later milestone |

**How Q3 branched, for the record:** Q3a–Q3h were opened 2026-08-19; **Q3i and Q3j added
2026-08-20** by the notation survey; **Q3k added 2026-08-21** from Von Halle ch. 2; **Q3l added
2026-08-21** from the vocabulary-layer convergence (§18d). Q4–Q7 were always the remainder of
round 1 and were unaffected by the branch.

## Q3 — Requirement form — ✅ **CLOSED IN FULL 2026-08-24. BACKGROUND ONLY.**

> ⚠️ **Every sub-question below (Q3a–Q3l) is ANSWERED.** The **Decision Log (SETTLED)** is the
> authority for what was decided and why; this section is retained because its option spaces,
> evidence tables and the **Candidate field list** remain useful when implementing. **Nothing
> here is open. Do not present it, do not re-ask it, and where this text and a Decision Log entry
> disagree, the Decision Log wins.**

### (historical framing, as written before the answers)

**Status of this branch:** reopened at the user's request. All eight original sub-questions
survive, **Q3b and Q3c are materially restated** (their option spaces were widened by the
survey), and **four new sub-questions (Q3i, Q3j, Q3k, Q3l) are added** because later research
produced decisions that do not fit inside any existing branch. The Q3 branch was twelve
questions; **all twelve were answered 2026-08-24. The Q3 branch is closed and the frontier is
four — Q4, Q5, Q6, Q7.**

No original recommendation was reversed. Two were sharpened (Q3b, Q3c), five gained
independent external corroboration (Q3a, Q3d, Q3f, Q3g, Q3h), one is unchanged and still
deferred (Q3e).

### The core framing (unchanged — and now corroborated by five independent sources)

Forward requirements engineering writes normative statements before code exists ("the system
shall"). Reverse engineering reads code that exists and produces descriptive statements ("the
code does"). **These are different claims, and the current Rule Card conflates them.**

The seam is visible in the real NNG output: a `Then` clause that says "It returns true,
causing a BusinessValidationException" is descriptive and provable from source (confidence =
extraction fidelity), while the `suspectedDefect` field beside it admits the code may not
match business intent (confidence = business intent, answerable only by an SME). One
`Confidence: Medium` field currently carries both, which is why "Medium" is nearly
uninformative across 470 rules.

What the survey added — the framing is no longer just reasoning:

| Source | What it contributes |
|---|---|
| **Leveson et al., TSE 1994 (TCAS II)** | "the basic information was all there, **the intent was missing.** Therefore, distinguishing between requirements and artifacts of the implementation was not possible in all cases." A funded team, source in hand, expert reviewers available — and they could not do it. §13 |
| **Chaparro et al., WCRE 2012** | The same conflation, **measured**: 29% correct business rules, **36% "implementation rules"**, 35% incomplete/incorrect. §15 |
| **Feathers 2004, p.188** | "That doesn't mean that we don't include the test in our test suite; instead, we should **mark it as suspicious**." §4 |
| **KAOS (van Lamsweerde)** | Already splits DomPre/DomPost (what the domain does) from ReqPre/ReqPost (what the requirement imposes) — the same split, in a 1993 notation. §3 |
| **Gannod & Cheng** | Supplies the vocabulary: **"as-built specification"** for the descriptive half, **"implementation bias"** for what leaks into the normative half. §19 |
| **van de Hoef et al. 2026** | A **third independent measurement**, and the first on Java: GPT-4.1 and Gemini 2.5 Pro "had difficulty **separating the source code from the decision made in the source code**." Worse, LLM knowledge of libraries "led to the actual values of the decision rules being **changed**" despite a prompt forbidding interpretation. §17e-bis |

The consequence is a design constraint, not an aspiration: **intent is
information-theoretically absent from code.** An extractor cannot populate it, so the schema
must have somewhere to put its absence.

The proposed shape is unchanged — a **layered** record: mandatory core (plain-English name,
normative statement + pattern, citations, dual confidence), 0..n G/W/T scenarios, and 0..1
typed body discriminated by category. One table plus two child tables.

### Candidate field list (consolidated from the survey — the concrete thing to react to)

The most useful column is **"filled by"**: it operationalizes the TCAS II finding. Every
SME-only field is one the extractor must leave empty *by design*; every derived field is one
no LLM should touch.

| Field | Provenance | Filled by | vs. today |
|---|---|---|---|
| `id` | **29148 cl. 5.2.8 Identification** — "**never changed** … **nor is it reused**" (stronger than ReqIF's "lifetime immutable", §9) | store | **absent** — dedupe key today is `{source-file}::{normalized-name}` (`extract-rules.js:256`); Layer-0 ids are line/hash-bearing so they cannot serve |
| `kind` | rule \| story \| expectation (Q3e, Q3i) | pipeline | new |
| `name`, `category`, `priority` | current Rule Card. ⚠️ `category` has **two verified gaps** (§17a-bis): no warn-don't-block tier (Von Halle's `guideline`) and `Lifecycle` has no counterpart in her taxonomy. 29148's own `Type` value set is systems-engineering-shaped and does **not** fit — borrow from Von Halle or Withall | extractor | exists |
| `subject` | 29148 Fig. 1 `[Subject]`; EARS `the <system>`; SOPHIST `<subject matter>` | **derived** from Layer-0 `file_domains` | new (Q3d) |
| `statement` | normative half; EARS pattern inside 29148's construct | extractor | splits the blended field |
| `pattern` | enum of the notation template used | extractor + validator | new (Q3b) |
| `as_built` (was `observed_behavior`) | Gannod & Cheng "as-built specification" (§19) | extractor, **cited** | new (Q3a) |
| `rule_class` | SBVR: **definitional** (alethic) \| **behavioral** (deontic) — §17a | extractor | new (Q3i) |
| `modality` | KAOS: **requirement** (software agent) \| **expectation** (environment agent) — §3 | extractor + SME | new (Q3i) |
| `enforcement_level` | SBVR cl. 24 — **valid only on `behavioral`**; a definitional rule cannot be broken | SME | new (Q3i) |
| `confidence_extraction` | "is the citation faithful" | extractor / referee | splits one field |
| `confidence_intent` | "is this the business's intent" | **SME only** | splits one field |
| `citations[]` | KDM's `implementation` property — "becomes the **'handle'** for the otherwise intangible… concept" (§1) | extractor | exists as `source` |
| `disposition` | AWS `traceability.yaml`: `captured \| not_applicable \| unreachable \| delegated \| not_accounted_for` | pipeline, gated | new (Q3g) |
| `scenarios[]` | G/W/T, re-authored implementation-independent | extractor | exists, re-shaped (Q3f) |
| `implementation_notes` | 29148 *Appropriate* (2011's *Implementation Free*); "implementation bias" | extractor | new (Q3f) |
| `structured_body` | 0..1, discriminated: **DMN decision table** \| state transition \| formula (`Scale`+`Meter`) \| **invariant** | extractor | new (Q3c) |
| `fit_criterion` | Volere — "**non-subjectively** test whether the solution fits"; one of the Robertsons' own load-bearing three | **SME-negotiated** | new (Q3j) |
| `rationale` | **29148 cl. 5.2.8** ("should be captured") + Volere + Planguage Fig. 4.12 | **SME only — empty by necessity on mined rules** | new (Q3j) |
| `assumptions`, `risks`, `issues` | **29148 cl. 5.2.7 — a normative `shall`**: "All assumptions made regarding a requirement **shall** be documented"; `risk` is a cl. 5.2.8 attribute; + Planguage Fig. 4.12 | extractor (assumptions) + SME | new (Q3j) |
| `suspectedDefect` | current; Feathers' "mark it as suspicious" | extractor | exists — **gains meaning** once Q3a splits the two halves |
| `smeQuestion` | current (required when confidence is not High) | extractor | exists |
| `reads[]`, `writes[]` | **computed** from Layer-0 data-access edges / `uses_table` / M24 `has_column` | **derived, no LLM** | new (Q3h) |
| `derived_from[]` | story → constituent rules rollup | pipeline | new (Q3e) |
| `status`, `owner`, reviewer + timestamp | **29148 cl. 5.2.8 Owner** ("approves changes … reports the status") + **Version Number** (volatility signal); Planguage "Basic Information"; §15's oracle argument | lifecycle | **Q5**, but §15 says capture from day one |

**KDM §20 supplies the vocabulary for the whole schema** and is ISO-backed (ISO/IEC
19506:2012): `TermUnit` (noun concepts) / `FactUnit` (verb concepts, incl. "a formula for
calculating an allowance") / `RuleUnit` (conditions and constraints) / `BehaviorUnit` /
`ScenarioUnit`, each with an `implementation` back-pointer to code. Adopting it as
*vocabulary* costs nothing and converts "we invented a rule schema" into "we implemented the
half ADM explicitly left to a 'difficult value-added knowledge discovery process'." Caveat:
KDM defines the container and **never the extraction**, ADM is dormant, and there is **no
requirements metamodel anywhere in ADM** — do not overclaim.

### Q3a — Split observed behavior from intended requirement?

Options: (a) **two fields on one GR** — `as_built` (descriptive, cited, "the code does X") and
`statement` (normative, "the &lt;subject&gt; shall X"), each with its own confidence, plus the
existing `suspectedDefect` as the flag that the two diverge; (b) **one blended field** as
today; (c) **two record types**, an Observation and a Requirement, linked many-to-many.

**Recommended: (a) — unchanged, and now the best-evidenced recommendation in the plan.** Five
independent precedents (table above) plus one measured error rate (36%). (c) is theoretically
cleaner but doubles the review surface and join complexity for a distinction that is 1:1 in
the overwhelming majority of cases.

**Survey updates:**
- Rename the field to **`as_built`** — "as-built specification" is the formal-methods
  tradition's own term for exactly this, and it is a better client-facing word than
  "observed behavior".
- Feathers' discipline must **cross from the test suite into the documentation layer**: any
  behavior-derived GR needs a provenance tag ("derived from observed behavior; intent
  unconfirmed") and a suspicion flag. §4's warning is blunt — presenting recorded behavior as
  a requirement "silently promotes every latent defect to a requirement… That is worse than an
  admitted gap because it is an unadmitted one."
- Leveson's team found the discrepancies they *did* identify "**merely represented design
  peculiarities of the pseudocode and not requirements**." So the split is not an accuracy
  improvement — it is the only honest way to record an irreducible ambiguity.

### Q3b — How strict is the notation — validated or advisory? **[RESTATED]**

**Why restated:** the original question asked *whether* to validate. That is now the easy
half. The survey found the validator's **content is standardized** — so the real question is
which published rubric it implements, and the honest performance envelope is known.

Options: (a) **enforced** — a `pattern` enum column plus a deterministic validator;
(b) **advisory** — store text and pattern, validator warns only; (c) **stylistic** —
notation-ish prose, no pattern column, no validator.

**Recommended: (a), with the validator implementing ISO/IEC/IEEE 29148:2018 rather than a
hand-rolled word list, and gating only the `approved` transition.** A bad extraction still
lands (you want the data); nothing reaches sign-off unconformant.

**What the survey changed — the validator is now a specification, not an idea:**

| Check | Source | Verbatim basis |
|---|---|---|
| Vagueness blocklist | **29148 cl. 5.2.7** | "Vague and general terms **shall** be avoided" — nine named classes: superlatives, subjective language, vague pronouns, ambiguous adverbs/adjectives **and 'or' / 'and/or'**, open-ended terms ("but not limited to"), comparatives, loopholes ("if possible", "as appropriate"), totality terms ('all','always','never','every'), incomplete references |
| Verb conventions | **29148 cl. 5.2.4** | requirements use **'shall'**; "**It is best to avoid using the term 'must'**"; 'will' = fact/futurity; 'should' = preference and "**They are not requirements**"; "**avoid negative requirements such as 'shall not'**"; "**Use active voice**"; "**Avoid… 'shall be able to'**" |
| Single `shall` | **29148 cl. 5.2.5 *Singular*** | "states a single capability, characteristic, constraint or quality factor." NOTE 2 permits multiple *conditions*. Independently reinvented by SOPHIST as "**one full verb per requirement sentence**" |
| Named subject present | **29148 cl. 5.2.4** prose ("A requirement **shall state the subject of the requirement**") **and Fig. 1's `[Subject]` slot** — figure verified 2026-08-21 | → feeds Q3d |
| **Template conformance itself** | **29148 cl. 5.2.5 *Conforming*** | "The individual items **conform to an approved standard template and style** for writing requirements." **This is the single best citation for the whole question** — conforming to a template is one of the nine mandatory characteristics, so the `pattern` column is required by the standard rather than merely advisable. Found 2026-08-21; the earlier draft missed it |
| Pattern conformance | EARS / 29148 Fig. 1 / Rupp | see the sub-choice below |

**A sub-choice the original question did not have: what does `pattern` enumerate?**
29148 Figure 1 (verified 2026-08-21) offers **two constructs**:
`[Condition][Subject][Action][Object][Constraint of Action]` and the shorter
`[Subject][Action][Constraint of Action]`. The five-slot form is **structurally EARS
event-driven with an explicit constraint slot**, so a well-formed EARS requirement satisfies
it. ⚠️ But **29148 never names EARS** (both editions grepped: zero substantive hits, and EARS
is absent from the 28-entry bibliography) — so "EARS is standards-conformant" is defensible;
"EARS is a standard" is false.

**Two implementation constraints the verified figure imposes on the validator** (details in §7):
- **The slots are not independently nullable.** In the short construct `[Object]` is *absorbed
  into* `[Action]` ("shall display pending customer invoices [Action]"), not omitted. A parser
  treating five slots as five optional fields will mis-parse it.
- **An empty `[Constraint of Action]` must not be a finding.** All three of 29148's examples
  bound the action, but its examples are performance-shaped; mined business rules are mostly
  conditional ("the system shall reject the order"), where no constraint of action exists.
  Where one *does* exist and is quantitative, treat it as the trigger to reach for Q3c's
  `formula` body rather than prose.

Independent support for keeping EARS's condition split: SOPHIST/MASTeR defines three
*separate* condition templates because German *"wenn"* is ambiguous — **FALLS/IF** (logical,
present tense), **SOBALD/AS SOON AS** (event, non-simultaneity), **SOLANGE/AS LONG AS** (time
period, simultaneity). That is non-EARS confirmation that EARS's `If` / `When` / `While` split
is **not arbitrary**.

**Calibrate the expectation — three numbers:**
- **The best argument for validating at all:** SCR's mechanical checks found **17 Coverage +
  57 Disjointness errors in 245 seconds** on the A-7E document *after* it had been reviewed by
  two expert teams. Verbatim: "our tools detected many significant errors that the reviewers
  missed." §13
- **The realistic ceiling:** Femmer et al., JSS 2017, "Requirements Smells" — the closest
  published analogue, transferring the code-smell metaphor precisely *because* 29148's
  criteria are not directly checkable — reports "**59% precision at 82% recall with high
  variation**", and that "some smells were not clearly distinguishable." **Expect a useful
  lint, not a gate.**
- **Direct prior art:** Arora, Sabetzadeh, Briand & Zimmer, IEEE TSE 41(10), 2015 — the Rupp
  template implemented as an **NLP conformance matcher**. This has been built before.

**And one reason the gate must stay advisory even where the check is mechanical:** SCR's own
authors, on false positives — "In some cases, nondeterminism may not be an error — in fact,
**requiring determinism can lead to overspecification of the requirements**." 2 of 19 A-7E
condition-table reports were false positives. **Flag, don't block** — what was already
recommended, now for a sourced reason.

**Where validator output should land — verified 2026-08-21.** 29148 cl. 5.2.8 defines a **Risk**
attribute whose definition is, verbatim, "Requirements that are at risk include requirements
that **fail to have the set of characteristics that well-formed requirements should have**."
So a lint failure is not an error state to be suppressed — it *is* the standard's `risk`
attribute. Write the finding to `risk`, gate only `approved`. That is the flag-don't-block
design with an SDO-sourced home for the flag.

⚠️ **Edition caveat on the 59%/82% number.** Femmer's smells are derived from **29148:2011**
(§7-ter), the superseded edition, so they do not map 1:1 onto the 2018 clauses this validator
would implement. Treat 59%/82% as the right order of magnitude, not as a measured result for a
2018-conformant checker. Per-smell variance is wide in the paper: precision 0.96 on subjective
language, 0.59 on another case, recall 0.5 on a rare smell — and a prior tool is cited at 12%
precision, so 59% is good for this class of check, not disappointing.

Evidence it matters at all: AWS Transform shipped without a validator and its own published
example requirement is mislabelled, multi-response (violating *Singular*), and carries COBOL
identifiers inline (violating *Appropriate*).

### Q3c — Typed bodies for decision tables / state machines / formulas? **[RESTATED — biggest change in the branch]**

**Why restated:** the original question treated typed bodies as a *storage shape* decision to
be deferred on cost grounds. The survey found that one body type is **executable**, and that
changes what the question is about. Q3c is now the only place in the entire plan where a
**measurable fidelity claim** is available.

Options as originally posed: (a) three typed child tables now; (b) one generic
`structured_body` JSON column, schema-validated per category; (c) flat cards only, defer.

**Recommended: still (b) — but the JSON for the decision-table type must be DMN-shaped
(serializable to DMN XML), not ad hoc, because executability is the point, not notation
aesthetics.** And the type list grows from three to **four**.

**The argument that changes the stakes — §17f(3), DMN-vs-legacy equivalence testing.**
§15 established there is **no oracle** for rule extraction: no benchmark, no ground truth,
~29% precision in the one honest measurement. But for the **decision-logic subset**
(Calculation, and much of Policy) a DMN table is executable, so **the legacy system becomes
the oracle**:

> extract to DMN XML → Drools/KIE **`ANALYZE_DECISION_TABLE`** for gaps, overlaps, masked /
> misleading / subsumed / contracted rules → **`COMPUTE_DECISION_TABLE_MCDC`** +
> **`MCDC2TCKGenerator`** to generate MC/DC-covering test cases → **replay `inputNode` values
> against the legacy system and diff against `resultNode/expected`.**

Every component was verified to exist. **The composition is unpublished.** It yields a
mechanical, quantitative fidelity measurement with no human annotation and no LLM in the
scoring loop — precisely what SparseAlign's "circular evaluation loop" warning says you
otherwise cannot get. It does not generalize (validation and lifecycle rules are not decision
tables, and coverage is bounded by what you can drive), but **it converts an unmeasurable
claim into a measurable one for the subset where money and correctness usually live.**

⚠️ **RESTATED 2026-08-21 after reading the only code→DMN paper in existence (§17e-bis).**
van de Hoef et al. reports **0% decision-rule F1 on three of its eight logic cases**, with
extraction collapsing past roughly six rules per table — on hand-picked single-file Java cases
of at most 19 rules. The Drools/KIE half of the chain above is unaffected (those tools were
verified independently), but the assumption that an extracted table is good enough to be worth
analysing does not hold. **Invert the framing rather than drop it: the equivalence loop is not a
validation of good extraction, it is the detector of bad extraction** — which given those numbers
makes it more valuable, not less, because it is the only place in this design where extraction
error is *measurable* rather than assumed. Design for rejecting most tables at first: a
`decision_table` body carries its own fidelity verdict, and failing the replay is an ordinary
recorded outcome (→ Q3g disposition, Q3a dual confidence), not an exception. **And do not promise
DMN coverage of the corpus** — the honest claim is "for the decision-logic subset we can *measure*
fidelity", not "we can extract decision logic reliably." One consequence for sequencing: measure
the **rule-count distribution per candidate table** in the first milestone alongside the
collapse-into-a-table count; if most candidates exceed ~6 rules, this paper predicts extraction
failure and the replay loop should wait.

**The four body types, and why each earns its place:**

| Type | Notation | Why | Checkable against |
|---|---|---|---|
| `decision_table` | **DMN 1.5** (`formal/24-01-01`, Aug 2024) | executable ⇒ oracle (above) | **legacy code**, mechanically |
| `state_transition` | mode/transition table | genuinely different shape; SOPHIST's SOLANGE/state case | — |
| `formula` | Planguage **`Scale` + `Meter`** + `Goal`/`Fail` thresholds | §12: for quantitative GRs the Scale/Meter decomposition is right and **G/W/T is the wrong shape** | — |
| `invariant` | contract/`invariant` clause | **§20.4 — new.** Uniquely, an invariant can be checked against **legacy production data**, not just legacy code | **production data** |

The invariant type has published inference precedent the others lack: **Daikon** (alive,
5.8.24 May 2026; checks 75 invariant kinds; emits JML / ESC-Java / Code-Contracts and ships an
`annotate` tool) and **Clousot necessary-precondition inference**, which ran "**directly on
the shipped binaries**" of contract-free `mscorlib.dll` and found necessary preconditions for
"almost **64%** of methods which contained warnings", in daily customer use since June 2011.
⚠️ Both need something we usually lack (a runnable build with an exercising workload, or at
minimum bytecode), and Daikon's own documented limit is overfitting to the test suite.

**Standards and practitioner support for typed bodies existing at all:**
- **29148, verbatim:** "**Condition-action tables and use cases are other means of capturing
  requirements**." Standards cover for not forcing everything into a sentence.
- **QRA's published "when NOT to use EARS":** don't force it when a requirement has more than
  ~3 preconditions or is best expressed as a mathematical formula — prefer lists, decision
  tables, diagrams, state-transition diagrams.
- The codebase **cannot currently `ALTER TABLE`**, so a JSON column evolves where a typed
  column could not. (Unchanged, still decisive for (b) over (a).)

**Three cautions the survey added:**
1. ⚠️ **"DMN gives mechanical gap/overlap checking" is true of tools, false of the standard.**
   The spec supplies the predicates and a single `SHALL`, **deleted its only explicit
   completeness construct in v1.1**, and leaves the algorithm to vendors. Drools/KIE is the
   real implementation. State it that way in any deliverable. Also: the **DMN TCK is still on
   1.4** — do not cite TCK results as 1.5 conformance; and **Trisotech does syntax-only V&V**,
   not gap/overlap analysis, contrary to common assumption.
2. ⚠️ **Do not model this on SCR/Parnas tables.** That earlier claim is **refuted** for
   business rules on five sourced grounds (§13): coverage checking requires enumerating every
   value every variable can take; the method's checkability rests on a small closed
   finitely-valued I/O boundary, and Heninger names the breakdown herself for general-purpose
   devices; modes must partition the state space and even the A-7E exemplar failed this; cost
   (17 man-months for 12K assembler lines; >$40M and 40kg of paper at Darlington); and **zero
   applications to business information systems in 45 years** — with the decisive signal that
   the McMaster group, who industrialised Parnas tables, reached for **dependency and
   change-impact analysis** when they attacked legacy enterprise code.
3. ⚠️ **Nursimulu & Probert (CASCON '95): the same decision table is produced whether or not
   the One-and-only-one / Inclusive / Exclusive constraints are present** — so **the table
   alone cannot detect a constraint omission.** Keep the constraint set (or the cause-effect
   graph) as a reviewable artifact in its own right, not just the table.

**Two things worth stealing for free:** DMN's own vocabulary — **contracted / expanded /
limited-entry** are verbatim spec terms; and the three-valued cell, which is one concept under
three names across 45 years — Elmendorf's 1970 enumeration base is **3ⁿ not 2ⁿ** (each cause
*invoked, suppressed, or ignored*), which is exactly Myers' blank in a limited-entry table and
exactly DMN's `-`.

**The void this lands in — the strongest negative result in the survey (§17e):** code → DMN is
**one 2026 SSRN preprint** (van de Hoef et al., DOI 10.2139/ssrn.6299556 — **now read in full,
§17e-bis**: still unrefereed, Java single-file, 10 hand-built cases, 0% decision-rule F1 on
three of eight logic cases). Code → decision tables: **nothing at all.**
"Decision mining" is a different field entirely — its input is always event logs or BPMN
models, **never source code**. And the sharpest observation in the whole survey: the slicing
literature **already computes exactly the path conditions a decision table needs** and then
presents them as slices or code fragments — "the dominant field definition of 'a business
rule' is literally an execution path over a business variable — **which is a decision table
row that nobody has written down as one.**" With the historical irony that 1962-1974 shipped a
dozen decision-table preprocessors compiling tables *into* COBOL (DETAB-X, DETAB/65, TABSOL,
LOGTAB…) and **nobody has published a tool that turns COBOL back into decision tables.**

**Still worth explicitly measuring in the first milestone:** how many of the 470 (or 815) NNG
rules actually collapse into a table. That number decides whether (a) is ever worth promoting
to — and it also sizes the equivalence-testing opportunity. If a taxonomy of body shapes is
needed, **Withall's 37 published requirement patterns** (§11) beat invented categories —
`Calculation Formula`, `ID`, `Data Longevity`, `Data Archiving`, `Transaction`, `Chronicle`,
`Approval`, `Fee/Tax` are close to what a legacy enterprise system actually yields.

### Q3d — Who is the subject of the normative statement?

EARS demands `the <system name> shall`. Candidates: (a) **the Layer-0 domain** of the citing
file — `file_domains` gives this deterministically and `domains.json` names are
business-capability-shaped ("Legal Entity", "Nomination"); (b) the **system/system-dir name**
(`customer.ple.nng.app`) — accurate but useless as a requirement subject; (c) the
**component/service the LLM names** from the code; (d) a literal "the system" everywhere.

**Recommended: (a), falling back to (c) when the file is `unassigned`, never (d) —
unchanged.** The shipped domain-tagging work makes the subject a *derived, consistent* value
rather than an LLM invention, so the same rule extracted twice gets the same subject; it
groups requirements by business capability in the render for free; and it satisfies the
draft's second implementation requirement (GR associated with a domain) against something
already canonical.

**Survey updates:**
- The subject slot is not an EARS quirk — it is a **required constituent of 29148's Figure 1
  construct** (`[Subject]`) and of SOPHIST's FunctionalMASTER (`<subject matter>`). Three
  independent templates demand a named subject; none permits "the system" as a placeholder.
- Deriving rather than generating it is the *Unambiguous* characteristic, done cheaply.
- If domain vocabulary is ever first-classed, **KDM's `TermUnit`** ("aligned with SBVR term or
  name concepts… some 'noun concept'") is where it belongs.
- **Still depends on Q4** for cost: cheap SQL join if GRs live in `knowledge.sqlite` (where
  `file_domains` is), Python-side join otherwise.

### Q3e — Do user stories exist, and at what level?

Options: (a) **no user-story layer** — GRs are rules/requirements only; (b) **user story as a
GR kind, authored as a rollup** over N rules where actor evidence exists (controller, auth
role, UI entry point), with a `derived_from` link to constituent rules; (c)
**`as-a/I-want/so-that` fields on every GR**, AWS-Transform-style.

**Recommended: (b), deferred to the Q2 future milestone — unchanged.** A story is a different
altitude than a mined rule, it needs citable actor evidence, and the rollup link gives the
traceability matrix (`US → UC → FR → RULE → code`) that `user-story-generator`'s template
already draws but cannot substantiate. Avoid (c): per-rule actors will be fabricated, because
mined code usually does not say who the user is. AWS Transform validates the *altitude* choice
— its user story is the **section heading** over a group of numbered requirements, not a
per-requirement field.

**Survey updates (all supporting, none changing the answer):**
- **iStar 2.0** separates **Role** from **Agent** — "the abstract actor a story is written
  for" vs "the concrete system component" — and its actor links are exactly `is-a` /
  `participates-in`. Worth borrowing if (b) is ever built. ⚠️ But do **not** adopt i\* as the
  notation: iStar 2.0 explicitly excludes any methodology or completion criterion ("when can a
  model be considered final?"), has no formal semantics, and has had no successor in 10 years.
  Only **piStar** is still maintained; OpenOME, jUCMNav and TAOM4E are dead.
- **29148 NOTE 2** concedes "Requirements in agile may use alternative formulations such as
  user stories without explicitly using the term 'shall'" — so a story layer does not breach
  the standard, but it also gets no template from it.
- Where actor evidence *does* live in code is enumerable: **Withall's Access Control domain**
  (User Registration, User Authentication, Specific Authorization, Configurable Authorization,
  Approval) is the published list of shapes to look for.
- ⚠️ Sobering precedent for the goal/story-recovery ambition generally: **Yu et al., RE'05,
  "Reverse engineering goal models from legacy code"** is a validated four-step pipeline
  (SquirrelMail, Columba) with **74 citations in 21 years**, only ~10 continuing the thread,
  and `title.search:goal-oriented reverse engineering` returns **count: 0** in OpenAlex.
  Validated, published, and essentially abandoned — an opportunity, not a mature practice.

### Q3f — What shape do G/W/T scenarios take in the new schema? **[RETITLED 2026-08-24]**

⚠️ **RETITLED because the old title — "What happens to the existing G/W/T text?" — read as a
migration question and contradicted `NORMATIVE SPEC-2`. It never was one.** Nothing is ever
migrated: the 470/815 NNG rules are **reference data, never input**, and the store starts empty.

**What "existing" actually referred to: the extractor's own current output shape, on runs that
have not happened yet.** `extract-rules.js:80` makes `given`, `when`, `then` **required** fields
on every rule in `RULES_SCHEMA` (plus an optional `and`), and the referee schema at
`extract-rules.js:139` asks "Is the Given/When/Then faithful to what the cited code does?" So
G/W/T is the pipeline's native output format **today**, and will be what the first run against
the new store produces unless the prompt and schema change.

**SCOPE, stated by the user 2026-08-24:** the new requirement shape **replaces** the current
extractor's G/W/T. G/W/T stops being *the requirement*. The normative record is SPEC-1's
`statement` (with Q3a's `as_built` beside it); scenarios become a **subordinate 0..n child**, not
the primary content. Q3f decides what that child looks like — it does **not** decide whether to
keep the old text, because there is no old text to keep.

The current scenarios are implementation-shaped ("returns true, causing a
BusinessValidationException"). Options: (a) **keep verbatim** as `scenarios`; (b) **re-author
to be implementation-independent** and keep legacy symbol/exception names in a separate
`implementation_notes` field; (c) keep verbatim and add a lint that flags leakage for human
cleanup.

**Recommended: (b) — unchanged, and now the recommendation with the clearest standards
mapping. But the survey argues for (b) *plus* (c)'s lint, not (b) alone.** The legacy method
and exception names are genuinely valuable — they are how you find the code again and how a
characterization test asserts current behavior — but they belong in an evidence field, not in
acceptance criteria a rewrite is judged against. Costs nothing extra at extraction time (the
extractor has both in hand); a prompt change, not new analysis. AWS Transform does the
opposite and its requirements are the worse for it.

**Survey updates:**
- This is exactly **29148's *Appropriate* characteristic** — "avoiding unnecessary constraints
  on the architecture or design while allowing implementation independence to the extent
  possible." ⚠️ Note the edition drift: *Implementation Free* was a 2011 characteristic,
  **absorbed into *Appropriate* in 2018**. Any checklist citing "implementation free" as a
  29148 characteristic is keyed to the superseded edition.
- The formal-methods tradition already names the defect: **"implementation bias"** (§19).
- **Chaparro measured it at 36%** of recovered rules — the single largest error class in the
  one honest published measurement. This is not a tidiness issue.
- ⚠️ **But TCAS II says the cleanup cannot be completed, only recorded.** Leveson: "we had
  difficulty abstracting away from the design… to **specify the problem without trying to
  solve it**. With practice we became better at omitting design information, but **the struggle
  never entirely abated**." So (c)'s lint is not an alternative to (b) — it is the honest
  *supplement* to it, feeding Q3b's validator.
- And the deeper warning: mined specs are **inherently more complex than greenfield ones** —
  "our resulting model is more complicated than necessary… we first built a nice, simple model
  and found that we had to complicate it for no better reason than that it had to match some
  errors or poor decisions in the pseudocode." That is an argument for `suspectedDefect` and
  for the preserve-vs-fix decision being a **recorded, first-class transition**.
- Where G/W/T is the *right* shape: §12 — for conditional business rules (the bulk of the
  corpus) **a G/W/T scenario *is* the fit criterion**. For quantitative GRs it is the wrong
  shape (→ Q3c `formula`).

### Q3g — Adopt a disposition model with a zero-invariant?

AWS's `traceability.yaml` gives every extracted rule a `disposition`:
`captured | not_applicable | unreachable | delegated | not_accounted_for`, with
**`not_accounted_for = 0`** as auditable proof no business logic was lost. Note a *different*
denominator already exists: `legacylift-search coverage --claimed` returns
`{total, claimed, uncovered, pct, uncovered_chunks}` and drives extract-rules' loop-until-dry
(`workflows/extract-rules.js:207-231`) — that measures "did we look at all the code," AWS's
measures "was every rule carried forward."

Options: (a) **adopt both** — keep chunk-level coverage as the extraction denominator, add a
`disposition` enum on the GR (or on the GR→citation link) with an enforced
`not_accounted_for = 0` gate before a run counts as complete; (b) chunk coverage only;
(c) disposition as free text, no enum, no invariant.

**Recommended: (a) — unchanged, still the single most valuable thing to steal from AWS, and
the survey raised its value rather than merely confirming it.** It converts "we found 470
rules" (unfalsifiable) into "67 rules, 46 captured, 21 not applicable, 0 unaccounted"
(auditable by a client). `unreachable` composes well with the already-shipped `exclude_globs`
/ `excluded` domain tier: dead code leaves the denominator honestly rather than silently. Two
of the five values (`delegated`, `unreachable`) may want renaming for a non-mainframe context.

**Survey updates — this is now a positioning decision, not a bookkeeping one:**
- **§15's central consequence:** disposition + `not_accounted_for = 0` is disproportionately
  valuable **precisely because the field has no benchmark**. It is an *auditable completeness*
  claim in a domain where nobody can make an *accuracy* claim. Given ~29% precision as the one
  honest number, that is the strongest defensible quality story available.
- **Only deterministic numbers are self-reportable.** SparseAlign names the failure mode:
  organizations "risk a **circular evaluation loop, where unverified LaaJs are used to assess
  model outputs**"; AgentModernize's 92.3%/90.2% is the worked example — its oracle was
  "drafted by the primary annotator with LLM assistance (GPT-4o enumerated candidate rules from
  the legacy code)", i.e. **seeded by an LLM reading the very code the pipeline is scored on**.
  Coverage and disposition are computed, not judged, which is exactly why they are the numbers
  we can print.
- **The long-game argument (§15, consequence 3):** approved, SME-signed-off GRs with code
  citations *are* the ground-truth artifact the field lacks. Architecture recovery had to write
  a whole ICSE paper (Garcia et al., ICSE 2013) whose contribution **was the oracle**; our
  store accumulates one as a byproduct. That argues for capturing **reviewer identity,
  decision, and timestamp on every lifecycle transition from day one** — a Q5 mechanism, but
  the reason for it is here.
- Corroboration that the *invariant* framing is sound rather than novel: SCR's checkable
  obligations (Coverage, Disjointness) are the same idea one layer down, and they found 74 real
  defects post-expert-review in 245 seconds.
- **NEW 2026-08-21 — the measured failure mode is omission, which is exactly what this catches.**
  van de Hoef et al. (§17e-bis) found that unlike GPT-3 in the prior natural-language work,
  GPT-4.1 and Gemini 2.5 Pro **did not hallucinate rules to fill gaps**: they "would rather
  **omit** decision rules or express the same concept more extensively than to devise a decision
  rule itself to create a complete decision table." A completeness invariant is therefore aimed
  at the right risk, and hallucination defences matter *less* than coverage defences.

### Q3h — Attach a deterministic data-flow block to GRs?

Each AWS requirement section carries `Data flows: Reads / Writes` naming datasets, derived
from its data-lineage pass. Layer 0 has the equivalent already: data-access edges and
`uses_table`, plus M24 `has_column` facts and `foreign_key` edges. Options: (a) **derive
reads/writes deterministically** from Layer-0 edges for the GR's cited symbols, no LLM;
(b) have the extractor LLM state them as prose; (c) omit.

**Recommended: (a) — unchanged.** A case where we can be strictly better than AWS rather than
equal: their block is LLM-generated in the same pass as the prose, ours would be *computed*
from the graph and therefore checkable. Enables a query nobody else has ("which requirements
touch table AGREEMENT?"), which is exactly what a data-migration workstream asks.
**Caveat unchanged:** T-SQL `uses_table` currently reports aliases as datastores, so this needs
a normalization step or it produces junk table names.

**Survey updates:**
- This is **KDM's `implementation` property** applied to data rather than code — the same
  "extent"/"handle" mechanism, which is the ISO-standardized shape for the whole citation
  design (§1).
- It is also the one place the survey's negative results *don't* apply: reads/writes are
  computed from a graph, so no oracle problem, no confidence field, no SME question. §15's
  "only deterministic numbers are self-reportable" makes this block one of the few things in
  the record we can assert flatly.
- Mild counterweight worth knowing: when the McMaster group attacked legacy *enterprise* code
  they used dependency and change-impact analysis — i.e. **the graph, not the tables** (§13).
  That is a vote of confidence in Layer 0 being the right substrate.
- **NEW 2026-08-21 — a named gap in the only code→DMN paper that we can fill from Layer 0.**
  van de Hoef et al.'s stated limitation, verbatim: "each decision table was extracted
  separately, i.e., **dependencies between decisions were not included, as the LLMs did not
  receive the context of other decisions**." We have those dependencies deterministically (call
  edges, `uses_table`, M24 `has_column`). **Supplying inter-decision dependency context from the
  graph rather than hoping an LLM infers it is a concrete differentiator over the published state
  of the art**, and it is the same mechanism this question already recommends. See §17e-bis.

### Q3i — Modality: requirement vs expectation, and definitional vs behavioral? **[NEW]**

Two orthogonal distinctions surfaced by the survey, each airtight in its source, each absent
from the current Rule Card, and both conflated in mined output today.

**(i) KAOS — requirement vs expectation (§3).** A goal assigned to a **software** agent is a
**requirement**; a goal assigned to an **environment** agent is an **expectation**. Verbatim:
"Unlike requirements, assumptions **cannot be enforced by the software-to-be**." Mined rules
contain plenty of the latter ("the upstream feed provides validated data") and currently state
them in the same voice as things the system actually enforces. KAOS also splits **domain
invariant** ("known to hold in every state" — a physical law, a regulation) from **domain
hypothesis** ("assumed to hold"); note the taxonomy is parent/child, not siblings.

**(ii) SBVR — definitional vs behavioral (§17a).** Confirmed three independent ways: the
definitions of both terms, **Clause 24's different enforcement semantics**, and the fact that
the spec defines **`is violated` only for behavioral rules**. Mapping: **alethic modality →
definitional rule** (cannot be violated — it defines what is true); **deontic modality →
behavioral rule** (can be violated — needs enforcement and a violation response).

Options: (a) **two enum fields** — `modality` (requirement | expectation) and `rule_class`
(definitional | behavioral) — with `enforcement_level` valid only when
`rule_class = behavioral`; (b) `rule_class` only, treat expectations as a `category` value;
(c) neither — leave both conflated, as today.

**Recommended: (a).** Both are cheap enums the extractor can attempt and an SME can correct,
both are load-bearing downstream (an expectation must not become a test case for the
system-to-be; a definitional rule must not be given an enforcement level it cannot have), and
each has a standards-grade source. The specific implementation rules:
1. `alethic → definitional`, `deontic → behavioral`.
2. **Attach enforcement levels only to behavioral rules.** A definitional rule has no
   enforcement level because it cannot be broken.
3. ⚠️ **Do not call the six enforcement levels normative SBVR** — they appear under an
   `Example:` caption, SBVR §6 declares examples purely informative, and they trace to **BMM**,
   not RuleSpeak.
4. ⚠️ **Do not adopt KAOS or i\* as the notation** (§20.5) — dead-or-dying tooling, no live
   code-recovery practice, and zero papers on recovering KAOS models from source. **Steal the
   concepts as fields.** Likewise **drop OCL entirely** — frozen at 2.4 (Feb 2014), the spec
   itself concedes "OCL expressions are not by definition directly executable", and it
   constrains a *UML model* rather than source.
5. **Von Halle's taxonomy is now verified (§17a-bis) and it lands directly on this question.**
   Her `mandatory constraint` vs `guideline` split *is* an enforcement-level distinction
   first-classed as a category: a guideline "does not force the circumstance to be true or not
   true, but merely warns about it, **allowing the human to make the decision**." That is
   deontic modality with a weaker enforcement level, reached from the business-analyst side
   rather than the SBVR side. **Consequence: our `category` enum has no warn-don't-block tier**,
   so advisory rules in the corpus are currently promoted to mandatory `Validation` silently.
   Fixing that is arguably more urgent than either enum in this question.
   ⚠️ Still do not print: "**is by definition**" is **not** a RuleSpeak keyword.

### Q3j — Do we ship SME-only fields that the extractor must leave empty? **[NEW]**

The survey's hardest finding is that some fields **cannot** be populated from code, ever.
TCAS II: "the basic information was all there, **the intent was missing**", and the audit
trail of decisions "**was not done for TCAS** over the 15 years of its development." §15 then
closes the escape hatch — there is **no human oracle either**: business rules are
"**incompletely understood by those who own, use and maintain such systems**" (Earls, Embury &
Turner, BT 2002).

So `rationale` and `fit_criterion` are not fields we are failing to fill — they are fields
whose emptiness is the product's most useful output.

Options: (a) **carry them as first-class fields, extractor-forbidden, SME-fillable**, and
report their fill rate as a review-progress metric; (b) carry them but let the extractor
populate them ("best guess"); (c) omit them until an SME workflow exists.

**Recommended: (a), and treat the empty field as a feature.** Rationale:
- **NEW, and it upgrades this question from "good practice" to "the standard says so"
  (verified 2026-08-21):** 29148 **cl. 5.2.8** lists **Rationale** as a requirement attribute
  ("The rationale for establishing each requirement should be captured… points to any supporting
  analysis, trade study, modelling, simulation or other substantive objective evidence"), and
  **cl. 5.2.7 carries a normative `shall`**: "**All assumptions made regarding a requirement
  shall be documented and validated in one of the requirement's attributes in 5.2.8 (e.g.,
  rationale)**." For mined rules — where the extractor is assuming constantly — `assumptions`
  is therefore the most defensible new field in the entire list, and `rationale` now has an SDO
  source rather than only Volere's and Gilb's recommendation.
- **Volere's own triage is the argument for minimalism**: of 13 snow-card fields the Robertsons
  say "**We will concentrate on the main three — Description, Rationale, and Fit Criterion —
  and ignore the rest of the card.**" Two of their three load-bearing fields are the two an
  extractor cannot fill.
- **Volere's method makes the emptiness productive**: establish the fit criterion *after* the
  rationale, and "**by negotiating the Fit Criterion with the stakeholder, you (and the
  stakeholder) learn more about the real need**." That reframes `rationale` from "a field the
  extractor populates" to **"the field that structures the SME conversation"** — a better
  product story than a filled-in guess.
- **(b) is actively harmful.** An LLM-invented rationale is unfalsifiable, indistinguishable
  from a real one, and would poison the store's value as an accumulating oracle (§15).
- **Planguage supplies the rest of the shape** (Fig. 4.12): `Rationale`, `Assumptions`,
  `Risks`, `Issues` as separate fields — `Assumptions` is the one the *extractor* legitimately
  fills (what it had to assume), which is distinct from `suspectedDefect` (what looks wrong)
  and from `smeQuestion` (what to ask). Fig. 4.12's `Version`/`Status`/`Owner` block is
  independent 1989-vintage corroboration of Q5's lifecycle recommendation.
- **Three traditions converge on the fit criterion and differ usefully** (§12): Volere's single
  `Fit Criterion` collapses success and failure; **Planguage alone distinguishes "good enough
  to claim success" (`Goal`) from "bad enough to be a failure" (`Fail`/`Survival`)**; 29148
  makes verifiability a mandatory *characteristic* rather than a field, and gives verification
  its own document section (§4, parallel to §3) — which means **a GR store that can emit a
  verification section keyed to each requirement is emitting the part IEEE 830 lacked.**
- ⚠️ **Licensing:** borrowing Volere field *names* and the fit-criterion *concept* is ordinary
  practice; copying the 90-page template into a product is not ($55/$255, and the licence
  forbids commercial use beyond "a basis for a requirements specification"). The snow card
  alone is free. Label precision if borrowed: `Requirement #`, `Fit Criterion` (singular),
  "Customer" prefixes both satisfaction fields, and there is **no `Release` field**.

### Q3k — Does the `category` enum change shape? **[NEW 2026-08-21]**

Prompted by reading Von Halle ch. 2 from the book (§17a-bis). **This is a live defect in shipped
output, not only a taxonomy question.**

Today's enum is `Calculation | Validation | Lifecycle | Policy`
(`commands/modernize-extract-rules.md:116-141`). Von Halle's verified seven-class taxonomy maps
onto it cleanly in two places and fails in two:

| Von Halle | Ours | |
|---|---|---|
| Computation | `Calculation` | clean — her definition even enumerates the operations ("sum, difference, product, quotient, count, maximum, minimum, and average") |
| Mandatory constraint | `Validation` | clean |
| Inference | `Policy` (partly) | creates a new *fact* |
| Action enabler | `Policy` (partly) | initiates an event outside the boundary; "think of mandatory constraints and action enablers as **opposites**" |
| **Guideline** | **nothing** | **GAP.** "Does not force the circumstance to be true or not true, but merely warns about it, **allowing the human to make the decision**" |
| — | **`Lifecycle`** | **GAP.** Her four ways a rule guides a business event contain no state-transition class |

Options: (a) **add a warn-don't-block tier *and* justify or drop `Lifecycle`**; (b) add the
warn-don't-block tier only, leave `Lifecycle` unexamined; (c) leave the enum alone.

**Recommended: (a).** Two separate reasons, of different urgency:

1. **The missing advisory tier is a correctness bug, not a gap.** Every warn-don't-block rule in
   the corpus is currently classified `Validation` and thereby **silently promoted to
   mandatory** — a modernized system built from that output would reject where the legacy system
   warned. This is the same distinction Q3i reaches from the SBVR side (deontic modality with a
   weaker enforcement level), arrived at independently from the business-analyst side. If Q3i's
   `enforcement_level` is adopted, the advisory tier may be expressible as an enforcement level
   rather than a category — **that is the real sub-choice here**, and it is worth deciding
   together with Q3i rather than separately.
2. **`Lifecycle` needs its own justification.** It has no counterpart in Von Halle, and none in
   29148 either — whose `Type` value set (Functional/Performance, Interface, Process, Quality,
   Usability, Human Factors) is systems-engineering-shaped and does not fit business rules at
   all. So the value set must come from **Von Halle** or **Withall's 37 patterns** (§11), and
   `Lifecycle` currently belongs to neither. Either justify it from the corpus (count how many
   NNG rules are genuinely state-transition-shaped — which is also Q3c's `state_transition` body
   count, so one measurement answers both) or fold it into action-enabler.

⚠️ **Von Halle cannot be used as a closed enum regardless of the answer.** She explicitly
disclaims exhaustiveness: "**You do not need to use this scheme. Feel free to adopt a scheme that
best suits your most important audience.**" And she deliberately excludes one class that exists —
the **presentation rule** (C. J. Date 2000: field labels, alignment, colours, fonts, edit masks),
which is precisely our `Priority: P2` "display/formatting/convenience" tier. So our P2 heuristic
is already doing taxonomy work that the category enum is not.

### Q3l — Does the store get a vocabulary layer? **[NEW 2026-08-21, second pass]**

❓ **Q3l** - **Vocabulary layer**: today a GR references code — a path, a line range, a symbol.
Four independent sources say that is backwards: rules are written **in** a business vocabulary,
and the vocabulary is recovered first. Do we model `term` and `fact_type` as records the GRs
reference, or keep rules pointing straight at code?

- **(a)** Two lightweight tables — `term` (a business noun, with the code symbols/columns that
  realize it) and `fact_type` (a verbalized relationship between terms, e.g. *rental specifies
  car group*) — which GRs reference. Seeded from Layer-0 symbols, table columns and DTO fields;
  named and merged by the analyst in Q5's review loop.
- **(b)** A free-text `glossary` or `terms_used` field on each GR. Cheap, unjoinable, and
  duplicates the same term across hundreds of rules with no way to rename it once.
- **(c)** No vocabulary layer — GRs cite code symbols directly, as today.

➡️ **(a), but sequenced as a later milestone** — land the GR tables, `disposition` and the
lifecycle first, then add vocabulary once there is a review loop to populate it. Reasons:

1. **Four independent convergences, one of which states the ordering as a method.** Von Halle
   2001 makes terms and facts *peers* of rules in a seven-part taxonomy and pre-maps them to the
   data model (§17a-bis); Baxter & Hendryx 2005 say "first get the business vocabulary, then
   build rules using vocabulary" (§18d); SBVR 2008 is built on term / fact type / rule; KDM 2012
   standardizes `TermUnit` / `FactUnit` / `RuleUnit` (§1).
2. **It is the fix for three of the six defects in the §18b rubric.** "Program symbols are not
   business terms", "failure to abstract a variable to a named business term" and "direct use of
   implementation technology" are all *unfixable* in a design where the only available referent
   is a code symbol. A lint can flag them; only a vocabulary layer can resolve them.
3. **It is what makes Q3b's validator complete.** Baxter & Hendryx's authoring loop checks the
   written rule for "syntax **and proper use of business terms**" — the second half is
   uncheckable without a term list.
4. **It is where the analyst's judgment accumulates most cheaply.** Naming one term fixes every
   rule that uses it; editing 200 rule sentences does not. That compounds Q5's argument.

**Costs and risks to weigh against it:** it is a second entity to dedupe and merge across
re-extraction runs (Q5's merge semantics apply to terms too, and terms alias far more than rules
do); an LLM will happily invent business terms that no stakeholder uses, so the extractor should
*propose* terms and the analyst should *promote* them; and it widens the first milestone if not
deliberately deferred. **The recommendation is therefore (a) with the tables designed now and
populated later** — the schema cost of reserving them is small, and retrofitting a vocabulary
under 800 existing rules is not.

**If (c):** record explicitly that three of the §18b defect categories are accepted as permanent,
and that Q3b's validator will only ever check sentence shape, never term usage.

### What the survey did NOT change, and one cross-reference

- **No original Q3 recommendation was reversed.** Two were sharpened (Q3b's rubric, Q3c's
  notation), the rest gained support.
- **EARS survives as the statement notation** — compatible with 29148's construct, with its
  condition split independently confirmed by SOPHIST. ⚠️ But it is **not an SDO standard** and
  29148 does not name it. If a client demands an SDO-backed citation, the available ones are
  **ISO/IEC 19506 (KDM)** for the recovered-knowledge model, **ITU-T Z.151 (GRL)** for goals,
  and **ISO/IEC/IEEE 29148** for requirement quality. EARS, SBVR Structured English, Volere
  and iStar 2.0 are **not** SDO standards.
- **Cross-reference to Q4:** ReqIF's data model separates content from structure — "an instance
  of SpecObject is 'empty' by itself", with the document tree living entirely in
  `SpecHierarchy`. That is exactly the **GR-record vs GR-placement** split needed once the same
  rule appears in a business-rules doc, a domain doc, and a brief. It is a storage-shape
  decision, so it belongs to Q4, but it originates here. Related: ReqIF specifies
  `Identifiable.identifier` as "the **lifetime immutable** identifier" — an interchange
  standard treating immutable identity as a *precondition*, which is another argument that
  line-bearing Layer-0 ids cannot be the GR's identity.
- ⚠️ **On ReqIF export as a deliverable feature:** the earlier "costs one exporter" claim is
  **too optimistic** (§9). `SpecObject` / `Specification` / `SpecHierarchy` / `SpecRelation`
  plus simple-typed attributes travel; XHTML rich text, **tables**, cross-document links and
  tool extensions lose data, and the spec itself instructs partners to "**agree on the
  requirement authoring tools and the tool capabilities they use prior to the exchange**." The
  2025 ProSTEP benchmark was its seventh, over 12 system combinations and 588 criteria, with
  errors still occurring. Treat it as a pilot, not a checkbox.

## Q4 — Which physical store, and how many? — ✅ **ANSWERED (b), `knowledge.sqlite`. BACKGROUND ONLY.**

Candidates: (a) **new tables inside `index.sqlite`** — one file, trivial joins to
`chunks`/`symbols`, but that DB is derived, gitignored, and `--reset`-able, so expensive
LLM output could be destroyed by a reindex; (b) **a separate durable store outside the
index dir** — either a new `requirements.sqlite` or new tables in the existing
`knowledge.sqlite`, which already survives `--reset`; (c) **Chroma as primary**; (d)
hosted (Postgres/Aurora), per the pending `hosted-data-store.md`.

**Recommended: (b)**, following the `knowledge.sqlite` precedent. Preserves the
Layer-0/Layer-1 trust boundary the fact-graph decision doc is built on: Layer 0 is
untrusted, deterministic, disposable; GRs are judgment, expensive, and must survive a
reindex. Chroma is an *addition* for vector recall (Q6), never the primary record — no
relational integrity, cannot express GR→chunk→symbol joins. Defer (d) entirely.

**Fact that strengthens this:** `file_domains` lives in `knowledge.sqlite`, NOT
`index.sqlite`, and the two DBs are never `ATTACH`ed — `cli.py:1102-1106` documents that
joins are done in Python because attaching a WAL `index.sqlite` read-only proved
unreliable. So GRs in `knowledge.sqlite` make Q3d's domain join one SQL statement in one
file; GRs in `index.sqlite` make it a Python-side join.

## Q5 — Do GRs have a lifecycle? — ✅ **ANSWERED: full lifecycle. BACKGROUND ONLY.**

If a GR is "whatever the last extraction produced," a database buys queries and little
else. If GRs are durable records with state — `draft` → `reviewed` →
`approved`/`rejected`/`superseded`, with analyst edits, notes, and a stable id surviving
re-extraction — the store does something markdown fundamentally cannot: accumulate human
judgment across runs. That drives identity, dedupe, and re-run semantics (a re-run must
**merge**, not overwrite).

**Recommended: yes, full lifecycle.** Strongest justification for the whole change and
the thing a client values ("we reviewed and signed off on 340 of 470 rules"). Implies
re-extraction is a **merge with dedupe against existing GRs**, not truncate-and-insert,
and human-edited text must be protected from the next LLM pass.

**Second, harder justification added 2026-08-24 — merge is how COVERAGE accumulates, not just
judgment.** §S2.6 measured the two NNG baselines: the only run that reached the web-action and
persistence layers (327 files vs 148) did so by **merging three scoped runs**, and the best
single run stopped at its round cap while still finding ~28 new rules per round. So a
truncate-and-insert design cannot reach the coverage already demonstrated, and the store must
support **scoped runs that merge into the same corpus** with dedupe on the §S2.2 join key.
Also record `rounds_run`, `cap_reached` and `new_rules_in_final_round` as run metadata so no
coverage claim can be read without its floor caveat.

**Fact that makes this a differentiator:** AWS Transform has **no lifecycle state on
requirements and no HITL gate on them.** Job-level approvals exist; requirement-level
approval does not. Requirements are immutable generated documents; re-running restarts
the step. Docs: "You are not prompted for any additional inputs before this process
starts." Refinement is punted to the IDE.

## Q6 — Are requirements embedded for semantic retrieval? — ✅ **ANSWERED (b). BACKGROUND ONLY.**

Options: (a) **relational + SQLite FTS5 only**; (b) **FTS5 + a dedicated Chroma
collection for GRs**; (c) put GRs in the *existing* `code_chunks` collection with a type
discriminator.

**Recommended: (b).** FTS5 covers keyword lookup for free; a **separate** GR collection
gives semantic dedupe — needed the moment Q5's merge semantics exist, because "have I
seen this rule before?" is a fuzzy-match question exact ids cannot answer. Keep it
separate: mixing requirement prose into `code_chunks` poisons code search and forces
every existing query to carry a filter.

## Q7 — Vehicle for the fact-graph decision? — ✅ **ANSWERED (a), scoped to ADDING. BACKGROUND ONLY.**

`docs/exec-plans/pending/fact-graph-decision.md` concludes that after M22–25,
fact-graph's residue is four pieces, of which only **(d) LLM-inferred facts Layer 0
cannot derive (`business_rule`, `state_transition`, …)** genuinely needs a model. A GR
store is precisely a home for (d). Options: (a) **explicitly yes** — this plan
implements the Layer-1 judgment store and the fact-graph decision records that its (d) is
satisfied here; (b) **explicitly no**, accept two Layer-1 stores; (c) defer until M21.

**Recommended: (a)**, with one caveat stated in the plan: the fact-graph doc gates
Option A on **M21** (the "does the index beat fact-graph" evaluation, still open in
`docs/exec-plans/active/semantic-code-search-graph-index.md`). Building the GR store does
not require M21 — it is additive and removes nothing — so proceed, but scope this plan
to *adding* the Layer-1 store, not *retiring* fact-graph. That keeps M21 an honest
evaluation instead of a formality decided by fait accompli.

---

# Deferred Questions — ✅ **ROUND 2 CLOSED IN FULL: D1, D2, D3, D7 ALL DECIDED**

⚠️ **Recomputing the tree after Q4–Q7 promoted four of these to the frontier** — blocked on
**Q4** (D1, D2, D3) and **Q7** (D7). **Three of the four are now closed:** D1 became
`NORMATIVE SPEC-3`, and **D2 and D3 were answered 2026-08-25, both at the standing
recommendation (a)**. **One remains: D7.**

| # | Was blocked on | Status |
|---|---|---|
| **D1** | Q4 | ✅ **CLOSED 2026-08-24 → `NORMATIVE SPEC-3`.** Four keys, each answering one question; `anchor_key` **in Layer 0**; `dedupe_key` = tiered composite (option E); **two-stage dedupe, stage 2 never auto-merges**; domain excluded from every key |
| **D2** | Q4 | ✅ **CLOSED 2026-08-25 → Decision Log.** (a) — DB stays gitignored and authoritative; a **committed JSONL export** sorted by `gr_id` rides alongside; read back **only** via explicit `import --from-jsonl`. GR tables only; `file_domains` export recorded as a known gap, not built here |
| **D3** | Q4 | ✅ **CLOSED 2026-08-25 → Decision Log.** (a) — build `PRAGMA user_version` + ordered forward-only migrations for **both** DBs, as **its own milestone before the GR tables land**. Scope this plan owns and pays for |
| **D7** | Q7 | ✅ **CLOSED 2026-08-25 → Decision Log.** (a) — **zero re-point.** SPEC-3 §S3.1's "must ride the pack-emitter shim" **re-scoped to a future obligation** (fact-graph reads no Layer-0 table, so `anchor_key` is invisible to it). Two-Layer-1-store duplication **accepted out loud**, exit = M21 |

**D4 is closed. D5 and D6 remain genuinely deferred** (D5 is a checklist, not a decision; D6 is
consumer migration and can follow milestone 1). ✅ **Recomputing the tree after D7 does NOT promote
either:** D5 is a task, and D6 (render fidelity / `/modernize-brief` back-compat) is gated on the
renderer existing, which is milestone-1 work. **The frontier is now genuinely EMPTY — next action
is the shared-understanding confirmation, then the ExecPlan.**

1. **Trace granularity — ✅ CLOSED 2026-08-24 → `NORMATIVE SPEC-3`. DO NOT RE-ASK.** The analysis
   below is retained as the problem statement; SPEC-3 is the answer and the authority. Summary of
   what was decided: citation anchor is **`(relative_path, start_line, end_line)`** with
   `anchor_key` as an **advisory soft link** refreshed by a resolution pass (the existing
   `citation-validator` skill); `anchor_key` **lives in Layer 0** (residue **(c)**, open question
   **#6**); a **span-level `content_hash`** on each citation gives drift-vs-clone discrimination
   and makes **moves auto-repairable**; `gr_id` is an immutable **surrogate** because Q5 lets an
   SME edit the text; and **no key takes a domain as input**. Original framing follows. The draft requires a GR to
   tie back to code chunks, but chunk and symbol ids are **not stable across edits**:
   `chunks.id = chunk:{path}:{language}:{chunk_index}:{text_sha256[:12]}` and
   `symbols.id = {language}:{path}:{qualified_name}:{start_line}`. Any edit to a file
   changes its chunk ids; any line shift changes its symbol ids. So a hard FK on
   `chunk_id` breaks on every reindex. Likely answer: citation is
   `(relative_path, start_line, end_line)` as the durable anchor, with `chunk_id` /
   `symbol_id` as advisory soft links refreshed by a resolution pass — but this is the
   user's decision. Note this is the same problem as open question #6 in
   `fact-graph-decision.md` (line-bearing symbol ids are not edit-stable).
2. **Durability vs git — ✅ CLOSED 2026-08-25 → Decision Log (a). DO NOT RE-ASK.** Original framing follows. `.gitignore` has
   `repos/*/legacylift-docs/knowledge/knowledge.sqlite*` — so a durable GR store there is
   neither committed nor shareable. A store of expensive LLM output plus human sign-off
   state that lives only on one analyst's disk is a problem. Likely answer: a committed
   text serialization (JSONL/YAML) alongside the binary DB, with the DB gitignored — but
   that raises which is authoritative on conflict.
3. **Migration mechanism — ✅ CLOSED 2026-08-25 → Decision Log (a). DO NOT RE-ASK.** Original framing follows. There is **no `ALTER TABLE` anywhere in
   `src/`**, no `PRAGMA user_version`, and `SCHEMA_VERSION = "1"` is written but never
   compared. Adding a *table* is free (idempotent `CREATE TABLE IF NOT EXISTS` in
   `migrate()`); adding a *column* is unsupported and today requires `index --reset`,
   which deletes the DB. For a durable GR store that is data loss. This plan must
   introduce a real versioned migration mechanism — a milestone, not a footnote.
   **Post-Q4 nuance:** `knowledge.sqlite` survives `--reset`, so the *destruction* path is
   narrower than for `index.sqlite` — but that cuts both ways: a store that survives resets is
   exactly the one that **will** need column evolution, and today there is no mechanism to do it.
4. **~~Backfilling the existing corpus~~ — CLOSED 2026-08-21, not deferred.** The user
   committed firmly: **nothing is migrated.** The store starts empty; the two existing NNG
   corpora become the comparison baseline instead. See the Decision Log entry
   *Q3-backfill — no migration, ever* and `NORMATIVE SPEC-2`. **Do not re-open this and do
   not build a migration path.**
5. **Draft open question 4 — "are we incorporating everything available via
   legacylift-search?"** Now answerable as a concrete checklist against the mapped
   Layer-0 surface: 9 tables in `index.sqlite`, 4 in `knowledge.sqlite`, the
   `symbol_facts` predicate set, the edge-kind set (`calls`, `references`, `inherits`,
   `implements`, `foreign_key`, `associates`, `has_field_of_type`, `accepts_dto`,
   `returns_dto`, data-access/`uses_table`), and the 9-key Chroma metadata dict.
6. **Render fidelity / back-compat.** `/modernize-brief` greps `Priority: P0`, which
   matches **neither** real generated file. When the store becomes authoritative, does
   the renderer reproduce today's (broken) markdown shape, or fix it and update
   `/modernize-brief` to query the store directly? Leaning strongly toward the latter,
   but it is a consumer-migration decision.
7. **Which of the 13 fact-graph Phase-0 consumers, if any, re-point at the GR store**
   — ✅ **CLOSED 2026-08-25 → Decision Log (a), zero re-point. DO NOT RE-ASK.** Original framing
   follows. ⚠️ **SPEC-3 raises the stakes here:**
   §S3.1 re-keys the fact-graph pack format, and §S3.6 removes `domain` from the entity id — both
   are breaking changes for these consumers, and SPEC-3 requires them to ride the pack-emitter
   shim as **one** migration. `fact-graph-decision.md` §2b establishes the consumer contract is
   narrow and uniform with fallbacks everywhere.

---

# Facts Established (2026-08-19 exploration)

### Answer to draft open question 3 — "Does AWS Transform do anything interesting?"

Yes, four things worth stealing; and it has four documented weaknesses we can beat.

**AWS Transform's assess-and-reimagine pipeline** (the requirements-generating one;
the older "custom job plan" pipeline generates no requirements) produces, in order:
analyze code/data -> Discover Data Paths -> Discover Business Functions -> [human
selects functions] -> Extract business logic (evidence packs via program slicing) ->
Generate requirements. Output: one `requirements.md` per business function, plus
`traceability.yaml`, plus an app-wide `data-model.md`, all as files in S3. Target code
is NOT produced -- forward engineering happens outside the service in Kiro or Claude Code.

**`requirements.md` structure** (verbatim from the AWS user guide): Title / Global
preconditions / numbered workflow sections, where each section contains "a user story
that states the goal as a role, the action that role wants to take, and the resulting
outcome" followed by "a list of Requirements in EARS (Easy Approach to Requirements
Syntax) format, each with a unique identifier." So: user story as the SECTION HEADING,
EARS statements as the numbered requirements beneath it. EARS appears exactly once in
the entire 1.17 MB user guide. Rule-level `rule_text` in `traceability.yaml` is also
EARS.

**Worth stealing:**
1. EARS normative requirement + separate user-story heading at a coarser altitude.
2. `traceability.yaml` with an explicit disposition set --
   `captured | not_applicable | unreachable | delegated | not_accounted_for` -- and the
   invariant **`not_accounted_for = 0`** as the proof that no business logic was lost.
   Per-rule `traceability_lines: [392, 394, ...]`.
3. A "Data flows: Reads / Writes" block attached to each requirement section, naming
   the legacy datasets. Requirements derived from data lineage, not control flow alone.
4. `unreachable` as a first-class disposition, so dead code is excluded from
   requirements without counting as a coverage loss.

**Weaknesses to beat:**
1. AWS uses only **4 EARS patterns** (Event-driven, State-driven, Ubiquitous, Complex).
   It omits `Where` (optional feature) and, more importantly, `If...then` (unwanted
   behavior) -- despite omission-of-unwanted-behavior being one of the eight NL defects
   the 2009 EARS paper was written to fix. Note: **Validation is the largest category in
   our own real NNG output (254 of 470 rules)**, and Validation maps almost exclusively
   to the `If...then` pattern AWS does not use.
2. Its generated requirements are **not strictly EARS-conformant** -- legacy artifact
   names and COBOL return codes inline ("return code '10'", "legacy: XREFFILE"),
   multiple responses per requirement id, and at least one requirement labelled
   `[State-driven]` that is actually Complex. No validator.
3. **No HITL gate on requirements and no requirement lifecycle state.** Job-level
   approvals exist (and "performing graph decomposition" is a critical HITL action), and
   `disposition` exists, but disposition is an analytical classification, not an approval
   state. Requirements are immutable generated documents; re-running restarts the step.
4. **Refinement is punted downstream** to the IDE ("these are living documents you can
   refine"). Docs explicitly: "You are not prompted for any additional inputs before
   this process starts."

**Storage:** `requirements.md` / `traceability.yaml` are documents in S3. Separately,
the mainframe reimagine connector requires an Amazon **Neptune** cluster that "serves
as the unified knowledge graph that stores all extracted artifacts about your job, and
the knowledge graph answers all questions in the AWS Transform chat interface." Not
documented as user-queryable; the graph is for chat, not as a queryable spec store.

### EARS reference facts

Alistair Mavin, Philip Wilkinson, Adrian Harwood, Mark Novak -- Rolls-Royce PLC, first
published at RE'09. Generic syntax:

    While <optional pre-condition>, when <optional trigger>, the <system name> shall <system response>

Ruleset: zero or many preconditions; zero or one trigger; one system name; one or many
system responses. **Five** patterns (Ubiquitous / State-driven `While` / Event-driven
`When` / Optional-feature `Where` / Unwanted-behavior `If...then`) plus **Complex** as a
documented combination rule -- the 2009 paper says five; Mavin's current site and Jama
count Complex and say six. Targets eight NL defects: ambiguity, vagueness, complexity,
omission, duplication, wordiness, inappropriate implementation, untestability.

QRA Corp's published "when NOT to use EARS": more than ~3 preconditions, or when the
requirement is best expressed as a mathematical formula. Prefer lists, decision tables,
diagrams, or state-transition diagrams. (External support for typed bodies -- see Q3c.)

### On pairing EARS with Given/When/Then -- the honest state of the evidence

A dedicated search of the EARS canon, RE/vendor literature, and academic databases found
**no authoritative published guidance for using EARS as the requirement statement and
Given/When/Then as its acceptance criteria.** Verified silent on Gherkin/BDD/GWT
entirely: Mavin's official EARS guide; the RE'09 paper (zero hits for
gherkin/given/BDD/acceptance-criteria/user-story/agile in full text); all four Jama EARS
pages; every QRA resource *including* "When Not to Use EARS"; Visure; Modern
Requirements; ReqView; Terzakis's Intel ICCGI'13 tutorial (1,008 lines, zero hits). No
peer-reviewed paper compares EARS with Gherkin or specifies translating between them --
the EARS literature and the Gherkin/BDD literature are effectively disjoint. Mavin &
Wilkinson's "Ten Years of EARS" (IEEE Software 36(5), 2019) is paywalled and unverified,
but no secondary account of it mentions BDD. There is **no canonical clause mapping**
(`While`->`Given`, `When`->`When`, `shall`->`Then`) anywhere.

What prior art exists:
- **Henrik Lau Eriksson, "Easy Approach to Requirements Syntax and the Segue to
  Behavior Driven Development" (conductofcode.io, 2017)** -- the one substantive,
  human-authored, pre-LLM source. Works a concrete example EARS -> SpecFlow feature
  files, one scenario per requirement, scenarios tagged with the EARS requirement type.
  "I copy-and-pasted the requirement to the SpecFlow feature file and then I knew exactly
  how many scenarios I needed to implement... Maybe this should be called Requirements by
  Example?" Personal blog, not an authority -- but direct prior art for our structure.
- **Andy Pastushok (LinkedIn, 2020)** -- treats them as *alternatives*: "When we talk
  about Acceptance Criteria, there are 2 ways to go: EARS and Gherkin."
- **CodeMySpec (vendor marketing, AI-assisted)** -- the cleanest articulation of the
  complementarity, quotable as one vendor's framing: "EARS phrases the requirement. BDD
  phrases the requirement and verifies the behavior... EARS has no execution step. It
  stops at the well-formed sentence."
- Everything else pairing them is 2025-2026 AI-tooling content of low provenance
  (RequireKit, SEO blogs, agent-skill marketplace listings). Not citable.

**The market precedent runs the other way.** Kiro -- the highest-volume real EARS
deployment -- puts EARS *in the acceptance-criteria slot where Gherkin would sit*, and
never mentions Gherkin/BDD/GWT anywhere in its spec docs. Same with GitHub spec-kit's
EARS proposal (issue #1356) and Joshua McDonald's "EARS, Fifteen Years On."

**Our defensible position** (reasoning, not citation): the substitution precedent is all
*forward* engineering, where there is no running legacy system whose behavior must be
pinned. AWS's own family splits along exactly that line -- its **reverse**-engineering
BRE pipeline emits per-rule `acceptance_criteria: {Given, When, Then}` JSON, while its
**forward** spec-generation pipeline emits EARS. LegacyLift does both halves in one
product, so it needs both representations. EARS cannot carry the concrete fixture values
("agreement level ALL, nomination flag set") that a characterization/equivalence test
needs, and equivalence proof is a promise `/modernize-transform` and `/modernize-uplift`
already make.

**Consequence for implementation:** because no canonical mapping exists, do NOT generate
one representation by translating the other. Both must be authored from the same code
evidence in the same extraction pass.

**(superseded, retained for audit) Original note:** well-supported for EARS + *user stories*
(Kiro's `requirements.md` spec, AWS Transform) -- but note both put EARS in the
*acceptance-criteria slot* where G/W/T normally sits. No authoritative primary source
(Mavin, Cucumber, IREB, peer-reviewed) prescribes EARS-statement + Gherkin-scenario as a
combined method; that combination is supported only by vendor/community material. The
strongest real evidence is AWS's own product family, which carries G/W/T
`acceptance_criteria` per rule in its older BRE JSON while using EARS at the generated-
requirement level -- plausibly two independently built pipelines rather than a deliberate
pairing.


---

# Facts Established — how requirements are stored today

### How requirements are stored TODAY (code-modernization plugin)

**The plugin has no `SKILL.md` files** — it is a command/agent/workflow plugin
(`.claude-plugin/plugin.json`). "Skills" here = 10 files in `commands/` + 5 in
`workflows/`. Output convention is uniform: **`analysis/<system-dir>/`** (sibling to
`legacy/<system-dir>/`), stated at `README.md:13` and `:29`. **Workflow `.js` scripts
never write files** — they return structured JSON and the calling session writes.

Requirements-bearing artifacts: `BUSINESS_RULES.md` + `DATA_OBJECTS.md`
(`commands/modernize-extract-rules.md:78-80`, `:143`, `:151`), `AI_NATIVE_SPEC.md`
§Behavior Contract (reimagine), `MODERNIZATION_BRIEF.md` §5 Behavior Contract,
`DELTA_CATALOG.md` (uplift), `SECURITY_FINDINGS.md` (harden).

**Rule Card prose template** — `commands/modernize-extract-rules.md:116-141`:
`### RULE-NNN: <name>` / `**Category:**` Calculation|Validation|Lifecycle|Policy /
`**Priority:**` P0|P1|P2 / `**Source:**` `path:line-line` / `**Plain English:**` /
`**Specification:**` Given/When/Then/[And] / `**Parameters:**` / `**Edge cases
handled:**` / `**Suspected defect:**` / `**Confidence:**` High|Medium|Low.
Priority heuristic `:137-141`: default P1; P0 if "moves money, enforces a
regulatory/compliance requirement, or guards data integrity"; P2 for
display/formatting/convenience. File structure `:143-147`: summary table at top, cards
grouped by category, final "Rules requiring SME confirmation" section. Plus `:81-84` an
"⚠ Instruction-shaped content found in source" section when `injectionFlags` is non-empty.

**Machine schema `RULES_SCHEMA`** — `workflows/extract-rules.js:72-114`. Top level
`required: ['rules','coveredAreas']`, optional `injectionSuspects` (array of `file:line`).
Per rule, required = `name, category, priority, source, plainEnglish, given, when, then,
confidence`; optional = `and, parameters, edgeCases[], suspectedDefect, smeQuestion`
("Required when confidence is not High: the exact question for a human"). `category` and
`priority` and `confidence` are enums. **There is no `id` field in the schema** — the
dedupe key is computed as `${source-file}::${lowercased-normalized-name}` (`:256`).

Verification mutates cards rather than adding fields: refuted → `rejectionReason`
(`:376`); wrong-citation → `source` replaced with `correctedSource`, `confidence` forced
to `Medium`, `smeQuestion` synthesized (`:373-374`); failed P0 panel → `priority` demoted
to `P1` and/or `confidence` → `Medium` + `smeQuestion` (`:424-436`). Verdict schemas:
`VERDICT_SCHEMA` `:116-132` (`verdict` enum `confirmed|refuted|wrong-citation`, `reason`,
`correctedSource`, `injectionSuspected`); `P0_SCHEMA` `:134-142` (`p0Justified`,
`faithful`, `reason`). Return payload `:455-469`: `{system, rounds, confirmedRules,
rejectedRules, dataObjects, injectionFlags, coverage, stats:{confirmed, rejected, p0,
needsSme}}`.

**`DTO_SCHEMA`** — `workflows/extract-rules.js:144-169`: `dataObjects[]` required
`['name','source','fields']`; `fields[]` required `['name','type']` each
`{name, type, note?}`; optional `consumedBy[]` ("Rule names that read/produce this
object"). Produced by a single `dto-catalog` agent (`:440-450`, agentType
`code-modernization:legacy-analyst`) given confirmed rule names capped at 250 (`:442`).

**Consumers of `BUSINESS_RULES.md` (complete list):**
1. `commands/modernize-brief.md:11-16` — whole-file read, hard prerequisite (with
   `ASSESSMENT.md`, `topology.json`); missing → "say so and stop". `:18-23` mtime
   staleness.
2. `commands/modernize-brief.md:71-75` — **the only structured extraction any consumer
   performs**: "List the **P0 rules** from BUSINESS_RULES.md (the ones tagged
   `Priority: P0` …)" into §5 Behavior Contract; P0 with Confidence < High becomes a
   blocker.
3. `commands/modernize-transform.md:40` — selective read of rules referencing the module
   for the Step 0b HITL plan. `:78` mentions "rule IDs" in docstrings but no ID source is
   defined.
4. `commands/modernize-status.md:19` — existence + mtime only. `:30-31`, `:35-36`
   staleness comparisons.
5. `README.md:59` link; `README.md:110` note that later commands "trust" it.

**`DATA_OBJECTS.md` has ZERO consumers** — written by extract-rules, read by nothing
except the `modernize-status` existence check.

**`modernize-reimagine` does NOT read `BUSINESS_RULES.md`** — it re-runs the
`business-rules-extractor` agent from scratch in Phase A (`:20-21`) and writes its own
`AI_NATIVE_SPEC.md` §Behavior Contract (`:38`).

**The code-modernization plugin and the fact-graph / LegacyLift-docs pipeline are
entirely disconnected** — no code-mod file mentions `legacylift-docs`, `context/`, or the
packs; no LegacyLift skill mentions `analysis/`, `BUSINESS_RULES.md`, or
`legacylift-search`.

**The four LegacyLift GR-producing skills are pure markdown**, no structured
intermediate: `detailed-req-documenter` → `03-BUSINESS-RULES-AND-REQUIREMENTS-{CAPABILITY}.md`;
`business-documenter` → `03-BUSINESS-RULES-AND-REQUIREMENTS.md`; `use-case-generator` →
`08-USE-CASES-{DOMAIN}.md`; `user-story-generator` → `11-USER-STORIES-{DOMAIN}.md`. Chain
is markdown→markdown. ID schemes live only in templates: `FR-{DOMAIN}-001` /
`FR-{DOMAIN}-001.1`, `BR-{DOMAIN}-001`, `UC-{XXX}`, `EP-{XXX}` / `US-{XXX}` with a
traceability matrix `US → EP → UC → FR`. Citation style `[📄](path:line)`, not code-mod's
`**Source:** \`file:line-line\``. All four consume the fact-graph pack format as an
optional Phase 0 (canonical spec `.claude/skills/FACT-GRAPH-INTEGRATION.md`):
`legacylift-docs/context/index.json` + `packs/*.{entities,relations,facts}.pack.json`,
with graceful fallback to direct code analysis.

### REAL generated output diverges from the template (important)

Files:
- `repos/nng-app-legacylift-analysis/analysis-original/customer.ple.nng.app/BUSINESS_RULES.md`
  — 2117 lines, **815 rules**; `DATA_OBJECTS.md` 83 objects
- `repos/nng-app-legacylift-analysis/analysis-semantic-search-enhanced/customer.ple.nng.app/BUSINESS_RULES.md`
  — 4901 lines, **470 rules**; `DATA_OBJECTS.md` 697 lines, 44 objects

**`grep -c "RULE-"` = 0 in BOTH files.** No `RULE-NNN` ids exist at all, and none of
`**Category:**`, `**Priority:**`, `**Source:**`, `**Plain English:**`,
`**Specification:**` labels appear. Citations render as `[📄](path:start-end)`
(enhanced) or a backticked path on a metadata line (original). Priority is a trailing
inline code badge on the `####` heading (enhanced) or a section grouping (original).
Category is a section heading. **Consequence: `modernize-brief.md:71`'s `Priority: P0`
grep matches neither file.** The two runs also use *different* card shapes from each
other. Category distribution in the enhanced run includes `## Validation (254)` — the
largest category, i.e. more than half of the 470 rules are validations.

Representative real card (enhanced run, verbatim):

    #### ALL-level agent designees cannot duplicate the same functional flag  `P0`

    For agreement level ALL, two agent designees cannot both have the same functional
    responsibility flag set (capacity release, contracting, confirmation, imbalance
    resolution, invoice, balancing, nomination, reallocation, or imbalance election);
    the code comment claims InvoiceDocs is exempt. [📄](ple-services/JavaSource/com/nng/ple/service/legalEntity/validator/LegalEntityAgentDesigneeValidator.java:88-107)

    - **Given** An existing ALL-level agent designee with the nomination flag set and a
      new ALL-level designee also with the nomination flag set
    - **When** validateMatchingFlags is evaluated during duplicate-level validation
    - **Then** It returns true, causing a BusinessValidationException
      'agent.designee.duplicate.agreement.levels'
    - **Parameters:** Checked flags: capacityRelease, contracting, confirmation,
      imbalanceResolution, invoice, balancing, nomination, reallocation, imbalanceElection
    - **Edge cases:** Comment says the InvoiceDocs flag is exempt, but the code checks
      getInvoiceFlag() (invoice) and there is no separate InvoiceDocs test here
    - **Confidence:** Medium
    - ⚠️ **Suspected defect:** The javadoc (lines 84-86) states the InvoiceDocs flag may
      be duplicated, but the code enforces the invoiceFlag as non-duplicable, so the
      comment and code may be inconsistent.

`DATA_OBJECTS.md` real shape (enhanced): `## <Name> (base class)` / `Source: [📄](path:line)`
/ a `| Field | Type | Note |` table / `**Consumed by:** <comma-separated rule names>` —
matching `DTO_SCHEMA` field-for-field.

### Which code-mod commands already use legacylift-search (Layer 0)

Five places; **no skill outside `code-modernization/` references it at all.**
- `README.md:122-162` — canonical Layer-0 section. `validate --repo-root` (`:134-136`,
  freshness `fresh|stale|missing`), `index --repo-root` (`:147`). Isolated venv at
  `tools/legacylift_search/.venv` (`:152`). Repo-path bridge rule `:156` — always pass
  the real on-disk `--repo-root`, never `legacy/<system>`. `:158-162` output is untrusted.
- `commands/modernize-extract-rules.md:16-39` — Step 0 index preflight; `:35-39`
  explicitly: retrieval changes only *discovery*, not the Rule Card format, referee, or
  P0 panel. `:51-69` — `Workflow({args:{system, modulePattern, repoRoot}})`, `repoRoot`
  present only when preflight said `fresh`/`stale`.
- `workflows/extract-rules.js:207-231` — `runCoverage()` delegates to a Bash-capable
  `legacy-analyst` agent running `legacylift-search coverage --repo-root <r> --claimed <f>
  --json --limit 40`. `COVERAGE_SCHEMA` `:175-199` = `{skipped?, total, claimed,
  uncovered, pct, uncovered_chunks[{chunk_id?, path, start_line, end_line, symbol|null}]}`.
  Called every round `:327-335`; uncovered chunks feed the next round's targeting prompt
  `:282-285`; final snapshot returned as `coverage` `:462`.
- `agents/business-rules-extractor.md:45-90` — per-lens search idioms; `:86-90` the index
  surfaces candidates only, judgment stays with the agent. Card-authoring discipline
  `:29-43`; credential masking `:92-99`.
- `commands/modernize-assess.md:143-147`, `:310`; `commands/modernize-map.md:15-43`,
  `:145`.

---

# Facts Established — legacylift-search persistence (Layer 0)

**Package:** `tools/legacylift_search/`, distribution `legacylift-code-search` v0.1.0,
console script `legacylift-search = "legacylift_search.cli:app"` (`pyproject.toml:41`),
source under `src/legacylift_search/`. Modules incl. `cli.py` (1617), `store.py` (1493),
`extractors.py` (2803), `indexer.py` (1285), `domain_tagger.py` (636), `embeddings.py`
(524), `knowledge_store.py` (366), `models.py` (223), `search.py` (260),
`vector_store.py` (274).

**15 CLI subcommands:** `init-config`, `index`, `backfill-vectors`, `validate`, `search`
(`--domain`), `symbols --name`, `callers`, `callees` (both `--depth`,
`--edge-kind/--kind` repeatable), `facts --predicate/--symbol`, `tag-domains --domains`,
`domains`, `render-architecture`, `stats`, `coverage --claimed [--json]`, `dump-ast`.

**`index.sqlite` tables** (all DDL in `SQLiteStore.migrate()`, `store.py:173-370`;
`PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`): `index_metadata` (`:184`),
`repo_files` (`:193`), `chunks` (`:207`), `chunk_fts` FTS5 virtual (`:230`), `symbols`
(`:241`), `symbol_refs` (`:270`), `graph_edges` (`:297`), `vectors_present` (`:333`),
`symbol_facts` (`:345`). **There is no `file_domains` table in `index.sqlite`.**

Notable: `chunks.symbol_id` is plain TEXT with **no FK** to `symbols`.
`symbol_refs.chunk_id` is always written as literal `NULL` (`store.py:577`).
`chunk_fts` has no external-content option and no custom tokenizer.
`vectors_present` deliberately has no FK (cache table, rationale `store.py:325-332`).
`symbol_facts.attributes` holds `json.dumps(...)` (`store.py:629-633`).

**Id string formats** (all line- or hash-bearing, i.e. NOT edit-stable):
- `chunks.id` = `chunk:{relative_path}:{language}:{chunk_index}:{text_sha256[:12]}`
  (`chunking.py:142-145`, `:221-224`, `:294-297`)
- `symbols.id` = `{language}:{relative_path}:{qualified_name}:{start_line}`
  (`extractors.py:1112-1115`, `:1662-1665`, `:2622-2625`, `xml_extractor.py:140`)
- `symbol_refs.id` = `{language}:{relative_path}:ref:{name}:{start_line}:{start_byte}`
- `symbol_facts.id` = `fact:{subject_symbol_id}:{predicate}:{object_segment}:{start_line}`
- `graph_edges.id` =
  `edge:{caller_symbol_id or relative_path}:{ref.name}:{start_line}:{edge_kind}:{ref.id}`
  (`graph.py:80-83`)

**Migration / schema versioning — THE KEY CONSTRAINT.** `SCHEMA_VERSION = "1"`
(`indexer.py:38`) is a string constant, written to `index_metadata` (`indexer.py:666`)
and Chroma collection metadata (`indexer.py:686`, `:1194`). `validate` requires the key
to be **present** but **never compares the value** (`cli.py:377-388`). Migration is
exclusively idempotent `CREATE TABLE/VIRTUAL TABLE/INDEX IF NOT EXISTS`. **There is no
`ALTER TABLE` anywhere in `src/`**, no `PRAGMA user_version`, no `PRAGMA table_info`
introspection, no versioned migration list. Therefore: **adding a table is free** (next
`index` run creates it, starts empty, populated only for re-extracted files); **adding a
column is unsupported** and requires `index --reset`, which deletes `index.sqlite` +
`chroma/` (`indexer.py:184-200`). Empirical proof the "add a table" path works and
back-fills lazily: the live `ctcm-api` index (indexed 2026-07-15) has **no
`symbol_facts` table**, so `stats()` (`store.py:1023`) raises
`sqlite3.OperationalError: no such table` until `migrate()` re-runs.

**`knowledge.sqlite` — the durable store precedent.** Path
`<repo_root>/legacylift-docs/knowledge/knowledge.sqlite`; dir from
`IndexConfig.knowledge_dir` default `"legacylift-docs/knowledge"` (`config.py:105`),
resolved by `resolve_knowledge_dir` (`config.py:285-302`); the **filename is hard-coded
at every call site** (`indexer.py:253`, `:1176`, `domain_tagger.py:358`, `cli.py:510`,
`:619`, `:1126`, `:1376`). `KnowledgeStore.__init__` (`knowledge_store.py:45-60`) mkdirs
+ connects + migrates, so *constructing* the object creates the file — every read-only
consumer probes `Path.exists()` first.

Schema (`KnowledgeStore.migrate()`, `knowledge_store.py:69-139`): `domains`
(`domain_id` PK, `name`, `description`, `path_globs`, `assess_run_id`, `display_order`)
`:83-92`; `domain_edges` (`from_domain`, `to_domain`, `kind` default `''`, `evidence`,
composite PK) `:97-105`; `file_domains` (`relative_path` PK, `domain`, `source` CHECK IN
('glob','manual'), `assess_run_id`, `confidence` default 1.0) `:112-120` + index
`ix_file_domains_domain`; `domain_exclusions` (`pattern` PK) `:133-137`.
**No foreign keys anywhere in `knowledge.sqlite`** — because the reserved sentinels
`"unassigned"` (`domain_tagger.py:50`) and `"excluded"` (`:58`) are `file_domains.domain`
*values* with no `domains` row. **There is no `schema_version` in `knowledge.sqlite`.**

**The two DBs are never `ATTACH`ed** — grep for `ATTACH` in `src/` returns nothing.
`DomainTagger.tag` opens two independent connections and joins in Python
(`domain_tagger.py:561-588`). `cli.py:1102-1106` documents why: *"separate files, so a
single-statement SQL join is impossible. This reads the two tables over separate
connections and joins in Python (issue #34) rather than ATTACHing a WAL `index.sqlite`
read-only (unreliable)."*

**Chroma.** `chromadb.PersistentClient(path=index_dir/"chroma")` — the `"chroma"`
subdir name is **hard-coded** at `vector_store.py:63-64` and `domain_tagger.py:601`, not
read from `manifest.index.chroma_dir`. Single collection, `collection_name` default
`"code_chunks"` (`config.py:108`). Collection metadata `vector_store.py:70-76` =
`{embedder_name, embedding_dimension (str), hnsw:sync_threshold 100000,
hnsw:batch_size 10000, **caller metadata}`; indexer passes
`{schema_version, repo_root}`. **Vector ids = `chunk.id` verbatim**
(`vector_store.py:117`); documents = `chunk.text`.

Per-vector metadata dict (`vector_store.py:123-137`) — exactly 8 keys + conditional 9th:
`relative_path`, `language`, `chunk_kind`, `symbol_id` (or `""`), `symbol_path` (or `""`),
`start_line` (**string**), `end_line` (**string**), `text_sha256`, and `domain` only when
a `domain_by_chunk` map is supplied and contains that chunk id.
`update_domain_metadata` (`vector_store.py:164-198`) stamps `domain` without re-embedding
via `collection.update(...)` in batches of 1000, relying on chromadb **1.5.9** merge
semantics (documented + empirically verified, `vector_store.py:167-172`).

Providers (`create_embedder`, `embeddings.py:476-524`), `Literal["qwen3","hash","api"]`:
`hash` → `HashEmbedder` blake2b, dim 64; `qwen3` → `QwenEmbedder`,
`Qwen/Qwen3-Embedding-0.6B`; `api` → `BedrockEmbedder`, name
`api:bedrock:{model}`, Titan default `amazon.titan-embed-text-v2:0`, region default
`us-east-2` (`config.py:161`), creds from `AWS_BEARER_TOKEN_BEDROCK`
(`embeddings.py:311`), `max_concurrency` 16. **Dimension consistency IS enforced**
(`validate_dimension`, `vector_store.py:247-263`; called `indexer.py:698`, `:1204`,
`cli.py:676`); **`embedder_name` consistency is NOT** — written to both stores, only
displayed, never compared, and deliberately differs for qwen3 (SQLite gets
`qwen3:{model}`, Chroma gets bare `qwen3`).

**Pins** (`pyproject.toml`): `chromadb==1.5.9` (load-bearing — the `update`-merges
behavior and the `where`-prefilter-fills-`n_results` behavior both depend on it, per
`vector_store.py:167-172` and `search.py:68-82`), `typer==0.26.4`, `rich==15.0.0`,
`pydantic==2.13.4`, `pathspec==1.1.1`, `chonkie==1.6.7`, `sentence-transformers==5.5.1`,
`numpy==2.4.6`, `networkx==3.6.1`, `tree-sitter==0.25.2`,
`tree-sitter-language-pack==1.8.1`, `pytest==9.0.3`.

**On-disk layout (relative to `<repo_root>`):** index dir
`legacylift-docs/index/code-search/` (`config.py:101`), containing `index.sqlite`
(+`-wal`/`-shm`), `chroma/`, `manifest.snapshot.json` (`indexer.py:206-214`),
`index.log` (`indexer.py:222-226`); knowledge DB
`legacylift-docs/knowledge/knowledge.sqlite`; repo manifest
`<repo_root>/semantic-search.manifest.json` (`cli_helpers.py:35`).

**Gitignore (repo root `.gitignore`):**

    repos/*/legacylift-docs/index/
    repos/*/*/legacylift-docs/index/
    repos/*/legacylift-docs/knowledge/knowledge.sqlite*
    repos/*/*/legacylift-docs/knowledge/knowledge.sqlite*

So the whole `index/` dir is ignored, and `knowledge.sqlite*` is ignored by explicit glob
(matching `-wal`/`-shm`) — the `knowledge/` **directory** itself is neither ignored nor
tracked. Depth patterns cover only `repos/<a>/` and `repos/<a>/<b>/`.
`config.py:71-72` additionally excludes `**/legacylift-docs/index/**` and
`**/.legacylift/**` from *discovery* so the tool never indexes its own artifacts.

**Models** (`models.py`, all pydantic `BaseModel`): `TextRange` `:16`, `Symbol` `:25`,
`SymbolRef` `:38`, `SymbolFact` `:50`, `ExtractedFile` `:79`, `SourceFile` `:88`,
`CodeChunk` `:100`, `GraphEdge` `:120`, `SearchResult` `:135`, `UncoveredChunk` `:150`,
`DomainRecord` `:160`, `DomainEdgeRecord` `:178`, `CoverageResult` `:192`.
**Row-shaped models live in `store.py`, not `models.py`** (comment `store.py:27`):
`LexicalResult` `:28`, `CodeChunkRecord` `:40`, `SymbolRecord` `:61`, `GraphEdgeRecord`
`:78`, `SymbolFactRecord` `:93`, `IndexStats` `:109`.

**Search fusion.** RRF, `search.py:206-257`: `score = 1/(k+vrank) + 1/(k+lrank)` with
`k = rrf_rank_constant = 60`; ranks are 1-based positions — the raw Chroma `distance`
and FTS `rank` are never used numerically. Sort key `(-score, best_rank, relative_path)`.
Lexical arm is FTS5 implicit `rank` (default BM25, no `bm25()` call, no column weights),
query sanitized by `re.findall(r"\w+", ...)` twice (`search.py:23-31`, `store.py:709-710`),
plus an N+1 `SELECT start_line, end_line FROM chunks WHERE id = ?` per row
(`store.py:730-733`). `--domain` filters three ways: Chroma metadata `where={"domain":…}`
on the vector arm; Python path-set filter + **dense rank re-enumeration** on the lexical
arm (pool enlarged to `min(lexical_candidates*5, 500)`); and a fusion-loop drop as a
safety net (`search.py:230-234`). `SearchConfig.graph_neighbor_depth = 1`
(`config.py:177`) is **unreferenced** — no graph-neighbor expansion is implemented.

**Tests.** `tools/legacylift_search/tests/`, flat, 32 modules, **350 test functions**,
`testpaths = ["tests"]`, `addopts = "-q"`. Fixture repo `tests/fixtures/polyglot_repo/`
(C#/Java/Python/TS/JS/COBOL/SQL + `node_modules`/`dist` decoys +
`domains.fixture.json`). Established template for "new table + new CLI command" =
`tests/test_symbol_facts_plumbing.py` (10 tests: model/pickle transport → store
round-trip on a tempfile SQLite → CLI via `typer.testing.CliRunner` against a real index).
Template for a knowledge.sqlite table + command = `tests/test_domain_store.py` (16 tests,
incl. `test_migrate_creates_domain_tables:68` asserting table+index presence from
`sqlite_master`, and `test_file_domains_source_check_constraint:95` asserting
`IntegrityError`). Shared index-fixture idiom: `shutil.copytree(polyglot_repo)` →
`Manifest()` with `embedding.provider="hash"`/`dimension=64` →
`Indexer(...).run(reset=True, embedding_provider_override="hash")` — no network, no model
download. `test_store.py:44 test_migration_creates_tables` is where a new
`index.sqlite` table assertion belongs (it currently asserts 7 tables and has a stale
unused `expected` list at `:52-65` omitting `vectors_present` and `symbol_facts`).

---

---

# Facts Established — requirements notations beyond EARS and GWT

> Researched 2026-08-19 in response to the user's request to widen Q3 beyond EARS and
> Given/When/Then. Four threads completed; four more (SCR/Parnas tables, SBVR/RuleSpeak +
> DMN, Volere/29148/ReqIF/Planguage, and business-rule-extraction literature) were
> relaunched after a credit interruption and are pending at the time of writing.

## 1. OMG ADM / KDM — ISO/IEC 19506, the standard nobody cites

**This is the most directly relevant standard to this entire plan, and it was missing from
the first survey pass.**

**KDM (Knowledge Discovery Metamodel)** is OMG's metamodel "for representing existing
software, its elements, associations, and operational environments." Current version
**KDM 1.4, formal/2016-09-01**. It **is** an ISO standard: **ISO/IEC 19506:2012** —
but note the ISO edition froze at **KDM v1.3** content; v1.4 was never ISO-published.
(ISO catalogue entry was "last reviewed and confirmed in 2025", i.e. reaffirmed unchanged.)

KDM has **12 packages / 9 models** across 4 layers (Infrastructure, Program Elements,
Runtime Resources, Abstractions). The one that matters here is the **Conceptual package**
(§20), which is explicitly "an architectural viewpoint for the **Business Rules domain**"
and whose stated concerns include verbatim: **"What are the business rules implemented by
the system?"**

**Its metaclasses are, essentially, our Rule Card schema, standardized:**

| KDM metaclass | § | Verbatim role |
|---|---|---|
| `AbstractConceptualElement` | 20.3.2 | abstract root; defines the `implementation` property |
| `TermUnit` | 20.5.2 | "aligned with SBVR term or name concepts… represents some 'noun concept'" |
| `FactUnit` | 20.5.3 | "aligned with SBVR fact type concept… represents a 'verb concept'"; "a formula for calculating an allowance can be considered as a fact" |
| `RuleUnit` | 20.5.4 | "represents a condition, a group of conditions, or a constraint"; "aligned with SBVR rule concept"; adds "obligation, necessity, qualifications, quantifications, conditions" |
| `BehaviorUnit` | 20.5.6 | "a behavior graph with several paths through the application logic"; an "abstraction of ActionElements" |
| `ScenarioUnit` | 20.5.7 | "a path… through the behavior graph… corresponds to a trace through the systems, or a 'use case'" |
| `ConceptualRole` | 20.5.5 | role of a participant in a FactUnit/RuleUnit |
| `ConceptualFlow` | 20.6.1 | possible behavioral continuation |

**The traceability mechanism is the key borrowing** (§20.3.2, verbatim): "it defines the
fundamental **'implementation' property** — a KDM grouping mechanism to link conceptual
elements to the implementation elements. … The set of KDM entities available through the
'implementation' property becomes the 'extent' of the application-specific concept … The
conceptual element itself becomes the **'handle'** for the otherwise intangible and
abstract high-value application domain specific concept."

That is exactly GR→code citation, in an ISO standard, since 2012.

**Three critical caveats:**

1. **KDM defines the container, never the extraction.** §20.3.2 verbatim: "It is expected
   that building conceptual models in general, and especially, determining the appropriate
   'implementation set,' is a **difficult value-added knowledge discovery process that may
   involve domain experts and application experts**. KDM framework provides the
   **intermediate representation for capturing the knowledge generated by this process**."
   And §20.1: conceptual views "**can be produced manually**." Nothing in ADM specifies how
   to get from source to rules. **That gap is precisely where an LLM extractor lives** — and
   citing KDM §20 is the strongest standards grounding available for a rule-card schema.
2. **There is NO requirements metamodel anywhere in ADM.** "Requirement" appears **5 times
   in 372 pages**, all incidental. Any claim that ADM standardizes requirements recovery is
   false.
3. **The Conceptual package is one of the thinnest chapters in the standard** (pp. 305-322,
   18 pages, vs. 78 for Code) and several metaclasses have empty "Semantics" subsections.
   It is also **compliance level L1**, not the L0 baseline.

**ADM is effectively dormant.** The ADMTF wiki was last updated **11 May 2012**;
`omg.org/adm/roadmap.htm` 404s; KDM 1.4's issue tracker shows **0 issues**; and of the 8
roadmap packages, **Testing, Visualization, Refactoring and Transformation were never
published**. Ten of the 16 specs now in OMG's "Software Modernization" category are CISQ
*measurement* standards (AFP/AEP/ATDM/ASC\*M), not modernization models. Practical KDM
tooling footprint = **Eclipse MoDisco (repo archived 14 Jul 2026, though maintenance
releases ran to 1.6.0 in Mar 2026) + KDM Analytics** — i.e. the two organizations that
authored the standard. CAST, Micro Focus/OpenText and Semantic Designs KDM claims could
**not** be verified.

**Asymmetry worth knowing:** KDM references SBVR 8 times and declares alignment. Grepping
the full SBVR 1.5 spec yields **zero** occurrences of "KDM", "Knowledge Discovery",
"legacy", or "reverse engineer". No OMG spec defines a KDM→SBVR or KDM→DMN mapping.

Key academic citation (verified via Crossref + Semantic Scholar): Pérez-Castillo,
García-Rodríguez de Guzmán, Piattini, "Knowledge Discovery Metamodel-ISO/IEC 19506: A
standard to modernize legacy systems," *Computer Standards & Interfaces* 33(6), 2011,
519-532, DOI 10.1016/j.csi.2011.02.007. Also: KDM-RE (VEM 2014) states verbatim
"**none of them uses KDM as their underlying metamodel**" — published evidence of thin
adoption. No systematic review of KDM adoption could be found; do not cite one.

## 2. Contracts and invariants — and the fact that inference on existing code WORKS

**Design by Contract** is a real standard: **ECMA-367 2nd ed. (June 2006)**, also
**ISO/IEC 25436:2006**. Grammar: `require` / `ensure` / `invariant` / `old` / `check` /
`variant` / `rescue`; inheritance uses `require else` (weaken) and `ensure then`
(strengthen). ECMA-367's own rationale for contracts is **documentation of reusable
components** — verbatim: "Assertions are also an indispensable tool for the documentation
of reusable software components: one cannot expect large-scale reuse without a precise
documentation of what every component expects (precondition), what it guarantees in return
(postcondition) and what general conditions it maintains (invariant)." It also defines a
**contract view** — the class text with implementation stripped but assertions kept — which
is exactly "the spec, derived from the code."

Blame assignment is built in: precondition breach = client's fault; postcondition/invariant
breach = supplier's fault. Caveat: EiffelStudio's **default monitoring level is `require`**,
so postconditions, invariants, loop variants and `check` clauses are **not** evaluated at
runtime by default.

**The important finding: contract inference from unannotated legacy code is demonstrated,
published, and shipped.**

- **Daikon** (Ernst et al.; TSE 27(2) 2001; SCP 69 (2007) 35-45) — **alive**: released
  **5.8.24, May 2026**; GitHub last push 2026-08-11. Instruments a program, runs it,
  infers likely invariants over traced **and derived** variables (25 kinds of derived
  variable). Checks **75 different invariants**; optimizations "reduce the number of
  invariants that need to be checked by 99%"; statistical null-hypothesis filtering.
  Emits **JML, ESC/Java, DBC, Java assertions, IOA, Simplify, and `CSharpContract`
  (Microsoft Code Contracts)** formats, and ships an **`annotate`** tool that "inserts
  likely invariants into source code as annotations." Front ends: Chicory/DynComp (Java),
  Kvasir (C/C++), **Celeriac (.NET — C#, F#, VB)**, dfepl (Perl), CSV, **CITADEL (Eiffel)**,
  Hynger (Simulink).
  Ernst's own framing is *documentation of existing code*: "The likely invariants produced
  by Daikon are a **dynamically-generated analogue of a program specification**… In
  practice, however, formal specifications are rarely available." And: "Information that is
  automatically extracted from the implementation is **guaranteed to be up to date**."
  **Documented limits, verbatim:** "the resulting properties are **not guaranteed to be
  true over all possible executions**"; accuracy "depends in part on the quality and
  completeness of the test cases"; explicit **overfitting** risk — their own published
  example includes a false invariant that "turns out to be a result of the test suite… and
  **not a requirement of `StackAr` itself**"; "It may be difficult, perhaps
  **overwhelming**, for a programmer to sort through a large number of inferred
  invariants"; cannot handle structs/classes/multidimensional arrays. Scale: used on
  NASA's **CTAS, "over 1 million lines of C and C++"**, but "often requires focusing Daikon
  on a subset of the program."
- **Clousot / cccheck necessary-precondition inference** (Cousot, Cousot, Fähndrich,
  Logozzo, VMCAI 2013, LNCS 7737, 128-148) — the strongest evidence, because it needed
  **only bytecode**. Ran "**directly on the shipped binaries**" of contract-free
  `mscorlib.dll`, `System.dll`, `System.Core.dll`, `System.Data.dll`. Found necessary
  preconditions for "almost **64%** of methods which contained warnings"; sufficient in 27%
  of those. Verbatim: "The necessary precondition inference is enabled by default in every
  run of the analyzer, and **used by our customers since June 2011 on a daily basis**." The
  stated motivation was legacy usability: "to help our users getting started with cccheck,
  by suggesting preconditions."
- **AutoInfer** (Wei, Furia, Kazmin, Meyer, ICSE 2011): "75% of the complete postconditions
  of commands can be inferred fully automatically" on Eiffel data structures.
  **Polikarpova, Ciupa, Meyer (ISSTA 2009)** compared programmer-written vs. inferred
  contracts and found them **complementary** (content unverified — paywalled).
- **Model learning / automata learning** (Angluin L\* 1987; LearnLib; Vaandrager, *CACM*
  60(2), Feb 2017) — the CACM piece has a section headed **"Legacy software"** and reports
  the Philips case (Schuts, Hooman, Vaandrager, iFM'16): Mealy machines were learned from
  **both** the legacy and the refactored implementation of an interventional-radiology
  Power Control Component and compared with an **equivalence checker** — "Issues were found
  in **both the refactored and the legacy implementation** in an early stage." Hard limits:
  "model learning currently can only be applied if there are **less than, say, 100
  inputs**"; "**Abstraction is the key**"; models "obtained through a finite number of
  tests, we can never be sure that they are correct."

**OCL is the weakest fit and should be dropped from consideration.** OMG OCL froze at
**2.4, February 2014** — twelve years without revision. The spec itself concedes "**OCL
expressions are not by definition directly executable**", and its *conformance* clause makes
`allInstances()`, `@pre` in postconditions, and `OclMessage` **optional** — precisely the
constructs contracts need. No credible code→OCL extraction line of work exists; OCL
constrains a *UML model*, not source, so any pipeline needs model recovery first.

**A .NET modernization audit item worth adding to `/modernize-assess` independently of this
plan:** `System.Diagnostics.Contracts` **still compiles on .NET 5-11** (API monikers run
through `net-11.0`), but the `ccrewrite` binary rewriter and `cccheck` static checker are
gone — repo **archived 15 Jul 2023**, and MS Learn states verbatim "Code contracts aren't
supported in .NET 5+ … Consider using **Nullable reference types** instead." So any legacy
.NET codebase using Code Contracts **silently lost both runtime enforcement and static
checking on port**. That is a real, citable finding for an assessment report.

## 3. Goal-oriented notations — and the one published code→model recovery pipeline

**KAOS** (Dardenne, van Lamsweerde, Fickas; *Sci. Comp. Prog.* 20, 1993; UCLouvain +
U. Oregon, from 1990). Correction to carry forward: the acronym is "**Keep All
**Objectives** Satisfied**" (van Lamsweerde's own slide), not "Objects"; the original
expansion is "Knowledge Acquisition in Automated Specification of Software."

Four models: **goal, object, agent(-responsibility), operation**. Behavioural goal types
**Achieve / Cease / Maintain / Avoid** (+ **Optimize** in the 2001 tour, **SoftGoal** in the
2003 taxonomy), with exact temporal-logic patterns: `Achieve = P ⇒ ◇Q`,
`Maintain = □(P ⇒ Q)`, `Avoid = □(P ⇒ ¬Q)`.

**Three KAOS concepts are directly worth stealing for a GR schema:**

1. **requirement vs expectation.** A goal assigned to a **software** agent is a
   **requirement**; a goal assigned to an **environment** agent is an **expectation**
   ("assumption" in the 2001 paper) — verbatim: "Unlike requirements, assumptions **cannot
   be enforced by the software-to-be**." Mined rules include plenty of the latter (e.g. "the
   upstream feed provides validated data").
2. **domain property = domain invariant ∪ domain hypothesis.** Descriptive assertions,
   distinct from prescriptive requirements: a **domain invariant** is "known to hold in
   every state" (a physical law, a regulation); a **domain hypothesis** is "assumed to
   hold." Note the taxonomy is parent/child, not siblings.
3. **Obstacle analysis** — an obstacle `O` obstructs goal `G` iff `{O, Dom} |= ¬G` and
   `Dom |≠ ¬O`. Resolution tactics: goal substitution, agent substitution, goal weakening,
   goal restoration, obstacle prevention, obstacle mitigation, runtime monitoring. Produces
   a "goal-anchored fault-tree… **provably complete with respect to what is known about the
   domain**."

Operations carry **DomPre / DomPost / ReqPre / ReqPost / ReqTrig** — i.e. KAOS already
separates *what the domain does* from *what the requirement imposes*, the same split as
Q3a's observed-vs-intended.

**KAOS limits (author-stated):** "More formal specifications yield more powerful reasoning
schemes at the price of **higher specification effort and lower usability by
non-experts**"; alternative selection is "**by and large an open problem**." Demonstrated
models are **small** — 50-100 goals; the largest reported was 65 goals → a 115-page
deliverable. Vendor sets an ROI floor at >100 man-days. Tooling (Objectiver) has had **no
release since ~2012**, and respect-it.com now serves spam. **Zero papers exist on
recovering KAOS models from source code.**

**iStar 2.0** (Dalpiaz, Franch, Horkoff; arXiv:1605.07767 v3, 17 Jun 2016; 24 endorsers; no
SDO). Actors: **Role, Agent** + generic Actor. Actor links: **is-a, participates-in**.
Intentional elements: **Goal, Quality, Task, Resource**. Element links — exactly four:
**refinement (AND / inclusive-OR), needed-by, contribution, qualification**. Contribution
types — **exactly four: Make, Help, Hurt, Break** (there is no neutral/`some+`/`some-`/
`unknown` in iStar 2.0 — those belong to the older NFR-framework propagation labels; do not
blend the schemes). Dependencies have **five** arguments (depender, dependerElmt, dependum,
dependee, dependeeElmt), and dependum type encodes **degree of delegated discretion**
(goal/quality = highest freedom, task = medium, resource = lowest).
iStar 2.0 explicitly excludes: the ontology of constructs, the graphical notation, wording
conventions, and **any methodology or completion criterion** ("when can a model be
considered final?"). No formal semantics. No successor version in 10 years.
**GRL**, the i*-derived dialect, **IS** a real standard: **ITU-T Z.151 (10/2018)**, with
Z.150 for the framework — the citable option if a client demands an SDO-backed notation.

**The single most relevant paper found in the whole survey:** Yu, Wang, Mylopoulos, Liaskos,
Lapouchnian, do Prado Leite, "**Reverse engineering goal models from legacy code**," RE'05,
DOI 10.1109/re.2005.61. Four-step pipeline: (1) **refactor source by extracting methods
based on comments**; (2) convert to an abstract program via statechart refactoring +
hammock graph construction; (3) **extract a goal model from the AST**; (4) **identify
non-functional requirements to derive soft goals based on traceability between code and
model**. Validated on **SquirrelMail (PHP)** and **Columba (Java)**.

But: **74 citations in ~21 years (~3.5/yr)**, and only ~10 of those continue the legacy
re-documentation thread — the citation mass went to self-adaptive systems instead. The two
most on-point recent papers are Brazilian workshop papers with **1 and 2 citations**.
OpenAlex `title.search:goal-oriented reverse engineering` returns **count: 0**.
**Interpretation: goal-model recovery from legacy code is a validated, published, and
essentially abandoned technique — an opportunity, not a mature practice.** Modern adjacent
thread: "An LLM-based Approach to Recover Traceability Links between Security Requirements
and Goal Models," EASE 2024, DOI 10.1145/3661167.3661261, 22 citations.

Tooling: **piStar** (MIT, browser-based, v2.1.0, actively maintained) is the only live i*
tool; OpenOME, jUCMNav and TAOM4E are all dead, and iStarML (the interchange format) never
made the jump to iStar 2.0.

## 4. Characterization / golden-master / approval testing — a record, not a specification

Feathers, *Working Effectively with Legacy Code* (Prentice Hall, Sep 2004, ISBN
978-0-13-117705-5). **"legacy code is simply code without tests"** (Preface, p. xvi).

**Characterization test**, Ch. 13 p. 186, verbatim: "In nearly every legacy system, **what
the system does is more important than what it is supposed to do**." / "A *characterization
test* is a test that characterizes the **actual behavior** of a piece of code." The
algorithm (five steps, p. 186): (1) use a piece of code in a test harness; (2) write an
assertion you know will fail; (3) **let the failure tell you what the behavior is**;
(4) change the test to expect what the code produces; (5) repeat.

Feathers' own blog ("Characterization Testing," 8 Aug 2016): "The purpose of
characterization testing is to **document your system's actual behavior, not check for the
behavior you wish your system had**." And: "**When a system goes into production, in a way,
it becomes its own specification.**" (Note the hedge — "in a way".) Also p. 185: "In the
natural flow of development, tests that *specify* become tests that *preserve*."

**Bug handling — the passage that matters most for Q3a**, p. 188: "Characterization tests
record the actual behavior of a piece of code. If we find something unexpected when we write
them, it pays to get some clarification. It could be a bug. **That doesn't mean that we
don't include the test in our test suite; instead, we should mark it as suspicious** and
find out what the effect would be of fixing it."

**Documented limitations:** they enshrine bugs as expected behavior (Feathers p. 188;
Seemann 2025); **no intent is captured** — Savoia (Artima, 2007) states the contrast
structurally: characterization tests "don't check what the code is **supposed** to do, **as
specification tests do**, but what the code actually and currently does"; high
false-negative rate and blind approval — Dodds: "Most developers, upon seeing a snapshot
test fail, will sooner just nuke the snapshot and record a fresh passing one"; huge
unreviewed approved files; **non-determinism forces scrubbers** (Verify's
`ScrubMachineName`/`ScrubUserName`/path scrubbers, Jest property matchers, Snapshooter
`IgnoreField`, Diffy's whole primary/secondary/candidate architecture exists to cancel
noise statistically); and coverage is **sampled, not exhaustive** (Rainsberger).

**The verdict, and it is directly actionable for this plan:** an approval/characterization
suite is an excellent **verification oracle for extracted rules** and a **poor source of
rule statements**. The pipeline is **record → interrogate → specify**, and the middle step
is the one always skipped. Two consequences:

1. If we mine a rule and need to prove the restatement is faithful, an approval test is
   exactly the right check — it catches drift.
2. **If we present recorded behavior as a requirement, we silently promote every latent
   defect to a requirement, with nothing distinguishing "this is policy" from "this is a bug
   nobody noticed."** That is worse than an admitted gap because it is an unadmitted one.
   So any behavior-derived GR needs a provenance tag ("derived from observed behavior;
   intent unconfirmed") and a suspicion flag — Feathers' "mark it as suspicious" discipline
   carried from the test suite into the documentation layer.

Corroborating from industry: GitHub's Scientist (Jesse Toth, 3 Feb 2016) exists because
"**Tests are a good place to start verifying the correctness of a new system as you write
it, but they aren't enough**" — "given enough time and volume, your data will have bugs,
too." Twitter/Sn126's **Diffy** does the same by proxying every request to candidate,
primary and secondary instances. (Note Diffy is **CC BY-NC-ND 4.0** — a restrictive licence
to flag before any commercial use.)

Correction to carry forward: **Fowler has no "Parallel Run" pattern page** — all plausible
URLs 404; parallel run appears only as a named strategy in one sentence of "Patterns of
Legacy Displacement" (Cartwright, Horn, Lewis, 5 Mar 2024). And Fowler's **Dark Launching**
page is about **performance impact**, not output comparison — not a shadow-testing pattern
in his usage.

## 6. Planguage (Tom Gilb) — the quantified-requirement notation

Earliest formal publication: Tom Gilb, "A planning language (a PLanguage)," **ACM SIGSOFT
Software Engineering Notes, 1989**, DOI 10.1145/75145.75168 — sixteen years before
*Competitive Engineering* (2005), which is the canonical reference. Gilb is still
publishing (works dated 2025 and 2026).

**The official scalar-requirement template (Competitive Engineering, Fig. 4.12), verbatim.**
This is the item most worth copying into a GR record schema:

    Tag: <Tag name>.   Type: <{Performance Requirement: {Quality, Resource Saving,
                        Workload Capacity}, Resource Requirement: {...}}>.
    =========================== Basic Information ==========================
    Version:  Status:  Quality Level:  Owner:  Stakeholders:  Gist:  Description:  Ambition:
    =========================== Scale of Measure ===========================
    Scale:
    ============================= Measurement =============================
    Meter:
    ============== Benchmarks ============ "Past Numeric Values" ==========
    Past [...]:  Record [...]:  Trend [...]:
    ============== Targets =============== "Future Numeric Values" ========
    Goal/Budget [...]:  Stretch [...]:  Wish [...]:
    ============== Constraints =========== "Specific Restrictions" ========
    Fail [...]:  Survival [...]:
    ============================ Relationships ============================
    Is Part Of:  Is Impacted By:  Impacts:
    ==================== Priority and Risk Management =====================
    Rationale:  Value:  Assumptions:  Dependencies:  Risks:  Priority:  Issues:

The spine is **Scale -> Meter -> Benchmarks -> Targets -> Constraints**, with relationships
and risk as separable trailers. Parameter icons: `Scale` `-|-|-`, `Meter` `-|?|-`,
`Past` `<`, `Record` `<<`, `Trend` `?<`, `Goal` `>`, `Stretch` `>+`, `Wish` `>?`,
`Fail` `!`, `Ambition` `@.S`, `Source` `<-`.

**Scale qualifiers give reusable parameterized requirements:**
`Scale: The defined [Time Units: Default = Hours] needed to do a defined [Task] by a
defined [Employee Type].` Named qualifiers: `German School: Qualifier: [Country = Germany,
User = Teachers].` then `Goal [German School]: 65%.`

**Keyword drift to be careful about** (three corrections to commonly-repeated lists):
`Plan` -> **`Goal`** (renamed, confirmed); `Must` -> **`Fail`** (half-right — the glossary
retires *two* distinct historical forms, `Must (Avoid) *098` and `Must Do *539`, both marked
"Historical usage only"); and **`Wish` was never a rename of `Stretch`** — it was *added*,
with a datable origin, per the CE glossary Historical Note: "The Wish parameter was first
suggested in December 1995 by the Scottish Widows organization, through Dorothy Graham of
Grove Consultants." A fourth target level, **`Ideal`** ("a future desired level which is
perfect"), appears in a 2004 ICEIS deck but was dropped from CE 2005's core list.
Open item: the ValueFirst syllabus and ValPlan help use a parameter named **"Tolerable"**
that is absent from CE 2005 — possibly a newer softening of `Fail`; post-2005 books are
paywalled so drift could not be checked.

**Relevance to this plan.** Planguage is the wrong notation for mined business rules — it
is built for quantified *quality/performance* requirements, which legacy rule extraction
rarely produces. But three things in Fig. 4.12 are directly transferable to the GR schema
and are absent from the current Rule Card:

1. **`Rationale`** — why the requirement exists. The single most valuable thing an SME adds
   and the thing most often lost. (Volere has this field too.)
2. **`Assumptions` / `Risks` / `Issues`** — distinct from `suspectedDefect`; these capture
   what the extractor had to assume and what remains unresolved.
3. **`Scale` + `Meter` as separate fields** — the measurable dimension and the measurement
   procedure. This is a sharper decomposition than a single free-text acceptance criterion,
   and it is the right shape for any GR that is genuinely quantitative (thresholds, rates,
   limits) rather than conditional.

Also note `Status` / `Quality Level` / `Owner` in the Basic Information block — independent
corroboration of Q5's lifecycle-state recommendation from a 1989-vintage notation.

## 7. ISO/IEC/IEEE 29148:2018 — the SDO-backed requirement-quality rubric AND a sentence template

**Correction to an earlier claim in this file:** 29148 was described as "not a competing
syntax — a standard defining characteristics." That is half wrong. **It does prescribe a
requirement sentence construct** (clause 5.2.4, Figure 1), and it publishes a normative
banned-term list. Both are directly usable.

Edition: **ISO/IEC/IEEE 29148:2018 (second edition, 2018-11)**, "Systems and software
engineering — Life cycle processes — Requirements engineering", 92 pp, ISO/IEC JTC 1/SC 7
with IEEE C/S2ESC. It **cancels and replaces** 29148:2011. Note: **IEEE 830, 1233 and 1362
were superseded by the 2011 edition**, not 2018. It does NOT replace 12207 or 15288 — it is
a companion that elaborates their 6.4.1-6.4.3 processes.

**The sentence construct (Figure 1 — VERIFIED 2026-08-21 from the figure itself; it is a
raster image, so this was previously the one unconfirmed 29148 item):**

    [Condition] [Subject] [Action] [Object] [Constraint of Action]
      EXAMPLE: When signal x is received [Condition], the system [Subject] shall set [Action]
               the signal x received bit [Object] within 2 seconds [Constraint of Action].
                                    Or
    [Condition] [Subject] [Action] [Object] [Constraint of Action]
      EXAMPLE: At sea state 1 [Condition], the Radar System [Subject] shall detect [Action]
               targets [Object] at ranges out to 100 nautical miles [Constraint of Action].
                                    Or
    [Subject] [Action] [Constraint of Action]
      EXAMPLE: The Invoice System [Subject] shall display pending customer invoices [Action]
               in ascending order of invoice due date [Constraint of Action].

**Two corrections to how this file previously rendered the figure:**

1. **It is TWO constructs and three examples, not three patterns.** The figure repeats the
   five-slot construct verbatim for its second example; only the third is a different
   (three-slot) construct. Earlier text here implied the middle example illustrated something
   structurally distinct. It does not.
2. **In the three-slot form, `[Object]` does not simply disappear — it is absorbed into
   `[Action]`.** Compare `shall detect [Action] targets [Object]` with
   `shall display pending customer invoices [Action]`, where the object sits inside the Action
   span. So the slots are **not independently optional**: dropping `[Object]` requires widening
   `[Action]` to carry it. Any `pattern` validator that treats the five slots as five nullable
   fields will mis-parse the short form.

**And one substantive observation the annotated figure makes visible:
`[Constraint of Action]` is present in all three examples, and in both constructs.** 29148
never illustrates a requirement without one. That refines the EARS claim:

- The **slot order** is compatible — EARS event-driven (`When <trigger>, the <system name>
  shall <system response>`) maps onto `[Condition] [Subject] [Action] [Object]`. So **adopting
  EARS does not put us outside the standard**, and 29148 confers no standing on EARS and does
  not name it (verified negative, see below).
- But **EARS has no constraint-of-action slot**, and every 29148 example bounds the action —
  "within 2 seconds", "out to 100 nautical miles", "in ascending order of invoice due date".
  Note the third shows `[Constraint of Action]` is broader than a performance bound; an
  *ordering* constraint qualifies.
- ⚠️ **Consequence for our corpus, and it is not small.** 29148's example syntax is oriented
  toward *bounded, measurable* requirements — consistent with cl. 5.2.5 *Verifiable*
  ("Verifiability is enhanced when the requirement is measurable"). Mined business rules are
  mostly *conditional and categorical*: "the system shall reject the order" has no natural
  constraint of action. So most GRs will legitimately leave that slot empty, which is
  conformant to the construct but unlike every example the standard gives. **Do not treat an
  empty `[Constraint of Action]` as a validator finding** — and where a rule *is* genuinely
  quantitative, that slot is the signal to reach for Q3c's `formula` body (Planguage
  `Scale`/`Meter`) rather than prose.

29148 also says, verbatim: "**Condition-action tables and use cases are other means of
capturing requirements**" — standards support for typed bodies (Q3c).

**Characteristics of an individual requirement (clause 5.2.5) — all normative `shall`:**
**Necessary · Appropriate · Unambiguous · Complete · Singular · Feasible · Verifiable ·
Correct · Conforming.** Two that matter most here:
- **Singular** — "states a single capability, characteristic, constraint or quality factor."
  (NOTE 2 allows "multiple conditions under which the requirement is to be met.") This is
  precisely what AWS Transform's published example violates with two `shall` clauses under
  one id.
- **Verifiable** — "structured and worded such that its realization can be proven
  (verified)… **Verifiability is enhanced when the requirement is measurable.**"

*2011→2018 drift to know:* the 2011 nine were Necessary, **Implementation Free**,
Unambiguous, **Consistent**, Complete, Singular, Feasible, **Traceable**, Verifiable.
*Implementation Free* was absorbed into **Appropriate**; *Consistent* moved to the set
level; *Traceable* moved to attributes/management. **Any checklist citing "implementation
free" as a 29148 characteristic is keyed to the 2011 edition.** (Our Q3f — keeping legacy
symbol names out of the statement — is the *Appropriate* characteristic: "avoiding
unnecessary constraints on the architecture or design while allowing implementation
independence to the extent possible.")

**Characteristics of a requirement SET (clause 5.2.6), also `shall`:** **Complete**
(and "does not contain any TBD, TBS, or TBR clauses") · **Consistent** ("unique, do not
conflict with or overlap") · **Feasible** (NOTE 4: "Feasible includes the concept of
'affordable'") · **Comprehensible** · **Able to be validated**.

**Verb conventions (clause 5.2.4), verbatim and directly implementable as lints:**
requirements are mandatory and use **'shall'**; non-requirements use 'are'/'is'/'was';
"**It is best to avoid using the term 'must'**, due to potential misinterpretation";
statements of fact/futurity use **'will'**; preferences/goals use **'should'** and "**They
are not requirements**"; suggestions use **'may'**; "**Use positive statements and avoid
negative requirements such as 'shall not'**"; "**Use active voice**"; "**Avoid using terms
such as 'shall be able to'**". NOTE 2 concedes "Requirements in agile may use alternative
formulations such as user stories without explicitly using the term 'shall'."

**Clause 5.2.7 — the ready-made vagueness blocklist for the Q3b validator.** Verbatim:
"Vague and general terms **shall** be avoided." The banned classes are: superlatives ·
subjective language ("user friendly") · vague pronouns · ambiguous adverbs and adjectives
**and 'or' / 'and/or'** · open-ended non-verifiable terms ("but not limited to") ·
comparative phrases · loopholes ("if possible", "as appropriate") · totality terms ('all',
'always', 'never', 'every') · incomplete references.
**This is Q3b's blocklist, standardized, from an ISO/IEC/IEEE document.** It is a
significantly stronger basis for the validator than a hand-rolled word list.

**EARS is absent — a documented negative.** Both editions' full text was grepped for
`EARS`, `Mavin`, `Easy Approach`, `boilerplate`, `SysML`: **zero substantive hits**, and the
28-entry bibliography has no EARS reference (it does cite the INCOSE SE Handbook v4 and
IIBA BABOK v2.0). 29148 names only its own Figure 1 construct, condition-action tables, use
cases, and (in a note) user stories.

**Document structures** live in **Clause 8 (Figures 5-8) with normative content in Clause
9**, not in annexes. Mandated information items: **BRS, StRS, SyRS**, plus **SRS** if
adhering to 12207, plus **OpsCon** (normative Annex A). **ConOps is informative only**;
there is no SEMP. Physical documents are not required — "The information items do not
require physical documentation, so long as required content is easily available and
logically organized." The **SRS outline is IEEE 830's with a new §4 Verification section
running parallel to §3** — worth noting, because a GR store that can emit a verification
section keyed to each requirement is emitting the part 830 lacked.
ConOps = organization-level (informative, elicitation aid); OpsCon = system-level
(normative, user's viewpoint, required) — commonly reversed.

*Provenance caveat recorded honestly:* the full text was obtained as IEEE-Xplore-watermarked
institutional PDFs on public sites — textually authoritative but almost certainly
unauthorized. **For anything citable in a client deliverable, buy the standard (~US$288).**
The ISO stage code could not be checked (iso.org 403s every route), so "no newer edition"
rests on IEEE SA "Active" plus zero hits for AWI/DIS/CD 29148.

### 7-bis. 29148 VERIFIED FROM THE STANDARD 2026-08-21 — and clause 5.2.8 was missed entirely

The standard is now on disk (`ISO-29148-Requirements-Engineering.pdf` + `ISO-29148.txt`) and
every 29148 claim in this file was re-checked against it directly rather than against the lost
agent's report. **Identity confirmed:** cover reads `ISO/IEC/IEEE 29148`, "**Second edition
2018-11**", `ISO/IEC/IEEE 29148:2018(E)`, © ISO/IEC 2018 / © IEEE 2018.

⚠️ **The licensing problem is NOT solved.** The copy carries the footer "Authorized licensed
use limited to: **Brigham Young University - Idaho**. Downloaded on May 21, 2020 … from IEEE
Xplore. Restrictions apply." That is an institutional copy belonging to a third party, not a
CapTech licence. It is fine for verifying facts in this planning document; **it is not a basis
for shipping quoted text in a client deliverable.** Buying it remains an open action.

**What verified clean (quote-for-quote against the draft):**

| Claim | Status |
|---|---|
| cl. 5.2.7 "Vague and general terms shall be avoided" + all nine ambiguous-term classes | ✅ verbatim, with two NOTEs recovered: NOTE 1 "Consider multiple requirements when encountering terms such as 'or', 'and', or 'and/or'"; NOTE 2 "It is very difficult to verify such requirements" (on totality terms) |
| cl. 5.2.4 verb conventions (shall / will / should / may, avoid 'must', avoid 'shall not', active voice, avoid 'shall be able to') | ✅ verbatim |
| cl. 5.2.5 nine characteristics — Necessary, Appropriate, Unambiguous, Complete, Singular, Feasible, Verifiable, Correct, Conforming | ✅ verbatim |
| cl. 5.2.6 five set characteristics — Complete, Consistent, Feasible (NOTE 4 "Feasible includes the concept of 'affordable'"), Comprehensible, Able to be validated | ✅ verbatim |
| "Condition-action tables and use cases are other means of capturing requirements" | ✅ verbatim, cl. 5.2.4 |
| NOTE 2 on agile/user stories | ✅ verbatim, and it points to **ISO/IEC/IEEE 12207:2017 Annex H** for agile discussion — a pointer the draft did not have |
| *Appropriate* = "avoiding unnecessary constraints on the architecture or design while allowing implementation independence…" | ✅ verbatim (Q3f's mapping holds) |
| **EARS absent** — the negative finding | ✅ **confirmed independently.** A case-insensitive grep for `EARS\|Mavin\|easy approach\|boilerplate` returns 5 lines, **all of them the substring "ears" inside "years"/"appears"**. Zero substantive hits stands |

✅ **Figure 1 — now VERIFIED 2026-08-21.** It is a raster image with no text layer, so it was
briefly the one unconfirmed 29148 item; the user supplied the figure text. The transcription in
§7 was substantially right and is now exact, with two structural corrections recorded there
(**two constructs, not three**; and `[Object]` is **absorbed into `[Action]`** in the short
form rather than being independently droppable). Independently, the surrounding prose carries
the same normative force, verbatim: "A requirement **shall state the subject of the
requirement** (e.g., the system, the software, etc.), what shall be done (e.g., operate at a
power level, provide a field for) or a constraint on the system" — so Q3d rests on cl. 5.2.4
prose *and* on the figure. **Every 29148 claim in this plan is now verified against the
standard; only the licensing caveat above remains open.**

**NEW — cl. 5.2.5 *Conforming* is Q3b's single best citation, and the draft missed it.**
Verbatim: "**Conforming.** The individual items conform to an approved standard template and
style for writing requirements." **Template conformance is a normative characteristic of an
individual requirement.** Q3b no longer has to argue that a pattern enum plus validator is a
good idea — the standard requires conformance to a template as one of the nine mandatory
characteristics. That is the strongest available justification for the `pattern` column.

**NEW — cl. 5.2.8 "Requirements attributes" was missing from this file entirely.** It is a
standards-backed attribute list, i.e. exactly what Q3's candidate field list was assembling from
Volere and Planguage. Verbatim highlights:

| 29148 attribute | Verbatim / note | Replaces or corroborates |
|---|---|---|
| **Identification** | "Once assigned, the identification is unique — **it is never changed** (even if the identified requirement changes) **nor is it reused** (even if the identified requirement is deleted)." | **Stronger than ReqIF.** ReqIF says "lifetime immutable"; 29148 adds *non-reuse*. Settles the `id` question with an SDO source — and confirms line/hash-bearing Layer-0 ids cannot be the GR identity |
| **Version Number** | "…as well as to provide an indication of the **volatility** of the requirement. A requirement that has a lot of change could indicate a problem or risk to the project." | Q5 lifecycle; volatility as a signal, not just an audit trail |
| **Owner** | "The person or element of the organization that maintains the requirement, who has the right to say something about this requirement, **approves changes** to the requirement, and **reports the status**" | Q5, and §15's "capture reviewer identity from day one" |
| **Stakeholder Priority** | 1–5 or High/Medium/Low; "not intended to imply that some requirements are not necessary" | Our existing P0/P1/P2 — but note ours is a *derived* heuristic, not a stakeholder consensus, which is a different thing and should be named differently |
| **Risk** | "Requirements that are at risk include requirements that **fail to have the set of characteristics that well-formed requirements should have**." | **Elegant: Q3b's validator output *is* 29148's Risk attribute.** Failing the lint raises `risk`, rather than blocking the write. Independent confirmation of flag-don't-block |
| **Rationale** | "The rationale for establishing each requirement **should be captured**. The rationale provides the reason that the requirement is needed and points to any supporting analysis, trade study, modelling, simulation or other substantive objective evidence." | **Q3j now has an SDO source**, not just Volere and Planguage |
| **Difficulty** | Easy/Nominal/Difficult; "helps with cost modelling" | New — plausibly useful for modernization sizing |
| **Type** | "Requirements vary in intent and in the kinds of properties they represent." | See the negative below |

**And a normative `shall` that lands directly on Q3j**, cl. 5.2.7 verbatim: "**All assumptions
made regarding a requirement shall be documented and validated in one of the requirement's
attributes in 5.2.8 (e.g., rationale)** associated with a requirement or in an accompanying
document." Planguage's `Assumptions` field is therefore not a nice-to-have borrowed from a
1989 notation — **documenting assumptions is a `shall` in the current standard.** For mined
rules, where the extractor is assuming constantly, this is the most defensible new field in the
whole list.

⚠️ **A negative worth recording: 29148's own `Type` taxonomy does NOT fit our corpus.**
Cl. 5.2.8.3's examples are Functional/Performance · Interface · Process Requirements · Quality
(Non-Functional) · Usability/Quality-in-Use · Human Factors — a systems-engineering taxonomy,
not a business-rule one. So `category` must keep borrowing from **Von Halle** (§17a-bis) or
**Withall** (§11); 29148 supplies the *attribute*, not its value set.

Also new: cl. 5.2.4's definition of a well-formed requirement is a **five-bullet "one or more of
the following"** list (met/possessed by a system; qualified by measurable conditions; bounded by
constraints; defines performance of the system "**but not a capability of the user, operator or
other stakeholder**"; can be verified), and it explicitly distinguishes "**between requirements
and the attributes of those requirements (conditions, assumptions and constraints)**" — a
record/attribute split that matches the layered-GR shape.

### 7-ter. Femmer et al. "Requirements Smells" — VERIFIED, with one edition caveat

On disk as `RapidQualityAssurancewithRequirementsSmells.pdf` + `femmer_smells.txt`. This copy is
the **arXiv preprint, arXiv:1611.08847v1, 27 Nov 2016** — openly licensed, so unlike the
standard there is **no provenance problem** with quoting it.

Abstract, verbatim, confirming the numbers this plan leans on: "The automatic detection yields
an **average precision of 59% at an average recall of 82% with high variation**… Yet, **some
smells were not clearly distinguishable**." Also confirmed: the approach is a "light-weight
static requirements analysis approach that allows for rapid checks immediately when requirements
are written down", the prototype is called **Smella**, and the conclusion is that smell detection
is "a helpful means to support quality assurance … **as a supplement to reviews**" — i.e. the
authors themselves position it as a supplement, not a gate. Q3b's flag-don't-block design is the
authors' own recommendation.

⚠️ **Edition caveat that matters:** Femmer's smells are derived from "**29148:2011**" (§3.2 is
titled "Requirements Smells based on ISO 29148"), i.e. the **superseded** edition. Since
*Implementation Free* was a 2011 characteristic absorbed into *Appropriate* in 2018, and
*Consistent* moved to the set level, **Femmer's smell set does not map 1:1 onto the 2018 clauses
Q3b would implement.** The 59%/82% envelope is still the right order-of-magnitude expectation,
but do not claim it as a measured result for a 2018-conformant validator.

Per-smell variation is large and worth knowing before promising a number: precision reaches
**0.96** for the subjective-language smell but falls to **0.59** on another case, and one rare
smell shows a recall of **0.5**. The paper also notes related tools measuring far worse — "a
precision of **12%** is reported" for one prior approach — so 59% is good, not disappointing, for
this class of check.

## 8. Volere — the field list, and the Robertsons' own 3-of-13 verdict

**The snow card, verbatim from the Robertsons' own PDF** (13 fields, in order):

    Requirement #:          Requirement Type:      Event/BUC/PUC #:
    Description:
    Rationale:
    Originator:
    Fit Criterion:
    Customer Satisfaction:  Customer Dissatisfaction:
    Priority:                                      Conflicts:
    Supporting Materials:
    History:

Label precision matters if we borrow them: it is `Requirement #` (not "Number"),
`Fit Criterion` (singular), and "Customer" prefixes **both** satisfaction fields. There is
**no `Release` field** — release numbering is a permitted *value* of Priority.
**`Dependencies` is a real Volere field but from earlier editions** — older cards have
`Dependencies` and no `Priority`; the current card has `Priority` and no `Dependencies`. By
Dec 2009 the Robertsons had moved it off the card: "We keep track of the dependencies
between requirements by maintaining the discipline of a data dictionary."

**Fit criterion — the canonical definition, verbatim:** "A measurement of the requirement
such that it is possible to **non-subjectively** test whether the solution fits the original
requirement." (*Atomic Requirements*, Dec 2009, p.4.) The FAQ adds: "It is needed because
some requirements are too vague or ambiguous to be properly useful," with the example "75%
of first-time users shall be able to buy the correct cinema tickets within 90 seconds,
without using the help functionality."

**The distinction that maps onto our EARS-statement-plus-scenarios design:** fit criteria
are "**input conditions for the eventual test of the software, rather than the test
itself**." And the Robertsons explicitly permit the synonym: "you can call this an
acceptance criterion if you prefer."

**Method (their most recent primary statement, Sept 2024):** establish the fit criterion
**after** the rationale, and "**by negotiating the Fit Criterion with the stakeholder, you
(and the stakeholder) learn more about the real need**." Testability claim: "The
description, rationale and fit criterion together specify the meaning of the requirement and
make it measurable and testable."

**The single most useful line for schema minimalism** — the authors' own triage:
"**We will concentrate on the main three — Description, Rationale, and Fit Criterion — and
ignore the rest of the card.**" Three of thirteen fields carry the weight, and `Rationale`
is one of them.

**Licensing caveat that affects us:** the full template (Edition 20, 90 pp, 27 sections) is
**$55 single project / $255 site licence**, and the licence says it "may not be sold, or
used for commercial gain or purposes other than as a basis for a requirements
specification." Free for genuine academics. **The snow card alone is free, no
registration.** Borrowing field *names* and the fit-criterion *concept* is ordinary
practice; copying the 90-page template into a product is not. Stewardship looks shaky —
every volere.org footer reads "copyright 2019", volere.co.uk is down, and atlsysguild.com
has been lost to a content farm (treat any citation to it as compromised). The template
ships as **Appendix A** of *Mastering the Requirements Process*, 4th ed., Robertson,
Robertson & Reed, Addison-Wesley, 21 Aug 2024, ISBN 978-0-13-796950-0, whose **Chapter 27 is
"Fit Criteria and Rationale"**. (A rumour that James Robertson has died is **not
supported** — Pearson's 2024 author bio is present-tense and he is lead co-author of that
edition. Do not repeat it.)

## 9. ReqIF — real, OMG-only, and interoperability is a project not a checkbox

**Correction to an earlier claim in this file:** ReqIF export was described as something
that lets a client "load LegacyLift's output directly into their existing
requirements-management tool… costs one exporter." **That was too optimistic.** The
structural core travels; the edges lose data, and the spec says so itself.

**Identity:** **ReqIF 1.2, OMG Document Number formal/2016-07-01, July 2016.** Prior: 1.0.1
(Apr 2011), 1.1 (Oct 2013, text-only changes). **It is OMG-only — NOT an ISO standard.**
OMG's own catalogue has a dedicated "ISO Adopted Specifications" section listing 16 specs
(BPMN→19510, UML→19505, SysML→19514, XMI→19509…) and **ReqIF is not in it**; the spec's
normative references are only IETF RFC 2396, XHTML Modularization 1.1, XML 1.0, XML
Namespaces and XML Schema.

**Origin (verbatim from the Acknowledgements):** initial work by the **HIS group** —
"the panel of the vehicle manufacturers **Audi AG, BMW Group, Daimler AG, Porsche AG, and
Volkswagen AG**" — released as RIF 1.0/1.0a/1.1/1.1a, then **ProSTEP iViP** recommendation
RIF 1.2. Renamed because "the acronym RIF has an ambiguous meaning within the OMG" (W3C's
Rule Interchange Format). **"ReqIF 1.0 is the direct successor of the ProSTEP iViP
recommendation RIF 1.2."** Formal OMG submitters were just Atego and ProSTEP iViP.

**Implementation gotcha:** the model and schemas are "**unchanged since ReqIF v1.0.1**", and
the `ReqIFHeader` constraint is "**The value of attribute reqIFVersion must be '1.0'**" — so
a conformant 1.2 file carries `reqIFVersion="1.0"` on the wire. Version negotiation cannot
use that attribute. **ReqIF 1.3 is in development** (ProSTEP: the 2026 merged
"ReqIF Interoperability Forum" has "the publication of the ReqIF 1.3 standard" as its
primary objective), and its **headline issue is table handling** — i.e. tables are a known
live interop defect. Note "ReqIF Recommendation 2.0" (Oct 2020) is a ProSTEP *workflow
recommendation*, not an OMG spec version.

**The data-model idea worth stealing outright: content and structure are fully separated.**
"an instance of SpecObject is 'empty' by itself and therefore contains no data" — attributes
hang off it via types, and the document tree lives entirely in **`SpecHierarchy`**, which
points at a `SpecObject` via its `object` association. So a requirement exists independently
of where it appears in any document, and can appear in several. That is exactly the
GR-record vs. GR-placement split we will need once the same rule appears in a business-rules
doc, a domain doc, and a brief.

Core classes: `ReqIF` (root) → `ReqIFHeader` + `ReqIFContent` + `ReqIFToolExtension`;
`ReqIFContent` composes exactly six collections — `datatypes`, `specTypes`, `specObjects`,
`specifications`, `specRelations`, `specRelationGroups`. Then `SpecObject`,
`Specification`, `SpecHierarchy`, `SpecRelation` (with global `source`/`target`),
`RelationGroup`, `SpecElementWithAttributes`, `SpecType` (four subclasses:
`SpecObjectType`, `SpecificationType`, `SpecRelationType`, `RelationGroupType`),
`AccessControlledElement` (`isEditable`), `Identifiable`, `AlternativeID`.
**Three parallel type ladders, 1:1:1** — `DatatypeDefinition…` / `AttributeDefinition…` /
`AttributeValue…` each × {Boolean, Date, Enumeration, Integer, Real, String, XHTML}, plus
`EnumValue`, `EmbeddedValue`, `XhtmlContent`. 45 classes in clause 10.8 plus 4 in 9.2.

**Directly relevant to our deferred stable-ID question:** `Identifiable.identifier` is
specified as "the **lifetime immutable** identifier." An interchange standard treats
immutable identity as a precondition — which is another argument that line-bearing,
hash-bearing Layer-0 ids cannot be the GR's identity.

**Interoperability, honestly.** The spec's own clause 7.3 tabulates the loss: "When users of
two different brands of requirement authoring tools exchange specifications, information may
get lost due to the different capabilities of the tools," with the consequence
"**Partners exchanging specifications should agree on the requirement authoring tools and
the tool capabilities they use prior to the exchange.**" Formatted content has an explicit
conformance variation point — the `isSimplified` flag on `AttributeValueXHTML`, where an
importer that cannot handle the original must substitute a simplified form, set
`isSimplified=true`, and preserve `theOriginalValue`. Tool extensions are explicitly
non-portable: preservation "cannot be guaranteed if different ReqIF tools are used for
export and import, or different requirements authoring tools are used as source and target."

There is a formal interop regime: ProSTEP iViP runs a **ReqIF Implementor Forum** (vendor
conventions "beyond the standard"), a **Workflow Forum**, and a **Benchmark Team**. The 2025
cycle was the **seventh annual benchmark, 12 system combinations against 588 evaluation
criteria**, with the project leader quoted "Tool vendors are continuously improving their
software, **with significantly fewer errors occurring compared to the previous benchmark**"
— improving, and errors still occurring. Detailed reports are members-only. A ReqIF
specialist (Formal Mind's reqif.academy — commercial interest, they sell ReqIF consulting)
puts it bluntly: "Most requirements tools do not support all ReqIF features!" and "in the
worst case scenario, only a ReqIF-exchange to the same tool will succeed."

**Tool support, graded by evidence quality:**

| Tool | Support | Evidence |
|---|---|---|
| ReqView (Eccam) | both, documented ID-preserving round-trip, exports 1.2 | vendor technical docs — best documented |
| Eclipse RMF / ProR | reference implementation, read/write | Eclipse project page — but **latest release 0.14.0, 2016-03-01**, still "Incubating", last push 2023: effectively dormant |
| Cameo Requirements Modeler (Dassault) | **import only** documented; "tested with IBM Rational DOORS 9.4, 9.5, Next Generation" | vendor technical docs |
| StrictDoc (OSS) | both, "initial support", profiles `p01_sdoc` and `doors` | project docs |
| Jama Connect Interchange | "import, export, and update" | **marketing only** — support hosts 403/JS-only |
| Polarion (Siemens) | "built-in ReqIF" | **marketing only** — help is login-gated |
| Visure | "native ReqIF import/export" | **marketing only** |
| IBM DOORS / DOORS Next | **UNVERIFIED from IBM** — every ibm.com/docs path 403s | corroborated indirectly by ReqView's and Dassault's docs naming DOORS/DNG |
| codebeamer (PTC), Enterprise Architect, Innoslate | **UNVERIFIED** | all 403 / DNS failure |

**Practical guidance:** `SpecObject` / `Specification` / `SpecHierarchy` / `SpecRelation`
plus simple-typed attributes travel reliably. Expect trouble with XHTML rich text and
embedded/OLE objects, **tables**, cross-document links, tool extensions (assume total loss),
and identifier stability across round-trips. The two mitigations that matter: agree the
attribute/type profile with the counterparty before the first exchange (as the spec
instructs), and run a real pilot round-trip with representative content rather than trusting
a "supports ReqIF" checkbox. *One gap:* a document actually titled "ReqIF Implementation
Guide" could not be retrieved — the Forum's conventions clearly exist, the artifact was not
obtained.

## 10. Rupp / SOPHIST MASTeR — and a premise of mine that did not survive

**MASTeR = "Mustergültige Anforderungen — die SOPHIST Templates für Requirements"**, a family
of **seven** templates, not one. Free (email-gated) brochure, **6th edition, 2024**.

**FunctionalMASTER** (SOPHIST's own English rendering):

    [<condition>] <subject matter> SHALL | SHOULD | WILL
       - (autonomous)
       - PROVIDE <whom?|what?> WITH THE ABILITY TO
       - BE ABLE TO
    <verb> <object>

The three middle slots are the **activity types**: autonomous system activity (the slot is
literally **empty** — not a labelled keyword, so the sentence is just
`<subject> SHALL <verb> <object>`), user interaction (`PROVIDE … WITH THE ABILITY TO`), and
interface requirement (`BE ABLE TO`, used when the system acts "only in dependence on
information handover by a third party"). Sibling templates: `EigenschaftsMASTeR`/
PropertyMASTER, `UmgebungsMASTeR`/EnvironmentMASTER, `ProzessMASTeR`/ProcessMASTER, and
three condition templates.

**⚠️ The shall/should/will "decision tree" I posited is UNVERIFIED — do not assert it.**
SOPHIST presents the three as *parallel definitions*, not branches. What they do define is
sharper than the generic account: **MUSS/SHALL** = "**Die Abnahme kann verweigert werden**"
— *acceptance can be refused* — a contractual-acceptance test, not "legally binding";
**SOLLTE/SHOULD** = a stakeholder wish, non-obligatory, raises satisfaction;
**WIRD/WILL** = documents intent and prepares a future integration.

**What SOPHIST does publish as a real discriminator — and it maps onto EARS:** three
condition templates, premised on German *"wenn"* being ambiguous.
**FALLS / IF** = a logical statement, present tense ("a logical expression cannot lie in the
past") → LogikMASTeR. **SOBALD / AS SOON AS** = an event as condition, **non-simultaneity**
("only after condition finishes does main clause apply") → EreignisMASTeR.
**SOLANGE / AS LONG AS** = a time period, **simultaneity** → ZeitraumMASTeR.
That is independent, non-EARS confirmation that *event-triggered*, *state-held* and
*logical-case* conditions are genuinely different things needing different syntax —
i.e. EARS's `When` / `While` / `If` split is not arbitrary.
Also: **"one full verb per requirement sentence"** = 29148's *Singular*, arrived at
independently.

**CPRE correction:** there is **no Foundation Level 4.x**; current is **v3.3.0, 1 April
2026** (the restructuring people remember is **3.0.0, Oct 2020**; the "4" is four
*levels* — Foundation/Practitioner/Specialist/Expert). FL 3.3.0 §3.3 teaches templates only
as a *category* ("phrase templates / form templates / document templates") and points at
literature — citing **[ISO29148], [MWHN2009] (= Mavin et al., EARS, RE'09), and
[Rupp2014]** side by side — but never reproduces MASTeR's slots or MUSS/SOLLTE/WIRD. A real
de-emphasis versus the v2.2 era. Best English source is Rupp & Pohl,
*Requirements Engineering Fundamentals*, 2nd ed., Rocky Nook, 2015, but it aligns to
**syllabus v2.2**, i.e. out of step with FL 3.x. Current German: 7th ed. (not 6th), Hanser,
2020/2021, ISBN 978-3-446-45587-0, ch. 20 covers MASTeR.

Operationalization precedent worth knowing: Arora, Sabetzadeh, Briand & Zimmer,
"Automated Checking of Conformance to Requirements Templates using Natural Language
Processing," **IEEE TSE 41(10):944-968, 2015**, DOI 10.1109/TSE.2015.2428709 — the Rupp
template implemented as an NLP conformance matcher. Direct prior art for Q3b's validator.

## 11. Withall, *Software Requirement Patterns* — 37 patterns, 8 domains

*Software Requirement Patterns*, Stephen Withall, foreword by Karl Wiegers, **Microsoft
Press, 13 June 2007, 384 pp, ISBN 978-0-7356-2398-9**. **37 patterns** ("over 400" example
requirements) — the "30" in the Microsoft Press Store blurb and Open Library is stale
marketing copy; the Preface says 37.

**Eight pattern domains**, several of which are conspicuously legacy-modernization-shaped:

| Domain | Patterns |
|---|---|
| Fundamental | Inter-System Interface; Inter-System Interaction; Technology; Comply-with-Standard; Refer-to-Requirements; Documentation |
| **Information** | Data Type; Data Structure; **ID**; **Calculation Formula**; **Data Longevity**; **Data Archiving** |
| **Data Entity** | Living Entity; **Transaction**; Configuration; **Chronicle** |
| User Function | Inquiry; Report; Accessibility |
| Performance | Response Time; Throughput; Dynamic Capacity; Static Capacity; Availability |
| Flexibility | Scalability; Extendability; Unparochialness; Multiness; Multi-Lingual; Installability |
| Access Control | User Registration; User Authentication; Specific Authorization; Configurable Authorization; **Approval** |
| Commercial | Multi-Organization Unit; **Fee/Tax** |

(There is no "Operational" domain. Two other structural concepts: some sections are
**"Infrastructures"** rather than patterns — Information Storage, User Interface, Reporting —
and there are **"Requirement Pattern Groups."**)

**The anatomy of one pattern entry (§3.2), verbatim, nine fields:** **Basic Details ·
Applicability · Discussion · Content · Template(s) · Example(s) · Extra Requirements ·
Considerations for Development · Considerations for Testing.**

**Why this matters to us:** `Calculation Formula`, `ID`, `Data Longevity`, `Data Archiving`,
`Transaction`, `Chronicle`, `Approval` and `Fee/Tax` are close to the categories a legacy
enterprise system actually yields. If Q3c's typed bodies need a taxonomy, this is a
published 37-entry catalogue of requirement *shapes* with templates and per-pattern
development/testing notes — a better starting point than inventing categories. Still
canonical but dated: print-on-demand since 2014, and the CPRE FL 3.3.0 reference list cites
Wiegers & Beatty and Robertson & Robertson but **not Withall at all**.

## 12. Cross-cutting: three traditions converge on "fit criterion", and they differ usefully

| Tradition | Name | Character |
|---|---|---|
| **Volere** | `Fit Criterion` (a field) | One measurement per requirement, **negotiated with the stakeholder**, established after the rationale; explicitly "input conditions for the eventual test, rather than the test itself"; may be called an acceptance criterion |
| **29148** | *Verifiable* (a mandatory characteristic, not a field) | "structured and worded such that its realization can be proven (verified)… Verifiability is enhanced when the requirement is measurable." Verification gets its own document section (§4, parallel to §3) |
| **Planguage** | `Scale` + `Meter` + `Goal`/`Fail`/`Survival` | Decomposes it: units, then measurement method, then *separate numeric levels* for success, failure and demise, each with `[when, where, who]` qualifiers. Most expressive and most verbose — and **the only one distinguishing "good enough to claim success" from "bad enough to be a failure"** |

**Reading for our design:** Volere's single fit criterion collapses success and failure
thresholds; Planguage's split is the more rigorous decomposition of the same idea. For
conditional business rules (the bulk of our corpus) a G/W/T scenario *is* the fit criterion.
For genuinely quantitative GRs (thresholds, rates, limits, retention periods) the
Scale/Meter/threshold decomposition is the right shape and G/W/T is the wrong one — which is
an argument for the typed-body approach in Q3c rather than one universal acceptance format.

## 13. SCR / Parnas tables — real precedent, but NOT for tabular business requirements

**Correction to an earlier claim in this file.** SCR was described as "a 45-year-old,
battle-tested answer to 'how do you express the required behavior of a system you didn't
design, precisely enough to rebuild it'" and as the method most worth looking at. The
research confirms the *reverse-documentation* half emphatically and **refutes the
transferability half**. The primary sources pre-diagnose exactly where the analogy fails,
and the failure is on our side of the line.

### What is confirmed, and it is worth citing

**The A-7E requirements document was written for an EXISTING program with no usable
requirements — verbatim, Heninger, IEEE TSE SE-6(1), Jan 1980:**

> "The new program must be functionally identical to the existing program… Unfortunately,
> when the project started there existed no requirements documentation for the old program;
> procurement specifications, which were originally sketchy, are now out-of-date. …
> **Writing down the requirements turned out to be surprisingly difficult in spite of the
> availability of a working program and experienced maintenance personnel. None of the
> available documents were entirely accurate; no single person knew the answers to all our
> questions; some questions were answered differently by different people; and some
> questions could not be answered without experimentation with the existing system.** …
> condensing several shelves of documentation into a single, 500-page document."

And the abstract states the purpose outright: "they were developed to document the
requirements of **existing** flight software for the Navy's A-7 aircraft," with the approach
useful "**to document unrecorded requirements for existing systems**."

Reports: Heninger, Kallander, Parnas, Shore, *Software Requirements for the A-7E Aircraft*,
NRL **Memorandum Report 3876, 27 Nov 1978**; revised as **NRL/FR/5530--92-9194**, 31 Aug
1992, 473 pp (full OCR at archive.org/details/DTIC_ADA255746). Effort: **~17 man-months**
for ~12,000 assembler instructions — but that included inventing the method.

**The mechanical checks find what expert review misses — my earlier claim, now VERIFIED.**
Heitmeyer, Jeffords, Labaw, "Automated Consistency Checking of Requirements
Specifications," *ACM TOSEM* 5(3), Jul 1996, 231-261. The checkable properties are
**Coverage** ("the disjunction of the conditions in each row of the table is true") and
**Disjointness** ("the pairwise conjunction of conditions in a row is always false"), plus
type correctness, completeness of definitions, initial values, reachability and
lack-of-circularity. Condition tables must satisfy both; **event and mode-transition tables
get Disjointness only** — they may define partial functions, with totality recovered by the
convention that a variable keeps its old value.

Result on the A-7E document: **17 confirmed Coverage errors** (of 19 reported, across 36
condition tables / 98 rows) and **57 Disjointness errors** (3 mode transition tables, 48
modes, 700 rows) — in **245 seconds** on a SPARCstation 20. And the document had already
"been carefully reviewed by two teams, one made up of NRL computer scientists…, the other
composed of engineers at the Naval Air Warfare Center who maintained the OFP. **As noted
above, our tools detected many significant errors that the reviewers missed.**"

Why coverage errors specifically evade humans, verbatim: "all the information needed to
detect Disjointness errors is in the table, whereas the information needed to detect
Coverage errors is not. **Finding Coverage errors requires knowledge of all values a
variable can take on.**"

**The Darlington process pattern is the most directly reusable thing here.** Wassyng,
Lawford, Maibaum, EMSOFT'11 §2.2 — Parnas's scheme for licensing the Darlington Nuclear
shutdown systems (SDS1: ~40,000 lines of FORTRAN + assembler, 84 monitored / 27 controlled
variables) was: (1) one team builds a mathematically precise **reference description of
required behaviour** from existing requirements/design docs plus expert knowledge, using
tabular expressions; (2) **a separate team independently derives Program Function Tables
(PFTs) from the code**, in which "intermediate variables, so prevalent in code, are all
replaced by equivalent expressions involving only inputs and outputs"; (3) **a third,
completely independent team compares the two** and analyses every mathematical difference to
decide whether it is a behavioural difference; (4) a moderated walkthrough with the
regulator. Cost: "**over U.S. $40M**", and Parnas's own remark that reviewers "analyzed
trivial tables for such properties in documents weighing **40 kilograms**."

That independent-re-derivation-then-compare shape is a genuine precedent for an
extract → referee → compare pipeline, and it is a *process* claim rather than a notation
claim, so it transfers cleanly.

Tables, for the record (NRL 9194 §0.3): **Selector tables** (rows = modes, mutually
exclusive), **Condition tables** (conditions are *cell entries* not column headings, with
values at the bottom — deliberately inverted "to draw attention to this inverted way of
organizing a table"), **Event tables** (`@T(cond)`, `@F(cond)`, `@T(In mode) WHEN(cond)`),
**Initial Modes tables**, and **Mode Transition tables** (row = one conditioned event; cell
entries `@T`/`@F` for triggers and `t`/`f` for WHEN-guards, conjoined). **Mode** = "a class
of system states"; **mode class** = "a partition of the possible states of the system into a
set of modes… the system can be in only one mode of a given mode class at a given time."
A-7E had 5 mode classes, 48 modes. Four-variable model (Parnas & Madey, *SCP* 25(1):41-61,
1995): monitored/controlled variables + input/output data items, related by **NAT** (natural
constraints), **REQ** (required monitored→controlled relation), **IN** (monitored→input
mapping), **OUT** (output→controlled mapping), with accuracy tolerances living in IN/OUT so
REQ can be stated as if measurement were perfect. (Patcas, Lawford, Maibaum, *SCP* 111, 2015
prove Parnas & Madey's acceptability conditions are "angelic" — too weak — and repair them.)

### Why it does NOT transfer to enterprise business rules — five sourced reasons

1. **The method's checkability rests on a small, closed, finitely-valued I/O boundary.**
   Heninger names the failure mode herself: "This approach, identifying functions by working
   backward from output data items, works well because most A-7 outputs are specialized…
   **The approach breaks down somewhat for a general-purpose device, such as a terminal,
   where the same data items are used to express many different types of information.**"
   Their workaround for one such device was **48 "virtual panels"** plus arbitration rules.
   A business system is nothing *but* general-purpose devices — screens, reports, files,
   APIs, a database with 100,000 objects.
2. **Coverage checking requires enumerating every value every variable can take** (quoted
   above). Cheap for `/IMSMODE/ ∈ {Gndal, Norm, Iner, Offnone}`; effectively unbounded over
   enterprise data domains.
3. **Modes must partition the state space** — and even the exemplar failed this. Heitmeyer
   TOSEM 1996 §2.1: "**A deficiency in the original A-7 requirements document… is that a
   mode class may be undefined in certain states**; for example, if no weapon is allocated,
   the Weapons mode class is undefined." Faulk's 1989 thesis had to repair it.
4. **Cost.** 17 man-months for 12K lines of assembler; >$40M and 40 kg of paper for a 40KLOC
   shutdown system. Wassyng & Lawford's own conclusion after thirteen years: "**the methods
   are just too costly without reliable, comprehensive tool support**," and "our methods have
   dealt much better with the logic aspects of behaviour than with anything that involves
   timing."
5. **Zero documented application to business information systems in 45 years.** A full-text
   grep across Heninger 1980, the 473-page NRL 9194, TOSEM 1996, CAV'98, Heitmeyer's 2002
   encyclopedia article, Heitmeyer et al. 2005, the Darlington papers, Parnas CRL-260 and
   Patcas 2015 for *business rule / business logic / information system / enterprise /
   COBOL / banking / insurance / payroll / accounting* returned **no substantive hits**.
   Every documented domain is embedded, reactive, or safety-critical.
   **The decisive signal:** the McMaster group — Lawford, Maibaum, Wassyng, i.e. the exact
   people who industrialised Parnas tables for Darlington over two decades — published on
   large legacy *enterprise* systems (Chen et al., LNBIP, DOI 10.1007/978-3-642-40654-6_17;
   case study of 4.6 million methods, 10 million dependencies, a database with >100,000
   objects) and **used none of the tabular apparatus**. Their keywords are "static analysis"
   and "dependency graph." When the world's most experienced Parnas-table practitioners
   attacked legacy enterprise code, they reached for dependency and change-impact analysis.

### The TCAS II finding — the most important warning in the entire survey

Leveson, Heimdahl, Hildreth, Reese, "Requirements Specification for Process-Control
Systems," *IEEE TSE* 20(9), Sept 1994, 684-707. TCAS II **was** a re-specification of an
existing, fielded, already-certified system — 300 pages of pseudocode plus English, evolved
over 15 years. The paper's index terms literally include "reverse engineering." Verbatim
from §V:

> "**we found it impossible to derive the requirements specification strictly from the
> pseudocode and an accompanying English language description. Although the basic
> information was all there, the intent was missing. Therefore, distinguishing between
> requirements and artifacts of the implementation was not possible in all cases.**"

> "an independent verification and validation was performed to compare the pseudocode
> specification and the RSML specification. The verifiers experienced the same problems that
> we did, and **a large number of identified discrepancies resulted in no change to the RSML
> specification because they merely represented design peculiarities of the pseudocode and
> not requirements.**"

> "**the final requirements specification model would have been different and much simpler
> if we had been starting from scratch.** … **our resulting model is more complicated than
> necessary, includes more than the minimum required behavior, and is harder to understand
> than is strictly necessary. This was frustrating as we first built a nice, simple model and
> found that we had to complicate it for no better reason than that it had to match some
> errors or poor decisions in the pseudocode.**"

> "we had difficulty abstracting away from the design. Even when we did not look at the
> pseudocode, we found it difficult in the beginning to eliminate functional decomposition
> and flowchart-like logic, i.e., **to specify the problem without trying to solve it.** With
> practice we became better at omitting design information, but **the struggle never
> entirely abated.**"

> "an audit trail of decisions and the reasons why decisions were made is absolutely
> essential. **This was not done for TCAS** over the 15 years of its development and those
> responsible for the system today are currently attempting to reconstruct decision-making
> information from old memos and corporate memory."

**Consequences for this plan, and they are not small:**

- This is the strongest available external evidence for **Q3a** (separate observed behavior
  from intended requirement) and **Q3f** (keep implementation artifacts out of the
  normative statement). Leveson's team, with the source in hand and expert reviewers
  available, *could not reliably tell requirement from implementation artifact.* An LLM
  extractor will not do better. The right response is not to try harder — it is to **record
  the distinction as a field and flag the uncertainty**, exactly as Feathers' "mark it as
  suspicious" prescribes.
- **Intent is information-theoretically absent from code.** It was never written down. This
  belongs in the ExecPlan as a stated limitation of the product, not as a gap to be closed:
  a GR store can hold `rationale`, but for mined rules that field is *initially empty by
  necessity* and can only be filled by an SME. That reframes `rationale` from "a field the
  extractor populates" to "the field that structures the SME conversation" — which is a
  better product story anyway, and matches Volere's method (negotiate the fit criterion with
  the stakeholder; establish it after the rationale).
- **Mined specs are inherently more complex than greenfield ones** and will faithfully carry
  the legacy's poor decisions. That is an argument for `suspectedDefect` and for the
  preserve-vs-fix decision being a *recorded, first-class* transition rather than an
  afterthought.

### What to actually cite SCR for

Three claims, all supported: (a) **reverse-documenting an existing system's required
behaviour is legitimate, respectable engineering with a 45-year pedigree** — useful for
client credibility; (b) **a specification format carrying machine-checkable structural
obligations finds real defects that expert human review misses, cheaply** — 17 + 57 defects
in 245 seconds, post-review, which is the single best argument for Q3b's validator and
Q3g's completeness invariant; (c) **the hard limit is missing intent, not notation or
tooling** — Leveson, above.

Do **not** claim SCR as precedent for tabular *business* requirements. The record does not
support it and a knowledgeable reader would catch it.

Tooling status: **SCR\*** (NRL) had a spec editor, Dependency Graph Browser, Consistency
Checker, simulator with domain-specific front-ends, Spin model checker with automatic sound
abstraction, Salsa property checker, invariant generator, TAME/PVS interface, test-case
generator and an APTS C code generator. Adoption claims drift upward across papers
(">50 organizations" 1998 → ">100" → ">200" in 2005) and are self-reported "experimenting
with" counts. **No public download, licence or distribution channel is documented in any
paper**, and the NRL CHACS server that hosted everything no longer exists — all sources came
from the Wayback Machine. Treat SCR\* as unobtainable. The clearest surviving commercial
descendant is **T-VEC's Tabular Modeler (TTM)**, whose own page states it "is derived from
the Software Cost Reduction (SCR) method developed by the Naval Research Lab." Tablewise
(ORA) is dead; **SpecTRM** (Leveson's RSML successor, Safeware Engineering) is effectively
dead — the domain resolves but serves an empty page.

One nuance worth keeping: **nondeterminism is not always an error.** TOSEM 1996: "In some
cases, nondeterminism may not be an error — in fact, **requiring determinism can lead to
overspecification of the requirements**." 2 of the 19 A-7E condition-table reports were
false positives, and an unquantified subset of the 57 disjointness reports reflected
nondeterminism genuinely present in the prose requirements. So even mechanical checks need
domain judgement on their output — a lesson for Q3b's gate design: **flag, don't block**,
which is what was already recommended.

## 15. The evaluation problem — there is no oracle, and one honest number

> This is the most consequential research finding for the plan. Sections 1-6 of the source
> report (the business-rule-extraction literature itself, LLM-based work, Chikofsky & Cross,
> slicing, formal spec recovery, commercial tools, feature location) had not been delivered
> at time of writing and have been re-requested.

### The headline: no benchmark, no ground truth, no accepted evaluation method

**For business-rule / requirements extraction from legacy code there is no accepted
benchmark, no shared ground-truth dataset, and no published evaluation-methodology paper.**
The sharpest proof is that a **2026** paper is still *proposing* an evaluation protocol as
its contribution — **Reversa** (Macedo & Costa, arXiv:2605.18684), verbatim: "We do not
claim broad empirical superiority… and propose an evaluation protocol with metrics for
coverage, traceability, confidence, utility, and cost," and §5.4: "There is no controlled
comparison against a single agent, a conventional documentation tool, or execution without
specifications." Its confidence index "was computed from the classification produced by the
pipeline itself, not by an independent audit."

**Recall is structurally almost never reported**, because recall requires knowing the true
rule set — which is exactly what nobody has.

Auditable negatives (DBLP and Crossref zero-hits are genuine negatives):
`business rule recovery evaluation` → 0 · `business rules program comprehension` → 0 ·
`requirements recovery legacy source code` → 0 · `business rules benchmark` → 1 hit, and it
is document-based (BREX). No Zenodo dataset, no HuggingFace annotated rule benchmark.

**The COBOL benchmark landscape proves it by contrast.** Shared corpora do exist — X-COBOL
(metadata only), **OpenCBS** (Lee, Henley, Hinshaw & Pandita, ICSME 2022, DOI
10.1109/ICSME55016.2022.00030), MainframeBench (arXiv:2408.04660), COBOLEval /
COBOLCodeBench / COBOL-JavaTrans (Dau et al., arXiv:2604.03986) — **but never with rule
annotations.** And **BREX** is the decisive contrast: when the source is *text*, the
community built a **2,855-rule expert-annotated benchmark**; when the source is *code*,
nobody has.

### The one number to anchor expectations: ~29% precision

**Chaparro, Aponte, Ortega & Marcus, WCRE 2012, DOI 10.1109/WCRE.2012.57** — precision only,
judged by **four employees of the system's owner**, one PL/SQL system (SIFI). Verbatim:

> "**29% of recovered rules are correct structural business rules, 36% correspond to
> implementation rules, and 35% are incomplete or incorrect.**"

No recall, because no oracle. **This is the most honest published accuracy figure in the
literature: under a third of automatically recovered rules were correct business rules.**

Note *what* the error modes are, because they map exactly onto our open questions:
**36% were "implementation rules"** — that is Q3a's observed-vs-intended conflation and
Leveson's "the intent was missing", *measured*. And 35% incomplete or incorrect — that is
what Q3b's validator and the referee pass exist to catch.

### Why every other reported number is softer than it looks

- **COBREX (ICSME 2022) reports no evaluation at all.** The field's de facto baseline — the
  thing later work measures itself against — was itself never measured.
- **Cosentino et al. (WCRE 2013)** ran a light evaluation: four internal IBM COBOL experts,
  "given two hours", 6,500 LOC, and critically "instead of generating all rules for the
  system, we focused on the rules related to a small subset of business variables."
  Unanimous agreement, no metric, no inter-rater statistic.
- **AgentModernize's 92.3% / 90.2% must be heavily discounted.** Eight scenarios of
  **195-310 lines each**, **106 gold rules total**, single annotator, artifact anonymized —
  and the oracle's provenance is **circular**: "drafted by the primary annotator with LLM
  assistance (GPT-4o enumerated candidate rules from the legacy code), then manually
  reviewed, edited, and filtered." **The oracle was seeded by an LLM reading the very code
  the pipeline is scored on.** Their own threats section concedes "real legacy systems are
  orders of magnitude larger."
- **Fidelity Probes** benchmarks on **AWS CardDemo** (~12 KLOC, 15 programs) — a public demo
  app. Its premise is the honest terminus of the whole problem, verbatim: "**We treat the
  code as the ground truth directly and measure agreement probabilistically… practitioners
  always know which artifact should be trusted.**"
- **IBM SparseAlign** (arXiv:2510.27244, companion REFINE arXiv:2508.02827) names the modern
  failure mode: "organizations risk a **circular evaluation loop, where unverified LaaJs are
  used to assess model outputs, potentially reinforcing unreliable judgments**."
- Other work and what it actually measured: Huang et al. (*JSM&RP* 1998) — industrial
  anecdote, unnamed and uncounted systems; Earls, Embury & Turner (BT 2002) — cost/yield
  economics on one BT system, effort per rule not correctness; Putrycz & Kark (2008,
  DOI 10.1007/978-3-540-88808-6_5) — scale demo on ~700 KLOC COBOL + 4,000 documents, no
  accuracy metric; Miskell et al. (NLPIR 2023, DOI 10.1145/3639233.3639242) — **no
  evaluation described**; Ayachi, Verhaeghe, Fuhrman, Anquetil (SANER 2026,
  DOI 10.1109/SANER67736.2026.00101) — one real-world codebase, ground-truth construction
  unverified. Worth chasing: McAllister & Cambillau, "Comparing Business Rule Extraction
  Approaches," IKE 2010 (no DOI recorded, DBLP only) — the title suggests it is the only
  comparative study in existence.
- **Closest thing to independent commercial-tool evidence:** Alzahrani, "Trust and
  Hallucinations: A Study of 39 Experts on AI-Assisted Requirements Reverse Engineering,"
  IJACSA 2026, DOI 10.14569/ijacsa.2026.0170413 — 39 senior practitioners rating EPAM ART /
  Copilot / **IBM ADDI**: scores of "4.05 out of 5" and "4.23 out of 5", but
  "**hallucination exceeding 20% were reported by 66.7% of participants**." Low-tier venue;
  weigh accordingly.

### There is no human oracle either — you cannot escape to "ask the SME"

A 30-year documented chain asserts the code is the only trustworthy specification. The
sharpest statement for our purposes, because it closes the SME escape hatch:

> "the business rules enforced by such systems… are often poorly documented (if at all) and
> **incompletely understood by those who own, use and maintain such systems**."
> — Earls, Embury & Turner, *BT Technology Journal*, 2002, DOI 10.1023/a:1021311932020

> "**The key challenge is to understand the underlying specification implemented by the
> software system. Regaining this understanding is more difficult when the source code is the
> only reliable source of information**, documentation is outdated or only present in
> fragments, and original developers are not available anymore."
> — Kirchmayr, Moser, Nocke, Pichler & Tober, ICSME 2016, DOI 10.1109/ICSME.2016.70

> "**software code becomes a more reliable source than any available documentation to obtain
> business rules.** Currently, extracting business rules from legacy systems is heavily
> dependent on human interaction and steering."
> — Wang, Sun, Yang, He & Maddineni, IEEE SMC 2004, DOI 10.1109/ICSMC.2004.1398297

> "the encompassing software is changed without changing the corresponding documents, so
> **the business organization often trusts the code more than any other documents**."
> — Huang, Tsai, Bhattacharya, Chen, Wang & Sun, COMPSAC 1996, DOI 10.1109/CMPSAC.1996.544158
> (earliest verifiable statement, 1996)

> "In those systems, **it is not even clear which business rules are enforced** nor whether
> rules are still consistent with the current organizational policies."
> — Cosentino et al., WCRE 2013, DOI 10.1109/WCRE.2013.6671316

### Requirements quality has no accepted measure either

There is **no accepted measure of requirements correctness or completeness** — only 29148's
qualitative characteristics, with no reference set, no oracle and no scoring procedure. The
proof is that every operational measure is an invented one-off: Sahu, Rai & Roshan (ASME
IDETC/CIE 2024, DOI 10.1115/DETC2024-139583) must build their own 0-1 "requirement quality
index" *in order to* verify against 29148.

**The realistic performance envelope for Q3b's validator** comes from the closest published
analogue: **Femmer, Méndez Fernández, Wagner & Eder, "Rapid quality assurance with
Requirements Smells," JSS 123:190-213, 2017, DOI 10.1016/j.jss.2016.02.047** — transfers the
code-smell metaphor precisely *because* the standard's criteria are not directly checkable,
and reports "**an average precision of 59% at an average recall of 82% with high
variation**" and that "some smells were not clearly distinguishable." So: expect a useful
lint, not a gate. **Independent confirmation of the flag-don't-block design.**

Framing citation for the general problem: Barr, Harman, McMinn, Shahbaz & Yoo, "The Oracle
Problem in Software Testing: A Survey," *IEEE TSE* 41(5):507-525, 2015,
DOI 10.1109/TSE.2014.2372785.

### The template for fixing this exists — in a neighbouring field

**Architecture recovery is the exact analogue and it solved this deliberately.**
- Garcia, Ivkovic & Medvidović, "A comparative analysis of software architecture recovery
  techniques," ASE 2013, DOI 10.1109/ASE.2013.6693106 — "assessing these rigorously has been
  hindered by the lack of architectural 'ground truths'"; they built 8 independently verified
  architectures and then found "even the best-performing methods showed surprisingly low
  accuracy."
- Garcia, Krka, Mattmann & Medvidović, "**Obtaining ground-truth software architectures**,"
  ICSE 2013, DOI 10.1109/ICSE.2013.6606639 — an entire ICSE paper **whose contribution is
  the oracle**: "these techniques are difficult to evaluate due to a lack of 'ground-truth'
  architectures… addresses an inherent obstacle — the limited availability of engineers who
  are closely familiar with the system in question."
  **This is the paper business-rule extraction never wrote.**

Also instructive: **feature location's proxy oracle** — Dit, Holtzhauer, Poshyvanyk & Kagdi,
MSR 2013, DOI 10.1109/MSR.2013.6624019 — uses "the methods/classes actually modified in the
commit that implemented the change request" as ground truth, i.e. bug-fix commits as a proxy
oracle (with known biases: Kochhar et al., ASE 2014 DOI 10.1145/2642937.2642997; MSR 2014;
ISSTA 2016). And **traceability**, which *has* shared datasets and contests (TraceLab,
Cleland-Huang et al. TEFSE@ICSE 2011 DOI 10.1145/1987856.1987861; Keenan et al. ICSE 2012
DOI 10.1109/ICSE.2012.6227244) *still* has no consensus on benchmarking (Shin, Hayes &
Cleland-Huang, SST@ICSE 2015, DOI 10.1109/SST.2015.13: "there is currently no consensus on
how a benchmark should be constructed and used to evaluate competing techniques"), and its
own community frames automated tracing as producing **candidate** links requiring human
vetting. Note **coest.org is dead**; the datasets survive only via third-party Zenodo
re-publications (e.g. 10.5281/zenodo.7867846, 10.5281/zenodo.8367392).

Correction to carry forward: **Chikofsky & Cross 1990 contains no statement about
documentation absence** — do not attribute one to it. Also, a commonly cited Antoniol DOI,
`10.1109/32.988497`, is **wrong** (that is Elbaum et al. on test prioritization); use
`10.1109/TSE.2002.1041053`.

### What this means for the plan — four consequences

1. **Q5's lifecycle is not a convenience, it is the product.** At ~29% precision on the one
   honest published measurement, human review is not a nice-to-have downstream step; it is
   where correctness actually comes from. "We reviewed and signed off on 340 of 470 rules"
   stops being a sales line and becomes the substance.
2. **Q3g's disposition model plus `not_accounted_for = 0` becomes disproportionately
   valuable**, precisely *because* the field has no benchmark. It is an *auditable
   completeness claim* in a domain where nobody can make an accuracy claim. That is the
   strongest defensible quality story available to us.
3. **The GR store can become the oracle the field lacks.** Approved, SME-signed-off GRs with
   code citations are exactly the ground-truth artifact Garcia et al. had to construct by
   hand for architecture recovery — and our store accumulates it as a *byproduct* of doing
   the work. That is a genuinely novel position: not "our extraction is more accurate" (which
   nobody can substantiate) but "we are the only pipeline that accumulates a reusable,
   citation-backed oracle across engagements." Worth stating in the plan as a deliberate
   long-term aim, and it argues for capturing reviewer identity, decision, and timestamp on
   every lifecycle transition from day one.
4. **Never self-score with the same model class that extracted.** SparseAlign's "circular
   evaluation loop" and AgentModernize's LLM-seeded oracle are the two documented ways to
   fool yourself. Our referee/P0-panel design already separates the passes; the plan should
   state explicitly that measured quality claims require an *independent* oracle, and that
   coverage/disposition metrics (deterministic) are the only self-reportable numbers.

## 17. SBVR modality, DMN, and the decision-table void

> Source report's section A (SBVR/RuleSpeak detail) arrived truncated; what survives is its
> bottom-line summary, which covers the facts needed for a decision. Sections B, C and C.4
> arrived in full.

### 17a. SBVR — the definitional/behavioral distinction is airtight

**Confirmed three independent ways:** SBVR builds the distinction into the definitions of
both terms; **Clause 24 gives the two classes different enforcement semantics**; and the spec
defines **`is violated` only for behavioral rules**. The mapping is
**alethic modality → definitional rule** (cannot be violated — it defines what is true) and
**deontic modality → behavioral rule** (can be violated — needs enforcement and a violation
response).

Three implementation consequences:
1. `alethic → definitional`, `deontic → behavioral`.
2. **Attach enforcement levels only to behavioral/operative rules.** A definitional rule has
   no enforcement level because it cannot be broken.
3. **Do not call the six enforcement levels normative SBVR.** They appear under an
   `Example:` caption, and SBVR §6 declares examples purely informative; they trace to
   **BMM**, not RuleSpeak.

**Correction to an earlier claim in this file.** Von Halle's taxonomy was given here as
"mandatory constraint / guideline / action enabler / computation / inference." **"Mandatory
constraint" is UNVERIFIED** — every reachable source says plain **"constraint."** Verify
against the physical book (*Business Rules Applied*, Wiley, 2001, ch. 2) before printing it.
Also: **"is by definition" is NOT a RuleSpeak keyword** — not found in any Ross source.

### 17a-bis. Von Halle ch. 2 — READ FROM THE BOOK 2026-08-21, and it settles more than the one term

Source now on disk: `Von-Halle-Business_Rules_Extracted_and_Restructured.docx` (+ `Von-Halle-ch2.txt`),
the relevant section of ch. 2 transcribed from the user's print copy of *Business Rules
Applied* (Wiley, 2001). **This replaces every "unverified" flag on Von Halle in this file.**

**The "mandatory constraint" question is resolved — both terms are correct, at different
levels of her taxonomy.** That is why secondary sources disagreed.

- **`constraint` is the parent.** Verbatim: "A constraint can be a **mandatory restriction or
  suggested restriction** on the behavior of the business event."
- **`mandatory constraint` is the leaf**, and it is the label used in Table 2.2, Table 2.3 and
  the seven-classification list. Verbatim definition: "A complete statement that expresses an
  **unconditional circumstance that must be true or not true for the business event to complete
  with integrity**."
- Figure 2.2 renders the pair as "**Constraints (mandatory)**" and "**Guidelines
  (suggestions)**".

So the original claim in this file was right and the correction that flagged it was
over-cautious. **Print `mandatory constraint` when naming the leaf class; print `constraint`
when naming the parent.**

**The taxonomy is seven classifications, not five, and terms/facts are peers of rules.**
Verbatim: "there are **seven** different kinds of business rule classifications needing
templates: **terms, facts, mandatory constraints, guidelines, inferences, action enablers, and
computations**." Figure 2.1 "divides the world of business rules into only **three** major
categories: **terms, facts, and rules**", and Figure 2.2 decomposes `rules` by intent:
constrains information (mandatory constraint, guideline) · enables other action (action
enabler) · creates new information (computation, inference).

⚠️ **Internal inconsistency to be aware of:** Table 2.2 labels the fifth rule class
**`Inference`**; Table 2.3 labels the same class **`Inferred knowledge`**. Both appear in the
book. Prefer `Inference` (it is the one used in the prose and the seven-classification list).

**Term / fact / rule is a third independent convergence, and the earliest of the three.**
Von Halle 2001 → SBVR's term / fact type / rule (1.0 in 2008) → KDM's `TermUnit` / `FactUnit` /
`RuleUnit` (2012, ISO/IEC 19506). She also pre-maps them to the data model, verbatim: "terms
will turn out to be entities, attributes, domains, or constants" and "facts will turn out to be
relationships among entities or the association of an attribute to an entity." **This
materially strengthens the KDM-vocabulary recommendation in §20.1** — it is not an OMG
invention being retrofitted, it is the business-rules tradition's own structure.

**She explicitly disclaims exhaustiveness — so it cannot be used as a closed enum.** Verbatim:
"It certainly is not the intent of this book to suggest unnecessarily another business rule
classification scheme"; "**You do not need to use this scheme. Feel free to adopt a scheme that
best suits your most important audience and serves your most important purposes.**" And one
class is deliberately excluded from Figure 2.2 — the **presentation rule**, "included because
they appear as a classification of rules within some commercial business rules products",
refined by C. J. Date (2000) into field labels, alignment, colours, fonts, captions, edit masks,
field defaults. (Note: our existing P2 priority tier — "display/formatting/convenience" — is
exactly Date's presentation rules.)

**Her stated purposes are, unexpectedly, an argument for Q3b's per-category patterns.**
Purpose 3, verbatim: "**Enables business people to express each kind of business rule in its own
kind of sentence template for better clarity.**" And Table 2.3 delivers exactly that — a
distinct template per classification, e.g. `<term1> MUST BE <comparison> <term2>, <value>,
<value list>` for mandatory constraints, `<term1> SHOULD BE …` for guidelines,
`<term1> IS COMPUTED AS <formula>` for computations, `IF <term1> <operator> <term2> THEN
<action>` for action enablers, and an `IF … THEN <term3> <operator> <term4>` form for inferred
knowledge. **This is a 2001 precedent for pattern-per-category rather than one universal
notation** — a design point Q3b/Q3c were reaching for without a citation.

**Figure 2.3 — four expression forms by audience, with a quality checklist per form.** This is
a 2001 precursor to 29148's quality characteristics, staged rather than absolute:

| Form | Audience | Properties |
|---|---|---|
| Business conversation piece | — | may not be relevant / atomic / declarative / precise / reliable / authentic; may be incomplete, redundant, inconsistent |
| Natural language version | business community | relevant · atomic · declarative · reliable; **not totally precise**; may be incomplete, redundant, inconsistent |
| Rule specification language version | business + technical | relevant · atomic · declarative · **precise · complete · reliable · authentic · unique · consistent** |
| Rule implementation language version | target technology | **executable**; may be procedural |

The third row is essentially 29148 cl. 5.2.5/5.2.6 seven years early. **Useful for the plan:
it says the quality bar is a function of which form a statement is in** — which is precisely
what a GR store needs, since a mined `as_built` string and a signed-off `statement` are not the
same form and should not face the same lint.

**One more entry for the 26-year-gap timeline (§19).** Verbatim, 2001: "**Unfortunately, there
is no standard rule specification language.** There are various rule languages proposed as part
of their modeling approaches." That sits neatly between GUIDE 2000 ("much work remains") and
Normantas 2013 ("not acceptable solution").

**And a line that directly supports Q3h.** Verbatim: "**all business rules are about data.**
That is, terms define data concepts and details, facts define associations among data,
constraints and guidelines test data values, computations arrive at a data value, inferences
arrive at a data conclusion, and action enablers evaluate data values prior to initiating
action." If every rule class is definitionally about data, a computed reads/writes block is not
an add-on — it is the one attribute every GR necessarily has.

**Mapping to our current `category` enum — two real gaps.**

| Von Halle | Our `category` | Note |
|---|---|---|
| Computation | `Calculation` | Clean match; her definition even enumerates the operations ("sum, difference, product, quotient, count, maximum, minimum, and average") |
| Mandatory constraint | `Validation` | Clean match |
| **Guideline** | **— nothing** | **GAP.** A rule that warns without rejecting: "does not force the circumstance to be true or not true, but merely warns about it, **allowing the human to make the decision**". Any warn-don't-block rule in the corpus is currently being forced into `Validation` and silently promoted to mandatory |
| Inference | `Policy` (partly) | Creates a new *fact* ("if a customer has no outstanding invoices, then the customer is of preferred status") |
| Action enabler | `Policy` (partly) | Initiates an event/message outside the system boundary. Her framing is useful: "think of mandatory constraints and action enablers as **opposites**. Mandatory constraints stop an event from completing. Action enablers start an event" |
| — | **`Lifecycle`** | **GAP in the other direction.** Her four ways a rule guides a business event are present information / constrain information / initiate external action / create new information. **There is no state-transition or lifecycle class.** So our `Lifecycle` category has no Von Halle counterpart and cannot borrow her authority — it needs its own justification (or maps, weakly, to action enabler) |
| — | `Priority: P2` display rules | = Date's **presentation rules**, which she names and deliberately excludes |

Her own triage of where the work is, verbatim: "The rule classifications you are likely to
spend the most time on … are **computations, constraints, and inferences**", for three stated
reasons — they create knowledge or restrict behaviour rather than present information;
responsibility for them "has been split or under debate between database and application
professionals"; and they "are the kinds of rules **most frequently supported in commercial rules
products**." That is independent corroboration of Q3c's bet: the typed bodies worth building
are exactly computation (→ `formula`) and constraint/inference (→ `decision_table`).

**Lead to chase:** she twice cites **Ross (1997)** as "an outstanding text on a classification
scheme of rule clauses" — i.e. a finer-grained taxonomy one level below her seven, at the
*clause* level. Not obtained.

### 17a-ter. SBVR v1.0 — READ FROM THE SPEC 2026-08-21, and it settles Q3i outright

Source now on disk: `SBVR-1.0.pdf`, supplied by the user as an OMG member. **Two corrections to
this file's own provenance notes before anything else:** the RuleSpeak material is in **Annex F**
("The RuleSpeak® Business Rule Notation", p. 343), **Annex H** is *Use of UML Notation in a
Business Context*, and **neither was member-restricted** — all of it is in the public v1.0
document. Open action #5 was chasing the wrong annex for the wrong reason.

**The F.1.1 modal-operations table, recovered verbatim** (this is what was lost when a research
report arrived truncated):

| Modal claim type | Statement form | SBVR Structured English | RuleSpeak |
|---|---|---|---|
| obligation formulation | obligative statement | `it is obligatory that p` | `r must s` |
| obligation formulation embedding a logical negation | prohibitive statement | `it is prohibited that p` | `r must not s` |
| permissibility formulation | restricted permission statement | `it is permitted that p only if q` | `r may s only t` |
| permissibility formulation | unrestricted permission statement | `it is permitted that p` | `r may s` / `r need not s` |
| necessity formulation | necessity statement | `it is necessary that p` | `r always s` |
| necessity formulation embedding a logical negation | impossibility statement | `it is impossible that p` | `r never s` |
| possibility formulation | restricted possibility statement | `it is possible that p only if q` | `r can s only t` |
| possibility formulation | unrestricted possibility statement | `it is possible that p` | `r sometimes s` / `r can s` |

**And the part that matters most for our schema — the keyword sets are split by rule class,
verbatim from p. 345:**

- *Operative* Business Rule or Advice: **`must`** or `should`, **`must not`** or `should not`,
  **`may … only`** (often `may … only if`) — all rule keywords; **`may`** or `need not` — advice
  keyword.
- *Structural* Business Rule or Advice: **`always`** (often `can … only if`), **`never`** or
  `not always`, **`can … only`** — rule keywords; **`sometimes`** — advice keyword.
- Special-purpose structural keywords, with `always` implicit: **`is to be considered`** /
  `is to be [number]` (derivation or inference), **`is to be computed as`** (computation),
  **`is to be fixed at [number]`** (establishing constants).

✅ This confirms the earlier correction that **"is by definition" is not a RuleSpeak keyword** —
the derivation keyword is `is to be considered`.

**Consequence for Q3b, and it changes the design:** a single flat `pattern` enum validated
against one keyword list is wrong. `must`/`must not` are *operative* keywords and
`always`/`never` are *structural* ones; using `always` for a behavioral rule or `must` for a
definitional one is a category error the validator should catch. **The validator's keyword set
must be selected by Q3i's `rule_class`.** That also gives Q3b a cheap, real check that is not
just "did the sentence match a template".

**Consequence for Q3i — it is no longer our reasoning, it is the spec's text:**

1. `operative business rule` carries the stated **Synonym: `behavioral business rule`**, and the
   stated **Necessity: "No operative business rule is a structural business rule."** The two
   values are exhaustive and disjoint by definition, so a two-valued `rule_class` is exactly
   right — and *our chosen word "behavioral" is SBVR's own synonym*, not a coinage.
2. Enforcement attaches to operative rules **only**, and this is stated twice: the fact type is
   literally `operative business rule has level of enforcement` (cl. 12.1.3), and cl. 12.6.12's
   caption note reads "The `Enforcement Level' caption labels the enforcement level that applies
   to an operative business rule **(only)**." Q3i(a)'s "`enforcement_level` valid only on
   behavioral" is therefore a **verified constraint**, not a design preference.

**Consequence for Q3k — the warn-don't-block tier belongs here, not in `category`.** cl. 12.1.3
defines `level of enforcement` as "a position in a graded or ordered scale of values that
specifies the severity of action imposed in order to put or keep an operative business rule in
force", and gives a six-value example set: **`strict`** (violate it and you cannot escape the
penalty), **`deferred`** (strictly enforced, enforcement may be delayed), **`pre-authorized`**
(exceptions allowed with before-the-fact override authorization), **`post-justified`** (if not
approved after the fact, you may be subject to sanction), **`override`** (comment must be
provided when the violation occurs), **`guideline` ("suggested, but not enforced")**. Von Halle's
`guideline` and SBVR's `guideline` are the same concept at the same name, arrived at
independently — which is the strongest kind of corroboration available here.
⚠️ **§17a's caveat is confirmed from the primary source and must be kept:** the six values sit
under an `Example:` caption ("An example set of levels of enforcement, **based on [BMM]**"), and
SBVR §6 declares examples informative. Cite them as *an example set SBVR gives*, never as a
normative SBVR enum.

**One more usage rule worth stealing, and it ties `should` to enforcement level.** RuleSpeak's
own rule 1: "`Should' may be used in place of `must' in expressing a business rule only if one of
the following is true: the business rule does not have an enforcement level; or the business rule
has an enforcement level, and that enforcement level is consistent with the English sense of
`should'." Restated by the spec as a prohibition: `should` must *not* replace `must` when the
rule has an enforcement level inconsistent with the sense of `should`. **This is a directly
implementable cross-field validation** between the modal keyword and `enforcement_level` —
another Q3b check that costs nothing and catches a real confusion. (Rule 2: "`May' must be used
in the sense of `permitted to'. `May' must not be used in the sense of `might'." — also lintable,
and exactly the ambiguity an LLM extractor will produce.)

**`advice` is a distinct element of guidance, and it is not a rule.** cl. 12.1.4 defines
`advice` as an "element of guidance that is practicable and that is a claim of permission or of
possibility", with the stated Necessities **"No business policy is an advice"** and **"No
business rule is an advice."** So if we ever want to record "it is possible that an account
balance is negative" (SBVR's own example), that is a **separate kind of record**, not a
`category` value on a rule. Filed as a note against Q3k rather than a new question — our corpus
is unlikely to yield advices, and the note exists so that nobody later adds `advice` to the
category enum by analogy with `guideline`.

### 17b. DMN — the hit policies, and where verification actually lives

**Current formal version is 1.5, `formal/24-01-01`, August 2024. There is no 1.7 document at
all** (correcting a "1.7 beta" seen on the spec page).

**Hit policies — the closed set of 11 strings from Table 46:**
`U` (Unique) · `A` (Any) · `P` (Priority) · `F` (First) · **`R` (Rule order)** ·
**`O` (Output order)** · `C` (Collect) · `C+` (sum) · `C#` (count) · `C<` (min) ·
`C>` (max).

**The critical finding: gap/overlap detection is decidable and shipping, but it is NOT in
the DMN spec.** The spec supplies the predicates and a single `SHALL`, then leaves the
algorithm entirely to vendors — and **deleted its only explicit completeness construct in
version 1.1**. So "DMN gives you mechanical gap and overlap checking" is true of *tools*,
false of the *standard*. State it that way.

**The strongest tool by a wide margin is Drools / Apache KIE:**
- **`ANALYZE_DECISION_TABLE`** finds **gaps, overlaps, masked rules, misleading rules,
  subsumed rules, contracted rules, and normal-form violations**.
- **`COMPUTE_DECISION_TABLE_MCDC`** computes MC/DC coverage over a decision table.
- **`MCDC2TCKGenerator` emits DMN-TCK test-case XML directly from a decision table.**

⚠️ The **DMN TCK is still on 1.4** — do not cite TCK results as evidence of 1.5 conformance.
⚠️ **Trisotech does only *syntax* V&V**, not gap/overlap analysis, contrary to common
assumption. Camunda has nothing on COBOL/mainframe → DMN.

DMN's own vocabulary is worth borrowing regardless: **contracted / expanded / limited-entry**
are verbatim spec terms.

### 17c. History — completeness checking of decision tables is a 1963 idea

Decision-table **completeness and consistency checking** dates to **Pollack, RAND
RM-3669-PR, 1963**, was formalized by Vanthienen's group at KU Leuven from 1986, and became
*terminology* in DMN but never an *algorithm*. The CODASYL Decision Table Task Group was
still writing about "consistency and redundancy" in 1982.

Provenance corrections worth keeping (a long list of commonly-repeated errors was compiled):
- The decision-table symposium was **September 20-21, 1962**, CODASYL-JUG, Barbizon Plaza
  Hotel, New York, 450-500 attendees. **There was no 1966 ACM decision tables symposium.**
- ***SIGPLAN Notices* 6(8), Sept 1971 is a special issue titled "Decision Tables," edited by
  C. J. Shaw**, pp. 1-111 — **not** a symposium proceedings. No such proceedings title exists.
- The IBM manual is *Decision Tables: A Systems Analysis and Documentation Technique*, form
  **F20-8102**, **1962** (not GF20-8102, not 1971). The 1971 Wiley book is Pollack, Hicks &
  Harrison, ***Decision Tables: Theory and Practice*** — a different work. Humby,
  *Programs from Decision Tables*, Macdonald / American Elsevier, 1973.
- **IBM "DTAB" does not exist** — absent from every period bibliography.
- The 1957 credit belongs to **GE's Integrated Systems Project under Burton Grad**, not
  "Sutherland."
- Best consolidated map of 1957-1974 work: **Pooch, "Translation of Decision Tables," *ACM
  Computing Surveys* 6(2), 1974, 125-151, DOI 10.1145/356628.356630** — its 107-item
  bibliography is exposed in full by Crossref.
- Optimization lineage ends at **Hyafil & Rivest, *IPL* 5(1), 1976,
  DOI 10.1016/0020-0190(76)90095-8 — optimal decision-tree construction is NP-complete.**
  (Decision-table *verification* being NP-hard is **unsupported** — do not claim it.)

### 17d. Myers' cause-effect graphing IS decision-table derivation — in his own words, twice

This matters because it links the testing tradition to the decision-table tradition, and
because it is the shape of what we would be building.

*The Art of Software Testing*, 3rd ed. (Wiley, 2012), p. 62, verbatim, step 5 of the
procedure: "**By methodically tracing state conditions in the graph, you convert the graph
into a limited-entry decision table. Each column in the table represents a test case.**"

And p. 72, verbatim: "**The next step is the generation of a limited-entry decision table.
For readers familiar with decision tables, the causes are the conditions and the effects are
the actions.**"

So: causes ↔ conditions, effects ↔ actions, **each column is one test case**. And p. 61
claims the same benefit Pollack claimed for decision tables 16 years earlier: cause-effect
graphing "**has a beneficial side effect in pointing out incompleteness and ambiguities**."

Constraint set confirmed verbatim — **E** (at most one of a,b is 1) · **I** (at least one of
a,b,c is 1) · **O** (one and only one) · **R** (a requires b) among *causes*; **M** (masks)
among *effects*.

**Provenance corrections:** the true origin is **Elmendorf, *Automated Design of Program Test
Libraries*, IBM TR 00.2089, 26 Aug 1970** (primary document retrieved), not the
commonly-cited 1973 TR-00.2487. Elmendorf used constraints **E, I, U** (no R, no M) and
**used no decision tables at all** — he enumerated "test patterns" classified
feasible/meaningful/unique. **The decision-table formulation is Myers', not Elmendorf's.**
Elmendorf's 1969 IEEE paper contains **no** cause-effect graphs — do not cite it for CEG.
And **Myers' 3rd edition does not credit Elmendorf** (full-text search returns zero); the
lineage is documented by third parties only.

**A lovely detail with direct bearing on our typed bodies:** Elmendorf's 1970 enumeration
base is **3ⁿ, not 2ⁿ**, because each cause can be *invoked, suppressed, or **ignored***.
That third state is exactly Myers' blank in a limited-entry table and exactly DMN's `-`.
**Three notations, one concept, 1970 → 1979 → 2015.**

**A documented negative result that should shape any table-based design:** Nursimulu &
Probert (CASCON '95) show that **the same decision table is produced whether or not the
One-and-only-one, Inclusive, or Exclusive constraints are present** — i.e. **the decision
table alone cannot detect a constraint omission.** Argument for treating the *graph* (or the
constraint set) as a reviewable artifact in its own right, not just the table.

### 17e. THE VOID: nobody recovers decision tables from source code

**This is the strongest negative result in the entire survey.**

- **Code → DMN: exactly one paper exists, a 2026 preprint.** van de Hoef, Vranken, Leewis &
  Smit, "Applying LLMs for Automated Extraction of Business Logic from Source Code into DMN
  Models," SSRN, **DOI 10.2139/ssrn.6299556** — GPT-4.1 and Gemini 2.5 Pro, Design Science
  Research methodology. ✅ **OBTAINED AND READ IN FULL 2026-08-21 — see §17e-bis.** Confirmed:
  still stamped "Preprint not peer reviewed"; the language is **Java, single-file** (not COBOL);
  the prototype is **DeCoMi**, source available on OSF; and the results are **weak** — decision-rule
  F1 hits 0% on three of eight logic cases and collapses past ~6 rules per table. **This
  materially changes Q3c — see the consequences at the end of §17e-bis.**
  Provenance note: Leewis & Smit come from the *decision-mining* side, so this looks like the
  first deliberate bridge between the two literatures.
- **Decision tables recovered from source code: nothing at all was found.**
- **"Decision mining" is a different field.** Rozinat & van der Aalst (BPM 2006) coined it
  for mining decision points from **event logs**; Batoulis/Bazhenova/Weske extract DMN from
  **BPMN models**. Input is always logs or models, **never source code**, and the two
  communities barely cite each other.

**And the sharpest observation in the report:** the slicing-based business-rule-extraction
literature **already computes exactly the path conditions a decision table needs** — Xie's
dependence-cache slicing, Hatano's conditional-statement extraction, A-COBREX's multi-variable
execution paths — **and then presents them as slices, conditions, or code fragments. Nobody
takes the last step of pivoting them into a condition-stub / action-stub table.** As the
report puts it: "the dominant field definition of 'a business rule' is literally an execution
path over a business variable — which is a decision table row that nobody has written down as
one."

**With a historical irony worth putting in a client deck:** from 1962 to 1974 the industry
shipped a dozen decision-table **preprocessors** (DETAB-X, DETAB/65, DETAP, TABSOL,
Detap/55, LOGTAB, LOBOC, TAB40…) that compiled decision tables *into* COBOL.
**Nobody has published a tool that turns COBOL back into decision tables.**

### 17e-bis. van de Hoef et al. — READ IN FULL 2026-08-21. The one code→DMN paper, and it partly undercuts §17f(3)

On disk as `Applying LLMs for Automated Extraction of Business Logic.pdf` +
`vandehoef_dmn.txt`. This was flagged throughout this file as "the single highest-value unread
item" and "if one paper is to be obtained and read in full, this is it." It has now been read.
**Two things it settles, and one thing it damages.**

**Identity and status.** van de Hoef (HU Utrecht), Vranken (Open Universiteit / Radboud),
Leewis, Smit. SSRN abstract 6299556. ⚠️ **Every page is stamped "Preprint not peer reviewed"** —
the earlier caveat in this file was correct and should be kept. Experiments ran April–May 2025.

**Settled #1 — the language question. It is Java, single-file, and NOT COBOL.** FR1: "The
prototype must ask the user to provide source code in **a single file format** as input." Their
own future work notes "decisions were extracted from Java source code, but different
programming languages may require distinct approaches." **This is unexpectedly good news for
us:** the entire rest of the business-rule-extraction literature is COBOL/mainframe, whereas our
corpus is Java/C#/T-SQL. The only code→DMN work in existence is on our language family.

**Settled #2 — the artifact is obtainable.** The prototype is **DeCoMi** ("Decision source Code
Mining"), and "its source code is available via the Open Science Framework (van de Hoef, 2025)",
as are all cases and few-shot examples. **This is a working four-stage pipeline with a published
prompt set and a 10-item FR list we can read rather than reinvent.** Highest-value follow-up
action from this paper.

**The four-stage design** (compare our own pipeline): (1) decision identification at **function
level** — split the file into parts containing decisions, assigning a model ID (groups decisions
into one DMN model) and a decision ID; (2) DRD extraction → JSON `{decisions, input data,
requirements}`; (3) decision-table extraction → JSON `{input, output, decision rules}`, **one
table at a time** (FR8); (4) JSON → DMN XML, rendered in the front end. Notably the UI does what
we would want: "when the user clicks on a decision in the DMN model, **the corresponding source
code for this decision is shown**" — i.e. GR→code citation, already built.

**The damage — the results are weak, and they collapse as complexity rises.** Dataset: **10
cases** (C1–C5 contain decision logic, C6–C10 contain none and exist to test false positives),
drawn from Java OSS projects via Florez et al. (2022) — itself a lead: *299 annotated data
constraints across 15 Java open-source projects*. The largest case is 3,488 LOC with **3
decisions and 19 decision rules**. Gold standard built by **one** professional DMN modeler over
three iterations.

Decision-rule extraction F1, best configuration per case (Table 9):

| Case | Gold rules | Best decision-rule F1 | Note |
|---|---|---|---|
| C1 | 2 | **100%** | trivial |
| C2 | 4 | 75% | |
| C3 | 3 | **0%** | zero across *every* model and temperature |
| C4.1 | 6 | 83.3% | GPT-4.1, temp 1 |
| C4.2 | 7 | 57.1% | |
| C5.1 | 7 | 71.4% | one config only; most configs 0% |
| C5.2 | 4–6 | **0%** | zero across every model and temperature |
| C5.3 | 8–10 | **0%** | zero across every model and temperature |

**Beyond roughly six rules, decision-rule extraction essentially fails.** Also: accuracy on
prompt question Q4 (the data type of the information item) is **0% for every model at every
temperature** — "the data type of variables in the source code was almost always used instead of
the data type for the information item."

The one stage that *does* work is **step 4, JSON→DMN XML**: Gemini 2.5 Pro achieved **100%
accuracy at temperatures 0–0.6**, validated by loading the generated XML into `dmn-js`. So
serialization is solved; comprehension is not.

**Their diagnosed failure mode is our Q3a/Q3f problem, measured a third time.** Verbatim: the
LLMs "had difficulty **separating the source code from the decision made in the source code**."
That now joins Chaparro's 36% "implementation rules" and Leveson's TCAS II as a **third
independent observation of the same conflation** — and the first one on Java rather than COBOL or
pseudocode. They also found LLM background knowledge actively corrupting extraction: awareness of
libraries and functions "led to the actual values of the decision rules being **changed** based
on their knowledge of these libraries and functions", *despite* a prompt explicitly forbidding
interpretation — with the sharp observation that "it is unclear when the LLM uses its own concept
instead of the given definition."

**One finding that is genuinely good news, and it strengthens Q3g.** Unlike GPT-3 in the prior
natural-language work, the modern models **did not hallucinate rules to fill gaps**: "Gemini 2.5
Pro and GPT-4.1 would rather **omit** decision rules or express the same concept more extensively
than to devise a decision rule itself to create a complete decision table." **The measured
failure mode is omission, not fabrication.** That is precisely the failure a
`not_accounted_for = 0` completeness invariant catches, and it means Q3g's disposition model is
aimed at the right risk. It also lowers the priority of hallucination defences relative to
coverage defences.

**A gap we are positioned to fill.** Their limitations, verbatim: "each decision table was
extracted separately, i.e., **dependencies between decisions were not included, as the LLMs did
not receive the context of other decisions**." We have that context deterministically — Layer-0
call edges, `uses_table`, M24 `has_column`. **Supplying inter-decision dependencies from the
graph instead of hoping an LLM infers them is a concrete, defensible differentiator**, and it is
the same argument as Q3h.

**Two conventions worth comparing against our own choices:**
- They deliberately **kept implementation naming**: "No interpretations of the source code have
  been made… all elements were modeled **as they appear in the original source code**", for
  "transparency and consistency", including function names with parameter lists (because Java
  method overloading requires it). That is the **opposite** of Q3f(b) — and instructive: even
  with implementation naming as the explicit target, the LLMs still could not hold the line. It
  also validates keeping `implementation_notes` for exactly their stated reason.
- Their dash convention matches §17d exactly: `-` means "the input is not applicable or not
  evaluated for that rule", used when a variable does not directly lead to a return value.
  **Elmendorf's 3ⁿ third state, confirmed in practice in 2026.**
- ⚠️ A DMN modelling limitation they hit: they used `String` as the information-item data type for
  return statements because "while this does not correspond to the nature of a return statement,
  it is **the most suitable option available in DMN**."

**And the no-oracle problem reappears, in their own words.** Precision/recall/F1 were
*unusable* for step 1 "because the gold standard may not model all decisions in the source code…
manually modeling and validating all decisions for a gold standard is time-consuming. **This is
precisely why an automated DMN model extraction method is needed.**" Their headline
interpretive caveat is the same one §15 raises: deviations from the gold standard "do not
necessarily imply that the resulting DMN models are incorrect but rather modeled in a different
manner. **This is not evident from quantitative analysis.**"

Other limitations they state plainly: 10 cases so "results cannot be generalized"; **one run per
case/setting** despite LLM non-determinism; 2–3 iterations per experiment; a prototype bug that
used temperature 0 instead of 0.6 for DRD extraction; a minor error in the step-4 prompt
(expected JSON stated where DMN XML was meant); and **Gemini 2.5 Pro was discontinued mid-study**,
blocking planned chain-of-thought runs. They are commendably explicit that the DSR contribution
is "the instantiated artifact and approach… **rather than in the performance of any specific LLM
version**."

### Consequences for this plan — Q3c's oracle argument needs restating, not withdrawing

§17f(3) proposed: extract to DMN XML → `ANALYZE_DECISION_TABLE` → `COMPUTE_DECISION_TABLE_MCDC`
+ `MCDC2TCKGenerator` → replay against the legacy system and diff. **The Drools/KIE half of that
chain is unaffected** — those tools were verified independently and do what they claim. What this
paper damages is the **implicit assumption that the extracted table is good enough to be worth
analysing.** At 0% decision-rule F1 on 8-rule cases, it often will not be.

The correct response is to invert the framing rather than abandon it:

1. **The equivalence loop is not a validation of good extraction — it is the detector of bad
   extraction.** Because a DMN table is executable, replaying MC/DC-derived inputs against the
   legacy system tells you *which specific tables are wrong*, mechanically, with no human
   annotation. Given this paper's numbers, that is **more** valuable, not less: it is the only
   place in the whole design where extraction error is measurable rather than assumed.
2. **Expect to reject most extracted tables at first**, and design for that: a `decision_table`
   body should carry its own fidelity verdict, and failing the replay must be an ordinary,
   recorded outcome (→ Q3g's disposition, and Q3a's dual confidence), not an exception.
3. **Do not promise DMN coverage of the corpus.** The honest claim is "for the decision-logic
   subset, we can *measure* fidelity" — not "we can extract decision logic reliably." Nobody can,
   as of the only published attempt.
4. **Sequence it after the count.** Q3c already says to measure how many NNG rules collapse into
   a table during the first milestone. This paper adds a second number worth measuring on our own
   corpus: **the rule-count distribution per candidate table.** If most candidates exceed ~6
   rules, this paper predicts extraction will fail and the milestone should stay at
   `structured_body` capture without the replay loop.
5. **Read DeCoMi before building anything.** Its prompts, its FR list, and its four-stage split
   are free prior art, and its front-end already does decision→source-code citation.

**The 26-year-gap framing (§19) survives intact and is arguably strengthened.** The timeline said
code→DMN amounted to "one unrefereed preprint." Having now read it: it is one unrefereed
preprint, on 10 hand-built Java cases, with a professional-modeler gold standard of at most 19
rules, reporting 0% decision-rule F1 on three of its eight logic cases. **The gap is not closed.**

### 17e-ter. DeCoMi — THE ARTIFACT OBTAINED AND INSPECTED 2026-08-21, and its 0% is a floor not a ceiling

**What it actually is.** Not a document — an OSF dataset (van de Hoef, 2025), two files, fetched
through the OSF API rather than the JS-only web UI: `DeCoMi.zip` (5.4 MB, 1,088 entries) and
`Explanation.docx`. Layout: `back-end/src/core/prototype_steps/` (the four pipeline stages),
`back-end/src/api/` (Flask), `front-end/` (incl. an offline build), `data/case1…case10` (for each
case: the whole Java file, the decision-only Java, the gold-standard `.dmn` XML, the DRD JSON,
one decision-logic JSON per decision, and rendered PNGs), and `experiment/` — **945 files** of
queries and results across all four experiments and every iteration with GPT-4.1 and Gemini 2.5
Pro. `Explanation.docx` notes the original prototype **cannot be run** (the LLM versions were
discontinued); an offline demo of five models is hosted at `decomi-prototype.web.app`.

**The prompts, as built** (this is the free prior art the paper promised):

| Stage | Model / settings | Shape |
|---|---|---|
| 1. Decision identification | GPT-4.1 via AzureOpenAI, `temperature=0.6` | 4 chained turns: capability priming → identify decision-bearing functions (6 few-shots: **3 positive, 3 negative**) → extract caller/callee pairs **only where the callee influences the caller's return value** → group into models by call-chain connectivity. Function bodies are then cut out of the file by `source_code.find(name)` plus **brace counting** — no parser. |
| 2. DRD extraction | Gemini 2.5 Pro, `temperature=0`, JSON mime type | 2 turns, 4 numbered extraction rules: variable names **exactly as they appear**, only variables in a decision expression that directly influence a return, co-occurring variables grouped as one input, empty object if no DRD. |
| 3. Decision-table extraction | Gemini 2.5 Pro, `temperature=0` | **8 turns**: what does this code decide → what does the function return → which variables influence it → data types and possible values of each input/output → relevant values of the numeric variables → **[emit the JSON table]** (6 rules, 6 few-shots) → *is this table complete?* → what are the inputs. |
| 4. DMN XML | deterministic | JSON → DMN XML, rendered in the front end. |

**Two defects in the published code, and both land on the number this file has been quoting.**

1. **The chain-of-thought is discarded at the exact moment it is needed.** Every other LLM call
   in the prototype passes the accumulated conversation (`generate(query, …)`). The
   decision-table call alone passes the bare question (`generate(question, True)` in
   `extract_decision_logic_level.py`). So the five elicitation turns that establish the return
   value, the influencing variables, the data types and possible values, and the relevant
   numeric thresholds are computed — and then **not sent** with the request that produces the
   table. Stage 2 does not have this asymmetry, which argues bug rather than design.
2. **The completeness check is computed and thrown away.** Turn 7 asks, verbatim, "Is this table
   complete? (I.e., is there an applicable rule for each set of inputs?) If it is incomplete, can
   you find an example for which no rule would be applicable?" The function returns `answers[5]`;
   `answers[6]` is never read. A gap detector was prompted for, paid for, and dropped.

**What this does to Q3c.** The headline — 0% decision-rule F1 on three of eight logic cases,
collapsing past ~6 rules per table — **stands as a reported result but is not established as an
inherent ceiling**, because the strongest version of their own method was never run. Restate the
warning's *reason*, not its direction:

- **Keep** "design for rejecting most tables at first" and **keep** "do not promise DMN coverage
  of the corpus." Nothing here is evidence that extraction works.
- **Drop** any framing that treats 0% as the state of the art's limit. It is a floor produced by
  a defective harness, so **our own measurement on our own corpus is mandatory** and cannot be
  short-circuited by citing theirs in either direction — §17e-bis item 4 (measure the rule-count
  distribution per candidate table) is now the load-bearing action, not an optional one.
- **Steal defect 2 deliberately.** Asking the extractor "is this table complete, and give me an
  input for which no rule applies" is a per-table completeness probe that costs one turn. It sits
  naturally next to Q3g's zero-invariant and next to §17b's finding that DMN leaves the
  completeness algorithm to vendors.
- **Steal the negative few-shots.** Three of six examples in stages 1 and 3 are *non*-decisions
  (a constant block, a getter, a Swing file dialog) whose expected output is `{ }`. Our own
  extractor prompts have no negative exemplars, and false-positive suppression is exactly where
  §15's ~29%-precision problem bites.

**And one thing worth more than the prompts: `data/case1–10` is a ready-made regression fixture
set.** Ten Java files paired with professional-modeler gold-standard DMN XML, DRD JSON and
decision-logic JSON, five of which contain no decision logic at all. If any milestone here
produces decision tables, this is an off-the-shelf harness for it — already licensed for reuse,
already structured for scoring, and it costs nothing to run against. **Caveat that must travel
with it:** the gold standard was built by **one** modeler over three iterations on hand-picked
single-file Java of at most 19 rules, so it validates a floor, not enterprise readiness.

### 17f. The three named gaps — and one of them answers the no-oracle problem

The report names three unpublished compositions that look like real contributions:

1. **Path conditions → decision table rows.** The material already exists in the slicing
   literature; the pivot has never been published.
2. **SBVR-verbalizing what KDM already models.** ISO/IEC 19506 defines `TermUnit` /
   `FactUnit` / `RuleUnit` each "aligned with SBVR" and explicitly intended to be "later
   exported into a business rule modeling tool in the process known as application business
   rules mining." **The verbalization step has never been built, and no ADM business-rules
   RFP was ever issued.**
3. **DMN-vs-legacy equivalence testing — and this is the important one.** Every component
   exists and was verified: extract to **DMN XML** → **`ANALYZE_DECISION_TABLE`** for
   gaps/overlaps (which doubles as a "did we miss a branch?" signal) →
   **`COMPUTE_DECISION_TABLE_MCDC` + `MCDC2TCKGenerator`** to generate test cases → **replay
   the `inputNode` values against the legacy system and diff against `resultNode/expected`.**
   **The composition is unpublished.**

**Why (3) matters more than it looks.** Section 15 established that business-rule extraction
has **no oracle** — no benchmark, no ground truth, ~29% precision in the one honest
measurement. But for the **decision-logic subset** of the corpus (Calculation and much of
Policy), a DMN table is **executable**, so the legacy system itself becomes the oracle: you
generate MC/DC-covering inputs from the extracted table, run them through the legacy code,
and diff. That is a *mechanical, quantitative* fidelity measurement on a real system, with no
human annotation and no LLM in the scoring loop — which is precisely what SparseAlign's
"circular evaluation loop" warning says you otherwise cannot get.

It does not solve the general problem (validation rules and lifecycle rules are not decision
tables, and coverage is bounded by what you can drive), but **it converts an unmeasurable
claim into a measurable one for the subset where money and correctness usually live.** That
is a strong argument for Q3c's typed bodies being **DMN specifically** rather than an ad-hoc
table format — the executability *is* the point, not the notation aesthetics.

### 17g. Calibration and usable baselines

If LegacyLift targets SBVR Structured English or DMN for rules recovered from legacy code, it
is in **near-greenfield territory** — opportunity, but with no established evaluation
methodology, no benchmark, and no prior-art notation conventions to borrow.

**Nearest usable baselines:**
- **A-COBREX: recall 74.12% / precision 62.21% on 27 annotated COBOL programs.**
- **COBRAIN — B S Chiranjeevi & Chimalakonda, "LLM Vs Rule-Based… Extracting Business Rules
  from COBOL," EASE 2025, DOI 10.1145/3756681.3756982** — a head-to-head LLM-vs-rule-based
  empirical comparison. The single most directly useful empirical baseline found.
- **Pradhan, Malvade, Medicherla, Patwardhan (TCS Research), "LLM Driven Business Rule
  Extraction from Enterprise Applications," SANER 2026, DOI 10.1109/SANER67736.2026.00104.**
  ⚠️ Note: the same lab that produced the one SBVR paper is **not** framing its new LLM work
  as SBVR.
- **Reversa** (arXiv:2605.18684) outputs **Gherkin plus confidence-marked claims** —
  architecturally the closest thing to LegacyLift in the literature, notable for explicit
  confidence marking and "preservation of gaps for human validation." COBOL ATM → Go:
  "517 claims classified by an internal confidence index, 10 registered gaps, 53 Gherkin
  parity scenarios," though "final parity validation and cutover were not completed."
- **AgentModernize** (arXiv:2605.17535) uses a "Behavioral Specification Graph," not DMN or
  SBVR, and reports the finding most relevant to sequencing: "**the bottleneck is code
  generation, not extraction**." Also: "Implicit rules, edge-case handling, and cross-module
  constraints that keep production systems running are lost, and nobody notices until
  something fails in production."
- **IBM knowledge-graph work** (arXiv:2505.06885) — customizable-ontology knowledge graph
  over COBOL/PL-I/Assembler, same group as A-COBREX. Directly comparable to the fact-graph
  and Layer-0 architecture.
- **BREX** (arXiv:2505.18542) — 409 real business documents, 2,855 expert-annotated rules,
  30+ domains. From documents, not code, but its finding that "executable grounding serves as
  a superior inductive bias" (i.e. have the model generate pseudo-code) is a transferable
  prompting result.

**Vendors:** EvolveWare claims rule extraction with output framed as **user stories and
technical specifications** — no DMN claim. Trisotech and Camunda are DMN *authoring*
platforms with nothing on code extraction. IBM watsonx Code Assistant for Z could not be
checked (403). No Anthropic, Microsoft or AWS material on mainframe rule extraction was found
through these channels.

**Highest-value unresolved leads — four of six are now CLOSED (2026-08-21):**
~~(1) the van de Hoef SSRN paper~~ → **read in full, §17e-bis**; its successor lead, DeCoMi's
source and prompt set on OSF, is also **closed — downloaded and inspected, §17e-ter**.
~~(2) Semantic Designs (Baxter & Hendryx)~~ → **read in full, §18**; the TLS failure was worked
around and the KDM implication in the title turned out to be **wrong** — it is SBVR-based.
~~(3) Von Halle ch. 2~~ → **read, §17a-bis**; "mandatory constraint" is confirmed as the leaf term.
~~(4) SBVR Annex H~~ → **the premise was wrong twice, §17a-ter**: the RuleSpeak annex is **F**, not
H, and nothing was member-restricted.
**Still open, and both are optional — nothing in this plan is blocked on them:**
(5) Grohé, Corea, Delfmann, BPM Forum 2021, DOI 10.1007/978-3-030-85440-9_3 — the one published
survey of DMN verification tool support; (6) Sneed & Verhoef 2019,
DOI 10.1007/978-3-030-26574-8_14 — 6.4 MLOC COBOL case study, output notation unconfirmed.

## 18. Baxter & Hendryx (Semantic Designs, 2005) — READ IN FULL 2026-08-21

**What it is, and why the provenance is unusually good.** `semdesigns_brex.pdf` is a **30-slide
conference deck**, not a paper — "A Standards-Based Approach to Extracting Business Rules", by
**Ira Baxter** (CEO, Semantic Designs; architect of DMS, the compiler-grade program
transformation system) and **Stan Hendryx** (co-chairman of the OMG Business Modeling &
Integration Task Force and **co-submitter of SBVR**). So it is an SBVR co-author, standing next
to the most capable commercial static-analysis engine of its era, describing how to get business
rules out of legacy code. On this topic there is no better-placed pair of authors.

**Correction to the expectation this file recorded.** The title's "standards-based" was read here
as implying the KDM angle. It does not: the standard is **SBVR**. KDM appears exactly once, as an
intermediate model in the tool-chain diagram (slide 18). Adjust §1's KDM evidence accordingly —
this deck is not a KDM data point.

### 18a. The finding to cite — an independent 2005 corroboration of §15 and of TCAS II

Slide 9, "The Code only hints at Business Rules", verbatim:

> "Business meaning of the data and actions **is determined only at the system inputs and
> outputs**." · "**Business rules are usually not in the code.**" · "Information is **lost or
> tangled** when programmed." · "Partly in **organization context** of software." · "Requires
> **people** to recover (induce) this information using code clues." · "Automated extraction of
> business rules is often proposed." · "**Can at best be heuristic.**" · "Defects: **missing
> rules, incorrect rules**, …"

**Why this is the strongest version of that claim available to us.** §15 gets the no-oracle
result from academic measurement, and §13 gets it from Leveson's TCAS II. This is the same
conclusion from **the vendor with the commercial incentive to claim the opposite** — a
transformation-tools company saying, in its own sales deck, that automated business-rule
extraction "can at best be heuristic." Twenty years before our corpus, with full compiler-grade
analysis available to them. Use this one when a client asks why the plan will not promise
accuracy.

Note the deck's own framing of what tools are *for*: they extract **clues**, and a human induces
the rule. Every tool on their slide 16 list — test coverage, system-wide information flow, E-R
extraction, clone detection — feeds a business analyst; none of them emits a rule.

### 18b. Slide 5 — the six-item defect rubric Q3f's lint was missing

Baxter and Hendryx take a competing rule-extraction vendor's own published output (12 "rules"
from COBOL, reproduced on the slide) and annotate what is wrong with it. Their categories:

1. **Nonsensical rule** — e.g. "End of File Switch Is Equal To 1 Apply VALIDATE-PUR-MASTER Until
   End Of File Switch Is Equal To 1": loop mechanics rendered as a business rule.
2. **Program symbols are not business terms** — `PUR-ORD-QTY` is not vocabulary.
3. **Direct use of implementation technology is not business vocabulary or business rule** —
   they mark **7 of the 12** rules with this defect.
4. **Over-specification** — e.g. incrementing an error counter recorded as a rule.
5. **Failure to abstract a variable to a named business term** — "Inventory Cat Is Equal To 86".
6. **Duplicated (cloned) business terms implies independence when rules may be coupled** — two
   rules that repeat the same derived quantity are recorded as unrelated when they are not.

**This is a named, citable rubric for exactly the lint Q3f recommends**, and it is better than
one we would invent because it was derived from real machine-extracted output rather than from
first principles. Two observations for the implementation:

- Items 2, 3 and 5 are **leakage** smells and map onto 29148 *Appropriate* / *Implementation
  Free* (§7) and onto Femmer's smells (§7-ter) — three independent sources now converge on the
  same lint, which is a good sign it is worth enforcing.
- Items 1, 4 and 6 are **not** leakage. Item 1 is "this is not a rule at all" (a disposition
  question — Q3g), item 4 is granularity, and **item 6 is a coupling smell our candidate field
  list has no field for at all.** If two GRs recompute the same derived quantity, nothing in the
  current design records that they move together. Worth raising when Q3g and the field list are
  revisited; not enough to warrant its own frontier question yet.

### 18c. Slide 6 — enforcement is separate from the rule, and there is a third level under Q3a

Verbatim: "**Enforcement of a business rule is separate from the rule itself** — partly enforced
by daily, manual business activities, partly enforced by IT systems — may span multiple
systems — **system requirements are rules about enforcing business rules in the system.**"

Q3a splits `as_built` (what the code does) from `statement` (what is required). This deck adds a
level *above* both: the **business rule** exists independently of any system, and what our
extractor recovers is at best the **system requirement that enforces part of it**. Consequences:

- It is a second, independent argument for Q3a's split — and a caution that even a clean
  `statement` field is a *system* requirement, not the business rule. Q3d's "who is the subject
  of shall" is the same question wearing a different hat: if the subject is a system component,
  the record is a system requirement by construction.
- It supports Q3i's `enforcement_level` living on the record (a business rule enforced partly by
  manual process is not `strict` in the system), and it explains **why** `enforcement_level` is
  not derivable from code: the manual half of the enforcement is not in the repository. That
  makes it an SME-filled field — the same argument Q3j makes for `rationale` and `fit_criterion`.
- Their definition of a business rule is worth recording as a filter: "an **actionable business
  directive** whose purpose is to advise or inform and that introduces an **obligation** that
  covers conduct, action, practice or procedure, **or** a **necessity** intended as a
  **definitional criterion**." That is the deontic/alethic split of §17a, in one sentence, from
  an SBVR co-submitter — and it is a usable "is this even a rule?" test for Q3g's disposition.

### 18d. Slides 7 and 10 — vocabulary before rules (this is what motivated Q3l)

"Business rules build on business **fact types**. Business fact types build on business
**terms**. … To get business rules: **first get the business vocabulary, then build rules using
vocabulary** — interleave activities in practice." And: vocabulary and rules "are **independent
of implementation** … not dependent on any business process, information system, or record
keeping system."

This is the **fourth** independent convergence on term / fact / rule — Von Halle 2001 (§17a-bis),
this deck 2005, SBVR 2008, KDM 2012 — and the only one that states the *ordering* as a method:
the vocabulary is recovered first and the rules are written in it. **Our design has no vocabulary
layer at all**; GRs reference code symbols directly, which is precisely defect 2/5 of §18b.
That gap is now **Q3l** in the frontier.

Their named clues for recovering vocabulary are concrete and worth checking against what Layer 0
already gives us:

| Clue (slide 10) | Do we have it? |
|---|---|
| Program symbolic names and types — data, functions, arguments | **yes** — `symbols`, `symbol_facts` |
| System-wide data flows and visibility of variables; equivalences of code concepts | **partly** — call/reference edges, `uses_table`; no dataflow |
| **Labels on input/output forms and in report-generator programs** | **no — not mined at all** |
| Program comments | available in chunk text, not extracted as a signal |

The I/O-label clue is the interesting one: form captions and report headings are business
vocabulary written *by* the business, sitting in the repository, and nothing in our pipeline
looks at them. Cheap to add and directly relevant to Q3d (naming the subject) and Q3l.

### 18e. Slides 11 and 13 — they specified our authoring loop in 2005, and composed a decision table by hand

Slide 11's loop: the analyst browses code with analysis tooling → selects a fragment →
"**selecting a fragment selects the corresponding business terms**" → the analyst writes the rule
in SBVR → "**written rule is checked for syntax and proper use of business terms**" → "**written
rule is tied to program fragment for traceability**."

Read against the frontier, that is: Q3l's vocabulary layer, Q3b's validator (and note *both*
halves — syntax **and** proper use of terms, which is only checkable if Q3l exists), our
citations, and Q5's human-in-the-loop lifecycle. The design we are converging on was specified
two decades ago; what is new is that an LLM can draft the rule the analyst would have written.

Slide 13 does Q3c by hand: a COBOL fragment → four individual rules ("if current balance is
$100.00 or more then current payment is 10% of current balance", …) → one **composed rule
(decision table)** over the same four. Two things to take from it — the composition step is
explicitly a *human* one, and the individual-rule form and the table form are both retained
rather than one replacing the other. That is an argument for Q3c(b): the `structured_body` is an
*additional* representation attached to rules that keep their sentence form, not a substitute
record type.

### 18f. One capability we have no notion of — test coverage as feature location

Slide 21: instrument the program, run a test case that exercises the feature of interest, and
display the executed blocks — "**code exercised by a test case is related to the feature
exercised by that test case**"; non-executed code is "likely to be dead or flawed". They are
repurposing a QA tool as a **feature-location** mechanism.

Our entire pipeline is static. This is a runtime evidence source that would tie a GR to code with
observational rather than inferential support — the same family as the Daikon/Clousot note in
§20(4), and subject to the same precondition (a runnable build with an exercising workload),
which our engagements usually lack. Recorded as a capability, not a recommendation.

## 19. What notation does the field actually use? — "code snippets or graph slices"

> Read directly from the primary PDF on disk, not via an agent summary. The
> business-rule-extraction agent's main report was lost twice, but it left its downloaded
> artifacts in the session scratchpad; the findings below are from my own reading of them.

### The citable answer

**Normantas, K. & Vasilecas, O., "A Systematic Review of Methods for Business Knowledge
Extraction from Existing Software Systems," *Baltic Journal of Modern Computing* 1(1-2),
2013, pp. 29-51.** A systematic literature review: 7 digital libraries, **24 papers**,
classified on four dimensions — knowledge kind, extraction technique, input artefacts, and
**"extracted knowledge representation forms."** Breakdown: 10 studies on business rules, 6 on
rules plus business vocabulary, 6 on business processes, 2 on both rules and processes.

**§6, verbatim — the finding that matters most to this plan:**

> "**We were surprised that very few methods consider widely accepted forms for business
> rules representation (such as templates, decision tables, etc.). Most of the reviewed
> studies suggest using either code snippets, or graph slices as the output representation,
> though such representation form is not acceptable solution when extracted rules must be
> evaluated with business analysts or stakeholders.** In our opinion, this issue should be
> investigated in the further research."

That is a peer-reviewed SLR stating, as its surprise finding, that **the field's output
notation is unfit for business validation** — and nominating it as future work. Thirteen
years later the DMN thread found the gap still open (one 2026 preprint for code→DMN, nothing
at all for code→decision tables).

**Note the asymmetry it draws immediately afterward, which sharpens the point:**

> "However, this issue is irrelevant for the output representation of extracted business
> processes. The most of reviewed studies consider representing business processes using
> models defined either with Business Process Modelling Notation (BPMN), or other notation
> supported by business process management tools."

So **business *processes* recovered from code do get a standard, business-readable notation.
Business *rules* do not.** The gap is specific to rules, which is exactly our scope.

### Other findings from the same SLR, all verbatim

**The canonical pipeline** — and it is the pipeline `/modernize-extract-rules` already
implements: "most of them concern the following general procedure for knowledge extraction:
**gathering initial information, extracting candidate rules, refining candidates, and
transforming to the output representation form**." Note "**candidate** rules" — the field's
own vocabulary already concedes that extraction yields candidates, not rules.

**Techniques:** "The most common techniques for business rules extraction are **program
slicing, pattern matching, and transformations**." Slicing methods use control-flow graphs,
call graphs or program-dependence graphs as intermediate representation; pattern-matching
methods either match directly in code or invent a custom meta-model.

**Standards adoption is minimal:** "**a minority of methods rely on standards (such as SBVR,
BPMN, UML/OCL, KDM)** for producing intermediate and output representation of extracted
knowledge." And: "**Only several methods use standard based (i.e. Knowledge Discovery
Meta-model) intermediate representation.**"

**Input sources are narrow:** "There are very few methods that consider knowledge extraction
from software artefacts other than source code, for instance, resource (**web pages, forms,
reports**) definitions or configurations. Though, within contemporary software systems, these
artefacts may contain much valuable information, including business vocabulary and rules.
This could be explained by the fact that the most of business rules extraction methods
considers legacy software written COBOL." — *Directly relevant: our corpus is Java/C#/T-SQL
with JSPs, forms and reports, i.e. precisely the artefact classes the field under-serves.*

**Maturity:** "the research field is still **immature** and requires more comprehensive
research"; "only very few of the methods were evaluated in industrial case studies on large
enterprise software systems"; and "there is an absence of rigorous and formal specifications
of algorithms that would allow the method to be reproduced in order to evaluate and validate
its characteristics: complexity, performance time, and accuracy of the results."

### Formal specification recovery is a disjoint literature — verified by grep

The Gannod & Cheng corpus (Michigan State; predicate logic, Larch/LCL interface
specifications, the **AUTOSPEC** tool, **AMMOS**) was checked directly: **`grep -c -i
business` returns 0 across all 20 extracted files, dissertation included.** `policy`
likewise 0. So the formal-methods reverse-engineering tradition and the business-rule
extraction tradition **never mention each other's subject matter.**

Two pieces of vocabulary from it are worth adopting anyway, both verbatim:
- **"as-built specifications"** — a better term than "recovered requirements" for the
  descriptive half of a GR (Q3a's `observed_behavior`).
- **"implementation bias"** — the formal-methods name for exactly the Q3f problem, and for
  what Chaparro et al. measured at 36%.

Also documented there: abstraction is "**exponential in size with respect to the input
program**", "AUTOSPEC is fully automated" but the overall approach is "**not completely
realizable as of yet**."

Attribution correction: the COBOL→Z line is **Lano, Breuer & Haughton** — Péter Breuer is
central to it and is routinely omitted.

### The NIST formal-methods survey — reverse engineering was the norm, and its open question is still open

NIST/NASA survey, two volumes (DTIC ADA273362, ADA272179), read directly. Verbatim findings:

- Finding #3 concerns "**re-engineering existing systems**".
- **Darlington** — "the Darlington project was **generally a reverse engineering exercise**",
  costing "**$4 million (Canadian) … approximately 30 individuals**", and "**required for
  licensing purposes**".
- **IBM CICS** — "**re-engineered existing code and documentation and used the ensuing Z
  specifications**". Precise figures, in the citable form: **268,000 lines of new and
  modified code, of which Z was used to specify some 37,000 lines fully and another 11,000
  lines partially.**
- **TBACS** — "a **reverse engineering task** in that existing source code was analyzed and
  then specified using FDM"; **300 lines of FDM against 2,500 lines of C**.
- **SACEM** — "**reverse-engineered the specification using B with manual proof** linking the
  new specification and the old assertions"; 315,000 person-hours.

**And the open question NIST left unanswered, which is still unanswered:**

> "**How does one systematically extract the various state machine components, e.g.,
> preconditions and constraints[?]**"

Thirty-plus years on, that is the same question the slicing literature answers with slices
and the LLM literature answers with prose. It is our question too.

### The gap is 26 years old and the business-rules community named it themselves

**The GUIDE Business Rules Project** — the foundational business-rules effort behind the
Business Rules Group — listed **four purposes** in its 2000 paper, the **third** of which is,
verbatim:

> "**To provide a rigorous basis for reverse engineering business rules from existing
> systems.**"

The same paper then concedes that **only the first two objectives were met**, and that for the
reverse-engineering and greenfield objectives "**much work remains to be done in these
areas.**"

So the timeline of this specific gap, from three independent sources:

| Year | Source | Statement |
|---|---|---|
| **2000** | GUIDE Business Rules Project / Business Rules Group | reverse-engineering rules from existing systems is an explicit project objective — and **unmet**; "much work remains to be done" |
| **2001** | Von Halle, *Business Rules Applied* ch. 2 (verified from the book, §17a-bis) | "**Unfortunately, there is no standard rule specification language.** There are various rule languages proposed as part of their modeling approaches" |
| **2013** | Normantas & Vasilecas SLR (24 papers) | output is "code snippets, or graph slices", which "is not acceptable solution when extracted rules must be evaluated with business analysts or stakeholders" |
| **2026** | this survey | code -> DMN: one unrefereed SSRN preprint. code -> decision tables: nothing. KDM's SBVR verbalization step: never built. |

**Twenty-six years, three independent acknowledgements, still open.** That is the single
best framing for why this plan is worth doing, and every link in it is citable.

### Consequence for the plan

This is the **strongest positioning statement available**, and it is peer-reviewed rather
than self-asserted: the acknowledged open problem in the literature is that recovered rules
come out as code snippets and graph slices, which **"is not acceptable solution when extracted
rules must be evaluated with business analysts or stakeholders."**

A GR store whose core field is a **business-readable normative statement** (Q3, whichever
notation) with **citations back to code** (the KDM `implementation` idea) and a
**human review lifecycle** (Q5) is a direct answer to that stated gap. That is a far better
claim than "our extraction is more accurate" — which §15 established nobody can substantiate.

### Artifacts retained on disk

The session scratchpad holds primary PDFs and text extracts worth mining rather than
re-fetching: `normantas_slr.pdf/.txt` (this SLR), `semdesigns_brex.pdf` (Baxter & Hendryx,
Semantic Designs — the "standards-based approach to extracting business rules" paper flagged
elsewhere as a top unresolved lead, **still unread**), `cosentino_wcre2013.pdf`,
`hatano2016.pdf/.txt`, `chikofsky.pdf`, `gprofit.pdf`, `DTIC_ADA273362/272179` (NIST survey),
20 Gannod & Cheng extracts (`g_*.txt`, `c_*.txt`), Martin Ward's 14 papers under `ward/`, and
the SCR/NRL corpus (`1996heitmeyer-*`, `1998*`, `1999*`, `ADA*`). **Note: scratchpad contents
are session-scoped — copy anything needed for the ExecPlan into the repo before relying on
it.**

## 20. Consequences for the design (my reading, for the user to accept or reject)

1. **Cite KDM §20 as the standards grounding for the GR schema.** `RuleUnit` /
   `FactUnit` / `TermUnit` / `BehaviorUnit` / `ScenarioUnit` with an `implementation`
   back-pointer to code is an ISO-standardized shape that our rule-card-plus-citations
   design already approximates. We are not inventing; we are implementing the half ADM
   explicitly left to "a difficult value-added knowledge discovery process." That is a
   strong story for a client deliverable and costs nothing to adopt as vocabulary.
2. **Q3a's observed/intended split has three independent precedents:** Feathers'
   actual-vs-supposed distinction plus "mark it as suspicious"; KAOS's
   prescriptive-requirement vs descriptive-domain-property split (and DomPre/DomPost vs
   ReqPre/ReqPost); and Savoia's structural separation of characterization from
   specification tests. This strengthens the recommendation considerably.
3. **Add `requirement` vs `expectation`** (KAOS) as a dimension: is this something the
   system-to-be must enforce, or something it assumes of its environment? Mined rules
   contain both and currently conflate them.
4. **Invariants are a legitimate third body type** alongside decision tables and state
   transitions — with the unique property that an invariant can be **checked against
   legacy production data**, not just legacy code. Daikon/Clousot prove invariant *inference*
   from existing code is real, though both need something we usually lack (a runnable build
   with an exercising workload, or at minimum bytecode).
5. **Drop OCL** from consideration entirely. **Do not adopt KAOS or i\* as the notation** —
   both have dead-or-dying tooling and neither has a live code-recovery practice — but
   **do steal their concepts** (obstacle/suspicion, requirement-vs-expectation,
   domain-invariant-vs-hypothesis) as GR *fields*.
6. **If a client needs an SDO-backed citation**, the available ones are ISO/IEC 19506
   (KDM, for the recovered-knowledge model), ITU-T Z.151 (GRL, for goals), and
   ISO/IEC/IEEE 29148 (for requirement quality characteristics). EARS, SBVR Structured
   English, Volere and iStar 2.0 are **not** SDO standards. (SBVR is an **OMG** specification —
   not an SDO standard, but freely redistributable and quotable, which 29148 is not.)
7. **The validator is two validators, keyed on `rule_class`.** SBVR Annex F.1.1 (§17a-ter) gives
   operative and structural rules disjoint keyword sets, so Q3b's `pattern` enum has to branch on
   Q3i's `rule_class`. Two cross-field checks come free with it: `should` may replace `must` only
   when the enforcement level is consistent with the sense of `should`, and `may` must mean
   "permitted to", never "might".
8. **Q3f's lint should implement Baxter & Hendryx slide 5 (§18b), not a rubric we invent** — six
   named defect categories derived from real machine-extracted output, three of which (symbols
   as terms, implementation technology as vocabulary, unabstracted variables) already converge
   with 29148 *Appropriate* and Femmer's smells.
9. **The plan's honest claim gained its best citation.** Baxter (DMS — compiler-grade analysis)
   and Hendryx (SBVR co-submitter) wrote in 2005 that automated business-rule extraction "**can
   at best be heuristic**", with "missing rules, incorrect rules" as the expected defects, because
   "business rules are usually not in the code." A vendor conceding this against its own interest
   is the strongest form of the §15 argument, and it is the one to put in front of a client.



# NORMATIVE SPEC-1 — Requirement Notation (SETTLED 2026-08-21)

> **Status: SETTLED.** The user approved the 29148/SBVR composition on 2026-08-21 and directed
> that it be "concretely defined with no ambiguity so an LLM can act upon it in the future."
> **This section is that definition. It is normative for this plan and for the ExecPlan that
> follows it.** Everything here is either a verbatim rule from a source read in this session or
> a decision recorded as such. **Do not re-derive it, do not re-litigate it, and do not
> paraphrase it into an implementation — implement these strings and these IDs literally.**
>
> **UPDATE 2026-08-24 — nothing in SPEC-1 is open any more.** Q3b's remaining half (whether the
> validator blocks, warns, or does not exist) was answered **(a) enforced**. **SPEC-1 stands
> exactly as written, unamended:** `ERROR` blocks the `draft` -> `approved` transition (§S1.9) and
> nothing gates `draft`. Do not downgrade any `ERROR` to `WARN`. The degrade-to-warn-only path
> described in earlier drafts is dead and must not be implemented.
>
> ⚠️ **UPDATE 2026-08-26 — SPEC-1 is no longer unamended. See [§S1.12 Amendment log](#s112-amendment-log).**
> **Four** amendments stand (`V-STY-03`'s rubric scope, `V-VAG-09`'s seed list, the sites of
> `V-VAG-04`/`V-SING-01`, and `V-VAG-03`'s site), each closing a place where SPEC-1 contradicted
> itself and none changing the twenty-eight checks or their severities. This line said "two" until
> 2026-09-09 and was stale from A3 onward; §S1.12's table, not this banner, is the count. The "stands exactly as written, unamended" sentence above is preserved as the record
> of what was true on 2026-08-24; §S1.12 is authoritative for what is true now.

## S1.0 Why this section exists (the collision it resolves)

Q3b recommended implementing **ISO/IEC/IEEE 29148:2018**. §17a-ter then established that SBVR
gives **operative** (behavioral) and **structural** (definitional) rules *disjoint* modal keyword
sets. Those two sources **disagree on four of five modal keywords** — 29148 cl. 5.2.4 says to
avoid `must`, to avoid negative requirements like `shall not`, that `should` statements "are not
requirements", and (cl. 5.2.7, final line) to "**include definitions as declarative statements,
not requirements**" — while SBVR/RuleSpeak makes `must`, `must not`, a conditional `should`, and
first-class definitional rules the core of the notation.

**Root cause:** 29148 is a *system-requirements* standard with no concept of a definitional rule;
SBVR is a *business-rules* standard where definitional rules are half the taxonomy. Our records
are business rules.

**The resolution, and the escape hatch that makes it legitimate.** 29148 cl. 5.2.5 *Conforming*
requires conformance to "**an** approved standard template and style for writing requirements" —
not to Figure 1 specifically. **SPEC-1 is that approved template.** So we satisfy *Conforming*
while taking the modal verb from SBVR. The four deviations from cl. 5.2.4 are enumerated in
§S1.8 and must be reproduced in any client deliverable that claims 29148 alignment.

## S1.1 Precedence — which source governs which aspect

Apply in this order. Where two sources speak to the same aspect, the row below is decisive.

| # | Aspect | Governing source | Where verified |
|---|---|---|---|
| 1 | Modal keyword, and its selection by rule class | **SBVR v1.0 Annex F.1.1 + p. 345** | §17a-ter |
| 2 | Sentence slot skeleton | **29148 cl. 5.2.4 / Figure 1** | §7 |
| 3 | Named subject is mandatory | **29148 cl. 5.2.4** | §7-bis |
| 4 | Vague and general terms | **29148 cl. 5.2.7** (nine classes) | §S1.6, §7-bis |
| 5 | One rule per statement | **29148 cl. 5.2.5 *Singular*** | §S1.6 |
| 6 | Template conformance is required at all | **29148 cl. 5.2.5 *Conforming*** — satisfied **by SPEC-1** | §S1.0 |
| 7 | Record attributes | **29148 cl. 5.2.8** | §7-bis |
| 8 | Enforcement level values, and that they attach to behavioral rules only | **SBVR cl. 12.1.3, cl. 12.6.12** | §17a-ter |
| 9 | Rule vs advice | **SBVR cl. 12.1.4** | §17a-ter |

**Conflict rule (normative):** where 29148 cl. 5.2.4's *verb conventions* conflict with row 1,
**row 1 wins**, and the conflict must be one of the enumerated deviations D1–D6 (§S1.8). A
conflict that is *not* in D1–D6 is a defect in this spec — stop and escalate; do not resolve it
locally.

## S1.2 `rule_class` — the deterministic decision procedure

`rule_class` is the primary discriminator: it selects the keyword set (§S1.3), the pattern set
(§S1.4), and whether `enforcement_level` is legal (§S1.7). It must be decided **before** the
statement is written.

**SBVR's own definitions** (cl. 12.1, verbatim): a `structural rule` is a "rule that is a claim of
**necessity**" whose restriction of freedom is "built-in (i.e., 'structural' or 'by definition')";
an `operative business rule` is a "business rule that is a claim of **obligation**", "directly
enforceable", which "people can still potentially **violate or ignore**". Stated Necessity: "**No
operative business rule is a structural business rule.**" The two values are disjoint and
exhaustive.

**The problem with using that definition directly:** the same fact can be phrased either way
(SBVR's own EU-Rent example appears both as "a rental **must** have a car group" and "each rental
**always** specifies exactly one car group"), so the philosophical test is not decidable by an
LLM without inventing an answer.

**Therefore the discriminator is observable in the cited code, not in the concept.** This is
decidable, it is evidence-bearing, and it matches SBVR's semantics exactly — violability is the
distinction, and a violation-handling path in the code is proof that violation is possible.

> **RULE-CLASS PROCEDURE (normative). Evaluate against the code cited by the GR, in order.**
>
> 1. Does the cited code contain a **violation-response path** — a runtime check whose failure
>    produces a rejection, thrown exception, error return, validation message, diagnostic,
>    compensating action, or audit/alert entry?
>    → **`rule_class = behavioral`.**
> 2. Otherwise, does the cited code **establish** a value or relationship with **no failure
>    path** — an assignment, computation, derivation, mapping, constant, or a schema/type/DDL
>    constraint with no application-level handler?
>    → **`rule_class = definitional`.**
> 3. **Both present** (a computation guarded by a validation): **`behavioral` wins.** The
>    violation-response path is decisive. Record the derivation half as a separate GR if it is
>    independently meaningful.
> 4. **Neither determinable** from the cited code: **`rule_class = NULL`**, and emit
>    `V-CLASS-01`. A NULL `rule_class` blocks `approved` (§S1.9). It must never be guessed.

**Expected correlation with `category`, as a WARN only — never as a substitute for the
procedure:** `Calculation` → usually `definitional`; `Validation` → usually `behavioral`. A
mismatch emits `V-CLASS-02` (WARN) and is often correct — a computation whose out-of-range result
is rejected is genuinely behavioral.

## S1.3 Modal keywords — exact strings, disjoint by rule class

**These are literal strings. Match them case-insensitively as whole words. No synonyms, no
inflections, no additions.**

| Modal position | `rule_class = behavioral` | `rule_class = definitional` |
|---|---|---|
| positive rule | `must` · `should` † | `always` |
| negative rule | `must not` · `should not` † | `never` · `not always` |
| restricted | `may ... only` · `may ... only if` | `can ... only` · `can ... only if` |
| **advice — NOT a rule** ‡ | `may` · `need not` | `sometimes` |

† `should` / `should not` are legal **only** under the condition in `V-KW-05`.
‡ An advice is **not a business rule** — SBVR cl. 12.1.4 states the Necessity "**No business rule
is an advice.**" A statement whose only keyword is an advice keyword must not be stored as a GR
with a `pattern`; see `V-KW-06`.

**Special-purpose `definitional` keywords** (SBVR p. 345; `always` is implicit in each, so these
carry no separate positive keyword):

| Keyword (literal) | Use for |
|---|---|
| `is to be computed as` | computation — a value produced by a formula |
| `is to be considered` | derivation or inference — a classification or status concluded from other facts |
| `is to be fixed at` | establishing a constant |

⚠️ **`is by definition` is NOT a keyword.** It was asserted earlier in this file, refuted, and
the refutation is confirmed against Annex F. The derivation keyword is `is to be considered`.

## S1.4 `pattern` — the closed enum and the exact templates

`pattern` is a **NOT NULL** enum on every GR whose `disposition` makes it a rule. Its permitted
values are partitioned by `rule_class`; a value from the wrong partition is `V-KW-02`.

**Slot names** are 29148 Figure 1's: `[Condition] [Subject] [Action] [Object] [ConstraintOfAction]`.

**`rule_class = behavioral`**

| `pattern` | Template | Example |
|---|---|---|
| `B-COND` | `[Condition], [Subject] must [Action] [Object] [ConstraintOfAction]` | *When the purchase order status is Open, the Order Service must recalculate the quantity due within the same transaction.* |
| `B-UNCOND` | `[Subject] must [Action] [Object] [ConstraintOfAction]` | *The Order Service must record a vendor number on every purchase order.* |
| `B-PROHIB` | `[Condition], [Subject] must not [Action] [Object]` | *When the vendor number is absent, the Order Service must not accept the purchase order.* |
| `B-RESTRICT` | `[Subject] may [Action] [Object] only if [Condition]` | *A branch manager may grant a spot discount only if the rental is open.* |

**`rule_class = definitional`**

| `pattern` | Template | Example |
|---|---|---|
| `D-NEC` | `[Subject] always [Action] [Object]` | *A rental always specifies exactly one car group.* |
| `D-IMPOSS` | `[Subject] never [Action] [Object]` | *A closed purchase order never carries an open balance.* |
| `D-RESTRICT` | `[Subject] can [Action] [Object] only if [Condition]` | *An account balance can be negative only if the account is a credit account.* |
| `D-COMPUTE` | `[Subject] is to be computed as [Formula]` | *The interest owed is to be computed as (old balance + purchases − payments) × interest rate / 10000.* |
| `D-INFER` | `[Subject] is to be considered [Value] if [Condition]` | *An inventory item is to be considered category 87 if its purchase cost is more than 1000.00 and less than 5000.00.* |
| `D-CONST` | `[Subject] is to be fixed at [Value]` | *The minimum payment allowed is to be fixed at 10.00.* |

**Slot rules carried from §7 — reproduce these, they are already-verified corrections:**

- **Slots are not independently nullable.** In the short construct `[Object]` is *absorbed into*
  `[Action]` ("must display pending customer invoices"), not omitted. A parser that treats the
  slots as five optional fields will mis-parse it.
- **`[ConstraintOfAction]` being empty is NOT a finding, and no check may be written for it.**
  29148's examples are performance-shaped; mined business rules are conditional and usually have
  no constraint of action. **This paragraph exists to stop a future implementer adding that
  check.** Where a quantitative constraint *is* present, that is the trigger to reach for Q3c's
  `formula` structured body instead of prose.
- **`D-COMPUTE` / `D-INFER` / `D-CONST` do not follow Figure 1's slot structure** — see D5.

## S1.5 `enforcement_level` — closed enum, behavioral only

Permitted values, in decreasing severity (SBVR cl. 12.1.3): `strict` · `deferred` ·
`pre-authorized` · `post-justified` · `override` · `guideline`.

| Value | SBVR's definition, verbatim |
|---|---|
| `strict` | "strictly enforced (If you violate the rule, you cannot escape the penalty.)" |
| `deferred` | "deferred enforcement (Strictly enforced, but enforcement may be delayed — e.g., waiting for resource with required skills.)" |
| `pre-authorized` | "pre-authorized override (Enforced, but exceptions allowed, with prior approval for actors with before-the-fact override authorization.)" |
| `post-justified` | "post-justified override (If not approved after the fact, you may be subject to sanction or other consequences.)" |
| `override` | "override with explanation (Comment must be provided when the violation occurs.)" |
| `guideline` | "guideline (suggested, but not enforced.)" |

**Constraints:**
- `enforcement_level` is **legal only when `rule_class = behavioral`** — `V-ENF-01`. Source: the
  fact type is literally `operative business rule has level of enforcement` (cl. 12.1.3), and cl.
  12.6.12's caption reads "… applies to an operative business rule **(only)**."
- It is **SME-filled, extractor-forbidden** — the manual half of enforcement is not in the
  repository (§18c), so it is not derivable from code. This is the same argument Q3j makes for
  `rationale` and `fit_criterion`; treat the empty field as review progress, not a defect.
- `guideline` is the **warn-don't-block tier** that Q3k identified as missing. It lives here, not
  in `category`.

⚠️ **Attribution constraint, mandatory in any deliverable:** these six values appear in SBVR
under an `Example:` caption ("An example set of levels of enforcement, **based on [BMM]**") and
SBVR §6 declares examples informative. Cite them as **an example set given by SBVR, derived from
BMM** — never as a normative SBVR enum.

## S1.6 The validator — numbered rules, exact tests, fixed severities

**Severity has exactly two values.** `ERROR` blocks the `draft → approved` transition (§S1.9).
`WARN` is recorded on the record and never blocks. **No rule may be added, removed, or have its
severity changed without amending SPEC-1.** IDs are stable and must be emitted with every finding.

### Class and keyword

| ID | Sev | Test |
|---|---|---|
| `V-CLASS-01` | ERROR | `rule_class IS NULL`. |
| `V-CLASS-02` | WARN | `category='Calculation' AND rule_class='behavioral'`, or `category='Validation' AND rule_class='definitional'`. Informational — often correct. |
| `V-KW-01` | ERROR | `statement` contains **no** keyword from its `rule_class`'s set (§S1.3). |
| `V-KW-02` | ERROR | `statement` contains a keyword belonging to the **other** class's set, **or** `pattern` is from the other class's partition. *This is the headline check the disjointness buys.* |
| `V-KW-03` | ERROR | `statement` contains `shall`, `shall not`, or `will` as a modal verb. These are 29148 verbs that SPEC-1 does not use (D1, D2). |
| `V-KW-04` | ERROR | More than one rule keyword present. (29148 cl. 5.2.5 *Singular*; independently SOPHIST's "one full verb per requirement sentence".) |
| `V-KW-05` | ERROR | `statement` uses `should` or `should not` **and** (`enforcement_level IS NULL` **or** `enforcement_level IN ('strict','deferred')`). Source: RuleSpeak usage rule 1 — `should` may replace `must` only when the rule has no enforcement level or one consistent with the English sense of `should`. |
| `V-KW-06` | ERROR | The only keyword is an **advice** keyword (`may` with no following `only`, `need not`, `sometimes`). SBVR cl. 12.1.4: "No business rule is an advice." Do not store as a rule — route to `disposition` (Q3g) as a non-rule observation. |
| `V-KW-07` | WARN | `may` appears without a following `only` in a context reading as possibility rather than permission. Source: RuleSpeak usage rule 2 — "`May' must be used in the sense of 'permitted to'. `May' must not be used in the sense of 'might'." Heuristic, hence WARN. |

### Slots

| ID | Sev | Test |
|---|---|---|
| `V-SLOT-01` | ERROR | No `[Subject]`. Source: 29148 cl. 5.2.4, "A requirement **shall state the subject** of the requirement." Feeds Q3d. |
| `V-SLOT-02` | ERROR | `[Subject]` is one of the literals `the system`, `the application`, `the software`, `the program`. Q3d rejects option (d) outright. |
| `V-SLOT-03` | ERROR | `pattern` requires a `[Condition]` (`B-COND`, `B-PROHIB`, `B-RESTRICT`, `D-RESTRICT`, `D-INFER`) and none is present. |
| — | **no check** | **`[ConstraintOfAction]` absence is deliberately unchecked.** See §S1.4. |

### Vagueness — 29148 cl. 5.2.7, nine classes verbatim

Seed terms are the standard's own examples; the lists are extensible, the **classes are not**.

| ID | Sev | Class and seed terms |
|---|---|---|
| `V-VAG-01` | ERROR | superlatives — `best`, `most` |
| `V-VAG-02` | ERROR | subjective language — `user friendly`, `easy to use`, `cost effective` |
| `V-VAG-03` | ERROR | vague pronouns — `it`, `this`, `that` |
| `V-VAG-04` | ERROR | ambiguous adverbs/adjectives — `almost always`, `significant`, `minimal` — **and** ambiguous logical statements — `or`, `and/or`. **Carve-out:** `or` is permitted inside `[Condition]` (cl. 5.2.5 *Singular* NOTE 2 permits multiple conditions) and is an ERROR inside `[Action]` or `[Object]`. |
| `V-VAG-05` | ERROR | open-ended, non-verifiable terms — `provide support`, `but not limited to`, `as a minimum`, `etc.` |
| `V-VAG-06` | ERROR | comparative phrases — `better than`, `higher quality` |
| `V-VAG-07` | ERROR | loopholes — `if possible`, `as appropriate`, `as applicable` |
| `V-VAG-08` | ERROR | totality terms — `all`, `always`, `never`, `every`. **CARVE-OUT, MANDATORY:** this rule **does not apply** to the *rule-keyword occurrence* of `always` or `never` in a `definitional` statement. It applies to every other occurrence. **Without this carve-out the validator rejects every well-formed definitional rule** (D6). |
| `V-VAG-09` | ERROR | incomplete references — a reference with no date/version, or not naming the applicable part. **Seed list, extensible like the other eight:** a token matching `ISO`, `IEEE`, `RFC`, `ANSI`, `NIST`, `CFR`, `the standard`, `the specification`, `the policy`, `the manual`, `the regulation`, `the agreement` with no adjacent number, date or part designator. The *class* — an unresolvable external reference — is closed; the seed terms are not |

### Singularity and style

| ID | Sev | Test |
|---|---|---|
| `V-SING-01` | ERROR | `and` joins two distinct actions inside `[Action]`. Conditions may be conjoined; actions may not. (cl. 5.2.5 *Singular*.) |
| `V-STY-01` | ERROR | Passive construction — `it is required that`, `it shall be possible to`, `is to be <verb>ed by`. **CARVE-OUT:** the three special-purpose definitional keywords (`is to be computed as`, `is to be considered`, `is to be fixed at`) are **exempt** — they are required passives (D5). Without this carve-out every computation rule fails. |
| `V-STY-02` | ERROR | `shall be able to` or `must be able to`. (29148 cl. 5.2.4.) |
| `V-STY-03` | WARN | Implementation leakage. Implement **items 2, 3 and 5 of the Baxter & Hendryx rubric** (§18b), not an invented list: (2) program symbols used as business terms, (3) implementation technology as vocabulary, (5) unabstracted variable instead of a named business term. These are the three §18b itself classifies as leakage, and the three that also satisfy 29148 *Appropriate* and Femmer's smells. **Rubric items 1, 4 and 6 are NOT this check** — see the note below. **CARVE-OUT, MANDATORY:** item 5 does **not** apply to the `[Value]` slot of `D-CONST` or `D-INFER`, which legitimately carry a literal — §S1.10 #3 is a conformant `D-INFER` containing *category 87* and *1000.00*, and a naive magic-number test fires on it. WARN because Q3f's premise (§13, TCAS II) is that leakage cannot be fully removed, only recorded. |

**Where rubric items 1, 4 and 6 went, so nobody re-adds them to `V-STY-03`.** §18b itself says
these three are **not** leakage, and one of them cannot be a validator finding under any reading:

- **Item 1** (nonsensical rule / loop mechanics rendered as a business rule) is *"this is not a rule
  at all"*, which §18b routes to **`disposition`** (Q3g). It is a human triage act, not a notation
  finding.
- **Item 4** (over-specification) is granularity. There is no field for it and no check; a reviewer
  splits or discards the rule.
- **Item 6** (cloned business terms implying independence where rules are coupled) is a relation
  **between two records**, and §S1.6's validator takes one record — `validate_statement(gr)`. It is
  structurally not expressible as a finding here. §18b already notes "our candidate field list has
  no field for it at all." It is a **Q3l vocabulary-layer candidate**, and the requirements plan
  notes that its drift-versus-clone matrix already computes most of the signal it needs.

### Enforcement

| ID | Sev | Test |
|---|---|---|
| `V-ENF-01` | ERROR | `enforcement_level IS NOT NULL AND rule_class = 'definitional'`. |
| `V-ENF-02` | ERROR | `enforcement_level` not in the §S1.5 six-value set. |
| `V-ENF-03` | WARN | `rule_class = 'behavioral' AND enforcement_level IS NULL`. Review-progress signal (Q3j), not a defect. |

## S1.7 Schema constraints implied by SPEC-1

Stated as constraints, not DDL — the physical store is Q4 and the migration mechanism is deferred
question 3.

1. `rule_class` — enum `('behavioral','definitional')`, nullable **only** in `draft`.
2. `pattern` — enum of the ten values in §S1.4, with a CHECK tying the partition to `rule_class`:
   `behavioral` → `B-*`, `definitional` → `D-*`.
3. `enforcement_level` — enum of the six §S1.5 values, with a CHECK that it is NULL whenever
   `rule_class = 'definitional'`.
4. `statement` — the normative sentence, conforming to the `pattern` template. Distinct from
   `as_built` (Q3a), which is descriptive, cited, and **not** validated by SPEC-1.
5. **SPEC-1 validates `statement` only.** `as_built` is deliberately exempt: it records what the
   code does, in whatever words fit, and forcing it into a normative template would destroy the
   very distinction Q3a exists to create.
6. Validator findings are stored per GR as `(rule_id, finding_id, severity, span)` so that
   `approved` can be gated by a single `NOT EXISTS (... severity='ERROR')`.

## S1.8 Deviation register — the six documented departures from 29148

**Any deliverable claiming 29148 alignment must reproduce this table.** A deviation not listed
here is a defect, not a decision.

| ID | Deviation | 29148 says | We do | Justification |
|---|---|---|---|---|
| **D1** | Obligation keyword | cl. 5.2.4: requirements use `shall`; "**it is best to avoid using the term `must`**" | `must` | SBVR Annex F.1.1 makes `must` *the* obligation keyword for business rules. cl. 5.2.5 *Conforming* requires "an approved standard template" — SPEC-1 is it. |
| **D2** | Prohibitions permitted | cl. 5.2.4: "use positive statements and **avoid negative requirements such as `shall not`**" | `must not` / `never` are first-class | Our corpus is dominated by rejection and validation logic. Rephrasing positively loses fidelity to the cited code and breaks Q3a's `as_built` correspondence. |
| **D3** | Definitional rules are rules | cl. 5.2.4: `is`/`are` mark "non-requirements, such as descriptive text"; cl. 5.2.7: "**Include definitions as declarative statements, not requirements**" | `definitional` is half the record set | SBVR cl. 12.1 and Von Halle's taxonomy both make them rules. Excluding them drops the entire Calculation / derivation / constant category — in our corpus, a large fraction of everything extractable. |
| **D4** | Conditional `should` | cl. 5.2.4: `should` marks preferences/goals — "**They are not requirements**" | `should` is a rule keyword when `V-KW-05` passes | RuleSpeak usage rule 1 ties `should` to `enforcement_level`, which is a sharper rule than 29148's blanket exclusion and is machine-checkable. |
| **D5** | Three templates ignore Figure 1's slots | cl. 5.2.4 Fig. 1 defines the slot skeleton; cl. 5.2.4 says "use active voice" | `D-COMPUTE`, `D-INFER`, `D-CONST` use SBVR's special-purpose forms, which are passive | Figure 1 has no computation construct. `V-STY-01` carries the matching carve-out. |
| **D6** | `always` / `never` permitted | cl. 5.2.7 bans totality terms including `always` and `never` | Permitted **as rule keywords in `definitional` statements only** | They are SBVR's structural keywords. `V-VAG-08` carries the carve-out; every other occurrence is still an ERROR. |

## S1.9 The gate

`draft → approved` requires **zero `ERROR` findings**. `WARN` findings never block and are carried
on the record. Nothing gates `draft` itself — a bad extraction must still land, because the data
is the point and §15 says extraction quality cannot be assumed.

Lifecycle states are Q5's; SPEC-1 assumes only that `draft` and `approved` exist and that the
transition between them is a place a check can run.

## S1.10 Worked examples — conformant and rejected

| # | Statement | Verdict |
|---|---|---|
| 1 | *When the vendor number is absent, the Order Service must not accept the purchase order.* | ✅ `behavioral` / `B-PROHIB`. Cited code raises a validation error → violation-response path → behavioral (§S1.2 step 1). |
| 2 | *The interest owed is to be computed as (old balance + purchases − payments) × interest rate / 10000.* | ✅ `definitional` / `D-COMPUTE`. Assignment, no failure path (step 2). Exempt from `V-STY-01` (D5). |
| 3 | *An inventory item is to be considered category 87 if its purchase cost is more than 1000.00 and less than 5000.00.* | ✅ `definitional` / `D-INFER`. |
| 4 | *A closed purchase order **never** carries an open balance.* | ✅ `definitional` / `D-IMPOSS`. `never` is exempt from `V-VAG-08` here (D6). |
| 5 | *The system shall validate the order.* | ❌ `V-KW-03` (`shall`), `V-SLOT-02` (`the system`), `V-VAG-03`-adjacent vagueness in `[Action]`. |
| 6 | *An order **always must** have a customer.* | ❌ `V-KW-02` — `always` is definitional, `must` is behavioral. **This is the error the disjointness exists to catch**, and it is the single most likely LLM output. |
| 7 | *The Order Service **should** reject the order.* with `enforcement_level` NULL | ❌ `V-KW-05`. Fix by setting an enforcement level consistent with `should` (`override` or `guideline`), or by using `must`. |
| 8 | *It is permitted that an account balance is negative.* | ❌ `V-KW-06` — an **advice**, not a rule (SBVR cl. 12.1.4). Route to `disposition`; do not assign a `pattern`. |
| 9 | *The Billing Service must recalculate the balance **and** notify the customer.* | ❌ `V-SING-01` — two actions. Split into two GRs. |
| 10 | *When PUR-ORD-QTY is greater than zero, the Order Service must set WS-QTY-DUE.* | ⚠️ `V-STY-03` (WARN) — rubric items 2 and 5: program symbols used as business terms. Lands, does not block; resolving it properly needs Q3l's vocabulary layer. |

## S1.11 Known consequences for existing data and open questions

1. **The 470/815 existing rules are never imported — SETTLED 2026-08-21, no migration.** They
   are Given/When/Then with **no modal keyword at all**, so `rule_class` is unrecoverable from
   their text and `V-CLASS-01` would fire on every one. Rather than import them as permanently
   un-approvable drafts, the user committed to **not migrating anything**: the store starts
   empty and the old corpora serve as the comparison baseline (`NORMATIVE SPEC-2`).
   **Consequence for SPEC-1: `rule_class IS NULL` is now an extraction failure, not an expected
   legacy state.** Do not write a migration path, and do not soften `V-CLASS-01` to accommodate
   imported data — there is none.
2. **RESOLVED 2026-08-24 — Q3d is answered, so `V-SLOT-01`/`V-SLOT-02` are now
   implementable.** The naming authority is **`file_domains`** (Layer-0 domain of the citing
   file), with an LLM-named fallback used only when the file is `unassigned` and **flagged** as
   such. `V-SLOT-01` checks absence; `V-SLOT-02` checks the banned literals; the provenance flag
   keeps derived subjects distinguishable from invented ones. *(Original text: they require a
   naming authority for the subject; until then they can detect absence but not correctness.)*
3. **RESOLVED 2026-08-24 — Q3l is answered: a `term`/`fact_type` vocabulary layer is adopted,
   sequenced as a later milestone** (GR tables → Q5 review loop → vocabulary). Rubric items 2, 3
   and 5 gain a resolution path once that layer is populated; **until then a code symbol remains
   the only referent and `V-STY-03` findings are expected**. ⚠️ **`V-STY-03` stays a `WARN` even
   after the vocabulary layer ships** — Q3f's TCAS II premise (leakage cannot be fully removed,
   only recorded) is independent of Q3l. Do not promote it to `ERROR`.
4. **RESOLVED 2026-08-24 — Q3k is answered and the enum is UNCHANGED.** `category` keeps
   `Calculation | Validation | Lifecycle | Policy`; it does **not** gain a `guideline` value (the
   advisory tier lives on `enforcement_level`, §S1.5, where SPEC-1 already put it), and
   `Lifecycle` is kept with a recorded basis (it is the category whose rules carry Q3c's
   `state_transition` body). **`V-CLASS-02` is the only rule that touches `category`, and it needs
   no change.** Optionally extend it with a `Lifecycle`↔`state_transition` correlation check —
   **WARN only**, never ERROR.
5. **SPEC-1 says nothing about `structured_body`** (Q3c). A `D-COMPUTE` statement and a `formula`
   structured body are complementary, not alternatives — §18e's slide 13 keeps both the sentence
   form and the composed table.

## S1.12 Amendment log

§S1.6 says no rule may be added, removed or have its severity changed without amending SPEC-1, and
the design history asserts in two places that "SPEC-1 now stands in full and unamended". That
sentence is no longer true, so the amendments are recorded here rather than left to be inferred.
**An amendment not in this table is a defect, not a decision** — the same rule §S1.8 applies to
deviations from 29148.

| # | Date | Amendment | Why it is an amendment and not an implementation note |
|---|---|---|---|
| **A1** | 2026-08-26 | `V-STY-03` rescoped from all six Baxter & Hendryx rubric items to **items 2, 3 and 5**, with items 1/4/6 routed explicitly (`disposition`, granularity, Q3l vocabulary layer). A mandatory carve-out added exempting the `[Value]` slot of `D-CONST`/`D-INFER` from item 5. | It changes the *test* of a numbered rule, which §S1.6 reserves to an amendment. It adds no rule, removes none, and re-severities none — the count stays twenty-eight and the `2/7/3/9/1/3/3` breakdown is unchanged. Raised as `PR-80`. **This is the reading three of §S1.6's own four cross-references already took**: §18b says items 1/4/6 are not leakage, §S1.10 #10 fires the check on "items 2 and 5", and §S1.11 item 3 names "items 2, 3 and 5". Only the check's own row said six, and its next sentence names three. Item 6 was additionally unbuildable in the validator's signature, being a relation between two records. |
| **A2** | 2026-08-26 | `V-VAG-09` gains a seed list, on the same "seed terms extensible, classes closed" convention as the other eight `V-VAG` classes. | The class had no operative test at all — "a reference" was never defined, so the check could not be written. Raised as `PR-80` alongside A1. |
| **A3** | 2026-08-28 | **`V-VAG-04`'s `or` prohibition and `V-SING-01`'s conjoined-action test have no site on `D-COMPUTE`, `D-CONST` and `D-INFER`, and are not evaluated on them.** Both checks are written against `[Action]`/`[Object]`, and §S1.4 states those three patterns "do not follow Figure 1's slot structure" — their post-keyword region is `[Formula]` or `[Value]`. Where `pattern` is NULL both checks still run, over the post-keyword region, with `[Condition]` located structurally so the `V-VAG-04` carve-out survives. | It changes **where** a numbered rule fires, which §S1.6 reserves to an amendment; it adds no rule, removes none and re-severities none, so the count stays twenty-eight and the `2/7/3/9/1/3/3` breakdown is unchanged. Raised as `PR-107`. **Same justification shape as A1: the amendment adopts the reading §S1.6's own cross-references already take.** §S1.4 says the three patterns are outside Figure 1, and §S1.10 #3 — *"An inventory item is to be considered category 87 if its purchase cost is more than 1000.00 **and** less than 5000.00"* — is marked ✅ conformant while containing an `and` in its post-keyword region and an `if [Condition]` that trails the keyword. Under the other reading that example carries two `ERROR`s (`V-SING-01`, `V-SLOT-03`) and can never be approved, which is the same self-contradiction the `V-VAG-08` carve-out was written to prevent. |
| **A4** | 2026-09-09 | **`V-VAG-03`'s site is the `[Subject]` slot, and it fires only when the subject *is* `it`, `this` or `that`.** Where no template locates `[Subject]` the check is not evaluated. | It changes **where** a numbered rule fires, which §S1.6 reserves to an amendment; it adds no rule, removes none and re-severities none, so the count stays twenty-eight and the `2/7/3/9/1/3/3` breakdown is unchanged. **Same justification shape as A1: only the seed-list reading says otherwise, and the check's own class name contradicts it.** §S1.6 names the class **vague pronouns**, but as a seed list over the whole statement it fires on words that are not pronouns at all -- `that` as a determiner (*that short name*) and as a relative pronoun (*types that do not allow physical volume*). Measured on the first real corpus (133 rules, 2026-09-09): **26 findings on 20% of the requirements, at a severity that blocks approval, and not one of the 26 was a pronoun lacking an antecedent in its own sentence** -- 21 were determiners or relative pronouns and 5 were object pronouns whose antecedent stood in the same clause. **The cost is declared rather than hidden:** a genuinely vague pronoun outside `[Subject]` (*The Order Service must reject it*) stops being flagged, and that example is kept as a test of the narrower site rather than deleted. §S1.10 #5 already declines to fire this check on a statement it calls only "`V-VAG-03`-adjacent", locating that vagueness in `[Action]`, so the spec never treated the seed list as the operative test. |

**Deliberately not amended, and recorded here so the asymmetry does not read as arbitrary.** This
plan carries **three declared refinements of `NORMATIVE SPEC-3`** — when `dedupe_key` is
recomputed, how a missing top-level part is encoded, and the `ch0:none` sentinel for a missing
element inside the tier-2 discriminator — and those are kept as ExecPlan Decision Log entries with
SPEC-3 left unedited. The two acts are different. The SPEC-3 three are the plan **choosing
differently** from a spec that is internally coherent; A1, A2 and A3 are the spec **contradicting
itself**, where the amendment adopts the reading its own cross-references already take. Departures
from a coherent spec belong in the departing document; corrections to an incoherent one belong
here.


# NORMATIVE SPEC-2 — Baseline Comparison (SETTLED 2026-08-21)

> **Status: SETTLED.** Consequence of the firm no-migration commitment. The two existing NNG rule
> corpora are **reference data, never input**. This section defines how the new feature's output
> is compared against them, concretely enough to execute without further design.
>
> **Read §S2.4 before reporting any number from this comparison.** The baselines are unvalidated
> LLM output. Overlap with them measures **agreement, not correctness**, and §15 (no oracle,
> ~29% precision) still governs every claim made from these numbers.

## S2.1 The baseline artifacts — exact paths, and they are not the same shape

System under comparison: **`customer.ple.nng.app`** (the NNG PLE application unit). The sibling
DB unit `customer.ple.nng.db.ETSPii` has **no** `BUSINESS_RULES.md` and is out of scope.

| Ref | Path (relative to repo root) | Rules | Card shape | Parse rule |
|---|---|---|---|---|
| **BASE-ORIG** | `repos/nng-app-legacylift-analysis/analysis-original/customer.ple.nng.app/BUSINESS_RULES.md` | **815** merged | `###` headings in a P0 section + a markdown **table** in `## Full rule catalog` | Two parsers needed — heading-cards *and* table rows (768 `\|` lines). Citation is a backticked path on the metadata line, or a table column. |
| **BASE-ENH** | `repos/nng-app-legacylift-analysis/analysis-semantic-search-enhanced/customer.ple.nng.app/BUSINESS_RULES.md` | **470** single run | `####` headings with a trailing `` `P0` `` code badge | One parser. Citations render as `[📄](path:start-end)`. |

**Neither file has `RULE-` ids** (`grep -c "RULE-"` = 0 in both), and the two runs use
structurally different cards **from each other**. Any comparison tooling must parse both shapes;
there is no shared format to normalize to up front.

**Three reference points, not two — match the comparison to the question:**

| Question | Compare against |
|---|---|
| Does the new feature beat the **unenhanced** pipeline, like for like? | BASE-ORIG's **full-system single run: 229 rules** (its Provenance table) |
| Does it beat the **current best single run**? | **BASE-ENH: 470** |
| Does it beat the **merged** corpus? | **BASE-ORIG: 815** (merged from full-system 229 + ple-persistence 197 + ple-web 389, deduped by `file:line` + name) |

⚠️ **Do not compare a single new run against 815.** 815 is a three-run merge; 470 and 229 are
single runs. Comparing a single run to a merge is the most likely way to produce a misleading
number from this exercise.

## S2.2 The join key — code location, because there are no ids

Since no id exists in either baseline, rules are matched by **where in the code they were found**:

    join_key = (normalized_repo_relative_path, start_line, end_line)

- Normalize path separators to `/` and strip any leading `./`.
- **Overlap tolerance:** two citations match if their line ranges **intersect at all** within the
  same file. Exact-range equality is too strict — the two baselines cite the same logic at
  different granularities (e.g. `:78-97` vs a wider method span).
- A rule with multiple citations matches if **any** citation intersects.
- Record both a **strict** count (identical ranges) and a **tolerant** count (intersecting). Report
  the tolerant one as the headline and the strict one as the floor.

## S2.3 The four buckets, and the dimensions worth reporting

For each pairing (NEW vs BASE-ENH, NEW vs BASE-ORIG), emit:

| Bucket | Meaning | **Correct interpretation** |
|---|---|---|
| **BOTH** | Same code location in both | Agreement. Not evidence of correctness — two runs of a similar pipeline agreeing is weak evidence. |
| **NEW-ONLY** | Location found only by the new feature | **Candidate discovery OR hallucination.** Requires reading the cited code to tell which. Never report as "rules gained". |
| **BASE-ONLY** | Location found only by a baseline | **Candidate regression OR a correctly-dropped false positive.** Never report as "rules lost". |
| **MOVED** | Same file, non-intersecting ranges | Usually granularity drift, not disagreement. Report separately so it does not inflate NEW-ONLY and BASE-ONLY. |

**Directly comparable dimensions** (both baselines carry them):

| Dimension | BASE-ORIG | BASE-ENH |
|---|---|---|
| Rule count | 815 (merged) / 229 (full-system run) | 470 |
| Priority split | 55 P0 · 614 P1 · 146 P2 | 61 P0 (verified on disk) |
| Category split | Validation 441 · Lifecycle 215 · Policy 101 · Calculation 58 | Validation 254 of 470 |
| SME questions | 173 | not separately totalled |
| Suspected defects | 20 | not separately totalled |
| Rejected candidates | 38 (see §S2.4) | not present |
| **Distinct files cited** | **327** | **148** |
| **Rules carrying `Parameters:`** | 49 (only the 55 P0 cards can) | **379** |

**Coverage breadth is a required reported dimension, not an optional one** — see §S2.6. Report
distinct-files-cited and the per-module split alongside rule counts; a run that raises rule count
while narrowing file coverage has regressed, and raw counts hide that completely.

⚠️ Category comparability depends on **Q3k**. If the enum changes, map new values back to the
four baseline values for the comparison and report the mapping; do not silently re-bucket.

**New-only capabilities — report as additions, never as a delta** (no baseline counterpart
exists, so there is nothing to compare): `rule_class`, `enforcement_level`, the
`as_built`/`statement` split, `structured_body`, `disposition` and its zero-invariant, the
deterministic data-flow block, and every SPEC-1 validator finding.

## S2.4 Interpretation rules — mandatory, and they constrain what may be claimed

1. **Neither baseline is ground truth.** Both are unvalidated LLM output over the same code. This
   comparison measures **change and agreement**, never accuracy. §15 stands: there is no oracle,
   no benchmark, and the one honest published precision figure is ~29%.
2. **A higher rule count is not a better result.** BASE-ORIG has 815 and BASE-ENH has 470 over the
   same system; the smaller set was judged the better run. Count is a description, not a score.
3. **The baselines disagree with each other, and that is the most useful thing about them.** Two
   runs over identical code produced sets differing by hundreds of rules. That is a **variance**
   signal, and it sets the bar: a new-vs-baseline delta smaller than the baseline-vs-baseline
   delta is within noise. **Compute BASE-ORIG vs BASE-ENH first and use it as the noise floor.**
   (Caveat: they differ in pipeline *and* in merge depth, so this is an upper bound on noise, not
   a clean variance measurement.)
4. **The 38 "rejected candidates" in BASE-ORIG are a weak negative set, not labels.** All 38 carry
   an **empty reason field**, and spot-checking shows several are **near-duplicates of accepted
   rules** rather than false positives — e.g. two DUNS entries both citing
   `LegalEntityStatusHistoryValidator.java:78-97`, a location that *also* appears on an accepted
   rule. Use them as a triage prompt ("did the new run re-emit these, and if so, why?"), never as
   ground-truth negatives.
5. **The baselines were not produced under uniform conditions.** BASE-ORIG contains at least one
   referee verdict whose stated reason is that the working directory **contained zero `.java`
   files** — the citation check ran without source access and rejected on unverifiability rather
   than on rule quality. Some baseline verdicts are environment artifacts. Do not treat BASE-ORIG's
   accept/reject decisions as judgments about the rules.
6. **BASE-ORIG's advantage is breadth of code covered, NOT card richness — measured 2026-08-24,
   and this corrects an earlier claim in this file.** See §S2.6 for the measurement. Card for
   card, **BASE-ENH is consistently the richer artifact**; BASE-ORIG reaches 2.2× as many files.
   Triage accordingly: a BASE-ONLY finding in `ple-web` or `ple-persistence` is a likely genuine
   coverage gap, while a BASE-ONLY finding elsewhere is more likely noise.
7. **Every headline number must state which reference point it used** (229, 470, or 815) and
   whether it is strict or tolerant matching (§S2.2). A number without both is not reportable.

## S2.5 What this comparison is for

It is a **change detector and a triage input** — the same shape as §17e-ter's finding that the
DMN replay loop detects bad extraction rather than validating good extraction. It tells us where
the new feature diverged from prior output so a human can look there. It does **not** tell us the
new output is right, and no deliverable may imply that it does.


## S2.6 Measured: where each baseline is actually stronger (2026-08-24)

**This section corrects an earlier claim in this file** that "the original run's cards are richer
in places" and that BASE-ORIG carries `**Parameters:**` content BASE-ENH dropped. **Both halves
of that are false**, and the correction matters because it inverts the triage advice that was
briefly written into §S2.4(6).

**How to reproduce these numbers** (no agent, no tooling beyond a script): parse BASE-ENH by
splitting on `^#### ` (470 cards). Parse BASE-ORIG in two passes — `^### ` headings inside the
`## P0 — Confirmed critical rules` section (55), plus markdown table rows matching
`^\| (P0\|P1\|P2) \|` anywhere in `## Full rule catalog` (760). 55 + 760 = 815, which is the
integrity check that the parse is correct. Extract citations with
`([A-Za-z0-9_\-./]+\.(?:java|jsp|xml|sql|properties|js))[:\s]*(\d+)(?:\s*-\s*(\d+))?` and
match per §S2.2. **Exclude** the `❓ Open SME questions`, `⚠️ Suspected defects` and
`Rejected candidates` sections from BASE-ORIG's rule set — they cite code but are not rules, and
including them inflates its coverage figures.

### Card richness — BASE-ENH wins, and not narrowly

| Field | BASE-ENH (470 cards) | BASE-ORIG P0 cards (55) | BASE-ORIG table rows (760) |
|---|---|---|---|
| Given / When / Then | 470 (100%) | 55 (100%) | 760 (100%), compressed into **one table cell** as `**G:** … **W:** … **T:** …` |
| `**Parameters:**` | **379 (81%)** | 49 (89%) | **0** |
| `**Edge cases:**` | **258 (55%)** | 25 (45%) | **0** |
| `**Confidence:**` | 470 (100%) | 55 (100%) | **0** |
| provenance (`_found by:_`) | 0 | 55 (100%) | present as a column |
| inline SME question | 0 | 17 (31%) | separate `❓ Open SME questions (173)` section |

**The decisive asymmetry: only 55 of BASE-ORIG's 815 rules (6.7%) are rich cards. The other
760 (93%) are table rows** with no parameters, no edge cases and no confidence. Median row is
639 characters against a median BASE-ENH card of 847. In absolute terms BASE-ENH carries
**379 parameterized rules to BASE-ORIG's 49** — nearly 8×.

Two paired examples at the same code location, both showing BASE-ENH ahead:

- `DateRangeSplitter.java` — BASE-ORIG gives 4 parameters and no edge cases. BASE-ENH gives the
  same 4 plus the insert/update routing rule (`systemAssignedKey` null-or-0), and **five** edge
  cases naming `equalsMinusDates`, `resetIdsForDateSplit`, and the `IllegalArgumentException`
  thrown on an unknown overlap type. BASE-ENH also cites a wider, more accurate span (`45-381`
  vs `143-352`).
- `LegalEntityService.java:505-582` (agent-designee edit) — identical citation. BASE-ORIG's
  parameter line reads "Editable fields: endDate + 10 capability flags"; **BASE-ENH names all
  ten flags**. ⚠️ The two also *disagree on priority* — BASE-ORIG P0, BASE-ENH P1 — a concrete
  instance of the §S2.4(3) noise floor.

### Coverage — BASE-ORIG wins, by 2.2×, and it is concentrated in two modules

Distinct source files cited from the rule sections: **BASE-ORIG 327, BASE-ENH 148.** Shared 108;
**orig-only 219**; enh-only 40.

| Layer (by citation count) | BASE-ORIG | BASE-ENH |
|---|---|---|
| web / Struts actions | **319** | 25 |
| model / persistence (DAO, `.hbm.xml`) | **238** | 65 |
| validator | 198 | **211** |
| service | 84 | **357** |

By module: `ple-web` **398 vs 43**, `ple-persistence` **186 vs 19** — while BASE-ENH leads
`ple-services` **357 vs 210** and is level on `ple-model`. **BASE-ENH went deeper into the
service/validator core; BASE-ORIG covered the web-action and persistence layers that BASE-ENH
barely touched.** The single most-cited orig-only file is
`ple-web/.../PointStatusHistoryAction.java` (16 citations, zero in BASE-ENH).

### Why — both causes are documented, and neither is "better extraction"

1. **BASE-ORIG's breadth was bought with targeted re-runs, not a better algorithm.** Its
   Provenance table records three runs: full-system **229**, `ple-persistence` **197**,
   `ple-web` **389** — "scoped deep-dives into under-covered modules". The two modules where it
   dominates are **exactly** the two that got a dedicated run. Its own single full-system run
   found 229 rules, against BASE-ENH's 470 in one run.
2. **BASE-ENH's narrowness is a budget artifact, stated in the file itself:** "extraction stopped
   at the `maxRounds=12` cap while still finding ~28 new rules/round — this catalog is a floor,
   not a complete enumeration."

So the two facts are consistent, not contradictory: **enhanced discovery is better per run;
scoped re-runs buy breadth that no single run reaches.**

### The design implication — this promotes Q5 from valuable to required

Q5 (lifecycle, and re-extraction as **merge-with-dedupe** rather than truncate-and-insert) has
been justified as the way human judgment accumulates. This measurement adds a second, harder
justification: **merge is also how coverage accumulates.** The only run in evidence that reached
the web and persistence layers did so by merging three scoped runs, and the best single run
stopped while still finding ~28 rules per round.

Two consequences to carry into the ExecPlan:

- The store must support **scoped runs** (a module/path filter) that merge into the same
  corpus, with dedupe on the §S2.2 join key. A design that only supports whole-system runs
  cannot reproduce BASE-ORIG's coverage at all.
- **Round-cap exhaustion must be recorded on the run, not just in prose.** BASE-ENH's floor
  caveat lives in a markdown sentence; in the store it belongs as run metadata
  (`rounds_run`, `cap_reached`, `new_rules_in_final_round`) so a coverage claim can never be
  read without it. This is the same discipline as Q3g's disposition zero-invariant — an
  auditable completeness statement rather than an accuracy claim.

# NORMATIVE SPEC-3 — Identity and Deduplication (SETTLED 2026-08-24)

**This section is normative and implementable as it stands.** It answers deferred question **D1**
(citation anchor / trace granularity) and supplies the identity substrate that **Q5**'s merge and
**Q6**'s semantic dedupe both stand on. Implement it literally.

**Governing rule, one sentence:** *each key answers exactly one question, and no key ever contains
a domain, a line number, or human-editable text.*

---

## S3.0 Why the existing id formats cannot be reused

Verified in code, 2026-08-24:

| Id | Formula | Where | Volatile on |
|---|---|---|---|
| Layer-0 chunk | `chunk:{relative_path}:{language}:{idx}:{sha256(chunk_text)[:12]}` | `chunking.py:142-145`, `:221-224`, `:294-297` | any edit inside the chunk; **`idx` is `enumerate(symbols)` (`chunking.py:116`) so inserting a symbol renumbers every later chunk in the file**; rename |
| Layer-0 symbol | `{language}:{relative_path}:{qualified_name}:{range.start_line}` | `extractors.py:1112-1115`, `:1662-1665` | **any line shift above the symbol — with zero content change**; rename |
| Layer-0 fact | `fact:{sym.id}:has_column:{col_name}:{line}` | `extractors.py:1689` | inherits the symbol id, plus its own line |
| fact-graph entity | `{prefix}:{domain}-{normalized_name}-{sha256(entity_type:qualified_name:file_path)[:12]}` | `SKILL.md:912-932` | **domain retag** (domain is in the id string, outside the hash); file move; extractor reclassification of `entity_type` |

**Reindex physically deletes and reinserts.** For a changed file, `store.py:392-417` runs
`DELETE FROM chunks WHERE relative_path = ?` plus `DELETE FROM symbol_refs / symbol_facts /
symbols WHERE file_id = ?`, and `PRAGMA foreign_keys=ON` (`store.py:181`) is set. So a GR table
holding a hard FK to `chunks(id)` or `symbols(id)` gets one of two outcomes on every reindex of a
touched file:

- **`ON DELETE CASCADE`** → the requirement row is **silently deleted**. A whitespace-only commit
  destroys signed-off SME work.
- **`ON DELETE SET NULL`** → the requirement survives but its trace is **silently nulled**, and
  "never had a citation" becomes indistinguishable from "lost it on reindex".

**Neither is acceptable under Q5.** This is the same root cause as `fact-graph-decision.md` §7
open question #6 and §5a.1 item 3 (*"Still true — and Layer 0 is actively worse"*).

### Two further fact-graph id findings, recorded 2026-08-24 (they bear on §S3.1's Layer-0 move)

Both were verified in `SKILL.md` and matter because putting `anchor_key` in Layer 0 re-keys the
fact-graph pack format, so whoever does that work will meet them.

1. **fact-graph relation and fact ids exclude file and line entirely, so they DEDUPLICATE
   co-occurring instances.** `generate_relation_id` hashes `relation_type:source_id:target_id`
   (`SKILL.md:1199-1203`) and `generate_fact_id` hashes `subject_id:predicate:object_value`
   (`SKILL.md:1732-1736`). Neither carries a location, so **two distinct call sites of the same
   type between the same pair of entities collapse to one id** — as do two facts with identical
   subject/predicate/object at different lines. That is deduplication *by design* and it is the
   right default for a graph, but it is the **opposite** of Layer 0, whose fact id embeds the line
   (`fact:{sym.id}:has_column:{col_name}:{line}`, `extractors.py:1689`). **Consequence for the
   pack-emitter shim:** emitting Layer-0 facts into a fact-graph-shaped pack is **lossy by
   construction** — many Layer-0 facts map onto one pack id. Decide deliberately whether the pack
   keeps the collapse (and reports the collapsed count) or the pack format gains a location
   discriminator. **Do not discover this during implementation.**

2. **`SKILL.md`'s own relation examples use an id format its generator cannot produce.** §2.4's
   entity example is correct (`"id": "cs:usermanagement-userservice-abc123"`, `SKILL.md:971`,
   matching `generate_entity_id`'s `{prefix}:{domain}-{name}-{hash}`), but §3.4's relation example
   references `"source_id": "class-userservice-xyz789"` and
   `"target_id": "interface-iuserservice-def456"` (`SKILL.md:1207-1208`) — a `class-` / `interface-`
   prefix shape that `prefix_map` never emits (both map to `cs`). So the documented relation
   examples cite entity ids in a format that cannot exist. Harmless as prose, but it means
   **`SKILL.md`'s examples are not a reliable spec for the pack id format** — read
   `generate_entity_id` itself when re-keying.

### The precedent this design follows — it is already the house pattern

`store.py:309-311` already solves exactly this for the graph:

```sql
FOREIGN KEY(caller_symbol_id) REFERENCES symbols(id) ON DELETE CASCADE,
FOREIGN KEY(callee_symbol_id) REFERENCES symbols(id) ON DELETE SET NULL,
FOREIGN KEY(source_ref_id)    REFERENCES symbol_refs(id) ON DELETE SET NULL
```

plus `symbol_refs.chunk_id → ON DELETE SET NULL` (`store.py:285`). The callee case keeps a
**durable name** (`callee_name`) beside the **advisory id**, which is why unresolved edges stay
usable at 0.30 confidence instead of vanishing. `graph_edges` already treats the symbol id as a
**cache, not as identity**. SPEC-3 generalizes that.

Likewise fact-graph already separates the three concerns and should be credited for it:
identity excludes line and body (`SKILL.md:912-932`), `line_range` is a separate evidence field
(`SKILL.md:818, 976`), and `content_hash` / `snippet_hash` exist **specifically so drift is
detectable without being identity-breaking** (`SKILL.md:809, 996-1020, 1271-1274`; line 993:
*"The `content_hash` enables drift detection by citation-validator skill."*).

---

## S3.1 `anchor_key` — code identity. **Lives in Layer 0.**

```
anchor_key = "ak1:" + sha256(
    language ␟ entity_class ␟ qualified_name ␟ normalized_relative_path
).hexdigest()[:16]
```

where `␟` is **U+001F UNIT SEPARATOR**.

**Includes** path. **Excludes** line numbers, body text, and domain.

**DECIDED 2026-08-24: `anchor_key` is a Layer-0 concern**, not a GR-store-local convenience. It
becomes a computed column on `symbols`, produced by the shared module in §S3.5, and it discharges
`fact-graph-decision.md` §5a.4 residue **(c)** (*"content-hashed, position-independent entity IDs
— deterministic, Layer-0 side"*) and §7 open question #6.

⚠️ **SCOPE CLARIFICATION 2026-08-25 (decided: option 3) — `anchor_key` is ADDITIVE; `symbols.id`
is NOT re-keyed by this plan.** `anchor_key` is a **new computed column beside** the primary key.
`symbols.id` remains `f"{language}:{relative_path}:{qualified}:{start_line}"`
(`extractors.py:1112-1115`), and five surfaces key off it — the PK (`store.py:209`),
`graph_edges.caller_symbol_id`/`callee_symbol_id` (`:309`/`:310`),
`symbol_facts.subject_symbol_id` (`:359`), and plain columns `chunks.symbol_id` (`:216`) and
`symbol_refs.enclosing_symbol_id` (`:278`). So an edit above a symbol still mints a new id and
cascades its edges and facts away. **That is safe here by design:** §S3.3 makes `anchor_key`
**advisory only, never an FK target** — `(relative_path, start_line, end_line)` is the durable
anchor and `gr_id` is the sole FK target, so a stale link is *recoverable* rather than dead.
**Re-keying `symbols.id` is filed as unowned Layer-0 work — piece (e) in
`fact-graph-decision.md` §5a.6/§5a.6.1 — which this plan DECLARES A DEPENDENCY ON and does not
own.** It does not gate Milestone 1.

⚠️ **RE-SCOPED 2026-08-25 by D7 — this paragraph previously over-claimed.** It read: *"It re-keys
`symbols` **and** the fact-graph pack format, so it must ride the pack-emitter shim (residue (a))
so the 13 Phase-0 consumers see one migration, not two."* **The pack-format half is a FUTURE
obligation, not a present dependency.** Verified: `.claude/skills/fact-graph/SKILL.md` contains
**zero** references to `legacylift-search`, `index.sqlite` or `symbols` — fact-graph mints its own
ids from its own snippet (`:912`, formula at `:942-947`), so **adding `anchor_key` to `symbols` is
invisible to fact-graph and to all 13 consumers.** And no Layer-0 pack emitter exists (none of the
15 CLI commands writes `legacylift-docs/context/`). **Correct statement:** `anchor_key` ships
**additively in Milestone 1 and breaks nothing**; *if and when* a Layer-0-backed pack emitter is
built, it must carry the §S3.1 and §S3.6 re-keying as **one** consumer migration. That obligation
belongs to residue **(a)**, which is a milestone on no plan — see `fact-graph-decision.md` §5a.5.

### Four mandatory departures from the existing formulas, each fixing a concrete defect

1. **The delimiter must be a character that cannot occur in the inputs.** Today's formulas join
   with `:` (`SKILL.md:930`, `extractors.py:1112`), but `qualified_name` and `relative_path` both
   contain `:`, `.` and `/`. So `a:b` + `c` and `a` + `b:c` hash identically. **Use `\x1f`.** No
   validated identifier or path component may contain it.
2. **Hash the COARSE `entity_class`, never the extractor's fine-grained `kind`.** fact-graph has
   this **backwards**: it coarsens `class`/`interface` → `cs` for the *display prefix* but hashes
   the **raw** `entity_type` (`SKILL.md:920-932`). The stable value sits in the volatile position
   and the volatile value sits in the hash, so any extractor improvement that reclassifies a
   symbol churns identity. `entity_class` is a **closed, coarse enum**; the fine `kind` stays a
   plain column.
3. **Normalize path separators to `/`; preserve case.** This repo runs on Windows and analyzes
   repos authored on Linux — without normalization the same file hashes differently by host.
   Do **not** case-fold: that is wrong on case-sensitive filesystems. (Same normalization as
   §S2.2, which also strips a leading `./`.)
4. **16 hex characters (64 bits), not 12.** 48 bits at 100k entities is roughly a 1-in-55,000
   collision chance. For a store where a collision silently merges two signed-off requirements
   that is too thin. 64 bits puts it near 3x10^-10.

The `ak1:` prefix is mandatory: it lets the formula evolve unambiguously. The repo currently has
no such mechanism — `SCHEMA_VERSION = "1"` is written but never compared (deferred question **D3**).

### S3.1.1 The FILE grain — added 2026-08-26 (`PR-82`)

**Everything above specifies `anchor_key` for Layer-0 *symbols*.** The GR store needs a second
grain: a citation whose line range matches no symbol must still anchor somewhere, and the ExecPlan's
Step 6a makes that fallback **total** — there is no tier beneath it. That grain was never specified
here, so two of its three non-path components had no defined value and `language` had none at all.
Specify all three:

```
file-level anchor_key = "ak1:" + sha256(
    "" ␟ "file" ␟ "" ␟ normalized_relative_path
).hexdigest()[:16]
```

**`language` is the constant empty string, not a lookup.** Two reasons, and the second is the
load-bearing one:

1. **It carries no information at this grain.** `entity_class` is fixed at `file` and
   `qualified_name` at `''`, so the only varying input is the path — which determines the
   extension, which determines the language. Measured across both NNG indexes and `ctcm-api`: zero
   files carry more than one symbol language and zero symbols disagree with their file's language.
   By construction, `discovery.py` assigns exactly one `lang_spec.key` per file.
2. **Any lookup makes the key depend on index state.** `repo_files.language` exists only for files
   the indexer accepted, and `detect_language` rejects every unrecognised extension outright
   (`languages.py`, `discovery.py:77-79`), so a file-level anchor read from either source would key
   differently before and after an `index` run — and for the `unresolved` case, a path not in the
   working tree, no source exists at all. `dedupe_key` would become a function of whether someone
   had run the indexer. That is the same class of failure §S3.6's retag invariant exists to
   prevent, arriving through a door §S3.6 does not cover. **A constant cannot churn.**

**This `""` is a constant for a whole class, not an absence encoding.** Every file-level anchor uses
it, without exception, so there is no second meaning it could be confused with. Do not "fix" it by
reading it as the empty-string defect the ExecPlan's `dedupe_key` rules exist to prevent — that rule
governs a value that is *sometimes* missing, and this one never is.

`language` is retained in the symbol-grain formula unchanged. It is arguably redundant there too, on
the same measurement, but that formula is settled and re-deriving it buys nothing.

### S3.1.2 `entity_class` is DECLARED at extraction, not derived from `kind` — added 2026-08-26 (`PR-83`)

The seven-value set is closed — `type`, `function`, `field`, `table`, `column`, `file`, `other` —
and departure 2 above requires the coarse class in the hash rather than the raw `kind`. What was
never specified is **how a `kind` becomes a class**, and that mapping has exactly the same churn
properties as the closed set: changing it re-keys every anchor derived from it.

**It cannot be a lookup table, because the `kind` domain is not enumerable from our source.**
`xml_extractor.py:208` mints a kind as `f"hibernate_{tag}"` from the client's own Hibernate mapping
element, and `:252` as the client's Spring Webflow state element name. A client's framework
vocabulary authors `kind` values no table can contain. The closed half is enumerable — 36
`definition_node_kinds` across seven language profiles in `profiles/extractors.json`, plus
hand-written `foreign_key`, `fallback_definition` and `create_temp_table` — but the open half is
open by construction.

**So each extractor declares the class of what it emits, and `symbols.entity_class` is a stored
column.** An extractor already knows: `xml_extractor.py` knows a Hibernate `<property>` is a
`field` and does not need a downstream table to infer it from the string `hibernate_property`. This
is `NORMATIVE PRINCIPLE-1` applied literally — classify once, at the point of maximum evidence —
and it is the same move the ExecPlan makes for `rule_class`. Three declaration sites:

- **`profiles/extractors.json`** — a class per `definition_node_kinds` entry, per language. Closed
  and testable: a new language declares its own, and a new node kind fails the build until
  classified.
- **Framework extractors** — declared at the symbol-construction site.
- **The regex fallback** — `other` by construction, since the kind genuinely is unknown.

**The default is `other` for the OPEN half only, and promoting a kind out of `other` later is an
`ak2:` event.** Write that where the mapping lives. It is what makes the open half safe: an
unrecognised framework's symbols land in `other` honestly rather than being guessed into a class
that a later "improvement" would change.

⚠️ **Do not extend that default to the closed half — added 2026-08-28 (`PR-108`).** The closed half
is enumerable, so leaving an entry unclassified and letting it fall to `other` is not an honest
default, it is an unrecorded classification. Measured on disk, 16 of the 36 `definition_node_kinds`
are the mainstream type and member kinds, and sending them to `other` destroys the discrimination
this section's own departure-2 argument rests on: `SecUser.StatusEnum` collides as
`enum_declaration` and `field_declaration`, and `FileDistributedCache.IsConnected` as
`property_declaration` and `method_declaration`, and both pairs re-collapse. **Every
`definition_node_kinds` entry carries a declared class.** The closed half classifies as:

| kind | class | kind | class |
|---|---|---|---|
| `class_declaration`, `class_definition`, `interface_declaration`, `struct_declaration`, `enum_declaration`, `record_declaration`, `type_alias_declaration` | `type` | `spring_bean`, `hibernate_class_mapping` | `type` |
| `method_declaration`, `method_definition`, `constructor_declaration`, `abstract_method_signature`, `function_declaration`, `function_definition`, `generator_function_declaration` | `function` | COBOL `paragraph`, `section_header`, `procedure_division`; SQL `create_procedure`, `create_function`, `create_trigger_statement` | `function` |
| `field_declaration`, **`property_declaration`**, `variable_declaration`, `lexical_declaration`, `variable_declarator` | `field` | COBOL `data_description_entry`; the `hibernate_{tag}` children | `field` |
| SQL `create_table`, `create_view`, `view_definition`, `table_definition`, `create_temp_table` | `table` | Python `decorated_definition`; SQL `create_index_statement`; COBOL `program_id_paragraph`, `file_description_entry`, `linkage_section`, `working_storage_section`; every Webflow state, `webflow_flow`, `xml_document`; `fallback_definition` | `other` |

`property_declaration` is the only ambiguous entry and the collision measurement decides it: it
reads as a member but is implemented as accessors, and mapping it to `function` re-collapses the
very `IsConnected` collision cited above. It is state, so it classifies as `field`.

**Note the error carried from the paragraph above and corrected here:** `foreign_key` is listed
there among the hand-written kinds, and it is not a symbol kind at all — `extractors.py:1618` and
`:1722` emit it into `symbol_refs`, which has no `entity_class` column. Only `fallback_definition`
and `create_temp_table` in that sentence are symbols.

**Why declaration rather than a central table, stated as the property that matters:** a change to
one framework extractor's classification touches only that framework's symbols, which are
re-extracted anyway when the extractor changes — so it rides §S3.3's existing re-resolution path
(recompute both dedupe keys, stamp `gr_citation.provenance = 'repaired'`). A change to a central
table potentially moves everything and needs a prefix bump. **Bounded re-keys have machinery;
global ones do not.**

**`column` is currently unreachable** — no extractor emits a column symbol today. It stays in the
closed set for the same reason `file` does: a value appended later is not a free extension.

**Do not merge this with the semantic-typing pass.** `fact-graph-explanation.md` §9.8 (residue (b))
derives `dto`, `controller`, `service`, `repository`, `endpoint` — architectural **roles**, a
different axis — and is explicitly inference-bearing, with `service` needing a heuristic flagged
under PRINCIPLE-1. **An inferred value can never be an `anchor_key` input.** The two enums look
alike and are not.

---

## S3.2 `content_hash` — change and clone detection. Two grains.

```
content_hash = "ch1:" + sha256(normalized_body).hexdigest()[:16]
```

**Includes** body text. **Excludes** path, name, language, line numbers, and domain.

`normalized_body`: line endings to `\n`, trailing whitespace stripped per line, leading and
trailing blank lines dropped. **Comments are KEPT** — a rule may be cited *to* a comment, so a
comment change is real drift. (If near-clone detection is ever wanted, add a second coarser hash
then. Do not build it now.)

**Two grains, both required:**

| Grain | Lives on | Covers |
|---|---|---|
| **Entity-level** | the Layer-0 `symbols` row | did this entity's code change; is it a clone of another entity |
| **Span-level** | each GR **citation** row | the exact cited lines — the input to §S3.3 tier 2 |

### The 2x2 this yields on every reindex

Because `anchor_key` includes path and excludes body while `content_hash` includes body and
excludes path, the pair is jointly informative:

| same `anchor_key` | same `content_hash` | meaning | action |
|---|---|---|---|
| yes | yes | unchanged | citation still valid |
| yes | no | **drift** | re-verify the requirement against the changed code |
| no | yes | **clone or move** | see below |
| no | no | unrelated | — |

**This is why keeping `relative_path` in `anchor_key` costs nothing.** Two byte-identical methods
in different files are correctly **distinct** entities. And a **move** is still recoverable: if an
`anchor_key` disappears in the same reindex in which a new `anchor_key` with the same
`content_hash` appears, that is a rename/move and the citation can be **auto-repaired**. A clone
has no vanished predecessor; a move does. The two are distinguishable, so path-in-identity does
not forfeit move tracking.

---

## S3.3 The four GR keys — separated by which question they answer

A requirement is **not** an entity. It outlives the code it was mined from, and under **Q5** its
text is **edited by a human during review**. Therefore a GR's identity can never be a hash of its
own content.

| Key | Answers | Derived from | Mutable | FK target |
|---|---|---|---|---|
| `gr_id` | which requirement is this | **nothing** — surrogate assigned once at creation (ULID) | **never** | **yes — the only one** |
| `dedupe_key` | have I extracted this rule before | §S3.3.1 below | recomputed on every write | **never** |
| `anchor_key` | which code entity does this cite | §S3.1 | stable across edits and retags | advisory only |
| `content_hash` | has the cited code changed; is it a clone | §S3.2 | recomputed on reindex | no |

**`gr_id` is a surrogate on purpose.** If identity were content-derived, approving an SME's
wording edit would mint a new requirement and **destroy the sign-off**. That is fatal to Q5.

**Citations are a child table**, so one requirement may cite many places and each citation carries
its own drift state:

```
gr_citation(gr_id, anchor_key, relative_path, start_line, end_line, content_hash, verified_at, provenance)
```

`(relative_path, start_line, end_line)` is the **durable anchor**; `anchor_key` is an **advisory
soft link**, refreshed by a resolution pass. A path plus line range always still points
*somewhere*, so it is wrong in a way that is **detectable and repairable** by re-reading the
source — which is exactly what the existing `citation-validator` skill does. An id, by contrast,
either matches or is gone: no partial answer, nothing to repair from. **The distinction is not
stable vs unstable, it is recoverable vs unrecoverable.**

### S3.3.1 `dedupe_key` — DECIDED 2026-08-24 (option E, tiered composite)

```
dedupe_key = "dk1:" + sha256(
    sorted(anchor_keys) ␟ rule_class ␟ pattern ␟ discriminator
).hexdigest()[:16]

discriminator =
    canonical structured_body form                  if a typed body exists   (tier 1)
    else sorted(span-level citation content_hash set)                        (tier 2)
    else NULL                                                                (tier 3)
```

Tier 1 uses Q3c's typed bodies, which are parsed rather than prose: the normalized formula for
`formula`, the `(from, to, trigger)` triple for `state_transition`, the input expressions for
`decision_table`. Tier 2 — the **span-level content hash of the cited code** — is fully
deterministic, involves no LLM, and discriminates two rules mined from different line ranges of
the same method, while two runs citing the same lines produce the same key.

**`dedupe_key` is built ONLY from extractor-owned, domain-independent fields.** Two consequences
that are not obvious and must not be "improved" away:

- **`statement` is EXCLUDED because it is SME-mutable.** Dedupe compares extraction output to
  extraction output. A key containing text an SME edits during review no longer matches what the
  extractor produces next run — so **the reviewed rules are exactly the ones that duplicate**.
  The more human work invested, the more likely it duplicates. Backwards, and fatal to Q5.
- **`subject` is EXCLUDED because it is domain-derived, and it is also strictly dominated.** Q3d
  derives `subject` from `file_domains`, so including it puts **domain-retag churn back into the
  hash**. And `anchor_key` already contains `relative_path` while `file_domains` maps path to
  domain, so `subject` is **functionally determined by the anchor**: zero added discrimination,
  all of the churn.

**Rejected alternatives, with the reason each fails:**

| Option | Why rejected |
|---|---|
| **A** — anchors only | one method routinely yields several rules (a validation, a calculation, a state transition); all collide |
| **B** — anchors + `rule_class` + `pattern` | fully stable, but still collides on the dominant real case: two different `B-COND` rules in one dense validator |
| **C** — B + normalized `as_built` | ⚠️ **the naive choice.** `as_built` is extractor-owned so it passes the SME test, but it is free LLM prose: re-extracting unchanged code yields a paraphrase, so the key changes **every run regardless of SME activity**. Duplicates unconditionally — worse than B |
| **D** — B + `structured_body` only | strongest discriminator where a typed body exists, but only four body types exist and not every rule has one; needs tier 2 beneath it |

---

## S3.4 Deduplication is TWO-STAGE, and stage 2 never auto-merges

**DECIDED 2026-08-24.** The two failure modes of any exact key are **not symmetric**:

- **false-distinct** (a duplicate row) is **visible** and a reviewer merges it — recoverable;
- **false-same** (an over-merge) is **invisible**: a real rule silently never enters the corpus,
  and coverage is the measured selling point (§S2.6).

So the exact key is deliberately biased toward **under-merging**, and the residue is recovered by
a pass that never merges on its own:

1. **Exact `dedupe_key` match** → same rule, **merge automatically**.
2. **No match** → candidate search via **Q6's dedicated GR Chroma collection** (semantic) plus
   **§S2.2's line-range-intersection rule** on shared anchors → surfaced as **review candidates**.
   **Never silently merged. No similarity threshold auto-merges anything, at any disposition.**

**This is the concrete reason Q6 is milestone-1 scope** rather than a nice-to-have: without stage
2, stage 1's deliberate under-merging has no backstop. It is also why §S2.2's *tolerant* overlap
rule belongs here — exact range equality is right for a **key**, and intersection is right for a
**candidate search**; they are different jobs and both are needed.

---

## S3.5 One shared module — the "shared" half of "stable, shared identity"

All three consumers MUST call one canonical implementation, e.g.
`src/legacylift_search/identity.py`, exporting at least:

```
anchor_key(language, entity_class, qualified_name, relative_path) -> str
content_hash(body_text) -> str
normalize_path(path) -> str
entity_class_of(kind) -> str     # the closed coarse mapping
```

Called by **the index**, **the pack emitter**, and **the GR store**. If each computes its own, they
cannot join and the identity is not shared — which is the whole point.

---

## S3.6 Domain retagging — the invariant, stated as a test

**No key defined in SPEC-3 takes a domain as input.** `domain` is a plain column; a retag is
`UPDATE ... SET domain = ?` on one row. Nothing re-keys, no row is orphaned, no citation breaks.

**Required regression test:** re-run `tag-domains` with a changed `domains.json` and assert that
**every** `anchor_key`, `content_hash`, and `dedupe_key` in the store is byte-identical before and
after. This test is the executable form of the invariant.

⚠️ **This differs from fact-graph's current id format**, which puts `domain` in the visible id
prefix (`SKILL.md:912`) — so a retag today silently churns every entity id string in that graph,
since domain tagging is a separately re-runnable Layer-1 pass. **RE-SCOPED 2026-08-25 by D7:**
this is **not** a breaking change for the 13 Phase-0 consumers *now*, because SPEC-3's keys live
in Layer 0 and fact-graph reads no Layer-0 table (see the §S3.1 note). It becomes a consumer
migration only **if** a Layer-0-backed pack emitter is built — residue **(a)** — and then §S3.1
and §S3.6 must ride it together as one migration.

---

## S3.7 Known gap — none of this has ever been exercised

fact-graph regenerates its JSON **wholesale** each run; it is not an incrementally maintained
store. So its position-independent ids are stable **by construction and untested** — nothing has
ever run them through an edit-and-reindex cycle. SPEC-3 is the first design here that will
actually be exercised that way, so the §S3.6 regression test and the drift 2x2 in §S3.2 are the
load-bearing verification, not documentation.

---

# Environment notes / gotchas (carried from prior sessions)

- The `legacylift-search` on PATH is a **broken shim** — use the venv binary at
  `tools/legacylift_search/.venv`.
- The `.venv` is missing the declared `aws` extra (boto3), so **no `provider=api` repo can
  be re-indexed** until it is installed. Blocks any at-scale Bedrock run.
- Clearing `analysis/` does **not** clear domain tagging — `knowledge.sqlite` lives
  outside the index dir. Re-run `tag-domains` before `map`.
- T-SQL `uses_table` reports **aliases** as datastores (affects Q3h).
- The index binds call edges at confidence 0.7/0.85 or not at all, and emits **no
  dispatch edges** — framework-config dispatch must be resolved by `map`.
- Workflow scripts in this repo fail on non-ASCII (approval-guard) and receive `args` as
  a JSON string; run an ASCII-copy + args-shim from the scratchpad.

# Related plans

⚠️ **The ExecPlan authored from this file is `docs/exec-plans/active/reqs-to-data-store.md`
(2026-08-25).** Implement from that; it is self-contained. This file is the audit trail.


- `docs/exec-plans/active/semantic-code-search-graph-index.md` — the governing Layer-0
  plan. M22–25 shipped; **M21 (index vs fact-graph value comparison) is still open** and
  gates the fact-graph decision (see Q7). M20 Part 2 and M18 are paused behind M21.
- `docs/exec-plans/active/code-graph-construction.md` — how Layer 0 builds symbols,
  edges, facts, and domain tags today. Reference for any Layer-0 capability claim.
- `docs/exec-plans/pending/fact-graph-decision.md` — the Layer-0/Layer-1 split, Options
  A/B/C, §5a.4's four residual pieces (only (d) inferred facts needs an LLM), and §7's
  six open sign-off questions. Directly coupled to Q7.
- `docs/exec-plans/pending/fact-graph-explanation.md` — fact-graph's full data model.
- `docs/exec-plans/pending/hosted-data-store.md` — AWS-hosted vector/graph store options.
  Deliberately deferred by Q4.
- `docs/exec-plans/completed/req-extraction.md` — prior characterization of the current
  format: "Markdown (`BUSINESS_RULES.md`) + loose `topology.json`; **the workflow
  enforces JSON schemas internally but discards them on write**" (`:41`).
- `docs/exec-plans/completed/domain-enhancements-plan.md` — authoritative for standing
  domain design decisions (`domains.json` is the one canonical domain set).
