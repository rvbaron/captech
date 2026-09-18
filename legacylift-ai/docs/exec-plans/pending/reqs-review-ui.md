# A review experience for generated requirements

See [reqs-review-ui-additional-info.md](reqs-review-ui-additional-info.md)

**Status: a read-only Milestone 1 is BUILT, in [`platform-ui/`](../../../platform-ui/) — its
[README](../../../platform-ui/README.md) is the definitive record of what exists, how to run it,
and what the data forced.** Started 2026-09-11, after the store plan's Milestone 1 completed on
2026-09-10. The interview below was held; its answers are the *Decisions of record* section that
follows, and by deliberate choice no conforming ExecPlan was written for M1 — the decisions live
here and the build detail lives in the README. Anything past read-only (editing, state
transitions, merge resolution, bulk operations) is still undesigned, and *What this plan will have
to decide* still governs it.

This repository's ExecPlan conventions live in [`docs/exec-plan.md`](../../exec-plan.md). This file is
**not a conforming ExecPlan** — no Plan of Work, no Concrete Steps, no acceptance criteria. That was
a decision rather than an omission, taken against a five-day demo deadline.

## Decisions of record — Milestone 1, 2026-09-11

Fifteen answers from the interview. They are settled for M1 and should not be re-litigated without
a reason the README's measurements do not already cover.

| Question | Answer |
|---|---|
| Surface | A local web app: Angular 21 LTS + Material front-end, .NET 10 minimal API. Not the existing React app in `main:web/frontend`, whose brand tokens and logo were reused. |
| Angular version | 21 LTS, not 22 — 22 needs Node ≥ 22.22.3 and the machine runs 22.17.1. |
| Location | A new `platform-ui/` folder: `api/`, `web/`, `tools/`, `data/`. |
| Data access | A byte copy of `knowledge.sqlite` under `platform-ui/data/`, opened read-only. Never the live store, which is Milestone 1.5's frozen 379/117 pair. |
| Client data in git | `platform-ui/data/` is gitignored in full. `tools/prepare_data.py` rebuilds it. |
| Project shape | One project (NNG) with a system switcher over its two systems, matching the analysis tree. `customer.ple.nng.db.ETSPii` has no `gr` tables at all, so its Requirements nav is disabled and its overview says why. |
| Code viewer | Cited line ranges only, pre-extracted with eight lines of context. Whole client files never leave the analysis tree. |
| Detail page | Findings highlighted by `span`, `statement` against `statement_extracted`, scenarios, edge cases, merge candidates from both sides. |
| Edit affordance | No inputs anywhere. Read-only values, plus an SME-progress meter driven by the three extractor-forbidden fields — which reads 0% on this corpus, honestly. |
| Reviewer identity | Not captured, because nothing transitions state. The binding requirement above applies to the first write path, which M1 does not open. |
| Approval gate | Previewed, never computed. The detail page says what `set_state` would refuse and why. |
| Missing artifacts | `BUSINESS_RULES.md` and `DATA_OBJECTS.md` are the stale June copies, banner-flagged as predating the store. `Recommendation` is an honest empty state — `/modernize-brief` has never been run for either system. |
| Diagrams | The four `.mmd` fragments render natively, brand-themed; `TOPOLOGY.html` is offered in a frame on its own tab. |
| Branch | `feature/reqs-to-data-store`, alongside the store work that produced the data. |
| Bulk operations, drift review, markdown-as-review-surface, multi-reviewer | Still undecided. M1 does not touch them. |

Two findings from building it are recorded in the README because they changed the code and would
otherwise be re-derived: **a `evaluated = 0` finding is not a violation** (24 of the store's 70
`ERROR` rows are checks that could not run, so 44 rules are blocked rather than 45), and **only 41
of 287 findings carry a `span`**, so inline highlighting is a minority case and the statement-wide
majority is listed instead.

## Why this is a separate plan

`active/reqs-to-data-store.md` builds a store that holds human judgment and protects it across
re-extraction. It ships exactly one write command, `requirements set-field`, and that command is
scoped by what the store's own acceptance tests need — proving that a hand-edited `statement`
survives a re-ingest, and making the SME-only fill rates in `requirements stats` something other
than structurally zero. It is not a review tool and the plan says so in as many words.

Actually reviewing a corpus is a different problem. On the reference corpus the numbers are 470
and 815 rules over one system; at that scale a reviewer needs to be steered to the next decision,
not handed a table. Nothing about that is required to prove the store works, and building it
inside Milestone 1 would put a user interface on the critical path of "does the merge merge."

## What is already settled, and must not be re-decided here

These come from the store plan and its design draft
(`pending/reqs-to-data-store-plan-draft.md`). Treat them as given.

**The approval gate lives in the store, never in the client.** `draft → approved` requires zero
`ERROR` findings, and the check is a guard inside the single `set_state` function. A UI may
*preview* the gate — grey out the button, show the blocking findings — but it must call
`set_state` and be prepared for a refusal. Any UI that computes approvability itself has forked
the rule.

**`statement != statement_extracted` is the only definition of "a human edited this."** It is a
single equality over two columns. A UI must not invent a second signal (a dirty flag, an edit
timestamp, a diff heuristic), because the merge in the store plan's Step 6 keys off exactly that
equality and a second source of truth would diverge from it.

**`statement_extracted` is read-only to every human path.** It is extractor-owned. Showing it is
the whole point — it is what lets a reviewer see what the extractor would now say about a rule
they have already reworded — but it is never editable.

**Which fields a human may write**, from the store plan's Step 8: `statement`, `rationale`,
`fit_criterion`, `enforcement_level`, `assumptions`, `confidence_intent`, `modality` /
`modality_confirmed`, `disposition`. Everything else on `gr` is extractor- or store-owned.
`rationale`, `fit_criterion` and `enforcement_level` are extractor-**forbidden**, so a non-NULL
value in them is human by definition and their fill rate is the honest measure of review
progress.

**Two fields are two fields on purpose.** `as_built` is descriptive and cited — what the code
does. `statement` is normative — what the business requires. Each carries its own confidence
(`confidence_extraction`, `confidence_intent`). Any UI that shows one field where the schema has
two undoes the central design decision of the store.

**Findings are stored, identified and re-derived, not accumulated.** `gr_finding` rows are deleted
and re-inserted per requirement on every validation, inside one transaction, so a finding that no
longer fires disappears. Findings carry stable identifiers (`V-KW-02` and the other twenty-seven
of `NORMATIVE SPEC-1` §S1.6) and a `span` giving the character range within `statement` that
tripped the check. A UI should render findings inline against the offending words; the `span` is
there for that.

**`set_state` and `import_records` are the only writers of `gr.state`.** A test asserts the set is
complete. Do not add a third.

**Reviewer identity is mandatory, and this is a binding requirement on whatever gets built here.**
`set_state` takes a **required** `reviewer` argument with no default and writes it to
`gr.reviewed_by`; `gr.owner` records who is accountable for the requirement. Any UI must therefore
establish who the viewer is *before* offering a state transition, and must pass that identity
through — it cannot approve anonymously, cannot substitute a placeholder, and cannot defer the
question to a later release. The reason is that identity is the only field in the store that cannot
be reconstructed retroactively: every other gap can be backfilled by re-running something, but
"who approved this" is gone the moment it is not captured. Whatever the surface turns out to be
(terminal, local web app, report, Artifact), the identity question has to be answered by its
design, not bolted on.

## What this plan will have to decide

None of these are settled. They are the interview's agenda.

- **Surface.** A terminal UI, a local web app served by the CLI, a static HTML report regenerated
  from the store, or an Artifact published per corpus. The store is SQLite on an analyst's laptop
  and the analyzed repository is often a client's, which constrains anything hosted.
- **Multi-reviewer or single.** Reviewer *identity* is settled and mandatory (above). What is not
  settled is everything built on top of it: assignment, queues per reviewer, two-reviewer
  agreement, and whether `owner` and `reviewed_by` are ever different people in practice.
- **Work ordering.** What a reviewer sees first. Candidate signals already in the store: `priority`
  (`P0`/`P1`/`P2`), `confidence_extraction`, `sme_question` presence, `suspected_defect` presence,
  `ERROR` finding count, and drift (a citation whose `content_hash` changed since `verified_at`).
- **Stage-two dedupe candidates.** The store plan's merge deliberately under-merges and surfaces
  near-duplicates as review candidates that never auto-merge. They live in `gr_merge_candidate`
  with a `resolution` of `merged` / `distinct` / `unresolved`, and `requirements list --candidates`
  already lists the unresolved ones. What is undesigned is the *act* of merging two records in a
  UI — which `gr_id` survives, what happens to the loser's citations and findings, and how a
  `distinct` judgement is captured without a reviewer having to reason about keys.
- **Drift-flagged candidates.** A candidate with `reason = 'drift'` means the same rule was
  recognised by its anchors but its cited code changed. That is a different reviewer task from a
  semantic near-duplicate and probably deserves a different screen.
- **Bulk operations.** Approving 470 rules one at a time is not a workflow, but bulk approval
  through a gate that exists to be read is a way to launder the gate. Needs a deliberate answer.
- **Drift review.** When cited code changes, the requirement may no longer describe it. The store
  can detect this (Step 1's drift-versus-clone matrix); what a reviewer is asked to do about it is
  undesigned.
- **Whether markdown export is the review surface.** The store plan already generates
  `BUSINESS_RULES.md` from the store and a sorted JSONL export for pull-request review. A pull
  request may be a better review venue than any UI, in which case this milestone is much smaller
  than it looks. Answer this one first — it is the question that sizes the rest.

## Dependencies

- **Hard:** Milestone 1 of `active/reqs-to-data-store.md`, accepted. The schema, the validator, the
  merge and `set_state` must all exist and be tested.
- **Soft:** Milestone 1.5 of that plan. Knowing whether the new pipeline's corpus is 200 rules or
  900 changes what a review surface has to cope with.
- **Unrelated:** Milestones 2 and 3 of that plan. A story producer and a vocabulary layer add
  record kinds this UI would eventually show, but neither gates it.

## Decision Log

- Decision: the review experience is deferred out of the store plan into this one, and the store
  plan ships only `requirements set-field`.
  Rationale: Milestone 1's acceptance turns on a human edit surviving re-extraction, so some write
  path must exist there or the headline test cannot be set up. But a review *experience* is a
  separate product, and putting a UI on the critical path of "does the merge work" would couple two
  unrelated risks.
  Date/Author: 2026-08-25, Darrell Norton with Claude.
